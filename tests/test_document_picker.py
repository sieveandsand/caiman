from copy import deepcopy

import pytest
from rich.console import COLOR_SYSTEMS
from textual.widgets import Button, Input, OptionList, SelectionList, Static, TextArea

from caiman.boards.form import BoardDocumentCard, BoardFormApp, DocumentRow, PartRow
from caiman.configurations.project_form import ProjectDocumentCard, ProjectFormApp
from caiman.configurations.tui import AttachmentTargetPicker, ConfigApp
from caiman.documents.collection_tui import CollectionApp, MemberCard
from caiman.configurations.service import ConfigurationService
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


def board():
    return dict(board='demo', version='A', parts=[dict(part='chip', role='mcu',
        vendor='another-vendor', documents=[])], links=[])


def snapshot(service):
    return {str(p): p.read_bytes() for p in service.store.root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
@pytest.mark.parametrize('size', [(110, 50), (65, 30)])
async def test_search_multiselect_attach_and_duplicate_exclusion(library, color_system, size, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    original = board()
    before = snapshot(library)
    app = BoardFormApp(original=original, service=library)
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=size) as pilot:
        part = app.query_one(PartRow)
        part.query_one('.part-summary', Button).press()
        await pilot.pause()
        choose = part.query_one('.add-document', Button)
        choose.press()
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, DocumentPicker)
        listing = picker.query_one(SelectionList)
        assert listing.option_count == 2
        search = picker.query_one('#picker-search', Input)
        search.value = 'alpha'
        await pilot.pause()
        listing.focus()
        await pilot.press('space')
        await pilot.pause()
        assert len(picker.chosen) == 1
        search.value = 'beta'
        await pilot.pause()
        assert '1 hidden' in str(picker.query_one('#picker-count', Static).content)
        listing.focus()
        await pilot.press('space')
        await pilot.pause()
        search.value = ''
        await pilot.pause()
        attach = picker.query_one('#picker-attach', Button)
        attach.focus()
        await pilot.pause()
        assert app.focused is attach
        assert attach.styles.border_top[0] == 'double'
        assert len(listing.selected) == 2
        assert '2 selected' in str(picker.query_one('#picker-count', Static).content)
        # Render after focus leaves the list; checkboxes retain selection.
        svg = app.export_screenshot()
        assert 'Alpha' in svg and 'Beta' in svg
        assert svg.count('Selected') >= 2
        assert attach.region.bottom <= size[1]
        attach.press()
        await pilot.pause()
        pins = app.collect()['parts'][0]['documents']
        assert len(pins) == 2
        assert all(set(pin) == {'pod', 'document', 'blob'} for pin in pins)
        assert '2 document pins' in part.query_one('.part-summary', Button).label.plain
        assert app.focused is choose
        rows = list(part.query(DocumentRow))
        assert 'Alpha manual' in str(rows[0].query_one('.document-label', Static).content)
        rows[0].query_one('.field-notes', Input).value = 'Timing details'
        # Metadata mismatch never excludes an attachment; preparation validates fixed pins.
        prepared = library.prepare('board', app.collect())
        assert prepared.manifest['parts'][0]['documents'][0]['notes'] == 'Timing details'
        choose.press()
        await pilot.pause()
        assert app.screen.query_one(SelectionList).option_count == 0
        assert app.screen.query_one('#picker-attach', Button).disabled
        await pilot.press('escape')
        await pilot.pause()
        rows[0].query_one('.remove-row', Button).press()
        await pilot.pause()
        assert '1 document pins' in part.query_one('.part-summary', Button).label.plain
        part.query_one('.collapse-part', Button).press()
        await pilot.pause()
        assert '1 document pins' in part.query_one('.part-summary', Button).label.plain
    assert original == board()
    assert snapshot(library) == before


async def test_cancel_discards_selected_documents_and_blank_rows_do_not_count(library):
    app = BoardFormApp(original=board(), service=library)
    async with app.run_test() as pilot:
        part = app.query_one(PartRow)
        part.query_one('.add-document', Button).press()
        await pilot.pause()
        app.screen.query_one(SelectionList).select_all()
        await pilot.pause()
        app.screen.query_one('#picker-cancel', Button).press()
        await pilot.pause()
        assert app.collect() == board()
        # A retained blank draft from the old workflow is harmless as well.
        await part.query_one('.documents').mount(DocumentRow({}))
        part.refresh_summary()
        assert '0 document pins' in part.query_one('.part-summary', Button).label.plain
        assert app.collect() == board()


async def test_reopened_pins_show_current_names_without_changing_identity(library):
    original = board()
    record = library.list_documents()[0]
    original['parts'][0]['documents'] = [document_pin(record) | {'notes': 'Keep this'}]
    untouched = deepcopy(original)
    app = BoardFormApp(original=original, service=library)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert record['manifest']['name'] in str(app.query_one('.document-label', Static).content)
        assert app.collect() == untouched


async def test_library_failure_keeps_draft_and_allows_cancel(library, monkeypatch):
    def fail():
        raise ValueError('Document dependency is unavailable locally')
    monkeypatch.setattr(library, 'list_documents', fail)
    app = BoardFormApp(original=board(), service=library)
    async with app.run_test() as pilot:
        app.query_one('.add-document', Button).press()
        await pilot.pause()
        assert 'unavailable' in str(app.screen.query_one('#picker-status', Static).content)
        assert app.screen.query_one('#picker-attach', Button).disabled
        await pilot.press('escape')
        await pilot.pause()
        assert app.collect() == board()


def project(library):
    prepared = library.prepare('board', board())
    library.register(prepared)
    return dict(project='program', version='A', customer='Synthetic', spec_set='A',
                boards=[dict(name='demo', version='A', pod=prepared.pod, digest=prepared.digest)],
                documents=[], features=[])


async def select_and_attach(app, pilot):
    listing = app.screen.query_one(SelectionList)
    listing.select_all()
    await pilot.pause()
    attach = app.screen.query_one('#picker-attach', Button)
    attach.focus()
    await pilot.pause()
    assert app.focused is attach
    assert attach.styles.border_top[0] == 'double'
    assert 'Selected' in app.export_screenshot()
    attach.press()
    await pilot.pause()


@pytest.mark.parametrize('kind', ['board', 'project'])
@pytest.mark.parametrize('mode,size', [('truecolor', (110, 50)), ('256', (65, 30)), ('standard', (65, 30))])
async def test_entity_documents_use_picker_and_preserve_existing_pins(library, kind, mode, size, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    original = board() if kind == 'board' else project(library)
    records = sorted(library.list_documents(), key=lambda r: r['manifest']['name'])
    existing = document_pin(records[0])
    if kind == 'board':
        existing['notes'] = 'Keep these notes'
    original['documents'] = [existing]
    untouched = deepcopy(original)
    app = (BoardFormApp(original=original, service=library) if kind == 'board' else
           ProjectFormApp(original=original, root=library.store.root))
    app.console._color_system = COLOR_SYSTEMS[mode]
    card_type = BoardDocumentCard if kind == 'board' else ProjectDocumentCard
    before = snapshot(library)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        add = app.query_one('#add-board-document' if kind == 'board' else '#add-project-document', Button)
        add.press()
        await pilot.pause()
        assert len(app.screen.records) == 1
        assert app.screen.records[0]['manifest']['name'] == 'Beta manual'
        await pilot.press('escape')
        await pilot.pause()
        assert app.collect() == untouched
        add.press()
        await pilot.pause()
        await select_and_attach(app, pilot)
        draft = app.collect()
        assert draft['documents'] == [existing, document_pin(records[1])]
        cards = list(app.query(card_type))
        assert 'BETA MANUAL' in cards[-1].query_one('.card-summary', Button).label.plain
        assert app.focused is add
        assert list(add.parent.parent.children)[-1] is add.parent
        library.prepare(kind, draft)
        cards[-1].query_one('.remove-row', Button).press()
        await pilot.pause()
        assert app.collect() == untouched
    assert original == untouched
    assert snapshot(library) == before


async def test_project_editor_preserves_hidden_features(library):
    original = project(library)
    original['documents'] = [document_pin(library.list_documents()[0])]
    original['features'] = [dict(name='boot', scope='required',
        governed_by=[original['documents'][0] | {'requirements': ['REQ-7']}])]
    app = ProjectFormApp(original=original, root=library.store.root)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.query('#features, #add-feature')
        assert app.collect() == original
        app.query_one('#project-customer', Input).value = 'Changed'
        await pilot.pause()
        draft = app.collect()
        assert draft['features'] == original['features']
        library.prepare('project', draft)


@pytest.mark.parametrize('kind,target', [('board', 'documents'), ('board', 'parts'),
                                        ('project', 'documents')])
async def test_configuration_authoring_picker_updates_only_chosen_target(library, kind, target):
    original = board() if kind == 'board' else project(library)
    if target == 'parts':
        original['parts'].append(dict(part='sensor', vendor='example', role='sensor', documents=[]))
    before = snapshot(library)
    app = ConfigApp(kind, library.store.root, original)
    async with app.run_test(size=(90, 40)) as pilot:
        button = app.query_one('#choose-' + target, Button)
        button.press()
        await pilot.pause()
        if target == 'parts':
            assert isinstance(app.screen, AttachmentTargetPicker)
            app.screen.query_one(OptionList).focus()
            await pilot.press('enter')
            await pilot.pause()
        assert isinstance(app.screen, DocumentPicker)
        await select_and_attach(app, pilot)
        draft = app.collect_draft()
        pins = draft['documents'] if target == 'documents' else draft[target][0]['documents']
        assert len(pins) == 2
        assert all(set(pin) == {'pod', 'document', 'blob'} for pin in pins)
        if target == 'parts':
            assert draft[target][1] == original[target][1]
        library.prepare(kind, draft)
        # Canceling retains the exact JSON, including formatting.
        previous = app.query_one('#' + target, TextArea).text
        button.press()
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert app.query_one('#' + target, TextArea).text == previous
    assert snapshot(library) == before


async def test_invalid_json_is_retained_when_opening_picker(library):
    app = ConfigApp('board', library.store.root, board())
    async with app.run_test() as pilot:
        app.query_one('#parts', TextArea).load_text('[unfinished')
        app.query_one('#choose-parts', Button).press()
        await pilot.pause()
        assert len(app.screen_stack) == 1
        assert app.query_one('#parts', TextArea).text == '[unfinished'
        assert app.query_one('#status', Static).content


@pytest.mark.parametrize('mode', ['truecolor', '256', 'standard'])
async def test_collection_search_picker_preserves_selections_after_cancel(library, mode, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    before = snapshot(library)
    app = CollectionApp(root=library.store.root)
    app.console._color_system = COLOR_SYSTEMS[mode]
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        assert not app.query(MemberCard)
        app.query_one('#choose-documents', Button).press()
        await pilot.pause()
        assert len(app.screen.records) == 2
        await select_and_attach(app, pilot)
        assert len(app.query(MemberCard)) == 2
        app.query_one('#name', Input).value = 'Library'
        app.service.prepare(app.collect())
        app.query_one('#choose-documents', Button).press()
        await pilot.pause()
        assert not app.screen.records
        await pilot.press('escape')
        await pilot.pause()
        assert len(app.query(MemberCard)) == 2
    assert snapshot(library) == before
