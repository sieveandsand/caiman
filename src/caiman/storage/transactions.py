"""Journaled publication of a reviewed set of mutable refs.

Objects are written first. An interrupted publication is rolled back before
the next store is opened; all immutable objects remain available.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import fcntl
import json
import os
from pathlib import Path
import stat

from caiman.documents.models import canonical_json

_held = ContextVar('caiman_store_locks', default=frozenset())
JOURNAL = '.document-update.json'


@contextmanager
def locked(store):
    from caiman.storage.store import StoreError
    if store.root in _held.get():
        yield
        return
    store._directory(store.root, create=True)
    fd = os.open(store.root / '.pods.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise StoreError('Pod lock must be a regular file')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise StoreError('Another pod operation is running') from error
        token = _held.set(_held.get() | {store.root})
        try:
            recover(store)
            yield
        finally:
            _held.reset(token)
    finally:
        os.close(fd)


def check_read(store):
    from caiman.storage.store import StoreError
    path = store.root / JOURNAL
    if store.root not in _held.get() and (path.exists() or path.is_symlink()):
        raise StoreError('Document update in progress; reopen the store to recover an interrupted update')


def _value(store, path):
    return store._read(path).decode('ascii') if path.exists() or path.is_symlink() else None


def _finish(store):
    (store.root / JOURNAL).unlink()
    store._fsync_directory(store.root)


def recover(store):
    from caiman.storage.store import StoreError, _hex
    path = store.root / JOURNAL
    if not path.exists() and not path.is_symlink():
        return
    try:
        changes = json.loads(store._read(path))
        if not isinstance(changes, list) or not changes:
            raise ValueError()
        paths = set()
        for change in changes:
            if not isinstance(change, dict) or set(change) != {'path', 'before', 'after'}:
                raise ValueError()
            relative = Path(change['path'])
            if (relative.is_absolute() or any(p in {'.', '..'} for p in relative.parts)
                    or len(relative.parts) < 4 or relative.parts[1] != 'refs'
                    or relative.parts[2] not in {'documents', 'boards', 'projects', 'collections', 'document-heads'}
                    or relative.as_posix() != change['path'] or relative in paths):
                raise ValueError()
            paths.add(relative)
            for key in ('before', 'after'):
                value = change[key]
                if value is not None:
                    if not isinstance(value, str):
                        raise ValueError('Invalid recovery ref value')
                    _hex(value.removesuffix('\n'))
            if _value(store, store.root / relative) not in (change['before'], change['after']):
                raise StoreError('Interrupted document update conflicts with a changed ref; manual recovery required')
    except (TypeError, KeyError, UnicodeError, ValueError) as error:
        raise StoreError('Cannot recover interrupted document update: ' + str(error)) from error
    for change in reversed(changes):
        target = store.root / change['path']
        if change['before'] is None:
            if target.exists():
                target.unlink()
                store._fsync_directory(target.parent)
        else:
            store._atomic_write(target, change['before'].encode(), immutable=False)
    _finish(store)


def publish(store, changes):
    """Called under the shared writer lock; changes contain relative paths and ref bytes."""
    from caiman.storage.store import StoreError
    for change in changes:
        if _value(store, store.root / change['path']) != change['before']:
            raise StoreError('A usage changed since review; review again')
    store._atomic_write(store.root / JOURNAL, canonical_json(changes), immutable=False)
    try:
        for change in changes:
            path = store.root / change['path']
            if change['after'] is None:
                path.unlink()
                store._fsync_directory(path.parent)
            else:
                store._atomic_write(path, change['after'].encode(), immutable=False)
        _finish(store)
    except Exception:
        recover(store)
        raise
