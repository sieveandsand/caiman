"""Prepare complete board/project snapshots and persist their immutable pins."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

from caiman.configurations.models import (project_boards, validate_board, validate_project,
                                          validate_project_links)
from caiman.documents.models import canonical_json, is_schema, valid_identifier
from caiman.storage.legacy import manifest_view
from caiman.storage.store import Store, StoreError, _component, _hex, document_ref


@dataclass(frozen=True)
class PreparedConfig:
    kind: str
    manifest: dict
    digest: str
    pod: str


@dataclass(frozen=True)
class ConfigRegistration:
    digest: str
    ref_paths: tuple[Path, ...]


def _digest(manifest: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(manifest)).hexdigest()


def _kind(kind: str) -> None:
    if kind not in {"board", "project"}:
        raise StoreError("Configuration kind must be board or project")


def _ref_path(ref: str) -> Path:
    if not isinstance(ref, str):
        raise StoreError("Document ref must be a relative encoded path")
    parts = ref.split("/")
    if len(parts) < 3 or any(not part or _component(unquote(part)) != part for part in parts):
        raise StoreError("Document ref must use canonical encoded path components")
    return Path(*parts)


class ConfigurationService:
    def __init__(self, store: Store):
        self.store = store

    def _config_path(self, kind: str, name: str, version: str, pod: str) -> Path:
        _kind(kind)
        return self.store.pod_path(pod) / "refs" / (kind + "s") / _component(name) / _component(version)

    def _read_ref(self, path: Path) -> str:
        try:
            digest = self.store._read(path).decode("ascii").strip()
        except UnicodeError as error:
            raise StoreError("Invalid ref encoding") from error
        _hex(digest)
        return digest

    def _document(self, selector: dict, *, pinned: bool = False, historical: bool = False, owner=None) -> tuple[dict, dict]:
        selected, _, manifest = self._resolve_document(selector, pinned=pinned, historical=historical, owner=owner)
        return selected, manifest

    def _resolve_document(self, selector: dict, *, pinned=False, historical=False, owner=None):
        """Return the reference, actual stored revision digest, and manifest together."""
        from caiman.documents.revisions import DocumentRevisions
        result = deepcopy(selector)
        if ('document' in result) != ('blob' in result):
            raise StoreError('Document references require both document ID and blob')
        if 'document' in result and ('ref' in result or 'digest' in result):
            raise StoreError('Use either document ID and blob, or a ref/manifest digest')
        if pinned and ('pod' not in result or not (
                {'document', 'blob'} <= result.keys() or 'digest' in result)):
            raise StoreError('Stored document selectors must contain a document ID, blob and pod')
        relative = _ref_path(result['ref']) if 'ref' in result else None
        candidates = {self.store.pods.resolve(result['pod'])['id']} if 'pod' in result else self.store.pods.selected()
        if owner is not None:
            if 'pod' in result:
                self.store.pods.check_reference(owner, result['pod'])
            candidates &= self.store.pods.reference_pods(owner)
        matches = []
        for pod in sorted(candidates):
            if 'document' in result:
                if 'blob' not in result:
                    raise StoreError('Document references must pin a blob')
                _hex(result['blob'])
                head = DocumentRevisions(self.store).ref(pod, result['document'])
                if not head.exists() and not head.is_symlink():
                    continue
                value, manifest = DocumentRevisions(self.store).current(pod, result['document'], result['blob'])
            else:
                if 'digest' in result:
                    value = result['digest']
                    if not self.store.has_object(pod, 'manifests', value):
                        continue
                else:
                    if relative is None:
                        raise StoreError('Document needs a ref, manifest digest or document ID')
                    path = self.store.pod_path(pod) / 'refs' / 'documents' / relative
                    if not path.exists() and not path.is_symlink():
                        continue
                    value = self._read_ref(path)
                manifest = self.store.read_manifest(pod, value)
                if not historical and 'document_id' in manifest:
                    value, manifest = DocumentRevisions(self.store).current(
                        pod, manifest['document_id'], 'sha256:' + manifest['files'][0]['sha256'])
            entry = manifest['files'][0]
            blob = self.store.read_blob(pod, 'sha256:' + entry['sha256'])
            if len(blob) != entry['size']:
                raise StoreError('Document blob size does not match its manifest')
            matches.append((pod, value, manifest))
        if not matches:
            raise StoreError('Document dependency is unavailable locally; add its pod or sync it')
        if len(matches) != 1:
            raise StoreError('Ambiguous document ref; declare its pod or digest')
        pod, value, manifest = matches[0]
        result['pod'] = pod
        if 'document_id' in manifest:
            result.pop('digest', None)
            result.pop('ref', None)
            result.update(document=manifest['document_id'], blob='sha256:' + manifest['files'][0]['sha256'])
        else:
            result['digest'] = value
        return result, value, manifest

    def document_record(self, selector, *, pinned=False):
        selected, value, manifest = self._resolve_document(selector, pinned=pinned)
        return {'pod': selected['pod'], 'digest': value,
                'ref': document_ref(manifest).as_posix(),
                'pod_name': self.store.pod_name(selected['pod']), 'manifest': manifest}

    def _read_config(self, kind: str, pod: str, digest: str, allowed: set[str]) -> dict:
        content = self.store._read_object(pod, "manifests", digest)
        try:
            manifest = json.loads(content)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise StoreError("Invalid configuration JSON") from error
        if not isinstance(manifest, dict) or not is_schema(kind, manifest.get("schema")):
            raise StoreError("Configuration schema does not match selected kind")
        if canonical_json(manifest) != content:
            raise StoreError("Configuration manifest is not canonical")
        manifest = manifest_view(manifest)
        validated = validate_board(manifest) if kind == "board" else validate_project(manifest)
        if validated != manifest:
            raise StoreError("Configuration manifest is not canonical")
        # Validate immutable pin shape without requiring dependencies to be local.
        pins = list(manifest.get('documents', []))
        if kind == 'board':
            for part in manifest['parts']:
                pins.extend(part.get('documents', []))
        else:
            pins.extend(manifest.get('precedence', []))
            for feature in manifest['features']:
                pins.extend(feature.get('governed_by', []))
            for board in project_boards(manifest):
                if 'digest' not in board:
                    raise StoreError('Stored board selector must contain immutable digest')
        for pin in pins:
            if 'pod' not in pin or not ({'document', 'blob'} <= pin.keys() or 'digest' in pin):
                raise StoreError('Stored document selectors must contain document ID, blob and pod')
        return manifest

    def _pin(self, kind: str, manifest: dict, *, owner: str, pinned: bool = False) -> dict:
        result = deepcopy(manifest)
        if kind == "board":
            if 'documents' in result:
                result['documents'] = [self._document(pin, pinned=pinned, owner=owner)[0] for pin in result['documents']]
            for part in result['parts']:
                part['documents'] = [self._document(pin, pinned=pinned, owner=owner)[0] for pin in part.get('documents', [])]
            return result
        allowed = self.store.pods.reference_pods(owner)
        boards = []
        # Each selector is resolved to its own digest once, here; a later
        # repoint of the version ref never reaches a registered project (I-4).
        for board_selector in project_boards(result):
            location = board_selector.get("pod")
            if location is not None:
                self.store.pods.check_reference(owner, location)
            if "digest" not in board_selector:
                if pinned:
                    raise StoreError("Stored board selector must contain immutable digest")
                matches = [r for r in self.list_configs("board", pods=[location] if location else allowed)
                           if (r["name"], r["version"]) == (board_selector["name"], board_selector["version"])]
                if len(matches) != 1:
                    raise StoreError("Board dependency is missing or ambiguous; choose its pod")
                board_selector.update(digest=matches[0]["digest"], pod=matches[0]["pod"])
            location = board_selector.get("pod", "public")  # Legacy boards lived in public.
            self.store.pods.check_reference(owner, location)
            board = self._read_config("board", location, board_selector["digest"], allowed)
            if not pinned or "pod" in board_selector:
                board_selector["pod"] = self.store.pods.resolve(location)["id"]
            self._pin("board", board, owner=location, pinned=True)
            if board["board"] != board_selector["name"] or board["version"] != board_selector["version"]:
                raise StoreError("Pinned board identity does not match project declaration")
            boards.append(board)
        governing = []
        for field in ("documents", "precedence"):
            if field not in result:
                continue
            documents = []
            for selector in result.get(field, []):
                selected, _ = self._document(selector, pinned=pinned, owner=owner)
                documents.append(selected)
                governing.append(selected)
            result[field] = documents
        for feature in result.get("features", []):
            documents = []
            for selector in feature.get("governed_by", []):
                selected, _ = self._document(selector, pinned=pinned, owner=owner)
                def identity(pin):
                    return (pin['pod'], pin.get('document', pin.get('digest')), pin.get('blob'))
                if not any(identity(selected) == identity(entry) for entry in governing):
                    raise StoreError("Feature governing document must belong to the project's documents")
                documents.append(selected)
            if "governed_by" in feature:
                feature["governed_by"] = documents
        validate_project_links(result, boards)
        return result

    def prepare(self, kind: str, data: dict, *, pod: str | None = None) -> PreparedConfig:
        _kind(kind)
        data = deepcopy(data)
        # Pod is draft/registration context, never a document access label.
        target = pod or data.pop("pod", None) or self.store.pods.default
        data.pop("pod", None)
        if "compartments" in data:
            owners = data["compartments"]
            if len(owners) != 1 and pod is None:
                raise StoreError("Choose one owning pod for this legacy project")
            target = pod or owners[0]
            data = manifest_view(data)
        data = manifest_view(data)
        location = self.store.pods.resolve(target)["id"]
        manifest = validate_board(data) if kind == "board" else validate_project(data)
        manifest = self._pin(kind, manifest, owner=location)
        # Different input refs/revisions may resolve to the same stable document.
        manifest = validate_board(manifest) if kind == 'board' else validate_project(manifest)
        return PreparedConfig(kind, manifest, _digest(manifest), location)

    def register(self, prepared: PreparedConfig, *, replaces: dict | None = None,
                 require_new_label: bool = False) -> ConfigRegistration:
        """Write a reviewed snapshot and point its name/version refs at it.

        ``replaces`` is the edited selection (``manifest`` and ``digest``). Its
        refs move to the new snapshot instead of staying behind as a second
        entry; the old manifest object is kept, so digest pins survive (I-4).
        ``require_new_label`` preserves the source ref while refusing to repoint
        an existing target label, as when a board edit declares a new version.
        """
        manifest = validate_board(prepared.manifest) if prepared.kind == 'board' else validate_project(prepared.manifest)
        if _digest(manifest) != prepared.digest or manifest != self._pin(prepared.kind, manifest, owner=prepared.pod, pinned=True):
            raise StoreError('Configuration changed after review; prepare it again')
        with self.store.locked():
            return self._register(prepared, replaces=replaces, require_new_label=require_new_label)

    def _register(self, prepared, *, replaces=None, require_new_label=False):
        _kind(prepared.kind)
        manifest = validate_board(prepared.manifest) if prepared.kind == "board" else validate_project(prepared.manifest)
        if _digest(manifest) != prepared.digest or manifest != self._pin(prepared.kind, manifest, owner=prepared.pod, pinned=True):
            raise StoreError("Configuration changed after review; prepare it again")
        pods = (self.store.pods.resolve(prepared.pod)["id"],)
        refs = tuple(self._config_path(prepared.kind, manifest[prepared.kind], manifest["version"], pod)
                     for pod in pods)
        if require_new_label and any(ref.exists() or ref.is_symlink() for ref in refs):
            raise StoreError("Another configuration already uses this name and version")
        stale = ()
        if replaces is not None:
            previous = replaces["manifest"]
            if (previous[prepared.kind] != manifest[prepared.kind] or previous["version"] != manifest["version"]
                or prepared.pod != replaces.get("pod", prepared.pod)):
                if any(ref.exists() or ref.is_symlink() for ref in refs):
                    raise StoreError("Another configuration already uses this name and version")
            opened_ref = self._config_path(prepared.kind, previous[prepared.kind], previous['version'],
                                           replaces.get('pod', prepared.pod))
            if not opened_ref.exists() or self._read_ref(opened_ref) != replaces['digest']:
                raise StoreError('Configuration changed since opening; reopen it before saving')
            old = (replaces.get("pod", prepared.pod),)
            stale = tuple(path for pod in old
                          if (path := self._config_path(prepared.kind, previous[prepared.kind], previous["version"],
                                                        pod)) not in refs)
        self.store.pods.ensure(prepared.pod)
        for pod in pods:
            self.store._write_object(pod, "manifests", prepared.digest, canonical_json(manifest))
        for ref in refs:
            self.store._atomic_write(ref, (prepared.digest + "\n").encode(), immutable=False)
        for path in stale:
            # Only the ref being edited moves; one repointed elsewhere meanwhile stays.
            if (path.exists() or path.is_symlink()) and self._read_ref(path) == replaces["digest"]:
                self._remove_ref(path)
        return ConfigRegistration(prepared.digest, refs)

    def _remove_ref(self, path: Path) -> None:
        path.unlink()
        self.store._fsync_directory(path.parent)
        try:
            path.parent.rmdir()
        except OSError:
            pass

    def unregister(self, kind: str, manifest: dict, digest: str, *, pod: str = "public") -> tuple[Path, ...]:
        """Remove a configuration's name/version refs; its manifest object stays.

        Objects are never deleted (STORAGE.md §8.5), so anything pinned to the
        digest still resolves (I-4). Refuses if any ref no longer names
        ``digest``: the configuration changed after it was shown.
        """
        with self.store.locked():
            return self._unregister(kind, manifest, digest, pod=pod)

    def _unregister(self, kind, manifest, digest, *, pod):
        _kind(kind)
        _hex(digest)
        pods = (pod,)
        refs = tuple(path for pod in pods
                     if (path := self._config_path(kind, manifest[kind], manifest["version"], pod)).exists()
                     or path.is_symlink())
        if not refs:
            raise StoreError("Configuration version not found in the selected pods")
        if any(self._read_ref(path) != digest for path in refs):
            raise StoreError("Configuration changed since it was opened; reopen it before deleting")
        for path in refs:
            self._remove_ref(path)
        return refs

    def load(self, kind: str, name: str, version: str, *, pods: set[str] | None = None) -> dict:
        _kind(kind)
        allowed = self.store.pods.selected(pods)
        locations = allowed
        found = []
        for pod in sorted(locations):
            path = self._config_path(kind, name, version, pod)
            if path.exists() or path.is_symlink():
                digest = self._read_ref(path)
                manifest = self._read_config(kind, pod, digest, allowed)
                if manifest[kind] != name or manifest["version"] != version:
                    raise StoreError("Configuration ref points to a different identity")
                found.append((digest, manifest))
        if not found:
            raise StoreError("Configuration version not found in the selected pods")
        if len(found) != 1:
            raise StoreError("Ambiguous configuration version across pods")
        return found[0][1]

    def load_digest(self, kind: str, digest: str, *, pod: str = "public",
                    pods: set[str] | None = None) -> dict:
        """Read an explicit immutable selection without resolving mutable refs."""
        _kind(kind)
        _hex(digest)
        allowed = self.store.pods.selected(pods)
        if not valid_identifier(pod):
            raise StoreError("Pod must be a valid name")
        return self._read_config(kind, pod, digest, allowed)

    def list_versions(self, kind: str, name: str, *, pods: set[str] | None = None) -> list[str]:
        _kind(kind)
        allowed = self.store.pods.selected(pods)
        versions = []
        for pod in sorted(allowed):
            directory = self._config_path(kind, name, "placeholder", pod).parent
            if not directory.exists() and not directory.is_symlink():
                continue
            self.store._directory(directory)
            for path in directory.iterdir():
                version = unquote(path.name)
                if _component(version) != path.name:
                    raise StoreError("Noncanonical configuration version ref")
                self._read_config(kind, pod, self._read_ref(path), allowed)
                if version not in versions:
                    versions.append(version)
        return versions

    def list_configs(self, kind: str, *, pods: set[str] | None = None) -> list[dict]:
        """List named snapshots in locally available pods.

        Each record contains name, version, digest, pod, and manifest.
        Each owning pod is a separate catalog location. Versions are opaque;
        discovery order carries no lineage or newest-version meaning.
        """
        _kind(kind)
        allowed = self.store.pods.selected(pods)
        records = []
        seen = set()
        for pod in sorted(allowed):
            directory = self.store.pod_path(pod) / "refs" / (kind + "s")
            if not directory.exists() and not directory.is_symlink():
                continue
            self.store._directory(directory)
            for named in directory.iterdir():
                name = unquote(named.name)
                if not valid_identifier(name) or _component(name) != named.name:
                    raise StoreError("Noncanonical configuration name ref")
                self.store._directory(named)
                for path in named.iterdir():
                    version = unquote(path.name)
                    if _component(version) != path.name:
                        raise StoreError("Noncanonical configuration version ref")
                    digest = self._read_ref(path)
                    manifest = self._read_config(kind, pod, digest, allowed)
                    if manifest[kind] != name or manifest["version"] != version:
                        raise StoreError("Configuration ref points to a different identity")
                    identity = (pod, name, version, digest)
                    if identity not in seen:
                        records.append({"name": name, "version": version, "digest": digest,
                                        "pod": pod, "pod_name": self.store.pod_name(pod), "manifest": manifest})
                        seen.add(identity)
        return records

    def list_documents(self, *, pods: set[str] | None = None) -> list[dict]:
        allowed = self.store.pods.selected(pods)
        records = []
        for pod in sorted(allowed):
            directory = self.store.pod_path(pod) / "refs" / "documents"
            if not directory.exists() and not directory.is_symlink():
                continue
            self.store._directory(directory)
            for path in sorted(directory.rglob("*")):
                if path.is_symlink():
                    raise StoreError("Document refs must not contain symlinks")
                if path.is_dir():
                    self.store._directory(path)
                    continue
                ref = path.relative_to(directory).as_posix()
                records.append(self.document_record({"ref": ref, "pod": pod}))
        return records
