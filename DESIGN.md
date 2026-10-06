---
name: Prometheus
description: The annual printed sabermetrics abstract of LoL esports. Every page is a typeset statistical register on uncoated paper.
colors:
  paper: "#f3eee3"
  paper-wash: "#e9e2d2"
  paper-deep: "#ded5c1"
  ink: "#1b1914"
  ink-2: "#4f4a41"
  ink-3: "#6a6458"
  hairline: "#b9ae98"
  hairline-soft: "#d3c9b5"
  spot: "#2342a0"
  spot-wash: "#dfe2ee"
  ink-lck: "#146a6c"
  ink-lpl: "#9a2a2a"
  ink-lec: "#4a6a1f"
  ink-lcs: "#8a5d08"
  ink-other: "#7a7264"
typography:
  title-page:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "clamp(3.25rem, 11vw, 7.5rem)"
    fontWeight: 300
    lineHeight: 0.9
    letterSpacing: "-0.025em"
  display:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "clamp(2.25rem, 5vw, 3.5rem)"
    fontWeight: 400
    lineHeight: 1.02
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "1.625rem"
    fontWeight: 400
    lineHeight: 1.15
  lede:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "1.1875rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "onum, pnum"
  body:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "1.0625rem"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "onum, pnum"
  table:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.3
    fontFeature: "lnum, tnum"
  label:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    letterSpacing: "0.06em"
    fontFeature: "c2sc, smcp, lnum"
  caption:
    fontFamily: "Source Serif 4, Iowan Old Style, Palatino Linotype, Georgia, serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.45
rounded:
  none: "0"
spacing:
  xs: "4px"
  sm: "8px"
  md: "14px"
  lg: "22px"
  xl: "36px"
  section: "44px"
  margin-column: "17rem"
components:
  running-head:
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    padding: "18px 0 12px"
  index-search:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    width: "10rem"
    rounded: "{rounded.none}"
  picker-summary:
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    padding: "3px 0"
  picker-panel:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "12px 14px 14px"
  register-header:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    padding: "7px 10px 5px"
  register-row:
    textColor: "{colors.ink}"
    typography: "{typography.table}"
    height: "1.75rem"
    padding: "4px 10px"
  register-row-hover:
    backgroundColor: "{colors.paper-wash}"
  register-row-traced:
    backgroundColor: "{colors.spot-wash}"
  printed-bar:
    backgroundColor: "{colors.ink-2}"
    height: "5px"
  margin-note:
    textColor: "{colors.ink-2}"
    typography: "{typography.caption}"
    width: "17rem"
---

# Design System: Prometheus

## Overview

**Creative North Star: "The Almanac"**

Prometheus is the annual printed sabermetrics abstract of League of Legends esports, in the line of Bill James's Baseball Abstract, Wisden and the density of Baseball-Reference. Every page is set like a section of that book: a running head over a double rule, a title in the text face, a lede, numbered figures and tables with printed captions, and notes in the outer margin keyed by superscript marks. The table is the product, so it is typeset as a statistical register: booktabs rules, tabular lining figures, a light rule after every fifth row.

The ground is warm uncoated paper and the type is real ink. There is one spot ink, ledger blue, and four restrained league inks that only ever appear as small printed league marks and chart lines. Nothing has a radius, nothing casts a shadow, and no surface is a card.

The world refuses the dark-neon esports stat hub, the card grid, and the parchment costume: there is no paper texture, no stain, no distressing. The paper is a flat color; the craft is in the setting.

**Key Characteristics:**
- One serif family, Source Serif 4 with optical sizes, for everything: old-style figures in prose, tabular lining figures in tables, true small caps for labels.
- Booktabs registers: 2px top and bottom rules, a hairline mid rule, a light rule every five rows, about 28px rows.
- One spot ink (ledger blue) for marks, active state, focus and tracing; league inks only as marks and lines.
- A main column plus a 17rem outer margin for marginalia; on narrow screens the margin follows the main text.
- Small printed figures drawn from the data: a distribution histogram over every register, a column chart and an Elo line on team pages, a short printed bar beside each value.
- One signature motion: register rows re-rank in place when the view changes.

## Colors

Paper and ink, plus one spot and four league inks. The strategy is Restrained.

### Primary
- **Ledger Blue** (spot): footnote marks, the current-section underline, the active sort mark, the open picker, focus outlines, the traced value on the distribution figure, hover on links and bars, the wordmark glyph. Never a fill larger than a mark, except the pale **Spot Wash** (spot-wash) behind a traced row or a targeted note.

### Secondary (league inks)
- **LCK Teal** (ink-lck), **LPL Oxblood** (ink-lpl), **LEC Olive** (ink-lec), **LCS Ochre** (ink-lcs), and **Grey Ink** (ink-other) for every other league. They appear only as the 0.5em square league mark before a league code and as the Elo line on a team page. Each holds at least 4:1 on paper even though they are used as marks, not text.

### Neutral
- **Paper** (paper): the page. **Paper Wash** (paper-wash): row hover, picker option hover. **Paper Deep** (paper-deep): reserved trough tone.
- **Ink** (ink): text, booktabs rules, values, checked boxes. 15:1 on paper.
- **Ink 2** (ink-2): secondary text, margin notes, printed bars and histogram columns. 7.6:1.
- **Ink 3** (ink-3): labels, ranks, trailing counts, muted figures. 5.1:1, the floor for any text.
- **Hairline** (hairline) and **Soft Hairline** (hairline-soft): every-fifth-row rules, dot leaders, chart grid, link underlines at rest. Never text.

### Named Rules
**The One Spot Rule.** Ledger blue marks state and reference: a footnote, a focus, a current section, a traced value. It is never decoration and never a large fill.

**The League Mark Rule.** A league ink appears only as that league's mark or line. Same league, same ink, on every page.

## Typography

**Text Face:** Source Serif 4 (self-hosted variable woff2, weights 300 to 700, optical size 8 to 60, roman and italic, SIL OFL; licence in `site_static/fonts/`), with Iowan Old Style, Palatino and Georgia fallbacks.

**Character:** a transitional text serif with a full figure set and true small caps. Optical sizing makes the 7.5rem title page fine and the 15px table figures sturdy. Italic carries subtitles, caption asides, filter values and the caveat note.

### Hierarchy
- **Title page** (300, clamp 3.25 to 7.5rem, 0.9, -0.025em): the home page name only.
- **Display** (400, clamp 2.25 to 3.5rem, 1.02): page titles (metric name, team name, Page not found). The metric's full name sits under it in italic at 1.1875rem.
- **Headline** (400, 1.625rem, 1.15): section heads on team pages.
- **Lede** (400, 1.1875rem, 1.5, old-style figures): the paragraph under a title, max 40rem.
- **Body** (400, 1.0625rem, 1.5, old-style proportional figures): prose; following paragraphs indent 1.5em instead of adding space.
- **Table** (400, 0.9375rem, 1.3, lining tabular figures): register cells; the value column is 600.
- **Label** (all small caps, 0.06em tracking, lining figures): running head, column heads, margin heads, caption numbers, fact lines.
- **Caption** (0.875rem, 1.45): "Table." and "Figure." captions, with the number in bold small caps.

### Named Rules
**The Figure Rule.** Prose uses old-style figures; anything compared in a column uses lining tabular figures, right-aligned. Signs use a true minus.

**The Small Caps Rule.** Labels are set in true small caps with light tracking, never in faked uppercase.

## Layout

A page is 82rem max with a fluid gutter (16 to 48px). The running head and colophon align to the content edges. Content is a two-column spread: the main column and a 17rem margin, 32 to 56px apart; the margin is sticky on desktop and, when its notes run taller than the window (AURA), scrolls on its own within the window's height (thin scrollbar, no scroll chaining to the page). Under 1000px the margin follows the main column (on the home page, the Contents moves between the intro and the tables). Under 720px the running head stacks (wordmark, sections, full-width index search), registers scroll horizontally edge to edge, wide-only columns hide and their league and year fold under the team name, and fact lines drop their middle-dot separators. Under 480px phone-hide columns drop.

Rhythm: 4px base, captions 8px above their table, 44px between registers, 36px between a page title and its body.

## Elevation & Depth

Flat. Hierarchy comes from rules, weight and the margin, never from shadow. An open picker sits on paper with an ink border and a 2px top rule.

### Named Rules
**The Printed Page Rule.** No shadows, no radius, no gradients, no textures. If it would not print, it does not ship.

## Shapes

Square. Rules are 1 device pixel (0.5px on high-density screens), 2px for booktabs top and bottom, and a 3px double rule under the running head. League marks are 0.5em squares. Checkboxes are 13px ink-bordered squares that fill with ink, inset by paper, when checked. Sort and picker carets are small CSS triangles.

## Components

### Running head
- Wordmark: a ledger-blue P glyph and PROMETHEUS in tracked small caps 600.
- Sections: Home, Predictions (a plain link), then two menus, *Teams* and *Players*, each a small-caps name with a small ink-3 caret (a `<details>`, so it opens without JS; `nav.js` closes the other menu, and closes on a click elsewhere or Escape). Open, the name and caret turn ledger blue and a slip drops under it, set like an open picker (paper, ink border, 2px top rule, 21rem): one line per stat, its name in small caps 600 over the question it answers in italic ink-2 caption size; hover washes the line and turns the name ledger blue. Teams lists GLORY, FORGE and Elo, then, after a hairline, *Sunset stats* in ink-2 regular. Players lists Elo and AURA. A menu's name is marked current (ink 600, 2px ledger-blue underline) on its stat pages, and Teams also on team pages, Sunset stats and retired metrics' pages, Players on player pages; inside the slip the current page's name is underlined the same way. The nav and the search share one line down to 1280px; narrower, the search wraps to its own line. Under 720px the slip spans the full width under the section line and its lines grow to 10px padding.
- Search: a "Find" label and a bare input ("Team or player") on a hairline baseline; focus thickens the baseline to 2px ledger blue. Typing opens a suggestion slip under the field, set like an open picker (paper, ink border, 2px top rule): up to eight teams and players, each a name with its league mark and, in ink-3, the last year (teams) or role and team (players); the highlighted one gets the paper wash and a ledger-blue name. Enter or a click opens the page. With no match the slip says so, and Enter (or no JS) searches the Team Elo register, which lists every team.

### Filter line
- Set as a sentence: "Showing years all, leagues all, team any". The label is small caps, the value italic on a dotted underline, with a caret. Opening turns the value and caret ledger blue.
- The team search is the last clause: a small-caps "team" label and a bare italic input on the same dotted underline, its placeholder *Any* set as a value; focus turns the rule 2px ledger blue. It filters the register by name and is stored in the URL (`?search=`).
- A page that sets `filters.roles` (AURA) adds a *roles* clause before the name search: the same picker, its options the five roles by name (Top, Jungle, Mid, Bot, Support), stored in the URL (`?roles=`); the caption names the chosen roles in brackets ("AURA, all player-seasons (support), 2025").
- Panel: paper, ink border, 2px top rule, small-caps legend, a grid of square checkboxes; leagues carry their mark. "Major four only" and "Clear filters" are italic underlined text buttons.
- Forecast pages (Elo, FORGE) label the year picker "season" and show *Now* as its empty value, the way the others show *All*: the register opens on current ratings for active teams. Its panel (legend "Season's end") leads with a "Current ratings" text button that returns to Now. Choosing seasons switches the register to team-seasons rated at the end of each year, and the caption says so ("Elo, all team-seasons, 2019, rated at season's end").

### Register (signature)
- Booktabs table with a printed caption that describes the current view in words ("GLORY, LCK team-seasons, 2021–2024, ranked by score.") and a count.
- Column heads are sort buttons; the sorted head goes ink 600 with a ledger-blue triangle. Superscript note numbers in heads point at the margin notes.
- A printed bar column sits before the value: a 5px ink-2 rule whose length is the value on a fixed scale for the page.
- Hover washes the row; hovering or focusing a row traces its value on the distribution figure in ledger blue.
- A team column with `mark` (the AURA register) leads each team name with its league mark instead of a League column, so the register fits beside the margin at 1280px; its ellipsis limit is 10rem instead of 11rem. A signed value (Luck, AURA) gets a symmetric scale around 0, and an acronym unit ("AURA scores") keeps its capitals in the figure caption.

### Head to head (FORGE)
- When the two teams play in different leagues, an italic caption-size note under the bar says the odds come from Elo alone.
- Set as a sentence at headline size (lede size on phones): "[team] *beats* [team] **57 times in 100**." Each team is a bare select on an ink baseline with a small caret, sized to the chosen name; its list is grouped by league (LCK, LPL, LEC, LCS, then any other, as `<optgroup>`s), alphabetical within each, with the top two rated teams preselected (`matchup_options` in `_marks.html.j2`, shared by the FORGE page and home); the verb is italic ink-2 and the result is ink 600 with tabular figures.
- Captioned like a figure ("Head to head." in bold small caps) with a note mark to the margin.
- Below it, a 5px printed bar: the first team's share in ink on a paper-deep trough, with a hairline tick at 50%. It does not animate.

### Fixture register (Predictions, home)
- A booktabs register of matches grouped by day: each day opens with a small-caps 600 day row in ink over a hairline ("Tomorrow, Sunday 4 October"; JS sets the visitor's time zone and regroups the days, adding Today, Tomorrow or Yesterday; without JS the days and times are UTC, and the time head says so). Days divide the register, so there is no every-fifth-row rule; only the last visible row closes it with the 2px rule.
- A match row reads time (ink-2, tabular), league mark and code, the first team right-aligned, its series chance, the duel bar, the second team's chance, the second team left-aligned, then Bo and the one-game chance (head "Game"; "62–38", or *same* for a Bo1) in ink-3 small caps and figures, the Kalshi pair (series chances, first team–second team, in ink-2 figures like One game, linked like team names to the match's page on Kalshi; an ink-3 dash when no usable quote; head note 5), and "By" (FORGE, or Elo with *across* in italic for teams from two leagues). The head "Series chance" spans both chances and the bar.
- The duel bar: a 5px paper-deep trough with the first team's share in ink and a hairline tick at 50, the head-to-head bar at row scale (5.5rem). Hover turns the share ledger blue. When Kalshi prices the match, a small ink-2 caret (a 7×5px CSS triangle, not a glyph) sits on the bar's top edge at the market's chance for the first team, so our share and the market's read against each other; the bar's tooltip gives the market's pair and when it was read. Results keep the caret at the last price before the start. `predictions.js` applies the hourly `kalshi.json` over the built prices (caret, pair, link, tooltips) and adds "Kalshi prices as of …" (ink-3, local time) to the upcoming register's caption.
- The favourite's name and chance are ink 600; the other chance is ink-3. In results the winner's name carries the 600 instead, a Result column gives the series score (600), and a Call column says Right (ink) or *Missed* / *To come* (ink-3 italic). A call rebuilt after the match carries note mark 3. Results drop Bo, Game, Kalshi and By to fit beside the margin at 1280px (the best-of is the score's tooltip, the method and the market's pair the bar's).
- Team names link to team pages when we have one; long names ellipsize at 9rem, with the full name as the cell's tooltip.
- The register fits its column, never scrolling sideways: a container query on its scroller drops By and Game under 840px of room, folds the league into the time cell under 700px, and narrows names to 8, 7 and 6.25rem.
- Under 720px the League and By columns drop (Game and Kalshi drop under 600px with the other phone-hide cells; the caret stays) and the league mark follows the time. Under 600px each match becomes two lines inside the same table markup: time and mark (caption size) with Bo, or score and call, at the right; then the two teams with their chances either side of a 3rem bar. Matches are divided by soft hairlines.
- The home page's compact version (no notes, no By) sits in the FORGE spotlight under the head-to-head box.

### The record so far (Predictions)
- A short register: rows for calls saved before the match, reconstructed calls and all (the total under an ink hairline, in 600); columns series, favourite won (%), games, picked (%), log loss. A prose sentence above it says the saved record in words. No hero number.

### Distribution figure
- A histogram of every entry in the current view on the page's fixed scale: ink-2 columns on a ruled axis with tabular tick labels and a dashed median with an italic label.
- A traced row draws a 2px ledger-blue rule at its value, with the name and value in ledger blue 600 in the band above the tallest column, knocked out of the rules with a paper stroke. The columns never cover it. While it would collide with the median label, the median keeps its line and drops its label.

### Sunset stats page
- Title and lede, then the retired metrics as a dot-leader contents list (name, full name in italic) with a "Why sunset." line in bold small caps.

### Sunset note
- A retired metric's page carries an italic caption-size note under the lede, set between two hairlines like an erratum slip and led by "Sunset." in bold small caps. It says why the metric was retired and what to use instead.

### Franchise entry (team pages)
- Name in display size; a small-caps fact line (league marks, seasons ranked, FORGE now, Elo); a prose summary with the best season, its year rank, and the Elo peak.
- Figure 1: printed column chart of GLORY by season (0 to 100).
- Season register: year, league, GLORY, year rank ("2nd of 47", or "Unranked" when the season had fewer than 5 games) and season-end FORGE. Under 480px the league column drops.
- Rosters: "Roster" (or "Last roster" for a team not active in six months), a three-column register of the last lineup (role in ink-3, player, Elo); then starters by season: year and one column per role, the main starter in body type and others under it at caption size with games started in ink-3, "+N more" past three. Under 480px the season table becomes a list: the year in 600, then a line per role with the role in ink-3 in a 4.75rem column; seasons are divided by hairlines.
- Figure 2: hand-drawn SVG Elo line in the league ink, dashed 1500 rule, annotated peak, and a pointer and arrow-key readout.

### Player entry (player pages)
- Set like the franchise entry: name in display size; a small-caps fact line (role, league mark, "Plays for" or "Last played for" the team, Elo); a prose summary with the peak, the latest rating, games, teams and other names, and the best AURA season ("Best AURA season 2021, +10.6 a game, 2nd of 52 major-league mid laners that year.") when there is one.
- Figure 1: the same SVG Elo line as team pages.
- AURA by season (players with major-league snapshot games), between the Elo figure and the career register: a block head with "See in AURA rankings", a caption, and a register of year, team, league, role, games, AURA (signed, 600) and role rank ("1st of 31", ink-3, or *Unranked* under 20 games), newest first, one row per season and role. Under 480px league and role drop. A margin note (4) explains AURA.
- Career register: one row per run of games with a team (team, league, role, from, to, games, Elo at the end), newest first. Under 480px league, role and "to" drop.

### Home
- Title page, then a lede naming the three things the site answers (FORGE, Elo, GLORY), each linked.
- The forecast leads: a *FORGE* head at 1.875–2.5rem with its question in italic under it, the head-to-head box (same component as the FORGE page; the top two teams preselected), and Table I, the top 10 major-league teams playing now (rating, Form, Elo).
- Under the head-to-head box, *Coming up*: the compact fixture register of the next 10 major-league and international matches within four days, captioned with a link to the Predictions page (or a one-line caption when there are none).
- Then Table II, Team Elo's top 10 teams playing now in every region, and Table III, Player Elo's top 10 players. Bars use the same scale as each metric's own page.
- Contents in the margin: two parts, *Teams* and *Players*, each a small-caps 600 head (the second after a hairline), listing every stat: name and count on a dot leader, its question in italic, then its description. Under 1000px the order is lede, FORGE, contents, then the Elo tables.

### Predictions page
- Title "Predictions" with its full name in italic, a lede, then the filter line (leagues, defaulting to the major leagues and international events, the picker reading *Majors*, with that shortcut and an "All leagues" one, and a team search; state in the URL as `?leagues=` (omitted for the default, `all` for every league) and `?search=`; hidden without JS, when every row shows; *Clear filters* returns to the default), *Coming up* (Table I, fixture register), *How the calls have done* (one line of prose; Table II, the record; Table III, against Kalshi, and Table IV, paper bets by edge, share one layout: FORGE and Elo row groups (the name once, a hairline between groups), each with a *Saved* source (calls made before the match) and a *Backtest* source (calls rebuilt after it; Table III's caption gives its dates and says the forecast weights saw those games), in italic ink-2 with a dotted hairline between them; under 600px the Calls column folds into Source ("FORGE, Saved"). Table III: Series, "Favourite won" and "Log loss" spanning Ours and Kalshi columns, and a Difference column with its interval in ink-3 (*too few* until 30 series; the interval on its own line under 600px). Table IV: edges *Any* (every match, backing our pick; Table III's matches) and > 0 / 3 / 5 / 10, Bets, Won, Return and CLV with intervals in ink-3, Beat close; Won and Beat close phone-hide; then one line on the alerts) and *Results* (Table V, the last three days' results, newest first, an "Every call as data" link to `predictions.json`, then a *By month* line of links to the results pages).

### Results pages
- `results/YYYY-MM.html`, one per month with a played match: title "Results" with the month in italic, a one-line lede linking back to Predictions, the same filter line, the month's fixture register with results (newest first), links to the months either side, and a margin note on reading the bar, the caret and note 3. Margin: "How to read the predictions", five notes (the fifth on Kalshi's prices) and the caveat. Counts under each table follow the filters; a filter that empties a table shows an italic line between two heavy rules.

### Margin notes
- Small-caps head over an ink rule; numbered notes with ledger-blue marks; the dagger note is the caveat, in italic. A targeted note gets the spot wash.

### Motion
- Rows re-rank in place: rows that stay in view slide from their old position to their new one over 360ms with cubic-bezier(0.16, 1, 0.3, 1). Instant under reduced motion.

## Do's and Don'ts

### Do:
- **Do** set every comparable number in lining tabular figures, right-aligned, with a true minus.
- **Do** caption every table and figure in words that say what is in view.
- **Do** key caveats and definitions to the margin with superscript marks.
- **Do** keep league inks to marks and lines, and ledger blue to state and reference.
- **Do** keep rows near 28px with a light rule every fifth row.

### Don't:
- **Don't** add cards, radius, shadows, gradients or paper textures.
- **Don't** introduce a second typeface; Source Serif 4 carries display, text, tables and labels.
- **Don't** use a league ink or ledger blue as a fill or for emphasis.
- **Don't** put a label or eyebrow above a heading.
- **Don't** animate anything other than the re-rank and the season switch.
