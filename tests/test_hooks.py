import io
import json
import os
import subprocess

import pytest
from textual.widgets import Button, Input, Static

from caiman.cli.commands import main
from caiman.hooks.service import install_hook, prepare_hook, settings_path
from caiman.hooks.tui import HooksApp


@pytest.mark.parametrize('harness', ['claude', 'codex'])
def test_install_preserves_settings_and_is_idempotent(tmp_path, harness):
    path = settings_path(harness, tmp_path)
    path.parent.mkdir()
    existing = {'permissions': {'allow': ['Read']}, 'hooks': {'SessionStart': [
        {'matcher': 'startup', 'hooks': [{'type': 'command', 'command': 'echo existing'}]}],
        'Stop': [{'hooks': [{'type': 'command', 'command': 'echo done'}]}]}}
    path.write_text(json.dumps(existing))
    plan = prepare_hook(harness, tmp_path, tmp_path / 'store')
    assert json.loads(path.read_text()) == existing  # Preview never writes.
    assert '+ ' in plan.preview
    assert install_hook(plan)
    data = json.loads(path.read_text())
    assert data['permissions'] == existing['permissions']
    assert data['hooks']['Stop'] == existing['hooks']['Stop']
    assert data['hooks']['SessionStart'][0] == existing['hooks']['SessionStart'][0]
    assert len(data['hooks']['SessionStart']) == 2
    assert not install_hook(prepare_hook(harness, tmp_path, tmp_path / 'store'))


@pytest.mark.parametrize('contents', ['{', '[]', '{"hooks": []}', '{"hooks":{"SessionStart":{}}}',
                                      '{"hooks":{},"hooks":{}}'])
def test_invalid_settings_untouched(tmp_path, contents):
    path = settings_path('claude', tmp_path)
    path.parent.mkdir()
    path.write_text(contents)
    with pytest.raises(ValueError):
        prepare_hook('claude', tmp_path, tmp_path)
    assert path.read_text() == contents


def test_stale_preview_and_symlink_rejected(tmp_path):
    plan = prepare_hook('codex', tmp_path, tmp_path)
    plan.path.parent.mkdir()
    plan.path.write_text('{"changed":true}')
    with pytest.raises(ValueError, match='changed since review'):
        install_hook(plan)
    assert plan.path.read_text() == '{"changed":true}'
    plan.path.unlink()
    target = tmp_path / 'target'
    target.write_text('{}')
    plan.path.symlink_to(target)
    with pytest.raises(ValueError, match='Symlink'):
        prepare_hook('codex', tmp_path, tmp_path)
    assert target.read_text() == '{}'


def test_upgrades_an_earlier_caiman_handler_in_place(tmp_path):
    path = settings_path('claude', tmp_path)
    path.parent.mkdir()
    old = '/old/python -m caiman --store /old/store session start 2>/dev/null || true'
    path.write_text(json.dumps({'hooks': {'SessionStart': [
        {'hooks': [{'type': 'command', 'command': 'echo keep'}, {'type': 'command', 'command': old}]}]}}))
    assert install_hook(prepare_hook('claude', tmp_path, tmp_path / 'store'))
    [group] = json.loads(path.read_text())['hooks']['SessionStart']
    assert group['hooks'][0]['command'] == 'echo keep'
    assert group['hooks'][1]['command'].endswith('session hook --harness claude 2>/dev/null || true')
    assert len(group['hooks']) == 2


def test_claude_hook_goes_to_uncommitted_local_settings(tmp_path):
    assert settings_path('claude', tmp_path) == tmp_path / '.claude' / 'settings.local.json'


def test_session_callback_no_private_contents_and_missing_store(tmp_path, monkeypatch, capsys):
    (tmp_path / 'private').write_text('PRIVATE CONTENT')
    worktree = tmp_path / 'firmware'
    worktree.mkdir()
    event = json.dumps({'session_id': 's1', 'cwd': str(worktree), 'source': 'startup'})
    monkeypatch.setattr('sys.stdin', io.StringIO(event))
    assert main(['--store', str(tmp_path), 'session', 'hook']) == 0
    output = capsys.readouterr().out
    assert 'PRIVATE CONTENT' not in output
    assert json.loads(output)['hookSpecificOutput']['hookEventName'] == 'SessionStart'
    monkeypatch.setattr('sys.stdin', io.StringIO(event))
    assert main(['--store', str(tmp_path / 'missing'), 'session', 'hook']) == 0
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('harness', ['claude', 'codex'])
def test_generated_command_runs_with_quoted_path(tmp_path, harness):
    root = tmp_path / "store ' with spaces"
    root.mkdir()
    worktree = tmp_path / 'firmware'
    worktree.mkdir()
    plan = prepare_hook(harness, worktree, root)
    command = json.loads(plan.after)['hooks']['SessionStart'][0]['hooks'][0]['command']
    event = json.dumps({'session_id': 's1', 'cwd': str(worktree)})
    result = subprocess.run(command, shell=True, input=event, text=True, capture_output=True,
                            env={k: v for k, v in os.environ.items() if not k.startswith('CLAUDE_')})
    assert result.returncode == 0
    assert json.loads(result.stdout)['hookSpecificOutput']['hookEventName'] == 'SessionStart'
    assert (worktree / '.caiman' / 'sessions' / f'{harness}-s1' / 'session.json').is_file()


@pytest.mark.asyncio
@pytest.mark.parametrize('harness', ['claude', 'codex'])
async def test_hook_screen_preview_install_and_cancel(tmp_path, harness):
    app = HooksApp(harness=harness, store_root=tmp_path, directory=tmp_path)
    path = settings_path(harness, tmp_path)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert app.query_one('#install', Button).disabled
        await pilot.click('#prepare')
        assert not path.exists()
        assert not app.query_one('#install', Button).disabled
        await pilot.click('#install')
        assert path.exists()
        assert 'Installed' in str(app.query_one('#status', Static).render())
        await pilot.press('q')
    other = tmp_path / 'other'
    other.mkdir()
    app = HooksApp(harness=harness, store_root=tmp_path, directory=other)
    async with app.run_test() as pilot:
        await pilot.click('#prepare')
        app.query_one('#directory', Input).value = str(tmp_path)
        await pilot.pause()
        assert app.query_one('#install', Button).disabled
        await pilot.press('q')
    assert not settings_path(harness, other).exists()
