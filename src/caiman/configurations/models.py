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

    def selector(self, value, path, compartments, extra=()):
        if not self.object(value, path, {'ref', 'digest', 'compartment', *extra}):
            return
        if not {'ref', 'digest'} & value.keys():
            self.error(path, 'Supply a document ref or digest')
        if 'ref' in value:
            ref = value['ref']
            if self.string(ref, path + '.ref'):
                if '\\' in ref or any(part in ('', '.', '..') for part in ref.split('/')):
                    self.error(path + '.ref', 'Use a relative document ref without traversal segments')
        if 'digest' in value:
            self.digest(value['digest'], path + '.digest')
        if 'compartment' in value:
            compartment = value['compartment']
            if self.string(compartment, path + '.compartment', True) and compartment not in compartments:
                self.error(path + '.compartment', 'Document compartment is outside this configuration')
        if 'note' in value:
            self.string(value['note'], path + '.note')
        if 'notes' in value:
            self.string(value['notes'], path + '.notes')
        if 'requirements' in value:
            self.strings(value['requirements'], path + '.requirements', nonempty=True)

    def selectors(self, value, path, compartments, extra=(), board=False):
        seen = set()
        for index, selector in enumerate(self.sequence(value, path)):
            location = f'{path}.{index}'
            self.selector(selector, location, compartments, extra)
            if not isinstance(selector, dict):
                continue
            if board:
                selector.setdefault('compartment', 'public')
            # Duplicate refs or pinned digests in the same compartment are ambiguous.
            for key in ('ref', 'digest'):
                item = selector.get(key)
                compartment = selector.get('compartment')
                if isinstance(item, str) and (compartment is None or isinstance(compartment, str)):
                    identity = (compartment, key, item)
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
    if not validator.object(data, '', allowed | {'schema', 'derives_from', 'relation'}, required):
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
        # Board-level documents resolve against <vendor>/<board>, mirroring the
        # per-part rule, so the board's own vendor becomes required with them.
        if data.get('documents') and 'vendor' not in data:
            validator.error('vendor', 'Board-level documents need the vendor that issues them')
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


def validate_project(data: dict) -> dict:
    fields = {'project', 'version', 'customer', 'compartments', 'board', 'spec_set', 'documents', 'precedence', 'features'}
    validator, data = _base(data, 'project', fields, fields - {'precedence'})
    validator.string(data.get('customer'), 'customer')
    validator.string(data.get('spec_set'), 'spec_set')
    compartments = validator.strings(data.get('compartments'), 'compartments', True, True)
    if 'public' in compartments:
        validator.error('compartments', 'Projects must carry named compartments, never public')
    board = data.get('board')
    if validator.object(board, 'board', {'name', 'version', 'digest'}, {'name', 'version'}):
        validator.string(board.get('name'), 'board.name', True)
        validator.string(board.get('version'), 'board.version')
        if 'digest' in board:
            validator.digest(board['digest'], 'board.digest')
    allowed = compartments | {'public'}
    validator.selectors(data.get('documents'), 'documents', allowed)
    validator.selectors(data.get('precedence', []), 'precedence', allowed, ('note',))
    names = set()
    features = validator.sequence(data.get('features'), 'features')
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
        validator.strings(feature.get('realized_on', []), path + '.realized_on', True)
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


def validate_project_links(project: dict, board: dict) -> None:
    project = validate_project(project)
    board = validate_board(board)
    validator = _Validator()
    roles = {part['role'] for part in board['parts']}
    if project['board']['name'] != board['board'] or project['board']['version'] != board['version']:
        validator.error('board', 'Board identity and version do not match the project declaration')
    for index, feature in enumerate(project['features']):
        for number, role in enumerate(feature.get('realized_on', [])):
            if role not in roles:
                validator.error(f'features.{index}.realized_on.{number}', 'Part role is not declared on the pinned board')
    validator.finish(project)
