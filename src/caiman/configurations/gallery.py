"""Project cards grouped by their declared compartments."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path

from rich.console import Console
from rich.text import Text
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static
from caiman.ui.cards import CARD_CSS, AddTile, CardFrame, OverviewCard, resize_card_grid

from caiman.configurations.models import project_boards
from caiman.configurations.service import ConfigurationService
from caiman.ui.heading import fullwidth_title
from caiman.ui.navigation import NavigationApp
from caiman.storage.store import Store
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class ProjectCard(OverviewCard):
    """A project overview with its pinned board and configuration counts."""

    def __init__(self, record: dict, *, index: int):
        super().__init__('', id=f'project-{index}', classes='dashboard-tile project-card card-face')
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
            rows = fullwidth_title(value, available)
            if rows:
                for row in rows:
                    label.append(row + '\n', style=f'bold {color}')
            else:
                line(caption, f'bold {color}')

        heading(manifest['project'], manifest['project'], '#eef3e6')
        line('')
        heading(manifest['version'], 'Version ' + manifest['version'], '#7fdc4f')
        line('')
        line(f"{len(manifest.get('documents', []))} Docs · {len(manifest.get('features', []))} Features", 'bold #aab69c')
        line('')
        line(manifest['customer'], '#dfe6d3')
        for board in project_boards(manifest):
            line(f"Board: {board['name']} @ {board['version']}", '#dfe6d3')
        label.rstrip()
        self.label = label
        height = len(label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class ProjectCardFrame(CardFrame):
    def __init__(self, card):
        super().__init__(card)
        self.add_class('project-card-frame')

class ProjectGalleryApp(NavigationApp):
    TITLE = 'Caiman · Projects'
    BINDINGS = [
        ('e', 'edit_selected', 'Edit project'),
        ('pagedown', 'page_down', 'Scroll down'),
        ('pageup', 'page_up', 'Scroll up'),
    ]
    CSS = TERMINAL_CSS + CARD_CSS + f'''
    #gallery {{ height: auto; }}
    .project-grid {{ height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }}
    .add-grid {{ margin-top: 1; }}
    .compartment-heading {{ height: auto; margin: 1 0; color: #7fdc4f; text-style: bold; }}
    #gallery-status {{ height: auto; margin-bottom: 1; color: #aab69c; }}
    #back {{ width: auto; }}
    '''

    def __init__(self, *, root: Path, compartments=()):
        super().__init__()
        apply_theme(self)
        self.compartments = list(compartments)
        self.service = ConfigurationService(Store(root))
        self.records = []

    def navigation_help(self):
        return 'hjkl move · Enter/e edit project · PgUp/PgDn scroll · q back'

    def compose(self):
        yield Static('caiman  /  projects', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Loading registered projects…', id='gallery-status', markup=False)
            yield Vertical(id='gallery')
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
            yield Button('Refresh catalog', id='refresh')
        yield self.navigation_hint()

    async def on_mount(self):
        await self.refresh_catalog()

    async def refresh_catalog(self):
        try:
            self.records = await asyncio.to_thread(self.service.list_configs, 'project', compartments=self.compartments)
            self.records.sort(key=lambda record: (record['manifest']['project'], record['digest']))
            gallery = self.query_one('#gallery', Vertical)
            await gallery.remove_children()
            groups = {}
            for index, record in enumerate(self.records):
                # Multi-compartment projects appear once under their complete scope.
                scope = tuple(sorted(record['manifest']['compartments']))
                groups.setdefault(scope, []).append(ProjectCard(record, index=index))
            for scope, cards in sorted(groups.items()):
                await gallery.mount(Static(', '.join(scope), classes='compartment-heading', markup=False))
                await gallery.mount(Grid(*(ProjectCardFrame(card) for card in cards), classes='project-grid'))
            # A new project may belong to any compartment, so its card follows every group.
            add = AddTile('Add project', id='add-project')
            await gallery.mount(Grid(CardFrame(add), classes='project-grid add-grid'))
            self.resize_cards(self.size.width)
            status = (f'{len(self.records)} Projects · Enter to Edit' if self.records else
                      'No projects registered in your remembered compartments.')
            self.query_one('#gallery-status', Static).update(status)
            self.call_after_refresh((self.query(ProjectCard).first() if self.records else add).focus)
        except (OSError, ValueError) as error:
            self.query_one('#gallery-status', Static).update(f'Cannot load projects: {error}')

    def on_resize(self, event):
        self.resize_cards(event.size.width)

    def resize_cards(self, terminal_width):
        columns = 2 if terminal_width >= 100 else 1
        # Reserve body padding and the two-cell scrollbar, plus column gutters.
        width = max(16, (terminal_width - 6 - (columns - 1) - 2) // columns)
        for grid in self.query('.project-grid'):
            resize_card_grid(grid, width, columns)

    async def on_button_pressed(self, event):
        if isinstance(event.button, ProjectCard):
            record = event.button.record
            self.exit(deepcopy({'manifest': record['manifest'], 'digest': record['digest']}))
        elif event.button.id == 'add-project':
            self.exit('add')
        elif event.button.id == 'refresh':
            await self.refresh_catalog()
        elif event.button.id == 'back':
            self.action_cancel()

    def action_edit_selected(self):
        if isinstance(self.focused, ProjectCard):
            record = self.focused.record
            self.exit(deepcopy({'manifest': record['manifest'], 'digest': record['digest']}))

    def action_page_down(self):
        self.query_one('#body', VerticalScroll).scroll_page_down(animate=False)

    def action_page_up(self):
        self.query_one('#body', VerticalScroll).scroll_page_up(animate=False)

    def action_cancel(self):
        self.exit(None)
