"""Read-only board cards that hand an explicit selection to the editor workflow."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path

from rich.console import Console
from rich.text import Text
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Static
from caiman.ui.cards import CARD_CSS, AddTile, CardFrame, OverviewCard, resize_card_grid

from caiman.configurations.service import ConfigurationService
from caiman.ui.heading import card_heading
from caiman.ui.navigation import NavigationApp
from caiman.storage.store import Store
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class BoardCard(OverviewCard):
    """A compact board overview with a prominent identity and hardware counts."""

    def __init__(self, record: dict, *, index: int):
        super().__init__('', id=f'board-{index}', classes='dashboard-tile board-card card-face')
        self.record = record

    def format_card(self, width: int) -> int:
        manifest = self.record['manifest']
        available = max(1, width - 6)
        label = Text(no_wrap=True, overflow='crop')

        console = Console()

        def line(value, style=''):
            for wrapped in Text(value).wrap(console, available, overflow='fold'):
                label.append(wrapped.plain + '\n', style=style)

        def heading(value, caption, color):
            label.append(card_heading(value, available, secondary=color == '#7fdc4f'))
            label.append('\n')

        heading(manifest['board'], manifest['board'], '#eef3e6')
        line('')
        heading(manifest['version'], 'Version ' + manifest['version'], '#7fdc4f')
        line('')
        parts = manifest['parts']
        documents = len(manifest.get('documents', [])) + sum(len(part.get('documents', [])) for part in parts)
        line(f"{len(parts)} Parts · {len(manifest.get('links', []))} Links · {documents} Docs", 'bold #aab69c')
        if parts:
            line('')
        for part in parts:
            line(part['part'], '#dfe6d3')
        label.rstrip()
        self.label = label
        height = len(label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class BoardCardFrame(CardFrame):
    def __init__(self, card):
        super().__init__(card)
        self.add_class('board-card-frame')

class BoardGalleryApp(NavigationApp):
    TITLE = 'Caiman · Boards'
    BINDINGS = [
        ('e', 'edit_selected', 'Edit board'),
        ('pagedown', 'page_down', 'Scroll down'),
        ('pageup', 'page_up', 'Scroll up'),
    ]
    CSS = TERMINAL_CSS + CARD_CSS + f'''
    #gallery {{ height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }}
    #gallery-status {{ height: auto; margin-bottom: 1; color: #aab69c; }}
    #back {{ width: auto; }}
    '''

    def __init__(self, store_root: Path):
        super().__init__()
        apply_theme(self)
        self.store_root = store_root
        self.service = ConfigurationService(Store(store_root))
        self.records = []

    def navigation_help(self):
        return 'hjkl move · Enter/e edit board · PgUp/PgDn scroll · q back'

    def compose(self):
        yield Static('caiman  /  boards', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Loading registered boards…', id='gallery-status', markup=False)
            yield Grid(id='gallery')
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
        yield self.navigation_hint()

    async def on_mount(self):
        grid = self.query_one('#gallery', Grid)
        add = AddTile('Add board', id='add-board')
        try:
            self.records = await asyncio.to_thread(self.service.list_configs, 'board')
            # Group names for browsing; opaque version labels have no ordering semantics.
            self.records.sort(key=lambda record: (record['manifest']['board'], record['digest']))
            cards = [BoardCard(record, index=index) for index, record in enumerate(self.records)]
            await grid.mount(*(BoardCardFrame(card) for card in cards), CardFrame(add))
            self.resize_cards(self.size.width)
            self.query_one('#gallery-status', Static).update(
                f'{len(cards)} Boards · Enter to Edit' if cards else 'No boards registered yet.')
            self.call_after_refresh((cards[0] if cards else add).focus)
        except (OSError, ValueError) as error:
            self.query_one('#gallery-status', Static).update(f'Cannot load boards: {error}')

    def on_resize(self, event):
        self.resize_cards(event.size.width)

    def resize_cards(self, terminal_width):
        grid = self.query_one('#gallery', Grid)
        if not grid.children:
            return
        columns = 2 if terminal_width >= 100 else 1
        # Reserve body padding and the two-cell scrollbar, plus column gutters.
        width = max(16, (terminal_width - 6 - (columns - 1) - 2) // columns)
        resize_card_grid(grid, width, columns)

    def on_button_pressed(self, event):
        if isinstance(event.button, BoardCard):
            self.exit(deepcopy(event.button.record))
        elif event.button.id == 'add-board':
            self.exit('add')
        elif event.button.id == 'back':
            self.action_cancel()

    def action_edit_selected(self):
        if isinstance(self.focused, BoardCard):
            self.exit(deepcopy(self.focused.record))

    def action_page_down(self):
        self.query_one('#body', VerticalScroll).scroll_page_down(animate=False)

    def action_page_up(self):
        self.query_one('#body', VerticalScroll).scroll_page_up(animate=False)

    def action_cancel(self):
        self.exit(None)
