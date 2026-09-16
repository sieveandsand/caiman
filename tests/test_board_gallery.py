"""The board gallery shows complete snapshots and returns exact editor selections."""


import pytest
from textual.widgets import Static

from caiman.board_gallery import BoardCard, BoardGalleryApp
from caiman.config_store import ConfigurationService
from caiman.store import Store


def register_board(root, name='alpha', version='A', parts=1):
    service = ConfigurationService(Store(root))
    draft = {
        'board': name, 'version': version,
        'parts': [{'role': f'role-{index:02d}', 'part': f'synthetic/chip-{index}',
                   'silicon_revision': 'mask-A', 'refdes': f'U{index + 1}', 'documents': []}
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
                assert f'role-{index:02d}' in text
                assert f'synthetic/chip-{index}' in text
                assert f'Ref U{index + 1}' in text
            assert 'Silicon mask-A' in text
            assert f'Parts ({count})' in text
            # The logo spells the version too, but an opaque label must also
            # appear as literal text (CLAUDE.md I-7).
            assert 'Version A' in text
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
        assert 'role-14' in card.label.plain
        assert 'synthetic/chip-14' in card.label.plain
        assert card.region.height > 24
        body = app.query_one('#body')
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
        assert 'Create a board' in str(app.query_one('#gallery-status', Static).render())
        assert not list(app.query(BoardCard))
        await pilot.press('q')
    assert not root.exists()


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


def test_board_cards_use_a_registered_dotted_border():
    """Textual ships no dotted border, so Caiman registers one.

    Registration reaches into Textual internals and falls back to the built-in
    dashed border if they move. That fallback must never pass silently: this is
    where a Textual upgrade gets noticed.
    """
    from textual._border import BORDER_CHARS
    from textual.css.constants import VALID_BORDER

    from caiman.theme import DOT, DOT_BORDER

    assert DOT_BORDER == 'dotted', 'Textual internals moved; the border degraded to dashed'
    assert 'dotted' in VALID_BORDER
    assert BORDER_CHARS['dotted'] == ((DOT, DOT, DOT), (DOT, ' ', DOT), (DOT, DOT, DOT))
    # Latin-1, so it renders in any terminal font — unlike Braille or block dots.
    assert DOT.encode('latin-1') == b'\xb7'
    assert f'border: {DOT_BORDER} ' in BoardGalleryApp.CSS


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
