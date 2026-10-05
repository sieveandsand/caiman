"""Choose documents and collection snapshots as fixed document attachments."""

import asyncio

from textual.widgets import Button, Static

from caiman.documents.cards import document_name
from caiman.documents.collections import CollectionService
from caiman.documents.models import is_schema
from caiman.ui.picker import RecordPicker


def document_pin(record):
    manifest = record['manifest']
    if is_schema('collection', manifest.get('schema')):
        return dict(pod=record['pod'], collection=manifest['id'], digest=record['digest'])
    if 'document_id' in manifest:
        return {'pod': record['pod'], 'document': manifest['document_id'],
                'blob': 'sha256:' + manifest['files'][0]['sha256']}
    return {'pod': record['pod'], 'digest': record['digest']}


def document_label(record):
    manifest = record['manifest']
    return f"{document_name(manifest)} · {manifest['version']} · {record.get('pod_name', record['pod'])}"


class DocumentPicker(RecordPicker):
    noun = 'documents and collections'
    container_id = 'document-picker'
    list_id = 'picker-documents'
    search_placeholder = 'Search documents, collections, or pod'

    @staticmethod
    def is_collection(record):
        return is_schema('collection', record['manifest'].get('schema'))

    @staticmethod
    def record_label(record):
        if DocumentPicker.is_collection(record):
            manifest = record['manifest']
            count = len(manifest['documents'])
            return (f"Collection · {manifest['name']} · {count} "
                    f"{'document' if count == 1 else 'documents'} · {record.get('pod_name', record['pod'])}")
        return 'Document · ' + document_label(record)

    def __init__(self, *, allow_collections=True, **kwargs):
        self.allow_collections = allow_collections
        if not allow_collections:
            self.noun = 'documents'
            self.search_placeholder = 'Search documents or pod'
        available = 'documents or collections' if allow_collections else 'documents'
        kwargs.setdefault('empty_message', f'No {available} available. Add them from the Documents page first.')
        super().__init__(**kwargs)

    def record_details(self, record):
        manifest = record['manifest']
        if self.is_collection(record):
            return manifest.get('description', '')
        return ' · '.join(str(manifest[k]) for k in
                          ('issuer', 'part', 'program', 'doc_type', 'description') if manifest.get(k))

    def load_records(self):
        if self.service is None:
            raise ValueError('Document library is unavailable in this editor.')
        records = (self.service.list_documents() if self.candidates is None else
                   [self.service.document_record(pin) for pin in self.candidates])
        if self.owner is not None:
            allowed = self.service.store.pods.reference_pods(self.owner)
            records = [record for record in records if record['pod'] in allowed]
        existing = set()
        for pin in self.attached:
            if 'collection' in pin:
                continue
            try:
                record = self.service.document_record(pin)
                existing.add((record['pod'], record['digest']))
            except (OSError, ValueError):
                # Unresolved drafts stay in the editor for its review validation.
                continue
        available = {(r['pod'], r['digest']): r for r in records
                     if (r['pod'], r['digest']) not in existing}
        # Explicit candidate lists remain restricted to their declared documents.
        collections = (CollectionService(self.service.store).list_collections(
            pods=self.service.store.pods.reference_pods(self.owner or 'public'))
            if self.allow_collections and self.candidates is None else [])
        attached_collections = {(self.service.store.pods.resolve(pin['pod'])['id'], pin['collection'])
                                for pin in self.attached if 'collection' in pin}
        collections = [r for r in collections if (r['pod'], r['manifest']['id']) not in attached_collections]
        return [*available.values(), *collections]

    def selected_documents(self):
        """Resolve every selected member before returning any, preserving fixed bodies."""
        collections = CollectionService(self.service.store)
        seen = set()

        def identity(record):
            return tuple(sorted(document_pin(record).items()))

        for pin in self.attached:
            if 'collection' in pin:
                continue
            try:
                seen.add(identity(self.service.document_record(pin)))
            except (OSError, ValueError):
                # Keep invalid draft references for normal review validation.
                continue
        documents = []
        for index in sorted(self.chosen):
            record = self.records[index]
            if self.is_collection(record) and not self.allow_collections:
                raise ValueError('Collections can contain only individual documents.')
            self.service.store.pods.check_reference(self.owner or 'public', record['pod'])
            members = (collections.members(record) if self.is_collection(record) else
                       [self.service.document_record(document_pin(record), pinned=True)])
            for member in members:
                self.service.store.pods.check_reference(self.owner or 'public', member['pod'])
                key = identity(member)
                if key not in seen:
                    documents.append(member)
                    seen.add(key)
        return documents

    async def on_button_pressed(self, event):
        event.stop()
        event.prevent_default()
        if event.button.id == 'picker-cancel':
            self.action_cancel()
        elif event.button.id == 'picker-attach' and self.chosen:
            button = self.query_one('#picker-attach', Button)
            button.disabled = True
            try:
                documents = await asyncio.to_thread(self.selected_documents)
            except (OSError, ValueError) as error:
                self.query_one('#picker-status', Static).update(str(error))
                button.disabled = False
            else:
                self.dismiss(documents)
