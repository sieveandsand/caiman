from copy import deepcopy

import pytest

from caiman.configurations.service import ConfigurationService
from caiman.documents.edit_service import DocumentEditService
from caiman.documents.ingest import digest, prepare_document, verify_prepared
from caiman.documents.models import ValidationError, accepted_schemas, canonical_json
from caiman.storage.store import Store


@pytest.mark.parametrize('field,value', [
    ('structure', 'prose'), ('structure', 'requirement'),
    ('requirements', {'pattern': 'REQ-[0-9]+'}),
    ('converter', {'name': 'Example', 'version': '1'}),
    ('converter', {'name': 'Example', 'hosted': False}),
])
def test_retired_document_fields_rejected_before_registration(tmp_path, field, value):
    source = tmp_path / 'manual.md'
    source.write_text('# Manual\nUnchanged content.\n')
    metadata = dict(issuer='synthetic', part='chip', doc_type='manual', version='A')
    prepared = prepare_document(source, metadata)
    with pytest.raises(ValidationError, match=field):
        prepare_document(source, {**metadata, field: value})
    prepared.manifest[field] = value
    with pytest.raises(ValidationError):
        verify_prepared(prepared)


@pytest.mark.parametrize('schema', accepted_schemas('document'))
def test_old_metadata_is_read_without_rewriting_snapshots(tmp_path, schema):
    source = tmp_path / 'manual.md'
    source.write_text('# Manual\nUnchanged content.\n')
    store = Store(tmp_path / 'store')
    registered = store.register(prepare_document(source,
        dict(issuer='synthetic', part='chip', doc_type='manual', version='A')))
    old = store.read_manifest('public', registered.manifest_digest)
    old.update(schema=schema, structure='requirement', requirements={'pattern': 'REQ-[0-9]+'})
    old['converter'] = {'name': 'Example', 'version': '1', 'hosted': False}
    content = canonical_json(old)
    old_digest = digest(content)
    store._write_object('public', 'manifests', old_digest, content)
    store._atomic_write(registered.ref_path, (old_digest + '\n').encode(), immutable=False)

    # Legacy reading remains available, but no overlay or old-data edit migration
    # is part of the new document revision model.
    viewed = store.read_manifest('public', old_digest)
    assert viewed['converter'] == {'name': 'Example'}
    assert not {'structure', 'requirements'} & viewed.keys()
    assert store._read_object('public', 'manifests', old_digest) == content
    assert store.read_blob('public', registered.blob_digest) == source.read_bytes()
