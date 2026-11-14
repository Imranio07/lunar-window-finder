#!/usr/bin/env python3
"""
Lunar Window Finder - pipeline step 5: a small terrain map for the browser.

The page lets the user click any point near the south pole. For that the
browser needs the terrain itself, but the NASA LOLA map (181 MB) is far too
big to download. This step shrinks it three times, to 240 m per pixel (the
resolution NASA's own illumination study of 2011 worked with), and packs the
heights into an ordinary PNG picture that every browser can read:

    red   = high byte of the height value
    green = low byte of the height value
    blue  = 255 where the height is known, 0 where it is not
    height in metres = OFFSET_M + STEP_M * (red * 256 + green)

It also writes docs/data/terrain.json with the map geometry and a reference
horizon computed here in Python, so the page can check its own JavaScript
horizon against it.

Run from the project folder:
    python3 pipeline/export_terrain.py
"""

import json
import warnings
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window

from horizon import COARSE_MAP, MAX_DIST, MOON_RADIUS, HeightMap, horizon_profile, local_directions, map_xy

FACTOR = 3                    # 80 m -> 240 m per pixel
OFFSET_M = -12000.0           # lowest height that can be stored
STEP_M = 0.5                  # height resolution

ROOT = Path(__file__).resolve().parents[1]
OUT_PNG = ROOT / "docs" / "data" / "terrain.png"
OUT_JSON = ROOT / "docs" / "data" / "terrain.json"

CHECK_POINTS = [(-89.9, 0.0), (-88.0, 90.0), (-86.0, -45.0), (-84.79, 29.2), (-83.0, 150.0)]
TEST_SITE = (-84.79, 29.2)    # IM-2 Athena: reference horizon for the page's self-check


def encode(heights):
    """Heights in metres (NaN = unknown) -> three 8-bit layers."""
    known = np.isfinite(heights)
    value = np.round((np.where(known, heights, OFFSET_M) - OFFSET_M) / STEP_M)
    value = np.clip(value, 0, 65535).astype(np.uint16)
    return np.stack([(value >> 8).astype(np.uint8), (value & 255).astype(np.uint8),
                     np.where(known, 255, 0).astype(np.uint8)])


def decode(layers):
    value = layers[0].astype(np.float64) * 256 + layers[1]
    return np.where(layers[2] > 0, OFFSET_M + STEP_M * value, np.nan)


def main():
    with rasterio.open(COARSE_MAP) as src:
        cols, rows = src.width // FACTOR, src.height // FACTOR
        window = Window(0, 0, cols * FACTOR, rows * FACTOR)
        heights = src.read(1, window=window, out_shape=(rows, cols), resampling=Resampling.average,
                           masked=True).astype("float64").filled(np.nan)
        pixel = src.res[0] * FACTOR
        left, top, crs = src.bounds.left, src.bounds.top, src.crs

    layers = encode(heights)
    small = HeightMap(decode(layers), left, top, pixel, "terrain.png")      # exactly what the browser will see

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with rasterio.open(OUT_PNG, "w", driver="PNG", width=cols, height=rows, count=3, dtype="uint8") as dst:
            dst.write(layers)
    for extra in OUT_PNG.parent.glob("terrain.png.aux.xml"):
        extra.unlink()

    checks = []
    for lat, lon in CHECK_POINTS:
        x, y = map_xy(crs, lat, lon)
        checks.append({"lat": lat, "lon": lon, "x": round(x, 2), "y": round(y, 2),
                       "h": round(float(small(np.array(x), np.array(y))), 2)})

    lat, lon = TEST_SITE
    x, y = map_xy(crs, lat, lon)
    north, east = local_directions(crs, lat, lon, x, y)
    ground = float(small(np.array(x), np.array(y)))
    _, by_mast, _ = horizon_profile([(small, MAX_DIST)], x, y, ground, north, east)
    test = {"lat": lat, "lon": lon, "ground_m": round(ground, 2),
            "horizon_2m_deg": [round(float(v), 3) for v in by_mast[2.0][0]]}

    meta = {"file": OUT_PNG.name, "width": cols, "height": rows, "pixel_m": pixel, "left": left, "top": top,
            "offset_m": OFFSET_M, "step_m": STEP_M, "radius_m": MOON_RADIUS, "max_dist_m": MAX_DIST,
            "source": f"{Path(COARSE_MAP).name} (NASA LOLA, PGDA), averaged {FACTOR}x{FACTOR}",
            "checks": checks, "test": test}
    OUT_JSON.write_text(json.dumps(meta), encoding="utf-8")

    known = np.isfinite(heights)
    print(f"Terrain for the browser: {cols} x {rows} pixels, {pixel:.0f} m per pixel")
    print(f"  heights {np.nanmin(heights):.0f} .. {np.nanmax(heights):.0f} m, {100 * known.mean():.1f}% of pixels known")
    print(f"  {OUT_PNG.name}: {OUT_PNG.stat().st_size / 1e6:.1f} MB   {OUT_JSON.name}: {OUT_JSON.stat().st_size / 1e3:.0f} kB")
    print("  check points (lat, lon -> x, y in m, height in m):")
    for c in checks:
        print(f"    {c['lat']:7.2f} {c['lon']:8.2f} -> {c['x']:12.1f} {c['y']:12.1f}   {c['h']:8.1f}")
    horizon = np.array(test["horizon_2m_deg"])
    print(f"  IM-2 horizon on the 240 m map: {horizon.min():.2f} .. {horizon.max():.2f} deg (80 m map: -1.47 .. 4.07 deg)")


if __name__ == "__main__":
    main()
