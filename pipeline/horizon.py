#!/usr/bin/env python3
"""
Lunar Window Finder - pipeline step 2: the terrain horizon.

For every site marked "terrain": true in sites.json, walks 720 rays
(one every 0.5 deg of azimuth) across the NASA LOLA height map and finds
how high the mountains rise above the flat horizon in each direction.
The Moon has no air, so there is no refraction: the horizon is just the
terrain plus the curve of the lunar sphere.

The horizon is computed for two heights of the solar panel / antenna
above the ground: a 2 m lander deck and a 10 m mast (like NASA's VSAT
vertical solar array concept).

Run from the project folder:
    python3 pipeline/horizon.py              # all terrain sites, 80 m map
    python3 pipeline/horizon.py im2 v01      # only these sites
    python3 pipeline/horizon.py --fine data/nasa/LDEM_80S_20MPP_ADJ.TIF
        # 20 m map for the first 30 km around each site, 80 m map beyond

Results go to data/terrain/<site id>.json

AI use: written during NASA Space Apps 2026 with help from an AI assistant
(Claude by Anthropic); every step was run and checked by the author.
"""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window, from_bounds

MOON_RADIUS = 1_737_400.0                        # m, the sphere the LOLA heights refer to
MOON_LONLAT = "+proj=longlat +R=1737400 +no_defs"
AZ_STEP = 0.5                                    # deg between rays
MAX_DIST = 150_000.0                             # m, how far each ray looks
FINE_DIST = 30_000.0                             # m, where the 20 m map hands over to the 80 m map
MASTS = (0.0, 2.0, 10.0)                         # m above the ground (0 = surface, used for the NASA check)

ROOT = Path(__file__).resolve().parents[1]
SITES_FILE = ROOT / "pipeline" / "sites.json"
COARSE_MAP = ROOT / "data" / "nasa" / "LDEM_80S_80MPP_ADJ.TIF"
OUT_DIR = ROOT / "data" / "terrain"


class HeightMap:
    """A square piece of a height map with smooth (bilinear) height lookup."""

    def __init__(self, heights, left, top, pixel, name):
        self.heights = heights                   # 2-D array of heights in m, NaN where unknown
        self.left, self.top = left, top          # map coordinates of the top-left corner, m
        self.pixel = pixel                       # pixel size, m
        self.name = name

    def __call__(self, x, y):
        """Height at map points (x, y); NaN outside this piece."""
        n_rows, n_cols = self.heights.shape
        col = (x - self.left) / self.pixel - 0.5          # 0.5: values sit at pixel centres
        row = (self.top - y) / self.pixel - 0.5
        inside = (col >= 0) & (col <= n_cols - 1) & (row >= 0) & (row <= n_rows - 1)
        c0 = np.clip(np.floor(col).astype(int), 0, n_cols - 2)
        r0 = np.clip(np.floor(row).astype(int), 0, n_rows - 2)
        fc, fr = col - c0, row - r0
        h = self.heights
        upper = h[r0, c0] * (1 - fc) + h[r0, c0 + 1] * fc
        lower = h[r0 + 1, c0] * (1 - fc) + h[r0 + 1, c0 + 1] * fc
        return np.where(inside, upper * (1 - fr) + lower * fr, np.nan)


def read_height_map(path, x, y, half_size):
    """Reads only the square of +-half_size metres around (x, y) from a big GeoTIFF."""
    with rasterio.open(path) as src:
        whole = Window(0, 0, src.width, src.height)
        window = from_bounds(x - half_size, y - half_size, x + half_size, y + half_size, src.transform)
        window = window.round_offsets().round_lengths().intersection(whole)
        heights = src.read(1, window=window, masked=True).astype("float64").filled(np.nan)
        corner = src.window_transform(window)
    return HeightMap(heights, corner.c, corner.f, corner.a, Path(path).name)


def map_xy(crs, lat, lon):
    xs, ys = transform(MOON_LONLAT, crs, [lon], [lat])
    return xs[0], ys[0]


def local_directions(crs, lat, lon, x, y):
    """Unit vectors on the map that point to local north and local east of the site.
    Measured from the map projection itself, so no assumption about its axes is needed."""
    step = 0.01
    nx, ny = map_xy(crs, min(lat + step, 89.99), lon)
    ex, ey = map_xy(crs, lat, lon + step)
    north = np.array([nx - x, ny - y])
    east = np.array([ex - x, ey - y])
    return north / np.linalg.norm(north), east / np.linalg.norm(east)


def horizon_profile(layers, x, y, ground, north, east, az_step=AZ_STEP):
    """Highest terrain angle in every direction.
    layers: list of (HeightMap, reach in m), finest first.
    Returns azimuths, {mast: (horizon angles in deg, distance to the blocking point in m)},
    and the share of rays that stayed on the map all the way out."""
    azimuth = np.arange(0.0, 360.0, az_step)
    a = np.radians(azimuth)                                   # clockwise from north, like Horizons
    dir_x = np.sin(a) * east[0] + np.cos(a) * north[0]
    dir_y = np.sin(a) * east[1] + np.cos(a) * north[1]

    distances, heights = [], []
    start = 0.0
    for height_map, reach in layers:
        d = np.arange(start + height_map.pixel, reach + 1e-6, height_map.pixel)
        heights.append(height_map(x + dir_x[:, None] * d, y + dir_y[:, None] * d))
        distances.append(d)
        start = d[-1]
    d = np.concatenate(distances)
    terrain = np.concatenate(heights, axis=1)

    curvature_drop = d ** 2 / (2 * MOON_RADIUS)               # the sphere curving away
    result = {}
    for mast in MASTS:
        angle = np.degrees(np.arctan((terrain - (ground + mast) - curvature_drop) / d))
        angle = np.where(np.isnan(angle), -np.inf, angle)
        best = angle.argmax(axis=1)
        result[mast] = (angle.max(axis=1), d[best])
    coverage = float(1 - np.isnan(terrain[:, -1]).mean())
    return azimuth, result, coverage


def rounded(values, digits):
    return [round(float(v), digits) if math.isfinite(v) else None for v in values]


def main():
    parser = argparse.ArgumentParser(description="Terrain horizon for lunar landing sites")
    parser.add_argument("sites", nargs="*", help="site ids (default: all sites with terrain)")
    parser.add_argument("--coarse", default=str(COARSE_MAP), help="80 m LOLA map")
    parser.add_argument("--fine", help="20 m LOLA map, used for the first 30 km")
    args = parser.parse_args()

    config = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    sites = [s for s in config["sites"] if s.get("terrain") and (not args.sites or s["id"] in args.sites)]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with rasterio.open(args.coarse) as src:
        crs = src.crs
        print(f"Coarse map: {Path(args.coarse).name}, {src.res[0]:.0f} m/pixel")

    started = time.time()
    for number, site in enumerate(sites, start=1):
        x, y = map_xy(crs, site["lat"], site["lon"])
        north, east = local_directions(crs, site["lat"], site["lon"], x, y)

        layers = []
        if args.fine:
            try:
                fine = read_height_map(args.fine, x, y, FINE_DIST + 200)
                if np.isnan(fine(np.array(x), np.array(y))):
                    raise ValueError("site is outside the fine map")
                layers.append((fine, FINE_DIST))
            except Exception as error:                        # e.g. the 20 m file is still downloading
                print(f"  fine map not usable for {site['id']} ({error}); using the coarse map only")
        coarse = read_height_map(args.coarse, x, y, MAX_DIST + 500)
        layers.append((coarse, MAX_DIST))

        ground = float(layers[0][0](np.array(x), np.array(y)))
        if not math.isfinite(ground):
            print(f"[{number}/{len(sites)}] {site['name']}: outside the height map, skipped")
            continue

        azimuth, by_mast, coverage = horizon_profile(layers, x, y, ground, north, east)
        record = {
            "id": site["id"], "name": site["name"], "lat": site["lat"], "lon": site["lon"],
            "ground_m": round(ground, 1),
            "az_step_deg": AZ_STEP,
            "max_dist_km": MAX_DIST / 1000,
            "maps": [{"file": m.name, "pixel_m": round(m.pixel, 2), "reach_km": reach / 1000}
                     for m, reach in layers],
            "rays_on_map": round(coverage, 3),
            "masts": {},
        }
        line = f"[{number}/{len(sites)}] {site['name']:<26} ground {ground:6.0f} m"
        for mast, (angles, blocker) in by_mast.items():
            record["masts"][f"{mast:g}"] = {
                "horizon_deg": rounded(angles, 3),
                "blocker_km": rounded(blocker / 1000, 2),
            }
            if mast == 0:
                continue                                      # keep the printed line short
            top = int(np.argmax(angles))
            line += (f" | {mast:g} m: {np.min(angles):6.2f}..{np.max(angles):6.2f} deg"
                     f" (top at az {azimuth[top]:5.1f}, {blocker[top] / 1000:5.1f} km)")
        if coverage < 0.99:
            line += f" | {100 * (1 - coverage):.0f}% of rays leave the map"
        print(line)
        (OUT_DIR / f"{site['id']}.json").write_text(json.dumps(record), encoding="utf-8")

    print(f"\nDone in {time.time() - started:.0f} s. Files are in {OUT_DIR}")


if __name__ == "__main__":
    main()
