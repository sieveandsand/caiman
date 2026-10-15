"""Home-menu hook installation with an exact settings preview."""

from pathlib import Path

from rich.text import Text
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Input, Label, Static

from caiman.hooks.service import (END_HOOK_HARNESSES, HARNESS_NAMES, end_hook_installed, install_hook,
                                  prepare_hook, prepare_skill)
from caiman.ui.navigation import NavigationApp
from caiman.ui.theme import TERMINAL_CSS, apply_theme

class HookChoice(Button):
    """One hook as a one-line toggle; its mark and focus cue are text, so both survive 16 colors."""

    def __init__(self, title, summary, *, checked=False, **kwargs):
        super().__init__('', classes='hook-choice', **kwargs)
        self.hook, self.summary, self.checked = title, summary, checked
        self.show(focused=False)

    def show(self, focused=None):
        focused = self.has_focus if focused is None else focused
        mark = ('› ' if focused else '  ') + ('[x] ' if self.checked else '[ ] ')
        self.label = Text.assemble(mark + f'{self.hook:<15}', (self.summary, '#8d9982'))

    def on_focus(self):
        self.show(focused=True)

    def on_blur(self):
        # Focus has not moved yet while the blur is delivered.
        self.show(focused=False)


class HooksApp(NavigationApp):
    TITLE = 'Caiman · Add hook'
    CSS = TERMINAL_CSS + '''
#preview { height: auto; margin-top: 1; }
.hook-choice { width: 100%; height: 1; margin: 0; padding: 0 1; content-align: left middle; text-align: left; text-style: none; }
.hook-choice:focus { text-style: bold; }
.hook-choice:disabled { color: #aab69c; text-opacity: 1; }
#end-hint { padding-left: 8; }
#preview-hint { margin-top: 1; }
'''

    def __init__(self, *, harness, store_root, directory=None, home=None):
        super().__init__()
        self.harness = harness
        self.store_root = store_root
        self.directory = directory or Path.cwd()
        self.home = home or Path.home()
        self.plans = []
        self.offers_end = harness in END_HOOK_HARNESSES
        # None follows the chosen project's settings until the user toggles it.
        self.end_choice = None
        apply_theme(self)

    def compose(self):
        yield Static(f'caiman  /  hooks  /  {HARNESS_NAMES[self.harness]}', id='brand')
        with VerticalScroll(id='body'):
            yield Static("Install Caiman's session hooks and agent skill.", id='step-title')
            yield Label('Project directory')
            yield Input(str(self.directory), id='directory')
            yield Label('Hooks')
            yield HookChoice('Session start', 'Registers each session · required', checked=True,
                             id='hook-start', disabled=True)
            if self.offers_end:
                yield HookChoice('Session end', "Deletes a session's documents when it ends", id='hook-end')
                yield Static('A resumed session loads again; little caiman loses its history.',
                             id='end-hint', classes='hint')
            yield Static('Preview lists every file change; existing hooks are kept.', id='preview-hint', classes='hint')
            yield Static('', id='preview', markup=False)
        yield Static('', id='status', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
            yield Button('Preview', id='prepare', variant='primary')
            yield Button('Install', id='install', disabled=True)
        yield self.navigation_hint()

    def on_mount(self):
        self.show_choices()

    def end_selected(self) -> bool:
        if not self.offers_end:
            return False
        if self.end_choice is not None:
            return self.end_choice
        value = self.query_one('#directory', Input).value.strip()
        return bool(value) and end_hook_installed(self.harness, Path(value))

    def show_choices(self):
        if self.offers_end:
            end = self.query_one('#hook-end', HookChoice)
            end.checked = self.end_selected()
            end.show()
            # The cost of the end hook shows only while it is chosen.
            self.query_one('#end-hint', Static).display = end.checked

    def invalidate(self):
        self.plans = []
        self.query_one('#install', Button).disabled = True
        self.query_one('#preview', Static).update('')
        self.query_one('#status', Static).update('')

    def on_input_changed(self, event):
        self.invalidate()
        self.show_choices()

    def on_button_pressed(self, event):
        if event.button.id == 'back':
            self.exit(None)
            return
        if event.button.id == 'hook-end':
            self.end_choice = not self.end_selected()
            self.invalidate()
            self.show_choices()
            return
        try:
            if event.button.id == 'prepare':
                value = self.query_one('#directory', Input).value.strip()
                if not value:
                    raise ValueError('Enter a project directory')
                self.plans = [prepare_hook(self.harness, Path(value), self.store_root, end=self.end_selected()),
                              prepare_skill(self.harness, self.home)]
                self.query_one('#preview', Static).update('\n'.join(plan.preview for plan in self.plans))
                self.query_one('#install', Button).disabled = not any(plan.changed for plan in self.plans)
                self.query_one('#status', Static).update('\n'.join(str(plan.path) for plan in self.plans))
            elif event.button.id == 'install' and self.plans:
                for plan in self.plans:
                    install_hook(plan)
                self.query_one('#install', Button).disabled = True
                self.query_one('#status', Static).update(
                    'Installed. Open /hooks in Codex to review and trust the hook, then start a new session.'
                    if self.harness == 'codex' else
                    'Installed. Restart Claude Code and review the hooks in /hooks.')
        except (OSError, ValueError) as error:
            self.plans = []
            self.query_one('#install', Button).disabled = True
            self.query_one('#status', Static).update(str(error))
