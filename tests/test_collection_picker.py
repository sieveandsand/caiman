"""One picker supplies live project collections and flat attachments elsewhere."""
import pytest
from rich.console import COLOR_SYSTEMS
from textual.widgets import Button, Input, SelectionList, Static, TextArea

from caiman.configurations.files import template
from caiman.configurations.project_form import ProjectDocumentCard, ProjectFormApp
from caiman.configurations.tui import ConfigApp
from caiman.documents.picker import DocumentPicker
from caiman.documents.collections import CollectionService
from caiman.documents.picker import document_pin
from test_document_picker import library, project, snapshot
from test_collections import document


def collections(library):
    service = CollectionService(library.store)
    pins = [document_pin(r) for r in sorted(library.list_documents(), key=lambda r: r['manifest']['name'])]
    first = service.register(service.prepare(dict(name='Security', documents=pins)))
    service.register(service.prepare(dict(name='Boot', documents=pins[:1])))
    return service, first, pins


@pytest.mark.parametrize('mode', ['truecolor', '256', 'standard'])
@pytest.mark.parametrize('size', [(110, 50), (65, 30)])
async def test_collection_selection_expands_once_and_preserves_draft(library, mode, size, monkeypatch, tmp_path):
    monkeypatch.delenv('NO_COLOR', raising=False)
    service, first, pins = collections(library)
    original = project(library)
    original['documents'] = pins[:1]
    original['features'] = [dict(name='boot', scope='required', governed_by=[pins[0] | {'requirements': ['REQ-7']}])]
    before = snapshot(library)
    app = ProjectFormApp(original=original, root=library.store.root)
    app.console._color_system = COLOR_SYSTEMS[mode]
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert not app.query('#choose-project-collection')
        review = app.query_one('#review-changes', Button)
        assert review.disabled
        add = app.query_one('#add-project-document', Button)
        add.press()
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, DocumentPicker)
        picker.query_one(SelectionList).select_all()
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert app.collect() == original
        assert review.disabled
        add.press()
        await pilot.pause()
        picker = app.screen
        listing = picker.query_one(SelectionList)
        listing.select_all()
        await pilot.pause()
        search = picker.query_one('#picker-search', Input)
        search.value = 'Security'
        await pilot.pause()
        assert '2 hidden' in str(picker.query_one('#picker-count', Static).content)
        search.value = ''
        await pilot.pause()
        attach = picker.query_one('#picker-attach', Button)
        attach.focus()
        await pilot.pause()
        assert listing.selected == [0, 1, 2]
        assert attach.styles.border_top[0] == 'double'
        svg = app.export_screenshot()
        assert svg.count('Selected') >= 3
        assert 'Collection' in svg and 'Document' in svg
        assert 'Beta' in svg
        assert 'Security' in svg and 'Boot' in svg
        (tmp_path / f'collections-{mode}-{size[0]}.svg').write_text(svg)
        attach.press()
        await pilot.pause()
        draft = app.collect()
        assert len(draft['documents']) == 4
        assert sum('collection' in pin for pin in draft['documents']) == 2
        assert {document_pin(r)['document'] for r in library.project_documents(draft, owner='public')} == {p['document'] for p in pins}
        assert draft['features'] == original['features']
        assert not review.disabled
        assert app.focused is add
        # Attached collections are excluded, so they cannot be added twice.
        add.press()
        await pilot.pause()
        assert not app.screen.records
        await pilot.press('escape')
        await pilot.pause()
        assert app.collect() == draft
        library.prepare('project', draft)
        cards = list(app.query(ProjectDocumentCard))
        for card in cards[1:]:
            card.query_one('.remove-row', Button).press()
            await pilot.pause()
        assert app.collect() == original
        assert review.disabled
    assert snapshot(library) == before
    # Saving a changed collection does not rewrite the project’s stored references.
    prepared = library.prepare('project', draft)
    library.register(prepared)
    service.register(service.prepare(first['manifest'] | {'documents': pins[:1]}), expected_digest=first['digest'])
    assert library.load_digest('project', prepared.digest)['documents'] == draft['documents']


async def test_authoring_collection_attach_preserves_hidden_features_and_invalid_json(library):
    _, _, pins = collections(library)
    original = project(library)
    original['features'] = [dict(name='boot', scope='required')]
    app = ConfigApp('project', library.store.root, original)
    async with app.run_test() as pilot:
        assert not app.query('#features, #choose-features, #choose-collections')
        area = app.query_one('#documents', TextArea)
        area.load_text('[unfinished')
        add = app.query_one('#choose-documents', Button)
        add.press()
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert area.text == '[unfinished'
        area.load_text('[]')
        add.press()
        await pilot.pause()
        app.screen.query_one(SelectionList).select_all()
        await pilot.pause()
        app.screen.query_one('#picker-attach', Button).press()
        await pilot.pause()
        draft = app.collect_draft()
        assert len(draft['documents']) == 4
        assert sum('collection' in pin for pin in draft['documents']) == 2
        assert {document_pin(r)['document'] for r in library.project_documents(draft, owner='public')} == {p['document'] for p in pins}
        assert draft['features'] == original['features']
        library.prepare('project', draft)


async def test_unavailable_member_never_partially_attaches(library, monkeypatch):
    service, first, pins = collections(library)
    original = project(library)
    before = snapshot(library)
    app = ProjectFormApp(original=original, root=library.store.root)
    async with app.run_test() as pilot:
        app.query_one('#add-project-document', Button).press()
        await pilot.pause()
        picker = app.screen
        real_read = library.store._read_object
        def missing(pod, kind, digest):
            if kind == 'blobs' and digest == pins[0]['blob']:
                raise ValueError('Missing collection member body')
            return real_read(pod, kind, digest)
        monkeypatch.setattr(app.service.store, '_read_object', missing)
        picker.query_one(SelectionList).select_all()
        await pilot.pause()
        picker.query_one('#picker-attach', Button).press()
        await pilot.pause()
        assert app.screen is picker
        assert 'Missing collection member' in str(picker.query_one('#picker-status', Static).content)
        assert app.collect() == original
        assert not picker.query_one('#picker-attach', Button).disabled
        await pilot.press('escape')
        await pilot.pause()
        assert app.collect() == original
    assert snapshot(library) == before


def test_collection_picker_only_offers_owning_pod_and_public(library, tmp_path):
    service, public, _ = collections(library)
    for pod in ('alpha', 'beta'):
        pin = document(tmp_path, library.store, pod=pod, name=pod)
        service.register(service.prepare(dict(name=pod, documents=[pin]), pod=pod))
    picker = DocumentPicker(service=library, owner='alpha')
    assert {r['pod'] for r in picker.load_records()} == {'alpha', 'public'}
    picker.records = [r for r in service.list_collections() if r['pod'] == 'beta']
    picker.chosen = {0}
    with pytest.raises(ValueError, match='cross-pod reference'):
        picker.selected_documents()


def test_new_project_without_features_roundtrips_storage_and_usages(library):
    from caiman.documents.usages import document_pins
    assert 'features' not in template('project')
    original = project(library)
    original.pop('features')
    prepared = library.prepare('project', original)
    library.register(prepared)
    loaded = library.load_digest('project', prepared.digest)
    assert 'features' not in loaded
    assert document_pins('project', loaded) == []
    assert library.prepare('project', loaded).digest == prepared.digest


def test_collection_edited_after_selection_uses_opened_snapshot(library):
    service, original, pins = collections(library)
    picker = DocumentPicker(service=library, owner='public')
    picker.records = [original]
    picker.chosen = {0}
    service.register(service.prepare(original['manifest'] | {'documents': pins[:1]}),
                     expected_digest=original['digest'])
    assert {r['manifest']['document_id'] for r in picker.selected_documents()} == {
        pin['document'] for pin in pins}


@pytest.mark.parametrize('target', ['board', 'part'])
async def test_shared_picker_expands_collections_for_every_attachment_target(library, target):
    from caiman.boards.form import BoardFormApp, PartRow
    from test_document_picker import board

    _, _, pins = collections(library)
    before = snapshot(library)
    app = BoardFormApp(original=board(), service=library)
    async with app.run_test() as pilot:
        await pilot.pause()
        button = (app.query_one('#add-board-document', Button) if target == 'board' else
                  app.query_one(PartRow).query_one('.add-document', Button))
        button.press()
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, DocumentPicker)
        assert sum(picker.is_collection(r) for r in picker.records) == 2
        assert sum(not picker.is_collection(r) for r in picker.records) == 2
        picker.query_one('#picker-search', Input).value = 'Security'
        await pilot.pause()
        picker.query_one(SelectionList).select_all()
        await pilot.pause()
        picker.query_one('#picker-attach', Button).press()
        await pilot.pause()
        draft = app.collect()
        actual = draft['parts'][0]['documents'] if target == 'part' else draft['documents']
        assert {tuple(sorted(pin.items())) for pin in actual} == {tuple(sorted(pin.items())) for pin in pins}
        assert all(set(pin) == {'pod', 'document', 'blob'} for pin in actual)
        library.prepare('board', draft)
    assert snapshot(library) == before


@pytest.mark.parametrize('editing', [False, True])
@pytest.mark.parametrize('mode', ['truecolor', '256', 'standard'])
async def test_collection_editor_picker_only_attaches_documents(library, editing, mode, monkeypatch):
    from caiman.documents.collection_tui import CollectionApp

    monkeypatch.delenv('NO_COLOR', raising=False)
    service, _, pins = collections(library)
    saved = next(r for r in service.list_collections() if r['manifest']['name'] == 'Boot')
    before = snapshot(library)
    app = CollectionApp(root=library.store.root, record=saved if editing else None)
    app.console._color_system = COLOR_SYSTEMS[mode]
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        app.query_one('#choose-documents', Button).press()
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, DocumentPicker)
        assert str(picker.query_one('#picker-title', Static).content) == 'Choose documents'
        assert len(picker.records) == (1 if editing else 2)
        assert all(not picker.is_collection(r) for r in picker.records)
        search = picker.query_one('#picker-search', Input)
        assert 'collections' not in search.placeholder
        search.value = 'Security'
        await pilot.pause()
        assert picker.query_one(SelectionList).option_count == 0
        search.value = ''
        await pilot.pause()
        picker.query_one(SelectionList).select_all()
        await pilot.pause()
        attach = picker.query_one('#picker-attach', Button)
        attach.focus()
        await pilot.pause()
        assert picker.chosen
        assert 'Selected' in app.export_screenshot()
        attach.press()
        await pilot.pause()
        assert app.screen is not picker
        assert {tuple(sorted(pin.items())) for pin in app.collect()['documents']} == {
            tuple(sorted(pin.items())) for pin in pins}
    assert snapshot(library) == before


def test_document_only_picker_rejects_collection_selection(library):
    _, collection, _ = collections(library)
    picker = DocumentPicker(service=library, owner='public', allow_collections=False)
    picker.records = [collection]
    picker.chosen = {0}
    with pytest.raises(ValueError, match='only individual documents'):
        picker.selected_documents()
