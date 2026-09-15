"""The dashboard exposes implemented workflows as a navigable action grid."""

import pytest
from textual.widgets import Button, Static

from caiman.onboarding import LauncherApp


def context():
    return {
        'board': {'manifest': {'board': 'synthetic-board', 'version': 'A'}, 'digest': 'sha256:' + '1' * 64},
        'project': {'manifest': {'project': 'synthetic-project', 'version': 'B'}, 'digest': 'sha256:' + '2' * 64},
    }


ACTIONS = ['ingest', 'documents'] + [
    f'{action}-{kind}' for kind in ('board', 'project')
    for action in ('create', 'select', 'edit', 'show', 'import', 'export', 'validate', 'template')
]


@pytest.mark.asyncio
async def test_dashboard_grid_layout_and_spatial_navigation():
    app = LauncherApp(context=context())
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause()
        assert {tile.id for tile in app.query('.dashboard-tile')} == set(ACTIONS)
        create = app.query_one('#create-board', Button)
        select = app.query_one('#select-board', Button)
        edit = app.query_one('#edit-board', Button)
        assert create.region.y == select.region.y == edit.region.y
        assert create.region.x < select.region.x < edit.region.x
        assert app.focused.id == 'ingest'
        await pilot.press('l', 'j')
        assert app.focused.id == 'select-board'
        await pilot.press('l', 'j')
        assert app.focused.id == 'export-board'
        await pilot.press('k', 'h')
        assert app.focused.id == 'select-board'
        assert 'h left' in str(app.query_one('.key-hint', Static).render())


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_dashboard_actions_are_reachable_by_keyboard(action):
    app = LauncherApp(context=context())
    async with app.run_test(size=(80, 24)) as pilot:
        button = app.query_one('#' + action, Button)
        button.focus()
        await pilot.pause()
        assert button.visible and not button.disabled
        await pilot.press('enter')
    assert app.return_value == action


@pytest.mark.asyncio
async def test_narrow_dashboard_reflows_without_losing_actions():
    app = LauncherApp(context=context())
    async with app.run_test(size=(60, 24)) as pilot:
        await pilot.pause()
        create = app.query_one('#create-board', Button)
        select = app.query_one('#select-board', Button)
        edit = app.query_one('#edit-board', Button)
        assert create.region.y == select.region.y
        assert edit.region.y > create.region.y
        assert edit.region.x == create.region.x
        assert len(app.query('.dashboard-tile')) == len(ACTIONS)
        app.query_one('#template-project', Button).focus()
        await pilot.pause()
        await pilot.press('enter')
    assert app.return_value == 'template-project'


@pytest.mark.asyncio
async def test_missing_selection_disables_only_dependent_actions():
    app = LauncherApp(context={})
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert app.query_one('#edit-board', Button).disabled
        assert app.query_one('#export-project', Button).disabled
        assert not app.query_one('#create-board', Button).disabled
        assert not app.query_one('#validate-project', Button).disabled
        assert 'No selection' in str(app.query_one('#current-context', Static).render())
        await pilot.press('ctrl+q')
    assert app.return_value == 'quit'
