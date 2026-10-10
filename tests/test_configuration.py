from copy import deepcopy

import pytest

from caiman.configurations.models import (restate_project_draft, part_aliases, part_identity, part_vendor_and_part,
                                  project_boards, realized_parts, validate_board, validate_project,
                                  validate_project_links)
from caiman.documents.models import ValidationError, accepted_schemas, current_schema


@pytest.fixture
def board():
    return {'board': 'synthetic', 'version': '../opaque', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': [{'ref': 'synthetic/chip/manual/v1'}]},
        {'role': 'flash', 'vendor': 'synthetic', 'part': 'flash', 'documents': []}],
        'links': [{'name': 'spi', 'between': ['mcu.SPI1', 'flash']}]}


@pytest.fixture
def project():
    return {'project': 'demo', 'version': '.', 'customer': 'Synthetic Customer',
            'pod': 'synthetic-alpha', 'boards': [{'name': 'synthetic', 'version': '../opaque'}],
            'spec_set': 'release / A', 'documents': [{'ref': 'synthetic/spec/v1'}],
            'features': [{'name': 'boot', 'scope': 'required', 'realized_on': [{'board': 'synthetic', 'version': '../opaque', 'role': 'mcu'}],
                          'governed_by': [{'ref': 'synthetic/spec/v1', 'requirements': ['REQ-001..005']}]},
                         {'name': 'ota', 'scope': 'not-used',
                          'related': [{'feature': 'boot', 'relation': 'Shares startup'}]}]}


def test_valid_drafts_are_copies_with_schema_and_public_board(board, project):
    original = deepcopy(board)
    result = validate_board(board)
    assert board == original
    assert result['schema'] == 'caiman.board.v3'
    assert result['version'] == '../opaque'
    assert 'pod' not in result['parts'][0]['documents'][0]
    assert validate_project(project)['version'] == '.'
    validate_project_links(project, [board])


@pytest.mark.parametrize('mutation', [
    lambda x: x.update(customer='Secret'),
    lambda x: x['parts'][0]['documents'][0].update(pod='../unsafe'),
    lambda x: x['parts'][0]['documents'][0].update(ref='../escape'),
    lambda x: x['parts'][0]['documents'][0].update(digest='sha256:short'),
    lambda x: x['parts'].append(deepcopy(x['parts'][0])),
    lambda x: x['links'][0].update(between=['mcu', 'unknown']),
    lambda x: x.update(derives_from='old'),
    lambda x: x.update(schema='caiman.project/1'),
])
def test_board_rejections(board, mutation):
    mutation(board)
    with pytest.raises(ValidationError):
        validate_board(board)


@pytest.mark.parametrize('mutation', [
    lambda x: x.update(pods=[]),
    lambda x: x.update(pods=['public', 'synthetic-alpha']),
    lambda x: x['documents'][0].update(pod='../unsafe'),
    lambda x: x['features'][0].update(scope='implemented'),
    lambda x: x['features'][0].update(status='verified'),
    lambda x: x['features'][1]['related'][0].update(feature='missing'),
    lambda x: x['features'].append(deepcopy(x['features'][0])),
    lambda x: x['features'][0]['governed_by'][0].update(requirements=['']),
])
def test_project_rejections(project, mutation):
    mutation(project)
    with pytest.raises(ValidationError):
        validate_project(project)


def test_project_board_roles_checked(project, board):
    project['features'][0]['realized_on'][0]['role'] = 'missing'
    with pytest.raises(ValidationError):
        validate_project_links(project, [board])


def second_version(board):
    other = deepcopy(board)
    other['version'] = 'B'
    other['parts'].append({'role': 'radio', 'vendor': 'synthetic', 'part': 'radio', 'documents': []})
    return other


def test_project_pins_several_boards_including_one_board_at_two_versions(project, board):
    project['boards'].append({'name': 'synthetic', 'version': 'B'})
    project['features'][0]['realized_on'].append({'board': 'synthetic', 'version': 'B', 'role': 'radio'})
    # The same role name on two boards is fine; the entry says which board.
    project['features'][0]['realized_on'].append({'board': 'synthetic', 'version': 'B', 'role': 'flash'})
    project['features'][0]['realized_on'].append({'board': 'synthetic', 'version': '../opaque', 'role': 'flash'})
    assert validate_project(project)['schema'] == 'caiman.project.v3'
    validate_project_links(project, [board, second_version(board)])


def test_realized_part_is_checked_on_its_own_board_only(project, board):
    project['boards'].append({'name': 'synthetic', 'version': 'B'})
    # `radio` exists only at version B; declaring it on the other version is an error.
    project['features'][0]['realized_on'] = [{'board': 'synthetic', 'version': '../opaque', 'role': 'radio'}]
    with pytest.raises(ValidationError, match='realized_on.0'):
        validate_project_links(project, [board, second_version(board)])


def test_board_manifests_must_match_each_selector(project, board):
    project['boards'].append({'name': 'synthetic', 'version': 'B'})
    with pytest.raises(ValidationError, match='boards'):
        validate_project_links(project, [board])
    with pytest.raises(ValidationError, match='boards.1'):
        validate_project_links(project, [board, board])


def test_project_needs_a_board_or_a_document(project):
    project['features'] = []
    documents_only = deepcopy(project) | {'boards': []}
    assert validate_project(documents_only)['boards'] == []
    validate_project_links(documents_only, [])
    boards_only = deepcopy(project) | {'documents': []}
    assert validate_project(boards_only)['documents'] == []
    with pytest.raises(ValidationError, match='at least one board or'):
        validate_project(project | {'boards': [], 'documents': []})


@pytest.mark.parametrize('mutation', [
    lambda x: x['boards'].append(dict(x['boards'][0])),
    lambda x: x['boards'].append({'name': 'synthetic', 'version': '../opaque', 'digest': 'sha256:' + 'a' * 64}),
    lambda x: x.update(board=x['boards'][0]),
    lambda x: x.update(precedence=[]),
    lambda x: x.update(precedence=[{'ref': 'synthetic/spec/v1', 'note': 'Declared authority'}]),
    lambda x: x['features'][0].update(realized_on=['mcu']),
    lambda x: x['features'][0]['realized_on'][0].pop('version'),
    lambda x: x['features'][0]['realized_on'][0].update(version='B'),
    lambda x: x['features'][0]['realized_on'][0].update(board='other'),
    lambda x: x['features'][0]['realized_on'].append(dict(x['features'][0]['realized_on'][0])),
])
def test_multi_board_rejections(project, mutation):
    mutation(project)
    with pytest.raises(ValidationError):
        validate_project(project)


def test_version_labels_match_exactly_never_loosely(project):
    # Versions are opaque (I-7): no trimming, case folding, or prefix match.
    for version in ('../OPAQUE', '../opaque ', '../opa'):
        changed = deepcopy(project)
        changed['features'][0]['realized_on'][0]['version'] = version
        with pytest.raises(ValidationError):
            validate_project(changed)


def test_v1_project_stays_valid_and_restates_without_guessing(project, board):
    legacy = deepcopy(project)
    legacy['schema'] = 'caiman.project/1'
    legacy['board'] = legacy.pop('boards')[0]
    legacy['features'][0]['realized_on'] = ['mcu']
    assert validate_project(legacy) == legacy
    validate_project_links(legacy, [board])
    assert project_boards(legacy) == [legacy['board']]
    assert realized_parts(legacy, legacy['features'][0]) == [('synthetic', '../opaque', 'mcu')]
    restated = restate_project_draft(legacy)
    assert restated['schema'] == 'caiman.project.v3'
    assert 'board' not in restated
    assert restated['boards'] == [legacy['board']]
    assert restated['features'][0]['realized_on'] == project['features'][0]['realized_on']
    assert legacy['board'] == {'name': 'synthetic', 'version': '../opaque'}
    validate_project_links(restated, [board])


def test_digest_only_and_lineage(board, project):
    board['parts'][0]['documents'] = [{'digest': 'sha256:' + 'a' * 64}]
    board.update(derives_from='release / zero', relation='Human supplied change')
    assert validate_board(board)['derives_from'] == 'release / zero'
    project['documents'] = [{'digest': 'sha256:' + 'b' * 64}]
    assert validate_project(project)['documents'][0]['digest'] == 'sha256:' + 'b' * 64


@pytest.mark.parametrize('value', [None, [], 'wrong', 1])
def test_malformed_root_is_validation_error(value):
    for validate in (validate_board, validate_project):
        with pytest.raises(ValidationError):
            validate(value)


@pytest.mark.parametrize('field,value', [('parts', [None]), ('parts', 'bad'),
    ('links', [None]), ('links', [{'name': 'broken', 'from': None, 'to': ['mcu']}])])
def test_malformed_board_nested_fields(board, field, value):
    board[field] = value
    with pytest.raises(ValidationError):
        validate_board(board)


@pytest.mark.parametrize('field,value', [('boards', {}), ('boards', [None]), ('pods', [None]),
    ('features', [None]), ('documents', [None]), ('documents', [{'requirements': ['REQ-1']}])])
def test_malformed_project_nested_fields(project, field, value):
    project[field] = value
    with pytest.raises(ValidationError):
        validate_project(project)


def test_directed_links_and_dotted_exact_roles(board):
    board['parts'][0]['role'] = 'core.mcu'
    board['links'] = [{'name': 'bus', 'from': 'core.mcu.SPI1', 'to': ['flash']}]
    validate_board(board)


def test_duplicate_selectors_and_related_edges(project):
    project['documents'] *= 2
    project['features'][1]['related'] *= 2
    with pytest.raises(ValidationError) as error:
        validate_project(project)
    assert 'documents.1' in error.value.errors
    assert 'features.1.related.1.feature' in error.value.errors


LEGACY_BOARD = {'schema': 'caiman.board/1', 'board': 'synthetic', 'version': 'Rev A',
                'parts': [{'role': 'mcu', 'part': 'synthetic/chip', 'refdes': 'U1', 'documents': []}],
                'links': [{'name': 'spi', 'between': ['mcu.SPI1', 'mcu.SPI2']}]}


def test_v2_carries_vendor_notes_aliases_and_board_documents(board):
    board.update(vendor='synthetic', notes='Dual-MCU safety mainboard.',
                 documents=[{'ref': 'synthetic/synthetic/user-guide/v1', 'notes': 'Connector pinout.'}])
    board['parts'][0].update(aliases={'refdes': 'U1', 'mpn': 'CHIP-0001'}, notes='Runs the application image.')
    board['parts'][0]['documents'][0]['notes'] = 'Errata 051234 applies at this mask revision.'
    board['links'][0]['notes'] = 'Watchdog handshake.'
    result = validate_board(board)
    assert result['schema'] == 'caiman.board.v3'
    assert result['parts'][0]['aliases'] == {'refdes': 'U1', 'mpn': 'CHIP-0001'}
    assert 'pod' not in result['documents'][0]


def test_legacy_board_validates_unchanged_and_keeps_its_literal():
    result = validate_board(deepcopy(LEGACY_BOARD))
    assert result['schema'] == 'caiman.board/1'
    assert result['parts'][0]['refdes'] == 'U1'


@pytest.mark.parametrize('mutation', [
    lambda x: x['parts'][0].update(vendor='synthetic'),
    lambda x: x['parts'][0].update(aliases={'refdes': 'U1'}),
    lambda x: x['parts'][0].update(notes='Commentary'),
    lambda x: x.update(notes='Commentary'),
    lambda x: x.update(vendor='synthetic'),
    lambda x: x.update(documents=[{'ref': 'synthetic/synthetic/user-guide/v1'}]),
    lambda x: x['links'][0].update(notes='Commentary'),
])
def test_v2_fields_are_rejected_on_a_legacy_board(mutation):
    board = deepcopy(LEGACY_BOARD)
    mutation(board)
    with pytest.raises(ValidationError):
        validate_board(board)


@pytest.mark.parametrize('mutation', [
    # refdes is no longer a field; it belongs in aliases.
    lambda x: x['parts'][0].update(refdes='U1'),
    # A packed identity is a v1 shape, and a bare part needs its vendor.
    lambda x: x['parts'][0].update(part='synthetic/chip'),
    lambda x: x['parts'][0].pop('vendor'),
    lambda x: x['parts'][0].update(aliases={}),
    lambda x: x['parts'][0].update(aliases={'ref des': 'U1'}),
    lambda x: x['parts'][0].update(aliases={'refdes': ''}),
    lambda x: x['parts'][0].update(aliases='U1'),
    lambda x: x.update(notes=''),
    lambda x: x.update(schema='caiman.board/2'),
    lambda x: x.update(schema='caiman.board.v99'),
])
def test_v2_board_rejections(board, mutation):
    mutation(board)
    with pytest.raises(ValidationError):
        validate_board(board)


def test_part_helpers_read_both_schemas(board):
    board['parts'][0].update(aliases={'mpn': 'CHIP-0001'})
    assert part_identity(board['parts'][0]) == 'synthetic/chip'
    assert part_vendor_and_part(board['parts'][0]) == ('synthetic', 'chip')
    assert part_aliases(board['parts'][0]) == {'mpn': 'CHIP-0001'}
    legacy = LEGACY_BOARD['parts'][0]
    assert part_identity(legacy) == 'synthetic/chip'
    assert part_vendor_and_part(legacy) == ('synthetic', 'chip')
    # A v1 refdes reads as the alias it becomes in v2, without rewriting the snapshot.
    assert part_aliases(legacy) == {'refdes': 'U1'}


@pytest.mark.parametrize('kind,validate', [('board', validate_board), ('project', validate_project)])
def test_declared_schema_literal_is_never_rewritten(project, kind, validate):
    """Rewriting a stored literal would change the canonical bytes of a snapshot
    that is supposed to be immutable, so validation defaults but never replaces."""
    current, *older = accepted_schemas(kind)
    assert current == current_schema(kind)
    if kind == 'board':
        assert validate(deepcopy(LEGACY_BOARD))['schema'] == 'caiman.board/1'
        return
    # Every older project literal is the single-board shape.
    legacy = {key: value for key, value in project.items() if key != 'boards'}
    legacy['board'] = project['boards'][0]
    legacy['features'] = [dict(feature, realized_on=['mcu']) if 'realized_on' in feature else feature
                          for feature in project['features']]
    for literal in ('caiman.project.v1', 'caiman.project/1'):
        assert validate(dict(legacy, schema=literal))['schema'] == literal


def test_omitting_the_schema_authors_the_current_version(board, project):
    assert validate_board(board)['schema'] == current_schema('board')
    assert validate_project(project)['schema'] == current_schema('project')
    # The two board shapes differ, so a legacy body without its literal is not a
    # v2 board: the schema is what says which rules apply.
    legacy = {key: value for key, value in LEGACY_BOARD.items() if key != 'schema'}
    with pytest.raises(ValidationError):
        validate_board(legacy)


def test_v1_precedence_stays_valid_and_restates_into_documents(project):
    legacy = deepcopy(project)
    legacy['schema'] = 'caiman.project.v1'
    legacy['board'] = legacy.pop('boards')[0]
    legacy['features'][0]['realized_on'] = ['mcu']
    deviation = {'ref': 'synthetic/deviation/v1', 'pod': 'synthetic-alpha', 'note': 'Amends REQ-003'}
    # Already in documents by ref: listed once. Only in precedence: kept as a document pin.
    legacy['precedence'] = [deviation, {'ref': 'synthetic/spec/v1'}]
    assert validate_project(legacy)['precedence'] == legacy['precedence']
    restated = restate_project_draft(legacy)
    assert 'precedence' not in restated
    assert restated['documents'] == [{'ref': 'synthetic/spec/v1'},
                                     {'ref': 'synthetic/deviation/v1', 'pod': 'synthetic-alpha'}]
    assert legacy['precedence'][0]['note'] == 'Amends REQ-003'
    validate_project(restated)
