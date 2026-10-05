"""A guided project form in the board editor's layout.

Identity, customer, and the owning pod sit at the top; boards and documents
are card grids below. Existing feature data is retained. The form
carries every key it does not render — lineage, resolved digests, pods
on existing pins — so an untouched draft collects to exactly what it was given.

A project pins any number of boards, including one board at several versions.
A v1 project, which pins a single board and may declare precedence, opens restated
in the current shape; the stored snapshot is untouched and the review shows the
rewrite.

A draft whose shape the form cannot represent is shown read-only with the raw
editor as its only path, rather than being coerced into the guided shape.
Nothing here writes: `collect` produces a draft for the existing review.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path

from rich.text import Text
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.suggester import SuggestFromList, Suggester
from textual.widgets import Button, Collapsible, Input, Label, Static

from caiman.boards.picker import BoardPicker, board_pin
from caiman.configurations.models import restate_project_draft, project_is_legacy
from caiman.configurations.service import ConfigurationService
from caiman.documents.cards import document_name
from caiman.documents.picker import DocumentPicker, document_pin
from caiman.storage.store import Store
from caiman.ui.editor import EDITOR_CSS, CardRow, EditorFormApp, Row, add_card
from caiman.ui.theme import apply_theme


SELECTOR_TEXT = ('ref', 'digest', 'pod', 'document', 'blob', 'collection', 'note', 'notes')


def _strings(value) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _selector_problem(selector, path) -> str | None:
    if not isinstance(selector, dict):
        return f'{path} is not an object'
    for key in SELECTOR_TEXT:
        if key in selector and not isinstance(selector[key], str):
            return f'{path}.{key} is not text'
    if 'requirements' in selector and not _strings(selector['requirements']):
        return f'{path}.requirements is not a list of IDs'
    return None


def guided_shape_problem(draft: dict) -> str | None:
    """Why the guided form cannot represent this draft, or None if it can.

    Only shape is checked; values are left for validation at review.
    """
    for key in ('project', 'version', 'customer', 'spec_set'):
        if key in draft and not isinstance(draft[key], str):
            return f'{key} is not text'
    if 'pod' in draft and not isinstance(draft['pod'], str):
        return 'pod is not a name'
    legacy = project_is_legacy(draft)
    boards = [draft.get('board', {})] if legacy else draft.get('boards', [])
    if not isinstance(boards, list):
        return 'boards is not a list'
    for board in boards:
        if not isinstance(board, dict) or any(key in board and not isinstance(board[key], str)
                                              for key in ('name', 'version', 'digest')):
            return 'a board is not an object of name, version, and digest'
    # A v1 precedence list is checked too: restating moves its pins to documents.
    for field in ('documents', 'precedence'):
        selectors = draft.get(field, [])
        if not isinstance(selectors, list):
            return f'{field} is not a list'
        for index, selector in enumerate(selectors):
            if problem := _selector_problem(selector, f'{field}.{index}'):
                return problem
    features = draft.get('features', [])
    if not isinstance(features, list):
        return 'features is not a list'
    for index, feature in enumerate(features):
        path = f'features.{index}'
        if not isinstance(feature, dict):
            return f'{path} is not an object'
        if any(key in feature and not isinstance(feature[key], str) for key in ('name', 'scope')):
            return f'{path} name or scope is not text'
        realized = feature.get('realized_on', [])
        if legacy and not _strings(realized):
            return f'{path}.realized_on is not a list of part roles'
        if not legacy and not (isinstance(realized, list) and all(
                isinstance(part, dict) and all(isinstance(part.get(key, ''), str) for key in ('board', 'version', 'role'))
                for part in realized)):
            return f'{path}.realized_on is not a list of board, version, and role'
        for key in ('governed_by', 'related'):
            if key in feature and not isinstance(feature[key], list):
                return f'{path}.{key} is not a list'
        for number, selector in enumerate(feature.get('governed_by', [])):
            if problem := _selector_problem(selector, f'{path}.governed_by.{number}'):
                return problem
        for number, related in enumerate(feature.get('related', [])):
            if not isinstance(related, dict) or any(key in related and not isinstance(related[key], str)
                                                    for key in ('feature', 'relation')):
                return f'{path}.related.{number} is not a feature and relation'
    return None


class CatalogSuggester(Suggester):
    """Completes registered names; typing anything else stays allowed."""

    def __init__(self):
        super().__init__(use_cache=False, case_sensitive=True)
        self.refs: list[str] = []

    async def get_suggestion(self, value: str) -> str | None:
        return next((ref for ref in self.refs if ref.startswith(value) and ref != value), None) if value else None


class Suggestions:
    """Completion sources shared by every card; none of them constrain a value."""

    def __init__(self, pods):
        names = [name for name in pods if isinstance(name, str)]
        self.pods = SuggestFromList([*names, 'public'])
        self.refs = CatalogSuggester()
        self.boards = CatalogSuggester()
        self.board_versions = CatalogSuggester()


def _collect_selector(row: Row, keys) -> dict:
    selector = row.carry(*keys)
    for key in keys:
        if row.value(key):
            selector[key] = row.value(key)
    return selector


def _selector_fields(row: Row, suggestions: Suggestions):
    yield from row.text_field('ref', 'Document Ref', suggester=suggestions.refs,
                              placeholder='issuer/part-or-program/doc-type/version')
    yield from row.text_field('digest', 'Manifest Digest (optional)', placeholder='sha256:…')
    yield from row.text_field('document', 'Document ID (optional)')
    yield from row.text_field('blob', 'Pinned Blob (with Document ID)', placeholder='sha256:…')
    yield from row.text_field('pod', 'Pod (optional)', suggester=suggestions.pods,
                              placeholder='Pod name or ID')


def _selector_title(data, new_label):
    return data.get('ref') or data.get('document') or ('Pinned by digest' if data.get('digest') else new_label)


class PinnedBoardCard(CardRow):
    """One board version the program runs on; the digest is resolved at review."""

    kind = 'pinned-board'
    first_field = 'name'

    def __init__(self, data, *, suggestions: Suggestions, expanded=False):
        super().__init__(data, expanded=expanded)
        self.suggestions = suggestions

    def editor_fields(self):
        yield from self.text_field('pod', 'Pod (optional)')
        yield from self.text_field('name', 'Board Name', suggester=self.suggestions.boards)
        yield from self.text_field('version', 'Board Version', suggester=self.suggestions.board_versions,
                                   placeholder='exact label')
        yield from self.text_field('digest', 'Board Manifest Digest (optional)',
                                   placeholder='sha256:… (blank pins the board version at review)')
        yield from self.actions('Remove board')

    def summary_data(self):
        return {key: self.value(key) for key in ('name', 'version', 'digest')}

    def summary(self, data):
        label = Text()
        self.heading(label, data.get('name') or 'New board')
        label.append('\n\n' + (f"Version {data['version']}" if data.get('version') else 'Version not set'), style='#7fdc4f')
        digest = data.get('digest')
        label.append('\n' + (digest[:19] + '…' if digest else 'Digest pinned at review'), style='#aab69c')
        label.append('\n\n' + self.summary_hint(), style='#aab69c')
        return label

    def collect(self) -> dict:
        board = self.carry('name', 'version', 'digest')
        board.update(name=self.value('name'), version=self.value('version'))
        if self.value('digest'):
            board['digest'] = self.value('digest')
        if self.value('pod'):
            board['pod'] = self.value('pod')
        else:
            board.pop('pod', None)
        return board


class ProjectDocumentCard(CardRow):
    kind = 'document'
    first_field = 'ref'
    keys = ('ref', 'digest', 'pod', 'document', 'blob')
    record = None

    def show_record(self, record):
        self.record = record
        self.record_selector = self.summary_data()
        self.refresh_summary()
        if 'collection' in self.data:
            members = record.get('members', [])
            self.query_one('.collection-members', Static).update('\n'.join(
                f"{document_name(r['manifest'])} · {r['manifest']['version']}" for r in members))

    def __init__(self, data, *, suggestions: Suggestions, expanded=False):
        super().__init__(data, expanded=expanded)
        self.suggestions = suggestions
        if 'collection' in data:
            self.add_class('live-collection')
            self.keys = ('pod', 'collection', 'digest')

    def editor_fields(self):
        if 'collection' in self.data:
            yield Static('Loading collection…', classes='collection-members', markup=False)
            yield from self.actions('Remove collection')
            return
        yield from _selector_fields(self, self.suggestions)
        yield from self.actions('Remove document')

    def summary_data(self):
        if 'collection' in self.data:
            return deepcopy(self.data)
        return {key: self.value(key) for key in self.keys}

    def summary(self, data):
        label = Text()
        record = self.record if self.record and data == self.record_selector else None
        if 'collection' in data:
            self.heading(label, record['manifest']['name'] if record else data['collection'])
            label.append('\n\nCollection · follows current membership', style='#7fdc4f')
            if record:
                count = len(record['manifest']['documents'])
                label.append(f"\n{count} {'document' if count == 1 else 'documents'}", style='#aab69c')
            hint = 'Collapse' if self.has_class('expanded') else 'Enter to view'
            label.append('\n\n' + hint, style='#aab69c')
            return label
        name = document_name(record['manifest']) if record else _selector_title(data, 'New document')
        self.heading(label, name)
        details = (f"{record['manifest']['version']} · {record.get('pod_name', record['pod'])}" if record else
                   data.get('pod') or 'Pod resolved at review')
        label.append('\n\n' + details, style='#7fdc4f')
        label.append('\n\n' + self.summary_hint(), style='#aab69c')
        return label

    def collect(self) -> dict:
        if 'collection' in self.data:
            return deepcopy(self.data)
        return _collect_selector(self, self.keys)


class ProjectFormApp(EditorFormApp):
    """Edit a project field by field. Exits with ('review'|'raw'|'delete', draft), or None."""

    TITLE = 'Caiman · Edit project'
    CSS = EDITOR_CSS + '''
    #project-pod { margin-bottom: 1; }
    .live-collection .row-actions Button { border: solid #33422e; }
    .live-collection .row-actions Button:focus { border: double #7fdc4f; }
    '''

    def __init__(self, *, original: dict, draft: dict | None = None, message: str = '', root: Path | None = None, creating: bool = False):
        super().__init__()
        apply_theme(self)
        self.creating = creating
        if creating:
            self.title = 'Caiman · Create project'
        self.original = deepcopy(original)
        self.draft = deepcopy(original if draft is None else draft)
        self.problem = guided_shape_problem(self.draft)
        self.read_only = self.problem is not None
        self.restated = not self.read_only and project_is_legacy(self.draft)
        if self.restated:
            self.draft = restate_project_draft(self.draft)
        self.message = message
        self.root = root
        self.service = ConfigurationService(Store(root)) if root is not None else None
        self.pod = self.draft.get('pod') or 'public'
        pods = [r['id'] for r in Store(root).pods.list()] if root else ['public']
        self.suggestions = Suggestions(pods)

    def field(self, key: str, label: str, value, *, placeholder='', suggester=None):
        yield Label(label, classes='field-label')
        yield Input(value=value, placeholder=placeholder, suggester=suggester, id=f'project-{key}')

    def section(self, title, grid_id, cards, add_label, add_id):
        with Collapsible(title=f'{title} · {len(cards)} declared', collapsed=False):
            with Grid(id=grid_id, classes='card-grid'):
                yield from cards
                yield add_card(add_label, id=add_id)

    def compose(self):
        yield Static('caiman  /  create project' if self.creating else 'caiman  /  edit project', id='brand')
        with VerticalScroll(id='body'):
            if self.read_only:
                yield Static(f'The guided form cannot show this project without changing it: {self.problem}. '
                             'Use raw JSON so nothing declared is dropped.', classes='hint', markup=False)
                yield Static(json.dumps(self.draft, indent=2, ensure_ascii=False), markup=False)
            else:
                draft = self.draft
                if self.restated:
                    yield Static('This project was registered as caiman.project.v1. The form shows it in the '
                                 'current shape: its board is listed under Boards, and any document that was only '
                                 'in precedence is listed under Documents; precedence order and notes are not kept. '
                                 'Registering writes caiman.project.v3, and the review shows every changed field.',
                                 classes='hint', markup=False)
                yield from self.field('project', 'Program name', draft.get('project', ''))
                yield from self.field('version', 'Version', draft.get('version', ''))
                yield from self.field('customer', 'Customer', draft.get('customer', ''))
                yield Label('Pod', classes='field-label')
                yield Static(self.service.store.pod_name(self.pod) if self.service else self.pod,
                             id='project-pod', markup=False)
                s = self.suggestions
                yield from self.section('Boards', 'boards',
                                        [PinnedBoardCard(board, suggestions=s) for board in draft.get('boards', [])],
                                        'Add board', 'add-board')
                yield from self.section('Documents', 'documents',
                                        [ProjectDocumentCard(pin, suggestions=s) for pin in draft.get('documents', [])],
                                        'Choose documents', 'add-project-document')
                if draft.get('features'):
                    yield Static('Existing feature declarations are retained. Use raw JSON to edit them.',
                                 classes='hint', markup=False)
        yield Static(self.message, id='form-error', markup=False)
        with Horizontal(id='navigation'):
            if not self.read_only:
                yield Button('Review project' if self.creating else 'Review changes',
                             id='review-changes', variant='primary', disabled=not self.creating)
            yield Button('Edit raw JSON in Vim', id='raw', variant='primary' if self.read_only else 'default')
            if not self.creating:
                yield Button('Delete project', id='delete', variant='error')
            yield Button('Back to projects', id='cancel')
        yield self.navigation_hint()

    def update_review_button(self):
        if self.creating and not self.read_only:
            self.query_one('#review-changes', Button).disabled = False
        else:
            super().update_review_button()

    def on_mount(self):
        # EditorFormApp's own on_mount also runs and sizes the grids.
        if self.root is not None and not self.read_only:
            self.run_worker(self.load_catalog(), exclusive=True)

    async def load_catalog(self):
        """Offer registered refs as completions; a failure only loses completion."""
        pods = None
        try:
            entries = await asyncio.to_thread(ConfigurationService(Store(self.root)).list_documents,
                                              pods=pods)
        except (OSError, ValueError):
            return
        self.suggestions.refs.refs = sorted({entry['ref'] for entry in entries if entry.get('ref')})
        for row in self.query(ProjectDocumentCard):
            try:
                record = await asyncio.to_thread(self.service.attachment_record, row.collect(), owner=self.pod)
                row.show_record(record)
            except (OSError, ValueError) as error:
                if 'collection' in row.data:
                    row.query_one('.collection-members', Static).update(f'Unavailable collection: {error}')
                    self.query_one('#form-error', Static).update(str(error))
        try:
            boards = await asyncio.to_thread(ConfigurationService(Store(self.root)).list_configs, 'board')
        except (OSError, ValueError):
            return
        # Completion only; version labels are listed, never ordered (I-7).
        self.suggestions.boards.refs = sorted({record['name'] for record in boards})
        self.suggestions.board_versions.refs = sorted({record['version'] for record in boards})

    def value(self, key):
        return self.query_one(f'#project-{key}', Input).value.strip()

    def collect(self) -> dict:
        """Build a draft from the form, keeping every field it does not render."""
        data = deepcopy(self.draft)
        for key in ('project', 'version', 'customer'):
            data[key] = self.value(key)
        data['boards'] = [card.collect() for card in self.query_one('#boards').query_children(PinnedBoardCard)]
        data['documents'] = [pin for card in self.query_one('#documents').query_children(ProjectDocumentCard) if (pin := card.collect())]
        return data

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button
        event.stop()
        if button.id == 'cancel':
            self.exit(None)
        elif button.id == 'delete':
            self.exit(('delete', deepcopy(self.draft) if self.read_only else self.collect()))
        elif button.id in {'review-changes', 'raw'}:
            action = 'review' if button.id == 'review-changes' else 'raw'
            self.exit((action, deepcopy(self.draft) if self.read_only else self.collect()))
        elif button.has_class('card-summary') or button.has_class('collapse-card'):
            card = next(node for node in button.ancestors if isinstance(node, CardRow))
            if 'collection' in card.data:
                card.set_expanded(not card.has_class('expanded'))
                target = card.query_one('.collapse-card' if card.has_class('expanded') else '.card-summary', Button)
                self.call_after_refresh(target.focus)
            else:
                self.toggle_card(button)
        elif button.id == 'add-board':
            async def attach_boards(records):
                for record in records or []:
                    card = PinnedBoardCard(board_pin(record), suggestions=self.suggestions)
                    await button.parent.parent.mount(card, before=button.parent)
                self.call_after_refresh(button.focus)

            self.push_screen(BoardPicker(service=self.service, owner=self.pod,
                attached=[card.collect() for card in self.query(PinnedBoardCard)]), attach_boards)
        elif button.id == 'add-project-document':
            async def attach_documents(records):
                for record in records or []:
                    card = ProjectDocumentCard(document_pin(record), suggestions=self.suggestions)
                    await self.query_one('#documents').mount(card, before=self.query_one('#add-project-document').parent)
                    card.show_record(record)
                self.call_after_refresh(button.focus)

            self.push_screen(DocumentPicker(service=self.service, owner=self.pod, preserve_collections=True,
                attached=[card.collect() for card in self.query(ProjectDocumentCard)]), attach_documents)
        elif button.has_class('remove-row'):
            await self.remove_row(button)

    def action_cancel(self) -> None:
        self.exit(None)
