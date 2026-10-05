"""Observe which Caiman-managed documents a coding-agent session touched.

Little caiman is a read-only sidecar. It tails the harness's own transcript and
keeps only tool-call inputs that name a managed document: the path, a line
range, and whether the call read, searched, or edited it. Tool results, prompts,
and shell command text are never kept, shown, or written anywhere (I-10).

Absence of a record is not proof a document was not read. Reads through
scripts, variables, a changed shell directory, other processes, or anything
outside the harness are invisible here.
"""

from collections import Counter
from dataclasses import dataclass, field, replace
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import sqlite3
from urllib.parse import unquote

from caiman.documents.ingest import heading_outline
from caiman.sessions.service import CAIMAN, find_workspace, is_registered, read_state, session_name


HARNESS_NAMES = {'claude': 'Claude Code', 'codex': 'Codex'}
ABSENCE_NOTICE = 'Absence of a record is not proof a document was not read.'

# A tree-wide search such as `rg ID .caiman/documents/` names no single document.
TREE = 'tree'
# Claude Code's Read returns this many lines when only an offset is given.
READ_DEFAULT_LIMIT = 2000

SEARCHERS = {'rg', 'grep', 'egrep', 'fgrep', 'ag', 'ack', 'git'}
EDITORS = {'rm', 'mv', 'chmod', 'chown', 'truncate', 'tee', 'touch', 'ed', 'vi', 'vim', 'nvim', 'nano', 'emacs'}
SEPARATORS = {'|', '||', '&&', ';', '&', '(', ')', '|&', ';;'}
REDIRECTS = {'>', '>>', '>|', '&>'}
WRAPPERS = {'sudo', 'command', 'exec', 'env', 'time', 'nice', 'xargs'}
EDIT_TOOLS = {'Edit': 'file_path', 'MultiEdit': 'file_path', 'Write': 'file_path',
              'NotebookEdit': 'notebook_path'}
SHELL_TOOLS = {'shell', 'shell_command', 'exec_command', 'local_shell', 'container.exec'}
PATCH_HEADER = re.compile(r'^\*\*\* (?:Update|Add|Delete) File: (.+?)\s*$', re.MULTILINE)
PATCH_MOVE = re.compile(r'^\*\*\* Move to: (.+?)\s*$', re.MULTILINE)
JS_STRING_FIELD = r'\b{}\s*:\s*("(?:[^"\\]|\\.)*")'
# Cheap pre-filter: most transcript lines are tool results and never need parsing.
INTERESTING = (b'tool_use', b'_call"', b'turn_context', b'session_meta')


# ── Sessions ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Session:
    harness: str
    transcript: Path
    session_id: str
    cwd: Path | None
    title: str
    updated: float
    # This session's installed documents, `<worktree>/.caiman/sessions/<id>/context/documents`.
    documents: Path | None = None

    def transcripts(self) -> list[Path]:
        """The main transcript first, then any subagent transcripts beside it."""
        paths = [self.transcript]
        if self.harness == 'claude':
            paths += sorted((self.transcript.with_suffix('') / 'subagents').glob('*.jsonl'))
        return paths


def _head(path: Path, lines: int = 200):
    try:
        with path.open('rb') as stream:
            for _, line in zip(range(lines), stream):
                yield line
    except OSError:
        return


def _tail(path: Path, size: int = 256 * 1024) -> list[bytes]:
    try:
        with path.open('rb') as stream:
            stream.seek(max(0, path.stat().st_size - size))
            return stream.read().splitlines()[1:]
    except OSError:
        return []


def _json(line: bytes):
    try:
        value = json.loads(line)
    except (UnicodeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _claude_session(path: Path, updated: float) -> Session:
    cwd = None
    for line in _head(path):
        if b'"cwd"' in line and (entry := _json(line)) and isinstance(entry.get('cwd'), str):
            cwd = Path(entry['cwd'])
            break
    title = ''
    for line in reversed(_tail(path)):
        if b'"ai-title"' in line and (entry := _json(line)) and isinstance(entry.get('aiTitle'), str):
            title = entry['aiTitle']
            break
    return Session('claude', path, path.stem, cwd, title, updated)


def _codex_titles(home: Path) -> dict[str, str]:
    database = home / '.codex' / 'state_5.sqlite'
    if not database.is_file():
        return {}
    try:
        with sqlite3.connect(f'file:{database}?mode=ro', uri=True, timeout=0.5) as connection:
            return {path: title for path, title in connection.execute('SELECT rollout_path, title FROM threads')
                    if isinstance(path, str) and isinstance(title, str)}
    except sqlite3.Error:
        return {}


def _codex_session(path: Path, updated: float, titles: dict[str, str]) -> Session:
    meta = next((entry.get('payload') for line in _head(path, 5) if (entry := _json(line))
                 and entry.get('type') == 'session_meta'), None) or {}
    cwd = Path(meta['cwd']) if isinstance(meta.get('cwd'), str) else None
    session_id = meta.get('id') if isinstance(meta.get('id'), str) else path.stem
    return Session('codex', path, session_id, cwd, titles.get(str(path), ''), updated)


def registered(session: Session) -> Session | None:
    """The session with its documents folder if Caiman's start hook registered it."""
    if session.cwd is None or (root := find_workspace(session.cwd)) is None:
        return None
    try:
        folder = root / CAIMAN / 'sessions' / session_name(session.harness, session.session_id)
    except ValueError:
        return None
    return replace(session, documents=folder / 'context' / 'documents') if is_registered(folder) else None


def loaded_context(session: Session) -> dict | None:
    """What `caiman session load` last installed for this session, read fresh each time."""
    if session.documents is None:
        return None
    try:
        return read_state(session.documents.parent.parent)
    except (OSError, ValueError):
        return None


def loaded_contents(session: Session) -> dict | None:
    """The installed context's identities: boards and document paths, never content."""
    if session.documents is None:
        return None
    try:
        data = json.loads((session.documents.parent / 'project.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def document_label(path: str) -> tuple[str, str]:
    """`documents/nxp/s32k344/manual@rev-4/document.pdf` → (`nxp/s32k344`, `manual @ rev-4`)."""
    folders = Path(path).parts[1:-1]
    if not folders:
        return '', path
    name, _, version = folders[-1].rpartition('@')
    scope = '/'.join(unquote(part) for part in folders[:-1])
    return scope, (f'{unquote(name)} @ {unquote(version)}' if name else unquote(folders[-1]))


def list_sessions(home: Path | None = None, limit: int = 30) -> list[Session]:
    """Most recently active sessions Caiman registered, newest first, across harnesses."""
    home = Path.home() if home is None else home
    candidates = []
    for harness, paths in (('claude', (home / '.claude' / 'projects').glob('*/*.jsonl')),
                           ('codex', (home / '.codex' / 'sessions').rglob('rollout-*.jsonl'))):
        for path in paths:
            try:
                candidates.append((path.stat().st_mtime, harness, path))
            except OSError:
                continue
    sessions, titles = [], None
    for updated, harness, path in sorted(candidates, reverse=True):
        if harness == 'claude':
            session = _claude_session(path, updated)
        else:
            titles = _codex_titles(home) if titles is None else titles
            session = _codex_session(path, updated, titles)
        if (found := registered(session)) is not None:
            sessions.append(found)
            if len(sessions) == limit:
                break
    return sessions


# ── Managed documents ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class DocumentRef:
    """Identity from the path alone, as the planned access log derives it."""

    path: Path
    name: str
    version: str | None
    location: str  # 'workspace' or 'store'
    pod: str | None = None

    @property
    def title(self) -> str:
        return self.name.rsplit('/', 1)[-1]

    @property
    def scope(self) -> str:
        return self.name.rsplit('/', 1)[0] if '/' in self.name else ''


class Resolver:
    def __init__(self, documents: Path | None, store_root: Path | None):
        self.workspace = Path(os.path.abspath(documents)) if documents else None
        self.store = Path(os.path.abspath(store_root)) if store_root else None

    @staticmethod
    def absolute(raw: str, base: Path | None) -> Path | None:
        if not raw or '\x00' in raw:
            return None
        path = Path(os.path.expanduser(raw))
        if not path.is_absolute():
            if base is None:
                return None
            path = base / path
        return Path(os.path.normpath(path))

    def identify(self, path: Path):
        """A DocumentRef, TREE for a directory or glob of managed documents, or None."""
        wildcard = any(character in str(path) for character in '*?[')
        for root, location in ((self.workspace, 'workspace'), (self.store, 'store')):
            if root is None:
                continue
            if path != root and not path.is_relative_to(root):
                # The session's `context/` holds only its documents and brief; broader parents are too noisy to count.
                if location == 'workspace' and path == root.parent:
                    return TREE
                continue
            parts = path.relative_to(root).parts
            if location == 'workspace' and len(parts) >= 2 and (parts[-1] == 'document' or parts[-1].startswith('document.')) and '@' in parts[-2]:
                name, version = parts[-2].split('@', 1)
                return DocumentRef(path, '/'.join((*parts[:-2], name)), version, location)
            if (location == 'store' and len(parts) == 5 and parts[1:3] == ('blobs', 'sha256')
                    and re.fullmatch(r'[0-9a-f]{64}', parts[4])):
                return DocumentRef(path, f'{parts[0]}/blob-{parts[4][:12]}', None, location, parts[0])
            if wildcard or path == root or path.is_dir():
                return TREE
            return None
        return None


# ── Usage ───────────────────────────────────────────────────────────────────

@dataclass
class DocumentUsage:
    ref: DocumentRef
    reads: int = 0
    whole_reads: int = 0
    searches: int = 0
    edits: int = 0
    via_shell: int = 0
    sections: Counter = field(default_factory=Counter)
    last_seen: str = ''
    order: int = 0


@dataclass(frozen=True)
class Integrity:
    """Whether the bytes on disk are still a blob the store holds."""

    state: str  # 'intact', 'modified', 'missing', or 'unverified'
    writable: bool = False


class UsageTracker:
    def __init__(self, session: Session, store_root: Path | None):
        self.session = session
        self.store_root = Path(os.path.abspath(store_root)) if store_root else None
        self.resolver = Resolver(session.documents, store_root)
        self.documents: dict[Path, DocumentUsage] = {}
        self.tree_searches = 0
        self._offsets: dict[Path, int] = {}
        self._partial: dict[Path, bytes] = {}
        self._cwd: dict[Path, Path | None] = {}
        self._sequence = 0
        self._outlines: dict[Path, tuple] = {}
        self._integrity: dict[Path, tuple] = {}

    @property
    def has_workspace(self) -> bool:
        return self.resolver.workspace is not None and self.resolver.workspace.is_dir()

    def ranked(self) -> list[DocumentUsage]:
        return sorted(self.documents.values(), key=lambda usage: usage.order, reverse=True)

    # Transcript tailing

    def poll(self) -> bool:
        """Read any newly appended transcript lines; True if usage changed."""
        before = (self._sequence, self.tree_searches)
        for path in self.session.transcripts():
            self._read(path)
        return before != (self._sequence, self.tree_searches)

    def _read(self, path: Path) -> None:
        try:
            size = path.stat().st_size
            offset = self._offsets.get(path, 0)
            if size < offset:  # Rewritten, not appended: start again.
                offset, self._partial[path] = 0, b''
            if size == offset:
                return
            with path.open('rb') as stream:
                stream.seek(offset)
                chunk = self._partial.get(path, b'') + stream.read(size - offset)
        except OSError:
            return
        self._offsets[path] = size
        *lines, self._partial[path] = chunk.split(b'\n')
        cwd = self._cwd.get(path, self.session.cwd)
        for line in lines:
            if not any(marker in line for marker in INTERESTING):
                continue
            entry = _json(line)
            if entry is None:
                continue
            if self.session.harness == 'claude':
                cwd = Path(entry['cwd']) if isinstance(entry.get('cwd'), str) else cwd
                self._claude(entry, cwd)
            else:
                payload = entry.get('payload')
                if isinstance(payload, dict) and isinstance(payload.get('cwd'), str):
                    cwd = Path(payload['cwd'])
                if entry.get('type') == 'response_item' and isinstance(payload, dict):
                    self._codex(payload, cwd, entry.get('timestamp', ''))
        self._cwd[path] = cwd

    def _claude(self, entry: dict, cwd: Path | None) -> None:
        message = entry.get('message')
        if entry.get('type') != 'assistant' or not isinstance(message, dict):
            return
        stamp = entry.get('timestamp', '')
        for block in message.get('content') or []:
            if not isinstance(block, dict) or block.get('type') != 'tool_use':
                continue
            name, arguments = block.get('name'), block.get('input')
            if not isinstance(arguments, dict):
                continue
            if name == 'Read':
                offset, limit = arguments.get('offset'), arguments.get('limit')
                lines = None
                if isinstance(offset, int) or isinstance(limit, int):
                    start = offset if isinstance(offset, int) and offset > 0 else 1
                    count = limit if isinstance(limit, int) and limit > 0 else READ_DEFAULT_LIMIT
                    lines = (start, start + count - 1)
                self._path(arguments.get('file_path'), cwd, 'read', lines, False, stamp)
            elif name == 'Grep':
                self._path(arguments.get('path'), cwd, 'search', None, False, stamp)
            elif name in EDIT_TOOLS:
                self._path(arguments.get(EDIT_TOOLS[name]), cwd, 'edit', None, False, stamp)
            elif name == 'Bash' and isinstance(arguments.get('command'), str):
                self._shell(arguments['command'], cwd, stamp)

    def _codex(self, payload: dict, cwd: Path | None, stamp: str) -> None:
        kind, name = payload.get('type'), payload.get('name')
        if kind == 'local_shell_call':
            action = payload.get('action') or {}
            command = action.get('command') if isinstance(action, dict) else None
            base = self.resolver.absolute(action.get('working_directory') or '', cwd) if isinstance(action, dict) else None
            self._shell(command, base or cwd, stamp)
        elif kind == 'custom_tool_call' and isinstance(payload.get('input'), str):
            text = payload['input']
            self._patch(text, cwd, stamp)
            if name != 'apply_patch':
                # Code-mode calls wrap commands, e.g. tools.exec_command({cmd:"…", workdir:"…"}).
                base = next(iter(self._js_strings(text, 'workdir')), None)
                base = self.resolver.absolute(base, cwd) if base else cwd
                for command in self._js_strings(text, 'cmd') + self._js_strings(text, 'command'):
                    self._shell(command, base, stamp)
        elif kind == 'function_call' and isinstance(payload.get('arguments'), str):
            arguments = _json(payload['arguments'].encode())
            if arguments is None:
                return
            if name == 'apply_patch' and isinstance(arguments.get('input'), str):
                self._patch(arguments['input'], cwd, stamp)
            elif name in SHELL_TOOLS:
                base = arguments.get('workdir') or arguments.get('cwd')
                base = self.resolver.absolute(base, cwd) if isinstance(base, str) else cwd
                self._shell(arguments.get('command') or arguments.get('cmd'), base, stamp)

    @staticmethod
    def _js_strings(text: str, key: str) -> list[str]:
        values = []
        for literal in re.findall(JS_STRING_FIELD.format(key), text):
            try:
                values.append(json.loads(literal))
            except ValueError:
                continue
        return [value for value in values if isinstance(value, str)]

    def _patch(self, text: str, cwd: Path | None, stamp: str) -> None:
        for raw in PATCH_HEADER.findall(text) + PATCH_MOVE.findall(text):
            self._path(raw, cwd, 'edit', None, False, stamp)

    # Shell commands are classified, never retained.

    def _shell(self, command, cwd: Path | None, stamp: str) -> None:
        if isinstance(command, list):
            command = shlex.join(str(part) for part in command)
        if not isinstance(command, str):
            return
        try:
            lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
            lexer.whitespace_split = True
            tokens = list(lexer)
        except ValueError:
            tokens = command.split()
        hits, program, flags, previous = [], None, [], None
        for index, token in enumerate(tokens):
            if token in SEPARATORS:
                program, flags, previous = None, [], token
                continue
            if program is None and (token in WRAPPERS or re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', token)):
                previous = token
                continue
            if program is None:
                program = os.path.basename(token)
                if program in {'bash', 'sh', 'zsh'} and '-c' in tokens[index + 1:index + 2]:
                    self._shell(tokens[index + 2] if index + 2 < len(tokens) else '', cwd, stamp)
                previous = token
                continue
            if token.startswith('-'):
                flags.append(token)
            elif token not in REDIRECTS:
                target = self.resolver.identify(path) if (path := self.resolver.absolute(token, cwd)) else None
                if target is not None:
                    if previous in REDIRECTS or program in EDITORS or (
                            program in {'sed', 'perl'} and any(flag.startswith('-i') for flag in flags)):
                        hits.append((target, 'edit'))
                    elif program in SEARCHERS:
                        hits.append((target, 'search'))
                    else:
                        hits.append((target, 'read'))
            previous = token
        documents = {target for target, _ in hits if target != TREE}
        lines = self._shell_range(tokens) if len(documents) == 1 else None
        for target, kind in hits:
            self._count(target, kind, lines if kind == 'read' else None, True, stamp)

    @staticmethod
    def _shell_range(tokens: list[str]):
        for index, token in enumerate(tokens):
            if token == 'sed':
                for value in tokens[index + 1:index + 4]:
                    if match := re.fullmatch(r'(\d+)(?:,(\d+))?p', value):
                        start = int(match[1])
                        return start, int(match[2] or start)
            if token == 'head':
                for option, value in zip(tokens[index + 1:index + 3], tokens[index + 2:index + 4] + ['']):
                    count = value if option == '-n' else option[2:] if option.startswith('-n') else option[1:]
                    if option.startswith('-') and count.isdigit():
                        return 1, int(count)
        return None

    def _path(self, raw, cwd, kind, lines, shell, stamp) -> None:
        if isinstance(raw, str) and (path := self.resolver.absolute(raw, cwd)):
            if (target := self.resolver.identify(path)) is not None:
                self._count(target, kind, lines, shell, stamp)

    def _count(self, target, kind: str, lines, shell: bool, stamp: str) -> None:
        if target == TREE:
            # Listing a directory reads no document; only searches reach content.
            if kind == 'search':
                self._sequence += 1
                self.tree_searches += 1
            return
        self._sequence += 1
        usage = self.documents.setdefault(target.path, DocumentUsage(target))
        if kind == 'read':
            usage.reads += 1
            if lines is None:
                usage.whole_reads += 1
            else:
                usage.sections.update(self.sections(target, *lines))
        elif kind == 'search':
            usage.searches += 1
        else:
            usage.edits += 1
        usage.via_shell += shell
        usage.last_seen = stamp if isinstance(stamp, str) else ''
        usage.order = self._sequence

    # Locators and integrity, computed from the document on disk.

    def sections(self, ref: DocumentRef, start: int, end: int) -> list[str]:
        """Heading paths whose span overlaps the lines read; a line range when none are known."""
        # Digest-only store paths carry no format; do not guess Markdown from bytes.
        headings = (self._headings(ref.path)
                    if ref.location == 'workspace' and ref.path.suffix.lower() in {'.md', '.markdown'} else ())
        if not headings:
            return [f'Lines {start}–{end}']
        spans = [(heading.line, following.line - 1 if following else None, heading.path)
                 for heading, following in zip(headings, (*headings[1:], None))]
        touched = [' › '.join(path) for first, last, path in spans
                   if first <= end and (last is None or last >= start)]
        return touched or [f'Lines {start}–{end}']

    def _headings(self, path: Path):
        try:
            status = path.stat()
            key = (status.st_mtime_ns, status.st_size)
            if self._outlines.get(path, (None,))[0] != key:
                text = path.read_text(encoding='utf-8')
                headings = heading_outline(text)[0] if '\x00' not in text else ()
                self._outlines[path] = (key, headings)
            return self._outlines[path][1]
        except (OSError, UnicodeError):
            return ()

    def integrity(self, ref: DocumentRef) -> Integrity:
        try:
            status = ref.path.stat()
        except OSError:
            return Integrity('missing')
        key = (status.st_mtime_ns, status.st_size, status.st_ino, status.st_mode)
        cached = self._integrity.get(ref.path)
        if cached and cached[0] == key:
            return cached[1]
        writable = bool(status.st_mode & 0o222)
        try:
            digest = hashlib.sha256(ref.path.read_bytes()).hexdigest()
        except OSError:
            return Integrity('missing')
        if ref.location == 'store':
            state = 'intact' if ref.path.name == digest else 'modified'
        elif self.store_root is None or not self.store_root.is_dir():
            state = 'unverified'
        else:
            held = any((pod / 'blobs' / 'sha256' / digest[:2] / digest).is_file()
                       for pod in self.store_root.iterdir() if pod.is_dir())
            state = 'intact' if held else 'modified'
        result = Integrity(state, writable)
        self._integrity[ref.path] = (key, result)
        return result
