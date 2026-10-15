import io
import json
import os
import subprocess

import pytest
from rich.console import COLOR_SYSTEMS
from textual.widgets import Button, Input, Static

from caiman.cli.commands import main
from caiman.hooks.service import end_hook_installed, install_hook, prepare_hook, prepare_skill, settings_path
from caiman.hooks.skill import SKILL
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


def test_end_hook_is_added_and_removed_beside_other_end_hooks(tmp_path):
    path = settings_path('claude', tmp_path)
    path.parent.mkdir()
    other = {'hooks': [{'type': 'command', 'command': 'echo bye'}]}
    path.write_text(json.dumps({'hooks': {'SessionEnd': [other]}}))
    assert not end_hook_installed('claude', tmp_path)
    assert install_hook(prepare_hook('claude', tmp_path, tmp_path / 'store', end=True))
    hooks = json.loads(path.read_text())['hooks']
    assert hooks['SessionEnd'][0] == other and len(hooks['SessionEnd']) == 2
    [handler] = hooks['SessionEnd'][1]['hooks']
    assert handler['command'].endswith('session end --harness claude 2>/dev/null || true')
    assert handler['timeout'] == 5 and end_hook_installed('claude', tmp_path)
    assert not install_hook(prepare_hook('claude', tmp_path, tmp_path / 'store', end=True))
    # Without `end`, only Caiman's end hook goes; the start hook stays.
    assert install_hook(prepare_hook('claude', tmp_path, tmp_path / 'store'))
    hooks = json.loads(path.read_text())['hooks']
    assert hooks['SessionEnd'] == [other] and len(hooks['SessionStart']) == 1
    assert not end_hook_installed('claude', tmp_path)
    path.write_text(json.dumps({'hooks': {'SessionEnd': [{'hooks': [handler]}]}}))
    assert install_hook(prepare_hook('claude', tmp_path, tmp_path / 'store'))
    assert 'SessionEnd' not in json.loads(path.read_text())['hooks']
    with pytest.raises(ValueError, match='Codex has no session end hook'):
        prepare_hook('codex', tmp_path, tmp_path, end=True)


def test_generated_end_command_removes_only_the_loaded_context(tmp_path):
    store = tmp_path / "store ' with spaces"
    store.mkdir()
    worktree = tmp_path / 'firmware'
    worktree.mkdir()
    hooks = json.loads(prepare_hook('claude', worktree, store, end=True).after)['hooks']
    start, end = (hooks[event][0]['hooks'][0]['command'] for event in ('SessionStart', 'SessionEnd'))
    env = {k: v for k, v in os.environ.items() if not k.startswith('CLAUDE_')}

    def run(command, event):
        payload = event if isinstance(event, str) else json.dumps(event)
        return subprocess.run(command, shell=True, input=payload, text=True, capture_output=True, env=env)

    event = {'session_id': 's1', 'cwd': str(worktree)}
    assert run(start, event).returncode == 0
    folder = worktree / '.caiman' / 'sessions' / 'claude-s1'
    document = folder / 'context' / 'documents' / 'issuer' / 'mcu' / 'manual' / 'v1' / 'manual.md'
    document.parent.mkdir(parents=True)
    document.write_text('Installed copy.')
    document.chmod(0o444)
    (folder / 'state.json').write_text('{}')
    result = run(end, event | {'hook_event_name': 'SessionEnd', 'reason': 'prompt_input_exit'})
    assert (result.returncode, result.stdout) == (0, '')
    assert not (folder / 'context').exists() and not (folder / 'state.json').exists()
    record = json.loads((folder / 'session.json').read_text())
    assert record['context_removed'] is True and record['last_end'] >= record['last_start']
    # Another session, a worktree without `.caiman/`, a bad ID, or bad input: exit 0, create nothing.
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    for bad in ({'session_id': 's2', 'cwd': str(worktree)}, {'session_id': 's1', 'cwd': str(elsewhere)},
                {'session_id': '../s1', 'cwd': str(worktree)}, 'not json'):
        assert (run(end, bad).returncode, run(end, bad).stdout) == (0, '')
    assert not (elsewhere / '.caiman').exists()
    assert sorted(path.name for path in folder.parent.iterdir()) == ['claude-s1']


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


@pytest.mark.parametrize('harness, folder', [('claude', '.claude/skills'), ('codex', '.codex/skills')])
def test_skill_installs_in_the_users_home_and_is_idempotent(tmp_path, harness, folder):
    plan = prepare_skill(harness, tmp_path)
    assert plan.path == tmp_path / folder / 'caiman' / 'SKILL.md'
    assert not plan.path.exists() and '+name: caiman' in plan.preview  # Preview never writes.
    assert install_hook(plan)
    assert plan.path.read_text() == SKILL
    assert not install_hook(prepare_skill(harness, tmp_path))
    assert 'Caiman skill already installed.' in prepare_skill(harness, tmp_path).preview
    plan.path.write_text('edited by hand')
    assert '-edited by hand' in prepare_skill(harness, tmp_path).preview


def test_skill_names_no_machine_paths_and_keeps_the_rules():
    head, body = SKILL.split('\n---\n', 1)
    assert head.startswith('---\nname: caiman\ndescription: ')
    assert '/Users/' not in SKILL and 'python' not in SKILL
    body = ' '.join(body.split())
    for rule in ('Never choose a version yourself', 'Never open, list, or search other folders',
                 '(document path, version, locator)', 'rg -n PATTERN', 'read-only'):
        assert rule in body


@pytest.mark.asyncio
@pytest.mark.parametrize('harness', ['claude', 'codex'])
async def test_hook_screen_preview_install_and_cancel(tmp_path, harness):
    home = tmp_path / 'home'
    app = HooksApp(harness=harness, store_root=tmp_path, directory=tmp_path, home=home)
    path, skill = settings_path(harness, tmp_path), prepare_skill(harness, home).path
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        assert app.query_one('#install', Button).disabled
        await pilot.click('#prepare')
        assert not path.exists() and not skill.exists()
        assert str(skill) in str(app.query_one('#preview', Static).render())
        assert not app.query_one('#install', Button).disabled
        await pilot.click('#install')
        assert path.exists() and skill.read_text() == SKILL
        assert 'Installed' in str(app.query_one('#status', Static).render())
        await pilot.press('q')
    other = tmp_path / 'other'
    other.mkdir()
    app = HooksApp(harness=harness, store_root=tmp_path, directory=other, home=home)
    async with app.run_test() as pilot:
        await pilot.click('#prepare')
        app.query_one('#directory', Input).value = str(tmp_path)
        await pilot.pause()
        assert app.query_one('#install', Button).disabled
        await pilot.press('q')
    assert not settings_path(harness, other).exists()


@pytest.mark.asyncio
async def test_hook_screen_installs_a_missing_skill_beside_an_existing_hook(tmp_path):
    home = tmp_path / 'home'
    install_hook(prepare_hook('claude', tmp_path, tmp_path))
    app = HooksApp(harness='claude', store_root=tmp_path, directory=tmp_path, home=home)
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.click('#prepare')
        assert 'Caiman hook already installed.' in str(app.query_one('#preview', Static).render())
        assert not app.query_one('#install', Button).disabled
        await pilot.click('#install')
        assert prepare_skill('claude', home).path.read_text() == SKILL
        await pilot.press('q')


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['truecolor', '256', 'standard'])
async def test_claude_hook_screen_always_adds_start_and_offers_end(tmp_path, mode, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    home, path = tmp_path / 'home', settings_path('claude', tmp_path)
    app = HooksApp(harness='claude', store_root=tmp_path, directory=tmp_path, home=home)
    app.console._color_system = COLOR_SYSTEMS[mode]
    async with app.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        start, end = app.query_one('#hook-start', Button), app.query_one('#hook-end', Button)
        assert start.disabled and start.label.plain.startswith('  [x] Session start')
        assert 'required' in start.label.plain and end.label.plain.startswith('  [ ] Session end')
        # The end hook's cost shows only while it is chosen.
        assert not app.query_one('#end-hint', Static).display
        await pilot.click('#prepare')
        assert 'SessionEnd' not in str(app.query_one('#preview', Static).render())
        await pilot.click('#hook-end')
        # Checked state and focus are both text, not color alone.
        assert end.label.plain.startswith('› [x] Session end')
        assert app.query_one('#end-hint', Static).display
        app.query_one('#prepare', Button).focus()
        await pilot.pause()
        assert end.label.plain.startswith('  [x] Session end')
        # Changing the choice discards the preview it no longer matches.
        assert app.query_one('#install', Button).disabled
        await pilot.click('#prepare')
        assert 'SessionEnd' in str(app.query_one('#preview', Static).render())
        await pilot.click('#install')
        assert end_hook_installed('claude', tmp_path)
        await pilot.press('q')
    # Reopened, the screen shows what is installed; clearing the choice removes the end hook.
    app = HooksApp(harness='claude', store_root=tmp_path, directory=tmp_path, home=home)
    async with app.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        end = app.query_one('#hook-end', Button)
        assert end.label.plain.startswith('  [x] Session end')
        await pilot.click('#prepare')
        assert app.query_one('#install', Button).disabled
        await pilot.click('#hook-end')
        await pilot.click('#prepare')
        await pilot.click('#install')
        await pilot.press('q')
    hooks = json.loads(path.read_text())['hooks']
    assert 'SessionEnd' not in hooks and len(hooks['SessionStart']) == 1


@pytest.mark.asyncio
async def test_codex_hook_screen_offers_no_end_hook(tmp_path):
    app = HooksApp(harness='codex', store_root=tmp_path, directory=tmp_path, home=tmp_path / 'home')
    async with app.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        assert app.query_one('#hook-start', Button).disabled and not app.query('#hook-end')
        await pilot.press('q')
