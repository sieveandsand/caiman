"""Document gallery → guided metadata form → review → immutable registration."""

import asyncio
from copy import deepcopy
import difflib
import json

from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Collapsible, Static, TextArea

from caiman.documents.cards import document_name
from caiman.documents.edit_service import DocumentEditService
from caiman.documents.form import DocumentFormApp
from caiman.storage.store import Store
from caiman.ui.navigation import NavigationApp
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class DocumentEditReviewApp(NavigationApp):
    TITLE = 'Caiman · Review document changes'
    CSS = TERMINAL_CSS + '''
    #document-identity { height: auto; margin-bottom: 1; text-style: bold; }
    #update-summary, #sync-note { margin-bottom: 1; }
    #affected-usages { height: auto; margin: 1 0; }
    .section-heading { height: auto; text-style: bold; color: #eef3e6; margin-bottom: 1; }
    .usage-group { height: auto; border: solid #aab69c; padding: 1 2; margin-bottom: 1; }
    .usage-group > Static { height: auto; }
    .usage-entry { margin-top: 1; }
    #usage-warning { margin-bottom: 1; }
    #changes { height: 18; }
    Button { width: auto; }
    '''

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
            yield Static(f"{document_name(manifest)} · {manifest['version']}\nPod: {self.selection['pod']}",
                         id='document-identity', markup=False)
            summary = 'Saves a complete manifest revision. All references, including older boards, show the approved metadata. File content stays fixed.'
            yield Static(summary, classes='hint', id='update-summary')
            if self.prepared.usages:
                with Vertical(id='affected-usages'):
                    yield Static('Affected local usages', classes='section-heading')
                    for kind, title in (('project', 'Projects'), ('board', 'Boards'), ('collection', 'Document collections')):
                        usages = [usage for usage in self.prepared.usages.usages if usage['kind'] == kind]
                        if usages:
                            with Vertical(classes='usage-group', id=f'affected-{kind}s'):
                                yield Static(f'{title} ({len(usages)})', classes='section-heading')
                                for index, usage in enumerate(usages):
                                    yield Static(usage['label'].removeprefix(f'{kind.title()}: '),
                                                 classes='usage-entry' if index else '', markup=False)
                    if not self.prepared.usages.usages:
                        yield Static('No current local usages found.', classes='hint')
                if self.prepared.usages.unknown:
                    yield Static('Usage scan incomplete:\n\n' + '\n\n'.join(self.prepared.usages.unknown),
                                 id='usage-warning', classes='error', markup=False)
            yield Static('Other clones receive metadata changes after pod Sync. Changed file content belongs in a new document.',
                         classes='hint', id='sync-note')
            with Collapsible(title='Review every changed field', collapsed=False):
                before = json.dumps(self.selection['manifest'], indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                after = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                diff = '\n'.join(difflib.unified_diff(before, after, fromfile='Stored document', tofile='Edited draft', lineterm=''))
                yield TextArea(diff, read_only=True, id='changes', soft_wrap=True)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Save metadata', id='register', variant='primary')
            yield Button('Continue editing', id='edit')
        yield self.navigation_hint()

    def action_cancel(self):
        if not self.saving:
            self.exit(None)

    async def on_button_pressed(self, event):
        if self.saving:
            return
        if event.button.id == 'edit':
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
        outcome = DocumentFormApp(original=original, draft=draft, message=message,
                                  selection=selection, store_root=root).run()
        if outcome is None:
            return None
        _, draft = outcome
        try:
            prepared = service.prepare(selection, draft)
        except (OSError, ValueError) as error:
            message = str(error)
            continue
        if prepared.mode == 'unchanged':
            message = 'This draft matches the registered snapshot. There is nothing to register.'
            continue
        message = ''
        reviewed = DocumentEditReviewApp(service=service, selection=selection, prepared=prepared).run()
        if reviewed == 'edit':
            continue
        return reviewed
