"""Dashboard repository setup with explicit preview and application."""

import asyncio

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from caiman.ui.navigation import NavigationApp
from caiman.repositories.service import RepoManager
from caiman.ui.theme import TERMINAL_CSS, apply_theme


OPERATIONS = {'add': 'Add repository', 'remove': 'Remove repository', 'initialize': 'Initialize repository'}


class RepoManagerApp(NavigationApp):
    TITLE = 'Caiman · Repo Manager'
    CSS = TERMINAL_CSS + '\n#catalog, #preview { height: auto; margin-top: 1; }\n'

    def __init__(self, *, store_root, action='add'):
        super().__init__()
        self.manager = RepoManager(store_root)
        self.initial_action = action
        self.plan = None
        self.busy = False
        self.records = []
        apply_theme(self)

    def compose(self):
        yield Static('caiman  /  Repo Manager', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Manage a repository for each compartment.', id='step-title')
            yield Static('', id='catalog', markup=False)
            yield Label('Action')
            yield Select([(label, key) for key, label in OPERATIONS.items()],
                         value=self.initial_action, allow_blank=False, id='operation')
            with VerticalScroll(id='remove-fields', classes='step'):
                yield Label('Registered repository')
                yield Select([], prompt='Choose a repository', id='repository')
                yield Static('Removes the saved entry. Local files and the hosted repository are kept.', classes='hint')
            with VerticalScroll(id='repository-fields', classes='step'):
                yield Label('Compartment')
                yield Input(placeholder='alpha', id='compartment')
                yield Static('One customer or project group. Use public for public documents.', classes='hint')
                yield Label('Repository URL', id='remote-label')
                yield Input(placeholder='git@example.com:team/store-alpha.git', id='remote')
                yield Checkbox('Push initial metadata to this remote', id='push')
                yield Static('', id='operation-help')
            yield Static('', id='preview', markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
            yield Button('Review', id='review', variant='primary')
            yield Button('Apply', id='apply', disabled=True)
        yield self.navigation_hint()

    async def on_mount(self):
        self.show_action()
        await self.refresh_catalog()

    def show_action(self):
        action = self.query_one('#operation', Select).value
        self.query_one('#remove-fields').display = action == 'remove'
        self.query_one('#repository-fields').display = action != 'remove'
        self.query_one('#push').display = action == 'initialize'
        self.query_one('#remote-label', Label).update('Repository URL (optional)' if action == 'initialize' else 'Repository URL')
        self.query_one('#operation-help', Static).update(
            'Creates locally. Optional push requires an empty remote you already created; it sends only Caiman metadata.'
            if action == 'initialize' else
            'Checks the remote caiman-store branch and compartment before saving its SSH or HTTPS address. Use a private repository; Git-host membership controls access.')

    async def refresh_catalog(self):
        try:
            self.records = await asyncio.to_thread(self.manager.list_repos)
            self.query_one('#repository', Select).set_options([
                (record['compartment'] + ' · ' + (record['remote'] or 'Local only'), record['compartment'])
                for record in self.records])
            lines = []
            for record in self.records:
                state = 'Local repo initialized' if record['initialized'] else 'Address registered'
                lines.append(f"{record['compartment']} · {state}\n{record['remote'] or 'Local only'}")
            self.query_one('#catalog', Static).update('\n\n'.join(lines) or 'No repositories registered yet.')
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))

    def invalidate(self):
        self.plan = None
        self.query_one('#apply', Button).disabled = True
        self.query_one('#preview', Static).update('')

    def on_input_changed(self, event):
        self.invalidate()

    def on_checkbox_changed(self, event):
        self.invalidate()

    def on_select_changed(self, event):
        self.invalidate()
        if event.select.id == 'operation':
            self.show_action()

    def set_busy(self, value):
        self.busy = value
        for widget in self.query('Input, Select, Checkbox, Button'):
            widget.disabled = value
        self.query_one('#apply', Button).disabled = value or self.plan is None

    def action_cancel(self):
        if not self.busy:
            self.exit(None)

    async def on_button_pressed(self, event):
        if self.busy:
            return
        if event.button.id == 'back':
            self.action_cancel()
            return
        self.set_busy(True)
        try:
            if event.button.id == 'review':
                self.invalidate()
                action = self.query_one('#operation', Select).value
                compartment = (self.query_one('#repository', Select).value if action == 'remove'
                               else self.query_one('#compartment', Input).value.strip())
                if not isinstance(compartment, str) or not compartment:
                    raise ValueError('Choose a registered repository' if action == 'remove' else 'Enter a compartment')
                remote = self.query_one('#remote', Input).value.strip()
                push = action == 'initialize' and self.query_one('#push', Checkbox).value
                self.plan = await asyncio.to_thread(self.manager.prepare, action, compartment, remote, push)
                self.query_one('#preview', Static).update(self.plan.preview)
                self.query_one('#apply', Button).label = OPERATIONS[action]
                self.query_one('#status', Static).update('Review the operation above, then apply it.')
            elif event.button.id == 'apply' and self.plan is not None:
                plan = self.plan
                self.query_one('#status', Static).update('Checking remote and applying repository operation…')
                await asyncio.to_thread(self.manager.apply, plan)
                self.invalidate()
                await self.refresh_catalog()
                message = {'add': 'Caiman repository verified and saved.',
                           'remove': 'Registration removed. Repository files were kept.',
                           'initialize': ('Initial metadata pushed. ' if plan.push else '') + 'Local repository ready: ' + str(plan.local_path)}[plan.action]
                self.query_one('#status', Static).update(message)
        except (OSError, ValueError) as error:
            self.invalidate()
            await self.refresh_catalog()
            self.query_one('#status', Static).update(str(error))
        finally:
            self.set_busy(False)
