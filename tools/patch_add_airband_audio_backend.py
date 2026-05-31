#!/usr/bin/env python3
import re
from pathlib import Path

SRC = Path("dump1090.c")
s = SRC.read_text(encoding="utf-8")

if "AIRBAND_AUDIO_SAMPLE_RATE" in s:
    print("Airband audio backend is already present.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Add airband state fields to Modes.
# ---------------------------------------------------------------------------

state_pattern = re.compile(r'int\s+stop\s*;\s*/\*\s*Networking\s*\*/')

state_replacement = r'''int stop;

    /* Airband AM listening mode. */
    pthread_mutex_t airband_mutex;
    int airband_requested;
    int airband_active;
    int airband_pending;
    long long airband_requested_freq;
    long long airband_freq;
    char airband_error[128];

    int16_t *airband_pcm;
    unsigned int airband_pcm_capacity;
    unsigned int airband_pcm_write;
    unsigned int airband_pcm_count;

    int airband_decimation_count;
    long long airband_decimation_sum;
    double airband_dc;

    /* Networking */'''

s, count = state_pattern.subn(state_replacement, s, count=1)
if count != 1:
    raise SystemExit("Could not add airband fields after Modes.stop.")

# ---------------------------------------------------------------------------
# Initialize airband state.
# ---------------------------------------------------------------------------

mutex_anchor = "pthread_cond_init(&Modes.data_cond, NULL);"

if mutex_anchor not in s:
    raise SystemExit("Could not find modesInit mutex initialization.")

s = s.replace(
    mutex_anchor,
    mutex_anchor + "\n    pthread_mutex_init(&Modes.airband_mutex, NULL);",
    1
)

exit_anchor = "Modes.exit = 0;"

init_code = r'''
    Modes.airband_requested = 0;
    Modes.airband_active = 0;
    Modes.airband_pending = 0;
    Modes.airband_requested_freq = MODES_DEFAULT_FREQ;
    Modes.airband_freq = MODES_DEFAULT_FREQ;
    Modes.airband_error[0] = '\0';

    Modes.airband_pcm_capacity = AIRBAND_AUDIO_SAMPLE_RATE * 5;
    Modes.airband_pcm = calloc(Modes.airband_pcm_capacity, sizeof(int16_t));
    if (Modes.airband_pcm == NULL) {
        fprintf(stderr, "Out of memory allocating airband PCM buffer\n");
        exit(1);
    }

    Modes.airband_pcm_write = 0;
    Modes.airband_pcm_count = 0;
    Modes.airband_decimation_count = 0;
    Modes.airband_decimation_sum = 0;
    Modes.airband_dc = 0.0;
'''

if exit_anchor not in s:
    raise SystemExit("Could not find Modes.exit initialization.")

# Constants must be inserted before modesInit() uses them.
constants_anchor = "#define MODES_NOTUSED(V) ((void) V)"

constants = r'''
#define AIRBAND_AUDIO_SAMPLE_RATE 16000
#define AIRBAND_AUDIO_DECIMATION (MODES_DEFAULT_RATE / AIRBAND_AUDIO_SAMPLE_RATE)
#define AIRBAND_AUDIO_RF_BANDWIDTH 200000
#define AIRBAND_MIN_FREQ_HZ 118000000LL
#define AIRBAND_MAX_FREQ_HZ 136975000LL
'''

if constants_anchor not in s:
    raise SystemExit("Could not find constant insertion point.")

s = s.replace(constants_anchor, constants_anchor + constants, 1)
s = s.replace(exit_anchor, exit_anchor + init_code, 1)

# ---------------------------------------------------------------------------
# Add RF-switching and AM envelope-demodulation functions before reader thread.
# ---------------------------------------------------------------------------

reader_comment = "/* We use a thread reading data in background"

if reader_comment not in s:
    raise SystemExit("Could not find Pluto reader-thread insertion point.")

audio_functions = r'''
/* ========================== Airband AM listening ========================== */

static int airbandTuneRadio(long long frequency, long long bandwidth) {
    struct iio_device *phy;
    struct iio_channel *rx_channel;
    struct iio_channel *lo_channel;
    int result;

    phy = iio_context_find_device(Modes.ctx, "ad9361-phy");
    if (phy == NULL) {
        return -1;
    }

    rx_channel = iio_device_find_channel(phy, "voltage0", false);
    lo_channel = iio_device_find_channel(phy, "altvoltage0", true);

    if (rx_channel == NULL || lo_channel == NULL) {
        return -1;
    }

    result = iio_channel_attr_write_longlong(
        rx_channel, "rf_bandwidth", bandwidth
    );
    if (result < 0) {
        return result;
    }

    result = iio_channel_attr_write_longlong(
        lo_channel, "frequency", frequency
    );
    if (result < 0) {
        return result;
    }

    return 0;
}

static void airbandResetAudio(void) {
    pthread_mutex_lock(&Modes.airband_mutex);

    Modes.airband_pcm_write = 0;
    Modes.airband_pcm_count = 0;
    Modes.airband_decimation_count = 0;
    Modes.airband_decimation_sum = 0;
    Modes.airband_dc = 0.0;

    pthread_mutex_unlock(&Modes.airband_mutex);
}

static void airbandRequestMode(int enabled, long long frequency) {
    pthread_mutex_lock(&Modes.airband_mutex);

    Modes.airband_requested = enabled;
    Modes.airband_requested_freq = enabled ? frequency : MODES_DEFAULT_FREQ;
    Modes.airband_pending = 1;
    Modes.airband_error[0] = '\0';

    pthread_mutex_unlock(&Modes.airband_mutex);
}

static void airbandApplyPendingTuning(void) {
    int pending;
    int requested;
    int result;
    long long frequency;
    long long bandwidth;

    pthread_mutex_lock(&Modes.airband_mutex);

    pending = Modes.airband_pending;
    requested = Modes.airband_requested;
    frequency = Modes.airband_requested_freq;

    pthread_mutex_unlock(&Modes.airband_mutex);

    if (!pending) {
        return;
    }

    bandwidth = requested ? AIRBAND_AUDIO_RF_BANDWIDTH : MODES_DEFAULT_RATE;
    result = airbandTuneRadio(frequency, bandwidth);

    pthread_mutex_lock(&Modes.airband_mutex);

    Modes.airband_pending = 0;

    if (result < 0) {
        snprintf(
            Modes.airband_error,
            sizeof(Modes.airband_error),
            "Unable to tune Pluto radio, error %d",
            result
        );
    } else {
        Modes.airband_active = requested;
        Modes.airband_freq = frequency;
        Modes.airband_error[0] = '\0';

        Modes.airband_pcm_write = 0;
        Modes.airband_pcm_count = 0;
        Modes.airband_decimation_count = 0;
        Modes.airband_decimation_sum = 0;
        Modes.airband_dc = 0.0;
    }

    pthread_mutex_unlock(&Modes.airband_mutex);
}

static int airbandIsActive(void) {
    int active;

    pthread_mutex_lock(&Modes.airband_mutex);
    active = Modes.airband_active;
    pthread_mutex_unlock(&Modes.airband_mutex);

    return active;
}

static void airbandStoreSamples(const int16_t *samples, int count) {
    int index;

    pthread_mutex_lock(&Modes.airband_mutex);

    for (index = 0; index < count; index++) {
        Modes.airband_pcm[Modes.airband_pcm_write] = samples[index];
        Modes.airband_pcm_write =
            (Modes.airband_pcm_write + 1) % Modes.airband_pcm_capacity;

        if (Modes.airband_pcm_count < Modes.airband_pcm_capacity) {
            Modes.airband_pcm_count++;
        }
    }

    pthread_mutex_unlock(&Modes.airband_mutex);
}

static void airbandDemodSample(
    int16_t i_sample,
    int16_t q_sample,
    int16_t *output,
    int *output_count,
    int output_capacity
) {
    int magnitude;
    double envelope;
    double audio;
    int audio_sample;

    magnitude = abs((int)i_sample) + abs((int)q_sample);

    Modes.airband_decimation_sum += magnitude;
    Modes.airband_decimation_count++;

    if (Modes.airband_decimation_count < AIRBAND_AUDIO_DECIMATION) {
        return;
    }

    envelope =
        (double)Modes.airband_decimation_sum /
        (double)Modes.airband_decimation_count;

    if (Modes.airband_dc == 0.0) {
        Modes.airband_dc = envelope;
    }

    /*
     * Remove the AM carrier/DC component slowly while preserving speech.
     * Output scaling is intentionally conservative for initial testing.
     */
    Modes.airband_dc += (envelope - Modes.airband_dc) * 0.0005;
    audio = (envelope - Modes.airband_dc) * 10.0;

    if (audio > 32767.0) {
        audio = 32767.0;
    } else if (audio < -32768.0) {
        audio = -32768.0;
    }

    audio_sample = (int)audio;

    if (*output_count < output_capacity) {
        output[*output_count] = (int16_t)audio_sample;
        (*output_count)++;
    }

    Modes.airband_decimation_sum = 0;
    Modes.airband_decimation_count = 0;
}

'''

s = s.replace(reader_comment, audio_functions + "\n" + reader_comment, 1)

# ---------------------------------------------------------------------------
# Replace the Pluto reader function so it generates PCM while in airband mode.
# ---------------------------------------------------------------------------

def function_bounds(source: str, name: str):
    match = re.search(
        r'void\s*\*\s*' + re.escape(name) +
        r'\s*\(\s*void\s*\*\s*arg\s*\)',
        source
    )
    if not match:
        return None

    brace = source.find("{", match.end())
    if brace < 0:
        return None

    depth = 0
    in_string = False
    in_char = False
    in_line = False
    in_block = False
    escape = False
    i = brace

    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ""

        if in_line:
            if c == "\n":
                in_line = False
            i += 1
            continue

        if in_block:
            if c == "*" and n == "/":
                in_block = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == "'":
                in_char = False
            i += 1
            continue

        if c == "/" and n == "/":
            in_line = True
            i += 2
            continue

        if c == "/" and n == "*":
            in_block = True
            i += 2
            continue

        if c == '"':
            in_string = True
            i += 1
            continue

        if c == "'":
            in_char = True
            i += 1
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return match.start(), i + 1

        i += 1

    return None

bounds = function_bounds(s, "readerThreadEntryPoint")
if not bounds:
    raise SystemExit("Could not find readerThreadEntryPoint() bounds.")

new_reader = r'''void *readerThreadEntryPoint(void *arg) {
    MODES_NOTUSED(arg);

    if (Modes.filename == NULL) {
        unsigned char cb_buf[MODES_DATA_LEN];
        int16_t audio_chunk[(MODES_DATA_LEN / (2 * AIRBAND_AUDIO_DECIMATION)) + 16];

        while (!Modes.stop) {
            void *p_dat;
            void *p_end;
            ptrdiff_t p_inc;
            int j = 0;
            int audio_mode;
            int audio_count = 0;

            airbandApplyPendingTuning();
            audio_mode = airbandIsActive();

            iio_buffer_refill(Modes.rxbuf);

            p_inc = iio_buffer_step(Modes.rxbuf);
            p_end = iio_buffer_end(Modes.rxbuf);

            for (
                p_dat = iio_buffer_first(Modes.rxbuf, Modes.rx0_i);
                p_dat < p_end;
                p_dat += p_inc
            ) {
                const int16_t i_sample = ((int16_t *)p_dat)[0];
                const int16_t q_sample = ((int16_t *)p_dat)[1];

                cb_buf[j * 2] = i_sample >> 4;
                cb_buf[j * 2 + 1] = q_sample >> 4;

                if (audio_mode) {
                    airbandDemodSample(
                        i_sample,
                        q_sample,
                        audio_chunk,
                        &audio_count,
                        (int)(sizeof(audio_chunk) / sizeof(audio_chunk[0]))
                    );
                }

                j++;
            }

            if (audio_mode && audio_count > 0) {
                airbandStoreSamples(audio_chunk, audio_count);
            }

            /*
             * Continue waking the main loop in airband mode so that the
             * embedded HTTP server remains responsive. At VHF frequencies
             * the Mode-S detector simply produces no ADS-B messages.
             */
            plutosdrCallback(cb_buf, MODES_DATA_LEN);
        }
    } else {
        readDataFromFile();
    }

    return NULL;
}'''

start, end = bounds
s = s[:start] + new_reader + s[end:]

# ---------------------------------------------------------------------------
# Add status/start/stop/WAV response builders before existing frequency JSON.
# ---------------------------------------------------------------------------

endpoint_anchor = "char *vrsAirbandFrequenciesJson(int *len) {"

if endpoint_anchor not in s:
    raise SystemExit(
        "Could not find vrsAirbandFrequenciesJson(). "
        "Apply the frequency endpoint patch first."
    )

endpoint_functions = r'''
static void airbandPutU16(unsigned char *buffer, unsigned int value) {
    buffer[0] = (unsigned char)(value & 0xff);
    buffer[1] = (unsigned char)((value >> 8) & 0xff);
}

static void airbandPutU32(unsigned char *buffer, unsigned int value) {
    buffer[0] = (unsigned char)(value & 0xff);
    buffer[1] = (unsigned char)((value >> 8) & 0xff);
    buffer[2] = (unsigned char)((value >> 16) & 0xff);
    buffer[3] = (unsigned char)((value >> 24) & 0xff);
}

char *vrsAirbandStatusJson(int *len) {
    char *out = malloc(512);
    int requested;
    int active;
    int pending;
    long long requested_freq;
    long long frequency;
    unsigned int pcm_count;
    char error[128];

    if (out == NULL) {
        fprintf(stderr, "Out of memory serving airband status JSON\n");
        exit(1);
    }

    pthread_mutex_lock(&Modes.airband_mutex);

    requested = Modes.airband_requested;
    active = Modes.airband_active;
    pending = Modes.airband_pending;
    requested_freq = Modes.airband_requested_freq;
    frequency = Modes.airband_freq;
    pcm_count = Modes.airband_pcm_count;
    snprintf(error, sizeof(error), "%s", Modes.airband_error);

    pthread_mutex_unlock(&Modes.airband_mutex);

    *len = snprintf(
        out,
        512,
        "{"
        "\"mode\":\"%s\","
        "\"requested\":%s,"
        "\"active\":%s,"
        "\"switching\":%s,"
        "\"requested_frequency_hz\":%lld,"
        "\"frequency_hz\":%lld,"
        "\"audio_sample_rate\":%d,"
        "\"pcm_samples\":%u,"
        "\"audio_url\":\"/VirtualRadar/Airband/Audio.wav\","
        "\"error\":\"%s\""
        "}\n",
        active ? "airband" : "adsb",
        requested ? "true" : "false",
        active ? "true" : "false",
        pending ? "true" : "false",
        requested_freq,
        frequency,
        AIRBAND_AUDIO_SAMPLE_RATE,
        pcm_count,
        error
    );

    return out;
}

char *vrsAirbandStartJson(const char *url, int *len) {
    const char *parameter = strstr(url, "freq=");
    long long frequency;

    if (parameter == NULL) {
        char *out = strdup("{\"error\":\"Missing freq parameter\"}\n");
        *len = strlen(out);
        return out;
    }

    frequency = strtoll(parameter + 5, NULL, 10);

    if (frequency < AIRBAND_MIN_FREQ_HZ ||
        frequency > AIRBAND_MAX_FREQ_HZ) {
        char *out = strdup(
            "{\"error\":\"Frequency is outside 118.000-136.975 MHz\"}\n"
        );
        *len = strlen(out);
        return out;
    }

    airbandRequestMode(1, frequency);
    return vrsAirbandStatusJson(len);
}

char *vrsAirbandStopJson(int *len) {
    airbandRequestMode(0, MODES_DEFAULT_FREQ);
    return vrsAirbandStatusJson(len);
}

char *vrsAirbandAudioWav(int *len) {
    unsigned int available;
    unsigned int samples;
    unsigned int first;
    unsigned int index;
    unsigned int data_bytes;
    unsigned int total_bytes;
    unsigned char *wav;

    pthread_mutex_lock(&Modes.airband_mutex);

    available = Modes.airband_pcm_count;
    samples = available > AIRBAND_AUDIO_SAMPLE_RATE
        ? AIRBAND_AUDIO_SAMPLE_RATE
        : available;

    data_bytes = samples * sizeof(int16_t);
    total_bytes = 44 + data_bytes;

    wav = malloc(total_bytes);
    if (wav == NULL) {
        pthread_mutex_unlock(&Modes.airband_mutex);
        fprintf(stderr, "Out of memory serving airband WAV audio\n");
        exit(1);
    }

    memcpy(wav, "RIFF", 4);
    airbandPutU32(wav + 4, total_bytes - 8);
    memcpy(wav + 8, "WAVE", 4);
    memcpy(wav + 12, "fmt ", 4);
    airbandPutU32(wav + 16, 16);
    airbandPutU16(wav + 20, 1);
    airbandPutU16(wav + 22, 1);
    airbandPutU32(wav + 24, AIRBAND_AUDIO_SAMPLE_RATE);
    airbandPutU32(wav + 28, AIRBAND_AUDIO_SAMPLE_RATE * 2);
    airbandPutU16(wav + 32, 2);
    airbandPutU16(wav + 34, 16);
    memcpy(wav + 36, "data", 4);
    airbandPutU32(wav + 40, data_bytes);

    first = (
        Modes.airband_pcm_write +
        Modes.airband_pcm_capacity -
        samples
    ) % Modes.airband_pcm_capacity;

    for (index = 0; index < samples; index++) {
        int16_t sample =
            Modes.airband_pcm[(first + index) % Modes.airband_pcm_capacity];

        airbandPutU16(
            wav + 44 + index * 2,
            (unsigned short)sample
        );
    }

    pthread_mutex_unlock(&Modes.airband_mutex);

    *len = total_bytes;
    return (char *)wav;
}

'''

s = s.replace(endpoint_anchor, endpoint_functions + endpoint_anchor, 1)

# ---------------------------------------------------------------------------
# Add WAV content type and HTTP routes.
# ---------------------------------------------------------------------------

json_type = '#define MODES_CONTENT_TYPE_JSON "application/json;charset=utf-8"'

if json_type not in s:
    raise SystemExit("Could not find JSON content type definition.")

s = s.replace(
    json_type,
    json_type + '\n#define MODES_CONTENT_TYPE_WAV "audio/wav"',
    1
)

route_anchor = '} else if (strstr(url, "/VirtualRadar/Airband/Frequencies.json")) {'

if route_anchor not in s:
    raise SystemExit("Could not find existing Airband Frequencies route.")

routes = r'''} else if (strstr(url, "/VirtualRadar/Airband/Status.json")) {
        content = vrsAirbandStatusJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strstr(url, "/VirtualRadar/Airband/Start.json")) {
        content = vrsAirbandStartJson(url, &clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strstr(url, "/VirtualRadar/Airband/Stop.json")) {
        content = vrsAirbandStopJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strstr(url, "/VirtualRadar/Airband/Audio.wav")) {
        content = vrsAirbandAudioWav(&clen);
        ctype = MODES_CONTENT_TYPE_WAV;
    '''

s = s.replace(route_anchor, routes + route_anchor, 1)

SRC.write_text(s, encoding="utf-8")

print("Installed airband AM backend:")
print("  /VirtualRadar/Airband/Status.json")
print("  /VirtualRadar/Airband/Start.json?freq=XXXXXXXXX")
print("  /VirtualRadar/Airband/Stop.json")
print("  /VirtualRadar/Airband/Audio.wav")
