#!/usr/bin/env python3
import re
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

MARKER = "airband-dblclick-cleanup-v9"

if MARKER in s:
    print("Airband double-click cleanup v9 is already installed.")
    raise SystemExit(0)

if '<script id="airband-controller-v3">' not in s:
    raise SystemExit("Could not find airband-controller-v3.")

# ---------------------------------------------------------------------------
# Hide the changing live buffer display. Web Audio continues operating.
# ---------------------------------------------------------------------------

css = r'''
/* airband-dblclick-cleanup-v9 */
#airband-v3-audio-area {
  display: none !important;
}
#airband-v3-table tbody tr {
  cursor: pointer;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style>.")

s = s.replace("</style>", css + "\n</style>", 1)

# Make bufferMessage() intentionally silent.
buffer_function = re.compile(
    r"""  function bufferMessage\(message\) \{
.*?
  \}

""",
    re.DOTALL
)

replacement = """  function bufferMessage(message) {
    /*
     * Audio buffering remains internal. The user only needs the stable
     * Listening / ADS-B paused status shown above the frequency table.
     */
    void message;
  }

"""

s, count = buffer_function.subn(replacement, s, count=1)

if count != 1:
    raise SystemExit("Could not find bufferMessage() to silence.")

# Remove changing PCM-buffer count from the main listening status.
old_status = """        status(
          'Listening ' +
          (backend.frequency_hz / 1000000).toFixed(3) +
          ' MHz AM · ADS-B paused · ' +
          (backend.pcm_samples || 0) +
          ' samples buffered.',
          true
        );"""

new_status = """        status(
          'Listening ' +
          (backend.frequency_hz / 1000000).toFixed(3) +
          ' MHz AM · ADS-B paused.',
          true
        );"""

if old_status in s:
    s = s.replace(old_status, new_status, 1)
elif "' samples buffered.'" in s:
    raise SystemExit("Found a different buffered-status format; inspect pollBackend().")

# ---------------------------------------------------------------------------
# Improve selection prompt.
# ---------------------------------------------------------------------------

s = s.replace(
    "Select a frequency.</div>",
    "Select a frequency, or double-click a row to listen.</div>",
    1
)

s = s.replace(
    "output.textContent = 'Select a frequency.';",
    "output.textContent = 'Select a frequency, or double-click a row to listen.';",
    1
)

# ---------------------------------------------------------------------------
# Add double-click-to-listen on each frequency row.
# ---------------------------------------------------------------------------

old_row_handler = """      row.addEventListener('click', function () {
        if (stateV3.listening) {
          status('Stop listening before changing frequencies.', true);
          return;
        }

        stateV3.selected = channel;
        renderRows();
        renderSelected();
      });

      rows.appendChild(row);"""

new_row_handler = """      row.title = 'Double-click to listen';

      row.addEventListener('click', function () {
        if (stateV3.listening) {
          status('Stop listening before changing frequencies.', true);
          return;
        }

        stateV3.selected = channel;
        renderRows();
        renderSelected();
      });

      row.addEventListener('dblclick', function (event) {
        event.preventDefault();

        if (stateV3.listening) {
          status('Stop listening before changing frequencies.', true);
          return;
        }

        stateV3.selected = channel;
        renderRows();
        renderSelected();
        beginListening();
      });

      rows.appendChild(row);"""

if old_row_handler not in s:
    raise SystemExit("Could not find the frequency row click-handler block.")

s = s.replace(old_row_handler, new_row_handler, 1)

HTML.write_text(s, encoding="utf-8")

print("Installed Airband UI cleanup v9:")
print("  - Hidden changing live-buffer display")
print("  - Simplified listening status")
print("  - Added double-click-to-listen on frequency rows")
