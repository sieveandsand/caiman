import json
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

from caiman.configurations.editor import VimDraft


def test_private_copy_never_edits_input_and_is_cleaned_up():
    original = {'board': 'synthetic', 'version': 'v1'}
    with VimDraft(original) as draft:
        path = draft.path
        directory = path.parent
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
        assert draft.read() == original
        assert not draft.changed
        path.write_text('{"board":"synthetic","version":"v2"}')
        assert draft.changed
        assert original['version'] == 'v1'
    assert not directory.exists()


def test_vim_invocation_disables_configuration_and_persistent_files(monkeypatch):
    calls = []
    monkeypatch.setattr(shutil, 'which', lambda name: '/usr/bin/vim')
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(subprocess, 'run', run)
    with VimDraft({'board': 'synthetic'}) as draft:
        assert draft.edit()
        args, kwargs = calls[0]
        assert args[0] == '/usr/bin/vim'
        assert args[-1] == str(draft.path)
        assert args[args.index('-u') + 1] == 'NONE'
        assert args[args.index('-U') + 1] == 'NONE'
        assert args[args.index('-i') + 1] == 'NONE'
        assert '-n' in args
        assert '--noplugin' in args
        assert 'nomodeline' in args[args.index('--cmd') + 1]
        assert 'noundofile' in args[args.index('--cmd') + 1]
        assert not kwargs.get('shell', False)


def test_cancel_does_not_return_an_edited_configuration(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda name: '/usr/bin/vim')
    monkeypatch.setattr(subprocess, 'run', lambda args, **kwargs: subprocess.CompletedProcess(args, 1))
    with VimDraft({'board': 'synthetic'}) as draft:
        assert not draft.edit()


def test_invalid_saved_json_remains_available_for_retry(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda name: '/usr/bin/vim')
    edits = ['{"board":', '{"board":"repaired"}']
    def run(args, **kwargs):
        Path(args[-1]).write_text(edits.pop(0))
        return subprocess.CompletedProcess(args, 0)
    monkeypatch.setattr(subprocess, 'run', run)
    with VimDraft({'board': 'synthetic'}) as draft:
        path = draft.path
        assert draft.edit()
        with pytest.raises(ValueError):
            draft.read()
        assert draft.text == '{"board":'
        assert draft.path == path
        assert draft.edit()
        assert draft.read() == {'board': 'repaired'}


def test_missing_vim_has_actionable_error(monkeypatch):
    monkeypatch.setattr(shutil, 'which', lambda name: None)
    with VimDraft({'board': 'synthetic'}) as draft:
        with pytest.raises(ValueError, match='vim.*PATH'):
            draft.edit()


@pytest.mark.skipif(shutil.which('vim') is None, reason='vim not installed')
def test_real_vim_headless_edit_preserves_private_draft(monkeypatch):
    real_run = subprocess.run
    def headless(args, **kwargs):
        args = [args[0], '-es', *args[1:-2], '-c', '%s/initial/revised/g', '-c', 'wq', *args[-2:]]
        return real_run(args, **kwargs)
    monkeypatch.setattr(subprocess, 'run', headless)
    with VimDraft({'version': 'initial'}) as draft:
        assert draft.edit()
        assert draft.read() == {'version': 'revised'}
        assert stat.S_IMODE(draft.path.stat().st_mode) == 0o600
        assert list(draft.path.parent.iterdir()) == [draft.path]
