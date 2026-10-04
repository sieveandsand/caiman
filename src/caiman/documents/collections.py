"""Named collections pin documents across locally available pods."""
from copy import deepcopy
import json
from uuid import uuid4

from caiman.configurations.service import ConfigurationService
from caiman.documents.ingest import digest, _text
from caiman.documents.models import canonical_json, current_schema, is_schema, valid_identifier
from caiman.storage.store import StoreError, _component, _hex
from caiman.storage.legacy import manifest_view


class CollectionService:
    def __init__(self, store):
        self.store = store
        self.documents = ConfigurationService(store)

    def _validate(self, data):
        if not isinstance(data, dict) or set(data) != {'schema', 'id', 'name', 'description', 'documents'}:
            raise StoreError('Invalid collection fields')
        if not is_schema('collection', data['schema']) or not valid_identifier(data['id']):
            raise StoreError('Invalid collection identity or schema')
        if not _text(data['name']) or not isinstance(data['description'], str):
            raise StoreError('Supply a collection name and description')
        if data['description'] and not _text(data['description']):
            raise StoreError('Description must not contain control characters')
        if not isinstance(data['documents'], list) or not data['documents']:
            raise StoreError('Choose at least one existing document')
        for pin in data['documents']:
            if not isinstance(pin, dict) or set(pin) not in ({'digest', 'pod'}, {'document', 'blob', 'pod'}) or not valid_identifier(pin['pod']):
                raise StoreError('Collection members must identify a document and fixed blob in a pod')
            if 'document' in pin and not valid_identifier(pin['document']):
                raise StoreError('Invalid document ID')
            _hex(pin.get('blob', pin.get('digest')))

    def prepare(self, data, *, pod=None, pods=None):
        if not isinstance(data, dict):
            raise StoreError('Expected a collection mapping')
        manifest = deepcopy(data)
        target = pod or manifest.pop('pod', None) or self.store.pods.default
        manifest.pop('pod', None)
        manifest.setdefault('schema', current_schema('collection'))
        manifest.setdefault('id', uuid4().hex)
        manifest.setdefault('description', '')
        self._validate(manifest)
        members = []
        for pin in manifest['documents']:
            selected, _ = self.documents._document(pin, pinned=True)
            members.append(selected)
        manifest['documents'] = [json.loads(value) for value in sorted({canonical_json(pin) for pin in members})]
        return {'manifest': manifest, 'digest': digest(canonical_json(manifest)),
                'pod': self.store.pods.resolve(target)['id']}

    def _ref(self, pod, identity):
        return self.store.pod_path(pod) / 'refs' / 'collections' / _component(identity)

    def register(self, prepared, *, pods=None, expected_digest=None):
        verified = self.prepare(prepared['manifest'], pod=prepared['pod'])
        if verified != prepared:
            raise StoreError('Collection changed; review again')
        with self.store.locked():
            return self._register(prepared, expected_digest=expected_digest)

    def _register(self, prepared, *, expected_digest=None):
        verified = self.prepare(prepared['manifest'], pod=prepared['pod'])
        if verified != prepared:
            raise StoreError('Collection changed; review again')
        manifest, value, pod = verified['manifest'], verified['digest'], verified['pod']
        ref = self._ref(pod, manifest['id'])
        current = self.documents._read_ref(ref) if ref.exists() or ref.is_symlink() else None
        if current != expected_digest:
            raise StoreError('Collection changed since opening; reopen it before saving')
        self.store.pods.ensure(pod)
        self.store._write_object(pod, 'manifests', value, canonical_json(manifest))
        self.store._atomic_write(ref, (value + '\n').encode(), immutable=False)
        return verified

    def load_digest(self, pod, value, *, pods=None):
        content = self.store._read_object(pod, 'manifests', value)
        manifest = json.loads(content)
        if canonical_json(manifest) != content:
            raise StoreError('Collection is not canonical')
        manifest = manifest_view(manifest)
        self._validate(manifest)
        return manifest

    def list_collections(self, *, pods=None):
        records = []
        for pod in sorted(self.store.pods.selected(pods)):
            directory = self.store.pod_path(pod) / 'refs' / 'collections'
            if not directory.exists() and not directory.is_symlink():
                continue
            self.store._directory(directory)
            for ref in sorted(directory.iterdir()):
                value = self.documents._read_ref(ref)
                manifest = self.load_digest(pod, value)
                if ref.name != _component(manifest['id']):
                    raise StoreError('Collection ref points to a different identity')
                records.append({'manifest': manifest, 'digest': value, 'pod': pod,
                                'pod_name': self.store.pod_name(pod)})
        return records

    def members(self, record, *, pods=None):
        manifest = self.load_digest(record['pod'], record['digest'])
        return [self.documents.document_record(pin, pinned=True) for pin in manifest['documents']]
