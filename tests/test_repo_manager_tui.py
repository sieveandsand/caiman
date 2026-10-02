from textual.widgets import Input, Select, Static
from caiman.repositories.tui import RepoManagerApp
import pytest


@pytest.mark.parametrize('action', ['initialize', 'sync', 'default', 'remove'])
async def test_selected_pod_is_carried_into_review(tmp_path, action):
    from caiman.repositories.service import RepoManager
    manager = RepoManager(tmp_path)
    manager.apply(manager.prepare('initialize', 'alpha', 'git@example.com:team/alpha.git'))
    app = RepoManagerApp(store_root=tmp_path, action=action, pod='alpha')
    async with app.run_test() as pilot:
        await pilot.pause()
        field = app.query_one('#pod', Input) if action == 'initialize' else app.query_one('#repository', Select)
        assert field.value == 'alpha' and field.disabled
        app.query_one('#review').press()
        await pilot.pause()
        assert app.plan.action == action and app.plan.pod == 'alpha'
        assert field.disabled
        assert not app.query('#operation')


async def test_create_review_invalidation_and_apply(tmp_path):
    root = tmp_path / 'store'; app = RepoManagerApp(store_root=root, action='create')
    async with app.run_test(size=(100, 38)) as pilot:
        await pilot.pause()
        app.query_one('#pod', Input).value = 'alpha'
        await pilot.pause()
        app.query_one('#review').press(); await pilot.pause()
        assert app.plan and not root.exists()
        app.query_one('#pod', Input).value = 'beta'; await pilot.pause()
        assert app.plan is None
        app.query_one('#review').press(); await pilot.pause()
        app.query_one('#apply').press(); await pilot.pause()
        assert (root / 'beta/pod.json').exists()
        assert not (root / 'beta/.git').exists()


async def test_connect_git_and_default_pod(tmp_path):
    app = RepoManagerApp(store_root=tmp_path, action='initialize')
    async with app.run_test(size=(100, 38)) as pilot:
        await pilot.pause()
        app.query_one('#pod', Input).value = 'alpha'
        await pilot.pause()
        app.query_one('#review').press(); await pilot.pause()
        app.query_one('#apply').press(); await pilot.pause()
        assert (tmp_path / 'alpha/.git').exists()
        assert not app.query('#operation')
    app = RepoManagerApp(store_root=tmp_path, action='default')
    async with app.run_test(size=(100, 38)) as pilot:
        await pilot.pause()
        app.query_one('#repository', Select).value = 'alpha'
        await pilot.pause()
        app.query_one('#review').press(); await pilot.pause()
        app.query_one('#apply').press(); await pilot.pause()
        assert app.manager.store.pods.default == 'alpha'
