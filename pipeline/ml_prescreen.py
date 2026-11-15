#!/usr/bin/env python3
"""
Lunar Window Finder - experiment: can machine learning replace the calculation?

The verdicts of the tool come from geometry (720 rays over the NASA LOLA map).
Here we test, openly, whether a machine-learning model could do the same job
faster. The model learns "share of 2027-2028 with the Sun in view" (2 m panel)
from the points of our Artemis III region scans.

Two sets of inputs are compared:
  shape  the shape of the ground only: height, height above the surroundings
         at six scales, depth below the highest ground nearby, slope, distance
         from the pole (13 numbers)
  rays   8 coarse horizon rays (instead of 720), the same 8 angles sorted,
         their mean, and the distance from the pole (18 numbers)

Honest test: leave one region out. The model is trained on eight regions and
tested on the ninth, which it has never seen; training points closer than 5 km
to the test region are removed, because neighbouring points are alike. A random
split would leak the answer.

The model is NOT used for the verdicts on the page. It is a measured baseline
and a possible fast pre-screen.

Run from the project folder, after region_scan.py and export_terrain.py:
    pip install scikit-learn pillow
    python3 pipeline/ml_prescreen.py
Writes data/results/ml.json (export_web.py then puts it on the page).

AI use: written during NASA Space Apps 2026 with help from an AI assistant
(Claude by Anthropic); every step was run and checked by the author.
"""

import json
import math
import time
import warnings
from pathlib import Path

import numpy as np
import sklearn
from scipy import ndimage as ndi
from scipy.stats import spearmanr
from sklearn.ensemble import GradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
REGIONS_DIR = ROOT / "data" / "regions"
TERRAIN_PNG = ROOT / "docs" / "data" / "terrain.png"       # the 240 m LOLA map of the page
TERRAIN_JSON = ROOT / "docs" / "data" / "terrain.json"
OUT_FILE = ROOT / "data" / "results" / "ml.json"

PANEL_M = 2.0
N_RAYS = 8
BUFFER_KM = 5.0
TREES, DEPTH, RATE = 400, 3, 0.05


def read_png(path):
    """The three colour layers of the terrain picture as arrays."""
    try:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None
        a = np.asarray(Image.open(path).convert("RGB"))
        return a[..., 0], a[..., 1], a[..., 2]
    except ImportError:
        import rasterio
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with rasterio.open(path) as src:
                a = src.read()
        return a[0], a[1], a[2]


def make_model():
    return GradientBoostingRegressor(n_estimators=TREES, max_depth=DEPTH, learning_rate=RATE,
                                     subsample=0.8, random_state=0)


def main():
    started = time.time()
    meta = json.loads(TERRAIN_JSON.read_text(encoding="utf-8"))
    high, low, _ = read_png(TERRAIN_PNG)
    heights = meta["offset_m"] + meta["step_m"] * (high.astype(np.float64) * 256 + low)
    pixel, moon_r = meta["pixel_m"], meta["radius_m"]

    def height(x, y):
        return ndi.map_coordinates(heights, [(meta["top"] - y) / pixel - 0.5, (x - meta["left"]) / pixel - 0.5],
                                   order=1, mode="nearest")

    # ---- the points of the region scans ----
    lat, lon, sun, region = [], [], [], []
    names = {}
    for path in sorted(REGIONS_DIR.glob("a3_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cols = data["columns"]
        ilat, ilon, isun = cols.index("lat"), cols.index("lon"), cols.index("sun_2m")
        names[data["region"]] = data["name"]
        for p in data["points"]:
            if p[isun] is None:
                continue
            lat.append(p[ilat]); lon.append(p[ilon]); sun.append(p[isun]); region.append(data["region"])
    lat, lon, sun, region = np.array(lat), np.array(lon), np.array(sun, float), np.array(region)
    keys = sorted(names)
    r = 2 * moon_r * np.tan(np.radians(90 + lat) / 2)             # south polar stereographic map, metres
    x, y = r * np.sin(np.radians(lon)), r * np.cos(np.radians(lon))
    pole_km = np.hypot(x, y) / 1000
    print(f"{len(sun)} scan points in {len(keys)} regions; map {heights.shape[1]} x {heights.shape[0]} pixels at {pixel:.0f} m")

    # ---- inputs 1: the shape of the ground ----
    layers = [heights]
    for km in (1, 2, 5, 10, 20, 50):
        layers.append(heights - ndi.uniform_filter(heights, max(3, int(round(2 * km * 1000 / pixel)) | 1), mode="nearest"))
    for km in (2, 5, 10, 20):
        layers.append(ndi.maximum_filter(heights, max(3, int(round(2 * km * 1000 / pixel)) | 1), mode="nearest") - heights)
    gy, gx = np.gradient(heights, pixel)
    layers.append(np.degrees(np.arctan(np.hypot(gx, gy))))
    rows, cols_ = (meta["top"] - y) / pixel - 0.5, (x - meta["left"]) / pixel - 0.5
    shape = np.column_stack([ndi.map_coordinates(layer, [rows, cols_], order=1, mode="nearest") for layer in layers] + [pole_km])

    # ---- inputs 2: 8 coarse horizon rays ----
    h0 = height(x, y) + PANEL_M
    north_x, north_y = x / np.hypot(x, y), y / np.hypot(x, y)     # away from the south pole
    east_x, east_y = north_y, -north_x
    distances = np.geomspace(300.0, meta["max_dist_m"], 48)
    horizon = np.empty((len(sun), N_RAYS))
    for k in range(N_RAYS):
        a = 2 * math.pi * k / N_RAYS
        dx, dy = north_x * math.cos(a) + east_x * math.sin(a), north_y * math.cos(a) + east_y * math.sin(a)
        best = np.full(len(sun), -90.0)
        for d in distances:
            best = np.maximum(best, np.degrees(np.arctan((height(x + dx * d, y + dy * d) - h0 - d * d / (2 * moon_r)) / d)))
        horizon[:, k] = best
    rays = np.column_stack([horizon, np.sort(horizon, axis=1), horizon.mean(axis=1), pole_km])

    # ---- leave one region out, with a 5 km buffer ----
    def test(inputs):
        guess, average, used = np.zeros_like(sun), np.zeros_like(sun), []
        for key in keys:
            out = region == key
            gap = np.sqrt((x[~out, None] - x[None, out]) ** 2 + (y[~out, None] - y[None, out]) ** 2).min(axis=1)
            train = np.flatnonzero(~out)[gap > BUFFER_KM * 1000]
            guess[out] = make_model().fit(inputs[train], sun[train]).predict(inputs[out])
            average[out] = sun[train].mean()
            used.append(len(train))
        per_region, hits = [], 0
        for key in keys:
            out = region == key
            top10 = np.argsort(-guess[out])[:10]
            miss = float(sun[out].max() - sun[out][top10].max())
            hits += miss <= 0.05
            per_region.append({"name": names[key], "points": int(out.sum()),
                               "mae": round(float(np.abs(guess[out] - sun[out]).mean()), 2),
                               "rank": round(float(spearmanr(guess[out], sun[out])[0]), 2),
                               "top10_miss": round(miss, 1)})
        return {"inputs": int(inputs.shape[1]),
                "mae": round(float(np.abs(guess - sun).mean()), 2),
                "r2": round(float(1 - ((guess - sun) ** 2).sum() / ((sun - sun.mean()) ** 2).sum()), 2),
                "rank": round(float(np.mean([p["rank"] for p in per_region])), 2),
                "top10_hits": int(hits), "per_region": per_region,
                "average_mae": round(float(np.abs(average - sun).mean()), 2), "train_points": int(np.mean(used))}

    print("Training (leave one region out)...")
    result_shape, result_rays = test(shape), test(rays)

    out = {"target": "share of 2027-2028 with the Sun in view, 2 m panel, from our region scans",
           "points": int(len(sun)), "regions": len(keys), "buffer_km": BUFFER_KM, "n_rays": N_RAYS,
           "model": f"gradient boosting, {TREES} trees of depth {DEPTH} (scikit-learn {sklearn.__version__})",
           "average_mae": result_rays["average_mae"], "shape": result_shape, "rays": result_rays}
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"\nError when predicting a region the model has never seen (percentage points of sunlight):")
    print(f"  guess the average of the other regions      {out['average_mae']:5.2f}")
    print(f"  ML, shape of the ground only ({result_shape['inputs']} inputs)     {result_shape['mae']:5.2f}   R2 {result_shape['r2']:5.2f}")
    print(f"  ML, {N_RAYS} coarse horizon rays ({result_rays['inputs']} inputs)        {result_rays['mae']:5.2f}   R2 {result_rays['r2']:5.2f}")
    print(f"\n  {'region':<22}{'error':>7}{'rank match':>12}{'best spot in top 10':>22}")
    for p in result_rays["per_region"]:
        print(f"  {p['name']:<22}{p['mae']:>6.1f} {p['rank']:>11.2f}{'yes' if p['top10_miss'] <= 0.05 else 'no, misses ' + str(p['top10_miss']) + ' pp':>22}")
    print(f"\n  best-lit point is among the model's 10 highest guesses in {result_rays['top10_hits']} of {len(keys)} regions")
    print(f"Saved {OUT_FILE} in {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
