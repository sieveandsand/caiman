"""Dashboard repository setup with explicit preview and application."""

import asyncio

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from caiman.ui.navigation import NavigationApp
from caiman.repositories.service import RepoManager
from caiman.ui.theme import TERMINAL_CSS, apply_theme


OPERATIONS = {'create': 'New local pod', 'add': 'Clone pod', 'initialize': 'Connect Git',
              'sync': 'Sync pod', 'default': 'Set default pod', 'remove': 'Disconnect Git'}


class RepoManagerApp(NavigationApp):
    TITLE = 'Caiman · Pods'
    CSS = TERMINAL_CSS + '\n#catalog, #preview { height: auto; margin-top: 1; }\n'

    def __init__(self, *, store_root, action='create'):
        super().__init__()
        self.manager = RepoManager(store_root)
        self.initial_action = action
        self.plan = None
        self.busy = False
        self.records = []
        apply_theme(self)

    def compose(self):
        yield Static('caiman  /  Pods', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Local folders, optionally shared through Git.', id='step-title')
            yield Static('', id='catalog', markup=False)
            yield Label('Action')
            yield Select([(label, key) for key, label in OPERATIONS.items()],
                         value=self.initial_action, allow_blank=False, id='operation')
            with VerticalScroll(id='remove-fields', classes='step'):
                yield Label('Registered repository')
                yield Select([], prompt='Choose a repository', id='repository')
                yield Static('Local files remain available.', classes='hint')
            with VerticalScroll(id='repository-fields', classes='step'):
                yield Label('Pod')
                yield Input(placeholder='alpha', id='pod')
                yield Static('Choose a pod name, such as alpha.', classes='hint')
                yield Label('Repository URL', id='remote-label')
                yield Input(placeholder='git@example.com:team/store-alpha.git', id='remote')

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
        choose = action in {'remove', 'sync', 'default'}
        self.query_one('#remove-fields').display = choose
        self.query_one('#repository-fields').display = not choose
        self.query_one('#remote').display = action in {'add', 'initialize'}
        self.query_one('#remote-label').display = action in {'add', 'initialize'}
        self.query_one('#remote-label', Label).update('Repository URL (optional)' if action == 'initialize' else 'Repository URL')
        self.query_one('#operation-help', Static).update({
            'create': 'Creates a folder. Git is optional.',
            'add': 'Clone an existing pod using your Git credentials.',
            'initialize': 'Enable Git in a pod folder. Use Sync to share its contents.',
        }.get(action, ''))

    async def refresh_catalog(self):
        try:
            self.records = await asyncio.to_thread(self.manager.list_repos)
            self.query_one('#repository', Select).set_options([
                (record['pod'] + ' · ' + (record['remote'] or 'Local only'), record['pod'])
                for record in self.records])
            lines = []
            for record in self.records:
                state = 'Git connected' if record['initialized'] else 'Local folder'
                if record['default']:
                    state += ' · Default'
                lines.append(f"{record['pod']} · {state}\n{record['remote'] or 'Local only'}")
            self.query_one('#catalog', Static).update('\n\n'.join(lines) or 'No pods yet.')
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
                pod = (self.query_one('#repository', Select).value if action in {'remove', 'sync', 'default'}
                               else self.query_one('#pod', Input).value.strip())
                if not isinstance(pod, str) or not pod:
                    raise ValueError('Choose a registered repository' if action in {'remove', 'sync', 'default'} else 'Enter a pod')
                remote = self.query_one('#remote', Input).value.strip()
                push = False
                self.plan = await asyncio.to_thread(self.manager.prepare, action, pod, remote, push)
                self.query_one('#preview', Static).update(self.plan.preview)
                self.query_one('#apply', Button).label = OPERATIONS[action]
                self.query_one('#status', Static).update('Review the operation above, then apply it.')
            elif event.button.id == 'apply' and self.plan is not None:
                plan = self.plan
                self.query_one('#status', Static).update('Checking remote and applying repository operation…')
                await asyncio.to_thread(self.manager.apply, plan)
                self.invalidate()
                await self.refresh_catalog()
                message = OPERATIONS[plan.action] + ' complete.'
                self.query_one('#status', Static).update(message)
        except (OSError, ValueError) as error:
            self.invalidate()
            await self.refresh_catalog()
            self.query_one('#status', Static).update(str(error))
        finally:
            self.set_busy(False)
