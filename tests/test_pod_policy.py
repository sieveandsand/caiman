"""The public default is fixed and unrelated pods cannot share references."""
import json

import pytest

from caiman.storage.store import Store
from caiman.configurations.service import ConfigurationService
from caiman.documents.collections import CollectionService
from caiman.repositories.service import RepoManager
from test_pods import add_document


def test_public_default_ignores_old_preference_and_cannot_change(tmp_path):
    store = Store(tmp_path)
    (tmp_path / '.pods.json').write_text(json.dumps({'default': 'alpha'}))
    assert store.pods.default == 'public'
    with pytest.raises(ValueError, match='public'):
        store.pods.set_default('alpha')
    with pytest.raises(ValueError, match='public'):
        RepoManager(tmp_path).prepare('default', 'alpha')
    with pytest.raises(ValueError, match='public'):
        RepoManager(tmp_path).prepare('unregister', 'public')
    assert not (tmp_path / 'alpha').exists()


@pytest.mark.parametrize('kind', ['board', 'project', 'collection'])
def test_unrelated_pod_document_rejected(tmp_path, kind):
    store = Store(tmp_path / 'store')
    doc = add_document(store.root, tmp_path, 'beta')
    service = ConfigurationService(store)
    board = service.prepare('board', {'board': 'base', 'version': 'A', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}]}, pod='public')
    service.register(board)
    pin = {'pod': 'beta', 'digest': doc.manifest_digest}
    if kind == 'collection':
        prepare = lambda: CollectionService(store).prepare({'name': 'manuals', 'documents': [pin]}, pod='alpha')
    else:
        data = ({'board': 'demo', 'version': 'A', 'documents': [pin], 'parts': [{'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}]} if kind == 'board'
                else {'project': 'demo', 'version': 'A', 'customer': 'Demo', 'spec_set': 'A',
                      'boards': [{'name': 'base', 'version': 'A', 'pod': 'public'}], 'documents': [pin], 'features': []})
        prepare = lambda: ConfigurationService(store).prepare(kind, data, pod='alpha')
    with pytest.raises(ValueError, match='pod reference'):
        prepare()
    assert not (store.root / 'alpha').exists()


def board_data(documents=()):
    return {'board': 'base', 'version': 'A', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': list(documents)}]}


def project_data(board_pod):
    return {'project': 'demo', 'version': 'A', 'customer': 'Demo', 'spec_set': 'A',
            'boards': [{'name': 'base', 'version': 'A', 'pod': board_pod}],
            'documents': [], 'features': []}


@pytest.mark.parametrize(('owner', 'target', 'allowed'), [
    ('public', 'public', True), ('alpha', 'public', True), ('alpha', 'alpha', True),
    ('public', 'alpha', False), ('alpha', 'beta', False),
])
def test_board_pod_boundary(tmp_path, owner, target, allowed):
    store = Store(tmp_path / 'store')
    service = ConfigurationService(store)
    service.register(service.prepare('board', board_data(), pod=target))
    if allowed:
        service.register(service.prepare('project', project_data(target), pod=owner))
    else:
        with pytest.raises(ValueError, match='cross-pod reference'):
            service.prepare('project', project_data(target), pod=owner)


def test_changed_owner_rejected_at_registration(tmp_path):
    from dataclasses import replace
    store = Store(tmp_path / 'store')
    doc = add_document(store.root, tmp_path, 'alpha')
    service = ConfigurationService(store)
    prepared = service.prepare('board', board_data([{'pod': 'alpha', 'digest': doc.manifest_digest}]), pod='alpha')
    with pytest.raises(ValueError, match='cross-pod reference'):
        service.register(replace(prepared, pod='beta'))
    assert not (store.root / 'beta').exists()
    collections = CollectionService(store)
    prepared = collections.prepare({'name': 'Manuals', 'documents': [
        {'pod': 'alpha', 'digest': doc.manifest_digest}]}, pod='alpha')
    with pytest.raises(ValueError, match='cross-pod reference'):
        collections.register(dict(prepared, pod='public'))


def test_public_board_cannot_introduce_private_transitive_dependency(tmp_path):
    from test_pod_removal import legacy_register
    store = Store(tmp_path / 'store')
    doc = add_document(store.root, tmp_path, 'beta')
    service = ConfigurationService(store)
    historical, _ = legacy_register(service, 'board', board_data([
        {'pod': 'beta', 'digest': doc.manifest_digest}]), 'public')
    # Historical bytes stay available, but reconstruction enforces today's boundary.
    assert service.load_digest('board', historical.digest) == historical.manifest
    with pytest.raises(ValueError, match='cross-pod reference'):
        service.prepare('project', project_data('public'), pod='alpha')


def test_public_identity_and_removal_protection_survive_rename(tmp_path):
    store = Store(tmp_path / 'store')
    assert store.pods.default == 'public'
    assert store.pods.selected() == {'public'}
    store.pods.ensure('alpha')
    assert (store.root / 'public' / 'pod.json').is_file()
    store.pod_path('public').rename(store.root / 'shared')
    assert store.pods.default == 'public'
    assert store.pod_path('public').name == 'shared'
    assert store.pods.check_reference('alpha', 'shared') == 'public'
    with pytest.raises(ValueError, match='public pod cannot be removed'):
        RepoManager(store.root).prepare('unregister', 'shared')


def test_another_pod_cannot_impersonate_public_folder(tmp_path):
    store = Store(tmp_path / 'store')
    path = store.root / 'public'
    path.mkdir(parents=True)
    (path / 'pod.json').write_text(json.dumps({'schema': 'caiman.pod.v1', 'id': 'alpha', 'name': 'Alpha'}))
    with pytest.raises(ValueError, match='public folder is occupied'):
        store.pods.ensure('public')


@pytest.mark.parametrize(('owner', 'expected'), [('public', {'public'}), ('alpha', {'public', 'alpha'})])
def test_document_picker_limits_candidates_to_reference_pods(tmp_path, owner, expected):
    from caiman.documents.picker import DocumentPicker
    store = Store(tmp_path / 'store')
    for pod in ('public', 'alpha', 'beta'):
        add_document(store.root, tmp_path, pod)
    picker = DocumentPicker(service=ConfigurationService(store), owner=owner)
    assert {record['pod'] for record in picker.load_records()} == expected
