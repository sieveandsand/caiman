"""Document metadata in the shared board/project guided editor layout."""

from copy import deepcopy
import json

from rich.text import Text
from textual.containers import Grid, Horizontal, VerticalScroll
from textual.widgets import Button, Collapsible, Input, Label, Select, Static, TextArea

from caiman.documents.cards import document_name
from caiman.ui.editor import CardRow, EditorFormApp, comma_list
from caiman.ui.theme import apply_theme


class DetailCard(CardRow):
    """A fixed metadata group, with no invented repeated records or add action."""
    kind = 'detail'

    def __init__(self, title, data, fields, *, key, hint):
        self.title = title
        self.fields = fields
        self.key = key
        self.hint = hint
        self.first_field = fields[0][0]
        super().__init__(data)
        self.id = 'detail-' + key

    def display_value(self, key):
        value = self.data.get(key, '')
        return ', '.join(value) if isinstance(value, list) else str(value)

    def editor_fields(self):
        for key, label in self.fields:
            yield Label(label, classes='field-label')
            yield Input(self.display_value(key), classes=f'field field-{key}')
        if self.key == 'converter':
            yield Label('Conversion Location', classes='field-label')
            yield Select([('Unknown', 'unknown'), ('Local', 'local'), ('Hosted', 'hosted')],
                         value={True: 'hosted', False: 'local'}.get(self.data.get('hosted'), 'unknown'),
                         allow_blank=False, classes='field-hosted')

    def collect(self):
        data = deepcopy(self.data)
        for key, _ in self.fields:
            value = self.query_one('.field-' + key, Input).value
            if value == self.display_value(key):
                continue
            if not value:
                data.pop(key, None)
            elif key == 'silicon_revisions':
                data[key] = comma_list(value)
            elif key == 'pages' and value.isdecimal():
                data[key] = int(value)
            else:
                data[key] = value
        if self.key == 'converter':
            hosted = self.query_one('.field-hosted', Select).value
            if hosted == 'unknown':
                data.pop('hosted', None)
            else:
                data['hosted'] = hosted == 'hosted'
        return data

    def summary_data(self):
        return self.collect()

    def summary(self, data):
        label = Text()
        self.heading(label, self.title)
        values = []
        if self.key == 'applicability':
            if data.get('issuer'):
                values.append(data['issuer'])
            if data.get('part') or data.get('program'):
                values.append(data.get('part') or data['program'])
        elif self.key == 'requirements':
            values.append('ID validation enabled' if data.get('pattern') else 'Optional ID validation')
        elif self.key == 'source':
            values.append(f"{data['pages']} pages" if data.get('pages') else 'Page count unknown')
            if data.get('sha256'):
                values.append('Source checksum supplied')
        else:
            values.extend(str(data[key]) for key in ('name', 'version') if data.get(key))
            if 'hosted' in data:
                values.append('Hosted' if data['hosted'] else 'Local')
        label.append('\n\n' + (' · '.join(values) or self.hint), style='#aab69c')
        return label


class DocumentFormApp(EditorFormApp):
    TITLE = 'Caiman · Edit document'

    def __init__(self, *, original, draft=None, message='', selection=None):
        super().__init__()
        apply_theme(self)
        self.original = deepcopy(original)
        self.draft = deepcopy(original if draft is None else draft)
        self.selection = deepcopy(selection)
        self.message = message

    def field(self, key, label, value):
        yield Label(label, classes='field-label')
        yield Input(value, id='document-' + key)

    def compose(self):
        yield Static('caiman  /  edit document', id='brand')
        with VerticalScroll(id='body'):
            yield from self.field('name', 'Document Name', document_name(self.draft))
            yield from self.field('version', 'Version', self.draft['version'])
            yield from self.field('description', 'Description', self.draft.get('description', ''))
            yield Label('Pod', classes='field-label')
            yield Static((self.selection or {}).get('pod_name', (self.selection or {}).get('pod', 'public')), id='document-pod', markup=False)
            with Collapsible(title='Document Details', collapsed=False):
                with Grid(classes='card-grid'):
                    yield DetailCard('Applicability', {key: self.draft[key] for key in
                        ('issuer', 'part', 'program', 'silicon_revisions') if key in self.draft},
                        [('issuer', 'Issuer'), ('part', 'Part'), ('program', 'Program'),
                         ('silicon_revisions', 'Silicon Revisions (comma separated)')],
                        key='applicability', hint='Issuer and hardware or program')
                    yield DetailCard('Requirement IDs', self.draft.get('requirements', {}),
                                     [('pattern', 'Requirement ID Pattern')], key='requirements', hint='Optional')
            with Collapsible(title='Provenance', collapsed=False):
                with Grid(classes='card-grid'):
                    yield DetailCard('Original Source', self.draft.get('source', {}),
                                     [('sha256', 'Original Source SHA-256'), ('pages', 'Original Page Count')],
                                     key='source', hint='Unknown')
                    yield DetailCard('Converter', self.draft.get('converter', {}),
                                     [('name', 'Converter Name'), ('version', 'Converter Version')],
                                     key='converter', hint='Unknown')
            with Collapsible(title='Stored File', collapsed=True):
                entry = self.original['files'][0]
                yield Static(f"{self.original.get('original_filename', entry['path'])}\n"
                             f"{entry['size']:,} bytes · Read Only\n\nSHA-256: {entry['sha256']}", markup=False)
            with Collapsible(title='Registration Details', collapsed=True):
                yield TextArea(json.dumps(self.selection or self.original, indent=2, ensure_ascii=False),
                               read_only=True, soft_wrap=True)
        yield Static(self.message, id='form-error', markup=False)
        with Horizontal(id='navigation'):
            yield Button('Review changes', id='review-changes', variant='primary')
            yield Button('Back to documents', id='cancel')
        yield self.navigation_hint()

    def collect(self):
        result = deepcopy(self.draft)
        for key in ('name', 'version', 'description'):
            value = self.query_one('#document-' + key, Input).value
            displayed = document_name(self.draft) if key == 'name' else self.draft.get(key, '')
            if value == displayed:
                continue
            if key == 'description' and not value:
                result.pop(key, None)
            else:
                result[key] = value
        for card in self.query(DetailCard):
            group = card.collect()
            if card.key == 'applicability':
                for key, _ in card.fields:
                    if key in group:
                        result[key] = group[key]
                    else:
                        result.pop(key, None)
            elif group:
                result[card.key] = group
            elif group != self.draft.get(card.key, {}):
                result.pop(card.key, None)
        return result

    def on_button_pressed(self, event):
        event.stop()
        button = event.button
        if button.id == 'cancel':
            self.exit(None)
        elif button.id == 'review-changes':
            self.exit(('review', self.collect()))
        elif button.has_class('card-summary') or button.has_class('collapse-card'):
            self.toggle_card(button)

    def on_descendant_focus(self, event):
        super().on_descendant_focus(event)
        # The shared editor frame owns the reserved shadow row too.
        if event.widget.has_class('card-summary'):
            card = next(node for node in event.widget.ancestors if isinstance(node, DetailCard))
            self.call_after_refresh(card.scroll_visible, animate=False)
