"""Current metadata stays consistent while content and historical snapshots stay pinned."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor

import pytest

from caiman.configurations.service import ConfigurationService
from caiman.documents.collections import CollectionService
from caiman.documents.edit_service import DocumentEditService
from caiman.documents.ingest import prepare_document
from caiman.documents.revisions import DocumentRevisions
from caiman.storage.store import Store, StoreError
from caiman.storage.transactions import JOURNAL


@pytest.fixture
def graph(tmp_path):
    source = tmp_path / 'manual.pdf'
    source.write_bytes(b'%PDF\x00\xff\n')
    store = Store(tmp_path / 'store')
    saved = store.register(prepare_document(source, dict(
        name='Manual', description='Original', issuer='synthetic', part='chip', version='A'), pod='public'))
    configurations = ConfigurationService(store)
    pin = {'pod': 'public', 'digest': saved.manifest_digest, 'ref': 'synthetic/chip/Manual/A'}
    board = configurations.prepare('board', {'board': 'controller', 'version': 'A', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'silicon_revision': '1', 'documents': [pin]}]}, pod='programs')
    configurations.register(board)
    project = configurations.prepare('project', {
        'project': 'flight', 'version': 'A', 'customer': 'Demo', 'spec_set': 'A',
        'boards': [{'name': 'controller', 'version': 'A', 'pod': 'programs'}],
        'documents': [pin], 'features': [{'name': 'start', 'scope': 'required',
                                       'governed_by': [dict(pin, requirements=['REQ-1'])]}]}, pod='programs')
    configurations.register(project)
    collections = CollectionService(store)
    collection = collections.prepare({'name': 'Reference set', 'documents': [
        {'pod': 'public', 'digest': saved.manifest_digest}]}, pod='programs')
    collections.register(collection)
    selected = configurations.list_documents()[0]
    return store, selected, board, project, collection


def refs(store):
    return {str(path.relative_to(store.root)): path.read_bytes()
            for path in store.root.glob('*/refs/**/*') if path.is_file()}


@pytest.mark.parametrize('changes', [
    {'description': 'Corrected'}, {'source': {'pages': 12}}, {'converter': {'name': 'Tool'}},
    {'name': 'Renamed'}, {'version': 'B'}, {'issuer': 'another'}, {'part': 'different'},
    {'doc_type': 'application note'}, {'silicon_revisions': ['2']},
])
def test_every_field_creates_complete_revision_without_repinning(graph, changes):
    store, selected, board, project, collection = graph
    before = refs(store)
    edits = DocumentEditService(store)
    prepared = edits.prepare(selected, dict(selected['manifest'], **changes))
    assert prepared.mode == 'revision'
    assert {item['kind'] for item in prepared.usages.usages} == {'board', 'project', 'collection'}
    updated = edits.register(selected, prepared)
    assert updated['digest'] == prepared.digest != selected['digest']
    assert updated['manifest']['previous'] == selected['digest']
    assert updated['manifest']['files'] == selected['manifest']['files']
    assert updated['manifest']['document_id'] == selected['manifest']['document_id']
    assert store.read_manifest('public', updated['digest']) == updated['manifest']
    assert store.read_manifest('public', selected['digest']) == selected['manifest']
    # Consumer pods and snapshots are completely untouched.
    assert all(refs(store)[path] == content for path, content in before.items() if not path.startswith('public/'))
    service = ConfigurationService(store)
    for pin in (board.manifest['parts'][0]['documents'][0], project.manifest['documents'][0],
                project.manifest['features'][0]['governed_by'][0]):
        assert service.document_record(pin, pinned=True) == updated
    assert CollectionService(store).members(collection) == [updated]
    assert service.list_documents() == [updated]
    assert service.prepare('project', project.manifest, pod='programs') == project
    assert service.load_digest('board', board.digest, pod='programs') == board.manifest
    unchanged = edits.prepare(updated, updated['manifest'])
    assert unchanged.mode == 'unchanged'
    before_noop = refs(store)
    assert edits.register(updated, unchanged) == updated
    assert refs(store) == before_noop


def test_history_and_restore_are_complete_revisions(graph):
    store, selected, *_ = graph
    edits = DocumentEditService(store)
    updated = edits.register(selected, edits.prepare(selected, dict(selected['manifest'], name='Renamed', description='Corrected')))
    restored_draft = dict(updated['manifest'], name='Manual', description='Original')
    restored = edits.register(updated, edits.prepare(updated, restored_draft))
    history = DocumentRevisions(store).history('public', selected['manifest']['document_id'])
    assert [entry['digest'] for entry in history] == [restored['digest'], updated['digest'], selected['digest']]
    assert history[-1]['manifest'] == selected['manifest']
    assert restored['manifest']['previous'] == updated['digest']


def test_clearing_optional_fields_does_not_fall_back_to_older_values(graph):
    store, selected, *_ = graph
    edits = DocumentEditService(store)
    draft = deepcopy(selected['manifest'])
    draft.pop('description')
    updated = edits.register(selected, edits.prepare(selected, draft))
    assert 'description' not in updated['manifest']
    assert 'description' not in ConfigurationService(store).document_record({'pod': 'public', 'digest': selected['digest']})['manifest']


def test_program_document_can_replace_part_metadata_without_changing_boards(graph):
    store, selected, board, *_ = graph
    draft = dict(selected['manifest'], program='flight')
    draft.pop('part')
    edits = DocumentEditService(store)
    updated = edits.register(selected, edits.prepare(selected, draft))
    assert ConfigurationService(store).document_record(board.manifest['parts'][0]['documents'][0]) == updated


def test_stale_metadata_and_new_usages_invalidate_review(graph):
    store, selected, *_ = graph
    edits = DocumentEditService(store)
    prepared = edits.prepare(selected, dict(selected['manifest'], name='Renamed'))
    collections = CollectionService(store)
    collections.register(collections.prepare({'name': 'Added after review', 'documents': [
        {'pod': selected['pod'], 'digest': selected['digest']}]}, pod='programs'))
    before = refs(store)
    with pytest.raises(StoreError, match='usages changed'):
        edits.register(selected, prepared)
    assert refs(store) == before
    first = edits.prepare(selected, dict(selected['manifest'], description='First'))
    second = edits.prepare(selected, dict(selected['manifest'], description='Second'))
    edits.register(selected, first)
    with pytest.raises(StoreError, match='changed since opening'):
        edits.register(selected, second)


@pytest.mark.parametrize('crash', [False, True])
def test_partial_reference_publication_rolls_back(graph, monkeypatch, crash):
    store, selected, *_ = graph
    edits = DocumentEditService(store)
    prepared = edits.prepare(selected, dict(selected['manifest'], name='Renamed'))
    before = refs(store)
    original_write = store._atomic_write
    count = 0
    class Interrupted(BaseException):
        pass
    def fail(path, content, *, immutable):
        nonlocal count
        if 'refs' in path.parts:
            count += 1
            if count == 2:
                raise Interrupted() if crash else OSError('Simulated write failure')
        return original_write(path, content, immutable=immutable)
    monkeypatch.setattr(store, '_atomic_write', fail)
    with pytest.raises(Interrupted if crash else OSError):
        edits.register(selected, prepared)
    if crash:
        assert (store.root / JOURNAL).exists()
        with pytest.raises(StoreError, match='in progress'):
            store.read_manifest(selected['pod'], selected['digest'])
    recovered = Store(store.root)
    assert refs(recovered) == before
    assert not (store.root / JOURNAL).exists()
    assert ConfigurationService(recovered).list_documents() == [selected]


def test_document_update_and_git_share_the_writer_lock(graph):
    store, selected, *_ = graph
    edits = DocumentEditService(store)
    prepared = edits.prepare(selected, dict(selected['manifest'], description='Changed'))
    with store.locked(), ThreadPoolExecutor() as executor:
        future = executor.submit(edits.register, selected, prepared)
        with pytest.raises(StoreError, match='Another pod operation'):
            future.result()


def test_changed_file_requires_a_new_document_label(graph, tmp_path):
    store, selected, *_ = graph
    file = tmp_path / 'changed.pdf'
    file.write_bytes(b'%PDF a different body')
    prepared = prepare_document(file, dict(name='Manual', issuer='synthetic', part='chip', version='A'), pod='public')
    before = refs(store)
    with pytest.raises(StoreError, match='new document name or version'):
        store.register(prepared)
    assert refs(store) == before
    new = store.register(prepare_document(file, dict(name='Manual', issuer='synthetic', part='chip', version='B'), pod='public'))
    assert new.manifest_digest != selected['digest']


def test_same_bytes_in_another_document_do_not_share_metadata(graph, tmp_path):
    store, selected, *_ = graph
    file = tmp_path / 'same.pdf'
    file.write_bytes(store.read_blob('public', 'sha256:' + selected['manifest']['files'][0]['sha256']))
    other = store.register(prepare_document(file, dict(name='Other Manual', description='Independent',
        issuer='synthetic', part='chip', version='A'), pod='public'))
    edits = DocumentEditService(store)
    edits.register(selected, edits.prepare(selected, dict(selected['manifest'], description='Changed')))
    assert ConfigurationService(store)._document({'pod': 'public', 'digest': other.manifest_digest})[1]['description'] == 'Independent'


def test_combined_metadata_edits_extend_revision_history(graph):
    store, selected, *_ = graph
    edits = DocumentEditService(store)
    first = edits.register(selected, edits.prepare(selected, dict(selected['manifest'], description='First')))
    second = edits.register(first, edits.prepare(first,
        dict(first['manifest'], description='Second', silicon_revisions=['1'])))
    assert second['manifest']['description'] == 'Second'
    assert second['digest'] != selected['digest']
    assert ConfigurationService(store).list_documents()[0] == second


def test_project_keeps_its_other_pinned_board_declarations(graph):
    store, selected, board, project, _ = graph
    service = ConfigurationService(store)
    # The current board tag can have changes the project has not adopted.
    newer = service.prepare('board', dict(board.manifest, notes='Not adopted by project'), pod='programs')
    service.register(newer)
    edits = DocumentEditService(store)
    edits.register(selected, edits.prepare(selected, dict(selected['manifest'], name='Renamed')))
    [current_project] = service.list_configs('project')
    pinned = service.load_digest('board', current_project['manifest']['boards'][0]['digest'], pod='programs')
    [current_board] = service.list_configs('board')
    assert 'notes' not in pinned
    assert current_board['manifest']['notes'] == 'Not adopted by project'
    assert pinned['parts'][0]['documents'] == current_board['manifest']['parts'][0]['documents']


def test_explicit_digest_reads_preserve_history_while_normal_reads_follow_current(graph):
    from caiman.documents.ingest import digest
    from caiman.documents.models import canonical_json
    store, selected, *_ = graph
    older = dict(selected['manifest'], description='Earlier description')
    value = digest(canonical_json(older))
    store._write_object('public', 'manifests', value, canonical_json(older))
    edits = DocumentEditService(store)
    edits.register(selected, edits.prepare(selected, dict(selected['manifest'], description='Current')))
    assert ConfigurationService(store)._document({'pod': 'public', 'digest': value})[1]['description'] == 'Current'
    assert store.read_manifest('public', value)['description'] == 'Earlier description'


@pytest.mark.parametrize('corruption', ['body', 'identity', 'missing'])
def test_bad_current_pointer_cannot_retarget_pinned_body_or_document(graph, corruption):
    from caiman.documents.ingest import digest
    from caiman.documents.models import canonical_json
    store, selected, board, *_ = graph
    revision = deepcopy(selected['manifest'])
    if corruption == 'body':
        revision['files'][0]['sha256'] = '0' * 64
    elif corruption == 'identity':
        revision['document_id'] = 'another-document'
    value = digest(canonical_json(revision))
    store._write_object('public', 'manifests', value, canonical_json(revision))
    if corruption == 'missing':
        value = 'sha256:' + '0' * 64
    head = DocumentRevisions(store).ref('public', selected['manifest']['document_id'])
    store._atomic_write(head, (value + '\n').encode(), immutable=False)
    with pytest.raises((StoreError, OSError)):
        ConfigurationService(store).document_record(board.manifest['parts'][0]['documents'][0], pinned=True)
    assert store.read_manifest('public', selected['digest']) == selected['manifest']


def test_incomplete_usage_scan_does_not_block_metadata_edit(graph, monkeypatch):
    store, selected, *_ = graph
    def unavailable(*args, **kwargs):
        raise StoreError('Missing dependency')
    monkeypatch.setattr(ConfigurationService, 'list_configs', unavailable)
    edits = DocumentEditService(store)
    prepared = edits.prepare(selected, dict(selected['manifest'], issuer='another'))
    assert prepared.usages.unknown
    assert edits.register(selected, prepared)['manifest']['issuer'] == 'another'


def test_only_document_pod_needs_sync_after_metadata_edit(graph, tmp_path):
    from caiman.repositories.service import RepoManager
    from test_pods import apply, bare
    store, selected, *_ = graph
    sender = RepoManager(store.root)
    receiver = RepoManager(tmp_path / 'clone')
    for pod in ('public', 'programs'):
        directory = tmp_path / pod
        directory.mkdir()
        remote = bare(directory)
        apply(sender, 'initialize', pod, remote)
        apply(sender, 'sync', pod)
        apply(receiver, 'add', 'local-' + pod, remote)
    edits = DocumentEditService(store)
    saved = edits.register(selected, edits.prepare(selected, dict(selected['manifest'], name='Renamed')))
    apply(sender, 'sync', 'public')
    apply(receiver, 'sync', 'public')
    service = ConfigurationService(receiver.store)
    [project] = service.list_configs('project')
    assert service.document_record(project['manifest']['documents'][0]) == saved
    assert service.prepare('project', project['manifest'], pod='programs').digest == project['digest']


@pytest.mark.asyncio
@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
@pytest.mark.parametrize('identity_change', [False, True])
async def test_review_shows_every_affected_usage_and_cancel_preserves_refs(graph, color_system, identity_change):
    from rich.console import COLOR_SYSTEMS
    from textual.widgets import Button, Static
    from caiman.documents.edit import DocumentEditReviewApp
    store, selected, *_ = graph
    edits = DocumentEditService(store)
    draft = dict(selected['manifest'], **({'name': 'Renamed'} if identity_change else {'description': 'Changed'}))
    prepared = edits.prepare(selected, draft)
    before = refs(store)
    app = DocumentEditReviewApp(service=edits, selection=selected, prepared=prepared)
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(110, 42)) as pilot:
        await pilot.pause()
        affected = '\n'.join(str(widget.content) for widget in app.query('#affected-usages Static'))
        assert 'programs/controller' in affected and 'programs/flight' in affected and 'Reference set' in affected
        app.query_one('#register', Button).focus()
        await pilot.pause()
        assert app.focused is app.query_one('#register', Button)
        await pilot.press('q')
    assert refs(store) == before


def test_open_configuration_editor_cannot_revert_current_document_metadata(graph):
    store, selected, board, *_ = graph
    service = ConfigurationService(store)
    [opened] = service.list_configs('board')
    pending = service.prepare('board', dict(board.manifest, notes='An older open draft'), pod='programs')
    edits = DocumentEditService(store)
    updated = edits.register(selected, edits.prepare(selected, dict(selected['manifest'], name='Renamed')))
    service.register(pending, replaces=opened)
    [current] = service.list_configs('board')
    assert service.document_record(current['manifest']['parts'][0]['documents'][0]) == updated


def test_recovery_rejects_paths_outside_reference_trees(graph):
    from caiman.documents.models import canonical_json
    store, selected, *_ = graph
    before = refs(store)
    journal = [{'path': '../outside', 'before': None, 'after': selected['digest'] + '\n'}]
    store._atomic_write(store.root / JOURNAL, canonical_json(journal), immutable=False)
    with pytest.raises(StoreError, match='Cannot recover'):
        Store(store.root)
    assert refs(store) == before
    assert (store.root / JOURNAL).exists()


def test_recovery_does_not_overwrite_refs_changed_outside_the_transaction(graph):
    from caiman.documents.models import canonical_json
    store, selected, *_ = graph
    path = store.pod_path('public') / 'refs/documents' / selected['ref']
    journal = [{'path': path.relative_to(store.root).as_posix(), 'before': 'sha256:' + '0' * 64 + '\n',
                'after': 'sha256:' + '1' * 64 + '\n'}]
    store._atomic_write(store.root / JOURNAL, canonical_json(journal), immutable=False)
    before = refs(store)
    with pytest.raises(StoreError, match='conflicts with a changed ref'):
        Store(store.root)
    assert refs(store) == before


def test_two_revisions_cannot_be_saved_as_duplicate_document_attachments(graph):
    store, selected, board, *_ = graph
    edits = DocumentEditService(store)
    updated = edits.register(selected, edits.prepare(selected, dict(selected['manifest'], name='Renamed')))
    draft = deepcopy(board.manifest)
    draft['parts'][0]['documents'] = [
        {'pod': 'public', 'digest': selected['digest']},
        {'pod': 'public', 'digest': updated['digest']},
    ]
    with pytest.raises(ValueError, match='Duplicate document selector'):
        ConfigurationService(store).prepare('board', draft, pod='programs')
