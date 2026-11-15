#!/usr/bin/env python3
"""
Lunar Window Finder - pipeline step 2c: ground slope for landing safety.

Sunlight is not enough: a lander also needs gentle ground. IM-2 Athena (March
2025) came down on a slope inside a crater and tipped over. This step measures
the ground slope from the NASA LOLA 80 m height map:

  * at every site that has terrain (the listed polar sites), and
  * at every grid point of the Artemis III region scans (data/regions/a3_*.json),
    where a "slope_deg" column is added.

Slope = steepest tilt of the ground, from the height difference between points
80 m on either side (central differences over a 160 m baseline).

Limit stated openly: an 80 m map smooths small bumps, so real slopes at the
size of a lander (a few metres) can be steeper. This is a first screening;
certifying a landing spot needs 5 m maps. NASA's crew lander requirement used
in site studies is a slope below 5 degrees (arXiv:2406.19863, citing the HLS
requirements).

Run from the project folder, after region_scan.py:
    python3 pipeline/slope.py
Writes data/terrain/slopes.json and updates data/regions/a3_*.json.

AI use: written during NASA Space Apps 2026 with help from an AI assistant
(Claude by Anthropic); every step was run and checked by the author.
"""

import json
import math
from pathlib import Path

import numpy as np
import rasterio

from horizon import COARSE_MAP, local_directions, map_xy, read_height_map

STEP = 80.0                                   # m, half of the baseline (one pixel of the 80 m map)

ROOT = Path(__file__).resolve().parents[1]
SITES_FILE = ROOT / "pipeline" / "sites.json"
REGIONS_DIR = ROOT / "data" / "regions"
SLOPES_FILE = ROOT / "data" / "terrain" / "slopes.json"


def slope_at(height_map, x, y, north, east):
    """Slope in degrees at map point (x, y): central differences along local east and north."""
    def h(dx, dy):
        return float(height_map(np.array(x + dx), np.array(y + dy)))
    e = h(east[0] * STEP, east[1] * STEP) - h(-east[0] * STEP, -east[1] * STEP)
    n = h(north[0] * STEP, north[1] * STEP) - h(-north[0] * STEP, -north[1] * STEP)
    if not (math.isfinite(e) and math.isfinite(n)):
        return None
    return math.degrees(math.atan(math.hypot(e, n) / (2 * STEP)))


def main():
    with rasterio.open(COARSE_MAP) as src:
        crs = src.crs
    config = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    SLOPES_FILE.parent.mkdir(parents=True, exist_ok=True)

    # ---- listed sites ----
    slopes = {}
    print("Ground slope at the listed polar sites (80 m map, 160 m baseline):")
    for site in config["sites"]:
        if not site.get("terrain") or site.get("group") == "validation":
            continue
        x, y = map_xy(crs, site["lat"], site["lon"])
        north, east = local_directions(crs, site["lat"], site["lon"], x, y)
        height_map = read_height_map(COARSE_MAP, x, y, 2000)
        value = slope_at(height_map, x, y, north, east)
        if value is None:
            print(f"  {site['name']:<38} outside the map")
            continue
        slopes[site["id"]] = round(value, 2)
        print(f"  {site['name']:<38} {value:5.1f} deg")
    SLOPES_FILE.write_text(json.dumps(slopes, indent=1), encoding="utf-8")

    # ---- region scan points ----
    print("\nArtemis III regions: share of scan points by slope (80 m map):")
    print(f"  {'region':<22}{'<5 deg':>9}{'<10 deg':>9}{'<15 deg':>9}{'median':>9}   best-lit spot with slope < 5 deg")
    for path in sorted(REGIONS_DIR.glob("a3_*.json")):
        region = json.loads(path.read_text(encoding="utf-8"))
        cols = region["columns"]
        ix, iy, ilat, ilon = (cols.index(c) for c in ("x_km", "y_km", "lat", "lon"))
        cx, cy = map_xy(crs, region["centre"]["lat"], region["centre"]["lon"])
        reach = max(max(abs(p[ix]), abs(p[iy])) for p in region["points"]) * 1000 + 2000
        height_map = read_height_map(COARSE_MAP, cx, cy, reach)
        if "slope_deg" in cols:                                   # running again: replace the old values
            k = cols.index("slope_deg")
            for p in region["points"]:
                del p[k]
            cols.pop(k)
        values = []
        for p in region["points"]:
            x, y = cx + p[ix] * 1000, cy + p[iy] * 1000
            north, east = local_directions(crs, p[ilat], p[ilon], x, y)
            value = slope_at(height_map, x, y, north, east)
            p.append(None if value is None else round(value, 2))
            values.append(np.nan if value is None else value)
        cols.append("slope_deg")
        path.write_text(json.dumps(region), encoding="utf-8")

        v = np.array(values)
        known = np.isfinite(v)
        share = lambda limit: 100 * float((v[known] < limit).mean()) if known.any() else float("nan")
        isun = cols.index("sun_2m")
        safe = [p for p, s in zip(region["points"], v) if np.isfinite(s) and s < 5]
        best_safe = max(safe, key=lambda p: p[isun]) if safe else None
        best_text = (f"{best_safe[isun]:.0f}% sunlight, {math.hypot(best_safe[ix], best_safe[iy]):.1f} km from centre"
                     if best_safe else "none")
        print(f"  {region['name']:<22}{share(5):>8.0f}%{share(10):>8.0f}%{share(15):>8.0f}%"
              f"{np.nanmedian(v):>8.1f}°   {best_text}")

    print(f"\nSaved {SLOPES_FILE} and slope columns in {REGIONS_DIR}")


if __name__ == "__main__":
    main()
