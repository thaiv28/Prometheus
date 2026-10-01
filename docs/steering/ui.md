# UI / Frontend

The site was redesigned with the **impeccable** skill (installed at `~/.claude/skills/impeccable`). Product facts live in `PRODUCT.md`. The visual direction contract lives in `.impeccable/surfaces/templates-metric-dynamic-html-j2.md`. `DESIGN.md` records the built design system. Run `/impeccable <command>` (for example `audit`, `polish`, or `critique`) for future UI work.

## Direction: "The Rafters"

Every team-season is a felt championship banner hanging from a steel rod. All banners hang at the **same length**, with rank, name, league and score stitched on the felt. (An earlier version made length proportional to score, but the differences between top-ten teams weren't noticeable, so it was dropped.) The ground is warm arena charcoal. Color appears only where it encodes a league:

| League | Felt |
|---|---|
| LCK | royal `#24479c` |
| LPL | crimson `#9c2338` |
| LEC | forest `#1f6346` |
| LCS | gold `#c9971f` (dark ink) |
| everything else | neutral `#4a4844` |

The same hue is used for banners, league tags, picker swatches, and the team Elo chart line, all through `[data-league="…"]` in `tokens.css`.

Type: a system UI stack for everything functional (tables, labels, copy). **Graduate**, a self-hosted varsity face, is used for page titles, the wordmark, metric names, and the lettering on banners. Don't use it in table data or controls.

## Pages

| Output | Template | Notes |
|---|---|---|
| `index.html` | `index.html.j2` | Intro, the all-time top ten GLORY banners, and a metric index |
| `glory.html`, `glorb.html`, `game_length_elo.html` | `rankings.html.j2` | Filters, top-ten rafters for the current view, sortable table, and a "How to read" section. Driven by a column config from `build_site.py`. |
| `teams/<slug>.html` | `team.html.j2` | One banner per season with a GLORY/GLORB toggle, an Elo chart (Chart.js), and a season table. Pages exist for all teams with Elo. |

## Behavior

- Filter state (years, leagues, search, sort) is stored in the URL, so filtered views can be shared.
- **Rank** is the position by the page's metric within the current filtered view. It doesn't change when you sort by another column.
- **Signature motion:** when the view changes, the banners re-hang (a clip-path reveal from the rod, about 260ms). It's instant under `prefers-reduced-motion`. No other decorative motion.
- On non-rankings pages, header search submits to the Elo page, which covers every team.
- Every value written by JS goes through `esc()`. Never interpolate raw data into `innerHTML`.

## Rules for future changes

- Keep banners a fixed length. Chart lengths must stay proportional to data.
- New colors go in `tokens.css`. Don't put inline `style=""` in templates except data-driven custom properties (`--n`, `--i`).
- Navigation uses real `<a>` links.
- Check both 1440px and 390px widths after any change. Headless Chrome won't render narrower than 500px; load the page in a 390px iframe to test mobile.

## Known gaps

- There's no light theme. Dark was chosen for the use scene (fans browsing at night), not as a default.
- Chart.js is still loaded from jsDelivr on team pages.
