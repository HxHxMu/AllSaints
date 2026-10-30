---
# gstack: design-md-format=spec
name: All Saints
description: A book of hours read by candlelight. Soot ground, vellum text, gold used like leaf, red rubrics for every action; quiet, slow, reverent.
colors:
  soot: "#0D0B09"
  umber: "#1C1712"
  vellum: "#EFE6D2"
  ash: "#9A9183"
  gilt: "#C9A44C"
  gilt-light: "#E6C878"
  martyr: "#7A1F1F"
  lapis: "#22406B"
  surface: "#0D0B09"
  surface-raised: "#1C1712"
  text: "#EFE6D2"
  text-muted: "#9A9183"
  accent: "#C9A44C"
  action: "#7A1F1F"
  on-action: "#EFE6D2"
  focus: "#E6C878"
  rule: "#C9A44C40"
typography:
  display:
    fontFamily: Cinzel
    fontWeight: 600
    fontSize: clamp(1.75rem, 1.2rem + 2.6vw, 3.25rem)
    lineHeight: 1.08
    letterSpacing: 0.12em
    textTransform: uppercase
  body:
    fontFamily: EB Garamond
    fontWeight: 400
    fontSize: 1.25rem
    lineHeight: 1.6
  devotional:
    fontFamily: Cormorant Garamond
    fontStyle: italic
    fontWeight: 500
    fontSize: 1.4375rem
    lineHeight: 1.3
  prayer:
    fontFamily: Cormorant Garamond
    fontStyle: italic
    fontWeight: 500
    fontSize: 1.875rem
    lineHeight: 1.2
  label:
    fontFamily: EB Garamond
    fontSize: 1.0625rem
    fontVariant: all-small-caps
    letterSpacing: 0.06em
  numeral:
    fontFamily: Junicode
    fontSize: 1.1875rem
    fontFeature: onum
rounded:
  none: 0px
  sm: 2px
  md: 3px
  full: 9999px
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  gutter: 20px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 72px
components:
  rubric:
    backgroundColor: "{colors.martyr}"
    textColor: "{colors.vellum}"
    rounded: "{rounded.md}"
    padding: 15px 18px
    fontSize: 1.1875rem
  rubric-hover:
    backgroundColor: "#8C2626"
  play:
    size: 56px
    backgroundColor: "#0D0B09B8"
    borderColor: "{colors.gilt}"
    iconColor: "{colors.gilt-light}"
    rounded: "{rounded.full}"
  nav-link:
    textColor: "{colors.ash}"
    activeTextColor: "{colors.vellum}"
  link:
    textColor: "{colors.gilt}"
    hoverTextColor: "{colors.gilt-light}"
  search-input:
    borderColor: "{colors.gilt}"
    textColor: "{colors.vellum}"
    placeholderColor: "{colors.ash}"
    rounded: "{rounded.none}"
  litany-row:
    dividerColor: "#9A91832E"
    dateColor: "{colors.gilt}"
    nameColor: "{colors.vellum}"
    lineColor: "{colors.ash}"
  email-band:
    backgroundColor: "{colors.lapis}"
    textColor: "{colors.vellum}"
---

# All Saints

## Overview

**Creative North Star:** "The Night Office": a book of hours you hold in the dark. Each forgotten saint gets the dignity of a gilded panel and a slow, sourced reading, because the visitor should feel they walked into a chapel, not a feed.
**Product context:** allholysaints.com, the home of the All Saints channel (one ~60 s video a day about a lesser-known Catholic saint, on their feast day). Readers are Catholics and curious people, mostly arriving on a phone from Instagram or YouTube, early morning or at night. English and Spanish (`/es/`). Static Astro site from `state/episodes/*.json`.
**Mode per surface:** Home: Experience (one saint, poster). Saint page: Read (long story, prayer, sources). Calendar/search: Operate, lightly (find a saint). Support and email: Persuade, quietly, after the prayer.
**Reference sites:** Franciscan Media Saint of the Day and Aleteia (the category: plain text or ad-heavy portals); Hallow (modern, breathable app design); icon museums (icons as devotional objects). The gap: nobody treats a forgotten saint as an object of beauty and slow reading.
**Key characteristics:**
- The icon is the first thing seen, edge to edge, with nothing printed over the face.
- Silence: soot covers most of every screen; no banners, chips, counters or feeds.
- Red means do; vellum means read; gold is material, not decoration.
- Type from the book world only: no sans-serif anywhere.

## Colors

**Strategy:** Restrained. Soot owns about 80% of every screen; vellum carries all reading; gilt is the one accent; martyr red is reserved for actions; lapis appears once (the email band).
**Light or dark:** Dark throughout, by use scene: a phone at 7:30 AM or at night, arriving from Instagram's dark UI, in a devotional moment. A bright page would break the hush (a light vellum reading page was mocked up and declined on 2026-10-29).
- **Interaction:** every action (watch, light a candle, go deeper, subscribe) is a **rubric**: martyr-red fill with vellum text (about 9:1). Martyr red is never used as text on soot (it fails contrast).
- **Links** inside reading text are gilt (about 8.9:1 on soot), underlined with a 1px offset rule; hover goes gilt-light. Focus rings are 2px gilt-light with a 3px offset, on every focusable element.
- **Muted text** is ash (about 6.6:1 on soot): sources, meta lines, "tradition holds" passages.
- **Depth** comes from umber planes (the image fade, the background numeral), never from glows.
- Vellum on soot is about 17:1; body text never drops below vellum or ash.

## Typography

The faces come from the world the saints lived in: inscriptions, missals and books of hours.
- **Cinzel** (display): saint names and the monogram only. Uppercase, +0.12em tracking, left-aligned, broken across lines like an inscription ("SAINT / NARCISSUS / OF JERUSALEM"). Never for sentences.
- **EB Garamond** (body and interface): the story at 20px/1.6 on phones (21px on desktop), max 62 characters per line. Interface labels use true small caps (`font-variant-caps: all-small-caps`) at 17px, which keeps small text readable without a sans-serif.
- **Cormorant Garamond Italic** (devotional voice): the hook, the feast line, and the prayer. It is on the overused-display list, so it is never the display voice here; the brand assigns it to prayer text only.
- **Junicode 2** (numerals): dates as manuscript numerals ("XXIX · October") and durations ("1:06"). OFL; self-host the WOFF2 variable font from the official repository (github.com/psb1558/Junicode-font), subset to Latin + numerals.
- **Loading:** self-host all four as WOFF2 via Fontsource (Cinzel, EB Garamond, Cormorant Garamond) plus the Junicode file; subset to Latin and Latin-Extended (Spanish accents); preload EB Garamond Regular and Cinzel SemiBold only; `font-display: swap`.
- **Scale:** name 32px (phone) to 52px (desktop); body 20px; devotional 23px; prayer 30px; label 17px. Levels differ by at least 1.25x or a change of face.

## Layout

- **Phone (base, 390px design width):** 20px side gutter. Home order: top bar (monogram left; Calendar · EN / ES right) → icon, full width, 400px tall, cropped so the face sits in the upper third, tap to play → numeral date → name → devotional hook → rubric "▶ Watch his story · 1:06" (must be above the fold on a 390×844 screen) → Yesterday / Tomorrow row.
- **Saint page:** the icon fades into soot at the top (160px band), then name, meta line, story, prayer, sources, AI disclosure, books ("Go deeper"), "Light a candle" rubric, then the lapis email band. Nothing asks for money or an email before the prayer.
- **Calendar ("the litany"):** one long typeset list by month: Junicode date numeral in a 62px column, name in vellum, one italic line in ash. Today in gilt-light; future dates in ash. A search field ("Find a saint, a place, a patronage…") filters the list live; the list works without JavaScript. No thumbnails.
- **Desktop (≥1024px):** max width 1200px. Home: icon on the right three-fifths, name/hook/rubric lower left, large soot silence. Saint page: icon sticky in a left column (5/12), story in the right column at 62ch.
- **Rhythm:** small spacing (8/16px) inside a block, large (48/72px) between sections. One deliberate grid break: the icon bleeds to the screen edges on phones.

## Elevation & Depth

Flat by default. Depth comes from umber planes, the icon's own gold, and image fades into soot. Allowed shadow: only on the play button over the art (`0 2px 8px rgba(0,0,0,.4)`). No glows, no frosted glass, no cards.

## Shapes

Nearly square: rubrics 3px, inputs 0px (an underline only), play button round. No card containers anywhere: sections are separated by space and, at most, a 1px gilt rule at 25% opacity.

## Components

- **Rubric (primary action):** martyr fill, vellum label, optional right-aligned numeral or second line in 16px at 80% opacity. Hover: #8C2626. Focus: gilt-light ring. Active: 1px down. Disabled: not used (hide unavailable actions instead).
- **Play affordance on the icon:** 56px round, soot at 72% with a 1px gilt ring and a gilt-light triangle, bottom-left of the art. Tapping replaces the art with the YouTube player (no iframe until tapped; `youtube-nocookie.com`).
- **Top bar:** monogram (Cinzel, gilt) links home; labels in small caps; the current language in vellum, the other in ash.
- **Litany row:** date, name, line; the whole row is the link; hover/focus tints the name gilt-light. Empty search state: "No saint by that name yet. The calendar grows every day."
- **Search input:** underline in gilt at 50%, italic placeholder in ash; full-width on phones.
- **Email band:** lapis field, one line of copy ("A week of saints, in one quiet email."), email input + rubric; success and error messages in vellum on the same band.
- **Story text:** first letter as a Cinzel drop cap in gilt; passages from legend set in italic ash and introduced in words ("Tradition holds…").

## Do's and Don'ts

- Do keep text off the painting; the face is never covered.
- Do make every action a rubric and nothing else red.
- Do put the prayer before any support, book or email request.
- Do use real numerals in Junicode for dates and durations.
- Do test every page at 390×844 with the main action above the fold.
- Don't add a sans-serif, a card, a chip or a badge.
- Don't use martyr red as text on soot, or gilt as a background behind text.
- Don't loop any motion, add candle-flicker effects, glows or particles.
- Don't show thumbnails in the calendar; each icon is seen on its own page.
- Don't write urgency or guilt copy, or call support a "donation".

## Motion

- **Approach:** intentional and slow, matching the videos.
- **Easing:** enter ease-out; exit ease-in; move ease-in-out.
- **Duration:** micro 100ms (hover/focus), short 200ms, medium 500ms (text fade + 12px rise), long 600ms (cross-dissolve between pages via View Transitions).
- **The one authored moment:** none on the home page for now (variant A). Candidate for later: a single soft band of light crossing the icon's gold once on load (3.2s, CSS mask, never loops), off under `prefers-reduced-motion`.
- All motion is disabled under `prefers-reduced-motion: reduce`.

## Decisions Log
| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-10-29 | Initial design system created ("The Night Office", variant A + litany calendar) | /design-consultation: product context, web research (Franciscan Media, Aleteia, Hallow, icon museums), independent proposals from a Claude agent ("The Night Office") and Codex ("The Daily Chapel"), HTML mockups of three variants; Luis chose A with C's litany calendar |
| 2026-10-29 | Dark throughout; light vellum story page declined | Use scene (phone, morning/night, from Instagram); keeps the chapel feeling |
| 2026-10-29 | Text never over the icon; poster image doubles as the video player | From Codex's proposal: protects the face and readability |
| 2026-10-29 | Junicode 2 added for numerals | From the Claude agent's proposal: manuscript dates replace UI labels |
