# Lunar Window Finder

**Will a lander have sunlight for its solar panels and a direct line of sight to Earth, at this spot on the Moon, on these dates?**
Lunar Window Finder answers that in one screen, using the real mountains around the landing site.

- **Live site:** https://imranio07.github.io/lunar-window-finder/
- **Challenge:** NASA Space Apps Challenge 2026, *Lunar Landing Site Navigator*
- **Team:** SpaceTalent (Imran Narbaev), NASA Space Apps Bishkek 2026

## The problem

At the lunar south pole the Sun never rises more than about 1.5° above the flat horizon, so the hills decide everything. A crater rim kilometres away can hide the Sun for days, and the Earth (needed for direct radio contact) wobbles up and down on the horizon every month. NASA’s tools (QuickMap, Moon Trek, JPL Horizons) hold all the data, but comparing *site × date* combinations quickly is hard. Real missions have been hurt by exactly this: IM-2 *Athena* (March 2025) came down in a crater about 250 m from its target, on its side, and could not recharge.

## What the tool does

- **Verdict in one sentence** for any site, landing date (every hour of 2027–2028), mission length and panel height (2 m deck or 10 m mast), with **GO / NO-GO** against a mission rule (for example a rover that survives at most 50 hours of darkness, like NASA’s VIPER). If the rule fails, it finds the **nearest landing date that works**, which is the “launch slipped” case from the challenge.
- **Big numbers with ranges:** Sun elevation at touchdown, time until sunset, solar availability, longest darkness, Earth line of sight, longest communication blackout. Every number is also computed with the horizon 0.1° higher and lower.
- **Sky with the real horizon:** terrain silhouette from NASA LOLA with the paths of the Sun and Earth. **Timeline** of both above the local horizon, with **eclipses** (Earth passing in front of the Sun).
- **Sunlight map of every Artemis III candidate region:** about 400 points per region, showing how a shift of a few kilometres changes everything, and the **best-lit spot**.
- **Feasibility calendar:** every site × every landing day of 2027–2028, coloured by the chosen rule.
- **Compare all sites** for the chosen landing date in one ranked table, GO / NO-GO for each.
- **Landing safety:** ground slope at every site and every scan point from the NASA LOLA 80 m map, a "max ground slope" rule (5° is the limit for NASA's crew lander used in Artemis III site studies), a slope map of each Artemis III region and the best-lit point that is also gentle enough.
- **Your own point:** click any spot on a shaded-relief map of the south pole, or type coordinates anywhere on the Moon. The page computes the horizon for that point in the browser (240 m LOLA map) and gives the verdict and a calendar row for it.
- **Real missions:** Apollo 11–17, IM-1, IM-2, Chandrayaan-3, Chang’e 4 and 6, SLIM, Blue Ghost 1 at their real landing moments.
- **Power check:** rough energy per m² of panel, panel area and battery size for a chosen load.
- **Bishkek vs the Moon:** the Sun’s path in Bishkek’s sky against the lunar site, for teachers and the public.

## Key results

| Artemis III region | Sunlight 2027–2028 at the region centre | at the best-lit spot of our scan | distance |
|---|---|---|---|
| Slater Plain | 2.0% | 63.9% | 4.5 km |
| Haworth | 12.0% | 52.5% | 16.5 km |
| Mons Mouton | 22.2% | 53.3% | 5.7 km |
| Malapert Massif | 31.9% | 66.0% | 5.0 km |
| Nobile Rim 1 | 30.4% | 67.1% | 12.0 km |
| de Gerlache Rim 2 | 35.8% | 69.4% | 7.8 km |

2 m panel. The best spot of de Gerlache Rim 2 has the shortest “longest night” of all regions: 160 h (6.7 days), against 13–19 days elsewhere.

## How we know it is right

1. **Against NASA’s illumination map.** NASA PGDA average solar illumination of the south pole (Mazarico et al. 2011, averaged over 18.6 years). We compute the same 18.6 years at 20 check points between 85.5° S and the pole, at the surface like NASA: **mean absolute difference 1.6 percentage points, largest 3.3, 19 of 20 points within 3, correlation 0.995.**
2. **Against NASA’s Earth visibility map** (same product, share of time with any part of Earth in view): **mean absolute difference 0.6 percentage points, correlation 0.997.** Seventeen of the twenty points agree to 0.1.
3. **Against the Apollo landings.** Sun and Earth altitude and azimuth at the six Apollo touchdowns, compared with the Apollo Lunar Surface Journal: **Sun within 0.05°, Earth within 0.35°** (the Journal itself quotes agreement with Horizons within 0.5°).
4. **Against a real mission.** For Blue Ghost Mission 1 (landed 2 March 2025) the tool gives 348 hours from touchdown to sunset; Firefly Aerospace reported 346 hours of daylight operations. Without being told, the tool also finds the eclipse of 14 March 2025 at the landing site (Earth covers the Sun between 05:00 and 09:50 UTC), which the lander filmed from the surface.
5. **Sanity checks of the horizon code:** flat ground gives the expected −0.087° horizon for a 2 m panel; mountains placed north or east appear at azimuth 0° or 90°.

## How it works

| Step | Script | What it does |
|---|---|---|
| 1 | `pipeline/fetch_horizons.py` | NASA JPL Horizons API: apparent azimuth and elevation of the Sun and Earth for a point on the lunar surface, hourly 2027–2028, every 10 min around real landings, every 6 h over 18.6 years for the checks. Horizons includes the Moon’s orbit and libration. |
| 2 | `pipeline/horizon.py` | NASA LOLA south-pole height map (80 m/pixel): 720 rays from each site, out to 150 km, highest terrain angle corrected for lunar curvature (no air, so no refraction). Heights 0 m, 2 m and 10 m. |
| 2b | `pipeline/artemis_regions.py`, `pipeline/region_scan.py` | USGS outlines of the nine Artemis III regions; grid scan of each region; the best-lit spot gets its own full calculation. |
| 3 | `pipeline/visibility.py` | Share of the Sun’s and Earth’s disk above the local horizon at every time step, eclipses, scores, ranges and the checks. |
| 4 | `pipeline/export_web.py` + `docs/index.html` | Packs the results; one static page draws everything in the browser (no server, no external libraries). |
| 2c | `pipeline/slope.py` | Ground slope from the LOLA 80 m map (central differences over 160 m) at every site and every region scan point. |
| 5 | `pipeline/export_terrain.py` | Shrinks the LOLA map to 240 m and packs it into a PNG, so the page can compute the horizon of any clicked point in the browser. |

**Formula of the horizon:** for terrain height *h* at distance *d* from a site at height *h₀* (ground + panel), the angle is `atan((h − h₀ − d²/2R) / d)` with *R* = 1737.4 km, and the horizon in each direction is the largest such angle.

## Limits (what the numbers are not)

- Sunlight in view is not electric power: panel angle, dust and temperature are not modelled (the power card is a rough estimate).
- Earth in view is not a radio link: antennas and ground stations are not modelled.
- The 80 m height map smooths ridges closer than about 1 km; the ±0.1° range shows the effect of small horizon errors. Sites far from the pole use a smooth Moon.
- Ground slope comes from an 80 m map, which smooths small bumps: the real slope under a lander's feet can be steeper. It is a first screening; certifying a spot needs 5 m maps.
- The height map ends at 80° S: for sites north of about 85° S a part of the 150 km search radius lies beyond that edge and is not counted.
- The click-any-point mode is a quick look on a 240 m map. At 19 sites computed both ways it differs from the 80 m calculation by 2.4 percentage points of sunlight on average and by up to 15 where a ridge stands within a few hundred metres. Its Sun and Earth directions are turned from the nearest computed site (checked against JPL Horizons: within 0.04°); the browser horizon code matches the Python pipeline within 0.001°.
- Artemis III region centres come from USGS outlines; the best-lit spots are our own result, not NASA’s choice.

## Run it yourself

```
python3 -m venv env && source env/bin/activate
pip install -r requirements.txt
# put the NASA files in data/nasa/ (links below), the USGS zip in data/artemis/
python3 pipeline/artemis_regions.py
python3 pipeline/fetch_horizons.py
python3 pipeline/horizon.py
python3 pipeline/region_scan.py
python3 pipeline/slope.py
python3 pipeline/fetch_horizons.py      # best-lit spots
python3 pipeline/horizon.py
python3 pipeline/visibility.py
python3 pipeline/export_web.py
python3 pipeline/export_terrain.py
cd docs && python3 -m http.server 8000
```

## Data and references

- NASA JPL Horizons API: https://ssd-api.jpl.nasa.gov/doc/horizons.html
- NASA LOLA south-pole height map `LDEM_80S_80MPP_ADJ.TIF`, NASA PGDA: https://pgda.gsfc.nasa.gov/products/90
- NASA PGDA Lunar Polar Illumination, `AVGVISIB_85S_060M_201608.TIF` and `..._EARTH.TIF`: https://pgda.gsfc.nasa.gov/products/69
- Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., Torrence, M. H. (2011). Illumination conditions of the lunar polar regions using LOLA topography. *Icarus* 211, 1066–1081.
- USGS, Down-selected Artemis III candidate landing site navigational grids, DOI 10.5066/P1MEQ6UK: https://www.sciencebase.gov/catalog/item/671a6fa8d34efed5620f89f8
- NASA, Artemis III candidate landing regions update (October 2024): https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/
- Apollo Lunar Surface Journal, Sun and Earth altitude/azimuth at the Apollo landings: https://www.nasa.gov/history/alsj/alsj-EarthSun_AltAz.html
- Slope limit for NASA's crew lander used in Artemis III site studies (5°): arXiv:2406.19863, https://arxiv.org/abs/2406.19863
- Firefly Aerospace, Blue Ghost Mission 1 completes 14 days of surface operations (346 hours of daylight, eclipse of 14 March 2025): https://fireflyspace.com/news/firefly-aerospace-successfully-completes-14-days-of-surface-operations-on-the-moon
- Landing coordinates and times of IM-1, IM-2, Chandrayaan-3, Chang’e 4 and 6, SLIM and Blue Ghost 1: public mission reports (rounded; used for illustration).

## Use of AI

The code and texts were written during the hackathon (14–15 November 2026) with help from an AI assistant (Claude by Anthropic). The 30-second demo video and the slides were assembled with its help from screen captures of the tool; the video is a real screen recording of the tool and carries a visible note that it was edited with AI assistance, and every code file states the AI use in its header. The author ran every step on his own computer, checked the results against the NASA and Apollo references above, and can explain each part. No numbers or results were generated by AI: every number comes from NASA and USGS data processed by the code in this repository.
