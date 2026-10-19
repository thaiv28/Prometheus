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
- Small printed figures drawn from the data: a distribution histogram over every register, an Elo line and a column chart on team pages, a short printed bar beside each value.
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

A page is 82rem max with a fluid gutter (16 to 48px). The running head and colophon align to the content edges. Content is a two-column spread: the main column and a 17rem margin, 32 to 56px apart; the margin is sticky on desktop and, when its notes run taller than the window (AURA), scrolls on its own within the window's height (thin scrollbar, no scroll chaining to the page). Under 1000px the margin follows the main column (on the home page, the Contents moves between the intro and the tables). Predictions, Call performance and the results months (`spread--wide`) move it under the main column below 1280px, so their registers never scroll on a laptop. Under 720px the running head stacks (wordmark, sections, full-width index search), registers scroll horizontally edge to edge, wide-only columns hide and their league and year fold under the team name, and fact lines drop their middle-dot separators. Under 480px phone-hide columns drop.

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
- Sections: Home, Predictions and Props (plain links), then two menus, *Teams* and *Players*, each a small-caps name with a small ink-3 caret (a `<details>`, so it opens without JS; `nav.js` closes the other menu, and closes on a click elsewhere or Escape). Open, the name and caret turn ledger blue and a slip drops under it, set like an open picker (paper, ink border, 2px top rule, 21rem): one line per stat, its name in small caps 600 over the question it answers in italic ink-2 caption size; hover washes the line and turns the name ledger blue. Teams lists GLORY, FORGE and Elo, then, after a hairline, *Sunset stats* in ink-2 regular. Players lists Elo and AURA. A menu's name is marked current (ink 600, 2px ledger-blue underline) on its stat pages, and Teams also on team pages, Sunset stats and retired metrics' pages, Players on player pages; inside the slip the current page's name is underlined the same way. The nav and the search share one line down to 1280px; narrower, the search wraps to its own line. Under 720px the slip spans the full width under the section line and its lines grow to 10px padding.
- Search: a "Find" label and a bare input ("Team or player") on a hairline baseline; focus thickens the baseline to 2px ledger blue. Typing opens a suggestion slip under the field, set like an open picker (paper, ink border, 2px top rule): up to eight teams and players, each a name with its league mark and, in ink-3, the last year (teams) or role and team (players); the highlighted one gets the paper wash and a ledger-blue name. Enter or a click opens the page. With no match the slip says so, and Enter (or no JS) searches the Team Elo register, which lists every team.

### Filter line
- Set as a sentence: "Showing years all, leagues all, team any". The label is small caps, the value italic on a dotted underline, with a caret. Opening turns the value and caret ledger blue.
- The team search is the last clause: a small-caps "team" label and a bare italic input on the same dotted underline, its placeholder *Any* set as a value; focus turns the rule 2px ledger blue. It filters the register by name and is stored in the URL (`?search=`).
- A page that sets `filters.roles` (AURA) adds a *roles* clause before the name search: the same picker, its options the five roles by name (Top, Jungle, Mid, Bot, Support), stored in the URL (`?roles=`); the caption names the chosen roles in brackets ("AURA, all player-seasons (support), 2025").
- Panel: paper, ink border, 2px top rule, small-caps legend, a grid of square checkboxes; leagues carry their mark. "Major four only" and "Clear filters" are italic underlined text buttons.
- FORGE rates each league on its own scale, so its league clause is singular ("league *Majors*") and its panel (legend "One league's scale") is a list of radio squares, styled like the checkboxes: *Major leagues* across the top, then every league. The register opens on the majors; *Clear filters* returns there. A team search reaches every league and ranks each team within its own.
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
- A match row reads time (ink-2, tabular), league mark and code, the first team right-aligned, its series chance, the duel bar, the second team's chance, the second team left-aligned, then Bo and the one-game chance (head "Game"; "62–38", or *same* for a Bo1) in ink-3 small caps and figures, the Kalshi pair (series chances, first team–second team, in ink-2 figures like One game, linked like team names to the match's page on Kalshi; an ink-3 dash when no usable quote; head note 4), and "By" (FORGE, or Elo with *across* in italic for teams from two leagues). The head "Series chance" spans both chances and the bar.
- The duel bar: a 5px paper-deep trough with the first team's share in ink and a hairline tick at 50, the head-to-head bar at row scale (5.5rem). Hover turns the share ledger blue. When Kalshi prices the match, a small ink-2 caret (a 7×5px CSS triangle, not a glyph) sits on the bar's top edge at the market's chance for the first team, so our share and the market's read against each other; the bar's tooltip gives the market's pair and when it was read. Results keep the caret at the last price before the start. `predictions.js` applies the hourly `kalshi.json` over the built prices (caret, pair, link, tooltips) and adds "Kalshi prices as of …" (ink-3, local time) to the upcoming register's caption.
- The favourite's name and chance are ink 600; the other chance is ink-3. In results the winner's name carries the 600 instead, a Result column gives the series score (600), and a Call column says Right (ink) or *Missed* / *To come* (ink-3 italic). A call rebuilt after the match carries note mark 3. Results drop Bo and Game (the best-of is the score's tooltip, the method the bar's) and show Kalshi's closing line instead: a *Close* column (last price before the start, the pair linked to Kalshi like the upcoming Kalshi column, head note 4) before Result. In results the league folds into the time cell under 840px of room and Close drops under 660px (and on phones), so it stays from about 800px windows up, except where the margin squeezes the column (about 1001–1050px).
- Team names link to team pages when we have one; long names ellipsize at 9rem, with the full name as the cell's tooltip.
- The register fits its column, never scrolling sideways: a container query on its scroller drops Game under 840px of room, folds the league into the time cell under 700px, and narrows names to 8, 7 and 6.25rem.
- Under 720px the League column drops (Game and Kalshi drop under 600px with the other phone-hide cells; the caret stays) and the league mark follows the time. Under 600px each match becomes two lines inside the same table markup: time and mark (caption size) with Bo, or score and call, at the right; then the two teams with their chances either side of a 3rem bar. Matches are divided by soft hairlines.
- The home page's compact version (no head notes) sits in the FORGE spotlight under the head-to-head box.

### The record so far (Call performance)
- A short register: rows for calls saved before the match, reconstructed calls and all (the total under an ink hairline, in 600); columns series, favourite won (%), games, picked (%), log loss. No hero number.

### Distribution figure
- A histogram of every entry in the current view on the page's fixed scale: ink-2 columns on a ruled axis with tabular tick labels and a dashed median with an italic label.
- A traced row draws a 2px ledger-blue rule at its value, with the name and value in ledger blue 600 in the band above the tallest column, knocked out of the rules with a paper stroke. The columns never cover it. While it would collide with the median label, the median keeps its line and drops its label.

### Sunset stats page
- Title and lede, then the retired metrics as a dot-leader contents list (name, full name in italic) with a "Why sunset." line in bold small caps.

### Sunset note
- A retired metric's page carries an italic caption-size note under the lede, set between two hairlines like an erratum slip and led by "Sunset." in bold small caps. It says why the metric was retired and what to use instead.

### Franchise entry (team pages)
- Name in display size; a small-caps fact line (league marks, seasons ranked, FORGE now, Elo); a prose summary with the best season, its year rank, and the Elo peak.
- Sections in order: Elo, Season by season, Roster, Games.
- Figure 1: hand-drawn SVG Elo line in the league ink, dashed 1500 rule, annotated peak, and a pointer and arrow-key readout.
- Figure 2: printed column chart of GLORY by season (0 to 100).
- Season register: year, league, GLORY, year rank ("2nd of 47", or "Unranked" when the season had fewer than 5 games) and season-end FORGE. Under 480px the league column drops.
- Rosters: "Roster" (or "Last roster" for a team not active in six months), a three-column register of the last lineup (role in ink-3, player, Elo); then starters by season: year and one column per role, the main starter in body type and others under it at caption size with games started in ink-3, "+N more" past three. Under 480px the season table becomes a list: the year in 600, then a line per role with the role in ink-3 in a 4.75rem column; seasons are divided by hairlines.
- Games (the game log, shared with player pages; see below).

### Player entry (player pages)
- Set like the franchise entry: name in display size; a small-caps fact line (role, league mark, "Plays for" or "Last played for" the team, Elo); a prose summary with the peak, the latest rating, games, teams and other names, and the best AURA season ("Best AURA season 2021, +10.6 a game, 2nd of 52 major-league mid laners that year.") when there is one.
- Figure 1: the same SVG Elo line as team pages.
- AURA by season (players with major-league snapshot games), between the Elo figure and the career register: a block head with "See in AURA rankings", a caption, and a register of year, team, league, role, games, AURA (signed, 600) and role rank ("1st of 31", ink-3, or *Unranked* under 20 games), newest first, one row per season and role. Under 480px league and role drop. A margin note (4) explains AURA.
- Career register: one row per run of games with a team (team, league, role, from, to, games, Elo at the end), newest first. Under 480px league, role and "to" drop.
- Then Games, the game log.

### On this page (team and player pages)
- At the top of the sticky margin, above Key terms: a small-caps "On this page" head over an ink rule, then one line per section set like a book's contents: name in ink-2, a dotted hairline leader, and a figure in ink-3 tabular (latest Elo, seasons, stints, games; none for Roster). The section in view is marked like the current menu (ink 600, 2px ledger-blue underline). Under 1000px the margin copy hides and a second copy sits under the entry head as a wrapped line of names and figures, no head or leaders.

### Game log (team and player pages)
- Block head "Games" with an italic count ("1,325 games in 532 series since 2015"); a "Seasons" line (small-caps label, underlined years) that jumps to any year, loading the whole log first if needed; a caption; then a booktabs register drawn by `entry.js`.
- Team columns: date, opponent (league mark only, an italic ink-3 *v*, the linked name, ellipsized at 13rem), result, length, Ours, Kalshi, Elo ±, starting five. Player columns: date, team, opponent, result, champion, AURA, Ours, Kalshi, Elo ±.
- Year rows divide the log (there is no every-fifth-row rule): the year in small caps 600 over an ink hairline, with "22–24 in series, 52–61 in games" in ink-3 at caption size.
- A series row: date ("4 Sep"), opponent, result (**W** in ink 600 or L in ink-3, then the score in ink-2), our chance for the team (FORGE in roman, Elo in ink-2 *italic*), Kalshi's chance linked to the match in ink-2, the Elo change signed with a true minus, and the five starters at caption size, each name followed by a hairline middot (outside its link). The five take only the width the other columns leave and wrap between names, never inside one, so a long lineup runs to a second line; a name longer than 12em ends in an ellipsis with the full name as its title. Series are divided by soft hairlines. A one-game series is a single row with its length (and champion and AURA on player pages).
- Game rows under a longer series: caption size, ink-2, 1.5rem tall: "Game 2" indented in ink-3, the side in italic ink-3 (with the length on player pages), result, length, our game chance, the Elo change, and the five only when they changed from game 1.
- Under the register, "Show every series (532)" as an italic underlined text button; it loads `games/<kind>s/<slug>.json`, says so while loading and offers a retry on failure. Between 1001px and 1280px (beside the margin) the length column drops and opponents ellipsize at 10rem; each game row keeps its side and length as a tooltip. The five keep a 13rem floor (18rem under 720px); past the column the register scrolls sideways inside its figure, never into the margin. Under 480px the length column drops.

### Home
- Title page, then a lede naming the three things the site answers (FORGE, Elo, GLORY), each linked.
- The forecast leads: a *FORGE* head at 1.875–2.5rem with its question in italic under it, the head-to-head box (same component as the FORGE page; the top two teams preselected), and Table I, the top 10 major-league teams playing now (rating, Form, Elo).
- Under the head-to-head box, *Coming up*: the compact fixture register of the next 10 major-league and international matches within four days, captioned with a link to the Predictions page (or a one-line caption when there are none).
- Then Table II, Team Elo's top 10 teams playing now in every region, and Table III, Player Elo's top 10 players. Bars use the same scale as each metric's own page.
- Contents in the margin: two parts, *Teams* and *Players*, each a small-caps 600 head (the second after a hairline), listing every stat: name and count on a dot leader, its question in italic, then its description. Under 1000px the order is lede, FORGE, contents, then the Elo tables.

### Predictions page
- Predictions: title and freeze lede with a Record link; hidden-until-active Live now register (Table I); filters and Coming up (Table II); compact Results for seven days (Table III), download and month links. Record and Kalshi comparison are Tables I–II on Call performance; existing edge tables follow as III–IV. The method stays in the duel tooltip and notes.

### Market Blend methodology

`market-blend.html` uses the existing Almanac headings and prose widths. Short estimate, signal and evidence sections; native disclosure holds formula, fit protocol and current coefficients. Linked from Blend, Predictions notes and Call performance. Keep the replay/profitability caveat; no new tokens or ranking page. Kelly copy describes capped bets without specifying order granularity; exact execution precision belongs in the execution guide.

### Props page
- Title "Props" with its full name in italic, a one-line lede ending "Lines as of …" (local time via `props.js`), then a filter line: a *stat* picker (radio list: Kills, Assists, Deaths, CS; `?stat=`) and a "with lines only" square checkbox, checked by default (`?lines=all` shows every match). Without JS the page shows kills and, already, only the matches with kills lines.
- *Coming up*: one block per match, soonest first. The match head sets the teams at headline size (an italic ink-3 *v* between them, names linked to team pages) with the local day and time in small caps ink-2 after them; under it a caption-size fact line in ink-3: league mark, Bo, our series chance as a pair ("74–26").
- Under it, one register per stat ("Table 1a. Kills, maps 1–3."; only the chosen stat shows): Player (linked), Last 10 (ink-2), Ours (median in 600 with the 10–90 range in ink-3 at 0.875em), then one column per app. Each team opens with a small-caps 600 row over a hairline, as days do in the fixture register; no every-fifth-row rule.
- The line cell: the line number, a 3rem meter (a 5px paper-deep trough, our chance of the over in ink-3, two hairline ticks at the break-even either side of 50: the band between them is no edge), then our pick ("U 64": side in small caps, our chance). When the pick clears its break-even the number and pick go ink 600 and the meter ink; hover turns a clearing meter ledger blue. The tooltip gives our chance of the over and the app's (Underdog), and "Over only" for one-sided lines. An app with no line shows an ink-3 dash.
- Between 1001px and 1100px (beside the margin) the meter narrows; under 720px Last 10 and the meter drop, the range goes under the median, and the register scrolls sideways in its figure; under 480px each line cell stacks the number over the pick.
- Line cells refresh between builds: `props.js` fetches the hourly `props-lines.json` and rebuilds each cell (same markup as the built one), each match's per-stat line counts (so "with lines only" follows them) and the "Lines as of" time.
- *How the lines have done*: "No line has settled yet." until one has, then the record register (app rows and an All row in 600: lines, our side won, break-even, log loss, Underdog's log loss).
- *Results*: the last 3 days of settled lines ("No settled lines in the last 3 days." otherwise) and a *By month* line of links. One register (shared with the monthly pages, `_props.html.j2`'s `results`): Player (linked), Stat (small caps ink-2), Actual (600), then one cell per app with the line and our pick ("U 84"); a pick that won goes ink 600, a miss italic ink-3, and a push or void says so in italic ink-3. Each match opens with a small-caps 600 row ("15 Oct · Karmine Corp v Cloud9"), newest first.
- Margin: "How to read the props", five one-line notes and the caveat.

### Prop results pages
- `props-results/YYYY-MM.html`, one per month with a settled line: title "Prop results" with the month in italic, a one-line lede linking back to Props, the month's results register, links to the months either side, and one margin note.
### Live results
- Predictions Results link followed series to their map pages; monthly live indexes redirect to the regular results archive.
- `live-results/YYYY-MM.html` redirects to `results/YYYY-MM.html`.
- `live-results/<match>.html`, one series: the teams as the title with the score between in ink-2 (no wrap), league mark, event and date in italic ink-3; a "Before the series" line between a 2px rule and a hairline (small-caps label, the duel bar with Kalshi's caret between the two chances, favourite 600, then the method, "Kalshi close 16–84", "Call right" in ink-2); Table I, "Before each map: FURIA’s chance in 100." (booktabs, 40rem): Map (a link to its figure when recorded), Score, Map (Ours, Kalshi), Series (Ours, Kalshi) under centred group heads, Won (hidden on phones); Kalshi figures in ink-2; a three-swatch key (our call, Kalshi, gold lead) in small caps; then each recorded map across the full page width, one per row, drawn by `live_results.js` at its real width (chance panel 260px, 170px on phones; gold lead 48/34px) with the watch page's tracing: a ledger-blue rule and dot and a framed ledger-blue reading beside it (time in 600, Ours, Kalshi, the gold lead), by pointer or arrow keys. Each figure's caption line: "Map 2 · 32′ · Karmine Corp won" with "Before: 20, Kalshi 18" in ink-3 at the right; the plot is a smaller Figure 1 without tracing (0–100 with a dashed 50, our call as a 2px ink step line from an open pre-map circle to a filled end point, Kalshi's mid as a 1px ink-2 step line, the gold lead as ink-3 columns about a hairline, minute ticks), always the first-listed team's chance. Unrecorded maps: one italic ink-3 line, "Not recorded: maps 1, 3." A figure's caption is "Map 4 · 28′ · FURIA won"; a Kalshi line filled in after the map from its minute prices is marked ‡ there, with a note. The notes ("Reading the maps") follow the figures, then a link back to the month.

### Predictions Live now (overview)
- Heading "Live now", then Table I with the count and freshness as its caption ("Table I. 4 matches in progress, updated 2 s ago."; stalled or unreachable turns it ink). One booktabs row per match in progress, majors first: clock (600 tabular) over "Map 3" (ink-3 caption); league mark and code; the first team right-aligned and the second left-aligned, both links to the match styled as plain text; our call either side of the fixture register's duel bar (Kalshi's caret on its top edge), the favourite's figure and name 600, the other ink-3; Kalshi's figure for the first team in ink-2; the series score; then the gold lead named for the team ahead ("T1 +2.8k", or *even*), kills, towers, dragons and barons as pairs in ink-2. Head notes 1 (our call) and 2 (Kalshi). Matches are divided by soft hairlines and the register closes on the 2px rule; the row opens the match and washes on hover, its bar turning ledger blue.
- Under 1100px towers, dragons and barons drop; under 720px league, Kalshi, series and figures fold into one left-aligned caption line under the match ("Series 1–1 · Kalshi 75 · Gold T1 +2.9k · Kills 1–3 · …", labels in small caps).
- No match in progress: the entire Live now section is hidden. Predictions retains Coming up and Results.

### Live page (watch)
- Match strip, above the stage and always in view while matches are on: an italic *All matches* link (to Predictions) behind a hairline (on phones it moves to the end, at caption size, and chips narrow to 8.25rem so two and a half show), then one chip per match, scrolling sideways when they don't fit: league mark and code with the clock at the right (ink-3 caption), the two short names with the score between in ink-3, a duel bar with Kalshi's caret, and "73 ours · 77 Kalshi" in ink-2 caption. The watched match has a 2px ink top rule, the paper wash and its names in 600, and shows its own file's numbers; the others show the index's latest. Chips are divided by soft hairlines; hover washes a chip and turns its bar ledger blue. In full screen the bar adds a *Match* select instead.
- Title "Live" shows only without JS; the stage starts right under the running head. Under the stream one wrapping baseline row: the fact line (league mark and event in small caps, "Map 3", each team with its side in italic ink-3) and one italic ink-3 status ("Updated 2 s ago." plus the feed's note; "Stalled: last update 2 min ago." or "Feed unreachable." in ink with a ledger-blue square; "Final." on a finished map).
- The spread: the stage (stream) with the fact line and status under it; beside it one column holds the series' maps (caption-size buttons, "Map 4 · KC", "Map 5 · now", level with the stage's top; a finished map opens its saved file, `?map=4`), the odds and Table I, the odds' 2px rule level with the stage's top and Table I's closing rule level with its bottom (no visible caption: the estimated game time heads the odds' Live group, "Live · 24:10"). Figure 1 runs the page's full width under both, 360–560px tall. On desktop the page, running head and colophon widen to the window; `live.js` sizes the stream from the window's height (`--fit-h`), and the column takes the rest of the row (26rem to 40rem). Beside the stream Table I uses the short heads and drops the side column. Under 1000px they stack (stage, meta, odds, scoreline, figure) at the usual page width; under 720px the stage bleeds to the screen edges and stays at the top while the rest scrolls.
- No game in the feed (no state file, or `idle`): the stream still plays (the saved or first stream); the odds column holds one italic ink-2 line saying the odds, scoreline and figure come when a map starts; the scoreline and figure hide and *Coming up* shows under the spread.
- Full screen (the corners icon, where the browser allows it on an element): the stage alone; the video fills the screen and is never resized. The control bar floats over its top and a copy of the odds floats at the top right (24rem), both on an ink veil (`--veil`, ink at 72%) with paper type, the odds' bars in paper on a paper-at-22% trough. Any pointer movement or key shows them (240ms fade) and they fade after 3 s idle, staying while the pointer is on them or the stream select is open; the pointer hides with them. The video's frame takes pointer events, so a clear layer over the video catches movement, stopping 64px above the bottom so the player's own control strip (play, volume, quality) stays usable. Full screen, the stream picker stays reachable from the bar.
- Plate: the stage, an ink block: the control bar as its top edge, then the 16:9 stream. The bar (paper type on ink, a paper hairline at 22% under it): "Watching" (small caps, paper-deep) and a bare italic select on a paper-deep hairline with a small caret (options in ink on paper, grouped *Official* then *Co-streams*); at the right, the full-screen icon (16px, stroked, paper-deep, paper on hover: four corners, turning inward to exit), hidden where the browser can't make an element full screen.
- Odds: a small table of each team's chance, the two team names over a hairline under a 2px rule level with the stage's top. A finished map swaps the Live group for *Final · 37:56* (the map's estimated length) and one row in the odds' columns: "Map 4", then "Won" (1.625rem, ink 600) under the winner and "Lost" (ink-3) under the other; "Result pending" in italic ink-3 until it settles. Its chip reads "KC won map 4". Three groups, each a bold small-caps head: *Live* (*Ours*, with "at 15′" in italic ink-3, and *Kalshi*), figures at headline size (2.25rem on desktop) either side of a 10–14px ink duel bar, the favourite ink 600, the other ink-3; then *Before the map* (FORGE, Kalshi) and *Series 1–1* (FORGE, Kalshi) at body size with 5px ink-2 bars. Kalshi labels link to the market. A 2px rule closes it. No prose under it.
- Figure 1: chance (0–100, dashed 50) over game minutes (ticks as 5′, 10′; dotted hairlines at the 10, 15 and 20-minute checkpoints), 320px (260px on phones). Our calls are a 2px ink step line with points (pre-game an open circle) labelled "10′ 56" in 600 with a paper halo (value only under 520px); Kalshi's map price is a 1px ink-2 stepped line over a paper-deep band for its spread; under the axis the gold lead is ink-3 columns about a hairline zero (up when the first team leads). A thin ink "now" rule ends the drawing, broken at the minute labels. Tracing (pointer, or arrow keys with Shift for larger steps) draws a ledger-blue rule, puts Kalshi's dot on it and prints the moment beside the rule near the plot's top (ledger blue on paper in a 1px ledger-blue frame, flipped left near the right edge: the time in 600, then "Ours 72", "Kalshi 68", "KC +1.2k gold"; the same line is read aloud from a visually hidden live region); the scoreline follows the traced moment. A key of three tiny drawn swatches sits under it in small caps.
- Scoreline (Table I, "Scoreline at 24:10."), Figure 1 ("T1's chance to win the map.") beside it, captions on one line: side in ink-3 small caps, team, gold ("85.8k"), kills, towers, dragons, barons, inhibitors (phone-hide); the larger figure in each column is 600; the two rows split by a hairline. Under 600px the side column drops and towers, dragons and barons head as *Twr*, *Drg*, *Bar*. A dash is a number the feed didn't give.
- Between games: *Coming up*, the compact fixture register of the next matches. Notes follow, up to 40rem wide.
- Motion: the bar's share and the reading change with a 600ms ease-out scale; nothing else moves.

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

### International forecast method (2026-10-14)

The head-to-head note calls cross-league comparisons an international matchup and names regional calibration. Fixture tooltips name calibration only when the saved call records its version; existing calls retain their original method label. Team/player game-log explanation mentions the international calibration. These are copy changes within the existing Almanac typography and layout; no new column or control.


### Alert history

`alerts.html` extends the Predictions register in the existing Almanac system: one section for each of the six fixture groups, with earlier unposted picks archived separately. Each has a compact profit/return/CLV line, then saved pick, chance, ask, outcome, profit and CLV. Empty tracks say “No picks yet.” On phones the saved chance/ask fold under the pick and CLV drops, keeping outcome and profit in view. No sample-size or interval explainer; calculated intervals remain where available. The Predictions summary line is a plain link here. The margin carries only definitions needed to read the ledger. No new tokens or visual identity.

### Call performance

Call performance Table III shows five allowed fixture groups, Saved and Backtest, at positive blended after-fee edge. The repeated Edge column is omitted from blended tables; their captions state that bets require net edge > 0 after fees. Raw threshold comparisons retain their Edge column. The upcoming register adds a phone-hidden Blend column beside Kalshi, with as-of provenance in its tooltip; raw bars remain FORGE/Elo. Signal returns include personal execution vetoes; those restrictions belong to trading, not alert visibility. `call-performance.html` places record and market comparisons before the blended signal register and retains the raw comparison for every existing threshold (Any, >0/3/5/10), then native disclosure rows open each group’s detailed call history. The ledger uses the same caption, tabular figures and horizontally scrolling register on phones; no new tokens, typeface, motion or controls. Public profit remains the $1 modeled record; private execution never appears here.

Waiting fixtures reuse the Live register and Watch stage: “Waiting” replaces the clock, no unassigned map label, and “Waiting for match to start.” is the sole fresh status. Watch retains team headings and the stream; scoreline and figure hide until observations arrive. No new colour, badge, panel or animation.


### Live freshness and Coming up (2026-10-17)

Live and Watch refresh active data every two seconds. On Live, a fixture leaves Coming up only once the same started series appears in the Live register; waiting alone does not remove it. Empty day rules hide; fixture counts and empty states follow the current filters. The existing register, labels, notes and Almanac styling remain the visual contract; Watch keeps its existing idle-only Coming up section.


### Alert fee definition (2026-10-17)

Market Blend’s Signals paragraph names the execution fee bound for alerts, while the paper record keeps its estimated-fee definition. No new visual component; preserve the existing prose and register hierarchy.

### Live completed series (2026-10-18)

Coming up removes provider-confirmed started/completed series across reloads.
Finished adds a compact Date / League / Match / Result register linking to
Watch until the next daily archive provides its richer row. Reuse the existing
booktabs register and phone-hidden league column; no new tokens or controls.
