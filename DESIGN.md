---
name: Prometheus
description: Sabermetrics for LoL esports. Every team-season is a championship banner hung in the rafters.
colors:
  felt-lck: "#24479c"
  felt-lpl: "#9c2338"
  felt-lec: "#1f6346"
  felt-lcs: "#c9971f"
  felt-other: "#4a4844"
  line-lck: "#7d9ef0"
  line-lpl: "#e5707f"
  line-lec: "#5cbf92"
  line-lcs: "#d9a83a"
  line-other: "#9b968c"
  ground: "#1a1917"
  ground-raised: "#23221f"
  ground-sunk: "#141312"
  rule: "#34312c"
  rule-strong: "#4b473f"
  thread: "#ede6d6"
  thread-dim: "#aba393"
  felt-ink: "#f3ecdc"
  felt-ink-dark: "#1d1a14"
  rod-hi: "#8a847a"
  rod-mid: "#4d4943"
  rod-lo: "#2b2926"
typography:
  display:
    fontFamily: "Graduate, Rockwell, Georgia, serif"
    fontSize: "2rem"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "0.01em"
  display-home:
    fontFamily: "Graduate, Rockwell, Georgia, serif"
    fontSize: "2.5rem"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "0.01em"
  numeral:
    fontFamily: "Graduate, Rockwell, Georgia, serif"
    fontSize: "1.875rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.01em"
  headline:
    fontFamily: "Graduate, Rockwell, Georgia, serif"
    fontSize: "1.375rem"
    fontWeight: 400
  title:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  body:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
  table:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    fontFeature: "tnum"
  label:
    fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 700
    letterSpacing: "0.07em"
rounded:
  hairline: "2px"
  sm: "3px"
  md: "4px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  2xl: "32px"
  section: "48px"
components:
  topbar:
    backgroundColor: "{colors.ground-sunk}"
    textColor: "{colors.thread-dim}"
    height: "52px"
    padding: "0 clamp(16px, 3vw, 32px)"
  search-input:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.thread}"
    rounded: "{rounded.md}"
    height: "34px"
    width: "220px"
    padding: "0 10px 0 32px"
  picker:
    backgroundColor: "{colors.ground-raised}"
    textColor: "{colors.thread}"
    rounded: "{rounded.md}"
    height: "34px"
    padding: "0 30px 0 12px"
  picker-panel:
    backgroundColor: "{colors.ground-raised}"
    rounded: "{rounded.md}"
    padding: "10px"
  button-outline:
    textColor: "{colors.thread}"
    rounded: "{rounded.md}"
    height: "30px"
    padding: "0 10px"
  segmented-option:
    textColor: "{colors.thread-dim}"
    typography: "{typography.label}"
    padding: "5px 12px"
  segmented-option-selected:
    backgroundColor: "{colors.thread}"
    textColor: "{colors.ground}"
  table-row:
    textColor: "{colors.thread}"
    typography: "{typography.table}"
    height: "29px"
    padding: "3px 10px"
  table-row-hover:
    backgroundColor: "{colors.ground-raised}"
  table-header:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.thread-dim}"
    typography: "{typography.label}"
    height: "34px"
  banner-felt:
    textColor: "{colors.felt-ink}"
    typography: "{typography.numeral}"
    height: "196px"
---

# Design System: Prometheus

## Overview

**Creative North Star: "The Rafters"**

Every team-season is a championship banner hung in the rafters, and the ranking is the order they hang in. The ground is dim arena steel, warm charcoal and never pure black, under a single steel rod. Banners are twill felt with a chain-stitched inner border and a swallowtail hem, set in varsity block numerals. Every banner hangs at the same length with its rank, name, league and score stitched on the felt, like a real championship banner.

Color is encoding, not decoration. Each major league owns one felt hue (LCK royal, LPL crimson, LEC forest, LCS gold), used identically on banners, league tags, filter swatches and chart lines. Every other league hangs in neutral felt. Everything that is not a league is cream stitch thread on steel. Below the rafters sits a dense, quiet table (about 29px rows, tabular numerals, right-aligned numbers), because the table is the product and the banners only stage it.

The world explicitly refuses the dark-neon esports dashboard and the card-grid stat hub. There are no cards, no glows, no gradients other than the rod's metal and the felt's shading.

**Key Characteristics:**
- Warm charcoal steel ground, single cream ink.
- League hue is the only color, and it always means the league.
- Every banner hangs at one fixed length; the lettering lives on the felt.
- Varsity block face for names, numerals and titles; system sans for reading and numbers.
- Dense, sortable, sticky-header table directly under the rafters.
- Motion only conveys state change (the re-hang), and is instant under reduced motion.

## Colors

A single-ink world: cream thread on warm steel, with four league felts as the only chroma.

### Primary (league felts)
- **LCK Royal Felt** (felt-lck): banner felt and hanging tabs for LCK team-seasons; also the favicon felt.
- **LPL Crimson Felt** (felt-lpl): banner felt for LPL.
- **LEC Forest Felt** (felt-lec): banner felt for LEC.
- **LCS Gold Felt** (felt-lcs): banner felt for LCS. The only light felt, so its numerals and chain stitch switch to the dark felt ink.
- **Neutral Felt** (felt-other): every league outside the major four.

### Secondary (league lines)
- **League Line tints** (line-lck, line-lpl, line-lec, line-lcs, line-other): lighter tints of each felt hue, used wherever the hue is a thin stroke or small mark on the dark ground: league-tag pennant swatches, filter swatches, and the Elo chart line. Each holds at least 3:1 against the ground.

### Neutral
- **Arena Steel** (ground): page background, table header background, caption backing.
- **Raised Steel** (ground-raised): pickers, picker panels, row hover, chart tooltip, empty-season felt.
- **Sunk Steel** (ground-sunk): the sticky top bar and the scrollbar track.
- **Seam** (rule) and **Strong Seam** (rule-strong): hairline dividers, input borders, table header underline, segmented-control borders, chart grid and axis.
- **Stitch Thread** (thread): all primary text, focus rings, selected states, the stitched average line.
- **Faded Thread** (thread-dim): secondary text, labels, metadata, placeholders, rank column.
- **Felt Ink** (felt-ink) and **Dark Felt Ink** (felt-ink-dark): numerals and chain stitch on felt.
- **Rod Steel** (rod-hi, rod-mid, rod-lo): the rafter rod and its end brackets, and the wordmark's rod.

### Named Rules
**The Felt Means League Rule.** A league hue appears only where it encodes that league, and the same league always gets the same hue on every surface (banner, tag, swatch, chart line). Never use a felt for emphasis, status or decoration.

**The One Ink Rule.** Everything that is not a league is drawn in stitch thread or faded thread on steel. There is no other accent; selected and focused states invert to thread rather than borrowing a hue.

## Typography

**Display Font:** Graduate (self-hosted latin woff2, with Rockwell and Georgia fallbacks)
**Body Font:** system-ui stack
**Label/Mono Font:** none distinct; labels are the system stack in small tracked uppercase

**Character:** Graduate is a collegiate varsity slab, the lettering sewn onto banners and jerseys; it renders lowercase as small caps. The system sans does all reading and all numbers, so the varsity face stays ceremonial.

### Hierarchy
- **Display** (400, 2rem, 1.1; 2.5rem on the home intro, 1.625–1.875rem under 720px): page titles (metric name, team name, home statement). A metric's full name sits under it in the same face at 0.875rem in faded thread.
- **Numeral** (400, 1.875rem, 1): the rank numeral on a banner; 1.125rem for year numerals on team season banners.
- **Headline** (400, 1.375rem): metric names in the home metric index. Banner captions use the same face at 0.8125rem.
- **Title** (700, 1.0625rem, 1.3, -0.01em): section headings in system sans.
- **Body** (400, 0.9375rem, 1.5): ledes and explanations, capped at 68–72ch.
- **Table** (400, 0.875rem, tabular numerals): table cells; the value column is 700.
- **Label** (700, 0.6875rem, 0.07em, uppercase): sortable table column headers only.

### Named Rules
**The Varsity Is Sewn Rule.** Graduate is for names, numerals and titles that would be stitched onto a banner. Never set paragraphs, table cells or controls in it.

**The Tabular Rule.** Every number that can be compared (scores, z-scores, Elo, counts, years in pickers) uses tabular numerals and right alignment in tables.

## Layout

Single column, max 1240px, centered, with a fluid gutter (clamp 16px to 32px). The sticky top bar is 52px: wordmark, metric links, search pushed right. Rankings pages stack: title and lede, a filter toolbar (pickers left, count right), the rafters with the current top ten, then the table starting immediately below, so the first rows sit in the first 1080p viewport.

The rafters are a 10-column grid with 12px gaps. Every felt is 196px long (184px under 900px), with the numeral at the top and the title, meta line and value stitched below it. Team pages use fixed 104px season columns with 132px felts.

Spacing rhythm is a 4px base (4, 8, 12, 16, 24, 32), with 48px between major sections and 56px before the home metric index. The page has 32px top and 64px bottom padding.

Responsive: under 900px the rafters stop shrinking and become a sideways-scrolling rod (92px columns, 180px felt scale, proximity snap, bleeding to the screen edge). Under 720px the wordmark text hides, search collapses to an icon-width field that expands on focus, the table scrolls horizontally, wide-only columns drop, and league and year fold into the team cell to keep one line per row. Under 480px phone-hide columns drop, the table header stops sticking, and picker panels pin to the gutters.

## Elevation & Depth

Flat steel with physical exceptions. Depth exists only where a real object hangs or floats: the felt banners cast a soft drop shadow onto the ground, and an open picker panel lifts slightly. The rod is the only metallic gradient. Felt gets inner shading (darkened selvedges and a shadow under the rod) plus a faint fractal-noise twill texture. Nothing else has shadow, glow or blur.

### Shadow Vocabulary
- **Banner hang** (`filter: drop-shadow(0 8px 10px rgb(0 0 0 / 0.4))`): on each banner, applied to the list item so the swallowtail clip does not cut it.
- **Panel lift** (`box-shadow: 0 6px 12px -4px rgb(0 0 0 / 0.5)`): open picker dropdowns only.
- **Header seam** (`box-shadow: inset 0 -1px var(--rule-strong)`): the sticky table header's bottom rule.

### Named Rules
**The Only Things That Hang Rule.** Shadows belong to objects that physically hang or float (banners, an open dropdown). Rows, sections and controls are flat.

## Shapes

Small, mostly square forms with two signature silhouettes. Controls use a 4px radius; picker options and banner tabs 3px; focus rings 2px. The banner felt is a rectangle clipped to a swallowtail hem (a 14px center notch); the league-tag and filter swatch are a 9 by 12px pennant using the same swallowtail. The chain stitch is a looped-link border image set 5px inside the felt edge. The rod is a 7px bar with 6 by 18px end brackets.

## Components

### Top bar
- **Style:** sticky, sunk steel with a seam below. Wordmark in Graduate 1.125rem with a small banner-on-rod mark.
- **Links:** system sans 600 0.875rem in faded thread; hover to thread; the current page gets thread text and a 2px thread underline at the bar's bottom edge.

### Search
- **Style:** 34px field on arena steel, seam border, 4px radius, magnifier icon inset left.
- **Focus:** border turns to thread; no outer glow.

### Filter pickers
- **Style:** native details/summary styled as 34px raised-steel buttons with a muted label, a bold value and a rotating chevron. Panel is raised steel, strong seam border, panel lift shadow.
- **Options:** checkbox grid (3 columns for leagues, 4 for years), tabular numerals; league options carry their pennant swatch. "Major four only" is a full-width outline button.
- **Clear filters:** a borderless underlined text button in faded thread.

### Segmented control
- **Style:** strong-seam outline, 4px radius, options in system sans 600 0.8125rem.
- **Selected:** inverts to thread background with ground text. Focus draws the 2px thread ring.

### Rankings table
- **Style:** full width, collapsed borders, seam under every row, 29px rows, sticky header under the top bar.
- **Header:** tracked uppercase label in faded thread with a sort glyph at 35% opacity; the sorted column goes to thread at full opacity. Numeric columns right-align.
- **Rows:** hover to raised steel. Rank in faded thread, team name 600 and linked, value 700.

### League tag
- **Style:** the league code preceded by a pennant swatch in the league's line tint.

### Felt banner (signature)
- **Construction:** hanging tabs wrap the rod in darkened felt; a fixed-length felt with chain stitch inside the edge and a swallowtail hem; the numeral at the top, then the Graduate title (wraps to three lines), a meta line with year and league, and the value in Graduate above the hem, all in the felt's ink.
- **States:** hover brightens the felt 12% and underlines the title; focus draws a thread ring 4px out.
- **Season variant:** on team pages one shorter banner per year (year, league, score); the GLORY/GLORB toggle swaps the score. Seasons without a score hang raised-steel felt.
- **Re-hang motion:** when filters or the metric change, each felt unfurls from the rod (clip-path, 260ms, ease-out cubic-bezier(0.16, 1, 0.3, 1), 16ms stagger per banner). It is instant under reduced motion.

### Elo chart
- **Style:** a single 2px line in the team's league line tint, no points until hover, no fill, no legend. Horizontal grid in seam, axis ticks in faded thread, raised-steel tooltip with strong-seam border. No chart animation.

## Do's and Don'ts

### Do:
- **Do** keep every banner the same length; the order and the stitched score carry the ranking.
- **Do** use the league's felt for banners and its line tint for any stroke or small mark, identically everywhere.
- **Do** keep table rows near 29px, numbers right-aligned in tabular numerals.
- **Do** draw selected and focused states by inverting to stitch thread or a 2px thread ring.
- **Do** let the rafters scroll sideways on narrow screens rather than shrinking banners.
- **Do** make every motion express a state change, and drop it under reduced motion.

### Don't:
- **Don't** use a league hue for anything that is not that league: no colored buttons, highlights, status colors or decorative accents.
- **Don't** use pure black or neon; the ground is warm charcoal steel.
- **Don't** introduce cards, glows, glassmorphism or gradient fills; the rod and the felt shading are the only gradients.
- **Don't** vary banner length or let lettering spill off the felt; long names wrap, they never break mid-word.
- **Don't** set body copy, table cells or controls in Graduate.
