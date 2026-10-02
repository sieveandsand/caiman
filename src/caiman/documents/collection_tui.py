"""Create and edit collections by choosing already registered documents."""

import asyncio
from copy import deepcopy

from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static

from caiman.documents.cards import DocumentCard, document_name
from caiman.documents.collections import CollectionService
from caiman.storage.store import Store
from caiman.ui.cards import CARD_CSS, CardFrame, resize_card_grid
from caiman.ui.navigation import NavigationApp
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class MemberCard(DocumentCard):
    def __init__(self, record, *, index, chosen=False):
        super().__init__(record, index=index)
        self.chosen = chosen

    def format_card(self, width):
        super().format_card(width)
        self.label = self.label.append_text('\n\n' + ('✓ Included' if self.chosen else 'Include document'), style='bold #7fdc4f')
        height = len(self.label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class CollectionApp(NavigationApp):
    TITLE = 'Caiman · Collection'
    CSS = TERMINAL_CSS + CARD_CSS + '''
    #fields { height: auto; }
    .document-grid { height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }
    Label { color: #eef3e6; text-style: bold; }
    #selection-count { height: auto; margin: 1 0; color: #7fdc4f; }
    Button { width: auto; }
    '''

    def __init__(self, *, root, compartments, record=None):
        super().__init__()
        apply_theme(self)
        self.service = CollectionService(Store(root))
        self.compartments = set(compartments)
        self.original = deepcopy(record)
        self.draft = deepcopy(record['manifest']) if record else {}
        self.records = []
        self.prepared = None
        self.busy = False
        self.loaded = False

    def compose(self):
        yield Static('caiman  /  ' + ('edit collection' if self.original else 'add collection'), id='brand')
        with VerticalScroll(id='body'):
            with Vertical(id='fields'):
                yield Label('Collection Name')
                yield Input(self.draft.get('name', ''), id='name')
                yield Label('Description')
                yield Input(self.draft.get('description', ''), id='description')
                yield Label('Access')
                yield Select([('Public', 'public')] + [(name, name) for name in sorted(self.compartments)],
                             value=self.original['compartment'] if self.original else Select.NULL,
                             prompt='Choose access', id='access', disabled=bool(self.original))
                yield Static('Select public documents or documents in the chosen compartment.', classes='hint')
                yield Static('Choose from existing documents', id='selection-count')
                yield Grid(classes='document-grid', id='documents')
            yield Static('', id='review', markup=False)
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Review changes', id='review-save', variant='primary', disabled=True)
            yield Button('Edit selection', id='edit-selection')
            yield Button('Back to documents', id='cancel')

    async def on_mount(self):
        self.query_one('#review').display = False
        self.query_one('#edit-selection').display = False
        try:
            records = await asyncio.to_thread(self.service.documents.list_documents, compartments=self.compartments)
            # Old pinned revisions must remain selectable even when refs move.
            members = await asyncio.to_thread(self.service.members, self.original, compartments=self.compartments) if self.original else []
            merged = {(r['compartment'], r['digest']): r for r in records + members}
            self.records = sorted(merged.values(), key=lambda r: (document_name(r['manifest']), r['compartment'], r['digest']))
            selected = {(r['compartment'], r['digest']) for r in members}
            cards = [MemberCard(r, index=i, chosen=(r['compartment'], r['digest']) in selected)
                     for i, r in enumerate(self.records)]
            await self.query_one('#documents', Grid).mount(*(CardFrame(card) for card in cards))
            self.loaded = True
            self.query_one('#review-save', Button).disabled = False
            self.resize_cards()
            self.update_count()
            if not cards:
                self.query_one('#status', Static).update('No existing documents. Add a document from the Documents page first.')
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        self.query_one('#name', Input).focus()

    def resize_cards(self):
        columns = 2 if self.size.width >= 100 else 1
        width = max(16, (self.size.width - 6 - (columns - 1) - 2) // columns)
        resize_card_grid(self.query_one('#documents', Grid), width, columns)

    def on_resize(self):
        self.resize_cards()

    def update_count(self):
        count = sum(card.chosen for card in self.query(MemberCard))
        self.query_one('#selection-count', Static).update(f'{count} selected · {len(self.records)} existing documents')

    def collect(self):
        access = self.query_one('#access', Select).value
        if access == Select.NULL:
            raise ValueError('Choose collection access')
        data = deepcopy(self.draft)
        data.update(name=self.query_one('#name', Input).value.strip(),
                    description=self.query_one('#description', Input).value.strip(),
                    labels={'public': access == 'public', 'compartments': [] if access == 'public' else [access]},
                    documents=[{'digest': c.record['digest'], 'compartment': c.record['compartment']}
                               for c in self.query(MemberCard) if c.chosen])
        return data

    def show_review(self, reviewing):
        self.query_one('#fields').display = not reviewing
        self.query_one('#review').display = reviewing
        self.query_one('#edit-selection').display = reviewing
        self.query_one('#review-save', Button).label = 'Save collection' if reviewing else 'Review changes'

    def action_cancel(self):
        if not self.busy:
            self.exit(None)

    def action_vim_move(self, direction):
        before = self.focused
        super().action_vim_move(direction)
        if before is self.focused and isinstance(before, MemberCard):
            if direction in {'h', 'k'}:
                self.screen.focus_previous()
            else:
                self.screen.focus_next()

    async def on_button_pressed(self, event):
        if self.busy:
            return
        if isinstance(event.button, MemberCard):
            event.button.chosen = not event.button.chosen
            self.resize_cards()
            self.update_count()
            return
        action = event.button.id
        if action == 'cancel':
            self.action_cancel()
        elif action == 'edit-selection':
            self.prepared = None
            self.show_review(False)
            self.query_one('#name', Input).focus()
        elif action == 'review-save' and self.loaded:
            self.busy = True
            self.query_one('#review-save', Button).disabled = True
            try:
                if self.prepared is None:
                    self.prepared = await asyncio.to_thread(self.service.prepare, self.collect(), compartments=self.compartments)
                    m = self.prepared['manifest']
                    names = [f"  {document_name(c.record['manifest'])} · {c.record['manifest']['version']} · {c.record['compartment']}"
                             for c in self.query(MemberCard) if c.chosen]
                    self.query_one('#review', Static).update('\n'.join([
                        m['name'], m['description'], '', f"Access: {self.prepared['compartment']}",
                        f"{len(names)} documents", *names]))
                    self.query_one('#status', Static).update('')
                    self.show_review(True)
                    self.query_one('#review-save').focus()
                else:
                    result = await asyncio.to_thread(self.service.register, self.prepared,
                        compartments=self.compartments, expected_digest=self.original['digest'] if self.original else None)
                    self.exit(result)
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.busy = False
                self.query_one('#review-save', Button).disabled = False
