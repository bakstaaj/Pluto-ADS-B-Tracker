#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if "audioQueueTargetSeconds: 4.0" in s:
    print("Deeper browser buffer is already installed.")
    raise SystemExit(0)

old_state = """    audioScheduledUntil: 0,
    audioChunkSamples: 8000,
    lastReceiverKey: ''
"""

new_state = """    audioScheduledUntil: 0,
    audioChunkSamples: 32000,
    audioPrebufferSamples: 64000,
    audioQueueTargetSeconds: 4.0,
    lastReceiverKey: ''
"""

if old_state not in s:
    raise SystemExit("Could not find Web Audio v4 state settings.")

s = s.replace(old_state, new_state, 1)

old_buffer_block = """      /*
       * Prebuffer one second before scheduling playback. Each queued block is
       * half a second, giving the browser time to fetch the next block before
       * the current audio reaches the speakers.
       */
      if (stateV3.audioNextCursor === null) {
        if (totalSamples < chunkSamples * 2) {
          bufferMessage(
            'Buffering audio... ' +
            Math.min(100, Math.round(totalSamples / (chunkSamples * 2) * 100)) +
            '%'
          );
          return;
        }

        stateV3.audioNextCursor = totalSamples - (chunkSamples * 2);
        stateV3.audioScheduledUntil =
          stateV3.audioContext.currentTime + 0.15;
      }
"""

new_buffer_block = """      /*
       * Start with a four-second reserve. The Pluto+ / browser connection can
       * occasionally take longer than real-time to complete a request, so a
       * deeper reserve prevents playback underruns.
       */
      if (stateV3.audioNextCursor === null) {
        if (totalSamples < stateV3.audioPrebufferSamples) {
          bufferMessage(
            'Buffering audio... ' +
            Math.min(
              100,
              Math.round(totalSamples / stateV3.audioPrebufferSamples * 100)
            ) +
            '%'
          );
          return;
        }

        stateV3.audioNextCursor =
          totalSamples - stateV3.audioPrebufferSamples;

        stateV3.audioScheduledUntil =
          stateV3.audioContext.currentTime + 0.20;
      }
"""

if old_buffer_block not in s:
    raise SystemExit("Could not find the existing Web Audio startup-buffer block.")

s = s.replace(old_buffer_block, new_buffer_block, 1)

old_stale = """      if (totalSamples - stateV3.audioNextCursor > sampleRate * 4) {
        stateV3.audioNextCursor = totalSamples - (chunkSamples * 2);
        stateV3.audioScheduledUntil =
          stateV3.audioContext.currentTime + 0.15;
      }
"""

new_stale = """      if (totalSamples - stateV3.audioNextCursor > sampleRate * 12) {
        stateV3.audioNextCursor =
          totalSamples - stateV3.audioPrebufferSamples;

        stateV3.audioScheduledUntil =
          stateV3.audioContext.currentTime + 0.20;

        bufferMessage('Audio connection recovered; rebuilding playback buffer...');
      }
"""

if old_stale not in s:
    raise SystemExit("Could not find stale-audio recovery block.")

s = s.replace(old_stale, new_stale, 1)

old_queue_condition = """        stateV3.audioScheduledUntil - stateV3.audioContext.currentTime < 2.0
"""

new_queue_condition = """        stateV3.audioScheduledUntil - stateV3.audioContext.currentTime <
          stateV3.audioQueueTargetSeconds
"""

if old_queue_condition not in s:
    raise SystemExit("Could not find scheduled-audio queue limit.")

s = s.replace(old_queue_condition, new_queue_condition, 1)

old_timer = "      stateV3.audioTimer = setInterval(pumpAudio, 100);"
new_timer = "      stateV3.audioTimer = setInterval(pumpAudio, 75);"

if old_timer in s:
    s = s.replace(old_timer, new_timer, 1)

HTML.write_text(s, encoding="utf-8")

print("Configured four-second browser audio reserve.")
print("Configured two-second sequential WAV chunks.")
print("Configured four-second scheduled playback target.")
