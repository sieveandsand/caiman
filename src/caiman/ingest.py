"""Read-only preparation of unchanged Markdown for reviewed registration."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from itertools import chain
from pathlib import Path
import re

from markdown_it import MarkdownIt

from .models import AccessLabel, ValidationError, canonical_json, valid_identifier


METADATA_FIELDS = frozenset({'issuer', 'part', 'program', 'doc_type', 'version', 'structure',
                             'labels', 'silicon_revisions', 'source', 'converter', 'requirements'})
GENERATED_FIELDS = frozenset({'schema', 'original_filename', 'pipeline_version', 'ingested_at', 'files'})


@dataclass(frozen=True)
class Heading:
    path: tuple[str, ...]
    line: int


@dataclass(frozen=True)
class PreparedDocument:
    source_path: Path
    content: bytes
    manifest: dict
    blob_digest: str
    manifest_digest: str
    headings: tuple[Heading, ...]


def digest(content: bytes) -> str:
    return 'sha256:' + hashlib.sha256(content).hexdigest()


def validate_headings(text: str) -> tuple[Heading, ...]:
    tokens = MarkdownIt('commonmark').parse(text)
    errors = []
    if not tokens or tokens[0].type != 'heading_open':
        errors.append('The first nonblank block must be a nonempty heading (line 1)')
    stack = []
    seen = {}
    headings = []
    for index, token in enumerate(tokens):
        if token.type != 'heading_open':
            continue
        inline = tokens[index + 1]
        title = ' '.join(''.join(child.content for child in (inline.children or [])
                                 if child.type in {'text', 'code_inline', 'image'}).split())
        line = token.map[0] + 1
        level = int(token.tag[1:])
        while stack and stack[-1][0] >= level:
            stack.pop()
        path = tuple(item[1] for item in stack) + (title,)
        if not title:
            errors.append(f'Empty heading at line {line}')
        if path in seen:
            errors.append(f'Duplicate heading path at lines {seen[path]} and {line}')
        seen[path] = line
        stack.append((level, title))
        headings.append(Heading(path, line))
    if errors:
        raise ValidationError({'headings': '; '.join(errors)})
    return tuple(headings)


def _text(value):
    return (isinstance(value, str) and bool(value.strip()) and
            not any(ord(char) < 32 or ord(char) == 127 for char in value))


def validate_metadata(metadata: dict) -> dict:
    errors = {}
    if not isinstance(metadata, dict):
        raise ValidationError({'metadata': 'Expected a mapping'})
    for key in metadata.keys() - METADATA_FIELDS:
        errors[str(key)] = 'Unknown or automatically generated field'
    result = {}
    for field in ('issuer', 'doc_type', 'version'):
        value = metadata.get(field)
        if not _text(value) or (field != 'version' and not valid_identifier(value)):
            errors[field] = 'Supply a nonempty value without control characters' if field == 'version' else 'Use letters, digits, dots, hyphens or underscores'
        else:
            result[field] = value
    identities = [field for field in ('part', 'program') if field in metadata]
    if len(identities) != 1:
        errors['part'] = 'Supply exactly one part or program'
    for field in identities:
        if not valid_identifier(metadata[field]):
            errors[field] = 'Use letters, digits, dots, hyphens or underscores'
        else:
            result[field] = metadata[field]
    structure = metadata.get('structure')
    if structure not in ('prose', 'requirement'):
        errors['structure'] = 'Choose prose or requirement'
    else:
        result['structure'] = structure
    labels = metadata.get('labels')
    try:
        if not isinstance(labels, dict) or labels.keys() - {'public', 'compartments'}:
            raise ValueError('Supply explicit public access or named compartments')
        compartments = labels.get('compartments', [])
        if not isinstance(compartments, list) or any(not isinstance(c, str) for c in compartments):
            raise ValueError('Compartments must be a list of names')
        label = AccessLabel(labels.get('public', False), frozenset(compartments))
        if not label.prefixed_labels():
            raise ValueError('Choose public access or at least one compartment')
        result['labels'] = {'public': label.is_public, 'compartments': sorted(label.compartments)}
    except (ValueError, TypeError) as error:
        errors['labels'] = str(error)
    if 'silicon_revisions' in metadata:
        revisions = metadata['silicon_revisions']
        if not isinstance(revisions, list) or any(not _text(v) for v in revisions):
            errors['silicon_revisions'] = 'Supply a list of nonempty revision strings'
        elif revisions:
            result['silicon_revisions'] = list(revisions)
    validators = {
        'source': {'sha256': lambda v: isinstance(v, str) and bool(re.fullmatch('[0-9a-fA-F]{64}', v)),
                   'pages': lambda v: type(v) is int and v > 0},
        'converter': {'name': _text, 'version': _text, 'hosted': lambda v: type(v) is bool},
    }
    for group, fields in validators.items():
        if group not in metadata:
            continue
        values = metadata[group]
        if not isinstance(values, dict):
            errors[group] = 'Supply an object or omit unknown provenance'
            continue
        clean = {}
        for key, value in values.items():
            if key not in fields or not fields[key](value):
                errors[f'{group}.{key}'] = 'Invalid supplied provenance value'
            else:
                clean[key] = value.lower() if key == 'sha256' else value
        if clean:
            result[group] = clean
    if structure == 'requirement':
        requirements = metadata.get('requirements')
        if not isinstance(requirements, dict) or set(requirements) != {'pattern'} or not _text(requirements.get('pattern')):
            errors['requirements.pattern'] = 'Supply a requirement-ID regular expression'
        else:
            try:
                pattern = re.compile(requirements['pattern'])
                if pattern.fullmatch(''):
                    raise ValueError('Pattern must not match an empty ID')
                result['requirements'] = dict(requirements)
            except (re.error, ValueError) as error:
                errors['requirements.pattern'] = str(error)
    elif 'requirements' in metadata:
        errors['requirements.pattern'] = 'Requirement patterns apply only to requirement documents'
    if errors:
        raise ValidationError(errors)
    return result


def prepare_document(path: Path, metadata: dict) -> PreparedDocument:
    manifest = validate_metadata(metadata)
    path = Path(path).expanduser().absolute()
    if path.suffix.lower() not in {'.md', '.markdown'} or not _text(path.name):
        raise ValidationError({'file': 'Select a Markdown file with a usable filename'})
    try:
        if not path.is_file():
            raise OSError('Not a regular file')
        content = path.read_bytes()
        text = content.decode('utf-8')
    except (OSError, UnicodeError) as error:
        raise ValidationError({'file': f'Cannot read UTF-8 Markdown: {error}'}) from error
    headings = validate_headings(text)
    if manifest['structure'] == 'requirement':
        pattern = re.compile(manifest['requirements']['pattern'])
        # Try literal whitespace-delimited IDs as well as conventional IDs
        # embedded in Markdown. Preserve punctuation within IDs such as R[123].
        literal = (candidate for match in re.finditer(r'\S+', text)
                   for candidate in (match[0], match[0].strip('`*_,.;:()<>')))
        conventional = (match[0] for match in re.finditer(r'[\w]+(?:[-.:/][\w]+)*', text))
        candidates = chain(literal, conventional)
        if not any(pattern.fullmatch(candidate) for candidate in candidates):
            raise ValidationError({'requirements.pattern': 'No matching requirement IDs found in the document'})
    blob_digest = digest(content)
    manifest.update(schema='caiman.document/1', original_filename=path.name,
                    pipeline_version='caiman-ingest/0.1',
                    ingested_at=datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
                    files=[{'path': 'document.md', 'sha256': blob_digest[7:], 'size': len(content)}])
    return PreparedDocument(path, content, manifest, blob_digest, digest(canonical_json(manifest)), headings)


def verify_prepared(prepared: PreparedDocument) -> None:
    try:
        manifest = prepared.manifest
        metadata = {key: value for key, value in manifest.items() if key in METADATA_FIELDS}
        validated = validate_metadata(metadata)
        expected_files = [{'path': 'document.md', 'sha256': digest(prepared.content)[7:],
                           'size': len(prepared.content)}]
        timestamp = datetime.fromisoformat(manifest.get('ingested_at', '').replace('Z', '+00:00'))
        unchanged = (prepared.source_path.read_bytes() == prepared.content and
                     digest(prepared.content) == prepared.blob_digest and
                     digest(canonical_json(manifest)) == prepared.manifest_digest and
                     manifest.keys() <= METADATA_FIELDS | GENERATED_FIELDS and
                     validated == metadata and manifest.get('files') == expected_files and
                     manifest.get('schema') == 'caiman.document/1' and
                     manifest.get('pipeline_version') == 'caiman-ingest/0.1' and
                     manifest.get('original_filename') == prepared.source_path.name and
                     timestamp.tzinfo is not None)
    except (OSError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError({'review': 'Document or metadata changed; review again'}) from error
    if not unchanged:
        raise ValidationError({'review': 'Document or metadata changed; review again'})
