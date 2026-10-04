"""Pod behavior across local storage, Git clones, and the document browser."""
import json
import subprocess
from dataclasses import replace

import pytest
from textual.widgets import Tabs, Select

from caiman.storage.store import Store
from caiman.documents.ingest import prepare_document
from caiman.configurations.service import ConfigurationService
from caiman.documents.collections import CollectionService
from caiman.repositories.service import RepoManager
from caiman.dashboard.actions import DocumentCatalogApp
from caiman.documents.cards import DocumentCard


def add_document(root, tmp_path, pod='public', name='Manual'):
    file = tmp_path / (name + '.md')
    file.write_text('# ' + name + '\n\nSynthetic text.\n')
    prepared = prepare_document(file, {'name': name, 'issuer': 'synthetic', 'part': 'chip', 'version': 'A'}, pod=pod)
    return Store(root).register(prepared)


def bare(tmp_path):
    path = tmp_path / 'remote.git'
    subprocess.run(['git', 'init', '--bare', str(path)], check=True, capture_output=True)
    return str(path)


def apply(manager, action, pod, remote=''):
    manager.apply(manager.prepare(action, pod, remote))


def test_no_labels_one_owner_and_cross_pod_dependencies(tmp_path):
    root = tmp_path / 'store'
    doc = add_document(root, tmp_path, 'manuals')
    service = ConfigurationService(Store(root))
    assert {d['pod'] for d in service.list_documents()} == {'manuals'}
    assert service.list_documents(pods=['public']) == []
    board = service.prepare('board', {'board': 'demo', 'version': 'A', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': [
            {'pod': 'manuals', 'digest': doc.manifest_digest}]}]}, pod='hardware')
    service.register(board)
    project = service.prepare('project', {'project': 'flight', 'version': 'A', 'customer': 'Demo',
        'spec_set': 'A', 'boards': [{'name': 'demo', 'version': 'A', 'pod': 'hardware'}],
        'documents': [], 'features': []}, pod='alpha')
    service.register(project)
    assert 'labels' not in service.list_documents()[0]['manifest']
    assert 'pods' not in project.manifest
    assert len(list(root.glob('*/refs/projects/flight/A'))) == 1
    (root / 'manuals').rename(tmp_path / 'unavailable')
    assert service.list_configs('project')[0]['pod'] == 'alpha'
    with pytest.raises(ValueError, match='unavailable'):
        service.prepare('project', project.manifest, pod='alpha')


def test_legacy_document_bytes_and_hash_stay_intact(tmp_path):
    from caiman.documents.models import canonical_json
    from caiman.documents.ingest import digest
    root = tmp_path / 'store'; store = Store(root)
    record = add_document(root, tmp_path, 'alpha')
    manifest = store.read_manifest('alpha', record.manifest_digest)
    manifest.pop('document_id')
    manifest.pop('previous')
    manifest.update(schema='caiman.document.v2', labels={'public': False, 'compartments': ['alpha']})
    content = canonical_json(manifest); value = digest(content)
    store._write_object('alpha', 'manifests', value, content)
    store._atomic_write(record.ref_path, (value + '\n').encode(), immutable=False)
    viewed = ConfigurationService(store).list_documents()[0]
    assert viewed['digest'] == value and 'labels' not in viewed['manifest']
    assert store._read_object('alpha', 'manifests', value) == content


def test_git_clone_roundtrip_and_independent_changes(tmp_path):
    remote = bare(tmp_path)
    first = RepoManager(tmp_path / 'one'); second = RepoManager(tmp_path / 'two')
    add_document(first.store.root, tmp_path, 'alpha')
    apply(first, 'initialize', 'alpha', remote)
    apply(first, 'sync', 'alpha')
    apply(second, 'add', 'teammate-folder', remote)
    assert second.store.pod_path('alpha').name == 'teammate-folder'
    assert ConfigurationService(second.store).list_documents()[0]['pod'] == 'alpha'
    add_document(first.store.root, tmp_path, 'alpha', 'First')
    add_document(second.store.root, tmp_path, 'alpha', 'Second')
    apply(first, 'sync', 'alpha')
    apply(second, 'sync', 'alpha')
    apply(first, 'sync', 'alpha')
    assert {r['manifest']['name'] for r in ConfigurationService(first.store).list_documents()} == {'Manual', 'First', 'Second'}
    assert not list(first.store.root.glob('.repositories/*'))


def test_sync_conflict_preserves_local_and_remote_versions(tmp_path):
    remote = bare(tmp_path)
    first = RepoManager(tmp_path / 'one'); second = RepoManager(tmp_path / 'two')
    add_document(first.store.root, tmp_path, 'alpha')
    apply(first, 'initialize', 'alpha', remote); apply(first, 'sync', 'alpha')
    apply(second, 'add', 'alpha', remote)
    from caiman.documents.edit_service import DocumentEditService
    revisions = []
    for manager, revision in ((first, 'mask-1'), (second, 'mask-2')):
        selected = ConfigurationService(manager.store).list_documents()[0]
        edits = DocumentEditService(manager.store)
        revisions.append(edits.register(selected, edits.prepare(selected,
            dict(selected['manifest'], silicon_revisions=[revision]))))
    one, two = revisions
    apply(first, 'sync', 'alpha')
    with pytest.raises(ValueError, match='needs a merge'):
        apply(second, 'sync', 'alpha')
    assert ConfigurationService(second.store).list_documents()[0]['digest'] == two['digest']
    assert second._git(second.local_path('alpha'), 'show', 'FETCH_HEAD:refs/documents/synthetic/chip/Manual/A') == one['digest']
    assert not (second.local_path('alpha') / '.git/MERGE_HEAD').exists()


def test_sync_failure_keeps_local_commit(tmp_path):
    manager = RepoManager(tmp_path / 'one')
    saved = add_document(manager.store.root, tmp_path, 'alpha')
    apply(manager, 'initialize', 'alpha', str(tmp_path / 'missing.git'))
    with pytest.raises(ValueError):
        apply(manager, 'sync', 'alpha')
    assert manager._git(manager.local_path('alpha'), 'rev-parse', 'HEAD')
    assert ConfigurationService(manager.store).list_documents()[0]['digest'] == saved.manifest_digest


async def test_document_tabs_filter_and_new_document_uses_active_pod(tmp_path):
    root = tmp_path / 'store'
    add_document(root, tmp_path, 'public', 'General')
    add_document(root, tmp_path, 'alpha', 'Customer')
    Store(root).pods.ensure('empty')
    app = DocumentCatalogApp(root=root)
    async with app.run_test(size=(100, 35)) as pilot:
        await pilot.pause()
        assert [c.record['manifest']['name'] for c in app.query(DocumentCard)] == ['General']
        tabs = app.query_one(Tabs)
        tabs.focus()
        await pilot.press('l')
        await pilot.pause()
        assert app.active_pod == 'alpha'
        assert [c.record['manifest']['name'] for c in app.query(DocumentCard)] == ['Customer']
        tabs.active = next(k for k, v in app.tab_pods.items() if v == 'empty')
        await pilot.pause()
        assert not app.query(DocumentCard)
        app.query_one('#add-document').press()
        await pilot.pause()
        assert app.return_value == {'action': 'ingest', 'pod': 'empty'}


async def test_ingest_and_collection_default_pod_forms(tmp_path):
    from caiman.documents.tui import IngestApp
    from caiman.documents.collection_tui import CollectionApp
    store = Store(tmp_path); store.pods.set_default('alpha')
    for app in (IngestApp(tmp_path), CollectionApp(root=tmp_path)):
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one('#pod', Select).value == 'alpha'
            assert not app.query('#visibility') and not app.query('#access')


def test_legacy_git_header_migrates_locally_until_sync(tmp_path):
    from caiman.repositories.service import ATTRIBUTES
    remote = bare(tmp_path)
    old = tmp_path / 'old'; old.mkdir()
    manager = RepoManager(tmp_path / 'store')
    manager._git(old, 'init', '--quiet', '--template=', '--initial-branch=caiman-store')
    (old / 'store.json').write_text(json.dumps({'schema': 'caiman.store.v1', 'compartment': 'alpha'}))
    (old / '.gitattributes').write_bytes(ATTRIBUTES)
    manager._git(old, 'add', '.')
    manager._git(old, '-c', 'commit.gpgSign=false', 'commit', '-qm', 'Legacy pod')
    manager._git(old, 'push', remote, 'HEAD:caiman-store')
    apply(manager, 'add', 'renamed', remote)
    assert json.loads((manager.local_path('alpha') / 'pod.json').read_text())['id'] == 'alpha'
    assert not (manager.local_path('alpha') / 'store.json').exists()
    assert 'store.json' in manager._git(tmp_path, '--git-dir=' + remote, 'ls-tree', '--name-only', 'caiman-store')
    apply(manager, 'sync', 'alpha')
    assert 'pod.json' in manager._git(tmp_path, '--git-dir=' + remote, 'ls-tree', '--name-only', 'caiman-store')


def test_unpinned_stored_configuration_rejected_without_resolving_dependencies(tmp_path):
    from caiman.documents.models import canonical_json
    from caiman.documents.ingest import digest
    store = Store(tmp_path / 'store')
    manifest = {'schema': 'caiman.board.v3', 'board': 'demo', 'version': 'A', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip',
         'documents': [{'ref': 'synthetic/chip/manual/A', 'pod': 'missing'}]}]}
    content = canonical_json(manifest); value = digest(content)
    store._write_object('alpha', 'manifests', value, content)
    with pytest.raises(ValueError, match='document ID, blob'):
        ConfigurationService(store).load_digest('board', value, pod='alpha')


def test_pod_cli_local_create_default_and_filtered_catalog(tmp_path, capsys):
    from caiman.cli.commands import main
    root = tmp_path / 'store'
    assert main(['pod', 'create', 'alpha', '--store', str(root)]) == 0
    assert main(['pod', 'default', 'alpha', '--store', str(root)]) == 0
    assert Store(root).pods.default == 'alpha'
    add_document(root, tmp_path, 'alpha')
    capsys.readouterr()
    assert main(['documents', '--store', str(root), '--pod', 'public']) == 0
    assert json.loads(capsys.readouterr().out) == []
    assert main(['documents', '--store', str(root)]) == 0
    assert json.loads(capsys.readouterr().out)[0]['pod'] == 'alpha'


def test_configuration_move_has_one_owner_and_rejects_collision(tmp_path):
    service = ConfigurationService(Store(tmp_path))
    data = {'board': 'demo', 'version': 'A', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}]}
    first = service.prepare('board', data, pod='alpha'); service.register(first)
    selected = service.list_configs('board')[0]
    moved = service.prepare('board', data, pod='beta')
    service.register(moved, replaces=selected)
    assert [r['pod'] for r in service.list_configs('board')] == ['beta']
    assert service.load_digest('board', first.digest, pod='alpha') == first.manifest
    service.register(first)
    selected = service.list_configs('board', pods=['beta'])[0]
    with pytest.raises(ValueError, match='already uses'):
        service.register(first, replaces=selected)


def test_binary_documents_survive_git_sync_clone_and_metadata_edit(tmp_path):
    from caiman.documents.edit_service import DocumentEditService

    source = tmp_path / 'manual.pdf'
    source.write_bytes(b'%PDF-1.7\n\x00\xff\r\n# Not Markdown\n')
    first = RepoManager(tmp_path / 'one')
    saved = first.store.register(prepare_document(source,
        dict(name='Manual', issuer='synthetic', part='chip', version='A'), pod='alpha'))
    remote = bare(tmp_path)
    apply(first, 'initialize', 'alpha', remote)
    apply(first, 'sync', 'alpha')
    second = RepoManager(tmp_path / 'two')
    apply(second, 'add', 'renamed-folder', remote)
    [selected] = ConfigurationService(second.store).list_documents()
    assert selected['digest'] == saved.manifest_digest
    assert selected['manifest']['files'][0]['path'] == 'document.pdf'
    assert second.store.read_blob('alpha', saved.blob_digest) == source.read_bytes()
    edits = DocumentEditService(second.store)
    changed = edits.prepare(selected, dict(selected['manifest'], description='Reviewed'))
    edits.register(selected, changed)
    apply(second, 'sync', 'alpha')
    apply(first, 'sync', 'alpha')
    assert ConfigurationService(first.store).list_documents()[0]['digest'] == changed.digest
    assert first.store.read_manifest('alpha', saved.manifest_digest)['files'] == selected['manifest']['files']
    assert first.store.read_blob('alpha', saved.blob_digest) == source.read_bytes()
