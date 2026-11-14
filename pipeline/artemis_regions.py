#!/usr/bin/env python3
"""
Lunar Window Finder - Artemis III candidate regions.

Reads the outlines of the nine Artemis III candidate landing regions from the
USGS file A3_9regions-lonlat-simplified.zip (data release DOI 10.5066/P1MEQ6UK,
regions from LROC QuickMap) and finds the centre of each region.
The centres are added to sites.json as group "artemis", so the other
pipeline steps pick them up.

Put the zip (or its unpacked files) under data/artemis/ and run:
    python3 pipeline/artemis_regions.py
"""

import json
import math
import re
import struct
import zipfile
from pathlib import Path

MOON_RADIUS = 1_737_400.0
ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "artemis"
SITES_FILE = ROOT / "pipeline" / "sites.json"
OUTLINES_FILE = ROOT / "data" / "regions" / "outlines.json"

REGIONS = {                     # simplified name -> display name (NASA, 28 Oct 2024)
    "peaknearcabeusb": "Peak near Cabeus B",
    "haworth": "Haworth",
    "malapertmassif": "Malapert Massif",
    "monsmoutonplateau": "Mons Mouton Plateau",
    "monsmouton": "Mons Mouton",
    "nobilerim1": "Nobile Rim 1",
    "nobilerim2": "Nobile Rim 2",
    "degerlacherim2": "de Gerlache Rim 2",
    "slaterplain": "Slater Plain",
}


def simple(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def match_region(texts):
    """Finds which region a record belongs to from its attribute values or file name."""
    for text in texts:
        s = simple(text)
        for key in sorted(REGIONS, key=len, reverse=True):     # "monsmoutonplateau" before "monsmouton"
            if key in s:
                return key
    return None


# ---- minimal shapefile reading (polygons + attribute table) ----
def read_polygons(shp_path):
    """List of polygons; each polygon is a list of rings; each ring a list of (x, y)."""
    data = shp_path.read_bytes()
    pos, shapes = 100, []
    while pos + 8 <= len(data):
        _, words = struct.unpack(">2i", data[pos:pos + 8])
        content = data[pos + 8: pos + 8 + 2 * words]
        pos += 8 + 2 * words
        shape_type = struct.unpack("<i", content[:4])[0]
        if shape_type not in (5, 15, 25):                        # polygon, polygonZ, polygonM
            shapes.append([])
            continue
        n_parts, n_points = struct.unpack("<2i", content[36:44])
        parts = list(struct.unpack(f"<{n_parts}i", content[44:44 + 4 * n_parts]))
        start = 44 + 4 * n_parts
        points = [struct.unpack("<2d", content[start + 16 * i: start + 16 * i + 16]) for i in range(n_points)]
        bounds = parts + [n_points]
        shapes.append([points[bounds[k]:bounds[k + 1]] for k in range(n_parts)])
    return shapes


def read_table(dbf_path):
    """Attribute table as a list of lists of text values."""
    if not dbf_path.exists():
        return []
    data = dbf_path.read_bytes()
    n_records, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields, pos = [], 32
    while data[pos] != 0x0D:
        fields.append(data[pos + 16])                            # field width
        pos += 32
    rows = []
    for r in range(n_records):
        rec = data[header_len + r * record_len: header_len + (r + 1) * record_len]
        values, offset = [], 1                                   # byte 0 = deletion flag
        for width in fields:
            values.append(rec[offset:offset + width].decode("latin-1", "ignore").strip())
            offset += width
        rows.append(values)
    return rows


# ---- centre of a region on the polar map ----
def to_polar(lon, lat):
    r = 2 * MOON_RADIUS * math.tan(math.radians(90 + lat) / 2) if lat < 0 else \
        2 * MOON_RADIUS * math.tan(math.radians(90 - lat) / 2)
    return r * math.sin(math.radians(lon)), r * math.cos(math.radians(lon))


def from_polar(x, y, south):
    r = math.hypot(x, y)
    colat = 2 * math.degrees(math.atan(r / (2 * MOON_RADIUS)))
    return math.degrees(math.atan2(x, y)), (colat - 90 if south else 90 - colat)


def centre(polygon):
    """Area-weighted centre of a lon/lat polygon, computed on a polar map."""
    south = sum(lat for ring in polygon for _, lat in ring) < 0
    area = cx = cy = 0.0
    projected = []
    for ring in polygon:
        pts = [to_polar(lon, lat) for lon, lat in ring]
        projected.extend(pts)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            cross = x0 * y1 - x1 * y0
            area += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
    if abs(area) < 1e-6:
        return None
    x, y = cx / (3 * area), cy / (3 * area)
    reach = max(math.hypot(px - x, py - y) for px, py in projected) / 1000
    lon, lat = from_polar(x, y, south)
    return lat, lon, abs(area) / 2 / 1e6, reach


def main():
    for archive in SOURCE_DIR.rglob("*.zip"):
        target = archive.with_suffix("")
        if not target.exists():
            with zipfile.ZipFile(archive) as z:
                z.extractall(target)

    found, outlines = {}, {}
    for shp in SOURCE_DIR.rglob("*.shp"):
        polygons = read_polygons(shp)
        table = read_table(shp.with_suffix(".dbf"))
        for i, polygon in enumerate(polygons):
            if not polygon:
                continue
            values = table[i] if i < len(table) else []
            key = match_region(values + [shp.stem])
            sample_lon = polygon[0][0][0]
            if key is None or abs(sample_lon) > 360:
                continue                                         # not a region, or not in degrees
            result = centre(polygon)
            if result and (key not in found or result[2] > found[key][2]):
                found[key] = result
                outlines[key] = polygon

    if not found:
        raise SystemExit(f"No Artemis region outlines found under {SOURCE_DIR}")

    print("Artemis III candidate regions (centre of the USGS outline):")
    for key, name in REGIONS.items():
        if key in found:
            lat, lon, area, reach = found[key]
            print(f"  {name:<22} lat {lat:9.4f}  lon {lon:9.4f}   area {area:6.0f} km2, edge up to {reach:4.1f} km from centre")
        else:
            print(f"  {name:<22} not found")

    OUTLINES_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTLINES_FILE.write_text(json.dumps({
        key: {"name": REGIONS[key], "site_id": "a3_" + key, "lat": round(found[key][0], 4), "lon": round(found[key][1], 4),
              "area_km2": round(found[key][2]), "rings": [[[round(lon, 5), round(lat, 5)] for lon, lat in ring] for ring in outlines[key]]}
        for key in found}), encoding="utf-8")

    config = json.loads(SITES_FILE.read_text(encoding="utf-8"))
    best_spots = [s for s in config["sites"] if s.get("spot") == "best"]          # keep results of region_scan.py
    config["sites"] = [s for s in config["sites"] if s.get("group") != "artemis"]
    new_sites = [{"id": "a3_" + key, "name": name + ", region centre", "group": "artemis", "region": key, "spot": "centre",
                  "lat": round(found[key][0], 4), "lon": round(found[key][1], 4), "terrain": True,
                  "windows": ["plan"],
                  "source": "centre of the USGS Artemis III region outline (DOI 10.5066/P1MEQ6UK)"}
                 for key, name in REGIONS.items() if key in found]
    config["sites"] = new_sites + best_spots + config["sites"]
    SITES_FILE.write_text(json.dumps(config, indent=1), encoding="utf-8")
    print(f"\nAdded {len(new_sites)} Artemis regions to {SITES_FILE.name}")


if __name__ == "__main__":
    main()
