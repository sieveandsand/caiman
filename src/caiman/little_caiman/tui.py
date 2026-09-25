"""Little caiman: a narrow, one-column sidecar beside a Claude Code or Codex session.

The picker lists recent sessions; the usage view tails the chosen transcript
and shows which managed documents were read, searched, or edited, and whether
the bytes on disk still match the store. Nothing here writes a file.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import time

from rich.console import Console
from rich.text import Text
from textual.binding import Binding
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Static

from caiman.little_caiman.service import (ABSENCE_NOTICE, HARNESS_NAMES, Session, UsageTracker,
                                          list_sessions)
from caiman.ui.cards import CARD_CSS, CardFrame, OverviewCard
from caiman.ui.navigation import NavigationApp
from caiman.ui.pixel_title import pixel_title
from caiman.ui.theme import TERMINAL_CSS, apply_theme

POLL_SECONDS = 2
SECTIONS_SHOWN = 4
STATUS = {
    'modified': ('Modified · no stored blob matches', '#e69a89'),
    'missing': ('Missing from disk', '#e69a89'),
    'unverified': ('Unverified · store not found', '#8d9982'),
}


def ago(timestamp: float, now: float | None = None) -> str:
    seconds = max(0, int((time.time() if now is None else now) - timestamp))
    for unit, size in (('d', 86400), ('h', 3600), ('m', 60)):
        if seconds >= size:
            return f'{seconds // size}{unit} ago'
    return 'just now'


def parse_stamp(value: str) -> float | None:
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (AttributeError, ValueError):
        return None
    return (stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)).timestamp()


class CardText:
    """The card hierarchy: dot headings, then summary, then items, blank-line separated."""

    def __init__(self, width):
        self.available = max(1, width - 6)
        self.text = Text(no_wrap=True, overflow='crop')
        self.console = Console()

    def line(self, value, style=''):
        for wrapped in Text(value).wrap(self.console, self.available, overflow='fold'):
            self.text.append(wrapped.plain + '\n', style=style)

    def facts(self, values, style):
        """Join facts with ` · `, breaking lines between facts rather than inside one."""
        rows = []
        for value in values:
            if rows and len(rows[-1]) + 3 + len(value) <= self.available:
                rows[-1] += ' · ' + value
            else:
                rows.append(value)
        for row in rows:
            self.line(row, style)

    def heading(self, value, fallback, color):
        dots = pixel_title(value, self.available)
        if dots:
            for row in dots:
                self.text.append(row + '\n', style=color)
        else:
            self.line(fallback, f'bold {color}')

    def gap(self):
        self.text.append('\n')

    def finish(self, card):
        self.text.rstrip()
        card.label = self.text
        height = len(self.text.plain.splitlines()) + 2
        card.styles.height = height
        return height


class SessionCard(OverviewCard):
    def __init__(self, session: Session, *, index):
        super().__init__('', id=f'session-{index}', classes='dashboard-tile card-face')
        self.session = session

    def format_card(self, width):
        session = self.session
        card = CardText(width)
        name = session.cwd.name if session.cwd and session.cwd.name else session.session_id[:8]
        card.heading(name, name, '#eef3e6')
        card.gap()
        harness = HARNESS_NAMES[session.harness]
        card.heading(harness, harness, '#7fdc4f')
        card.gap()
        card.facts([f'Active {ago(session.updated)}', session.session_id[:8]], 'bold #aab69c')
        if session.title:
            card.gap()
            card.line(session.title, '#dfe6d3')
        return card.finish(self)


class SessionSummaryCard(OverviewCard):
    """The watched session; activating it returns to the session list."""

    def __init__(self, tracker: UsageTracker):
        super().__init__('', id='session-summary', classes='dashboard-tile card-face')
        self.tracker = tracker

    def format_card(self, width):
        tracker, session = self.tracker, self.tracker.session
        usages = tracker.documents.values()
        card = CardText(width)
        name = session.cwd.name if session.cwd and session.cwd.name else session.session_id[:8]
        card.heading(name, name, '#eef3e6')
        card.gap()
        harness = HARNESS_NAMES[session.harness]
        card.heading(harness, harness, '#7fdc4f')
        card.gap()
        modified = sum(tracker.integrity(usage.ref).state == 'modified' for usage in usages)
        card.facts([f'{len(tracker.documents)} Docs', f'{sum(u.reads for u in usages)} Reads',
                    f'{sum(u.searches for u in usages)} Searches', f'{sum(u.edits for u in usages)} Edits'],
                   'bold #aab69c')
        details = []
        if tracker.tree_searches:
            details.append((f'{tracker.tree_searches} searches across all documents', '#dfe6d3'))
        if modified:
            details.append((f'{modified} modified on disk', '#e69a89'))
        if not tracker.has_workspace:
            details.append(('No .caiman/documents here; only store reads can appear', '#8d9982'))
        if details:
            card.gap()
            for value, style in details:
                card.line(value, style)
        return card.finish(self)


class DocumentUsageCard(OverviewCard):
    """One touched document; Enter shows every section instead of the busiest few."""

    def __init__(self, tracker: UsageTracker, key: Path, *, index):
        super().__init__('', id=f'usage-{index}', classes='dashboard-tile card-face')
        self.tracker = tracker
        self.key = key
        self.expanded = False

    def format_card(self, width):
        usage = self.tracker.documents[self.key]
        ref = usage.ref
        card = CardText(width)
        card.heading(ref.title, ref.title, '#eef3e6')
        card.gap()
        if ref.version is not None:
            card.heading(ref.version, 'Version ' + ref.version, '#7fdc4f')
        else:
            card.line('Read from the store directly', 'bold #7fdc4f')
        card.gap()
        counts = [f'Read {usage.reads}×']
        if usage.searches:
            counts.append(f'Searched {usage.searches}×')
        if usage.edits:
            counts.append(f'Edited {usage.edits}×')
        card.facts(counts, 'bold #aab69c')
        context = [ref.scope] if ref.scope else []
        if (seen := parse_stamp(usage.last_seen)) is not None:
            context.append(ago(seen))
        if usage.via_shell:
            context.append(f'{usage.via_shell} via shell')
        if context:
            card.facts(context, '#8d9982')
        integrity = self.tracker.integrity(ref)
        if integrity.state in STATUS:
            card.line(*STATUS[integrity.state])
        if integrity.writable:
            card.line('Writable · expected read-only', '#e69a89')
        sections = [(f'{count}× {name}', '#dfe6d3') for name, count in usage.sections.most_common()]
        if usage.whole_reads:
            sections.insert(0, (f'{usage.whole_reads}× Whole document', '#dfe6d3'))
        if sections:
            card.gap()
            shown = sections if self.expanded else sections[:SECTIONS_SHOWN]
            for value, style in shown:
                card.line(value, style)
            if len(sections) > len(shown):
                card.line(f'+{len(sections) - len(shown)} more · Enter to show', '#8d9982')
        return card.finish(self)


class LittleApp(NavigationApp):
    CSS = TERMINAL_CSS + CARD_CSS + '''
    #brand { height: 1; }
    .little-grid { height: auto; grid-size: 1; grid-columns: 1fr; grid-gutter: 1 0; }
    #little-status { height: auto; margin-bottom: 1; color: #aab69c; }
    #notice { height: auto; padding: 0 2; color: #8d9982; }
    #navigation Button { width: auto; }
    '''
    BINDINGS = [('pagedown', 'page_down', 'Scroll down'), ('pageup', 'page_up', 'Scroll up')]

    def __init__(self):
        super().__init__()
        apply_theme(self)

    def on_resize(self, event):
        self.resize_cards(event.size.width)

    def resize_cards(self, terminal_width=None):
        # Body padding and the scrollbar; always one column for a narrow pane.
        width = max(16, (terminal_width or self.size.width) - 6)
        for grid in self.query('.little-grid'):
            heights = [frame.resize_card(width) for frame in grid.children]
            grid.styles.grid_rows = heights or [1]
            grid.styles.height = sum(heights) + max(0, len(heights) - 1)

    def action_page_down(self):
        self.query_one('#body', VerticalScroll).scroll_page_down(animate=False)

    def action_page_up(self):
        self.query_one('#body', VerticalScroll).scroll_page_up(animate=False)


class SessionPickerApp(LittleApp):
    TITLE = 'Caiman · Little caiman'
    BINDINGS = [Binding('r', 'reload', 'Refresh', show=False)]

    def __init__(self, *, home: Path | None = None):
        super().__init__()
        self.home = home
        self.sessions = []

    def navigation_help(self):
        return 'j/k move · Enter watch · r refresh · q back'

    def compose(self):
        yield Static('little caiman', id='brand')
        with VerticalScroll(id='body'):
            yield Static('Finding sessions…', id='little-status', markup=False)
            yield Grid(id='sessions', classes='little-grid')
        with Horizontal(id='navigation'):
            yield Button('Back', id='back')
        yield self.navigation_hint()

    async def on_mount(self):
        await self.action_reload()

    async def action_reload(self):
        status = self.query_one('#little-status', Static)
        try:
            self.sessions = await asyncio.to_thread(list_sessions, self.home)
        except OSError as error:
            status.update(str(error))
            return
        grid = self.query_one('#sessions', Grid)
        await grid.remove_children()
        await grid.mount_all([CardFrame(SessionCard(session, index=index))
                              for index, session in enumerate(self.sessions)])
        status.update('Pick the session you are working in.' if self.sessions else
                      'No Claude Code or Codex sessions found.')
        self.resize_cards()
        if self.sessions:
            self.query_one('#session-0', Button).focus()

    def on_button_pressed(self, event):
        if isinstance(event.button, SessionCard):
            self.exit(event.button.session)
        elif event.button.id == 'back':
            self.exit(None)


class UsageApp(LittleApp):
    TITLE = 'Caiman · Little caiman'

    def __init__(self, *, session: Session, store_root: Path | None):
        super().__init__()
        self.tracker = UsageTracker(session, store_root)
        self.cards: dict[Path, CardFrame] = {}
        self.busy = False

    def navigation_help(self):
        return 'j/k move · Enter expand · q sessions'

    def compose(self):
        yield Static('little caiman', id='brand')
        with VerticalScroll(id='body'):
            with Grid(id='summary-grid', classes='little-grid'):
                yield CardFrame(SessionSummaryCard(self.tracker))
            yield Static('Reading transcript…', id='little-status', markup=False)
            yield Grid(id='documents', classes='little-grid')
        yield Static(ABSENCE_NOTICE, id='notice')
        yield self.navigation_hint()

    async def on_mount(self):
        self.query_one('#session-summary', Button).focus()
        await self.refresh_usage()
        self.set_interval(POLL_SECONDS, self.refresh_usage)

    async def refresh_usage(self):
        if self.busy:
            return
        self.busy = True
        try:
            changed = await asyncio.to_thread(self.tracker.poll)
            if changed:
                await self.show_documents()
            self.query_one('#little-status', Static).update(
                '' if self.tracker.documents else 'No managed documents touched yet.')
            self.query_one('#little-status', Static).display = not self.tracker.documents
            # Relative times and on-disk state change even when the transcript does not.
            self.resize_cards()
        finally:
            self.busy = False

    async def show_documents(self):
        grid = self.query_one('#documents', Grid)
        ranked = [usage.ref.path for usage in self.tracker.ranked()]
        new = [key for key in ranked if key not in self.cards]
        for key in new:
            self.cards[key] = CardFrame(DocumentUsageCard(self.tracker, key, index=len(self.cards)))
        if new:
            await grid.mount_all([self.cards[key] for key in new])
        # Most recently touched first; moving keeps focus on the same card.
        for index, key in enumerate(ranked):
            if grid.children[index] is not self.cards[key]:
                grid.move_child(self.cards[key], before=index)

    def on_button_pressed(self, event):
        if isinstance(event.button, DocumentUsageCard):
            event.button.expanded = not event.button.expanded
            self.resize_cards()
        elif isinstance(event.button, SessionSummaryCard):
            self.exit('sessions')


def run_little_caiman(store_root: Path | None, session: Session | None = None, *, home: Path | None = None) -> int:
    """Pick a session, watch it, and return to the picker until the user backs out."""
    while True:
        chosen = session or SessionPickerApp(home=home).run()
        if chosen is None:
            return 0
        UsageApp(session=chosen, store_root=store_root).run()
        session = None
