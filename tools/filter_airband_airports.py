#!/usr/bin/env python3
"""
Filter the full FAA-derived airband database into a compact Pluto deployment file.

Default deployed airports:
    KCOS - Colorado Springs Airport
    KPHX - Phoenix Sky Harbor International Airport
    KDEN - Denver International Airport / DIA
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INPUT = ROOT / "data" / "airband_frequencies_full.json"
DEFAULT_OUTPUT = ROOT / "data" / "airband_frequencies.json"

AIRPORTS = {
    "KCOS": {
        "display_name": "Colorado Springs Airport",
        "identifiers": ["KCOS", "COS"],
        "names": ["COLORADO SPRINGS"],
    },
    "KPHX": {
        "display_name": "Phoenix Sky Harbor International Airport",
        "identifiers": ["KPHX", "PHX"],
        "names": ["PHOENIX SKY HARBOR", "SKY HARBOR"],
    },
    "KDEN": {
        "display_name": "Denver International Airport (DIA)",
        "identifiers": ["KDEN", "DEN"],
        "names": ["DENVER INTERNATIONAL", "DENVER INTL"],
    },
}


def normalize(value: object) -> str:
    return str(value or "").upper().strip()


def channel_text(channel: dict[str, object]) -> str:
    fields = [
        channel.get("facility_id"),
        channel.get("facility_name"),
        channel.get("facility_type"),
        channel.get("call"),
        channel.get("city"),
        channel.get("state"),
        channel.get("use"),
    ]
    return " | ".join(normalize(value) for value in fields)


def matches_airport(channel: dict[str, object], airport_code: str) -> bool:
    definition = AIRPORTS[airport_code]

    facility_id = normalize(channel.get("facility_id"))
    text = channel_text(channel)

    for ident in definition["identifiers"]:
        if facility_id == ident:
            return True

    for name in definition["names"]:
        if name in text:
            return True

    return False


def dedupe_key(channel: dict[str, object]) -> tuple[object, ...]:
    return (
        channel.get("frequency_hz"),
        channel.get("use"),
        channel.get("facility_id"),
        channel.get("lat"),
        channel.get("lon"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--airports",
        nargs="+",
        default=["KCOS", "KPHX", "KDEN"],
        choices=sorted(AIRPORTS),
    )
    args = parser.parse_args()

    source = json.loads(args.input.read_text(encoding="utf-8"))
    source_channels = source.get("channels", [])

    selected: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    counts: dict[str, int] = {}

    for airport_code in args.airports:
        airport_channels: list[dict[str, object]] = []

        for channel in source_channels:
            if not matches_airport(channel, airport_code):
                continue

            key = dedupe_key(channel)
            if key in seen:
                continue

            copied = dict(channel)
            copied["airport_code"] = airport_code
            copied["airport_name"] = AIRPORTS[airport_code]["display_name"]

            seen.add(key)
            airport_channels.append(copied)
            selected.append(copied)

        counts[airport_code] = len(airport_channels)

    missing = [code for code, count in counts.items() if count == 0]
    if missing:
        print("No matching frequency records found for:", ", ".join(missing))
        print("Available likely identifiers in source:")
        identifiers = sorted({
            normalize(channel.get("facility_id"))
            for channel in source_channels
            if channel.get("facility_id")
        })
        print(", ".join(identifiers[:80]))
        return 1

    selected.sort(
        key=lambda channel: (
            channel["airport_code"],
            int(channel.get("priority", 9)),
            float(channel.get("frequency_mhz", 0)),
        )
    )

    output = {
        "metadata": {
            **source.get("metadata", {}),
            "filtered": True,
            "airports": args.airports,
            "airport_names": {
                code: AIRPORTS[code]["display_name"]
                for code in args.airports
            },
            "source_record_count": len(source_channels),
            "record_count": len(selected),
        },
        "channels": selected,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, separators=(",", ":")),
        encoding="utf-8",
    )

    print("Compact Pluto airband database created:")
    print(f"  Output: {args.output}")
    print(f"  Size:   {args.output.stat().st_size:,} bytes")
    print()
    for airport_code in args.airports:
        print(
            f"  {airport_code}: {counts[airport_code]} frequencies - "
            f"{AIRPORTS[airport_code]['display_name']}"
        )
    print()
    print(f"  Total deployed frequencies: {len(selected)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
