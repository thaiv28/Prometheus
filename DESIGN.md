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
    width: "12.5rem"
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

A page is 82rem max with a fluid gutter (16 to 48px). The running head and colophon align to the content edges. Content is a two-column spread: the main column and a 17rem margin, 32 to 56px apart; the margin is sticky on desktop. Under 1000px the margin follows the main column (on the home page, the Contents moves between the intro and the tables). Under 720px the running head stacks (wordmark, sections, full-width index search), registers scroll horizontally edge to edge, wide-only columns hide and their league and year fold under the team name, and fact lines drop their middle-dot separators. Under 480px phone-hide columns drop.

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
- Sections: Home, then two groups, each led by an italic ink-3 group name in normal caps: *Season stats* (GLORY, GLORB, GLORY+) and *Forecasts* (GlorELO+, Elo). Links are small caps; the current one is ink 600 with a 2px ledger-blue underline. A hairline divides the groups on desktop; under 720px each group takes its own line and the divider drops.
- Search: a "Search" label and a bare input on a hairline baseline; focus thickens the baseline to 2px ledger blue. Off the rankings pages it submits to the Elo register, which lists every team.

### Filter line
- Set as a sentence: "Showing years all, leagues all". The label is small caps, the value italic on a dotted underline, with a caret. Opening turns the value and caret ledger blue.
- Panel: paper, ink border, 2px top rule, small-caps legend, a grid of square checkboxes; leagues carry their mark. "Major four only" and "Clear filters" are italic underlined text buttons.
- Forecast pages (Elo, GlorELO+) label the year picker "season" and show *Now* as its empty value, the way the others show *All*: the register opens on current ratings for active teams. Its panel (legend "Season's end") leads with a "Current ratings" text button that returns to Now. Choosing seasons switches the register to team-seasons rated at the end of each year, and the caption says so ("Elo, all team-seasons, 2019, rated at season's end").

### Register (signature)
- Booktabs table with a printed caption that describes the current view in words ("GLORY, LCK team-seasons, 2021–2024, ranked by score.") and a count.
- Column heads are sort buttons; the sorted head goes ink 600 with a ledger-blue triangle. Superscript note numbers in heads point at the margin notes.
- A printed bar column sits before the value: a 5px ink-2 rule whose length is the value on a fixed scale for the page.
- Hover washes the row; hovering or focusing a row traces its value on the distribution figure in ledger blue.

### Head to head (GlorELO+)
- Set as a sentence at headline size (lede size on phones): "[team] *beats* [team] **57 times in 100**." Each team is a bare select on an ink baseline with a small caret, sized to the chosen name; the verb is italic ink-2 and the result is ink 600 with tabular figures.
- Captioned like a figure ("Head to head." in bold small caps) with a note mark to the margin.
- Below it, a 5px printed bar: the first team's share in ink on a paper-deep trough, with a hairline tick at 50%. It does not animate.

### Distribution figure
- A histogram of every entry in the current view on the page's fixed scale: ink-2 columns on a ruled axis with tabular tick labels and a dashed median with an italic label.

### Franchise entry (team pages)
- Name in display size; a small-caps fact line (league marks, seasons ranked, Elo); a prose summary with the best season, its year rank, and the Elo peak.
- Figure 1: printed column chart of GLORY or GLORB by season, switched by a two-option small-caps control with a ledger-blue underline.
- Season register with year rank ("2nd of 47", or "Unranked" when the season had fewer than 5 games).
- Figure 2: hand-drawn SVG Elo line in the league ink, dashed 1500 rule, annotated peak, and a pointer and arrow-key readout.

### Margin notes
- Small-caps head over an ink rule; numbered notes with ledger-blue marks; the dagger note is the caveat, in italic. A targeted note gets the spot wash.

### Motion
- Rows re-rank in place: rows that stay in view slide from their old position to their new one over 360ms with cubic-bezier(0.16, 1, 0.3, 1). Season columns scale to the switched metric over 320ms. Both are instant under reduced motion.

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
