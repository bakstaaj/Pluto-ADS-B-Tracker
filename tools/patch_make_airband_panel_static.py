#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if '<script id="airband-listen-ui-v1">' not in s:
    raise SystemExit(
        "Airband Listen JavaScript is missing. "
        "Run tools/patch_add_airband_listen_panel.py, "
        "tools/patch_airband_auto_select_best.py and "
        "tools/patch_connect_airband_listen_ui.py first."
    )

if "airband-functional-audio-v1" not in s:
    raise SystemExit(
        "Functional Airband audio UI is missing. "
        "Run tools/patch_connect_airband_listen_ui.py first."
    )

static_panel = r'''      <details id="airband-panel">
        <summary>Airband Listen</summary>
        <div id="airband-panel-body">
          <div id="airband-status">Loading FAA airband frequency data...</div>
          <div id="airband-source"></div>
          <div id="airband-table-wrap">
            <table id="airband-table">
              <thead>
                <tr>
                  <th>Freq</th>
                  <th>Use / Facility</th>
                  <th>Dist</th>
                </tr>
              </thead>
              <tbody id="airband-rows"></tbody>
            </table>
          </div>
          <div id="airband-selected">Select a listed frequency.</div>
          <div id="airband-audio-area">
            <audio id="airband-audio-player" controls preload="none"></audio>
            <div id="airband-audio-note">
              Live AM audio is delivered in short WAV segments. Press Play manually if browser autoplay is blocked.
            </div>
          </div>
          <div class="airband-actions">
            <button type="button" id="airband-best">Select Best Nearby</button>
            <button type="button" id="airband-listen">Listen</button>
            <button type="button" id="airband-stop" disabled>Stop / Resume ADS-B</button>
          </div>
        </div>
      </details>

'''

# Add the visible, permanent panel above Options.
if '<details id="airband-panel">' not in s:
    anchor = '      <details id="options-panel">'
    if anchor not in s:
        raise SystemExit("Could not find the Options panel insertion point.")
    s = s.replace(anchor, static_panel + anchor, 1)
    print("Inserted permanent Airband Listen panel in sidebar.")
else:
    print("Permanent Airband Listen panel already exists.")

# Replace the dynamic panel-creation function with one that wires up the
# permanent panel already present in the page.
start = s.find("  function installPanel() {")
end = s.find("  function render() {", start)

if start < 0 or end < 0:
    raise SystemExit("Could not locate installPanel() in Airband JavaScript.")

new_install = r'''  function installPanel() {
    if (installed) return true;

    const panel = document.getElementById('airband-panel');
    const bestButton = document.getElementById('airband-best');
    const listenButton = document.getElementById('airband-listen');
    const stopButton = document.getElementById('airband-stop');

    if (!panel ||
        !bestButton ||
        !listenButton ||
        !stopButton ||
        typeof state === 'undefined') {
      return false;
    }

    bestButton.addEventListener('click', function () {
      if (playbackActive) {
        actionStatus = 'Stop listening before selecting a different frequency.';
        render();
        return;
      }

      const ranked = rankedChannels();

      if (!ranked.length) {
        document.getElementById('airband-status').textContent =
          'Set the receiver location before selecting a nearby frequency.';
        return;
      }

      automaticallyChooseBest(ranked, true);
      render();
    });

    listenButton.addEventListener('click', function () {
      startListening();
    });

    stopButton.addEventListener('click', function () {
      stopListening();
    });

    installed = true;
    updateListenButtons();
    return true;
  }

'''

s = s[:start] + new_install + s[end:]

# Add a small visible hint so the collapsed panel is obvious.
if "#airband-panel summary::after" not in s:
    style_marker = "#airband-panel[open] summary::before { content: '▼'; }"
    replacement = style_marker + r'''
#airband-panel summary::after {
  content: 'AM radio';
  float: right;
  color: #7f8992;
  font-size: 11px;
  font-weight: normal;
}
'''
    if style_marker in s:
        s = s.replace(style_marker, replacement, 1)

HTML.write_text(s, encoding="utf-8")
print("Airband Listen is now permanent HTML and no longer depends on dynamic panel insertion.")
