"""Board/project creation and the terminal home screen."""

import asyncio
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from caiman.ui.navigation import NavigationApp
from caiman.ui.cards import CARD_CSS, AddTile, CardFrame, OverviewCard, card_label, resize_card_grid
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, SelectionList, Static
from textual.widgets.selection_list import Selection

from caiman.boards.form import vendor_suggester
from caiman.configurations.service import ConfigurationService
from caiman.configurations.models import part_aliases, part_identity, project_boards
from caiman.ui.mascot import HEIGHT as MASCOT_HEIGHT, WIDTH as MASCOT_WIDTH, render_mascot
from caiman.documents.models import ValidationError
from caiman.storage.store import Store
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class SetupApp(NavigationApp):
    """Create one board or project. A project names its boards explicitly, every time."""

    TITLE = 'Caiman · Create configuration'
    CSS = TERMINAL_CSS + '\n#review { height: auto; }\nButton { width: auto; }\n#board-choice { height: auto; max-height: 12; }\n'

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

    def field(self, name, label, value='', suggester=None):
        yield Label(label)
        yield Input(value=value, suggester=suggester, id=name)

    def compose(self) -> ComposeResult:
        yield Static(f'caiman  /  create {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            with VerticalScroll(id='edit', classes='step'):
                yield from self.field('name', 'Board name' if self.kind == 'board' else 'Program codename')
                yield from self.field('version', 'Version (exact label)')
                if self.kind == 'board':
                    yield from self.field('notes', 'Notes (optional, unstructured)')
                    yield Static('Add the first hardware part. More parts, links, and board documents can be added in board configuration.', classes='hint')
                    yield from self.field('part', 'Part name')
                    yield from self.field('role', 'Part role', 'application-mcu')
                    yield from self.field('vendor', 'Vendor', suggester=vendor_suggester())
                    yield from self.field('silicon_revision', 'Silicon revision (optional)')
                    yield from self.field('refdes', 'Schematic reference (optional; stored as aliases.refdes)')
                else:
                    yield Label('Boards')
                    yield Static('Mark every board version this program runs on with Space. '
                                 'A board may be chosen at more than one version.', classes='hint')
                    yield SelectionList(id='board-choice')
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
            selector = self.query_one('#board-choice', SelectionList)
            selector.clear_options()
            # Only a board handed over from ingestion starts marked; nothing else is preselected.
            selector.add_options([Selection(f"{record['name']} @ {record['version']} [{record['digest'][7:19]}]", index,
                                            bool(initial) and record['digest'] == initial['digest'])
                                  for index, record in enumerate(self.boards)])
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
        for widget in self.query('Input, SelectionList, Button'):
            widget.disabled = self.busy
        self.query_one('#back', Button).disabled = not self.reviewing or self.busy
        self.query_one('#cancel', Button).disabled = self.saving
        self.query_one('#next', Button).label = 'Register' if self.reviewing else 'Review'

    def draft(self):
        data = {self.kind: self.text('name'), 'version': self.text('version')}
        if self.kind == 'board':
            part = {'part': self.text('part'), 'role': self.text('role'), 'vendor': self.text('vendor'), 'documents': []}
            if self.text('silicon_revision'):
                part['silicon_revision'] = self.text('silicon_revision')
            # A reference designator is one cross-domain identifier among several,
            # never the part identity or its display name (S-12).
            if self.text('refdes'):
                part['aliases'] = {'refdes': self.text('refdes')}
            if self.text('notes'):
                data['notes'] = self.text('notes')
            data.update(parts=[part], links=[])
        else:
            chosen = sorted(self.query_one('#board-choice', SelectionList).selected)
            if not chosen:
                raise ValueError('Choose the board versions this project uses')
            boards = [{'name': self.boards[index]['manifest']['board'], 'version': self.boards[index]['manifest']['version'],
                       'digest': self.boards[index]['digest']} for index in chosen]
            data.update(customer=self.text('customer'),
                        compartments=[s.strip() for s in self.text('compartments').split(',') if s.strip()],
                        boards=boards,
                        spec_set=self.text('spec_set'), documents=[], features=[])
        return data

    def action_cancel(self):
        if not self.saving:
            self.exit(None)

    def review_text(self):
        manifest = self.selection['manifest']
        lines = [f"{self.kind.capitalize()}: {manifest[self.kind]}", f"Version: {manifest['version']}"]
        if self.kind == 'board':
            lines.append('Access: Public')
            if manifest.get('notes'):
                lines.append('Notes: ' + manifest['notes'])
            lines.append('Parts:')
            for part in manifest['parts']:
                lines.append(f"  {part['role']}: {part_identity(part)}")
                if part.get('silicon_revision'):
                    lines.append(f"    Silicon revision: {part['silicon_revision']}")
                for key, value in sorted(part_aliases(part).items()):
                    lines.append(f"    Alias {key}: {value}")
                lines.append(f"    Pinned documents: {len(part['documents'])}")
            lines.append(f"Hardware links: {len(manifest.get('links', []))}")
        else:
            lines.extend([f"Customer: {manifest['customer']}",
                          'Compartments: ' + ', '.join(manifest['compartments'])])
            for board in project_boards(manifest):
                lines.extend([f"Board: {board['name']} @ {board['version']}", f"  Board digest: {board['digest']}"])
            lines.extend([f"Specification set: {manifest['spec_set']}",
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


class DashboardTile(OverviewCard):
    """A keyboard-focusable action with a fullwidth heading."""

    def __init__(self, title, description, *, action, disabled=False):
        super().__init__('', id=action, classes='dashboard-tile card-face', disabled=disabled)
        self.title = title
        self.description = description

    def format_card(self, width):
        self.label = card_label(self.title, self.description, width)
        height = len(self.label.plain.splitlines()) + 2
        self.styles.height = height
        return height


class Mascot(Static):
    """The masthead caiman is a button: click, or focus it and press Enter, to open little caiman."""

    can_focus = True
    BINDINGS = [Binding('enter,space', 'press', 'Little caiman', show=False)]

    def __init__(self, *args, **kwargs):
        # dashboard-tile joins hjkl movement: k from the top tiles reaches the mascot.
        super().__init__(*args, classes='dashboard-tile', **kwargs)
        self.tooltip = 'Little caiman'

    def action_press(self):
        self.app.exit('little-caiman')

    def on_click(self, event):
        event.stop()
        self.action_press()


# Home shows one card per category. Documents, boards, and projects open their
# gallery, which ends in an add card; these two open a page of their actions.
CATEGORY_MENUS = {
    'hooks': ('Hooks', [('Claude Code', 'Add Caiman hook', 'hooks-claude'),
                        ('Codex', 'Add Caiman hook', 'hooks-codex')]),
    'repos': ('Repo Manager', [('Remove repo', 'Remove registration', 'repo-remove'),
                               ('Initialize repo', 'Create; optional push', 'repo-initialize'),
                               ('Add repo', None, 'repo-add')]),
}


def resize_tile_grid(grid, width):
    columns = 2 if width >= 100 else 1
    resize_card_grid(grid, max(8, (width - 6 - (columns - 1)) // columns), columns)


class LauncherApp(NavigationApp):
    TITLE = 'Caiman'
    BINDINGS = [Binding('c', 'little_caiman', 'Little caiman', show=False)]
    CSS = TERMINAL_CSS + CARD_CSS + f'''
    .dashboard-grid {{ grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; height: auto; margin-top: 1; }}
    #quit {{ width: auto; }}
    #masthead {{ height: auto; }}
    #masthead #brand {{ width: 1fr; }}
    #mascot {{ width: auto; height: auto; padding: 0 2 0 0; }}
    #mascot:hover {{ background: #0c140c; }}
    #mascot:focus {{ background: #25331f; }}
    '''

    # Below these sizes the mascot would crowd the title or the tiles, so it steps aside.
    MASCOT_MIN_WIDTH = MASCOT_WIDTH + 24
    MASCOT_MIN_HEIGHT = MASCOT_HEIGHT + 20

    def __init__(self):
        super().__init__()
        apply_theme(self)

    def navigation_help(self):
        return 'h left · j down · k up · l right · Enter open · c little caiman · q quit'

    def tile(self, *args, **kwargs):
        return CardFrame(DashboardTile(*args, **kwargs))

    def compose(self):
        with Horizontal(id='masthead'):
            yield Static('caiman  /  home', id='brand')
            yield Mascot(render_mascot(), id='mascot')
        with VerticalScroll(id='body'):
            with Grid(id='category-grid', classes='dashboard-grid'):
                yield self.tile('Documents', 'Ingest · browse registered', action='documents')
                yield self.tile('Boards', 'Add · view · edit', action='show-board')
                yield self.tile('Projects', 'Add · view · edit', action='show-project')
                yield self.tile('Hooks', 'Claude Code · Codex', action='hooks')
                yield self.tile('Repo Manager', 'Add · remove · initialize', action='repos')
        with Horizontal(id='navigation'):
            yield Button('Quit', id='quit')
        yield self.navigation_hint()

    def on_mount(self):
        self.resize_grid(self.size.width, self.size.height)
        self.query_one('#documents', Button).focus()

    def on_resize(self, event):
        self.resize_grid(event.size.width, event.size.height)

    def resize_grid(self, width, height=MASCOT_HEIGHT + 20):
        self.query_one('#mascot').display = width >= self.MASCOT_MIN_WIDTH and height >= self.MASCOT_MIN_HEIGHT
        resize_tile_grid(self.query_one('#category-grid', Grid), width)

    def on_button_pressed(self, event):
        self.exit(event.button.id)

    def action_little_caiman(self):
        self.exit('little-caiman')

    def action_quit_launcher(self):
        self.exit('quit')

    def action_cancel(self):
        self.action_quit_launcher()


class CategoryApp(NavigationApp):
    """One home category's actions as cards; returns the chosen action."""

    CSS = LauncherApp.CSS

    def __init__(self, category):
        super().__init__()
        apply_theme(self)
        self.heading, self.actions = CATEGORY_MENUS[category]
        self.title = 'Caiman · ' + self.heading

    def navigation_help(self):
        return 'hjkl move · Enter open · q back'

    def compose(self):
        yield Static('caiman  /  ' + self.heading.lower(), id='brand')
        with VerticalScroll(id='body'):
            with Grid(id='category-grid', classes='dashboard-grid'):
                for title, description, action in self.actions:
                    card = (AddTile(title, id=action) if description is None else
                            DashboardTile(title, description, action=action))
                    yield CardFrame(card)
        with Horizontal(id='navigation'):
            yield Button('Back', id='quit')
        yield self.navigation_hint()

    def on_mount(self):
        resize_tile_grid(self.query_one('#category-grid', Grid), self.size.width)
        self.query('.card-face').first().focus()

    def on_resize(self, event):
        resize_tile_grid(self.query_one('#category-grid', Grid), event.size.width)

    def on_button_pressed(self, event):
        self.exit(None if event.button.id == 'quit' else event.button.id)
