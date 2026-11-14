#!/usr/bin/env python3
"""
Lunar Window Finder - pipeline step 3: visibility, scores and the checks.

Puts together step 1 (where the Sun and the Earth are, from JPL Horizons)
and step 2 (the terrain horizon from LOLA) and works out, for every time
step, how much of the Sun's disk and of the Earth's disk is above the
local horizon.

Scores (each for a 2 m and a 10 m mast, and as a range for a horizon
0.1 deg higher or lower, i.e. how sure we are of the terrain):
  Solar Availability              average share of the Sun's disk in view, %
  Longest Darkness                longest stretch with no sunlight at all, h
  Earth Line-of-Sight             average share of the Earth's disk in view, %
  Longest Communication Blackout  longest stretch with the Earth fully hidden, h
Sunlight in view is not the same as power, and Earth in view is not the
same as a radio link: these are geometric scores.

Three checks against independent references:
  1. NASA PGDA average solar illumination map (Mazarico et al. 2011, 18.6 years)
     at the check points near the south pole, compared at the surface (0 m).
  2. Sun and Earth position at the six Apollo landings, as listed by the
     Apollo Lunar Surface Journal.
  3. NASA PGDA average Earth visibility map, same check points (if the file is there).

Run from the project folder:
    python3 pipeline/visibility.py
Results: data/results/<site id>.json and data/results/validation.json
"""

import csv
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import transform
from rasterio.windows import Window

SUN_RADIUS = 0.267            # deg, apparent radius of the Sun seen from the Moon
EARTH_RADIUS = 0.95           # deg, apparent radius of the Earth seen from the Moon
SHIFT = 0.1                   # deg, horizon uncertainty used for the ranges
MASTS = ("2", "10")           # m, must match pipeline/horizon.py
MOON_RADIUS = 1_737_400.0
MOON_LONLAT = "+proj=longlat +R=1737400 +no_defs"

ROOT = Path(__file__).resolve().parents[1]
SITES_FILE = ROOT / "pipeline" / "sites.json"
HORIZONS_DIR = ROOT / "data" / "horizons"
TERRAIN_DIR = ROOT / "data" / "terrain"
RESULTS_DIR = ROOT / "data" / "results"
NASA_SUN_MAP = ROOT / "data" / "nasa" / "AVGVISIB_85S_060M_201608.TIF"
NASA_EARTH_MAP = ROOT / "data" / "nasa" / "AVGVISIB_85S_060M_201608_EARTH.TIF"

# Sun and Earth seen from the Apollo landing sites at touchdown, from the Apollo Lunar
# Surface Journal (computed by P. Fjeld and J. Scotti, spot-checked against JPL Horizons):
# https://www.nasa.gov/history/alsj/alsj-EarthSun_AltAz.html
# The Apollo 11 Earth altitude is printed as "59:43" there, so it is left out.
APOLLO_REFERENCE = {
    "apollo11": {"sun_el": 10.65, "sun_az": 88.81, "earth_el": None, "earth_az": 272.16},
    "apollo12": {"sun_el": 5.19, "sun_az": 91.16, "earth_el": 61.56, "earth_az": 86.95},
    "apollo14": {"sun_el": 10.36, "sun_az": 89.54, "earth_el": 66.10, "earth_az": 96.70},
    "apollo15": {"sun_el": 12.05, "sun_az": 95.73, "earth_el": 69.28, "earth_az": 203.00},
    "apollo16": {"sun_el": 14.76, "sun_az": 86.01, "earth_el": 77.16, "earth_az": 319.70},
    "apollo17": {"sun_el": 13.33, "sun_az": 95.83, "earth_el": 45.52, "earth_az": 240.88},
}


# ---------------- inputs ----------------
def load_track(site_id, window, body):
    """Times (minutes since 1970), azimuth and elevation saved by fetch_horizons.py."""
    path = HORIZONS_DIR / f"{site_id}.{window}.{body}.csv"
    if not path.exists():
        return None
    with open(path, newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        rows = list(reader)
    minutes = np.array([np.datetime64(t, "m") for t, _, _ in rows]).astype(np.int64)
    az = np.array([float(a) for _, a, _ in rows])
    el = np.array([float(e) for _, _, e in rows])
    return minutes, az, el


def masts_of(site_id):
    """Heights available for a site: 0 m (surface) is only computed where there is terrain."""
    path = TERRAIN_DIR / f"{site_id}.json"
    if path.exists():
        return list(json.loads(path.read_text(encoding="utf-8"))["masts"])
    return list(MASTS)


def load_horizon(site_id, mast):
    """Terrain horizon from horizon.py, or a smooth Moon if the site has no terrain file."""
    path = TERRAIN_DIR / f"{site_id}.json"
    smooth = -math.degrees(math.sqrt(2 * float(mast) / MOON_RADIUS))   # dip of a smooth sphere
    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        values = record["masts"][mast]["horizon_deg"]
        horizon = np.array([smooth if v is None else v for v in values])
        az_grid = np.arange(len(horizon)) * record["az_step_deg"]
        return az_grid, horizon, "LOLA terrain"
    az_grid = np.arange(0.0, 360.0, 0.5)
    return az_grid, np.full(az_grid.size, smooth), "smooth Moon, no terrain"


# ---------------- geometry ----------------
def visible_share(az, el, az_grid, horizon, radius, shift=0.0):
    """Share (0..1) of a round disk's area that is above the local horizon."""
    local = np.interp(az % 360.0, az_grid, horizon, period=360.0) + shift
    h = np.clip((el - local) / radius, -1.0, 1.0)      # disk centre above the horizon, in radii
    return (np.arccos(-h) + h * np.sqrt(1.0 - h * h)) / math.pi


def eclipse_factor(sun_az, sun_el, earth_az, earth_el):
    """Share (0..1) of the Sun's disk NOT covered by the Earth's disk.
    Seen from the Moon, a lunar eclipse is the Earth passing in front of the Sun."""
    a1, e1, a2, e2 = (np.radians(v) for v in (sun_az, sun_el, earth_az, earth_el))
    cos_sep = np.sin(e1) * np.sin(e2) + np.cos(e1) * np.cos(e2) * np.cos(a1 - a2)
    d = np.degrees(np.arccos(np.clip(cos_sep, -1.0, 1.0)))
    r1, r2 = SUN_RADIUS, EARTH_RADIUS
    covered = np.zeros_like(d)
    full = d <= r2 - r1
    part = (d < r1 + r2) & ~full
    if part.any():
        dp = d[part]
        area = (r1 ** 2 * np.arccos(np.clip((dp ** 2 + r1 ** 2 - r2 ** 2) / (2 * dp * r1), -1, 1))
                + r2 ** 2 * np.arccos(np.clip((dp ** 2 + r2 ** 2 - r1 ** 2) / (2 * dp * r2), -1, 1))
                - 0.5 * np.sqrt(np.clip((-dp + r1 + r2) * (dp + r1 - r2) * (dp - r1 + r2) * (dp + r1 + r2), 0, None)))
        covered[part] = area / (math.pi * r1 ** 2)
    covered[full] = 1.0
    return 1.0 - np.clip(covered, 0.0, 1.0)


def eclipse_events(minutes, factor, sun_up):
    """Stretches of time when the Earth covers part of the Sun while the Sun is above the horizon."""
    mask = (factor < 1.0) & sun_up
    events, i = [], 0
    while i < mask.size:
        if mask[i]:
            j = i
            while j + 1 < mask.size and mask[j + 1]:
                j += 1
            events.append({"start": str(np.datetime64(int(minutes[i]), "m")),
                           "end": str(np.datetime64(int(minutes[j]), "m")),
                           "max_cover_pct": round(100 * (1 - float(factor[i:j + 1].min())), 1)})
            i = j + 1
        else:
            i += 1
    return events


def longest_run_hours(mask, step_hours):
    if not mask.any():
        return 0.0
    padded = np.concatenate(([0], mask.astype(np.int8), [0]))
    edges = np.flatnonzero(np.diff(padded))
    return float((edges[1::2] - edges[::2]).max() * step_hours)


def scores(sun, earth, step_hours):
    return {
        "sun_pct": 100 * float(sun.mean()),
        "sun_any_pct": 100 * float((sun > 0).mean()),
        "longest_dark_h": longest_run_hours(sun == 0, step_hours),
        "earth_pct": 100 * float(earth.mean()),
        "earth_any_pct": 100 * float((earth > 0).mean()),
        "longest_blackout_h": longest_run_hours(earth == 0, step_hours),
    }


def value_at(minutes, values, moment, angle=False):
    """Value at an exact moment, interpolated between time steps."""
    if angle:
        unwrapped = np.degrees(np.unwrap(np.radians(values)))
        return float(np.interp(moment, minutes, unwrapped) % 360.0)
    return float(np.interp(moment, minutes, values))


def angle_gap(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


# ---------------- NASA map ----------------
def nasa_share(path, lat, lon):
    """Value of a NASA PGDA average-visibility map at a point (0..1), or None."""
    with rasterio.open(path) as src:
        xs, ys = transform(MOON_LONLAT, src.crs, [lon], [lat])
        row, col = src.index(xs[0], ys[0])
        if not (0 <= row < src.height and 0 <= col < src.width):
            return None
        raw = float(src.read(1, window=Window(col, row, 1, 1))[0, 0])
        if src.nodata is not None and raw == src.nodata:
            return None
        scale = src.scales[0] if src.scales and src.scales[0] not in (None, 1.0) else 4e-05
        offset = src.offsets[0] if src.offsets else 0.0
    value = raw * scale + offset
    return value if -0.0001 <= value <= 1.0001 else None


# ---------------- main ----------------
def site_results(site, windows_config):
    record = {"id": site["id"], "name": site["name"], "group": site["group"],
              "lat": site["lat"], "lon": site["lon"], "windows": {}}
    masts = masts_of(site["id"])
    horizons = {mast: load_horizon(site["id"], mast) for mast in masts}
    record["horizon_source"] = horizons["2"][2]

    window_names = list(site.get("windows", [])) + (["mission"] if "mission" in site else [])
    for window in window_names:
        sun_track = load_track(site["id"], window, "sun")
        earth_track = load_track(site["id"], window, "earth")
        if sun_track is None or earth_track is None:
            continue
        minutes, sun_az, sun_el = sun_track
        _, earth_az, earth_el = earth_track
        step_hours = float(np.median(np.diff(minutes))) / 60.0
        entry = {"start": str(np.datetime64(int(minutes[0]), "m")),
                 "stop": str(np.datetime64(int(minutes[-1]), "m")),
                 "step_h": step_hours, "masts": {}}
        eclipse = eclipse_factor(sun_az, sun_el, earth_az, earth_el)
        for mast in masts:
            az_grid, horizon, _ = horizons[mast]
            variants = []
            for shift in (0.0, -SHIFT, SHIFT):
                sun = visible_share(sun_az, sun_el, az_grid, horizon, SUN_RADIUS, shift) * eclipse
                earth = visible_share(earth_az, earth_el, az_grid, horizon, EARTH_RADIUS, shift)
                variants.append(scores(sun, earth, step_hours))
            entry["masts"][mast] = {
                key: {"value": round(variants[0][key], 2),
                      "low": round(min(v[key] for v in variants), 2),
                      "high": round(max(v[key] for v in variants), 2)}
                for key in variants[0]}

        az_grid, horizon, _ = horizons["2"]
        entry["eclipses"] = eclipse_events(minutes, eclipse,
                                           visible_share(sun_az, sun_el, az_grid, horizon, SUN_RADIUS) > 0)

        if window == "mission":
            landing = int(np.datetime64(site["mission"]["landing_utc"], "m").astype(np.int64))
            sun = visible_share(sun_az, sun_el, az_grid, horizon, SUN_RADIUS)      # terrain only: sunset
            earth = visible_share(earth_az, earth_el, az_grid, horizon, EARTH_RADIUS)
            after = minutes >= landing
            dark = np.flatnonzero(after & (sun == 0))
            hidden = np.flatnonzero(after & (earth == 0))
            entry["landing"] = {
                "time_utc": site["mission"]["landing_utc"],
                "sun_el": round(value_at(minutes, sun_el, landing), 2),
                "sun_az": round(value_at(minutes, sun_az, landing, angle=True), 2),
                "earth_el": round(value_at(minutes, earth_el, landing), 2),
                "earth_az": round(value_at(minutes, earth_az, landing, angle=True), 2),
                "sun_above_horizon_deg": round(value_at(minutes, sun_el, landing)
                                               - float(np.interp(value_at(minutes, sun_az, landing, angle=True),
                                                                 az_grid, horizon, period=360.0)), 2),
                "hours_to_sunset": round((minutes[dark[0]] - landing) / 60.0, 1) if dark.size else None,
                "hours_to_earthset": round((minutes[hidden[0]] - landing) / 60.0, 1) if hidden.size else None,
            }
        record["windows"][window] = entry
    return record


def main():
    config = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    results = {}
    for site in config["sites"]:
        record = site_results(site, config["windows"])
        results[site["id"]] = record
        (RESULTS_DIR / f"{site['id']}.json").write_text(json.dumps(record), encoding="utf-8")

    # ---- planning window summary ----
    print("Planning window 2027-2028, 2 m mast (value, range for horizon +-0.1 deg):")
    print(f"  {'site':<22}{'horizon':<26}{'Sun %':>16}{'longest dark h':>18}{'Earth %':>16}{'longest blackout h':>20}")
    for record in results.values():
        plan = record["windows"].get("plan")
        if not plan:
            continue
        s = plan["masts"]["2"]
        cell = lambda key, f: f"{s[key]['value']:{f}} ({s[key]['low']:.0f}-{s[key]['high']:.0f})"
        print(f"  {record['name']:<22}{record['horizon_source']:<26}{cell('sun_pct', '.1f'):>16}"
              f"{cell('longest_dark_h', '.0f'):>18}{cell('earth_pct', '.1f'):>16}{cell('longest_blackout_h', '.0f'):>20}")

    # ---- checks 1 and 3: NASA average visibility maps ----
    # The NASA maps are computed for the surface, so we compare our 0 m horizon with them.
    validation = {"apollo": []}
    checks = [
        ("nasa_sun", NASA_SUN_MAP, "sun_pct", "Check 1: our Solar Availability over 18.6 years vs NASA map",
         "NASA PGDA average solar illumination, 85-90S, 60 m (Mazarico et al. 2011)"),
        ("nasa_earth", NASA_EARTH_MAP, "earth_any_pct", "Check 3: share of time with any part of Earth in view vs NASA map",
         "NASA PGDA average Earth visibility, 85-90S, 60 m (Mazarico et al. 2011)"),
    ]
    for name, map_file, key, title, source in checks:
        if not map_file.exists():
            print(f"\n{title}: {map_file.name} is not in data/nasa/, skipped")
            continue
        try:
            with rasterio.open(map_file):
                pass
        except Exception as error:
            print(f"\n{title}: cannot read {map_file.name} ({error}), skipped")
            continue
        print(f"\n{title} {map_file.name}")
        print(f"  {'point':<18}{'ours 0 m':>10}{'range':>14}{'ours 2 m':>10}{'ours 10 m':>11}{'NASA':>8}{'diff':>8}")
        points, pairs = [], {"0": [], "2": []}
        for record in results.values():
            val = record["windows"].get("validation")
            if not val:
                continue
            reference = "0" if "0" in val["masts"] else "2"
            ours = val["masts"][reference][key]
            ours2 = val["masts"]["2"][key]["value"]
            ours10 = val["masts"]["10"][key]["value"]
            nasa = nasa_share(map_file, record["lat"], record["lon"])
            point = {"id": record["id"], "lat": record["lat"], "lon": record["lon"], "height_m": float(reference),
                     "ours": ours["value"], "low": ours["low"], "high": ours["high"],
                     "ours_2m": ours2, "ours_10m": ours10, "nasa": None if nasa is None else round(100 * nasa, 2)}
            line = (f"  {record['lat']:>6.1f}, {record['lon']:>6.1f}  {ours['value']:>9.1f}%"
                    f"{ours['low']:>7.1f}-{ours['high']:<5.1f}{ours2:>9.1f}%{ours10:>10.1f}%")
            if nasa is None:
                line += "       ?"
            else:
                point["diff"] = round(ours["value"] - 100 * nasa, 2)
                pairs["0"].append((ours["value"], 100 * nasa))
                pairs["2"].append((ours2, 100 * nasa))
                line += f"{100 * nasa:>7.1f}%{point['diff']:>+8.1f}"
            points.append(point)
            print(line)
        validation[name] = {"source": f"{source}, {map_file.name}", "points": points}
        for height, label in (("0", "stats"), ("2", "stats_2m")):
            if len(pairs[height]) < 3:
                continue
            mine, theirs = np.array(pairs[height]).T
            d = mine - theirs
            stats = {"n": int(d.size), "mean_diff": round(float(d.mean()), 2),
                     "mean_abs_diff": round(float(np.abs(d).mean()), 2),
                     "max_abs_diff": round(float(np.abs(d).max()), 2),
                     "rms_diff": round(float(np.sqrt((d ** 2).mean())), 2),
                     "within_3pp": int((np.abs(d) <= 3).sum()),
                     "correlation": round(float(np.corrcoef(mine, theirs)[0, 1]), 3)}
            validation[name][label] = stats
            print(f"  at {height} m, {stats['n']} points: mean diff {stats['mean_diff']:+.1f} pp, "
                  f"mean |diff| {stats['mean_abs_diff']:.1f} pp, max |diff| {stats['max_abs_diff']:.1f} pp, "
                  f"RMS {stats['rms_diff']:.1f} pp, {stats['within_3pp']}/{stats['n']} within 3 pp, "
                  f"correlation {stats['correlation']}")

    # ---- check 2: Apollo landings ----
    print("\nCheck 2: Sun and Earth at the Apollo landings, ours vs Apollo Lunar Surface Journal")
    print(f"  {'mission':<12}{'Sun el':>16}{'Sun az':>18}{'Earth el':>18}{'Earth az':>18}")
    for site_id, ref in APOLLO_REFERENCE.items():
        landing = results.get(site_id, {}).get("windows", {}).get("mission", {}).get("landing")
        if not landing:
            continue
        row = {"id": site_id, "ours": landing, "reference": ref}
        cells = []
        for key in ("sun_el", "sun_az", "earth_el", "earth_az"):
            if ref[key] is None:
                cells.append(f"{landing[key]:>8.2f} vs   -   ")
                continue
            gap = angle_gap(landing[key], ref[key]) if key.endswith("az") else landing[key] - ref[key]
            row[f"{key}_diff"] = round(gap, 2)
            cells.append(f"{landing[key]:>8.2f} vs {ref[key]:>6.2f}")
        validation["apollo"].append(row)
        print(f"  {results[site_id]['name']:<12}" + "".join(f"{c:>18}" for c in cells))

    (RESULTS_DIR / "validation.json").write_text(json.dumps(validation), encoding="utf-8")

    # ---- real missions at landing ----
    print("\nReal missions at the moment of landing (2 m mast):")
    for record in results.values():
        landing = record["windows"].get("mission", {}).get("landing")
        if not landing:
            continue
        sunset = landing["hours_to_sunset"]
        earthset = landing["hours_to_earthset"]
        print(f"  {record['name']:<22} Sun {landing['sun_el']:6.2f} deg ({landing['sun_above_horizon_deg']:+6.2f} over local horizon)"
              f" | Earth {landing['earth_el']:6.2f} deg"
              f" | sunset in {'>' + 'window' if sunset is None else f'{sunset:.0f} h ({sunset / 24:.1f} d)'}"
              f" | Earth hidden in {'never in window' if earthset is None else f'{earthset:.0f} h'}"
              f" | horizon: {record['horizon_source']}")

    print("\nEclipses (Earth in front of the Sun) seen from the real mission sites:")
    for record in results.values():
        events = record["windows"].get("mission", {}).get("eclipses", [])
        for e in events:
            print(f"  {record['name']:<22} {e['start']} to {e['end']} UTC, up to {e['max_cover_pct']:.0f}% of the Sun covered")
    plan_counts = {r["name"]: len(r["windows"]["plan"].get("eclipses", [])) for r in results.values() if "plan" in r["windows"]}
    if plan_counts:
        top = max(plan_counts, key=plan_counts.get)
        print(f"  2027-2028: up to {plan_counts[top]} eclipse(s) seen from one site ({top})")

    print(f"\nSaved: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
