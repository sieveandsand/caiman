"""The dashboard exposes implemented workflows as a navigable action grid."""

import pytest
from textual.widgets import Button, Static

from caiman.onboarding import LauncherApp


ACTIONS = ['ingest', 'documents', 'create-board', 'show-board', 'create-project', 'show-project']


@pytest.mark.asyncio
async def test_home_offers_only_create_and_view_per_kind():
    app = LauncherApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause()
        assert [tile.id for tile in app.query('.dashboard-tile')] == ACTIONS
        for kind in ('board', 'project'):
            create = app.query_one(f'#create-{kind}', Button)
            show = app.query_one(f'#show-{kind}', Button)
            assert create.region.y == show.region.y and create.region.x < show.region.x


@pytest.mark.asyncio
async def test_dashboard_spatial_navigation():
    app = LauncherApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause()
        assert app.focused.id == 'ingest'
        await pilot.press('j')
        assert app.focused.id == 'create-board'
        await pilot.press('l', 'j')
        assert app.focused.id == 'show-project'
        await pilot.press('h', 'k', 'k')
        assert app.focused.id == 'ingest'
        assert 'h left' in str(app.query_one('.key-hint', Static).render())


@pytest.mark.asyncio
@pytest.mark.parametrize('action', ACTIONS)
async def test_dashboard_actions_are_reachable_by_keyboard(action):
    app = LauncherApp()
    async with app.run_test(size=(80, 24)) as pilot:
        button = app.query_one('#' + action, Button)
        button.focus()
        await pilot.pause()
        assert button.visible and not button.disabled
        await pilot.press('enter')
    assert app.return_value == action


def test_dashboard_tiles_use_the_dotted_border():
    from caiman.theme import DOT_BORDER
    assert DOT_BORDER == 'dotted'
    css = LauncherApp.CSS
    tile_rules = [line for line in css.splitlines() if line.strip().startswith('.dashboard-tile')]
    assert tile_rules and all(f'border: {DOT_BORDER} ' in rule for rule in tile_rules)
    assert 'border: round' not in ''.join(tile_rules)


@pytest.mark.asyncio
async def test_home_has_no_default_board_or_project():
    app = LauncherApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert not app.query('#current-context')
        assert not app.query('#select-board') and not app.query('#select-project')
        assert not any(tile.disabled for tile in app.query('.dashboard-tile'))
        await pilot.press('q')
    assert app.return_value == 'quit'


@pytest.mark.asyncio
async def test_bottom_prompt_is_the_vim_hint_only():
    from textual.widgets import Footer
    app = LauncherApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert not app.query(Footer)
        assert not any(key.startswith('ctrl+') for key in app._bindings.key_to_bindings)
        await pilot.press('ctrl+q')
        assert app.is_running
        await pilot.press('q')
    assert app.return_value == 'quit'


@pytest.mark.asyncio
@pytest.mark.parametrize('width, height, shown', [(100, 40, True), (40, 40, False), (100, 24, False)])
async def test_mascot_sits_top_right_and_steps_aside_when_cramped(width, height, shown):
    from caiman.mascot import HEIGHT, LOWER_HALF, UPPER_HALF
    app = LauncherApp()
    async with app.run_test(size=(width, height)) as pilot:
        await pilot.pause()
        mascot = app.query_one('#mascot', Static)
        assert mascot.display is shown
        if shown:
            brand = app.query_one('#brand', Static)
            assert mascot.region.y == brand.region.y == 0
            assert mascot.region.x > brand.region.x
            assert mascot.region.right >= width - 3
            art = str(mascot.render())
            assert len(art.splitlines()) == HEIGHT
            assert set(art) <= {UPPER_HALF, LOWER_HALF, ' ', '\n'}


def test_mascot_half_blocks_map_two_square_pixels_per_cell():
    from caiman import mascot
    from caiman.mascot import LOWER_HALF, PALETTE, UPPER_HALF, WIDTH, render_mascot
    original = mascot.SPRITE
    try:
        mascot.SPRITE = ('gd.', 'p..')
        art = render_mascot()
    finally:
        mascot.SPRITE = original
    cells = list(art.plain)
    # Padding to the full sprite width keeps the masthead from shifting.
    assert len(cells) == WIDTH
    assert cells[:3] == [UPPER_HALF, UPPER_HALF, ' ']
    styles = {span.start: span.style for span in art.spans}
    assert (styles[0].color.name, styles[0].bgcolor.name) == (PALETTE['g'], PALETTE['p'])
    assert (styles[1].color.name, styles[1].bgcolor) == (PALETTE['d'], None)
    mascot.SPRITE = ('..', 'g.')
    try:
        assert render_mascot().plain[0] == LOWER_HALF
    finally:
        mascot.SPRITE = original
