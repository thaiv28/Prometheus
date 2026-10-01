# UI / Frontend

The site was designed with the **impeccable** skill (installed at `~/.claude/skills/impeccable`). Product facts live in `PRODUCT.md`. The visual direction contract lives in `.impeccable/surfaces/templates-rankings-html-j2.md`. `DESIGN.md` (with `.impeccable/design.json`) records the built design system. Run `/impeccable <command>` (for example `audit`, `polish`, or `critique`) for future UI work.

## Direction: "The Almanac"

Prometheus is set like the annual printed sabermetrics abstract of LoL esports (Bill James's Abstract, Wisden, Baseball-Reference). Every page has a running head over a double rule, a title in the text face, captioned tables and figures, and notes in the outer margin keyed by superscript marks. The ground is flat warm paper (`#f3eee3`) with real ink (`#1b1914`). There is one spot ink, ledger blue `#2342a0`, used only for state and reference (footnote marks, current section, sort mark, focus, traced values). League inks are used only as small square league marks and the Elo line:

| League | Ink |
|---|---|
| LCK | teal `#146a6c` |
| LPL | oxblood `#9a2a2a` |
| LEC | olive `#4a6a1f` |
| LCS | ochre `#8a5d08` |
| everything else | grey `#7a7264` |

All of these come from `tokens.css` through `[data-league="…"]`.

Type: one family, **Source Serif 4** (self-hosted variable woff2, OFL, licence in `site_static/fonts/`). Prose uses old-style figures; tables use lining tabular figures; labels use true small caps.

## Pages

| Output | Template | Notes |
|---|---|---|
| `index.html` | `index.html.j2` | Title, intro, top 15 GLORY team-seasons, best team-season of each year, and the list of rankings in the margin |
| `glory.html`, `glorb.html`, `game_length_elo.html` | `rankings.html.j2` | Title and lede, a distribution figure of the current view, the filter line, the sortable register, and "How to read" notes in the margin. Driven by a column config from `build_site.py` (`note` keys put superscripts on column heads). |
| `teams/<slug>.html` | `team.html.j2` | Franchise entry: fact line, summary sentence, season column chart with a GLORY/GLORB switch, season register with year rank, and an SVG Elo chart. Pages exist for all teams with Elo. |
| `404.html` | `404.html.j2` | "Page not found" with links to the home page and each ranking. Links are root-absolute. |

## Behavior

- Filter state (years, leagues, search, sort) is stored in the URL, so filtered views can be shared.
- **Rank** is the position by the page's metric within the current filtered view. It doesn't change when you sort by another column.
- The table caption describes the current view in words and gives the count.
- Hovering or focusing a row traces its value on the distribution figure.
- **Signature motion:** when the view changes, rows that stay on screen slide from their old position to the new one (about 360ms). Instant under `prefers-reduced-motion`. No other decorative motion.
- The Elo chart is keyboard-readable: focus it and use the arrow keys (Shift for steps of 10, Home/End).
- On non-rankings pages, the header search submits to the Elo page, which covers every team.
- Every value written by JS goes through `esc()`. Never interpolate raw data into `innerHTML`.

## Rules for future changes

- New colors go in `tokens.css`. Don't put inline `style=""` in templates except data-driven custom properties (`--v`, `--n`, `--glory`, `--glorb`).
- No cards, radius, shadows, gradients or paper textures.
- Navigation uses real `<a>` links.
- Check both 1440px and 390px widths after any change. Headless Chrome won't render narrower than 500px; load the page in a 390px iframe to test mobile.

## Known gaps

- Light only; there is no dark mode.
- Copy is plain and direct. Each line should explain a number, a concept, or where to go next; no book-metaphor wording ("register", "edition", "errata") in visible text.
- Phone rows are two lines tall (team, then league and year), so a phone shows about 20 rows per screen.
