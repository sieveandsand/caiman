"""Board gallery editing: guided form, optional Vim, explicit review, then registration."""

import asyncio
from copy import deepcopy
import difflib
import json
from pathlib import Path

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Static, TextArea

from caiman.configurations.service import ConfigurationService
from caiman.configurations.models import part_aliases, part_identity
from caiman.ui.navigation import NavigationApp
from caiman.storage.store import Store
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class BoardEditReviewApp(NavigationApp):
    TITLE = 'Caiman · Review board changes'
    CSS = TERMINAL_CSS + '\n#changes { height: 18; }\n'

    def __init__(self, *, root, original, prepared=None, error=None, original_pod=None, original_digest=None):
        super().__init__()
        apply_theme(self)
        self.root = root
        self.original = original
        self.original_pod = original_pod
        self.original_digest = original_digest
        self.prepared = prepared
        self.error = error
        self.saving = False

    def compose(self):
        yield Static('caiman  /  review board changes', id='brand')
        with VerticalScroll(id='body'):
            if self.prepared is None:
                yield Static('The draft needs correction before it can be registered.', classes='hint')
                yield Static(str(self.error), markup=False)
                yield Static('Your edited file is retained while you keep editing. Back discards this draft.', classes='hint')
            else:
                manifest = self.prepared.manifest
                yield Static(f"Board: {manifest['board']} @ {manifest['version']}\nPod: {self.prepared.pod}", markup=False)
                same_label = all(manifest[key] == self.original[key] for key in ('board', 'version'))
                yield Static('Register updates this version label. Existing digest pins remain unchanged.' if same_label else
                             'Register saves the name/version below. Choose another label if it already exists.', classes='hint')
                for part in manifest['parts']:
                    details = [f"{part['role']} · {part_identity(part)}"]
                    if part.get('silicon_revision'):
                        details.append('Silicon: ' + part['silicon_revision'])
                    details.extend(f'{key}: {value}' for key, value in sorted(part_aliases(part).items()))
                    details.append(f"{len(part['documents'])} document pins")
                    yield Static('  |  '.join(details), markup=False)
                yield Static(f"Manifest: {self.prepared.digest}", markup=False)
                with Collapsible(title='Review every changed field', collapsed=False):
                    before = json.dumps(self.original, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                    after = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                    diff = '\n'.join(difflib.unified_diff(before, after, fromfile='Stored board', tofile='Edited draft', lineterm=''))
                    yield TextArea(diff, read_only=True, id='changes', soft_wrap=True)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            if self.prepared is not None:
                yield Button('Register changes', id='register', variant='primary')
            yield Button('Continue editing', id='edit')
            yield Button('Back to boards', id='cancel')
        yield self.navigation_hint()

    def action_cancel(self):
        if not self.saving:
            self.exit(None)

    async def on_button_pressed(self, event):
        if self.saving:
            return
        if event.button.id == 'cancel':
            self.action_cancel()
        elif event.button.id == 'edit':
            self.exit('edit')
        elif event.button.id == 'register':
            self.saving = True
            for button in self.query(Button):
                button.disabled = True
            try:
                require_new_label = any(self.prepared.manifest[key] != self.original[key]
                                        for key in ('board', 'version'))
                replaces = None
                if (not require_new_label and self.original_digest and self.original_pod
                    and self.original_pod != self.prepared.pod):
                    replaces = {'manifest': self.original, 'digest': self.original_digest, 'pod': self.original_pod}
                registration = await asyncio.to_thread(ConfigurationService(Store(self.root)).register,
                                                       self.prepared, require_new_label=require_new_label, replaces=replaces)
                self.exit({'manifest': deepcopy(self.prepared.manifest), 'digest': registration.digest, 'pod': self.prepared.pod})
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.saving = False
                for button in self.query(Button):
                    button.disabled = False


class BoardDeleteApp(NavigationApp):
    """Confirm removing one board version from the list; exits True once deleted."""

    TITLE = 'Caiman · Delete board'
    AUTO_FOCUS = '#cancel'
    CSS = TERMINAL_CSS + '''
    Button { width: auto; }
    Button:focus { border: double #7fdc4f; }
    '''

    def __init__(self, *, root, selection):
        super().__init__()
        apply_theme(self)
        self.root = root
        self.selection = selection
        self.deleting = False

    def compose(self):
        manifest = self.selection['manifest']
        yield Static('caiman  /  delete board', id='brand')
        with VerticalScroll(id='body'):
            yield Static(f"Delete {manifest['board']} @ {manifest['version']} from "
                         + self.selection.get('pod', 'public') + '?', markup=False)
            yield Static('The board leaves the board list. Its snapshot stays in the store by digest, so '
                         'anything already pinned to it keeps working. Nothing is pushed.', classes='hint')
            yield Static(f"Manifest: {self.selection['digest']}", markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Keep board', id='cancel', variant='primary')
            yield Button('Delete board', id='delete', variant='error')
        yield self.navigation_hint()

    def action_cancel(self):
        if not self.deleting:
            self.exit(False)

    async def on_button_pressed(self, event):
        if self.deleting:
            return
        if event.button.id == 'cancel':
            self.action_cancel()
        elif event.button.id == 'delete':
            self.deleting = True
            for button in self.query(Button):
                button.disabled = True
            try:
                await asyncio.to_thread(ConfigurationService(Store(self.root)).unregister, 'board',
                                        self.selection['manifest'], self.selection['digest'], pod=self.selection.get('pod', 'public'))
                self.exit(True)
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.deleting = False
                for button in self.query(Button):
                    button.disabled = False


def _vim_excursion(root, original, draft):
    from caiman.configurations.editor import vim_excursion

    return vim_excursion(root, original, draft, review=BoardEditReviewApp)


def edit_board(root: Path, service: ConfigurationService, selection: dict) -> dict | None:
    """Drive one board through the guided form, Vim, and review.

    The guided form is the way in; Vim is the escape hatch at the bottom of it
    and returns to the same form, so an edit made either way is reviewed the
    same way. Returns the registered board, if one was registered. Confirmed
    deletion removes its name/version ref and returns None.
    """
    from caiman.boards.form import BoardFormApp

    original = selection['manifest']
    draft, message = deepcopy(original), ''
    draft['pod'] = selection.get('pod', service.store.pods.default)
    # Pod ownership lives outside the stored manifest. Compare the form against
    # the same editable context, without treating that supplied field as an edit.
    form_original = dict(original, pod=selection.get('pod', service.store.pods.default))
    while True:
        outcome = BoardFormApp(original=form_original, draft=draft, message=message, service=service).run()
        if outcome is None:
            return None
        action, draft = outcome
        message = ''
        if action == 'delete':
            if BoardDeleteApp(root=root, selection=selection).run():
                return None
            continue
        if action == 'raw':
            edited = _vim_excursion(root, original, draft)
            if edited is not None:
                draft = edited
            continue
        try:
            prepared = service.prepare('board', draft)
        except (OSError, ValueError) as invalid:
            message = str(invalid)
            continue
        if prepared.digest == selection['digest'] and prepared.pod == selection.get('pod', prepared.pod):
            message = 'This draft matches the registered snapshot. There is nothing to register.'
            continue
        reviewed = BoardEditReviewApp(root=root, original=original, prepared=prepared,
                                      original_pod=selection.get('pod'), original_digest=selection['digest']).run()
        if reviewed == 'edit':
            continue
        return reviewed if isinstance(reviewed, dict) else None


def run_board_gallery(root: Path) -> dict | None:
    """Vim runs only after every app releases the terminal; no nested TUIs.

    Returns the last board registered from the gallery, if any, or hands the
    add card back to the workflow as ``{'action': 'create-board'}``.
    """
    from caiman.boards.gallery import BoardGalleryApp
    from caiman.dashboard.actions import ViewerApp

    registered = None
    service = ConfigurationService(Store(root))
    active_pod = None
    while True:
        selection = BoardGalleryApp(store_root=root, pod=active_pod).run()
        if selection is None:
            return registered
        if isinstance(selection, dict):
            active_pod = selection.get('pod', active_pod)
        if isinstance(selection, dict) and selection.get('action') == 'add':
            return {'action': 'create-board', 'registered': registered, 'pod': active_pod}
        if selection == 'add':
            return {'action': 'create-board', 'registered': registered}
        try:
            registered = edit_board(root, service, selection) or registered
        except (OSError, ValueError) as error:
            ViewerApp(title='Board editor needs attention', content=str(error)).run()
