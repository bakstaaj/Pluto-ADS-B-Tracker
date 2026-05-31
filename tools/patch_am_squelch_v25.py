#!/usr/bin/env python3
"""
Patch current Pluto-ADS-B-Tracker source to:
  - restore the selected AM v21 32 kHz offset tuning if missing locally
  - add v25 adjustable AM-only squelch backend and UI slider

Built against the user's uploaded current source files after v24 failed to apply.
Usage:
    python3 tools/patch_am_squelch_v25.py --check
    python3 tools/patch_am_squelch_v25.py --apply
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
C_PATH = ROOT / "dump1090.c"
HTML_PATH = ROOT / "web" / "vrs_desktop.html"


def read_normalized(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    return text, newline


def write_with_newline(path: Path, text: str, newline: str) -> None:
    output = text if newline == "\n" else text.replace("\n", "\r\n")
    path.write_bytes(output.encode("utf-8"))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one matching source block, found {count}")
    return text.replace(old, new, 1)


def patch_c(text: str) -> tuple[str, bool]:
    restored_v21 = False

    if "airband-am-notch-250-v22" in text or "airband-am-notch-500-v23" in text:
        raise RuntimeError("Discarded AM notch experiment markers v22/v23 are still present; revert them first.")

    if "airband-am-adjustable-squelch-v24" in text or "airband-am-adjustable-squelch-v25" in text:
        raise RuntimeError("An adjustable squelch patch marker is already present in dump1090.c.")

    if "airband-true-envelope-v20" not in text:
        raise RuntimeError("Required selected AM v20 true-envelope baseline is not present.")

    if "airband-am-offset-tuning-v21" not in text:
        text = replace_once(
            text,
            """/* airband-true-envelope-v20: phase-independent AM envelope detection. */
#define AM_TRUE_ENVELOPE_GAIN 12.75     /* Match prior AM voice level without L1 detector buzz. */

INCBIN(html,"map.html");""",
            """/* airband-true-envelope-v20: phase-independent AM envelope detection. */
#define AM_TRUE_ENVELOPE_GAIN 12.75     /* Match prior AM voice level without L1 detector buzz. */

/* airband-am-offset-tuning-v21: keep an AM carrier away from AD9361 zero-IF DC. */
#define AM_LO_OFFSET_HZ 32000LL        /* Exact 2 x 16 kHz audio-rate null after decimation. */

INCBIN(html,"map.html");""",
            "restore v21 constant",
        )
        text = replace_once(
            text,
            """    int requested_demodulation;
    int result;
    long long frequency;
    long long bandwidth;""",
            """    int requested_demodulation;
    int result;
    long long frequency;
    long long tuned_frequency;
    long long bandwidth;""",
            "restore v21 tuning variable",
        )
        text = replace_once(
            text,
            """    bandwidth = requested ? AIRBAND_AUDIO_RF_BANDWIDTH : MODES_DEFAULT_RATE;
    result = airbandTuneRadio(frequency, bandwidth);""",
            """    bandwidth = requested ? AIRBAND_AUDIO_RF_BANDWIDTH : MODES_DEFAULT_RATE;
    tuned_frequency = frequency;

    /*
     * airband-am-offset-tuning-v21
     *
     * A zero-IF receiver has a DC spur at the center frequency. When an AM
     * carrier is nearly centered, residual oscillator offset lets that DC
     * spur beat against the carrier and the envelope detector hears it as
     * a steady low-frequency buzz. Receive AM 32 kHz above the displayed
     * channel instead. The wanted AM envelope is unchanged, while the DC
     * beat moves to a null of the existing 2 MHz -> 16 kHz boxcar output
     * decimation. NOAA NFM and ADS-B tuning remain unchanged.
     */
    if (requested && requested_demodulation == AIRBAND_DEMOD_AM) {
        tuned_frequency += AM_LO_OFFSET_HZ;
    }

    result = airbandTuneRadio(tuned_frequency, bandwidth);""",
            "restore v21 tune operation",
        )
        restored_v21 = True

    text = replace_once(
        text,
        """/* airband-am-offset-tuning-v21: keep an AM carrier away from AD9361 zero-IF DC. */
#define AM_LO_OFFSET_HZ 32000LL        /* Exact 2 x 16 kHz audio-rate null after decimation. */

INCBIN(html,"map.html");""",
        """/* airband-am-offset-tuning-v21: keep an AM carrier away from AD9361 zero-IF DC. */
#define AM_LO_OFFSET_HZ 32000LL        /* Exact 2 x 16 kHz audio-rate null after decimation. */

/* airband-am-adjustable-squelch-v25: user controlled AM-only audio squelch. */
#define AM_SQUELCH_MAX_LEVEL 100
#define AM_SQUELCH_THRESHOLD_SCALE 20.0 /* Slider level -> PCM amplitude threshold. */
#define AM_SQUELCH_LEVEL_ALPHA 0.025   /* Fast level follower at 16 kHz PCM. */
#define AM_SQUELCH_HANG_SAMPLES 960    /* Keep voice open for 60 ms. */
#define AM_SQUELCH_OPEN_ALPHA 0.65     /* Restore speech quickly. */
#define AM_SQUELCH_CLOSE_ALPHA 0.30    /* Mute hum promptly. */

INCBIN(html,"map.html");""",
        "v25 definitions",
    )

    text = replace_once(
        text,
        """    /* AM envelope demodulator state. */
    int airband_decimation_count;
    long long airband_decimation_sum;
    double airband_dc;

    /* Narrow-FM discriminator state for NOAA Weather Radio. */""",
        """    /* AM envelope demodulator state. */
    int airband_decimation_count;
    long long airband_decimation_sum;
    double airband_dc;

    /* Adjustable AM-only audio squelch; NFM is intentionally unaffected. */
    int airband_am_squelch_level;
    double am_squelch_envelope;
    double am_squelch_gain;
    int am_squelch_hold_samples;

    /* Narrow-FM discriminator state for NOAA Weather Radio. */""",
        "v25 state",
    )

    text = replace_once(
        text,
        """    Modes.airband_decimation_count = 0;
    Modes.airband_decimation_sum = 0;
    Modes.airband_dc = 0.0;
    Modes.nfm_i_sum = 0;""",
        """    Modes.airband_decimation_count = 0;
    Modes.airband_decimation_sum = 0;
    Modes.airband_dc = 0.0;
    Modes.airband_am_squelch_level = 0;
    Modes.am_squelch_envelope = 0.0;
    Modes.am_squelch_gain = 1.0;
    Modes.am_squelch_hold_samples = 0;
    Modes.nfm_i_sum = 0;""",
        "v25 initialization",
    )

    text = replace_once(
        text,
        """    Modes.airband_decimation_count = 0;
    Modes.airband_decimation_sum = 0;
    Modes.airband_dc = 0.0;

    Modes.nfm_i_sum = 0;""",
        """    Modes.airband_decimation_count = 0;
    Modes.airband_decimation_sum = 0;
    Modes.airband_dc = 0.0;
    Modes.am_squelch_envelope = 0.0;
    Modes.am_squelch_gain = 1.0;
    Modes.am_squelch_hold_samples = 0;

    Modes.nfm_i_sum = 0;""",
        "v25 reset",
    )

    text = replace_once(
        text,
        """static int airbandAudioMode(int *demodulation) {
    int active;

    pthread_mutex_lock(&Modes.airband_mutex);
    active = Modes.airband_active;
    *demodulation = Modes.airband_demod;
    pthread_mutex_unlock(&Modes.airband_mutex);

    return active;
}""",
        """static int airbandAudioMode(int *demodulation, int *am_squelch_level) {
    int active;

    pthread_mutex_lock(&Modes.airband_mutex);
    active = Modes.airband_active;
    *demodulation = Modes.airband_demod;
    *am_squelch_level = Modes.airband_am_squelch_level;
    pthread_mutex_unlock(&Modes.airband_mutex);

    return active;
}""",
        "v25 audio mode",
    )

    text = replace_once(
        text,
        """static void airbandDemodAmSample(
    int16_t i_sample,
    int16_t q_sample,
    int16_t *output,""",
        """/*
 * airband-am-adjustable-squelch-v25
 *
 * Suppress low-level AM hum/noise when the selected channel is inactive.
 * Level 0 disables squelch completely. The slider threshold is adjustable
 * because useful signal and background hum vary by antenna/site. NOAA NFM
 * never enters this path.
 */
static double airbandApplyAmSquelch(double audio, int squelch_level) {
    double threshold;
    double target_gain;

    if (squelch_level <= 0) {
        Modes.am_squelch_envelope = 0.0;
        Modes.am_squelch_gain = 1.0;
        Modes.am_squelch_hold_samples = 0;
        return audio;
    }

    threshold = (double)squelch_level * AM_SQUELCH_THRESHOLD_SCALE;
    Modes.am_squelch_envelope +=
        (fabs(audio) - Modes.am_squelch_envelope) * AM_SQUELCH_LEVEL_ALPHA;

    if (Modes.am_squelch_envelope >= threshold) {
        Modes.am_squelch_hold_samples = AM_SQUELCH_HANG_SAMPLES;
    } else if (Modes.am_squelch_hold_samples > 0) {
        Modes.am_squelch_hold_samples--;
    }

    target_gain = Modes.am_squelch_hold_samples > 0 ? 1.0 : 0.0;
    if (target_gain > Modes.am_squelch_gain) {
        Modes.am_squelch_gain +=
            (target_gain - Modes.am_squelch_gain) * AM_SQUELCH_OPEN_ALPHA;
    } else {
        Modes.am_squelch_gain +=
            (target_gain - Modes.am_squelch_gain) * AM_SQUELCH_CLOSE_ALPHA;
    }

    if (Modes.am_squelch_gain < 0.001) {
        Modes.am_squelch_gain = 0.0;
    }

    return audio * Modes.am_squelch_gain;
}

static void airbandDemodAmSample(
    int16_t i_sample,
    int16_t q_sample,
    int am_squelch_level,
    int16_t *output,""",
        "v25 squelch function",
    )

    text = replace_once(
        text,
        """    Modes.airband_dc += (envelope - Modes.airband_dc) * 0.0005;
    audio = (envelope - Modes.airband_dc) * AM_TRUE_ENVELOPE_GAIN;

    airbandWriteAudioSample(audio, output, output_count, output_capacity);""",
        """    Modes.airband_dc += (envelope - Modes.airband_dc) * 0.0005;
    audio = (envelope - Modes.airband_dc) * AM_TRUE_ENVELOPE_GAIN;
    audio = airbandApplyAmSquelch(audio, am_squelch_level);

    airbandWriteAudioSample(audio, output, output_count, output_capacity);""",
        "v25 apply squelch",
    )

    text = replace_once(
        text,
        """            int audio_mode;
            int audio_demodulation = AIRBAND_DEMOD_AM;
            int audio_count = 0;

            airbandApplyPendingTuning();
            audio_mode = airbandAudioMode(&audio_demodulation);""",
        """            int audio_mode;
            int audio_demodulation = AIRBAND_DEMOD_AM;
            int am_squelch_level = 0;
            int audio_count = 0;

            airbandApplyPendingTuning();
            audio_mode = airbandAudioMode(&audio_demodulation, &am_squelch_level);""",
        "v25 reader state",
    )

    text = replace_once(
        text,
        """                        airbandDemodAmSample(
                            i_sample,
                            q_sample,
                            audio_chunk,""",
        """                        airbandDemodAmSample(
                            i_sample,
                            q_sample,
                            am_squelch_level,
                            audio_chunk,""",
        "v25 AM call",
    )

    text = replace_once(
        text,
        """    int requested_demodulation;
    int demodulation;
    long long requested_freq;""",
        """    int requested_demodulation;
    int demodulation;
    int am_squelch_level;
    long long requested_freq;""",
        "v25 status variable",
    )

    text = replace_once(
        text,
        """    requested_demodulation = Modes.airband_requested_demod;
    demodulation = Modes.airband_demod;
    requested_freq = Modes.airband_requested_freq;""",
        """    requested_demodulation = Modes.airband_requested_demod;
    demodulation = Modes.airband_demod;
    am_squelch_level = Modes.airband_am_squelch_level;
    requested_freq = Modes.airband_requested_freq;""",
        "v25 status read",
    )

    text = replace_once(
        text,
        """        "\\"frequency_hz\\":%lld,"
        "\\"demodulation\\":\\"%s\\","
        "\\"audio_sample_rate\\":%d,""",
        """        "\\"frequency_hz\\":%lld,"
        "\\"demodulation\\":\\"%s\\","
        "\\"am_squelch_level\\":%d,"
        "\\"am_squelch_max\\":%d,"
        "\\"audio_sample_rate\\":%d,""",
        "v25 status fields",
    )

    text = replace_once(
        text,
        """        airbandDemodulationName(
            requested ? requested_demodulation : demodulation
        ),
        AIRBAND_AUDIO_SAMPLE_RATE,""",
        """        airbandDemodulationName(
            requested ? requested_demodulation : demodulation
        ),
        am_squelch_level,
        AM_SQUELCH_MAX_LEVEL,
        AIRBAND_AUDIO_SAMPLE_RATE,""",
        "v25 status values",
    )

    text = replace_once(
        text,
        """char *vrsAirbandAudioWav(const char *url, int *len) {""",
        """char *vrsAirbandSquelchJson(const char *url, int *len) {
    unsigned int level = (unsigned int)airbandUrlUnsignedParameter(
        url, "level=", 0
    );

    if (level > AM_SQUELCH_MAX_LEVEL) {
        level = AM_SQUELCH_MAX_LEVEL;
    }

    pthread_mutex_lock(&Modes.airband_mutex);
    Modes.airband_am_squelch_level = (int)level;
    pthread_mutex_unlock(&Modes.airband_mutex);

    return vrsAirbandStatusJson(len);
}

char *vrsAirbandAudioWav(const char *url, int *len) {""",
        "v25 endpoint",
    )

    text = replace_once(
        text,
        """    } else if (strstr(url, "/VirtualRadar/Airband/Stop.json")) {
        content = vrsAirbandStopJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strstr(url, "/VirtualRadar/Airband/Audio.wav")) {""",
        """    } else if (strstr(url, "/VirtualRadar/Airband/Stop.json")) {
        content = vrsAirbandStopJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strstr(url, "/VirtualRadar/Airband/Squelch.json")) {
        content = vrsAirbandSquelchJson(url, &clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strstr(url, "/VirtualRadar/Airband/Audio.wav")) {""",
        "v25 route",
    )

    return text, restored_v21


def patch_html(text: str) -> str:
    if "airband-am-adjustable-squelch-v24" in text or "airband-am-adjustable-squelch-v25" in text:
        raise RuntimeError("An adjustable squelch patch marker is already present in web/vrs_desktop.html.")
    if "aircraft-freeze-during-audio-v19" not in text:
        raise RuntimeError("Expected v19 aircraft-freeze UI baseline is not present.")

    text = replace_once(
        text,
        """#airband-v3-inline-stop:hover {
  background: #393223;
  border-color: #ffdf4d;
}


/* coverage-summary-removed-v11 */""",
        """#airband-v3-inline-stop:hover {
  background: #393223;
  border-color: #ffdf4d;
}

/* airband-am-adjustable-squelch-v25 */
#airband-v3-squelch {
  display: none;
  align-items: center;
  gap: 5px;
  color: #c5cbd0;
  font-size: 11px;
  white-space: nowrap;
}
#airband-v3-squelch.visible {
  display: inline-flex;
}
#airband-v3-squelch input[type="range"] {
  width: 82px;
  accent-color: #ffdf4d;
}
#airband-v3-squelch-value {
  min-width: 28px;
  color: #ffdf4d;
  text-align: right;
}

/* coverage-summary-removed-v11 */""",
        "HTML style",
    )

    text = replace_once(
        text,
        """                      title="Stop listening and resume ADS-B"
                      aria-label="Stop listening and resume ADS-B"
                      disabled>■</button>
            </div>""",
        """                      title="Stop listening and resume ADS-B"
                      aria-label="Stop listening and resume ADS-B"
                      disabled>■</button>
              <label id="airband-v3-squelch" title="AM squelch: raise until idle-channel hum mutes without clipping transmissions">
                Sq
                <input type="range" id="airband-v3-squelch-slider" min="0" max="100" step="1" value="0">
                <span id="airband-v3-squelch-value">Off</span>
              </label>
            </div>""",
        "HTML slider",
    )

    text = replace_once(
        text,
        """    lastReceiverKey: '',
    pageIndex: 0,
    pageSize: 10,
    pagingReceiverKey: ''
  };""",
        """    lastReceiverKey: '',
    pageIndex: 0,
    pageSize: 10,
    pagingReceiverKey: '',
    amSquelchLevel: Number(window.localStorage.getItem('plutoAdsBAmSquelchV1') || 0),
    squelchTimer: null
  };""",
        "HTML state",
    )

    text = replace_once(
        text,
        """  function status(message, listening) {""",
        """  function showAmSquelch(active) {
    const control = element('airband-v3-squelch');
    if (!control) return;
    control.classList.toggle('visible', !!active);
  }

  function renderAmSquelch() {
    const slider = element('airband-v3-squelch-slider');
    const value = element('airband-v3-squelch-value');
    if (!slider || !value) return;
    slider.value = String(stateV3.amSquelchLevel);
    value.textContent = stateV3.amSquelchLevel > 0
      ? String(stateV3.amSquelchLevel)
      : 'Off';
  }

  async function setAmSquelch(level) {
    stateV3.amSquelchLevel = Math.max(0, Math.min(100, Number(level) || 0));
    window.localStorage.setItem('plutoAdsBAmSquelchV1', String(stateV3.amSquelchLevel));
    renderAmSquelch();

    try {
      await fetch(
        '/VirtualRadar/Airband/Squelch.json?level=' +
        encodeURIComponent(stateV3.amSquelchLevel) +
        '&_=' + Date.now(),
        { cache: 'no-store' }
      );
    } catch (error) {
      console.log('Unable to update AM squelch:', error);
    }
  }

  function status(message, listening) {""",
        "HTML functions",
    )

    text = replace_once(
        text,
        """    if (inlineStop) {
      inlineStop.classList.toggle('visible', !!listening);
      inlineStop.disabled = !listening;
    }
  }""",
        """    if (inlineStop) {
      inlineStop.classList.toggle('visible', !!listening);
      inlineStop.disabled = !listening;
    }

    showAmSquelch(
      !!listening && !!stateV3.selected && demodulation(stateV3.selected) === 'AM'
    );
  }""",
        "HTML visibility",
    )

    text = replace_once(
        text,
        """      stateV3.listening = true;
      stateV3.audioNextCursor = null;""",
        """      if (demodulation(stateV3.selected) === 'AM') {
        await setAmSquelch(stateV3.amSquelchLevel);
      }

      stateV3.listening = true;
      stateV3.audioNextCursor = null;""",
        "HTML set initial level",
    )

    text = replace_once(
        text,
        """    element('airband-v3-listen').addEventListener('click', beginListening);
    element('airband-v3-stop').addEventListener('click', endListening);
    element('airband-v3-inline-stop').addEventListener('click', endListening);

    element('airband-v3-prev').addEventListener('click', function () {""",
        """    element('airband-v3-listen').addEventListener('click', beginListening);
    element('airband-v3-stop').addEventListener('click', endListening);
    element('airband-v3-inline-stop').addEventListener('click', endListening);

    renderAmSquelch();
    element('airband-v3-squelch-slider').addEventListener('input', function (event) {
      stateV3.amSquelchLevel = Number(event.target.value) || 0;
      renderAmSquelch();
      clearTimeout(stateV3.squelchTimer);
      stateV3.squelchTimer = setTimeout(function () {
        setAmSquelch(stateV3.amSquelchLevel);
      }, 80);
    });

    element('airband-v3-prev').addEventListener('click', function () {""",
        "HTML listener",
    )

    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="validate patch anchors without writing")
    action.add_argument("--apply", action="store_true", help="write the patched source files")
    args = parser.parse_args()

    if not C_PATH.exists() or not HTML_PATH.exists():
        raise RuntimeError(f"Run this tool inside the repository; missing {C_PATH} or {HTML_PATH}.")

    c, c_newline = read_normalized(C_PATH)
    html, html_newline = read_normalized(HTML_PATH)
    new_c, restored_v21 = patch_c(c)
    new_html = patch_html(html)

    if args.check:
        print("CHECK PASS: current source matches the corrected v25 squelch patch anchors.")
        if restored_v21:
            print("NOTE: local dump1090.c is missing selected v21; --apply will restore AM_LO_OFFSET_HZ 32000LL.")
        print("Would modify: dump1090.c, web/vrs_desktop.html")
        return 0

    write_with_newline(C_PATH, new_c, c_newline)
    write_with_newline(HTML_PATH, new_html, html_newline)
    print("APPLIED: restored v21 if needed and installed v25 adjustable AM squelch.")
    print("Modified: dump1090.c, web/vrs_desktop.html")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
