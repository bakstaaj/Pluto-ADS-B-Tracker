#!/usr/bin/env python3
from pathlib import Path

HTML = Path("web/vrs_desktop.html")
s = HTML.read_text(encoding="utf-8")

# ---------------------------------------------------------------------------
# Remove the floating Receiver / Range Rings map overlay.
# Keep the receiver controls in the right-side aircraft panel.
# ---------------------------------------------------------------------------

script_marker = '<script id="receiver-rings-overlay-v1">'

if script_marker in s:
    script_start = s.find(script_marker)
    script_end = s.find('</script>', script_start)

    if script_end < 0:
        raise SystemExit("Found receiver overlay script start, but not its closing </script>.")

    script_end += len('</script>')

    # The overlay CSS block was inserted immediately before its script.
    style_start = s.rfind('<style>', 0, script_start)
    style_end = s.find('</style>', style_start, script_start) if style_start >= 0 else -1

    if style_start >= 0 and style_end >= 0:
        style_text = s[style_start:style_end + len('</style>')]
        if '.rx-control' in style_text:
            s = s[:style_start] + s[script_end:]
        else:
            s = s[:script_start] + s[script_end:]
    else:
        s = s[:script_start] + s[script_end:]

    print("Removed floating map receiver/range-ring overlay.")
else:
    print("Floating map receiver overlay was already removed.")

# ---------------------------------------------------------------------------
# Change only the sidebar receiver ring styling.
# Preserve the yellow receiver-site marker.
# ---------------------------------------------------------------------------

ring_start = s.find('for (const ringNm of RANGE_RINGS_NM)')
if ring_start < 0:
    raise SystemExit("Could not find sidebar range-ring drawing block.")

ring_end = s.find('updateReceiverStatus();', ring_start)
if ring_end < 0:
    raise SystemExit("Could not determine end of sidebar range-ring drawing block.")

ring_block = s[ring_start:ring_end]

ring_block = ring_block.replace("color: '#ffdf4d'", "color: '#30343b'")
ring_block = ring_block.replace("weight: 1", "weight: 2")
ring_block = ring_block.replace("opacity: 0.50", "opacity: 0.88")
ring_block = ring_block.replace("dashArray: '5 7'", "dashArray: '7 6'")

s = s[:ring_start] + ring_block + s[ring_end:]

HTML.write_text(s, encoding="utf-8")

print("Updated sidebar receiver rings to dark gray.")
print("Receiver-site marker remains yellow.")
