"""Read-only preparation of unchanged files for reviewed registration."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
from uuid import uuid4

from markdown_it import MarkdownIt

from caiman.documents.models import ValidationError, canonical_json, current_schema, is_schema, valid_identifier


METADATA_FIELDS = frozenset({'name', 'description', 'issuer', 'part', 'program', 'doc_type', 'version',
                             'silicon_revisions', 'source', 'converter'})
GENERATED_FIELDS = frozenset({'schema', 'original_filename', 'pipeline_version', 'ingested_at', 'files', 'document_id', 'previous'})


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
    pod: str = "public"


def digest(content: bytes) -> str:
    return 'sha256:' + hashlib.sha256(content).hexdigest()


def heading_outline(text: str) -> tuple[tuple[Heading, ...], list[str]]:
    """Best-effort Markdown heading paths and navigation diagnostics."""
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
    return tuple(headings), errors


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
    named = 'name' in metadata
    for field in (('issuer', 'version') if named else ('issuer', 'doc_type', 'version')):
        value = metadata.get(field)
        if not _text(value) or (field != 'version' and not valid_identifier(value)):
            errors[field] = 'Supply a nonempty value without control characters' if field == 'version' else 'Use letters, digits, dots, hyphens or underscores'
        else:
            result[field] = value
    for field in ('name', 'description', 'doc_type'):
        if field in metadata:
            if not _text(metadata[field]):
                errors[field] = 'Supply nonempty text without control characters'
            else:
                result[field] = metadata[field]
    identities = [field for field in ('part', 'program') if field in metadata]
    if len(identities) != 1:
        errors['part'] = 'Supply exactly one part or program'
    for field in identities:
        if not valid_identifier(metadata[field]):
            errors[field] = 'Use letters, digits, dots, hyphens or underscores'
        else:
            result[field] = metadata[field]
    if 'silicon_revisions' in metadata:
        revisions = metadata['silicon_revisions']
        if not isinstance(revisions, list) or any(not _text(v) for v in revisions):
            errors['silicon_revisions'] = 'Supply a list of nonempty revision strings'
        elif revisions:
            result['silicon_revisions'] = list(revisions)
    validators = {
        'source': {'sha256': lambda v: isinstance(v, str) and bool(re.fullmatch('[0-9a-fA-F]{64}', v)),
                   'pages': lambda v: type(v) is int and v > 0},
        'converter': {'name': _text},
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
    if errors:
        raise ValidationError(errors)
    return result


def document_path(filename: str) -> str:
    """Keep the file extension without allowing source names to become paths."""
    return 'document' + Path(filename).suffix


def prepare_document(path: Path, metadata: dict, *, pod: str = "public") -> PreparedDocument:
    metadata = dict(metadata)
    pod = metadata.pop("pod", pod)
    if not valid_identifier(pod):
        raise ValidationError({"pod": "Choose a pod"})
    manifest = validate_metadata(metadata)
    path = Path(path).expanduser().absolute()
    if not _text(path.name):
        raise ValidationError({'file': 'Select a file with a usable filename'})
    try:
        if not path.is_file():
            raise OSError('Not a regular file')
        content = path.read_bytes()
    except OSError as error:
        raise ValidationError({'file': f'Cannot read file: {error}'}) from error
    blob_digest = digest(content)
    manifest.update(schema=current_schema('document'), document_id=uuid4().hex, previous=None, original_filename=path.name,
                    pipeline_version='caiman-ingest/0.1',
                    ingested_at=datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z'),
                    files=[{'path': document_path(path.name), 'sha256': blob_digest[7:], 'size': len(content)}])
    return PreparedDocument(path, content, manifest, blob_digest, digest(canonical_json(manifest)), pod)


def verify_prepared(prepared: PreparedDocument) -> None:
    try:
        if not valid_identifier(prepared.pod):
            raise ValueError("Invalid pod")
        manifest = prepared.manifest
        metadata = {key: value for key, value in manifest.items() if key in METADATA_FIELDS}
        validated = validate_metadata(metadata)
        expected_files = [{'path': document_path(prepared.source_path.name), 'sha256': digest(prepared.content)[7:],
                           'size': len(prepared.content)}]
        timestamp = datetime.fromisoformat(manifest.get('ingested_at', '').replace('Z', '+00:00'))
        unchanged = (prepared.source_path.read_bytes() == prepared.content and
                     digest(prepared.content) == prepared.blob_digest and
                     digest(canonical_json(manifest)) == prepared.manifest_digest and
                     manifest.keys() <= METADATA_FIELDS | GENERATED_FIELDS and
                     validated == metadata and manifest.get('files') == expected_files and
                     is_schema('document', manifest.get('schema')) and
                     valid_identifier(manifest.get('document_id')) and manifest.get('previous') is None and
                     manifest.get('pipeline_version') == 'caiman-ingest/0.1' and
                     manifest.get('original_filename') == prepared.source_path.name and
                     timestamp.tzinfo is not None)
    except (OSError, TypeError, ValueError, AttributeError) as error:
        raise ValidationError({'review': 'Document or metadata changed; review again'}) from error
    if not unchanged:
        raise ValidationError({'review': 'Document or metadata changed; review again'})
