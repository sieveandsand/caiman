"""Dashboard access to existing configuration operations."""

import asyncio
from pathlib import Path

from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static, TextArea, Tabs

from caiman.documents.cards import CollectionCard, CollectionFrame, DocumentCard, document_name
from caiman.documents.collections import CollectionService
from caiman.ui.cards import CARD_CSS, AddTile, CardFrame, resize_card_grid
from caiman.configurations.service import ConfigurationService
from caiman.ui.navigation import NavigationApp
from caiman.ui.pod_tabs import POD_BINDINGS, POD_HELP, PodTabsMixin
from caiman.storage.store import Store
from caiman.ui.theme import TERMINAL_CSS, apply_theme


class ActionApp(NavigationApp):
    CSS = TERMINAL_CSS + '\nButton { width: auto; }\n#content { height: 1fr; }\n'

    def __init__(self):
        super().__init__()
        apply_theme(self)

    def action_cancel(self):
        self.exit(None)


class ChooseApp(ActionApp):
    """Pick the board or project an action applies to; nothing is preselected."""

    TITLE = 'Caiman · Choose configuration'

    def __init__(self, *, kind, root, pods=(), purpose='choose'):
        super().__init__()
        self.kind = kind
        self.purpose = purpose
        self.pods = list(pods)
        self.service = ConfigurationService(Store(root))
        self.records = []
        self.busy = False

    def compose(self):
        yield Static(f'caiman  /  {self.purpose} {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            yield Label(f'{self.kind.capitalize()} version')
            yield Select([], prompt=f'Choose a {self.kind}', id='choice')
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Continue', id='continue', variant='primary')
            yield Button('Cancel', id='cancel')

    async def on_mount(self):
        await self.refresh_catalog()

    async def refresh_catalog(self):
        if self.busy:
            return
        self.busy = True
        try:
            scopes = None
            self.records = await asyncio.to_thread(self.service.list_configs, self.kind, pods=scopes)
            self.query_one('#choice', Select).set_options([
                (f"{record['name']} @ {record['version']} [{record['pod']}; {record['digest'][7:19]}]", str(index))
                for index, record in enumerate(self.records)])
            self.query_one('#status', Static).update(f'{len(self.records)} {self.kind} versions available.')
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False

    async def on_button_pressed(self, event):
        if event.button.id == 'cancel':
            self.exit(None)
        elif event.button.id == 'find':
            await self.refresh_catalog()
        elif event.button.id == 'continue' and not self.busy:
            choice = self.query_one('#choice', Select).value
            if not isinstance(choice, str):
                self.query_one('#status', Static).update(f'Choose a {self.kind} first.')
                return
            record = self.records[int(choice)]
            self.exit(record)


class ViewerApp(ActionApp):
    TITLE = 'Caiman · Inspect'

    def __init__(self, *, title, content):
        super().__init__()
        self.heading = title
        self.content = content

    def compose(self):
        yield Static('caiman  /  ' + self.heading.lower(), id='brand', markup=False)
        with VerticalScroll(id='body'):
            yield TextArea(self.content, read_only=True, id='content', soft_wrap=True)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Back', id='close', variant='primary')

    def on_button_pressed(self, event):
        self.exit(None)


class DocumentCatalogApp(PodTabsMixin, ActionApp):
    TITLE = 'Caiman · Documents'
    CSS = ActionApp.CSS + CARD_CSS + '''
    #document-sections { height: auto; }
    .document-grid { height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }
    .add-grid { margin-top: 1; }
    .pod-heading { height: auto; margin: 1 0; color: #7fdc4f; text-style: bold; }
    '''
    BINDINGS = POD_BINDINGS + [('pagedown', 'page_down', 'Scroll down'), ('pageup', 'page_up', 'Scroll up')]

    def navigation_help(self):
        return f'hjkl move · Enter open · {POD_HELP} · PgUp/PgDn scroll · q back'

    def __init__(self, *, root, pods=(), pod=None):
        super().__init__()
        self.service = ConfigurationService(Store(root))
        self.collections = CollectionService(self.service.store)
        self.pods = pods
        self.active_pod = pod or self.service.store.pods.default
        self.records = []
        self.collection_records = []
        self.tab_pods = {}
        self.render_lock = asyncio.Lock()
        self.busy = False

    def compose(self):
        yield Static('caiman  /  documents', id='brand')
        yield Tabs(id='pod-tabs')
        with VerticalScroll(id='body'):
            yield Vertical(id='document-sections')
        yield Static('', id='status', markup=False)
        yield self.navigation_hint()
        with Horizontal(id='navigation'):
            yield Button('Back to dashboard', id='close', variant='primary')
            yield Button('Refresh catalog', id='refresh')

    async def on_mount(self):
        await self.refresh_catalog()
        cards = self.query('.card-face')
        if cards:
            self.call_after_refresh(cards.first().focus)

    async def refresh_catalog(self):
        if self.busy:
            return
        self.busy = True
        try:
            self.records = await asyncio.to_thread(self.service.list_documents, pods=None)
            self.collection_records = await asyncio.to_thread(self.collections.list_collections, pods=None)
            available = {r['id']: r['name'] for r in self.service.store.pods.list()}
            for record in self.records + self.collection_records:
                available.setdefault(record['pod'], record.get('pod_name', record['pod']))
            await self.update_pod_tabs(available)
            await self.render_pod()
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False

    async def render_pod(self):
        async with self.render_lock:
            group = [r for r in self.records + self.collection_records if r['pod'] == self.active_pod]
            group.sort(key=lambda r: (document_name(r['manifest']), r['digest']))
            sections = self.query_one('#document-sections', Vertical)
            await sections.remove_children()
            cards = [(CollectionCard if 'documents' in r['manifest'] else DocumentCard)(r, index=i)
                     for i, r in enumerate(group)]
            if cards:
                await sections.mount(Grid(*((CollectionFrame if isinstance(c, CollectionCard) else CardFrame)(c)
                                             for c in cards), classes='document-grid'))
            else:
                await sections.mount(Static('No documents in this pod yet.', markup=False))
            await sections.mount(Grid(CardFrame(AddTile('Add document', id='add-document')),
                                      CollectionFrame(AddTile('Add collection', id='add-collection')),
                                      classes='document-grid add-grid'))
            self.resize_cards(self.size.width)
            count = sum('documents' in r['manifest'] for r in group)
            self.query_one('#status', Static).update(f'{len(group) - count} documents · {count} collections')
            self.query_one('#body', VerticalScroll).scroll_home(animate=False)

    def on_resize(self, event):
        self.resize_cards(event.size.width)

    def resize_cards(self, terminal_width):
        columns = 2 if terminal_width >= 100 else 1
        width = max(16, (terminal_width - 6 - (columns - 1) - 2) // columns)
        for grid in self.query('.document-grid'):
            resize_card_grid(grid, width, columns)

    def action_page_down(self):
        self.query_one('#body', VerticalScroll).scroll_page_down(animate=False)

    def action_page_up(self):
        self.query_one('#body', VerticalScroll).scroll_page_up(animate=False)

    async def on_button_pressed(self, event):
        if isinstance(event.button, DocumentCard):
            self.exit({'document': event.button.record})
        elif isinstance(event.button, CollectionCard):
            self.exit({'collection': event.button.record})
        elif event.button.id == 'add-collection':
            self.exit({'action': 'add-collection', 'pod': self.active_pod})
        elif event.button.id == 'add-document':
            self.exit({'action': 'ingest', 'pod': self.active_pod})
        elif event.button.id == 'refresh':
            await self.refresh_catalog()
        elif event.button.id == 'close':
            self.exit(None)


def run_dashboard_action(action: str, root: Path, pods) -> dict | None:
    """Run one dashboard action; return the project or board it registered.

    Boards and projects both open from their gallery straight into the guided
    form: every field is shown and editable, and nothing registers without review.
    A gallery's add card returns ``{'action': ...}`` for the workflow to run.
    """
    try:
        if action == 'documents':
            from caiman.documents.collection_tui import CollectionApp
            from caiman.documents.edit import edit_document
            active_pod = None
            while True:
                choice = DocumentCatalogApp(root=root, pods=pods, pod=active_pod).run()
                if isinstance(choice, dict):
                    active_pod = choice.get('pod') or choice.get('document', choice.get('collection', {})).get('pod')
                if isinstance(choice, dict) and choice.get('action') == 'ingest':
                    return choice
                if choice == 'add':
                    return {'action': 'ingest'}
                if isinstance(choice, dict) and 'document' in choice:
                    try:
                        edit_document(root, choice['document'], pods=pods)
                    except (OSError, ValueError) as error:
                        ViewerApp(title='Document editor needs attention', content=str(error)).run()
                elif isinstance(choice, dict) and choice.get('action') == 'add-collection' or isinstance(choice, dict) and 'collection' in choice:
                    CollectionApp(root=root, pods=pods,
                                  record=choice.get('collection') if isinstance(choice, dict) else None, pod=active_pod).run()
                else:
                    return None
        if action == 'show-board':
            from caiman.boards.edit import run_board_gallery
            return run_board_gallery(root)
        if action == 'show-project':
            from caiman.configurations.project_edit import run_project_gallery
            return run_project_gallery(root, pods)
        raise ValueError('Unknown dashboard action')
    except (OSError, ValueError) as error:
        ViewerApp(title='Action needs attention', content=str(error)).run()
    return None
