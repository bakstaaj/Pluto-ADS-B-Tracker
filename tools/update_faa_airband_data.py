#!/usr/bin/env python3
"""
Create a compact airband-frequency database from the FAA NASR FRQ CSV group.

Default data cycle:
    FAA NASR subscription effective 2026-05-14

Output:
    data/airband_frequencies.json

This is host-side only; it does not run on the Pluto+.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "airband_frequencies.json"


def faa_url_for_cycle(cycle: str) -> str:
    date = datetime.strptime(cycle, "%Y-%m-%d")
    filename = f"{date.day:02d}_{date.strftime('%B')}_{date.year}_FRQ_CSV.zip"
    return (
        "https://nfdc.faa.gov/webContent/28DaySub/extra/"
        + filename
    )


def norm(value: str | None) -> str:
    return (value or "").strip()


def pick(row: dict[str, str], *names: str) -> str:
    upper = {str(k).strip().upper(): v for k, v in row.items()}
    for name in names:
        value = norm(upper.get(name.upper()))
        if value:
            return value
    return ""


def parse_float(value: str) -> float | None:
    try:
        return float(value.strip())
    except (TypeError, ValueError, AttributeError):
        return None


def parse_frequency(value: str) -> float | None:
    match = re.search(r"\d{3}(?:\.\d+)?", value or "")
    if not match:
        return None

    try:
        result = float(match.group(0))
    except ValueError:
        return None

    if 118.000 <= result <= 136.975:
        return round(result, 3)

    return None


def locate_frq_csv(archive: zipfile.ZipFile) -> str:
    candidates = [
        name for name in archive.namelist()
        if Path(name).name.upper() == "FRQ.CSV"
    ]

    if not candidates:
        raise RuntimeError(
            "FRQ.csv was not found in the FAA ZIP. Files include:\n"
            + "\n".join(archive.namelist()[:30])
        )

    return candidates[0]


def download_zip(url: str) -> bytes:
    print(f"Downloading FAA FRQ data:\n  {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Pluto-ADS-B-Tracker/0.1"}
    )

    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def channel_priority(use_text: str) -> int:
    text = use_text.upper()

    if any(term in text for term in ("TOWER", "CTAF", "UNICOM")):
        return 1
    if any(term in text for term in ("APP", "APCH", "APPROACH", "DEP", "DEPARTURE")):
        return 2
    if "GROUND" in text:
        return 3
    if any(term in text for term in ("ATIS", "AWOS", "ASOS")):
        return 4
    return 5


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cycle",
        default="2026-05-14",
        help="FAA NASR effective date in YYYY-MM-DD format; default: 2026-05-14",
    )
    parser.add_argument(
        "--url",
        default="",
        help="Override the FAA FRQ ZIP URL.",
    )
    parser.add_argument(
        "--zip-file",
        type=Path,
        help="Use a previously downloaded FRQ ZIP instead of downloading.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path; default: {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    source_url = args.url or faa_url_for_cycle(args.cycle)

    if args.zip_file:
        zip_bytes = args.zip_file.read_bytes()
        source_label = str(args.zip_file)
    else:
        zip_bytes = download_zip(source_url)
        source_label = source_url

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        frq_name = locate_frq_csv(archive)
        print(f"Reading: {frq_name}")

        raw = archive.read(frq_name).decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(raw))

        channels: list[dict[str, object]] = []
        seen: set[tuple[object, ...]] = set()

        for row in reader:
            frequency = parse_frequency(pick(row, "FREQ", "FREQUENCY"))
            latitude = parse_float(pick(row, "LAT_DECIMAL", "LATITUDE_DECIMAL", "LATITUDE"))
            longitude = parse_float(pick(row, "LONG_DECIMAL", "LONGITUDE_DECIMAL", "LONGITUDE"))

            if frequency is None or latitude is None or longitude is None:
                continue

            use = pick(row, "FREQ_USE", "SERVICE", "FACILITY_TYPE") or "Published Frequency"
            facility_id = pick(row, "SERVICED_FACILITY", "FACILITY_ID", "FACILITY")
            facility_name = pick(row, "SERVICED_FAC_NAME", "FACILITY_NAME", "FAC_NAME")
            city = pick(row, "SERVICED_CITY", "CITY")
            state = pick(row, "SERVICED_STATE", "STATE_CODE")
            facility_type = pick(row, "FACILITY_TYPE")
            tower_call = pick(row, "TOWER_OR_COMM_CALL", "PRIMARY_APCH_RADIO_CALL")

            key = (
                frequency,
                round(latitude, 6),
                round(longitude, 6),
                facility_id,
                use,
            )

            if key in seen:
                continue

            seen.add(key)

            channels.append(
                {
                    "frequency_mhz": frequency,
                    "frequency_hz": int(round(frequency * 1_000_000)),
                    "use": use,
                    "priority": channel_priority(use),
                    "facility_id": facility_id,
                    "facility_name": facility_name,
                    "facility_type": facility_type,
                    "call": tower_call,
                    "city": city,
                    "state": state,
                    "lat": round(latitude, 6),
                    "lon": round(longitude, 6),
                }
            )

    channels.sort(
        key=lambda item: (
            item["state"],
            item["facility_id"],
            item["priority"],
            item["frequency_mhz"],
        )
    )

    output = {
        "metadata": {
            "source": "FAA 28 Day NASR Subscription - FRQ CSV",
            "effective_date": args.cycle,
            "source_url": source_label,
            "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "airband_min_mhz": 118.000,
            "airband_max_mhz": 136.975,
            "record_count": len(channels),
        },
        "channels": channels,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, separators=(",", ":")),
        encoding="utf-8",
    )

    size_kb = args.output.stat().st_size / 1024
    print(f"Wrote: {args.output}")
    print(f"Channels: {len(channels)}")
    print(f"Size: {size_kb:.1f} KB")

    if not channels:
        print("No channels were produced. Verify the FAA CSV column names.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
