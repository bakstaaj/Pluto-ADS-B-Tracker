#!/usr/bin/env python3
from pathlib import Path

html_path = Path("web/vrs_desktop.html")
s = html_path.read_text(encoding="utf-8")

if "trailPoints: new Map()" in s:
    print("Live trail patch already applied.")
    raise SystemExit(0)

# Add control styling.
css_anchor = """#status { color: #aaa; font-size: 13px; }
"""

css_replacement = """#status { color: #aaa; font-size: 13px; margin-bottom: 9px; }
#controls {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #ddd;
}
#controls label {
  display: flex;
  align-items: center;
  gap: 5px;
}
#controls button {
  border: 1px solid #444;
  border-radius: 4px;
  background: #242424;
  color: #eee;
  padding: 4px 9px;
  cursor: pointer;
}
#controls button:hover {
  background: #333;
}
"""

if css_anchor not in s:
    raise SystemExit("Could not find CSS status insertion point.")

s = s.replace(css_anchor, css_replacement, 1)

# Add controls beneath status.
header_anchor = """      <div id="status">Loading aircraft feed...</div>
"""

header_replacement = """      <div id="status">Loading aircraft feed...</div>
      <div id="controls">
        <label><input type="checkbox" id="show-trails" checked> Show trails</label>
        <button type="button" id="clear-trails">Clear trails</button>
      </div>
"""

if header_anchor not in s:
    raise SystemExit("Could not find header control insertion point.")

s = s.replace(header_anchor, header_replacement, 1)

# Extend application state.
state_anchor = """  initialPlaneCentered: false,
  config: {
"""

state_replacement = """  initialPlaneCentered: false,
  trailPoints: new Map(),
  trailLayers: new Map(),
  showTrails: true,
  trailMaxPoints: 80,
  config: {
"""

if state_anchor not in s:
    raise SystemExit("Could not find application state insertion point.")

s = s.replace(state_anchor, state_replacement, 1)

# Add trail functions before marker updating.
marker_function_anchor = """function updateMarkers(acList) {
"""

trail_functions = """function updateTrail(a) {
  const id = String(a.Id);
  const point = [a.Lat, a.Long];
  const points = state.trailPoints.get(id) || [];
  const previous = points.length ? points[points.length - 1] : null;

  if (!previous || previous[0] !== point[0] || previous[1] !== point[1]) {
    points.push(point);

    while (points.length > state.trailMaxPoints) {
      points.shift();
    }

    state.trailPoints.set(id, points);
  }

  if (points.length < 2) return;

  if (!state.trailLayers.has(id)) {
    const layer = L.polyline(points, {
      weight: 2,
      opacity: 0.70,
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

function removeTrail(id) {
  if (state.trailLayers.has(id)) {
    state.map.removeLayer(state.trailLayers.get(id));
    state.trailLayers.delete(id);
  }

  state.trailPoints.delete(id);
}

function setTrailsVisible(visible) {
  state.showTrails = visible;

  for (const layer of state.trailLayers.values()) {
    if (visible) {
      layer.addTo(state.map);
    } else {
      state.map.removeLayer(layer);
    }
  }
}

function clearTrails() {
  for (const layer of state.trailLayers.values()) {
    state.map.removeLayer(layer);
  }

  state.trailLayers.clear();
  state.trailPoints.clear();
}

function updateMarkers(acList) {
"""

if marker_function_anchor not in s:
    raise SystemExit("Could not find updateMarkers() insertion point.")

s = s.replace(marker_function_anchor, trail_functions, 1)

# Record positions after updating each aircraft marker.
popup_anchor = """    marker.setIcon(icon);
    marker.bindPopup(popupHtml(a));
"""

popup_replacement = """    marker.setIcon(icon);
    marker.bindPopup(popupHtml(a));
    updateTrail(a);
"""

if popup_anchor not in s:
    raise SystemExit("Could not find marker popup update point.")

s = s.replace(popup_anchor, popup_replacement, 1)

# Remove trails when the aircraft drops out of the active aircraft list.
cleanup_anchor = """      state.map.removeLayer(marker);
      state.markers.delete(id);
"""

cleanup_replacement = """      state.map.removeLayer(marker);
      state.markers.delete(id);
      removeTrail(id);
"""

if cleanup_anchor not in s:
    raise SystemExit("Could not find marker cleanup point.")

s = s.replace(cleanup_anchor, cleanup_replacement, 1)

# Activate controls when the page starts.
main_anchor = """async function main() {
  await loadConfig();
  initMap();
  await refresh();
"""

main_replacement = """async function main() {
  await loadConfig();
  initMap();

  document.getElementById('show-trails').addEventListener('change', event => {
    setTrailsVisible(event.target.checked);
  });

  document.getElementById('clear-trails').addEventListener('click', () => {
    clearTrails();
  });

  await refresh();
"""

if main_anchor not in s:
    raise SystemExit("Could not find main() initialization point.")

s = s.replace(main_anchor, main_replacement, 1)

html_path.write_text(s, encoding="utf-8")
print("Added live aircraft trails and trail controls.")
