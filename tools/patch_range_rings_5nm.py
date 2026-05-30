#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

old_array = "const RANGE_RINGS_NM = [25, 50, 100, 150];"
new_array = "const RANGE_RINGS_NM = Array.from({ length: 30 }, (_, index) => (index + 1) * 5);"

if old_array in s:
    s = s.replace(old_array, new_array, 1)
elif new_array in s:
    print("5 nm ring spacing is already configured.")
else:
    raise SystemExit("Could not find RANGE_RINGS_NM definition.")

old_status = """`Receiver: ${state.receiverLocation.lat.toFixed(5)}, ${state.receiverLocation.lon.toFixed(5)} | Rings: 25 / 50 / 100 / 150 nm`;"""
new_status = """`Receiver: ${state.receiverLocation.lat.toFixed(5)}, ${state.receiverLocation.lon.toFixed(5)} | Rings: every 5 nm to 150 nm`;"""

if old_status in s:
    s = s.replace(old_status, new_status, 1)

old_ring = """    const ring = L.circle(position, {
      radius: ringNm * 1852,
      color: '#30343b',
      weight: 2,
      opacity: 0.88,
      fill: false,
      dashArray: '7 6',
      interactive: false
    });"""

new_ring = """    const majorRing = ringNm % 25 === 0;

    const ring = L.circle(position, {
      radius: ringNm * 1852,
      color: majorRing ? '#30343b' : '#444951',
      weight: majorRing ? 2 : 1,
      opacity: majorRing ? 0.90 : 0.52,
      fill: false,
      dashArray: majorRing ? '7 6' : '3 8',
      interactive: false
    });"""

if old_ring in s:
    s = s.replace(old_ring, new_ring, 1)
elif "const majorRing = ringNm % 25 === 0;" in s:
    print("Major/minor ring styling is already configured.")
else:
    raise SystemExit("Could not find dark-gray range-ring style block.")

HTML.write_text(s, encoding="utf-8")
print("Configured receiver rings every 5 nm through 150 nm.")
print("Major rings remain emphasized every 25 nm.")
