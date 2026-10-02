"""Shared card headings and dotted focus shadows for Caiman cards."""

from rich.console import Console
from rich.text import Text
from textual.widget import Widget
from textual.widgets import Button, Static

from caiman.ui.heading import card_heading

CARD_CSS = """
    .card-frame { width: 100%; height: auto; layers: shadow face; }
    .card-shadow { position: absolute; offset: 1 1; layer: shadow; visibility: hidden; color: #466d36; background: #000000; }
    .card-frame.selected .card-shadow { visibility: visible; }
    /* Button centres its label by default, which content-align alone does not undo. */
    .card-face { layer: face; width: 100%; min-width: 0; height: auto; margin: 0; padding: 0 1; content-align: left top; text-align: left; background: #000000; color: #dfe6d3; text-style: none; border: solid #33422e; }
    .card-face:hover, .card-face:focus { background: #000000; color: #dfe6d3; text-style: none; border: solid #7fdc4f; }
"""


def card_label(title, summary, width):
    # Borders, face padding, and Textual Button's one-cell line padding.
    available = max(1, width - 6)
    label = Text(no_wrap=True, overflow='crop')
    label.append(card_heading(title, available))
    label.append('\n\n')
    for line in Text(summary).wrap(Console(), available, overflow='fold'):
        label.append(line.plain + '\n', style='bold #aab69c')
    label.rstrip()
    return label


class OverviewCard(Button):
    def on_focus(self):
        self.parent.add_class('selected')
        # Scroll only as far as needed; the frame includes the shadow row.
        self.parent.scroll_visible(animate=False)

    def on_blur(self):
        self.parent.remove_class('selected')


class AddTile(OverviewCard):
    """The last card of a gallery grid: a centred plus that starts an addition."""

    def __init__(self, label, *, id):
        super().__init__('', id=id, classes='dashboard-tile add-tile card-face')
        self.action_label = label

    def format_card(self, width):
        # Centre within the text area left after borders and padding.
        available = max(1, width - 6)
        # Centre the plus as one block so its bars stay aligned at any width.
        plus = ' ' * max(0, (available - 5) // 2)
        rows = [plus + '  ┃', plus + '━━╋━━', plus + '  ┃', '', self.action_label.center(available).rstrip()]
        self.label = Text('\n'.join(rows), style='bold #7fdc4f')
        height = len(rows) + 2
        self.styles.height = height
        return height


def resize_card_grid(grid, width, columns):
    """Size every card frame in a gallery grid; rows take their tallest frame."""
    heights = [frame.resize_card(width) for frame in grid.children]
    rows = [max(heights[index:index + columns]) for index in range(0, len(heights), columns)]
    grid.styles.grid_size_columns = columns
    grid.styles.grid_rows = rows or [0]
    grid.styles.height = sum(rows) + max(0, len(rows) - 1)


class CardFrame(Widget):
    """Reserve shadow space so focus never shifts the surrounding grid."""

    def __init__(self, card):
        super().__init__(classes='card-frame')
        self.card = card

    def compose(self):
        yield Static('', classes='card-shadow', markup=False)
        yield self.card

    def resize_card(self, width):
        face_width = max(12, width - 1)
        height = self.card.format_card(face_width)
        self.card.styles.width = face_width
        shadow = self.query_one('.card-shadow', Static)
        shadow.styles.width = face_width
        shadow.styles.height = height
        # The face covers the interior, exposing only an offset right/bottom edge.
        dots = ('⠢⠔' * ((face_width + 1) // 2))[:face_width]
        shadow.update('\n'.join([dots] * height))
        self.styles.height = height + 1
        return height + 1


class DotShadow(Static):
    """Fill the reserved layer at its current size, including expanded editors."""

    def on_resize(self, event):
        width, height = event.size
        # Draw the offset inside the layer so it cannot affect auto height.
        dots = ' ' + ('⠢⠔' * ((width + 1) // 2))[:max(0, width - 1)]
        rows = [' ' * width] + [dots] * max(0, height - 1)
        self.update(Text('\n'.join(rows), style='#466d36'), layout=False)


class EditorFrame(Widget):
    """An opaque face reveals the last column and row of a dotted underlay.

    Percentage sizing lets the shadow shrink when an inline editor collapses;
    an explicit shadow height would contribute to Textual's auto-height layout.
    """

    DEFAULT_CSS = '''
    .editor-frame { width: 100%; height: auto; padding: 0; layers: shadow face; }
    .editor-frame > .editor-face { layer: face; width: 1fr; margin: 0 1 1 0; height: auto; background: #000000; }
    .editor-frame > .card-shadow { color: #466d36; background: #000000; width: 100%; height: 100%; offset: 0 0; position: absolute; layer: shadow; visibility: hidden; }
    .editor-frame.selected > .card-shadow { visibility: visible; }
    '''

    def on_descendant_focus(self, event):
        self.add_class('selected')

    def on_descendant_blur(self, event):
        self.remove_class('selected')


class AddCardFrame(EditorFrame):
    def __init__(self, label, *, id):
        super().__init__()
        self.add_class('editor-frame')
        self.action_label = label
        self.action_id = id

    def compose(self):
        yield DotShadow('', classes='card-shadow', markup=False)
        yield Button('  ┃  \n━━╋━━\n  ┃  \n\n' + self.action_label,
                     id=self.action_id, classes='dashboard-tile add-card editor-face')
