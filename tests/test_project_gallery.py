from copy import deepcopy

import pytest
from textual.containers import Grid
from textual.widgets import Static

from caiman.configurations.gallery import ProjectCard, ProjectGalleryApp
from caiman.configurations.service import ConfigurationService
from caiman.storage.store import Store


def register_project(service, name, compartments):
    prepared = service.prepare('project', {
        'project': name, 'version': 'release / B', 'customer': 'Example customer',
        'compartments': compartments, 'boards': [{'name': 'demo', 'version': 'A'}],
        'spec_set': 'Specification A', 'documents': [], 'features': [],
    })
    service.register(prepared)
    return prepared


@pytest.mark.asyncio
async def test_project_cards_scope_layout_focus_and_selection(tmp_path):
    service = ConfigurationService(Store(tmp_path))
    service.register(service.prepare('board', {
        'board': 'demo', 'version': 'A',
        'parts': [{'role': 'main', 'vendor': 'vendor', 'part': 'chip', 'documents': []}],
    }))
    register_project(service, 'first', ['alpha'])
    register_project(service, 'second', ['alpha'])
    shared = register_project(service, 'shared', ['alpha', 'beta'])
    register_project(service, 'hidden', ['secret'])
    app = ProjectGalleryApp(root=tmp_path, compartments=['alpha', 'beta'])
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        assert not app.query('#compartments')
        assert [str(widget.content) for widget in app.query('.compartment-heading')] == ['alpha', 'alpha, beta']
        cards = list(app.query(ProjectCard))
        assert len(cards) == 3
        assert all(grid.styles.grid_size_columns == 2 for grid in app.query(Grid))
        assert '0 Docs · 0 Features\n\nExample customer' in cards[0].label.plain
        assert 'Board: demo @ A' in cards[0].label.plain
        assert 'sha256' not in cards[0].label.plain
        assert app.focused is cards[0]
        regions = [card.virtual_region for card in cards]
        await pilot.press('l')
        assert app.focused is cards[1]
        assert not cards[0].parent.has_class('selected')
        assert cards[1].parent.has_class('selected')
        assert regions == [card.virtual_region for card in cards]
        await pilot.resize_terminal(65, 30)
        await pilot.pause()
        assert all(grid.styles.grid_size_columns == 1 for grid in app.query(Grid))
        assert all(card.region.right <= 65 for card in cards)
        cards[2].focus()
        await pilot.press('enter')
    assert app.return_value == {'manifest': shared.manifest, 'digest': shared.digest}


@pytest.mark.asyncio
async def test_empty_project_gallery_does_not_create_store(tmp_path):
    root = tmp_path / 'absent'
    app = ProjectGalleryApp(root=root)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert not app.query(ProjectCard)
        assert 'No projects' in str(app.query_one('#gallery-status', Static).content)
        assert app.focused.id == 'add-project'
        await pilot.press('q')
    assert app.return_value is None
    assert not root.exists()


def test_project_card_preserves_fallback_identity():
    record = {'manifest': {'project': 'Mixed ß project', 'version': 'opaque / label',
              'customer': 'Customer', 'boards': [{'name': 'Board', 'version': 'A'}],
              'documents': [{}, {}], 'features': [{}]}}
    before = deepcopy(record)
    card = ProjectCard(record, index=0)
    card.format_card(30)
    assert 'Mixed ß project' in card.label.plain
    assert '  [ opaque / label ]' in card.label.plain
    assert '2 Docs · 1 Features' in card.label.plain
    assert record == before


def test_project_card_lists_every_pinned_board_and_reads_v1():
    boards = [{'name': 'main', 'version': 'A'}, {'name': 'main', 'version': 'B'}, {'name': 'io', 'version': '1'}]
    card = ProjectCard({'manifest': {'project': 'p', 'version': 'v', 'customer': 'c', 'boards': boards}}, index=0)
    card.format_card(60)
    for board in boards:
        assert f"Board: {board['name']} @ {board['version']}" in card.label.plain
    legacy = {'schema': 'caiman.project/1', 'project': 'p', 'version': 'v', 'customer': 'c',
              'board': {'name': 'old', 'version': '1'}}
    card = ProjectCard({'manifest': legacy}, index=0)
    card.format_card(60)
    assert 'Board: old @ 1' in card.label.plain


@pytest.mark.asyncio
async def test_e_opens_the_focused_project_for_editing(tmp_path):
    service = ConfigurationService(Store(tmp_path))
    service.register(service.prepare('board', {
        'board': 'demo', 'version': 'A',
        'parts': [{'role': 'main', 'vendor': 'vendor', 'part': 'chip', 'documents': []}],
    }))
    project = register_project(service, 'first', ['alpha'])
    app = ProjectGalleryApp(root=tmp_path, compartments=['alpha'])
    async with app.run_test(size=(120, 45)) as pilot:
        await pilot.pause()
        await pilot.press('e')
    assert app.return_value == {'manifest': project.manifest, 'digest': project.digest}


@pytest.mark.asyncio
async def test_empty_project_gallery_add_card_requests_creation(tmp_path):
    app = ProjectGalleryApp(root=tmp_path / 'absent')
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await pilot.press('enter')
    assert app.return_value == 'add'
    assert not (tmp_path / 'absent').exists()
