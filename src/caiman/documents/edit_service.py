"""One reviewed save path for every document metadata field."""
from copy import deepcopy
from dataclasses import dataclass

from caiman.configurations.service import ConfigurationService
from caiman.documents.ingest import GENERATED_FIELDS, validate_metadata, digest
from caiman.documents.revisions import DocumentRevisions
from caiman.documents.usages import DocumentUsages, UsagePlan
from caiman.documents.models import canonical_json
from caiman.storage.store import StoreError, document_ref
from caiman.storage.transactions import publish


@dataclass(frozen=True)
class PreparedDocumentEdit:
    manifest: dict
    digest: str
    mode: str = 'unchanged'
    usages: UsagePlan | None = None
    refs: tuple = ()


class DocumentEditService:
    def __init__(self, store, *, pods=()):
        self.store = store
        self.documents = ConfigurationService(store)
        self.revisions = DocumentRevisions(store)

    def original(self, selection):
        record = self.documents.document_record({'document': selection['manifest']['document_id'],
            'blob': 'sha256:' + selection['manifest']['files'][0]['sha256'], 'pod': selection['pod']}, pinned=True)
        if record['manifest'] != selection['manifest'] or record['digest'] != selection['digest']:
            raise StoreError('The selected document changed since opening; reopen it before saving')
        if selection.get('ref') != document_ref(record['manifest']).as_posix():
            raise StoreError('The selected document ref does not match its identity')
        return record['manifest']

    def prepare(self, selection, draft):
        original = self.original(selection)
        if not isinstance(draft, dict):
            raise StoreError('Expected a document mapping')
        # previous is supplied by this service; accepted drafts include either
        # the opened manifest's previous or the newly prepared revision link.
        protected = GENERATED_FIELDS - {'previous'}
        if any(draft.get(key) != original.get(key) for key in protected):
            raise StoreError('Stored file and registration details are read-only; add a new document for changed content')
        if draft.get('previous') not in (original['previous'], selection['digest']):
            raise StoreError('Revision history is read-only')
        metadata = validate_metadata({key: value for key, value in draft.items() if key not in GENERATED_FIELDS})
        manifest = {key: deepcopy(value) for key, value in original.items() if key in GENERATED_FIELDS}
        manifest.update(metadata)
        if manifest == original:
            return PreparedDocumentEdit(manifest, selection['digest'])
        manifest['previous'] = selection['digest']
        value = digest(canonical_json(manifest))
        directory = self.store.pod_path(selection['pod']) / 'refs' / 'documents'
        old_ref, target = directory / selection['ref'], directory / document_ref(manifest)
        if not old_ref.exists() or self.documents._read_ref(old_ref) != selection['digest']:
            raise StoreError('This document changed since opening; reopen it before saving')
        if target != old_ref and (target.exists() or target.is_symlink()):
            raise StoreError('A document already uses this name and version; choose another label')
        head = self.revisions.ref(selection['pod'], manifest['document_id'])
        refs = [{'path': head.relative_to(self.store.root).as_posix(),
                 'before': selection['digest'] + '\n', 'after': value + '\n'},
                {'path': target.relative_to(self.store.root).as_posix(),
                 'before': selection['digest'] + '\n' if target == old_ref else None, 'after': value + '\n'}]
        if target != old_ref:
            refs.append({'path': old_ref.relative_to(self.store.root).as_posix(),
                         'before': selection['digest'] + '\n', 'after': None})
        return PreparedDocumentEdit(manifest, value, 'revision', DocumentUsages(self.store, selection).prepare(), tuple(refs))

    def register(self, selection, prepared):
        with self.store.locked():
            verified = self.prepare(selection, prepared.manifest)
            if verified != prepared:
                raise StoreError('The document or its usages changed after review; review again')
            if prepared.mode == 'unchanged':
                return deepcopy(selection)
            self.store._write_object(selection['pod'], 'manifests', prepared.digest, canonical_json(prepared.manifest))
            publish(self.store, list(prepared.refs))
            return self.documents.document_record({'pod': selection['pod'], 'digest': prepared.digest})
