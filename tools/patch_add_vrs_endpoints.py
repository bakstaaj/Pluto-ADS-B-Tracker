#!/usr/bin/env python3
import re
from pathlib import Path

p = Path("dump1090.c")
s = p.read_text()

if "vrsAircraftListJson" in s:
    print("VRS endpoint patch already appears to be applied.")
    raise SystemExit(0)

# Add stdarg.h for vrsAppend().
if "#include <stdarg.h>" not in s:
    s = s.replace('#include "anet.h"', '#include <stdarg.h>\n#include "anet.h"', 1)

vrs_code = r'''
/* ======================== VRS-compatible JSON output ====================== */

static void vrsAppend(char **buf, char **p, int *buflen, const char *fmt, ...) {
    while (1) {
        va_list ap;
        int n;
        int used;

        va_start(ap, fmt);
        n = vsnprintf(*p, *buflen, fmt, ap);
        va_end(ap);

        if (n < 0) return;

        if (n < *buflen) {
            *p += n;
            *buflen -= n;
            return;
        }

        used = *p - *buf;
        *buflen = used + n + 1024;
        *buf = realloc(*buf, *buflen);
        if (*buf == NULL) {
            fprintf(stderr, "Out of memory building VRS JSON\n");
            exit(1);
        }
        *p = *buf + used;
        *buflen -= used;
    }
}

static void vrsTrimCallsign(const char *src, char *dst, int dstlen) {
    int i, end;

    if (dstlen <= 0) return;

    for (i = 0; i < dstlen - 1 && src[i]; i++) {
        dst[i] = src[i];
    }
    dst[i] = '\0';

    end = strlen(dst) - 1;
    while (end >= 0 && (dst[end] == ' ' || dst[end] == '\t')) {
        dst[end] = '\0';
        end--;
    }
}

char *vrsAircraftListJson(int *len) {
    int buflen = 4096;
    char *buf = malloc(buflen);
    char *p = buf;
    struct aircraft *a;
    long long now = mstime();
    int total = 0;
    int emitted = 0;

    if (buf == NULL) {
        fprintf(stderr, "Out of memory allocating VRS JSON buffer\n");
        exit(1);
    }

    for (a = Modes.aircrafts; a; a = a->next) {
        total++;
    }

    vrsAppend(&buf, &p, &buflen,
        "{"
        "\"lastDv\":%lld,"
        "\"totalAc\":%d,"
        "\"src\":1,"
        "\"showSil\":false,"
        "\"showFlg\":false,"
        "\"showPic\":false,"
        "\"shtTrlSec\":30,"
        "\"stm\":%lld,"
        "\"feeds\":[{\"id\":1,\"name\":\"Pluto+ ADS-B\"}],"
        "\"srcFeed\":1,"
        "\"configChanged\":false,"
        "\"acList\":[",
        now, total, now);

    for (a = Modes.aircrafts; a; a = a->next) {
        char call[9];
        int tsecs = 0;
        long long pos_time = 0;

        vrsTrimCallsign(a->flight, call, sizeof(call));

        if (a->seen > 0) {
            tsecs = (int)(time(NULL) - a->seen);
            if (tsecs < 0) tsecs = 0;
            pos_time = ((long long)a->seen) * 1000;
        }

        if (emitted) {
            vrsAppend(&buf, &p, &buflen, ",");
        }

        vrsAppend(&buf, &p, &buflen,
            "{"
            "\"Id\":%u,"
            "\"TSecs\":%d,"
            "\"Rcvr\":1,"
            "\"Icao\":\"%s\","
            "\"CMsgs\":%ld",
            a->addr, tsecs, a->hexaddr, a->messages);

        if (call[0]) {
            vrsAppend(&buf, &p, &buflen, ",\"Call\":\"%s\"", call);
        }

        if (a->altitude != 0) {
            vrsAppend(&buf, &p, &buflen, ",\"Alt\":%d", a->altitude);
        }

        if (a->speed != 0) {
            vrsAppend(&buf, &p, &buflen, ",\"Spd\":%d", a->speed);
        }

        if (a->track != 0) {
            vrsAppend(&buf, &p, &buflen, ",\"Trak\":%d", a->track);
        }

        if (a->lat != 0 && a->lon != 0) {
            vrsAppend(&buf, &p, &buflen,
                ",\"Lat\":%.6f,\"Long\":%.6f,\"PosTime\":%lld",
                a->lat, a->lon, pos_time);
        }

        vrsAppend(&buf, &p, &buflen, "}");
        emitted++;
    }

    vrsAppend(&buf, &p, &buflen, "]}\n");
    *len = p - buf;
    return buf;
}

char *vrsServerConfigJson(int *len) {
    const char *json =
        "{"
        "\"GoogleMapsApiKey\":\"\","
        "\"InitialDistanceUnit\":\"nm\","
        "\"InitialHeightUnit\":\"f\","
        "\"InitialSpeedUnit\":\"kt\","
        "\"InitialLatitude\":33.0,"
        "\"InitialLongitude\":-112.0,"
        "\"InitialMapType\":\"m\","
        "\"InitialZoom\":7,"
        "\"MinimumRefreshSeconds\":1,"
        "\"RefreshSeconds\":1,"
        "\"UseMarkerLabels\":true,"
        "\"VrsVersion\":\"Pluto ADS-B Tracker VRS 0.1\","
        "\"Receivers\":[{\"id\":1,\"name\":\"Pluto+ ADS-B\"}],"
        "\"TileServerSettings\":{"
            "\"MapProvider\":0,"
            "\"IsCustom\":true,"
            "\"Name\":\"OpenStreetMap\","
            "\"Url\":\"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png\","
            "\"Subdomains\":\"abc\","
            "\"MinZoom\":1,"
            "\"MaxZoom\":19,"
            "\"Attribution\":\"OpenStreetMap\""
        "}"
        "}\n";

    char *out = strdup(json);
    *len = strlen(out);
    return out;
}

char *vrsDesktopHtml(int *len) {
    const char *html =
        "<!doctype html>"
        "<html>"
        "<head>"
        "<meta charset=\"utf-8\">"
        "<title>Pluto ADS-B Tracker</title>"
        "<style>"
        "body{font-family:Arial,sans-serif;margin:20px;background:#111;color:#eee;}"
        "h1{margin-bottom:4px;}"
        ".muted{color:#aaa;margin-top:0;}"
        "table{border-collapse:collapse;width:100%;margin-top:16px;}"
        "th,td{border-bottom:1px solid #333;padding:6px 8px;text-align:left;}"
        "th{background:#222;}"
        "code{background:#222;padding:2px 4px;border-radius:3px;}"
        "</style>"
        "</head>"
        "<body>"
        "<h1>Pluto ADS-B Tracker</h1>"
        "<p class=\"muted\">VRS-compatible aircraft feed: "
        "<code>/VirtualRadar/AircraftList.json</code></p>"
        "<div id=\"summary\">Loading...</div>"
        "<table>"
        "<thead><tr>"
        "<th>ICAO</th><th>Call</th><th>Alt</th><th>Speed</th><th>Track</th><th>Lat</th><th>Lon</th><th>Msgs</th><th>Age</th>"
        "</tr></thead>"
        "<tbody id=\"rows\"></tbody>"
        "</table>"
        "<script>"
        "async function refresh(){"
        "try{"
        "const r=await fetch('/VirtualRadar/AircraftList.json?_=' + Date.now());"
        "const j=await r.json();"
        "document.getElementById('summary').textContent='Aircraft tracked: '+j.totalAc+' | Server time: '+new Date(j.stm).toLocaleTimeString();"
        "const rows=document.getElementById('rows');"
        "rows.innerHTML='';"
        "(j.acList||[]).forEach(a=>{"
        "const tr=document.createElement('tr');"
        "tr.innerHTML='<td>'+(a.Icao||'')+'</td><td>'+(a.Call||'')+'</td><td>'+(a.Alt||'')+'</td><td>'+(a.Spd||'')+'</td><td>'+(a.Trak||'')+'</td><td>'+(a.Lat||'')+'</td><td>'+(a.Long||'')+'</td><td>'+(a.CMsgs||'')+'</td><td>'+(a.TSecs||0)+'s</td>';"
        "rows.appendChild(tr);"
        "});"
        "}catch(e){document.getElementById('summary').textContent='Error loading aircraft list: '+e;}"
        "}"
        "refresh();setInterval(refresh,1000);"
        "</script>"
        "</body>"
        "</html>";

    char *out = strdup(html);
    *len = strlen(out);
    return out;
}

'''

marker = '#define MODES_CONTENT_TYPE_HTML "text/html;charset=utf-8"'
if marker not in s:
    raise SystemExit("Could not find MODES_CONTENT_TYPE_HTML insertion point.")

s = s.replace(marker, vrs_code + "\n" + marker, 1)

# Flexible match for the original route:
# if (strstr(url, "/data.json")) { content = aircraftsToJson(&clen); ctype = MODES_CONTENT_TYPE_JSON; } else {
route_re = re.compile(
    r'if\s*\(\s*strstr\s*\(\s*url\s*,\s*"/data\.json"\s*\)\s*\)\s*'
    r'\{\s*content\s*=\s*aircraftsToJson\s*\(\s*&clen\s*\)\s*;\s*'
    r'ctype\s*=\s*MODES_CONTENT_TYPE_JSON\s*;\s*\}\s*else\s*\{',
    re.DOTALL
)

new_route = '''if (strstr(url, "/VirtualRadar/AircraftList.json")) {
        content = vrsAircraftListJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strstr(url, "/VirtualRadar/ServerConfig.json")) {
        content = vrsServerConfigJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else if (strcmp(url, "/VirtualRadar/") == 0 || strstr(url, "/VirtualRadar/desktop.html")) {
        content = vrsDesktopHtml(&clen);
        ctype = MODES_CONTENT_TYPE_HTML;
    } else if (strstr(url, "/data.json")) {
        content = aircraftsToJson(&clen);
        ctype = MODES_CONTENT_TYPE_JSON;
    } else {'''

s2, count = route_re.subn(new_route, s, count=1)

if count != 1:
    print("Could not find HTTP route block to patch.")
    print()
    print("Diagnostic matches:")
    for pat in ["/data.json", "aircraftsToJson(&clen)", "MODES_CONTENT_TYPE_JSON", "handleHTTPRequest"]:
        print(f"  {pat}: {'FOUND' if pat in s else 'NOT FOUND'}")
    raise SystemExit(1)

p.write_text(s2)
print("Applied VRS endpoint patch.")
