---
name: caiman-focus-scroll
description: Keep keyboard focus movement in Caiman's Textual TUIs calm; never scroll a card that is already visible, and never pin the focused card to the top of the viewport. Use when adding focus handlers, card grids, inline editors, validation jumps, or any scroll-into-view behavior, or when scrolling looks jumpy or glitchy while moving between cards.
---

# Caiman Focus Scroll

Moving focus should scroll **only when the target is not fully visible**. A
focused card that is already on screen must not move. If the viewport pins each
focused card to the top, every `j`/`k` press shifts the whole screen, which reads
as a glitch even though nothing is wrong.

Two things scroll on focus, in this order:

1. Textual's `Screen.set_focus` centres a target that is off-screen
   (`scroll_to_center`); a visible target is left alone. Keep this default.
2. Caiman's focus handler then scrolls the card's frame **minimally**, which
   only matters when the dotted shadow row would otherwise sit just out of view.

Anything that re-scrolls with `top=True` afterwards overrides both and causes the
glitch.

## The rule

- Call `scroll_visible(animate=False)` **without** `top=True`. Minimal
  scrolling is Textual's default; `top=True` pins the widget to the top on every
  focus change.
- Scroll the widget that owns the complete visual footprint. For Caiman cards,
  that is the **frame** (`CardFrame`/`EditorFrame`), not the focusable face,
  so the reserved dotted shadow row on the right and bottom edges scrolls into
  view too. The shared handler is `OverviewCard.on_focus` in
  `src/caiman/ui/cards.py`:

  ```python
  def on_focus(self):
      self.parent.add_class('selected')
      # Scroll only as far as needed; the frame includes the shadow row.
      self.parent.scroll_visible(animate=False)
  ```

- Keep `animate=False`. Animated scrolling under rapid Vim movement lags behind
  focus and exposes stale shadows.
- For widgets mounted in this cycle, such as a newly added card or row, defer the
  scroll until layout exists: `self.call_after_refresh(row.scroll_visible,
  animate=False)`. Scrolling before layout uses a zero-size region.
- Reordering cards without moving focus, as little caiman does when it moves the
  most recently touched document first, must not scroll. Only focus changes and
  explicit user actions scroll.

`top=True` is appropriate only for a deliberate jump whose purpose is to show
something from its start, such as opening a new screen at a section heading. It
is not appropriate for ordinary navigation, focus handlers, or validation
feedback. Validation jumps to the first invalid field also use minimal scrolling.

Do not hand-compute scroll offsets from card heights. Region geometry changes
with responsive column counts, unequal card heights, and expanded editors; let
`scroll_visible` measure the rendered region.

## Verification

Test observable scrolling, not implementation calls. At a height where the list
overflows:

1. Focus a card, then move to a neighbour that is already fully visible. Assert
   the scroll container's `scroll_y` is unchanged.
2. Press `j` until the first press that scrolls. Assert the whole focused
   **frame**, shadow row included, lies inside the container's `content_region`,
   and that its top is below the container's top (it was not pinned). Do not
   assert an exact position: Textual centres the target, and the position
   depends on card heights.
3. Move back up past the top edge and check the symmetric case when that path
   changes.

`tests/test_dashboard.py::test_focus_scrolls_minimally_instead_of_pinning_cards_to_the_top`
is an example. Use `pilot.pause()` after key presses before reading regions.
Exercise narrow and wide layouts when the change affects column count.
