"""Vim-style form navigation without stealing letters while editing."""

from textual import events
from textual.app import App
from textual.binding import Binding
from textual.reactive import reactive
from textual.widgets import Input, OptionList, Select, Static, TextArea


class NavigationApp(App, inherit_bindings=False):
    """Vim keys are the only navigation: no Ctrl+Q, Footer, or command palette."""

    ENABLE_COMMAND_PALETTE = False
    editing = reactive(False)
    BINDINGS = [
        Binding('h', "vim_move('h')", 'Previous', priority=True, show=False),
        Binding('j', "vim_move('j')", 'Next', priority=True, show=False),
        Binding('k', "vim_move('k')", 'Previous', priority=True, show=False),
        Binding('l', "vim_move('l')", 'Next', priority=True, show=False),
        Binding('enter,i', 'vim_edit', 'Edit field', priority=True, show=False),
        Binding('escape', 'vim_normal', 'Navigate', priority=True, show=False),
        Binding('q', 'vim_back', 'Back', priority=True, show=False),
    ]

    def navigation_hint(self):
        return Static(self.navigation_help(), classes='key-hint')

    def navigation_help(self):
        return 'NAVIGATE · h/k previous · j/l next · Enter/i edit · q back'

    def watch_editing(self, editing):
        hint = ('EDIT · hjkl type normally · Esc returns to navigation' if editing else
                self.navigation_help())
        for widget in self.query('.key-hint'):
            widget.update(hint)

    def check_action(self, action, parameters):
        if action.startswith('vim_') and len(self.screen_stack) != 1:
            return False
        if action in {'vim_move', 'vim_back'}:
            return not self.editing
        if action == 'vim_edit':
            return not self.editing and self._editable(self.focused)
        if action == 'vim_normal':
            return self.editing
        return super().check_action(action, parameters)

    @staticmethod
    def _editable(widget):
        return isinstance(widget, Input) or (isinstance(widget, TextArea) and not widget.read_only)

    def on_descendant_focus(self, event: events.DescendantFocus):
        self.editing = False

    def on_click(self, event: events.Click):
        if self._editable(event.widget):
            self.editing = True

    async def on_event(self, event):
        if len(self.screen_stack) != 1:
            await super().on_event(event)
            return
        # Textual excludes character bindings above widgets that consume text.
        # Handle mode keys before forwarding to an input or dropdown search.
        if isinstance(event, events.Key) and not event.is_forwarded:
            if self.editing and event.key == 'escape':
                self.action_vim_normal()
                return
            if not self.editing:
                if event.key == 'q':
                    self.action_vim_back()
                    return
                if event.key in {'h', 'j', 'k', 'l'}:
                    self.action_vim_move(event.key)
                    return
                if event.key in {'enter', 'i'} and self._editable(self.focused):
                    self.action_vim_edit()
                    return
        # Text inputs must not receive incidental typing in navigation mode.
        # Priority bindings still handle the navigation and edit-entry keys.
        if (isinstance(event, (events.Key, events.Paste)) and not event.is_forwarded
                and not self.editing and self._editable(self.focused)):
            if isinstance(event, events.Paste):
                return
            if isinstance(event, events.Key) and event.key not in {'h', 'j', 'k', 'l', 'i'}:
                if event.is_printable or event.key in {'backspace', 'delete'}:
                    return
        await super().on_event(event)

    def action_vim_edit(self):
        self.editing = True

    def action_vim_normal(self):
        self.editing = False

    def action_vim_back(self):
        focused = self.focused
        if focused is not None:
            select = next((node for node in (focused, *focused.ancestors)
                           if isinstance(node, Select) and node.expanded), None)
            if select is not None:
                select.expanded = False
                select.focus()
                return
        # Reuse each form's cancellation guard, including in-flight writes.
        self.action_cancel()

    def action_cancel(self):
        self.exit(None)

    def action_vim_move(self, direction):
        focused = self.focused
        if focused is not None and focused.has_class('dashboard-tile'):
            self._move_tile(focused, direction)
            return
        # Select menus use their own highlighted option, not form focus.
        if isinstance(focused, OptionList):
            select = next((node for node in focused.ancestors if isinstance(node, Select)), None)
            if select is not None and select.expanded:
                if direction == 'j':
                    focused.action_cursor_down()
                elif direction == 'k':
                    focused.action_cursor_up()
                elif direction == 'h':
                    select.expanded = False
                    select.focus()
                else:
                    focused.action_select()
                return
        if direction in {'h', 'k'}:
            self.screen.focus_previous()
        else:
            self.screen.focus_next()

    def _move_tile(self, focused, direction):
        """Follow rendered tile positions, including responsive grid layouts."""
        def region(tile):
            # A collection's narrower face reserves room for its back cards.
            # Navigate by the full grid footprint, not that decorative inset.
            return next((node.region for node in tile.ancestors if node.has_class('card-frame')), tile.region)

        origin = region(focused)
        x, y = origin.center
        top = origin.y
        candidates = []
        for tile in self.query('.dashboard-tile'):
            if tile is focused or tile.disabled or not tile.visible or not tile.display:
                continue
            target = region(tile)
            tx, ty = target.center
            dx, dy = tx - x, ty - y
            if direction in {'h', 'l'}:
                if target.y != top or (dx <= 0 if direction == 'l' else dx >= 0):
                    continue
                score = (abs(dy), abs(dx))
            else:
                if (target.y <= top if direction == 'j' else target.y >= top):
                    continue
                # Visit the next row before choosing its closest column.
                # Tiny width differences must never cause a row to be skipped.
                score = (abs(target.y - top), abs(dx))
            candidates.append((score, tile))
        if candidates:
            min(candidates, key=lambda item: item[0])[1].focus()
