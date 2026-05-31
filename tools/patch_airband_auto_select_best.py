#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

start_marker = '<script id="airband-listen-ui-v1">'
start = s.find(start_marker)

if start < 0:
    raise SystemExit("Could not find the existing Airband Listen script.")

end = s.find('</script>', start)
if end < 0:
    raise SystemExit("Could not find the end of the Airband Listen script.")

end += len('</script>')

new_script = r'''<script id="airband-listen-ui-v1">
(function () {
  let channels = [];
  let selectedChannel = null;
  let recommendation = null;
  let metadata = null;
  let installed = false;
  let selectedReceiverKey = null;
  let actionStatus = '';

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

  function receiverKey() {
    if (typeof state === 'undefined' || !state.receiverLocation) {
      return '';
    }

    return (
      state.receiverLocation.lat.toFixed(6) + '|' +
      state.receiverLocation.lon.toFixed(6)
    );
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

  function channelName(channel) {
    if (!channel) return '';

    return channel.airport_code ||
      channel.facility_id ||
      channel.facility_name ||
      channel.city ||
      'Unknown facility';
  }

  function voicePriority(channel) {
    const text = (
      (channel.use || '') + ' ' +
      (channel.facility_type || '') + ' ' +
      (channel.facility_name || '')
    ).toUpperCase();

    if (text.includes('TOWER') ||
        text.includes('CTAF') ||
        text.includes('UNICOM')) {
      return 1;
    }

    if (text.includes('APPROACH') ||
        text.includes('APCH') ||
        text.includes('DEPARTURE') ||
        text.includes(' DEPART') ||
        text.includes(' DEP ')) {
      return 2;
    }

    if (text.includes('GROUND')) {
      return 3;
    }

    if (text.includes('CLEARANCE') ||
        text.includes('CLNC') ||
        text.includes('DELIVERY')) {
      return 4;
    }

    if (text.includes('ATIS') ||
        text.includes('AWOS') ||
        text.includes('ASOS')) {
      return 6;
    }

    return 5;
  }

  function rankedChannels() {
    if (typeof state === 'undefined' || !state.receiverLocation) {
      return [];
    }

    return channels
      .map(channel => ({
        ...channel,
        distance_nm: distanceNm(
          state.receiverLocation.lat,
          state.receiverLocation.lon,
          channel.lat,
          channel.lon
        ),
        voice_priority: voicePriority(channel)
      }))
      .sort((a, b) =>
        a.distance_nm - b.distance_nm ||
        a.voice_priority - b.voice_priority ||
        a.frequency_mhz - b.frequency_mhz
      );
  }

  function recommendedChannel(ranked) {
    if (!ranked.length) {
      return null;
    }

    /*
     * Pick the closest airport/facility first, then choose its best useful
     * voice frequency. This prevents a distant Tower frequency from being
     * recommended over a nearby airport.
     */
    const nearest = ranked[0];
    const airportCode = nearest.airport_code || nearest.facility_id;

    const sameAirport = ranked.filter(channel =>
      (channel.airport_code || channel.facility_id) === airportCode
    );

    return sameAirport
      .sort((a, b) =>
        a.voice_priority - b.voice_priority ||
        a.distance_nm - b.distance_nm ||
        a.frequency_mhz - b.frequency_mhz
      )[0] || nearest;
  }

  function selectChannel(channel, reason) {
    selectedChannel = channel;
    actionStatus = '';

    const selected = document.getElementById('airband-selected');

    if (!channel) {
      selected.textContent = 'Select a listed frequency.';
      return;
    }

    const prefix = reason === 'recommended'
      ? 'Recommended'
      : 'Selected';

    selected.textContent =
      `${prefix}: ${channel.frequency_mhz.toFixed(3)} MHz AM · ` +
      `${channel.use || 'Published'} · ${channelName(channel)} · ` +
      `${channel.distance_nm.toFixed(1)} nm`;
  }

  function automaticallyChooseBest(ranked, force) {
    recommendation = recommendedChannel(ranked);

    if (!recommendation) {
      return;
    }

    const currentReceiverKey = receiverKey();

    if (force ||
        !selectedChannel ||
        selectedReceiverKey !== currentReceiverKey) {
      selectedReceiverKey = currentReceiverKey;
      selectChannel(recommendation, 'recommended');
    }
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
          <button type="button" id="airband-best">Select Best Nearby</button>
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

    document.getElementById('airband-best').addEventListener('click', function () {
      const ranked = rankedChannels();

      if (!ranked.length) {
        document.getElementById('airband-status').textContent =
          'Set the receiver location before selecting a nearby frequency.';
        return;
      }

      automaticallyChooseBest(ranked, true);
      render();
    });

    document.getElementById('airband-listen').addEventListener('click', function () {
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

    const airportList = Array.isArray(metadata.airports)
      ? metadata.airports.join(', ')
      : '';

    source.textContent =
      `FAA NASR effective ${metadata.effective_date || 'unknown'} · ` +
      `${metadata.record_count || channels.length} channels` +
      (airportList ? ` · ${airportList}` : '');

    if (!state.receiverLocation) {
      status.textContent =
        'Set the receiver location in Options to find nearby airband frequencies.';
      rows.innerHTML = '';
      selectedChannel = null;
      selectedReceiverKey = null;
      document.getElementById('airband-selected').textContent =
        'Select a listed frequency.';
      return;
    }

    const ranked = rankedChannels();
    automaticallyChooseBest(ranked, false);

    if (actionStatus) {
      status.textContent = actionStatus;
    } else if (recommendation) {
      status.textContent =
        `Best nearby voice channel: ${recommendation.frequency_mhz.toFixed(3)} MHz AM · ` +
        `${recommendation.use || 'Published'} · ${channelName(recommendation)}`;
    } else {
      status.textContent = 'No nearby VHF frequencies found in the deployed database.';
    }

    rows.innerHTML = '';

    /*
     * Show up to 20 closest channels. The recommended channel is highlighted
     * even when the user selects another channel manually.
     */
    for (const channel of ranked.slice(0, 20)) {
      const tr = document.createElement('tr');
      const isSelected =
        selectedChannel &&
        channelKey(selectedChannel) === channelKey(channel);

      const isRecommended =
        recommendation &&
        channelKey(recommendation) === channelKey(channel);

      if (isSelected) {
        tr.className = 'selected-airband';
      }

      const star = isRecommended ? '★ ' : '';

      tr.innerHTML = `
        <td class="airband-frequency">${star}${channel.frequency_mhz.toFixed(3)}</td>
        <td>${channel.use || channel.facility_type || 'Published'}<br>
          <span class="muted">${channelName(channel)}</span>
        </td>
        <td>${channel.distance_nm.toFixed(1)} nm</td>
      `;

      tr.addEventListener('click', function () {
        selectedReceiverKey = receiverKey();
        selectChannel(channel, 'manual');
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
        actionStatus = metadata.message || 'No airband frequency records are deployed.';
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
</script>'''

s = s[:start] + new_script + s[end:]
HTML.write_text(s, encoding="utf-8")

print("Added Airband automatic best-nearby channel recommendation.")
print("Priority: Tower/CTAF/UNICOM, Approach/Departure, Ground, Clearance, Other, Weather.")
