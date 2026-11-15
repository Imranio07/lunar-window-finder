# Texts for the NASA Space Apps project page

Fields in the same order as on spaceappschallenge.org → profile icon → My Team → Project tab → Edit.
Copy only the text under each heading. Everything must stay in English.

---

## Project Name

Lunar Window Finder

## High-Level Project Summary

Lunar Window Finder is a one-screen web tool that tells a mission planner, a teacher or anyone curious whether a lunar lander will have sunlight for its solar panels and a direct line of sight to Earth at a chosen site on chosen dates. At the Moon’s south pole the Sun never rises more than about 1.5° above a flat horizon, so mountains decide everything; we compute the real horizon of each site from NASA LOLA terrain and combine it with Sun and Earth positions from NASA JPL Horizons for every hour of 2027–2028. The tool gives a one-sentence GO / NO-GO verdict against a mission rule (for example “survives at most 50 hours of darkness”), and if the answer is NO-GO it finds the nearest landing date that works, which is exactly the “launch slipped” situation described in the challenge. It covers the nine Artemis III candidate regions, their best-lit spots found by our own scan, thirteen real missions from Apollo 11 to Blue Ghost, and any point you click near the pole. Its numbers match NASA’s published illumination map within 1.6 percentage points on average, and it shows why a move of a few kilometres can change sunlight from 2% to 64% of the time. New on day 2: it also checks landing safety, the ground slope from the same NASA map against the 5° limit of NASA’s crew lander.

## Link to Project Demo

PASTE THE YOUTUBE LINK HERE (29.5-second video, English subtitles, note “edited with AI assistance”)

## Link to Final Project

https://github.com/Imranio07/lunar-window-finder

## Detailed Project Description

Live tool (no login needed): https://imranio07.github.io/lunar-window-finder/

**What it does**

- Pick a landing site, a landing date and hour (any hour of 2027–2028), a mission length, a panel height (2 m lander deck or 10 m mast) and a mission rule.
- Read the verdict in one sentence, with six key numbers: Sun elevation at touchdown, time until sunset, solar availability, longest darkness, Earth line of sight, longest communication blackout. Each number is also shown for a horizon 0.1° higher and lower, so the user sees how sure the result is.
- See the sky with the real terrain silhouette and the paths of the Sun and Earth, and a timeline of both above the local horizon, including eclipses (Earth passing in front of the Sun).
- Compare everything at once in the feasibility calendar: every site against every landing day of 2027–2028, coloured GO / NO-GO for the chosen rule. Click a cell to open it.
- Rank all sites for the chosen landing date in one table.
- Pick your own point: click anywhere on a shaded-relief map of the south pole, or type any lunar coordinates. The page computes the horizon of that point in the browser and gives the verdict and a calendar row for it.
- Explore a sunlight map of each Artemis III candidate region (about 400 points per region) and jump to its best-lit spot.
- Open thirteen real missions at their real landing moment.
- Get a rough power check (energy per square metre of panel, panel area, battery for the longest night).
- For teachers and the public: “Bishkek vs the Moon” compares the Sun’s path over our city with its path at the landing site.

**How it works**

1. Sun and Earth: NASA JPL Horizons API, apparent azimuth and elevation for a point on the lunar surface (hourly for 2027–2028, every 10 minutes around real landings, every 6 hours over 18.6 years for the checks). Horizons already includes the Moon’s orbit and libration.
2. Terrain horizon: NASA LOLA south-pole height map at 80 m per pixel. From each site we cast 720 rays (every 0.5°) out to 150 km and keep the highest terrain angle, corrected for the curve of the Moon: angle = atan((h − h0 − d²/2R) / d). The Moon has no air, so there is no refraction.
3. Visibility: the share of the Sun’s disk (0.53° wide) and Earth’s disk (1.9° wide) above the local horizon at each time step, and the share of the Sun covered by Earth during eclipses.
4. Region scan: the USGS outlines of the nine Artemis III regions are covered with a grid; the Sun and Earth directions of the region centre are rotated to each grid point; the best-lit point is then recomputed in full.
5. A single static web page (HTML and JavaScript, no server, no external libraries) draws everything and repeats the same formulas in the browser, so every control responds instantly. For a clicked point it reads a 240 m version of the LOLA map and casts the same 720 rays itself; its result matches the Python pipeline within 0.001°.

**What we found**

- Where you land inside a region matters more than which region you choose. In Slater Plain the centre of the region gets sunlight 2% of the time in 2027–2028; a spot 4.5 km away gets 64%. In Mons Mouton: 22% at the centre, 53% at a spot 5.7 km away.
- The best-lit spot of de Gerlache Rim 2 has the shortest “longest night” of all nine regions: 160 hours (6.7 days), against 13 to 19 days elsewhere.
- A 10 m mast instead of a 2 m deck can double the sunlight where a small bump stands within a few hundred metres (one check point: 11% → 23%).
- Chang’e 4 and Chang’e 6 see Earth about 40° below the horizon: the tool shows at once why they needed a relay satellite.

**How we know it is right**

- NASA’s average illumination map (PGDA, Mazarico et al. 2011, 18.6 years): at 20 check points between 85.5° S and the pole our result differs by 1.6 percentage points on average (largest 3.3, correlation 0.995).
- NASA’s Earth visibility map: 0.6 percentage points on average (correlation 0.997); 17 of 20 points agree to 0.1.
- Apollo landings (Apollo Lunar Surface Journal): Sun position within 0.05°, Earth within 0.35°, for all six landings.
- A real mission: for Blue Ghost Mission 1 the tool gives 348 hours from touchdown to sunset, and Firefly Aerospace reported 346 hours of daylight operations. The tool also finds, on its own, the eclipse of 14 March 2025 that the lander filmed from the surface.

**Limits we state openly**

Sunlight in view is not electric power, and Earth in view is not a radio link: panel angle, dust, temperature, antennas and ground stations are not modelled. The 80 m height map smooths ridges closer than about 1 km and ends at 80° S, so for sites north of about 85° S some far terrain is not counted. The click-any-point mode is a quick look on a 240 m map: at 19 sites computed both ways it differs from the full calculation by 2.4 percentage points of sunlight on average, and by up to 15 next to a close ridge. The best-lit spots are our result, not NASA’s selection.

**Landing safety: ground slope (added on day 2)**

Sunlight is not enough: a lander also needs gentle ground. IM-2 Athena (March 2025) ended on its side in a crater. The tool measures the ground slope from the same NASA LOLA 80 m map (height difference between points 80 m on either side) at every site and at every point of the region maps.

- New rule “Max ground slope”: 5° (the limit for NASA’s crew lander used in Artemis III site studies), 10° or 15°. A site steeper than the limit is NO-GO on every date, and the tool says that no landing date fixes it.
- Slope map of each Artemis III region, with the best-lit point that is also gentle enough marked “safe”.
- Slope column in the comparison table; steep sites are marked in the calendar.

What we found: with the 5° limit, 4 of the 9 best-lit spots are too steep (Peak near Cabeus B, Haworth, Mons Mouton Plateau, Nobile Rim 2). In Peak near Cabeus B only 5 of 400 scan points are under 5°. In Slater Plain 26% of the points are, and its best-lit spot (64% sunlight) slopes only 2.9°.

Limit: an 80 m map smooths small bumps, so the real slope under a lander’s feet can be steeper. This is a first screening; certifying a spot needs 5 m maps. Where the tool has no terrain map, there is no slope value and the rule is not checked.

Reference for the 5° limit: arXiv:2406.19863, https://arxiv.org/abs/2406.19863

**Experiment: can machine learning replace the calculation? (added on day 2)**

The verdicts of the tool are geometry, not machine learning. We tested openly whether a model could do the same job. A gradient-boosting model (scikit-learn, 400 trees) learned “share of 2027–2028 with the Sun in view” from the 3,529 points of our Artemis III region scans. Honest test: train on eight regions, test on the ninth, which the model has never seen; training points closer than 5 km to the test region are removed.

- Guessing the average of the other regions: error 11.6 percentage points.
- Model that sees only the shape of the ground (height, height above the surroundings, slope; 13 inputs): 13.4. No better than guessing.
- Model that sees 8 coarse horizon rays instead of 720 (18 inputs): 2.9, R² 0.92. It orders the points of an unseen region almost correctly (rank correlation 0.95), and its 10 highest guesses contain the best-lit point in 9 of 9 regions.

What it shows: at the lunar pole sunlight is decided by the horizon line, not by the local shape of the ground. The model is a measured baseline and a possible fast pre-screen (8 rays instead of 720). It imitates our calculation and was not checked against NASA’s map, so every verdict still comes from the full calculation. Script: pipeline/ml_prescreen.py.

**Benefits and goals:** make site-and-date trade-offs for lunar landings fast, honest and understandable, so a planner can re-check a slipped launch in seconds and a teacher can show why the lunar pole is so hard.

**Tools:** Python (NumPy, Rasterio, Requests, scikit-learn, SciPy, Pillow), JavaScript, HTML and CSS, Git, GitHub Pages. The page runs in any browser with no install and no server.

## Use of Super Intelligence (SI)

Yes. I used an AI assistant (Claude by Anthropic) during the hackathon, after the official start:

- Code: it helped write the Python pipeline and the JavaScript web page. I ran every step on my own computer and checked the results against independent references (NASA illumination and Earth visibility maps, Apollo landing records, the Blue Ghost mission report). The README, the page and each code file state this.
- Text: it helped write the README, these texts and the slides.
- Video and slides: the 30-second demo video and the slide deck were assembled with its help from screen captures of the tool; the video is a real screen recording of the tool and carries a visible note “edited with AI assistance”.
- Method: I discussed options for the method and the features with it; the choice of challenge and the decisions on what to build and how to check it were mine.

No numbers or results were generated by AI: every number comes from NASA and USGS data processed by the open code in the repository. No NASA logos or branding are used.

## NASA Data

- **NASA JPL Horizons** (API): Sun and Earth azimuth and elevation at every site, for every time step. This is the core input of the whole tool.
- **NASA LOLA (Lunar Orbiter Laser Altimeter) south-pole height map**, 80 m per pixel, from NASA’s Planetary Geodesy Data Archive (PGDA): used to compute the terrain horizon of every polar site and of about 3,500 scan points, and (reduced to 240 m) for the click-any-point mode.
- **NASA PGDA Lunar Polar Illumination maps** (average solar illumination and average Earth visibility, Mazarico et al. 2011): used as the independent reference to check our results.
- **NASA Artemis III candidate landing regions** (announced October 2024), as outlines published by USGS from LROC QuickMap: the nine regions shown in the tool.
- **Apollo Lunar Surface Journal (NASA History)**: Sun and Earth angles at the Apollo landings, used as a second check.

## Space Agency Partner Data and Other References

Other data:
- USGS Astrogeology, Down-selected Artemis III candidate landing site navigational grids, DOI 10.5066/P1MEQ6UK: https://www.sciencebase.gov/catalog/item/671a6fa8d34efed5620f89f8
- Public landing coordinates and times of ISRO Chandrayaan-3, JAXA SLIM, CNSA Chang’e 4 and Chang’e 6, Intuitive Machines IM-1 and IM-2, and Firefly Blue Ghost Mission 1 (ISRO and JAXA are 2026 Space Apps Space Agency Partners).

References:
- NASA JPL Horizons System and API: https://ssd.jpl.nasa.gov/horizons/ and https://ssd-api.jpl.nasa.gov/doc/horizons.html
- NASA PGDA, High-resolution LOLA topography of the lunar south pole: https://pgda.gsfc.nasa.gov/products/90
- NASA PGDA, Lunar Polar Illumination: https://pgda.gsfc.nasa.gov/products/69
- Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., Torrence, M. H. (2011). Illumination conditions of the lunar polar regions using LOLA topography. Icarus 211, 1066–1081.
- NASA, “NASA Provides Update on Artemis III Moon Landing Regions” (October 2024): https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/
- Apollo Lunar Surface Journal, Sun and Earth altitude and azimuth at the landing sites: https://www.nasa.gov/history/alsj/alsj-EarthSun_AltAz.html
- Firefly Aerospace, “Firefly Aerospace Successfully Completes 14 Days of Surface Operations on the Moon” (March 2025): https://fireflyspace.com/news/firefly-aerospace-successfully-completes-14-days-of-surface-operations-on-the-moon

Tools and open-source software: Python, NumPy, Rasterio (GDAL), Requests, Git, GitHub Pages; Inter font (SIL Open Font License) in the video; AI assistant Claude by Anthropic (see the SI section).
