#!/usr/bin/env python3
from pathlib import Path

html_path = Path("web/vrs_desktop.html")
s = html_path.read_text(encoding="utf-8")

state_anchor = """  selectedId: null,
  config: {
"""

state_replacement = """  selectedId: null,
  initialPlaneCentered: false,
  config: {
"""

center_anchor = """    const id = String(a.Id);
    seen.add(id);

    const icon = L.divIcon({
"""

center_replacement = """    const id = String(a.Id);
    seen.add(id);

    /*
     * Center once on the first aircraft with decoded coordinates.
     * Aircraft detected without a position remain visible in the table,
     * but do not prevent centering once a valid position is available.
     */
    if (!state.initialPlaneCentered) {
      state.map.setView([a.Lat, a.Long], state.map.getZoom());
      state.initialPlaneCentered = true;
    }

    const icon = L.divIcon({
"""

if "initialPlaneCentered: false" not in s:
    if state_anchor not in s:
        raise SystemExit("Could not find the state object insertion point.")
    s = s.replace(state_anchor, state_replacement, 1)

if "Center once on the first aircraft with decoded coordinates." not in s:
    if center_anchor not in s:
        raise SystemExit("Could not find the marker update insertion point.")
    s = s.replace(center_anchor, center_replacement, 1)

html_path.write_text(s, encoding="utf-8")
print("Added one-time centering on first positioned aircraft.")
