"""Reviewed metadata edits reuse the registered blob, never a local source file."""

from copy import deepcopy
from dataclasses import dataclass

from caiman.configurations.service import ConfigurationService
from caiman.documents.ingest import GENERATED_FIELDS, validate_metadata, validate_document_text, digest
from caiman.documents.models import canonical_json, current_schema
from caiman.storage.store import StoreError, document_ref


@dataclass(frozen=True)
class PreparedDocumentEdit:
    manifest: dict
    digest: str


class DocumentEditService:
    def __init__(self, store, *, pods=()):
        self.store = store
        self.documents = ConfigurationService(store)

    def original(self, selection):
        _, manifest = self.documents._document(
            {'digest': selection['digest'], 'pod': selection['pod']}, pinned=True)
        if manifest != selection['manifest']:
            raise StoreError('The selected document does not match its stored snapshot')
        if selection.get('ref') != document_ref(manifest).as_posix():
            raise StoreError('The selected document ref does not match its identity')
        return manifest

    def prepare(self, selection, draft):
        original = self.original(selection)
        if not isinstance(draft, dict):
            raise StoreError('Expected a document mapping')
        protected = (GENERATED_FIELDS - {'schema'})
        if any(draft.get(key) != original.get(key) for key in protected):
            raise StoreError('Stored file, registration details are read-only')
        if draft.get('schema') not in {original['schema'], current_schema('document')}:
            raise StoreError('Unsupported document schema')
        metadata = {key: value for key, value in draft.items() if key not in GENERATED_FIELDS}
        validated = validate_metadata(metadata)
        content = self.store.read_blob(selection['pod'], 'sha256:' + original['files'][0]['sha256'])
        validate_document_text(content.decode('utf-8'), validated)
        manifest = deepcopy(original)
        for key in set(manifest) - GENERATED_FIELDS:
            manifest.pop(key)
        manifest.update(validated)
        if manifest != original:
            manifest['schema'] = current_schema('document')
        return PreparedDocumentEdit(manifest, selection["digest"] if manifest == original else digest(canonical_json(manifest)))

    def register(self, selection, prepared):
        verified = self.prepare(selection, prepared.manifest)
        if verified != prepared:
            raise StoreError('The draft changed after review; review again')
        if prepared.digest == selection['digest'] and prepared.manifest == selection['manifest']:
            return deepcopy(selection)
        directory = self.store.pod_path(selection['pod']) / 'refs' / 'documents'
        old_ref = directory / document_ref(selection['manifest'])
        if self.documents._read_ref(old_ref) != selection['digest']:
            raise StoreError('This document changed since opening; reopen it before saving')
        target = directory / document_ref(prepared.manifest)
        if target != old_ref and (target.exists() or target.is_symlink()):
            raise StoreError('A document already uses this name and version; choose another label')
        self.store._write_object(selection['pod'], 'manifests', prepared.digest, canonical_json(prepared.manifest))
        self.store._atomic_write(target, (prepared.digest + '\n').encode(), immutable=False)
        return {'manifest': deepcopy(prepared.manifest), 'digest': prepared.digest,
                'pod': selection['pod'], 'pod_name': self.store.pod_name(selection['pod']), 'ref': document_ref(prepared.manifest).as_posix()}
