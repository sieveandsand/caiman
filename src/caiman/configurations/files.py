"""Editable JSON drafts, independent of terminal widgets and stored manifests."""

from __future__ import annotations

import json
import os
from pathlib import Path


# Spellings offered when typing a vendor, so one board does not end up with
# `nxp` on one part and `NXP` on another. Ordered by roughly how often firmware
# work pins documentation from each, because a prefix match takes the first hit.
#
# This is a convenience, never a constraint: a vendor field accepts any declared
# string, and nothing validates against this list or derives anything from it
# (I-8). Adding a name here changes what is suggested and nothing else.
COMMON_VENDORS = (
    "nxp", "stm", "ti", "infineon", "renesas", "microchip", "nordic", "espressif",
    "silabs", "ambiq", "analog", "maxim", "onsemi", "toshiba", "rohm", "diodes",
    "nexperia", "vishay", "murata", "tdk", "bosch", "sensirion", "winbond",
    "micron", "macronix", "issi", "cypress", "broadcom", "marvell", "realtek",
    "mediatek", "qualcomm", "lattice", "microsemi",
)


def vendor_suggestions(manifest: dict | None = None) -> tuple[str, ...]:
    """Common vendors, then any this board already declares that is not one.

    Keeping the common spellings first makes completion predictable; the trailing
    names exist so a vendor already on the board stays completable too.
    """
    if not isinstance(manifest, dict):
        return COMMON_VENDORS
    parts = manifest.get("parts") if isinstance(manifest.get("parts"), list) else []
    declared = [manifest.get("vendor")]
    declared += [part.get("vendor") for part in parts if isinstance(part, dict)]
    known = {name.casefold() for name in COMMON_VENDORS}
    extra = {}
    for name in declared:
        if isinstance(name, str) and name.strip() and name.casefold() not in known:
            extra.setdefault(name.casefold(), name)
    return COMMON_VENDORS + tuple(extra.values())


def template(kind: str) -> dict:
    if kind == "board":
        return {
            "board": "", "version": "",
            "parts": [{"role": "application-mcu", "vendor": "", "part": "", "documents": []}],
            "links": [],
        }
    if kind == "project":
        return {
            "project": "", "version": "", "customer": "", "compartments": [],
            "boards": [{"name": "", "version": ""}], "spec_set": "",
            "documents": [], "features": [],
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
