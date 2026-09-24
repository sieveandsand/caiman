"""Local repository registration and initialization, separate from publication."""

from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
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


def _compartment(value):
    if not valid_identifier(value):
        raise ValueError('Enter one compartment using letters, digits, dots, hyphens or underscores')
    return value


def _remote(value):
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise ValueError('Enter an SSH or HTTPS repository URL')
    if '://' in value:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'https', 'ssh'} or not parsed.hostname or
                not parsed.path.strip('/') or parsed.query or parsed.fragment or
                parsed.password is not None or (parsed.scheme == 'https' and parsed.username is not None)):
            raise ValueError('Use an SSH or HTTPS repository URL without passwords, tokens or query parameters')
        # Accessing port validates malformed/non-numeric port declarations.
        parsed.port
    elif not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*@[A-Za-z0-9][A-Za-z0-9.-]*:[A-Za-z0-9_./~-]+', value):
        raise ValueError('Enter an SSH or HTTPS repository URL')
    return value


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate repository configuration key')
        result[key] = value
    return result


@dataclass(frozen=True)
class RepoPlan:
    action: str
    compartment: str
    remote: str | None
    local_path: Path
    before: bytes | None
    push: bool = False

    @property
    def preview(self):
        verb = {'add': 'Add repository', 'remove': 'Remove registration', 'initialize': 'Initialize local repository'}[self.action]
        lines = [verb, f'Compartment: {self.compartment}', f'Remote: {self.remote or "Local only"}',
                 f'Local repository: {self.local_path}']
        if self.action == 'remove':
            lines.append('Removes this entry from Caiman. Local files and the hosted repository are kept.')
        elif self.action == 'add':
            lines.append('Verifies the caiman-store branch and compartment before saving the address.')
        else:
            lines.append('Creates a local Git repository on branch caiman-store, or reuses its existing initialization.')
            lines.append('Pushes only the initial Caiman metadata to the supplied empty remote.' if self.push else 'Keeps initialization local; nothing is pushed.')
            lines.append('Existing documents and configurations are not included.')
        return '\n'.join(lines)


class RepoManager:
    def __init__(self, root: Path):
        self.store = Store(root)
        self.path = self.store.root / '.repositories.json'

    def local_path(self, compartment):
        return self.store.root / '.repositories' / _compartment(compartment)

    def _load(self):
        if not self.path.exists() and not self.path.is_symlink():
            return None, {}
        before = self.store._read(self.path)
        data = json.loads(before, object_pairs_hook=_unique)
        if not isinstance(data, dict) or set(data) != {'schema', 'repositories'} or data['schema'] != 'caiman.repositories.v1':
            raise ValueError('Invalid repository registry')
        records = data['repositories']
        if not isinstance(records, dict):
            raise ValueError('Invalid repository entries')
        for compartment, record in records.items():
            _compartment(compartment)
            if not isinstance(record, dict) or set(record) != {'remote', 'initialized'} or type(record['initialized']) is not bool:
                raise ValueError('Invalid repository entry')
            if record['remote'] is not None:
                _remote(record['remote'])
            elif not record['initialized']:
                raise ValueError('Repository requires a remote or local initialization')
        return before, records

    def list_repos(self):
        _, records = self._load()
        return [dict(compartment=key, **records[key]) for key in sorted(records)]

    def _git(self, path, *args, allow_missing=False):
        env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0',
                   GIT_SSH_COMMAND='ssh -oBatchMode=yes', GIT_ALLOW_PROTOCOL='ssh:https',
                   GIT_AUTHOR_NAME='Caiman', GIT_AUTHOR_EMAIL='caiman@localhost',
                   GIT_COMMITTER_NAME='Caiman', GIT_COMMITTER_EMAIL='caiman@localhost',
                   GIT_AUTHOR_DATE='2000-01-01T00:00:00Z', GIT_COMMITTER_DATE='2000-01-01T00:00:00Z')
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
                                    env=env, capture_output=True, text=True, timeout=60)
        except FileNotFoundError as error:
            raise ValueError('Git is not installed or is not on PATH') from error
        except subprocess.TimeoutExpired as error:
            raise ValueError('Git operation timed out; check the remote and retry') from error
        if allow_missing and result.returncode == 1:
            return ''
        if result.returncode:
            raise ValueError('Git repository operation failed: ' + (result.stderr.strip() or 'unknown error'))
        return result.stdout.strip()

    def _verify_remote(self, compartment, remote):
        # Fetch objects into a disposable private directory; never check out remote files.
        with tempfile.TemporaryDirectory(prefix='caiman-verify-') as directory:
            path = Path(directory)
            self._git(path, 'init', '--quiet', '--template=')
            self._git(path, 'fetch', '--quiet', '--depth=1', '--no-tags', '--no-recurse-submodules',
                      remote, 'refs/heads/caiman-store')
            entries = self._git(path, 'ls-tree', '-rz', '--full-tree', 'FETCH_HEAD').split('\0')
            header = None
            attributes = None
            for entry in filter(None, entries):
                metadata, name = entry.split('\t', 1)
                mode, kind, oid = metadata.split()
                if mode != '100644' or kind != 'blob':
                    raise ValueError('Remote is not a Caiman repository: unsupported file type')
                if name == 'store.json':
                    header = json.loads(self._git(path, 'cat-file', 'blob', oid), object_pairs_hook=_unique)
                elif name == '.gitattributes':
                    attributes = self._git(path, 'cat-file', 'blob', oid)
                elif not re.fullmatch(r'(blobs|manifests)/sha256/[0-9a-f]{2}/[0-9a-f]{64}|refs/(documents|boards|projects|contexts)/[^\s]+|withdrawals/[^/]+\.json', name):
                    raise ValueError('Remote is not a Caiman repository: unexpected tracked path')
            if header != {'schema': 'caiman.store.v1', 'compartment': compartment}:
                raise ValueError('Remote is not a Caiman repository for this compartment (store.json mismatch)')
            if attributes != ATTRIBUTES.decode().strip():
                raise ValueError('Remote is not a Caiman repository: unsupported transport attributes')

    def _push_initial(self, plan):
        # Build the commit from fixed metadata, never from the existing working tree.
        with tempfile.TemporaryDirectory(prefix='caiman-push-') as directory:
            path = Path(directory)
            self._git(path, 'init', '--quiet', '--template=', '--initial-branch=caiman-store')
            (path / 'store.json').write_bytes(canonical_json({'schema': 'caiman.store.v1', 'compartment': plan.compartment}))
            (path / '.gitattributes').write_bytes(ATTRIBUTES)
            self._git(path, 'add', '--', 'store.json', '.gitattributes')
            self._git(path, '-c', 'commit.gpgSign=false', 'commit', '--quiet', '-m', 'Initialize Caiman compartment repository')
            head = self._git(path, 'rev-parse', 'HEAD')
            refs = self._git(path, 'ls-remote', '--refs', plan.remote)
            expected = head + '\trefs/heads/caiman-store'
            if refs == expected:
                return  # Retry after a successful push whose response was lost.
            if refs:
                raise ValueError('Initialize requires an empty remote. Use Add for an existing Caiman repository.')
            self._git(path, 'push', '--porcelain', '--force-with-lease=refs/heads/caiman-store:',
                      plan.remote, 'HEAD:refs/heads/caiman-store')

    def _existing(self, compartment, remote):
        path = self.local_path(compartment)
        if not path.exists() and not path.is_symlink():
            return False
        try:
            self.store._directory(path / '.git')
        except FileNotFoundError as error:
            raise ValueError('The local directory already exists and is not an initialized Caiman repository') from error
        expected = {'schema': 'caiman.store.v1', 'compartment': compartment}
        if json.loads(self.store._read(path / 'store.json'), object_pairs_hook=_unique) != expected:
            raise ValueError('Existing repository belongs to a different compartment or format')
        actual = self._git(path, 'config', '--local', '--get-all', 'remote.origin.url', allow_missing=True)
        if actual and actual != (remote or ''):
            raise ValueError('Existing local repository has a different remote; its configuration was preserved')
        return True

    def prepare(self, action, compartment, remote='', push=False):
        if action not in {'add', 'remove', 'initialize'}:
            raise ValueError('Choose Add, Remove or Initialize')
        _compartment(compartment)
        if type(push) is not bool or (push and action != 'initialize'):
            raise ValueError('Push is available only for initialization')
        before, records = self._load()
        record = records.get(compartment)
        if action == 'remove':
            if record is None:
                raise ValueError('Choose a registered repository to remove')
            remote = record['remote']
        else:
            remote = _remote(remote) if remote else None
            if action == 'add' and record is not None:
                raise ValueError('A repository is already registered for this compartment')
            if action == 'add' and remote is None:
                raise ValueError('Enter an SSH or HTTPS repository URL')
            if record is not None:
                if record['remote'] is not None and remote is not None and remote != record['remote']:
                    raise ValueError('This compartment already has a different remote registered')
                remote = remote or record['remote']
            self._existing(compartment, record['remote'] if record else remote)
        if push and not remote:
            raise ValueError('Enter a remote URL to push initialization')
        return RepoPlan(action, compartment, remote, self.local_path(compartment), before, push)

    @contextmanager
    def _locked(self):
        self.store._directory(self.store.root, create=True)
        path = self.store.root / '.repositories.lock'
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('Repository lock must be a regular file')
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('Another repository operation is running; try again') from error
            yield
        finally:
            os.close(fd)

    def _initialize(self, plan):
        if self._existing(plan.compartment, plan.remote):
            return
        parent = plan.local_path.parent
        self.store._directory(parent, create=True)
        temporary = Path(tempfile.mkdtemp(prefix='.initialize-', dir=parent))
        try:
            self._git(temporary, 'init', '--quiet', '--template=', '--initial-branch=caiman-store')
            if plan.remote:
                self._git(temporary, 'remote', 'add', 'origin', plan.remote)
            for name in ('blobs/sha256', 'manifests/sha256', 'refs/documents', 'refs/boards', 'refs/projects', 'refs/contexts'):
                self.store._directory(temporary / name, create=True)
            header = {'schema': 'caiman.store.v1', 'compartment': plan.compartment}
            self.store._atomic_write(temporary / 'store.json', canonical_json(header), immutable=False)
            self.store._atomic_write(temporary / '.gitattributes', ATTRIBUTES, immutable=False)
            if plan.local_path.exists() or plan.local_path.is_symlink():
                raise ValueError('Repository directory appeared during initialization; review again')
            temporary.rename(plan.local_path)
            self.store._fsync_directory(parent)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def apply(self, plan: RepoPlan):
        with self._locked():
            before, records = self._load()
            if before != plan.before:
                raise ValueError('Repository configuration changed since review; review again')
            checked = self.prepare(plan.action, plan.compartment, plan.remote, plan.push)
            if checked != plan:
                raise ValueError('Repository operation changed since review; review again')
            if plan.action == 'remove':
                del records[plan.compartment]
            else:
                if plan.action == 'add':
                    self._verify_remote(plan.compartment, plan.remote)
                if plan.action == 'initialize':
                    self._initialize(plan)
                records[plan.compartment] = {'remote': plan.remote,
                                             'initialized': self._existing(plan.compartment, plan.remote)}
            data = {'schema': 'caiman.repositories.v1', 'repositories': records}
            self.store._atomic_write(self.path, canonical_json(data), immutable=False)
            if plan.push:
                try:
                    self._push_initial(plan)
                except (OSError, ValueError) as error:
                    raise ValueError('Local repository saved; remote push did not complete. Retry Initialize with push. ' + str(error)) from error
        return plan.compartment
