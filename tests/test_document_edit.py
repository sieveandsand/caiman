from copy import deepcopy
from dataclasses import replace

import pytest
from textual.containers import Grid, VerticalScroll
from textual.widgets import Button, Input, Static

from caiman.configurations.service import ConfigurationService
from caiman.documents.edit import DocumentEditReviewApp, edit_document
from caiman.documents.edit_service import DocumentEditService
from caiman.documents.form import DetailCard, DocumentFormApp
from caiman.documents.ingest import digest, prepare_document
from caiman.documents.models import canonical_json
from caiman.storage.store import Store, StoreError


@pytest.fixture
def setup(tmp_path):
    source = tmp_path / 'manual.md'
    source.write_bytes(b'# Synthetic manual\r\nREQ-123: Start correctly.\r\n')
    store = Store(tmp_path / 'store')
    store.register(prepare_document(source, {
        'name': 'Reference Manual', 'description': 'Registers and behavior',
        'issuer': 'synthetic', 'part': 'chip', 'version': 'Release / A',
        'pod': ('alpha'),
        'source': {'pages': 12, 'sha256': 'a' * 64},
        'converter': {'name': 'Synthetic', 'version': '1', 'hosted': False},
        'silicon_revisions': ['mask-A', 'mask-B'],
        'requirements': {'pattern': r'^REQ-\d+$'},
    }))
    selection = ConfigurationService(store).list_documents(pods={'alpha'})[0]
    return DocumentEditService(store, pods={'alpha'}), selection, source


def snapshot(store):
    return {path.relative_to(store.root): path.read_bytes() for path in store.root.rglob('*') if path.is_file()}


def test_edit_stored_metadata_without_source_preserves_bytes_and_old_pin(setup):
    service, selection, source = setup
    original = deepcopy(selection['manifest'])
    # Metadata editing must not require the original import path to still exist.
    source.rename(source.with_suffix('.moved'))
    assert service.prepare(selection, original).digest == selection['digest']
    draft = deepcopy(original)
    draft['description'] = 'Updated purpose'
    before = snapshot(service.store)
    prepared = service.prepare(selection, draft)
    assert snapshot(service.store) == before
    registered = service.register(selection, prepared)
    assert registered['manifest']['files'] == original['files']
    assert registered['manifest']['ingested_at'] == original['ingested_at']
    assert service.store.read_manifest('alpha', selection['digest']) == original
    assert ConfigurationService(service.store).list_documents(pods={'alpha'})[0] == registered
    assert service.store.read_blob('alpha', 'sha256:' + original['files'][0]['sha256']).startswith(b'# Synthetic manual\r\n')
    with pytest.raises(StoreError, match='changed since opening'):
        service.register(selection, prepared)


@pytest.mark.parametrize('change', [
    lambda draft: draft.update(pod='public'),
    lambda draft: draft.pop('files'),
    lambda draft: draft['files'][0].update(size=0),
    lambda draft: draft.update(original_filename='other.md'),
    lambda draft: draft.update(requirements={'pattern': '^MISSING$'}),
])
def test_protected_fields_and_invalid_requirement_edits_never_write(setup, change):
    service, selection, _ = setup
    before = snapshot(service.store)
    draft = deepcopy(selection['manifest'])
    change(draft)
    with pytest.raises(ValueError):
        service.prepare(selection, draft)
    assert snapshot(service.store) == before


def test_editor_cannot_load_private_document_outside_scope(setup):
    service, selection, _ = setup
    assert DocumentEditService(service.store).original(selection) == selection['manifest']


def test_rename_collision_does_not_replace_another_document(setup):
    service, selection, _ = setup
    draft = {**selection['manifest'], 'version': 'Another label'}
    service.register(selection, service.prepare(selection, draft))
    before = snapshot(service.store)
    with pytest.raises(StoreError, match='already uses this name and version'):
        service.register(selection, service.prepare(selection, draft))
    assert snapshot(service.store) == before


def test_mutated_review_is_rejected_without_writes(setup):
    service, selection, _ = setup
    prepared = service.prepare(selection, {**selection['manifest'], 'description': 'Reviewed'})
    prepared.manifest['description'] = 'Not reviewed'
    before = snapshot(service.store)
    with pytest.raises(StoreError, match='changed after review'):
        service.register(selection, prepared)
    assert snapshot(service.store) == before


@pytest.mark.asyncio
async def test_legacy_document_roundtrip_retains_opaque_version_and_hidden_fields(tmp_path):
    source = tmp_path / 'manual.md'
    source.write_text('# Synthetic manual\nContent.\n')
    prepared = prepare_document(source, {'issuer': 'synthetic', 'part': 'chip',
        'version': '  Rev / A  ', 'doc_type': 'manual', 'structure': 'prose',
        'pod': 'public'})
    prepared.manifest['schema'] = 'caiman.document.v1'
    prepared = replace(prepared, manifest_digest=digest(canonical_json(prepared.manifest)))
    store = Store(tmp_path / 'store')
    store.register(prepared)
    selection = ConfigurationService(store).list_documents()[0]
    service = DocumentEditService(store)
    app = DocumentFormApp(original=selection['manifest'])
    async with app.run_test(size=(110, 45)) as pilot:
        await pilot.pause()
        assert app.collect() == selection['manifest']
        assert service.prepare(selection, app.collect()).digest == selection['digest']
        app.query_one('#document-description', Input).value = 'Legacy manual description'
        edited = service.prepare(selection, app.collect())
        assert edited.manifest['version'] == '  Rev / A  '
        assert edited.manifest['doc_type'] == 'manual'
        assert edited.manifest['structure'] == 'prose'
        assert edited.manifest['schema'] == 'caiman.document.v3'


@pytest.mark.asyncio
async def test_form_roundtrip_cards_draft_retention_and_responsive_layout(setup):
    service, selection, _ = setup
    app = DocumentFormApp(original=selection['manifest'], selection=selection)
    before = snapshot(service.store)
    async with app.run_test(size=(120, 55)) as pilot:
        await pilot.pause()
        assert app.collect() == selection['manifest']
        assert all(g.styles.grid_size_columns == 2 for g in app.query(Grid))
        assert 'alpha' in str(app.query_one('#document-pod', Static).content)
        assert all(not card.has_class('expanded') for card in app.query(DetailCard))
        source = app.query_one('#detail-source', DetailCard)
        source.query_one('.card-summary', Button).press()
        await pilot.pause()
        assert source.has_class('expanded')
        assert app.focused is source.query_one('.field-sha256', Input)
        source.query_one('.field-pages', Input).value = 'not a number'
        source.query_one('.collapse-card', Button).press()
        await pilot.pause()
        assert not source.has_class('expanded')
        assert app.collect()['source']['pages'] == 'not a number'
        source.query_one('.card-summary', Button).press()
        await pilot.pause()
        assert source.query_one('.field-pages', Input).value == 'not a number'
        assert app.collect()['converter'] == selection['manifest']['converter']
        await pilot.resize_terminal(65, 30)
        await pilot.pause()
        assert all(g.styles.grid_size_columns == 1 for g in app.query(Grid))
        assert all(c.region.right <= 65 for c in app.query(DetailCard))
        app.query_one('#cancel', Button).press()
    assert snapshot(service.store) == before


@pytest.mark.asyncio
async def test_visible_card_focus_keeps_scroll_stable_and_typing_is_preserved(setup):
    _, selection, _ = setup
    app = DocumentFormApp(original=selection['manifest'])
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        first = app.query_one('#detail-applicability', DetailCard)
        second = app.query_one('#detail-requirements', DetailCard)
        first.query_one('.card-summary', Button).focus()
        await pilot.pause()
        body = app.query_one('#body', VerticalScroll)
        before = body.scroll_y
        await pilot.press('l')
        await pilot.pause()
        assert app.focused is second.query_one('.card-summary', Button)
        assert body.scroll_y == before
        assert not first.has_class('selected') and second.has_class('selected')
        await pilot.press('enter')
        await pilot.pause()
        field = second.query_one(Input)
        field.value = ''
        await pilot.press('i', 'h', 'j', 'k', 'l', 'escape')
        assert field.value == 'hjkl'


@pytest.mark.asyncio
@pytest.mark.parametrize('save', [False, True])
async def test_review_requires_explicit_save(setup, save):
    service, selection, _ = setup
    prepared = service.prepare(selection, {**selection['manifest'], 'description': 'Edited description'})
    before = snapshot(service.store)
    app = DocumentEditReviewApp(service=service, selection=selection, prepared=prepared)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        assert snapshot(service.store) == before
        app.query_one('#register' if save else '#cancel', Button).press()
        for _ in range(30):
            if not app.is_running:
                break
            await pilot.pause(0.025)
    if save:
        assert app.return_value['digest'] == prepared.digest
        assert service.store.read_manifest('alpha', selection['digest']) == selection['manifest']
    else:
        assert app.return_value is None and snapshot(service.store) == before


def test_invalid_and_unchanged_drafts_return_to_form_with_draft_intact(setup, monkeypatch):
    import caiman.documents.edit as editing
    service, selection, _ = setup
    invalid = deepcopy(selection['manifest'])
    invalid['source']['pages'] = 'bad'
    outcomes = [('review', invalid), ('review', selection['manifest']), None]
    seen = []
    class Form:
        def __init__(self, **kwargs):
            seen.append(kwargs)
        def run(self):
            return outcomes.pop(0)
    monkeypatch.setattr(editing, 'DocumentFormApp', Form)
    monkeypatch.setattr(editing, 'DocumentEditReviewApp', lambda **kwargs: pytest.fail('Unexpected review'))
    before = snapshot(service.store)
    assert edit_document(service.store.root, selection, pods={'alpha'}) is None
    assert seen[1]['draft'] == invalid
    assert 'source.pages' in seen[1]['message']
    assert 'nothing to register' in seen[2]['message']
    assert snapshot(service.store) == before
