"""Exercise remote admission and initial publication using real isolated Git repos."""

import json
import subprocess

import pytest

from caiman.repositories.service import RepoManager


REMOTE = 'ssh://git@example.invalid/team/alpha.git'


@pytest.fixture
def transport(tmp_path, monkeypatch):
    remote = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', '--quiet', str(remote)], check=True)
    original = subprocess.run

    def run(args, **kwargs):
        if 'env' in kwargs:
            if any(command in args for command in ('fetch', 'push', 'ls-remote')):
                args = [str(remote) if arg == REMOTE else arg for arg in args]
            kwargs['env']['GIT_ALLOW_PROTOCOL'] = 'file'
        return original(args, **kwargs)

    monkeypatch.setattr(subprocess, 'run', run)
    return RepoManager(tmp_path / 'store'), remote


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def test_initialize_push_add_and_retry(transport, tmp_path):
    manager, remote = transport
    manager.apply(manager.prepare('initialize', 'alpha', REMOTE))
    manager.apply(manager.prepare('sync', 'alpha'))
    assert json.loads(git(remote, 'show', 'caiman-store:pod.json'))['id'] == 'alpha'
    head = git(remote, 'rev-parse', 'caiman-store')
    manager.apply(manager.prepare('sync', 'alpha'))
    assert git(remote, 'rev-parse', 'caiman-store') == head
    teammate = RepoManager(tmp_path / 'teammate')
    teammate.apply(teammate.prepare('add', 'alpha', REMOTE))
    assert teammate.local_path('alpha').exists()
    assert next(r for r in teammate.list_repos() if r['pod'] == 'alpha')['remote'] == REMOTE


def test_empty_remote_cannot_be_added(transport):
    manager, _ = transport
    with pytest.raises(ValueError, match='Git repository operation failed'):
        manager.apply(manager.prepare('add', 'alpha', REMOTE))
    assert [r['pod'] for r in manager.list_repos()] == ['public']


@pytest.mark.parametrize('change', ['header', 'extra', 'symlink', 'attributes'])
def test_invalid_remote_is_not_registered(transport, tmp_path, change):
    manager, remote = transport
    manager.apply(manager.prepare('initialize', 'alpha', REMOTE))
    manager.apply(manager.prepare('sync', 'alpha'))
    work = tmp_path / 'editor'
    subprocess.run(['git', 'clone', '--quiet', '--branch', 'caiman-store', str(remote), str(work)], check=True)
    if change == 'header':
        (work / 'pod.json').write_text('{"schema":"other"}')
    elif change == 'extra':
        (work / 'script.sh').write_text('echo unexpected')
    elif change == 'symlink':
        (work / 'pod.json').unlink()
        (work / 'pod.json').symlink_to('/tmp/not-a-header')
    else:
        (work / '.gitattributes').write_text('* filter=unexpected')
    git(work, 'add', '.')
    git(work, '-c', 'user.name=Test', '-c', 'user.email=test@localhost', '-c', 'commit.gpgSign=false', 'commit', '-qm', 'Invalid format')
    git(work, 'push', '-q', 'origin', 'caiman-store')
    reader = RepoManager(tmp_path / 'reader')
    with pytest.raises(ValueError):
        reader.apply(reader.prepare('add', 'alpha', REMOTE))
    assert [r['pod'] for r in reader.list_repos()] == ['public']
    before = git(remote, 'rev-parse', 'caiman-store')
    with pytest.raises(ValueError):
        manager.apply(manager.prepare('sync', 'alpha'))
    assert git(remote, 'rev-parse', 'caiman-store') == before


def test_local_initialization_can_later_push(transport):
    manager, remote = transport
    manager.apply(manager.prepare('initialize', 'alpha'))
    manager.apply(manager.prepare('initialize', 'alpha', REMOTE))
    manager.apply(manager.prepare('sync', 'alpha'))
    assert next(r for r in manager.list_repos() if r['pod'] == 'alpha')['remote'] == REMOTE
    assert git(remote, 'rev-parse', 'caiman-store')


def test_https_imports_credentials_without_other_git_settings(tmp_path, monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs['env']))
        if '--get-urlmatch' in args:
            return subprocess.CompletedProcess(args, 0,
                'credential.helper osxkeychain\ncredential.username engineer\nurl.bad.insteadof https://\n', '')
        return subprocess.CompletedProcess(args, 0, '', '')

    monkeypatch.setattr(subprocess, 'run', run)
    RepoManager(tmp_path)._git(tmp_path, 'ls-remote', '--refs', 'https://example.invalid/team/alpha.git')
    args, env = calls[-1]
    assert 'credential.helper=osxkeychain' in args
    assert 'credential.username=engineer' in args
    assert not any('insteadof' in value for value in args)
    assert env['GIT_CONFIG_GLOBAL'] == '/dev/null'
    assert env['GIT_ALLOW_PROTOCOL'] == 'ssh:https:file'
