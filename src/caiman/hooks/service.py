"""Reviewed, additive harness setup and the session start hook."""

from dataclasses import dataclass
import difflib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import tempfile

from caiman.hooks.skill import SKILL


HARNESS_NAMES = {'claude': 'Claude Code', 'codex': 'Codex'}
CAIMAN_HANDLER = re.compile(r'-m caiman\b.*\bsession (?:start|hook)\b')


def settings_path(harness: str, directory: Path) -> Path:
    if harness == 'claude':
        # Local settings: the command embeds this machine's paths, so it is never committed.
        return directory / '.claude' / 'settings.local.json'
    if harness == 'codex':
        return directory / '.codex' / 'hooks.json'
    raise ValueError('Choose Claude Code or Codex')


def _read(path: Path) -> bytes | None:
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f'Symlinked settings paths are not supported: {path}')
    return path.read_bytes() if path.exists() else None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate settings key: {key}')
        result[key] = value
    return result


@dataclass(frozen=True)
class HookPlan:
    path: Path
    before: bytes | None
    after: bytes
    unchanged: str = 'Caiman hook already installed.'

    @property
    def changed(self):
        return self.before != self.after

    @property
    def preview(self):
        return ''.join(difflib.unified_diff(
            (self.before or b'').decode('utf-8').splitlines(keepends=True),
            self.after.decode('utf-8').splitlines(keepends=True),
            fromfile=str(self.path), tofile=str(self.path))) or self.unchanged


def skill_path(harness: str, home: Path) -> Path:
    """User-level, so no firmware repository gains files (I-3)."""
    if harness not in HARNESS_NAMES:
        raise ValueError('Choose Claude Code or Codex')
    return home / f'.{harness}' / 'skills' / 'caiman' / 'SKILL.md'


def prepare_skill(harness: str, home: Path) -> HookPlan:
    path = skill_path(harness, home.expanduser().absolute())
    return HookPlan(path, _read(path), SKILL.encode('utf-8'), 'Caiman skill already installed.')


def prepare_hook(harness: str, directory: Path, store_root: Path) -> HookPlan:
    directory = directory.expanduser().absolute()
    if not directory.is_dir():
        raise ValueError('Choose an existing project directory')
    path = settings_path(harness, directory)
    before = _read(path)
    data = json.loads(before.decode('utf-8'), object_pairs_hook=_unique) if before is not None else {}
    if not isinstance(data, dict):
        raise ValueError('Settings must be a JSON object')
    hooks = data.setdefault('hooks', {})
    if not isinstance(hooks, dict):
        raise ValueError('hooks must be a JSON object')
    groups = hooks.setdefault('SessionStart', [])
    if not isinstance(groups, list) or any(not isinstance(g, dict) or not isinstance(g.get('hooks'), list)
                                         or any(not isinstance(h, dict) for h in g['hooks']) for g in groups):
        raise ValueError('SessionStart must contain hook groups')
    command = _cli(store_root) + f' session hook --harness {harness} 2>/dev/null || true'
    handler = {'type': 'command', 'command': command, 'timeout': 5}
    # Upgrade an earlier Caiman handler in place rather than running two.
    placed = False
    for group in groups:
        kept = []
        for entry in group['hooks']:
            if not CAIMAN_HANDLER.search(str(entry.get('command', ''))):
                kept.append(entry)
            elif not placed and group.get('matcher', '') in ('', '*'):
                kept.append(handler)
                placed = True
        group['hooks'] = kept
    groups[:] = [group for group in groups if group['hooks']]
    if not placed:
        groups.append({'hooks': [handler]})
    after = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    if before is not None and json.loads(before) == data:
        return HookPlan(path, before, before)
    return HookPlan(path, before, after)


def install_hook(plan: HookPlan) -> bool:
    """Apply only the reviewed bytes; refuse settings changed since preview."""
    if _read(plan.path) != plan.before:
        raise ValueError('Settings changed since review. Preview the change again.')
    if not plan.changed:
        return False
    plan.path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(plan.path.stat().st_mode) if plan.before is not None else 0o600
    fd, temporary = tempfile.mkstemp(prefix='.caiman-hooks-', dir=plan.path.parent)
    try:
        with os.fdopen(fd, 'wb') as output:
            os.fchmod(output.fileno(), mode)
            output.write(plan.after)
        if _read(plan.path) != plan.before:
            raise ValueError('Settings changed since review. Preview the change again.')
        os.replace(temporary, plan.path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


def _cli(store_root: Path) -> str:
    return shlex.join([sys.executable, '-m', 'caiman', '--store', str(store_root.absolute())])


def session_context(store_root: Path, folder: Path, state: dict | None) -> str:
    """What the agent is told at start; identities and paths only, never content (I-6)."""
    cli, name = _cli(store_root), folder.name
    load = f'{cli} session load <board|project> <name> --version <version> --session {name}'
    if state is None or not (folder / 'context').is_dir():
        return ('Caiman manages versioned firmware documents, boards, and projects. '
                f'No board or project is loaded for this session ({name}). '
                'At the start of your first reply, whatever the user asked, ask which board '
                'or project and version to load for this session; they may decline, and then '
                'do not ask again. Show the choices from '
                f'`{cli} session list` (add a name to see its versions). Never choose a '
                f'version yourself. Load the user\'s choice with `{load}`, then continue '
                'with their request.')
    from caiman.sessions.service import search_hint

    brief, documents = folder / 'context' / 'project.md', folder / 'context' / 'documents'
    return (f"Caiman: this session ({name}) has {state['kind']} {state['name']} @ "
            f"{state['version']} loaded (revision {state['revision']}). Read {brief} before "
            f'answering hardware or requirement questions; its documents are under {documents}. '
            f'{search_hint(documents)} To switch, ask the user which board or '
            f'project and version, then run `{load}` and reread the brief.')


def session_hook(store_root: Path, harness: str, event: dict, env=os.environ) -> str | None:
    """Register the session, creating `.caiman/` on first use, and orient the agent.

    Returns the hook's stdout, or None when there is nothing to say. Never prompts,
    never provisions, never reads document content (S-23, I-10).
    """
    from caiman.sessions.service import find_workspace, prune_sessions, read_state, register_session

    if not store_root.is_dir() or not isinstance(event, dict):
        return None
    cwd = event.get('cwd') if isinstance(event.get('cwd'), str) else os.getcwd()
    project = env.get('CLAUDE_PROJECT_DIR') or cwd
    root = find_workspace(Path(project)) or Path(project)
    folder = register_session(root, harness, event.get('session_id'),
                              source=event.get('source', ''), transcript=event.get('transcript_path'))
    try:
        prune_sessions(root, folder.name)
    except Exception:
        # Cleanup is housekeeping; it must never cost the agent its orientation (I-10).
        pass
    if env_file := env.get('CLAUDE_ENV_FILE'):
        # Later Bash commands in this session find their own folder without guessing.
        with open(env_file, 'a', encoding='utf-8') as stream:
            stream.write(f'export CAIMAN_SESSION={shlex.quote(folder.name)}\n'
                         f'export CAIMAN_WORKSPACE={shlex.quote(str(root))}\n')
    return json.dumps({'hookSpecificOutput': {
        'hookEventName': 'SessionStart',
        'additionalContext': session_context(store_root, folder, read_state(folder))}})
