---
version: 1
slug: "templates-live-html-j2"
primary_target: "templates/live.html.j2"
related_targets: ["site_static/js/live_overview.js","site_static/css/live.css"]
---

# Live overview (`live.html`)

Scope: the Live home: every pro match in progress, as numbers, each opening its watch page. Mode: Operate (scan which games are on and how they stand, then pick one). Visitors: fans checking several leagues at once, often during overlapping LCK/LPL or LEC/LCS slates. Data: `live/index.json` (one summary per match, written by the lol-live collector), polled every few seconds; the build adds the next fixtures. Constraints: Almanac unchanged; probabilities only at verified checkpoints; numbers are the feed's latest (no stream delay here, since nothing is being watched on this page).

## Direction contract

THESIS: the live slate as one statistical register, the Predictions fixture register made live: a row per match, read across. It refuses the esports scores hub (cards of team logos, a hero match, colour-coded live badges).

OWN-WORLD: the Almanac unchanged: paper, ink, ledger blue for state; league marks; booktabs rules; the fixture register's duel bar with Kalshi's caret; tabular lining figures; italic ink-3 for basis notes ("at 15′", "before the map").

STORY: the visitor sees every match in progress at once, which team leads each and by how much (our call, Kalshi, gold, kills, objectives), and opens one to watch it.

FIRST VIEWPORT: running head; the page title "Live" with a one-line status ("4 matches in progress, updated 3 s ago"); Table I, the live register: game clock and map, league mark, first team right-aligned, our chance, duel bar with Kalshi's caret, second chance, second team, series score and best-of, Kalshi's pair, gold lead, kills, towers, dragons, barons, and "Watch"; the whole row opens the match. Below: Coming up (the build's fixtures), then notes.

FORM: "The scoreboard register", 1 of 7 on the ordered list; surface seed key 94ae1178.

Signature interaction: rows keep a fixed order (majors first, then by league) so a match doesn't move under the pointer; hovering a row washes it and turns its bar ledger blue, as on the fixture register.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
