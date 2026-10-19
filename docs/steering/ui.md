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
| `index.html` | `index.html.j2` | Title, intro, the FORGE spotlight (head-to-head box, *Coming up* major-league and international matches, top 10 major-league teams playing now), the top 10 of Team Elo and Player Elo, and every stat with its question in the margin |
| `glory.html`, `forge.html`, `form.html`, `game_length_elo.html` (Team Elo), `player_elo.html` (Player Elo, `entity: "player"`: player, role and team columns), `aura.html` (AURA, a player-season register with a role filter, league marks on the team column and a symmetric scale), and the sunset `record.html`, `luck.html`, `glory_unadjusted.html` and `glorb.html` | `rankings.html.j2` | Title and lede (plus a sunset note for a retired metric), a distribution figure of the current view, the filter line, the sortable register, and "How to read" notes in the margin. Driven by a column config from `prometheus/site/config.py` (`note` keys put superscripts on column heads; `domain` fixes the value scale, as for Luck; a metric's `value_word`/`value_plural` name it in captions). |
| `predictions.html` | `predictions.html.j2` | Upcoming matches between rated teams (fixture register, `fixtures` macro in `_marks.html.j2`), live matches and seven days of results; league and team filters in `predictions.js`, which also sets local times and regroups days (also loaded on home for the *Coming up* table). |
| `market-blend.html` | `market_blend.html.j2` | Short methodology linked from Blend; formula/fit in a native disclosure, policy and validation limits visible. |
| `alerts.html` | `alerts.html.j2` | Saved alert ledger, linked from Predictions: original odds, outcomes and after-fee profit, grouped by six fixture types; earlier unposted records separate; totals and compact phone rows. |
| `call-performance.html` | `call_performance.html.j2`, `_call_edges.html.j2` | Every edge threshold by fixture group and Saved/Backtest, with expandable detailed historical calls. Record and market comparisons precede blended signals and raw threshold comparisons. |
| `live.html` | redirect | Redirects to Predictions. Its Live now register is filled by `live_overview.js` from `live/index.json`; rows open Watch. |
| `watch.html` | `watch.html.j2` | One match (`?match=`): a strip of every match in progress above the stream (clock, score, our call and Kalshi's), then the stream (YouTube, Twitch or a co-stream; picker in its bar) with one line of facts and status under it and, beside it, the series' map picker, the odds (live first and largest: our in-game call and Kalshi now; then before the map: FORGE and Kalshi's close; each a pair of figures either side of a duel bar), Figure 1 (chance over game time: our calls as a step line with points, Kalshi as a stepped line on its spread, gold lead as columns below), the scoreline and the series line; between games, the next fixtures. Filled by `live.js` from `live/index.json` and the match's file. |
| `predictions.json` | — | Every matched entry of the prediction log (calls, method, result). |
| `teams/<slug>.html` | `team.html.j2` | Franchise entry: fact line, summary sentence, GLORY season column chart, season register (GLORY, year rank, season-end FORGE), rosters (the last lineup with player Elo, then starters by season and role), and an SVG Elo chart. Pages exist for all teams with Elo. |
| `players/<slug>.html` | `player.html.j2` | Player entry: fact line (role, league, team, Elo), summary (peak, latest, games, teams, other names, best AURA season), the SVG Elo chart (shared `team.js`), an AURA by season register (when the player has major-league snapshot games), and a career register of team stints. For listed players only (see tech.md). |
| `sunset.html` | `sunset.html.j2` | Retired metrics (`METRICS` entries with a `sunset` note, plus `FOLDED` entries that point at their replacement) with links and why each was retired. The Teams menu ends with a "Sunset stats" link here instead of listing the metrics. |
| `glory_plus.html`, `glorelo_plus.html` | `redirect.html.j2` | Meta-refresh to `glory.html` (GLORY+ was folded into GLORY) and to `forge.html` (GlorELO+ was renamed FORGE), with a link and canonical URL. |
| `404.html` | `404.html.j2` | "Page not found" with links to the home page, each ranking and Sunset stats. Links are root-absolute. |
| `teams.json` | — | Team index for the header search: name, slug, league, last game; major-league teams first, then newest. |
| `players.json` | — | Player index for the header search: name, slug, role, team, league, last game; major-league players first, then newest. |

## Behavior

- Filter state (years, leagues, search, sort) is stored in the URL, so filtered views can be shared.
- **Rank** is the position by the page's metric within the current filtered view. It doesn't change when you sort by another column.
- The table caption describes the current view in words and gives the count.
- Hovering or focusing a row traces its value on the distribution figure; the name and value sit in the band above the columns, and the median label hides while they would collide.
- **Signature motion:** when the view changes, rows that stay on screen slide from their old position to the new one (about 360ms). Instant under `prefers-reduced-motion`. No other decorative motion.
- The Elo chart is keyboard-readable: focus it and use the arrow keys (Shift for steps of 10, Home/End).
- The header search (`search.js`, every page) suggests teams and players from `teams.json` and `players.json` (teams first on equal matches) and opens the page. With no match, or without JS, it submits to the Team Elo page, which lists every team.
- Rankings pages filter the register by name with the search box in the filter line (on Player Elo it also matches the team).
- The live page shows every number as it arrives. Hovering Figure 1, or focusing it and using the arrow keys, traces a moment (ledger-blue rule) and the scoreline shows that moment. On phones the stream stays at the top while the rest scrolls. With no game in the feed the stream still plays and the odds column says the numbers come when a map starts. On desktop the page widens to the window and the stream is sized so it and the odds fit without scrolling. A control bar on the stream's top edge holds the stream picker and a *Full screen* icon (only the stream; the bar and a see-through copy of the odds float over the video on any movement and fade after 3 s; a clear layer over the video, short of the player's control strip, catches the movement because the video's frame swallows pointer events). `live.js` writes text with `textContent` only.
- Every value written by JS goes through `esc()`. Never interpolate raw data into `innerHTML`.

## Rules for future changes

- Link CSS and JS through `asset()` in templates. It adds a content hash (`?v=`), so a browser never pairs new HTML with a cached old stylesheet.
- New colors go in `tokens.css`. Don't put inline `style=""` in templates except data-driven custom properties (`--v`, `--n`, `--glory`, `--record`).
- No cards, radius, shadows, gradients or paper textures.
- Navigation uses real `<a>` links.
- Check both 1440px and 390px widths after any change. Headless Chrome won't render narrower than 500px; load the page in a 390px iframe to test mobile.

## Copy

**Required for every UI change:** review the whole affected page, including generated text, at desktop and phone widths. Record `Copy review: PASS`, the surfaces reviewed and the cuts made (or why the copy is already minimal) in the work log and PR checklist before finishing. This applies even when the requested change is visual rather than textual. See `AGENTS.md` for the completion gate.

Every word on the site must be necessary; more text is not better (the owner, 2026-10-06 and 2026-10-08). For any lede, caption, label, margin note, tooltip or status line: draft it, cut it by about half, then check each remaining phrase. Is it said elsewhere on the page? Does a column head, key or tooltip already cover it? Prefer a number or a label to a sentence. Keep method detail in the README and the reports, not on the page; keep the one caveat that matters. No book-metaphor wording ("register", "edition", "errata") in visible text. Predictions follows this with short captions, definition-only margin notes, and no prose repeating table values; retain the backtest bias caveat and the net > 0 selection rule.

## Known gaps

- Light only; there is no dark mode.
- Phone rows are two lines tall (team, then league and year), so a phone shows about 20 rows per screen.

The feed includes preparing fixtures while the worker runs; Predictions shows live and between-game matches. Their Watch URL stays the same when map data arrives; the stream remains visible, with a short waiting status and no empty scoreline or chart.

Live uses persisted confirmed series states, so Coming up stays current after
reloads and Finished links newly recorded completed series to Watch immediately.
The daily archive takes over once its richer result row exists.
