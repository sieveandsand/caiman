"""Repository management is local, reviewed, and compartment-scoped."""

import json
from pathlib import Path
import subprocess

import pytest

from caiman.repositories.service import RepoManager


REMOTE = 'git@example.invalid:team/store-alpha.git'


@pytest.fixture(autouse=True)
def verified_remote(monkeypatch):
    # Transport validation is exercised against real Git remotes in its own module.
    monkeypatch.setattr(RepoManager, '_verify_remote', lambda *args: None)


def test_review_and_empty_catalog_write_nothing(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    assert manager.list_repos() == []
    plan = manager.prepare('add', 'alpha', REMOTE)
    assert 'alpha' in plan.preview and REMOTE in plan.preview
    assert not manager.store.root.exists()


@pytest.mark.parametrize('compartment', ['', '../alpha', 'alpha,beta', 'alpha beta', '.git'])
def test_invalid_compartment_writes_nothing(tmp_path, compartment):
    manager = RepoManager(tmp_path / 'store')
    with pytest.raises(ValueError):
        manager.prepare('add', compartment, REMOTE)
    assert not manager.store.root.exists()


@pytest.mark.parametrize('remote', ['', '--upload-pack=evil', 'ext::evil',
    'https://secret@example.invalid/repo', 'https://example.invalid/repo?token=secret',
    'ssh://git:secret@example.invalid/repo', 'git@example.invalid:repo\nother'])
def test_invalid_remote_writes_nothing(tmp_path, remote):
    manager = RepoManager(tmp_path / 'store')
    with pytest.raises(ValueError):
        manager.prepare('add', 'alpha', remote)
    assert not manager.store.root.exists()


def test_add_persists_without_running_git(tmp_path, monkeypatch):
    manager = RepoManager(tmp_path / 'store')
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: pytest.fail('Add must not run Git'))
    manager.apply(manager.prepare('add', 'alpha', REMOTE))
    records = RepoManager(manager.store.root).list_repos()
    assert records == [{'compartment': 'alpha', 'remote': REMOTE, 'initialized': False}]
    assert manager.path.stat().st_mode & 0o777 == 0o600
    assert not manager.local_path('alpha').exists()


def test_duplicate_and_stale_registration_preserve_state(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    first = manager.prepare('add', 'alpha', REMOTE)
    stale = manager.prepare('add', 'beta', 'https://example.invalid/team/beta.git')
    manager.apply(first)
    with pytest.raises(ValueError, match='already registered'):
        manager.prepare('add', 'alpha', REMOTE)
    with pytest.raises(ValueError, match='changed since review'):
        manager.apply(stale)
    assert len(manager.list_repos()) == 1


def test_initialize_separate_repository_without_committing_documents(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    manager.apply(manager.prepare('add', 'alpha', REMOTE))
    document = manager.store.root / 'alpha' / 'existing.md'
    document.parent.mkdir()
    document.write_text('Synthetic private content')
    manager.apply(manager.prepare('initialize', 'alpha'))
    local = manager.local_path('alpha')
    assert (local / '.git').is_dir()
    assert json.loads((local / 'store.json').read_text()) == {'schema': 'caiman.store.v1', 'compartment': 'alpha'}
    assert (local / '.git/HEAD').read_text().strip() == 'ref: refs/heads/caiman-store'
    assert 'Synthetic private content' not in ''.join(p.read_text() for p in local.glob('*.md'))
    assert subprocess.run(['git', '-C', str(local), 'rev-parse', '--verify', 'HEAD'], capture_output=True).returncode != 0
    assert subprocess.check_output(['git', '-C', str(local), 'remote', 'get-url', 'origin'], text=True).strip() == REMOTE
    assert document.read_text() == 'Synthetic private content'
    assert not (manager.store.root / '.git').exists()
    assert local.stat().st_mode & 0o777 == 0o700


def test_remove_keeps_local_repository_and_other_compartments(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    manager.apply(manager.prepare('initialize', 'alpha', REMOTE))
    manager.apply(manager.prepare('add', 'beta', 'https://example.invalid/team/beta.git'))
    local = manager.local_path('alpha')
    before = (local / '.git/config').read_bytes()
    manager.apply(manager.prepare('remove', 'alpha'))
    assert [r['compartment'] for r in manager.list_repos()] == ['beta']
    assert (local / '.git/config').read_bytes() == before
    manager.apply(manager.prepare('add', 'alpha', REMOTE))
    assert manager.list_repos()[0]['initialized'] is True


def test_initialize_public_locally_and_reinitialize_without_changes(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    manager.apply(manager.prepare('initialize', 'public'))
    local = manager.local_path('public')
    (local / 'keep.txt').write_text('preserve me')
    manager.apply(manager.prepare('initialize', 'public'))
    assert (local / 'keep.txt').read_text() == 'preserve me'
    assert manager.list_repos() == [{'compartment': 'public', 'remote': None, 'initialized': True}]


def test_existing_unmanaged_directory_is_not_overwritten(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    local = manager.local_path('alpha')
    local.mkdir(parents=True)
    (local / 'keep.txt').write_text('keep')
    with pytest.raises(ValueError):
        manager.prepare('initialize', 'alpha', REMOTE)
    assert (local / 'keep.txt').read_text() == 'keep'
    assert not (local / '.git').exists()


def test_symlink_registry_and_repository_rejected(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    manager.store.root.mkdir()
    outside = tmp_path / 'outside'
    outside.write_text('{}')
    manager.path.symlink_to(outside)
    with pytest.raises(ValueError):
        manager.list_repos()
    manager.path.unlink()
    local = manager.local_path('alpha')
    local.parent.mkdir()
    local.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        manager.prepare('initialize', 'alpha')


def test_failed_git_initialization_leaves_no_registration_or_target(tmp_path, monkeypatch):
    manager = RepoManager(tmp_path / 'store')
    plan = manager.prepare('initialize', 'alpha')
    def fail(*args, **kwargs):
        raise FileNotFoundError('git unavailable')
    monkeypatch.setattr(subprocess, 'run', fail)
    with pytest.raises(ValueError, match='Git'):
        manager.apply(plan)
    assert manager.list_repos() == []
    assert not manager.local_path('alpha').exists()


def test_git_environment_cannot_redirect_initialization(tmp_path, monkeypatch):
    outside = tmp_path / 'unrelated.git'
    monkeypatch.setenv('GIT_DIR', str(outside))
    monkeypatch.setenv('GIT_WORK_TREE', str(tmp_path))
    manager = RepoManager(tmp_path / 'store')
    manager.apply(manager.prepare('initialize', 'alpha'))
    assert not outside.exists()
    assert (manager.local_path('alpha') / '.git').is_dir()
