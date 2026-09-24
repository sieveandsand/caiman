from copy import deepcopy

import pytest

from caiman.configurations.models import (part_aliases, part_identity, part_vendor_and_part,
                                  validate_board, validate_project, validate_project_links)
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
            'compartments': ['synthetic-alpha'], 'board': {'name': 'synthetic', 'version': '../opaque'},
            'spec_set': 'release / A', 'documents': [{'ref': 'synthetic/spec/v1'}],
            'features': [{'name': 'boot', 'scope': 'required', 'realized_on': ['mcu'],
                          'governed_by': [{'ref': 'synthetic/spec/v1', 'requirements': ['REQ-001..005']}]},
                         {'name': 'ota', 'scope': 'not-used',
                          'related': [{'feature': 'boot', 'relation': 'Shares startup'}]}]}


def test_valid_drafts_are_copies_with_schema_and_public_board(board, project):
    original = deepcopy(board)
    result = validate_board(board)
    assert board == original
    assert result['schema'] == 'caiman.board.v2'
    assert result['version'] == '../opaque'
    assert result['parts'][0]['documents'][0]['compartment'] == 'public'
    assert validate_project(project)['version'] == '.'
    validate_project_links(project, board)


@pytest.mark.parametrize('mutation', [
    lambda x: x.update(customer='Secret'),
    lambda x: x['parts'][0]['documents'][0].update(compartment='synthetic-alpha'),
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
    lambda x: x.update(compartments=[]),
    lambda x: x.update(compartments=['public', 'synthetic-alpha']),
    lambda x: x['documents'][0].update(compartment='synthetic-beta'),
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
    project['features'][0]['realized_on'] = ['missing']
    with pytest.raises(ValidationError):
        validate_project_links(project, board)


def test_digest_only_and_lineage(board, project):
    board['parts'][0]['documents'] = [{'digest': 'sha256:' + 'a' * 64}]
    board.update(derives_from='release / zero', relation='Human supplied change')
    assert validate_board(board)['derives_from'] == 'release / zero'
    project['precedence'] = [{'digest': 'sha256:' + 'b' * 64, 'note': 'Explicit authority'}]
    assert validate_project(project)['precedence'][0]['note'] == 'Explicit authority'


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


@pytest.mark.parametrize('field,value', [('board', []), ('compartments', [None]),
    ('features', [None]), ('documents', [None]), ('precedence', [{'requirements': ['REQ-1']}])])
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
    assert result['schema'] == 'caiman.board.v2'
    assert result['parts'][0]['aliases'] == {'refdes': 'U1', 'mpn': 'CHIP-0001'}
    assert result['documents'][0]['compartment'] == 'public'


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
    # Board-level documents resolve against <vendor>/<board>, so vendor is required.
    lambda x: x.update(documents=[{'ref': 'synthetic/synthetic/user-guide/v1'}]),
    lambda x: x.update(schema='caiman.board/2'),
    lambda x: x.update(schema='caiman.board.v3'),
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
    current, older = accepted_schemas(kind)
    assert current == current_schema(kind)
    data = deepcopy(LEGACY_BOARD) if kind == 'board' else dict(project, schema=older)
    assert validate(data)['schema'] == older


def test_omitting_the_schema_authors_the_current_version(board, project):
    assert validate_board(board)['schema'] == current_schema('board')
    assert validate_project(project)['schema'] == current_schema('project')
    # The two board shapes differ, so a legacy body without its literal is not a
    # v2 board: the schema is what says which rules apply.
    legacy = {key: value for key, value in LEGACY_BOARD.items() if key != 'schema'}
    with pytest.raises(ValidationError):
        validate_board(legacy)
