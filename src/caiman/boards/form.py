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
from caiman.ui.editor import EDITOR_CSS, CardRow, EditorFormApp, Row, add_card, comma_list
from caiman.ui.theme import apply_theme


BOARD_FORM_CSS = EDITOR_CSS + '''
.documents { height: auto; }
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


class DocumentRow(Row):
    """A document pin with an optional pod route."""

    def compose(self):
        yield from self.text_field('ref', 'Document Ref')
        yield from self.text_field('pod', 'Pod (optional)')
        yield from self.text_field('digest', 'Manifest Digest (optional)')
        yield from self.text_field('document', 'Document ID (optional)')
        yield from self.text_field('blob', 'Pinned Blob (with Document ID)')
        yield from self.text_field('notes', 'Notes (optional)')
        yield from self.actions('Remove document')

    def collect(self) -> dict:
        selector = self.carry('ref', 'digest', 'notes', 'pod', 'document', 'blob')
        for key in ('ref', 'digest', 'notes', 'pod', 'document', 'blob'):
            if self.value(key):
                selector[key] = self.value(key)
        return selector


class BoardDocumentCard(CardRow, DocumentRow):
    kind = 'document'
    first_field = 'ref'

    def editor_fields(self):
        yield from DocumentRow.compose(self)

    def summary_data(self):
        return {key: self.value(key) for key in ('ref', 'digest', 'notes', 'pod', 'document', 'blob')}

    def summary(self, data):
        label = Text()
        self.heading(label, data.get('ref') or data.get('document') or ('Pinned board document' if data.get('digest') else 'New board document'))
        label.append('\n\nBoard document', style='bold #aab69c')
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
        self.heading(label, data.get('part') or 'New part')
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
        self.heading(label, data.get('name') or 'New link')
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
        link['between'] = comma_list(self.value('between'))
        if self.value('notes'):
            link['notes'] = self.value('notes')
        return link


class BoardFormApp(EditorFormApp):
    """Edit a board field by field. Exits with ('review'|'raw'|'delete', draft), or None."""

    TITLE = 'Caiman · Edit board'
    CSS = BOARD_FORM_CSS + '''
    #board-pod { margin-bottom: 1; }
    #navigation { layout: grid; grid-size: 2; grid-columns: 1fr; grid-rows: 3; height: auto; }
    #navigation Button { width: 100%; min-width: 0; margin: 0; }
    #navigation Button:focus { border: double #7fdc4f; }
    '''

    def __init__(self, *, original: dict, draft: dict | None = None, message: str = '', service=None):
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
        self.service = service
        self.pod = self.draft.get('pod') or 'public'

    def on_resize(self, event):
        self.query_one('#navigation').styles.grid_size_columns = 4 if event.size.width >= 100 else 2

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
                yield from self.field('notes', 'Description')
                yield from self.field('vendor', 'Board Vendor', suggester=self.vendors)
                yield Label('Pod', classes='field-label')
                yield Static(self.service.store.pod_name(self.pod) if self.service else self.pod,
                             id='board-pod', markup=False)
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
                yield Button('Review changes', id='review-changes', variant='primary', disabled=True)
            yield Button('Edit raw JSON in Vim', id='raw', variant='primary' if self.read_only else 'default')
            yield Button('Delete board', id='delete', variant='error')
            yield Button('Back to boards', id='cancel')
        yield self.navigation_hint()

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

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        event.stop()
        if button.id == 'cancel':
            self.exit(None)
        elif button.id in {'review-changes', 'raw', 'delete'}:
            action = 'review' if button.id == 'review-changes' else button.id
            try:
                self.exit((action, deepcopy(self.draft) if self.read_only else self.collect()))
            except ValueError as error:
                self.query_one('#form-error', Static).update(str(error))
        elif button.has_class('card-summary') or button.has_class('collapse-card'):
            self.toggle_card(button)
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
            await self.add_row_within(row.query_one('.documents'), DocumentRow({}))
        elif button.has_class('remove-row'):
            await self.remove_row(button)

    def action_cancel(self) -> None:
        self.exit(None)
