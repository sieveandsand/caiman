import pytest

from caiman.documents.picker import document_pin
from test_document_picker import library, project
from test_collection_picker import collections


def collection_pin(record):
    return dict(pod=record['pod'], collection=record['manifest']['id'], digest=record['digest'])


def test_project_follows_membership_without_rewriting_its_snapshot(library):
    service, group, pins = collections(library)
    draft = project(library)
    draft['documents'] = [collection_pin(group)]
    prepared = library.prepare('project', draft)
    library.register(prepared)
    service.register(service.prepare(group['manifest'] | {'name': 'Renamed', 'documents': pins[:1]}),
                     expected_digest=group['digest'])
    stored = library.load_digest('project', prepared.digest)
    assert stored == prepared.manifest
    assert [document_pin(r) for r in library.project_documents(stored, owner='public')] == pins[:1]
    assert {r['manifest']['document_id'] for r in library.project_documents(stored, owner='public', historical=True)} == {p['document'] for p in pins}
    assert library.collection_record(stored['documents'][0], owner='public')['manifest']['name'] == 'Renamed'


def test_direct_document_survives_collection_removal_and_overlap_is_deduplicated(library):
    service, group, pins = collections(library)
    draft = project(library)
    draft['documents'] = [pins[1], collection_pin(group)]
    prepared = library.prepare('project', draft)
    assert len(library.project_documents(prepared.manifest, owner='public')) == 2
    service.register(service.prepare(group['manifest'] | {'documents': pins[:1]}), expected_digest=group['digest'])
    assert {document_pin(r)['document'] for r in library.project_documents(prepared.manifest, owner='public')} == {p['document'] for p in pins}


def test_changed_collection_invalidates_project_review(library):
    service, group, pins = collections(library)
    draft = project(library)
    draft['documents'] = [collection_pin(group)]
    prepared = library.prepare('project', draft)
    service.register(service.prepare(group['manifest'] | {'documents': pins[:1]}), expected_digest=group['digest'])
    with pytest.raises(ValueError, match='after review'):
        library.register(prepared)
    assert not library.list_configs('project')


def test_missing_or_cross_pod_collection_is_an_error(library, tmp_path):
    from test_collections import document
    from caiman.documents.collections import CollectionService
    service = CollectionService(library.store)
    pin = document(tmp_path, library.store, pod='alpha', name='Private')
    group = service.register(service.prepare(dict(name='Private', documents=[pin]), pod='alpha'))
    draft = project(library)
    draft['documents'] = [collection_pin(group)]
    with pytest.raises(ValueError, match='cross-pod'):
        library.prepare('project', draft)
    draft['documents'] = [dict(pod='public', collection='missing')]
    with pytest.raises(ValueError):
        library.prepare('project', draft)


@pytest.mark.parametrize('mode', ['truecolor', '256', 'standard'])
async def test_project_reopens_with_current_collection_members_and_unchanged_draft(library, mode, tmp_path, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    from rich.console import COLOR_SYSTEMS
    from textual.widgets import Button, Static
    from caiman.configurations.project_form import ProjectFormApp, ProjectDocumentCard
    service, group, pins = collections(library)
    draft = project(library)
    draft['documents'] = [collection_pin(group)]
    prepared = library.prepare('project', draft)
    library.register(prepared)
    service.register(service.prepare(group['manifest'] | {'name': 'Renamed', 'documents': pins[:1]}),
                     expected_digest=group['digest'])
    app = ProjectFormApp(original=prepared.manifest, root=library.store.root)
    app.console._color_system = COLOR_SYSTEMS[mode]
    async with app.run_test(size=(80, 40)) as pilot:
        await pilot.pause()
        card = app.query_one(ProjectDocumentCard)
        assert 'RENAMED' in card.query_one('.card-summary', Button).label.plain
        assert '1 document' in card.query_one('.card-summary', Button).label.plain
        assert app.collect() == prepared.manifest
        assert app.query_one('#review-changes', Button).disabled
        card.query_one('.card-summary', Button).press()
        await pilot.pause()
        assert app.focused is card.query_one('.collapse-card', Button)
        assert app.focused.styles.border_top[0] == 'double'
        text = str(card.query_one('.collection-members', Static).content)
        assert 'Alpha manual' in text and 'Beta manual' not in text
        (tmp_path / f'live-collection-{mode}.svg').write_text(app.export_screenshot())
        card.query_one('.remove-row', Button).press()
        await pilot.pause()
        assert app.collect()['documents'] == []
        assert not app.query_one('#review-changes', Button).disabled


def test_document_usage_tracks_current_membership(library):
    from caiman.documents.usages import DocumentUsages
    service, group, pins = collections(library)
    draft = project(library)
    draft['documents'] = [collection_pin(group)]
    library.register(library.prepare('project', draft))
    second = library.document_record(pins[1])
    assert any(r['kind'] == 'project' for r in DocumentUsages(library.store, second).prepare().usages)
    service.register(service.prepare(group['manifest'] | {'documents': pins[:1]}), expected_digest=group['digest'])
    usage = DocumentUsages(library.store, second).prepare()
    assert not usage.unknown
    assert not any(r['kind'] == 'project' for r in usage.usages)


def test_project_follows_new_collection_member(library, tmp_path):
    from test_collections import document
    service, group, pins = collections(library)
    draft = project(library)
    draft['documents'] = [collection_pin(group)]
    prepared = library.prepare('project', draft)
    library.register(prepared)
    added = document(tmp_path, library.store, name='New member')
    service.register(service.prepare(group['manifest'] | {'documents': [pins[1], added]}), expected_digest=group['digest'])
    current = library.project_documents(prepared.manifest, owner='public')
    assert {r['manifest']['name'] for r in current} == {'Beta manual', 'New member'}
    assert library.load_digest('project', prepared.digest) == prepared.manifest
