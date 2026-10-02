"""Configuration forms share real validation, resolution, and storage."""

from copy import deepcopy
import json

import pytest
from textual.widgets import Input, Static, TextArea

from caiman.configurations.service import ConfigurationService
from caiman.configurations.tui import ConfigApp
from caiman.documents.ingest import prepare_document
from caiman.documents.models import ValidationError
from caiman.storage.store import Store


def board_draft():
    return {"board": "synthetic-board", "version": "A", "parts": [{"role": "mcu", "vendor": "synthetic", "part": "chip", "documents": []}], "links": []}


async def next_step(pilot):
    await pilot.click("#next")
    await pilot.pause(0.15)


@pytest.mark.asyncio
async def test_board_draft_cancel_and_shared_theme(tmp_path):
    draft = board_draft()
    original = deepcopy(draft)
    store = tmp_path / "store"
    app = ConfigApp("board", store, draft)
    async with app.run_test(size=(80, 24)) as pilot:
        assert app.theme == "caiman-terminal"
        assert "author board" in str(app.query_one("#brand", Static).render())
        app.query_one("#version", Input).value = "B"
        await next_step(pilot)
        assert app.reviewing, str(app.query_one("#status", Static).render())
        assert app.prepared.manifest["version"] == "B"
        assert "Access: public" in app.review_text()
        assert not store.exists()
        await pilot.click("#cancel")
    assert draft == original
    assert not store.exists()


@pytest.mark.asyncio
async def test_board_invalid_collection_edit_then_register(tmp_path):
    store = tmp_path / "store"
    app = ConfigApp("board", store, board_draft())
    async with app.run_test(size=(90, 30)) as pilot:
        app.query_one("#parts", TextArea).load_text("[")
        await next_step(pilot)
        assert not app.reviewing
        assert "line 1" in str(app.query_one("#error-parts", Static).render())
        assert app.value("board") == "synthetic-board"
        assert not store.exists()
        app.query_one("#parts", TextArea).load_text(json.dumps(board_draft()["parts"]))
        await next_step(pilot)
        digest = app.prepared.digest
        await pilot.click("#back")
        await pilot.pause(0.15)
        app.query_one("#version", Input).value = "B"
        await next_step(pilot)
        assert app.prepared.digest != digest
        await next_step(pilot)
        assert app.registration is not None
        assert "Registered locally" in str(app.query_one("#status", Static).render())
    service = ConfigurationService(Store(store))
    assert service.list_versions("board", "synthetic-board") == ["B"]
    assert service.load("board", "synthetic-board", "B")["parts"][0]["role"] == "mcu"


@pytest.mark.asyncio
async def test_project_catalog_scope_review_and_real_registration(tmp_path):
    root = tmp_path / "store"
    store = Store(root)
    service = ConfigurationService(store)
    board = service.prepare("board", board_draft())
    service.register(board)
    source = tmp_path / "spec.md"
    source.write_text("# Synthetic specification\n## Timing\nA fictional constraint.\n")
    for compartment in ("synthetic-alpha", "synthetic-beta"):
        store.register(prepare_document(source, {
            "issuer": compartment, "program": "demo", "doc_type": "spec", "version": "1",
            "structure": "prose", "labels": {"public": False, "compartments": [compartment]},
        }))
    pin = service.list_documents(compartments={"synthetic-alpha"})[0]
    draft = {
        "project": "synthetic-project", "version": "1", "customer": "Synthetic Alpha",
        "compartments": ["synthetic-alpha"], "boards": [{"name": "synthetic-board", "version": "A"}],
        "spec_set": "Synthetic release", "documents": [{"digest": pin["digest"]}],
        "features": [{"name": "timing", "scope": "required", "realized_on": [{"board": "synthetic-board", "version": "A", "role": "mcu"}]}],
    }
    app = ConfigApp("project", root, draft)
    async with app.run_test(size=(90, 35)) as pilot:
        # Exercise catalog operation without making the test depend on scroll position.
        await app.refresh_catalog()
        catalog = app.query_one("#catalog", TextArea).text
        assert "synthetic-alpha" in catalog
        assert "synthetic-beta" not in catalog
        assert pin["digest"] in catalog
        await next_step(pilot)
        assert app.reviewing, str(app.query_one("#status", Static).render())
        assert app.prepared.manifest["boards"][0]["digest"] == board.digest
        assert app.prepared.manifest["documents"][0]["digest"] == pin["digest"]
        assert "Compartments: synthetic-alpha" in app.review_text()
        assert "Selected by digest" in app.review_text()
        assert "timing: required" in app.review_text()
        assert "precedence" not in app.review_text().lower()
        await next_step(pilot)
        assert app.registration is not None
    saved = service.load("project", "synthetic-project", "1", compartments={"synthetic-alpha"})
    assert saved["boards"][0]["digest"] == board.digest
    assert not (root / "public" / "refs" / "projects").exists()


@pytest.mark.asyncio
async def test_nested_validation_keeps_json_for_correction(tmp_path):
    app = ConfigApp("board", tmp_path / "store", board_draft())
    async with app.run_test(size=(80, 24)) as pilot:
        invalid = '[{"role":"mcu","part":"missing-vendor","documents":[]}]'
        app.query_one("#parts", TextArea).load_text(invalid)
        await next_step(pilot)
        assert not app.reviewing
        assert "parts.0.vendor" in str(app.query_one("#error-parts", Static).render())
        assert app.query_one("#parts", TextArea).text == invalid
        assert not (tmp_path / "store").exists()


@pytest.mark.asyncio
async def test_duplicate_json_key_is_an_inline_error(tmp_path):
    app = ConfigApp("board", tmp_path / "store", board_draft())
    async with app.run_test(size=(80, 24)) as pilot:
        app.query_one("#parts", TextArea).load_text('[{"role":"first","role":"second"}]')
        await next_step(pilot)
        assert not app.reviewing
        assert "Duplicate configuration key: role" in str(app.query_one("#error-parts", Static).render())
        assert not (tmp_path / "store").exists()


@pytest.mark.parametrize("field,value", [("boards", None), ("boards", {}), ("compartments", "alpha"), ("compartments", [123])])
def test_malformed_import_shapes_report_field(tmp_path, field, value):
    with pytest.raises(ValidationError) as caught:
        ConfigApp("project", tmp_path / "store", {field: value})
    assert field in caught.value.errors


@pytest.mark.parametrize("value", [None, []])
def test_malformed_v1_board_reports_field(tmp_path, value):
    with pytest.raises(ValidationError) as caught:
        ConfigApp("project", tmp_path / "store", {"schema": "caiman.project/1", "board": value})
    assert "board" in caught.value.errors


def test_v1_import_is_restated_with_its_one_board(tmp_path):
    app = ConfigApp("project", tmp_path / "store", {
        "schema": "caiman.project/1", "board": {"name": "demo", "version": "A"},
        "features": [{"name": "boot", "scope": "required", "realized_on": ["mcu"]}]})
    assert app.draft["schema"] == "caiman.project.v2"
    assert app.draft["boards"] == [{"name": "demo", "version": "A"}]
    assert app.draft["features"][0]["realized_on"] == [{"board": "demo", "version": "A", "role": "mcu"}]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["board", "project"])
async def test_blank_template_can_be_opened_and_corrected(tmp_path, kind):
    app = ConfigApp(kind, tmp_path / "store")
    async with app.run_test(size=(80, 24)) as pilot:
        await next_step(pilot)
        assert not app.reviewing
        assert kind in str(app.query_one("#status", Static).render())
        assert not (tmp_path / "store").exists()
