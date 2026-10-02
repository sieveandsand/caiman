"""Equipment label typography shared by gallery and editor cards."""

from rich.console import Console
from rich.text import Text


def card_heading(value: str, width: int, *, secondary=False):
    """Render normal-width identities with consistent styling at every width."""
    width = max(1, width)
    # ASCII casing is presentation only; preserve non-ASCII identifiers exactly.
    display = value.upper() if not secondary and value.isascii() else value
    color = '#7fdc4f' if secondary else 'bold #eef3e6'
    prefix = '  ' if secondary else '▌ '
    # Keep at least one cell for text even in an exceptionally narrow editor.
    if width <= len(prefix):
        prefix = prefix[:max(0, width - 1)]
    if secondary:
        display = '[ ' + display + ' ]'
    rows = Text(display).wrap(Console(), max(1, width - len(prefix)), overflow='fold')
    result = Text(no_wrap=True, overflow='crop')
    for index, row in enumerate(rows):
        if index:
            result.append('\n')
        result.append(prefix if index == 0 else ' ' * len(prefix), style='#7fdc4f')
        result.append(row.plain, style=color)
    return result
