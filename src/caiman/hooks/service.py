"""Reviewed, additive harness setup and a content-free startup orientation."""

from dataclasses import dataclass
import difflib
import json
import os
from pathlib import Path
import shlex
import stat
import sys
import tempfile


HARNESS_NAMES = {'claude': 'Claude Code', 'codex': 'Codex'}


def settings_path(harness: str, directory: Path) -> Path:
    if harness == 'claude':
        return directory / '.claude' / 'settings.json'
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

    @property
    def changed(self):
        return self.before != self.after

    @property
    def preview(self):
        return ''.join(difflib.unified_diff(
            (self.before or b'').decode('utf-8').splitlines(keepends=True),
            self.after.decode('utf-8').splitlines(keepends=True),
            fromfile=str(self.path), tofile=str(self.path))) or 'Caiman hook already installed.'


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
    command = shlex.join([sys.executable, '-m', 'caiman', '--store', str(store_root.absolute()),
                          'session', 'start']) + ' 2>/dev/null || true'
    handler = {'type': 'command', 'command': command, 'timeout': 5}
    if any(g.get('matcher', '') in ('', '*') and handler in g['hooks'] for g in groups):
        return HookPlan(path, before, before)
    groups.append({'hooks': [handler]})
    return HookPlan(path, before, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))


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


def session_start(root: Path) -> int:
    """No store contents, event payload, or document bodies enter hook output."""
    if not root.is_dir():
        return 0
    cli = shlex.join([sys.executable, '-m', 'caiman', '--store', str(root.absolute())])
    context = (
        'Caiman manages versioned firmware documents, boards, and projects. '
        f'Use `{cli} --help` for commands and `{cli} documents` for the local document catalog. '
        'Ask the engineer which board or project and version is relevant before selecting context. '
        'Local pods are available directly; Git hosts control repository sharing. '
        'Automatic workspace sync and access logging are not available in this version.'
    )
    print(json.dumps({'hookSpecificOutput': {'hookEventName': 'SessionStart', 'additionalContext': context}}))
    return 0
