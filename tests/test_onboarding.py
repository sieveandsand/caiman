import pytest
from textual.widgets import Input, Select

from caiman.configurations.service import ConfigurationService
from caiman.dashboard.onboarding import SetupApp
from caiman.storage.store import Store


async def fill(app, values):
    for field, value in values.items():
        app.query_one('#' + field, Input).value = value


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
        await fill(project_app, {'name': 'program', 'version': 'A', 'customer': 'Synthetic Customer',
                                 'compartments': 'alpha', 'spec_set': 'release A'})
        await pilot.click('#next')
        await wait_for(pilot, lambda: project_app.reviewing and not project_app.busy)
        assert project_app.reviewing
        await pilot.pause(0.15)
        await pilot.click('#next')
        await wait_for(pilot, lambda: project_app.return_value is not None)
    result = project_app.return_value
    assert result['manifest']['board']['digest'] == board['digest']
    assert result['manifest']['documents'] == []


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
        assert app.query_one('#board-choice', Select).value == Select.NULL
        await fill(app, {'name': 'program', 'version': 'A', 'customer': 'Synthetic Customer',
                         'compartments': 'alpha', 'spec_set': 'release A'})
        await pilot.click('#next')
        await wait_for(pilot, lambda: not app.busy)
        assert not app.reviewing
        assert 'Choose the board' in str(app.query_one('#status').render())
