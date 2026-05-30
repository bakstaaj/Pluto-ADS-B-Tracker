#!/usr/bin/env python3
import re
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

marker = "aircraft-popups-disabled-v1"

if marker in s:
    print("Aircraft popup removal patch is already present.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Make the selected callsign map label clearly dark and unobtrusive.
# ---------------------------------------------------------------------------

css = r'''
/* aircraft-popups-disabled-v1 */
.plane-label {
  background: rgba(20, 23, 27, 0.94);
  border: 1px solid #3b4249;
  color: #f0f2f4;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: bold;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style> for aircraft label styling.")

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Aircraft markers should no longer bind the white Leaflet popup.
# Receiver-site popup is intentionally left untouched.
# ---------------------------------------------------------------------------

s, bind_count = re.subn(
    r'(?m)^(\s*)marker\.bindPopup\s*\(\s*popupHtml\s*\(\s*a\s*\)\s*\)\s*;\s*$',
    r'\1/* Aircraft details appear in the right-side selected panel only. */\n\1marker.unbindPopup();',
    s
)

if bind_count == 0 and "marker.unbindPopup();" not in s:
    raise SystemExit("Could not find aircraft marker popup binding to disable.")

# ---------------------------------------------------------------------------
# Remove popup-opening actions used by:
# - aircraft marker selection
# - aircraft table-row selection
# - Center Aircraft button in the detail panel
# ---------------------------------------------------------------------------

open_patterns = [
    r'(?m)^\s*marker\.openPopup\s*\(\s*\)\s*;\s*$\n?',
    r'(?m)^\s*state\.markers\.get\s*\(\s*id\s*\)\.openPopup\s*\(\s*\)\s*;\s*$\n?'
]

removed_open_calls = 0
for pattern in open_patterns:
    s, count = re.subn(pattern, "", s)
    removed_open_calls += count

# ---------------------------------------------------------------------------
# When an aircraft is selected, close any existing aircraft popup left open
# in the current browser session, then redraw marker labels.
# ---------------------------------------------------------------------------

old_select = """function selectAircraft(id) {
  state.selectedId = id;
  refreshMarkerIcons();
"""

new_select = """function selectAircraft(id) {
  state.selectedId = id;

  if (state.map) {
    state.map.closePopup();
  }

  refreshMarkerIcons();
"""

if old_select in s:
    s = s.replace(old_select, new_select, 1)
elif "function selectAircraft(id)" not in s:
    raise SystemExit("Could not find selectAircraft() function.")

HTML.write_text(s, encoding="utf-8")

print("Disabled aircraft popup bubbles.")
print("Kept selected-aircraft callsign tag on the map.")
print("Kept aircraft details in the right-side panel.")
print(f"Disabled {bind_count} aircraft popup binding(s).")
print(f"Removed {removed_open_calls} aircraft popup open action(s).")
