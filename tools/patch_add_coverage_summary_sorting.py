#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if 'id="coverage-summary"' in s:
    print("Coverage summary and sorting are already installed.")
    raise SystemExit(0)

def replace_once(old, new, name):
    global s
    if old not in s:
        raise SystemExit(f"Could not find {name}.")
    s = s.replace(old, new, 1)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

css = r'''
#coverage-summary {
  margin-top: 10px;
  padding: 9px 10px;
  border: 1px solid #31343a;
  border-radius: 5px;
  background: #1b1d21;
  font-size: 12px;
}
#coverage-summary .coverage-title {
  margin-bottom: 7px;
  color: #ddd;
  font-size: 13px;
  font-weight: bold;
}
#coverage-summary .coverage-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 5px 10px;
  margin-bottom: 8px;
}
#coverage-summary .coverage-label {
  color: #9098a0;
}
#coverage-summary .coverage-value {
  color: #e7eaed;
  text-align: right;
  font-weight: bold;
}
#coverage-summary .coverage-sort {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
#coverage-summary select {
  min-width: 150px;
  padding: 3px 5px;
  color: #eee;
  background: #24272c;
  border: 1px solid #474b52;
  border-radius: 4px;
}
'''

replace_once(
    "</style>",
    css + "\n</style>",
    "style close tag"
)

# ---------------------------------------------------------------------------
# Coverage panel above the collapsible Options block.
# ---------------------------------------------------------------------------

panel = r'''      <div id="coverage-summary">
        <div class="coverage-title">Coverage Summary</div>
        <div class="coverage-grid">
          <span class="coverage-label">Positioned aircraft</span>
          <span class="coverage-value" id="coverage-positioned">—</span>

          <span class="coverage-label">Current farthest</span>
          <span class="coverage-value" id="coverage-current">Set receiver</span>

          <span class="coverage-label">Session maximum</span>
          <span class="coverage-value" id="coverage-maximum">Set receiver</span>
        </div>
        <div class="coverage-sort">
          <label for="aircraft-sort">Sort aircraft</label>
          <select id="aircraft-sort">
            <option value="range-desc" selected>Range: farthest first</option>
            <option value="range-asc">Range: nearest first</option>
            <option value="callsign">Callsign</option>
            <option value="altitude-desc">Altitude: highest first</option>
          </select>
        </div>
      </div>
'''

options_anchor = '      <details id="options-panel">'

replace_once(
    options_anchor,
    panel + options_anchor,
    "collapsed Options panel insertion point"
)

# ---------------------------------------------------------------------------
# Extend application state.
# ---------------------------------------------------------------------------

state_anchor = """  showRangeRings: true,
  ringMaxNm: 150,
"""

state_replacement = """  showRangeRings: true,
  ringMaxNm: 150,
  aircraftSortMode: 'range-desc',
  sessionMaximumRange: null,
"""

replace_once(
    state_anchor,
    state_replacement,
    "receiver/map state"
)

# ---------------------------------------------------------------------------
# Add coverage helper functions ahead of updateTable().
# ---------------------------------------------------------------------------

functions = r'''const AIRCRAFT_SORT_STORAGE_KEY = 'plutoAdsBAircraftSortModeV1';

function loadAircraftSortMode() {
  try {
    const saved = window.localStorage.getItem(AIRCRAFT_SORT_STORAGE_KEY);
    const allowed = ['range-desc', 'range-asc', 'callsign', 'altitude-desc'];

    if (allowed.includes(saved)) {
      state.aircraftSortMode = saved;
    }
  } catch (e) {
    console.log('Unable to load aircraft sort mode:', e);
  }

  document.getElementById('aircraft-sort').value = state.aircraftSortMode;
}

function saveAircraftSortMode() {
  try {
    window.localStorage.setItem(AIRCRAFT_SORT_STORAGE_KEY, state.aircraftSortMode);
  } catch (e) {
    console.log('Unable to save aircraft sort mode:', e);
  }
}

function aircraftRangeRecord(a) {
  const range = distanceAndBearing(a);

  if (!range) {
    return null;
  }

  return {
    aircraft: a,
    distanceNm: range.distanceNm,
    bearing: range.bearing
  };
}

function rangeAircraftName(record) {
  return aircraftName(record.aircraft);
}

function updateCoverageSummary(acList) {
  const positionedCount = acList.filter(hasPosition).length;
  const positionedField = document.getElementById('coverage-positioned');
  const currentField = document.getElementById('coverage-current');
  const maximumField = document.getElementById('coverage-maximum');

  positionedField.textContent = String(positionedCount);

  if (!state.receiverLocation) {
    currentField.textContent = 'Set receiver';
    maximumField.textContent = 'Set receiver';
    return;
  }

  const ranged = acList
    .map(aircraftRangeRecord)
    .filter(record => record !== null)
    .sort((a, b) => b.distanceNm - a.distanceNm);

  if (!ranged.length) {
    currentField.textContent = 'No positions';
    maximumField.textContent = state.sessionMaximumRange
      ? `${state.sessionMaximumRange.distanceNm.toFixed(1)} nm · ${state.sessionMaximumRange.name}`
      : 'No positions';
    return;
  }

  const farthest = ranged[0];

  currentField.textContent =
    `${farthest.distanceNm.toFixed(1)} nm · ${rangeAircraftName(farthest)}`;

  if (!state.sessionMaximumRange ||
      farthest.distanceNm > state.sessionMaximumRange.distanceNm) {
    state.sessionMaximumRange = {
      distanceNm: farthest.distanceNm,
      name: rangeAircraftName(farthest),
      time: new Date()
    };
  }

  maximumField.textContent =
    `${state.sessionMaximumRange.distanceNm.toFixed(1)} nm · ${state.sessionMaximumRange.name}`;
}

function compareAircraftForList(a, b) {
  if (state.aircraftSortMode === 'range-desc' ||
      state.aircraftSortMode === 'range-asc') {
    const ar = distanceAndBearing(a);
    const br = distanceAndBearing(b);

    if (ar && br) {
      return state.aircraftSortMode === 'range-desc'
        ? br.distanceNm - ar.distanceNm
        : ar.distanceNm - br.distanceNm;
    }

    if (ar) return -1;
    if (br) return 1;
  }

  if (state.aircraftSortMode === 'altitude-desc') {
    const altitudeDifference = Number(b.Alt || -1) - Number(a.Alt || -1);

    if (altitudeDifference !== 0) {
      return altitudeDifference;
    }
  }

  return aircraftName(a).localeCompare(aircraftName(b));
}

'''

update_table_anchor = "function updateTable(acList) {"

replace_once(
    update_table_anchor,
    functions + update_table_anchor,
    "updateTable function anchor"
)

# ---------------------------------------------------------------------------
# Replace alphabetical-only sorting with selected sorting mode.
# ---------------------------------------------------------------------------

old_sort = """  const sorted = [...acList].sort((a, b) => {
    const ac = aircraftName(a);
    const bc = aircraftName(b);
    return ac.localeCompare(bc);
  });
"""

new_sort = """  const sorted = [...acList].sort(compareAircraftForList);
"""

replace_once(
    old_sort,
    new_sort,
    "alphabetical aircraft sorting block"
)

# ---------------------------------------------------------------------------
# Update coverage on every aircraft feed refresh.
# ---------------------------------------------------------------------------

refresh_anchor = """    const positioned = acList.filter(hasPosition).length;

    status.textContent =
"""

refresh_replacement = """    const positioned = acList.filter(hasPosition).length;

    updateCoverageSummary(acList);

    status.textContent =
"""

replace_once(
    refresh_anchor,
    refresh_replacement,
    "refresh positioned-aircraft block"
)

# ---------------------------------------------------------------------------
# Reset session maximum if receiver coordinates change or are cleared.
# ---------------------------------------------------------------------------

finish_anchor = """  state.receiverLocation = {
    lat: latlng.lat,
    lon: latlng.lng
  };

  state.settingReceiverLocation = false;
"""

finish_replacement = """  state.receiverLocation = {
    lat: latlng.lat,
    lon: latlng.lng
  };

  state.sessionMaximumRange = null;
  state.settingReceiverLocation = false;
"""

replace_once(
    finish_anchor,
    finish_replacement,
    "receiver selection completion block"
)

clear_anchor = """  state.settingReceiverLocation = false;
  state.receiverLocation = null;

  const button = document.getElementById('set-receiver');
"""

clear_replacement = """  state.settingReceiverLocation = false;
  state.receiverLocation = null;
  state.sessionMaximumRange = null;

  const button = document.getElementById('set-receiver');
"""

replace_once(
    clear_anchor,
    clear_replacement,
    "receiver clear block"
)

# ---------------------------------------------------------------------------
# Initialize sort selection and change handling.
# ---------------------------------------------------------------------------

main_anchor = """  loadReceiverLocation();
  loadDisplaySettings();
  drawReceiverLocation();

"""

main_replacement = """  loadReceiverLocation();
  loadDisplaySettings();
  loadAircraftSortMode();
  drawReceiverLocation();

  document.getElementById('aircraft-sort').addEventListener('change', event => {
    state.aircraftSortMode = event.target.value;
    saveAircraftSortMode();
  });

"""

replace_once(
    main_anchor,
    main_replacement,
    "main receiver/display initialization block"
)

HTML.write_text(s, encoding="utf-8")

print("Added Coverage Summary and selectable aircraft sorting.")
print("Default sorting: range farthest first when receiver location is set.")
