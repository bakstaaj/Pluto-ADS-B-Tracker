#!/usr/bin/env python3
from pathlib import Path

html_path = Path("web/vrs_desktop.html")
s = html_path.read_text(encoding="utf-8")

marker = "receiver-rings-overlay-v1"

if marker in s:
    print("Receiver overlay v1 is already present.")
    raise SystemExit(0)

if "</body>" not in s:
    raise SystemExit("Could not find </body> in web/vrs_desktop.html.")

overlay = r'''
<style>
.rx-control {
  background: rgba(18, 18, 18, 0.95);
  border: 1px solid #555;
  border-radius: 6px;
  box-shadow: 0 2px 9px rgba(0,0,0,0.55);
  color: #eee;
  font: 13px Arial, sans-serif;
  min-width: 205px;
  padding: 10px;
}
.rx-control-title {
  color: #ffdf4d;
  font-size: 14px;
  font-weight: bold;
  margin-bottom: 8px;
}
.rx-control-buttons {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}
.rx-control button {
  background: #252525;
  border: 1px solid #666;
  border-radius: 4px;
  color: #eee;
  cursor: pointer;
  font-size: 12px;
  padding: 5px 8px;
}
.rx-control button:hover {
  background: #363636;
}
.rx-control button.active {
  background: #886d00;
  border-color: #ffdf4d;
}
.rx-control-status {
  color: #ccc;
  font-size: 11px;
  line-height: 1.35;
}
.rx-ring-label {
  background: rgba(20,20,20,0.82);
  border: 1px solid #ffdf4d;
  border-radius: 3px;
  box-shadow: none;
  color: #ffdf4d;
  font-size: 10px;
  padding: 1px 4px;
}
.rx-ring-label::before {
  display: none;
}
</style>

<script id="receiver-rings-overlay-v1">
(function () {
  const STORAGE_KEY = 'plutoAdsBReceiverOverlayLocationV1';
  const RANGE_RINGS_NM = [25, 50, 100, 150];

  let map = null;
  let receiverMarker = null;
  let ringLayers = [];
  let selecting = false;
  let setButton = null;
  let statusElement = null;

  function setStatus(text) {
    if (statusElement) statusElement.textContent = text;
  }

  function removeLayers() {
    if (!map) return;

    if (receiverMarker) {
      map.removeLayer(receiverMarker);
      receiverMarker = null;
    }

    for (const layer of ringLayers) {
      map.removeLayer(layer);
    }

    ringLayers = [];
  }

  function saveLocation(location) {
    try {
      if (location) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(location));
      } else {
        localStorage.removeItem(STORAGE_KEY);
      }
    } catch (e) {
      console.log('Receiver location storage failed:', e);
    }
  }

  function loadLocation() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return null;

      const parsed = JSON.parse(saved);
      if (typeof parsed.lat === 'number' && typeof parsed.lon === 'number') {
        return parsed;
      }
    } catch (e) {
      console.log('Receiver location load failed:', e);
    }

    return null;
  }

  function drawReceiver(location) {
    removeLayers();

    if (!location) {
      setStatus('Receiver location not set.');
      return;
    }

    const point = [location.lat, location.lon];

    receiverMarker = L.circleMarker(point, {
      radius: 7,
      color: '#151515',
      weight: 2,
      fillColor: '#ffdf4d',
      fillOpacity: 1
    }).addTo(map);

    receiverMarker.bindPopup(
      '<b>Receiver Site</b><br>' +
      'Lat: ' + location.lat.toFixed(6) + '<br>' +
      'Lon: ' + location.lon.toFixed(6)
    );

    for (const distanceNm of RANGE_RINGS_NM) {
      const ring = L.circle(point, {
        radius: distanceNm * 1852,
        color: '#ffdf4d',
        weight: 2,
        opacity: 0.72,
        fill: false,
        dashArray: '7 7',
        interactive: false
      }).addTo(map);

      ring.bindTooltip(distanceNm + ' nm', {
        permanent: true,
        direction: 'right',
        className: 'rx-ring-label',
        opacity: 0.90
      });

      ringLayers.push(ring);
    }

    setStatus(
      'Receiver: ' +
      location.lat.toFixed(5) + ', ' +
      location.lon.toFixed(5) +
      ' | Rings: 25 / 50 / 100 / 150 nm'
    );
  }

  function startSelection() {
    selecting = true;
    setButton.classList.add('active');
    setButton.textContent = 'Click map...';
    map.getContainer().style.cursor = 'crosshair';
    setStatus('Click the map at the receiver antenna location.');
  }

  function finishSelection(latlng) {
    const location = {
      lat: latlng.lat,
      lon: latlng.lng
    };

    selecting = false;
    setButton.classList.remove('active');
    setButton.textContent = 'Set receiver';
    map.getContainer().style.cursor = '';

    saveLocation(location);
    drawReceiver(location);
  }

  function clearReceiver() {
    selecting = false;
    setButton.classList.remove('active');
    setButton.textContent = 'Set receiver';
    map.getContainer().style.cursor = '';

    saveLocation(null);
    drawReceiver(null);
  }

  function installOverlay() {
    if (typeof L === 'undefined' ||
        typeof state === 'undefined' ||
        !state.map) {
      window.setTimeout(installOverlay, 250);
      return;
    }

    map = state.map;

    const ReceiverControl = L.Control.extend({
      options: {
        position: 'topright'
      },

      onAdd: function () {
        const panel = L.DomUtil.create('div', 'rx-control');
        panel.innerHTML =
          '<div class="rx-control-title">Receiver / Range Rings</div>' +
          '<div class="rx-control-buttons">' +
          '  <button type="button" id="rx-overlay-set">Set receiver</button>' +
          '  <button type="button" id="rx-overlay-clear">Clear</button>' +
          '</div>' +
          '<div class="rx-control-status" id="rx-overlay-status">' +
          'Receiver location not set.' +
          '</div>';

        L.DomEvent.disableClickPropagation(panel);
        L.DomEvent.disableScrollPropagation(panel);

        return panel;
      }
    });

    new ReceiverControl().addTo(map);

    setButton = document.getElementById('rx-overlay-set');
    statusElement = document.getElementById('rx-overlay-status');

    setButton.addEventListener('click', startSelection);
    document.getElementById('rx-overlay-clear').addEventListener('click', clearReceiver);

    map.on('click', function (event) {
      if (selecting) {
        finishSelection(event.latlng);
      }
    });

    drawReceiver(loadLocation());
  }

  installOverlay();
})();
</script>
'''

s = s.replace("</body>", overlay + "\n</body>", 1)
html_path.write_text(s, encoding="utf-8")

print("Added visible map overlay: Receiver / Range Rings.")
