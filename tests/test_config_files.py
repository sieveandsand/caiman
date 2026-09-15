import json
import stat

import pytest

from caiman.config_files import read_draft, template, write_draft


def test_export_round_trip_and_private_mode(tmp_path):
    path = tmp_path / "drafts/project.json"
    data = template("project")
    data["customer"] = "Synthetic customer"
    write_draft(path, data)
    assert read_draft(path) == data
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_export_never_clobbers_existing_file_or_symlink(tmp_path):
    target = tmp_path / "existing.json"
    target.write_text("my work")
    link = tmp_path / "alias.json"
    link.symlink_to(target)
    for path in [target, link]:
        with pytest.raises(FileExistsError):
            write_draft(path, template("board"))
    assert target.read_text() == "my work"


@pytest.mark.parametrize("text", ['[]', '{"compartments":[],"compartments":["alpha"]}', '{"board":'])
def test_invalid_config_is_not_silently_interpreted(tmp_path, text):
    path = tmp_path / "draft.json"
    path.write_text(text)
    with pytest.raises(ValueError):
        read_draft(path)
