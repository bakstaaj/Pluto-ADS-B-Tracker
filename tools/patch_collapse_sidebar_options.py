#!/usr/bin/env python3
import re
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

if 'id="options-panel"' in s:
    print("Collapsible Options panel is already present.")
    raise SystemExit(0)

# ---------------------------------------------------------------------------
# Add panel styling
# ---------------------------------------------------------------------------

css = r'''
#options-panel {
  margin-top: 10px;
  border: 1px solid #31343a;
  border-radius: 5px;
  background: #1b1d21;
}
#options-panel summary {
  cursor: pointer;
  padding: 8px 10px;
  color: #ddd;
  font-size: 13px;
  font-weight: bold;
  list-style: none;
  user-select: none;
}
#options-panel summary::-webkit-details-marker {
  display: none;
}
#options-panel summary::before {
  content: '▶';
  display: inline-block;
  width: 16px;
  color: #9da6ad;
  font-size: 11px;
}
#options-panel[open] summary::before {
  content: '▼';
}
#options-panel summary:hover {
  background: #23262b;
}
#options-panel-body {
  padding: 0 10px 10px 10px;
  border-top: 1px solid #31343a;
}
#options-panel #controls {
  margin-top: 10px;
}
#options-panel #display-settings {
  margin-top: 10px;
}
'''

if "</style>" not in s:
    raise SystemExit("Could not find </style> insertion point.")

s = s.replace("</style>", css + "\n</style>", 1)

# ---------------------------------------------------------------------------
# Find the controls area and the complete Map Display div.
# ---------------------------------------------------------------------------

controls_start = s.find('<div id="controls">')
if controls_start < 0:
    raise SystemExit('Could not find <div id="controls">.')

settings_start = s.find('<div id="display-settings">', controls_start)
if settings_start < 0:
    raise SystemExit('Could not find <div id="display-settings"> after controls.')

def find_matching_div_end(text, start):
    token_re = re.compile(r'<div\b[^>]*>|</div\s*>', re.IGNORECASE)
    depth = 0

    for match in token_re.finditer(text, start):
        token = match.group(0).lower()

        if token.startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return match.end()

    return None

settings_end = find_matching_div_end(s, settings_start)
if settings_end is None:
    raise SystemExit("Could not find closing </div> for Map Display settings.")

existing_options = s[controls_start:settings_end]

wrapped_options = '''<details id="options-panel">
        <summary>Options</summary>
        <div id="options-panel-body">
''' + existing_options + '''
        </div>
      </details>'''

s = s[:controls_start] + wrapped_options + s[settings_end:]

HTML.write_text(s, encoding="utf-8")

print("Wrapped sidebar controls in a collapsed Options panel.")
print("The aircraft status line remains visible above the collapsed panel.")
