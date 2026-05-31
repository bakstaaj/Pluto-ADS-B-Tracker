#!/usr/bin/env python3
import re
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
BACKUP = Path("web/vrs_desktop.before_airband_v3.html")

s = HTML.read_text(encoding="utf-8")
BACKUP.write_text(s, encoding="utf-8")

def remove_script_by_id(text, element_id):
    pattern = re.compile(
        r'\s*<script\b[^>]*\bid=["\']' + re.escape(element_id) +
        r'["\'][^>]*>.*?</script>\s*',
        re.IGNORECASE | re.DOTALL
    )
    return pattern.sub("\n", text)

def remove_balanced_element_by_id(text, tag, element_id):
    start_re = re.compile(
        r'<' + tag + r'\b[^>]*\bid=["\']' + re.escape(element_id) +
        r'["\'][^>]*>',
        re.IGNORECASE
    )
    match = start_re.search(text)
    if not match:
        return text

    token_re = re.compile(r'</?' + tag + r'\b[^>]*>', re.IGNORECASE)
    depth = 0

    for token in token_re.finditer(text, match.start()):
        value = token.group(0).lower()
        if value.startswith('</'):
            depth -= 1
            if depth == 0:
                return text[:match.start()] + text[token.end():]
        else:
            depth += 1

    raise SystemExit(f"Could not find closing {tag} tag for id={element_id}")

# ---------------------------------------------------------------------------
# Remove all prior Airband panels and JavaScript controllers.
# ---------------------------------------------------------------------------

for script_id in [
    "airband-listen-ui-v1",
    "airband-options-controller-v2",
    "airband-functional-audio-v1",
]:
    s = remove_script_by_id(s, script_id)

# Previous implementations used either a details block or a section.
s = remove_balanced_element_by_id(s, "details", "airband-panel")
s = remove_balanced_element_by_id(s, "section", "airband-panel")

# Remove the visible orphaned JavaScript tail left by an earlier patch.
orphan_pattern = re.compile(
    r'\s*(?:document\.getElementById\()?["\']airband-status["\']\)?'
    r'\.textContent\s*=\s*["\']Unable to load airband frequency database:\s*["\']'
    r'\s*\+\s*error\s*;.*?start\s*\(\s*\)\s*;\s*\}\)\s*\(\s*\)\s*;?\s*',
    re.DOTALL
)
s, orphan_count = orphan_pattern.subn("\n", s)

# A second form can start with only the trailing argument visible in HTML.
orphan_tail_pattern = re.compile(
    r'\s*["\']airband-status["\']\)\.textContent\s*=\s*'
    r'["\']Unable to load airband frequency database:\s*["\']'
    r'\s*\+\s*error\s*;.*?start\s*\(\s*\)\s*;\s*\}\)\s*\(\s*\)\s*;?\s*',
    re.DOTALL
)
s, orphan_tail_count = orphan_tail_pattern.subn("\n", s)

# ---------------------------------------------------------------------------
# Add a clean Airband panel inside the existing collapsed Options panel.
# ---------------------------------------------------------------------------

options_body = '<div id="options-panel-body">'

if options_body not in s:
    raise SystemExit("Could not find options-panel-body in web/vrs_desktop.html.")

panel_html = r'''
          <section id="airband-panel-v3">
            <div class="airband-v3-title">Airband Listen</div>
            <div id="airband-v3-status">Loading airband frequency data...</div>
            <div id="airband-v3-source"></div>

            <div id="airband-v3-table-wrap">
              <table id="airband-v3-table">
                <thead>
                  <tr>
                    <th>Freq</th>
                    <th>Use / Airport</th>
                    <th>Dist</th>
                  </tr>
                </thead>
                <tbody id="airband-v3-rows"></tbody>
              </table>
            </div>

            <div id="airband-v3-selected">Select a frequency.</div>

            <div id="airband-v3-audio-area">
              <audio id="airband-v3-audio" controls preload="none"></audio>
              <div class="airband-v3-note">
                Live AM audio uses short WAV segments. Press Play if browser autoplay is blocked.
              </div>
            </div>

            <div class="airband-v3-actions">
              <button type="button" id="airband-v3-best">Select Best Nearby</button>
              <button type="button" id="airband-v3-listen">Listen</button>
              <button type="button" id="airband-v3-stop" disabled>Stop / Resume ADS-B</button>
            </div>
          </section>
'''

insert_pos = s.find(options_body) + len(options_body)
s = s[:insert_pos] + panel_html + s[insert_pos:]

css = r'''
/* Clean Airband Listen panel v3 */
#airband-panel-v3 {
  margin: 10px 0 12px 0;
  padding: 9px;
  border: 1px solid #31343a;
  border-radius: 5px;
  background: #171a1e;
}
.airband-v3-title {
  margin-bottom: 8px;
  color: #ddd;
  font-size: 13px;
  font-weight: bold;
}
#airband-v3-status {
  margin-bottom: 7px;
  color: #b7bec5;
  font-size: 12px;
  line-height: 1.35;
}
#airband-v3-status.listening {
  color: #ffdf4d;
  font-weight: bold;
}
#airband-v3-source {
  margin-bottom: 8px;
  color: #7f8992;
  font-size: 11px;
}
#airband-v3-table-wrap {
  max-height: 245px;
  overflow-y: auto;
  border: 1px solid #30343a;
}
#airband-v3-table {
  width: 100%;
  font-size: 11px;
}
#airband-v3-table th,
#airband-v3-table td {
  padding: 5px;
}
#airband-v3-table tr.selected {
  background: #273941;
}
#airband-v3-table tr:hover {
  background: #242c32;
}
.airband-v3-frequency {
  color: #f1f3f4;
  font-weight: bold;
}
.airband-v3-star {
  color: #ffdf4d;
}
#airband-v3-selected {
  margin-top: 8px;
  color: #d9dde0;
  font-size: 12px;
  line-height: 1.4;
}
#airband-v3-audio-area {
  display: none;
  margin-top: 10px;
  padding: 8px;
  border: 1px solid #35414a;
  border-radius: 5px;
  background: #14191d;
}
#airband-v3-audio-area.visible {
  display: block;
}
#airband-v3-audio {
  width: 100%;
  height: 34px;
}
.airband-v3-note {
  margin-top: 5px;
  color: #8e98a1;
  font-size: 11px;
}
.airband-v3-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 9px;
}
.airband-v3-actions button {
  padding: 5px 9px;
  border: 1px solid #465058;
  border-radius: 4px;
  background: #262e34;
  color: #eee;
  cursor: pointer;
  font-size: 12px;
}
.airband-v3-actions button:disabled {
  color: #707880;
  cursor: default;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style>.")

s = s.replace("</style>", css + "\n</style>", 1)

controller = r'''
<script id="airband-controller-v3">
(function () {
  const stateV3 = {
    channels: [],
    metadata: null,
    selected: null,
    recommended: null,
    listening: false,
    loaded: false,
    audioTimer: null,
    statusTimer: null,
    lastReceiverKey: ''
  };

  function element(id) {
    return document.getElementById(id);
  }

  function receiver() {
    if (typeof state === 'undefined' || !state.receiverLocation) {
      return null;
    }
    return state.receiverLocation;
  }

  function receiverKey() {
    const value = receiver();
    if (!value) return '';
    return value.lat.toFixed(6) + '|' + value.lon.toFixed(6);
  }

  function distanceNm(lat1, lon1, lat2, lon2) {
    const radians = value => value * Math.PI / 180;
    const p1 = radians(lat1);
    const p2 = radians(lat2);
    const dLat = radians(lat2 - lat1);
    const dLon = radians(lon2 - lon1);
    const h =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(p1) * Math.cos(p2) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 3440.065 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
  }

  function key(channel) {
    if (!channel) return '';
    return [
      channel.airport_code || '',
      channel.frequency_hz || '',
      channel.use || '',
      channel.facility_id || ''
    ].join('|');
  }

  function airport(channel) {
    return channel.airport_code ||
      channel.facility_id ||
      channel.facility_name ||
      channel.city ||
      'Unknown';
  }

  function priority(channel) {
    const text = String(channel.use || '').toUpperCase();

    if (text.includes('TOWER') || text.includes('CTAF') || text.includes('UNICOM')) return 1;
    if (text.includes('APPROACH') || text.includes('APCH') ||
        text.includes('DEPARTURE') || text.includes(' DEP ')) return 2;
    if (text.includes('GROUND')) return 3;
    if (text.includes('CLEARANCE') || text.includes('CLNC') ||
        text.includes('DELIVERY')) return 4;
    if (text.includes('ATIS') || text.includes('AWOS') || text.includes('ASOS')) return 6;
    return 5;
  }

  function preparedChannels() {
    const site = receiver();
    const result = stateV3.channels.map(channel => {
      const value = Object.assign({}, channel);
      value.priority = priority(value);
      if (site) {
        value.distance_nm = distanceNm(site.lat, site.lon, value.lat, value.lon);
      }
      return value;
    });

    if (site) {
      result.sort((a, b) =>
        a.distance_nm - b.distance_nm ||
        a.priority - b.priority ||
        a.frequency_mhz - b.frequency_mhz
      );
    } else {
      result.sort((a, b) =>
        String(a.airport_code || '').localeCompare(String(b.airport_code || '')) ||
        a.priority - b.priority ||
        a.frequency_mhz - b.frequency_mhz
      );
    }

    return result;
  }

  function chooseBest(list) {
    const site = receiver();

    if (!site || !list.length) {
      stateV3.recommended = null;
      return;
    }

    const nearestAirport = list[0].airport_code || list[0].facility_id;
    const nearbyAirportChannels = list.filter(channel =>
      (channel.airport_code || channel.facility_id) === nearestAirport
    );

    nearbyAirportChannels.sort((a, b) =>
      a.priority - b.priority ||
      a.frequency_mhz - b.frequency_mhz
    );

    stateV3.recommended = nearbyAirportChannels[0] || list[0];

    if (!stateV3.selected || stateV3.lastReceiverKey !== receiverKey()) {
      stateV3.selected = stateV3.recommended;
      stateV3.lastReceiverKey = receiverKey();
    }
  }

  function status(message, listening) {
    const output = element('airband-v3-status');
    output.textContent = message;
    output.classList.toggle('listening', !!listening);
  }

  function renderSelected() {
    const output = element('airband-v3-selected');

    if (!stateV3.selected) {
      output.textContent = 'Select a frequency.';
      return;
    }

    const distance =
      typeof stateV3.selected.distance_nm === 'number'
        ? ' · ' + stateV3.selected.distance_nm.toFixed(1) + ' nm'
        : '';

    output.textContent =
      'Selected: ' +
      stateV3.selected.frequency_mhz.toFixed(3) + ' MHz AM · ' +
      (stateV3.selected.use || 'Published') + ' · ' +
      airport(stateV3.selected) +
      distance;
  }

  function renderRows() {
    const rows = element('airband-v3-rows');
    const list = preparedChannels();

    chooseBest(list);
    rows.innerHTML = '';

    const visible = receiver() ? list.slice(0, 30) : list.slice(0, 60);

    visible.forEach(channel => {
      const row = document.createElement('tr');
      const isSelected = stateV3.selected && key(stateV3.selected) === key(channel);
      const isRecommended = stateV3.recommended && key(stateV3.recommended) === key(channel);

      if (isSelected) row.className = 'selected';

      const frequencyCell = document.createElement('td');
      frequencyCell.className = 'airband-v3-frequency';
      frequencyCell.innerHTML =
        (isRecommended ? '<span class="airband-v3-star">★ </span>' : '') +
        channel.frequency_mhz.toFixed(3);

      const useCell = document.createElement('td');
      useCell.textContent = (channel.use || 'Published') + ' / ' + airport(channel);

      const distanceCell = document.createElement('td');
      distanceCell.textContent =
        typeof channel.distance_nm === 'number'
          ? channel.distance_nm.toFixed(1) + ' nm'
          : '—';

      row.appendChild(frequencyCell);
      row.appendChild(useCell);
      row.appendChild(distanceCell);

      row.addEventListener('click', function () {
        if (stateV3.listening) {
          status('Stop listening before changing frequencies.', true);
          return;
        }

        stateV3.selected = channel;
        renderRows();
        renderSelected();
      });

      rows.appendChild(row);
    });

    renderSelected();

    if (!stateV3.loaded) {
      status('Loading airband frequency data...', false);
    } else if (!stateV3.channels.length) {
      status('The deployed airband database contains no frequencies.', false);
    } else if (!receiver()) {
      status(
        stateV3.channels.length +
        ' frequencies loaded. Set receiver location for nearest-channel recommendation.',
        false
      );
    } else if (!stateV3.listening && stateV3.recommended) {
      status(
        'Recommended: ' +
        stateV3.recommended.frequency_mhz.toFixed(3) +
        ' MHz AM · ' +
        (stateV3.recommended.use || 'Published') +
        ' · ' +
        airport(stateV3.recommended),
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
      stateV3.metadata = data.metadata || {};
      stateV3.channels = data.channels || [];
      stateV3.loaded = true;

      const airports = Array.isArray(stateV3.metadata.airports)
        ? stateV3.metadata.airports.join(', ')
        : '';

      element('airband-v3-source').textContent =
        'FAA NASR ' + (stateV3.metadata.effective_date || '') +
        ' · ' + stateV3.channels.length + ' channels' +
        (airports ? ' · ' + airports : '');

      renderRows();
    } catch (error) {
      stateV3.loaded = true;
      status('Unable to load frequencies: ' + error.message, false);
    }
  }

  function stopPlayer() {
    if (stateV3.audioTimer) clearTimeout(stateV3.audioTimer);
    if (stateV3.statusTimer) clearInterval(stateV3.statusTimer);

    const player = element('airband-v3-audio');
    player.pause();
    player.removeAttribute('src');
    player.load();

    element('airband-v3-audio-area').classList.remove('visible');
  }

  async function playAudioChunk() {
    if (!stateV3.listening) return;

    const player = element('airband-v3-audio');
    player.src = '/VirtualRadar/Airband/Audio.wav?_=' + Date.now();

    try {
      await player.play();
    } catch (error) {
      status('Listening is active. Press Play if browser autoplay is blocked.', true);
    }
  }

  async function pollBackend() {
    if (!stateV3.listening) return;

    try {
      const response = await fetch(
        '/VirtualRadar/Airband/Status.json?_=' + Date.now(),
        { cache: 'no-store' }
      );
      const backend = await response.json();

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
      }
    } catch (error) {
      status('Unable to read backend status: ' + error.message, true);
    }
  }

  async function beginListening() {
    if (!stateV3.selected) {
      status('Select a frequency before listening.', false);
      return;
    }

    try {
      const response = await fetch(
        '/VirtualRadar/Airband/Start.json?freq=' +
        encodeURIComponent(stateV3.selected.frequency_hz) +
        '&_=' + Date.now(),
        { cache: 'no-store' }
      );
      const backend = await response.json();

      if (backend.error) {
        status('Unable to start listening: ' + backend.error, false);
        return;
      }

      stateV3.listening = true;
      element('airband-v3-listen').disabled = true;
      element('airband-v3-stop').disabled = false;
      element('airband-v3-best').disabled = true;
      element('airband-v3-audio-area').classList.add('visible');

      const player = element('airband-v3-audio');
      player.onended = function () {
        if (stateV3.listening) {
          stateV3.audioTimer = setTimeout(playAudioChunk, 100);
        }
      };

      status(
        'Listening ' +
        stateV3.selected.frequency_mhz.toFixed(3) +
        ' MHz AM · ADS-B paused.',
        true
      );

      stateV3.audioTimer = setTimeout(playAudioChunk, 1200);
      stateV3.statusTimer = setInterval(pollBackend, 1000);

    } catch (error) {
      status('Unable to start listening: ' + error.message, false);
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

  function initialize() {
    if (!element('airband-panel-v3')) return;

    element('airband-v3-best').addEventListener('click', function () {
      const list = preparedChannels();
      chooseBest(list);

      if (!stateV3.recommended) {
        status('Set receiver location before choosing the best nearby channel.', false);
        return;
      }

      stateV3.selected = stateV3.recommended;
      renderRows();
    });

    element('airband-v3-listen').addEventListener('click', beginListening);
    element('airband-v3-stop').addEventListener('click', endListening);

    loadFrequencies();

    setInterval(function () {
      if (!stateV3.listening) renderRows();
    }, 1000);
  }

  initialize();
})();
</script>
'''

if "</body>" not in s:
    raise SystemExit("Could not find </body>.")

s = s.replace("</body>", controller + "\n</body>", 1)

# The old rendered-JavaScript symptom must now be absent from source.
if "Unable to load airband frequency database:" in s:
    raise SystemExit(
        "An old orphaned JavaScript fragment still remains. "
        "Restore web/vrs_desktop.before_airband_v3.html and inspect Airband sections."
    )

HTML.write_text(s, encoding="utf-8")

print("Backed up original HTML to:", BACKUP)
print("Removed old Airband panel/controller fragments.")
print("Installed clean Airband Listen v3 inside collapsed Options.")
print("Removed orphaned JavaScript fragments:", orphan_count + orphan_tail_count)
