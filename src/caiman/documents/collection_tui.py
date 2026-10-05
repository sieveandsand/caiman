"""Create and edit collections by choosing already registered documents."""

import asyncio
from copy import deepcopy

from rich.text import Text

from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Collapsible, Input, Label, Select, Static

from caiman.documents.cards import document_name
from caiman.documents.collections import CollectionService
from caiman.documents.picker import DocumentPicker, document_pin
from caiman.storage.store import Store
from caiman.ui.editor import EDITOR_CSS, CardRow, EditorFormApp, add_card
from caiman.ui.theme import apply_theme


class MemberCard(CardRow):
    """An included document with explicit actions inside its expanded card."""

    kind = 'member'

    def __init__(self, record, *, index):
        self.record = record
        super().__init__(record)
        self.id = f'document-{index}'

    def summary_data(self):
        return self.record

    def summary(self, record):
        manifest = record['manifest']
        label = Text()
        self.heading(label, document_name(manifest))
        label.append(f"\n\n  [ {manifest['version']} ]", style='#7fdc4f')
        if manifest.get('description'):
            label.append('\n\n' + manifest['description'], style='bold #aab69c')
        return label

    def editor_fields(self):
        yield Label('Pod', classes='field-label')
        yield Static(self.record.get('pod_name', self.record['pod']), markup=False)
        manifest = self.record['manifest']
        if manifest.get('original_filename'):
            yield Label('Stored File', classes='field-label')
            yield Static(manifest['original_filename'], markup=False)
        with Horizontal(classes='row-actions'):
            yield Button('Remove from collection', classes='remove-member')


class CollectionApp(EditorFormApp):
    TITLE = 'Caiman · Collection'
    CSS = EDITOR_CSS + '''
    #fields { height: auto; }
    #pod { margin-bottom: 1; }
    .remove-member { border: solid #33422e; }
    .remove-member:focus { border: double #7fdc4f; }
    #selection-count { height: auto; margin: 1 0; color: #7fdc4f; }
    #choose-documents:focus { border: double #7fdc4f; }
    '''

    def __init__(self, *, root, pods=(), record=None, pod=None):
        super().__init__()
        apply_theme(self)
        self.service = CollectionService(Store(root))
        self.pods = set(pods)
        self.pod = record['pod'] if record else pod or self.service.store.pods.default
        self.original = deepcopy(record)
        self.draft = deepcopy(record['manifest']) if record else {}
        self.next_member_index = 0
        self.prepared = None
        self.busy = False
        self.loaded = False
        self.initial_values = None

    def compose(self):
        yield Static('caiman  /  ' + ('edit collection' if self.original else 'add collection'), id='brand')
        with VerticalScroll(id='body'):
            with Vertical(id='fields'):
                yield Label('Collection Name', classes='field-label')
                yield Input(self.draft.get('name', ''), id='name')
                yield Label('Description', classes='field-label')
                yield Input(self.draft.get('description', ''), id='description')
                yield Label('Pod', classes='field-label')
                if self.original:
                    yield Static(self.service.store.pod_name(self.pod), id='pod', markup=False)
                else:
                    yield Select([(r['name'], r['id']) for r in self.service.store.pods.list()],
                                 value=self.pod, prompt='Choose pod', id='pod')
                with Collapsible(title='Documents', collapsed=False):
                    yield Static('Choose from existing documents', id='selection-count')
                    with Grid(classes='card-grid', id='documents'):
                        yield add_card('Choose documents', id='choose-documents')
            yield Static('', id='review', markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Review changes', id='review-save', variant='primary', disabled=True)
            yield Button('Edit selection', id='edit-selection')
            yield Button('Back to documents', id='cancel')
        yield self.navigation_hint()

    async def on_mount(self):
        self.query_one('#review').display = False
        self.query_one('#edit-selection').display = False
        try:
            members = await asyncio.to_thread(self.service.members, self.original, pods=self.pods) if self.original else []
            members.sort(key=lambda r: (document_name(r['manifest']), r['pod'], r['digest']))
            cards = [MemberCard(record, index=i) for i, record in enumerate(members)]
            self.next_member_index = len(cards)
            await self.query_one('#documents', Grid).mount(
                *cards, before=self.query_one('#choose-documents').parent)
            self.loaded = True
            self.initial_values = self.collect()
            self.update_review_button()
            self.query_one('#choose-documents', Button).disabled = False
            self.resize_cards()
            self.update_count()
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        self.call_after_refresh(self.focus_initial_field)

    def focus_initial_field(self):
        # Opening starts at the page heading, even if mounting the cards caused
        # a pending focus scroll. Later navigation keeps normal minimal scrolling.
        self.query_one('#name', Input).focus(scroll_visible=False)
        self.query_one('#body', VerticalScroll).scroll_home(animate=False, immediate=True)

    def resize_cards(self):
        self.resize_grids(self.size.width)

    def update_count(self):
        count = len(self.query(MemberCard))
        self.query_one('#selection-count', Static).update(
            f'{count} selected' if count else 'No documents selected. Choose documents to add them.')
        self.update_review_button()

    def update_review_button(self):
        if not self.loaded:
            return
        unchanged = bool(self.original) and self.collect() == self.initial_values
        self.query_one('#review-save', Button).disabled = self.busy or unchanged

    def on_input_changed(self, event: Input.Changed):
        self.update_review_button()

    def on_select_changed(self, event: Select.Changed):
        self.update_review_button()

    def selected_pod(self):
        pod = self.pod if self.original else self.query_one('#pod', Select).value
        if pod == Select.NULL:
            raise ValueError('Choose a pod')
        return pod

    def collect(self):
        data = deepcopy(self.draft)
        data.update(name=self.query_one('#name', Input).value.strip(),
                    description=self.query_one('#description', Input).value.strip(),
                    pod=self.selected_pod(),
                    documents=[document_pin(c.record)
                               for c in self.query(MemberCard)])
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
        focused = self.focused
        if focused is not None and any(
            isinstance(node, MemberCard) and node.has_class('expanded')
            for node in focused.ancestors
        ):
            # Inside an open card, follow its controls like Tab instead of
            # treating the summary as a shortcut to a neighbouring grid tile.
            if direction in {'h', 'k'}:
                self.screen.focus_previous()
            else:
                self.screen.focus_next()
            return
        super().action_vim_move(direction)

    async def on_button_pressed(self, event):
        if self.busy:
            return
        event.stop()
        if event.button.has_class('card-summary') or event.button.has_class('collapse-card'):
            card = next(node for node in event.button.ancestors if isinstance(node, MemberCard))
            card.set_expanded(not card.has_class('expanded'))
            # Expansion lands on Done, never on the removal action.
            target = card.query_one('.collapse-card' if card.has_class('expanded') else '.card-summary', Button)
            self.call_after_refresh(target.focus)
            return
        if event.button.has_class('remove-member'):
            card = next(node for node in event.button.ancestors if isinstance(node, MemberCard))
            await card.remove()
            self.call_after_refresh(self.query_one('#choose-documents').focus)
            self.resize_cards()
            self.update_count()
            return
        action = event.button.id
        if action == 'cancel':
            self.action_cancel()
        elif action == 'choose-documents' and self.loaded:
            async def attach(records):
                for record in records or []:
                    card = next((card for card in self.query(MemberCard)
                                 if document_pin(card.record) == document_pin(record)), None)
                    if card is None:
                        card = MemberCard(record, index=self.next_member_index)
                        self.next_member_index += 1
                        await self.query_one('#documents', Grid).mount(
                            card, before=self.query_one('#choose-documents').parent)
                    else:
                        card.record = record
                        card.refresh_summary()
                self.query_one('#documents', Grid).sort_children(
                    key=lambda card: (0, document_name(card.record['manifest']),
                                      card.record['pod'], card.record['digest'])
                    if isinstance(card, MemberCard) else (1, '', '', ''))
                self.resize_cards()
                self.update_count()
                self.call_after_refresh(self.query_one('#choose-documents').focus)

            self.push_screen(DocumentPicker(service=self.service.documents, owner=self.selected_pod(),
                allow_collections=False,
                attached=[document_pin(card.record) for card in self.query(MemberCard)]), attach)
        elif action == 'edit-selection':
            self.prepared = None
            self.show_review(False)
            self.query_one('#name', Input).focus()
        elif action == 'review-save' and self.loaded:
            self.busy = True
            self.query_one('#review-save', Button).disabled = True
            try:
                if self.prepared is None:
                    self.prepared = await asyncio.to_thread(self.service.prepare, self.collect(), pods=self.pods)
                    m = self.prepared['manifest']
                    names = [f"  {document_name(c.record['manifest'])} · {c.record['manifest']['version']} · {c.record['pod']}"
                             for c in self.query(MemberCard)]
                    self.query_one('#review', Static).update('\n'.join([
                        m['name'], m['description'], '', f"Pod: {self.prepared['pod']}",
                        f"{len(names)} documents", *names]))
                    self.query_one('#status', Static).update('')
                    self.show_review(True)
                    self.query_one('#review-save').focus()
                else:
                    result = await asyncio.to_thread(self.service.register, self.prepared,
                        pods=self.pods, expected_digest=self.original['digest'] if self.original else None)
                    self.exit(result)
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.busy = False
                self.update_review_button()
