"""Board gallery editing: Vim draft, explicit review, then local registration."""

import asyncio
from copy import deepcopy
import difflib
import json
from pathlib import Path

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Static, TextArea

from .config_store import ConfigurationService
from .navigation import NavigationApp
from .store import Store
from .theme import TERMINAL_CSS, apply_theme


class BoardEditReviewApp(NavigationApp):
    TITLE = 'Caiman · Review board changes'
    CSS = TERMINAL_CSS + '\n#changes { height: 18; }\n'

    def __init__(self, *, root, original, prepared=None, error=None):
        super().__init__()
        apply_theme(self)
        self.root = root
        self.original = original
        self.prepared = prepared
        self.error = error
        self.saving = False

    def compose(self):
        yield Static('caiman  /  review board changes', id='brand')
        with VerticalScroll(id='body'):
            if self.prepared is None:
                yield Static('The draft needs correction before it can be registered.', classes='hint')
                yield Static(str(self.error), markup=False)
                yield Static('Your edited file is retained while you return to Vim. Back discards this draft.', classes='hint')
            else:
                manifest = self.prepared.manifest
                yield Static(f"Board: {manifest['board']} @ {manifest['version']}\nAccess: Public", markup=False)
                same_label = all(manifest[key] == self.original[key] for key in ('board', 'version'))
                yield Static('Register updates this version label. Existing digest pins remain unchanged.' if same_label else
                             'Register saves the name/version below. If that label exists, it will point to this snapshot.', classes='hint')
                for part in manifest['parts']:
                    details = [f"{part['role']} · {part['part']}"]
                    if part.get('silicon_revision'):
                        details.append('Silicon: ' + part['silicon_revision'])
                    if part.get('refdes'):
                        details.append('Schematic: ' + part['refdes'])
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
            yield Button('Edit in Vim', id='edit')
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
                registration = await asyncio.to_thread(ConfigurationService(Store(self.root)).register, self.prepared)
                self.exit({'manifest': deepcopy(self.prepared.manifest), 'digest': registration.digest})
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.saving = False
                for button in self.query(Button):
                    button.disabled = False


def run_board_gallery(root: Path) -> dict | None:
    """Vim runs only after the gallery releases the terminal; no nested TUIs.

    Returns the last board registered from the gallery, if any.
    """
    from .board_gallery import BoardGalleryApp
    from .dashboard_actions import ViewerApp
    from .external_editor import VimDraft

    registered = None
    service = ConfigurationService(Store(root))
    while True:
        selection = BoardGalleryApp(store_root=root).run()
        if selection is None:
            return registered
        original = selection['manifest']
        try:
            with VimDraft(original) as draft:
                while draft.edit():
                    try:
                        prepared = service.prepare('board', draft.read())
                        if prepared.digest == selection['digest']:
                            break
                        error = None
                    except (OSError, ValueError) as invalid:
                        prepared = None
                        error = str(invalid)
                    outcome = BoardEditReviewApp(root=root, original=original, prepared=prepared, error=error).run()
                    if outcome == 'edit':
                        continue
                    if isinstance(outcome, dict):
                        registered = outcome
                    break
        except (OSError, ValueError) as error:
            ViewerApp(title='Vim editor needs attention', content=str(error)).run()
