"""Guided first board/project setup and the terminal home screen."""

import asyncio
from copy import deepcopy
from pathlib import Path

from rich.text import Text

from textual.app import ComposeResult
from caiman.navigation import NavigationApp
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Input, Label, Select, Static

from .config_store import ConfigurationService
from .models import ValidationError
from .store import Store
from .theme import TERMINAL_CSS, apply_theme


class SetupApp(NavigationApp):
    TITLE = 'Caiman · Get started'
    BINDINGS = [('ctrl+q', 'cancel', 'Cancel')]
    CSS = TERMINAL_CSS + '\n#review { height: auto; }\nButton { width: auto; }\n'

    def __init__(self, *, kind: str, store_root: Path, board=None, compartments=(), create=False):
        super().__init__()
        apply_theme(self)
        self.kind = kind
        self.store_root = store_root
        self.board = board
        self.compartments = list(compartments)
        self.create = create
        self.service = ConfigurationService(Store(store_root))
        self.records = []
        self.prepared = None
        self.reviewing = False
        self.busy = False
        self.saving = False

    def field(self, name, label, value=''):
        yield Label(label)
        yield Input(value=value, id=name)

    def compose(self) -> ComposeResult:
        yield Static(f'caiman  /  set up {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Start with your hardware, then the customer program. Documents can be added afterwards.', classes='hint')
            with VerticalScroll(id='edit', classes='step'):
                if not self.create:
                    yield Label(f'Use an existing {self.kind}, or create one')
                    yield Select([('Create new', 'new')], value='new', allow_blank=False, id='existing')
                if self.kind == 'project':
                    yield Label('Access groups to search (comma separated)')
                    yield Static('Usually one per customer, such as oem-alpha. Only projects in these groups are listed.', classes='hint')
                    yield Input(value=', '.join(self.compartments), id='search-compartments')
                    yield Button('Find projects', id='find')
                with VerticalScroll(id='new-fields', classes='step'):
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
                        manifest = (self.board or {}).get('manifest', {})
                        yield Static(f"Board: {manifest.get('board', 'Choose a board first')} @ {manifest.get('version', '')}", markup=False)
                        yield from self.field('customer', 'Customer identity')
                        yield from self.field('compartments', 'Project access groups (comma separated; required)')
                        yield Static('Usually one per customer, such as oem-alpha. A project must include every group required by a document to use it.', classes='hint')
                        yield from self.field('spec_set', 'Specification set (exact release label)')
            yield Static('', id='review', markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Back to edit', id='back', disabled=True)
            yield Button('Review', id='next', variant='primary')
            yield Button('Cancel', id='cancel')
        yield self.navigation_hint()
        yield Footer()

    async def on_mount(self):
        if not self.create:
            await self.refresh_catalog()

    def text(self, field):
        return self.query_one(f'#{field}', Input).value.strip()

    async def refresh_catalog(self):
        self.busy = True
        self.show_view()
        try:
            scopes = self.compartments
            if self.kind == 'project':
                scopes = [s.strip() for s in self.text('search-compartments').split(',') if s.strip()]
            self.records = await asyncio.to_thread(self.service.list_configs, self.kind, compartments=scopes)
            if not self.create:
                selector = self.query_one('#existing', Select)
                selector.set_options([('Create new', 'new')] + [
                    (f"{record['name']} @ {record['version']} [{record['compartment']}; {record['digest'][7:19]}]", str(index)) for index, record in enumerate(self.records)])
                selector.value = 'new'
            self.query_one('#status', Static).update(f'{len(self.records)} existing {self.kind} configurations available.')
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
        self.query_one('#next', Button).label = ('Use selection' if self.prepared is None else 'Register and continue') if self.reviewing else 'Review'
        if not self.create:
            self.query_one('#new-fields').display = self.query_one('#existing', Select).value == 'new'

    def on_select_changed(self, event):
        if event.select.id == 'existing':
            self.show_view()

    def draft(self):
        data = {self.kind: self.text('name'), 'version': self.text('version')}
        if self.kind == 'board':
            part = {'role': self.text('role'), 'part': self.text('issuer') + '/' + self.text('part'), 'documents': []}
            for key in ('silicon_revision', 'refdes'):
                if self.text(key):
                    part[key] = self.text(key)
            data.update(parts=[part], links=[])
        else:
            if self.board is None:
                raise ValueError('Choose or create a board before creating a project')
            board = self.board['manifest']
            data.update(customer=self.text('customer'),
                        compartments=[s.strip() for s in self.text('compartments').split(',') if s.strip()],
                        board={'name': board['board'], 'version': board['version'], 'digest': self.board['digest']},
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
                          'Access groups: ' + ', '.join(manifest['compartments']),
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
        if action == 'find':
            await self.refresh_catalog()
            return
        if action == 'back':
            self.prepared = None
            self.reviewing = False
            self.show_view()
            return
        if action != 'next':
            return
        self.busy = True
        self.saving = self.reviewing and self.prepared is not None
        self.show_view()
        try:
            if self.reviewing:
                if self.prepared is not None:
                    await asyncio.to_thread(self.service.register, self.prepared)
                self.exit(self.selection)
                return
            selected = 'new' if self.create else self.query_one('#existing', Select).value
            if selected != 'new':
                record = self.records[int(selected)]
                self.selection = {'manifest': record['manifest'], 'digest': record['digest']}
            else:
                self.prepared = await asyncio.to_thread(self.service.prepare, self.kind, self.draft())
                self.selection = {'manifest': self.prepared.manifest, 'digest': self.prepared.digest}
            self.query_one('#review', Static).update('Review this configuration before continuing.\n\n' + self.review_text())
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
        label.append('\n' + description, style='#99958e')
        super().__init__(label, id=action, classes='dashboard-tile', disabled=disabled)


class LauncherApp(NavigationApp):
    TITLE = 'Caiman'
    BINDINGS = [('ctrl+q', 'quit_launcher', 'Quit')]
    CSS = TERMINAL_CSS + '''
    #current-context { height: auto; margin-bottom: 1; color: #b4afa7; }
    .dashboard-heading { height: 1; margin: 1 0 0 0; color: #d97757; text-style: bold; }
    .dashboard-grid { grid-size: 3; grid-columns: 1fr; grid-rows: 4; grid-gutter: 0 1; height: auto; }
    #documents-grid { height: 4; }
    #board-grid, #project-grid { height: 12; }
    .dashboard-tile { width: 100%; height: 4; min-width: 0; margin: 0; padding: 0 1; content-align: left middle; border: round #49453f; background: #000000; color: #e6e1d8; text-style: none; }
    .dashboard-tile:hover, .dashboard-tile:focus { border: round #d97757; background: #18120f; color: #d97757; text-style: none; }
    .dashboard-tile:disabled { border: round #292929; background: #000000; color: #615d57; }
    #quit { width: auto; }
    '''

    def __init__(self, *, context):
        super().__init__()
        apply_theme(self)
        self.context = deepcopy(context)

    def navigation_help(self):
        return 'h left · j down · k up · l right · Enter open · Tab next · q quit'

    def tiles(self, kind):
        selected = kind in self.context
        actions = (
            ('create', f'Create {kind}', 'New configuration'),
            ('select', f'Select {kind}', 'Choose saved version'),
            ('edit', f'Edit {kind}', 'Create a new version'),
            ('show', f'View {kind}', 'Board grid · Vim edit' if kind == 'board' else 'Inspect snapshot'),
            ('import', f'Import {kind}', 'Open a JSON draft'),
            ('export', f'Export {kind}', 'Save JSON draft'),
            ('validate', f'Validate {kind}', 'Check without saving'),
            ('template', f'Blank {kind} draft', 'Save JSON template'),
        )
        for action, title, description in actions:
            yield DashboardTile(title, description, action=f'{action}-{kind}', disabled=not selected and action in {'edit', 'show', 'export'})

    def compose(self):
        yield Static('caiman  /  home', id='brand')
        with VerticalScroll(id='body'):
            context_lines = []
            for kind in ('board', 'project'):
                manifest = self.context.get(kind, {}).get('manifest')
                selection = f"{manifest[kind]} @ {manifest['version']}" if manifest else 'No selection'
                context_lines.append(f'{kind.capitalize()}: {selection}')
            yield Static('\n'.join(context_lines), id='current-context', markup=False)
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
        yield Footer()

    def on_mount(self):
        self.resize_grid(self.size.width)
        self.query_one('#ingest', Button).focus()

    def on_resize(self, event):
        self.resize_grid(event.size.width)

    def resize_grid(self, width):
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
