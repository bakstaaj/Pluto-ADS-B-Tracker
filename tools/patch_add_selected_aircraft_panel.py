#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

marker = "selected-aircraft-panel-v1"

if marker in s:
    print("Selected aircraft panel is already present.")
    raise SystemExit(0)

if "</body>" not in s:
    raise SystemExit("Could not find </body> in web/vrs_desktop.html.")

addition = r'''
<style>
#selected-aircraft-panel {
  display: none;
  margin-top: 10px;
  padding: 10px;
  border: 1px solid #36424a;
  border-radius: 5px;
  background: #1a2024;
  font-size: 12px;
}
#selected-aircraft-panel.visible {
  display: block;
}
#selected-aircraft-panel .selected-title {
  margin-bottom: 8px;
  color: #fff;
  font-size: 15px;
  font-weight: bold;
}
#selected-aircraft-panel .selected-subtitle {
  margin-left: 7px;
  color: #9da6ad;
  font-size: 12px;
  font-weight: normal;
}
#selected-aircraft-panel .selected-grid {
  display: grid;
  grid-template-columns: auto 1fr auto 1fr;
  gap: 5px 9px;
  margin-bottom: 9px;
}
#selected-aircraft-panel .selected-label {
  color: #858e95;
}
#selected-aircraft-panel .selected-value {
  color: #e6e9eb;
  text-align: right;
}
#selected-aircraft-panel .selected-actions {
  display: flex;
  gap: 7px;
}
#selected-aircraft-panel button {
  padding: 4px 9px;
  border: 1px solid #465058;
  border-radius: 4px;
  background: #262e34;
  color: #eee;
  cursor: pointer;
  font-size: 12px;
}
#selected-aircraft-panel button:hover {
  background: #354048;
}
</style>

<script id="selected-aircraft-panel-v1">
(function () {
  let installed = false;

  function value(value, suffix) {
    if (value === undefined || value === null || value === '') {
      return '—';
    }

    return String(value) + (suffix || '');
  }

  function selectedAircraft() {
    if (typeof state === 'undefined' ||
        !state.selectedId ||
        !state.aircraftById) {
      return null;
    }

    return state.aircraftById.get(String(state.selectedId)) || null;
  }

  function installPanel() {
    if (installed) {
      return true;
    }

    const header = document.getElementById('header');

    if (!header ||
        typeof state === 'undefined' ||
        !state.map) {
      return false;
    }

    header.insertAdjacentHTML(
      'beforeend',
      `<div id="selected-aircraft-panel">
        <div class="selected-title">
          <span id="selected-call"></span>
          <span class="selected-subtitle" id="selected-icao"></span>
        </div>
        <div class="selected-grid">
          <span class="selected-label">Altitude</span>
          <span class="selected-value" id="selected-alt"></span>
          <span class="selected-label">Speed</span>
          <span class="selected-value" id="selected-spd"></span>

          <span class="selected-label">Track</span>
          <span class="selected-value" id="selected-track"></span>
          <span class="selected-label">Messages</span>
          <span class="selected-value" id="selected-msgs"></span>

          <span class="selected-label">Distance</span>
          <span class="selected-value" id="selected-dist"></span>
          <span class="selected-label">Bearing</span>
          <span class="selected-value" id="selected-bearing"></span>

          <span class="selected-label">Last seen</span>
          <span class="selected-value" id="selected-age"></span>
        </div>
        <div class="selected-actions">
          <button type="button" id="selected-center">Center Aircraft</button>
          <button type="button" id="selected-clear">Clear Selection</button>
        </div>
      </div>`
    );

    document.getElementById('selected-center').addEventListener('click', function () {
      const aircraft = selectedAircraft();

      if (!aircraft ||
          typeof aircraft.Lat !== 'number' ||
          typeof aircraft.Long !== 'number') {
        return;
      }

      state.map.setView(
        [aircraft.Lat, aircraft.Long],
        Math.max(state.map.getZoom(), 10)
      );

      const id = String(aircraft.Id);
      if (state.markers && state.markers.has(id)) {
        state.markers.get(id).openPopup();
      }
    });

    document.getElementById('selected-clear').addEventListener('click', function () {
      state.selectedId = null;

      if (typeof refreshMarkerIcons === 'function') {
        refreshMarkerIcons();
      }

      if (state.map) {
        state.map.closePopup();
      }

      renderPanel();
    });

    installed = true;
    return true;
  }

  function renderPanel() {
    if (!installPanel()) {
      return;
    }

    const panel = document.getElementById('selected-aircraft-panel');
    const aircraft = selectedAircraft();

    if (!aircraft) {
      panel.classList.remove('visible');
      return;
    }

    let range = null;

    if (typeof distanceAndBearing === 'function') {
      range = distanceAndBearing(aircraft);
    }

    document.getElementById('selected-call').textContent =
      aircraft.Call || aircraft.Icao || String(aircraft.Id);

    document.getElementById('selected-icao').textContent =
      aircraft.Icao || '';

    document.getElementById('selected-alt').textContent =
      value(aircraft.Alt, ' ft');

    document.getElementById('selected-spd').textContent =
      value(aircraft.Spd, ' kt');

    document.getElementById('selected-track').textContent =
      value(aircraft.Trak, '°');

    document.getElementById('selected-msgs').textContent =
      value(aircraft.CMsgs, '');

    document.getElementById('selected-age').textContent =
      value(aircraft.TSecs, ' s');

    document.getElementById('selected-dist').textContent =
      range ? range.distanceNm.toFixed(1) + ' nm' : '—';

    document.getElementById('selected-bearing').textContent =
      range ? range.bearing.toFixed(0) + '°' : '—';

    panel.classList.add('visible');
  }

  function start() {
    if (!installPanel()) {
      window.setTimeout(start, 250);
      return;
    }

    renderPanel();
    window.setInterval(renderPanel, 250);
  }

  start();
})();
</script>
'''

s = s.replace("</body>", addition + "\n</body>", 1)
HTML.write_text(s, encoding="utf-8")

print("Added selected-aircraft detail panel.")
