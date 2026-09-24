"""Dashboard access to existing configuration operations."""

import asyncio
from copy import deepcopy
import json
from pathlib import Path

from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from caiman.configurations.service import ConfigurationService
from caiman.ui.navigation import NavigationApp
from caiman.storage.store import Store
from caiman.ui.theme import TERMINAL_CSS, apply_theme


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

    def __init__(self):
        super().__init__()
        apply_theme(self)

    def action_cancel(self):
        self.exit(None)


class ChooseApp(ActionApp):
    """Pick the board or project an action applies to; nothing is preselected."""

    TITLE = 'Caiman · Choose configuration'

    def __init__(self, *, kind, root, compartments=(), purpose='choose'):
        super().__init__()
        self.kind = kind
        self.purpose = purpose
        self.compartments = list(compartments)
        self.service = ConfigurationService(Store(root))
        self.records = []
        self.busy = False

    def compose(self):
        yield Static(f'caiman  /  {self.purpose} {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            if self.kind == 'project':
                yield Label('Compartments to search (comma separated)')
                yield Static('Usually one per customer, such as oem-alpha. Only projects in these compartments are listed.', classes='hint')
                yield Input(', '.join(self.compartments), id='compartments')
                yield Button('Find projects', id='find')
            yield Label(f'{self.kind.capitalize()} version')
            yield Select([], prompt=f'Choose a {self.kind}', id='choice')
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Continue', id='continue', variant='primary')
            yield Button('Cancel', id='cancel')

    async def on_mount(self):
        await self.refresh_catalog()

    async def refresh_catalog(self):
        if self.busy:
            return
        self.busy = True
        try:
            scopes = []
            if self.kind == 'project':
                scopes = [s.strip() for s in self.query_one('#compartments', Input).value.split(',') if s.strip()]
            self.records = await asyncio.to_thread(self.service.list_configs, self.kind, compartments=scopes)
            self.query_one('#choice', Select).set_options([
                (f"{record['name']} @ {record['version']} [{record['compartment']}; {record['digest'][7:19]}]", str(index))
                for index, record in enumerate(self.records)])
            self.query_one('#status', Static).update(f'{len(self.records)} {self.kind} versions available.')
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False

    async def on_button_pressed(self, event):
        if event.button.id == 'cancel':
            self.exit(None)
        elif event.button.id == 'find':
            await self.refresh_catalog()
        elif event.button.id == 'continue' and not self.busy:
            choice = self.query_one('#choice', Select).value
            if not isinstance(choice, str):
                self.query_one('#status', Static).update(f'Choose a {self.kind} first.')
                return
            record = self.records[int(choice)]
            self.exit({'manifest': record['manifest'], 'digest': record['digest']})


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


class ViewerApp(ActionApp):
    TITLE = 'Caiman · Inspect'
    BINDINGS = [Binding('e', 'edit', 'Edit', priority=True, show=False)]

    def __init__(self, *, title, content, editable=False):
        super().__init__()
        self.heading = title
        self.content = content
        self.editable = editable

    def navigation_help(self):
        if self.editable:
            return 'NAVIGATE · j/k move · e edit · Enter press button · q back'
        return super().navigation_help()

    def compose(self):
        yield Static('caiman  /  ' + self.heading.lower(), id='brand', markup=False)
        with VerticalScroll(id='body'):
            yield TextArea(self.content, read_only=True, id='content', soft_wrap=True)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            if self.editable:
                yield Button('Edit', id='edit', variant='primary')
            yield Button('Back', id='close', variant='primary' if not self.editable else 'default')

    def check_action(self, action, parameters):
        if action == 'edit':
            return self.editable and not self.editing
        return super().check_action(action, parameters)

    def action_edit(self):
        self.exit('edit')

    def on_button_pressed(self, event):
        self.exit('edit' if event.button.id == 'edit' else None)


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
            yield Label('Compartments (comma separated; public documents are always included)')
            yield Static('Usually one compartment per customer, such as oem-alpha. Enter only compartments you intend to access.', classes='hint')
            yield Input(', '.join(self.compartments), id='compartments')
            yield Button('Refresh catalog', id='refresh')
            yield TextArea('', read_only=True, id='content', soft_wrap=True)
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Back to dashboard', id='close', variant='primary')

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


def run_dashboard_action(action: str, root: Path, compartments) -> dict | None:
    """Run one dashboard action; return the project or board it viewed or registered.

    Editing starts from viewing: the board grid edits in Vim, and a viewed
    project snapshot offers Edit, which opens the revision form and editor.
    """
    try:
        if action == 'documents':
            DocumentCatalogApp(root=root, compartments=compartments).run()
            return None
        if action == 'show-board':
            from caiman.boards.edit import run_board_gallery
            return run_board_gallery(root)
        if action != 'show-project':
            raise ValueError('Unknown dashboard action')
        selection = ChooseApp(kind='project', root=root, compartments=compartments, purpose='view').run()
        while selection is not None:
            content = (json.dumps(selection['manifest'], indent=2, ensure_ascii=False) +
                       '\n\nManifest: ' + selection['digest'])
            if ViewerApp(title='Project snapshot', content=content, editable=True).run() != 'edit':
                break
            draft = RevisionApp(kind='project', selection=selection, root=root).run()
            if draft is None:
                continue
            from caiman.configurations.tui import ConfigApp
            editor = ConfigApp(kind='project', store_root=root, draft=draft)
            editor.run()
            if editor.registration is not None:
                # Show what was just registered, not the snapshot it came from.
                selection = {'manifest': deepcopy(editor.prepared.manifest), 'digest': editor.registration.digest}
        return selection
    except (OSError, ValueError) as error:
        ViewerApp(title='Action needs attention', content=str(error)).run()
    return None
