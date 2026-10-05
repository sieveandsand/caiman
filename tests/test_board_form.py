"""The guided board form renders the fields it owns and invents none of them."""

from copy import deepcopy

import pytest
from textual.widgets import Button, Input

from caiman.boards.form import (BoardFormApp, BoardDocumentCard, DocumentRow, LinkRow, PartRow, alias_text,
                              parse_aliases)
from caiman.configurations.files import COMMON_VENDORS, vendor_suggestions
from caiman.configurations.models import validate_board
from caiman.ui.heading import card_heading


def wide(value):
    """A card title as the editor shows it."""
    return card_heading(value, 200).plain


@pytest.fixture
def manifest():
    return {
        'schema': 'caiman.board.v2', 'board': 'falcon-mainboard', 'version': '2.1',
        'vendor': 'acme', 'notes': 'Dual-MCU safety mainboard.',
        'derives_from': '2.0', 'relation': 'Adds the secure element.',
        'documents': [{'ref': 'acme/falcon-mainboard/board-user-guide/2.1', 'pod': 'public',
                       'notes': 'Connector pinout and jumper defaults.'}],
        'parts': [
            {'role': 'application-mcu', 'vendor': 'nxp', 'part': 's32k344', 'silicon_revision': '1.1',
             'aliases': {'refdes': 'U1', 'mpn': 'S32K344EHTAR'}, 'notes': 'Runs the safety-rated image.',
             'documents': [{'ref': 'nxp/s32k344/reference-manual/Rev%204', 'pod': 'public',
                            'notes': 'Errata 051234 applies at this mask revision.'}]},
            {'role': 'safety-companion', 'vendor': 'ti', 'part': 'tps65313', 'documents': []},
        ],
        'links': [{'name': 'safety-link', 'between': ['application-mcu.LPSPI1', 'safety-companion.SPI'],
                   'notes': 'Watchdog handshake.'}],
    }


@pytest.mark.parametrize('aliases', [{}, {'refdes': 'U1'}, {'refdes': 'U1', 'mpn': 'S32K344EHTAR', 'devicetree': 'cpu0'}])
def test_aliases_round_trip_through_their_text_form(aliases):
    assert parse_aliases(alias_text(aliases)) == aliases


@pytest.mark.parametrize('text,message', [
    ('refdes U1', 'name = value'),
    ('refdes = U1, refdes = U2', 'Duplicate'),
])
def test_malformed_aliases_are_reported_not_guessed(text, message):
    with pytest.raises(ValueError, match=message):
        parse_aliases(text)


@pytest.mark.asyncio
async def test_untouched_form_collects_the_manifest_it_was_given(manifest):
    """Opening and reviewing without typing must not change a single field, or
    every edit silently rewrites the snapshot it started from."""
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert app.collect() == manifest


@pytest.mark.asyncio
async def test_every_declared_field_is_editable_and_optional_ones_can_be_cleared(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        app.query_one('#board-notes', Input).value = 'Now with a secure element.'
        app.query_one('#board-vendor', Input).value = ''
        parts = list(app.query(PartRow))
        parts[0].query_one('.field-silicon_revision', Input).value = '2.0'
        parts[0].query_one('.field-aliases', Input).value = 'refdes = U7'
        parts[1].query_one('.field-notes', Input).value = 'Resets the MCU.'
        list(app.query(LinkRow))[0].query_one('.field-notes', Input).value = 'Question and answer sequence.'
        draft = app.collect()
    assert draft['notes'] == 'Now with a secure element.'
    assert 'vendor' not in draft
    assert draft['parts'][0]['silicon_revision'] == '2.0'
    assert draft['parts'][0]['aliases'] == {'refdes': 'U7'}
    assert draft['parts'][1]['notes'] == 'Resets the MCU.'
    assert draft['links'][0]['notes'] == 'Question and answer sequence.'
    # Attachment is independent of the board vendor.
    assert validate_board(draft)['documents'] == draft['documents']


@pytest.mark.asyncio
async def test_rows_are_added_and_removed_without_touching_their_neighbours(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        app.query_one('#add-part', Button).press()
        await pilot.pause()
        added = list(app.query(PartRow))[-1]
        added.query_one('.field-role', Input).value = 'secure-element'
        added.query_one('.field-vendor', Input).value = 'nxp'
        added.query_one('.field-part', Input).value = 'se051'
        app.query_one('#add-link', Button).press()
        await pilot.pause()
        list(app.query(LinkRow))[-1].query_one('.field-name', Input).value = 'secure-bus'
        list(app.query(LinkRow))[-1].query_one('.field-between', Input).value = 'application-mcu.I2C0, secure-element.I2C'
        draft = app.collect()
        assert [part['role'] for part in draft['parts']] == ['application-mcu', 'safety-companion', 'secure-element']
        assert [link['name'] for link in draft['links']] == ['safety-link', 'secure-bus']
        removed = next(row for row in app.query(LinkRow) if row.data.get('name') == 'safety-link')
        removed.query_one('.remove-row', Button).press()
        await pilot.pause()
        draft = app.collect()
    assert [link['name'] for link in draft['links']] == ['secure-bus']
    assert draft['links'][0]['between'] == ['application-mcu.I2C0', 'secure-element.I2C']
    assert [part['role'] for part in draft['parts']] == ['application-mcu', 'safety-companion', 'secure-element']


@pytest.mark.asyncio
async def test_document_pins_are_fields_and_the_pod_stays_public(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        part = list(app.query(PartRow))[1]
        part.query_one('.add-document', Button).press()
        await pilot.pause()
        pin = list(part.query(DocumentRow))[-1]
        pin.query_one('.field-ref', Input).value = 'ti/tps65313/datasheet/A'
        pin.query_one('.field-notes', Input).value = 'Watchdog timing.'
        draft = app.collect()
    assert draft['parts'][1]['documents'] == [
        {'ref': 'ti/tps65313/datasheet/A', 'notes': 'Watchdog timing.'}]
    # The existing pin keeps the pod it was stored with.
    assert draft['parts'][0]['documents'][0]['pod'] == 'public'


@pytest.mark.asyncio
async def test_review_and_raw_exit_with_the_same_collected_draft(manifest):
    for action in ('review', 'raw'):
        app = BoardFormApp(original=manifest)
        async with app.run_test(size=(110, 50)) as pilot:
            await pilot.pause()
            app.query_one('#board-version', Input).value = '2.2'
            await pilot.pause()
            app.query_one('#review-changes' if action == 'review' else '#raw', Button).press()
            await pilot.pause()
        assert app.return_value[0] == action
        assert app.return_value[1]['version'] == '2.2'


@pytest.mark.asyncio
async def test_back_discards_everything_typed(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        app.query_one('#board-version', Input).value = '2.2'
        app.query_one('#cancel', Button).press()
        await pilot.pause()
    assert app.return_value is None


@pytest.mark.asyncio
async def test_malformed_aliases_stop_at_the_form_without_exiting(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        list(app.query(PartRow))[0].query_one('.field-aliases', Input).value = 'refdes U1'
        await pilot.pause()
        assert not app.query_one('#review-changes', Button).disabled
        app.query_one('#review-changes', Button).press()
        await pilot.pause()
        assert app.return_value is None
        assert 'name = value' in str(app.query_one('#form-error').render())


@pytest.mark.asyncio
async def test_a_legacy_board_is_shown_but_only_editable_as_raw_json(manifest):
    """A caiman.board/1 part identity is packed into one field. Authoring it in
    the v2 form would migrate a stored version, so the form refuses to (S-11)."""
    legacy = {'schema': 'caiman.board/1', 'board': 'falcon-mainboard', 'version': '2.1', 'links': [],
              'parts': [{'role': 'application-mcu', 'part': 'nxp/s32k344', 'refdes': 'U1', 'documents': []}]}
    app = BoardFormApp(original=legacy)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert not app.query('#review-changes')
        assert not app.query(PartRow)
        assert 'caiman.board/1' in app.read_only_reason()
        app.query_one('#raw', Button).press()
        await pilot.pause()
    assert app.return_value == ('raw', legacy)


@pytest.mark.asyncio
async def test_a_directed_link_is_never_rewritten_as_a_between_link(manifest):
    directed = deepcopy(manifest)
    directed['links'] = [{'name': 'clock-tree', 'from': 'application-mcu', 'to': ['safety-companion']}]
    app = BoardFormApp(original=directed)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert not app.query('#review-changes')
        assert 'from/to' in app.read_only_reason()
        app.query_one('#raw', Button).press()
        await pilot.pause()
    assert app.return_value == ('raw', directed)


def test_vendor_suggestions_are_offered_not_enforced():
    """The list exists so one board does not carry `nxp` and `NXP`. It is a
    convenience, so nothing validates against it (I-8)."""
    assert vendor_suggestions() == COMMON_VENDORS
    assert 'nxp' in COMMON_VENDORS and 'stm' in COMMON_VENDORS and 'ti' in COMMON_VENDORS
    # Casing is canonicalised by the suggestion, never by rejecting input.
    assert validate_board({
        'board': 'b', 'version': '1', 'links': [],
        'parts': [{'role': 'r', 'vendor': 'a-vendor-nobody-listed', 'part': 'p', 'documents': []}],
    })['parts'][0]['vendor'] == 'a-vendor-nobody-listed'


def test_vendor_suggestions_include_what_this_board_already_declares(manifest):
    suggestions = vendor_suggestions(manifest)
    assert suggestions[:len(COMMON_VENDORS)] == COMMON_VENDORS
    # acme and ti are on the board; ti is already common, acme is not.
    assert 'acme' in suggestions
    assert suggestions.count('ti') == 1
    assert len(suggestions) == len(COMMON_VENDORS) + 1


@pytest.mark.asyncio
@pytest.mark.parametrize('typed,expected', [
    ('nx', 'nxp'), ('NX', 'nxp'), ('St', 'stm'), ('ac', 'acme'), ('zzz', ''),
])
async def test_vendor_completion_is_case_insensitive(manifest, typed, expected):
    """Typing `NX` offers the canonical `nxp`, which is the whole point: the
    spelling that reaches the manifest is the one already in use."""
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        field = list(app.query(PartRow))[0].query_one('.field-vendor', Input)
        field.value = typed
        await pilot.pause(0.1)
        # A suggestion is displayed, not applied: the typed value is untouched
        # until the engineer moves the caret onto it.
        assert field._suggestion == expected
        assert field.value == typed


@pytest.mark.asyncio
async def test_part_fields_read_part_name_then_role_then_vendor(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        part = list(app.query(PartRow))[0]
        order = [next(name for name in widget.classes if name.startswith('field-'))
                 for widget in part.query(Input)]
        assert order[:4] == ['field-part', 'field-role', 'field-vendor', 'field-silicon_revision']
        assert part.query_one('.field-vendor', Input).suggester is not None
        assert part.query_one('.field-part', Input).suggester is None


@pytest.mark.asyncio
async def test_lineage_is_not_a_field_but_survives_an_edit(manifest):
    """The form stopped rendering derives_from and relation. They are still
    declared values on the snapshot, so editing anything else must not drop them."""
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert not app.query('#board-derives_from')
        assert not app.query('#board-relation')
        app.query_one('#board-notes', Input).value = 'Edited without touching lineage.'
        draft = app.collect()
    assert draft['derives_from'] == '2.0'
    assert draft['relation'] == 'Adds the secure element.'
    assert draft['notes'] == 'Edited without touching lineage.'


@pytest.mark.asyncio
async def test_a_board_without_lineage_does_not_gain_empty_lineage(manifest):
    plain = {key: value for key, value in manifest.items()
             if key not in {'derives_from', 'relation'}}
    app = BoardFormApp(original=plain)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        draft = app.collect()
    assert 'derives_from' not in draft and 'relation' not in draft
    validate_board(draft)


@pytest.mark.asyncio
async def test_part_cards_expand_in_place_and_keep_edits_when_collapsed(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        first, second = app.query(PartRow)
        assert first.region.y == second.region.y
        assert first.region.right < second.region.x
        assert not first.query_one('.part-editor').display
        closed_height = first.size.height
        summary = first.query_one('.part-summary', Button)
        summary.focus()
        await pilot.press('enter')
        await pilot.pause()
        assert first.query_one('.part-editor').display
        assert first.size.height > closed_height
        assert second.size.height == closed_height
        assert first.region.x < second.region.x
        first.query_one('.field-part', Input).value = 's32k358'
        first.query_one('.collapse-part', Button).press()
        await pilot.pause()
        assert not first.query_one('.part-editor').display
        assert first.size.height == closed_height
        assert wide('s32k358') in summary.label.plain
        assert app.focused is summary
        await pilot.press('enter')
        await pilot.pause()
        assert first.query_one('.field-part', Input).value == 's32k358'
        assert app.collect()['parts'][1] == manifest['parts'][1]


@pytest.mark.asyncio
async def test_plus_card_adds_expanded_part_and_removal_restores_focus(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        add = app.query_one('#add-part', Button)
        assert add.parent.parent.id == 'parts'
        assert '╋' in add.label.plain
        add.focus()
        await pilot.press('enter')
        await pilot.pause()
        added = list(app.query(PartRow))[-1]
        assert added.has_class('expanded')
        assert app.focused is added.query_one('.field-part', Input)
        assert list(add.parent.parent.children)[-1] is add.parent
        added.query_one('.remove-row', Button).press()
        # Removal and its post-layout focus callback finish on separate cycles.
        for _ in range(20):
            await pilot.pause()
            if added not in app.query(PartRow) and app.focused is add:
                break
        assert app.focused is add
        assert app.collect() == manifest


@pytest.mark.asyncio
async def test_part_grid_reflows_and_empty_board_keeps_add_card(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        await pilot.resize_terminal(70, 35)
        first, second = app.query(PartRow)
        assert first.region.x == second.region.x
        assert first.region.bottom < second.region.y
        first.query_one('.part-summary', Button).press()
        await pilot.pause()
        assert first.region.bottom < second.region.y
        assert first.region.right <= 70
    empty = dict(manifest, parts=[])
    app = BoardFormApp(original=empty)
    async with app.run_test(size=(70, 35)) as pilot:
        await pilot.pause()
        assert not app.query(PartRow)
        app.query_one('#add-part', Button).press()
        await pilot.pause()
        assert len(app.query(PartRow)) == 1
        assert app.query_one(PartRow).has_class('expanded')


@pytest.mark.asyncio
async def test_card_keyboard_navigation_can_leave_grid(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        first, second = app.query(PartRow)
        first.query_one('.part-summary', Button).focus()
        await pilot.press('l')
        assert app.focused is second.query_one('.part-summary', Button)
        await pilot.press('h', 'j')
        assert app.focused is app.query_one('#add-part')
        await pilot.press('j')
        assert app.focused is app.query_one(LinkRow).query_one('.card-summary', Button)
        app.query_one('#add-link', Button).focus()
        await pilot.press('j')
        assert not app.focused.has_class('dashboard-tile')


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,card_type,field,new_value,add_id', [
    ('documents', BoardDocumentCard, 'ref', 'acme/falcon-mainboard/schematic/B', 'add-board-document'),
    ('links', LinkRow, 'name', 'updated-link', 'add-link'),
])
async def test_document_and_link_cards_preserve_edits_and_neighbours(
        manifest, kind, card_type, field, new_value, add_id):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        card = app.query_one(card_type)
        add = app.query_one('#' + add_id, Button)
        assert card.region.y == add.region.y
        assert card.region.right < add.region.x
        assert not card.query_one('.card-editor').display
        summary = card.query_one('.card-summary', Button)
        summary.focus()
        await pilot.press('enter')
        await pilot.pause()
        assert card.query_one('.card-editor').display
        card.query_one('.field-' + field, Input).value = new_value
        card.query_one('.collapse-card', Button).press()
        await pilot.pause()
        assert not card.query_one('.card-editor').display
        # Keep the selected typography when the title wraps.
        shown = card_heading(new_value, card.summary_width).plain
        assert summary.label.plain.startswith(shown + '\n')
        assert app.focused is summary
        expected = deepcopy(manifest)
        expected[kind][0][field] = new_value
        assert app.collect() == expected
        await pilot.resize_terminal(70, 35)
        assert card.region.x == add.region.x
        assert card.region.bottom < add.region.y
        add.focus()
        await pilot.press('enter')
        await pilot.pause()
        added = list(app.query(card_type))[-1]
        assert added.has_class('expanded')
        assert app.focused is added.query_one('.field-' + field, Input)
        assert list(add.parent.parent.children)[-1] is add.parent
        added.query_one('.remove-row', Button).press()
        await pilot.pause()
        assert app.focused is add
        assert app.collect() == expected


@pytest.mark.asyncio
async def test_empty_document_and_link_sections_offer_plus_cards(manifest):
    empty = dict(manifest, documents=[], links=[])
    app = BoardFormApp(original=empty)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        for add_id, card_type in [('add-board-document', BoardDocumentCard), ('add-link', LinkRow)]:
            add = app.query_one('#' + add_id, Button)
            assert all(node.display for node in (add, *add.ancestors))
            assert '╋' in add.label.plain
            add.focus()
            await pilot.press('enter')
            await pilot.pause()
            assert app.query_one(card_type).has_class('expanded')
        app.query_one(BoardDocumentCard).query_one('.field-ref', Input).value = 'acme/falcon-mainboard/schematic/A'
        app.query_one(LinkRow).query_one('.field-name', Input).value = 'new-link'
        app.query_one(LinkRow).query_one('.field-between', Input).value = 'application-mcu, safety-companion'
        draft = app.collect()
        assert draft['documents'] == [{'ref': 'acme/falcon-mainboard/schematic/A'}]
        assert draft['links'] == [{'name': 'new-link', 'between': ['application-mcu', 'safety-companion']}]
        assert draft['parts'] == manifest['parts']


@pytest.mark.asyncio
async def test_editor_and_add_card_shadows_follow_focus_and_preserve_geometry(manifest):
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        first, second = app.query(PartRow)
        first.query_one('.card-summary', Button).focus()
        await pilot.pause()
        shadow = first.query_one('.card-shadow')
        face = first.query_one('.editor-face')
        assert shadow.visible
        assert shadow.region.x == face.region.x
        assert shadow.region.y == face.region.y
        assert shadow.region.right == face.region.right + 1
        assert shadow.region.bottom == face.region.bottom + 1
        first.scroll_visible(animate=False, top=True)
        await pilot.pause()
        assert '⠢' in app.export_screenshot() or '⠔' in app.export_screenshot()
        regions = [card.region for card in (first, second)]
        second.query_one('.card-summary', Button).focus()
        await pilot.pause()
        assert not shadow.visible
        assert second.query_one('.card-shadow').visible
        assert regions == [card.region for card in (first, second)]
        add = app.query_one('#add-part', Button)
        add.focus()
        await pilot.pause()
        assert not second.query_one('.card-shadow').visible
        assert add.parent.query_one('.card-shadow').visible
        app.query_one('#raw').focus()
        await pilot.pause()
        assert not add.parent.query_one('.card-shadow').visible


@pytest.mark.asyncio
async def test_editor_card_titles_match_gallery_and_preserve_unicode(manifest):
    from rich.cells import cell_len

    short, long, unsupported = 'S32K358-rev2', 'S32K358-long-part-number-rev2', 'TJA1145ß'
    manifest['parts'][0]['part'] = short
    manifest['parts'][1]['part'] = long
    manifest['parts'].append(deepcopy(manifest['parts'][1]) | {'part': unsupported})
    app = BoardFormApp(original=manifest, draft=deepcopy(manifest))
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        titles = [row.query_one('.part-summary', Button) for row in app.query(PartRow)]
        first_lines = [summary.label.plain.split('\n')[0] for summary in titles]
        # Same heading style as the gallery cards, sized to the card.
        assert first_lines[0] == wide(short)
        assert cell_len(first_lines[0]) <= titles[0].content_region.width
        # Long ASCII titles keep their case treatment; Unicode is not transliterated.
        assert first_lines[1:] == [wide(long), wide(unsupported)]
        assert [part['part'] for part in app.collect()['parts']] == [short, long, unsupported]
        # Narrowing the terminal re-renders the title rather than overflowing the card.
        await pilot.resize_terminal(34, 50)
        await pilot.pause()
        assert titles[0].label.plain.split('\n')[0] == wide(short)


@pytest.mark.asyncio
@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
async def test_stable_document_reference_roundtrip_and_replacement(manifest, color_system):
    from rich.console import COLOR_SYSTEMS
    pin = {'pod': 'manuals', 'document': 'stable-document', 'blob': 'sha256:' + 'a' * 64,
           'notes': 'Shared across hardware variants'}
    manifest['documents'] = [pin]
    manifest['parts'][0]['documents'] = [deepcopy(pin)]
    app = BoardFormApp(original=manifest)
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert app.collect() == manifest
        card = app.query_one(BoardDocumentCard)
        card.query_one('.card-summary', Button).press()
        await pilot.pause()
        assert card.query_one('.field-document', Input).value == pin['document']
        assert card.query_one('.field-blob', Input).value == pin['blob']
        card.query_one('.field-document', Input).value = 'replacement-document'
        card.query_one('.field-blob', Input).value = 'sha256:' + 'b' * 64
        card.query_one('.collapse-card', Button).press()
        await pilot.pause()
        app.query_one('#review-changes', Button).focus()
        await pilot.pause()
        draft = app.collect()
        assert draft['documents'][0]['document'] == 'replacement-document'
        assert draft['documents'][0]['notes'] == pin['notes']
        assert draft['parts'][0]['documents'] == [pin]
        assert validate_board(draft)['documents'] == draft['documents']


@pytest.mark.parametrize('width', [70, 110])
@pytest.mark.parametrize('read_only', [False, True])
async def test_delete_board_is_keyboard_accessible(manifest, width, read_only):
    if read_only:
        manifest['links'] = [{'name': 'legacy', 'from': 'application-mcu', 'to': 'safety-companion'}]
    app = BoardFormApp(original=manifest)
    async with app.run_test(size=(width, 40)) as pilot:
        await pilot.pause()
        app.query_one('#raw').focus()
        await pilot.press('tab')
        button = app.query_one('#delete', Button)
        assert app.focused is button
        assert app.screen.region.contains_region(button.region)
        assert app.screen.region.contains_region(app.query_one('#cancel').region)
        await pilot.press('enter')
    action, draft = app.return_value
    assert action == 'delete'
    assert draft == manifest


@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
async def test_review_tracks_edits_reverts_and_nested_records(manifest, color_system):
    from rich.console import COLOR_SYSTEMS

    app = BoardFormApp(original=manifest)
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        review = app.query_one('#review-changes', Button)
        assert review.disabled
        review.press()
        await pilot.pause()
        assert app.return_value is None
        field = app.query_one('#board-notes', Input)
        original = field.value
        field.value = 'Changed'
        await pilot.pause()
        assert not review.disabled
        review.focus()
        await pilot.pause()
        assert app.focused is review
        enabled_style = review.rich_style
        field.value = original
        await pilot.pause()
        assert review.disabled
        assert app.focused is not review
        assert review.rich_style != enabled_style
        app.query_one('#add-part', Button).press()
        await pilot.pause()
        assert not review.disabled
        row = list(app.query(PartRow))[-1]
        row.query_one('.remove-row', Button).press()
        await pilot.pause()
        assert review.disabled


async def test_retained_changed_draft_can_be_reviewed(manifest):
    draft = deepcopy(manifest)
    draft['version'] = 'edited version'
    app = BoardFormApp(original=manifest, draft=draft)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert not app.query_one('#review-changes', Button).disabled
