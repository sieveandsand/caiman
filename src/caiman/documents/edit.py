"""Document gallery → guided metadata form → review → immutable registration."""

import asyncio
from copy import deepcopy
import difflib
import json

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Static, TextArea

from caiman.documents.cards import document_name
from caiman.documents.edit_service import DocumentEditService
from caiman.documents.form import DocumentFormApp
from caiman.storage.store import Store
from caiman.ui.navigation import NavigationApp
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class DocumentEditReviewApp(NavigationApp):
    TITLE = 'Caiman · Review document changes'
    CSS = TERMINAL_CSS + '\n#changes { height: 18; }\nButton { width: auto; }\n'

    def __init__(self, *, service, selection, prepared):
        super().__init__()
        apply_theme(self)
        self.service = service
        self.selection = deepcopy(selection)
        self.prepared = prepared
        self.saving = False

    def compose(self):
        yield Static('caiman  /  review document changes', id='brand')
        with VerticalScroll(id='body'):
            manifest = self.prepared.manifest
            yield Static(f"{document_name(manifest)} · {manifest['version']}\nPod: {self.selection['pod']}", markup=False)
            yield Static('Register saves a metadata snapshot. Existing document pins keep their original snapshot.', classes='hint')
            with Collapsible(title='Review every changed field', collapsed=False):
                before = json.dumps(self.selection['manifest'], indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                after = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                diff = '\n'.join(difflib.unified_diff(before, after, fromfile='Stored document', tofile='Edited draft', lineterm=''))
                yield TextArea(diff, read_only=True, id='changes', soft_wrap=True)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Register changes', id='register', variant='primary')
            yield Button('Continue editing', id='edit')
            yield Button('Back to documents', id='cancel')
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
                result = await asyncio.to_thread(self.service.register, self.selection, self.prepared)
                self.exit(result)
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.saving = False
                for button in self.query(Button):
                    button.disabled = False


def edit_document(root, selection, *, pods=()):
    service = DocumentEditService(Store(root), pods=pods)
    original = service.original(selection)
    draft, message = deepcopy(original), ''
    while True:
        outcome = DocumentFormApp(original=original, draft=draft, message=message, selection=selection).run()
        if outcome is None:
            return None
        _, draft = outcome
        try:
            prepared = service.prepare(selection, draft)
        except (OSError, ValueError) as error:
            message = str(error)
            continue
        if prepared.digest == selection['digest']:
            message = 'This draft matches the registered snapshot. There is nothing to register.'
            continue
        message = ''
        reviewed = DocumentEditReviewApp(service=service, selection=selection, prepared=prepared).run()
        if reviewed == 'edit':
            continue
        return reviewed
