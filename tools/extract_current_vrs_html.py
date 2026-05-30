#!/usr/bin/env python3
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "dump1090.c"
OUT = ROOT / "web" / "vrs_desktop.html"

s = SRC.read_text(encoding="utf-8")

start = s.find("char *vrsDesktopHtml")
if start < 0:
    raise SystemExit("Could not find vrsDesktopHtml() in dump1090.c")

end_marker = s.find("#define MODES_CONTENT_TYPE_HTML", start)
if end_marker < 0:
    end_marker = len(s)

area = s[start:end_marker]

match = re.search(
    r'const\s+char\s+\*html\s*=\s*(.*?)\s*;\s*'
    r'char\s+\*out\s*=\s*strdup\s*\(\s*html\s*\)',
    area,
    re.DOTALL
)

if not match:
    raise SystemExit("Could not find embedded HTML text inside vrsDesktopHtml().")

literal_area = match.group(1)
string_literals = re.findall(r'"(?:\\.|[^"\\])*"', literal_area)

if not string_literals:
    raise SystemExit("No C string literals found in vrsDesktopHtml().")

html = "".join(ast.literal_eval(item) for item in string_literals)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(html, encoding="utf-8")

print(f"Extracted current working page to: {OUT}")
print(f"HTML size: {len(html.encode('utf-8'))} bytes")
