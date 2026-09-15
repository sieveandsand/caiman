"""Synthetic board and customer snapshots exercise immutable pin boundaries."""
from copy import deepcopy

import pytest

from caiman.config_store import ConfigurationService
from caiman.ingest import prepare_document
from caiman.store import AccessDenied, Store, StoreError


def document(tmp_path, store, *, compartments=(), version="v1", text="# Manual\n\n## Registers\nSynthetic text\n", part="chip", silicon_revisions=()):
    path = tmp_path / "synthetic.md"
    path.write_text(text)
    prepared = prepare_document(path, {
        "issuer": "synthetic", "part": part, "doc_type": "manual", "version": version,
        "structure": "prose", "labels": {"public": not compartments, "compartments": list(compartments)},
        "silicon_revisions": list(silicon_revisions),
    })
    registered = store.register(prepared)
    return {"ref": registered.ref_path.relative_to(store.root / registered.compartments[0] / "refs" / "documents").as_posix()}


def board(selector):
    return {"board": "demo", "version": "v/one", "parts": [
        {"role": "main", "part": "synthetic/chip", "documents": [selector]}], "links": []}


def project(selector, *, compartments=("alpha",)):
    return {"project": "flight", "version": "sample/A", "customer": "Synthetic customer",
            "compartments": list(compartments), "board": {"name": "demo", "version": "v/one"},
            "spec_set": "release A", "documents": [selector], "precedence": [selector],
            "features": [{"name": "flash", "scope": "required", "governed_by": [selector], "realized_on": ["main"]}]}


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path / "store")
    service = ConfigurationService(store)
    ref = document(tmp_path, store)
    service.register(service.prepare("board", board(ref)))
    return store, service, ref


def test_board_pins_survive_document_ref_repoint(tmp_path, setup):
    store, service, ref = setup
    first = service.load("board", "demo", "v/one")
    digest = first["parts"][0]["documents"][0]["digest"]
    document(tmp_path, store, text="# Replacement\nNew bytes\n")
    assert service.load("board", "demo", "v/one") == first
    prepared = service.prepare("board", board(ref))
    assert prepared.manifest["parts"][0]["documents"][0]["digest"] != digest
    assert service.list_versions("board", "demo") == ["v/one"]


def test_project_whole_snapshot_and_pins(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha",), part="spec")
    prepared = service.prepare("project", project(selector))
    snapshot = deepcopy(prepared.manifest)
    result = service.register(prepared)
    assert len(result.ref_paths) == 1
    assert service.load("project", "flight", "sample/A", compartments={"alpha"}) == snapshot
    assert service.list_versions("project", "flight", compartments={"alpha"}) == ["sample/A"]
    assert service.list_versions("project", "flight") == []
    for location in (snapshot["documents"][0], snapshot["precedence"][0], snapshot["features"][0]["governed_by"][0]):
        assert location["digest"].startswith("sha256:")
        assert location["compartment"] == "alpha"
    assert snapshot["board"]["digest"].startswith("sha256:")
    with pytest.raises(StoreError):
        service.load("project", "flight", "sample/A")


def test_project_board_ref_repoint_does_not_change_prepared_pin(tmp_path, setup):
    store, service, ref = setup
    selector = document(tmp_path, store, compartments=("alpha",), part="spec")
    prepared = service.prepare("project", project(selector))
    original = prepared.manifest["board"]["digest"]
    data = board(ref)
    data["parts"][0]["refdes"] = "U99"
    newer = service.register(service.prepare("board", data))
    assert newer.digest != original
    service.register(prepared)
    assert service.load("project", "flight", "sample/A", compartments={"alpha"})["board"]["digest"] == original


def test_feature_ref_uses_project_pin_even_after_ref_repoint(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha",), part="spec")
    earlier = service.prepare("project", project(selector)).manifest["documents"][0]
    document(tmp_path, store, compartments=("alpha",), part="spec", text="# Replacement\nDifferent\n")
    data = project(selector)
    data["documents"] = [earlier]
    data["precedence"] = [earlier]
    prepared = service.prepare("project", data)
    assert prepared.manifest["features"][0]["governed_by"][0]["digest"] == earlier["digest"]
    document(tmp_path, store, compartments=("alpha",), part="spec", text="# Again\nDifferent again\n")
    service.register(prepared)
    assert service.load("project", "flight", "sample/A", compartments={"alpha"})["documents"][0]["digest"] == earlier["digest"]


def test_cross_customer_and_public_board_rejected(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("beta",), part="spec")
    with pytest.raises(ValueError):
        service.prepare("project", project({**selector, "compartment": "beta"}))
    with pytest.raises(ValueError):
        service.prepare("board", board({**selector, "compartment": "beta"}))
    assert not (store.root / "alpha").exists()


def test_multi_compartment_project_requires_all_labels(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha", "program"), part="spec")
    data = project(selector, compartments=("alpha", "program"))
    service.register(service.prepare("project", data))
    with pytest.raises(StoreError, match="authorized"):
        service.load("project", "flight", "sample/A", compartments={"alpha"})
    assert service.load("project", "flight", "sample/A", compartments={"alpha", "program"})["customer"] == data["customer"]


def test_review_mutation_and_blob_corruption_fail_before_new_writes(tmp_path, setup):
    store, service, ref = setup
    prepared = service.prepare("board", {**board(ref), "version": "new"})
    prepared.manifest["version"] = "changed"
    with pytest.raises(StoreError):
        service.register(prepared)
    assert service.list_versions("board", "demo") == ["v/one"]
    prepared = service.prepare("board", {**board(ref), "version": "new"})
    blob = next(store.root.glob("public/blobs/sha256/*/*"))
    blob.chmod(0o600)
    blob.write_bytes(b"corrupt")
    with pytest.raises(StoreError):
        service.register(prepared)
    assert not (store.root / "public/refs/boards/demo/new").exists()


def test_ambiguous_ref_requires_compartment(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha",), part="spec")
    document(tmp_path, store, compartments=("beta",), part="spec", text="# Different\nText\n")
    data = project(selector, compartments=("alpha", "beta"))
    with pytest.raises(StoreError, match="Ambiguous"):
        service.prepare("project", data)
    data = project({**selector, "compartment": "alpha"}, compartments=("alpha", "beta"))
    assert service.prepare("project", data).manifest["documents"][0]["compartment"] == "alpha"


def test_feature_cannot_silently_add_document(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha",), part="spec")
    extra = document(tmp_path, store, compartments=("alpha",), part="extra")
    data = project(selector)
    data["features"][0]["governed_by"] = [extra]
    with pytest.raises(StoreError, match="belong"):
        service.prepare("project", data)


def test_list_documents_default_public_only(tmp_path, setup):
    store, service, _ = setup
    document(tmp_path, store, compartments=("alpha",), part="spec")
    assert {entry["compartment"] for entry in service.list_documents()} == {"public"}
    assert {entry["compartment"] for entry in service.list_documents(compartments={"alpha"})} == {"public", "alpha"}


def test_board_document_applicability(tmp_path, setup):
    _, service, ref = setup
    data = board(ref)
    data["parts"][0]["part"] = "synthetic/other"
    with pytest.raises(StoreError, match="part"):
        service.prepare("board", data)


def test_board_revision_must_be_declared_applicable(tmp_path, setup):
    store, service, _ = setup
    ref = document(tmp_path, store, silicon_revisions=("A",))
    data = board(ref)
    data["parts"][0]["silicon_revision"] = "B"
    with pytest.raises(StoreError, match="revision"):
        service.prepare("board", data)


def test_dropped_project_labels_never_register(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha",), part="spec")
    prepared = service.prepare("project", project(selector))
    prepared.manifest["compartments"] = []
    with pytest.raises(ValueError):
        service.register(prepared)
    assert not (store.root / "alpha/refs/projects").exists()


@pytest.mark.parametrize("ref", ["../escape/path", "/root/document/version", "synthetic/chip/manual/%2e%2e"])
def test_selector_traversal_rejected(setup, ref):
    _, service, _ = setup
    with pytest.raises(ValueError):
        service.prepare("board", board({"ref": ref}))


@pytest.mark.parametrize("compartments", ["alpha", b"alpha", 123, [None], {"nested": "alpha"}])
def test_scope_requires_explicit_names_collection(setup, compartments):
    _, service, _ = setup
    with pytest.raises(StoreError):
        service.list_documents(compartments=compartments)


def test_catalog_omits_documents_requiring_additional_compartments(tmp_path, setup):
    store, service, _ = setup
    document(tmp_path, store, compartments=("alpha",), part="visible")
    restricted = document(tmp_path, store, compartments=("alpha", "program"), part="restricted")
    records = service.list_documents(compartments={"alpha"})
    assert {entry["manifest"]["part"] for entry in records} == {"chip", "visible"}
    assert len(service.list_documents(compartments={"alpha", "program"})) == 4
    with pytest.raises(AccessDenied):
        service.prepare("project", project({**restricted, "compartment": "alpha"}))


def test_version_catalog_omits_project_with_additional_compartments(tmp_path, setup):
    store, service, _ = setup
    visible = document(tmp_path, store, compartments=("alpha",), part="visible")
    service.register(service.prepare("project", project(visible)))
    restricted = document(tmp_path, store, compartments=("alpha", "program"), part="restricted")
    data = project(restricted, compartments=("alpha", "program"))
    data["version"] = "restricted"
    service.register(service.prepare("project", data))
    assert service.list_versions("project", "flight", compartments={"alpha"}) == ["sample/A"]
    with pytest.raises(AccessDenied):
        service.load("project", "flight", "restricted", compartments={"alpha"})


def test_unqualified_ref_skips_restricted_match_for_public_alternative(tmp_path, setup):
    store, service, ref = setup
    document(tmp_path, store, compartments=("alpha", "program"))
    prepared = service.prepare("project", project(ref))
    assert prepared.manifest["documents"][0]["compartment"] == "public"
    with pytest.raises(AccessDenied):
        service.prepare("project", project({**ref, "compartment": "alpha"}))


def test_catalog_does_not_hide_corrupt_restricted_manifest(tmp_path, setup):
    store, service, _ = setup
    document(tmp_path, store, compartments=("alpha", "program"), part="restricted")
    path = next(store.root.glob("alpha/manifests/sha256/*/*"))
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    with pytest.raises(StoreError) as error:
        service.list_documents(compartments={"alpha"})
    assert not isinstance(error.value, AccessDenied)


def test_configuration_catalog_boards_and_explicit_project_scopes(tmp_path, setup):
    store, service, _ = setup
    boards = service.list_configs("board")
    assert [(entry["name"], entry["version"], entry["compartment"]) for entry in boards] == [("demo", "v/one", "public")]
    assert boards[0]["digest"].startswith("sha256:")
    selector = document(tmp_path, store, compartments=("alpha",), part="spec")
    service.register(service.prepare("project", project(selector)))
    assert service.list_configs("project") == []
    assert service.list_configs("project", compartments={"beta"}) == []
    projects = service.list_configs("project", compartments={"alpha"})
    assert [(entry["name"], entry["version"]) for entry in projects] == [("flight", "sample/A")]
    assert projects[0]["manifest"]["customer"] == "Synthetic customer"


def test_configuration_catalog_omits_restricted_and_deduplicates_copies(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha", "program"), part="spec")
    service.register(service.prepare("project", project(selector, compartments=("alpha", "program"))))
    assert service.list_configs("project", compartments={"alpha"}) == []
    assert len(service.list_configs("project", compartments={"alpha", "program"})) == 1


def test_configuration_catalog_surfaces_corruption(tmp_path, setup):
    store, service, _ = setup
    board_record = service.list_configs("board")[0]
    path = store._path("public", "manifests", board_record["digest"])
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    with pytest.raises(StoreError):
        service.list_configs("board")


def test_configuration_catalog_rejects_symlinked_names(tmp_path, setup):
    store, service, _ = setup
    directory = store.root / "public/refs/boards"
    (directory / "alias").symlink_to(directory / "demo", target_is_directory=True)
    with pytest.raises(StoreError):
        service.list_configs("board")


def test_load_digest_retains_board_selection_after_ref_moves(setup):
    _, service, ref = setup
    selected = service.list_configs("board")[0]
    updated = board(ref)
    updated["parts"][0]["refdes"] = "U99"
    service.register(service.prepare("board", updated))
    assert service.load_digest("board", selected["digest"]) == selected["manifest"]
    assert service.load("board", "demo", "v/one") != selected["manifest"]


def test_load_digest_project_requires_explicit_location_and_full_scope(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, compartments=("alpha", "program"), part="spec")
    prepared = service.prepare("project", project(selector, compartments=("alpha", "program")))
    service.register(prepared)
    with pytest.raises(StoreError):
        service.load_digest("project", prepared.digest)
    with pytest.raises(StoreError):
        service.load_digest("project", prepared.digest, compartment="alpha")
    with pytest.raises(AccessDenied):
        service.load_digest("project", prepared.digest, compartment="alpha", compartments={"alpha"})
    assert service.load_digest("project", prepared.digest, compartment="alpha", compartments={"alpha", "program"}) == prepared.manifest
    with pytest.raises(StoreError):
        service.load_digest("board", prepared.digest, compartment="alpha", compartments={"alpha", "program"})


@pytest.mark.parametrize("digest", ["../escape", "sha256:" + "A" * 64, "sha256:short"])
def test_load_digest_rejects_malformed_pins(setup, digest):
    _, service, _ = setup
    with pytest.raises(StoreError):
        service.load_digest("board", digest)
