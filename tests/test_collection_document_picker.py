"""Collection editors attach individual documents through the shared picker."""
import pytest
from rich.console import COLOR_SYSTEMS
from textual.widgets import Button, Input, SelectionList, Static

from caiman.configurations.service import ConfigurationService
from caiman.documents.collections import CollectionService
from caiman.documents.ingest import prepare_document
from caiman.documents.picker import DocumentPicker, document_pin
from caiman.storage.store import Store


@pytest.fixture
def library(tmp_path):
    store = Store(tmp_path / 'store')
    source = tmp_path / 'manual.txt'
    source.write_text('Synthetic test document')
    for name, pod in [('Alpha manual', 'public'), ('Beta manual', 'public')]:
        store.register(prepare_document(source, dict(name=name, issuer='synthetic',
            part='different-chip', version='A', description='Test document'), pod=pod))
    return ConfigurationService(store)


def snapshot(service):
    return {str(p): p.read_bytes() for p in service.store.root.rglob('*') if p.is_file()}


def collections(library):
    service = CollectionService(library.store)
    pins = [document_pin(r) for r in sorted(library.list_documents(), key=lambda r: r['manifest']['name'])]
    first = service.register(service.prepare(dict(name='Security', documents=pins)))
    service.register(service.prepare(dict(name='Boot', documents=pins[:1])))
    return service, first, pins


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
