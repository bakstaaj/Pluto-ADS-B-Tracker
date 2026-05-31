#!/usr/bin/env python3
import re
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

MARKER = "coverage-summary-removed-v11"

if MARKER in s:
    print("Coverage Summary removal v11 is already installed.")
    raise SystemExit(0)

def remove_balanced_div_by_id(text, element_id):
    start_match = re.search(
        r'<div\b[^>]*\bid=["\']' + re.escape(element_id) + r'["\'][^>]*>',
        text,
        re.IGNORECASE
    )

    if not start_match:
        return text, False

    token_re = re.compile(r'<div\b[^>]*>|</div\s*>', re.IGNORECASE)
    depth = 0

    for match in token_re.finditer(text, start_match.start()):
        token = match.group(0).lower()

        if token.startswith("<div"):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return text[:start_match.start()] + text[match.end():], True

    raise SystemExit("Could not find closing div for Coverage Summary.")

# ---------------------------------------------------------------------------
# Remove the visible Coverage Summary panel.
# ---------------------------------------------------------------------------

s, removed = remove_balanced_div_by_id(s, "coverage-summary")

if removed:
    print("Removed visible Coverage Summary panel.")
else:
    print("Coverage Summary panel was already absent.")

# ---------------------------------------------------------------------------
# Remove unused Coverage Summary CSS.
# ---------------------------------------------------------------------------

coverage_css = re.compile(
    r'\n?#coverage-summary\s*\{.*?'
    r'#coverage-summary\s+select\s*\{.*?\}\s*',
    re.DOTALL
)

s, css_count = coverage_css.subn("\n", s, count=1)

if css_count:
    print("Removed Coverage Summary CSS.")

# ---------------------------------------------------------------------------
# Move the useful sorting control into Options -> Map Display.
# ---------------------------------------------------------------------------

if 'id="aircraft-sort"' not in s:
    trail_select_start = s.find('<select id="trail-points">')

    if trail_select_start < 0:
        raise SystemExit("Could not find Trail history select box in Map Display.")

    trail_select_end = s.find('</select>', trail_select_start)

    if trail_select_end < 0:
        raise SystemExit("Could not find end of Trail history select box.")

    trail_select_end += len('</select>')

    sort_control = r'''

          <label for="aircraft-sort">Sort aircraft</label>
          <select id="aircraft-sort">
            <option value="range-desc" selected>Range: farthest first</option>
            <option value="range-asc">Range: nearest first</option>
            <option value="callsign">Callsign</option>
            <option value="altitude-desc">Altitude: highest first</option>
          </select>'''

    s = s[:trail_select_end] + sort_control + s[trail_select_end:]
    print("Moved Sort aircraft control into Options -> Map Display.")
else:
    print("Sort aircraft control already remains in the page.")

# ---------------------------------------------------------------------------
# Remove the refresh-time Coverage Summary call.
# Without this removal it would reference DOM elements that no longer exist.
# ---------------------------------------------------------------------------

s, call_count = re.subn(
    r'\n\s*updateCoverageSummary\s*\(\s*acList\s*\)\s*;\s*',
    "\n",
    s
)

if call_count:
    print("Removed live Coverage Summary refresh call.")

# ---------------------------------------------------------------------------
# Remove unused Coverage Summary calculation helpers while preserving list
# sorting logic.
# ---------------------------------------------------------------------------

helper_start = s.find("function aircraftRangeRecord(a) {")
helper_end = s.find("function compareAircraftForList(a, b) {", helper_start)

if helper_start >= 0 and helper_end > helper_start:
    s = s[:helper_start] + s[helper_end:]
    print("Removed unused Coverage Summary calculation helpers.")

# Remove no-longer-used session maximum state/reset statements.
s = s.replace("  sessionMaximumRange: null,\n", "")
s = s.replace("  state.sessionMaximumRange = null;\n", "")

# ---------------------------------------------------------------------------
# Keep the selected aircraft panel above Options after Coverage Summary is gone.
# ---------------------------------------------------------------------------

old_insert = """    const coverage = document.getElementById('coverage-summary');
    if (coverage && coverage.parentNode === header) {
      header.insertBefore(panel, coverage);
    } else {
      header.appendChild(panel);
    }
"""

new_insert = """    const options = document.getElementById('options-panel');
    if (options && options.parentNode === header) {
      header.insertBefore(panel, options);
    } else {
      header.appendChild(panel);
    }
"""

if old_insert in s:
    s = s.replace(old_insert, new_insert, 1)
    print("Kept Selected Aircraft panel positioned above Options.")

# Add a source marker for deployment verification.
if "</style>" not in s:
    raise SystemExit("Could not find style closing tag.")

s = s.replace(
    "</style>",
    "\n/* coverage-summary-removed-v11 */\n</style>",
    1
)

HTML.write_text(s, encoding="utf-8")

print("Coverage Summary removal complete.")
