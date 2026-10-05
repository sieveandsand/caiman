import pytest
from textual.widgets import Button, Input, Select, Static

from caiman.dashboard.actions import DocumentCatalogApp
from caiman.documents.cards import CollectionCard, CollectionFrame
from caiman.documents.collection_tui import CollectionApp, MemberCard
from caiman.documents.collections import CollectionService
from caiman.storage.store import Store
from test_collections import document, draft


@pytest.mark.asyncio
async def test_create_review_edit_save_and_reopen_old_members(tmp_path):
    store = Store(tmp_path / 'store')
    pin = document(tmp_path, store)
    app = CollectionApp(root=store.root, pods=[])
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        app.query_one('#name', Input).value = 'Chip library'
        app.query_one('#description', Input).value = 'Documents for bring-up'
        app.query_one('#pod', Select).value = 'public'
        card = app.query_one(MemberCard)
        card.press()
        await pilot.pause()
        assert card.chosen
        await pilot.click('#review-save')
        await pilot.pause(0.25)
        assert CollectionService(store).documents.document_record(app.prepared['manifest']['documents'][0])['digest'] == pin['digest']
        assert not list(store.root.rglob('collections'))
        assert 'Manual' in str(app.query_one('#review', Static).content)
        await pilot.click('#edit-selection')
        assert app.query_one(MemberCard).chosen
        await pilot.click('#review-save')
        await pilot.pause(0.25)
        await pilot.click('#review-save')
        await pilot.pause()
    saved = app.return_value
    assert saved['manifest']['name'] == 'Chip library'
    from caiman.configurations.service import ConfigurationService
    from caiman.documents.edit_service import DocumentEditService
    selected = ConfigurationService(store).list_documents()[0]
    edits = DocumentEditService(store)
    updated = edits.register(selected, edits.prepare(selected, dict(selected['manifest'], name='Renamed')))
    current_digest = CollectionService(store).list_collections()[0]['digest']
    assert current_digest == saved['digest']
    # The same collection snapshot shows current metadata for its fixed member.
    edit = CollectionApp(root=store.root, pods=[], record=saved)
    async with edit.run_test(size=(65, 30)) as pilot:
        await pilot.pause()
        cards = list(edit.query(MemberCard))
        assert len(cards) == 1
        assert [c.record['digest'] for c in cards if c.chosen] == [updated['digest']]
        assert not edit.query('#version')
        await pilot.click('#cancel')
    assert CollectionService(store).list_collections()[0]['digest'] == current_digest


@pytest.mark.asyncio
async def test_empty_validation_and_cancel_do_not_write(tmp_path):
    app = CollectionApp(root=tmp_path / 'store', pods=[])
    async with app.run_test(size=(65, 30)) as pilot:
        await pilot.pause()
        assert 'No existing documents' in str(app.query_one('#status', Static).content)
        await pilot.click('#review-save')
        await pilot.pause(0.25)
        assert 'Supply a collection name' in str(app.query_one('#status', Static).content)
        app.query_one('#pod', Select).value = 'public'
        app.query_one('#name', Input).value = 'Empty'
        await pilot.click('#review-save')
        await pilot.pause()
        assert 'at least one existing document' in str(app.query_one('#status', Static).content)
        await pilot.click('#cancel')
    assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_collection_stack_is_persistent_focus_does_not_resize(tmp_path):
    store = Store(tmp_path / 'store')
    pin = document(tmp_path, store)
    service = CollectionService(store)
    saved = service.register(service.prepare(draft([pin])))
    app = DocumentCatalogApp(root=store.root, pods=[])
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        card = app.query_one(CollectionCard)
        frame = card.parent
        assert isinstance(frame, CollectionFrame)
        assert all(back.visible for back in frame.query('.stack-back'))
        dimensions = frame.region
        card.focus()
        await pilot.pause()
        assert frame.has_class('selected')
        assert frame.query_one('.card-shadow').visible
        assert '⠢' in app.export_screenshot() or '⠔' in app.export_screenshot()
        app.query_one('#add-document').focus()
        await pilot.pause()
        assert not frame.has_class('selected')
        assert frame.region == dimensions
        assert all(back.visible for back in frame.query('.stack-back'))
        await pilot.resize_terminal(65, 30)
        await pilot.pause()
        assert frame.region.right <= 65
        assert frame.region.height == card.region.height + 3
        card.focus()
        await pilot.press('enter')
    assert app.return_value['collection']['digest'] == saved['digest']


@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
async def test_collection_review_tracks_edits_and_reverted_selection(tmp_path, color_system):
    from rich.console import COLOR_SYSTEMS

    store = Store(tmp_path / 'store')
    pin = document(tmp_path, store)
    service = CollectionService(store)
    saved = service.register(service.prepare(draft([pin])))
    app = CollectionApp(root=store.root, record=saved)
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        review = app.query_one('#review-save', Button)
        assert review.disabled
        name = app.query_one('#name', Input)
        original = name.value
        name.value = 'Changed'
        await pilot.pause()
        assert not review.disabled
        name.value = original
        await pilot.pause()
        assert review.disabled
        card = app.query_one(MemberCard)
        card.press()
        await pilot.pause()
        assert not review.disabled
        card.press()
        await pilot.pause()
        assert review.disabled
        app.query_one('#cancel', Button).focus()
        await pilot.pause()
        assert card.chosen
        assert '✓ Included' in card.label.plain
