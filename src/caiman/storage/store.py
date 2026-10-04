"""Local content storage in independent pod folders. Registration never publishes remotely.

Objects are durable before a ref becomes visible. Failure may leave unreachable
objects; existing refs remain valid. Each document has one owning pod.
The store assumes a single writer, not a hostile process modifying directories.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import quote

from caiman.documents.ingest import PreparedDocument, document_path, validate_metadata, verify_prepared
from caiman.documents.models import canonical_json, is_schema, valid_identifier


class StoreError(ValueError):
    """Invalid or corrupt store data; no unverified content is returned."""


@dataclass(frozen=True)
class Registration:
    manifest_digest: str
    blob_digest: str
    ref_path: Path
    pod: str


def _hex(digest: str) -> str:
    if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise StoreError("Expected a complete lowercase sha256 digest")
    return digest[7:]


def _digest(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _component(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise StoreError("Invalid empty path component")
    # quote leaves dots unescaped even with safe="". Encode dot-only labels
    # explicitly so opaque versions never become filesystem traversal.
    if value in (".", ".."):
        return "%2E" * len(value)
    return quote(value, safe="")


def _validate_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict) or not is_schema("document", manifest.get("schema")):
        raise StoreError("Not a document manifest")
    generated = {"schema", "original_filename", "pipeline_version", "ingested_at", "files", "document_id", "previous"}
    validate_metadata({key: value for key, value in manifest.items() if key not in generated})
    if manifest['schema'] == 'caiman.document.v4':
        if not valid_identifier(manifest.get('document_id')) or 'previous' not in manifest:
            raise StoreError('Manifest must identify its document and previous revision')
        if manifest['previous'] is not None:
            _hex(manifest['previous'])
    filename = manifest.get("original_filename")
    if (not isinstance(filename, str) or not filename.strip()
            or Path(filename).name != filename or filename in {'.', '..'}
            or any(ord(char) < 32 or ord(char) == 127 for char in filename)):
        raise StoreError("Manifest must name the original input basename")
    files = manifest.get("files")
    if (not isinstance(files, list) or len(files) != 1 or not isinstance(files[0], dict)
            or set(files[0]) != {"path", "sha256", "size"}
            or not isinstance(files[0]["path"], str)
            or files[0]["path"] not in {"document.md", document_path(filename)}
            or type(files[0]["size"]) is not int or files[0]["size"] < 0):
        raise StoreError("Manifest must describe exactly one unchanged document blob")
    _hex("sha256:" + str(files[0]["sha256"]))


def document_ref(manifest: dict) -> Path:
    """The canonical mutable name for both ingestion and metadata edits."""
    return Path(*[_component(value) for value in (
        manifest.get('issuer'), manifest.get('part') or manifest.get('program'),
        manifest.get('name') or manifest.get('doc_type'), manifest.get('version'))])


class Store:
    def __init__(self, root: Path):
        # Resolve the parent only: standard platform aliases such as /tmp are
        # allowed, but the store root and everything within it may not be links.
        root = Path(root).expanduser().absolute()
        self.root = root.parent.resolve() / root.name
        from caiman.pods.service import PodRegistry
        self.pods = PodRegistry(self)
        from caiman.storage.transactions import JOURNAL
        if (self.root / JOURNAL).exists() or (self.root / JOURNAL).is_symlink():
            with self.locked():
                pass

    def locked(self):
        from caiman.storage.transactions import locked
        return locked(self)

    def pod_path(self, pod):
        return self.pods.resolve(pod)["path"]

    def pod_name(self, pod):
        return self.pods.resolve(pod)["name"]

    def _directory(self, path: Path, *, create: bool = False) -> None:
        if not path.is_relative_to(self.root):
            raise StoreError("Path lies outside store")
        if create and not self.root.parent.exists():
            missing = []
            parent = self.root.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                parent.mkdir(mode=0o700)
                self._fsync_directory(parent.parent)
        for current in (self.root, *[self.root / Path(*path.relative_to(self.root).parts[:i])
                                   for i in range(1, len(path.relative_to(self.root).parts) + 1)]):
            if create:
                try:
                    current.mkdir(mode=0o700)
                    self._fsync_directory(current.parent)
                except FileExistsError:
                    pass
            mode = current.lstat().st_mode
            if not stat.S_ISDIR(mode):
                raise StoreError(f"Store directory must not be a link: {current}")
            if create:
                current.chmod(0o700)

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _path(self, pod: str, kind: str, digest: str) -> Path:
        value = _hex(digest)
        return self.pod_path(pod) / kind / "sha256" / value[:2] / value

    def _read(self, path: Path) -> bytes:
        from caiman.storage.transactions import check_read
        check_read(self)
        self._directory(path.parent)
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except OSError as exc:
            raise StoreError(f"Cannot safely read store object: {path}") from exc
        with os.fdopen(fd, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise StoreError(f"Store object is not a regular file: {path}")
            return stream.read()

    def _read_object(self, pod: str, kind: str, digest: str) -> bytes:
        content = self._read(self._path(pod, kind, digest))
        if _digest(content) != digest:
            raise StoreError(f"Store object digest mismatch: {digest}")
        return content

    def read_blob(self, pod: str, digest: str) -> bytes:
        return self._read_object(pod, "blobs", digest)

    def has_object(self, pod, kind, digest):
        path = self._path(pod, kind, digest)
        return path.exists() or path.is_symlink()

    def read_manifest(self, pod: str, digest: str) -> dict:
        content = self._read_object(pod, "manifests", digest)
        try:
            manifest = json.loads(content)
            if canonical_json(manifest) != content:
                raise StoreError("Manifest is not canonical")
            from caiman.storage.legacy import manifest_view
            manifest = manifest_view(manifest)
            _validate_manifest(manifest)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise StoreError("Invalid manifest JSON") from exc
        return manifest

    def _atomic_write(self, path: Path, content: bytes, *, immutable: bool) -> None:
        self._directory(path.parent, create=True)
        fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fchmod(stream.fileno(), 0o444 if immutable else 0o600)
                os.fsync(stream.fileno())
            if immutable:
                # A no-clobber publication; never modify an existing inode.
                try:
                    os.link(temporary, path, follow_symlinks=False)
                except FileExistsError:
                    if self._read(path) != content:
                        raise StoreError(f"Existing object digest mismatch: {path}")
                    if stat.S_IMODE(path.lstat().st_mode) != 0o444:
                        raise StoreError(f"Existing immutable object must have mode 0444: {path}")
            else:
                if path.is_symlink():
                    raise StoreError(f"Ref must not be a symlink: {path}")
                os.replace(temporary, path)
            self._fsync_directory(path.parent)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _write_object(self, pod: str, kind: str, digest: str, content: bytes) -> None:
        if _digest(content) != digest:
            raise StoreError("Prepared object digest mismatch")
        path = self._path(pod, kind, digest)
        self._atomic_write(path, content, immutable=True)

    def register(self, prepared: PreparedDocument) -> Registration:
        verify_prepared(prepared)
        _validate_manifest(prepared.manifest)
        with self.locked():
            return self._register(prepared)

    def _register(self, prepared: PreparedDocument) -> Registration:
        verify_prepared(prepared)
        manifest = prepared.manifest
        _validate_manifest(manifest)
        pod = self.pods.resolve(prepared.pod)["id"]
        content = canonical_json(manifest)
        if _digest(content) != prepared.manifest_digest or _digest(prepared.content) != prepared.blob_digest:
            raise StoreError("Prepared document digest mismatch")
        if manifest["files"][0] != {"path": document_path(prepared.source_path.name), "sha256": _hex(prepared.blob_digest), "size": len(prepared.content)}:
            raise StoreError("Manifest does not describe prepared document bytes")
        ref = self.pod_path(pod) / "refs" / "documents" / document_ref(manifest)
        if ref.exists() or ref.is_symlink():
            previous_digest = self._read(ref).decode('ascii').strip()
            previous = self.read_manifest(pod, previous_digest)
            if previous['files'][0]['sha256'] != _hex(prepared.blob_digest):
                raise StoreError('This document already contains a different file; use a new document name or version')
            from caiman.documents.ingest import METADATA_FIELDS
            current = previous
            if ({key: value for key, value in current.items() if key in METADATA_FIELDS}
                    != {key: value for key, value in manifest.items() if key in METADATA_FIELDS}
                    or current['files'] != manifest['files']):
                raise StoreError('This document is already registered; edit its metadata or use a new name or version')
            self.read_blob(pod, prepared.blob_digest)
            for kind, value in (('blobs', prepared.blob_digest), ('manifests', previous_digest)):
                if stat.S_IMODE(self._path(pod, kind, value).lstat().st_mode) != 0o444:
                    raise StoreError('Existing immutable object must have mode 0444')
            return Registration(previous_digest, prepared.blob_digest, ref, pod)
        # Source verification and all input checks precede the first mkdir.
        self.pods.ensure(pod)
        self._write_object(pod, "blobs", prepared.blob_digest, prepared.content)
        self._write_object(pod, "manifests", prepared.manifest_digest, content)
        from caiman.documents.revisions import DocumentRevisions
        from caiman.storage.transactions import publish
        current = DocumentRevisions(self).ref(pod, manifest['document_id'])
        publish(self, [{'path': path.relative_to(self.root).as_posix(), 'before': None,
                        'after': prepared.manifest_digest + '\n'} for path in (current, ref)])
        return Registration(prepared.manifest_digest, prepared.blob_digest, ref, pod)
