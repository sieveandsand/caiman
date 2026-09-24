"""Home-menu hook installation with an exact settings preview."""

from pathlib import Path

from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, Static

from caiman.hooks.service import HARNESS_NAMES, install_hook, prepare_hook
from caiman.ui.navigation import NavigationApp
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class HooksApp(NavigationApp):
    TITLE = 'Caiman · Add hook'
    CSS = TERMINAL_CSS + '\n#preview { height: auto; margin-top: 1; }\n'

    def __init__(self, *, harness, store_root, directory=None):
        super().__init__()
        self.harness = harness
        self.store_root = store_root
        self.directory = directory or Path.cwd()
        self.plan = None
        apply_theme(self)

    def compose(self):
        yield Static(f'caiman  /  hooks  /  {HARNESS_NAMES[self.harness]}', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Add Caiman startup guidance to this project.', id='step-title')
            yield Static('Introduces Caiman commands when a session starts or resumes.\n'
                         'Document syncing and access logging are not available yet.', classes='hint')
            yield Label('Project directory')
            yield Input(str(self.directory), id='directory')
            yield Static('Preview the exact settings change, then choose Install. Existing hooks are preserved.', classes='hint')
            yield Static('', id='preview', markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
            yield Button('Preview', id='prepare', variant='primary')
            yield Button('Install', id='install', disabled=True)
        yield self.navigation_hint()

    def on_input_changed(self, event):
        self.plan = None
        self.query_one('#install', Button).disabled = True
        self.query_one('#preview', Static).update('')
        self.query_one('#status', Static).update('')

    def on_button_pressed(self, event):
        if event.button.id == 'back':
            self.exit(None)
            return
        try:
            if event.button.id == 'prepare':
                value = self.query_one('#directory', Input).value.strip()
                if not value:
                    raise ValueError('Enter a project directory')
                self.plan = prepare_hook(self.harness, Path(value), self.store_root)
                self.query_one('#preview', Static).update(self.plan.preview)
                self.query_one('#install', Button).disabled = not self.plan.changed
                self.query_one('#status', Static).update(str(self.plan.path))
            elif event.button.id == 'install' and self.plan is not None:
                install_hook(self.plan)
                self.query_one('#install', Button).disabled = True
                self.query_one('#status', Static).update(
                    'Installed. Open /hooks in Codex to review and trust the hook, then start a new session.'
                    if self.harness == 'codex' else
                    'Installed. Restart Claude Code and review the hook in /hooks.')
        except (OSError, ValueError) as error:
            self.plan = None
            self.query_one('#install', Button).disabled = True
            self.query_one('#status', Static).update(str(error))
