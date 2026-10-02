"""Optional Git transport for independent pod folders.

Saving data never commits or pushes. Sync commits locally, fetches, merges, and
pushes with Git's fast-forward protection. Conflicts keep both histories.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
from urllib.parse import urlsplit

from caiman.documents.models import canonical_json, valid_identifier
from caiman.storage.store import Store

ATTRIBUTES = b'blobs/** -text -filter -ident -working-tree-encoding -merge\nmanifests/** -text -filter -ident -working-tree-encoding -merge\n'
BRANCH = 'caiman-store'


def _pod(value):
    if not valid_identifier(value):
        raise ValueError('Enter a pod ID using letters, digits, dots, hyphens or underscores')
    return value


def _remote(value):
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Enter an SSH or HTTPS repository URL, or an absolute local repository path')
    if Path(value).is_absolute():
        return value
    if '://' in value:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'https', 'ssh'} or not parsed.hostname or not parsed.path.strip('/') or
            parsed.query or parsed.fragment or parsed.password is not None or
            (parsed.scheme == 'https' and parsed.username is not None)):
            raise ValueError('Use SSH or HTTPS without embedded credentials')
        parsed.port
    elif not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*:[A-Za-z0-9_./~-]+', value):
        raise ValueError('Use SSH, HTTPS, or an absolute local repository path')
    return value


@dataclass(frozen=True)
class RepoPlan:
    action: str
    pod: str
    remote: str | None
    local_path: Path
    before: str
    push: bool = False

    @property
    def preview(self):
        verbs = {'create': 'Create local pod', 'add': 'Clone pod', 'initialize': 'Connect Git',
                 'remove': 'Disconnect Git remote', 'sync': 'Sync pod', 'default': 'Set default pod'}
        lines = [verbs[self.action], f'Pod: {self.pod}', f'Folder: {self.local_path}',
                 f'Remote: {self.remote or "Local only"}']
        if self.action == 'sync':
            lines.append('Commit local changes, fetch team changes, merge, and push. Conflicts preserve both versions.')
        elif self.action == 'initialize':
            lines.append('Enable Git in this pod folder. Existing data stays local until Sync.')
        elif self.action == 'remove':
            lines.append('Keep local data and Git history; remove the remote connection.')
        return '\n'.join(lines)


class RepoManager:
    def __init__(self, root: Path):
        self.store = Store(root)

    def local_path(self, pod):
        return self.store.pod_path(_pod(pod))

    def list_repos(self):
        records = []
        for r in self.store.pods.list():
            initialized = (r['path'] / '.git').exists()
            remote = self._git(r['path'], 'config', '--local', '--get', 'remote.origin.url', allow_missing=True) if initialized else ''
            records.append(dict(pod=r['id'], name=r['name'], remote=remote or None,
                                initialized=initialized, default=r['id'] == self.store.pods.default))
        return records

    def _state(self, path):
        if not path.exists():
            return ''
        entries = []
        self.store._directory(path)
        for p in sorted(path.rglob('*')):
            if '.git' in p.relative_to(path).parts:
                continue
            if p.is_symlink():
                raise ValueError('Pod files must not be symlinks')
            if p.is_file():
                entries.append((str(p.relative_to(path)), hashlib.sha256(self.store._read(p)).hexdigest()))
        if (path / '.git').exists():
            entries.append(('git-status', self._git(path, 'status', '--porcelain')))
            entries.append(('git-head', self._git(path, 'show-ref', '--head', allow_missing=True)))
            entries.append(('git-remote', self._git(path, 'config', '--local', '--get', 'remote.origin.url', allow_missing=True)))
        return hashlib.sha256(canonical_json({'files': entries})).hexdigest()

    def prepare(self, action, pod, remote='', push=False):
        if action not in {'create', 'add', 'initialize', 'remove', 'sync', 'default'}:
            raise ValueError('Unknown pod operation')
        path = self.local_path(pod)
        if push:
            raise ValueError('Use Sync after connecting Git')
        remote = _remote(remote) if remote else None
        if action == 'add' and (remote is None or path.exists()):
            raise ValueError('Clone needs a remote and a new local pod folder')
        if action == 'create' and path.exists():
            raise ValueError('This pod folder already exists')
        if (path / '.git').exists() or (path / '.git').is_symlink():
            self.store._directory(path / '.git')
            existing = self._git(path, 'config', '--local', '--get', 'remote.origin.url', allow_missing=True)
            if existing and remote and existing != remote:
                raise ValueError('Disconnect the existing remote before connecting a different one')
            remote = remote or existing or None
        elif action in {'sync', 'remove'}:
            raise ValueError('Connect Git for this pod first')
        return RepoPlan(action, pod, remote, path, self._state(path))

    @contextmanager
    def _locked(self):
        self.store._directory(self.store.root, create=True)
        fd = os.open(self.store.root / '.pods.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('Pod lock must be a regular file')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('Another pod operation is running') from error
            yield
        finally:
            os.close(fd)

    def _verify_tree(self, path, revision, expected=None):
        header = None
        attributes = None
        object_paths = set()
        refs = []
        for entry in filter(None, self._git(path, 'ls-tree', '-rz', '--full-tree', revision).split('\0')):
            metadata, name = entry.split('\t', 1)
            mode, kind, oid = metadata.split()
            if mode != '100644' or kind != 'blob' or any(p in ('', '.', '..') for p in name.split('/')):
                raise ValueError('Unsupported file type in pod repository')
            object_paths.add(name)
            if name.startswith('refs/'):
                refs.append(self._git(path, 'cat-file', 'blob', oid))
            if name.startswith(('blobs/', 'manifests/')):
                content = self._git(path, 'cat-file', 'blob', oid, raw=True)
                if (hashlib.sha256(content).hexdigest() != name.split('/')[-1] or
                    name.split('/')[-2] != name.split('/')[-1][:2]):
                    raise ValueError('Remote object digest mismatch')
            if name in {'pod.json', 'store.json'}:
                if header is not None:
                    raise ValueError('Repository contains conflicting pod headers')
                header = json.loads(self._git(path, 'cat-file', 'blob', oid))
                if name == 'store.json':
                    if not isinstance(header, dict) or set(header) != {'schema', 'compartment'} or header['schema'] != 'caiman.store.v1':
                        raise ValueError('Invalid legacy store header')
                    header = {'schema': 'caiman.pod.v1', 'id': header['compartment'], 'name': header['compartment']}

            elif name == '.gitattributes':
                attributes = self._git(path, 'cat-file', 'blob', oid)
            elif not re.fullmatch(r'(blobs|manifests)/sha256/[0-9a-f]{2}/[0-9a-f]{64}|refs/(documents|boards|projects|collections)/[^\s]+', name):
                raise ValueError(f'Unexpected file in pod repository: {name}')
        if (not isinstance(header, dict) or set(header) != {'schema', 'id', 'name'} or
            header['schema'] != 'caiman.pod.v1' or not valid_identifier(header['id']) or
            not isinstance(header['name'], str) or not header['name'].strip() or
            (expected is not None and header['id'] != expected)):
            raise ValueError('Repository pod identity does not match')
        if attributes != ATTRIBUTES.decode().strip():
            raise ValueError('Unsupported pod transport attributes')
        for value in refs:
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', value):
                raise ValueError('Invalid remote pod reference')
            if f'manifests/sha256/{value[7:9]}/{value[7:]}' not in object_paths:
                raise ValueError('Remote reference points to a missing manifest')
        return header

    def _verify_files(self, path):
        # Verify every immutable object's name and bytes before using or publishing it.
        for kind in ('blobs', 'manifests'):
            for p in (path / kind).rglob('*') if (path / kind).exists() else []:
                if p.is_symlink():
                    raise ValueError('Pod objects must not be symlinks')
                if not p.is_file():
                    continue
                content = p.read_bytes()
                if hashlib.sha256(content).hexdigest() != p.name or p.parent.name != p.name[:2]:
                    raise ValueError(f'Object digest mismatch: {p.name}')
                p.chmod(0o444)
        for p in (path / 'refs').rglob('*') if (path / 'refs').exists() else []:
            if p.is_file():
                value = p.read_text().strip()
                if not re.fullmatch(r'sha256:[0-9a-f]{64}', value):
                    raise ValueError('Invalid pod reference')
                if not (path / 'manifests' / 'sha256' / value[7:9] / value[7:]).is_file():
                    raise ValueError('Pod reference points to a missing manifest')

    def _initialize(self, plan):
        self.store.pods.ensure(plan.pod)
        if not (plan.local_path / '.git').exists():
            self._git(plan.local_path, 'init', '--quiet', '--template=', '--initial-branch=' + BRANCH)
        branch = self._git(plan.local_path, 'symbolic-ref', '--short', 'HEAD')
        if branch != BRANCH:
            raise ValueError('Switch this pod to the caiman-store branch before syncing')
        if plan.remote:
            self._git(plan.local_path, 'config', '--local', 'remote.origin.url', plan.remote)
        self.store._atomic_write(plan.local_path / '.gitattributes', ATTRIBUTES, immutable=False)

    def _clone(self, plan):
        self.store._directory(self.store.root, create=True)
        temporary = Path(tempfile.mkdtemp(prefix='.clone-', dir=self.store.root))
        try:
            self._git(temporary, 'init', '--quiet', '--template=', '--initial-branch=' + BRANCH)
            self._git(temporary, 'fetch', '--quiet', '--no-tags', '--no-recurse-submodules', plan.remote, 'refs/heads/' + BRANCH)
            header = self._verify_tree(temporary, 'FETCH_HEAD')
            existing = [r for r in self.store.pods.list() if r['id'] == header['id'] and r['path'].exists()]
            if existing:
                raise ValueError('This pod is already available locally')
            self._git(temporary, 'reset', '--hard', 'FETCH_HEAD')
            if (temporary / 'store.json').exists():
                self.store._atomic_write(temporary / 'pod.json', canonical_json(header), immutable=False)
                (temporary / 'store.json').unlink()
            self._git(temporary, 'remote', 'add', 'origin', plan.remote)
            self._verify_files(temporary)
            temporary.rename(plan.local_path)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def _sync(self, plan):
        path = plan.local_path
        if self._git(path, 'symbolic-ref', '--short', 'HEAD') != BRANCH:
            raise ValueError('Switch this pod to the caiman-store branch before syncing')
        if (path / '.git' / 'MERGE_HEAD').exists():
            raise ValueError('Finish or abort the existing Git merge first')
        self._verify_files(path)
        self._git(path, 'add', '-A', '--', '.')
        # Verify the index before committing: no unrelated files get published.
        tree = self._git(path, 'write-tree')
        pod_id = self.store.pods.resolve(plan.pod)['id']
        self._verify_tree(path, tree, pod_id)
        if self._git(path, 'status', '--porcelain'):
            self._git(path, '-c', 'commit.gpgSign=false', 'commit', '--quiet', '-m', 'Update Caiman pod')
        if not plan.remote:
            return
        refs = self._git(path, 'ls-remote', '--heads', plan.remote, 'refs/heads/' + BRANCH)
        if refs:
            self._git(path, 'fetch', '--quiet', '--no-tags', '--no-recurse-submodules', plan.remote, 'refs/heads/' + BRANCH)
            self._verify_tree(path, 'FETCH_HEAD', pod_id)
            try:
                self._git(path, '-c', 'commit.gpgSign=false', 'merge', '--no-edit', 'FETCH_HEAD')
            except ValueError as error:
                conflicts = self._git(path, 'diff', '--name-only', '--diff-filter=U')
                if (path / '.git' / 'MERGE_HEAD').exists():
                    self._git(path, 'merge', '--abort')
                raise ValueError('Pod sync needs a merge. Local changes are committed and remote history is fetched. '
                                 'Resolve with Git, then retry Sync. ' + (conflicts or str(error))) from error
            self._verify_files(path)
        self._git(path, 'push', '--porcelain', plan.remote, 'HEAD:refs/heads/' + BRANCH)

    def apply(self, plan):
        with self._locked():
            if self.prepare(plan.action, plan.pod, plan.remote, plan.push) != plan:
                raise ValueError('Pod changed since review; review again')
            if plan.action == 'create':
                self.store.pods.ensure(plan.pod)
            elif plan.action == 'default':
                self.store.pods.set_default(plan.pod)
            elif plan.action == 'initialize':
                self._initialize(plan)
            elif plan.action == 'add':
                self._clone(plan)
            elif plan.action == 'sync':
                self._sync(plan)
            elif plan.action == 'remove':
                self._git(plan.local_path, 'remote', 'remove', 'origin')
        return self.store.pods.resolve(plan.pod)['id']

    def _git(self, path, *args, allow_missing=False, raw=False):
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0',
                   GIT_SSH_COMMAND='ssh -oBatchMode=yes', GIT_ALLOW_PROTOCOL='ssh:https:file',
                   GIT_AUTHOR_NAME='Caiman', GIT_AUTHOR_EMAIL='caiman@localhost',
                   GIT_COMMITTER_NAME='Caiman', GIT_COMMITTER_EMAIL='caiman@localhost')
        try:
            credentials = []
            https_remote = next((arg for arg in args if arg.startswith('https://')), None)
            if https_remote and args[0] in {'fetch', 'push', 'ls-remote'}:
                # Import only credential settings from trusted user/system config;
                # leave URL rewrites, filters, hooks and transport overrides disabled.
                credential_env = {key: value for key, value in env.items()
                                  if key not in {'GIT_CONFIG_GLOBAL', 'GIT_CONFIG_NOSYSTEM'}}
                settings = subprocess.run(['git', '-C', str(path), 'config', '--get-urlmatch',
                                           'credential', https_remote], env=credential_env,
                                          capture_output=True, text=True, timeout=15)
                if settings.returncode not in {0, 1}:
                    raise ValueError('Unable to read Git credential settings')
                for line in settings.stdout.splitlines():
                    key, _, value = line.partition(' ')
                    if key in {'credential.helper', 'credential.username', 'credential.usehttppath'}:
                        credentials.extend(['-c', key + '=' + value])
            result = subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull,
                                     '-c', 'http.followRedirects=false', '-c', 'credential.interactive=false',
                                     *credentials, '-C', str(path), *args],
                                    env=env, capture_output=True, text=not raw, timeout=60)
        except FileNotFoundError as error:
            raise ValueError('Git is not installed or is not on PATH') from error
        except subprocess.TimeoutExpired as error:
            raise ValueError('Git operation timed out; check the remote and retry') from error
        if allow_missing and result.returncode == 1:
            return ''
        if result.returncode:
            raise ValueError('Git repository operation failed: ' + ((result.stderr.decode() if raw else result.stderr).strip() or 'unknown error'))
        return result.stdout if raw else result.stdout.strip()
