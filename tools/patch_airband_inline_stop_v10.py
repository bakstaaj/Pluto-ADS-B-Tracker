#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

MARKER = "airband-inline-stop-v10"

if MARKER in s:
    print("Airband inline stop control v10 is already installed.")
    raise SystemExit(0)

if '<script id="airband-controller-v3">' not in s:
    raise SystemExit("Could not find airband-controller-v3.")

# ---------------------------------------------------------------------------
# Replace the standalone status div with a status line and compact stop button.
# ---------------------------------------------------------------------------

old_status_html = '''            <div id="airband-v3-status">Loading airband frequency data...</div>'''

new_status_html = '''            <div id="airband-v3-status-line">
              <span id="airband-v3-status">Loading airband frequency data...</span>
              <button type="button"
                      id="airband-v3-inline-stop"
                      title="Stop listening and resume ADS-B"
                      aria-label="Stop listening and resume ADS-B"
                      disabled>■</button>
            </div>'''

if old_status_html not in s:
    raise SystemExit("Could not find the Airband status HTML element.")

s = s.replace(old_status_html, new_status_html, 1)

# ---------------------------------------------------------------------------
# Add compact inline-stop styling.
# ---------------------------------------------------------------------------

css = r'''
/* airband-inline-stop-v10 */
#airband-v3-status-line {
  display: flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 7px;
  min-height: 22px;
}
#airband-v3-status-line #airband-v3-status {
  margin-bottom: 0;
}
#airband-v3-inline-stop {
  display: none;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  width: 21px;
  height: 21px;
  padding: 0;
  border: 1px solid #b79b32;
  border-radius: 4px;
  background: #28251a;
  color: #ffdf4d;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
}
#airband-v3-inline-stop.visible {
  display: inline-flex;
}
#airband-v3-inline-stop:hover {
  background: #393223;
  border-color: #ffdf4d;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style>.")

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Show or hide the inline stop button based on listening state.
# ---------------------------------------------------------------------------

old_status_function = '''  function status(message, listening) {
    const output = element('airband-v3-status');
    output.textContent = message;
    output.classList.toggle('listening', !!listening);
  }
'''

new_status_function = '''  function status(message, listening) {
    const output = element('airband-v3-status');
    const inlineStop = element('airband-v3-inline-stop');

    output.textContent = message;
    output.classList.toggle('listening', !!listening);

    if (inlineStop) {
      inlineStop.classList.toggle('visible', !!listening);
      inlineStop.disabled = !listening;
    }
  }
'''

if old_status_function not in s:
    raise SystemExit("Could not find the Airband status() function.")

s = s.replace(old_status_function, new_status_function, 1)

# ---------------------------------------------------------------------------
# Wire the compact stop button to the existing stop/resume action.
# ---------------------------------------------------------------------------

old_handlers = '''    element('airband-v3-listen').addEventListener('click', beginListening);
    element('airband-v3-stop').addEventListener('click', endListening);

'''

new_handlers = '''    element('airband-v3-listen').addEventListener('click', beginListening);
    element('airband-v3-stop').addEventListener('click', endListening);
    element('airband-v3-inline-stop').addEventListener('click', endListening);

'''

if old_handlers not in s:
    raise SystemExit("Could not find Airband Listen / Stop handler initialization.")

s = s.replace(old_handlers, new_handlers, 1)

HTML.write_text(s, encoding="utf-8")

print("Installed Airband inline stop control v10.")
print("The compact stop button appears beside the yellow listening status.")
