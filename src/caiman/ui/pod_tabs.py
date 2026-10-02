"""Shared pod tabs and keyboard navigation for catalog galleries."""

from textual.binding import Binding
from textual.widgets import Tab, Tabs


POD_BINDINGS = [
    Binding('left_square_bracket', 'switch_pod(-1)', 'Previous pod'),
    Binding('right_square_bracket,slash', 'switch_pod(1)', 'Next pod'),
]
POD_HELP = '/ next pod · Tab controls'


class PodTabsMixin:
    async def update_pod_tabs(self, available):
        if self.active_pod not in available:
            default = self.service.store.pods.default
            self.active_pod = default if default in available else next(iter(available))
        tabs = self.query_one('#pod-tabs', Tabs)
        await tabs.clear()
        self.tab_pods = {f'pod-{i}': pod for i, pod in enumerate(available)}
        for tab_id, pod in self.tab_pods.items():
            await tabs.add_tab(Tab(available[pod], id=tab_id))
        tabs.active = next(key for key, pod in self.tab_pods.items() if pod == self.active_pod)

    async def on_tabs_tab_activated(self, event: Tabs.TabActivated):
        if (self.busy or event.tab.id not in self.tab_pods or event.tab.id != event.tabs.active
                or self.tab_pods[event.tab.id] == self.active_pod):
            return
        self.active_pod = self.tab_pods[event.tab.id]
        await self.render_pod()

    def action_switch_pod(self, step):
        if self.busy or len(self.screen_stack) != 1:
            return
        tabs = self.query_one('#pod-tabs', Tabs)
        # Keep focus on a surviving control while the old cards are removed.
        tabs.focus()
        if step < 0:
            tabs.action_previous_tab()
        else:
            tabs.action_next_tab()

    def action_vim_move(self, direction):
        if isinstance(self.focused, Tabs) and direction == 'j':
            cards = self.query('.card-face')
            if cards:
                cards.first().focus()
            return
        if isinstance(self.focused, Tabs) and direction in {'h', 'l'}:
            self.action_switch_pod(-1 if direction == 'h' else 1)
            return
        super().action_vim_move(direction)
