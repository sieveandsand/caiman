"""Document overview cards and their complete registration details."""

from rich.console import Console
from rich.text import Text
from textual.widgets import Static

from caiman.ui.cards import CardFrame, OverviewCard, card_label
from caiman.ui.heading import card_heading


def document_name(manifest):
    return manifest.get('name') or manifest.get('part') or manifest.get('program') or manifest['original_filename']


class DocumentCard(OverviewCard):
    def __init__(self, record, *, index):
        super().__init__('', id=f'document-{index}', classes='dashboard-tile card-face')
        self.record = record

    def format_card(self, width):
        manifest = self.record['manifest']
        available = max(1, width - 6)
        label = Text(no_wrap=True, overflow='crop')
        console = Console()

        def line(value, style):
            for wrapped in Text(value).wrap(console, available, overflow='fold'):
                label.append(wrapped.plain + '\n', style=style)

        def heading(value, caption, color):
            label.append(card_heading(value, available, secondary=color == '#7fdc4f'))
            label.append('\n')

        identity = document_name(manifest)
        heading(identity, identity, '#eef3e6')
        label.append('\n')
        heading(manifest['version'], 'Version ' + manifest['version'], '#7fdc4f')
        label.append('\n')
        line(manifest.get('description') or f"{manifest['issuer']} · {manifest.get('doc_type', 'Document')}", 'bold #aab69c')
        label.rstrip()
        self.label = label
        height = len(label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class CollectionCard(OverviewCard):
    def __init__(self, record, *, index):
        super().__init__('', id=f'collection-{index}', classes='dashboard-tile card-face')
        self.record = record

    def format_card(self, width):
        manifest = self.record['manifest']
        summary = f"Collection · {len(manifest['documents'])} documents"
        if manifest['description']:
            summary += '\n\n' + manifest['description']
        self.label = card_label(manifest['name'], summary, width)
        height = len(self.label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class CollectionFrame(CardFrame):
    """Persistent solid back cards, with a separate focus-only dotted shadow."""

    DEFAULT_CSS = '''
    CollectionFrame > .stack-back { position: absolute; background: #000000; border: solid #33422e; }
    CollectionFrame > .stack-far { layer: far; offset: 2 2; }
    CollectionFrame > .stack-near { layer: near; offset: 1 1; }
    '''

    def __init__(self, card):
        super().__init__(card)
        # Gallery-level CARD_CSS overrides widget defaults; set stack geometry
        # here so the shared two-layer frame cannot hide the dotted shadow.
        self.styles.layers = ('shadow', 'far', 'near', 'face')

    def compose(self):
        yield Static('', classes='card-shadow', markup=False)
        yield Static('', classes='stack-back stack-far')
        yield Static('', classes='stack-back stack-near')
        yield self.card

    def resize_card(self, width):
        face_width = max(12, width - 3)
        height = self.card.format_card(face_width)
        self.card.styles.width = face_width
        for layer in self.query('.stack-back, .card-shadow'):
            layer.styles.width = face_width
            layer.styles.height = height
        dots = ('⠢⠔' * ((face_width + 1) // 2))[:face_width]
        shadow = self.query_one('.card-shadow', Static)
        shadow.styles.offset = (3, 3)
        shadow.update('\n'.join([dots] * height))
        self.styles.height = height + 3
        return height + 3
