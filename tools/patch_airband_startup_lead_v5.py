#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if "audioStartupLeadSeconds: 2.25" in s:
    print("Audio startup lead v5 is already installed.")
    raise SystemExit(0)

old_state = """    audioChunkSamples: 32000,
    audioPrebufferSamples: 64000,
    audioQueueTargetSeconds: 4.0,
    lastReceiverKey: ''
"""

new_state = """    audioChunkSamples: 32000,
    audioPrebufferSamples: 64000,
    audioStartupLeadSeconds: 2.25,
    audioQueueTargetSeconds: 6.0,
    lastReceiverKey: ''
"""

if old_state not in s:
    raise SystemExit(
        "Could not find the Web Audio state settings. "
        "Confirm that tools/patch_airband_deeper_browser_buffer.py was applied."
    )

s = s.replace(old_state, new_state, 1)

old_initial_schedule = """        stateV3.audioScheduledUntil =
          stateV3.audioContext.currentTime + 0.20;
"""

new_initial_schedule = """        /*
         * Do not begin playback immediately after the first HTTP response.
         * Hold the first block briefly so the second initial block can be
         * downloaded, decoded and scheduled before audio reaches the speaker.
         */
        stateV3.audioScheduledUntil =
          stateV3.audioContext.currentTime +
          stateV3.audioStartupLeadSeconds;

        bufferMessage('Scheduling initial playback buffer...');
"""

count = s.count(old_initial_schedule)

if count < 1:
    raise SystemExit("Could not find initial playback scheduling assignment.")

# Replace both the initial scheduling case and recovery case, if both exist.
s = s.replace(old_initial_schedule, new_initial_schedule)

old_status = """      bufferMessage(
        'Live buffered audio · ' +
        secondsQueued.toFixed(1) +
        ' seconds queued'
      );
"""

new_status = """      const playbackBeginsIn = Math.max(
        0,
        stateV3.audioScheduledUntil -
        stateV3.audioContext.currentTime -
        stateV3.audioQueueTargetSeconds
      );

      if (stateV3.audioContext.currentTime <
          stateV3.audioScheduledUntil - stateV3.audioQueueTargetSeconds + 0.25) {
        bufferMessage(
          'Starting buffered audio · ' +
          secondsQueued.toFixed(1) +
          ' seconds scheduled'
        );
      } else {
        bufferMessage(
          'Live buffered audio · ' +
          secondsQueued.toFixed(1) +
          ' seconds queued'
        );
      }
"""

if old_status not in s:
    raise SystemExit("Could not find buffered-audio queue status block.")

s = s.replace(old_status, new_status, 1)

HTML.write_text(s, encoding="utf-8")

print("Added 2.25-second browser playback lead-in.")
print("Raised scheduled audio target to 6 seconds.")
print("The browser can now schedule both initial WAV blocks before sound begins.")
