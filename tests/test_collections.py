from copy import deepcopy

import pytest

from caiman.documents.collections import CollectionService
from caiman.documents.ingest import prepare_document
from caiman.storage.store import AccessDenied, Store, StoreError


def document(tmp_path, store, compartment='public', name='Manual'):
    path = tmp_path / (name + '.md')
    path.write_text('# Synthetic document\n\nContent.\n')
    prepared = prepare_document(path, {
        'name': name, 'description': 'Synthetic reference', 'issuer': 'synthetic',
        'part': 'chip', 'version': 'A',
        'labels': {'public': compartment == 'public',
                   'compartments': [] if compartment == 'public' else [compartment]},
    })
    store.register(prepared)
    return {'digest': prepared.manifest_digest, 'compartment': compartment}


def draft(documents, compartment='public'):
    return {'name': 'Chip documents', 'description': 'Everything for the chip',
            'labels': {'public': compartment == 'public',
                       'compartments': [] if compartment == 'public' else [compartment]},
            'documents': documents}


def test_labels_and_dependencies_fail_before_writes(tmp_path):
    store = Store(tmp_path / 'store')
    service = CollectionService(store)
    private = document(tmp_path, store, 'alpha')
    for data in [draft([private]), {**draft([private], 'alpha'), 'labels': {}},
                 draft([private], 'beta')]:
        with pytest.raises(ValueError):
            service.prepare(data, compartments={'alpha', 'beta'})
    with pytest.raises(AccessDenied):
        service.prepare(draft([private], 'alpha'), compartments=set())
    assert not list(store.root.rglob('collections'))


def test_snapshots_survive_edits_reordering_and_repointed_documents(tmp_path):
    store = Store(tmp_path / 'store')
    service = CollectionService(store)
    first = document(tmp_path, store)
    second = document(tmp_path, store, name='Specification')
    prepared = service.prepare(draft([first, second]))
    original = service.register(prepared)
    reordered = service.prepare({**prepared['manifest'], 'documents': [second, first, first]})
    assert reordered['digest'] == original['digest']
    changed = service.prepare({**prepared['manifest'], 'documents': [second]})
    updated = service.register(changed, expected_digest=original['digest'])
    assert updated['digest'] != original['digest']
    assert len(service.load_digest('public', original['digest'])['documents']) == 2
    assert service.list_collections()[0]['digest'] == updated['digest']
    with pytest.raises(StoreError, match='changed'):
        service.register(prepared, expected_digest=original['digest'])
    # Re-registering a document name cannot change old collection membership.
    document(tmp_path, store)
    assert service.load_digest('public', original['digest'])['documents'] == prepared['manifest']['documents']


def test_private_collection_visibility_and_corrupt_dependency(tmp_path):
    store = Store(tmp_path / 'store')
    service = CollectionService(store)
    pin = document(tmp_path, store, 'alpha')
    saved = service.register(service.prepare(draft([pin], 'alpha'), compartments={'alpha'}),
                             compartments={'alpha'})
    assert service.list_collections() == []
    assert len(service.list_collections(compartments={'alpha'})) == 1
    with pytest.raises(AccessDenied):
        service.load_digest('alpha', saved['digest'])
    tampered = deepcopy(saved)
    tampered['manifest']['documents'][0]['digest'] = 'sha256:' + '0' * 64
    with pytest.raises(ValueError):
        service.register(tampered, compartments={'alpha'}, expected_digest=saved['digest'])
    assert service.list_collections(compartments={'alpha'})[0]['digest'] == saved['digest']


def test_collection_requires_existing_documents_and_rejects_nesting(tmp_path):
    service = CollectionService(Store(tmp_path / 'store'))
    with pytest.raises(ValueError):
        service.prepare(draft([]))
    with pytest.raises(ValueError):
        service.prepare(draft([{'digest': 'sha256:' + '0' * 64, 'compartment': 'public'}]))
    assert not service.store.root.exists()
    pin = document(tmp_path, service.store)
    saved = service.register(service.prepare(draft([pin])))
    with pytest.raises(StoreError, match='Not a document manifest'):
        service.prepare(draft([{'compartment': 'public', 'digest': saved['digest']}]))
