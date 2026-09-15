"""Dashboard access to existing configuration operations."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Footer, Input, Label, Select, Static, TextArea

from .config_files import read_draft, template, write_draft
from .config_store import ConfigurationService
from .navigation import NavigationApp
from .store import Store
from .theme import TERMINAL_CSS, apply_theme


def revision_draft(manifest: dict, *, mode: str, version='', relation='') -> dict:
    draft = deepcopy(manifest)
    if mode == 'replace':
        return draft
    if mode != 'new':
        raise ValueError('Choose a new version or explicitly update the selected version')
    if not version.strip() or version == manifest['version']:
        raise ValueError('Supply a different, nonempty version label')
    if not relation.strip():
        raise ValueError('Describe the relationship to the selected version')
    draft.update(version=version, derives_from=manifest['version'], relation=relation)
    return draft


class ActionApp(NavigationApp):
    CSS = TERMINAL_CSS + '\nButton { width: auto; }\n#content { height: 1fr; }\n'
    BINDINGS = [('ctrl+q', 'cancel', 'Cancel')]

    def __init__(self):
        super().__init__()
        apply_theme(self)

    def action_cancel(self):
        self.exit(None)


class RevisionApp(ActionApp):
    TITLE = 'Caiman · Modify configuration'

    def __init__(self, *, kind, selection, root=None):
        super().__init__()
        self.kind = kind
        self.selection = selection
        self.root = root
        self.busy = False

    def compose(self):
        manifest = self.selection['manifest']
        yield Static(f'caiman  /  modify {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            yield Static(f"Selected: {manifest[self.kind]} @ {manifest['version']}\nDigest: {self.selection['digest']}", markup=False)
            yield Label('How should this change be saved?')
            yield Select([('Create a new version', 'new'), ('Update the selected version label', 'replace')],
                         value='new', allow_blank=False, id='mode')
            yield Static('Updating the selected label repoints that label. Existing immutable pins keep their original snapshot.', classes='hint')
            with VerticalScroll(id='new-version', classes='step'):
                yield Label('New version label')
                yield Input(id='version')
                yield Label('Relationship to the selected version')
                yield Input(id='relation')
            yield Static('The full configuration editor and registration review follow. Board changes do not change project pins.', classes='hint')
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Continue to editor', id='continue', variant='primary')
            yield Button('Cancel', id='cancel')
        yield Footer()

    def on_select_changed(self, event):
        if event.select.id == 'mode':
            self.query_one('#new-version').display = event.value == 'new'

    async def on_button_pressed(self, event):
        if event.button.id == 'cancel':
            self.exit(None)
        elif event.button.id == 'continue' and not self.busy:
            self.busy = True
            try:
                mode = self.query_one('#mode', Select).value
                draft = revision_draft(self.selection['manifest'], mode=mode,
                                       version=self.query_one('#version', Input).value.strip(),
                                       relation=self.query_one('#relation', Input).value.strip())
                if mode == 'new' and self.root is not None:
                    manifest = self.selection['manifest']
                    versions = await asyncio.to_thread(ConfigurationService(Store(self.root)).list_versions,
                                                       self.kind, manifest[self.kind],
                                                       compartments=manifest.get('compartments', []))
                    if draft['version'] in versions:
                        raise ValueError('That version label already exists. Choose another label or select that version and explicitly update it.')
                self.exit(draft)
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.busy = False


class FileActionApp(ActionApp):
    TITLE = 'Caiman · Configuration file'

    def __init__(self, *, operation, kind, root, selection=None):
        super().__init__()
        self.operation = operation
        self.kind = kind
        self.root = root
        self.selection = selection
        self.busy = False

    def compose(self):
        yield Static(f'caiman  /  {self.operation} {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            if self.selection:
                manifest = self.selection['manifest']
                yield Static(f"Selected: {manifest[self.kind]} @ {manifest['version']}", markup=False)
                if self.kind == 'project':
                    yield Static('Project exports contain customer metadata and are written as private files.', classes='hint')
            yield Label('JSON configuration file path')
            yield Input(id='path')
            if self.operation == 'import':
                yield Static('Import opens an editable draft. Register only after reviewing it in the editor.', classes='hint')
            elif self.operation == 'validate':
                yield Static('Validation resolves exact pins and writes no configurations.', classes='hint')
            else:
                yield Static('Choose a new output filename. Existing files are never overwritten.', classes='hint')
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button(self.operation.capitalize(), id='run', variant='primary')
            yield Button('Cancel', id='cancel')
        yield Footer()

    def action_cancel(self):
        if not self.busy:
            self.exit(None)

    def perform(self, path):
        if self.operation == 'import':
            return {'draft': read_draft(path)}
        if self.operation == 'validate':
            prepared = ConfigurationService(Store(self.root)).prepare(self.kind, read_draft(path))
            return {'title': 'Validation passed', 'content': 'No configuration was registered.\n\n' +
                    json.dumps(prepared.manifest, indent=2, ensure_ascii=False) + '\n\nDigest: ' + prepared.digest}
        draft = template(self.kind) if self.operation == 'template' else self.selection['manifest']
        write_draft(path, draft)
        return {'title': 'Configuration file written', 'content': str(path.expanduser().absolute())}

    async def on_button_pressed(self, event):
        if event.button.id == 'cancel':
            self.action_cancel()
            return
        if event.button.id != 'run' or self.busy:
            return
        value = self.query_one('#path', Input).value.strip()
        if not value:
            self.query_one('#status', Static).update('Enter a file path.')
            return
        self.busy = True
        for button in self.query('Button'):
            button.disabled = True
        try:
            result = await asyncio.to_thread(self.perform, Path(value))
            self.exit(result)
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False
            for button in self.query('Button'):
                button.disabled = False


class ViewerApp(ActionApp):
    TITLE = 'Caiman · Inspect'

    def __init__(self, *, title, content):
        super().__init__()
        self.heading = title
        self.content = content

    def compose(self):
        yield Static('caiman  /  ' + self.heading.lower(), id='brand', markup=False)
        with VerticalScroll(id='body'):
            yield TextArea(self.content, read_only=True, id='content', soft_wrap=True)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Back to dashboard', id='close', variant='primary')
        yield Footer()

    def on_button_pressed(self, event):
        self.exit(None)


class DocumentCatalogApp(ActionApp):
    TITLE = 'Caiman · Documents'

    def __init__(self, *, root, compartments):
        super().__init__()
        self.service = ConfigurationService(Store(root))
        self.compartments = compartments
        self.busy = False

    def compose(self):
        yield Static('caiman  /  registered documents', id='brand')
        with VerticalScroll(id='body'):
            yield Label('Access groups (comma separated; public documents are always included)')
            yield Static('Usually one group per customer, such as oem-alpha. Enter only groups you intend to access.', classes='hint')
            yield Input(', '.join(self.compartments), id='compartments')
            yield Button('Refresh catalog', id='refresh')
            yield TextArea('', read_only=True, id='content', soft_wrap=True)
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Back to dashboard', id='close', variant='primary')
        yield Footer()

    async def on_mount(self):
        await self.refresh_catalog()

    async def refresh_catalog(self):
        if self.busy:
            return
        self.busy = True
        try:
            names = [s.strip() for s in self.query_one('#compartments', Input).value.split(',') if s.strip()]
            records = await asyncio.to_thread(self.service.list_documents, compartments=names)
            self.query_one('#content', TextArea).load_text(json.dumps(records, indent=2, ensure_ascii=False))
            self.query_one('#status', Static).update(f'{len(records)} accessible registered documents.')
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False

    async def on_button_pressed(self, event):
        if event.button.id == 'refresh':
            await self.refresh_catalog()
        elif event.button.id == 'close':
            self.exit(None)


def run_dashboard_action(action: str, root: Path, context: dict, compartments) -> dict | None:
    """Run one dashboard action; return only explicitly registered selection changes."""
    try:
        if action == 'documents':
            DocumentCatalogApp(root=root, compartments=compartments).run()
            return None
        operation, kind = action.split('-', 1)
        if kind not in {'board', 'project'}:
            raise ValueError('Unknown dashboard action')
        selection = context.get(kind)
        if operation == 'show':
            if kind == 'board':
                from .board_edit import run_board_gallery
                return run_board_gallery(root, selection)
            ViewerApp(title=f'{kind.capitalize()} snapshot', content=json.dumps(selection['manifest'], indent=2, ensure_ascii=False) +
                      '\n\nManifest: ' + selection['digest']).run()
            return None
        if operation == 'edit':
            draft = RevisionApp(kind=kind, selection=selection, root=root).run()
            if draft is None:
                return None
        elif operation in {'import', 'export', 'validate', 'template'}:
            result = FileActionApp(operation=operation, kind=kind, root=root, selection=selection).run()
            if result is None:
                return None
            if operation != 'import':
                ViewerApp(title=result['title'], content=result['content']).run()
                return None
            draft = result['draft']
        else:
            raise ValueError('Unknown dashboard action')
        from .config_tui import ConfigApp
        editor = ConfigApp(kind=kind, store_root=root, draft=draft)
        editor.run()
        if editor.registration is not None:
            return {kind: {'manifest': deepcopy(editor.prepared.manifest), 'digest': editor.registration.digest}}
    except (OSError, ValueError) as error:
        ViewerApp(title='Action needs attention', content=str(error)).run()
    return None
