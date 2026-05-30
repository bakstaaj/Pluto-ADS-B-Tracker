#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "dump1090.c"

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
        raise SystemExit("Could not find a safe include insertion location.")

def find_function_bounds(source, func_name):
    signature = re.search(
        r'char\s*\*\s*' + re.escape(func_name) +
        r'\s*\(\s*int\s*\*\s*len\s*\)',
        source
    )

    if not signature:
        return None

    brace_start = source.find("{", signature.end())
    if brace_start < 0:
        return None

    depth = 0
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escape = False
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
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
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
                return signature.start(), end

        i += 1

    return None

bounds = find_function_bounds(s, "vrsDesktopHtml")

if not bounds:
    raise SystemExit("Could not find vrsDesktopHtml() function bounds.")

new_function = '''char *vrsDesktopHtml(int *len) {
    char *out = malloc(vrs_desktop_html_len + 1);

    if (out == NULL) {
        fprintf(stderr, "Out of memory serving VRS desktop HTML\\n");
        exit(1);
    }

    memcpy(out, vrs_desktop_html, vrs_desktop_html_len + 1);
    *len = (int)vrs_desktop_html_len;
    return out;
}

'''

start, end = bounds
s = s[:start] + new_function + s[end:]

SRC.write_text(s, encoding="utf-8")
print("Updated dump1090.c to serve generated web/vrs_desktop.html asset.")
