"""Read-only browsing of complete saved document manifests."""

import asyncio
import json

from textual.containers import Vertical
from textual.widgets import Collapsible, Label, Static, TextArea

from caiman.documents.cards import document_name
from caiman.documents.revisions import DocumentRevisions
from caiman.storage.store import Store


class ManifestRevision(Collapsible):
    def __init__(self, record, number, *, current=False):
        manifest = record['manifest']
        status = ' · Current' if current else ''
        if manifest['previous'] is None:
            status += ' · Original'
        children = []
        for key, label in (
            ('name', 'Document Name'), ('version', 'Version'),
            ('description', 'Description'), ('doc_type', 'Document Type'),
            ('issuer', 'Issuer'), ('part', 'Part'), ('program', 'Program'),
            ('silicon_revisions', 'Silicon Revisions'),
            ('source', 'Original Source'), ('converter', 'Converter'),
            ('files', 'Stored File'),
        ):
            value = manifest.get(key)
            if value is None:
                continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, indent=2, ensure_ascii=False)
            children.extend((Label(label, classes='field-label'), Static(str(value), markup=False)))
        children.extend((
            Label('Manifest Digest', classes='field-label'),
            Static(record['digest'], markup=False),
            Label('Raw Manifest JSON', classes='field-label'),
            TextArea(json.dumps(manifest, indent=2, ensure_ascii=False),
                     read_only=True, soft_wrap=True),
        ))
        super().__init__(*children, title=f'Revision {number}{status} · {document_name(manifest)}',
                         collapsed=True, id=f'manifest-revision-{number}')


class MetadataHistory(Vertical):
    DEFAULT_CSS = '''
    MetadataHistory { height: auto; }
    MetadataHistory .history-revisions { height: auto; }
    MetadataHistory TextArea { height: 14; }
    MetadataHistory CollapsibleTitle:focus {
        color: #eef3e6; background: #000000; text-style: bold reverse;
    }
    '''

    def __init__(self, root, selection):
        super().__init__()
        self.root = root
        self.pod = selection['pod']
        self.document = selection['manifest']['document_id']
        self.loaded = False

    def compose(self):
        with Collapsible(title='Metadata History', collapsed=True, id='metadata-history'):
            yield Static('Saved revisions, newest first. Viewing history does not change your draft.')
            yield Static('Expand to load saved revisions.', id='history-status', markup=False)
            yield Vertical(classes='history-revisions')

    async def on_collapsible_expanded(self, event: Collapsible.Expanded):
        if event.collapsible.id != 'metadata-history' or self.loaded:
            return
        event.stop()
        self.loaded = True
        status = self.query_one('#history-status', Static)
        status.update('Loading saved revisions…')
        try:
            records = await asyncio.to_thread(
                DocumentRevisions(Store(self.root)).history, self.pod, self.document)
        except (OSError, ValueError) as error:
            status.update(f'Unable to load metadata history: {error}\nCollapse and expand to retry.')
            self.loaded = False
            return
        await self.query_one('.history-revisions', Vertical).mount(*(
            ManifestRevision(record, len(records) - index, current=index == 0)
            for index, record in enumerate(records)
        ))
        status.update('No earlier revisions.' if len(records) == 1 else f'{len(records)} saved revisions.')
