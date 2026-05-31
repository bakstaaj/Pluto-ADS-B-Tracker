#!/usr/bin/env python3
import re
from pathlib import Path

SRC = Path("dump1090.c")
s = SRC.read_text(encoding="utf-8")

if "airband_pcm_total" in s and "airbandUrlUnsignedParameter" in s:
    print("Sequential audio backend already appears to be installed.")
    raise SystemExit(0)

def replace_required(old, new, label, count=1):
    global s
    if old not in s:
        raise SystemExit(f"Could not find {label}.")
    s = s.replace(old, new, count)

def find_function_bounds(source, name):
    match = re.search(
        r'char\s*\*\s*' + re.escape(name) + r'\s*\([^)]*\)',
        source
    )
    if not match:
        return None

    brace = source.find('{', match.end())
    if brace < 0:
        return None

    depth = 0
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escaped = False
    i = brace

    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ''

        if in_line_comment:
            if c == '\n':
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if c == '*' and n == '/':
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == "'":
                in_char = False
            i += 1
            continue

        if c == '/' and n == '/':
            in_line_comment = True
            i += 2
            continue

        if c == '/' and n == '*':
            in_block_comment = True
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

        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return match.start(), i + 1

        i += 1

    return None

# ---------------------------------------------------------------------------
# Add an absolute PCM sequence counter to the existing ring buffer.
# ---------------------------------------------------------------------------

if "unsigned long long airband_pcm_total;" not in s:
    replace_required(
        "    unsigned int airband_pcm_count;\n",
        "    unsigned int airband_pcm_count;\n"
        "    unsigned long long airband_pcm_total;\n",
        "airband PCM state fields"
    )

if "Modes.airband_pcm_total = 0;" not in s:
    s = s.replace(
        "    Modes.airband_pcm_count = 0;\n",
        "    Modes.airband_pcm_count = 0;\n"
        "    Modes.airband_pcm_total = 0;\n"
    )

if "Modes.airband_pcm_total++;" not in s:
    replace_required(
        """        if (Modes.airband_pcm_count < Modes.airband_pcm_capacity) {
            Modes.airband_pcm_count++;
        }
""",
        """        if (Modes.airband_pcm_count < Modes.airband_pcm_capacity) {
            Modes.airband_pcm_count++;
        }

        Modes.airband_pcm_total++;
""",
        "airbandStoreSamples PCM increment block"
    )

# ---------------------------------------------------------------------------
# Add pcm_total to the status JSON response.
# ---------------------------------------------------------------------------

if '\\"pcm_total\\"' not in s:
    replace_required(
        "    unsigned int pcm_count;\n",
        "    unsigned int pcm_count;\n"
        "    unsigned long long pcm_total;\n",
        "status PCM variable declarations"
    )

    replace_required(
        "    pcm_count = Modes.airband_pcm_count;\n",
        "    pcm_count = Modes.airband_pcm_count;\n"
        "    pcm_total = Modes.airband_pcm_total;\n",
        "status PCM assignment"
    )

    replace_required(
        '        "\\"pcm_samples\\":%u,"\n',
        '        "\\"pcm_samples\\":%u,"\n'
        '        "\\"pcm_total\\":%llu,"\n',
        "status JSON pcm_samples field"
    )

    replace_required(
        """        AIRBAND_AUDIO_SAMPLE_RATE,
        pcm_count,
        error
""",
        """        AIRBAND_AUDIO_SAMPLE_RATE,
        pcm_count,
        pcm_total,
        error
""",
        "status JSON arguments"
    )

# ---------------------------------------------------------------------------
# Replace Audio.wav so it can serve sequential blocks:
#   /Audio.wav?from=<absolute sample cursor>&samples=<block size>
# ---------------------------------------------------------------------------

bounds = find_function_bounds(s, "vrsAirbandAudioWav")
if not bounds:
    raise SystemExit("Could not find vrsAirbandAudioWav().")

new_audio_function = r'''static unsigned long long airbandUrlUnsignedParameter(
    const char *url,
    const char *name,
    unsigned long long fallback
) {
    const char *value = strstr(url, name);

    if (value == NULL) {
        return fallback;
    }

    value += strlen(name);
    return strtoull(value, NULL, 10);
}

char *vrsAirbandAudioWav(const char *url, int *len) {
    unsigned int available;
    unsigned int requested_samples;
    unsigned int samples;
    unsigned int oldest_index;
    unsigned int first_index;
    unsigned int index;
    unsigned int data_bytes;
    unsigned int total_bytes;

    unsigned long long total_samples;
    unsigned long long oldest_cursor;
    unsigned long long requested_cursor;
    unsigned long long samples_after_cursor;
    unsigned long long offset_from_oldest;

    unsigned char *wav;

    pthread_mutex_lock(&Modes.airband_mutex);

    available = Modes.airband_pcm_count;
    total_samples = Modes.airband_pcm_total;
    oldest_cursor = total_samples - available;

    requested_samples = (unsigned int)airbandUrlUnsignedParameter(
        url,
        "samples=",
        AIRBAND_AUDIO_SAMPLE_RATE
    );

    if (requested_samples == 0 ||
        requested_samples > AIRBAND_AUDIO_SAMPLE_RATE) {
        requested_samples = AIRBAND_AUDIO_SAMPLE_RATE;
    }

    /*
     * Without a cursor, preserve the old behavior of returning the most
     * recent second. The browser buffered player supplies an explicit cursor.
     */
    requested_cursor = airbandUrlUnsignedParameter(
        url,
        "from=",
        total_samples > AIRBAND_AUDIO_SAMPLE_RATE
            ? total_samples - AIRBAND_AUDIO_SAMPLE_RATE
            : 0
    );

    if (requested_cursor < oldest_cursor) {
        requested_cursor = oldest_cursor;
    }

    if (requested_cursor > total_samples) {
        requested_cursor = total_samples;
    }

    samples_after_cursor = total_samples - requested_cursor;
    samples = samples_after_cursor > requested_samples
        ? requested_samples
        : (unsigned int)samples_after_cursor;

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

    oldest_index = (
        Modes.airband_pcm_write +
        Modes.airband_pcm_capacity -
        available
    ) % Modes.airband_pcm_capacity;

    offset_from_oldest = requested_cursor - oldest_cursor;

    first_index = (
        oldest_index +
        (unsigned int)offset_from_oldest
    ) % Modes.airband_pcm_capacity;

    for (index = 0; index < samples; index++) {
        int16_t sample =
            Modes.airband_pcm[(first_index + index) % Modes.airband_pcm_capacity];

        airbandPutU16(
            wav + 44 + index * 2,
            (unsigned short)sample
        );
    }

    pthread_mutex_unlock(&Modes.airband_mutex);

    *len = total_bytes;
    return (char *)wav;
}'''

start, end = bounds
s = s[:start] + new_audio_function + s[end:]

replace_required(
    "content = vrsAirbandAudioWav(&clen);",
    "content = vrsAirbandAudioWav(url, &clen);",
    "Audio.wav route call"
)

SRC.write_text(s, encoding="utf-8")

print("Installed cursor-based sequential airband WAV chunks.")
print("Status.json now reports pcm_total for browser buffering.")
