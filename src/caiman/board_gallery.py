"""Read-only board cards that hand an explicit selection to the editor workflow."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
import textwrap

from rich.text import Text
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Static

from .config_store import ConfigurationService
from .navigation import NavigationApp
from .store import Store
from .theme import DOT_BORDER, TERMINAL_CSS, apply_theme


class BoardCard(Button):
    """A complete board summary; no parts are omitted to make the card shorter."""

    def __init__(self, record: dict, *, index: int):
        super().__init__('', id=f'board-{index}', classes='dashboard-tile board-card')
        self.record = record

    def on_focus(self):
        self.scroll_visible(animate=False, top=True)

    def format_card(self, width: int) -> int:
        manifest = self.record['manifest']
        available = max(12, width - 4)
        label = Text(no_wrap=True, overflow='crop')

        def line(value, style='', accent=0):
            """One wrapped field; the first *accent* characters take the highlight."""
            for index, wrapped in enumerate(textwrap.wrap(value, available, break_long_words=True, break_on_hyphens=False) or ['']):
                start = len(label.plain)
                label.append(wrapped + '\n', style=style)
                if accent and not index:
                    label.stylize('#7fdc4f', start, start + min(accent, len(wrapped)))

        line(manifest['board'], 'bold')
        version = 'Version ' + manifest['version']
        line(f"{version} · Public · {self.record['digest'][7:19]}", '#8d9982', accent=len(version))
        line(f"Parts ({len(manifest['parts'])})", 'bold')
        for part in manifest['parts']:
            line(f"{part['role']} · {part['part']}", accent=len(part['role']))
            # Silicon revision, schematic reference and document count all stay on
            # the card; they share one line rather than taking three.
            details = [prefix + value for prefix, value in
                       (('Silicon ', part.get('silicon_revision')), ('Ref ', part.get('refdes'))) if value]
            details.append(f"Docs {len(part['documents'])}")
            line(' · '.join(details), '#aab69c')
        line(f"Hardware links {len(manifest.get('links', []))}", '#8d9982')
        label.rstrip()
        self.label = label
        height = len(label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class BoardGalleryApp(NavigationApp):
    TITLE = 'Caiman · Boards'
    BINDINGS = [
        ('e', 'edit_selected', 'Edit board'),
        ('pagedown', 'page_down', 'Scroll down'),
        ('pageup', 'page_up', 'Scroll up'),
    ]
    CSS = TERMINAL_CSS + f'''
    #gallery {{ height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }}
    /* Button centres its label by default, which content-align alone does not undo. */
    .board-card {{ width: 100%; min-width: 0; height: auto; margin: 0; padding: 0 1; content-align: left top; text-align: left; background: #000000; color: #dfe6d3; text-style: none; border: {DOT_BORDER} #33422e; }}
    .board-card:hover, .board-card:focus {{ background: #000000; color: #dfe6d3; text-style: none; border: {DOT_BORDER} #7fdc4f; }}
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
        try:
            self.records = await asyncio.to_thread(self.service.list_configs, 'board')
            # Group names for browsing; opaque version labels have no ordering semantics.
            self.records.sort(key=lambda record: (record['manifest']['board'], record['digest']))
            if not self.records:
                self.query_one('#gallery-status', Static).update('No boards registered. Create a board from the dashboard.')
                return
            cards = [BoardCard(record, index=index) for index, record in enumerate(self.records)]
            await self.query_one('#gallery', Grid).mount(*cards)
            self.resize_cards(self.size.width)
            self.query_one('#gallery-status', Static).update(f'{len(cards)} board snapshots · Select a card to edit its configuration in Vim.')
            self.call_after_refresh(cards[0].focus)
        except (OSError, ValueError) as error:
            self.query_one('#gallery-status', Static).update(f'Cannot load boards: {error}')

    def on_resize(self, event):
        self.resize_cards(event.size.width)

    def resize_cards(self, terminal_width):
        cards = list(self.query(BoardCard))
        if not cards:
            return
        columns = 2 if terminal_width >= 100 else 1
        # Four cells are the shared body padding; one cell separates columns.
        width = max(16, (terminal_width - 4 - (columns - 1) - 1) // columns)
        heights = [card.format_card(width) for card in cards]
        rows = [max(heights[index:index + columns]) for index in range(0, len(cards), columns)]
        grid = self.query_one('#gallery', Grid)
        grid.styles.grid_size_columns = columns
        grid.styles.grid_rows = rows
        grid.styles.height = sum(rows) + len(rows) - 1

    def on_button_pressed(self, event):
        if isinstance(event.button, BoardCard):
            self.exit(deepcopy(event.button.record))
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
