#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if "receiverLocation: null" in s:
    print("Receiver-location patch already applied.")
    raise SystemExit(0)

def replace_once(old, new, description):
    global s
    if old not in s:
        raise SystemExit(f"Could not find {description}.")
    s = s.replace(old, new, 1)

def replace_between(start_marker, end_marker, replacement, description):
    global s
    start = s.find(start_marker)
    if start < 0:
        raise SystemExit(f"Could not find start of {description}.")
    end = s.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"Could not find end of {description}.")
    s = s[:start] + replacement + s[end:]

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

replace_once(
"""#controls button:hover {
  background: #333;
}
""",
"""#controls button:hover {
  background: #333;
}
#controls button.active {
  background: #005d70;
  border-color: #00bddd;
}
#receiver-status {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  color: #9da6ad;
}
.receiver-site {
  color: #ffdf4d;
  font-weight: bold;
}
.selected-row {
  background: #27343a;
}
""",
"controls CSS block"
)

# ---------------------------------------------------------------------------
# Header controls
# ---------------------------------------------------------------------------

replace_once(
"""        <button type="button" id="clear-trails">Clear trails</button>
      </div>
""",
"""        <button type="button" id="clear-trails">Clear trails</button>
        <button type="button" id="set-receiver">Set receiver</button>
        <button type="button" id="clear-receiver">Clear receiver</button>
      </div>
      <span id="receiver-status">Receiver location not set</span>
""",
"controls HTML block"
)

# ---------------------------------------------------------------------------
# Table columns
# ---------------------------------------------------------------------------

replace_once(
"""            <th>Msgs</th>
            <th>Age</th>
""",
"""            <th>Msgs</th>
            <th>Age</th>
            <th>Dist</th>
            <th>Brg</th>
""",
"aircraft table header"
)

# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------

replace_once(
"""  trailMaxPoints: 80,
  config: {
""",
"""  trailMaxPoints: 80,
  receiverLocation: null,
  receiverMarker: null,
  ringLayers: [],
  settingReceiverLocation: false,
  config: {
""",
"application state block"
)

# ---------------------------------------------------------------------------
# Popup function
# ---------------------------------------------------------------------------

new_popup = r'''function popupHtml(a) {
  const range = distanceAndBearing(a);
  const rangeHtml = range
    ? `<div>Distance: ${range.distanceNm.toFixed(1)} nm</div>
       <div>Bearing: ${range.bearing.toFixed(0)}°</div>`
    : '';

  return `
    <div class="popup-title">${aircraftName(a)}</div>
    <div>ICAO: ${fmt(a.Icao)}</div>
    <div>Altitude: ${fmt(a.Alt, ' ft')}</div>
    <div>Speed: ${fmt(a.Spd, ' kt')}</div>
    <div>Track: ${fmt(a.Trak, '°')}</div>
    <div>Messages: ${fmt(a.CMsgs)}</div>
    <div>Age: ${fmt(a.TSecs, 's')}</div>
    ${rangeHtml}
  `;
}

'''

replace_between(
    "function popupHtml(a) {",
    "async function loadConfig() {",
    new_popup,
    "popupHtml function"
)

# ---------------------------------------------------------------------------
# Receiver location, rings, range and bearing functions
# ---------------------------------------------------------------------------

receiver_functions = r'''const RECEIVER_STORAGE_KEY = 'plutoAdsBReceiverLocation';
const RANGE_RINGS_NM = [25, 50, 100, 150];

function updateReceiverStatus(message = null) {
  const status = document.getElementById('receiver-status');

  if (message) {
    status.textContent = message;
    return;
  }

  if (!state.receiverLocation) {
    status.textContent = 'Receiver location not set';
    return;
  }

  status.textContent =
    `Receiver: ${state.receiverLocation.lat.toFixed(5)}, ${state.receiverLocation.lon.toFixed(5)} | Rings: 25 / 50 / 100 / 150 nm`;
}

function loadReceiverLocation() {
  try {
    const saved = window.localStorage.getItem(RECEIVER_STORAGE_KEY);
    if (!saved) return;

    const parsed = JSON.parse(saved);

    if (typeof parsed.lat === 'number' && typeof parsed.lon === 'number') {
      state.receiverLocation = parsed;
    }
  } catch (e) {
    console.log('Unable to load receiver location:', e);
  }
}

function saveReceiverLocation() {
  try {
    if (state.receiverLocation) {
      window.localStorage.setItem(
        RECEIVER_STORAGE_KEY,
        JSON.stringify(state.receiverLocation)
      );
    } else {
      window.localStorage.removeItem(RECEIVER_STORAGE_KEY);
    }
  } catch (e) {
    console.log('Unable to save receiver location:', e);
  }
}

function removeReceiverLayers() {
  if (state.receiverMarker) {
    state.map.removeLayer(state.receiverMarker);
    state.receiverMarker = null;
  }

  for (const layer of state.ringLayers) {
    state.map.removeLayer(layer);
  }

  state.ringLayers = [];
}

function drawReceiverLocation() {
  removeReceiverLayers();

  if (!state.receiverLocation) {
    updateReceiverStatus();
    return;
  }

  const position = [
    state.receiverLocation.lat,
    state.receiverLocation.lon
  ];

  state.receiverMarker = L.circleMarker(position, {
    radius: 7,
    color: '#111',
    weight: 2,
    fillColor: '#ffdf4d',
    fillOpacity: 1
  }).addTo(state.map);

  state.receiverMarker.bindPopup(
    `<div class="popup-title">Receiver Site</div>
     <div>Latitude: ${state.receiverLocation.lat.toFixed(6)}</div>
     <div>Longitude: ${state.receiverLocation.lon.toFixed(6)}</div>`
  );

  for (const ringNm of RANGE_RINGS_NM) {
    const ring = L.circle(position, {
      radius: ringNm * 1852,
      color: '#ffdf4d',
      weight: 1,
      opacity: 0.50,
      fill: false,
      dashArray: '5 7',
      interactive: false
    });

    ring.addTo(state.map);
    state.ringLayers.push(ring);
  }

  updateReceiverStatus();
}

function beginReceiverSelection() {
  state.settingReceiverLocation = true;
  const button = document.getElementById('set-receiver');
  button.classList.add('active');
  button.textContent = 'Click map location...';
  state.map.getContainer().style.cursor = 'crosshair';
  updateReceiverStatus('Click the map at your receiver antenna location.');
}

function finishReceiverSelection(latlng) {
  state.receiverLocation = {
    lat: latlng.lat,
    lon: latlng.lng
  };

  state.settingReceiverLocation = false;

  const button = document.getElementById('set-receiver');
  button.classList.remove('active');
  button.textContent = 'Set receiver';
  state.map.getContainer().style.cursor = '';

  saveReceiverLocation();
  drawReceiverLocation();
}

function clearReceiverLocation() {
  state.settingReceiverLocation = false;
  state.receiverLocation = null;

  const button = document.getElementById('set-receiver');
  button.classList.remove('active');
  button.textContent = 'Set receiver';
  state.map.getContainer().style.cursor = '';

  saveReceiverLocation();
  drawReceiverLocation();
}

function distanceAndBearing(a) {
  if (!state.receiverLocation || !hasPosition(a)) {
    return null;
  }

  const toRad = degrees => degrees * Math.PI / 180;
  const toDeg = radians => radians * 180 / Math.PI;

  const lat1 = toRad(state.receiverLocation.lat);
  const lon1 = toRad(state.receiverLocation.lon);
  const lat2 = toRad(a.Lat);
  const lon2 = toRad(a.Long);

  const dLat = lat2 - lat1;
  const dLon = lon2 - lon1;

  const h =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1) * Math.cos(lat2) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);

  const distanceNm = 3440.065 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));

  const y = Math.sin(dLon) * Math.cos(lat2);
  const x =
    Math.cos(lat1) * Math.sin(lat2) -
    Math.sin(lat1) * Math.cos(lat2) * Math.cos(dLon);

  const bearing = (toDeg(Math.atan2(y, x)) + 360) % 360;

  return {
    distanceNm,
    bearing
  };
}

'''

replace_once(
"function updateTrail(a) {\n",
receiver_functions + "function updateTrail(a) {\n",
"updateTrail insertion point"
)

# ---------------------------------------------------------------------------
# Handle map clicks for receiver placement or deselection
# ---------------------------------------------------------------------------

replace_once(
"""  state.map.on('click', () => {
    state.selectedId = null;
    refreshMarkerIcons();
  });
""",
"""  state.map.on('click', event => {
    if (state.settingReceiverLocation) {
      finishReceiverSelection(event.latlng);
      return;
    }

    state.selectedId = null;
    refreshMarkerIcons();
  });
""",
"map click handler"
)

# ---------------------------------------------------------------------------
# Replace table function to add distance and bearing
# ---------------------------------------------------------------------------

new_table = r'''function updateTable(acList) {
  const rows = document.getElementById('rows');
  rows.innerHTML = '';

  const sorted = [...acList].sort((a, b) => {
    const ac = aircraftName(a);
    const bc = aircraftName(b);
    return ac.localeCompare(bc);
  });

  for (const a of sorted) {
    const tr = document.createElement('tr');
    const id = String(a.Id);
    const name = aircraftName(a);
    const range = distanceAndBearing(a);
    const distance = range ? `${range.distanceNm.toFixed(1)} nm` : '';
    const bearing = range ? `${range.bearing.toFixed(0)}°` : '';

    if (id === state.selectedId) {
      tr.className = 'selected-row';
    }

    tr.innerHTML = `
      <td><span class="callsign">${name}</span><br><span class="muted">${fmt(a.Icao)}</span></td>
      <td>${fmt(a.Alt)}</td>
      <td>${fmt(a.Spd)}</td>
      <td>${fmt(a.Trak)}</td>
      <td>${fmt(a.CMsgs)}</td>
      <td>${fmt(a.TSecs, 's')}</td>
      <td>${fmt(distance)}</td>
      <td>${fmt(bearing)}</td>
    `;

    tr.onclick = () => {
      state.selectedId = id;
      refreshMarkerIcons();
      updateTable(acList);

      if (hasPosition(a) && state.markers.has(id)) {
        state.map.setView([a.Lat, a.Long], Math.max(state.map.getZoom(), 9));
        state.markers.get(id).openPopup();
      }
    };

    rows.appendChild(tr);
  }
}

'''

replace_between(
    "function updateTable(acList) {",
    "async function refresh() {",
    new_table,
    "updateTable function"
)

# ---------------------------------------------------------------------------
# Initialize receiver controls and stored location
# ---------------------------------------------------------------------------

replace_once(
"""  document.getElementById('clear-trails').addEventListener('click', () => {
    clearTrails();
  });

  await refresh();
""",
"""  document.getElementById('clear-trails').addEventListener('click', () => {
    clearTrails();
  });

  document.getElementById('set-receiver').addEventListener('click', () => {
    beginReceiverSelection();
  });

  document.getElementById('clear-receiver').addEventListener('click', () => {
    clearReceiverLocation();
  });

  loadReceiverLocation();
  drawReceiverLocation();

  await refresh();
""",
"main control initialization"
)

HTML.write_text(s, encoding="utf-8")
print("Added receiver location selection, range rings, distance and bearing.")
