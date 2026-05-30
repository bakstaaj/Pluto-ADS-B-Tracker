#!/usr/bin/env python3
import re
from pathlib import Path

SRC = Path("dump1090.c")
MAKEFILE = Path("Makefile")
BUILD = Path("tools/build_pluto_v0_39.sh")

s = SRC.read_text(encoding="utf-8")

include_line = '#include "generated/vrs_web_assets.h"\n'

if include_line not in s:
    if "#include <stdarg.h>\n" in s:
        s = s.replace(
            "#include <stdarg.h>\n",
            "#include <stdarg.h>\n" + include_line,
            1
        )
    elif '#include "anet.h"\n' in s:
        s = s.replace(
            '#include "anet.h"\n',
            '#include "anet.h"\n' + include_line,
            1
        )
    else:
        raise SystemExit("Could not find include insertion point in dump1090.c.")

def find_function_bounds(source, func_name):
    match = re.search(
        r'char\s*\*\s*' + re.escape(func_name) +
        r'\s*\(\s*int\s*\*\s*len\s*\)',
        source
    )

    if not match:
        return None

    brace_start = source.find("{", match.end())
    if brace_start < 0:
        return None

    depth = 0
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escaped = False
    i = brace_start

    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ""

        if in_line_comment:
            if c == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if c == "*" and n == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == "'":
                in_char = False
            i += 1
            continue

        if c == "/" and n == "/":
            in_line_comment = True
            i += 2
            continue

        if c == "/" and n == "*":
            in_block_comment = True
            i += 2
            continue

        if c == '"':
            in_string = True
            i += 1
            continue

        if c == "'":
            in_char = True
            i += 1
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                while end < len(source) and source[end] in " \t\r\n":
                    end += 1
                return match.start(), end

        i += 1

    return None

bounds = find_function_bounds(s, "vrsDesktopHtml")
if not bounds:
    raise SystemExit("Could not find vrsDesktopHtml() in dump1090.c.")

new_function = r'''char *vrsDesktopHtml(int *len) {
    char *out = malloc(vrs_desktop_html_len + 1);

    if (out == NULL) {
        fprintf(stderr, "Out of memory serving VRS desktop HTML\n");
        exit(1);
    }

    memcpy(out, vrs_desktop_html, vrs_desktop_html_len);
    out[vrs_desktop_html_len] = '\0';
    *len = (int)vrs_desktop_html_len;
    return out;
}

'''

start, end = bounds
s = s[:start] + new_function + s[end:]
SRC.write_text(s, encoding="utf-8")

m = MAKEFILE.read_text(encoding="utf-8")
dependency = "dump1090.o: generated/vrs_web_assets.h"
if dependency not in m:
    m += "\n# Rebuild HTTP server object when embedded web UI changes.\n" + dependency + "\n"
    MAKEFILE.write_text(m, encoding="utf-8")

b = BUILD.read_text(encoding="utf-8")
if "tools/generate_web_assets.py" not in b:
    anchor = 'cd "$ROOT_DIR"\n'
    if anchor not in b:
        raise SystemExit("Could not find build script insertion point.")
    b = b.replace(
        anchor,
        anchor + '\necho "== Generating embedded web assets =="\n'
                 'python3 "$ROOT_DIR/tools/generate_web_assets.py"\n'
                 'echo\n',
        1
    )
    BUILD.write_text(b, encoding="utf-8")

print("Repaired web asset embedding.")
print("dump1090.c now serves generated/vrs_web_assets.h.")
print("Makefile now rebuilds dump1090.o when the generated header changes.")
