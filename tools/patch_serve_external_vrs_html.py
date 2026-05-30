#!/usr/bin/env python3
import re
from pathlib import Path

SRC = Path("dump1090.c")
MAKEFILE = Path("Makefile")

s = SRC.read_text(encoding="utf-8")

# The HTML is no longer compiled into the ARM executable.
s = s.replace('#include "generated/vrs_web_assets.h"\n', '')

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

new_function = r'''#define VRS_DESKTOP_HTML_FILE "/mnt/jffs2/pluto_adsb_tracker/web/vrs_desktop.html"

char *vrsDesktopHtml(int *len) {
    FILE *fp;
    long size;
    size_t bytes_read;
    char *out;

    const char *fallback =
        "<!doctype html>"
        "<html><head><meta charset=\"utf-8\">"
        "<title>Pluto ADS-B Tracker</title></head>"
        "<body style=\"font-family:Arial,sans-serif;background:#111;color:#eee;padding:30px\">"
        "<h1>Pluto ADS-B Tracker</h1>"
        "<p>Unable to load <code>/mnt/jffs2/pluto_adsb_tracker/web/vrs_desktop.html</code>.</p>"
        "<p>Run the deploy script again to install the web interface.</p>"
        "</body></html>";

    fp = fopen(VRS_DESKTOP_HTML_FILE, "rb");

    if (fp == NULL) {
        out = strdup(fallback);
        *len = strlen(out);
        return out;
    }

    if (fseek(fp, 0, SEEK_END) != 0 ||
        (size = ftell(fp)) < 0 ||
        fseek(fp, 0, SEEK_SET) != 0) {
        fclose(fp);
        out = strdup(fallback);
        *len = strlen(out);
        return out;
    }

    out = malloc((size_t)size + 1);

    if (out == NULL) {
        fclose(fp);
        fprintf(stderr, "Out of memory serving VRS desktop HTML\n");
        exit(1);
    }

    bytes_read = fread(out, 1, (size_t)size, fp);
    fclose(fp);

    if (bytes_read != (size_t)size) {
        free(out);
        out = strdup(fallback);
        *len = strlen(out);
        return out;
    }

    out[size] = '\0';
    *len = (int)size;
    return out;
}

'''

start, end = bounds
s = s[:start] + new_function + s[end:]
SRC.write_text(s, encoding="utf-8")

# Remove the obsolete dependency; web HTML is now a deployed runtime file.
if MAKEFILE.exists():
    m = MAKEFILE.read_text(encoding="utf-8")
    m = m.replace(
        "\n# Rebuild the HTTP server object whenever the embedded VRS web page changes.\n"
        "dump1090.o: generated/vrs_web_assets.h\n",
        "\n"
    )
    m = m.replace(
        "\n# Rebuild HTTP server object when embedded web UI changes.\n"
        "dump1090.o: generated/vrs_web_assets.h\n",
        "\n"
    )
    MAKEFILE.write_text(m, encoding="utf-8")

print("Changed VRS desktop serving from embedded asset to runtime HTML file.")
print("Runtime path: /mnt/jffs2/pluto_adsb_tracker/web/vrs_desktop.html")
