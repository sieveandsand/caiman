import io
import sys
from pathlib import Path

import pytest

from caiman.cli.commands import main, store_path


def test_noninteractive_ingestion_does_not_create_store(tmp_path, monkeypatch, capsys):
    root = tmp_path / "absent-store"
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    assert main(["ingest", "missing.md", "--store", str(root)]) == 2
    assert "interactive terminal" in capsys.readouterr().err
    assert not root.exists()


def test_little_caiman_requires_terminal_without_writes(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'absent-store'
    monkeypatch.setattr(sys, 'stdin', io.StringIO())
    assert main(['little', '--store', str(root)]) == 2
    assert 'interactive terminal' in capsys.readouterr().err
    assert not root.exists()


def test_bare_launcher_requires_terminal_without_writes(tmp_path, monkeypatch, capsys):
    root = tmp_path / 'absent-store'
    monkeypatch.setattr(sys, 'stdin', io.StringIO())
    assert main(['--store', str(root)]) == 2
    assert 'interactive terminal' in capsys.readouterr().err
    assert not root.exists()


@pytest.mark.parametrize('before', [True, False])
def test_store_option_routes_before_or_after_ingest(tmp_path, monkeypatch, before):
    import caiman.dashboard.workflow
    class Terminal(io.StringIO):
        def isatty(self):
            return True
    monkeypatch.setattr(sys, 'stdin', Terminal())
    monkeypatch.setattr(sys, 'stdout', Terminal())
    captured = []
    monkeypatch.setattr(caiman.dashboard.workflow, 'run_workflow', lambda root, **kwargs: captured.append(root) or 0)
    args = ['--store', str(tmp_path), 'ingest'] if before else ['ingest', '--store', str(tmp_path)]
    assert main(args) == 0
    assert captured == [tmp_path]


def test_explicit_store_takes_precedence_over_broken_config(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "caiman").mkdir()
    (tmp_path / "caiman/config.toml").write_text("[broken")
    assert store_path(tmp_path / "chosen") == tmp_path / "chosen"


def test_config_store_root(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "caiman").mkdir()
    desired = tmp_path / "store"
    (tmp_path / "caiman/config.toml").write_text(f'store_root = "{desired}"\n')
    assert store_path(None) == desired
    assert not desired.exists()


def test_bad_config_does_not_silently_select_another_store(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    (tmp_path / "caiman").mkdir()
    (tmp_path / "caiman/config.toml").write_text("store_root = 12\n")
    with pytest.raises(ValueError, match="store_root"):
        store_path(None)


def test_default_store_is_outside_working_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.chdir(tmp_path)
    assert store_path(None) == tmp_path / "data/caiman/store"
    assert not (tmp_path / "data").exists()


def test_help_and_version_do_not_load_tui(monkeypatch, capsys):
    monkeypatch.delitem(sys.modules, "caiman.documents.tui", raising=False)
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "0.1.0" in capsys.readouterr().out
    assert "caiman.documents.tui" not in sys.modules


@pytest.mark.parametrize("kind", ["board", "project"])
def test_configure_requires_terminal_without_writes(kind, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO())
    root = tmp_path / "store"
    assert main([kind, "configure", "--store", str(root)]) == 2
    assert "interactive terminal" in capsys.readouterr().err
    assert not root.exists()


def test_template_can_be_written_without_a_terminal(tmp_path, monkeypatch):
    from caiman.configurations.files import read_draft

    monkeypatch.setattr(sys, "stdin", io.StringIO())
    path = tmp_path / "board.json"
    assert main(["board", "template", "--output", str(path)]) == 0
    assert read_draft(path)["parts"][0]["role"] == "application-mcu"
