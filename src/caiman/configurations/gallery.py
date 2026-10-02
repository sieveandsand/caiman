"""Project cards filtered by the selected pod tab."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path

from rich.console import Console
from rich.text import Text
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Static, Tabs
from caiman.ui.cards import CARD_CSS, AddTile, CardFrame, OverviewCard, resize_card_grid

from caiman.configurations.models import project_boards
from caiman.configurations.service import ConfigurationService
from caiman.ui.heading import card_heading
from caiman.ui.navigation import NavigationApp
from caiman.ui.pod_tabs import POD_BINDINGS, POD_HELP, PodTabsMixin
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
            label.append(card_heading(value, available, secondary=color == '#7fdc4f'))
            label.append('\n')

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

class ProjectGalleryApp(PodTabsMixin, NavigationApp):
    TITLE = 'Caiman · Projects'
    BINDINGS = POD_BINDINGS + [
        ('e', 'edit_selected', 'Edit project'),
        ('pagedown', 'page_down', 'Scroll down'),
        ('pageup', 'page_up', 'Scroll up'),
    ]
    CSS = TERMINAL_CSS + CARD_CSS + f'''
    #gallery {{ height: auto; }}
    .project-grid {{ height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }}
    .add-grid {{ margin-top: 1; }}
    #gallery-status {{ height: auto; margin-bottom: 1; color: #aab69c; }}
    #back {{ width: auto; }}
    '''

    def __init__(self, *, root: Path, pods=(), pod=None):
        super().__init__()
        apply_theme(self)
        self.pods = list(pods)
        self.service = ConfigurationService(Store(root))
        self.records = []
        self.active_pod = pod or self.service.store.pods.default
        self.tab_pods = {}
        self.render_lock = asyncio.Lock()
        self.busy = False

    def navigation_help(self):
        return f'hjkl move · Enter/e edit project · {POD_HELP} · PgUp/PgDn scroll · q back'

    def compose(self):
        yield Static('caiman  /  projects', id='brand')
        yield Tabs(id='pod-tabs')
        with VerticalScroll(id='body'):
            yield Static('Loading registered projects…', id='gallery-status', markup=False)
            yield Vertical(id='gallery')
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
            yield Button('Refresh catalog', id='refresh')
        yield self.navigation_hint()

    async def on_mount(self):
        await self.refresh_catalog()
        cards = self.query('.card-face')
        if cards:
            self.call_after_refresh(cards.first().focus)

    async def refresh_catalog(self):
        if self.busy:
            return
        self.busy = True
        try:
            self.records = await asyncio.to_thread(self.service.list_configs, 'project', pods=self.pods)
            self.records.sort(key=lambda record: (record['manifest']['project'], record['digest']))
            available = {r['id']: r['name'] for r in self.service.store.pods.list()}
            selected = self.service.store.pods.selected(self.pods)
            available = {key: name for key, name in available.items() if key in selected}
            for record in self.records:
                available.setdefault(record['pod'], record.get('pod_name', record['pod']))
            if not available:
                available = {self.service.store.pods.default: self.service.store.pods.default}
            await self.update_pod_tabs(available)
            await self.render_pod()
        except (OSError, ValueError) as error:
            self.query_one('#gallery-status', Static).update(f'Cannot load projects: {error}')
        finally:
            self.busy = False

    async def render_pod(self):
        async with self.render_lock:
            gallery = self.query_one('#gallery', Vertical)
            await gallery.remove_children()
            records = [record for record in self.records if record['pod'] == self.active_pod]
            cards = [ProjectCard(record, index=index) for index, record in enumerate(records)]
            add = AddTile('Add project', id='add-project')
            await gallery.mount(Grid(*(ProjectCardFrame(card) for card in cards), CardFrame(add), classes='project-grid'))
            self.resize_cards(self.size.width)
            self.query_one('#gallery-status', Static).update(
                f'{len(cards)} Projects · Enter to Edit' if cards else 'No projects in this pod yet.')
            self.query_one('#body', VerticalScroll).scroll_home(animate=False)

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
            self.exit(deepcopy(record))
        elif event.button.id == 'add-project':
            self.exit({'action': 'add', 'pod': self.active_pod})
        elif event.button.id == 'refresh':
            await self.refresh_catalog()
        elif event.button.id == 'back':
            self.action_cancel()

    def action_edit_selected(self):
        if isinstance(self.focused, ProjectCard):
            record = self.focused.record
            self.exit(deepcopy(record))

    def action_page_down(self):
        self.query_one('#body', VerticalScroll).scroll_page_down(animate=False)

    def action_page_up(self):
        self.query_one('#body', VerticalScroll).scroll_page_up(animate=False)

    def action_cancel(self):
        self.exit(None)
