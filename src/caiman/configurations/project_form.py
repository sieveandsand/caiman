"""A guided project form in the board editor's layout.

Identity, customer, compartments, and the specification set sit at the top;
boards, documents, and features are card grids below. The form
carries every key it does not render — lineage, resolved digests, compartments
on existing pins — so an untouched draft collects to exactly what it was given.

A project pins any number of boards, including one board at several versions,
so each part a feature is realized on names its board and version. A v1
project, which pins a single board and may declare precedence, opens restated
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
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.suggester import SuggestFromList, Suggester
from textual.widgets import Button, Collapsible, Input, Label, Static

from caiman.configurations.models import restate_project_draft, project_is_legacy
from caiman.configurations.service import ConfigurationService
from caiman.storage.store import Store
from caiman.ui.editor import EDITOR_CSS, CardRow, EditorFormApp, Row, add_card, comma_list
from caiman.ui.theme import apply_theme


SCOPES = ('required', 'not-used')
SELECTOR_TEXT = ('ref', 'digest', 'compartment', 'note', 'notes')


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
    if 'compartments' in draft and not _strings(draft['compartments']):
        return 'compartments is not a list of names'
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

    def __init__(self, compartments):
        names = [name for name in compartments if isinstance(name, str)]
        self.compartments = SuggestFromList([*names, 'public'])
        self.scopes = SuggestFromList(SCOPES)
        self.refs = CatalogSuggester()
        self.boards = CatalogSuggester()
        self.board_versions = CatalogSuggester()
        self.roles = CatalogSuggester()


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
    yield from row.text_field('compartment', 'Compartment (optional)', suggester=suggestions.compartments,
                              placeholder='public or a project compartment')


def _selector_title(data, new_label):
    return data.get('ref') or ('Pinned by digest' if data.get('digest') else new_label)


class PinnedBoardCard(CardRow):
    """One board version the program runs on; the digest is resolved at review."""

    kind = 'pinned-board'
    first_field = 'name'

    def __init__(self, data, *, suggestions: Suggestions, expanded=False):
        super().__init__(data, expanded=expanded)
        self.suggestions = suggestions

    def editor_fields(self):
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
        return board


class ProjectDocumentCard(CardRow):
    kind = 'document'
    first_field = 'ref'
    keys = ('ref', 'digest', 'compartment')

    def __init__(self, data, *, suggestions: Suggestions, expanded=False):
        super().__init__(data, expanded=expanded)
        self.suggestions = suggestions

    def editor_fields(self):
        yield from _selector_fields(self, self.suggestions)
        yield from self.actions('Remove document')

    def summary_data(self):
        return {key: self.value(key) for key in self.keys}

    def summary(self, data):
        label = Text()
        self.heading(label, _selector_title(data, 'New document'))
        label.append('\n\n' + (data.get('compartment') or 'Compartment resolved at review'), style='#7fdc4f')
        label.append('\n\n' + self.summary_hint(), style='#aab69c')
        return label

    def collect(self) -> dict:
        return _collect_selector(self, self.keys)


class GoverningRow(Row):
    """A governing document inside a feature, with the requirement IDs it names."""

    keys = ('ref', 'digest', 'compartment')

    def __init__(self, data, *, suggestions: Suggestions):
        super().__init__(data)
        self.suggestions = suggestions

    def compose(self):
        yield from _selector_fields(self, self.suggestions)
        yield Label('Requirement IDs (optional)', classes='field-label')
        yield Input(value=', '.join(self.data.get('requirements') or []), placeholder='REQ-101, REQ-102',
                    classes='field field-requirements')
        yield from self.actions('Remove governing document')

    def collect(self) -> dict:
        selector = _collect_selector(self, self.keys)
        selector.pop('requirements', None)
        if requirements := comma_list(self.value('requirements')):
            selector['requirements'] = requirements
        return selector


class RealizedRow(Row):
    """A part the feature is realized on: a role on one pinned board version."""

    def __init__(self, data, *, suggestions: Suggestions):
        super().__init__(data)
        self.suggestions = suggestions

    def compose(self):
        yield from self.text_field('board', 'Board', suggester=self.suggestions.boards)
        yield from self.text_field('version', 'Board Version', suggester=self.suggestions.board_versions)
        yield from self.text_field('role', 'Part Role', suggester=self.suggestions.roles,
                                   placeholder='application-mcu')
        yield from self.actions('Remove part')

    def collect(self) -> dict:
        part = self.carry('board', 'version', 'role')
        part.update(board=self.value('board'), version=self.value('version'), role=self.value('role'))
        return part


def _part_text(part: dict) -> str:
    return f"{part.get('role') or '?'} on {part.get('board') or '?'} @ {part.get('version') or '?'}"


class RelatedRow(Row):
    def compose(self):
        yield from self.text_field('feature', 'Related Feature')
        yield from self.text_field('relation', 'Relation', placeholder='declared in words, e.g. shares the bootloader')
        yield from self.actions('Remove related feature')

    def collect(self) -> dict:
        related = self.carry('feature', 'relation')
        related.update(feature=self.value('feature'), relation=self.value('relation'))
        return related


class FeatureCard(CardRow):
    kind = 'feature'
    first_field = 'name'

    def __init__(self, data, *, suggestions: Suggestions, expanded=False):
        super().__init__(data, expanded=expanded)
        self.suggestions = suggestions

    def editor_fields(self):
        yield from self.text_field('name', 'Feature Name')
        yield from self.text_field('scope', 'Scope', suggester=self.suggestions.scopes,
                                   placeholder='required or not-used')
        yield Label('Realized On', classes='field-label')
        yield Vertical(*(RealizedRow(part, suggestions=self.suggestions)
                         for part in self.data.get('realized_on') or []), classes='nested-rows realized')
        yield Label('Governed By', classes='field-label')
        yield Vertical(*(GoverningRow(selector, suggestions=self.suggestions)
                         for selector in self.data.get('governed_by') or []), classes='nested-rows governing')
        yield Label('Related Features', classes='field-label')
        yield Vertical(*(RelatedRow(related) for related in self.data.get('related') or []),
                       classes='nested-rows related')
        with Horizontal(classes='section-actions'):
            yield Button('Add part', classes='add-realized')
            yield Button('Add governing document', classes='add-governing')
            yield Button('Add related feature', classes='add-related')
            yield Button('Remove feature', classes='remove-row')

    def summary_data(self):
        return {'name': self.value('name'), 'scope': self.value('scope'),
                'realized_on': [row.collect() for row in self.query(RealizedRow)],
                'governed_by': list(self.query(GoverningRow))}

    def summary(self, data):
        label = Text()
        self.heading(label, data.get('name') or 'New feature')
        label.append('\n\n' + (data.get('scope') or 'Scope not set'), style='#7fdc4f')
        parts = data.get('realized_on') or []
        label.append('\n' + ('\n'.join(_part_text(part) for part in parts) if parts else 'No parts'), style='#aab69c')
        label.append(f"\n\n{len(data.get('governed_by') or [])} governing documents", style='bold #aab69c')
        label.append('\n\n' + self.summary_hint(), style='#aab69c')
        return label

    def collect(self) -> dict:
        feature = self.carry('name', 'scope', 'realized_on', 'governed_by', 'related')
        feature.update(name=self.value('name'), scope=self.value('scope'))
        # An absent list stays absent and a declared one stays declared, even
        # when empty; either way the snapshot's bytes follow what was stored.
        values = {'realized_on': [row.collect() for row in self.query_one('.realized').query_children(RealizedRow)],
                  'governed_by': [row.collect() for row in self.query_one('.governing').query_children(GoverningRow)],
                  'related': [row.collect() for row in self.query_one('.related').query_children(RelatedRow)]}
        for key, value in values.items():
            if value or key in self.data:
                feature[key] = value
        return feature


class ProjectFormApp(EditorFormApp):
    """Edit a project field by field. Exits with ('review'|'raw'|'delete', draft), or None."""

    TITLE = 'Caiman · Edit project'

    def __init__(self, *, original: dict, draft: dict | None = None, message: str = '', root: Path | None = None):
        super().__init__()
        apply_theme(self)
        self.original = deepcopy(original)
        self.draft = deepcopy(original if draft is None else draft)
        self.problem = guided_shape_problem(self.draft)
        self.read_only = self.problem is not None
        self.restated = not self.read_only and project_is_legacy(self.draft)
        if self.restated:
            self.draft = restate_project_draft(self.draft)
        self.message = message
        self.root = root
        compartments = self.draft.get('compartments') if isinstance(self.draft.get('compartments'), list) else []
        self.suggestions = Suggestions(compartments)

    def field(self, key: str, label: str, value, *, placeholder='', suggester=None):
        yield Label(label, classes='field-label')
        yield Input(value=value, placeholder=placeholder, suggester=suggester, id=f'project-{key}')

    def section(self, title, grid_id, cards, add_label, add_id):
        with Collapsible(title=f'{title} · {len(cards)} declared', collapsed=False):
            with Grid(id=grid_id, classes='card-grid'):
                yield from cards
                yield add_card(add_label, id=add_id)

    def compose(self):
        yield Static('caiman  /  edit project', id='brand')
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
                                 'Registering writes caiman.project.v2, and the review shows every changed field.',
                                 classes='hint', markup=False)
                yield from self.field('project', 'Program Codename', draft.get('project', ''))
                yield from self.field('version', 'Version', draft.get('version', ''))
                yield from self.field('customer', 'Customer', draft.get('customer', ''))
                yield from self.field('compartments', 'Compartments', ', '.join(draft.get('compartments', [])),
                                      placeholder='oem-alpha, oem-beta')
                yield from self.field('spec_set', 'Specification Set', draft.get('spec_set', ''))
                s = self.suggestions
                yield from self.section('Boards', 'boards',
                                        [PinnedBoardCard(board, suggestions=s) for board in draft.get('boards', [])],
                                        'Add board', 'add-board')
                yield from self.section('Documents', 'documents',
                                        [ProjectDocumentCard(pin, suggestions=s) for pin in draft.get('documents', [])],
                                        'Add document', 'add-project-document')
                yield from self.section('Features', 'features',
                                        [FeatureCard(feature, suggestions=s) for feature in draft.get('features', [])],
                                        'Add feature', 'add-feature')
        yield Static(self.message, id='form-error', markup=False)
        with Horizontal(id='navigation'):
            if not self.read_only:
                yield Button('Review changes', id='review-changes', variant='primary')
            yield Button('Edit raw JSON in Vim', id='raw', variant='primary' if self.read_only else 'default')
            yield Button('Delete project', id='delete', variant='error')
            yield Button('Back to projects', id='cancel')
        yield self.navigation_hint()

    def on_mount(self):
        # EditorFormApp's own on_mount also runs and sizes the grids.
        if self.root is not None and not self.read_only:
            self.run_worker(self.load_catalog(), exclusive=True)

    async def load_catalog(self):
        """Offer registered refs as completions; a failure only loses completion."""
        compartments = comma_list(self.query_one('#project-compartments', Input).value)
        try:
            entries = await asyncio.to_thread(ConfigurationService(Store(self.root)).list_documents,
                                              compartments=compartments)
        except (OSError, ValueError):
            return
        self.suggestions.refs.refs = sorted({entry['ref'] for entry in entries if entry.get('ref')})
        try:
            boards = await asyncio.to_thread(ConfigurationService(Store(self.root)).list_configs, 'board')
        except (OSError, ValueError):
            return
        # Completion only; version labels are listed, never ordered (I-7).
        self.suggestions.boards.refs = sorted({record['name'] for record in boards})
        self.suggestions.board_versions.refs = sorted({record['version'] for record in boards})
        self.suggestions.roles.refs = sorted({part['role'] for record in boards
                                              for part in record['manifest'].get('parts', [])})

    def value(self, key):
        return self.query_one(f'#project-{key}', Input).value.strip()

    def collect(self) -> dict:
        """Build a draft from the form, keeping every field it does not render."""
        data = deepcopy(self.draft)
        for key in ('project', 'version', 'customer', 'spec_set'):
            data[key] = self.value(key)
        data['compartments'] = comma_list(self.value('compartments'))
        data['boards'] = [card.collect() for card in self.query_one('#boards').query_children(PinnedBoardCard)]
        data['documents'] = [card.collect() for card in self.query_one('#documents').query_children(ProjectDocumentCard)]
        data['features'] = [card.collect() for card in self.query_one('#features').query_children(FeatureCard)]
        return data

    def single_board(self) -> dict:
        """Start a new part on the board when exactly one is pinned; it stays editable."""
        boards = [card.collect() for card in self.query_one('#boards').query_children(PinnedBoardCard)]
        if len(boards) != 1:
            return {}
        return {'board': boards[0]['name'], 'version': boards[0]['version']}

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
            self.toggle_card(button)
        elif button.id == 'add-board':
            await self.add_card(button, PinnedBoardCard({}, suggestions=self.suggestions, expanded=True))
        elif button.id == 'add-project-document':
            await self.add_card(button, ProjectDocumentCard({}, suggestions=self.suggestions, expanded=True))
        elif button.id == 'add-feature':
            feature = FeatureCard({'name': '', 'scope': ''}, suggestions=self.suggestions, expanded=True)
            await self.add_card(button, feature)
        elif button.has_class('add-governing'):
            feature = next(node for node in button.ancestors if isinstance(node, FeatureCard))
            await self.add_row_within(feature.query_one('.governing'), GoverningRow({}, suggestions=self.suggestions))
        elif button.has_class('add-realized'):
            feature = next(node for node in button.ancestors if isinstance(node, FeatureCard))
            await self.add_row_within(feature.query_one('.realized'), RealizedRow(self.single_board(),
                                                                                  suggestions=self.suggestions))
        elif button.has_class('add-related'):
            feature = next(node for node in button.ancestors if isinstance(node, FeatureCard))
            await self.add_row_within(feature.query_one('.related'), RelatedRow({}))
        elif button.has_class('remove-row'):
            await self.remove_row(button)

    def action_cancel(self) -> None:
        self.exit(None)
