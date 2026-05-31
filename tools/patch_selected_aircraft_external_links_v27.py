#!/usr/bin/env python3
"""
Add smart external aircraft/flight links to the selected-aircraft title.

Behavior:
- A registration-style Call value such as N123AB or C-FABC opens the
  FlightAware aircraft-registration page.
- A flight-callsign-style Call value such as SWA4331 opens the FlightAware
  live flight page, which may show origin, destination, times and aircraft type.
- An ICAO hex fallback is not linked.

This installer is safe to apply either before or after
patch_selected_aircraft_flightaware_link_v26.py.

Usage:
    python3 tools/patch_selected_aircraft_external_links_v27.py --check
    python3 tools/patch_selected_aircraft_external_links_v27.py --apply
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

MARKER_V27 = "/* selected-aircraft-external-links-v27 */"


def load_preserving_newline(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    return raw.decode("utf-8").replace("\r\n", "\n"), newline


def write_preserving_newline(path: Path, text: str, newline: str) -> None:
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def install_css(text: str, changes: list[str]) -> str:
    if MARKER_V27 in text:
        return text

    css_anchor = "/* coverage-summary-removed-v11 */"
    if css_anchor not in text:
        raise RuntimeError("Could not find CSS insertion anchor in web/vrs_desktop.html.")

    css = """/* selected-aircraft-external-links-v27 */
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
    changes.append("added smart selected-aircraft hyperlink styling")
    return text


def install_anchor_element(text: str, changes: list[str]) -> str:
    old_span = '<span id="selected-v2-call"></span>'
    linked_element = (
        '<a id="selected-v2-call" class="selected-tail-link" '
        'target="_blank" rel="noopener noreferrer"></a>'
    )

    if old_span in text:
        text = text.replace(old_span, linked_element, 1)
        changes.append("changed selected aircraft title to a safe new-tab link")
    elif linked_element not in text:
        raise RuntimeError("Could not find selected-aircraft title element.")

    return text


def smart_helper_block() -> str:
    return """  function registrationFromSelectedAircraft(aircraft) {
    const candidate = String((aircraft && aircraft.Call) || '')
      .trim()
      .toUpperCase()
      .replace(/\\s+/g, '');

    const usNNumber = /^N[1-9][0-9A-HJ-NP-Z]{0,4}$/.test(candidate);
    const hyphenatedRegistration = /^[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$/.test(candidate);

    return (usNNumber || hyphenatedRegistration) ? candidate : null;
  }

  function flightCallsignFromSelectedAircraft(aircraft) {
    const candidate = String((aircraft && aircraft.Call) || '')
      .trim()
      .toUpperCase()
      .replace(/\\s+/g, '');

    /*
     * Link a transmitted flight identification such as SWA4331, but do not
     * treat a missing callsign's ICAO hex fallback as a flight identifier.
     */
    const looksLikeFlightId =
      /^(?=.*[0-9])[A-Z0-9]{3,8}$/.test(candidate);

    return looksLikeFlightId ? candidate : null;
  }

  function updateAircraftLookupLink(aircraft) {
    const link = document.getElementById('selected-v2-call');
    const displayedValue = aircraft.Call || aircraft.Icao || String(aircraft.Id);
    const registration = registrationFromSelectedAircraft(aircraft);
    const flightCallsign = registration ? null : flightCallsignFromSelectedAircraft(aircraft);

    link.textContent = displayedValue;

    if (registration) {
      link.href =
        'https://www.flightaware.com/resources/registration/' +
        encodeURIComponent(registration);
      link.title =
        'Open aircraft details and photos for ' + registration +
        ' in a new browser tab';
      link.classList.add('active');
      return;
    }

    if (flightCallsign) {
      link.href =
        'https://www.flightaware.com/live/flight/' +
        encodeURIComponent(flightCallsign);
      link.title =
        'Open live flight information for ' + flightCallsign +
        ' in a new browser tab';
      link.classList.add('active');
      return;
    }

    link.removeAttribute('href');
    link.title =
      'No registration or flight callsign lookup is available for this aircraft';
    link.classList.remove('active');
  }

"""


def install_helpers(text: str, changes: list[str]) -> str:
    new_helpers = smart_helper_block()

    if "function updateAircraftLookupLink(aircraft)" in text:
        return text

    # Upgrade the v26 registration-only block when it has already been installed.
    v26_pattern = re.compile(
        r"  function registrationFromSelectedAircraft\(aircraft\) \{.*?"
        r"  function updateRegistrationLink\(aircraft\) \{.*?"
        r"  \}\n\n(?=  function install\(\) \{)",
        re.DOTALL,
    )
    if v26_pattern.search(text):
        text = v26_pattern.sub(lambda _match: new_helpers, text, count=1)
        changes.append("upgraded registration-only link logic to registration-or-flight lookup")
        return text

    anchor = "  function install() {\n"
    if anchor not in text:
        raise RuntimeError("Could not find selected-aircraft script helper insertion anchor.")

    text = text.replace(anchor, new_helpers + anchor, 1)
    changes.append("added registration and flight-callsign FlightAware lookup logic")
    return text


def install_render_call(text: str, changes: list[str]) -> str:
    original_render = """    document.getElementById('selected-v2-call').textContent =
      aircraft.Call || aircraft.Icao || String(aircraft.Id);

"""
    v26_render = """    updateRegistrationLink(aircraft);

"""
    new_render = """    updateAircraftLookupLink(aircraft);

"""

    if new_render in text:
        return text
    if v26_render in text:
        text = text.replace(v26_render, new_render, 1)
        changes.append("changed selected aircraft renderer to smart external lookup")
        return text
    if original_render in text:
        text = text.replace(original_render, new_render, 1)
        changes.append("enabled smart external lookup in selected aircraft renderer")
        return text

    raise RuntimeError("Could not find selected-aircraft title rendering anchor.")


def apply_html_change(text: str) -> tuple[str, list[str]]:
    changes: list[str] = []
    text = install_css(text, changes)
    text = install_anchor_element(text, changes)
    text = install_helpers(text, changes)
    text = install_render_call(text, changes)
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
        print("Already installed: selected aircraft external links v27.")
        return 0

    if args.check:
        print("CHECK PASS: current web/vrs_desktop.html matches the v27 patch anchors.")
        print("Would modify: web/vrs_desktop.html")
        for change in changes:
            print(f"  - {change}")
        return 0

    write_preserving_newline(html_path, updated, newline)
    print("Installed selected aircraft external links v27.")
    print("Modified: web/vrs_desktop.html")
    for change in changes:
        print(f"  - {change}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
