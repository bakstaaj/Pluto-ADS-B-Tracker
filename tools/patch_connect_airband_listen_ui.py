#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

marker = "airband-functional-audio-v1"

if marker in s:
    print("Functional airband audio UI is already installed.")
    raise SystemExit(0)

script_start = s.find('<script id="airband-listen-ui-v1">')
script_end = s.find('</script>', script_start)

if script_start < 0 or script_end < 0:
    raise SystemExit("Could not find the Airband Listen UI script.")

script_end += len('</script>')
script = s[script_start:script_end]

# ---------------------------------------------------------------------------
# Add audio player CSS.
# ---------------------------------------------------------------------------

css = r'''
#airband-audio-area {
  display: none;
  margin-top: 10px;
  padding: 8px;
  border: 1px solid #35414a;
  border-radius: 5px;
  background: #14191d;
}
#airband-audio-area.visible {
  display: block;
}
#airband-audio-area audio {
  width: 100%;
  height: 34px;
}
#airband-audio-note {
  margin-top: 5px;
  color: #8e98a1;
  font-size: 11px;
  line-height: 1.35;
}
.airband-listening {
  color: #ffdf4d !important;
  font-weight: bold;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style> insertion point.")

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Extend variables inside the Airband Listen script.
# ---------------------------------------------------------------------------

old_vars = """  let installed = false;
  let selectedReceiverKey = null;
  let actionStatus = '';
"""

new_vars = """  let installed = false;
  let selectedReceiverKey = null;
  let actionStatus = '';

  // airband-functional-audio-v1
  let playbackActive = false;
  let audioRefreshTimer = null;
  let backendStatusTimer = null;
"""

if old_vars not in script:
    raise SystemExit("Could not find Airband state variable block.")

script = script.replace(old_vars, new_vars, 1)

# ---------------------------------------------------------------------------
# Add audio player to the Airband panel.
# ---------------------------------------------------------------------------

old_panel = """        <div id="airband-selected">Select a listed frequency.</div>
        <div class="airband-actions">
          <button type="button" id="airband-best">Select Best Nearby</button>
          <button type="button" id="airband-listen">Listen</button>
          <button type="button" id="airband-stop" disabled>Stop / Resume ADS-B</button>
        </div>
"""

new_panel = """        <div id="airband-selected">Select a listed frequency.</div>
        <div id="airband-audio-area">
          <audio id="airband-audio-player" controls preload="none"></audio>
          <div id="airband-audio-note">
            Live AM audio is delivered in short WAV segments. Press Play manually if browser autoplay is blocked.
          </div>
        </div>
        <div class="airband-actions">
          <button type="button" id="airband-best">Select Best Nearby</button>
          <button type="button" id="airband-listen">Listen</button>
          <button type="button" id="airband-stop" disabled>Stop / Resume ADS-B</button>
        </div>
"""

if old_panel not in script:
    raise SystemExit("Could not find Airband panel button HTML.")

script = script.replace(old_panel, new_panel, 1)

# ---------------------------------------------------------------------------
# Add operational listen / playback functions before installPanel().
# ---------------------------------------------------------------------------

function_anchor = "  function installPanel() {"

audio_functions = r'''  function updateListenButtons() {
    const listenButton = document.getElementById('airband-listen');
    const stopButton = document.getElementById('airband-stop');

    if (!listenButton || !stopButton) {
      return;
    }

    listenButton.disabled = playbackActive;
    stopButton.disabled = !playbackActive;
  }

  function showAudioPlayer(visible) {
    const area = document.getElementById('airband-audio-area');

    if (!area) {
      return;
    }

    area.classList.toggle('visible', visible);
  }

  function stopAudioPlayback() {
    if (audioRefreshTimer) {
      window.clearTimeout(audioRefreshTimer);
      audioRefreshTimer = null;
    }

    if (backendStatusTimer) {
      window.clearInterval(backendStatusTimer);
      backendStatusTimer = null;
    }

    const audio = document.getElementById('airband-audio-player');

    if (audio) {
      audio.pause();
      audio.removeAttribute('src');
      audio.load();
    }

    showAudioPlayer(false);
  }

  async function refreshAudioChunk() {
    if (!playbackActive) {
      return;
    }

    const audio = document.getElementById('airband-audio-player');

    if (!audio) {
      return;
    }

    audio.src =
      '/VirtualRadar/Airband/Audio.wav?_=' + Date.now();

    try {
      await audio.play();
    } catch (error) {
      actionStatus =
        'Listening is active. Press Play in the audio control if your browser blocked automatic playback.';
      render();
    }
  }

  function queueNextAudioChunk() {
    if (!playbackActive) {
      return;
    }

    if (audioRefreshTimer) {
      window.clearTimeout(audioRefreshTimer);
    }

    audioRefreshTimer = window.setTimeout(refreshAudioChunk, 80);
  }

  async function pollBackendStatus() {
    try {
      const response = await fetch(
        '/VirtualRadar/Airband/Status.json?_=' + Date.now(),
        { cache: 'no-store' }
      );

      const backend = await response.json();

      if (backend.error) {
        actionStatus = 'Airband backend error: ' + backend.error;
        render();
        return;
      }

      if (playbackActive && backend.active) {
        const mhz = Number(backend.frequency_hz || 0) / 1000000;

        actionStatus =
          `Listening ${mhz.toFixed(3)} MHz AM · ADS-B tracking paused · ` +
          `${backend.pcm_samples || 0} audio samples buffered.`;
      } else if (playbackActive && backend.switching) {
        actionStatus = 'Switching Pluto receiver into airband listen mode...';
      }

      render();
    } catch (error) {
      actionStatus = 'Unable to read airband backend status: ' + error;
      render();
    }
  }

  async function startListening() {
    if (!selectedChannel) {
      actionStatus = 'Select a frequency before starting listen mode.';
      render();
      return;
    }

    try {
      actionStatus =
        `Switching to ${selectedChannel.frequency_mhz.toFixed(3)} MHz AM...`;
      render();

      const response = await fetch(
        '/VirtualRadar/Airband/Start.json?freq=' +
        encodeURIComponent(selectedChannel.frequency_hz) +
        '&_=' + Date.now(),
        { cache: 'no-store' }
      );

      const backend = await response.json();

      if (backend.error) {
        actionStatus = 'Unable to start listening: ' + backend.error;
        render();
        return;
      }

      playbackActive = true;
      updateListenButtons();
      showAudioPlayer(true);

      actionStatus =
        `Listening ${selectedChannel.frequency_mhz.toFixed(3)} MHz AM · ADS-B tracking paused.`;

      render();

      const audio = document.getElementById('airband-audio-player');

      if (audio) {
        audio.onended = queueNextAudioChunk;
        audio.onerror = function () {
          if (playbackActive) {
            audioRefreshTimer = window.setTimeout(refreshAudioChunk, 500);
          }
        };
      }

      /*
       * Give the Pluto a moment to tune and accumulate the first audio
       * samples before requesting the first WAV segment.
       */
      audioRefreshTimer = window.setTimeout(refreshAudioChunk, 1200);
      backendStatusTimer = window.setInterval(pollBackendStatus, 1000);

    } catch (error) {
      actionStatus = 'Unable to start airband listen mode: ' + error;
      render();
    }
  }

  async function stopListening() {
    try {
      actionStatus = 'Returning Pluto receiver to 1090 MHz ADS-B tracking...';
      render();

      await fetch(
        '/VirtualRadar/Airband/Stop.json?_=' + Date.now(),
        { cache: 'no-store' }
      );

    } catch (error) {
      actionStatus = 'Stop request failed: ' + error;
    }

    playbackActive = false;
    stopAudioPlayback();
    updateListenButtons();

    actionStatus = 'ADS-B tracking active.';
    render();
  }

'''

if function_anchor not in script:
    raise SystemExit("Could not find installPanel() function anchor.")

script = script.replace(
    function_anchor,
    audio_functions + function_anchor,
    1
)

# ---------------------------------------------------------------------------
# Replace scaffold-only Listen and Stop handlers.
# ---------------------------------------------------------------------------

old_handlers = """    document.getElementById('airband-listen').addEventListener('click', function () {
      if (!selectedChannel) {
        actionStatus = 'Select a frequency before starting listen mode.';
        render();
        return;
      }

      actionStatus =
        `Audio backend not installed yet. Selected ` +
        `${selectedChannel.frequency_mhz.toFixed(3)} MHz AM · ` +
        `${channelName(selectedChannel)}. ADS-B tracking remains active.`;

      render();
    });

    document.getElementById('airband-stop').addEventListener('click', function () {
      actionStatus = 'ADS-B tracking active.';
      render();
    });
"""

new_handlers = """    document.getElementById('airband-listen').addEventListener('click', function () {
      startListening();
    });

    document.getElementById('airband-stop').addEventListener('click', function () {
      stopListening();
    });
"""

if old_handlers not in script:
    raise SystemExit("Could not find scaffold Listen/Stop handler block.")

script = script.replace(old_handlers, new_handlers, 1)

# ---------------------------------------------------------------------------
# Prevent recommendation/frequency changes while listening is active.
# ---------------------------------------------------------------------------

old_best = """    document.getElementById('airband-best').addEventListener('click', function () {
      const ranked = rankedChannels();

      if (!ranked.length) {
"""

new_best = """    document.getElementById('airband-best').addEventListener('click', function () {
      if (playbackActive) {
        actionStatus = 'Stop listening before selecting a different frequency.';
        render();
        return;
      }

      const ranked = rankedChannels();

      if (!ranked.length) {
"""

if old_best not in script:
    raise SystemExit("Could not find Select Best Nearby handler block.")

script = script.replace(old_best, new_best, 1)

old_row_click = """      tr.addEventListener('click', function () {
        selectedReceiverKey = receiverKey();
        selectChannel(channel, 'manual');
        render();
      });
"""

new_row_click = """      tr.addEventListener('click', function () {
        if (playbackActive) {
          actionStatus = 'Stop listening before selecting a different frequency.';
          render();
          return;
        }

        selectedReceiverKey = receiverKey();
        selectChannel(channel, 'manual');
        render();
      });
"""

if old_row_click not in script:
    raise SystemExit("Could not find frequency row click handler.")

script = script.replace(old_row_click, new_row_click, 1)

# ---------------------------------------------------------------------------
# Give the status field a visual listening indicator.
# ---------------------------------------------------------------------------

old_status_logic = """    if (actionStatus) {
      status.textContent = actionStatus;
    } else if (recommendation) {
"""

new_status_logic = """    status.classList.toggle('airband-listening', playbackActive);

    if (actionStatus) {
      status.textContent = actionStatus;
    } else if (recommendation) {
"""

if old_status_logic not in script:
    raise SystemExit("Could not find Airband status render block.")

script = script.replace(old_status_logic, new_status_logic, 1)

# Replace only the Airband script in the HTML document.
s = s[:script_start] + script + s[script_end:]
HTML.write_text(s, encoding="utf-8")

print("Connected Airband Listen UI to operational backend endpoints.")
print("Added browser WAV playback and ADS-B resume control.")
