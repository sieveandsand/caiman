"""Prepare complete board/project snapshots and persist their immutable pins."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote

from caiman.configurations.models import board_is_legacy, validate_board, validate_project, validate_project_links
from caiman.documents.models import AccessLabel, canonical_json, is_schema, valid_identifier
from caiman.storage.store import AccessDenied, Store, StoreError, _component, _hex


@dataclass(frozen=True)
class PreparedConfig:
    kind: str
    manifest: dict
    digest: str
    compartments: tuple[str, ...]


@dataclass(frozen=True)
class ConfigRegistration:
    digest: str
    ref_paths: tuple[Path, ...]


def _digest(manifest: dict) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(manifest)).hexdigest()


def _kind(kind: str) -> None:
    if kind not in {"board", "project"}:
        raise StoreError("Configuration kind must be board or project")


def _scope(compartments: set[str] | None) -> set[str]:
    if compartments is not None and not isinstance(compartments, (set, frozenset, list, tuple)):
        raise StoreError("Compartments must be an explicit collection of names")
    if compartments is not None and any(not isinstance(name, str) for name in compartments):
        raise StoreError("Compartment names must be strings")
    names = set() if compartments is None else set(compartments)
    if any(not valid_identifier(name) or name == "public" for name in names):
        raise StoreError("Declare named compartments; public access is automatic")
    return names


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

    def _config_path(self, kind: str, name: str, version: str, compartment: str) -> Path:
        _kind(kind)
        return self.store.root / _component(compartment) / "refs" / (kind + "s") / _component(name) / _component(version)

    def _read_ref(self, path: Path) -> str:
        try:
            digest = self.store._read(path).decode("ascii").strip()
        except UnicodeError as error:
            raise StoreError("Invalid ref encoding") from error
        _hex(digest)
        return digest

    def _document(self, selector: dict, allowed: set[str], *, pinned: bool = False) -> tuple[dict, dict]:
        result = deepcopy(selector)
        if pinned and ("digest" not in result or "compartment" not in result):
            raise StoreError("Stored document selectors must contain immutable digest and compartment")
        if "ref" in result:
            relative = _ref_path(result["ref"])
        else:
            relative = None
        candidates = {result["compartment"]} if "compartment" in result else allowed | {"public"}
        if not candidates <= allowed | {"public"}:
            raise StoreError("Document belongs to an undeclared compartment")
        matches = []
        for compartment in sorted(candidates):
            if "digest" in result:
                digest = result["digest"]
                path = self.store._path(compartment, "manifests", digest)
            else:
                if relative is None:
                    raise StoreError("Document needs a ref or digest")
                path = self.store.root / _component(compartment) / "refs" / "documents" / relative
                if not path.exists() and not path.is_symlink():
                    continue
                digest = self._read_ref(path)
            if not path.exists() and not path.is_symlink():
                continue
            try:
                manifest = self.store.read_manifest(compartment, digest, allowed_compartments=allowed)
            except AccessDenied:
                if "compartment" in result:
                    raise
                continue
            entry = manifest["files"][0]
            blob = self.store.read_blob(compartment, "sha256:" + entry["sha256"])
            if len(blob) != entry["size"]:
                raise StoreError("Document blob size does not match its manifest")
            matches.append((compartment, digest, manifest))
        if not matches:
            raise StoreError("Document selector does not resolve inside declared compartments")
        if len({digest for _, digest, _ in matches}) != 1:
            raise StoreError("Ambiguous document ref; declare its compartment or digest")
        compartment, digest, manifest = matches[0]
        result.update(digest=digest, compartment=compartment)
        return result, manifest

    def _read_config(self, kind: str, compartment: str, digest: str, allowed: set[str]) -> dict:
        content = self.store._read_object(compartment, "manifests", digest)
        try:
            manifest = json.loads(content)
        except (UnicodeError, json.JSONDecodeError) as error:
            raise StoreError("Invalid configuration JSON") from error
        if not isinstance(manifest, dict) or not is_schema(kind, manifest.get("schema")):
            raise StoreError("Configuration schema does not match selected kind")
        validated = validate_board(manifest) if kind == "board" else validate_project(manifest)
        if canonical_json(validated) != content:
            raise StoreError("Configuration manifest is not canonical")
        if kind == "board":
            if compartment != "public":
                raise StoreError("Boards must be stored in public")
        elif compartment not in manifest["compartments"]:
            raise StoreError("Project labels do not match containing compartment")
        elif not AccessLabel(False, frozenset(manifest["compartments"])).permits(allowed):
            raise AccessDenied("All project compartments must be authorized")
        self._pin(kind, manifest, pinned=True)
        return manifest

    def _pin(self, kind: str, manifest: dict, *, pinned: bool = False) -> dict:
        result = deepcopy(manifest)
        if kind == "board":
            legacy = board_is_legacy(result)
            if not legacy and "documents" in result:
                # A board-level document is issued by the board's own vendor and
                # names the assembly, not a part: the board user guide, stackup
                # or assembly errata that no part instance can carry.
                documents = []
                for selector in result["documents"]:
                    selected, document = self._document(selector, set(), pinned=pinned)
                    if (document["issuer"], document.get("part")) != (result.get("vendor"), result["board"]):
                        raise StoreError("Board document issuer/part does not match this board assembly")
                    documents.append(selected)
                result["documents"] = documents
            for part in result["parts"]:
                documents = []
                for selector in part.get("documents", []):
                    selected, document = self._document(selector, set(), pinned=pinned)
                    if legacy:
                        matches = part["part"] == document["issuer"] + "/" + document.get("part", "")
                    else:
                        # Two field comparisons, not a rebuilt string: this is
                        # also where a document carrying a program rather than a
                        # part is rejected, which the packed form could not say.
                        matches = (document["issuer"], document.get("part")) == (part["vendor"], part["part"])
                    if not matches:
                        raise StoreError("Board document issuer/part does not match its part instance")
                    revisions = document.get("silicon_revisions", [])
                    if revisions and "silicon_revision" in part and part["silicon_revision"] not in revisions:
                        raise StoreError("Board silicon revision is outside document applicability")
                    documents.append(selected)
                part["documents"] = documents
            return result
        allowed = set(result["compartments"])
        board_selector = result["board"]
        if "digest" not in board_selector:
            if pinned:
                raise StoreError("Stored board selector must contain immutable digest")
            board_selector["digest"] = self._read_ref(self._config_path("board", board_selector["name"], board_selector["version"], "public"))
        board = self._read_config("board", "public", board_selector["digest"], set())
        if board["board"] != board_selector["name"] or board["version"] != board_selector["version"]:
            raise StoreError("Pinned board identity does not match project declaration")
        governing = []
        for field in ("documents", "precedence"):
            documents = []
            for selector in result.get(field, []):
                selected, _ = self._document(selector, allowed, pinned=pinned)
                documents.append(selected)
                governing.append(selected)
            result[field] = documents
        for feature in result.get("features", []):
            documents = []
            for selector in feature.get("governed_by", []):
                # Bind feature declarations to the already selected project set,
                # never to a newer target of a mutable document ref.
                matches = [entry for entry in governing
                           if (("digest" in selector and entry["digest"] == selector["digest"])
                               or ("digest" not in selector and entry.get("ref") == selector.get("ref")))
                           and ("compartment" not in selector or entry["compartment"] == selector["compartment"])]
                if not matches:
                    raise StoreError("Feature governing document must belong to project documents or precedence")
                if len({entry["digest"] for entry in matches}) != 1:
                    raise StoreError("Ambiguous feature governing ref within pinned project documents")
                selected = deepcopy(selector)
                if not pinned:
                    selected.update(digest=matches[0]["digest"], compartment=matches[0]["compartment"])
                selected, _ = self._document(selected, allowed, pinned=pinned)
                documents.append(selected)
            if "governed_by" in feature:
                feature["governed_by"] = documents
        validate_project_links(result, board)
        return result

    def prepare(self, kind: str, data: dict) -> PreparedConfig:
        _kind(kind)
        manifest = validate_board(data) if kind == "board" else validate_project(data)
        manifest = self._pin(kind, manifest)
        compartments = ("public",) if kind == "board" else tuple(sorted(manifest["compartments"]))
        return PreparedConfig(kind, manifest, _digest(manifest), compartments)

    def register(self, prepared: PreparedConfig) -> ConfigRegistration:
        _kind(prepared.kind)
        manifest = validate_board(prepared.manifest) if prepared.kind == "board" else validate_project(prepared.manifest)
        if _digest(manifest) != prepared.digest or manifest != self._pin(prepared.kind, manifest, pinned=True):
            raise StoreError("Configuration changed after review; prepare it again")
        compartments = ("public",) if prepared.kind == "board" else tuple(sorted(manifest["compartments"]))
        if prepared.compartments != compartments:
            raise StoreError("Configuration compartment labels changed after review")
        refs = tuple(self._config_path(prepared.kind, manifest[prepared.kind], manifest["version"], compartment)
                     for compartment in compartments)
        for compartment in compartments:
            self.store._write_object(compartment, "manifests", prepared.digest, canonical_json(manifest))
        for ref in refs:
            self.store._atomic_write(ref, (prepared.digest + "\n").encode(), immutable=False)
        return ConfigRegistration(prepared.digest, refs)

    def load(self, kind: str, name: str, version: str, *, compartments: set[str] | None = None) -> dict:
        _kind(kind)
        allowed = _scope(compartments)
        locations = {"public"} if kind == "board" else allowed
        found = []
        for compartment in sorted(locations):
            path = self._config_path(kind, name, version, compartment)
            if path.exists() or path.is_symlink():
                digest = self._read_ref(path)
                manifest = self._read_config(kind, compartment, digest, allowed)
                if manifest[kind] != name or manifest["version"] != version:
                    raise StoreError("Configuration ref points to a different identity")
                found.append((digest, manifest))
        if not found:
            raise StoreError("Configuration version not found in declared compartments")
        if len({digest for digest, _ in found}) != 1:
            raise StoreError("Ambiguous configuration version across compartments")
        return found[0][1]

    def load_digest(self, kind: str, digest: str, *, compartment: str = "public",
                    compartments: set[str] | None = None) -> dict:
        """Read an explicit immutable selection without resolving mutable refs."""
        _kind(kind)
        _hex(digest)
        allowed = _scope(compartments)
        if not valid_identifier(compartment):
            raise StoreError("Compartment must be a valid name")
        if kind == "board":
            if compartment != "public":
                raise StoreError("Boards must be loaded from public storage")
        elif compartment == "public" or compartment not in allowed:
            raise StoreError("Project location must belong to explicitly declared compartments")
        return self._read_config(kind, compartment, digest, allowed)

    def list_versions(self, kind: str, name: str, *, compartments: set[str] | None = None) -> list[str]:
        _kind(kind)
        allowed = _scope(compartments)
        versions = []
        for compartment in sorted({"public"} if kind == "board" else allowed):
            directory = self._config_path(kind, name, "placeholder", compartment).parent
            if not directory.exists() and not directory.is_symlink():
                continue
            self.store._directory(directory)
            for path in directory.iterdir():
                version = unquote(path.name)
                if _component(version) != path.name:
                    raise StoreError("Noncanonical configuration version ref")
                try:
                    self.load(kind, name, version, compartments=allowed)
                except AccessDenied:
                    continue
                if version not in versions:
                    versions.append(version)
        return versions

    def list_configs(self, kind: str, *, compartments: set[str] | None = None) -> list[dict]:
        """List visible named snapshots in explicitly selected compartments.

        Each record contains name, version, digest, compartment, and manifest.
        Identical copies across compartments appear once. Versions are opaque;
        discovery order carries no lineage or newest-version meaning.
        """
        _kind(kind)
        allowed = _scope(compartments)
        records = []
        seen = set()
        for compartment in sorted({"public"} if kind == "board" else allowed):
            directory = self.store.root / _component(compartment) / "refs" / (kind + "s")
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
                    try:
                        manifest = self._read_config(kind, compartment, digest, allowed)
                    except AccessDenied:
                        continue
                    if manifest[kind] != name or manifest["version"] != version:
                        raise StoreError("Configuration ref points to a different identity")
                    identity = (name, version, digest)
                    if identity not in seen:
                        records.append({"name": name, "version": version, "digest": digest,
                                        "compartment": compartment, "manifest": manifest})
                        seen.add(identity)
        return records

    def list_documents(self, *, compartments: set[str] | None = None) -> list[dict]:
        allowed = _scope(compartments)
        records = []
        for compartment in sorted(allowed | {"public"}):
            directory = self.store.root / _component(compartment) / "refs" / "documents"
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
                try:
                    selector, manifest = self._document({"ref": ref, "compartment": compartment}, allowed)
                except AccessDenied:
                    continue
                records.append({"compartment": compartment, "digest": selector["digest"], "ref": ref, "manifest": manifest})
        return records
