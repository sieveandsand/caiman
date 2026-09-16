"""The caiman mascot: solid pixel art built from half-block characters.

A terminal cell is about twice as tall as it is wide, so each cell holds two
square pixels stacked vertically. The upper half block U+2580 is painted with
the top pixel as its foreground and the bottom pixel as its background; U+2584
covers a cell whose top pixel is transparent. Most terminals draw block elements
themselves, edge to edge, which is what makes the figure solid rather than
dotted. No font files, rasterizer, or generated assets are involved.
"""

from rich.style import Style
from rich.text import Text

UPPER_HALF = "▀"
LOWER_HALF = "▄"

# One key per colour; "." is transparent.
PALETTE = {
    "g": "#5fae3c",  # green hide
    "d": "#34612a",  # dark bands: brow, back scutes, smile, tail tip, and feet
    "w": "#d8c25a",  # yellow iris
    "k": "#11170c",  # pupil
    "p": "#b5dc86",  # pale cheek, where the jaw lightens toward the belly
}

# Square pixels, side profile facing left toward the title: a raised yellow eye
# with a forward pupil, back scutes, a long smile ending in a pale cheek, and
# four legs mid-stride. Kept to nine pixel rows so the masthead stays five
# terminal rows tall.
SPRITE = (
    ".......dddd.......................",
    "......dwwkd..d.d.d.d.d.d.d.d......",
    ".ggggggwwkggggggggggggggggggggg...",
    "ggggggggggggggggggggggggggggggggg.",
    "ddddddddgpgggggggggggggggggggggggd",
    ".gggggggggggggggggggggggggggggggg.",
    "......gg.gg..............gg.gg....",
    ".....gg..gg.............gg..gg....",
    ".....dd..dd.............dd..dd....",
)

WIDTH = max(len(row) for row in SPRITE)
HEIGHT = (len(SPRITE) + 1) // 2  # terminal rows


def render_mascot() -> Text:
    """Return the sprite as half blocks, one terminal cell per pixel column."""
    rows = [row.ljust(WIDTH, ".") for row in SPRITE]
    if len(rows) % 2:
        rows.append("." * WIDTH)
    art = Text(no_wrap=True, overflow="crop")
    for y in range(0, len(rows), 2):
        if y:
            art.append("\n")
        for top, bottom in zip(rows[y], rows[y + 1]):
            top, bottom = PALETTE.get(top), PALETTE.get(bottom)
            if top:
                art.append(UPPER_HALF, Style(color=top, bgcolor=bottom))
            elif bottom:
                art.append(LOWER_HALF, Style(color=bottom))
            else:
                art.append(" ")
    return art
