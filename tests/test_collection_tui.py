import pytest
from textual.widgets import Button, Collapsible, Input, Select, SelectionList, Static

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
        assert not app.query(MemberCard)
        app.query_one('#choose-documents', Button).press()
        await pilot.pause()
        app.screen.query_one(SelectionList).select_all()
        await pilot.pause()
        app.screen.query_one('#picker-attach', Button).press()
        await pilot.pause()
        assert len(app.query(MemberCard)) == 1
        await pilot.click('#review-save')
        await pilot.pause(0.25)
        assert CollectionService(store).documents.document_record(app.prepared['manifest']['documents'][0])['digest'] == pin['digest']
        assert not list(store.root.rglob('collections'))
        assert 'Manual' in str(app.query_one('#review', Static).content)
        await pilot.click('#edit-selection')
        assert len(app.query(MemberCard)) == 1
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
        assert [c.record['digest'] for c in cards] == [updated['digest']]
        assert not edit.query('#version')
        await pilot.click('#cancel')
    assert CollectionService(store).list_collections()[0]['digest'] == current_digest


@pytest.mark.asyncio
async def test_empty_validation_and_cancel_do_not_write(tmp_path):
    app = CollectionApp(root=tmp_path / 'store', pods=[])
    async with app.run_test(size=(65, 30)) as pilot:
        await pilot.pause()
        assert 'No documents selected' in str(app.query_one('#selection-count', Static).content)
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


@pytest.mark.parametrize('size', [(70, 30), (110, 40)])
async def test_collection_opens_at_top_and_navigation_can_scroll(tmp_path, size):
    store = Store(tmp_path / 'store')
    pins = [document(tmp_path, store, name=f'Manual {number}') for number in range(5)]
    service = CollectionService(store)
    saved = service.register(service.prepare(draft(pins)))
    app = CollectionApp(root=store.root, record=saved)
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        body = app.query_one('#body')
        assert body.max_scroll_y > 0
        assert body.scroll_y == 0
        assert app.focused is app.query_one('#name', Input)
        await pilot.press('j')
        await pilot.pause()
        assert app.focused is app.query_one('#description', Input)
        assert body.scroll_y == 0
        cards = list(app.query(MemberCard))
        cards[-1].query_one('.card-summary', Button).focus()
        await pilot.pause(0.3)
        assert body.scroll_y > 0
        assert body.content_region.contains_region(cards[-1].query_one('.card-summary').region)
        offset = body.scroll_y
        app.query_one('#cancel').focus()
        await pilot.pause()
        assert body.scroll_y == offset


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
async def test_collection_review_tracks_edits_and_reverted_selection(tmp_path, color_system, monkeypatch):
    from rich.console import COLOR_SYSTEMS

    monkeypatch.delenv('NO_COLOR', raising=False)
    store = Store(tmp_path / 'store')
    pin = document(tmp_path, store, pod='alpha')
    document(tmp_path, store, name='Not included')
    service = CollectionService(store)
    saved = service.register(service.prepare(draft([pin], 'alpha')))
    app = CollectionApp(root=store.root, record=saved, pod='public')
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        review = app.query_one('#review-save', Button)
        assert review.disabled
        pod = app.query_one('#pod', Static)
        assert not pod.can_focus
        assert str(pod.content) == store.pod_name(saved['pod'])
        assert app.collect()['pod'] == saved['pod']
        app.query_one('#choose-documents', Button).press()
        await pilot.pause()
        assert app.screen.owner == saved['pod']
        await pilot.press('escape')
        await pilot.pause()
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
        assert len(app.query(MemberCard)) == 1
        summary = card.query_one('.card-summary', Button)
        assert 'Included' not in summary.label.plain
        assert 'Enter to remove' not in summary.label.plain
        remove = card.query_one('.remove-member', Button)
        assert not card.query_one('.card-editor').display
        add = app.query_one('#choose-documents', Button)
        assert add.has_class('add-card')
        assert '╋' in add.label.plain
        assert app.query_one('#documents').children[-1] is add.parent
        summary.focus()
        await pilot.press('enter')
        await pilot.pause()
        assert card.has_class('expanded')
        assert card.query_one('.card-editor').display
        assert app.focused is card.query_one('.collapse-card')
        await pilot.press('enter')
        await pilot.pause()
        assert len(app.query(MemberCard)) == 1
        assert review.disabled
        assert not card.has_class('expanded')
        assert app.focused is summary
        await pilot.press('enter')
        await pilot.pause()
        remove.focus()
        await pilot.pause()
        assert len(app.query(MemberCard)) == 1
        assert remove.styles.border_top[0] == 'double'
        await pilot.press('enter')
        await pilot.pause()
        assert not review.disabled
        assert not app.query(MemberCard)
        assert app.collect()['documents'] == []
        assert app.focused is app.query_one('#choose-documents')
        app.query_one('#choose-documents', Button).press()
        await pilot.pause()
        picker = app.screen
        index = next(i for i, record in enumerate(picker.records) if record['pod'] == 'alpha')
        picker.query_one(SelectionList).select(index)
        await pilot.pause()
        picker.query_one('#picker-attach', Button).press()
        await pilot.pause()
        assert review.disabled
        card = app.query_one(MemberCard)
        app.query_one('#cancel', Button).focus()
        await pilot.pause()
        assert len(app.query(MemberCard)) == 1
        assert 'Included' not in card.query_one('.card-summary', Button).label.plain
        section = app.query_one(Collapsible)
        section.collapsed = True
        await pilot.pause()
        section.collapsed = False
        await pilot.pause()
        assert len(app.query(MemberCard)) == 1
        assert review.disabled


@pytest.mark.parametrize('size', [(70, 40), (110, 50)])
@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
async def test_expanded_card_keyboard_visits_actions_without_losing_focus(tmp_path, size, color_system, monkeypatch):
    from rich.console import COLOR_SYSTEMS

    monkeypatch.delenv('NO_COLOR', raising=False)
    store = Store(tmp_path / 'store')
    pins = [document(tmp_path, store, name=f'Manual {i}') for i in range(3)]
    service = CollectionService(store)
    saved = service.register(service.prepare(draft(pins)))
    app = CollectionApp(root=store.root, record=saved)
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        card, neighbour, _ = app.query(MemberCard)
        summary = card.query_one('.card-summary', Button)
        remove = card.query_one('.remove-member', Button)
        done = card.query_one('.collapse-card', Button)
        original = app.collect()
        summary.focus()
        await pilot.press('enter')
        await pilot.pause(0.3)
        assert app.focused is done
        body = app.query_one('#body')
        for previous, forward in [('k', 'j'), ('h', 'l'), ('shift+tab', 'tab')]:
            offset = body.scroll_y
            await pilot.press(previous)
            await pilot.pause()
            assert app.focused is remove
            assert card.has_class('selected')
            assert card.query_one('.card-shadow').visible
            assert body.scroll_y == offset
            await pilot.press(previous)
            await pilot.pause(0.3)
            assert app.focused is summary
            assert card.has_class('selected')
            await pilot.press(forward)
            await pilot.pause(0.3)
            assert app.focused is remove
            assert card.has_class('selected')
            await pilot.press(forward)
            await pilot.pause(0.3)
            assert app.focused is done
            assert card.has_class('selected')
            assert app.collect() == original
            assert app.query_one('#review-save', Button).disabled
        await pilot.press('j')
        await pilot.pause(0.3)
        assert app.focused is neighbour.query_one('.card-summary')
        assert not card.has_class('selected')
        assert neighbour.has_class('selected')
        await pilot.press('shift+tab')
        await pilot.pause(0.3)
        assert app.focused is done
        await pilot.press('enter')
        await pilot.pause()
        assert not card.has_class('expanded')
        assert app.focused is summary
        assert card.has_class('selected')
        await pilot.press('tab')
        await pilot.pause()
        assert app.focused is neighbour.query_one('.card-summary')
        assert app.collect() == original
