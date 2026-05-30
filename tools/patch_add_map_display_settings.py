#!/usr/bin/env python3
import re
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if 'id="display-settings"' in s:
    print("Map display settings are already present.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# CSS for settings panel
# ---------------------------------------------------------------------------

css = r'''
#display-settings {
  margin-top: 10px;
  padding: 9px 10px;
  border: 1px solid #31343a;
  border-radius: 5px;
  background: #1b1d21;
  font-size: 12px;
}
#display-settings .settings-title {
  margin-bottom: 7px;
  color: #ddd;
  font-size: 13px;
  font-weight: bold;
}
#display-settings .settings-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 7px 8px;
}
#display-settings label {
  color: #c5c9cf;
}
#display-settings select {
  min-width: 92px;
  padding: 3px 5px;
  color: #eee;
  background: #24272c;
  border: 1px solid #474b52;
  border-radius: 4px;
}
#display-settings .checkbox-row {
  display: flex;
  align-items: center;
  gap: 5px;
  grid-column: 1 / 3;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style> for settings CSS.")

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Sidebar HTML panel
# ---------------------------------------------------------------------------

receiver_status = '<span id="receiver-status">Receiver location not set</span>'

settings_html = r'''
      <div id="display-settings">
        <div class="settings-title">Map Display</div>
        <div class="settings-grid">
          <label class="checkbox-row">
            <input type="checkbox" id="show-rings" checked>
            Show range rings
          </label>

          <label for="ring-max">Ring extent</label>
          <select id="ring-max">
            <option value="25">25 nm</option>
            <option value="50">50 nm</option>
            <option value="75">75 nm</option>
            <option value="100">100 nm</option>
            <option value="150" selected>150 nm</option>
            <option value="200">200 nm</option>
          </select>

          <label for="trail-points">Trail history</label>
          <select id="trail-points">
            <option value="10">10 points</option>
            <option value="25">25 points</option>
            <option value="50">50 points</option>
            <option value="80" selected>80 points</option>
            <option value="150">150 points</option>
            <option value="300">300 points</option>
          </select>
        </div>
      </div>
'''

if receiver_status not in s:
    raise SystemExit("Could not find sidebar receiver-status element.")

s = s.replace(receiver_status, receiver_status + settings_html, 1)

# ---------------------------------------------------------------------------
# Extend state
# ---------------------------------------------------------------------------

state_anchor = """  ringLayers: [],
  settingReceiverLocation: false,
"""

state_replacement = """  ringLayers: [],
  settingReceiverLocation: false,
  showRangeRings: true,
  ringMaxNm: 150,
"""

if state_anchor not in s:
    raise SystemExit("Could not find receiver state block.")

s = s.replace(state_anchor, state_replacement, 1)

# ---------------------------------------------------------------------------
# Replace fixed range ring list with dynamic ring generation
# ---------------------------------------------------------------------------

if "const RANGE_RINGS_NM = Array.from({ length: 30 }, (_, index) => (index + 1) * 5);" in s:
    s = s.replace(
        "const RANGE_RINGS_NM = Array.from({ length: 30 }, (_, index) => (index + 1) * 5);",
        """function rangeRingsNm() {
  if (!state.showRangeRings) {
    return [];
  }

  return Array.from(
    { length: Math.floor(state.ringMaxNm / 5) },
    (_, index) => (index + 1) * 5
  );
}""",
        1
    )
elif "const RANGE_RINGS_NM = [25, 50, 100, 150];" in s:
    s = s.replace(
        "const RANGE_RINGS_NM = [25, 50, 100, 150];",
        """function rangeRingsNm() {
  if (!state.showRangeRings) {
    return [];
  }

  return Array.from(
    { length: Math.floor(state.ringMaxNm / 5) },
    (_, index) => (index + 1) * 5
  );
}""",
        1
    )
elif "function rangeRingsNm()" not in s:
    raise SystemExit("Could not find the range-ring constant.")

s = s.replace(
    "for (const ringNm of RANGE_RINGS_NM) {",
    "for (const ringNm of rangeRingsNm()) {"
)

# ---------------------------------------------------------------------------
# Add browser-persisted settings functions
# ---------------------------------------------------------------------------

settings_functions = r'''const DISPLAY_SETTINGS_STORAGE_KEY = 'plutoAdsBMapDisplaySettingsV1';

function loadDisplaySettings() {
  try {
    const saved = window.localStorage.getItem(DISPLAY_SETTINGS_STORAGE_KEY);

    if (saved) {
      const settings = JSON.parse(saved);

      if (typeof settings.showRangeRings === 'boolean') {
        state.showRangeRings = settings.showRangeRings;
      }

      if ([25, 50, 75, 100, 150, 200].includes(Number(settings.ringMaxNm))) {
        state.ringMaxNm = Number(settings.ringMaxNm);
      }

      if ([10, 25, 50, 80, 150, 300].includes(Number(settings.trailMaxPoints))) {
        state.trailMaxPoints = Number(settings.trailMaxPoints);
      }
    }
  } catch (e) {
    console.log('Unable to load map display settings:', e);
  }

  document.getElementById('show-rings').checked = state.showRangeRings;
  document.getElementById('ring-max').value = String(state.ringMaxNm);
  document.getElementById('trail-points').value = String(state.trailMaxPoints);
}

function saveDisplaySettings() {
  try {
    window.localStorage.setItem(
      DISPLAY_SETTINGS_STORAGE_KEY,
      JSON.stringify({
        showRangeRings: state.showRangeRings,
        ringMaxNm: state.ringMaxNm,
        trailMaxPoints: state.trailMaxPoints
      })
    );
  } catch (e) {
    console.log('Unable to save map display settings:', e);
  }
}

function trimExistingTrails() {
  for (const [id, points] of state.trailPoints.entries()) {
    while (points.length > state.trailMaxPoints) {
      points.shift();
    }

    if (state.trailLayers.has(id)) {
      state.trailLayers.get(id).setLatLngs(points);
    }
  }
}

'''

function_anchor = "function updateReceiverStatus(message = null) {"

if function_anchor not in s:
    raise SystemExit("Could not find updateReceiverStatus function.")

s = s.replace(function_anchor, settings_functions + function_anchor, 1)

# ---------------------------------------------------------------------------
# Replace receiver status function so it reflects current ring settings
# ---------------------------------------------------------------------------

start = s.find("function updateReceiverStatus(message = null) {")
end = s.find("function loadReceiverLocation() {", start)

if start < 0 or end < 0:
    raise SystemExit("Could not locate updateReceiverStatus function bounds.")

new_status_function = r'''function updateReceiverStatus(message = null) {
  const status = document.getElementById('receiver-status');

  if (message) {
    status.textContent = message;
    return;
  }

  if (!state.receiverLocation) {
    status.textContent = 'Receiver location not set';
    return;
  }

  const ringsText = state.showRangeRings
    ? `Rings: every 5 nm to ${state.ringMaxNm} nm`
    : 'Rings hidden';

  status.textContent =
    `Receiver: ${state.receiverLocation.lat.toFixed(5)}, ${state.receiverLocation.lon.toFixed(5)} | ${ringsText}`;
}

'''

s = s[:start] + new_status_function + s[end:]

# ---------------------------------------------------------------------------
# Initialize settings and connect events
# ---------------------------------------------------------------------------

old_init = """  loadReceiverLocation();
  drawReceiverLocation();

  await refresh();
"""

new_init = """  loadReceiverLocation();
  loadDisplaySettings();
  drawReceiverLocation();

  document.getElementById('show-rings').addEventListener('change', event => {
    state.showRangeRings = event.target.checked;
    saveDisplaySettings();
    drawReceiverLocation();
  });

  document.getElementById('ring-max').addEventListener('change', event => {
    state.ringMaxNm = Number(event.target.value);
    saveDisplaySettings();
    drawReceiverLocation();
  });

  document.getElementById('trail-points').addEventListener('change', event => {
    state.trailMaxPoints = Number(event.target.value);
    saveDisplaySettings();
    trimExistingTrails();
  });

  await refresh();
"""

if old_init not in s:
    raise SystemExit("Could not find receiver initialization block in main().")

s = s.replace(old_init, new_init, 1)

HTML.write_text(s, encoding="utf-8")

print("Added Map Display settings panel.")
print("Range rings remain spaced every 5 nm.")
print("Settings persist in browser local storage.")
