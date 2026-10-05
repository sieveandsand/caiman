"""Shared searchable, multi-select attachment dialog."""

import asyncio

from rich.text import Text
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, SelectionList, Static


class RecordPicker(ModalScreen):
    noun = 'records'
    container_id = 'record-picker'
    list_id = 'picker-records'
    search_placeholder = 'Search'

    BINDINGS = [Binding('escape', 'cancel', 'Cancel')]
    CSS = '''
    RecordPicker { align: center middle; background: #000000 80%; }
    .record-picker { width: 90%; max-width: 110; height: 90%; border: solid #7fdc4f; background: #000000; padding: 1 2; }
    #picker-title, #picker-status, #picker-count, #picker-help { height: auto; }
    #picker-title { color: #eef3e6; text-style: bold; margin-bottom: 1; }
    #picker-search { margin-bottom: 1; }
    .picker-records { height: 1fr; border: solid #33422e; }
    .picker-records:focus { border: double #7fdc4f; }
    .picker-records > .option-list--option-highlighted { text-style: bold reverse; }
    #picker-detail { height: auto; max-height: 6; overflow-y: auto; margin-top: 1; }
    #picker-actions { height: auto; margin-top: 1; }
    #picker-actions Button { width: auto; border: solid #33422e; }
    #picker-actions Button:focus { border: double #7fdc4f; }
    '''

    def __init__(self, *, service, attached=(), candidates=None, empty_message=None, owner=None):
        super().__init__()
        self.owner = owner
        self.service = service
        self.attached = attached
        self.candidates = candidates
        self.empty_message = empty_message or f'No unattached {self.noun}.'
        self.records = []
        self.chosen = set()
        self.visible_indices = set()

    def compose(self):
        with Vertical(id=self.container_id, classes='record-picker'):
            yield Static(f'Choose {self.noun}', id='picker-title')
            yield Input(placeholder=self.search_placeholder, id='picker-search')
            yield SelectionList(id=self.list_id, classes='picker-records')
            yield Static('', id='picker-detail', markup=False)
            yield Static(f'Loading {self.noun}…', id='picker-status', markup=False)
            yield Static('0 selected', id='picker-count')
            yield Static('↑/↓ move · Space select · Tab next · Esc cancel', id='picker-help')
            with Horizontal(id='picker-actions'):
                yield Button('Attach selected', id='picker-attach', variant='primary', disabled=True)
                yield Button('Cancel', id='picker-cancel')

    async def on_mount(self):
        try:
            self.records = await asyncio.to_thread(self.load_records)
            self.records.sort(key=self.record_sort_key)
            self.filter_records()
        except (OSError, ValueError) as error:
            self.query_one('#picker-status', Static).update(str(error))
        self.query_one('#picker-search').focus()

    def record_sort_key(self, record):
        return self.record_label(record).casefold()

    def on_input_changed(self, event):
        if event.input.id == 'picker-search':
            self.filter_records()

    def filter_records(self):
        query = self.query_one('#picker-search', Input).value.casefold().split()
        listing = self.query_one(SelectionList)
        # Rebuilding the filtered list must not deselect hidden choices.
        with listing.prevent(SelectionList.SelectedChanged):
            listing.clear_options()
            self.visible_indices = set()
            for index, record in enumerate(self.records):
                searchable = (self.record_label(record) + ' ' + self.record_details(record)).casefold()
                if all(term in searchable for term in query):
                    self.visible_indices.add(index)
                    listing.add_option((self.option_label(index), index, index in self.chosen))
            if listing.option_count:
                listing.highlighted = 0
        status = (f'{len(self.visible_indices)} available {self.noun}' if self.visible_indices else
                  'No matches. Try another search.' if self.records else
                  self.empty_message)
        self.query_one('#picker-status', Static).update(status)
        if not self.visible_indices:
            self.query_one('#picker-detail', Static).update('')
        self.update_count()

    def option_label(self, index):
        marker = '✓ Selected · ' if index in self.chosen else ''
        return Text(marker + self.record_label(self.records[index]))

    def on_selection_list_selection_highlighted(self, event):
        record = self.records[event.selection.value]
        self.query_one('#picker-detail', Static).update(self.record_label(record) + '\n' + self.record_details(record))

    def on_selection_list_selected_changed(self, event):
        self.chosen.difference_update(self.visible_indices)
        self.chosen.update(event.selection_list.selected)
        for index in range(event.selection_list.option_count):
            option = event.selection_list.get_option_at_index(index)
            event.selection_list.replace_option_prompt_at_index(index, self.option_label(option.value))
        self.update_count()

    def update_count(self):
        hidden = len(self.chosen - self.visible_indices)
        self.query_one('#picker-count', Static).update(
            f'{len(self.chosen)} selected' + (f' · {hidden} hidden by search' if hidden else ''))
        self.query_one('#picker-attach', Button).disabled = not self.chosen

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == 'picker-cancel':
            self.action_cancel()
        elif event.button.id == 'picker-attach' and self.chosen:
            self.dismiss([self.records[i] for i in sorted(self.chosen)])

    def action_cancel(self):
        self.dismiss(None)
