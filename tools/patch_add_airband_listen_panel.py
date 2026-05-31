#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if 'id="airband-listen-ui-v1"' in s:
    print("Airband Listen UI is already installed.")
    raise SystemExit(0)

addition = r'''
<style>
#airband-panel {
  margin-top: 10px;
  border: 1px solid #31343a;
  border-radius: 5px;
  background: #1b1d21;
}
#airband-panel summary {
  cursor: pointer;
  padding: 8px 10px;
  color: #ddd;
  font-size: 13px;
  font-weight: bold;
  list-style: none;
  user-select: none;
}
#airband-panel summary::-webkit-details-marker { display: none; }
#airband-panel summary::before {
  content: '▶';
  display: inline-block;
  width: 16px;
  color: #9da6ad;
  font-size: 11px;
}
#airband-panel[open] summary::before { content: '▼'; }
#airband-panel-body {
  padding: 9px 10px 10px 10px;
  border-top: 1px solid #31343a;
  font-size: 12px;
}
#airband-status {
  margin-bottom: 8px;
  color: #aeb6be;
  line-height: 1.35;
}
#airband-source {
  margin: 8px 0;
  color: #7f8992;
  font-size: 11px;
}
#airband-table-wrap {
  max-height: 230px;
  overflow: auto;
  border: 1px solid #30343a;
}
#airband-table {
  width: 100%;
  font-size: 11px;
}
#airband-table td, #airband-table th {
  padding: 5px 5px;
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
.airband-actions {
  display: flex;
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
#airband-selected {
  margin-top: 8px;
  color: #d9dde0;
  line-height: 1.4;
}
</style>

<script id="airband-listen-ui-v1">
(function () {
  let channels = [];
  let selectedChannel = null;
  let metadata = null;
  let installed = false;

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

  function rankedChannels() {
    if (typeof state === 'undefined' || !state.receiverLocation) return [];

    return channels
      .map(channel => ({
        ...channel,
        distance_nm: distanceNm(
          state.receiverLocation.lat,
          state.receiverLocation.lon,
          channel.lat,
          channel.lon
        )
      }))
      .sort((a, b) =>
        a.distance_nm - b.distance_nm ||
        Number(a.priority || 9) - Number(b.priority || 9) ||
        a.frequency_mhz - b.frequency_mhz
      )
      .slice(0, 20);
  }

  function channelName(channel) {
    return channel.facility_id ||
      channel.facility_name ||
      channel.city ||
      'Unknown facility';
  }

  function installPanel() {
    if (installed) return true;

    const header = document.getElementById('header');
    const options = document.getElementById('options-panel');

    if (!header || typeof state === 'undefined') return false;

    const panel = document.createElement('details');
    panel.id = 'airband-panel';
    panel.innerHTML = `
      <summary>Airband Listen</summary>
      <div id="airband-panel-body">
        <div id="airband-status">Loading FAA airband frequency data...</div>
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
        <div class="airband-actions">
          <button type="button" id="airband-listen">Listen</button>
          <button type="button" id="airband-stop" disabled>Stop / Resume ADS-B</button>
        </div>
      </div>
    `;

    if (options) {
      header.insertBefore(panel, options);
    } else {
      header.appendChild(panel);
    }

    document.getElementById('airband-listen').addEventListener('click', function () {
      const status = document.getElementById('airband-status');

      if (!selectedChannel) {
        status.textContent = 'Select a frequency before starting listen mode.';
        return;
      }

      status.textContent =
        `Audio backend not installed yet. Selected ${selectedChannel.frequency_mhz.toFixed(3)} MHz AM; ADS-B tracking remains active.`;
    });

    document.getElementById('airband-stop').addEventListener('click', function () {
      document.getElementById('airband-status').textContent =
        'ADS-B tracking active.';
    });

    installed = true;
    return true;
  }

  function render() {
    if (!installPanel()) return;

    const status = document.getElementById('airband-status');
    const source = document.getElementById('airband-source');
    const rows = document.getElementById('airband-rows');

    if (!metadata) {
      status.textContent = 'FAA frequency database not loaded.';
      return;
    }

    source.textContent =
      `FAA NASR effective ${metadata.effective_date || 'unknown'} · ${metadata.record_count || channels.length} VHF channels`;

    if (!state.receiverLocation) {
      status.textContent = 'Set the receiver location in Options to find nearby airband frequencies.';
      rows.innerHTML = '';
      return;
    }

    const nearest = rankedChannels();

    status.textContent =
      nearest.length
        ? 'Nearby published VHF AM frequencies. Audio mode is the next implementation phase.'
        : 'No nearby VHF frequencies found in the deployed database.';

    rows.innerHTML = '';

    for (const channel of nearest) {
      const tr = document.createElement('tr');

      if (selectedChannel &&
          selectedChannel.frequency_hz === channel.frequency_hz &&
          selectedChannel.facility_id === channel.facility_id) {
        tr.className = 'selected-airband';
      }

      tr.innerHTML = `
        <td class="airband-frequency">${channel.frequency_mhz.toFixed(3)}</td>
        <td>${channel.use || channel.facility_type || 'Published'}<br>
          <span class="muted">${channelName(channel)}</span>
        </td>
        <td>${channel.distance_nm.toFixed(1)} nm</td>
      `;

      tr.addEventListener('click', function () {
        selectedChannel = channel;
        document.getElementById('airband-selected').textContent =
          `Selected: ${channel.frequency_mhz.toFixed(3)} MHz AM · ${channel.use || 'Published'} · ${channelName(channel)} · ${channel.distance_nm.toFixed(1)} nm`;
        render();
      });

      rows.appendChild(tr);
    }
  }

  async function loadData() {
    try {
      const response = await fetch(
        '/VirtualRadar/Airband/Frequencies.json?_=' + Date.now(),
        { cache: 'no-store' }
      );
      const data = await response.json();

      metadata = data.metadata || {};
      channels = data.channels || [];

      if (!channels.length) {
        document.getElementById('airband-status').textContent =
          metadata.message || 'No airband frequency records are deployed.';
      }

      render();
    } catch (error) {
      document.getElementById('airband-status').textContent =
        'Unable to load airband frequency database: ' + error;
    }
  }

  function start() {
    if (!installPanel()) {
      window.setTimeout(start, 250);
      return;
    }

    loadData();
    window.setInterval(render, 1000);
  }

  start();
})();
</script>
'''

if "</body>" not in s:
    raise SystemExit("Could not find </body> in web/vrs_desktop.html.")

s = s.replace("</body>", addition + "\n</body>", 1)
HTML.write_text(s, encoding="utf-8")

print("Added Airband Listen frequency-selection scaffold.")
