"""A guided board form: one field per declared value, Vim as the escape hatch.

The form owns every field the board schema declares, so an ordinary edit — a
silicon revision, an alias, a note, one more document pin — never requires
knowing the JSON shape. What it does not own it carries through untouched: the
draft it returns starts from the manifest it was given and only the keys the
form rendered are replaced. A `caiman.board/1` snapshot is shown read-only for
that reason; its packed part identity is a different shape, and rewriting it
here would silently migrate a stored version (S-11, I-4).

Nothing here writes: `collect` produces a draft, and registration stays behind
the review screen that already exists.
"""

from __future__ import annotations

from copy import deepcopy
import json

from rich.text import Text
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.suggester import SuggestFromList
from textual.widgets import Button, Collapsible, Input, Label, Static

from caiman.configurations.files import vendor_suggestions
from caiman.configurations.models import board_is_legacy
from caiman.ui.navigation import NavigationApp
from caiman.ui.cards import AddCardFrame, DotShadow, EditorFrame
from caiman.ui.theme import TERMINAL_CSS, apply_theme


BOARD_FORM_CSS = TERMINAL_CSS + EditorFrame.DEFAULT_CSS + '''
/* Every repeated container sizes to its rows; the default 1fr would leave one
   section holding all the leftover height and the rest crammed under it. */
#board-documents, #parts, #links, .documents { height: auto; }
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


def alias_text(aliases: dict) -> str:
    """Aliases as `name = value` pairs, which is how they are edited."""
    return ', '.join(f'{key} = {value}' for key, value in sorted((aliases or {}).items()))


def vendor_suggester(manifest: dict | None = None) -> SuggestFromList:
    """Case-insensitive completion, so typing `NX` offers the canonical `nxp`.

    Textual only takes a suggestion when the caret is moved onto it, so this
    completes what the engineer types and never replaces or rejects it.
    """
    return SuggestFromList(vendor_suggestions(manifest), case_sensitive=False)


def parse_aliases(text: str) -> dict:
    """Read `name = value` pairs back. Keys and values stay declared strings."""
    aliases = {}
    for entry in text.split(','):
        if not entry.strip():
            continue
        key, separator, value = entry.partition('=')
        if not separator:
            raise ValueError(f'Alias entry needs a name = value pair: {entry.strip()}')
        key, value = key.strip(), value.strip()
        if key in aliases:
            raise ValueError(f'Duplicate alias name: {key}')
        aliases[key] = value
    return aliases


class Row(Vertical):
    """One repeated record. Fields carry classes, not ids, so rows can repeat."""

    def __init__(self, data: dict):
        super().__init__(classes='row')
        self.data = deepcopy(data) if isinstance(data, dict) else {}

    def text_field(self, key: str, label: str, *, suggester=None):
        yield Label(label, classes='field-label')
        value = self.data.get(key, '')
        yield Input(value='' if value is None else str(value), suggester=suggester,
                    classes=f'field field-{key}')

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
        self.query_one('.card-summary', Button).label = self.summary(self.summary_data())

    def summary_hint(self):
        return 'Collapse' if self.has_class('expanded') else 'Enter to edit'


class DocumentRow(Row):
    """A document pin. Compartment is not a field: board documents are public."""

    def compose(self):
        yield from self.text_field('ref', 'Document Ref')
        yield from self.text_field('digest', 'Manifest Digest (optional)')
        yield from self.text_field('notes', 'Notes (optional)')
        yield from self.actions('Remove document')

    def collect(self) -> dict:
        selector = self.carry('ref', 'digest', 'notes')
        for key in ('ref', 'digest', 'notes'):
            if self.value(key):
                selector[key] = self.value(key)
        return selector


class BoardDocumentCard(CardRow, DocumentRow):
    kind = 'document'
    first_field = 'ref'

    def editor_fields(self):
        yield from DocumentRow.compose(self)

    def summary_data(self):
        return {key: self.value(key) for key in ('ref', 'digest', 'notes')}

    def summary(self, data):
        label = Text()
        label.append(data.get('ref') or ('Pinned board document' if data.get('digest') else 'New board document'), style='bold #dfe6d3')
        label.append('\n\nPublic · Board document', style='bold #aab69c')
        label.append('\n\n' + self.summary_hint(), style='#aab69c')
        return label


class PartRow(CardRow):
    """A compact part card whose editor stays mounted to retain draft values."""

    kind = 'part'
    first_field = 'part'

    def __init__(self, data: dict, *, vendors=None, expanded=False):
        super().__init__(data, expanded=expanded)
        self.vendors = vendors

    def summary(self, data):
        label = Text()
        label.append(data.get('part') or 'New part', style='bold #dfe6d3')
        label.append('\n\n' + (data.get('vendor') or 'Vendor not set'), style='#aab69c')
        label.append('\n' + (data.get('role') or 'Role not set'), style='#7fdc4f')
        details = []
        if data.get('silicon_revision'):
            details.append('Silicon ' + data['silicon_revision'])
        details.append(f"{len(data.get('documents', []) or [])} document pins")
        label.append('\n\n' + ' · '.join(details), style='bold #aab69c')
        label.append('\n\n' + self.summary_hint(), style='#aab69c')
        return label

    def summary_data(self):
        data = {key: self.value(key) for key in ('part', 'vendor', 'role', 'silicon_revision')}
        data['documents'] = list(self.query(DocumentRow))
        return data

    def editor_fields(self):
        yield from self.text_field('part', 'Part Name')
        yield from self.text_field('role', 'Part Role')
        yield from self.text_field('vendor', 'Vendor', suggester=self.vendors)
        yield from self.text_field('silicon_revision', 'Silicon Revision (optional)')
        yield Label('Aliases (optional)', classes='field-label')
        yield Input(value=alias_text(self.data.get('aliases')), placeholder='refdes = U1, mpn = S32K344EHTAR',
                    classes='field field-aliases')
        yield from self.text_field('notes', 'Notes (optional)')
        yield Label('Document Pins', classes='field-label')
        yield Vertical(*(DocumentRow(pin) for pin in self.data.get('documents', []) or []), classes='documents')
        with Horizontal(classes='section-actions'):
            yield Button('Add document', classes='add-document')
            yield Button('Remove part', classes='remove-row')

    def collect(self) -> dict:
        part = self.carry('part', 'role', 'vendor', 'silicon_revision', 'aliases', 'notes', 'documents')
        for key in ('part', 'role', 'vendor', 'silicon_revision', 'notes'):
            if self.value(key) or key in {'part', 'role', 'vendor'}:
                part[key] = self.value(key)
        try:
            aliases = parse_aliases(self.value('aliases'))
        except ValueError:
            self.set_expanded(True)
            self.query_one('.field-aliases', Input).focus()
            raise
        if aliases:
            part['aliases'] = aliases
        part['documents'] = [row.collect() for row in self.query(DocumentRow)]
        return part


class LinkRow(CardRow):
    kind = 'link'
    first_field = 'name'

    def summary_data(self):
        return self.collect()

    def summary(self, data):
        label = Text()
        label.append(data.get('name') or 'New link', style='bold #dfe6d3')
        label.append('\n\n' + (', '.join(data.get('between') or []) or 'Endpoints not set'), style='#7fdc4f')
        label.append('\n\n' + self.summary_hint(), style='#aab69c')
        return label

    def editor_fields(self):
        yield from self.text_field('name', 'Link Name')
        endpoints = self.data.get('between') or []
        joined = ', '.join(endpoints) if isinstance(endpoints, list) else str(endpoints)
        yield Label('Between (comma separated)', classes='field-label')
        yield Input(value=joined, classes='field field-between')
        yield from self.text_field('notes', 'Notes (optional)')
        yield from self.actions('Remove link')

    def collect(self) -> dict:
        link = self.carry('name', 'between', 'notes')
        link['name'] = self.value('name')
        link['between'] = [item.strip() for item in self.value('between').split(',') if item.strip()]
        if self.value('notes'):
            link['notes'] = self.value('notes')
        return link


class BoardFormApp(NavigationApp):
    """Edit a board field by field. Exits with ('review'|'raw', draft), or None."""

    TITLE = 'Caiman · Edit board'
    CSS = BOARD_FORM_CSS

    def __init__(self, *, original: dict, draft: dict | None = None, message: str = ''):
        super().__init__()
        apply_theme(self)
        self.original = deepcopy(original)
        self.draft = deepcopy(original if draft is None else draft)
        # Directed from/to links have no guided shape; a legacy board has a
        # different one altogether. Both stay editable, in raw JSON only.
        self.legacy = board_is_legacy(self.draft)
        self.directed = any(isinstance(link, dict) and {'from', 'to'} & link.keys()
                            for link in self.draft.get('links', []) or [])
        self.read_only = self.legacy or self.directed
        self.message = message
        self.vendors = vendor_suggester(self.draft)

    def navigation_help(self):
        return 'NAVIGATE · hjkl move · Enter open card · Enter/i edit field · Tab next · q back'

    def action_vim_move(self, direction):
        focused = self.focused
        super().action_vim_move(direction)
        # At the grid edge, continue into the surrounding board form.
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

    def field(self, key: str, label: str, *, suggester=None):
        yield Label(label, classes='field-label')
        yield Input(value=str(self.draft.get(key, '') or ''), suggester=suggester, id=f'board-{key}')

    def compose(self):
        yield Static('caiman  /  edit board', id='brand')
        with VerticalScroll(id='body'):
            if self.read_only:
                yield Static(self.read_only_reason(), classes='hint', markup=False)
                yield Static(json.dumps(self.draft, indent=2, ensure_ascii=False), markup=False)
            else:
                yield from self.field('board', 'Board Name')
                yield from self.field('version', 'Version')
                yield from self.field('vendor', 'Board Vendor', suggester=self.vendors)
                yield from self.field('notes', 'Notes (optional)')
                with Collapsible(title=f"Board Documents · {len(self.draft.get('documents', []) or [])} declared", collapsed=False):
                    with Grid(id='board-documents', classes='card-grid'):
                        for pin in self.draft.get('documents', []) or []:
                            yield BoardDocumentCard(pin)
                        yield add_card('Add board document', id='add-board-document')
                with Collapsible(title=f"Parts · {len(self.draft.get('parts', []) or [])} declared", collapsed=False):
                    with Grid(id='parts', classes='card-grid'):
                        for part in self.draft.get('parts', []) or []:
                            yield PartRow(part, vendors=self.vendors)
                        yield add_card('Add part', id='add-part')
                with Collapsible(title=f"Links · {len(self.draft.get('links', []) or [])} declared", collapsed=False):
                    with Grid(id='links', classes='card-grid'):
                        for link in self.draft.get('links', []) or []:
                            yield LinkRow(link)
                        yield add_card('Add link', id='add-link')
        yield Static(self.message, id='form-error', markup=False)
        with Horizontal(id='navigation'):
            if not self.read_only:
                yield Button('Review changes', id='review-changes', variant='primary')
            yield Button('Edit raw JSON in Vim', id='raw', variant='primary' if self.read_only else 'default')
            yield Button('Back to boards', id='cancel')
        yield self.navigation_hint()

    def on_mount(self):
        self.resize_grids(self.size.width)

    def on_resize(self, event):
        self.resize_grids(event.size.width)

    def resize_grids(self, width):
        for grid in self.query('.card-grid'):
            grid.styles.grid_size_columns = 2 if width >= 100 else 1

    def read_only_reason(self) -> str:
        if self.legacy:
            return ('This board is a caiman.board/1 snapshot. Its part identity is packed into one field, '
                    'which the guided form does not author — editing it here would rewrite a stored version. '
                    'Use raw JSON, or declare a new version with the current schema.')
        return ('This board declares a link with from/to endpoints, which the guided form does not author. '
                'Use raw JSON so no declared endpoint is dropped.')

    def collect(self) -> dict:
        """Build a draft from the form, keeping every field it does not render."""
        data = deepcopy(self.draft)
        # Lineage is not a form field. `derives_from` and `relation` ride through
        # untouched from the snapshot, like every other value the form does not
        # render, so a board that declares lineage keeps it.
        for key in ('board', 'version', 'vendor', 'notes'):
            value = self.query_one(f'#board-{key}', Input).value.strip()
            if value or key in {'board', 'version'}:
                data[key] = value
            else:
                data.pop(key, None)
        documents = [row.collect() for row in self.query_one('#board-documents').query(BoardDocumentCard)]
        if documents:
            data['documents'] = documents
        else:
            data.pop('documents', None)
        data['parts'] = [row.collect() for row in self.query_one('#parts').query(PartRow)]
        data['links'] = [row.collect() for row in self.query_one('#links').query(LinkRow)]
        return data

    async def add_card(self, button, row: CardRow) -> None:
        await button.parent.parent.mount(row, before=button.parent)
        self.call_after_refresh(row.query_one(f'.field-{row.first_field}', Input).focus)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        event.stop()
        if button.id == 'cancel':
            self.exit(None)
        elif button.id in {'review-changes', 'raw'}:
            action = 'review' if button.id == 'review-changes' else 'raw'
            try:
                self.exit((action, deepcopy(self.draft) if self.read_only else self.collect()))
            except ValueError as error:
                self.query_one('#form-error', Static).update(str(error))
        elif button.has_class('card-summary') or button.has_class('collapse-card'):
            card = next(node for node in button.ancestors if isinstance(node, CardRow))
            card.set_expanded(not card.has_class('expanded'))
            target = (card.query_one(f'.field-{card.first_field}', Input) if card.has_class('expanded')
                      else card.query_one('.card-summary', Button))
            self.call_after_refresh(target.focus)
        elif button.id == 'add-part':
            part = PartRow({'part': '', 'role': '', 'vendor': '', 'documents': []},
                           vendors=self.vendors, expanded=True)
            await self.add_card(button, part)
        elif button.id == 'add-link':
            await self.add_card(button, LinkRow({'name': '', 'between': []}, expanded=True))
        elif button.id == 'add-board-document':
            await self.add_card(button, BoardDocumentCard({}, expanded=True))
        elif button.has_class('add-document'):
            row = next(node for node in button.ancestors if isinstance(node, PartRow))
            await self.add_row_within(row, DocumentRow({}))
        elif button.has_class('remove-row'):
            row = next(node for node in button.ancestors if isinstance(node, Row))
            container = row.parent
            await row.remove()
            # Focus never disappears with the row it was standing on.
            remaining = container.query(Input) if container is not None else []
            target = (container.query_one('.add-card', Button) if isinstance(row, CardRow) else
                      next((field for field in remaining if all(node.display for node in (field, *field.ancestors))), None)
                      or self.query_one('#review-changes', Button))
            self.call_after_refresh(target.focus)

    async def add_row_within(self, part: PartRow, row: DocumentRow) -> None:
        await part.query_one('.documents').mount(row)
        self.call_after_refresh(row.scroll_visible, animate=False)

    def action_cancel(self) -> None:
        self.exit(None)
