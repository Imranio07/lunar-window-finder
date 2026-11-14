#!/usr/bin/env python3
"""
Lunar Window Finder - pipeline step 4: pack the data for the website.

  docs/data/index.json     every site: terrain horizon, scores, real-mission facts,
                           hourly share of Sun and Earth in view (feeds the calendar),
                           and the results of the checks
  docs/data/sky/<id>.json  hourly Sun and Earth positions for one site
                           (the page loads it when the site is picked)

Numbers are packed as base64 byte arrays to keep the files small.

Run from the project folder, after visibility.py:
    python3 pipeline/export_web.py

AI use: written during NASA Space Apps 2026 with help from an AI assistant
(Claude by Anthropic); every step was run and checked by the author.
"""

import base64
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from visibility import (EARTH_RADIUS, MASTS, RESULTS_DIR, SITES_FILE, SUN_RADIUS, TERRAIN_DIR,
                        eclipse_factor, load_horizon, load_track, visible_share)

ROOT = Path(__file__).resolve().parents[1]
WEB_DATA = ROOT / "docs" / "data"          # GitHub Pages serves the docs/ folder
REGIONS_DIR = ROOT / "data" / "regions"


def pack(values, dtype):
    return base64.b64encode(np.asarray(values).astype(dtype).tobytes()).decode("ascii")


def share_bytes(share):
    """0..1 -> 0..255, keeping 'any light at all' as at least 1."""
    scaled = np.round(share * 255).astype(int)
    scaled[(share > 0) & (scaled == 0)] = 1
    return pack(scaled, "<u1")


def window_block(site_id, window):
    sun = load_track(site_id, window, "sun")
    earth = load_track(site_id, window, "earth")
    if sun is None or earth is None:
        return None, None
    minutes, sun_az, sun_el = sun
    earth_minutes, earth_az, earth_el = earth
    if len(minutes) != len(earth_minutes):
        print(f"  {site_id}/{window}: Sun and Earth files have different lengths, skipped")
        return None, None
    step = int(np.median(np.diff(minutes)))
    block = {
        "start": str(np.datetime64(int(minutes[0]), "m")),
        "step_min": step,
        "n": int(len(minutes)),
        "sun_az": pack(np.round(sun_az * 100), "<u2"),        # centi-degrees
        "sun_el": pack(np.round(sun_el * 100), "<i2"),
        "earth_az": pack(np.round(earth_az * 100), "<u2"),
        "earth_el": pack(np.round(earth_el * 100), "<i2"),
    }
    return block, (sun_az, sun_el, earth_az, earth_el)


def main():
    config = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    (WEB_DATA / "sky").mkdir(parents=True, exist_ok=True)

    index = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "sun_radius": SUN_RADIUS, "earth_radius": EARTH_RADIUS, "masts": list(MASTS),
             "plan": None, "sites": []}

    for site in config["sites"]:
        if site.get("group") == "validation":
            continue
        results_file = RESULTS_DIR / f"{site['id']}.json"
        if not results_file.exists():
            print(f"  {site['name']}: no results yet, run visibility.py first")
            continue
        results = json.loads(results_file.read_text(encoding="utf-8"))

        sky = {}
        entry = {key: site[key] for key in ("id", "name", "group", "lat", "lon")}
        entry["source"] = site.get("source", "")
        entry["region"] = site.get("region")
        entry["spot"] = site.get("spot")
        entry["horizon_source"] = results.get("horizon_source")
        terrain_file = TERRAIN_DIR / f"{site['id']}.json"
        if terrain_file.exists():
            terrain = json.loads(terrain_file.read_text(encoding="utf-8"))
            entry["ground_m"] = terrain["ground_m"]
            entry["maps"] = terrain["maps"]
            entry["blocker_km"] = {m: terrain["masts"][m]["blocker_km"] for m in MASTS}
        entry["horizon"] = {}
        horizons = {}
        for mast in MASTS:
            az_grid, horizon, _ = load_horizon(site["id"], mast)
            horizons[mast] = (az_grid, horizon)
            entry["horizon"][mast] = [round(float(v), 2) for v in horizon]
        entry["az_step"] = float(horizons[MASTS[0]][0][1] - horizons[MASTS[0]][0][0])

        plan_block, plan_tracks = window_block(site["id"], "plan")
        if plan_block:
            sky["plan"] = plan_block
            meta = {k: plan_block[k] for k in ("start", "step_min", "n")}
            if index["plan"] is None:
                index["plan"] = meta
            elif index["plan"] != meta:
                print(f"  {site['name']}: planning window differs from the other sites, skipped")
                continue
            sun_az, sun_el, earth_az, earth_el = plan_tracks
            eclipse = eclipse_factor(sun_az, sun_el, earth_az, earth_el)
            entry["shares"] = {}
            for mast in MASTS:
                az_grid, horizon = horizons[mast]
                entry["shares"][f"sun{mast}"] = share_bytes(
                    visible_share(sun_az, sun_el, az_grid, horizon, SUN_RADIUS) * eclipse)
                entry["shares"][f"earth{mast}"] = share_bytes(
                    visible_share(earth_az, earth_el, az_grid, horizon, EARTH_RADIUS))
            entry["scores"] = results["windows"]["plan"]["masts"]
            entry["eclipses"] = results["windows"]["plan"].get("eclipses", [])

        mission_block, _ = window_block(site["id"], "mission")
        if mission_block:
            sky["mission"] = mission_block
            entry["landing"] = results["windows"]["mission"].get("landing")
            entry["mission_scores"] = results["windows"]["mission"]["masts"]
            entry["mission_eclipses"] = results["windows"]["mission"].get("eclipses", [])

        if not sky:
            print(f"  {site['name']}: no Horizons data yet")
            continue
        (WEB_DATA / "sky" / f"{site['id']}.json").write_text(json.dumps(sky), encoding="utf-8")
        index["sites"].append(entry)

    index["regions"] = {}
    for region_file in sorted(REGIONS_DIR.glob("a3_*.json")):
        region = json.loads(region_file.read_text(encoding="utf-8"))
        index["regions"][region["region"]] = region

    validation_file = RESULTS_DIR / "validation.json"
    if validation_file.exists():
        index["validation"] = json.loads(validation_file.read_text(encoding="utf-8"))

    (WEB_DATA / "index.json").write_text(json.dumps(index), encoding="utf-8")
    size = (WEB_DATA / "index.json").stat().st_size / 1e6
    print(f"Exported {len(index['sites'])} sites to {WEB_DATA} (index.json {size:.1f} MB)")


if __name__ == "__main__":
    main()
