#!/usr/bin/env python3
"""
Lunar Window Finder - pipeline step 2b: scan the Artemis III regions.

A candidate region is roughly 20 x 20 km. Its centre can sit in shadow while a
ridge two kilometres away is lit most of the year. This step lays a grid over
every region outline, computes the terrain horizon and the 2027-2028 sunlight
at each grid point, and finds the best-lit spot of each region.

The Sun and Earth directions at a grid point come from the JPL Horizons track
of the region centre: the direction vector is turned from the centre's local
sky to the grid point's local sky. Both bodies are so far away that this is
exact to about 0.01 deg inside one region.

Run after fetch_horizons.py has the planning window of the region centres:
    python3 pipeline/region_scan.py
Results: data/regions/<site id>.json, and the best-lit spots are added to
sites.json (then run fetch_horizons.py, horizon.py, visibility.py again).

AI use: written during NASA Space Apps 2026 with help from an AI assistant
(Claude by Anthropic); every step was run and checked by the author.
"""

import json
import math
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform

from horizon import COARSE_MAP, MAX_DIST, MOON_LONLAT, horizon_profile, read_height_map
from visibility import EARTH_RADIUS, SUN_RADIUS, load_track, longest_run_hours, visible_share

TARGET_POINTS = 450           # grid points per region (the spacing is chosen to get about this many)
MIN_SPACING = 1000.0          # m
SCAN_AZ_STEP = 1.0            # deg between rays (coarser than the 0.5 deg used for the final sites)
SCAN_MASTS = (2.0, 10.0)

ROOT = Path(__file__).resolve().parents[1]
SITES_FILE = ROOT / "pipeline" / "sites.json"
REGIONS_DIR = ROOT / "data" / "regions"
OUTLINES_FILE = REGIONS_DIR / "outlines.json"


# ---------- map <-> lon/lat (through the projection of the height map) ----------
def map_crs():
    with rasterio.open(COARSE_MAP) as src:
        return src.crs


def to_map(crs, lons, lats):
    xs, ys = transform(MOON_LONLAT, crs, list(lons), list(lats))
    return np.array(xs), np.array(ys)


def to_lonlat(crs, xs, ys):
    lons, lats = transform(crs, MOON_LONLAT, list(xs), list(ys))
    return np.array(lons), np.array(lats)


# ---------- turning a sky direction from one site to another ----------
def sky_axes(lat, lon):
    """East, north and up unit vectors of a site, in Moon-fixed coordinates."""
    p, l = math.radians(lat), math.radians(lon)
    east = np.array([-math.sin(l), math.cos(l), 0.0])
    north = np.array([-math.sin(p) * math.cos(l), -math.sin(p) * math.sin(l), math.cos(p)])
    up = np.array([math.cos(p) * math.cos(l), math.cos(p) * math.sin(l), math.sin(p)])
    return east, north, up


def to_vectors(az, el, lat, lon):
    east, north, up = sky_axes(lat, lon)
    a, e = np.radians(az), np.radians(el)
    return (np.cos(e) * np.sin(a))[:, None] * east + (np.cos(e) * np.cos(a))[:, None] * north + np.sin(e)[:, None] * up


def to_az_el(vectors, lat, lon):
    east, north, up = sky_axes(lat, lon)
    el = np.degrees(np.arcsin(np.clip(vectors @ up, -1.0, 1.0)))
    az = np.degrees(np.arctan2(vectors @ east, vectors @ north)) % 360.0
    return az, el


def inside(px, py, rings):
    """Which points lie inside a polygon (even-odd rule), all on the map plane."""
    result = np.zeros(px.shape, dtype=bool)
    for rx, ry in rings:
        for k in range(len(rx)):
            x0, y0, x1, y1 = rx[k], ry[k], rx[(k + 1) % len(rx)], ry[(k + 1) % len(rx)]
            if y0 == y1:
                continue
            crosses = ((y0 > py) != (y1 > py)) & (px < (x1 - x0) * (py - y0) / (y1 - y0) + x0)
            result ^= crosses
    return result


def scan_region(key, info, crs):
    centre_id = info["site_id"]
    sun = load_track(centre_id, "plan", "sun")
    earth = load_track(centre_id, "plan", "earth")
    if sun is None or earth is None:
        print(f"  {info['name']}: no Horizons planning data for the centre yet, skipped")
        return None
    step_hours = float(np.median(np.diff(sun[0]))) / 60.0
    sun_vectors = to_vectors(sun[1], sun[2], info["lat"], info["lon"])
    earth_vectors = to_vectors(earth[1], earth[2], info["lat"], info["lon"])

    rings = [to_map(crs, [p[0] for p in ring], [p[1] for p in ring]) for ring in info["rings"]]
    all_x = np.concatenate([r[0] for r in rings])
    all_y = np.concatenate([r[1] for r in rings])
    cx, cy = (v[0] for v in to_map(crs, [info["lon"]], [info["lat"]]))
    spacing = max(MIN_SPACING, math.sqrt(info["area_km2"] * 1e6 / TARGET_POINTS))
    spacing = math.ceil(spacing / 250.0) * 250.0
    gx, gy = np.meshgrid(np.arange(all_x.min() + spacing / 2, all_x.max(), spacing),
                         np.arange(all_y.min() + spacing / 2, all_y.max(), spacing))
    keep = inside(gx.ravel(), gy.ravel(), rings)
    px, py = gx.ravel()[keep], gy.ravel()[keep]

    lons, lats = to_lonlat(crs, px, py)
    nx, ny = to_map(crs, lons, np.minimum(lats + 0.01, 89.99))
    ex, ey = to_map(crs, lons + 0.01, lats)
    reach = max(np.abs(all_x - cx).max(), np.abs(all_y - cy).max()) + MAX_DIST + 500
    height_map = read_height_map(COARSE_MAP, cx, cy, reach)

    rows = []
    for i in range(px.size):
        ground = float(height_map(np.array(px[i]), np.array(py[i])))
        if not math.isfinite(ground):
            continue
        north = np.array([nx[i] - px[i], ny[i] - py[i]])
        east = np.array([ex[i] - px[i], ey[i] - py[i]])
        north, east = north / np.linalg.norm(north), east / np.linalg.norm(east)
        az_grid, by_mast, _ = horizon_profile([(height_map, MAX_DIST)], px[i], py[i], ground, north, east,
                                              az_step=SCAN_AZ_STEP)
        sun_az, sun_el = to_az_el(sun_vectors, lats[i], lons[i])
        earth_az, earth_el = to_az_el(earth_vectors, lats[i], lons[i])
        row = [round((px[i] - cx) / 1000, 2), round((py[i] - cy) / 1000, 2),
               round(float(lats[i]), 4), round(float(lons[i]), 4), round(ground)]
        for mast in SCAN_MASTS:
            horizon = by_mast[mast][0]
            horizon = np.where(np.isfinite(horizon), horizon, 0.0)
            sun_share = visible_share(sun_az, sun_el, az_grid, horizon, SUN_RADIUS)
            earth_share = visible_share(earth_az, earth_el, az_grid, horizon, EARTH_RADIUS)
            row += [round(100 * float(sun_share.mean()), 1),
                    round(longest_run_hours(sun_share == 0, step_hours)),
                    round(100 * float((earth_share > 0).mean()), 1)]
        rows.append(row)

    columns = ["x_km", "y_km", "lat", "lon", "ground_m",
               "sun_2m", "dark_h_2m", "earth_2m", "sun_10m", "dark_h_10m", "earth_10m"]
    table = np.array(rows)
    best = rows[int(table[:, 5].argmax())]
    nearest = rows[int((table[:, 0] ** 2 + table[:, 1] ** 2).argmin())]
    pole = np.array([-cx, -cy]) / math.hypot(cx, cy)
    outline = [[[round((x - cx) / 1000, 2), round((y - cy) / 1000, 2)] for x, y in zip(*ring)] for ring in rings]
    return {"region": key, "name": info["name"], "site_id": centre_id, "spacing_m": spacing,
            "centre": {"lat": info["lat"], "lon": info["lon"]},
            "to_pole": [round(float(pole[0]), 3), round(float(pole[1]), 3)],
            "outline_km": outline, "columns": columns, "points": rows,
            "best": dict(zip(columns, best)), "centre_point": dict(zip(columns, nearest))}


def main():
    if not OUTLINES_FILE.exists():
        raise SystemExit("Run pipeline/artemis_regions.py first (it writes data/regions/outlines.json)")
    outlines = json.loads(OUTLINES_FILE.read_text(encoding="utf-8"))
    crs = map_crs()
    config = json.loads(SITES_FILE.read_text(encoding="utf-8"))

    print("Scanning the Artemis III regions (sunlight 2027-2028, 2 m panel):")
    print(f"  {'region':<22}{'points':>7}{'grid':>8}{'centre':>9}{'best':>8}{'move':>9}{'longest dark at best':>24}")
    started = time.time()
    for key, info in outlines.items():
        result = scan_region(key, info, crs)
        if result is None:
            continue
        (REGIONS_DIR / f"{info['site_id']}.json").write_text(json.dumps(result), encoding="utf-8")
        best, centre = result["best"], result["centre_point"]
        move = math.hypot(best["x_km"], best["y_km"])
        print(f"  {info['name']:<22}{len(result['points']):>7}{result['spacing_m'] / 1000:>6.2f} km"
              f"{centre['sun_2m']:>8.1f}%{best['sun_2m']:>7.1f}%{move:>6.1f} km"
              f"{best['dark_h_2m']:>12.0f} h ({best['dark_h_2m'] / 24:.1f} d)")

        best_site = {"id": info["site_id"] + "_best", "name": info["name"] + ", best-lit spot", "group": "artemis",
                     "region": key, "spot": "best", "lat": best["lat"], "lon": best["lon"], "terrain": True,
                     "windows": ["plan"],
                     "source": f"best-lit point of our {result['spacing_m'] / 1000:g} km scan of the USGS region outline"}
        config["sites"] = [s for s in config["sites"] if s["id"] != best_site["id"]]
        position = next((i for i, s in enumerate(config["sites"]) if s["id"] == info["site_id"]), -1)
        config["sites"].insert(position + 1, best_site)

    SITES_FILE.write_text(json.dumps(config, indent=1), encoding="utf-8")
    print(f"\nDone in {(time.time() - started) / 60:.1f} min. Best-lit spots were added to {SITES_FILE.name}.")


if __name__ == "__main__":
    main()
