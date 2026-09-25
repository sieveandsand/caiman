"""The dashboard exposes implemented workflows as a navigable action grid."""

import pytest
from textual.widgets import Button, Static

from caiman.dashboard.onboarding import LauncherApp


ACTIONS = ['ingest', 'documents', 'create-board', 'show-board', 'create-project', 'show-project', 'hooks-claude', 'hooks-codex',
           'repo-add', 'repo-remove', 'repo-initialize']


@pytest.mark.asyncio
async def test_home_offers_only_create_and_view_per_kind():
    app = LauncherApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause()
        assert [tile.id for tile in app.query('.dashboard-tile.card-face')] == ACTIONS
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
    from caiman.ui.mascot import HEIGHT, LOWER_HALF, UPPER_HALF
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
    from caiman.ui import mascot
    from caiman.ui.mascot import LOWER_HALF, PALETTE, UPPER_HALF, WIDTH, render_mascot
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


@pytest.mark.asyncio
async def test_dashboard_cards_resize_and_move_shadow_without_layout_changes():
    from caiman.dashboard.onboarding import DashboardTile
    from caiman.ui.pixel_title import pixel_title

    app = LauncherApp()
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        first = app.query_one('#ingest', DashboardTile)
        second = app.query_one('#documents', DashboardTile)
        assert '\n'.join(pixel_title('Ingest document', 100)) in first.label.plain
        assert 'Ingest document' not in first.label.plain
        assert 'Register Markdown' in app.export_screenshot().replace('&#160;', ' ')
        before = [card.region for card in (first, second)]
        assert first.parent.query_one('.card-shadow').visible
        await pilot.press('l')
        assert not first.parent.query_one('.card-shadow').visible
        assert second.parent.query_one('.card-shadow').visible
        assert before == [card.region for card in (first, second)]
        await pilot.resize_terminal(60, 30)
        assert second.region.y > first.parent.region.bottom
        app.query_one('#quit').focus()
        await pilot.pause()
        assert not second.parent.query_one('.card-shadow').visible


def test_dashboard_card_fallback_keeps_exact_unicode_identity():
    from caiman.dashboard.onboarding import DashboardTile

    tile = DashboardTile('板-α / Rev B', '3 Documents', action='example')
    tile.format_card(24)
    assert '板-α / Rev B' in tile.label.plain
    assert '3 Documents' in tile.label.plain


@pytest.mark.asyncio
async def test_clicking_the_mascot_opens_little_caiman():
    app = LauncherApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        await pilot.click('#mascot')
    assert app.return_value == 'little-caiman'


@pytest.mark.asyncio
async def test_little_caiman_key_works_when_the_mascot_steps_aside():
    app = LauncherApp()
    async with app.run_test(size=(40, 40)) as pilot:
        await pilot.pause()
        assert not app.query_one('#mascot').display
        assert 'c little caiman' in str(app.query_one('.key-hint', Static).render())
        await pilot.press('c')
    assert app.return_value == 'little-caiman'


@pytest.mark.asyncio
async def test_mascot_is_a_keyboard_button_for_little_caiman():
    app = LauncherApp()
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert app.focused.id == 'ingest'
        await pilot.press('k')
        assert app.focused.id == 'mascot'
        await pilot.press('j')
        assert app.focused.id != 'mascot'
        app.query_one('#mascot').focus()
        await pilot.press('enter')
    assert app.return_value == 'little-caiman'


@pytest.mark.asyncio
async def test_focus_scrolls_minimally_instead_of_pinning_cards_to_the_top():
    app = LauncherApp()
    async with app.run_test(size=(60, 30)) as pilot:
        await pilot.pause()
        body = app.query_one('#body')
        await pilot.press('j')
        await pilot.pause()
        # The next tile was already visible, so nothing moves.
        assert body.scroll_y == 0
        # Move down until the first press that has to scroll.
        for _ in range(20):
            await pilot.press('j')
            await pilot.pause()
            if body.scroll_y > 0:
                break
        frame, view = app.focused.parent.region, body.content_region
        assert body.scroll_y > 0
        # Textual centres an off-screen focus target; the whole frame, shadow row
        # included, is visible and the card is not pinned to the top.
        assert view.y < frame.y and frame.bottom <= view.bottom
