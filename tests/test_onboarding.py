import pytest
from textual.widgets import Input, Select, SelectionList

from caiman.configurations.service import ConfigurationService
from caiman.dashboard.onboarding import SetupApp
from caiman.storage.store import Store


async def fill(app, values):
    for field, value in values.items():
        app.query_one('#' + field, Select if field == 'pod' else Input).value = value


async def wait_for(pilot, condition):
    for _ in range(40):
        if condition():
            return
        await pilot.pause(0.025)
    assert condition()


@pytest.mark.asyncio
async def test_guided_board_then_project_without_documents(tmp_path):
    board_app = SetupApp(kind='board', store_root=tmp_path / 'store')
    async with board_app.run_test(size=(110, 45)) as pilot:
        await pilot.pause()
        await fill(board_app, {'name': 'demo', 'version': 'v1', 'vendor': 'synthetic', 'part': 'chip'})
        await pilot.click('#next')
        await wait_for(pilot, lambda: board_app.reviewing and not board_app.busy)
        assert board_app.reviewing
        assert not (tmp_path / 'store').exists()
        await pilot.pause(0.15)
        await pilot.click('#next')
        await wait_for(pilot, lambda: board_app.return_value is not None)
    board = board_app.return_value
    assert board['manifest']['parts'][0]['documents'] == []
    project_app = SetupApp(kind='project', store_root=tmp_path / 'store', board=board)
    async with project_app.run_test(size=(110, 45)) as pilot:
        await pilot.pause()
        await fill(project_app, {'name': 'program', 'version': 'A', 'customer': 'Synthetic Customer'})
        await pilot.click('#next')
        await wait_for(pilot, lambda: project_app.reviewing and not project_app.busy)
        assert project_app.reviewing
        await pilot.pause(0.15)
        await pilot.click('#next')
        await wait_for(pilot, lambda: project_app.return_value is not None)
    result = project_app.return_value
    assert result['manifest']['boards'][0]['digest'] == board['digest']
    assert result['manifest']['documents'] == []
    assert 'spec_set' not in result['manifest']


@pytest.mark.asyncio
async def test_cancel_setup_does_not_create_store(tmp_path):
    app = SetupApp(kind='board', store_root=tmp_path / 'store')
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click('#cancel')
    assert app.return_value is None
    assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_project_requires_an_explicitly_chosen_board(tmp_path):
    root = tmp_path / 'store'
    service = ConfigurationService(Store(root))
    service.register(service.prepare('board', {'board': 'demo', 'version': 'v1',
        'parts': [{'role': 'main', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}], 'links': []}))
    app = SetupApp(kind='project', store_root=root)
    async with app.run_test(size=(110, 45)) as pilot:
        await wait_for(pilot, lambda: app.boards and not app.busy)
        assert app.query_one('#board-choice', SelectionList).selected == []
        await fill(app, {'name': 'program', 'version': 'A', 'customer': 'Synthetic Customer'})
        await pilot.click('#next')
        await wait_for(pilot, lambda: not app.busy)
        assert not app.reviewing
        assert 'Choose the board' in str(app.query_one('#status').render())


@pytest.mark.asyncio
async def test_project_pins_every_chosen_board_including_two_versions_of_one(tmp_path):
    root = tmp_path / 'store'
    service = ConfigurationService(Store(root))
    digests = {}
    for name, version in (('demo', 'A'), ('demo', 'B'), ('io', 'A')):
        prepared = service.prepare('board', {'board': name, 'version': version,
            'parts': [{'role': 'main', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}], 'links': []})
        service.register(prepared)
        digests[(name, version)] = prepared.digest
    app = SetupApp(kind='project', store_root=root)
    async with app.run_test(size=(110, 45)) as pilot:
        await wait_for(pilot, lambda: len(app.boards) == 3 and not app.busy)
        choice = app.query_one('#board-choice', SelectionList)
        for index, record in enumerate(app.boards):
            if record['name'] == 'demo':
                choice.select(index)
        await fill(app, {'name': 'program', 'version': 'A', 'customer': 'Synthetic Customer'})
        await pilot.click('#next')
        await wait_for(pilot, lambda: app.reviewing and not app.busy)
        review = str(app.query_one('#review').render())
        assert 'Board: demo @ A' in review and 'Board: demo @ B' in review and 'io @' not in review
        app.query_one('#next').press()
        await wait_for(pilot, lambda: app.return_value is not None)
    boards = app.return_value['manifest']['boards']
    assert sorted((board['name'], board['version'], board['digest']) for board in boards) == [
        ('demo', 'A', digests[('demo', 'A')]), ('demo', 'B', digests[('demo', 'B')])]


@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
@pytest.mark.parametrize('width', [70, 110])
async def test_project_pickers_keyboard_and_retained_selection(tmp_path, color_system, width):
    from rich.console import COLOR_SYSTEMS

    store = Store(tmp_path / 'store')
    store.pods.ensure('customer', name='Customer pod')
    service = ConfigurationService(store)
    for version in ('A', 'B', 'C'):
        service.register(service.prepare('board', {
            'board': 'demo', 'version': version, 'pod': 'customer',
            'parts': [{'role': 'main', 'vendor': 'Synthetic', 'part': 'chip', 'documents': []}],
            'links': [],
        }))
    app = SetupApp(kind='project', store_root=store.root, pod='customer')
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(width, 40)) as pilot:
        await pilot.pause()
        assert not app.query('Select#pod')
        assert app.project_pod == 'customer'
        app.query_one('#version').focus()
        await pilot.press('tab')
        boards = app.query_one('#board-choice', SelectionList)
        assert app.focused is boards
        assert boards.selected == []
        before = app.query_one('#edit').scroll_y
        await pilot.press('j', 'space', 'down', 'space', 'k')
        assert boards.highlighted == 1
        assert boards.selected == [1, 2]
        assert app.query_one('#edit').scroll_y == before
        assert boards.styles.border_top[0] == 'double'
        assert boards.get_component_rich_style('option-list--option-highlighted').reverse
        await pilot.press('tab')
        assert app.focused.id == 'customer'
        app.query_one('#next').focus()
        await pilot.pause()
        assert boards.selected == [1, 2]
        for index in (1, 2):
            assert boards.get_option_at_index(index).prompt.plain.startswith('[x]')
        assert 'Customer pod' in boards.get_option_at_index(0).prompt.plain
        assert not app.query('#spec_set')
        await fill(app, {'name': 'program', 'version': 'release', 'customer': 'Customer'})
        await pilot.press('enter')
        await wait_for(pilot, lambda: app.reviewing and not app.busy)
        assert app.prepared.pod == 'customer'
        assert 'spec_set' not in app.prepared.manifest
        assert {pin['pod'] for pin in app.prepared.manifest['boards']} == {'customer'}
        app.query_one('#back').press()
        await pilot.pause()
        assert app.project_pod == 'customer'
        assert boards.selected == [1, 2]


async def test_legacy_missing_default_uses_public(tmp_path):
    store = Store(tmp_path / 'store')
    store.pods.ensure('available')
    store._atomic_write(store.root / '.pods.json', b'{"default":"missing"}', immutable=False)
    app = SetupApp(kind='project', store_root=store.root)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.project_pod == 'public'


async def test_handed_over_board_keeps_its_pod_after_label_moves(tmp_path):
    store = Store(tmp_path / 'store')
    store.pods.ensure('hardware')
    service = ConfigurationService(store)
    draft = {'board': 'demo', 'version': 'A', 'pod': 'hardware',
             'parts': [{'role': 'main', 'vendor': 'Synthetic', 'part': 'first', 'documents': []}],
             'links': []}
    original = service.prepare('board', draft)
    service.register(original)
    draft['parts'][0]['part'] = 'replacement'
    service.register(service.prepare('board', draft))
    app = SetupApp(kind='project', store_root=store.root,
                   board={'manifest': original.manifest, 'digest': original.digest, 'pod': original.pod})
    async with app.run_test() as pilot:
        await pilot.pause()
        boards = app.query_one('#board-choice', SelectionList)
        assert len(boards.selected) == 1
        pin = app.draft()['boards'][0]
        assert pin['pod'] == 'hardware'
        assert pin['digest'] == original.digest
        assert boards.get_option_at_index(boards.selected[0]).prompt.plain.startswith('[x]')


@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
@pytest.mark.parametrize('size', [(110, 50), (65, 30)])
async def test_create_project_with_documents_and_collection(tmp_path, color_system, size):
    from rich.console import COLOR_SYSTEMS
    from textual.widgets import Button
    from caiman.documents.collections import CollectionService
    from caiman.documents.ingest import prepare_document
    from caiman.documents.picker import DocumentPicker, document_pin

    store = Store(tmp_path / 'store')
    store.pods.ensure('customer')
    store.pods.ensure('unrelated')
    source = tmp_path / 'manual.txt'
    source.write_text('Synthetic manual')
    for pod in ('public', 'customer', 'unrelated'):
        store.register(prepare_document(source, dict(name=f'{pod} manual', issuer='Synthetic',
            part='chip', version='A'), pod=pod))
    service = ConfigurationService(store)
    public = next(r for r in service.list_documents() if r['pod'] == 'public')
    collections = CollectionService(store)
    collections.register(collections.prepare(dict(name='Reference set', documents=[document_pin(public)])))
    prepared = service.prepare('board', dict(board='demo', version='A', parts=[dict(
        part='chip', role='mcu', vendor='Synthetic', documents=[])], links=[]))
    service.register(prepared)
    before = {p: p.read_bytes() for p in store.root.rglob('*') if p.is_file()}
    app = SetupApp(kind='project', store_root=store.root, pod='customer')
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=size) as pilot:
        await wait_for(pilot, lambda: app.boards and not app.busy)
        app.query_one('#board-choice', SelectionList).select(0)
        await fill(app, dict(name='program', version='A', customer='Customer'))
        add = app.query_one('#add-project-document', Button)
        add.press()
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, DocumentPicker)
        await wait_for(pilot, lambda: len(picker.records) == 3)
        assert {r['pod'] for r in picker.records} == {'customer', 'public'}
        picker.query_one(SelectionList).select_all()
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert app.draft()['documents'] == []
        add.press()
        await pilot.pause()
        picker = app.screen
        await wait_for(pilot, lambda: len(picker.records) == 3)
        listing = picker.query_one(SelectionList)
        listing.focus()
        await pilot.press('space', 'down', 'space', 'down', 'space')
        attach = picker.query_one('#picker-attach', Button)
        attach.focus()
        await pilot.pause()
        assert len(listing.selected) == 3
        assert app.export_screenshot().count('Selected') >= 3
        assert attach.styles.border_top[0] == 'double'
        attach.press()
        await wait_for(pilot, lambda: len(app.documents) == 3)
        await pilot.pause()
        assert app.focused is add
        assert len(app.draft()['documents']) == 3
        add.press()
        await pilot.pause()
        assert app.screen.query_one(SelectionList).option_count == 0
        await pilot.press('escape')
        await pilot.pause()
        # Remove a single document; the collection remains an editable attachment.
        index = next(i for i, r in app.documents.items() if r['pod'] == 'customer')
        app.query_one(f'#remove-document-{index}', Button).press()
        await pilot.pause()
        pins = app.draft()['documents']
        assert len(pins) == 2
        assert sum('collection' in pin for pin in pins) == 1
        app.query_one('#next', Button).press()
        await wait_for(pilot, lambda: app.reviewing and not app.busy)
        review = str(app.query_one('#review').render())
        assert 'public manual' in review and 'Reference set' in review
        assert app.prepared.manifest['documents'] == pins
        app.query_one('#back', Button).press()
        await pilot.pause()
        assert app.draft()['documents'] == pins
        assert {p: p.read_bytes() for p in store.root.rglob('*') if p.is_file()} == before
        app.query_one('#next', Button).press()
        await wait_for(pilot, lambda: app.reviewing and not app.busy)
        app.query_one('#next', Button).press()
        await wait_for(pilot, lambda: app.return_value is not None)
    assert app.return_value['pod'] == 'customer'
    assert app.return_value['manifest']['documents'] == pins
