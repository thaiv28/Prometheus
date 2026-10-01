---
version: 1
slug: "templates-metric-dynamic-html-j2"
primary_target: "templates/metric_dynamic.html.j2"
related_targets: ["templates/base.html.j2","templates/index.html.j2","templates/elo_dynamic.html.j2","templates/team.html.j2"]
---

# Surface brief: Prometheus rankings site (all pages)

Scope: the whole static site (home, metric rankings pages, Elo page, team pages). Visitor mode: **Operate**. Fans look up, filter, sort, and share team rankings; the home page orients them toward that task.

Audience/job: LoL esports fans settling cross-era and cross-region arguments, on phones and desktops, often late at night. Task: find a team-season, see its rank and why, and share the filtered view by URL.

Constraints: static, vanilla JS, no build step. Tables stay semantic, sortable, and keyboard-usable. Data attribution to Oracle's Elixir stays visible.

## Direction contract

THESIS: Every team-season is a championship banner hung in the rafters, and the ranking is the order they hang in. It refuses the dark-neon esports dashboard and the card-grid stat hub.

OWN-WORLD: The ground is dim arena steel (warm charcoal, never pure black) under a single truss rod. Banners are twill felt with a chain-stitched inner border and a swallowtail hem, set in varsity block numerals. Each major league owns one felt hue (LCK royal, LPL crimson, LEC forest, LCS gold) used identically in banners, badges, and chart lines. Other leagues get neutral felt. Color appears only where it encodes a league. Everything else is cream stitch thread on steel.

STORY: The visitor sees who hangs highest, filters to their era or league, watches the banners re-hang, and reads the exact numbers in the dense table below.

FIRST VIEWPORT: A slim top bar (wordmark, metric links, search). A one-line metric title and a filter row. Then a rod across the full width with the current top ten hanging as fixed-length felt banners with rank, name, league and score stitched on. (User decision on 2026-09-30: proportional lengths were not noticeable, so all banners are the same length.) The dense table (28–30px rows) begins directly underneath, with its first rows visible in the first viewport on a 1080p desktop.

FORM: candidate 4 of 7 (Championship rafters banners); seed key e67df08e. Raises: fixed league hue everywhere (transit); color only as encoding (monochrome); every length is data (acetate; later dropped for banners by user decision); right-aligned tabular numerals (j-card); row density at about 28px per row (doujin).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Signature interaction: when filters change, the banners re-hang (each unfurls from the rod in about 260ms). Motion conveys state only; under reduced motion it is instant.

Unresolved: whether GLORY/GLORB extend beyond the four major leagues (product decision, see PRODUCT.md).
