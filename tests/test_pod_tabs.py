"""Pod switching behaves consistently across all catalog galleries."""
import pytest
from textual.widgets import Select, Tabs

from caiman.boards.gallery import BoardGalleryApp, BoardCard
from caiman.configurations.gallery import ProjectGalleryApp, ProjectCard
from caiman.configurations.service import ConfigurationService
from caiman.dashboard.actions import DocumentCatalogApp
from caiman.dashboard.onboarding import SetupApp
from caiman.documents.cards import DocumentCard
from caiman.documents.ingest import prepare_document
from caiman.storage.store import Store


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['document', 'board', 'project'])
async def test_pod_tabs_keyboard_mouse_empty_and_selection(tmp_path, kind):
    store = Store(tmp_path / 'store')
    service = ConfigurationService(store)
    for pod in ('alpha', 'beta'):
        store.pods.ensure(pod)
        board = service.prepare('board', {'board': 'same', 'version': 'A', 'parts': [
            {'role': 'mcu', 'part': 'chip', 'vendor': 'Example', 'documents': []}]}, pod=pod)
        service.register(board)
        service.register(service.prepare('project', {
            'project': 'same', 'version': 'A', 'customer': 'Example', 'spec_set': 'A',
            'boards': [{'name': 'same', 'version': 'A', 'pod': pod}],
            'documents': [], 'features': []}, pod=pod))
        source = tmp_path / 'manual.md'
        source.write_text('# Manual\n\nExample\n')
        store.register(prepare_document(source, {
            'name': 'same', 'issuer': 'Example', 'part': 'chip', 'version': 'A'}, pod=pod))
    store.pods.ensure('empty')
    if kind == 'document':
        app, card_type = DocumentCatalogApp(root=store.root), DocumentCard
    elif kind == 'board':
        app, card_type = BoardGalleryApp(store.root), BoardCard
    else:
        app, card_type = ProjectGalleryApp(root=store.root), ProjectCard
    before = {p: p.read_bytes() for p in store.root.rglob('*') if p.is_file()}
    async with app.run_test(size=(110, 35)) as pilot:
        await pilot.pause()
        tabs = app.query_one('#pod-tabs', Tabs)
        hints = list(app.query('.key-hint'))
        assert len(hints) == 1
        hint = str(hints[0].content)
        assert hint.count('/ next pod') == 1
        assert 'h/l tabs' not in hint and 'j cards' not in hint
        assert set(app.tab_pods.values()) == {'public', 'alpha', 'beta', 'empty'}
        tabs.active = next(key for key, pod in app.tab_pods.items() if pod == 'alpha')
        await pilot.pause()
        await pilot.press('j')
        assert app.active_pod == 'alpha'
        assert app.focused is app.query_one(card_type)
        # The literal slash shown in the guide works from card focus.
        await pilot.press('/')
        await pilot.pause()
        assert app.active_pod == 'beta'
        assert app.query_one(card_type).record['pod'] == 'beta'
        assert app.focused is tabs
        await pilot.press('h')
        await pilot.pause()
        assert app.active_pod == 'alpha'
        await pilot.press('right')
        await pilot.pause()
        assert app.active_pod == 'beta'
        await pilot.press('l')
        await pilot.pause()
        assert app.active_pod == 'empty'
        assert not app.query(card_type)
        # Empty pods retain creation controls, carrying their owning pod.
        add_id = 'add-document' if kind == 'document' else f'add-{kind}'
        assert app.query_one(f'#{add_id}')
        # Repeated changes wrap and keep keyboard focus usable.
        for _ in app.tab_pods:
            await pilot.press('right_square_bracket')
        await pilot.pause()
        assert app.active_pod == 'empty'
        await pilot.press('left_square_bracket')
        await pilot.pause()
        assert app.active_pod == 'beta'
        # Refresh preserves selection; mouse switching uses the same filter.
        await app.refresh_catalog()
        await pilot.pause()
        assert app.active_pod == 'beta'
        alpha_id = next(key for key, value in app.tab_pods.items() if value == 'alpha')
        await pilot.click(f'#{alpha_id}')
        await pilot.pause()
        assert app.active_pod == 'alpha'
        await pilot.press('j')
        await pilot.pause()
        assert app.focused is app.query_one(card_type)
        await pilot.press('enter')
    selected = app.return_value['document'] if kind == 'document' else app.return_value
    assert selected['pod'] == 'alpha'
    assert {p: p.read_bytes() for p in store.root.rglob('*') if p.is_file()} == before


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['board', 'project'])
async def test_empty_pod_add_uses_selected_pod(tmp_path, kind):
    store = Store(tmp_path)
    store.pods.ensure('empty')
    app = (BoardGalleryApp(tmp_path, pod='empty') if kind == 'board' else
           ProjectGalleryApp(root=tmp_path, pod='empty'))
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press('enter')
    assert app.return_value == {'action': 'add', 'pod': 'empty'}
    setup = SetupApp(kind=kind, store_root=tmp_path, pod=app.return_value['pod'])
    async with setup.run_test() as pilot:
        await pilot.pause()
        if kind == 'project':
            assert setup.project_pod == 'empty'
            assert not setup.query('Select#pod')
        else:
            assert setup.query_one('#pod', Select).value == 'empty'
