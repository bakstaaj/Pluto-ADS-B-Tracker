#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if "function updateTrail(a)" not in s:
    raise SystemExit("Live trail feature is not present in web/vrs_desktop.html.")

def replace_between(text, start_marker, end_marker, replacement):
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"Could not find start marker: {start_marker}")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"Could not find end marker: {end_marker}")
    return text[:start] + replacement + text[end:]

# Add final CSS overrides for SVG marker and selected-only callsign label.
if "/* Directional SVG marker fixes */" not in s:
    css = r'''
/* Directional SVG marker fixes */
.plane-marker-wrap {
  position: relative;
  width: 34px;
  height: 34px;
}
.plane-marker {
  width: 30px;
  height: 30px;
  display: block;
  transform-origin: 50% 50%;
  filter: drop-shadow(0 0 3px #000) drop-shadow(0 0 5px #000);
}
.plane-marker path {
  fill: #00d7ff;
  stroke: #06151a;
  stroke-width: 1.2;
}
.plane-label {
  position: absolute;
  left: 27px;
  top: 7px;
  margin-left: 0;
}
'''
    s = s.replace("</style>", css + "\n</style>", 1)

# Keep latest aircraft records so marker labels can be redrawn immediately after selection.
if "aircraftById: new Map()" not in s:
    s = s.replace(
        "  markers: new Map(),\n",
        "  markers: new Map(),\n  aircraftById: new Map(),\n",
        1
    )

new_marker_functions = r'''function markerHtml(a) {
  /*
   * This SVG is drawn pointing straight up. On a north-up map:
   * track 0 = north, 90 = east, 180 = south, 270 = west.
   */
  const trackValue = Number(a.Trak);
  const track = Number.isFinite(trackValue) ? trackValue : 0;
  const selected = String(a.Id) === state.selectedId;
  const label = selected
    ? `<span class="plane-label">${aircraftName(a)}</span>`
    : '';

  return `
    <div class="plane-marker-wrap">
      <svg class="plane-marker" style="transform: rotate(${track}deg)" viewBox="0 0 32 32" aria-hidden="true">
        <path d="M16 2 L19.4 12.2 L29 17 L29 20 L18.7 17.9 L18 28 L16 31 L14 28 L13.3 17.9 L3 20 L3 17 L12.6 12.2 Z"></path>
      </svg>
      ${label}
    </div>
  `;
}

function aircraftIcon(a) {
  return L.divIcon({
    className: '',
    html: markerHtml(a),
    iconSize: [110, 34],
    iconAnchor: [16, 16]
  });
}

function refreshMarkerIcons() {
  for (const [id, marker] of state.markers.entries()) {
    const aircraft = state.aircraftById.get(id);
    if (aircraft) {
      marker.setIcon(aircraftIcon(aircraft));
    }
  }
}

function selectAircraft(id) {
  state.selectedId = id;
  refreshMarkerIcons();

  if (state.markers.has(id)) {
    state.markers.get(id).openPopup();
  }
}

'''

s = replace_between(
    s,
    "function markerHtml(a) {",
    "function popupHtml(a) {",
    new_marker_functions
)

new_init_map = r'''function initMap() {
  state.map = L.map('map').setView(
    [state.config.InitialLatitude, state.config.InitialLongitude],
    state.config.InitialZoom
  );

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(state.map);

  /*
   * Clicking open map space clears the selection and hides the callsign tag.
   */
  state.map.on('click', () => {
    state.selectedId = null;
    refreshMarkerIcons();
  });
}

'''

s = replace_between(
    s,
    "function initMap() {",
    "function updateTrail(a) {",
    new_init_map
)

new_update_trail = r'''function updateTrail(a) {
  const id = String(a.Id);
  const point = [a.Lat, a.Long];
  const points = state.trailPoints.get(id) || [];
  const previous = points.length ? points[points.length - 1] : null;

  /*
   * Only record an actual position change. A visible line requires two
   * different decoded ADS-B positions from the same aircraft.
   */
  if (!previous || previous[0] !== point[0] || previous[1] !== point[1]) {
    points.push(point);

    while (points.length > state.trailMaxPoints) {
      points.shift();
    }

    state.trailPoints.set(id, points);
  }

  if (points.length < 2) {
    return;
  }

  if (!state.trailLayers.has(id)) {
    const layer = L.polyline(points, {
      color: '#00d7ff',
      weight: 3,
      opacity: 0.90,
      dashArray: '7 5',
      lineCap: 'round',
      lineJoin: 'round',
      interactive: false
    });

    state.trailLayers.set(id, layer);

    if (state.showTrails) {
      layer.addTo(state.map);
    }
  } else {
    state.trailLayers.get(id).setLatLngs(points);
  }
}

'''

s = replace_between(
    s,
    "function updateTrail(a) {",
    "function removeTrail(id) {",
    new_update_trail
)

new_update_markers = r'''function updateMarkers(acList) {
  const seen = new Set();

  state.aircraftById = new Map(
    acList.map(a => [String(a.Id), a])
  );

  for (const a of acList) {
    if (!hasPosition(a)) continue;

    const id = String(a.Id);
    seen.add(id);

    /*
     * Center once on the first aircraft with decoded coordinates.
     */
    if (!state.initialPlaneCentered) {
      state.map.setView([a.Lat, a.Long], state.map.getZoom());
      state.initialPlaneCentered = true;
    }

    if (!state.markers.has(id)) {
      const marker = L.marker([a.Lat, a.Long], {
        icon: aircraftIcon(a),
        bubblingMouseEvents: false
      });

      marker.addTo(state.map);

      marker.on('click', () => {
        selectAircraft(id);
      });

      state.markers.set(id, marker);
    }

    const marker = state.markers.get(id);
    marker.setLatLng([a.Lat, a.Long]);
    marker.setIcon(aircraftIcon(a));
    marker.bindPopup(popupHtml(a));

    updateTrail(a);
  }

  for (const [id, marker] of state.markers.entries()) {
    if (!seen.has(id)) {
      state.map.removeLayer(marker);
      state.markers.delete(id);

      /*
       * Intentionally retain the trail after an aircraft falls out of the
       * active feed. This makes completed tracks visible until the user
       * presses Clear trails or refreshes the page.
       */
    }
  }
}

'''

s = replace_between(
    s,
    "function updateMarkers(acList) {",
    "function updateTable(acList) {",
    new_update_markers
)

new_update_table = r'''function updateTable(acList) {
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

    tr.innerHTML = `
      <td><span class="callsign">${name}</span><br><span class="muted">${fmt(a.Icao)}</span></td>
      <td>${fmt(a.Alt)}</td>
      <td>${fmt(a.Spd)}</td>
      <td>${fmt(a.Trak)}</td>
      <td>${fmt(a.CMsgs)}</td>
      <td>${fmt(a.TSecs, 's')}</td>
    `;

    tr.onclick = () => {
      state.selectedId = id;
      refreshMarkerIcons();

      if (hasPosition(a) && state.markers.has(id)) {
        state.map.setView([a.Lat, a.Long], Math.max(state.map.getZoom(), 9));
        state.markers.get(id).openPopup();
      }
    };

    rows.appendChild(tr);
  }
}

'''

s = replace_between(
    s,
    "function updateTable(acList) {",
    "async function refresh() {",
    new_update_table
)

HTML.write_text(s, encoding="utf-8")
print("Fixed aircraft marker direction, selected-only tags, and retained visible trails.")
