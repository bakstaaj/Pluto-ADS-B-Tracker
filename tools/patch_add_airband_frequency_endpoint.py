#!/usr/bin/env python3
from pathlib import Path

SRC = Path("dump1090.c")
s = SRC.read_text(encoding="utf-8")

if "vrsAirbandFrequenciesJson" in s:
    print("Airband frequency endpoint is already installed.")
    raise SystemExit(0)

marker = '#define VRS_DESKTOP_HTML_FILE "/mnt/jffs2/pluto_adsb_tracker/web/vrs_desktop.html"'

if marker not in s:
    raise SystemExit("Could not find VRS_DESKTOP_HTML_FILE runtime web marker.")

code = r'''
#define VRS_AIRBAND_FREQUENCY_FILE "/mnt/jffs2/pluto_adsb_tracker/data/airband_frequencies.json"

char *vrsAirbandFrequenciesJson(int *len) {
    FILE *fp;
    long size;
    size_t bytes_read;
    char *out;

    const char *fallback =
        "{\"metadata\":{\"status\":\"not-installed\","
        "\"message\":\"Airband frequency database has not been deployed.\"},"
        "\"channels\":[]}";

    fp = fopen(VRS_AIRBAND_FREQUENCY_FILE, "rb");

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
        fprintf(stderr, "Out of memory serving airband frequency JSON\n");
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

s = s.replace(marker, code + "\n" + marker, 1)

route_anchor = '} else if (strcmp(url, "/VirtualRadar/") == 0 || strstr(url, "/VirtualRadar/desktop.html")) {'

if route_anchor not in s:
    raise SystemExit("Could not find the /VirtualRadar/ desktop route.")

new_route = '''} else if (strstr(url, "/VirtualRadar/Airband/Frequencies.json")) {
        content = vrsAirbandFrequenciesJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    ''' + route_anchor

s = s.replace(route_anchor, new_route, 1)
SRC.write_text(s, encoding="utf-8")

print("Added /VirtualRadar/Airband/Frequencies.json endpoint.")
