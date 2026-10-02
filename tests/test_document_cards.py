import pytest
from textual.containers import Grid, VerticalScroll
from textual.widgets import Static

from caiman.dashboard.actions import DocumentCatalogApp
from caiman.documents.cards import DocumentCard


@pytest.mark.asyncio
@pytest.mark.parametrize('width,column', [(120, 0), (120, 1), (65, 0)])
async def test_vertical_navigation_visits_collections_and_add_cards(tmp_path, width, column):
    app = DocumentCatalogApp(root=tmp_path, compartments=[])
    app.service.list_documents = lambda **kwargs: [record('public', name) for name in ('A', 'B', 'E', 'F')]
    app.collections.list_collections = lambda **kwargs: [
        {'compartment': 'public', 'digest': 'sha256:' + 'b' * 64,
         'manifest': {'name': name, 'description': 'Related documents', 'documents': [{}]}}
        for name in ('C', 'D')]
    async with app.run_test(size=(width, 45)) as pilot:
        await pilot.pause()
        cards = list(app.query('.card-face'))
        columns = 2 if width >= 100 else 1
        route = cards[column::columns]
        route[0].focus()
        await pilot.pause()
        body = app.query_one('#body', VerticalScroll)
        for key, targets in [('j', route[1:]), ('k', list(reversed(route[:-1])))]:
            for target in targets:
                was_visible = body.content_region.contains_region(target.parent.region)
                scroll = body.scroll_y
                await pilot.press(key)
                await pilot.pause()
                assert app.focused is target
                assert body.content_region.contains_region(target.parent.region)
                if was_visible:
                    assert body.scroll_y == scroll


def record(compartment, part='Chip', version='A'):
    return {'compartment': compartment, 'digest': 'sha256:' + 'a' * 64,
            'ref': f'vendor/{part}/manual/{version}',
            'manifest': {'issuer': 'Vendor', 'part': part, 'version': version, 'doc_type': 'manual'}}


@pytest.mark.asyncio
async def test_document_sections_resize_focus_details_and_refresh(tmp_path):
    app = DocumentCatalogApp(root=tmp_path, compartments=['alpha'])
    public = record('public')
    private = record('alpha', 'Long mixed case document identity with ß', 'release / B')
    calls = []

    def documents(*, compartments):
        calls.append(compartments)
        return [private, public, record('public', 'Other')] if len(calls) == 1 else [public]

    app.service.list_documents = documents
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        assert not app.query('#compartments')
        headings = list(app.query('.compartment-heading'))
        assert [str(heading.content) for heading in headings] == ['Public · 2 Documents', 'alpha · 1 Documents']
        cards = list(app.query(DocumentCard))
        assert cards[2].record == private
        assert 'sha256' not in cards[0].label.plain
        assert 'ß' in cards[2].label.plain
        assert all(grid.styles.grid_size_columns == 2 for grid in app.query(Grid))
        cards[0].focus()
        await pilot.pause()
        before = [card.virtual_region for card in cards]
        assert cards[0].parent.has_class('selected')
        await pilot.press('l')
        assert app.focused is cards[1]
        assert not cards[0].parent.has_class('selected')
        assert cards[1].parent.has_class('selected')
        assert before == [card.virtual_region for card in cards]
        await pilot.resize_terminal(65, 30)
        await pilot.pause()
        assert all(grid.styles.grid_size_columns == 1 for grid in app.query(Grid))
        assert all(card.region.right <= 65 for card in cards)
        await pilot.click('#refresh')
        await pilot.pause()
        assert len(app.query(DocumentCard)) == 1
        assert len(app.query('.compartment-heading')) == 1
        assert calls == [['alpha'], ['alpha']]
        assert '1 accessible' in str(app.query_one('#status', Static).content)


@pytest.mark.asyncio
async def test_document_card_hands_off_to_guided_editor(tmp_path):
    app = DocumentCatalogApp(root=tmp_path, compartments=[])
    selected = record('public')
    app.service.list_documents = lambda **kwargs: [selected]
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        await pilot.press('enter')
    assert app.return_value == {'document': selected}


@pytest.mark.asyncio
async def test_document_catalog_ends_with_an_add_card(tmp_path):
    app = DocumentCatalogApp(root=tmp_path, compartments=[])
    app.service.list_documents = lambda *, compartments: [record('public')]
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        faces = list(app.query('.card-face'))
        assert isinstance(faces[0], DocumentCard)
        assert [face.id for face in faces[-2:]] == ['add-document', 'add-collection']
        assert app.focused is faces[0]
        faces[-2].focus()
        await pilot.press('enter')
    assert app.return_value == 'add'


def test_document_catalog_add_card_hands_off_to_ingest(tmp_path, monkeypatch):
    import caiman.dashboard.actions as actions
    from caiman.dashboard.actions import run_dashboard_action

    class Catalog:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return 'add'

    monkeypatch.setattr(actions, 'DocumentCatalogApp', Catalog)
    assert run_dashboard_action('documents', tmp_path, []) == {'action': 'ingest'}


def test_collection_actions_return_to_the_gallery(tmp_path, monkeypatch):
    import caiman.dashboard.actions as actions
    import caiman.documents.collection_tui as collections

    saved = {'manifest': {'name': 'Collection'}}
    choices = iter(['add-collection', {'collection': saved}, None])
    opened = []

    class Catalog:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return next(choices)

    class Editor:
        def __init__(self, **kwargs):
            opened.append(kwargs['record'])
        def run(self):
            return None

    monkeypatch.setattr(actions, 'DocumentCatalogApp', Catalog)
    monkeypatch.setattr(collections, 'CollectionApp', Editor)
    assert actions.run_dashboard_action('documents', tmp_path, []) is None
    assert opened == [None, saved]


def test_document_edit_returns_to_gallery(tmp_path, monkeypatch):
    import caiman.dashboard.actions as actions
    import caiman.documents.edit as editing
    selection = record('public')
    choices = iter([{'document': selection}, None])
    opened = []

    class Catalog:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return next(choices)

    monkeypatch.setattr(actions, 'DocumentCatalogApp', Catalog)
    monkeypatch.setattr(editing, 'edit_document', lambda root, selected, **kwargs: opened.append((root, selected, kwargs)))
    assert actions.run_dashboard_action('documents', tmp_path, ['alpha']) is None
    assert opened == [(tmp_path, selection, {'compartments': ['alpha']})]
