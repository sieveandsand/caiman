"""Per-session context folders in a worktree, provisioned on the host.

A harness start hook registers its session, creating the worktree's `.caiman/`
folder on first use. `caiman session load` installs one board or project
version's complete pinned document set into that session's `context/` folder.
Session folders separate selections, not permissions (S-19).
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

from caiman.configurations.models import part_identity, project_boards
from caiman.configurations.service import ConfigurationService
from caiman.documents.models import canonical_json
from caiman.storage.store import Store, document_ref


CAIMAN = '.caiman'
HARNESSES = ('claude', 'codex')
WORKSPACE_SCHEMA = 'caiman.workspace.v1'
SESSION_SCHEMA = 'caiman.session.v1'
STATE_SCHEMA = 'caiman.session-state.v1'
CONTEXT_SCHEMA = 'caiman.session-context.v1'
SESSION_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}')
KINDS = ('board', 'project')


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _plain_directory(path: Path) -> None:
    if path.is_symlink() or (path.exists() and not path.is_dir()):
        raise ValueError(f'Caiman workspace path must be a plain directory: {path}')


def _write_json(path: Path, data: dict) -> None:
    fd, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def _read_json(path: Path) -> dict | None:
    if path.is_symlink() or not path.is_file():
        return None
    data = json.loads(path.read_text(encoding='utf-8'))
    return data if isinstance(data, dict) else None


# ── Workspace and sessions ──────────────────────────────────────────────────

def find_workspace(start: Path) -> Path | None:
    """The nearest directory at or above `start` holding an initialized `.caiman/`."""
    start = Path(os.path.abspath(start))
    for directory in (start, *start.parents):
        marker = directory / CAIMAN / 'workspace.json'
        if marker.is_file() and not marker.is_symlink():
            return directory
    return None


def ensure_workspace(root: Path) -> Path:
    """Create `.caiman/` on first use; an existing one is reused unchanged."""
    root = Path(os.path.abspath(root))
    if not root.is_dir():
        raise ValueError(f'Workspace folder does not exist: {root}')
    caiman = root / CAIMAN
    _plain_directory(caiman)
    caiman.mkdir(mode=0o700, exist_ok=True)
    # Generated state and documents never enter the worktree's Git history (I-3).
    ignore = caiman / '.gitignore'
    if not ignore.exists() and not ignore.is_symlink():
        ignore.write_text('*\n', encoding='utf-8')
    marker = caiman / 'workspace.json'
    if not marker.exists() and not marker.is_symlink():
        _write_json(marker, {'schema': WORKSPACE_SCHEMA, 'id': uuid.uuid4().hex})
    return root


def session_name(harness: str, session_id: str) -> str:
    """Namespace the harness's ID and refuse anything that is not a safe folder name."""
    if harness not in HARNESSES:
        raise ValueError(f'Unknown harness: {harness}')
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        raise ValueError('Session ID is not a safe folder name')
    return f'{harness}-{session_id}'


def session_folder(root: Path, name: str) -> Path:
    if not isinstance(name, str) or '-' not in name:
        raise ValueError('Session must be <harness>-<session id>')
    harness, session_id = name.split('-', 1)
    sessions = Path(root) / CAIMAN / 'sessions'
    _plain_directory(sessions)
    return sessions / session_name(harness, session_id)


def register_session(root: Path, harness: str, session_id: str, *, source: str = '',
                     transcript: str | None = None) -> Path:
    """Create or reuse this session's folder; resuming keeps its installed context."""
    ensure_workspace(root)
    sessions = Path(root) / CAIMAN / 'sessions'
    _plain_directory(sessions)
    sessions.mkdir(mode=0o700, exist_ok=True)
    folder = sessions / session_name(harness, session_id)
    _plain_directory(folder)
    folder.mkdir(mode=0o700, exist_ok=True)
    path = folder / 'session.json'
    data = _read_json(path) or {'created_at': _now()}
    data.update(schema=SESSION_SCHEMA, harness=harness, session_id=session_id,
                last_start=_now(), last_source=source if isinstance(source, str) else '')
    if isinstance(transcript, str):
        data['transcript_path'] = transcript
    _write_json(path, data)
    return folder


def is_registered(folder: Path) -> bool:
    path = folder / 'session.json'
    return path.is_file() and not path.is_symlink()


def read_state(folder: Path) -> dict | None:
    return _read_json(folder / 'state.json')


# ── Choices ─────────────────────────────────────────────────────────────────

def list_choices(store_root: Path, name: str | None = None, *, kind: str | None = None,
                 pods: set[str] | None = None) -> list[dict]:
    """Every loadable board/project version; versions are opaque and unordered (I-7)."""
    service = ConfigurationService(Store(store_root))
    choices = []
    for each in ([kind] if kind else KINDS):
        for record in service.list_configs(each, pods=pods):
            if name is None or record['name'] == name:
                choices.append({'kind': each, 'name': record['name'], 'version': record['version'],
                                'pod': record['pod'], 'pod_name': record['pod_name'],
                                'digest': record['digest']})
    return choices


# ── Resolution ──────────────────────────────────────────────────────────────

def _document_key(record: dict) -> tuple:
    manifest = record['manifest']
    return (record['pod'], manifest.get('document_id', record['digest']), manifest['files'][0]['sha256'])


def resolve_context(store: Store, kind: str, name: str, version: str, pod: str | None = None) -> dict:
    """The selected snapshot, its boards, and its complete deduplicated document set."""
    if kind not in KINDS:
        raise ValueError('Choose board or project')
    service = ConfigurationService(store)
    matches = [record for record in service.list_configs(kind, pods={pod} if pod else None)
               if (record['name'], record['version']) == (name, version)]
    if not matches:
        versions = service.list_versions(kind, name)
        if not versions:
            raise ValueError(f'No {kind} named {name!r} is available locally')
        raise ValueError(f'{kind} {name!r} has no version {version!r}; available: {", ".join(versions)}')
    if len(matches) != 1:
        pods = ', '.join(record['pod'] for record in matches)
        raise ValueError(f'{kind} {name}@{version} exists in several pods ({pods}); choose one with --pod')
    record = matches[0]
    owner, manifest = record['pod'], record['manifest']
    boards = [(owner, record['digest'], manifest)] if kind == 'board' else []
    for selector in project_boards(manifest) if kind == 'project' else []:
        location = store.pods.check_reference(owner, selector.get('pod', 'public'))
        boards.append((location, selector['digest'],
                       service.load_digest('board', selector['digest'], pod=location)))
    documents, seen = [], set()

    def add(selectors, owning_pod):
        for found in service.project_documents({'documents': selectors}, owner=owning_pod):
            if (key := _document_key(found)) not in seen:
                seen.add(key)
                documents.append(found)

    for location, _, board in boards:
        add(list(board.get('documents', []))
            + [pin for part in board['parts'] for pin in part.get('documents', [])], location)
    if kind == 'project':
        add(list(manifest.get('documents', [])) + list(manifest.get('precedence', [])), owner)
    return {'kind': kind, 'name': name, 'version': version, 'pod': owner,
            'digest': record['digest'], 'manifest': manifest, 'boards': boards,
            'documents': documents}


def document_location(manifest: dict) -> Path:
    """`issuer/part/name@version/<original filename>`: the path is the citation (ARCHITECTURE §5)."""
    issuer, scope, name, version = document_ref(manifest).parts
    return Path(issuer, scope, f'{name}@{version}', _materialized_filename(manifest))


def _materialized_filename(manifest: dict) -> str:
    """The uploaded filename when it is a plain name; the stored `document.<ext>` otherwise."""
    filename = manifest.get('original_filename')
    if (isinstance(filename, str) and filename not in {'', '.', '..'} and not filename.startswith('.')
            and Path(filename).name == filename and '\\' not in filename and filename.isprintable()):
        return filename
    return manifest['files'][0]['path']


def document_set_digest(documents: list[dict]) -> str:
    """Depends only on what was installed, never on the session (STORAGE §6)."""
    keys = sorted([pod, str(identity), body] for pod, identity, body in map(_document_key, documents))
    return 'sha256:' + hashlib.sha256(canonical_json({'documents': keys})).hexdigest()


# ── Materialization ─────────────────────────────────────────────────────────

def _write_readonly(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o444)


def count(n: int) -> str:
    return f'{n} document' + ('' if n == 1 else 's')


def _brief(resolved: dict, revision: int, entries: list[dict]) -> str:
    """Metadata only: names, versions, roles, part numbers, paths (I-6)."""
    kind, name, version = resolved['kind'], resolved['name'], resolved['version']
    lines = [f'# {name} @ {version}', '',
             f'Caiman {kind} context, revision {revision}. Snapshot {resolved["digest"]} '
             f'from pod {resolved["pod"]}.', '', '## Boards', '']
    for pod, _, board in resolved['boards']:
        lines.append(f'- {board["board"]} @ {board["version"]} (pod {pod})')
        lines += [f'  - {part.get("role", "")}: {part_identity(part)}' for part in board['parts']]
    lines += ['', '## Documents', '',
              f'{count(len(entries))} installed under `documents/`; '
              '`documents/_index.md` lists every one. Search them with `rg` or `grep -r`.',
              'Each path encodes issuer, part, document, and version. Cite facts as '
              '(document path, version, locator such as a heading, page, or requirement ID).', '']
    lines += [f'- `{entry["path"]}`' for entry in entries]
    return '\n'.join(lines) + '\n'


def _index(entries: list[dict]) -> str:
    lines = ['# Installed documents', '',
             f'This is the complete installed set: {count(len(entries))}. '
             'Nothing pinned was left out.', '',
             '| Path | Pod | Document | Body |', '|---|---|---|---|']
    lines += [f'| `{e["path"]}` | {e["pod"]} | {e["document"]} | {e["blob"]} |' for e in entries]
    return '\n'.join(lines) + '\n'


def _build(store: Store, staging: Path, resolved: dict, revision: int) -> dict:
    entries, used = [], {}
    for record in resolved['documents']:
        manifest = record['manifest']
        relative = Path('documents') / document_location(manifest)
        if relative in used:
            # Two pinned documents would share one citation path; never drop either (I-9).
            raise ValueError(f'Two pinned documents map to {relative.as_posix()} '
                             f'(pods {used[relative]} and {record["pod"]}); rename one before loading')
        used[relative] = record['pod']
        blob = 'sha256:' + manifest['files'][0]['sha256']
        try:
            content = store.read_blob(record['pod'], blob)
        except ValueError as error:
            raise ValueError(f'Cannot install {relative.as_posix()}: {error}') from error
        _write_readonly(staging / relative, content)
        entries.append({'path': relative.as_posix(), 'pod': record['pod'],
                        'document': manifest.get('document_id', record['digest']),
                        'manifest': record['digest'], 'blob': blob})
    identity = {'schema': CONTEXT_SCHEMA, 'revision': revision, 'kind': resolved['kind'],
                'name': resolved['name'], 'version': resolved['version'], 'pod': resolved['pod'],
                'digest': resolved['digest'], 'document_set': document_set_digest(resolved['documents']),
                'boards': [{'name': board['board'], 'version': board['version'], 'pod': pod, 'digest': digest}
                           for pod, digest, board in resolved['boards']],
                'documents': entries}
    _write_readonly(staging / 'documents' / '_index.md', _index(entries).encode())
    _write_readonly(staging / 'project.json',
                    (json.dumps(identity, ensure_ascii=False, indent=2) + '\n').encode())
    _write_readonly(staging / 'project.md', _brief(resolved, revision, entries).encode())
    return identity


@contextmanager
def _locked(folder: Path):
    """One change at a time per session, whether from the TUI or an agent."""
    fd = os.open(folder / '.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def _generation(folder: Path, name, prefix: str) -> Path:
    if not isinstance(name, str) or not name.startswith(prefix) or '/' in name:
        raise ValueError(f'Corrupt installation journal in {folder}')
    return folder / name


def recover(folder: Path) -> None:
    """Finish or roll back an interrupted install; never expose a partial context."""
    journal = folder / 'install.json'
    record = _read_json(journal)
    context = folder / 'context'
    if record is not None:
        staging = _generation(folder, record.get('staging'), '.staging-')
        previous = _generation(folder, record.get('previous'), '.previous-')
        if context.is_dir() and not staging.exists():
            _write_json(folder / 'state.json', record['state'])
        elif not context.exists() and previous.is_dir():
            os.rename(previous, context)
        journal.unlink()
    for leftover in [*folder.glob('.staging-*'), *folder.glob('.previous-*')]:
        if leftover.is_dir() and not leftover.is_symlink():
            shutil.rmtree(leftover)


def load_context(store_root: Path, folder: Path, kind: str, name: str, version: str,
                 pod: str | None = None) -> dict:
    """Install a complete context revision, or fail and keep the previous one."""
    if not is_registered(folder):
        raise ValueError('This session is not registered. Install the Caiman start hook '
                         'and start a new session.')
    store = Store(store_root)
    with _locked(folder):
        recover(folder)
        resolved = resolve_context(store, kind, name, version, pod)
        revision = (read_state(folder) or {}).get('revision', 0) + 1
        staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=folder))
        previous = folder / f'.previous-{revision}'
        context = folder / 'context'
        try:
            identity = _build(store, staging, resolved, revision)
            state = {key: identity[key] for key in
                     ('revision', 'kind', 'name', 'version', 'pod', 'digest', 'document_set')}
            state.update(schema=STATE_SCHEMA, documents=len(identity['documents']), installed_at=_now())
            _write_json(folder / 'install.json',
                        {'staging': staging.name, 'previous': previous.name, 'state': state})
            if context.exists():
                os.rename(context, previous)
            os.rename(staging, context)
            _write_json(folder / 'state.json', state)
            (folder / 'install.json').unlink()
        finally:
            recover(folder)
    return state
