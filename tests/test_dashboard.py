"""The dashboard exposes implemented workflows as a navigable action grid."""

import pytest
from textual.widgets import Button, ListView, Static

from caiman.dashboard.onboarding import LauncherApp


ACTIONS = ['documents', 'show-board', 'show-project', 'hooks', 'repos']


async def test_q_returns_from_pod_actions_before_leaving_page(tmp_path):
    from caiman.dashboard.onboarding import CategoryApp

    app = CategoryApp('repos', store_root=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('enter')
        assert app.focused.id == 'repo-initialize'
        assert 'q back to pods' in str(app.query_one('.key-hint', Static).render())
        await pilot.press('q')
        assert app.is_running and app.focused.id == 'pod-list'
        assert 'Enter select pod' in str(app.query_one('.key-hint', Static).render())
        await pilot.press('q')
    assert app.return_value is None


@pytest.mark.parametrize('width', [45, 100])
@pytest.mark.parametrize('up, down, left, right', [('k', 'j', 'h', 'l'), ('up', 'down', 'left', 'right')])
async def test_pod_keyboard_navigation_reaches_all_controls(tmp_path, width, up, down, left, right):
    from caiman.dashboard.onboarding import CategoryApp
    from caiman.repositories.service import RepoManager

    manager = RepoManager(tmp_path)
    manager.apply(manager.prepare('initialize', 'alpha'))
    app = CategoryApp('repos', store_root=tmp_path)
    async with app.run_test(size=(width, 32)) as pilot:
        await pilot.pause()
        assert app.focused.id == 'pod-list'
        await pilot.press(up)
        assert app.focused.id == 'repo-add'
        await pilot.press(left)
        assert app.focused.id == 'repo-create'
        await pilot.press(right, down)
        assert app.focused.id == 'pod-list'
        # Enter selects the pod and skips its unavailable actions.
        await pilot.press('enter')
        assert app.focused.id == 'repo-initialize'
        await pilot.press(left, right)
        assert app.focused.id == 'repo-initialize'
        await pilot.press('q')
        assert app.is_running and app.focused.id == 'pod-list'
        await pilot.press(down)
        assert app.selected_pod == 'alpha'
        await pilot.press(down)
        assert app.focused.id == 'pod-list'
        await pilot.press('enter')
        assert app.focused.id == 'repo-sync'
        await pilot.press(right)
        assert app.focused.id == 'repo-default'
        await pilot.press(right)
        assert app.focused.id == 'repo-initialize'
        await pilot.press(right)
        assert app.focused.id == 'repo-unregister'
        await pilot.press(right)
        assert app.focused.id == 'repo-sync'
        await pilot.press(left)
        assert app.focused.id == 'repo-unregister'
        await pilot.press('q')
        assert app.is_running and app.focused.id == 'pod-list'
        assert app.selected_pod == 'alpha'
        await pilot.press('enter', 'enter')
    assert app.return_value == {'action': 'repo-sync', 'pod': 'alpha'}


@pytest.mark.parametrize('width', [45, 100])
@pytest.mark.parametrize('action', ['sync', 'default', 'initialize', 'remove', 'unregister', 'create', 'add'])
async def test_pod_buttons_target_selection(tmp_path, width, action):
    from caiman.dashboard.onboarding import CategoryApp
    from caiman.repositories.service import RepoManager

    manager = RepoManager(tmp_path)
    remote = 'git@example.com:team/alpha.git' if action == 'remove' else ''
    manager.apply(manager.prepare('initialize', 'alpha', remote))
    app = CategoryApp('repos', store_root=tmp_path)
    async with app.run_test(size=(width, 32)) as pilot:
        await pilot.pause()
        assert not app.query('.card-face')
        assert app.query_one('#repo-create').region.y < app.query_one('#pod-list').region.y
        assert app.query_one('#repo-sync').disabled
        assert app.query_one('#repo-default').disabled
        await pilot.press('j')
        await pilot.pause()
        assert 'alpha' in str(app.query_one('#selected-pod', Static).render())
        assert not app.query_one('#repo-sync').disabled
        assert app.query_one('#repo-initialize').display is (action != 'remove')
        assert app.query_one('#repo-remove').display is (action == 'remove')
        button = app.query_one('#repo-' + action, Button)
        button.focus()
        await pilot.pause()
        assert button.region.right <= width
        await pilot.press('enter')
    assert app.return_value == ('repo-' + action if action in {'create', 'add'} else
                                {'action': 'repo-' + action, 'pod': 'alpha'})


async def test_pod_list_navigation_scrolls_only_for_offscreen_rows(tmp_path):
    from caiman.dashboard.onboarding import CategoryApp
    from caiman.storage.store import Store

    for index in range(12):
        Store(tmp_path).pods.ensure(f'pod-{index:02}')
    app = CategoryApp('repos', store_root=tmp_path)
    async with app.run_test(size=(70, 28)) as pilot:
        await pilot.pause()
        body = app.query_one('#body')
        listing = app.query_one('#pod-list', ListView)
        assert body.scroll_y == 0
        await pilot.press('j')
        await pilot.pause()
        assert body.scroll_y == 0
        for _ in range(10):
            await pilot.press('j')
            await pilot.pause()
            if body.scroll_y:
                break
        assert body.scroll_y > 0
        row = listing.highlighted_child.region
        assert body.content_region.y < row.y
        assert row.bottom <= body.content_region.bottom
        await pilot.press(*(['k'] * listing.index))
        await pilot.pause()
        assert listing.index == 0
        assert listing.highlighted_child.region.y >= body.content_region.y


@pytest.mark.parametrize('width', [60, 110])
async def test_pods_status_precedes_actions_and_refreshes(tmp_path, width):
    from caiman.dashboard.onboarding import CategoryApp
    from caiman.repositories.service import RepoManager
    from caiman.repositories.status import PodStatusRow

    manager = RepoManager(tmp_path)
    manager.apply(manager.prepare('initialize', 'alpha'))
    manager.apply(manager.prepare('sync', 'alpha'))
    app = CategoryApp('repos', store_root=tmp_path)
    async with app.run_test(size=(width, 35)) as pilot:
        await pilot.pause()
        rows = list(app.query(PodStatusRow))
        listing = app.query_one('#pod-list', ListView)
        text = lambda row: str(row.query_one(Static).render())
        assert 'alpha' in text(rows[1])
        assert 'Clean  ·  caiman-store' in text(rows[1])
        assert '[default]' in text(rows[0])
        assert listing.region.bottom < app.query_one('#pod-actions').region.y
        assert rows[1].region.y >= rows[0].region.bottom
        assert app.query_one('#body').scroll_y == 0
        assert app.focused is listing
        assert listing.index == 0
        await pilot.press('j')
        await pilot.pause()
        assert listing.index == 1
        assert app.query_one('#body').scroll_y == 0
        await pilot.press('up', 'down')
        assert listing.index == 1
        assert app.is_running
        await pilot.press('tab')
        assert app.focused.id == 'repo-sync'
        (manager.local_path('alpha') / 'new file').write_text('new\n')
        app.query_one('#refresh-status', Button).press()
        await pilot.pause()
        assert '1 untracked' in text(list(app.query(PodStatusRow))[1])
        assert listing.highlighted_child.record['pod'] == 'alpha'
        assert app.is_running


@pytest.mark.asyncio
async def test_home_offers_one_card_per_category():
    app = LauncherApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause()
        assert [tile.id for tile in app.query('.dashboard-tile.card-face')] == ACTIONS
        # Adding and viewing live inside each category, not on the home screen.
        assert not app.query('#ingest') and not app.query('#create-board') and not app.query('#repo-add')


@pytest.mark.asyncio
async def test_dashboard_spatial_navigation():
    app = LauncherApp()
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause()
        assert app.focused.id == 'documents'
        await pilot.press('l')
        assert app.focused.id == 'show-board'
        await pilot.press('j')
        assert app.focused.id == 'hooks'
        await pilot.press('h', 'j')
        assert app.focused.id == 'repos'
        await pilot.press('k', 'k')
        assert app.focused.id == 'documents'
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
@pytest.mark.parametrize('category, actions', [
    ('hooks', ['hooks-claude', 'hooks-codex'])])
async def test_category_pages_offer_their_actions_as_cards(category, actions):
    from caiman.dashboard.onboarding import CategoryApp
    from caiman.ui.cards import AddTile

    for action in actions:
        app = CategoryApp(category)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert [card.id for card in app.query('.card-face')] == actions
            assert app.focused.id == ('refresh-status' if category == 'repos' else actions[0])
            app.query_one('#' + action, Button).focus()
            await pilot.press('enter')
        assert app.return_value == action
    app = CategoryApp(category)
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        # The repo manager's add action is the trailing add card.
        assert [card.id for card in app.query(AddTile)] == (['repo-add'] if category == 'repos' else [])
        await pilot.press('q')
    assert app.return_value is None


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

    app = LauncherApp()
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        first = app.query_one('#documents', DashboardTile)
        second = app.query_one('#show-board', DashboardTile)
        assert 'DOCUMENTS' in first.label.plain
        assert 'Documents' not in first.label.plain
        assert 'Add · view · edit' in first.label.plain
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
async def test_menu_defaults_to_normal_width_uppercase_headings():
    from caiman.dashboard.onboarding import DashboardTile

    app = LauncherApp()
    async with app.run_test(size=(110, 40)) as pilot:
        first = app.query_one('#documents', DashboardTile)
        await pilot.pause()
        assert first.label.plain.startswith('▌ DOCUMENTS\n')
        # Unbound letters leave the screen as it was.
        await pilot.press('t', 'T')
        assert app.focused is first
        assert first.label.plain.startswith('▌ DOCUMENTS\n')
        assert 'font' not in str(app.query_one('.key-hint', Static).render())
        await pilot.press('enter')
    assert app.return_value == 'documents'




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
        assert app.focused.id == 'documents'
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
