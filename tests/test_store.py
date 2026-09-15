"""Synthetic content only: registration boundaries and crash-safe publication."""
import copy
import hashlib
import os
from dataclasses import replace

import pytest

from caiman.ingest import prepare_document
from caiman.models import canonical_json
from caiman.store import AccessDenied, Store, StoreError


def prepared(tmp_path, *, public=True, compartments=(), version="rev/one"):
    source = tmp_path / "manual.md"
    source.write_bytes(b"# Synthetic manual\r\n\r\n## Registers\r\n| Name | Value |\r\n| --- | --- |\r\n| CTRL | 0 |\r\n")
    return prepare_document(source, {
        "issuer": "synthetic", "part": "chip", "doc_type": "manual",
        "version": version, "structure": "prose",
        "labels": {"public": public, "compartments": list(compartments)},
    })


def test_unchanged_bytes_and_immutable_objects(tmp_path):
    document = prepared(tmp_path)
    store = Store(tmp_path / "store")
    result = store.register(document)
    assert store.read_blob("public", result.blob_digest) == document.content
    assert store.read_manifest("public", result.manifest_digest) == document.manifest
    assert result.ref_path.name == "rev%2Fone"
    assert result.ref_path.read_text().strip() == result.manifest_digest
    assert store.register(document) == result
    for path in (tmp_path / "store").rglob("*"):
        if path.is_dir():
            assert path.stat().st_mode & 0o777 == 0o700
        elif "sha256" in path.parts:
            assert path.stat().st_mode & 0o777 == 0o444


@pytest.mark.parametrize("labels", [{}, {"public": False}, {"public": False, "compartments": []}, {"public": True, "compartments": ["alpha"]}])
def test_invalid_or_dropped_labels_write_nothing(tmp_path, labels):
    document = prepared(tmp_path)
    manifest = copy.deepcopy(document.manifest)
    manifest["labels"] = labels
    store = Store(tmp_path / "store")
    with pytest.raises(ValueError):
        store.register(replace(document, manifest=manifest))
    assert not store.root.exists()


def test_source_changed_after_review_writes_nothing(tmp_path):
    document = prepared(tmp_path)
    document.source_path.write_text("# Changed\n")
    store = Store(tmp_path / "store")
    with pytest.raises(ValueError):
        store.register(document)
    assert not store.root.exists()


def test_labels_change_identity_and_separate_storage(tmp_path):
    public = prepared(tmp_path)
    private = prepared(tmp_path, public=False, compartments=("alpha", "program"))
    store = Store(tmp_path / "store")
    a, b = store.register(public), store.register(private)
    assert a.blob_digest == b.blob_digest
    assert a.manifest_digest != b.manifest_digest
    assert b.compartments == ("alpha", "program")
    with pytest.raises(AccessDenied, match="authorized"):
        store.read_manifest("alpha", b.manifest_digest)
    assert store.read_manifest("alpha", b.manifest_digest, allowed_compartments={"alpha", "program"})["labels"]["compartments"] == ["alpha", "program"]
    blobs = list(store.root.glob("*/blobs/sha256/*/*"))
    assert len({p.stat().st_ino for p in blobs}) == 3


def test_corruption_blocks_read_and_registration(tmp_path):
    document = prepared(tmp_path)
    store = Store(tmp_path / "store")
    result = store.register(document)
    blob = next(store.root.glob("public/blobs/sha256/*/*"))
    blob.chmod(0o600)
    blob.write_bytes(b"corrupt")
    with pytest.raises(StoreError, match="digest"):
        store.read_blob("public", result.blob_digest)
    with pytest.raises(StoreError, match="digest"):
        store.register(document)


def test_symlink_directory_rejected(tmp_path):
    document = prepared(tmp_path)
    store = Store(tmp_path / "store")
    store.root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "public").symlink_to(outside, target_is_directory=True)
    with pytest.raises(StoreError, match="directory"):
        store.register(document)
    assert list(outside.iterdir()) == []


def test_failed_manifest_publish_leaves_no_ref(tmp_path, monkeypatch):
    document = prepared(tmp_path)
    store = Store(tmp_path / "store")
    original = store._write_object
    def fail_manifest(compartment, kind, digest, content):
        if kind == "manifests":
            raise OSError("simulated disk failure")
        return original(compartment, kind, digest, content)
    monkeypatch.setattr(store, "_write_object", fail_manifest)
    with pytest.raises(OSError, match="simulated"):
        store.register(document)
    assert not list(store.root.glob("*/refs/documents/**/*"))


def test_existing_writable_object_rejected(tmp_path):
    document = prepared(tmp_path)
    store = Store(tmp_path / "store")
    store.register(document)
    blob = next(store.root.glob("public/blobs/sha256/*/*"))
    blob.chmod(0o644)
    with pytest.raises(StoreError, match="0444"):
        store.register(document)


def test_read_rejects_manifest_with_dropped_compartment(tmp_path):
    document = prepared(tmp_path, public=False, compartments=("alpha",))
    store = Store(tmp_path / "store")
    store.register(document)
    manifest = copy.deepcopy(document.manifest)
    manifest["labels"]["compartments"] = []
    content = canonical_json(manifest)
    digest = "sha256:" + hashlib.sha256(content).hexdigest()
    store._write_object("alpha", "manifests", digest, content)
    with pytest.raises(ValueError):
        store.read_manifest("alpha", digest, allowed_compartments={"alpha"})


def test_wrong_containing_compartment_is_corruption_not_access_denial(tmp_path):
    document = prepared(tmp_path, public=False, compartments=("alpha",))
    store = Store(tmp_path / "store")
    result = store.register(document)
    store._write_object("beta", "manifests", result.manifest_digest, canonical_json(document.manifest))
    with pytest.raises(StoreError) as error:
        store.read_manifest("beta", result.manifest_digest, allowed_compartments={"beta"})
    assert not isinstance(error.value, AccessDenied)


def test_ref_hardlink_does_not_overwrite_other_file(tmp_path):
    document = prepared(tmp_path)
    store = Store(tmp_path / "store")
    first = store.register(document)
    outside = tmp_path / "other-ref"
    os.link(first.ref_path, outside)
    original = outside.read_bytes()
    document.source_path.write_bytes(b"# Different\nChanged\n")
    metadata = {key: document.manifest[key] for key in ("issuer", "part", "doc_type", "version", "structure", "labels")}
    store.register(prepare_document(document.source_path, metadata))
    assert outside.read_bytes() == original
    assert first.ref_path.read_bytes() != original


def test_ref_repoint_preserves_previous_digest(tmp_path):
    first = prepared(tmp_path)
    store = Store(tmp_path / "store")
    a = store.register(first)
    first.source_path.write_bytes(b"# Synthetic manual\n\n## Changed\nDifferent content\n")
    metadata = {key: first.manifest[key] for key in ("issuer", "part", "doc_type", "version", "structure", "labels")}
    second = prepare_document(first.source_path, metadata)
    b = store.register(second)
    assert a.ref_path == b.ref_path
    assert a.ref_path.read_text().strip() == b.manifest_digest
    assert store.read_blob("public", a.blob_digest) == first.content
    assert store.read_manifest("public", a.manifest_digest) == first.manifest


@pytest.mark.parametrize("version", [".", ".."])
def test_dot_version_encoded_as_opaque_label(tmp_path, version):
    document = prepared(tmp_path, version=version)
    store = Store(tmp_path / "store")
    registered = store.register(document)
    assert registered.ref_path.name == "%2E" * len(version)
    assert registered.ref_path.is_relative_to(store.root)
    assert store.read_manifest("public", registered.manifest_digest)["version"] == version


@pytest.mark.parametrize("digest", ["../escape", "sha256:" + "../" * 22, "sha256:" + "A" * 64])
def test_invalid_digest_rejected(tmp_path, digest):
    with pytest.raises(StoreError):
        Store(tmp_path / "store").read_blob("public", digest)
