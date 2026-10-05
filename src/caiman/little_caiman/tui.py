"""Little caiman: a narrow, one-column sidecar beside a Claude Code or Codex session.

The picker lists recent sessions that Caiman's start hook registered; the usage
view tails the chosen transcript and shows which managed documents were read,
searched, or edited, and whether the bytes on disk still match the store.
Nothing here writes a file.
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
                                          document_label, loaded_context, loaded_contents,
                                          list_sessions)
from caiman.ui.cards import CARD_CSS, CardFrame, OverviewCard
from caiman.ui.navigation import NavigationApp
from caiman.ui.heading import card_heading
from caiman.ui.theme import TERMINAL_CSS, apply_theme

POLL_SECONDS = 2
SECTIONS_SHOWN = 4
DOCUMENTS_SHOWN = 6
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
    """The card hierarchy: styled headings, then summary, then items, blank-line separated."""

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
        self.text.append(card_heading(value, self.available, secondary=color == '#7fdc4f'))
        self.text.append('\n')

    def gap(self):
        self.text.append('\n')

    def divider(self, label, style):
        """`── LABEL ──────`: a section break that survives 16-color terminals."""
        head = f'── {label.upper()} '
        self.text.append(head + '─' * max(0, self.available - len(head)) + '\n', style=style)

    def finish(self, card):
        self.text.rstrip()
        card.label = self.text
        height = len(self.text.plain.splitlines()) + 2
        card.styles.height = height
        return height


def context_facts(card: CardText, session: Session) -> None:
    """The loaded board or project, or a plain statement that there is none."""
    state = loaded_context(session)
    if state is None:
        card.line('No context loaded', '#8d9982')
        return
    card.facts([f"{str(state.get('kind', '')).title()} {state.get('name')} @ {state.get('version')}",
                f"Revision {state.get('revision')}", f"{state.get('documents', 0)} Installed"],
               '#dfe6d3')


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
        context_facts(card, session)
        if session.title:
            card.gap()
            card.line(session.title, '#dfe6d3')
        return card.finish(self)


class SessionHeader(Static):
    """The watched session as plain text above the cards, not a card itself."""

    def __init__(self, tracker: UsageTracker):
        super().__init__('', id='session-summary')
        self.tracker = tracker

    def format_header(self, width):
        tracker, session = self.tracker, self.tracker.session
        usages = tracker.documents.values()
        card = CardText(width)
        name = session.cwd.name if session.cwd and session.cwd.name else session.session_id[:8]
        card.line(name, 'bold #eef3e6')
        card.line(HARNESS_NAMES[session.harness], '#aab69c')
        modified = sum(tracker.integrity(usage.ref).state == 'modified' for usage in usages)
        card.facts([f'{len(tracker.documents)} Docs', f'{sum(u.reads for u in usages)} Reads',
                    f'{sum(u.searches for u in usages)} Searches', f'{sum(u.edits for u in usages)} Edits'],
                   '#aab69c')
        details = []
        if tracker.tree_searches:
            details.append((f'{tracker.tree_searches} searches across all documents', '#dfe6d3'))
        if modified:
            details.append((f'{modified} modified on disk', '#e69a89'))
        if not tracker.has_workspace:
            details.append(('Only direct store reads can appear', '#8d9982'))
        for value, style in details:
            card.line(value, style)
        card.text.rstrip()
        self.update(card.text)


class LoadedContextCard(OverviewCard):
    """What `caiman session load` installed; Enter shows every document."""

    def __init__(self, session: Session):
        super().__init__('', id='loaded-context', classes='dashboard-tile card-face')
        self.session = session
        self.expanded = False

    def format_card(self, width):
        contents = loaded_contents(self.session)
        card = CardText(width)
        if contents is None:
            card.heading('No context loaded', 'No context loaded', '#eef3e6')
            card.gap()
            card.line('Ask the agent to load a board or project.', '#8d9982')
            return card.finish(self)
        title = f"{contents.get('name')} @ {contents.get('version')}"
        card.heading(title, title, '#eef3e6')
        card.gap()
        kind = str(contents.get('kind', '')).title()
        card.heading(kind, kind, '#7fdc4f')
        card.gap()
        boards = [board for board in contents.get('boards') or [] if isinstance(board, dict)]
        documents = [entry.get('path', '') for entry in contents.get('documents') or [] if isinstance(entry, dict)]
        card.line(f"Revision {contents.get('revision')}", 'bold #aab69c')
        # Each category gets a labeled divider; each entry is its name with its
        # location indented beneath, and a blank line between entries.
        if boards:
            card.gap()
            card.divider(f'Boards · {len(boards)}', 'bold #7fdc4f')
        for board in boards:
            card.gap()
            card.line(f"{board.get('name')} @ {board.get('version')}", '#dfe6d3')
            card.line(f"  pod {board.get('pod')}", '#8d9982')
        if documents:
            card.gap()
            card.divider(f'Documents · {len(documents)}', 'bold #7fdc4f')
        shown = documents if self.expanded else documents[:DOCUMENTS_SHOWN]
        for path in shown:
            scope, document = document_label(path)
            card.gap()
            card.line(document, '#dfe6d3')
            if scope:
                card.line(f'  {scope}', '#8d9982')
        if len(documents) > len(shown):
            card.gap()
            card.line(f'+{len(documents) - len(shown)} more · Enter to show', '#8d9982')
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
    #session-summary { height: auto; padding: 0 1; margin-bottom: 1; }
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
        for header in self.query(SessionHeader):
            header.format_header(width)

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
                      'No Caiman sessions yet. Sessions appear once the Caiman start hook runs in them.')
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
            yield SessionHeader(self.tracker)
            with Grid(id='context-grid', classes='little-grid'):
                yield CardFrame(LoadedContextCard(self.tracker.session))
            yield Static('Reading transcript…', id='little-status', markup=False)
            yield Grid(id='documents', classes='little-grid')
        yield Static(ABSENCE_NOTICE, id='notice')
        yield self.navigation_hint()

    async def on_mount(self):
        self.query_one('#loaded-context', Button).focus()
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
        if isinstance(event.button, (DocumentUsageCard, LoadedContextCard)):
            event.button.expanded = not event.button.expanded
            self.resize_cards()


def run_little_caiman(store_root: Path | None, session: Session | None = None, *, home: Path | None = None) -> int:
    """Pick a session, watch it, and return to the picker until the user backs out."""
    while True:
        chosen = session or SessionPickerApp(home=home).run()
        if chosen is None:
            return 0
        UsageApp(session=chosen, store_root=store_root).run()
        session = None
