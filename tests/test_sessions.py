"""Session registration from the start hook, and host-side context loading."""

from datetime import datetime, timedelta, timezone
import fcntl
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

from caiman.cli.commands import main
from caiman.configurations.service import ConfigurationService
from caiman.documents.ingest import prepare_document
from caiman.hooks.service import session_hook
from caiman.sessions.service import (load_context, prune_sessions, read_state, recover,
                                     register_session, search_hint)
from caiman.storage.store import Store


SECRET = 'REQ-SECRET-0142 shall never appear in a brief'
MANUAL = b'# Synthetic manual\r\n\r\n## Serial port\r\n\r\n| Reg | Bit |\r\n|---|---|\r\n'


@pytest.fixture
def library(tmp_path):
    root = tmp_path / 'store'
    store = Store(root)
    manual = tmp_path / 'manual.md'
    manual.write_bytes(MANUAL)
    board_doc = store.register(prepare_document(manual, {
        'issuer': 'example', 'part': 'mcu', 'doc_type': 'manual', 'version': 'Rev 1', 'pod': 'public'}))
    spec = tmp_path / 'spec.pdf'
    spec.write_bytes(b'%PDF-1.7\n' + SECRET.encode())
    project_doc = store.register(prepare_document(spec, {
        'issuer': 'customer', 'program': 'kestrel', 'doc_type': 'spec', 'version': 'R1', 'pod': 'alpha'}))
    service = ConfigurationService(store)
    service.register(service.prepare('board', {
        'board': 'demo-board', 'version': 'Rev A', 'links': [],
        'parts': [{'role': 'application-mcu', 'vendor': 'example', 'part': 'mcu',
                   'documents': [{'digest': board_doc.manifest_digest}]}]}))
    service.register(service.prepare('project', {
        'project': 'kestrel', 'version': 'dvt-1', 'customer': 'Synthetic customer', 'pod': 'alpha',
        'boards': [{'name': 'demo-board', 'version': 'Rev A'}], 'spec_set': 'Release 1',
        'documents': [{'digest': project_doc.manifest_digest, 'pod': 'alpha'}], 'features': []}))
    worktree = tmp_path / 'firmware'
    worktree.mkdir()
    return root, worktree, board_doc, project_doc


def start(root, worktree, session_id='s1', env=None, **event):
    event = {'session_id': session_id, 'cwd': str(worktree), 'source': 'startup', **event}
    output = session_hook(root, 'claude', event, env or {})
    return json.loads(output)['hookSpecificOutput']['additionalContext'] if output else None


def folder(worktree, session_id='s1'):
    return worktree / '.caiman' / 'sessions' / f'claude-{session_id}'


def tree(path):
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob('*')) if p.is_file()}


def test_first_start_creates_the_workspace_and_asks_for_a_choice(library, tmp_path):
    root, worktree, *_ = library
    env_file = tmp_path / 'env'
    context = start(root, worktree, env={'CLAUDE_ENV_FILE': str(env_file)}, transcript_path='/t.jsonl')
    assert (worktree / '.caiman' / '.gitignore').read_text() == '*\n'
    assert json.loads((worktree / '.caiman' / 'workspace.json').read_text())['schema'] == 'caiman.workspace.v1'
    session = json.loads((folder(worktree) / 'session.json').read_text())
    assert (session['harness'], session['session_id'], session['transcript_path']) == ('claude', 's1', '/t.jsonl')
    assert 'No board or project is loaded' in context and 'session list' in context
    assert 'Never choose a version yourself' in context
    # Asking must not depend on the first prompt being about hardware.
    assert 'At the start of your first reply, whatever the user asked' in context
    assert env_file.read_text() == f'export CAIMAN_SESSION=claude-s1\nexport CAIMAN_WORKSPACE={worktree}\n'


def test_later_starts_reuse_the_existing_workspace_from_a_subdirectory(library):
    root, worktree, *_ = library
    start(root, worktree)
    marker = (worktree / '.caiman' / 'workspace.json').read_bytes()
    nested = worktree / 'src' / 'drivers'
    nested.mkdir(parents=True)
    start(root, nested, session_id='s2')
    assert (worktree / '.caiman' / 'workspace.json').read_bytes() == marker
    assert folder(worktree, 's2').is_dir() and not (nested / '.caiman').exists()


@pytest.mark.parametrize('session_id', ['../escape', '', None, 'a/b', '.hidden'])
def test_unsafe_session_ids_write_nothing_and_never_fail_the_session(library, monkeypatch, capsys, session_id):
    root, worktree, *_ = library
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps({'session_id': session_id, 'cwd': str(worktree)})))
    assert main(['--store', str(root), 'session', 'hook']) == 0
    assert capsys.readouterr().out == ''
    assert not (worktree / '.caiman' / 'sessions').exists() or not any((worktree / '.caiman' / 'sessions').iterdir())
    assert not (worktree.parent / 'escape').exists()


def test_missing_store_or_malformed_input_is_silent(library, monkeypatch, capsys):
    root, worktree, *_ = library
    monkeypatch.setattr('sys.stdin', io.StringIO(json.dumps({'session_id': 's1', 'cwd': str(worktree)})))
    assert main(['--store', str(root.parent / 'missing'), 'session', 'hook']) == 0
    monkeypatch.setattr('sys.stdin', io.StringIO('not json'))
    assert main(['--store', str(root), 'session', 'hook']) == 0
    assert capsys.readouterr().out == ''
    assert not (worktree / '.caiman').exists()


def test_load_project_without_boards_installs_its_documents(library):
    root, worktree, _, project_doc = library
    service = ConfigurationService(Store(root))
    service.register(service.prepare('project', {
        'project': 'kestrel', 'version': 'concept', 'customer': 'Synthetic customer', 'pod': 'alpha',
        'boards': [], 'documents': [{'digest': project_doc.manifest_digest, 'pod': 'alpha'}]}))
    start(root, worktree)
    state = load_context(root, folder(worktree), 'project', 'kestrel', 'concept')
    assert state['documents'] == 1
    files = tree(folder(worktree) / 'context')
    assert 'documents/customer/kestrel/spec@R1/spec.pdf' in files
    assert '## Boards\n\n- None pinned.\n' in files['project.md'].decode()


def test_load_project_installs_the_complete_read_only_set_with_a_metadata_only_brief(library):
    root, worktree, *_ = library
    start(root, worktree)
    state = load_context(root, folder(worktree), 'project', 'kestrel', 'dvt-1')
    assert (state['revision'], state['documents'], state['pod']) == (1, 2, 'alpha')
    context = folder(worktree) / 'context'
    files = tree(context)
    assert files['documents/example/mcu/manual@Rev%201/manual.md'] == MANUAL
    assert files['documents/customer/kestrel/spec@R1/spec.pdf'].endswith(SECRET.encode())
    assert set(files) == {'.ignore', 'project.md', 'project.json', 'documents/_index.md',
                          'documents/example/mcu/manual@Rev%201/manual.md',
                          'documents/customer/kestrel/spec@R1/spec.pdf'}
    assert files['.ignore'] == b'!*\n'
    for path in context.rglob('*'):
        assert not path.is_symlink()
        if path.is_file():
            assert stat.S_IMODE(path.stat().st_mode) == 0o444
    # Existence is structure, detail is content; customer identity stays in the manifest (I-6).
    for name in ('project.md', 'project.json', 'documents/_index.md'):
        assert SECRET not in files[name].decode() and 'Synthetic customer' not in files[name].decode()
    brief = files['project.md'].decode()
    assert 'kestrel @ dvt-1' in brief and 'application-mcu: example/mcu' in brief
    # Searches name this session's folder; the repository root skips `.caiman/`.
    assert f'rg -n PATTERN {context / "documents"}' in brief
    assert 'Synthetic customer' not in json.dumps(read_state(folder(worktree)))
    resumed = start(root, worktree, source='resume')
    assert 'project kestrel @ dvt-1 loaded (revision 1)' in resumed
    assert str(context / 'project.md') in resumed and SECRET not in resumed
    assert f'rg -n PATTERN {context / "documents"}' in resumed


def test_bare_name_lists_versions_and_writes_nothing(library, monkeypatch, capsys):
    root, worktree, *_ = library
    start(root, worktree)
    before = tree(worktree)
    monkeypatch.chdir(worktree)
    monkeypatch.setenv('CAIMAN_SESSION', 'claude-s1')
    assert main(['session', 'load', 'project', 'kestrel', '--store', str(root)]) == 1
    output = capsys.readouterr()
    assert [c['version'] for c in json.loads(output.out)] == ['dvt-1']
    assert 'choose one version' in output.err
    assert tree(worktree) == before


def test_cli_load_and_status_find_the_session_from_the_environment(library, monkeypatch, capsys):
    root, worktree, *_ = library
    start(root, worktree)
    nested = worktree / 'src'
    nested.mkdir()
    monkeypatch.chdir(nested)
    monkeypatch.setenv('CAIMAN_SESSION', 'claude-s1')
    monkeypatch.delenv('CAIMAN_WORKSPACE', raising=False)
    assert main(['session', 'load', 'board', 'demo-board', '--version', 'Rev A', '--store', str(root)]) == 0
    assert 'Loaded board demo-board @ Rev A into claude-s1 (revision 1, 1 document)' in capsys.readouterr().out
    assert main(['session', 'status', '--store', str(root)]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status['loaded']['name'] == 'demo-board'
    assert status['brief'] == str(folder(worktree) / 'context' / 'project.md')
    assert main(['session', 'list', 'kestrel', '--store', str(root)]) == 0
    assert [(c['kind'], c['version']) for c in json.loads(capsys.readouterr().out)] == [('project', 'dvt-1')]


def test_switching_one_session_leaves_another_unchanged(library):
    root, worktree, *_ = library
    start(root, worktree, 's1')
    start(root, worktree, 's2')
    first = load_context(root, folder(worktree, 's1'), 'board', 'demo-board', 'Rev A')
    second = load_context(root, folder(worktree, 's2'), 'board', 'demo-board', 'Rev A')
    # Same documents, same document-set identity, regardless of session (STORAGE §6).
    assert first['document_set'] == second['document_set']
    before = tree(folder(worktree, 's2'))
    switched = load_context(root, folder(worktree, 's1'), 'project', 'kestrel', 'dvt-1')
    assert switched['revision'] == 2 and switched['document_set'] != first['document_set']
    assert tree(folder(worktree, 's2')) == before
    assert not list(folder(worktree, 's1').glob('.staging-*')) and not list(folder(worktree, 's1').glob('.previous-*'))


def test_search_hint_quotes_a_folder_with_spaces(tmp_path):
    documents = tmp_path / 'my firmware' / '.caiman' / 'sessions' / 'claude-s1' / 'context' / 'documents'
    assert f"rg -n PATTERN '{documents}'" in search_hint(documents)


@pytest.mark.skipif(not (shutil.which('rg') and shutil.which('git')), reason='needs rg and git')
def test_ripgrep_finds_only_the_named_sessions_documents_in_a_git_worktree(library):
    root, worktree, *_ = library
    subprocess.run(['git', 'init', '-q', str(worktree)], check=True)
    start(root, worktree, 's1')
    start(root, worktree, 's2')
    load_context(root, folder(worktree, 's1'), 'board', 'demo-board', 'Rev A')
    load_context(root, folder(worktree, 's2'), 'project', 'kestrel', 'dvt-1')

    def rg(*args):
        result = subprocess.run(['rg', '-l', *args], cwd=worktree, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True)
        return sorted(Path(line).resolve() for line in result.stdout.splitlines())

    # A search from the worktree root reaches no session, even with --hidden.
    assert rg('Serial port') == rg('--hidden', 'Serial port') == []
    # Naming a session's folder searches that session and no other.
    documents = folder(worktree, 's1') / 'context' / 'documents'
    assert rg('Serial port', str(documents)) == [(documents / 'example/mcu/manual@Rev%201/manual.md').resolve()]
    assert rg('REQ-SECRET', str(documents)) == []


def age(session, days, *, loaded_days=None):
    """Backdate a session's last start and, optionally, its last load."""
    stamp = lambda d: (datetime.now(timezone.utc) - timedelta(days=d)).isoformat(timespec='seconds')
    path = session / 'session.json'
    path.write_text(json.dumps(dict(json.loads(path.read_text()), last_start=stamp(days))))
    if loaded_days is not None:
        path = session / 'state.json'
        path.write_text(json.dumps(dict(json.loads(path.read_text()), installed_at=stamp(loaded_days))))


def test_start_prunes_other_sessions_idle_past_the_window(library):
    root, worktree, *_ = library
    for name in ('idle', 'loaded', 'recent', 'self'):
        start(root, worktree, name)
    load_context(root, folder(worktree, 'idle'), 'board', 'demo-board', 'Rev A')
    load_context(root, folder(worktree, 'loaded'), 'board', 'demo-board', 'Rev A')
    age(folder(worktree, 'idle'), 15, loaded_days=15)
    age(folder(worktree, 'loaded'), 15, loaded_days=2)  # a recent load counts as activity
    age(folder(worktree, 'recent'), 13)
    age(folder(worktree, 'self'), 30)
    stray = worktree / '.caiman' / 'sessions' / 'notes'
    stray.mkdir()
    os.utime(stray, (0, 0))
    context = start(root, worktree, 'self', source='resume')
    assert 'No board or project is loaded' in context
    remaining = sorted(p.name for p in (worktree / '.caiman' / 'sessions').iterdir())
    # Never the starting session, and never a folder Caiman did not name.
    assert remaining == ['claude-loaded', 'claude-recent', 'claude-self', 'notes']


def test_prune_skips_a_session_mid_install_or_with_unreadable_times(library):
    root, worktree, *_ = library
    for name in ('busy', 'corrupt', 'self'):
        start(root, worktree, name)
    age(folder(worktree, 'busy'), 30)
    (folder(worktree, 'corrupt') / 'session.json').write_text('{"last_start": "yesterday-ish"')
    fd = os.open(folder(worktree, 'busy') / '.lock', os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert prune_sessions(worktree, 'claude-self') == []
    finally:
        os.close(fd)
    assert folder(worktree, 'busy').is_dir() and folder(worktree, 'corrupt').is_dir()
    assert prune_sessions(worktree, 'claude-self') == ['claude-busy']


def test_a_failed_prune_never_fails_the_start(library, monkeypatch):
    root, worktree, *_ = library
    def broken(*args, **kwargs):
        raise OSError('disk on fire')
    monkeypatch.setattr('caiman.sessions.service.prune_sessions', broken)
    assert 'No board or project is loaded' in start(root, worktree)


def test_unregistered_session_or_unknown_version_writes_nothing(library):
    root, worktree, *_ = library
    start(root, worktree)
    with pytest.raises(ValueError, match='not registered'):
        load_context(root, folder(worktree, 'other'), 'board', 'demo-board', 'Rev A')
    with pytest.raises(ValueError, match="available: Rev A"):
        load_context(root, folder(worktree), 'board', 'demo-board', 'Rev B')
    assert sorted(p.name for p in folder(worktree).iterdir()) == ['.lock', 'session.json']


def test_corrupt_blob_fails_and_keeps_the_previous_context(library):
    root, worktree, _, project_doc = library
    start(root, worktree)
    load_context(root, folder(worktree), 'board', 'demo-board', 'Rev A')
    before = tree(folder(worktree))
    digest = project_doc.blob_digest[7:]
    blob = root / 'alpha' / 'blobs' / 'sha256' / digest[:2] / digest
    blob.chmod(0o644)
    blob.write_bytes(b'tampered')
    with pytest.raises(ValueError):
        load_context(root, folder(worktree), 'project', 'kestrel', 'dvt-1')
    assert tree(folder(worktree)) == before
    assert read_state(folder(worktree))['name'] == 'demo-board'


def test_interrupted_install_is_rolled_back_or_finished(library):
    root, worktree, *_ = library
    start(root, worktree)
    session = folder(worktree)
    state = load_context(root, session, 'board', 'demo-board', 'Rev A')
    installed = tree(session / 'context')
    # Crash after moving the old generation aside, before the new one landed.
    (session / '.staging-x').mkdir()
    os.rename(session / 'context', session / '.previous-2')
    (session / 'install.json').write_text(json.dumps(
        {'staging': '.staging-x', 'previous': '.previous-2', 'state': dict(state, revision=2)}))
    recover(session)
    assert tree(session / 'context') == installed and read_state(session)['revision'] == 1
    # Crash after the new generation landed, before state was recorded.
    os.rename(session / 'context', session / '.previous-2')
    (session / 'context').mkdir()
    (session / 'install.json').write_text(json.dumps(
        {'staging': '.staging-x', 'previous': '.previous-2', 'state': dict(state, revision=2)}))
    recover(session)
    assert read_state(session)['revision'] == 2
    assert sorted(p.name for p in session.iterdir()) == ['.lock', 'context', 'session.json', 'state.json']


def test_register_session_rejects_a_symlinked_caiman_folder(tmp_path):
    target = tmp_path / 'elsewhere'
    target.mkdir()
    worktree = tmp_path / 'firmware'
    worktree.mkdir()
    (worktree / '.caiman').symlink_to(target)
    with pytest.raises(ValueError, match='plain directory'):
        register_session(worktree, 'claude', 's1')
    assert not any(target.iterdir())
