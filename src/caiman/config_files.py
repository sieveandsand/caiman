"""Editable JSON drafts, independent of terminal widgets and stored manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path


def template(kind: str) -> dict:
    if kind == "board":
        return {
            "board": "", "version": "",
            "parts": [{"role": "application-mcu", "part": "", "documents": []}],
            "links": [],
        }
    if kind == "project":
        return {
            "project": "", "version": "", "customer": "", "compartments": [],
            "board": {"name": "", "version": ""}, "spec_set": "",
            "documents": [], "precedence": [], "features": [],
        }
    raise ValueError("Choose board or project")


def unique_keys(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate configuration key: {key}")
        result[key] = value
    return result


def read_draft(path: Path) -> dict:
    try:
        with path.expanduser().open(encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=unique_keys)
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}:{error.lineno}:{error.colno}: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError("Configuration must be a JSON object")
    return value


def write_draft(path: Path, data: dict) -> None:
    """Explicit exports create a private file and never clobber existing work."""
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    path = path.expanduser().absolute()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as file:
        file.write(content)
        file.flush()
        os.fsync(file.fileno())
