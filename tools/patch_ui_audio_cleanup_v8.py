#!/usr/bin/env python3
import re
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

MARKER = "ui-audio-cleanup-v8"

if MARKER in s:
    print("UI/audio cleanup v8 is already installed.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# 1. Reduce buffered audio startup latency now that source-cursor bug is fixed.
# ---------------------------------------------------------------------------

audio_replacements = {
    "audioChunkSamples: 32000": "audioChunkSamples: 16000",
    "audioPrebufferSamples: 64000": "audioPrebufferSamples: 32000",
    "audioStartupLeadSeconds: 2.25": "audioStartupLeadSeconds: 0.50",
    "audioQueueTargetSeconds: 6.0": "audioQueueTargetSeconds: 3.0",
}

for old, new in audio_replacements.items():
    if old in s:
        s = s.replace(old, new, 1)
    elif new not in s:
        raise SystemExit(f"Could not find audio setting: {old}")

# Remove the visible buffering percentage.
buffer_pattern = re.compile(
    r"""bufferMessage\(\s*
        'Buffering\ audio\.\.\.\ '\s*\+
        .*?
        '%'\s*
        \);\s*
        return;
    """,
    re.DOTALL | re.VERBOSE
)

s, buffer_count = buffer_pattern.subn(
    "bufferMessage('Preparing live audio...');\n          return;",
    s,
    count=1
)

if buffer_count == 0 and "Preparing live audio..." not in s:
    raise SystemExit("Could not find the buffering-percentage message block.")

# Update comments that described the longer former buffer.
s = s.replace(
    "Start with a four-second reserve.",
    "Start with a two-second reserve."
)
s = s.replace(
    "Configured four-second browser audio reserve.",
    "Configured two-second browser audio reserve."
)

# ---------------------------------------------------------------------------
# 2. Remove prior selected-aircraft controller script, if present.
#    A new robust controller is installed below.
# ---------------------------------------------------------------------------

old_selected_script = re.compile(
    r'\s*<script\b[^>]*\bid=["\']selected-aircraft-panel-v1["\'][^>]*>'
    r'.*?</script>\s*',
    re.IGNORECASE | re.DOTALL
)

s = old_selected_script.sub("\n", s)

# ---------------------------------------------------------------------------
# 3. Make map aircraft respond to single click and double click.
# ---------------------------------------------------------------------------

if "marker.on('dblclick'" not in s:
    original_marker_click = re.compile(
        r"""marker\.on\('click',\s*\(\)\s*=>\s*\{\s*
            selectAircraft\(id\);\s*
            \}\);""",
        re.DOTALL | re.VERBOSE
    )

    replacement_marker_click = """marker.on('click', event => {
        if (event && event.originalEvent) {
          L.DomEvent.stopPropagation(event.originalEvent);
        }

        selectAircraft(id);
      });

      marker.on('dblclick', event => {
        if (event && event.originalEvent) {
          L.DomEvent.stopPropagation(event.originalEvent);
          L.DomEvent.preventDefault(event.originalEvent);
        }

        selectAircraft(id);
      });"""

    s, click_count = original_marker_click.subn(
        replacement_marker_click,
        s,
        count=1
    )

    if click_count != 1:
        raise SystemExit(
            "Could not find the aircraft marker click handler. "
            "Run: grep -n -A8 -B5 \"marker.on('click'\" web/vrs_desktop.html"
        )

# Ensure selection immediately refreshes the right-side detail panel.
select_anchor = """  refreshMarkerIcons();

"""

select_replacement = """  refreshMarkerIcons();

  if (typeof window.renderSelectedAircraftDetails === 'function') {
    window.renderSelectedAircraftDetails();
  }

"""

select_start = s.find("function selectAircraft(id) {")
select_end = s.find("}", select_start)

if select_start < 0:
    raise SystemExit("Could not find selectAircraft().")

select_area = s[select_start:select_start + 400]

if "renderSelectedAircraftDetails" not in select_area:
    if select_anchor not in select_area:
        raise SystemExit("Could not find refreshMarkerIcons() inside selectAircraft().")
    absolute_anchor = s.find(select_anchor, select_start)
    s = s[:absolute_anchor] + s[absolute_anchor:].replace(
        select_anchor,
        select_replacement,
        1
    )

# ---------------------------------------------------------------------------
# 4. Add reliable Selected Aircraft detail panel styling and controller.
# ---------------------------------------------------------------------------

css = r'''
/* ui-audio-cleanup-v8 */
#selected-aircraft-panel-v2 {
  display: none;
  margin-top: 10px;
  padding: 10px;
  border: 1px solid #36424a;
  border-radius: 5px;
  background: #1a2024;
  font-size: 12px;
}
#selected-aircraft-panel-v2.visible {
  display: block;
}
#selected-aircraft-panel-v2 .selected-title {
  color: #fff;
  font-size: 15px;
  font-weight: bold;
  margin-bottom: 8px;
}
#selected-aircraft-panel-v2 .selected-icao {
  margin-left: 7px;
  color: #9da6ad;
  font-size: 12px;
  font-weight: normal;
}
#selected-aircraft-panel-v2 .selected-grid {
  display: grid;
  grid-template-columns: auto 1fr auto 1fr;
  gap: 5px 9px;
  margin-bottom: 9px;
}
#selected-aircraft-panel-v2 .selected-label {
  color: #858e95;
}
#selected-aircraft-panel-v2 .selected-value {
  color: #e6e9eb;
  text-align: right;
}
#selected-aircraft-panel-v2 .selected-actions {
  display: flex;
  gap: 7px;
}
#selected-aircraft-panel-v2 button {
  padding: 4px 9px;
  border: 1px solid #465058;
  border-radius: 4px;
  background: #262e34;
  color: #eee;
  cursor: pointer;
  font-size: 12px;
}
#selected-aircraft-panel-v2 button:hover {
  background: #354048;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style>.")

s = s.replace("</style>", css + "\n</style>", 1)

selected_controller = r'''
<script id="selected-aircraft-panel-v2">
(function () {
  let installed = false;

  function value(item, suffix) {
    if (item === undefined || item === null || item === '') {
      return '—';
    }
    return String(item) + (suffix || '');
  }

  function currentAircraft() {
    if (typeof state === 'undefined' ||
        state.selectedId === null ||
        state.selectedId === undefined ||
        !state.aircraftById) {
      return null;
    }

    return state.aircraftById.get(String(state.selectedId)) || null;
  }

  function install() {
    if (installed) return true;

    const header = document.getElementById('header');
    if (!header) return false;

    const panel = document.createElement('div');
    panel.id = 'selected-aircraft-panel-v2';
    panel.innerHTML = `
      <div class="selected-title">
        <span id="selected-v2-call"></span>
        <span class="selected-icao" id="selected-v2-icao"></span>
      </div>
      <div class="selected-grid">
        <span class="selected-label">Altitude</span>
        <span class="selected-value" id="selected-v2-alt"></span>
        <span class="selected-label">Speed</span>
        <span class="selected-value" id="selected-v2-spd"></span>

        <span class="selected-label">Track</span>
        <span class="selected-value" id="selected-v2-track"></span>
        <span class="selected-label">Messages</span>
        <span class="selected-value" id="selected-v2-msgs"></span>

        <span class="selected-label">Distance</span>
        <span class="selected-value" id="selected-v2-dist"></span>
        <span class="selected-label">Bearing</span>
        <span class="selected-value" id="selected-v2-bearing"></span>

        <span class="selected-label">Last seen</span>
        <span class="selected-value" id="selected-v2-age"></span>
      </div>
      <div class="selected-actions">
        <button type="button" id="selected-v2-center">Center Aircraft</button>
        <button type="button" id="selected-v2-clear">Clear Selection</button>
      </div>
    `;

    const coverage = document.getElementById('coverage-summary');
    if (coverage && coverage.parentNode === header) {
      header.insertBefore(panel, coverage);
    } else {
      header.appendChild(panel);
    }

    document.getElementById('selected-v2-center').addEventListener('click', function () {
      const aircraft = currentAircraft();

      if (!aircraft ||
          typeof aircraft.Lat !== 'number' ||
          typeof aircraft.Long !== 'number' ||
          typeof state === 'undefined' ||
          !state.map) {
        return;
      }

      state.map.setView(
        [aircraft.Lat, aircraft.Long],
        Math.max(state.map.getZoom(), 10)
      );
    });

    document.getElementById('selected-v2-clear').addEventListener('click', function () {
      if (typeof state !== 'undefined') {
        state.selectedId = null;

        if (typeof refreshMarkerIcons === 'function') {
          refreshMarkerIcons();
        }

        if (state.map) {
          state.map.closePopup();
        }
      }

      render();
    });

    installed = true;
    return true;
  }

  function render() {
    if (!install()) return;

    const panel = document.getElementById('selected-aircraft-panel-v2');
    const aircraft = currentAircraft();

    if (!aircraft) {
      panel.classList.remove('visible');
      return;
    }

    const range =
      typeof distanceAndBearing === 'function'
        ? distanceAndBearing(aircraft)
        : null;

    document.getElementById('selected-v2-call').textContent =
      aircraft.Call || aircraft.Icao || String(aircraft.Id);

    document.getElementById('selected-v2-icao').textContent =
      aircraft.Icao || '';

    document.getElementById('selected-v2-alt').textContent =
      value(aircraft.Alt, ' ft');

    document.getElementById('selected-v2-spd').textContent =
      value(aircraft.Spd, ' kt');

    document.getElementById('selected-v2-track').textContent =
      value(aircraft.Trak, '°');

    document.getElementById('selected-v2-msgs').textContent =
      value(aircraft.CMsgs, '');

    document.getElementById('selected-v2-age').textContent =
      value(aircraft.TSecs, ' s');

    document.getElementById('selected-v2-dist').textContent =
      range ? range.distanceNm.toFixed(1) + ' nm' : '—';

    document.getElementById('selected-v2-bearing').textContent =
      range ? range.bearing.toFixed(0) + '°' : '—';

    panel.classList.add('visible');
  }

  window.renderSelectedAircraftDetails = render;

  function start() {
    if (!install()) {
      window.setTimeout(start, 200);
      return;
    }

    render();
    window.setInterval(render, 200);
  }

  start();
})();
</script>
'''

if "</body>" not in s:
    raise SystemExit("Could not find </body>.")

s = s.replace("</body>", selected_controller + "\n</body>", 1)

HTML.write_text(s, encoding="utf-8")

print("Installed UI/audio cleanup v8:")
print("  - Hidden audio buffering percentage")
print("  - Reduced initial airband buffer latency")
print("  - Restored aircraft detail panel")
print("  - Added single-click and double-click aircraft selection")
