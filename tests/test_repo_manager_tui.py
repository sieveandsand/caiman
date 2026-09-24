import pytest
from textual.widgets import Button, Checkbox, Input, Select

from caiman.repositories.tui import RepoManagerApp


@pytest.mark.asyncio
async def test_add_review_edit_and_apply(tmp_path, monkeypatch):
    app = RepoManagerApp(store_root=tmp_path)
    monkeypatch.setattr(app.manager, '_verify_remote', lambda *args: None)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        app.query_one('#compartment', Input).value = 'alpha'
        app.query_one('#remote', Input).value = 'git@example.com:team/alpha.git'
        await pilot.pause()
        await pilot.click('#review')
        await pilot.pause()
        assert app.plan.compartment == 'alpha'
        assert not app.manager.path.exists()
        app.query_one('#compartment', Input).value = 'falcon'
        await pilot.pause()
        assert app.plan is None
        assert app.query_one('#apply', Button).disabled
        await pilot.pause(0.35)  # Allow Textual's repeated-click debounce to expire.
        await pilot.click('#review')
        await pilot.pause()
        await pilot.click('#apply')
        await pilot.pause()
        assert app.manager.list_repos() == [dict(compartment='falcon', remote='git@example.com:team/alpha.git', initialized=False)]


@pytest.mark.asyncio
async def test_initialize_then_remove_keeps_files(tmp_path):
    app = RepoManagerApp(store_root=tmp_path, action='initialize')
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        app.query_one('#compartment', Input).value = 'alpha'
        await pilot.pause()
        await pilot.click('#review')
        await pilot.pause()
        await pilot.click('#apply')
        await pilot.pause()
        assert (app.manager.local_path('alpha') / '.git').is_dir()
        app.query_one('#operation', Select).value = 'remove'
        app.query_one('#repository', Select).value = 'alpha'
        await pilot.pause()
        await pilot.click('#review')
        await pilot.pause()
        await pilot.click('#apply')
        await pilot.pause()
        assert app.manager.list_repos() == []
        assert (app.manager.local_path('alpha') / '.git').is_dir()


@pytest.mark.asyncio
async def test_empty_remove_and_cancel_do_not_write(tmp_path):
    root = tmp_path / 'store'
    app = RepoManagerApp(store_root=root, action='remove')
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.click('#review')
        await pilot.pause()
        assert app.plan is None
        assert app.query_one('#apply', Button).disabled
        await pilot.click('#back')
    assert not root.exists()


@pytest.mark.asyncio
async def test_push_choice_is_reviewed_and_forwarded(tmp_path, monkeypatch):
    app = RepoManagerApp(store_root=tmp_path, action='initialize')
    pushed = []
    monkeypatch.setattr(app.manager, '_push_initial', pushed.append)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        app.query_one('#compartment', Input).value = 'alpha'
        app.query_one('#remote', Input).value = 'git@example.com:team/alpha.git'
        await pilot.pause()
        await pilot.click('#review')
        await pilot.pause()
        assert not app.plan.push
        checkbox = app.query_one('#push', Checkbox)
        checkbox.focus()
        await pilot.press('enter')
        await pilot.pause()
        assert checkbox.value
        assert app.plan is None
        await pilot.click('#review')
        await pilot.pause()
        assert app.plan.push
        await pilot.click('#apply')
        await pilot.pause()
        assert len(pushed) == 1 and pushed[0].push
