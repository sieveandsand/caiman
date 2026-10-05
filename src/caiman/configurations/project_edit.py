"""Project editing: guided form, optional Vim, explicit review, then registration."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import difflib
import json
from pathlib import Path

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Static, TextArea

from caiman.configurations.models import project_boards, realized_parts
from caiman.configurations.service import ConfigurationService
from caiman.storage.store import Store
from caiman.ui.navigation import NavigationApp
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class ProjectEditReviewApp(NavigationApp):
    TITLE = 'Caiman · Review project changes'
    CSS = TERMINAL_CSS + '\nButton { width: auto; }\n#changes { height: 18; }\n'

    def __init__(self, *, root, original, prepared=None, error=None, original_digest=None, original_pod=None):
        super().__init__()
        apply_theme(self)
        self.root = root
        self.original = original
        self.original_digest = original_digest
        self.original_pod = original_pod
        self.prepared = prepared
        self.error = error
        self.saving = False

    def summary(self) -> str:
        manifest = self.prepared.manifest
        lines = [f"Project: {manifest['project']} @ {manifest['version']}",
                 'Pod: ' + self.prepared.pod]
        lines.extend(f"Board: {board['name']} @ {board['version']}  ({board['digest']})"
                     for board in project_boards(manifest))
        lines += [f"Specification set: {manifest['spec_set']}",
                 f"{len(manifest['documents'])} documents · {len(manifest['features'])} features"]
        for feature in manifest['features']:
            lines.append(f"Feature {feature['name']}: {feature['scope']}")
            lines.extend(f"  Realized on {role} · {board} @ {version}"
                         for board, version, role in realized_parts(manifest, feature))
        return '\n'.join(lines)

    def compose(self):
        yield Static('caiman  /  review project changes', id='brand')
        with VerticalScroll(id='body'):
            if self.prepared is None:
                yield Static('The draft needs correction before it can be registered.', classes='hint')
                yield Static(str(self.error), markup=False)
                yield Static('Your edited file is retained while you keep editing. Back discards this draft.', classes='hint')
            else:
                manifest = self.prepared.manifest
                yield Static(self.summary(), markup=False)
                same_label = all(manifest[key] == self.original.get(key) for key in ('project', 'version'))
                yield Static('Register updates this project in place. Existing digest pins remain unchanged.' if same_label else
                             'Register renames this project to the name/version above. Existing digest pins remain unchanged.',
                             classes='hint')
                yield Static(f'Manifest: {self.prepared.digest}', markup=False)
                with Collapsible(title='Review every changed field', collapsed=False):
                    before = json.dumps(self.original, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                    after = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True).splitlines()
                    diff = '\n'.join(difflib.unified_diff(before, after, fromfile='Stored project',
                                                          tofile='Edited draft', lineterm=''))
                    yield TextArea(diff, read_only=True, id='changes', soft_wrap=True)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            if self.prepared is not None:
                yield Button('Register changes', id='register', variant='primary')
            yield Button('Continue editing', id='edit')
            yield Button('Back to projects', id='cancel')
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
                replaces = None if self.original_digest is None else {'manifest': self.original,
                                                                      'digest': self.original_digest, 'pod': self.original_pod or self.prepared.pod}
                registration = await asyncio.to_thread(ConfigurationService(Store(self.root)).register,
                                                       self.prepared, replaces=replaces)
                self.exit({'manifest': deepcopy(self.prepared.manifest), 'digest': registration.digest, 'pod': self.prepared.pod})
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.saving = False
                for button in self.query(Button):
                    button.disabled = False


class ProjectDeleteApp(NavigationApp):
    """Confirm removing one project version from the list; exits True once deleted."""

    TITLE = 'Caiman · Delete project'
    CSS = TERMINAL_CSS + '\nButton { width: auto; }\n'

    def __init__(self, *, root, selection):
        super().__init__()
        apply_theme(self)
        self.root = root
        self.selection = selection
        self.deleting = False

    def compose(self):
        manifest = self.selection['manifest']
        yield Static('caiman  /  delete project', id='brand')
        with VerticalScroll(id='body'):
            yield Static(f"Delete {manifest['project']} @ {manifest['version']} from "
                         + self.selection.get('pod', 'public') + '?', markup=False)
            yield Static('The project leaves the project list. Its snapshot stays in the store by digest, so '
                         'anything already pinned to it keeps working. Nothing is pushed.', classes='hint')
            yield Static(f"Manifest: {self.selection['digest']}", markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Keep project', id='cancel', variant='primary')
            yield Button('Delete project', id='delete', variant='error')
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
                await asyncio.to_thread(ConfigurationService(Store(self.root)).unregister, 'project',
                                        self.selection['manifest'], self.selection['digest'], pod=self.selection.get('pod', 'public'))
                self.exit(True)
            except (OSError, ValueError) as error:
                self.query_one('#status', Static).update(str(error))
            finally:
                self.deleting = False
                for button in self.query(Button):
                    button.disabled = False


def edit_project(root: Path, service: ConfigurationService, selection: dict, draft: dict | None = None) -> dict | None:
    """Drive one project through the guided form, Vim, and review.

    The form opens on the stored snapshot and Register updates that project in
    place, moving its ref if the name, version, or pods changed. Returns
    the registered project, if any. Delete, once confirmed, removes the project
    from the list and returns None.
    """
    from caiman.configurations.editor import vim_excursion
    from caiman.configurations.project_form import ProjectFormApp

    original = selection['manifest']
    draft, message = deepcopy(original if draft is None else draft), ''
    draft.setdefault('pod', selection.get('pod', service.store.pods.default))
    # Pod ownership lives outside the stored manifest. Compare the form against
    # the same editable context, without treating that supplied field as an edit.
    form_original = dict(original, pod=selection.get('pod', service.store.pods.default))
    while True:
        outcome = ProjectFormApp(original=form_original, draft=draft, message=message, root=root).run()
        if outcome is None:
            return None
        action, draft = outcome
        message = ''
        if action == 'delete':
            if ProjectDeleteApp(root=root, selection=selection).run():
                return None
            continue
        if action == 'raw':
            edited = vim_excursion(root, original, draft, review=ProjectEditReviewApp)
            if edited is not None:
                draft = edited
            continue
        try:
            prepared = service.prepare('project', draft, pod=draft.get('pod', selection.get('pod', service.store.pods.default)))
        except (OSError, ValueError) as invalid:
            message = str(invalid)
            continue
        if prepared.digest == selection['digest'] and prepared.pod == selection.get('pod', prepared.pod):
            message = 'This draft matches the registered snapshot. There is nothing to register.'
            continue
        reviewed = ProjectEditReviewApp(root=root, original=original, prepared=prepared,
                                        original_digest=selection['digest'], original_pod=selection.get('pod')).run()
        if reviewed == 'edit':
            continue
        return reviewed if isinstance(reviewed, dict) else None


def run_project_gallery(root: Path, pods) -> dict | None:
    """Gallery → guided form → review, as boards do; no separate viewer page.

    Vim runs only after every app releases the terminal; no nested TUIs.
    Returns the last project registered from the gallery, if any, or hands the
    add card back to the workflow as ``{'action': 'create-project'}``.
    """
    from caiman.configurations.gallery import ProjectGalleryApp
    from caiman.dashboard.actions import ViewerApp

    registered = None
    service = ConfigurationService(Store(root))
    active_pod = None
    while True:
        selection = ProjectGalleryApp(root=root, pods=pods, pod=active_pod).run()
        if selection is None:
            return registered
        if isinstance(selection, dict):
            active_pod = selection.get('pod', active_pod)
        if isinstance(selection, dict) and selection.get('action') == 'add':
            return {'action': 'create-project', 'registered': registered, 'pod': active_pod}
        if selection == 'add':
            return {'action': 'create-project', 'registered': registered}
        try:
            registered = edit_project(root, service, selection, selection['manifest']) or registered
        except (OSError, ValueError) as error:
            ViewerApp(title='Project editor needs attention', content=str(error)).run()
