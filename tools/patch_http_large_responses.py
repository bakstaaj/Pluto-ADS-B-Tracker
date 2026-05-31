#!/usr/bin/env python3
import re
from pathlib import Path

SRC = Path("dump1090.c")
s = SRC.read_text(encoding="utf-8")

if "httpWriteAll" in s:
    print("Large HTTP response support is already installed.")
    raise SystemExit(0)

anchor = "int handleHTTPRequest(struct client *c) {"

if anchor not in s:
    raise SystemExit("Could not find handleHTTPRequest() insertion point.")

helper = r'''/*
 * Send a complete HTTP response over the nonblocking client socket.
 *
 * The original dump1090 HTTP handler assumes that the socket can accept an
 * entire response in one write(). That works for the small original map and
 * data.json output, but fails for the VRS page and FAA frequency database.
 */
static int httpWriteAll(int fd, const void *buffer, size_t length) {
    const char *p = (const char *)buffer;
    size_t remaining = length;

    while (remaining > 0) {
        ssize_t written = write(fd, p, remaining);

        if (written > 0) {
            p += written;
            remaining -= (size_t)written;
            continue;
        }

        if (written < 0 && errno == EINTR) {
            continue;
        }

        if (written < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
            fd_set writefds;
            struct timeval timeout;
            int ready;

            FD_ZERO(&writefds);
            FD_SET(fd, &writefds);

            timeout.tv_sec = 2;
            timeout.tv_usec = 0;

            ready = select(fd + 1, NULL, &writefds, NULL, &timeout);

            if (ready > 0) {
                continue;
            }

            return 1;
        }

        return 1;
    }

    return 0;
}

'''

s = s.replace(anchor, helper + anchor, 1)

pattern = re.compile(
    r'if\s*\(\s*write\s*\(\s*c->fd\s*,\s*hdr\s*,\s*hdrlen\s*\)\s*!=\s*hdrlen\s*\|\|\s*'
    r'write\s*\(\s*c->fd\s*,\s*content\s*,\s*clen\s*\)\s*!=\s*clen\s*\)\s*\{',
    re.DOTALL
)

replacement = '''if (httpWriteAll(c->fd, hdr, (size_t)hdrlen) ||
        httpWriteAll(c->fd, content, (size_t)clen)) {'''

s2, count = pattern.subn(replacement, s, count=1)

if count != 1:
    raise SystemExit(
        "Could not find the original single-write HTTP response block. "
        "Run: grep -n 'write(c->fd' dump1090.c"
    )

SRC.write_text(s2, encoding="utf-8")

print("Added complete HTTP-response writer for large VRS and FAA payloads.")
