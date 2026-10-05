from copy import deepcopy

import pytest
from rich.console import COLOR_SYSTEMS
from textual.widgets import Button, Input, SelectionList, Static

from caiman.boards.picker import BoardPicker, board_pin
from caiman.configurations.project_form import PinnedBoardCard, ProjectFormApp
from caiman.configurations.service import ConfigurationService
from caiman.storage.store import Store


@pytest.fixture
def library(tmp_path):
    service = ConfigurationService(Store(tmp_path / 'store'))
    for pod, name, version in [('public', 'main', 'Z-sample'), ('public', 'main', 'A-sample'),
                               ('alpha', 'io', 'rev-b'), ('beta', 'other', '1')]:
        service.register(service.prepare('board', dict(pod=pod, board=name, version=version,
            vendor='Synthetic', parts=[dict(part='chip', vendor='Synthetic', role='mcu', documents=[])], links=[])))
    return service


def project():
    return dict(project='demo', version='A', customer='Synthetic', pod='alpha',
                boards=[], documents=[], features=[])


def snapshot(service):
    return {str(p): p.read_bytes() for p in service.store.root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('mode', ['truecolor', '256', 'standard'])
@pytest.mark.parametrize('size', [(110, 50), (65, 30)])
async def test_pick_board_versions_search_attach_and_remove(library, mode, size, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    before = snapshot(library)
    original = project()
    app = ProjectFormApp(original=original, root=library.store.root)
    app.console._color_system = COLOR_SYSTEMS[mode]
    async with app.run_test(size=size) as pilot:
        choose = app.query_one('#add-board', Button)
        choose.press()
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, BoardPicker)
        assert len(picker.records) == 3
        search = picker.query_one('#picker-search', Input)
        listing = picker.query_one(SelectionList)
        search.value = 'main Z-sample'
        await pilot.pause()
        assert listing.option_count == 1
        listing.focus()
        await pilot.press('space')
        search.value = 'main A-sample'
        await pilot.pause()
        assert '1 hidden' in str(picker.query_one('#picker-count', Static).content)
        listing.focus()
        await pilot.press('space')
        search.value = 'no-matches'
        await pilot.pause()
        assert listing.option_count == 0
        assert 'No matches' in str(picker.query_one('#picker-status', Static).content)
        search.value = 'main'
        await pilot.pause()
        attach = picker.query_one('#picker-attach', Button)
        attach.focus()
        await pilot.pause()
        assert len(listing.selected) == 2
        assert attach.styles.border_top[0] == 'double'
        assert app.export_screenshot().count('Selected') >= 2
        assert attach.region.bottom <= size[1]
        attach.press()
        await pilot.pause()
        pins = app.collect()['boards']
        assert {p['version'] for p in pins} == {'Z-sample', 'A-sample'}
        assert all(set(p) == {'name', 'version', 'pod', 'digest'} for p in pins)
        assert pins == [board_pin(r) for r in picker.records if r['name'] == 'main']
        assert app.focused is choose
        library.prepare('project', app.collect())
        choose.press()
        await pilot.pause()
        assert [r['name'] for r in app.screen.records] == ['io']
        app.screen.query_one(SelectionList).select_all()
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert app.collect()['boards'] == pins
        card = app.query(PinnedBoardCard).first()
        card.query_one('.card-summary', Button).press()
        await pilot.pause()
        card.query_one('.remove-row', Button).press()
        await pilot.pause()
        assert app.collect()['boards'] == pins[1:]
    assert original == project()
    assert snapshot(library) == before


def test_board_picker_filters_owner_and_existing_pins(library):
    records = library.list_configs('board', pods={'public'})
    picker = BoardPicker(service=library, owner='public', attached=[board_pin(records[0])])
    assert picker.load_records() == records[1:]
    picker.attached = [dict(name=records[0]['name'], version=records[0]['version']), {}]
    assert picker.load_records() == records[1:]
    # A retained immutable pin is not silently replaced after its label changes.
    picker.attached = [board_pin(records[0]) | {'digest': 'sha256:' + '0' * 64}]
    assert picker.load_records() == records


async def test_empty_library_cancel_and_failure_preserve_draft(tmp_path, monkeypatch):
    app = ProjectFormApp(original=project(), root=tmp_path / 'store')
    async with app.run_test() as pilot:
        choose = app.query_one('#add-board', Button)
        before = deepcopy(app.collect())
        choose.press()
        await pilot.pause()
        assert 'No unattached boards' in str(app.screen.query_one('#picker-status', Static).content)
        assert app.screen.query_one('#picker-attach', Button).disabled
        await pilot.press('escape')
        await pilot.pause()
        def fail(*args, **kwargs):
            raise ValueError('Board dependency unavailable')
        monkeypatch.setattr(app.service, 'list_configs', fail)
        choose.press()
        await pilot.pause()
        assert 'unavailable' in str(app.screen.query_one('#picker-status', Static).content)
        app.screen.query_one('#picker-cancel', Button).press()
        await pilot.pause()
        assert app.collect() == before
    assert not (tmp_path / 'store').exists()
