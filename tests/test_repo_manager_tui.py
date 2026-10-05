from textual.widgets import Input, Select, Static
from caiman.repositories.tui import RepoManagerApp
import pytest


async def test_broken_neighbor_does_not_block_healthy_sync(tmp_path):
    from caiman.repositories.service import RepoManager
    manager = RepoManager(tmp_path)
    manager.apply(manager.prepare('initialize', 'healthy'))
    manager.store.pods.ensure('broken')
    (manager.local_path('broken') / '.git').mkdir()
    app = RepoManagerApp(store_root=tmp_path, action='sync', pod='healthy')
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one('#repository', Select).value == 'healthy'
        app.query_one('#review').press()
        await pilot.pause()
        assert app.plan and app.plan.pod == 'healthy'
        app.query_one('#apply').press()
        await pilot.pause()
        assert 'complete' in str(app.query_one('#status', Static).render())
    assert manager._git(manager.local_path('healthy'), 'rev-parse', 'HEAD')


async def test_public_default_has_no_change_control(tmp_path):
    from caiman.dashboard.onboarding import CategoryApp
    from caiman.repositories.service import RepoManager
    manager = RepoManager(tmp_path / 'store')
    app = CategoryApp('repos', store_root=manager.store.root)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert 'permanent default' in str(app.query_one('#pod-status', Static).render())
        assert not app.query('#repo-default')
        assert app.query_one('#repo-unregister').disabled
    assert manager.store.pods.default == 'public'


@pytest.mark.parametrize('action', ['initialize', 'sync', 'remove'])
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


@pytest.mark.parametrize('remote', ['', 'git@example.com:team/pod.git'])
async def test_create_pod_with_create_button(tmp_path, remote):
    root = tmp_path / 'store'; app = RepoManagerApp(store_root=root, action='create')
    async with app.run_test(size=(100, 38)) as pilot:
        await pilot.pause()
        assert app.query_one('#pod', Input).placeholder == 'pod name'
        assert app.query_one('#remote', Input).display
        assert not app.query('#review') and not app.query('#apply')
        app.query_one('#pod', Input).value = 'demo'
        app.query_one('#remote', Input).value = remote
        await pilot.pause()
        assert not root.exists()
        app.query_one('#create').press(); await pilot.pause()
        assert not app.is_running
    assert (root / 'demo/pod.json').exists()
    assert (root / 'demo/.git').exists() == bool(remote)
    if remote:
        assert app.manager._git(root / 'demo', 'config', '--get', 'remote.origin.url') == remote
        assert not app.manager._git(root / 'demo', 'show-ref', '--head', allow_missing=True)


@pytest.mark.parametrize('pod, remote', [('', ''), ('../invalid', ''), ('demo', 'invalid')])
async def test_create_validation_allows_correction(tmp_path, pod, remote):
    root = tmp_path / 'store'
    app = RepoManagerApp(store_root=root, action='create')
    async with app.run_test() as pilot:
        app.query_one('#pod', Input).value = pod
        app.query_one('#remote', Input).value = remote
        app.query_one('#create').press(); await pilot.pause()
        assert app.is_running and not root.exists()
        assert str(app.query_one('#status', Static).render())
        assert not app.query_one('#create').disabled
        app.query_one('#pod', Input).value = 'demo'
        app.query_one('#remote', Input).value = ''
        app.query_one('#create').press(); await pilot.pause()
    assert (root / 'demo/pod.json').exists()


@pytest.mark.parametrize('action', ['create', 'add'])
async def test_back_leaves_no_pod(tmp_path, action):
    root = tmp_path / 'store'
    app = RepoManagerApp(store_root=root, action=action)
    async with app.run_test() as pilot:
        app.query_one('#pod', Input).value = 'demo'
        app.query_one('#back').press(); await pilot.pause()
    assert not root.exists()


async def test_clone_directly_and_retry_missing_remote(tmp_path):
    from caiman.repositories.service import RepoManager

    source = RepoManager(tmp_path / 'source')
    source.apply(source.prepare('initialize', 'demo'))
    source.apply(source.prepare('sync', 'demo'))
    root = tmp_path / 'destination'
    app = RepoManagerApp(store_root=root, action='add')
    async with app.run_test() as pilot:
        assert app.query_one('#pod', Input).placeholder == 'pod name'
        assert app.query_one('#remote', Input).display
        assert not app.query('#review') and not app.query('#apply')
        app.query_one('#pod', Input).value = 'local-demo'
        app.query_one('#clone').press(); await pilot.pause()
        assert app.is_running and not root.exists()
        assert 'Clone needs a remote' in str(app.query_one('#status', Static).render())
        assert not app.query_one('#clone').disabled
        app.query_one('#remote', Input).value = str(source.local_path('demo'))
        app.query_one('#clone').press()
        # Git runs in a background thread; one UI pause need not finish a clone.
        import asyncio
        async with asyncio.timeout(10):
            while app.is_running:
                await pilot.pause()
                await asyncio.sleep(0.02)
        assert not app.is_running
    assert (root / 'local-demo/pod.json').exists()
    assert app.manager.local_path('demo') == root / 'local-demo'
    assert app.manager._git(root / 'local-demo', 'rev-parse', 'HEAD') == source._git(
        source.local_path('demo'), 'rev-parse', 'HEAD')


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
    assert app.manager.store.pods.default == 'public'
