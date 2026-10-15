---
version: 1
slug: "templates-watch-html-j2"
primary_target: "templates/watch.html.j2"
related_targets: ["site_static/js/live.js","site_static/css/live.css"]
---

# Watch page (`watch.html?match=…`)

Scope: one match with its stream, inside the Live pages. Mode: Operate (watching a map and reading the odds while it plays). Visitors: fans watching a pro map, often on a second screen or a co-stream, sometimes following two leagues at once. Data: `live/index.json` (every match in progress) and `live/<match>.json` (the watched one), polled every few seconds; written by the lol-live collector. Constraints: Almanac world unchanged; stats arrive ahead of the video, so a viewer-set delay holds the watched match back; probabilities only at verified checkpoints (pre-game FORGE, 10/15/20 gold+Elo), never interpolated.

## Direction contract

THESIS: the live game as a plate (the stream) beside a small printed odds table, with the day's other matches always one click away. It refuses the esports-overlay default (dark HUD, neon win-prob ribbon, stat cards around the player).

OWN-WORLD: the Almanac: paper, ink, one ledger-blue spot for state, league inks only as marks. The stage is an ink block: a control bar (paper type, small-caps labels) as its top edge, then the stream. Odds are a booktabs table of duel bars; Figure 1 is a hand-drawn SVG of our calls (ink steps) and Kalshi (ink-2 stepped line on its spread) with gold-lead columns. The match strip is a row of printed chips divided by hairlines; the watched one carries a 2px ink top rule.

STORY: the visitor sees which matches are on and picks one; watches it with numbers that never run ahead of the picture; reads at a glance who leads by our call and the market, live and before the map; switches matches or streams and the odds follow.

FIRST VIEWPORT: running head; the match strip (All matches, then a chip per match: league, clock, score, duel bar, "73 ours · 77 Kalshi"); the stage, sized so stage and odds fit the window, with its bar (Watching, Delay, full screen); the odds column level with it (Live: ours, Kalshi now; Before the map: FORGE, Kalshi close); under the stream the fact line and status.

FORM: "The chance figure", 3 of 7 on the original ordered list (surface seed key d046b4a7); since reshaped by the owner to odds table, one wide layout, control bar, full-screen overlay and match strip.

Signature interaction: tracing Figure 1 (pointer or arrow keys) shows that moment in the scoreline; in full screen the bar and odds float in on any movement and fade after 3 s.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
