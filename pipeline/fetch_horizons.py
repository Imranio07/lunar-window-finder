#!/usr/bin/env python3
"""
Lunar Window Finder - pipeline step 1.

Asks NASA JPL Horizons where the Sun and the Earth are in the sky
(azimuth and elevation) for every landing site listed in sites.json,
and saves each answer as a small CSV file in data/horizons/.

Run from the project folder:
    python3 pipeline/fetch_horizons.py                  # everything that is still missing
    python3 pipeline/fetch_horizons.py im2 apollo11     # only these sites

Files that already exist are skipped, so the script can be stopped
and started again at any time.

AI use: written during NASA Space Apps 2026 with help from an AI assistant
(Claude by Anthropic); every step was run and checked by the author.
"""

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
BODIES = {"sun": "10", "earth": "399"}      # Horizons numbers for the Sun and the Earth
MOON_SURFACE = "coord@301"                  # "a point on the surface of the Moon"
MONTHS = {name: number for number, name in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), start=1)}

ROOT = Path(__file__).resolve().parents[1]
SITES_FILE = ROOT / "pipeline" / "sites.json"
OUT_DIR = ROOT / "data" / "horizons"


def ask_horizons(body_id, site, window):
    """One request to Horizons. Returns the raw text of the answer."""
    params = {
        "format": "json",
        "COMMAND": f"'{body_id}'",
        "CENTER": f"'{MOON_SURFACE}'",
        "COORD_TYPE": "'GEODETIC'",
        "SITE_COORD": f"'{site['lon']},{site['lat']},0'",   # east longitude, latitude, height in km
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'OBSERVER'",
        "START_TIME": f"'{window['start']}'",
        "STOP_TIME": f"'{window['stop']}'",
        "STEP_SIZE": f"'{window['step']}'",
        "QUANTITIES": "'4'",                                # 4 = apparent azimuth and elevation
        "ANG_FORMAT": "'DEG'",
        "CSV_FORMAT": "'YES'",
    }
    problem = "no answer"
    for attempt in range(1, 5):
        try:
            response = requests.get(API_URL, params=params, timeout=600)
            response.raise_for_status()
            payload = response.json()
            text = payload.get("result", "")
            if "$$SOE" in text:
                return text
            problem = (payload.get("error") or text[-500:]).strip()
        except (requests.RequestException, ValueError) as error:
            problem = repr(error)
        print(f"    attempt {attempt} failed: {problem[:200]}")
        time.sleep(10 * attempt)
    raise RuntimeError(f"Horizons gave no data: {problem}")


def parse_table(text):
    """Turns the Horizons table into rows (time, azimuth, elevation)."""
    table = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    rows = []
    for line in table.strip().splitlines():
        cells = [cell.strip() for cell in line.split(",")]
        date_text, clock = cells[0].split()[:2]             # "2027-Jan-01" "00:00"
        year, month, day = date_text.split("-")
        stamp = f"{int(year):04d}-{MONTHS[month]:02d}-{int(day):02d}T{clock[:5]}"
        numbers = []
        for cell in cells[1:]:
            try:
                numbers.append(float(cell))
            except ValueError:
                continue                                    # empty flag columns
        if len(numbers) >= 2:
            rows.append((stamp, numbers[-2], numbers[-1]))  # azimuth, elevation
    return rows


def save_rows(path, rows):
    temporary = path.with_suffix(".part")
    with open(temporary, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_utc", "az_deg", "el_deg"])
        for stamp, az, el in rows:
            writer.writerow([stamp, f"{az:.4f}", f"{el:.4f}"])
    temporary.replace(path)


def load_rows(path):
    with open(path, newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        return [(datetime.fromisoformat(t), float(az), float(el)) for t, az, el in reader]


def elevation_at(rows, moment):
    """Elevation at an exact moment, by straight-line interpolation between two rows."""
    for (t0, _, el0), (t1, _, el1) in zip(rows, rows[1:]):
        if t0 <= moment <= t1:
            share = (moment - t0) / (t1 - t0)
            return el0 + (el1 - el0) * share
    return None


def main():
    config = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    wanted = set(sys.argv[1:])
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jobs = []
    for site in config["sites"]:
        if wanted and site["id"] not in wanted:
            continue
        for window_name in site.get("windows", []):
            jobs.append((site, window_name, config["windows"][window_name]))
        if "mission" in site:
            jobs.append((site, "mission", site["mission"]))
    jobs.sort(key=lambda job: job[1] == "validation")       # long validation requests go last

    total = len(jobs) * len(BODIES)
    done = 0
    started = time.time()
    for site, window_name, window in jobs:
        for body, body_id in BODIES.items():
            done += 1
            path = OUT_DIR / f"{site['id']}.{window_name}.{body}.csv"
            label = f"[{done}/{total}] {site['name']} / {window_name} / {body}"
            if path.exists():
                print(f"{label}: already saved")
                continue
            print(f"{label}: asking Horizons...")
            rows = parse_table(ask_horizons(body_id, site, window))
            save_rows(path, rows)
            elevations = [el for _, _, el in rows]
            print(f"    {len(rows)} rows, elevation from {min(elevations):.2f} to {max(elevations):.2f} deg")
            time.sleep(1)                                   # be polite to the NASA server

    print(f"\nDone in {(time.time() - started) / 60:.1f} min. Files are in {OUT_DIR}")

    print("\nSun and Earth at the moment of landing (flat horizon, no terrain yet):")
    for site in config["sites"]:
        mission = site.get("mission")
        sun_file = OUT_DIR / f"{site['id']}.mission.sun.csv"
        earth_file = OUT_DIR / f"{site['id']}.mission.earth.csv"
        if not mission or not sun_file.exists() or not earth_file.exists():
            continue
        moment = datetime.fromisoformat(mission["landing_utc"])
        sun = elevation_at(load_rows(sun_file), moment)
        earth = elevation_at(load_rows(earth_file), moment)
        if sun is None or earth is None:
            continue
        print(f"  {site['name']:<22} {mission['landing_utc']}  Sun {sun:6.2f} deg   Earth {earth:6.2f} deg")


if __name__ == "__main__":
    main()
