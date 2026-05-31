#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

marker = "airband-options-controller-v2"

if marker in s:
    print("Airband Options controller v2 is already installed.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Remove the existing standalone Airband <details> panel.
# ---------------------------------------------------------------------------

panel_start = s.find('<details id="airband-panel">')

if panel_start >= 0:
    panel_end = s.find('</details>', panel_start)
    if panel_end < 0:
        raise SystemExit("Found airband-panel start but not its closing </details>.")
    panel_end += len('</details>')
    s = s[:panel_start] + s[panel_end:]
    print("Removed standalone Airband Listen panel.")
else:
    print("Standalone Airband Listen panel was not present.")

# ---------------------------------------------------------------------------
# Add a compact Airband section inside the existing Options panel.
# ---------------------------------------------------------------------------

options_body = '<div id="options-panel-body">'

if options_body not in s:
    raise SystemExit("Could not find options-panel-body.")

airband_html = r'''
          <section id="airband-panel">
            <div class="airband-title">Airband Listen</div>
            <div id="airband-status">Loading deployed airband frequency data...</div>
            <div id="airband-source"></div>

            <div id="airband-table-wrap">
              <table id="airband-table">
                <thead>
                  <tr>
                    <th>Freq</th>
                    <th>Use / Facility</th>
                    <th>Dist</th>
                  </tr>
                </thead>
                <tbody id="airband-rows"></tbody>
              </table>
            </div>

            <div id="airband-selected">Select a listed frequency.</div>

            <div id="airband-audio-area">
              <audio id="airband-audio-player" controls preload="none"></audio>
              <div id="airband-audio-note">
                Live AM audio uses short WAV segments. Press Play manually if browser autoplay is blocked.
              </div>
            </div>

            <div class="airband-actions">
              <button type="button" id="airband-best">Select Best Nearby</button>
              <button type="button" id="airband-listen">Listen</button>
              <button type="button" id="airband-stop" disabled>Stop / Resume ADS-B</button>
            </div>
          </section>
'''

insert_at = s.find(options_body) + len(options_body)
s = s[:insert_at] + airband_html + s[insert_at:]

# ---------------------------------------------------------------------------
# Add overriding compact layout styles.
# ---------------------------------------------------------------------------

css = r'''
/* airband-options-controller-v2 */
#options-panel #airband-panel {
  margin-top: 10px;
  margin-bottom: 12px;
  padding: 9px;
  border: 1px solid #31343a;
  border-radius: 5px;
  background: #171a1e;
}
#airband-panel .airband-title {
  margin-bottom: 8px;
  color: #ddd;
  font-size: 13px;
  font-weight: bold;
}
#airband-status {
  margin-bottom: 7px;
  color: #b7bec5;
  font-size: 12px;
  line-height: 1.35;
}
#airband-status.listening {
  color: #ffdf4d;
  font-weight: bold;
}
#airband-source {
  margin-bottom: 8px;
  color: #7f8992;
  font-size: 11px;
}
#airband-table-wrap {
  max-height: 245px;
  overflow: auto;
  border: 1px solid #30343a;
}
#airband-table {
  width: 100%;
  font-size: 11px;
}
#airband-table td, #airband-table th {
  padding: 5px;
}
#airband-table tr.selected-airband {
  background: #273941;
}
#airband-table tr:hover {
  background: #242c32;
}
.airband-frequency {
  color: #f1f3f4;
  font-weight: bold;
}
.airband-recommended {
  color: #ffdf4d;
}
#airband-selected {
  margin-top: 8px;
  color: #d9dde0;
  font-size: 12px;
  line-height: 1.4;
}
.airband-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 9px;
}
.airband-actions button {
  padding: 5px 9px;
  border: 1px solid #465058;
  border-radius: 4px;
  background: #262e34;
  color: #eee;
  cursor: pointer;
  font-size: 12px;
}
.airband-actions button:disabled {
  color: #707880;
  cursor: default;
}
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
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style> insertion point.")

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Remove the old Airband script, if present.
# ---------------------------------------------------------------------------

script_start = s.find('<script id="airband-listen-ui-v1">')

if script_start >= 0:
    script_end = s.find('</script>', script_start)
    if script_end < 0:
        raise SystemExit("Found old Airband script but not its closing </script>.")
    script_end += len('</script>')
    s = s[:script_start] + s[script_end:]
    print("Removed old Airband JavaScript controller.")

# ---------------------------------------------------------------------------
# Install a single, static-panel Airband controller.
# It displays frequencies even when receiver coordinates are not yet set.
# ---------------------------------------------------------------------------

script = r'''
<script id="airband-options-controller-v2">
(function () {
  let channels = [];
  let metadata = null;
  let selectedChannel = null;
  let recommended = null;
  let listening = false;
  let loaded = false;
  let audioTimer = null;
  let statusTimer = null;
  let lastReceiverKey = '';

  function byId(id) {
    return document.getElementById(id);
  }

  function receiverLocation() {
    if (typeof state === 'undefined' || !state.receiverLocation) {
      return null;
    }
    return state.receiverLocation;
  }

  function receiverKey() {
    const receiver = receiverLocation();
    if (!receiver) return '';
    return receiver.lat.toFixed(6) + '|' + receiver.lon.toFixed(6);
  }

  function distanceNm(lat1, lon1, lat2, lon2) {
    const toRad = value => value * Math.PI / 180;
    const p1 = toRad(lat1);
    const p2 = toRad(lat2);
    const dLat = toRad(lat2 - lat1);
    const dLon = toRad(lon2 - lon1);

    const h =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(p1) * Math.cos(p2) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);

    return 3440.065 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  }

  function channelFacility(channel) {
    return channel.airport_code ||
      channel.facility_id ||
      channel.facility_name ||
      channel.city ||
      'Unknown';
  }

  function channelKey(channel) {
    if (!channel) return '';
    return [
      channel.airport_code || '',
      channel.frequency_hz || '',
      channel.use || '',
      channel.facility_id || ''
    ].join('|');
  }

  function voicePriority(channel) {
    const text = (
      (channel.use || '') + ' ' +
      (channel.facility_type || '') + ' ' +
      (channel.facility_name || '')
    ).toUpperCase();

    if (text.includes('TOWER') || text.includes('CTAF') || text.includes('UNICOM')) return 1;
    if (text.includes('APPROACH') || text.includes('APCH') ||
        text.includes('DEPARTURE') || text.includes(' DEP ')) return 2;
    if (text.includes('GROUND')) return 3;
    if (text.includes('CLEARANCE') || text.includes('CLNC') ||
        text.includes('DELIVERY')) return 4;
    if (text.includes('ATIS') || text.includes('AWOS') || text.includes('ASOS')) return 6;

    return 5;
  }

  function displayedChannels() {
    const receiver = receiverLocation();

    const prepared = channels.map(channel => {
      const copy = Object.assign({}, channel);
      copy.voice_priority = voicePriority(copy);

      if (receiver) {
        copy.distance_nm = distanceNm(
          receiver.lat,
          receiver.lon,
          copy.lat,
          copy.lon
        );
      }

      return copy;
    });

    if (receiver) {
      prepared.sort((a, b) =>
        a.distance_nm - b.distance_nm ||
        a.voice_priority - b.voice_priority ||
        a.frequency_mhz - b.frequency_mhz
      );
    } else {
      prepared.sort((a, b) =>
        String(a.airport_code || '').localeCompare(String(b.airport_code || '')) ||
        a.voice_priority - b.voice_priority ||
        a.frequency_mhz - b.frequency_mhz
      );
    }

    return prepared;
  }

  function chooseRecommended(list) {
    const receiver = receiverLocation();

    if (!receiver || !list.length) {
      recommended = null;
      return;
    }

    const nearestAirport = list[0].airport_code || list[0].facility_id;

    const sameAirport = list
      .filter(channel =>
        (channel.airport_code || channel.facility_id) === nearestAirport
      )
      .sort((a, b) =>
        a.voice_priority - b.voice_priority ||
        a.frequency_mhz - b.frequency_mhz
      );

    recommended = sameAirport[0] || list[0];

    if (!selectedChannel || lastReceiverKey !== receiverKey()) {
      selectedChannel = recommended;
      lastReceiverKey = receiverKey();
    }
  }

  function showStatus(text, isListening) {
    const status = byId('airband-status');
    status.textContent = text;
    status.classList.toggle('listening', !!isListening);
  }

  function renderSelection() {
    const selected = byId('airband-selected');

    if (!selectedChannel) {
      selected.textContent = 'Select a listed frequency.';
      return;
    }

    const distanceText =
      typeof selectedChannel.distance_nm === 'number'
        ? ' · ' + selectedChannel.distance_nm.toFixed(1) + ' nm'
        : '';

    selected.textContent =
      'Selected: ' +
      selectedChannel.frequency_mhz.toFixed(3) + ' MHz AM · ' +
      (selectedChannel.use || 'Published') + ' · ' +
      channelFacility(selectedChannel) +
      distanceText;
  }

  function renderRows() {
    const rows = byId('airband-rows');
    const list = displayedChannels();

    chooseRecommended(list);
    rows.innerHTML = '';

    /*
     * Before a receiver is set, show the compact deployed dataset grouped by
     * airport. Once set, show the closest 30 channels by range.
     */
    const visible = receiverLocation() ? list.slice(0, 30) : list.slice(0, 60);

    for (const channel of visible) {
      const row = document.createElement('tr');
      const selected =
        selectedChannel &&
        channelKey(selectedChannel) === channelKey(channel);
      const isRecommended =
        recommended &&
        channelKey(recommended) === channelKey(channel);

      if (selected) {
        row.className = 'selected-airband';
      }

      const star = isRecommended
        ? '<span class="airband-recommended">★ </span>'
        : '';

      const distanceText =
        typeof channel.distance_nm === 'number'
          ? channel.distance_nm.toFixed(1) + ' nm'
          : '—';

      row.innerHTML =
        '<td class="airband-frequency">' + star +
          channel.frequency_mhz.toFixed(3) + '</td>' +
        '<td>' + (channel.use || 'Published') + '<br>' +
          '<span class="muted">' + channelFacility(channel) + '</span></td>' +
        '<td>' + distanceText + '</td>';

      row.addEventListener('click', function () {
        if (listening) {
          showStatus('Stop listening before selecting another frequency.', true);
          return;
        }

        selectedChannel = channel;
        renderSelection();
        renderRows();
      });

      rows.appendChild(row);
    }

    renderSelection();

    if (!loaded) {
      showStatus('Loading deployed airband frequency data...', false);
    } else if (!channels.length) {
      showStatus('No airband frequencies are present in the deployed database.', false);
    } else if (!receiverLocation()) {
      showStatus(
        channels.length +
        ' frequencies loaded. Set receiver location to rank the closest voice channel.',
        false
      );
    } else if (!listening && recommended) {
      showStatus(
        'Recommended: ' +
        recommended.frequency_mhz.toFixed(3) + ' MHz AM · ' +
        (recommended.use || 'Published') + ' · ' +
        channelFacility(recommended),
        false
      );
    }
  }

  async function loadFrequencies() {
    try {
      const response = await fetch(
        '/VirtualRadar/Airband/Frequencies.json?_=' + Date.now(),
        { cache: 'no-store' }
      );

      if (!response.ok) {
        throw new Error('HTTP ' + response.status);
      }

      const data = await response.json();
      metadata = data.metadata || {};
      channels = data.channels || [];
      loaded = true;

      const airports = Array.isArray(metadata.airports)
        ? metadata.airports.join(', ')
        : '';

      byId('airband-source').textContent =
        'FAA NASR ' + (metadata.effective_date || '') +
        ' · ' + channels.length + ' channels' +
        (airports ? ' · ' + airports : '');

      renderRows();
    } catch (error) {
      loaded = true;
      channels = [];
      showStatus('Unable to load frequency database: ' + error.message, false);
    }
  }

  function stopAudioPlayer() {
    if (audioTimer) {
      clearTimeout(audioTimer);
      audioTimer = null;
    }

    if (statusTimer) {
      clearInterval(statusTimer);
      statusTimer = null;
    }

    const player = byId('airband-audio-player');
    player.pause();
    player.removeAttribute('src');
    player.load();

    byId('airband-audio-area').classList.remove('visible');
  }

  async function playAudioChunk() {
    if (!listening) return;

    const player = byId('airband-audio-player');
    player.src = '/VirtualRadar/Airband/Audio.wav?_=' + Date.now();

    try {
      await player.play();
    } catch (error) {
      showStatus(
        'Listening is active. Press Play in the audio control if autoplay is blocked.',
        true
      );
    }
  }

  async function pollStatus() {
    if (!listening) return;

    try {
      const response = await fetch(
        '/VirtualRadar/Airband/Status.json?_=' + Date.now(),
        { cache: 'no-store' }
      );
      const backend = await response.json();

      if (backend.error) {
        showStatus('Backend error: ' + backend.error, true);
      } else if (backend.active) {
        showStatus(
          'Listening ' +
          (backend.frequency_hz / 1000000).toFixed(3) +
          ' MHz AM · ADS-B tracking paused · ' +
          (backend.pcm_samples || 0) +
          ' samples buffered.',
          true
        );
      } else if (backend.switching) {
        showStatus('Switching Pluto receiver into airband mode...', true);
      }
    } catch (error) {
      showStatus('Unable to read listening status: ' + error.message, true);
    }
  }

  async function startListening() {
    if (!selectedChannel) {
      showStatus('Select a frequency before listening.', false);
      return;
    }

    try {
      showStatus(
        'Switching to ' + selectedChannel.frequency_mhz.toFixed(3) + ' MHz AM...',
        false
      );

      const response = await fetch(
        '/VirtualRadar/Airband/Start.json?freq=' +
        encodeURIComponent(selectedChannel.frequency_hz) +
        '&_=' + Date.now(),
        { cache: 'no-store' }
      );

      const backend = await response.json();

      if (backend.error) {
        showStatus('Unable to start listening: ' + backend.error, false);
        return;
      }

      listening = true;
      byId('airband-listen').disabled = true;
      byId('airband-stop').disabled = false;
      byId('airband-best').disabled = true;
      byId('airband-audio-area').classList.add('visible');

      const player = byId('airband-audio-player');
      player.onended = function () {
        if (listening) {
          audioTimer = setTimeout(playAudioChunk, 80);
        }
      };

      player.onerror = function () {
        if (listening) {
          audioTimer = setTimeout(playAudioChunk, 600);
        }
      };

      showStatus(
        'Listening ' + selectedChannel.frequency_mhz.toFixed(3) +
        ' MHz AM · ADS-B tracking paused.',
        true
      );

      audioTimer = setTimeout(playAudioChunk, 1200);
      statusTimer = setInterval(pollStatus, 1000);

    } catch (error) {
      showStatus('Unable to start listening: ' + error.message, false);
    }
  }

  async function stopListening() {
    try {
      await fetch(
        '/VirtualRadar/Airband/Stop.json?_=' + Date.now(),
        { cache: 'no-store' }
      );
    } catch (error) {
      console.log('Stop request failed:', error);
    }

    listening = false;
    stopAudioPlayer();

    byId('airband-listen').disabled = false;
    byId('airband-stop').disabled = true;
    byId('airband-best').disabled = false;

    showStatus('ADS-B tracking active.', false);
    renderRows();
  }

  function initialize() {
    const panel = byId('airband-panel');

    if (!panel) {
      return;
    }

    byId('airband-best').addEventListener('click', function () {
      if (listening) return;

      const list = displayedChannels();
      chooseRecommended(list);

      if (!recommended) {
        showStatus('Set receiver location before selecting the best nearby channel.', false);
        return;
      }

      selectedChannel = recommended;
      renderRows();
    });

    byId('airband-listen').addEventListener('click', startListening);
    byId('airband-stop').addEventListener('click', stopListening);

    loadFrequencies();

    /*
     * Re-render periodically so changes made in the receiver location
     * controls immediately affect frequency recommendations.
     */
    setInterval(function () {
      if (!listening) {
        renderRows();
      }
    }, 1000);
  }

  initialize();
})();
</script>
'''

if "</body>" not in s:
    raise SystemExit("Could not find </body> for controller insertion.")

s = s.replace("</body>", script + "\n</body>", 1)

HTML.write_text(s, encoding="utf-8")

print("Moved Airband Listen inside collapsed Options.")
print("Installed static frequency-list controller with visible error reporting.")
