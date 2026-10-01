---
version: 1
slug: "templates-rankings-html-j2"
primary_target: "templates/rankings.html.j2"
related_targets: ["templates/base.html.j2","templates/index.html.j2","templates/team.html.j2","templates/404.html.j2"]
---

# Surface brief: Prometheus site (all pages)

Scope: the whole static site: home, the three rankings pages (GLORY, GLORB, Game-Length Elo), one page per team, and 404. Visitor mode: **Operate** (rankings, team pages) with a **Read** home and explainers. Fans look up, filter, sort and share team rankings; the home page orients them and shows the all-time leaders.

Audience/job: LoL esports fans settling cross-era and cross-region arguments, on desktops and on phones from Discord/Reddit links. Task: find a team-season, see its rank and why, share the filtered view by URL. Secondary: portfolio readers judging the methodology.

Constraints: static, Jinja2 + hand-written CSS + vanilla JS, no build step. Tables stay semantic, sortable, keyboard-usable. Oracle's Elixir attribution stays visible. Fonts self-hosted.

## Direction contract

THESIS: Prometheus is the annual printed sabermetrics abstract of LoL esports, in the line of Bill James's Abstract, Wisden and Baseball-Reference: a typeset statistical register, not a dashboard. It refuses the dark-neon esports stat hub and the card grid.

OWN-WORLD: Warm uncoated paper, real ink black, one spot ink (ledger blue) for marks, active state and focus, and four restrained league inks used only as small league marks and chart lines. One serious text serif (Source Serif 4, optical sizes) does everything: old-style figures in prose, tabular lining figures in tables, true small caps for labels and running heads. Hairline rules at one device pixel, a heavier rule every fifth table row, no radius, no shadow. Marginalia carry footnoted caveats and tiny printed charts.

STORY: The visitor reads a running head and a title like a book section, sees the register immediately, narrows it by year and league, reads the exact figures, and follows a dagger to the caveat in the margin.

FIRST VIEWPORT: Running head (wordmark left, section small caps, folio-style nav and an index search right). On rankings pages: section title with full name, a two-line lede, a "Figure" distribution strip of the current view's values printed in hairlines, the filter line set as a sentence of small-caps controls, then the register table whose first rows are inside the first 1080p viewport. The margin column (desktop) holds the how-to-read notes keyed by superscript marks. On the home page: a title-page block (name, subtitle, edition line), then Table I, the all-time GLORY leaders, beside a table of contents with dot leaders.

FORM: The Almanac (brief-pinned by the user; it beats the roll). Seed key c6c0f019 assigned grounded index 4; the user's pinned world overrides it. Raises: from the centre-rail reference setting, every rule drawn at one device pixel and states as printed marks (bracketed focus, filled pressed, no radius); from the Japanese high-density site, density courage (about 26px rows, no whitespace inflation); from the gate board, rows re-rank in place on filter change (row identity kept, top rows slide to their new position) as the one signature motion, instant under reduced motion. Declined: the catalog sleeve and the vertical feed.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Unresolved: whether GLORY/GLORB extend beyond the four major leagues (product decision, see PRODUCT.md).
