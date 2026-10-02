# Terminal implementation

Read when implementing this style with Python/Textual. Reuse the target project's
existing UI primitives and dependencies. Do not copy the whole board workflow to
create a different entity's cards.

## Existing examples in a Caiman checkout

Paths are relative to the checkout root, not to this skill:

- `src/caiman/ui/heading.py`: `fullwidth_title` renders an uppercase fullwidth
  heading in one terminal row and returns an empty list for fallback.
- `src/caiman/ui/cards.py`: shared `card_label`, `OverviewCard`, `CardFrame`,
  `EditorFrame`, and `AddCardFrame` presentation and focus behavior.
- `src/caiman/boards/gallery.py`: `BoardCard.format_card` shows the information
  hierarchy and pin counts; adapt the data mapping for other entities.
- `src/caiman/dashboard/onboarding.py`: menu cards use the shared heading style.
- `src/caiman/boards/form.py`: `CardRow`, grids, and add-card handling retain
  inline editor drafts. Fields use `.field-label` styling.
- `src/caiman/ui/theme.py`: shared colors and terminal controls.
- `tests/test_board_gallery.py` and `tests/test_board_form.py`: examples of focus,
  layout, fallback, and draft-preservation checks.

If these paths are unavailable, implement equivalent behavior locally. Do not
assume the user's checkout lives at any particular absolute path.

## Heading renderer

Map each character of a validated heading to its fullwidth form after
uppercasing it for display:

```python
def fullwidth_title(value, width):
    if not value or any(not ' ' <= c <= '~' for c in value) or len(value) * 2 > width:
        return []
    return [''.join('\u3000' if c == ' ' else chr(ord(c) + 0xFEE0)
                    for c in value.upper())]
```

Every fullwidth character occupies two cells, so the width check is twice the
character count against the available content width. Return an empty list for
the complete heading if any character is not printable ASCII or it does not
fit; the caller then shows bold ordinary text with the original value and
casing, using Rich/Textual cell-aware wrapping. Do not append a plain-text
duplicate after a successful render. Measure rendered widths in cells, never
in characters.

Do not stack rows or add a font-size/negative-line-height workaround. The
permanent style is a single fullwidth row, not a style preview selector.

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

Compute text width after subtracting face borders, padding, and Textual Button's
line padding. Current overview cards reserve six columns: two for borders, two
for face padding, and two for Button line padding. Omitting the last two can
wrap the heading and hide the summary. Compute each grid
row height as the maximum **frame** height in that row. Include gutters and the
scrollbar in the grid's width/height budget. In the current Caiman layout, body
padding consumes four columns and the vertical scrollbar consumes two. Do not
hardcode those deductions for a different theme or toolkit.

Keep the normal button background, tint, and alignment rules from overriding
the black face or left-aligned text. Prevent the decorative layer from taking
focus or intercepting activation. Verify the last row and rightmost shadow are
not clipped after resizing or scrolling.

For auto-height editor cards, `EditorFrame` uses a percentage-sized underlay and
reserves the exposed right column and bottom row with face margins. Draw the
one-cell offset inside that layer. A fixed shadow height can prevent the parent
from shrinking after collapse; outer padding can clip the exposed shadow.
Refresh the dot content when the layer resizes, and verify actual rendered dots
as well as geometry. Descendant focus/blur must update selection as fields change.

## Navigation and inline editing

Base horizontal movement on shared grid-row tops, not vertical centers: cards
in the same row may have different heights. When summary buttons are inset
inside cards, compare the **outer card** rectangles so a summary and an add card
are treated as belonging to the same row. Skip hidden/collapsed descendants.
Allow keyboard navigation to leave a card grid for surrounding form controls.

On focus, scroll the card's frame into view minimally, including its shadow row.
Do not pin the focused card to the top of the viewport: every move then
scrolls, which reads as a glitch.

Keep the add card last after insertions. Collapse must not discard incomplete
values or bypass validation. Invalid values remain editable and the ordinary
review/save stage reports them. Do not equate the `Done` button with persistence.
