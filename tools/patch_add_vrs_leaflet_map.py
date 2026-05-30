#!/usr/bin/env python3
import json
import re
from pathlib import Path

p = Path("dump1090.c")
s = p.read_text()

html = r'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Pluto ADS-B Tracker</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
html, body { height: 100%; margin: 0; font-family: Arial, sans-serif; background: #111; color: #eee; }
#app { display: grid; grid-template-columns: minmax(420px, 1fr) 430px; height: 100%; }
#map { height: 100%; background: #222; }
#side { display: flex; flex-direction: column; min-width: 360px; border-left: 1px solid #333; background: #151515; }
#header { padding: 12px 14px; border-bottom: 1px solid #333; }
#header h1 { font-size: 20px; margin: 0 0 4px 0; }
#status { color: #aaa; font-size: 13px; }
#table-wrap { overflow: auto; flex: 1; }
table { border-collapse: collapse; width: 100%; font-size: 13px; }
th, td { border-bottom: 1px solid #2c2c2c; padding: 6px 8px; text-align: left; white-space: nowrap; }
th { position: sticky; top: 0; z-index: 1; background: #222; color: #ddd; }
tr:hover { background: #242424; cursor: pointer; }
.callsign { font-weight: bold; color: #fff; }
.muted { color: #888; }
.plane-marker { color: #00d7ff; font-size: 23px; text-shadow: 0 0 4px #000, 0 0 8px #000; transform-origin: center center; }
.plane-label { display: inline-block; margin-left: 4px; padding: 1px 4px; border-radius: 3px; background: rgba(0,0,0,0.72); color: #fff; font-size: 11px; white-space: nowrap; }
.leaflet-popup-content { margin: 9px 11px; }
.popup-title { font-weight: bold; font-size: 15px; margin-bottom: 4px; }
@media (max-width: 900px) {
  #app { grid-template-columns: 1fr; grid-template-rows: 60% 40%; }
  #side { min-width: 0; border-left: 0; border-top: 1px solid #333; }
}
</style>
</head>
<body>
<div id="app">
  <div id="map"></div>
  <div id="side">
    <div id="header">
      <h1>Pluto ADS-B Tracker</h1>
      <div id="status">Loading aircraft feed...</div>
    </div>
    <div id="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Aircraft</th>
            <th>Alt</th>
            <th>Spd</th>
            <th>Trk</th>
            <th>Msgs</th>
            <th>Age</th>
          </tr>
        </thead>
        <tbody id="rows"></tbody>
      </table>
    </div>
  </div>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const state = {
  map: null,
  markers: new Map(),
  selectedId: null,
  config: {
    InitialLatitude: 38.75,
    InitialLongitude: -105.18,
    InitialZoom: 8
  }
};

function fmt(value, suffix = '') {
  if (value === undefined || value === null || value === '') return '<span class="muted">—</span>';
  return String(value) + suffix;
}

function aircraftName(a) {
  return a.Call || a.Icao || String(a.Id);
}

function hasPosition(a) {
  return typeof a.Lat === 'number' && typeof a.Long === 'number';
}

function markerHtml(a) {
  const track = Number(a.Trak || 0);
  const label = aircraftName(a);
  return `<div style="transform: rotate(${track}deg)" class="plane-marker">✈</div><span class="plane-label">${label}</span>`;
}

function popupHtml(a) {
  return `
    <div class="popup-title">${aircraftName(a)}</div>
    <div>ICAO: ${fmt(a.Icao)}</div>
    <div>Altitude: ${fmt(a.Alt, ' ft')}</div>
    <div>Speed: ${fmt(a.Spd, ' kt')}</div>
    <div>Track: ${fmt(a.Trak, '°')}</div>
    <div>Messages: ${fmt(a.CMsgs)}</div>
    <div>Age: ${fmt(a.TSecs, 's')}</div>
  `;
}

async function loadConfig() {
  try {
    const response = await fetch('/VirtualRadar/ServerConfig.json?_=' + Date.now());
    const config = await response.json();
    state.config = Object.assign(state.config, config || {});
  } catch (e) {
    console.log('Using default map config:', e);
  }
}

function initMap() {
  state.map = L.map('map').setView(
    [state.config.InitialLatitude, state.config.InitialLongitude],
    state.config.InitialZoom
  );

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors'
  }).addTo(state.map);
}

function updateMarkers(acList) {
  const seen = new Set();

  for (const a of acList) {
    if (!hasPosition(a)) continue;

    const id = String(a.Id);
    seen.add(id);

    const icon = L.divIcon({
      className: '',
      html: markerHtml(a),
      iconSize: [90, 28],
      iconAnchor: [12, 14]
    });

    if (!state.markers.has(id)) {
      const marker = L.marker([a.Lat, a.Long], { icon });
      marker.addTo(state.map);
      marker.on('click', () => {
        state.selectedId = id;
        marker.openPopup();
      });
      state.markers.set(id, marker);
    }

    const marker = state.markers.get(id);
    marker.setLatLng([a.Lat, a.Long]);
    marker.setIcon(icon);
    marker.bindPopup(popupHtml(a));
  }

  for (const [id, marker] of state.markers.entries()) {
    if (!seen.has(id)) {
      state.map.removeLayer(marker);
      state.markers.delete(id);
    }
  }
}

function updateTable(acList) {
  const rows = document.getElementById('rows');
  rows.innerHTML = '';

  const sorted = [...acList].sort((a, b) => aircraftName(a).localeCompare(aircraftName(b)));

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
      if (hasPosition(a) && state.markers.has(id)) {
        state.selectedId = id;
        state.map.setView([a.Lat, a.Long], Math.max(state.map.getZoom(), 9));
        state.markers.get(id).openPopup();
      }
    };

    rows.appendChild(tr);
  }
}

async function refresh() {
  const status = document.getElementById('status');

  try {
    const response = await fetch('/VirtualRadar/AircraftList.json?_=' + Date.now());
    const data = await response.json();
    const acList = data.acList || [];
    const positioned = acList.filter(hasPosition).length;

    status.textContent =
      `Aircraft: ${data.totalAc || acList.length} | Positioned: ${positioned} | Server: ${new Date(data.stm).toLocaleString()}`;

    updateMarkers(acList);
    updateTable(acList);
  } catch (e) {
    status.textContent = 'Error loading aircraft feed: ' + e;
  }
}

async function main() {
  await loadConfig();
  initMap();
  await refresh();
  setInterval(refresh, 1000);
}

main();
</script>
</body>
</html>
'''

def c_literal(text):
    return "\n        ".join(json.dumps(line + "\n") for line in text.splitlines())

new_func = f'''char *vrsDesktopHtml(int *len) {{
    const char *html =
        {c_literal(html)};

    char *out = strdup(html);
    *len = strlen(out);
    return out;
}}

'''

def find_function_bounds(source, func_name):
    sig = re.search(r'char\s*\*\s*' + re.escape(func_name) + r'\s*\(\s*int\s*\*\s*len\s*\)', source)
    if not sig:
        return None

    brace_start = source.find('{', sig.end())
    if brace_start < 0:
        return None

    i = brace_start
    depth = 0
    in_str = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escape = False

    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ''

        if in_line_comment:
            if c == '\n':
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if c == '*' and n == '/':
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_str:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                in_str = False
            i += 1
            continue

        if in_char:
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == "'":
                in_char = False
            i += 1
            continue

        if c == '/' and n == '/':
            in_line_comment = True
            i += 2
            continue

        if c == '/' and n == '*':
            in_block_comment = True
            i += 2
            continue

        if c == '"':
            in_str = True
            i += 1
            continue

        if c == "'":
            in_char = True
            i += 1
            continue

        if c == '{':
            depth += 1

        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(source) and source[end] in ' \t\r\n':
                    end += 1
                return sig.start(), end

        i += 1

    return None

bounds = find_function_bounds(s, "vrsDesktopHtml")

if bounds:
    start, end = bounds
    s2 = s[:start] + new_func + s[end:]
    print("Replaced existing vrsDesktopHtml().")
else:
    marker = '#define MODES_CONTENT_TYPE_HTML "text/html;charset=utf-8"'
    if marker not in s:
        print("Could not find vrsDesktopHtml() or MODES_CONTENT_TYPE_HTML insertion point.")
        print()
        print("Diagnostics:")
        for term in ["vrsDesktopHtml", "/VirtualRadar/", "AircraftList.json", "MODES_CONTENT_TYPE_HTML"]:
            print(f"  {term}: {'FOUND' if term in s else 'NOT FOUND'}")
        raise SystemExit(1)

    s2 = s.replace(marker, new_func + "\n" + marker, 1)
    print("vrsDesktopHtml() was missing; inserted new function before content-type defines.")

p.write_text(s2)
print("Updated /VirtualRadar/ desktop page to Leaflet map.")
