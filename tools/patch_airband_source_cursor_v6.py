#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

marker = "airband-source-cursor-v6"

if marker in s:
    print("Airband source-sample cursor fix v6 is already installed.")
    raise SystemExit(0)

old = """        const bytes = await response.arrayBuffer();
        const audioBuffer = await stateV3.audioContext.decodeAudioData(bytes);

        if (!audioBuffer.length) {
          break;
        }

        const source = stateV3.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(stateV3.audioContext.destination);

        const startAt = Math.max(
          stateV3.audioScheduledUntil,
          stateV3.audioContext.currentTime + 0.05
        );

        source.start(startAt);

        stateV3.audioScheduledUntil = startAt + audioBuffer.duration;
        stateV3.audioNextCursor += audioBuffer.length;
"""

new = """        const bytes = await response.arrayBuffer();

        /*
         * airband-source-cursor-v6
         *
         * The Pluto cursor is measured in source PCM samples at 16 kHz.
         * decodeAudioData() can resample the WAV into the browser output
         * sample rate, so audioBuffer.length must not advance the Pluto
         * source cursor.
         *
         * WAV is 44-byte header plus signed 16-bit mono PCM.
         */
        const sourceSamples = Math.max(
          0,
          Math.floor((bytes.byteLength - 44) / 2)
        );

        if (!sourceSamples) {
          break;
        }

        const audioBuffer = await stateV3.audioContext.decodeAudioData(bytes);

        if (!audioBuffer.length) {
          break;
        }

        const source = stateV3.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(stateV3.audioContext.destination);

        const startAt = Math.max(
          stateV3.audioScheduledUntil,
          stateV3.audioContext.currentTime + 0.05
        );

        source.start(startAt);

        stateV3.audioScheduledUntil = startAt + audioBuffer.duration;

        /*
         * Advance by source samples returned by the Pluto, not browser-
         * resampled AudioBuffer samples.
         */
        stateV3.audioNextCursor += sourceSamples;
"""

if old not in s:
    if "stateV3.audioNextCursor += audioBuffer.length;" in s:
        raise SystemExit(
            "Found the cursor increment, but surrounding code differs. "
            "Run: grep -n -A15 -B15 'audioNextCursor += audioBuffer.length' web/vrs_desktop.html"
        )
    raise SystemExit(
        "Could not find the Web Audio cursor block. "
        "It may already have been changed or a prior audio patch is not deployed."
    )

s = s.replace(old, new, 1)

HTML.write_text(s, encoding="utf-8")

print("Fixed Web Audio cursor to advance using Pluto source PCM samples.")
print("The browser will no longer skip ahead when decoded audio is resampled.")
