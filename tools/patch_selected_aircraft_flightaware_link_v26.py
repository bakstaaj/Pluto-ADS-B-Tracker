#!/usr/bin/env python3
"""
Add a FlightAware aircraft-registration hyperlink to the selected-aircraft panel.

The currently displayed ADS-B Call value is linked only when it looks like an
aircraft registration, such as a U.S. N-number or a hyphenated registration.
Airline flight callsigns and bare ICAO hex identifiers remain plain text.

Usage:
    python3 tools/patch_selected_aircraft_flightaware_link_v26.py --check
    python3 tools/patch_selected_aircraft_flightaware_link_v26.py --apply
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

MARKER = "/* selected-aircraft-flightaware-link-v26 */"


def load_preserving_newline(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), newline


def write_preserving_newline(path: Path, text: str, newline: str) -> None:
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def apply_html_change(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []

    if MARKER not in text:
        css_anchor = "/* coverage-summary-removed-v11 */"
        if css_anchor not in text:
            raise RuntimeError("Could not find CSS insertion anchor in web/vrs_desktop.html.")

        css = """/* selected-aircraft-flightaware-link-v26 */
#selected-aircraft-panel-v2 .selected-tail-link.active {
  color: #80c8ff;
  text-decoration: underline;
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
  cursor: pointer;
}
#selected-aircraft-panel-v2 .selected-tail-link.active:hover {
  color: #b5e0ff;
}

"""
        text = text.replace(css_anchor, css + css_anchor, 1)
        changes.append("added selected-aircraft link styling")

    old_title = '<span id="selected-v2-call"></span>'
    new_title = (
        '<a id="selected-v2-call" class="selected-tail-link" '
        'target="_blank" rel="noopener noreferrer"></a>'
    )
    if old_title in text:
        text = text.replace(old_title, new_title, 1)
        changes.append("changed selected title element to a safe new-tab link")
    elif new_title not in text:
        raise RuntimeError("Could not find selected-aircraft title element.")

    helper_anchor = """  function install() {
"""
    if "function registrationFromSelectedAircraft" not in text:
        helpers = """  function registrationFromSelectedAircraft(aircraft) {
    const candidate = String((aircraft && aircraft.Call) || '')
      .trim()
      .toUpperCase()
      .replace(/\\s+/g, '');

    /*
     * The VRS-compatible feed currently exposes ADS-B callsign and ICAO hex,
     * not a separate registration database field. Link only values that look
     * like tail/registration numbers; do not mis-label airline flight IDs.
     */
    const usNNumber = /^N[1-9][0-9A-HJ-NP-Z]{0,4}$/.test(candidate);
    const hyphenatedRegistration = /^[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$/.test(candidate);

    return (usNNumber || hyphenatedRegistration) ? candidate : null;
  }

  function updateRegistrationLink(aircraft) {
    const link = document.getElementById('selected-v2-call');
    const displayedValue = aircraft.Call || aircraft.Icao || String(aircraft.Id);
    const registration = registrationFromSelectedAircraft(aircraft);

    link.textContent = displayedValue;

    if (registration) {
      link.href =
        'https://www.flightaware.com/resources/registration/' +
        encodeURIComponent(registration);
      link.title =
        'Open aircraft details and photos for ' + registration +
        ' in a new browser tab';
      link.classList.add('active');
    } else {
      link.removeAttribute('href');
      link.title =
        'Registration lookup is available when the ADS-B callsign is a tail number';
      link.classList.remove('active');
    }
  }

"""
        if helper_anchor not in text:
            raise RuntimeError("Could not find selected-aircraft script helper insertion anchor.")
        text = text.replace(helper_anchor, helpers + helper_anchor, 1)
        changes.append("added registration detection and FlightAware URL helper")

    old_render = """    document.getElementById('selected-v2-call').textContent =
      aircraft.Call || aircraft.Icao || String(aircraft.Id);

"""
    new_render = """    updateRegistrationLink(aircraft);

"""
    if old_render in text:
        text = text.replace(old_render, new_render, 1)
        changes.append("enabled link rendering for selected aircraft")
    elif new_render not in text:
        raise RuntimeError("Could not find selected-aircraft call rendering anchor.")

    return text, changes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write the HTML modification.")
    parser.add_argument("--check", action="store_true", help="Validate anchors without writing.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root.")
    args = parser.parse_args()

    if args.apply == args.check:
        parser.error("Choose exactly one of --check or --apply.")

    html_path = args.repo / "web" / "vrs_desktop.html"
    if not html_path.exists():
        print(f"ERROR: File not found: {html_path}", file=sys.stderr)
        return 1

    original, newline = load_preserving_newline(html_path)
    try:
        updated, changes = apply_html_change(original)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if not changes and updated == original:
        print("Already installed: selected aircraft FlightAware registration link v26.")
        return 0

    if args.check:
        print("CHECK PASS: current web/vrs_desktop.html matches the v26 patch anchors.")
        print("Would modify: web/vrs_desktop.html")
        for change in changes:
            print(f"  - {change}")
        return 0

    write_preserving_newline(html_path, updated, newline)
    print("Installed selected-aircraft FlightAware registration link v26.")
    print("Modified: web/vrs_desktop.html")
    for change in changes:
        print(f"  - {change}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
