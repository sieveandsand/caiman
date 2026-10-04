"""Dashboard pod creation and Git operations."""

import asyncio

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

from caiman.ui.navigation import NavigationApp
from caiman.repositories.service import RepoManager
from caiman.ui.theme import TERMINAL_CSS, apply_theme


OPERATIONS = {'create': 'New local pod', 'add': 'Clone pod', 'initialize': 'Connect Git',
              'sync': 'Sync pod', 'default': 'Set default pod', 'remove': 'Disconnect Git', 'unregister': 'Remove pod'}


class RepoManagerApp(NavigationApp):
    TITLE = 'Caiman · Pods'
    CSS = TERMINAL_CSS + '''
    #preview { height: auto; margin-top: 1; }
    #operation-title { height: auto; color: #7fdc4f; text-style: bold; }
    #navigation Button { height: 3; }
    '''

    def __init__(self, *, store_root, action='create', pod=None):
        super().__init__()
        self.manager = RepoManager(store_root)
        self.operation = action
        self.selected_pod = pod
        self.plan = None
        self.busy = False
        self.records = []
        apply_theme(self)

    def compose(self):
        yield Static('caiman  /  Pods', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Local folders, optionally shared through Git.', id='step-title')
            yield Static(OPERATIONS[self.operation], id='operation-title')
            with VerticalScroll(id='remove-fields', classes='step'):
                yield Label('Pod')
                yield Select([], prompt='Choose a pod', id='repository')
                yield Static('Files and Git history are preserved in the local archive.' if self.operation == 'unregister' else 'Local files remain available.', classes='hint')
            with VerticalScroll(id='repository-fields', classes='step'):
                yield Label('Pod')
                yield Input(value=self.selected_pod or '', placeholder='pod name', id='pod', disabled=bool(self.selected_pod))
                yield Static('Use letters, digits, dots, hyphens or underscores.', classes='hint')
                yield Label('Repository URL', id='remote-label')
                yield Input(placeholder='git@example.com:team/pod.git', id='remote')

                yield Static('', id='operation-help')
            yield Static('', id='preview', markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
            if self.operation == 'create':
                yield Button('Create', id='create', variant='primary')
            elif self.operation == 'add':
                yield Button('Clone', id='clone', variant='primary')
            else:
                yield Button('Review', id='review', variant='primary')
                yield Button('Apply', id='apply', disabled=True)
        yield self.navigation_hint()

    async def on_mount(self):
        self.show_action()
        await self.refresh_catalog()

    def show_action(self):
        action = self.operation
        choose = action in {'remove', 'sync', 'default', 'unregister'}
        self.query_one('#remove-fields').display = choose
        self.query_one('#repository-fields').display = not choose
        self.query_one('#remote').display = action in {'create', 'add', 'initialize'}
        self.query_one('#remote-label').display = action in {'create', 'add', 'initialize'}
        self.query_one('#remote-label', Label).update('Git remote (optional)' if action in {'create', 'initialize'} else 'Repository URL')
        self.query_one('#operation-help', Static).update({
            'create': 'Leave the remote blank for a local pod. Use Sync to share its contents.',
            'add': 'Clone an existing pod using your Git credentials.',
            'initialize': 'Enable Git in a pod folder. Use Sync to share its contents.',
        }.get(action, ''))

    async def refresh_catalog(self):
        try:
            self.records = await asyncio.to_thread(self.manager.list_repos)
            self.query_one('#repository', Select).set_options([
                (record['pod'] + ' · ' + ('Git unavailable' if record.get('error') else record['remote'] or 'Local only'), record['pod'])
                for record in self.records])
            if self.selected_pod:
                self.query_one('#repository', Select).value = self.selected_pod
                self.query_one('#repository', Select).disabled = True
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))

    def invalidate(self):
        self.plan = None
        for button in self.query('#apply'):
            button.disabled = True
        self.query_one('#preview', Static).update('')

    def on_input_changed(self, event):
        self.invalidate()

    def on_checkbox_changed(self, event):
        self.invalidate()

    def on_select_changed(self, event):
        self.invalidate()

    def set_busy(self, value):
        self.busy = value
        for widget in self.query('Input, Select, Checkbox, Button'):
            widget.disabled = value
        if self.selected_pod:
            self.query_one('#repository', Select).disabled = True
            self.query_one('#pod', Input).disabled = True
        for button in self.query('#apply'):
            button.disabled = value or self.plan is None

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
            if event.button.id in {'review', 'create', 'clone'}:
                self.invalidate()
                action = self.operation
                pod = (self.query_one('#repository', Select).value if action in {'remove', 'sync', 'default', 'unregister'}
                               else self.query_one('#pod', Input).value.strip())
                if not isinstance(pod, str) or not pod:
                    raise ValueError('Choose a pod' if action in {'remove', 'sync', 'default', 'unregister'} else 'Enter a pod')
                remote = self.query_one('#remote', Input).value.strip()
                push = False
                self.plan = await asyncio.to_thread(self.manager.prepare, action, pod, remote, push)
                if event.button.id in {'create', 'clone'}:
                    self.query_one('#status', Static).update(
                        'Cloning pod…' if action == 'add' else 'Creating pod…')
                    await asyncio.to_thread(self.manager.apply, self.plan)
                    self.exit(None)
                    return
                self.query_one('#preview', Static).update(self.plan.preview)
                self.query_one('#apply', Button).label = OPERATIONS[action]
                self.query_one('#status', Static).update('Review the operation above, then apply it.')
            elif event.button.id == 'apply' and self.plan is not None:
                plan = self.plan
                self.query_one('#status', Static).update('Checking and applying pod operation…')
                await asyncio.to_thread(self.manager.apply, plan)
                if plan.action == 'unregister':
                    self.exit(None)
                    return
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
