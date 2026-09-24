---
name: caiman-card-ui
description: Design, implement, or review Caiman-style cards with a black-and-green palette, individual-dot headings, concise information hierarchy, inline editors, and dotted selection shadows. Apply to cards for any entity, including projects, documents, devices, tasks, and configurations; use for requests to reuse this card aesthetic, not unrelated UI work.
---

# Caiman Card UI

Build cards that are easy to scan: a prominent identity, a small amount of useful
information, and a clear selection state. The style is independent of the data
model. Do not introduce board-specific fields into another kind of card.

## Choose the information before drawing

Map the entity to these slots, omitting slots that have no useful meaning:

1. **Primary identity:** the name the user recognizes.
2. **Secondary identity:** a version, revision, or meaningful status. Do not invent
   a version just to fill the layout.
3. **Summary line:** a few short, labeled counts or facts that help choose a card.
4. **Item list:** names of the most relevant constituent items, one per line.

Separate primary identity, secondary identity, and summary with a blank line.
Put another blank line between the summary line and the item list. Do not add an
empty item-list region when there are no items. Use ` · ` between summary facts.

Examples of mappings, not mandatory schemas:

| Entity | Primary | Secondary | Summary | Item list |
| --- | --- | --- | --- | --- |
| Project | Project name | Release | Tasks, documents | Milestone names |
| Document | Document title | Revision | Sections, pages | Section names |
| Device | Device name | Status | Components, connections | Component names |
| Configuration | Configuration name | Version | Parts, links, documents | Part names |

Only use available, meaningful data. Define what counts include; for example,
aggregate document-pin counts can include both entity-level and child-item pins.
Do not silently substitute unique-document counts for pin counts. Keep raw IDs,
digests, aliases, verbose notes, provenance, and implementation details in the
expanded editor or detail view unless specifically requested on the card.
Retain underlying data and selection identity when simplifying the display.

## Appearance

Use a black canvas, solid rectangular outlines, green accents, and pale text.
The border itself is **solid**, never dotted. Dots belong to the heading and
selection shadow.

| Element | Color | Treatment |
| --- | --- | --- |
| Canvas and card face | `#000000` | Flat, opaque background |
| Default border | `#33422e` | Thin solid line |
| Focused or hovered border | `#7fdc4f` | Same border geometry |
| Primary heading | `#eef3e6` | Prominent individual-dot lettering |
| Secondary heading | `#7fdc4f` | Individual-dot lettering |
| Summary line | `#aab69c` | Bold ordinary text |
| Item names | `#dfe6d3` | Ordinary text |
| Selected-card shadow | `#466d36` | Discrete dots |

Left-align content and text; a button's default centering must not override the
layout. Give the face horizontal inset space. Size each card to its content,
with aligned row tops and space between cards. Start with two columns when the
viewport supports them and one on narrow screens. Do not force equal card heights
that create large blank interiors. Reserve shadow space in the layout at all times.

## Typography: individual dots, not solid pixels

Use enlarged dot-matrix lettering for the main identity and secondary identity
on overview cards. Each letter consists of **individual dots**. Do not substitute
solid block, quadrant, or half-block lettering to fix a dot-spacing issue.

Render each identity **once**. When the dot heading fits, do not repeat the same
name or version as an ordinary-text caption beneath it. Preserve original casing,
punctuation, and opaque version labels. If the value contains unsupported glyphs
or cannot fit, use bold ordinary text for that entire heading instead of the dot
heading. Wrap the fallback; do not truncate an identifier or replace characters.
A short prefix such as `Version` may identify a plain-text secondary heading.

Terminal cards use the terminal's monospace font. The dot heading is a glyph
renderer, not a different installed font or a per-widget font-size setting.
Unicode Braille packs a five-by-seven dot alphabet into two terminal rows.
Spacing at the row seam depends on the terminal font; do not claim CSS can remove
that gap, or silently trade away the requested dot aesthetic. For graphical UIs,
render actual separated circles on an evenly spaced grid to preserve the look
without the terminal's font metrics.

Keep ordinary field labels bold, bright, and in Title Case: `Document Ref`,
`Project Name`, `Board Vendor`. Capitalize display labels, not stored values.
Use extra vertical space for terminal field labels rather than pretending their
font size can change.

## Selected-card shadow

Selection means the currently focused card, not a remembered default entity.
Place a dotted shadow behind the face, offset one terminal cell right and one
row down. Use a quiet green pattern such as repeated `⠢⠔`. Only the right and
bottom edges should remain exposed; the opaque face hides the interior.

Reserve the extra right column and bottom row even when unselected. Show the
shadow on focus and hide it on blur. Moving focus must never resize cards, move
neighbours, or leave a stale shadow behind. Hover can brighten the outline; it
does not imply a persistent selected state. Keep the shadow decorative and
nonfocusable. Keyboard activation and mouse clicks must still reach the card.

For graphical UIs, use a separate dotted layer or mask with a small right/down
offset. A smooth blurred box shadow is not the same style.

## Editable and add-card variants

Use compact, ordinary-text summaries for repeated cards inside an editor; do not
force oversized headings onto every nested form. Keep the same palette, solid
outline, clear identity, and spacing. Board-level or entity-level fields can
remain above the grids in the existing form layout.

Click or Enter opens the card's editor **in place**. Keep fields mounted or
otherwise retain their complete draft state while collapsed. `Done` collapses
the card, updates its summary, and returns focus to it; it does not imply saving
or registering data. Preserve the application's review/save workflow.

Place a matching **add card** at the end of each grid, including empty grids.
Center a large `+` with a short action label. Activation adds a blank expanded
card before the add card and focuses its first field. Removal returns focus to
a useful surviving control, typically the add card. Expanded forms retain all
editable fields, even when their summaries omit those details.

Remove explanatory subtitles and implementation commentary from the normal edit
flow. Keep concise field labels, essential format cues in placeholders, actual
validation errors, and explanations needed for read-only or unsupported records.

## Implementation and verification

For Textual, read [Terminal implementation](references/textual.md) for the
renderer, layering, geometry, and keyboard details. The reference includes
existing Caiman code locations; they are examples, not required dependencies in
another project.

Check the observable behavior relevant to the change: dotted rather than solid
headings, no duplicate identity text, correct counts, whitespace before item
lists, exact fallback values, focus/blur shadow transitions, and stable geometry.
For editable cards, check collapse/reopen draft retention, add/remove focus,
and preservation of fields omitted from the summary. Exercise narrow and wide
layouts, long names, mixed case, unsupported glyphs, unequal card heights, and
scrolling when those paths change. Inspect a screenshot in the target renderer
when font appearance is material; headless geometry tests cannot prove how a
user's terminal draws the dots.
