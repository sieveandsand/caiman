"""Equipment labels retain identity, layout, and in-progress edits."""
import pytest
from rich.cells import cell_len
from textual.widgets import Input, Static

from caiman.ui import heading
from caiman.ui.cards import CARD_CSS, CardFrame, resize_card_grid
from caiman.ui.navigation import NavigationApp
from caiman.documents.cards import DocumentCard
from textual.containers import Grid


@pytest.mark.parametrize('secondary', [False, True])
def test_wrapping_keeps_equipment_style_and_all_identity_characters(secondary):
    value = 'Sensor Hub with a long identifier'
    wide = heading.card_heading(value, 100, secondary=secondary)
    narrow = heading.card_heading(value, 12, secondary=secondary)
    assert all(cell_len(row) <= 12 for row in narrow.plain.splitlines())
    assert ''.join(wide.plain.split()) == ''.join(narrow.plain.split())
    assert wide.plain == ('  [ ' + value + ' ]' if secondary else '▌ ' + value.upper())
    assert not any('\uff01' <= char <= '\uff5e' for char in narrow.plain)
    assert 'Straße' in heading.card_heading('Straße', 30).plain


class PreviewApp(NavigationApp):
    CSS = CARD_CSS + 'Grid { height: auto; }'

    def compose(self):
        record = {'manifest': {'name': 'Sensor Hub', 'version': 'rev B / 2.4', 'issuer': 'Vendor'}}
        yield Grid(CardFrame(DocumentCard(record, index=0)))
        yield Input(value='Draft value', id='draft')
        yield self.navigation_hint()

    def on_mount(self):
        resize_card_grid(self.query_one(Grid), 30, 1)


@pytest.mark.asyncio
async def test_equipment_style_is_permanent_and_f6_does_not_change_it():
    app = PreviewApp()
    async with app.run_test(size=(70, 35)) as pilot:
        card = app.query_one(DocumentCard)
        card.focus()
        await pilot.pause()
        expected = '▌ SENSOR HUB\n\n  [ rev B / 2.4 ]'
        assert card.label.plain.startswith(expected)
        await pilot.press('f6')
        assert card.label.plain.startswith(expected)
        assert app.focused is card
        assert 'F6' not in str(app.query_one('.key-hint', Static).content)
        assert card.parent.styles.height.value == len(card.label.plain.splitlines()) + 3
    other = PreviewApp()
    async with other.run_test():
        assert other.query_one(DocumentCard).label.plain.startswith(expected)


@pytest.mark.asyncio
async def test_resizing_expanded_equipment_card_retains_draft_and_focus():
    from caiman.boards.form import BoardFormApp, PartRow
    from textual.widgets import Button

    manifest = {'schema': 'caiman.board.v2', 'board': 'Sensor Hub', 'version': 'B',
                'vendor': 'Vendor', 'parts': [{'part': 'Sensor Chip', 'role': 'sensor',
                                             'vendor': 'Vendor', 'documents': []}],
                'documents': [], 'links': []}
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(100, 45)) as pilot:
        row = app.query_one(PartRow)
        row.set_expanded(True)
        field = row.query_one('.field-part', Input)
        field.value = 'Unsaved Chip'
        field.focus()
        await pilot.pause()
        await pilot.press('i')
        assert app.focused is field
        assert app.editing
        assert row.has_class('expanded')
        assert field.value == 'Unsaved Chip'
        row.refresh_summary()
        assert row.query_one('.card-summary', Button).label.plain.startswith('▌ UNSAVED CHIP')
        await pilot.resize_terminal(45, 35)
        await pilot.pause()
        assert row.query_one('.card-summary', Button).label.plain.startswith('▌ UNSAVED CHIP')
        assert field.value == 'Unsaved Chip'
