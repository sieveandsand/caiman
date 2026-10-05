"""Guided entity editors: top-level fields, then card grids of repeated records.

Shared by the board and project forms. A card keeps its fields mounted while
collapsed, so an incomplete draft survives Done; nothing here validates, saves,
or registers anything.
"""

from __future__ import annotations

from copy import deepcopy

from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label

from caiman.ui.cards import AddCardFrame, DotShadow, EditorFrame
from caiman.ui.heading import card_heading
from caiman.ui.navigation import NavigationApp
from caiman.ui.theme import TERMINAL_CSS


EDITOR_CSS = TERMINAL_CSS + EditorFrame.DEFAULT_CSS + '''
/* Every repeated container sizes to its rows; the default 1fr would leave one
   section holding all the leftover height and the rest crammed under it. */
.card-grid, .nested-rows { height: auto; }
.row { height: auto; border-left: outer #33422e; padding: 0 0 0 1; margin: 1 0 0 0; }
.card-grid { grid-size: 2; grid-columns: 1fr; grid-rows: auto; grid-gutter: 1 2; }
.record-card { height: auto; min-width: 0; margin: 0; }
.record-card > .editor-face { padding: 0 1; border: solid #33422e; }
.record-card.selected > .editor-face { border: solid #7fdc4f; }
.card-summary { width: 100%; height: auto; min-height: 0; margin: 0; padding: 0; text-align: left; content-align: left top; }
.card-summary:hover, .card-summary:focus { background: #000000; color: #dfe6d3; text-style: none; }
.card-editor { height: auto; display: none; }
.record-card.expanded .card-editor { display: block; }
.add-card { width: 100%; min-width: 0; height: 9; margin: 0; border: solid #33422e; color: #7fdc4f; content-align: center middle; text-align: center; }
.add-card:hover, .add-card:focus { border: solid #7fdc4f; background: #000000; }
.row-actions, .section-actions { height: 3; margin: 0; }
.section-actions { margin: 1 0 0 0; }
Button { width: auto; }
.field-label { height: auto; min-height: 2; margin: 1 0 0 0; content-align: left bottom; text-style: bold; color: #eef3e6; }
#form-error { height: auto; padding: 0 2; color: #e69a89; }
'''


def comma_list(text: str) -> list[str]:
    return [item.strip() for item in text.split(',') if item.strip()]


class Row(Vertical):
    """One repeated record. Fields carry classes, not ids, so rows can repeat."""

    def __init__(self, data: dict):
        super().__init__(classes='row')
        self.data = deepcopy(data) if isinstance(data, dict) else {}

    def on_mount(self):
        # Picker attachments and nested rows can change the draft without typing.
        self.app.call_after_refresh(self.app.update_review_button)

    def text_field(self, key: str, label: str, *, suggester=None, placeholder=''):
        yield Label(label, classes='field-label')
        value = self.data.get(key, '')
        yield Input(value='' if value is None else str(value), suggester=suggester,
                    placeholder=placeholder, classes=f'field field-{key}')

    def value(self, key: str) -> str:
        return self.query_one(f'.field-{key}', Input).value.strip()

    def actions(self, label: str):
        with Horizontal(classes='row-actions'):
            yield Button(label, classes='remove-row')

    def carry(self, *keys) -> dict:
        """Start from what was stored so unrendered fields survive an edit."""
        return {key: value for key, value in self.data.items() if key not in keys}


def add_card(label, *, id):
    return AddCardFrame(label, id=id)


class CardRow(Row, EditorFrame):
    """Keep editors mounted while a summary card is collapsed."""

    kind = ''
    first_field = ''
    # Summary text width, known once the card is laid out; resizing re-renders.
    summary_width = 80

    def __init__(self, data, *, expanded=False):
        super().__init__(data)
        self.remove_class('row')
        self.add_class('editor-frame', 'record-card', f'{self.kind}-card')
        self.set_class(expanded, 'expanded')

    def compose(self):
        yield DotShadow('', classes='card-shadow', markup=False)
        with Vertical(classes='editor-face'):
            yield Button(self.summary(self.data), classes=f'card-summary {self.kind}-summary dashboard-tile')
            with Vertical(classes=f'card-editor {self.kind}-editor'):
                yield from self.editor_fields()
                with Horizontal(classes='row-actions'):
                    yield Button('Done', classes=f'collapse-card collapse-{self.kind}', variant='primary')

    def set_expanded(self, expanded):
        self.set_class(expanded, 'expanded')
        self.refresh_summary()

    def refresh_summary(self):
        self.query_one('.card-summary', Button).label = self.summary(self.summary_data())

    def heading(self, label, value):
        """Use the same wrapping identity treatment as gallery cards."""
        label.append(card_heading(value, self.summary_width))

    def on_resize(self, event):
        # Shadow margin, face border and padding, and Button line padding.
        width = max(1, event.size.width - 7)
        if width != self.summary_width:
            self.summary_width = width
            self.refresh_summary()

    def summary_hint(self):
        return 'Collapse' if self.has_class('expanded') else 'Enter to edit'


class EditorFormApp(NavigationApp):
    """Grid navigation, responsive columns, and card add/open/remove handling."""

    CSS = EDITOR_CSS

    def navigation_help(self):
        return 'NAVIGATE · hjkl move · Enter open card · Enter/i edit field · Tab next · q back'

    def action_vim_move(self, direction):
        focused = self.focused
        super().action_vim_move(direction)
        # At the grid edge, continue into the surrounding form.
        if focused is not None and focused.has_class('dashboard-tile') and self.focused is focused:
            if direction in {'h', 'k'}:
                self.screen.focus_previous()
            else:
                self.screen.focus_next()

    def _move_tile(self, focused, direction):
        # Summary buttons sit inside card borders; compare the outer cards so
        # an add card and its neighbours are treated as the same grid row.
        def region(button):
            return next((node.region for node in button.ancestors if isinstance(node, EditorFrame)), button.region)

        origin = region(focused)
        candidates = []
        for button in self.query('.dashboard-tile'):
            if button is focused or not all(node.display for node in (button, *button.ancestors)):
                continue
            target = region(button)
            dx = target.center[0] - origin.center[0]
            dy = target.y - origin.y
            if direction in {'h', 'l'}:
                if dy or (dx <= 0 if direction == 'l' else dx >= 0):
                    continue
                score = (abs(dx), 0)
            else:
                if (dy <= 0 if direction == 'j' else dy >= 0):
                    continue
                score = (abs(dx), abs(dy))
            candidates.append((score, button))
        if candidates:
            min(candidates, key=lambda item: item[0])[1].focus()

    def on_mount(self):
        self.resize_grids(self.size.width)
        self.call_after_refresh(self.update_review_button)

    def update_review_button(self):
        buttons = self.query('#review-changes')
        if not buttons:
            return  # Unsupported shapes offer only the raw editor.
        try:
            unchanged = self.collect() == self.original
        except ValueError:
            # Invalid edits still need access to review's validation feedback.
            unchanged = False
        buttons.first(Button).disabled = unchanged

    def on_input_changed(self, event: Input.Changed):
        self.update_review_button()

    def on_resize(self, event):
        self.resize_grids(event.size.width)

    def resize_grids(self, width):
        for grid in self.query('.card-grid'):
            grid.styles.grid_size_columns = 2 if width >= 100 else 1

    async def add_card(self, button, row: CardRow) -> None:
        """Insert an expanded record just before its section's add card."""
        await button.parent.parent.mount(row, before=button.parent)
        self.call_after_refresh(row.query_one(f'.field-{row.first_field}', Input).focus)

    def toggle_card(self, button) -> None:
        card = next(node for node in button.ancestors if isinstance(node, CardRow))
        card.set_expanded(not card.has_class('expanded'))
        target = (card.query_one(f'.field-{card.first_field}', Input) if card.has_class('expanded')
                  else card.query_one('.card-summary', Button))
        self.call_after_refresh(target.focus)

    async def add_row_within(self, container, row: Row) -> None:
        await container.mount(row)
        self.call_after_refresh(row.scroll_visible, animate=False)

    async def remove_row(self, button) -> Row:
        row = next(node for node in button.ancestors if isinstance(node, Row))
        container = row.parent
        await row.remove()
        self.update_review_button()
        # Focus never disappears with the row it was standing on.
        if isinstance(row, CardRow):
            target = container.query_one('.add-card', Button)
        else:
            visible = [field for field in container.query(Input)
                       if all(node.display for node in (field, *field.ancestors))]
            owner = next((node for node in container.ancestors if isinstance(node, CardRow)), None)
            target = (visible[0] if visible else
                      owner.query_one(f'.field-{owner.first_field}', Input) if owner is not None else
                      self.query_one('#review-changes', Button))
        self.call_after_refresh(target.focus)
        return row
