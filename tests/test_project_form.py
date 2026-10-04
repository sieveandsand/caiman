"""The guided project form edits what it renders and carries everything else."""

from copy import deepcopy

import pytest
from textual.widgets import Button, Input

from caiman.configurations.project_form import (FeatureCard, GoverningRow, PinnedBoardCard,
                                                ProjectDocumentCard, ProjectFormApp, RealizedRow, RelatedRow,
                                                guided_shape_problem)

A = 'sha256:' + 'a' * 64
B = 'sha256:' + 'b' * 64
C = 'sha256:' + 'c' * 64
from caiman.ui.heading import card_heading


def wide(value):
    """A card title as the editor shows it."""
    return card_heading(value, 200).plain


@pytest.fixture
def manifest():
    return {
        'schema': 'caiman.project.v2', 'project': 'falcon', 'version': 'B-sample',
        'derives_from': 'A-sample', 'relation': 'Adds the deviation list.',
        'customer': 'Synthetic OEM', 'pod': 'oem-alpha',
        'boards': [{'name': 'falcon-mainboard', 'version': '2.1', 'digest': C},
                   {'name': 'falcon-io', 'version': 'A'}],
        'spec_set': 'Synthetic release 3',
        'documents': [{'ref': 'oem/falcon/spec/3', 'digest': A, 'pod': 'oem-alpha'},
                      {'ref': 'oem/falcon/deviations/1', 'digest': B, 'pod': 'oem-alpha'}],
        'features': [
            {'name': 'secure-boot', 'scope': 'required', 'realized_on': [{'board': 'falcon-mainboard', 'version': '2.1', 'role': 'application-mcu'}],
             'governed_by': [{'ref': 'oem/falcon/spec/3', 'digest': A, 'pod': 'oem-alpha',
                              'requirements': ['REQ-7', 'REQ-8']}],
             'related': [{'feature': 'ota-update', 'relation': 'Verifies each update image.'}]},
            {'name': 'ota-update', 'scope': 'not-used'},
        ],
    }


@pytest.mark.asyncio
async def test_untouched_form_collects_the_manifest_it_was_given(manifest):
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert app.collect() == manifest


@pytest.mark.asyncio
async def test_absent_feature_lists_stay_absent(manifest):
    manifest['features'][0]['related'] = []
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        draft = app.collect()
    assert draft['features'][0]['related'] == []
    assert 'governed_by' not in draft['features'][1]


@pytest.mark.asyncio
async def test_fields_edit_and_optional_values_clear(manifest):
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        app.query_one('#project-version', Input).value = 'C-sample'
        app.query_one('#project-pod', Input).value = 'oem-beta'
        board = app.query_one(PinnedBoardCard)
        board.query_one('.field-digest', Input).value = ''
        board.query_one('.field-version', Input).value = '2.2'
        governing = app.query_one(GoverningRow)
        governing.query_one('.field-requirements', Input).value = ''
        part = app.query_one(RealizedRow)
        part.query_one('.field-role', Input).value = 'modem'
        draft = app.collect()
    assert draft['version'] == 'C-sample'
    assert draft['pod'] == 'oem-beta'
    assert draft['boards'] == [{'name': 'falcon-mainboard', 'version': '2.2'}, {'name': 'falcon-io', 'version': 'A'}]
    assert draft['features'][0]['governed_by'][0] == {'ref': 'oem/falcon/spec/3', 'digest': A,
                                                      'pod': 'oem-alpha'}
    assert draft['features'][0]['realized_on'] == [{'board': 'falcon-mainboard', 'version': '2.1', 'role': 'modem'}]
    # Lineage is not a field and rides through.
    assert draft['derives_from'] == 'A-sample'


@pytest.mark.asyncio
async def test_cards_add_collapse_and_remove_without_touching_neighbours(manifest):
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        add = app.query_one('#add-feature', Button)
        add.focus()
        await pilot.press('enter')
        await pilot.pause()
        added = list(app.query(FeatureCard))[-1]
        assert added.has_class('expanded')
        assert app.focused is added.query_one('.field-name', Input)
        added.query_one('.field-name', Input).value = 'half-typed'
        added.query_one('.collapse-feature', Button).press()
        await pilot.pause()
        assert not added.has_class('expanded')
        assert wide('half-typed') in added.query_one('.card-summary', Button).label.plain
        assert added.query_one('.field-name', Input).value == 'half-typed'
        added.query_one('.add-related', Button).press()
        await pilot.pause()
        added.query_one(RelatedRow).query_one('.field-feature', Input).value = 'secure-boot'
        assert app.collect()['features'][-1]['related'] == [{'feature': 'secure-boot', 'relation': ''}]
        added.query_one(RelatedRow).query_one('.remove-row', Button).press()
        await pilot.pause()
        assert app.focused is added.query_one('.field-name', Input)
        added.query_one('.remove-row', Button).press()
        await pilot.pause()
        assert app.focused is add
        document = list(app.query(ProjectDocumentCard))[0]
        document.query_one('.remove-row', Button).press()
        await pilot.pause()
        assert app.focused is app.query_one('#add-project-document', Button)
        draft = app.collect()
    assert draft['documents'] == manifest['documents'][1:]
    assert draft['features'] == manifest['features']


@pytest.mark.asyncio
async def test_empty_sections_offer_add_cards_and_grids_reflow(manifest):
    empty = dict(manifest, documents=[], features=[])
    app = ProjectFormApp(original=empty)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        for add_id in ('add-board', 'add-project-document', 'add-feature'):
            assert app.query_one(f'#{add_id}', Button)
        assert not app.query('#precedence')
        for add_id in ('add-project-document', 'add-feature'):
            assert app.query_one(f'#{add_id}', Button)
        app.query_one('#add-project-document', Button).press()
        await pilot.pause()
        assert app.collect()['documents'] == [{}]
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(70, 40)) as pilot:
        await pilot.pause()
        first, second = app.query(FeatureCard)
        assert first.region.x == second.region.x and first.region.bottom < second.region.y
        await pilot.resize_terminal(110, 40)
        await pilot.pause()
        assert first.region.y == second.region.y and first.region.x < second.region.x


@pytest.mark.asyncio
async def test_card_keyboard_navigation_can_leave_grid(manifest):
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        first, second = app.query(FeatureCard)
        first.query_one('.card-summary', Button).focus()
        await pilot.press('l')
        assert app.focused is second.query_one('.card-summary', Button)
        app.query_one('#add-feature', Button).focus()
        await pilot.press('j')
        assert not app.focused.has_class('dashboard-tile')


@pytest.mark.asyncio
async def test_review_raw_and_back_exit_as_the_board_form_does(manifest):
    for button, expected in (('#review-changes', 'review'), ('#raw', 'raw')):
        app = ProjectFormApp(original=manifest)
        async with app.run_test(size=(110, 50)) as pilot:
            await pilot.pause()
            app.query_one(button, Button).press()
            await pilot.pause()
        assert app.return_value == (expected, manifest)
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        app.query_one('#project-customer', Input).value = 'typed'
        app.query_one('#cancel', Button).press()
        await pilot.pause()
    assert app.return_value is None


@pytest.mark.parametrize('change', [
    lambda m: m.update(boards='falcon-mainboard@2.1'),
    lambda m: m['boards'].append('falcon-io@B'),
    lambda m: m['features'][0].update(realized_on='application-mcu'),
    lambda m: m['features'][0].update(realized_on=['application-mcu']),
    lambda m: m['features'][0]['realized_on'][0].update(version=2),
    lambda m: m['documents'][0].update(pod=['oem-alpha']),
    lambda m: m['features'][0]['governed_by'][0].update(requirements='REQ-7'),
])
def test_unrepresentable_shapes_are_reported(manifest, change):
    assert guided_shape_problem(manifest) is None
    change(manifest)
    assert guided_shape_problem(manifest)


@pytest.mark.asyncio
async def test_unrepresentable_project_is_raw_only_and_unchanged(manifest):
    manifest['features'][0]['realized_on'] = 'application-mcu'
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert not app.query('#review-changes')
        assert not app.query(FeatureCard)
        app.query_one('#raw', Button).press()
        await pilot.pause()
    assert app.return_value == ('raw', manifest)


@pytest.mark.asyncio
async def test_boards_add_and_remove_as_cards(manifest):
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        first, second = app.query(PinnedBoardCard)
        assert wide('falcon-mainboard') in first.query_one('.card-summary', Button).label.plain
        assert 'Digest pinned at review' in second.query_one('.card-summary', Button).label.plain
        app.query_one('#add-board', Button).press()
        await pilot.pause()
        added = list(app.query(PinnedBoardCard))[-1]
        assert app.focused is added.query_one('.field-name', Input)
        # One board at a second version is an ordinary second pin.
        added.query_one('.field-name', Input).value = 'falcon-mainboard'
        added.query_one('.field-version', Input).value = '2.2'
        assert app.collect()['boards'][-1] == {'name': 'falcon-mainboard', 'version': '2.2'}
        first.query_one('.remove-row', Button).press()
        await pilot.pause()
        assert [board['version'] for board in app.collect()['boards']] == ['A', '2.2']


@pytest.mark.asyncio
async def test_a_new_part_starts_blank_unless_exactly_one_board_is_pinned(manifest):
    app = ProjectFormApp(original=manifest)
    async with app.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        feature = list(app.query(FeatureCard))[1]
        feature.query_one('.add-realized', Button).press()
        await pilot.pause()
        assert app.collect()['features'][1]['realized_on'] == [{'board': '', 'version': '', 'role': ''}]
    single = dict(manifest, boards=manifest['boards'][:1])
    app = ProjectFormApp(original=single)
    async with app.run_test(size=(110, 60)) as pilot:
        await pilot.pause()
        feature = list(app.query(FeatureCard))[1]
        feature.query_one('.add-realized', Button).press()
        await pilot.pause()
        feature.query_one(RealizedRow).query_one('.field-role', Input).value = 'modem'
        assert app.collect()['features'][1]['realized_on'] == [
            {'board': 'falcon-mainboard', 'version': '2.1', 'role': 'modem'}]
        assert 'modem on falcon-mainboard @ 2.1' in feature.summary(feature.summary_data()).plain


@pytest.mark.asyncio
async def test_v1_project_opens_restated_with_its_one_board(manifest):
    legacy = deepcopy(manifest)
    legacy['schema'] = 'caiman.project/1'
    legacy['board'] = legacy.pop('boards')[0]
    legacy['features'][0]['realized_on'] = ['application-mcu']
    legacy['precedence'] = [{'ref': 'oem/falcon/deviations/2', 'digest': 'sha256:' + 'd' * 64,
                             'pod': 'oem-alpha', 'note': 'Amends REQ-7.'},
                            dict(legacy['documents'][0], note='Base specification.')]
    stored = deepcopy(legacy)
    app = ProjectFormApp(original=legacy)
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert 'caiman.project.v1' in ' '.join(str(hint.render()) for hint in app.query('.hint'))
        draft = app.collect()
    assert draft['schema'] == 'caiman.project.v3'
    assert 'board' not in draft
    assert draft['boards'] == [stored['board']]
    # Precedence is gone from v2; its pins stay as documents, without order or notes.
    assert 'precedence' not in draft
    assert draft['documents'] == stored['documents'] + [
        {'ref': 'oem/falcon/deviations/2', 'digest': 'sha256:' + 'd' * 64, 'pod': 'oem-alpha'}]
    assert draft['features'][0]['realized_on'] == [
        {'board': 'falcon-mainboard', 'version': '2.1', 'role': 'application-mcu'}]
    # The stored snapshot the review diffs against is untouched.
    assert app.original == stored


@pytest.mark.asyncio
@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
async def test_stable_document_references_preserve_feature_requirements(manifest, color_system):
    from rich.console import COLOR_SYSTEMS
    pin = {'pod': 'manuals', 'document': 'stable-document', 'blob': A}
    manifest['documents'] = [pin]
    manifest['features'][0]['governed_by'] = [dict(pin, requirements=['REQ-7'])]
    app = ProjectFormApp(original=manifest)
    app.console._color_system = COLOR_SYSTEMS[color_system]
    async with app.run_test(size=(110, 50)) as pilot:
        await pilot.pause()
        assert app.collect() == manifest
        card = app.query_one(ProjectDocumentCard)
        card.query_one('.card-summary', Button).press()
        await pilot.pause()
        assert card.query_one('.field-document', Input).value == pin['document']
        assert card.query_one('.field-blob', Input).value == A
        card.query_one('.collapse-card', Button).press()
        await pilot.pause()
        app.query_one('#review-changes', Button).focus()
        await pilot.pause()
        assert app.collect() == manifest
