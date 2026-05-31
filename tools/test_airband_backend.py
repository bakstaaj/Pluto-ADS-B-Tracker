#!/usr/bin/env python3
from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path

BASE = "http://192.168.2.1:8080"
DATA = Path("data/airband_frequencies.json")
OUT = Path("test_output/direct_airband_test.wav")


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def get_bytes(path: str) -> bytes:
    with urllib.request.urlopen(BASE + path, timeout=10) as response:
        return response.read()


def choose_test_channel() -> dict:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    channels = data["channels"]

    # Prefer a KCOS Tower/CTAF/Approach frequency for local testing.
    for keywords in (("TOWER", "CTAF"), ("APPROACH", "APCH", "DEPARTURE"), ()):
        for channel in channels:
            if channel.get("airport_code") != "KCOS":
                continue
            use = str(channel.get("use", "")).upper()
            if not keywords or any(word in use for word in keywords):
                return channel

    return channels[0]


def main() -> int:
    channel = choose_test_channel()
    frequency_hz = int(channel["frequency_hz"])

    print("Selected test channel:")
    print(
        f"  {channel.get('airport_code', '')} "
        f"{channel['frequency_mhz']:.3f} MHz "
        f"{channel.get('use', '')}"
    )
    print()

    initial = get_json("/VirtualRadar/Airband/Status.json")
    print("Initial backend status:")
    print(json.dumps(initial, indent=2))
    print()

    if "pcm_total" not in initial:
        print("FAIL: Running Pluto binary does not include the sequential-audio backend.")
        print("Rebuild, deploy, stop the old process, and restart the tracker.")
        return 1

    try:
        print("Requesting airband mode...")
        start = get_json(
            f"/VirtualRadar/Airband/Start.json?freq={frequency_hz}&_={int(time.time())}"
        )
        print(json.dumps(start, indent=2))
        print()

        time.sleep(2)

        first = get_json("/VirtualRadar/Airband/Status.json")
        print("Status after 2 seconds:")
        print(json.dumps(first, indent=2))
        print()

        if first.get("error"):
            print("FAIL: Backend reported a tuning error:", first["error"])
            return 1

        if not first.get("active"):
            print("FAIL: Airband mode did not become active.")
            print("The reader thread may not be applying the pending tune request.")
            return 1

        a = int(first.get("pcm_total", 0))

        time.sleep(5)

        second = get_json("/VirtualRadar/Airband/Status.json")
        print("Status after 7 seconds:")
        print(json.dumps(second, indent=2))
        print()

        b = int(second.get("pcm_total", 0))
        produced = b - a

        print("PCM production over 5 seconds:")
        print(f"  Start cursor: {a}")
        print(f"  End cursor:   {b}")
        print(f"  Samples:      {produced}")
        print(f"  Rate:         {produced / 5:.1f} samples/sec")
        print("  Expected:     approximately 16000 samples/sec")
        print()

        if produced <= 0:
            print("FAIL: Airband mode is active but no PCM samples are being generated.")
            return 1

        start_cursor = max(0, b - 32000)
        wav = get_bytes(
            f"/VirtualRadar/Airband/Audio.wav?from={start_cursor}&samples=32000"
        )

        OUT.write_bytes(wav)

        print("Two-second WAV block:")
        print(f"  Bytes:        {len(wav)}")
        print(f"  Expected:     64044")
        print(f"  Saved:        {OUT}")
        print()

        if len(wav) != 64044:
            print("FAIL: Backend did not return a full two-second WAV block.")
            return 1

        print("PASS: Pluto backend is tuning and producing sequential audio.")
        return 0

    finally:
        print()
        print("Returning Pluto to ADS-B mode...")
        try:
            stopped = get_json("/VirtualRadar/Airband/Stop.json")
            print(json.dumps(stopped, indent=2))
        except Exception as error:
            print("Unable to send stop request:", error)


if __name__ == "__main__":
    raise SystemExit(main())
