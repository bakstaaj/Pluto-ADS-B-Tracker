#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if "airband-buffered-audio-v4" in s:
    print("Buffered Airband audio v4 is already installed.")
    raise SystemExit(0)

if '<script id="airband-controller-v3">' not in s:
    raise SystemExit(
        "Could not find airband-controller-v3. "
        "Apply tools/repair_airband_ui_v3.py first."
    )

# ---------------------------------------------------------------------------
# Replace the visible HTML audio player with buffered-audio status.
# Web Audio performs playback; a standard audio element is no longer needed.
# ---------------------------------------------------------------------------

old_audio_html = """              <audio id="airband-v3-audio" controls preload="none"></audio>
              <div class="airband-v3-note">
                Live AM audio uses short WAV segments. Press Play if browser autoplay is blocked.
              </div>"""

new_audio_html = """              <div id="airband-v3-buffer-status">Preparing audio buffer...</div>
              <div class="airband-v3-note">
                Buffered live AM playback is active. Audio begins after a short startup buffer.
              </div>"""

if old_audio_html not in s:
    raise SystemExit("Could not find existing Airband audio-player HTML.")

s = s.replace(old_audio_html, new_audio_html, 1)

# ---------------------------------------------------------------------------
# Extend CSS for buffered status display.
# ---------------------------------------------------------------------------

css = r'''
/* airband-buffered-audio-v4 */
#airband-v3-buffer-status {
  color: #ffdf4d;
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 5px;
}
'''

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Extend the v3 state object.
# ---------------------------------------------------------------------------

old_state = """    audioTimer: null,
    statusTimer: null,
    lastReceiverKey: ''
"""

new_state = """    audioTimer: null,
    statusTimer: null,
    audioContext: null,
    audioPumpBusy: false,
    audioNextCursor: null,
    audioScheduledUntil: 0,
    audioChunkSamples: 8000,
    lastReceiverKey: ''
"""

if old_state not in s:
    raise SystemExit("Could not find Airband v3 state object.")

s = s.replace(old_state, new_state, 1)

# ---------------------------------------------------------------------------
# Replace old stop/play/poll/start/stop functions.
# ---------------------------------------------------------------------------

start = s.find("  function stopPlayer() {")
end = s.find("  function initialize() {", start)

if start < 0 or end < 0:
    raise SystemExit("Could not find the old Airband playback function block.")

new_functions = r'''  function bufferMessage(message) {
    const output = element('airband-v3-buffer-status');
    if (output) {
      output.textContent = message;
    }
  }

  async function createAudioContext() {
    const AudioContextClass =
      window.AudioContext || window.webkitAudioContext;

    if (!AudioContextClass) {
      throw new Error('This browser does not support Web Audio playback.');
    }

    if (!stateV3.audioContext) {
      stateV3.audioContext = new AudioContextClass();
    }

    if (stateV3.audioContext.state === 'suspended') {
      await stateV3.audioContext.resume();
    }

    stateV3.audioScheduledUntil =
      stateV3.audioContext.currentTime + 0.15;
  }

  function stopPlayer() {
    if (stateV3.audioTimer) {
      clearInterval(stateV3.audioTimer);
      stateV3.audioTimer = null;
    }

    if (stateV3.statusTimer) {
      clearInterval(stateV3.statusTimer);
      stateV3.statusTimer = null;
    }

    stateV3.audioNextCursor = null;
    stateV3.audioScheduledUntil = 0;
    stateV3.audioPumpBusy = false;

    if (stateV3.audioContext) {
      stateV3.audioContext.close().catch(function () {});
      stateV3.audioContext = null;
    }

    element('airband-v3-audio-area').classList.remove('visible');
  }

  async function fetchBackendStatus() {
    const response = await fetch(
      '/VirtualRadar/Airband/Status.json?_=' + Date.now(),
      { cache: 'no-store' }
    );

    if (!response.ok) {
      throw new Error('Status HTTP ' + response.status);
    }

    return response.json();
  }

  async function pollBackend() {
    if (!stateV3.listening) return;

    try {
      const backend = await fetchBackendStatus();

      if (backend.error) {
        status('Backend error: ' + backend.error, true);
      } else if (backend.active) {
        status(
          'Listening ' +
          (backend.frequency_hz / 1000000).toFixed(3) +
          ' MHz AM · ADS-B paused · ' +
          (backend.pcm_samples || 0) +
          ' samples buffered.',
          true
        );
      } else if (backend.switching) {
        status('Switching Pluto receiver into airband mode...', true);
      }
    } catch (error) {
      status('Unable to read backend status: ' + error.message, true);
    }
  }

  async function pumpAudio() {
    if (!stateV3.listening ||
        !stateV3.audioContext ||
        stateV3.audioPumpBusy) {
      return;
    }

    stateV3.audioPumpBusy = true;

    try {
      const backend = await fetchBackendStatus();

      if (!backend.active) {
        bufferMessage('Waiting for receiver tuning...');
        return;
      }

      const totalSamples = Number(backend.pcm_total || 0);
      const sampleRate = Number(backend.audio_sample_rate || 16000);
      const chunkSamples = stateV3.audioChunkSamples;

      /*
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

      /*
       * If browser playback was suspended for several seconds, discard stale
       * queued audio and restart from the recent buffer.
       */
      if (totalSamples - stateV3.audioNextCursor > sampleRate * 4) {
        stateV3.audioNextCursor = totalSamples - (chunkSamples * 2);
        stateV3.audioScheduledUntil =
          stateV3.audioContext.currentTime + 0.15;
      }

      while (
        stateV3.listening &&
        totalSamples - stateV3.audioNextCursor >= chunkSamples &&
        stateV3.audioScheduledUntil - stateV3.audioContext.currentTime < 2.0
      ) {
        const response = await fetch(
          '/VirtualRadar/Airband/Audio.wav?from=' +
          stateV3.audioNextCursor +
          '&samples=' +
          chunkSamples +
          '&_=' + Date.now(),
          { cache: 'no-store' }
        );

        if (!response.ok) {
          throw new Error('Audio HTTP ' + response.status);
        }

        const bytes = await response.arrayBuffer();
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
      }

      const secondsQueued = Math.max(
        0,
        stateV3.audioScheduledUntil - stateV3.audioContext.currentTime
      );

      bufferMessage(
        'Live buffered audio · ' +
        secondsQueued.toFixed(1) +
        ' seconds queued'
      );

    } catch (error) {
      bufferMessage('Audio buffering error: ' + error.message);
    } finally {
      stateV3.audioPumpBusy = false;
    }
  }

  async function beginListening() {
    if (!stateV3.selected) {
      status('Select a frequency before listening.', false);
      return;
    }

    try {
      await createAudioContext();

      const response = await fetch(
        '/VirtualRadar/Airband/Start.json?freq=' +
        encodeURIComponent(stateV3.selected.frequency_hz) +
        '&_=' + Date.now(),
        { cache: 'no-store' }
      );

      const backend = await response.json();

      if (backend.error) {
        status('Unable to start listening: ' + backend.error, false);
        stopPlayer();
        return;
      }

      stateV3.listening = true;
      stateV3.audioNextCursor = null;

      element('airband-v3-listen').disabled = true;
      element('airband-v3-stop').disabled = false;
      element('airband-v3-best').disabled = true;
      element('airband-v3-audio-area').classList.add('visible');

      bufferMessage('Preparing audio buffer...');

      status(
        'Listening ' +
        stateV3.selected.frequency_mhz.toFixed(3) +
        ' MHz AM · ADS-B paused.',
        true
      );

      stateV3.audioTimer = setInterval(pumpAudio, 100);
      stateV3.statusTimer = setInterval(pollBackend, 1000);

    } catch (error) {
      status('Unable to start listening: ' + error.message, false);
      stopPlayer();
    }
  }

  async function endListening() {
    try {
      await fetch(
        '/VirtualRadar/Airband/Stop.json?_=' + Date.now(),
        { cache: 'no-store' }
      );
    } catch (error) {
      console.log('Unable to stop backend:', error);
    }

    stateV3.listening = false;
    stopPlayer();

    element('airband-v3-listen').disabled = false;
    element('airband-v3-stop').disabled = true;
    element('airband-v3-best').disabled = false;

    status('ADS-B tracking active.', false);
    renderRows();
  }

'''

s = s[:start] + new_functions + s[end:]

HTML.write_text(s, encoding="utf-8")

print("Installed Web Audio buffered playback for continuous airband listening.")
print("Audio is scheduled as sequential half-second blocks with one-second startup buffering.")
