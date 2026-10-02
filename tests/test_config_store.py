"""Synthetic board and customer snapshots exercise immutable pin boundaries."""
from copy import deepcopy

import pytest

from caiman.configurations.service import ConfigurationService
from caiman.documents.ingest import prepare_document
from caiman.storage.store import Store, StoreError


def document(tmp_path, store, *, pods=(), version="v1", text="# Manual\n\n## Registers\nSynthetic text\n", part="chip", silicon_revisions=()):
    path = tmp_path / "synthetic.md"
    path.write_text(text)
    prepared = prepare_document(path, {
        "issuer": "synthetic", "part": part, "doc_type": "manual", "version": version,
        "structure": "prose", 'pod': ('public' if not pods else (list(pods))[0]),
        "silicon_revisions": list(silicon_revisions),
    })
    registered = store.register(prepared)
    return {"ref": registered.ref_path.relative_to(store.root / registered.pod / "refs" / "documents").as_posix()}


def board(selector):
    return {"board": "demo", "version": "v/one", "parts": [
        {"role": "main", "vendor": "synthetic", "part": "chip", "documents": [selector]}], "links": []}


def project(selector, *, pods=("alpha",)):
    return {"project": "flight", "version": "sample/A", "customer": "Synthetic customer",
            'pod': (list(pods))[0], "boards": [{"name": "demo", "version": "v/one"}],
            "spec_set": "release A", "documents": [selector],
            "features": [{"name": "flash", "scope": "required", "governed_by": [selector], "realized_on": [{"board": "demo", "version": "v/one", "role": "main"}]}]}


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
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    prepared = service.prepare("project", project(selector))
    snapshot = deepcopy(prepared.manifest)
    result = service.register(prepared)
    assert len(result.ref_paths) == 1
    assert service.load("project", "flight", "sample/A", pods={"alpha"}) == snapshot
    assert service.list_versions("project", "flight", pods={"alpha"}) == ["sample/A"]
    assert service.list_versions("project", "flight") == ["sample/A"]
    assert "precedence" not in snapshot
    for location in (snapshot["documents"][0], snapshot["features"][0]["governed_by"][0]):
        assert location["digest"].startswith("sha256:")
        assert location["pod"] == "alpha"
    assert snapshot["boards"][0]["digest"].startswith("sha256:")
    assert service.load("project", "flight", "sample/A") == prepared.manifest


def test_project_board_ref_repoint_does_not_change_prepared_pin(tmp_path, setup):
    store, service, ref = setup
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    prepared = service.prepare("project", project(selector))
    original = prepared.manifest["boards"][0]["digest"]
    data = board(ref)
    data["parts"][0]["aliases"] = {"refdes": "U99"}
    newer = service.register(service.prepare("board", data))
    assert newer.digest != original
    service.register(prepared)
    assert service.load("project", "flight", "sample/A", pods={"alpha"})["boards"][0]["digest"] == original


def test_project_pins_two_versions_of_one_board_each_by_its_own_digest(tmp_path, setup):
    store, service, ref = setup
    second = board(ref)
    second["version"] = "v/two"
    second["parts"].append({"role": "radio", "vendor": "synthetic", "part": "chip", "documents": []})
    two = service.register(service.prepare("board", second)).digest
    one = service.load_digest("board", service._read_ref(service._config_path("board", "demo", "v/one", "public")))
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    data = project(selector)
    data["boards"].append({"name": "demo", "version": "v/two"})
    # Both boards declare `main`; each entry names which one it means.
    data["features"][0]["realized_on"] += [{"board": "demo", "version": "v/two", "role": "main"},
                                           {"board": "demo", "version": "v/two", "role": "radio"}]
    prepared = service.prepare("project", data)
    pinned = {board["version"]: board["digest"] for board in prepared.manifest["boards"]}
    assert pinned["v/two"] == two
    assert pinned["v/one"] != two and one["version"] == "v/one"
    service.register(prepared)
    assert service.load("project", "flight", "sample/A", pods={"alpha"}) == prepared.manifest
    data["features"][0]["realized_on"] = [{"board": "demo", "version": "v/one", "role": "radio"}]
    with pytest.raises(ValueError, match="realized_on"):
        service.prepare("project", data)


def test_every_pinned_board_must_exist(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    data = project(selector)
    data["boards"].append({"name": "demo", "version": "missing"})
    with pytest.raises(StoreError):
        service.prepare("project", data)


def test_feature_ref_uses_project_pin_even_after_ref_repoint(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    earlier = service.prepare("project", project(selector)).manifest["documents"][0]
    document(tmp_path, store, pods=("alpha",), part="spec", text="# Replacement\nDifferent\n")
    data = project(selector)
    data["documents"] = [earlier]
    prepared = service.prepare("project", data)
    assert prepared.manifest["features"][0]["governed_by"][0]["digest"] == earlier["digest"]
    document(tmp_path, store, pods=("alpha",), part="spec", text="# Again\nDifferent again\n")
    service.register(prepared)
    assert service.load("project", "flight", "sample/A", pods={"alpha"})["documents"][0]["digest"] == earlier["digest"]


def test_cross_customer_and_public_board_rejected(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=('beta',), part='spec')
    prepared = service.prepare('project', project({**selector, 'pod': 'beta'}))
    assert prepared.manifest['documents'][0]['pod'] == 'beta'
    # Board applicability still checks hardware identity, independent of pod.
    with pytest.raises(ValueError, match='part'):
        service.prepare('board', board({**selector, 'pod': 'beta'}))


def test_multi_pod_project_requires_all_labels(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=('alpha',), part='spec')
    data = project(selector)
    saved = service.prepare('project', data)
    service.register(saved)
    assert service.load('project', 'flight', 'sample/A') == saved.manifest
    assert len(list(store.root.glob('*/refs/projects/flight/sample%2FA'))) == 1


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


def test_ambiguous_ref_requires_pod(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    document(tmp_path, store, pods=("beta",), part="spec", text="# Different\nText\n")
    data = project(selector, pods=("alpha", "beta"))
    with pytest.raises(StoreError, match="Ambiguous"):
        service.prepare("project", data)
    data = project({**selector, "pod": "alpha"}, pods=("alpha", "beta"))
    assert service.prepare("project", data).manifest["documents"][0]["pod"] == "alpha"


def test_feature_cannot_silently_add_document(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    extra = document(tmp_path, store, pods=("alpha",), part="extra")
    data = project(selector)
    data["features"][0]["governed_by"] = [extra]
    with pytest.raises(StoreError, match="belong"):
        service.prepare("project", data)


def test_list_documents_default_public_only(tmp_path, setup):
    store, service, _ = setup
    document(tmp_path, store, pods=("alpha",), part="spec")
    assert {entry["pod"] for entry in service.list_documents()} == {"public", "alpha"}
    assert {entry["pod"] for entry in service.list_documents(pods={"alpha"})} == {"alpha"}


def test_board_document_applicability(tmp_path, setup):
    _, service, ref = setup
    data = board(ref)
    data["parts"][0]["part"] = "other"
    with pytest.raises(StoreError, match="part"):
        service.prepare("board", data)
    data = board(ref)
    data["parts"][0]["vendor"] = "another"
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
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    prepared = service.prepare("project", project(selector))
    prepared.manifest["pods"] = []
    with pytest.raises(ValueError):
        service.register(prepared)
    assert not (store.root / "alpha/refs/projects").exists()


@pytest.mark.parametrize("ref", ["../escape/path", "/root/document/version", "synthetic/chip/manual/%2e%2e"])
def test_selector_traversal_rejected(setup, ref):
    _, service, _ = setup
    with pytest.raises(ValueError):
        service.prepare("board", board({"ref": ref}))


@pytest.mark.parametrize("pods", ["alpha", b"alpha", 123, [None], {"nested": "alpha"}])
def test_scope_requires_explicit_names_collection(setup, pods):
    _, service, _ = setup
    with pytest.raises(ValueError):
        service.list_documents(pods=pods)


def test_catalog_omits_documents_in_other_pods(tmp_path, setup):
    store, service, _ = setup
    document(tmp_path, store, pods=("alpha",), part="visible")
    restricted = document(tmp_path, store, pods=("program",), part="restricted")
    records = service.list_documents(pods={"alpha"})
    assert {entry["manifest"]["part"] for entry in records} == {"visible"}
    assert len(service.list_documents(pods={"alpha", "program"})) == 2
    assert service.prepare("project", project({**restricted, "pod": "program"})).manifest["documents"][0]["pod"] == "program"


def test_version_catalog_omits_project_with_additional_pods(tmp_path, setup):
    store, service, _ = setup
    pin = document(tmp_path, store, pods=('alpha',), part='spec')
    saved = service.prepare('project', project(pin)); service.register(saved)
    (store.root / 'alpha' / 'blobs').rename(store.root / 'alpha' / '.unavailable-blobs')
    assert service.list_versions('project', 'flight') == ['sample/A']
    assert service.load('project', 'flight', 'sample/A') == saved.manifest
    with pytest.raises(OSError):
        service.prepare('project', saved.manifest, pod='alpha')


def test_unqualified_ref_ignores_undeclared_pod_for_public_alternative(tmp_path, setup):
    store, service, ref = setup
    document(tmp_path, store, pods=('program',))
    with pytest.raises(ValueError, match='Ambiguous'):
        service.prepare('project', project(ref))
    saved = service.prepare('project', project({**ref, 'pod': 'program'}))
    assert saved.manifest['documents'][0]['pod'] == 'program'


def test_catalog_does_not_hide_corrupt_restricted_manifest(tmp_path, setup):
    store, service, _ = setup
    document(tmp_path, store, pods=("alpha",), part="restricted")
    path = next(store.root.glob("alpha/manifests/sha256/*/*"))
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    with pytest.raises(StoreError) as error:
        service.list_documents(pods={"alpha"})


def test_configuration_catalog_boards_and_explicit_project_scopes(tmp_path, setup):
    store, service, _ = setup
    boards = service.list_configs("board")
    assert [(entry["name"], entry["version"], entry["pod"]) for entry in boards] == [("demo", "v/one", "public")]
    assert boards[0]["digest"].startswith("sha256:")
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    service.register(service.prepare("project", project(selector)))
    assert len(service.list_configs("project")) == 1
    assert service.list_configs("project", pods={"beta"}) == []
    projects = service.list_configs("project", pods={"alpha"})
    assert [(entry["name"], entry["version"]) for entry in projects] == [("flight", "sample/A")]
    assert projects[0]["manifest"]["customer"] == "Synthetic customer"


def test_configuration_catalog_omits_restricted_and_deduplicates_copies(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=("alpha",), part="spec")
    service.register(service.prepare("project", project(selector, pods=("alpha", "program"))))
    assert len(service.list_configs("project", pods={"alpha"})) == 1
    assert len(service.list_configs("project", pods={"alpha", "program"})) == 1


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
    updated["parts"][0]["aliases"] = {"refdes": "U99"}
    service.register(service.prepare("board", updated))
    assert service.load_digest("board", selected["digest"]) == selected["manifest"]
    assert service.load("board", "demo", "v/one") != selected["manifest"]


def test_load_digest_project_requires_explicit_location_and_full_scope(tmp_path, setup):
    store, service, _ = setup
    selector = document(tmp_path, store, pods=('alpha',), part='spec')
    saved = service.prepare('project', project(selector)); service.register(saved)
    assert service.load_digest('project', saved.digest, pod='alpha') == saved.manifest
    with pytest.raises((OSError, ValueError)):
        service.load_digest('project', saved.digest, pod='missing')
    with pytest.raises(ValueError):
        service.load_digest('board', saved.digest, pod='alpha')


@pytest.mark.parametrize("digest", ["../escape", "sha256:" + "A" * 64, "sha256:short"])
def test_load_digest_rejects_malformed_pins(setup, digest):
    _, service, _ = setup
    with pytest.raises(StoreError):
        service.load_digest("board", digest)


def test_board_level_document_pins_the_assembly(tmp_path, setup):
    """A board user guide is issued by the board vendor and names the assembly,
    which no part instance can express (D-13)."""
    store, service, _ = setup
    guide = document(tmp_path, store, part="demo", text="# Guide\n\n## Connectors\nSynthetic text\n")
    data = board(document(tmp_path, store))
    data.update(vendor="synthetic", documents=[dict(guide, notes="Connector pinout and jumper defaults.")])
    prepared = service.prepare("board", data)
    assert prepared.manifest["documents"][0]["digest"].startswith("sha256:")
    assert prepared.manifest["documents"][0]["notes"] == "Connector pinout and jumper defaults."
    service.register(prepared)
    assert service.load("board", "demo", "v/one")["documents"][0] == prepared.manifest["documents"][0]


def test_board_level_document_must_match_the_board_vendor_and_name(tmp_path, setup):
    store, service, _ = setup
    guide = document(tmp_path, store, part="demo")
    data = board(document(tmp_path, store))
    data.update(vendor="elsewhere", documents=[guide])
    with pytest.raises(StoreError, match="assembly"):
        service.prepare("board", data)
    # A document about a part is not a document about the board that carries it.
    data.update(vendor="synthetic", documents=[document(tmp_path, store)])
    with pytest.raises(StoreError, match="assembly"):
        service.prepare("board", data)


def test_board_part_document_cannot_be_a_program_document(tmp_path, setup):
    """The packed v1 identity could not say this; two field comparisons can."""
    store, service, _ = setup
    path = tmp_path / "program.md"
    path.write_text("# Spec\n\n## Boot\nSynthetic text\n")
    prepared = prepare_document(path, {
        "issuer": "synthetic", "program": "flight", "doc_type": "spec", "version": "v1",
        "structure": "prose", 'pod': 'public'})
    registered = store.register(prepared)
    ref = registered.ref_path.relative_to(store.root / "public" / "refs" / "documents").as_posix()
    with pytest.raises(StoreError, match="part"):
        service.prepare("board", board({"ref": ref}))


def test_legacy_board_snapshot_keeps_resolving_after_v2(tmp_path, setup):
    """Stored snapshots are immutable (S-11): a caiman.board/1 board still loads,
    pins by its packed identity, and is never rewritten into the v2 shape."""
    store, service, ref = setup
    legacy = {"schema": "caiman.board/1", "board": "legacy", "version": "v/one", "links": [],
              "parts": [{"role": "main", "part": "synthetic/chip", "refdes": "U1", "documents": [ref]}]}
    prepared = service.prepare("board", legacy)
    assert prepared.manifest["schema"] == "caiman.board/1"
    assert prepared.manifest["parts"][0]["part"] == "synthetic/chip"
    service.register(prepared)
    assert service.load("board", "legacy", "v/one") == prepared.manifest
    assert service.load_digest("board", prepared.digest)["parts"][0]["refdes"] == "U1"
