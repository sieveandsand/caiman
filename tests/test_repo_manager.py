"""Pod management stays local until an explicit sync or clone."""
import subprocess
import pytest
from caiman.repositories.service import RepoManager


def test_pod_status_tracks_local_changes_and_detached_head(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    assert manager.list_status()[0]['status'] == 'Not created yet'
    manager.apply(manager.prepare('initialize', 'alpha'))
    path = manager.local_path('alpha')
    status = lambda: next(r for r in manager.list_status() if r['pod'] == 'alpha')
    assert status()['status'] == 'caiman-store · 2 untracked'
    manager.apply(manager.prepare('sync', 'alpha'))
    assert status()['status'] == 'caiman-store · Clean'
    (path / '.gitattributes').write_text('changed\n')
    (path / 'new file').write_text('new\n')
    assert status()['status'] == 'caiman-store · 1 modified · 1 untracked'
    manager._git(path, 'add', '.gitattributes')
    assert status()['status'] == 'caiman-store · 1 staged · 1 untracked'
    manager._git(path, 'mv', 'pod.json', 'renamed.json')
    # Restore the pod header so discovery still recognizes it; the rename's
    # extra filename must not be counted as another changed file.
    (path / 'pod.json').write_text((path / 'renamed.json').read_text())
    assert status()['status'] == 'caiman-store · 2 staged · 2 untracked'
    manager._git(path, 'checkout', '--detach')
    assert status()['status'].startswith('Detached HEAD ')


def test_one_broken_git_repository_does_not_hide_other_pods(tmp_path):
    manager = RepoManager(tmp_path)
    manager.store.pods.ensure('broken')
    (manager.local_path('broken') / '.git').mkdir()
    manager.store.pods.ensure('healthy')
    records = {r['pod']: r for r in manager.list_status()}
    assert records['broken']['status'].startswith('Git status unavailable:')
    assert records['healthy']['status'] == 'Local folder'


def test_review_and_empty_catalog_write_nothing(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    assert manager.list_repos()[0]['pod'] == 'public'
    plan = manager.prepare('create', 'alpha')
    assert 'Create local pod' in plan.preview
    assert not manager.store.root.exists()


@pytest.mark.parametrize('pod', ['', '../alpha', 'alpha,beta', 'alpha beta', '.git'])
def test_invalid_pod_writes_nothing(tmp_path, pod):
    manager = RepoManager(tmp_path / 'store')
    with pytest.raises(ValueError):
        manager.prepare('create', pod)
    assert not manager.store.root.exists()


@pytest.mark.parametrize('remote', ['', '--upload-pack=evil', 'ext::evil',
    'https://secret@example.invalid/repo', 'https://example.invalid/repo?token=secret',
    'ssh://git:secret@example.invalid/repo', 'git@example.invalid:repo\nother'])
def test_invalid_remote_writes_nothing(tmp_path, remote):
    manager = RepoManager(tmp_path / 'store')
    with pytest.raises(ValueError):
        manager.prepare('add', 'alpha', remote)
    assert not manager.store.root.exists()


def test_stale_review_preserves_files(tmp_path):
    manager = RepoManager(tmp_path)
    manager.apply(manager.prepare('create', 'alpha'))
    plan = manager.prepare('initialize', 'alpha')
    (tmp_path / 'alpha' / 'note').write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        manager.apply(plan)
    assert not (tmp_path / 'alpha/.git').exists()


def test_initialize_uses_data_folder_without_committing(tmp_path):
    from test_pods import add_document
    manager = RepoManager(tmp_path / 'store')
    add_document(manager.store.root, tmp_path, 'alpha')
    manager.apply(manager.prepare('initialize', 'alpha'))
    assert manager.local_path('alpha') == manager.store.root / 'alpha'
    assert (manager.local_path('alpha') / '.git').is_dir()
    assert not manager._git(manager.local_path('alpha'), 'show-ref', '--head', allow_missing=True)
    assert list((manager.local_path('alpha') / 'refs/documents').rglob('A'))


def test_disconnect_keeps_data_and_history(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    manager.apply(manager.prepare('initialize', 'alpha', str(tmp_path / 'remote.git')))
    manager.apply(manager.prepare('remove', 'alpha'))
    assert (manager.local_path('alpha') / '.git').is_dir()
    assert next(r for r in manager.list_repos() if r['pod'] == 'alpha')['remote'] is None


def test_symlink_pod_rejected(tmp_path):
    (tmp_path / 'outside').mkdir()
    root = tmp_path / 'store'; root.mkdir()
    (root / 'alpha').symlink_to(tmp_path / 'outside')
    with pytest.raises(ValueError):
        RepoManager(root).prepare('initialize', 'alpha')


def test_git_environment_cannot_redirect_initialization(tmp_path, monkeypatch):
    manager = RepoManager(tmp_path / 'store')
    monkeypatch.setenv('GIT_DIR', str(tmp_path / 'outside'))
    monkeypatch.setenv('GIT_WORK_TREE', str(tmp_path / 'elsewhere'))
    manager.apply(manager.prepare('initialize', 'alpha'))
    assert (manager.local_path('alpha') / '.git').exists()
    assert not (tmp_path / 'outside').exists()


def test_unexpected_file_is_not_published(tmp_path):
    from test_pods import bare, apply
    manager = RepoManager(tmp_path / 'store')
    remote = bare(tmp_path)
    apply(manager, 'initialize', 'alpha', remote)
    (manager.local_path('alpha') / 'unrelated.txt').write_text('Not pod data')
    with pytest.raises(ValueError, match='Unexpected file'):
        apply(manager, 'sync', 'alpha')
    result = subprocess.run(['git', '-C', remote, 'show-ref'], capture_output=True)
    assert result.returncode == 1
