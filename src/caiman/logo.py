"""Doto font artwork rendered as ordinary terminal Braille cells.

The atlas is generated offline by scripts/build_doto_atlas.py. No font renderer,
image service, network request, or AI is involved at application runtime.
"""
from functools import lru_cache
from importlib.resources import files
import json

from rich.cells import cell_len


@lru_cache(maxsize=1)
def _atlas() -> dict:
    path = files("caiman").joinpath("assets/doto-atlas.json")
    if not path.is_file():
        return {"sizes": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _plain(text: str, max_width: int) -> str:
    lines, line = [], ""
    for char in text:
        if char == "\n":
            lines.append(line)
            line = ""
        elif cell_len(line + char) <= max_width:
            line += char
        else:
            if line:
                lines.append(line)
            line = char
    lines.append(line)
    return "\n".join(lines)


def render_logo(text: str, max_width: int = 60) -> str:
    """Return literal multiline artwork; display with Rich markup disabled.

    Choose the largest bundled Doto raster that fits. Long or unsupported names
    fall back to exact, wrapped text, preserving case and Unicode characters.
    """
    if not isinstance(text, str):
        raise TypeError("Logo text must be a string")
    if type(max_width) is not int or max_width < 2:
        raise ValueError("Logo width must be at least two terminal cells")
    if not text:
        return ""
    for size in reversed(_atlas()["sizes"]):
        glyphs = size["glyphs"]
        if any(char not in glyphs for char in text):
            continue
        width = sum(len(glyphs[char][0]) for char in text)
        if width <= max_width:
            return "\n".join("".join(glyphs[char][row] for char in text).rstrip()
                             for row in range(size["rows"]))
    return _plain(text, max_width)
