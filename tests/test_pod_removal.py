"""Pod removal preserves files and protects references from current roots."""
import pytest
from rich.console import COLOR_SYSTEMS
from textual.widgets import Button, ListView, Static

from caiman.configurations.service import ConfigurationService
from caiman.documents.collections import CollectionService
from caiman.repositories.service import RepoManager
from caiman.repositories.tui import RepoManagerApp
from caiman.dashboard.onboarding import CategoryApp
from test_pods import add_document, apply


def legacy_register(service, kind, data, pod):
    from caiman.configurations.models import validate_board, validate_project
    from caiman.documents.models import canonical_json
    from caiman.documents.ingest import digest
    from caiman.storage.store import _component
    manifest = (validate_board if kind == 'board' else validate_project)(data)
    content = canonical_json(manifest)
    value = digest(content)
    service.store.pods.ensure(pod)
    service.store._write_object(pod, 'manifests', value, content)
    ref = service.store.pod_path(pod) / 'refs' / (kind + 's') / _component(manifest[kind]) / _component(manifest['version'])
    service.store._atomic_write(ref, (value + '\n').encode(), immutable=False)
    from caiman.configurations.service import PreparedConfig, ConfigRegistration
    return PreparedConfig(kind, manifest, value, pod), ConfigRegistration(value, (ref,))


def board(manager, tmp_path):
    doc = add_document(manager.store.root, tmp_path, 'manuals')
    service = ConfigurationService(manager.store)
    prepared, registration = legacy_register(service, 'board', {'board': 'demo', 'version': 'A', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': [
            {'pod': 'manuals', 'digest': doc.manifest_digest}]}]}, pod='hardware')
    return service, prepared, registration


def test_current_and_historical_references(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    service, prepared, registration = board(manager, tmp_path)
    with pytest.raises(ValueError, match='Board: hardware/demo @ A'):
        manager.prepare('unregister', 'manuals')
    before = {p.relative_to(manager.local_path('manuals')): p.read_bytes()
              for p in manager.local_path('manuals').rglob('*') if p.is_file()}
    for ref in registration.ref_paths:
        ref.unlink()
    apply(manager, 'unregister', 'manuals')
    assert 'manuals' not in manager.store.pods.selected()
    [archived] = (manager.store.root / '.removed-pods' / 'manuals').iterdir()
    assert {p.relative_to(archived): p.read_bytes() for p in archived.rglob('*') if p.is_file()} == before
    assert service.load_digest('board', prepared.digest, pod='hardware') == prepared.manifest


def test_current_project_keeps_historical_board_dependencies_live(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    service, prepared, registration = board(manager, tmp_path)
    project, _ = legacy_register(service, 'project', {'project': 'flight', 'version': 'A', 'customer': 'Demo',
        'spec_set': 'A', 'boards': [{'name': 'demo', 'version': 'A', 'pod': 'hardware', 'digest': prepared.digest}],
        'documents': [], 'features': []}, pod='programs')
    for ref in registration.ref_paths:
        ref.unlink()
    for pod in ('manuals', 'hardware'):
        with pytest.raises(ValueError, match='Project: programs/flight @ A'):
            manager.prepare('unregister', pod)


def test_collection_added_after_review_blocks_apply(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    doc = add_document(manager.store.root, tmp_path, 'manuals')
    plan = manager.prepare('unregister', 'manuals')
    collections = CollectionService(manager.store)
    from caiman.documents.models import canonical_json
    from caiman.documents.ingest import digest
    manifest = {'schema': 'caiman.collection.v1', 'id': 'guides', 'name': 'Guides',
                'description': '', 'documents': [{'pod': 'manuals', 'digest': doc.manifest_digest}]}
    content = canonical_json(manifest); value = digest(content)
    manager.store.pods.ensure('library')
    manager.store._write_object('library', 'manifests', value, content)
    manager.store._atomic_write(collections._ref('library', 'guides'), (value + '\n').encode(), immutable=False)
    with pytest.raises(ValueError, match='Collection: library/Guides'):
        manager.apply(plan)
    assert manager.local_path('manuals').exists()


def test_renamed_default_and_last_pod_removal(tmp_path):
    manager = RepoManager(tmp_path)
    apply(manager, 'create', 'alpha')
    (tmp_path / 'alpha').rename(tmp_path / 'renamed')
    apply(manager, 'unregister', 'renamed')
    assert manager.store.pods.default == 'public'
    with pytest.raises(ValueError, match='public pod cannot be removed'):
        apply(manager, 'unregister', 'public')
    assert manager.store.pods.default == 'public'


@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
async def test_remove_button_selection_and_review(tmp_path, color_system):
    manager = RepoManager(tmp_path / 'store')
    apply(manager, 'create', 'alpha')
    app = CategoryApp('repos', store_root=manager.store.root, selected_pod='alpha')
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(80, 32)) as pilot:
        await pilot.pause()
        button = app.query_one('#repo-unregister', Button)
        button.focus()
        await pilot.pause()
        row = app.query_one('#pod-list', ListView).highlighted_child
        assert row.record['pod'] == 'alpha'
        assert row.has_class('-highlight')
        assert row.styles.border_left[0] == 'solid'
        assert 'alpha' in str(app.query_one('#selected-pod', Static).render())
        await pilot.press('enter')
    assert app.return_value == {'action': 'repo-unregister', 'pod': 'alpha'}
    review = RepoManagerApp(store_root=manager.store.root, action='unregister', pod='alpha')
    review.console._color_system = COLOR_SYSTEMS[color_system]
    async with review.run_test(size=(90, 36)) as pilot:
        await pilot.click('#review')
        await pilot.pause()
        assert not review.query_one('#apply', Button).disabled
        assert '.removed-pods' in str(review.query_one('#preview', Static).render())
        await pilot.click('#apply')
        await pilot.pause()
    assert 'alpha' not in manager.store.pods.selected()


async def test_blocked_review_explains_reference(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    board(manager, tmp_path)
    app = RepoManagerApp(store_root=manager.store.root, action='unregister', pod='manuals')
    async with app.run_test() as pilot:
        await pilot.click('#review')
        await pilot.pause()
        assert app.query_one('#apply', Button).disabled
        assert 'hardware/demo' in str(app.query_one('#status', Static).render())


@pytest.mark.parametrize('kind', ['documents', 'boards', 'projects'])
async def test_galleries_after_last_pod_removed(tmp_path, kind):
    from caiman.dashboard.actions import DocumentCatalogApp
    from caiman.boards.gallery import BoardGalleryApp
    from caiman.configurations.gallery import ProjectGalleryApp
    manager = RepoManager(tmp_path)
    apply(manager, 'create', 'alpha')
    apply(manager, 'unregister', 'alpha')
    app = (DocumentCatalogApp(root=tmp_path) if kind == 'documents' else
           BoardGalleryApp(tmp_path) if kind == 'boards' else ProjectGalleryApp(root=tmp_path))
    async with app.run_test() as pilot:
        await pilot.pause()
        status = app.query_one('#status' if kind == 'documents' else '#gallery-status', Static)
        assert app.active_pod == 'public'
        assert 'create a pod' not in str(status.render())


def test_git_files_preserved_and_internal_references_leave_together(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    doc = add_document(manager.store.root, tmp_path, 'alpha')
    collections = CollectionService(manager.store)
    collections.register(collections.prepare({'name': 'Internal', 'documents': [
        {'pod': 'alpha', 'digest': doc.manifest_digest}]}, pod='alpha'))
    apply(manager, 'initialize', 'alpha')
    apply(manager, 'sync', 'alpha')
    before = (manager.local_path('alpha') / '.git' / 'HEAD').read_bytes()
    apply(manager, 'unregister', 'alpha')
    [archived] = (manager.store.root / '.removed-pods' / 'alpha').iterdir()
    assert (archived / '.git' / 'HEAD').read_bytes() == before


def test_incomplete_catalog_blocks_removal(tmp_path):
    manager = RepoManager(tmp_path / 'store')
    service, prepared, registration = board(manager, tmp_path)
    registration.ref_paths[0].write_text('broken')
    with pytest.raises(ValueError):
        manager.prepare('unregister', 'manuals')
    assert manager.local_path('manuals').exists()


def test_cli_remove_uses_reference_checks(tmp_path, capsys):
    from caiman.cli import main
    manager = RepoManager(tmp_path / 'store')
    service, prepared, registration = board(manager, tmp_path)
    args = ['pod', 'remove', 'manuals', '--store', str(manager.store.root)]
    assert main(args) == 1
    assert 'hardware/demo' in capsys.readouterr().err
    for ref in registration.ref_paths:
        ref.unlink()
    assert main(args) == 0
    assert 'manuals' not in manager.store.pods.selected()
