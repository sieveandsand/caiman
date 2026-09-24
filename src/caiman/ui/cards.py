"""Shared dot headings and focus shadows for Caiman cards."""

from rich.console import Console
from rich.text import Text
from textual.widget import Widget
from textual.widgets import Button, Static

from caiman.ui.pixel_title import pixel_title

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
    dots = pixel_title(title, available)
    for line in dots or Text(title).wrap(Console(), available, overflow='fold'):
        label.append(str(line) + '\n', style='bold #eef3e6')
    label.append('\n')
    for line in Text(summary).wrap(Console(), available, overflow='fold'):
        label.append(line.plain + '\n', style='bold #aab69c')
    label.rstrip()
    return label


class OverviewCard(Button):
    def on_focus(self):
        self.parent.add_class('selected')
        self.scroll_visible(animate=False, top=True)

    def on_blur(self):
        self.parent.remove_class('selected')


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
