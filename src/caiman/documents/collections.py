"""Named collections with immutable snapshots of existing document digests."""

from copy import deepcopy
import json
from uuid import uuid4

from caiman.configurations.service import ConfigurationService, _scope
from caiman.documents.ingest import digest, _text
from caiman.documents.models import AccessLabel, canonical_json, current_schema, is_schema, valid_identifier
from caiman.storage.store import AccessDenied, StoreError, _compartments, _component, _hex


class CollectionService:
    def __init__(self, store):
        self.store = store
        self.documents = ConfigurationService(store)

    def _validate(self, data, allowed):
        if not isinstance(data, dict) or set(data) != {'schema', 'id', 'name', 'description', 'labels', 'documents'}:
            raise StoreError('Invalid collection fields')
        if not is_schema('collection', data['schema']) or not valid_identifier(data['id']):
            raise StoreError('Invalid collection identity or schema')
        if not _text(data['name']) or not isinstance(data['description'], str):
            raise StoreError('Supply a collection name and description')
        if data['description'] and not _text(data['description']):
            raise StoreError('Description must not contain control characters')
        compartment, = _compartments(data)
        labels = AccessLabel(data['labels']['public'], frozenset(data['labels']['compartments']))
        if not labels.permits(allowed):
            raise AccessDenied('The collection compartment must be authorized')
        members = data['documents']
        if not isinstance(members, list) or not members:
            raise StoreError('Choose at least one existing document')
        for pin in members:
            if not isinstance(pin, dict) or set(pin) != {'digest', 'compartment'}:
                raise StoreError('Collection members must pin existing documents')
            if not isinstance(pin['compartment'], str) or pin['compartment'] not in {'public', compartment}:
                raise StoreError('Choose public documents or documents in the collection compartment')
            self.documents._document(pin, allowed, pinned=True)
        return compartment

    def prepare(self, data, *, compartments=()):
        allowed = _scope(compartments)
        if not isinstance(data, dict):
            raise StoreError('Expected a collection mapping')
        manifest = deepcopy(data)
        manifest.setdefault('schema', current_schema('collection'))
        manifest.setdefault('id', uuid4().hex)
        manifest.setdefault('description', '')
        compartment = self._validate(manifest, allowed)
        # Membership is a set; presentation order does not change its identity.
        manifest['documents'] = [dict(compartment=location, digest=value) for location, value in
                                 sorted({(p['compartment'], p['digest']) for p in manifest['documents']})]
        return {'manifest': manifest, 'digest': digest(canonical_json(manifest)), 'compartment': compartment}

    def _ref(self, compartment, identity):
        return self.store.root / _component(compartment) / 'refs' / 'collections' / _component(identity)

    def register(self, prepared, *, compartments=(), expected_digest=None):
        verified = self.prepare(prepared['manifest'], compartments=compartments)
        if verified != prepared:
            raise StoreError('Collection changed; review again')
        manifest, value, compartment = verified['manifest'], verified['digest'], verified['compartment']
        ref = self._ref(compartment, manifest['id'])
        exists = ref.exists() or ref.is_symlink()
        current = self.documents._read_ref(ref) if exists else None
        if current != expected_digest:
            raise StoreError('Collection changed since opening; reopen it before saving')
        self.store._write_object(compartment, 'manifests', value, canonical_json(manifest))
        self.store._atomic_write(ref, (value + '\n').encode(), immutable=False)
        return verified

    def load_digest(self, compartment, value, *, compartments=()):
        allowed = _scope(compartments)
        if compartment != 'public' and compartment not in allowed:
            raise AccessDenied('The collection compartment must be authorized')
        _hex(value)
        content = self.store._read_object(compartment, 'manifests', value)
        try:
            manifest = json.loads(content)
        except (UnicodeError, ValueError) as error:
            raise StoreError('Invalid collection JSON') from error
        prepared = self.prepare(manifest, compartments=allowed)
        if prepared['compartment'] != compartment or canonical_json(prepared['manifest']) != content:
            raise StoreError('Collection is not canonical or its labels do not match storage')
        return manifest

    def list_collections(self, *, compartments=()):
        allowed = _scope(compartments)
        records = []
        for compartment in sorted(allowed | {'public'}):
            directory = self.store.root / _component(compartment) / 'refs' / 'collections'
            if not directory.exists() and not directory.is_symlink():
                continue
            self.store._directory(directory)
            for ref in sorted(directory.iterdir()):
                value = self.documents._read_ref(ref)
                manifest = self.load_digest(compartment, value, compartments=allowed)
                if ref.name != _component(manifest['id']):
                    raise StoreError('Collection ref points to a different identity')
                records.append({'manifest': manifest, 'digest': value, 'compartment': compartment})
        return records

    def members(self, record, *, compartments=()):
        manifest = self.load_digest(record['compartment'], record['digest'], compartments=compartments)
        return [{'manifest': self.documents._document(pin, _scope(compartments), pinned=True)[1], **pin}
                for pin in manifest['documents']]
