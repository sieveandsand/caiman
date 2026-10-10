"""Pure validation of explicitly declared board and project snapshots."""

from copy import deepcopy
import re

from caiman.documents.models import ValidationError, accepted_schemas, current_schema, valid_identifier


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and not any(ord(c) < 32 or ord(c) == 127 for c in value)


class _Validator:
    def __init__(self):
        self.errors = {}

    def error(self, path, message):
        self.errors[path] = message

    def object(self, value, path, allowed, required=()):
        if not isinstance(value, dict):
            self.error(path, 'Expected an object')
            return False
        for key in value.keys() - set(allowed):
            self.error(f'{path}.{key}'.strip('.'), 'Unknown field')
        for key in set(required) - value.keys():
            self.error(f'{path}.{key}'.strip('.'), 'Required field')
        return True

    def string(self, value, path, identifier=False):
        if not _text(value) or (identifier and not valid_identifier(value)):
            self.error(path, 'Expected a safe identifier' if identifier else 'Expected nonempty text without control characters')
            return False
        return True

    def sequence(self, value, path, nonempty=False):
        if not isinstance(value, list) or (nonempty and not value):
            self.error(path, 'Expected a nonempty list' if nonempty else 'Expected a list')
            return []
        return value

    def strings(self, value, path, identifier=False, nonempty=False):
        items = self.sequence(value, path, nonempty)
        seen = set()
        for index, item in enumerate(items):
            location = f'{path}.{index}'
            if self.string(item, location, identifier):
                if item in seen:
                    self.error(location, 'Duplicate value')
                seen.add(item)
        return seen

    def digest(self, value, path):
        if not isinstance(value, str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', value):
            self.error(path, 'Expected a complete lowercase sha256 digest')

    def lineage(self, data):
        if ('derives_from' in data) != ('relation' in data):
            self.error('derives_from', 'Lineage requires both derives_from and a human-written relation')
        for key in ('derives_from', 'relation'):
            if key in data:
                self.string(data[key], key)

    def selector(self, value, path, pods, extra=(), collections=False):
        if collections and isinstance(value, dict) and 'collection' in value:
            self.object(value, path, {'pod', 'collection', 'digest'}, {'pod', 'collection'})
            self.string(value.get('pod'), path + '.pod', True)
            self.string(value['collection'], path + '.collection', True)
            if 'digest' in value:
                self.digest(value['digest'], path + '.digest')
            return
        if not self.object(value, path, {'ref', 'digest', 'pod', 'document', 'blob', *extra}):
            return
        if not {'ref', 'digest', 'document'} & value.keys():
            self.error(path, 'Supply a document ref, manifest digest, or document ID and blob')
        if 'document' in value:
            if 'ref' in value or 'digest' in value:
                self.error(path, 'Use either document ID and blob, or a ref/manifest digest')
            self.string(value['document'], path + '.document', True)
            self.digest(value.get('blob'), path + '.blob')
        elif 'blob' in value:
            self.error(path + '.document', 'A blob pin requires a document ID')
        if 'ref' in value:
            ref = value['ref']
            if self.string(ref, path + '.ref'):
                if '\\' in ref or any(part in ('', '.', '..') for part in ref.split('/')):
                    self.error(path + '.ref', 'Use a relative document ref without traversal segments')
        if 'digest' in value:
            self.digest(value['digest'], path + '.digest')
        if 'pod' in value:
            pod = value['pod']
            self.string(pod, path + '.pod', True)
        if 'note' in value:
            self.string(value['note'], path + '.note')
        if 'notes' in value:
            self.string(value['notes'], path + '.notes')
        if 'requirements' in value:
            self.strings(value['requirements'], path + '.requirements', nonempty=True)

    def selectors(self, value, path, pods, extra=(), board=False, collections=False):
        seen = set()
        for index, selector in enumerate(self.sequence(value, path)):
            location = f'{path}.{index}'
            self.selector(selector, location, pods, extra, collections=collections)
            if not isinstance(selector, dict):
                continue
            # Duplicate refs or pinned digests in the same pod are ambiguous.
            for key in ('ref', 'digest', 'document', 'collection'):
                item = selector.get(key)
                pod = selector.get('pod')
                if isinstance(item, str) and (pod is None or isinstance(pod, str)):
                    identity = (pod, key, item)
                    if identity in seen:
                        self.error(location, 'Duplicate document selector')
                    seen.add(identity)

    def finish(self, data):
        if self.errors:
            raise ValidationError(self.errors)
        return data


def declared_schema(data, kind):
    """The accepted literal a snapshot declares, or the current one when absent.

    Peeked before validation because the board's field rules follow its schema
    version. An unrecognised literal reads as the current one here and is
    reported by ``_base``.
    """
    declared = data.get('schema') if isinstance(data, dict) else None
    return declared if declared in accepted_schemas(kind) else current_schema(kind)


def _base(data, kind, allowed, required):
    validator = _Validator()
    if not validator.object(data, '', allowed | {'schema', 'derives_from', 'relation', 'pod'}, required):
        validator.finish(data)
    data = deepcopy(data)
    accepted = accepted_schemas(kind)
    if 'schema' in data and data['schema'] not in accepted:
        validator.error('schema', 'Expected ' + ' or '.join(accepted))
    # Default, never overwrite: rewriting a stored literal would change the
    # canonical bytes of a snapshot that is supposed to be immutable.
    data.setdefault('schema', current_schema(kind))
    validator.string(data.get(kind), kind, True)
    validator.string(data.get('version'), 'version')
    if 'pod' in data:
        validator.string(data['pod'], 'pod', True)
    validator.lineage(data)
    return validator, data


def _endpoint(value, roles, validator, path):
    if not validator.string(value, path):
        return
    if value in roles:
        return
    # Exact role wins; otherwise take a declared role followed by a peripheral.
    if any(value.startswith(role + '.') and _text(value[len(role) + 1:]) for role in roles):
        return
    validator.error(path, 'Endpoint must name a declared part role or role.PERIPHERAL')


LEGACY_BOARD_SCHEMA = 'caiman.board/1'


def board_is_legacy(data) -> bool:
    """True for a `caiman.board/1` snapshot: packed part identity, no notes."""
    return declared_schema(data, 'board') == LEGACY_BOARD_SCHEMA


def part_identity(part: dict) -> str:
    """Render `vendor/part` from either schema; v1 already packs the two."""
    if not isinstance(part, dict):
        return ''
    vendor, identity = part.get('vendor'), part.get('part', '')
    return f'{vendor}/{identity}' if vendor else str(identity)


def part_vendor_and_part(part: dict) -> tuple[str, str]:
    """Split identity for either schema; v1 packs vendor and part into one field."""
    if not isinstance(part, dict):
        return '', ''
    if part.get('vendor'):
        return part['vendor'], str(part.get('part', ''))
    vendor, _, name = str(part.get('part', '')).partition('/')
    return vendor, name


def part_aliases(part: dict) -> dict:
    """Cross-domain identifiers, lifting a v1 `refdes` into the v2 shape."""
    if not isinstance(part, dict):
        return {}
    aliases = dict(part.get('aliases') or {})
    if part.get('refdes') and 'refdes' not in aliases:
        aliases['refdes'] = part['refdes']
    return aliases


def _aliases(value, validator, path):
    """Declared strings that nothing interprets; only their shape is checked."""
    if not isinstance(value, dict) or not value:
        validator.error(path, 'Expected a nonempty object of cross-domain identifiers')
        return
    for key in sorted(value, key=str):
        if not valid_identifier(key):
            validator.error(path, 'Alias names use letters, digits, dots, hyphens or underscores')
        else:
            validator.string(value[key], f'{path}.{key}')


def validate_board(data: dict) -> dict:
    legacy = board_is_legacy(data)
    allowed = {'board', 'version', 'parts', 'links'}
    if not legacy:
        allowed |= {'vendor', 'notes', 'documents'}
    validator, data = _base(data, 'board', allowed, {'board', 'version', 'parts'})
    if not legacy:
        if 'vendor' in data:
            validator.string(data['vendor'], 'vendor', True)
        if 'notes' in data:
            validator.string(data['notes'], 'notes')
        validator.selectors(data.get('documents', []), 'documents', {'public'}, ('notes',), board=True)
    part_fields = {'role', 'part', 'silicon_revision', 'documents'}
    part_fields |= {'refdes'} if legacy else {'vendor', 'aliases', 'notes'}
    part_required = {'role', 'part', 'documents'} | (set() if legacy else {'vendor'})
    roles = set()
    for index, part in enumerate(validator.sequence(data.get('parts'), 'parts', True)):
        path = f'parts.{index}'
        if not validator.object(part, path, part_fields, part_required):
            continue
        role = part.get('role')
        if validator.string(role, path + '.role', True):
            if role in roles:
                validator.error(path + '.role', 'Duplicate part role')
            roles.add(role)
        identity = part.get('part')
        if legacy:
            if not isinstance(identity, str) or len(identity.split('/')) != 2 or not all(valid_identifier(x) for x in identity.split('/')):
                validator.error(path + '.part', 'Expected issuer/part identity')
        else:
            validator.string(part.get('vendor'), path + '.vendor', True)
            validator.string(identity, path + '.part', True)
            if 'aliases' in part:
                _aliases(part['aliases'], validator, path + '.aliases')
            if 'notes' in part:
                validator.string(part['notes'], path + '.notes')
        for key in ('silicon_revision', 'refdes'):
            if key in part:
                validator.string(part[key], path + '.' + key)
        validator.selectors(part.get('documents'), path + '.documents', {'public'},
                            () if legacy else ('notes',), board=True)
    link_fields = {'name', 'between', 'from', 'to'} | (set() if legacy else {'notes'})
    names = set()
    for index, link in enumerate(validator.sequence(data.get('links', []), 'links')):
        path = f'links.{index}'
        if not validator.object(link, path, link_fields, {'name'}):
            continue
        if 'notes' in link:
            validator.string(link['notes'], path + '.notes')
        name = link.get('name')
        if validator.string(name, path + '.name', True):
            if name in names:
                validator.error(path + '.name', 'Duplicate link name')
            names.add(name)
        if 'between' in link:
            if 'from' in link or 'to' in link:
                validator.error(path, 'Choose between or from/to endpoints')
            endpoints = validator.sequence(link['between'], path + '.between', True)
            if len(endpoints) < 2:
                validator.error(path + '.between', 'At least two endpoints required')
            validator.strings(endpoints, path + '.between')
            for number, endpoint in enumerate(endpoints):
                _endpoint(endpoint, roles, validator, f'{path}.between.{number}')
        else:
            for key in ('from', 'to'):
                endpoints = link.get(key)
                if isinstance(endpoints, str):
                    endpoints = [endpoints]
                endpoints = validator.sequence(endpoints, path + '.' + key, True)
                validator.strings(endpoints, path + '.' + key)
                for number, endpoint in enumerate(endpoints):
                    _endpoint(endpoint, roles, validator, f'{path}.{key}.{number}')
    return validator.finish(data)


LEGACY_PROJECT_SCHEMAS = ('caiman.project.v1', 'caiman.project/1')


def project_is_legacy(data) -> bool:
    """True for a v1 project snapshot: one `board` and bare `realized_on` roles."""
    return declared_schema(data, 'project') in LEGACY_PROJECT_SCHEMAS


def project_boards(project: dict) -> list[dict]:
    """Every pinned board selector, in declared order; a v1 project pins exactly one."""
    if not isinstance(project, dict):
        return []
    if project_is_legacy(project):
        board = project.get('board')
        return [board] if isinstance(board, dict) else []
    boards = project.get('boards')
    return [board for board in boards if isinstance(board, dict)] if isinstance(boards, list) else []


def realized_parts(project: dict, feature: dict) -> list[tuple[str, str, str]]:
    """`(board, version, role)` for each part a feature is realized on.

    A v1 role can only name a part on the project's one pinned board; v2 entries
    say which board version they mean, because roles repeat across boards.
    """
    entries = feature.get('realized_on', []) if isinstance(feature, dict) else []
    if project_is_legacy(project):
        board = project.get('board') or {}
        return [(board.get('name'), board.get('version'), role) for role in entries]
    return [(entry.get('board'), entry.get('version'), entry.get('role')) for entry in entries if isinstance(entry, dict)]


def restate_project_draft(data: dict) -> dict:
    """Restate a v1 project draft in the current schema.

    Nothing is guessed: every v1 role already names a part on the one pinned
    board, so the rewrite only spells that board out. v2 has no precedence; a
    document pinned only there moves to `documents` so the pin set loses nothing,
    and its order and note are dropped. The stored v1 snapshot is untouched;
    registering the result creates a new snapshot, and review shows the rewrite.
    """
    result = deepcopy(data)
    if not project_is_legacy(result):
        return result
    result['schema'] = current_schema('project')
    board = result.pop('board', {})
    result['boards'] = [board]
    precedence = result.pop('precedence', [])
    if isinstance(precedence, list) and isinstance(result.get('documents'), list):
        for selector in precedence:
            pin = {key: value for key, value in selector.items() if key != 'note'} if isinstance(selector, dict) else selector
            if pin not in result['documents'] and not _same_pin(pin, result['documents']):
                result['documents'].append(pin)
    name, version = (board.get('name', ''), board.get('version', '')) if isinstance(board, dict) else ('', '')
    for feature in result.get('features', []):
        if isinstance(feature, dict) and isinstance(feature.get('realized_on'), list):
            feature['realized_on'] = [{'board': name, 'version': version, 'role': role}
                                      for role in feature['realized_on']]
    return result


def _same_pin(selector, documents) -> bool:
    """A selector naming, by digest or by ref, a document already in the list."""
    if not isinstance(selector, dict):
        return False
    for document in documents:
        if not isinstance(document, dict) or document.get('pod') != selector.get('pod'):
            continue
        if 'document' in selector and (document.get('document'), document.get('blob')) == (selector['document'], selector.get('blob')):
            return True
        if 'digest' in selector and document.get('digest') == selector['digest']:
            return True
        if 'digest' not in selector and 'ref' in selector and document.get('ref') == selector['ref']:
            return True
    return False


def _board_selector(board, validator, path) -> bool:
    if not validator.object(board, path, {'name', 'version', 'digest', 'pod'}, {'name', 'version'}):
        return False
    if 'pod' in board:
        validator.string(board['pod'], path + '.pod', True)
    named = validator.string(board.get('name'), path + '.name', True)
    versioned = validator.string(board.get('version'), path + '.version')
    if 'digest' in board:
        validator.digest(board['digest'], path + '.digest')
    return named and versioned


def validate_project(data: dict) -> dict:
    legacy = project_is_legacy(data)
    fields = {'project', 'version', 'customer', 'spec_set', 'documents', 'features'}
    # v1 snapshots may still carry a declared precedence; v2 has none.
    fields |= {'board', 'precedence'} if legacy else {'boards'}
    validator, data = _base(data, 'project', fields, fields - {'precedence', 'spec_set', 'features'})
    validator.string(data.get('customer'), 'customer')
    if 'spec_set' in data:
        validator.string(data['spec_set'], 'spec_set')
    pinned = set()
    if legacy:
        if _board_selector(data.get('board'), validator, 'board'):
            pinned.add((data['board']['name'], data['board']['version']))
    else:
        if 'board' in data:
            validator.error('board', 'One board object is the caiman.project.v1 shape; list pinned boards under boards')
        for index, board in enumerate(validator.sequence(data.get('boards'), 'boards')):
            path = f'boards.{index}'
            if _board_selector(board, validator, path):
                # The same board may be pinned at several versions; the same
                # version twice would make realized_on entries ambiguous.
                identity = (board['name'], board['version'])
                if identity in pinned:
                    validator.error(path, 'Duplicate board version; pin each board version once')
                pinned.add(identity)
    allowed = set()
    validator.selectors(data.get('documents'), 'documents', allowed, collections=True)
    # Either one may start empty and be filled in by a later edit, but not both.
    if not legacy and data.get('boards') == [] and data.get('documents') == []:
        validator.error('boards', 'Pin at least one board or add at least one document')
    if legacy:
        validator.selectors(data.get('precedence', []), 'precedence', allowed, ('note',))
    names = set()
    features = validator.sequence(data.get('features', []), 'features')
    for index, feature in enumerate(features):
        path = f'features.{index}'
        if not validator.object(feature, path, {'name', 'scope', 'governed_by', 'realized_on', 'related'}, {'name', 'scope'}):
            continue
        name = feature.get('name')
        if validator.string(name, path + '.name', True):
            if name in names:
                validator.error(path + '.name', 'Duplicate feature name')
            names.add(name)
        if feature.get('scope') not in ('required', 'not-used'):
            validator.error(path + '.scope', 'Choose required or not-used; implementation status is not supported')
        validator.selectors(feature.get('governed_by', []), path + '.governed_by', allowed, ('requirements',))
        if legacy:
            validator.strings(feature.get('realized_on', []), path + '.realized_on', True)
        else:
            _realized_on(feature.get('realized_on', []), pinned, validator, path + '.realized_on')
        seen_related = set()
        for number, related in enumerate(validator.sequence(feature.get('related', []), path + '.related')):
            location = f'{path}.related.{number}'
            if not validator.object(related, location, {'feature', 'relation'}, {'feature', 'relation'}):
                continue
            target = related.get('feature')
            if validator.string(target, location + '.feature', True):
                if target in seen_related or target == name:
                    validator.error(location + '.feature', 'Duplicate or self-related feature')
                seen_related.add(target)
            validator.string(related.get('relation'), location + '.relation')
    for index, feature in enumerate(features):
        if not isinstance(feature, dict) or not isinstance(feature.get('related', []), list):
            continue
        for number, related in enumerate(feature.get('related', [])):
            if isinstance(related, dict) and isinstance(related.get('feature'), str) and related['feature'] not in names:
                validator.error(f'features.{index}.related.{number}.feature', 'Referenced feature is not declared in this project')
    return validator.finish(data)


def _realized_on(value, pinned, validator, path):
    seen = set()
    for number, entry in enumerate(validator.sequence(value, path)):
        location = f'{path}.{number}'
        if not validator.object(entry, location, {'board', 'version', 'role'}, {'board', 'version', 'role'}):
            continue
        valid = all([validator.string(entry.get('board'), location + '.board', True),
                     validator.string(entry.get('version'), location + '.version'),
                     validator.string(entry.get('role'), location + '.role', True)])
        if not valid:
            continue
        identity = (entry['board'], entry['version'], entry['role'])
        if identity in seen:
            validator.error(location, 'Duplicate part')
        seen.add(identity)
        # Exact label match against this project's own pins; versions are
        # never compared, ordered, or matched loosely (I-7).
        if identity[:2] not in pinned:
            validator.error(location, 'Board version is not pinned by this project')


def validate_project_links(project: dict, boards: list[dict]) -> None:
    """Check each pinned board manifest against its selector, and every realized part.

    `boards` holds one board manifest per pinned selector, in declared order.
    """
    project = validate_project(project)
    boards = [validate_board(board) for board in boards]
    legacy = project_is_legacy(project)
    selectors = project_boards(project)
    validator = _Validator()
    if len(boards) != len(selectors):
        validator.error('board' if legacy else 'boards', 'Expected one board manifest per pinned board')
    roles = {}
    for index, (selector, board) in enumerate(zip(selectors, boards)):
        if (selector['name'], selector['version']) != (board['board'], board['version']):
            validator.error('board' if legacy else f'boards.{index}',
                            'Board identity and version do not match the project declaration')
        roles[(board['board'], board['version'])] = {part['role'] for part in board['parts']}
    for index, feature in enumerate(project.get('features', [])):
        for number, (name, version, role) in enumerate(realized_parts(project, feature)):
            if role not in roles.get((name, version), set()):
                validator.error(f'features.{index}.realized_on.{number}', 'Part role is not declared on that pinned board')
    validator.finish(project)
