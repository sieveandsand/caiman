"""Synthetic documents exercise the complete interactive registration boundary."""

import json
from copy import deepcopy

import pytest
from textual.widgets import Button, Collapsible, Input, Select, Static

from caiman.documents.tui import IngestApp
from caiman.configurations.service import ConfigurationService
from caiman.storage.store import Store


async def advance(pilot):
    await pilot.click("#next")
    await pilot.pause(0.15)


def fill_document(app):
    for field, value in {"issuer": "synthetic", "part": "chip", "name": "Manual", "version": "rev-1"}.items():
        app.query_one(f"#{field}", Input).value = value


@pytest.mark.asyncio
async def test_cancel_has_no_side_effects(tmp_path):
    source = tmp_path / "manual.md"
    source.write_text("# Synthetic manual\n\n## Control\nContent.\n")
    store = tmp_path / "store"
    app = IngestApp(store, source)
    async with app.run_test(size=(100, 45)) as pilot:
        assert app.theme == "caiman-terminal"
        assert "ingest document" in str(app.query_one("#brand", Static).render())
        await advance(pilot)
        fill_document(app)
        app.query_one("#pod", Select).value = "public"
        await advance(pilot)
        await advance(pilot)
        assert app.step == 3, str(app.query_one("#status", Static).render())
        assert not store.exists()
        await pilot.click("#cancel")
    assert not store.exists()


@pytest.mark.asyncio
async def test_invalid_labels_retained_then_register_and_edit(tmp_path):
    source = tmp_path / "manual.md"
    original = b"# Synthetic manual\r\n\r\n## Control\r\nContent.\r\n"
    source.write_bytes(original)
    store = tmp_path / "store"
    app = IngestApp(store, source)
    async with app.run_test(size=(100, 45)) as pilot:
        await advance(pilot)
        fill_document(app)
        assert app.query_one("#pod", Select).value == "public"
        assert app.value("issuer") == "synthetic"
        assert not store.exists()
        app.query_one("#pod", Select).value = "public"
        await advance(pilot)
        assert app.step == 2
        await advance(pilot)
        assert app.step == 3
        first_digest = app.prepared.manifest_digest
        await pilot.click("#back")
        await pilot.pause(0.15)
        await pilot.click("#back")
        app.query_one("#version", Input).value = "rev-2"
        await advance(pilot)
        await advance(pilot)
        assert app.prepared.manifest_digest != first_digest
        assert "source" not in app.prepared.manifest
        assert "converter" not in app.prepared.manifest
        await advance(pilot)
        assert app.registered
        assert "Registered locally" in str(app.query_one("#status", Static).render())
        assert source.read_bytes() == original
        manifests = [json.loads(path.read_bytes()) for path in (store / "public" / "manifests").rglob("*") if path.is_file()]
        assert len(manifests) == 1
        assert manifests[0]["version"] == "rev-2"


@pytest.mark.asyncio
async def test_heading_errors_are_located_without_writes(tmp_path):
    source = tmp_path / "manual.md"
    source.write_text("# Manual\n## Control\n## Control\n")
    store = tmp_path / "store"
    app = IngestApp(store, source)
    async with app.run_test(size=(100, 35)) as pilot:
        await advance(pilot)
        assert app.step == 0
        assert "lines 2 and 3" in str(app.query_one("#error-file", Static).render())
        assert app.value("file") == str(source)
        assert not store.exists()


@pytest.mark.asyncio
async def test_optional_errors_can_be_corrected_after_going_back(tmp_path):
    source = tmp_path / "manual.md"
    source.write_text("# Synthetic manual\nBody.\n")
    app = IngestApp(tmp_path / "store", source)
    async with app.run_test(size=(80, 24)) as pilot:
        await advance(pilot)
        fill_document(app)
        app.query_one("#pod", Select).set_options([("Program", "synthetic-program")])
        app.query_one("#pod", Select).value = "synthetic-program"
        await advance(pilot)
        app.query_one(Collapsible).collapsed = False
        app.query_one("#source_pages", Input).value = "not a number"
        await advance(pilot)
        assert app.step == 2
        assert "source.pages" in str(app.query_one("#status", Static).render())
        await pilot.click("#back")
        await pilot.pause(0.15)
        await advance(pilot)
        assert app.step == 2
        app.query_one("#source_pages", Input).value = "12"
        app.query_one("#converter_version", Input).value = "1.2"
        await advance(pilot)
        assert app.step == 3
        assert app.prepared.manifest["converter"] == {"version": "1.2"}
        assert "Pod: synthetic-program" in app.review_text()
        assert "Conversion location: Unknown" in app.review_text()
    assert not (tmp_path / "store").exists()


@pytest.mark.asyncio
async def test_optional_requirement_pattern_can_be_corrected_after_back(tmp_path):
    source = tmp_path / 'spec.md'
    source.write_text('# Specification\nREQ-123: Start correctly.\n')
    app = IngestApp(tmp_path / 'store', source)
    async with app.run_test(size=(100, 45)) as pilot:
        await advance(pilot)
        fill_document(app)
        app.query_one('#pod', Select).value = 'public'
        await advance(pilot)
        app.query_one('#pattern', Input).value = '['
        await advance(pilot)
        assert app.step == 2
        await pilot.click('#back')
        await pilot.pause(0.25)
        await advance(pilot)
        assert app.step == 2
        app.query_one('#pattern', Input).value = r'^REQ-\d+$'
        await advance(pilot)
        assert app.step == 3
        assert app.prepared.manifest['requirements'] == {'pattern': r'^REQ-\d+$'}
    assert not (tmp_path / 'store').exists()


def registered_contexts(root):
    service = ConfigurationService(Store(root))
    board = service.prepare("board", {
        "board": "synthetic-board", "version": "A",
        "parts": [{"role": "mcu", "vendor": "synthetic", "part": "chip", "silicon_revision": "mask-1", "documents": []}],
        "links": [],
    })
    service.register(board)
    for scope in ("synthetic-alpha", "synthetic-beta"):
        project = service.prepare("project", {
            "project": scope + "-program", "version": "1", "customer": "Synthetic Customer",
            'pod': ([scope])[0], "boards": [{"name": "synthetic-board", "version": "A"}],
            "spec_set": "release-1", "documents": [], "features": [],
        })
        service.register(project)
    return service, board


@pytest.mark.asyncio
async def test_document_form_rejects_multiple_pods(tmp_path):
    app = IngestApp(tmp_path / 'store')
    async with app.run_test() as pilot:
        assert app.query_one('#pod', Select).value == 'public'
        assert not app.query('#pods') and not app.query('#visibility')
        assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_multi_pod_project_does_not_choose_document_pod(tmp_path):
    service, _ = registered_contexts(tmp_path / 'store')
    record = service.list_configs('project', pods=['synthetic-alpha'])[0]
    app = IngestApp(service.store.root)
    async with app.run_test() as pilot:
        await app.apply_project(record)
        assert app.query_one('#pod', Select).value == 'synthetic-alpha'
        assert app.value('program') == record['manifest']['project']


@pytest.mark.asyncio
async def test_existing_board_part_then_project_and_manual_clear_stale_metadata(tmp_path):
    store = tmp_path / "store"
    registered_contexts(store)
    source = tmp_path / "manual.md"
    source.write_text("# Synthetic manual\nBody.\n")
    app = IngestApp(store, source)
    async with app.run_test(size=(100, 45)) as pilot:
        await advance(pilot)
        app.query_one("#identity_source", Select).value = "board"
        await pilot.pause(0.15)
        assert len(app.boards) == 1
        app.query_one("#board_choice", Select).value = "0"
        await pilot.pause(0.15)
        app.query_one("#board_part", Select).value = "0"
        await pilot.pause(0.15)
        assert app.value("issuer") == "synthetic"
        assert app.value("part") == "chip"
        assert app.value("silicon_revisions") == "mask-1"
        assert isinstance(app.query_one("#pod", Select).value, str)
        app.query_one("#pod", Select).value = "public"
        state = app.export_state()
        selected_context = deepcopy(app.context)
        app.query_one("#identity_source", Select).value = "project"
        await pilot.pause(0.15)
        assert app.value("part") == ""
        await app.find_projects()
        assert len(app.projects) == 2
        app.query_one("#project_choice", Select).value = "0"
        await pilot.pause(0.15)
        assert app.value("program") == "synthetic-alpha-program"
        assert app.value("issuer") == ""
        assert app.value("silicon_revisions") == ""
        assert app.query_one("#pod", Select).value == "synthetic-alpha"
        assert isinstance(app.query_one("#pod", Select).value, str)
        assert "Synthetic Customer" in str(app.query_one("#context-status", Static).render())
        app.query_one("#identity_source", Select).value = "manual"
        await pilot.pause(0.15)
        assert app.value("program") == ""
        assert app.query_one("#pod", Select).value == "synthetic-alpha"
        assert "project" in app.context and "board" in app.context
        app.query_one("#identity_source", Select).value = "project"
        await pilot.pause(0.15)
        assert app.query_one("#project_choice", Select).value == Select.NULL
        app.query_one("#project_choice", Select).value = "0"
        await pilot.pause(0.15)
        assert app.value("program") == "synthetic-alpha-program"
    resumed = IngestApp(store, state=state, context=selected_context)
    async with resumed.run_test(size=(100, 45)) as pilot:
        await pilot.pause(0.15)
        assert resumed.query_one("#board_choice", Select).value == "0"
        assert resumed.query_one("#board_part", Select).value == "0"
        assert resumed.value("part") == "chip"
        assert resumed.query_one("#pod", Select).value == "public"


@pytest.mark.asyncio
async def test_inline_create_cancel_resume_retains_ingestion_form(tmp_path):
    store = tmp_path / "store"
    service, _ = registered_contexts(store)
    context = {"project": service.list_configs("project", pods={"synthetic-alpha"})[0]}
    source = tmp_path / "spec.md"
    source.write_text("# Synthetic specification\nBody.\n")
    app = IngestApp(store, source, context=context)
    async with app.run_test(size=(100, 45)) as pilot:
        await advance(pilot)
        app.query_one("#issuer", Input).value = "synthetic-publisher"
        app.query_one("#name", Input).value = "Specification"
        app.query_one("#version", Input).value = "release-A"
        app.query_one("#pod", Select).value = "synthetic-alpha"
        app.query_one("#create-project", Button).press()
        await pilot.pause(0.15)
    request = app.return_value
    assert request["action"] == "create-project"
    normalized_context = {kind: {key: record[key] for key in ("manifest", "digest")} for kind, record in request["context"].items()}
    resumed = IngestApp(store, state=request["ingest_state"], context=normalized_context)
    async with resumed.run_test(size=(100, 45)) as pilot:
        await pilot.pause(0.15)
        assert resumed.step == 1
        assert resumed.value("file") == str(source)
        assert resumed.value("issuer") == "synthetic-publisher"
        assert resumed.value("name") == "Specification"
        assert resumed.value("version") == "release-A"
        assert resumed.query_one("#pod", Select).value == "synthetic-alpha"
        await advance(pilot)
        assert resumed.step == 2
    assert not (store / "synthetic-alpha" / "refs" / "documents").exists()


@pytest.mark.asyncio
async def test_project_selection_never_uses_repointed_board_ref_for_hardware(tmp_path):
    root = tmp_path / "store"
    service, original = registered_contexts(root)
    replacement = deepcopy(original.manifest)
    replacement["parts"][0]["part"] = "replacement"
    service.register(service.prepare("board", replacement))
    context = {"project": service.list_configs("project", pods={"synthetic-alpha"})[0]}
    app = IngestApp(root, context=context)
    async with app.run_test(size=(100, 45)) as pilot:
        await pilot.pause(0.15)
        assert app.context["project"]["manifest"]["boards"][0]["digest"] == original.digest
        assert app.context["board"]["digest"] == original.digest
        assert app.context["board"]["manifest"]["parts"][0]["part"] == "chip"
        assert app.value("part") == ""
        assert app.value("program") == "synthetic-alpha-program"
