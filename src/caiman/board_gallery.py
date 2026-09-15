"""Read-only board cards that hand an explicit selection to the editor workflow."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path
import textwrap

from rich.text import Text
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Static

from .config_store import ConfigurationService
from .navigation import NavigationApp
from .store import Store
from .theme import TERMINAL_CSS, apply_theme


class BoardCard(Button):
    """A complete board summary; no parts are omitted to make the card shorter."""

    def __init__(self, record: dict, *, index: int, current: bool = False, archived: bool = False):
        super().__init__('', id=f'board-{index}', classes='dashboard-tile board-card')
        self.record = record
        self.current = current
        self.archived = archived

    def on_focus(self):
        self.scroll_visible(animate=False, top=True)

    def format_card(self, width: int) -> int:
        from .logo import render_logo

        manifest = self.record['manifest']
        available = max(12, width - 4)
        label = Text(no_wrap=True, overflow='crop')
        logo = render_logo(manifest['board'], max_width=available)
        version_logo = render_logo(manifest['version'], max_width=available)
        label.append(logo.rstrip() + '\n' + version_logo.rstrip() + '\n\n', style='#d97757')

        def line(value, style=''):
            for wrapped in textwrap.wrap(value, available, break_long_words=True, break_on_hyphens=False) or ['']:
                label.append(wrapped + '\n', style=style)

        line(manifest['board'], 'bold')
        line('Version: ' + manifest['version'])
        if self.current:
            line('Current selection', '#d97757')
        if self.archived:
            line('Pinned snapshot · version label has moved', '#b4afa7')
        line('Public · ' + self.record['digest'][7:19], '#99958e')
        line('')
        line(f"Parts ({len(manifest['parts'])})", 'bold')
        for index, part in enumerate(manifest['parts']):
            if index:
                line('')
            line(part['role'], '#d97757')
            line(part['part'])
            if part.get('silicon_revision'):
                line('Silicon: ' + part['silicon_revision'], '#b4afa7')
            if part.get('refdes'):
                line('Reference: ' + part['refdes'], '#b4afa7')
            line(f"Documents: {len(part['documents'])}", '#99958e')
        line('')
        line(f"Hardware links: {len(manifest.get('links', []))}", '#99958e')
        label.rstrip()
        self.label = label
        height = len(label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class BoardGalleryApp(NavigationApp):
    TITLE = 'Caiman · Boards'
    BINDINGS = [
        ('ctrl+q', 'cancel', 'Back'),
        ('e', 'edit_selected', 'Edit board'),
        ('pagedown', 'page_down', 'Scroll down'),
        ('pageup', 'page_up', 'Scroll up'),
    ]
    CSS = TERMINAL_CSS + '''
    #gallery { height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }
    .board-card { width: 100%; min-width: 0; height: auto; margin: 0; padding: 0 1; content-align: left top; background: #000000; color: #e6e1d8; text-style: none; border: round #49453f; }
    .board-card:hover, .board-card:focus { background: #000000; color: #e6e1d8; text-style: none; border: round #d97757; }
    #gallery-status { height: auto; margin-bottom: 1; color: #b4afa7; }
    #back { width: auto; }
    '''

    def __init__(self, store_root: Path, selected: dict | None = None):
        super().__init__()
        apply_theme(self)
        self.store_root = store_root
        self.selected = deepcopy(selected)
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
        yield Footer()

    async def on_mount(self):
        try:
            self.records = await asyncio.to_thread(self.service.list_configs, 'board')
            archived = None
            if self.selected and not any(record['digest'] == self.selected['digest'] for record in self.records):
                manifest = await asyncio.to_thread(self.service.load_digest, 'board', self.selected['digest'])
                archived = self.selected['digest']
                self.records.append({'manifest': manifest, 'digest': archived, 'name': manifest['board'], 'version': manifest['version'], 'compartment': 'public'})
            # Group names for browsing; opaque version labels have no ordering semantics.
            self.records.sort(key=lambda record: (record['manifest']['board'], record['digest']))
            if not self.records:
                self.query_one('#gallery-status', Static).update('No boards registered. Create a board from the dashboard.')
                return
            current_digest = self.selected['digest'] if self.selected else None
            cards = [BoardCard(record, index=index, current=record['digest'] == current_digest, archived=record['digest'] == archived) for index, record in enumerate(self.records)]
            await self.query_one('#gallery', Grid).mount(*cards)
            self.resize_cards(self.size.width)
            self.query_one('#gallery-status', Static).update(f'{len(cards)} board snapshots · Select a card to edit its configuration in Vim.')
            selected = next((card for card in cards if card.current), cards[0])
            self.call_after_refresh(selected.focus)
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
