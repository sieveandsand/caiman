"""Dashboard access to existing configuration operations."""

import asyncio
from pathlib import Path

from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from caiman.documents.cards import CollectionCard, CollectionFrame, DocumentCard, document_name
from caiman.documents.collections import CollectionService
from caiman.ui.cards import CARD_CSS, AddTile, CardFrame, resize_card_grid
from caiman.configurations.service import ConfigurationService
from caiman.ui.navigation import NavigationApp
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

    def __init__(self, *, kind, root, compartments=(), purpose='choose'):
        super().__init__()
        self.kind = kind
        self.purpose = purpose
        self.compartments = list(compartments)
        self.service = ConfigurationService(Store(root))
        self.records = []
        self.busy = False

    def compose(self):
        yield Static(f'caiman  /  {self.purpose} {self.kind}', id='brand')
        with VerticalScroll(id='body'):
            if self.kind == 'project':
                yield Label('Compartments to search (comma separated)')
                yield Static('Usually one per customer, such as oem-alpha. Only projects in these compartments are listed.', classes='hint')
                yield Input(', '.join(self.compartments), id='compartments')
                yield Button('Find projects', id='find')
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
            scopes = []
            if self.kind == 'project':
                scopes = [s.strip() for s in self.query_one('#compartments', Input).value.split(',') if s.strip()]
            self.records = await asyncio.to_thread(self.service.list_configs, self.kind, compartments=scopes)
            self.query_one('#choice', Select).set_options([
                (f"{record['name']} @ {record['version']} [{record['compartment']}; {record['digest'][7:19]}]", str(index))
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
            self.exit({'manifest': record['manifest'], 'digest': record['digest']})


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


class DocumentCatalogApp(ActionApp):
    TITLE = 'Caiman · Documents'
    CSS = ActionApp.CSS + CARD_CSS + '''
    #document-sections { height: auto; }
    .document-grid { height: auto; grid-size: 2; grid-columns: 1fr; grid-gutter: 1 1; }
    .add-grid { margin-top: 1; }
    .compartment-heading { height: auto; margin: 1 0; color: #7fdc4f; text-style: bold; }
    '''
    BINDINGS = [('pagedown', 'page_down', 'Scroll down'), ('pageup', 'page_up', 'Scroll up')]

    def navigation_help(self):
        return 'hjkl move · Enter open · Tab next control · PgUp/PgDn scroll · q back'

    def __init__(self, *, root, compartments):
        super().__init__()
        self.service = ConfigurationService(Store(root))
        self.collections = CollectionService(self.service.store)
        self.compartments = compartments
        self.busy = False

    def compose(self):
        yield Static('caiman  /  registered documents', id='brand')
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
            records = await asyncio.to_thread(self.service.list_documents, compartments=self.compartments)
            collections = await asyncio.to_thread(self.collections.list_collections, compartments=self.compartments)
            sections = self.query_one('#document-sections', Vertical)
            await sections.remove_children()
            groups = {}
            for record in records + collections:
                groups.setdefault(record['compartment'], []).append(record)
            index = 0
            for compartment in sorted(groups, key=lambda name: (name != 'public', name)):
                group = sorted(groups[compartment], key=lambda record: (document_name(record['manifest']), record['digest']))
                title = 'Public' if compartment == 'public' else compartment
                count = sum('documents' in r['manifest'] for r in group)
                summary = f'{title} · {len(group) - count} Documents' + (f' · {count} Collections' if count else '')
                await sections.mount(Static(summary,
                                            classes='compartment-heading', markup=False))
                cards = [(CollectionCard if 'documents' in record['manifest'] else DocumentCard)(record, index=index + offset)
                         for offset, record in enumerate(group)]
                index += len(cards)
                await sections.mount(Grid(*((CollectionFrame if isinstance(card, CollectionCard) else CardFrame)(card)
                                             for card in cards), classes='document-grid'))
            if not records and not collections:
                await sections.mount(Static('No documents registered in these compartments.', markup=False))
            add = AddTile('Add document', id='add-document')
            await sections.mount(Grid(CardFrame(add), CollectionFrame(AddTile('Add collection', id='add-collection')),
                                      classes='document-grid add-grid'))
            self.resize_cards(self.size.width)
            self.query_one('#status', Static).update(f'{len(records)} accessible registered documents · {len(collections)} collections.')
        except (OSError, ValueError) as error:
            self.query_one('#status', Static).update(str(error))
        finally:
            self.busy = False

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
            self.exit('add-collection')
        elif event.button.id == 'add-document':
            self.exit('add')
        elif event.button.id == 'refresh':
            await self.refresh_catalog()
        elif event.button.id == 'close':
            self.exit(None)


def run_dashboard_action(action: str, root: Path, compartments) -> dict | None:
    """Run one dashboard action; return the project or board it registered.

    Boards and projects both open from their gallery straight into the guided
    form: every field is shown and editable, and nothing registers without review.
    A gallery's add card returns ``{'action': ...}`` for the workflow to run.
    """
    try:
        if action == 'documents':
            from caiman.documents.collection_tui import CollectionApp
            from caiman.documents.edit import edit_document
            while True:
                choice = DocumentCatalogApp(root=root, compartments=compartments).run()
                if choice == 'add':
                    return {'action': 'ingest'}
                if isinstance(choice, dict) and 'document' in choice:
                    try:
                        edit_document(root, choice['document'], compartments=compartments)
                    except (OSError, ValueError) as error:
                        ViewerApp(title='Document editor needs attention', content=str(error)).run()
                elif choice == 'add-collection' or isinstance(choice, dict) and 'collection' in choice:
                    CollectionApp(root=root, compartments=compartments,
                                  record=choice['collection'] if isinstance(choice, dict) else None).run()
                else:
                    return None
        if action == 'show-board':
            from caiman.boards.edit import run_board_gallery
            return run_board_gallery(root)
        if action == 'show-project':
            from caiman.configurations.project_edit import run_project_gallery
            return run_project_gallery(root, compartments)
        raise ValueError('Unknown dashboard action')
    except (OSError, ValueError) as error:
        ViewerApp(title='Action needs attention', content=str(error)).run()
    return None
