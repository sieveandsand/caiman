"""Board/project creation and the terminal home screen."""

import asyncio
from pathlib import Path

from rich.text import Text

from textual.app import ComposeResult
from caiman.navigation import NavigationApp
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static

from .config_store import ConfigurationService
from .mascot import HEIGHT as MASCOT_HEIGHT, WIDTH as MASCOT_WIDTH, render_mascot
from .models import ValidationError
from .store import Store
from .theme import DOT_BORDER, TERMINAL_CSS, apply_theme


class SetupApp(NavigationApp):
    """Create one board or project. A project names its board explicitly, every time."""

    TITLE = 'Caiman · Create configuration'
    CSS = TERMINAL_CSS + '\n#review { height: auto; }\nButton { width: auto; }\n'

    def __init__(self, *, kind: str, store_root: Path, board=None):
        super().__init__()
        apply_theme(self)
        self.kind = kind
        self.store_root = store_root
        self.initial_board = board
        self.service = ConfigurationService(Store(store_root))
        self.boards = []
        self.prepared = None
        self.selection = None
        self.reviewing = False
        self.busy = False
        self.saving = False

    def field(self, name, label, value=''):
        yield Label(label)
        yield Input(value=value, id=name)

    def compose(self) -> ComposeResult:
        yield Static(f'caiman  /  create {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            with VerticalScroll(id='edit', classes='step'):
                yield from self.field('name', 'Board name' if self.kind == 'board' else 'Program codename')
                yield from self.field('version', 'Version (exact label)')
                if self.kind == 'board':
                    yield Static('Add the first hardware part. More parts and links can be added in board configuration.', classes='hint')
                    yield from self.field('role', 'Part role', 'application-mcu')
                    yield from self.field('issuer', 'Part manufacturer identifier')
                    yield from self.field('part', 'Part number identifier')
                    yield from self.field('silicon_revision', 'Silicon revision (optional)')
                    yield from self.field('refdes', 'Schematic reference (optional)')
                else:
                    yield Label('Board version')
                    yield Select([], prompt='Choose a registered board', id='board-choice')
                    yield from self.field('customer', 'Customer identity')
                    yield from self.field('compartments', 'Project compartments (comma separated; required)')
                    yield Static('Usually one per customer, such as oem-alpha. A project must include every compartment required by a document to use it.', classes='hint')
                    yield from self.field('spec_set', 'Specification set (exact release label)')
            yield Static('', id='review', markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Back to edit', id='back', disabled=True)
            yield Button('Review', id='next', variant='primary')
            yield Button('Cancel', id='cancel')
        yield self.navigation_hint()

    async def on_mount(self):
        self.show_view()
        if self.kind == 'project':
            await self.load_boards()

    def text(self, field):
        return self.query_one(f'#{field}', Input).value.strip()

    async def load_boards(self):
        self.busy = True
        self.show_view()
        try:
            self.boards = await asyncio.to_thread(self.service.list_configs, 'board')
            initial = self.initial_board
            # A board handed over from ingestion stays choosable even if its label moved.
            if initial and not any(record['digest'] == initial['digest'] for record in self.boards):
                manifest = initial['manifest']
                self.boards.append({'manifest': manifest, 'digest': initial['digest'], 'name': manifest['board'],
                                    'version': manifest['version'], 'compartment': 'public'})
            selector = self.query_one('#board-choice', Select)
            selector.set_options([(f"{record['name']} @ {record['version']} [{record['digest'][7:19]}]", str(index))
                                  for index, record in enumerate(self.boards)])
            if initial:
                selector.value = next(str(index) for index, record in enumerate(self.boards) if record['digest'] == initial['digest'])
            self.query_one('#status', Static).update(
                f'{len(self.boards)} registered boards.' if self.boards else 'No boards registered. Create a board first.')
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False
            self.show_view()

    def show_view(self):
        self.query_one('#edit').display = not self.reviewing
        self.query_one('#review').display = self.reviewing
        for widget in self.query('Input, Select, Button'):
            widget.disabled = self.busy
        self.query_one('#back', Button).disabled = not self.reviewing or self.busy
        self.query_one('#cancel', Button).disabled = self.saving
        self.query_one('#next', Button).label = 'Register' if self.reviewing else 'Review'

    def draft(self):
        data = {self.kind: self.text('name'), 'version': self.text('version')}
        if self.kind == 'board':
            part = {'role': self.text('role'), 'part': self.text('issuer') + '/' + self.text('part'), 'documents': []}
            for key in ('silicon_revision', 'refdes'):
                if self.text(key):
                    part[key] = self.text(key)
            data.update(parts=[part], links=[])
        else:
            choice = self.query_one('#board-choice', Select).value
            if not isinstance(choice, str):
                raise ValueError('Choose the board version this project uses')
            record = self.boards[int(choice)]
            board = record['manifest']
            data.update(customer=self.text('customer'),
                        compartments=[s.strip() for s in self.text('compartments').split(',') if s.strip()],
                        board={'name': board['board'], 'version': board['version'], 'digest': record['digest']},
                        spec_set=self.text('spec_set'), documents=[], precedence=[], features=[])
        return data

    def action_cancel(self):
        if not self.saving:
            self.exit(None)

    def review_text(self):
        manifest = self.selection['manifest']
        lines = [f"{self.kind.capitalize()}: {manifest[self.kind]}", f"Version: {manifest['version']}"]
        if self.kind == 'board':
            lines.append('Access: Public')
            lines.append('Parts:')
            for part in manifest['parts']:
                lines.append(f"  {part['role']}: {part['part']}")
                if part.get('silicon_revision'):
                    lines.append(f"    Silicon revision: {part['silicon_revision']}")
                if part.get('refdes'):
                    lines.append(f"    Schematic reference: {part['refdes']}")
                lines.append(f"    Pinned documents: {len(part['documents'])}")
            lines.append(f"Hardware links: {len(manifest.get('links', []))}")
        else:
            board = manifest['board']
            lines.extend([f"Customer: {manifest['customer']}",
                          'Compartments: ' + ', '.join(manifest['compartments']),
                          f"Board: {board['name']} @ {board['version']}",
                          f"Board digest: {board['digest']}",
                          f"Specification set: {manifest['spec_set']}",
                          f"Pinned project documents: {len(manifest['documents'])}",
                          f"Features: {len(manifest['features'])}"])
        lines.extend(['', f'Store: {self.store_root}', 'Manifest: ' + self.selection['digest']])
        return '\n'.join(lines)

    async def on_button_pressed(self, event):
        action = event.button.id
        if action == 'cancel':
            self.action_cancel()
            return
        if self.busy:
            return
        if action == 'back':
            self.prepared = None
            self.reviewing = False
            self.show_view()
            return
        if action != 'next':
            return
        self.busy = True
        self.saving = self.reviewing
        self.show_view()
        try:
            if self.reviewing:
                await asyncio.to_thread(self.service.register, self.prepared)
                self.exit(self.selection)
                return
            self.prepared = await asyncio.to_thread(self.service.prepare, self.kind, self.draft())
            self.selection = {'manifest': self.prepared.manifest, 'digest': self.prepared.digest}
            self.query_one('#review', Static).update('Review this configuration before registering.\n\n' + self.review_text())
            self.query_one('#status', Static).update('Use Back to edit or Cancel to leave without registering this configuration.')
            self.reviewing = True
        except ValidationError as error:
            self.query_one('#status', Static).update('\n'.join(f'{key}: {value}' for key, value in error.errors.items()))
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False
            self.saving = False
            self.show_view()


class DashboardTile(Button):
    """A keyboard-focusable action with a short description."""

    def __init__(self, title, description, *, action, disabled=False):
        label = Text()
        label.append(title, style='bold')
        label.append('\n' + description, style='#8d9982')
        super().__init__(label, id=action, classes='dashboard-tile', disabled=disabled)


class LauncherApp(NavigationApp):
    TITLE = 'Caiman'
    CSS = TERMINAL_CSS + f'''
    .dashboard-heading {{ height: 1; margin: 1 0 0 0; color: #7fdc4f; text-style: bold; }}
    .dashboard-grid {{ grid-size: 3; grid-columns: 1fr; grid-rows: 4; grid-gutter: 0 1; height: 4; }}
    .dashboard-tile {{ width: 100%; height: 4; min-width: 0; margin: 0; padding: 0 1; content-align: left middle; border: {DOT_BORDER} #33422e; background: #000000; color: #dfe6d3; text-style: none; }}
    .dashboard-tile:hover, .dashboard-tile:focus {{ border: {DOT_BORDER} #7fdc4f; background: #102210; color: #7fdc4f; text-style: none; }}
    .dashboard-tile:disabled {{ border: {DOT_BORDER} #1f291c; background: #000000; color: #56604e; }}
    #quit {{ width: auto; }}
    #masthead {{ height: auto; }}
    #masthead #brand {{ width: 1fr; }}
    #mascot {{ width: auto; height: auto; padding: 0 2 0 0; }}
    '''

    # Below these sizes the mascot would crowd the title or the tiles, so it steps aside.
    MASCOT_MIN_WIDTH = MASCOT_WIDTH + 24
    MASCOT_MIN_HEIGHT = MASCOT_HEIGHT + 20

    def __init__(self):
        super().__init__()
        apply_theme(self)

    def navigation_help(self):
        return 'h left · j down · k up · l right · Enter open · Tab next · q quit'

    def tiles(self, kind):
        # Only create and view live here; editing starts from what is being viewed.
        yield DashboardTile(f'Create {kind}', 'New configuration', action=f'create-{kind}')
        yield DashboardTile(f'View {kind}s', 'Browse · e to edit' if kind == 'board' else 'Pick one · e to edit',
                            action=f'show-{kind}')

    def compose(self):
        with Horizontal(id='masthead'):
            yield Static('caiman  /  home', id='brand')
            yield Static(render_mascot(), id='mascot')
        with VerticalScroll(id='body'):
            yield Static('Documents', classes='dashboard-heading')
            with Grid(id='documents-grid', classes='dashboard-grid'):
                yield DashboardTile('Ingest document', 'Register Markdown', action='ingest')
                yield DashboardTile('Browse documents', 'Find document pins', action='documents')
            yield Static('Boards', classes='dashboard-heading')
            with Grid(id='board-grid', classes='dashboard-grid'):
                yield from self.tiles('board')
            yield Static('Projects', classes='dashboard-heading')
            with Grid(id='project-grid', classes='dashboard-grid'):
                yield from self.tiles('project')
        with Horizontal(id='navigation'):
            yield Button('Quit', id='quit')
        yield self.navigation_hint()

    def on_mount(self):
        self.resize_grid(self.size.width, self.size.height)
        self.query_one('#ingest', Button).focus()

    def on_resize(self, event):
        self.resize_grid(event.size.width, event.size.height)

    def resize_grid(self, width, height=MASCOT_HEIGHT + 20):
        self.query_one('#mascot').display = width >= self.MASCOT_MIN_WIDTH and height >= self.MASCOT_MIN_HEIGHT
        columns = 2 if width < 72 else 3
        for grid in self.query('.dashboard-grid'):
            grid.styles.grid_size_columns = columns
            grid.styles.height = ((len(grid.children) + columns - 1) // columns) * 4

    def on_button_pressed(self, event):
        self.exit(event.button.id)

    def action_quit_launcher(self):
        self.exit('quit')

    def action_cancel(self):
        self.action_quit_launcher()
