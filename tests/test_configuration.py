from copy import deepcopy

import pytest

from caiman.configuration import validate_board, validate_project, validate_project_links
from caiman.models import ValidationError


@pytest.fixture
def board():
    return {'board': 'synthetic', 'version': '../opaque', 'parts': [
        {'role': 'mcu', 'part': 'synthetic/chip', 'documents': [{'ref': 'synthetic/chip/manual/v1'}]},
        {'role': 'flash', 'part': 'synthetic/flash', 'documents': []}],
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
    assert result['schema'] == 'caiman.board/1'
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
