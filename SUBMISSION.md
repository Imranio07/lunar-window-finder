# Texts for the NASA Space Apps project page

Copy each block into the matching field on spaceappschallenge.org → your team → Project.
Team: SpaceTalent · Challenge: Lunar Landing Site Navigator · Project name: **Lunar Window Finder**

---

## 1. High-Level Project Summary

Lunar Window Finder is a one-screen web tool that tells a mission planner, a teacher or anyone curious whether a lunar lander will have sunlight for its solar panels and a direct line of sight to Earth at a chosen site on chosen dates. At the Moon’s south pole the Sun never rises more than about 1.5° above a flat horizon, so mountains decide everything; we compute the real horizon of each site from NASA LOLA terrain and combine it with Sun and Earth positions from NASA JPL Horizons for every hour of 2027–2028. The tool gives a one-sentence GO / NO-GO verdict against a mission rule (for example “survives at most 50 hours of darkness”), and if the answer is NO-GO it finds the nearest landing date that works, which is exactly the “launch slipped” situation described in the challenge. It covers the nine Artemis III candidate regions, their best-lit spots found by our own scan, and thirteen real missions from Apollo 11 to Blue Ghost. Its numbers match NASA’s published illumination map within 1.6 percentage points on average, and it shows why a move of a few kilometres can change sunlight from 2% to 64% of the time.

## 2. Link to Project Demo

(paste the link to the 30-second video here)

## 3. Link to Final Project

https://github.com/Imranio07/lunar-window-finder
Live tool: https://imranio07.github.io/lunar-window-finder/

## 4. Detailed Project Description

**What it does**

- Pick a landing site, a landing date and hour (any hour of 2027–2028), a mission length, a panel height (2 m lander deck or 10 m mast) and a mission rule.
- Read the verdict in one sentence, with six key numbers: Sun elevation at touchdown, time until sunset, solar availability, longest darkness, Earth line of sight, longest communication blackout. Each number is also shown for a horizon 0.1° higher and lower, so the user sees how sure the result is.
- See the sky with the real terrain silhouette and the paths of the Sun and Earth, and a timeline of both above the local horizon, including eclipses (Earth passing in front of the Sun).
- Compare everything at once in the feasibility calendar: every site against every landing day of 2027–2028, coloured GO / NO-GO for the chosen rule. Click a cell to open it.
- Rank all sites for the chosen landing date in one table.
- Explore a sunlight map of each Artemis III candidate region (about 400 points per region) and jump to its best-lit spot.
- Open thirteen real missions at their real landing moment.
- Get a rough power check (energy per square metre of panel, panel area, battery for the longest night).
- For teachers and the public: “Bishkek vs the Moon” compares the Sun’s path over our city with its path at the landing site.

**How it works**

1. Sun and Earth: NASA JPL Horizons API, apparent azimuth and elevation for a point on the lunar surface (hourly for 2027–2028, every 10 minutes around real landings, every 6 hours over 18.6 years for the checks). Horizons already includes the Moon’s orbit and libration.
2. Terrain horizon: NASA LOLA south-pole height map at 80 m per pixel. From each site we cast 720 rays (every 0.5°) out to 150 km and keep the highest terrain angle, corrected for the curve of the Moon: angle = atan((h − h0 − d²/2R) / d). The Moon has no air, so there is no refraction.
3. Visibility: the share of the Sun’s disk (0.53° wide) and Earth’s disk (1.9° wide) above the local horizon at each time step, and the share of the Sun covered by Earth during eclipses.
4. Region scan: the USGS outlines of the nine Artemis III regions are covered with a grid; the Sun and Earth directions of the region centre are rotated to each grid point; the best-lit point is then recomputed in full.
5. A single static web page (HTML and JavaScript, no server, no external libraries) draws everything and repeats the same formulas in the browser, so every control responds instantly.

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

Sunlight in view is not electric power, and Earth in view is not a radio link: panel angle, dust, temperature, antennas and ground stations are not modelled. The 80 m height map smooths ridges closer than about 1 km. The best-lit spots are our result, not NASA’s selection.

**Tools:** Python (NumPy, Rasterio, Requests), JavaScript, HTML and CSS, Git, GitHub Pages.

**Goals:** make site-and-date trade-offs for lunar landings fast, honest and understandable for planners, teachers and the public.

## 5. NASA Data

- **NASA JPL Horizons** (API): Sun and Earth azimuth and elevation at every site, for every time step. This is the core input of the whole tool.
- **NASA LOLA (Lunar Orbiter Laser Altimeter) south-pole height map**, 80 m per pixel, from NASA’s Planetary Geodesy Data Archive (PGDA): used to compute the terrain horizon of every polar site and of about 3,500 scan points.
- **NASA PGDA Lunar Polar Illumination maps** (average solar illumination and average Earth visibility, Mazarico et al. 2011): used as the independent reference to check our results.
- **NASA Artemis III candidate landing regions** (announced October 2024), as outlines published by USGS from LROC QuickMap: the nine regions shown in the tool.
- **Apollo Lunar Surface Journal (NASA History)**: Sun and Earth angles at the Apollo landings, used as a second check.

## 6. Space Agency Partner & Other Data

- **USGS Astrogeology**: Down-selected Artemis III candidate landing site navigational grids (DOI 10.5066/P1MEQ6UK), region outlines.
- Public landing coordinates and times of ISRO Chandrayaan-3, JAXA SLIM, CNSA Chang’e 4 and Chang’e 6, Intuitive Machines IM-1 and IM-2, and Firefly Blue Ghost Mission 1.

## 7. Use of Artificial Intelligence

We used an AI assistant (Claude by Anthropic) during the hackathon to help write the Python and JavaScript code, the README and these texts, and to discuss the method. All work was done after the official start. The author ran every step on his own computer, compared the results with independent NASA references (illumination maps, Apollo records, a real eclipse) and can explain each part of the method. No data, images or results were generated by AI: every number comes from NASA and USGS data processed by the open code in the repository. No NASA logos or branding are used.

## 8. References

- NASA JPL Horizons System and API: https://ssd.jpl.nasa.gov/horizons/ and https://ssd-api.jpl.nasa.gov/doc/horizons.html
- NASA PGDA, High-resolution LOLA topography of the lunar south pole: https://pgda.gsfc.nasa.gov/products/90
- NASA PGDA, Lunar Polar Illumination: https://pgda.gsfc.nasa.gov/products/69
- Mazarico, E., Neumann, G. A., Smith, D. E., Zuber, M. T., Torrence, M. H. (2011). Illumination conditions of the lunar polar regions using LOLA topography. Icarus 211, 1066–1081.
- NASA, “NASA Provides Update on Artemis III Moon Landing Regions” (October 2024): https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/
- USGS, Down-selected Artemis III candidate landing site navigational grids, DOI 10.5066/P1MEQ6UK: https://www.sciencebase.gov/catalog/item/671a6fa8d34efed5620f89f8
- Apollo Lunar Surface Journal, Sun and Earth altitude and azimuth at the landing sites: https://www.nasa.gov/history/alsj/alsj-EarthSun_AltAz.html
- Firefly Aerospace, “Firefly Aerospace Successfully Completes 14 Days of Surface Operations on the Moon” (March 2025): https://fireflyspace.com/news/firefly-aerospace-successfully-completes-14-days-of-surface-operations-on-the-moon
- Tools: Python, NumPy, Rasterio (GDAL), Requests, Git, GitHub Pages.
