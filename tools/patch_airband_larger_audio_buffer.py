#!/usr/bin/env python3
from pathlib import Path

SRC = Path("dump1090.c")
s = SRC.read_text(encoding="utf-8")

if "AIRBAND_PCM_BUFFER_SECONDS" not in s:
    anchor = "#define AIRBAND_AUDIO_RF_BANDWIDTH 200000\n"
    replacement = """#define AIRBAND_AUDIO_RF_BANDWIDTH 200000
#define AIRBAND_PCM_BUFFER_SECONDS 15
#define AIRBAND_MAX_WAV_SAMPLES (AIRBAND_AUDIO_SAMPLE_RATE * 2)
"""

    if anchor not in s:
        raise SystemExit("Could not find AIRBAND_AUDIO_RF_BANDWIDTH define.")

    s = s.replace(anchor, replacement, 1)

old_capacity = "Modes.airband_pcm_capacity = AIRBAND_AUDIO_SAMPLE_RATE * 5;"
new_capacity = "Modes.airband_pcm_capacity = AIRBAND_AUDIO_SAMPLE_RATE * AIRBAND_PCM_BUFFER_SECONDS;"

if old_capacity in s:
    s = s.replace(old_capacity, new_capacity, 1)
elif new_capacity not in s:
    raise SystemExit("Could not find airband PCM ring-buffer capacity initialization.")

old_limit = """    if (requested_samples == 0 ||
        requested_samples > AIRBAND_AUDIO_SAMPLE_RATE) {
        requested_samples = AIRBAND_AUDIO_SAMPLE_RATE;
    }
"""

new_limit = """    if (requested_samples == 0 ||
        requested_samples > AIRBAND_MAX_WAV_SAMPLES) {
        requested_samples = AIRBAND_MAX_WAV_SAMPLES;
    }
"""

if old_limit in s:
    s = s.replace(old_limit, new_limit, 1)
elif "requested_samples > AIRBAND_MAX_WAV_SAMPLES" not in s:
    raise SystemExit("Could not find WAV requested-samples limit block.")

SRC.write_text(s, encoding="utf-8")

print("Expanded Pluto airband PCM buffer to 15 seconds.")
print("Enabled sequential WAV requests up to 2 seconds per block.")
