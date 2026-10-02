# Terminal implementation

Read when implementing this style with Python/Textual. Reuse the target project's
existing UI primitives and dependencies. Do not copy the whole board workflow to
create a different entity's cards.

## Existing examples in a Caiman checkout

Paths are relative to the checkout root, not to this skill:

- `src/caiman/ui/heading.py`: `card_heading` renders equipment labels with
  cell-aware wrapping, a title marker, and bracketed secondary identities.
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

Use `card_heading(value, available, secondary=False)` from
`src/caiman/ui/heading.py`. It returns Rich `Text` with a green `▌ ` marker and
bold pale normal-width title. Set `secondary=True` for a regular-weight green
`  [ value ]` subtitle with its original casing. Append this Rich text directly
so its separate marker and text styles survive.

Wrap using Rich's cell-aware `Text.wrap(..., overflow='fold')`, reserving two
cells for the prefix. Subsequent lines start with two spaces. Uppercase ASCII
titles for display only; preserve non-ASCII titles exactly. Long identities keep
the same treatment and all their characters. Count the resulting lines when
sizing the card and its shadow; do not assume a single title row.

The available width excludes borders, padding, Button line padding, and shadow
space. In unusually narrow editors, leave at least one cell for text by reducing
the prefix. Do not add a typography switcher to the permanent presentation.

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
