"""The board gallery shows concise summaries and returns exact editor selections."""


import pytest
from textual.widgets import Static

from caiman.boards.gallery import BoardCard, BoardGalleryApp
from caiman.configurations.service import ConfigurationService
from caiman.storage.store import Store


def register_board(root, name='alpha', version='A', parts=1):
    service = ConfigurationService(Store(root))
    draft = {
        'board': name, 'version': version,
        'parts': [{'role': f'role-{index:02d}', 'vendor': 'synthetic', 'part': f'chip-{index}',
                   'silicon_revision': 'mask-A', 'aliases': {'refdes': f'U{index + 1}'}, 'documents': []}
                  for index in range(parts)],
        'links': [],
    }
    prepared = service.prepare('board', draft)
    service.register(prepared)
    return {'manifest': prepared.manifest, 'digest': prepared.digest}


async def ready(pilot, app):
    for _ in range(100):
        if list(app.query(BoardCard)):
            await pilot.pause()
            return
        await pilot.pause(0.02)
    pytest.fail(str(app.query_one('#gallery-status', Static).render()))


@pytest.mark.asyncio
async def test_gallery_two_columns_complete_parts_and_keyboard_edit(tmp_path):
    root = tmp_path / 'store'
    alpha = register_board(root, 'alpha', parts=2)
    beta = register_board(root, 'beta', parts=3)
    before = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    app = BoardGalleryApp(root)
    async with app.run_test(size=(110, 40)) as pilot:
        await ready(pilot, app)
        cards = list(app.query(BoardCard))
        assert len(cards) == 2
        assert cards[0].region.y == cards[1].region.y
        assert cards[0].region.x < cards[1].region.x
        for card, count in zip(cards, (2, 3)):
            text = card.label.plain
            for index in range(count):
                assert f'chip-{index}' in text
                assert f'role-{index:02d}' not in text
                assert f'refdes U{index + 1}' not in text
            assert 'Silicon mask-A' not in text
            assert f'{count} Parts · 0 Links · 0 Docs' in text
            assert '  [ A ]' in text
            assert 'Version A' not in text
        await pilot.press('l', 'e')
    assert app.return_value['digest'] == beta['digest']
    assert app.return_value['digest'] != alpha['digest']
    after = {str(path.relative_to(root)): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    assert after == before


@pytest.mark.asyncio
async def test_gallery_marks_no_board_as_current(tmp_path):
    """There is no default board: every card is an equal choice."""
    root = tmp_path / 'store'
    register_board(root, 'alpha')
    register_board(root, 'beta')
    app = BoardGalleryApp(root)
    async with app.run_test(size=(80, 30)) as pilot:
        await ready(pilot, app)
        cards = list(app.query(BoardCard))
        assert len(cards) == 2
        assert app.focused is cards[0]
        assert not any('Current selection' in card.label.plain for card in cards)


@pytest.mark.asyncio
async def test_long_part_list_is_scrollable_and_cancel_writes_nothing(tmp_path):
    root = tmp_path / 'store'
    register_board(root, parts=15)
    app = BoardGalleryApp(root)
    async with app.run_test(size=(80, 24)) as pilot:
        await ready(pilot, app)
        card = app.query_one(BoardCard)
        assert 'chip-14' in card.label.plain
        assert 'role-14' not in card.label.plain
        body = app.query_one('#body')
        assert card.region.height > body.region.height
        before = body.scroll_y
        await pilot.press('pagedown')
        await pilot.pause()
        assert body.scroll_y > before
        await pilot.press('q')
    assert app.return_value is None


@pytest.mark.asyncio
async def test_empty_gallery_has_actionable_message(tmp_path):
    root = tmp_path / 'absent-store'
    app = BoardGalleryApp(root)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        assert 'No boards' in str(app.query_one('#gallery-status', Static).render())
        assert not list(app.query(BoardCard))
        assert app.focused.id == 'add-board'
        await pilot.press('q')
    assert not root.exists()


@pytest.mark.asyncio
async def test_add_card_follows_every_board_and_requests_creation(tmp_path):
    root = tmp_path / 'store'
    register_board(root, 'alpha', parts=3)
    register_board(root, 'beta', parts=1)
    app = BoardGalleryApp(root)
    async with app.run_test(size=(110, 30)) as pilot:
        await ready(pilot, app)
        faces = list(app.query('#gallery .card-face'))
        assert [face.id for face in faces][-1] == 'add-board' and len(faces) == 3
        add = faces[-1]
        # Third card wraps to the second row, sized to its own content.
        assert add.region.y > faces[0].region.y and add.region.x == faces[0].region.x
        assert 'Add board' in add.label.plain and '╋' in add.label.plain
        await pilot.press('j')
        assert app.focused is add
        assert add.parent.has_class('selected')
        await pilot.press('enter')
    assert app.return_value == 'add'


@pytest.mark.asyncio
async def test_different_height_cards_navigate_by_grid_row(tmp_path):
    root = tmp_path / 'store'
    register_board(root, 'alpha', parts=15)
    register_board(root, 'beta', parts=1)
    register_board(root, 'gamma', parts=2)
    app = BoardGalleryApp(root)
    async with app.run_test(size=(110, 30)) as pilot:
        await ready(pilot, app)
        assert app.focused.record['manifest']['board'] == 'alpha'
        await pilot.press('l')
        assert app.focused.record['manifest']['board'] == 'beta'
        await pilot.press('k')
        assert app.focused.record['manifest']['board'] == 'beta'
        await pilot.press('h', 'j')
        assert app.focused.record['manifest']['board'] == 'gamma'
        await pilot.press('k')
        assert app.focused.record['manifest']['board'] == 'alpha'


@pytest.mark.asyncio
async def test_board_card_text_is_left_aligned(tmp_path):
    """Button centres its label by default; a card is a left-aligned document."""
    root = tmp_path / 'store'
    register_board(root, 'alpha', parts=2)
    app = BoardGalleryApp(root)
    async with app.run_test(size=(110, 40)) as pilot:
        await ready(pilot, app)
        card = next(iter(app.query(BoardCard)))
        assert card.styles.text_align == 'left'


def test_card_counts_board_and_part_docs_and_omits_details():
    record = {'digest': 'sha256:' + 'f' * 64, 'manifest': {
        'board': 'falcon', 'version': 'Rev B', 'vendor': 'hidden-vendor',
        'notes': 'Hidden board note', 'documents': [{'ref': 'board-guide'}],
        'parts': [{'part': 'mcu-1', 'role': 'hidden-role', 'vendor': 'hidden-vendor',
                   'notes': 'Hidden part note', 'silicon_revision': 'hidden-mask',
                   'aliases': {'refdes': 'hidden-refdes'}, 'documents': [{'ref': 'manual'}, {'ref': 'errata'}]}],
        'links': [{'name': 'hidden-link', 'between': ['a', 'b']}],
    }}
    card = BoardCard(record, index=0)
    height = card.format_card(48)
    text = card.label.plain
    assert 'FALCON' in text
    assert '[ Rev B ]' in text
    assert 'falcon' not in text and 'Version Rev B' not in text
    assert '1 Parts · 1 Links · 3 Docs' in text
    assert 'mcu-1' in text
    assert 'hidden' not in text.lower() and 'sha256' not in text and 'Public' not in text
    assert text.startswith('▌ FALCON\n\n  [ Rev B ]')
    assert not any('\u2801' <= char <= '\u28ff' for char in text)
    assert height == len(text.splitlines()) + 2
    assert max(map(len, text.splitlines())) <= 44


def test_equipment_labels_wrap_long_and_unicode_identifiers():
    record = {'manifest': {'board': '板-α', 'version': 'Revision B / prototype build', 'parts': [], 'links': []}}
    card = BoardCard(record, index=0)
    card.format_card(20)
    assert '板-α' in card.label.plain
    assert 'Revision' in card.label.plain and 'prototype' in card.label.plain
    assert '0 Parts' in card.label.plain and '0 Docs' in card.label.plain


@pytest.mark.asyncio
async def test_dotted_shadow_tracks_selection_without_moving_cards(tmp_path):
    root = tmp_path / 'store'
    register_board(root, 'alpha')
    register_board(root, 'beta')
    app = BoardGalleryApp(root)
    async with app.run_test(size=(110, 40)) as pilot:
        await ready(pilot, app)
        first, second = app.query(BoardCard)
        shadows = [card.parent.query_one('.card-shadow', Static) for card in (first, second)]
        assert shadows[0].visible and not shadows[1].visible
        regions = [card.region for card in (first, second)]
        assert shadows[0].region.x == first.region.x + 1
        assert shadows[0].region.y == first.region.y + 1
        assert shadows[0].region.right == first.region.right + 1
        assert shadows[0].region.bottom == first.region.bottom + 1
        assert '⠢⠔' in str(shadows[0].render())
        await pilot.press('l')
        assert not shadows[0].visible and shadows[1].visible
        assert [card.region for card in (first, second)] == regions
        await pilot.resize_terminal(80, 30)
        assert second.region.y > first.parent.region.bottom
        assert shadows[1].region.right <= second.parent.region.right
        assert shadows[1].region.bottom <= second.parent.region.bottom
        app.query_one('#back').focus()
        await pilot.pause()
        assert not any(shadow.visible for shadow in shadows)
