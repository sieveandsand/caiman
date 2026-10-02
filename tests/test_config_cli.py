import json
import io
import stat
import sys
from types import SimpleNamespace

import pytest

from caiman.cli.commands import main
from caiman.configurations.service import ConfigurationService
from caiman.documents.ingest import prepare_document
from caiman.storage.store import Store


@pytest.fixture
def configured(tmp_path):
    root = tmp_path / "store"
    store = Store(root)
    source = tmp_path / "manual.md"
    source.write_text("# Synthetic manual\n## Serial port\nFictional register.\n")
    doc = store.register(prepare_document(source, {
        "issuer": "example", "part": "mcu", "doc_type": "manual", "version": "Rev 1",
        "structure": "prose", "labels": {"public": True, "compartments": []},
    }))
    service = ConfigurationService(store)
    board = service.prepare("board", {
        "board": "example-board", "version": "Rev A",
        "parts": [{"role": "application-mcu", "vendor": "example", "part": "mcu",
                   "documents": [{"digest": doc.manifest_digest}]}], "links": [],
    })
    service.register(board)
    project = service.prepare("project", {
        "project": "example-program", "version": "Prototype", "customer": "Synthetic customer",
        "compartments": ["alpha"], "boards": [{"name": "example-board", "version": "Rev A"}],
        "spec_set": "Synthetic release 1", "documents": [], "features": [],
    })
    service.register(project)
    return root, board, project


def test_bare_board_lists_versions_and_explicit_show_loads_snapshot(configured, capsys):
    root, board, _ = configured
    assert main(["board", "show", "example-board", "--store", str(root)]) == 0
    assert json.loads(capsys.readouterr().out) == ["Rev A"]
    assert main(["board", "show", "example-board", "--version", "Rev A", "--store", str(root)]) == 0
    assert json.loads(capsys.readouterr().out) == board.manifest


def test_project_export_requires_compartments_and_preserves_pins(configured, tmp_path, capsys):
    root, _, project = configured
    output = tmp_path / "project.json"
    args = ["project", "export", "example-program", "--version", "Prototype",
            "--store", str(root), "--output", str(output)]
    assert main(args) == 1
    assert not output.exists()
    assert "Synthetic customer" not in capsys.readouterr().err
    assert main([*args, "--compartment", "alpha"]) == 0
    assert json.loads(output.read_text()) == project.manifest
    assert stat.S_IMODE(output.stat().st_mode) == 0o600
    assert main([*args, "--compartment", "alpha"]) == 1
    assert json.loads(output.read_text()) == project.manifest


def test_file_validation_is_read_only(configured, tmp_path, capsys):
    root, board, _ = configured
    draft = tmp_path / "board.json"
    draft.write_text(json.dumps(board.manifest))
    before = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert main(["board", "validate", str(draft), "--store", str(root)]) == 0
    assert json.loads(capsys.readouterr().out) == board.manifest
    after = {str(path): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    assert before == after


def test_document_catalog_uses_exact_digest(configured, capsys):
    root, board, _ = configured
    assert main(["documents", "--store", str(root)]) == 0
    records = json.loads(capsys.readouterr().out)
    assert records[0]["digest"] == board.manifest["parts"][0]["documents"][0]["digest"]
    assert records[0]["ref"].endswith("Rev%201")


def test_new_version_opens_copy_with_pins_and_declared_lineage(configured, monkeypatch):
    import caiman.configurations.tui

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    root, board, _ = configured
    opened = {}

    def app(**kwargs):
        opened.update(kwargs)
        return SimpleNamespace(run=lambda: None)

    monkeypatch.setattr(sys, "stdin", Terminal())
    monkeypatch.setattr(sys, "stdout", Terminal())
    monkeypatch.setattr(caiman.configurations.tui, "ConfigApp", app)
    assert main(["board", "new-version", "example-board", "--from-version", "Rev A",
                 "--version", "Rev B", "--relation", "Synthetic revision",
                 "--store", str(root)]) == 0
    assert opened["draft"]["parts"] == board.manifest["parts"]
    assert opened["draft"]["derives_from"] == "Rev A"
    assert opened["draft"]["version"] == "Rev B"
    assert opened["draft"]["relation"] == "Synthetic revision"
    assert ConfigurationService(Store(root)).list_versions("board", "example-board") == ["Rev A"]
