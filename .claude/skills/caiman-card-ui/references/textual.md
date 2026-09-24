# Terminal implementation

Read when implementing this style with Python/Textual. Reuse the target project's
existing UI primitives and dependencies. Do not copy the whole board workflow to
create a different entity's cards.

## Existing examples in a Caiman checkout

Paths are relative to the checkout root, not to this skill:

- `src/caiman/pixel_title.py`: despite its historical name, `pixel_title` currently
  returns **Braille dots**, not solid pixels. It supports separate uppercase and
  lowercase five-by-seven glyphs and returns an empty list for fallback.
- `src/caiman/board_gallery.py`: `BoardCard.format_card` shows the information
  hierarchy; `BoardCardFrame` provides the decorative shadow. Adapt the data
  mapping and names for the new entity.
- `src/caiman/board_form.py`: `CardRow`, the card grids, and add-card handling show
  inline editing and draft retention. Fields use `.field-label` styling.
- `src/caiman/theme.py`: shared colors and terminal controls.
- `tests/test_board_gallery.py` and `tests/test_board_form.py`: examples of focus,
  layout, fallback, and draft-preservation checks.

If these paths are unavailable, implement equivalent behavior locally. Do not
assume the user's checkout lives at any particular absolute path.

## Dot renderer

A five-column glyph plus a blank separator column occupies three Braille cells.
Seven dot rows plus one empty padding row occupy two terminal rows. Preserve
case by looking up the original character rather than uppercasing the value.

For each two-column/four-row cell, pack bits using these row/column positions:

```python
DOT_BITS = ((0, 3), (1, 4), (2, 5), (6, 7))
mask = sum(
    1 << DOT_BITS[dy][dx]
    for dy in range(4)
    for dx in range(2)
    if pixels[y + dy][x + dx]
)
character = chr(0x2800 + mask) if mask else ' '
```

Here `pixels` contains booleans or integers; convert string `0`/`1` entries
before using this example. Never render an unknown glyph as a blank. Fall back
for the complete heading if unsupported or if `3 * len(value)` exceeds the
available content width. Do not append a plain-text duplicate after a successful
render. Use Rich/Textual cell-aware wrapping for the plain-text fallback.

Font ascent, descent, and line spacing can make a seam between Braille rows.
There is no portable Textual font-size or negative line-height fix. Keep real
dots unless the user explicitly chooses another appearance.

## Frame and shadow

Use a nonfocusable frame containing a background shadow widget and the existing
focusable card. Keep the card as the event source for activation.

```css
.card-frame { width: 100%; height: auto; layers: shadow face; }
.card-shadow {
    position: absolute; offset: 1 1; layer: shadow;
    visibility: hidden; color: #466d36; background: #000000;
}
.card-frame.selected .card-shadow { visibility: visible; }
.card-face {
    layer: face; min-width: 0; margin: 0; padding: 0 1;
    text-align: left; content-align: left top;
    background: #000000; color: #dfe6d3;
    border: solid #33422e; text-style: none;
}
.card-face:hover, .card-face:focus { border: solid #7fdc4f; }
```

Set `.selected` on the frame in the face's focus handler and remove it on blur.
Explicit handlers avoid relying on ancestor `:focus-within` style invalidation;
verify the old frame loses its shadow after keyboard movement.

For frame width `W`, use face width `W - 1`. If the measured face height is `H`,
reserve frame height `H + 1`. Size the shadow to the face's dimensions and fill
it with repeated `⠢⠔` rows. The opaque face covers the pattern except along the
offset right and bottom edges. Focus only changes visibility, never geometry.

Compute text width after subtracting face borders and padding. Compute each grid
row height as the maximum **frame** height in that row. Include gutters and the
scrollbar in the grid's width/height budget. In the current Caiman layout, body
padding consumes four columns and the vertical scrollbar consumes two. Do not
hardcode those deductions for a different theme or toolkit.

Keep the normal button background, tint, and alignment rules from overriding
the black face or left-aligned text. Prevent the decorative layer from taking
focus or intercepting activation. Verify the last row and rightmost shadow are
not clipped after resizing or scrolling.

## Navigation and inline editing

Base horizontal movement on shared grid-row tops, not vertical centers: cards
in the same row may have different heights. When summary buttons are inset
inside cards, compare the **outer card** rectangles so a summary and an add card
are treated as belonging to the same row. Skip hidden/collapsed descendants.
Allow keyboard navigation to leave a card grid for surrounding form controls.

Keep the add card last after insertions. Collapse must not discard incomplete
values or bypass validation. Invalid values remain editable and the ordinary
review/save stage reports them. Do not equate the `Done` button with persistence.
