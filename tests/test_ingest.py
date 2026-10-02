import copy
from dataclasses import replace

import pytest

from caiman.documents.ingest import ValidationError, prepare_document, verify_prepared
from caiman.documents.ingest import digest
from caiman.documents.models import canonical_json, current_schema, is_schema


@pytest.fixture
def metadata():
    return dict(issuer='synthetic', part='demo', doc_type='manual', version='Release / A',
                structure='prose', labels={'public': True, 'compartments': []})


@pytest.fixture
def document(tmp_path):
    path = tmp_path / 'manual.md'
    path.write_bytes(b'# Synthetic\r\n\r\nText.\r\n')
    return path


@pytest.mark.parametrize('labels', [None, {}, {'public': False}, {'public': 'true'},
    {'public': True, 'compartments': ['alpha']}, {'compartments': ['../alpha']}])
def test_invalid_labels_never_admitted(document, metadata, labels):
    metadata['labels'] = labels
    with pytest.raises(ValidationError):
        prepare_document(document, metadata)


@pytest.mark.parametrize('compartments', [['alpha', 'falcon'], ['alpha', 'alpha']])
def test_document_requires_one_compartment_without_silent_deduplication(document, metadata, compartments):
    metadata['labels'] = {'public': False, 'compartments': compartments}
    with pytest.raises(ValidationError, match='exactly one compartment'):
        prepare_document(document, metadata)


def test_unchanged_bytes_and_optional_provenance(document, metadata):
    prepared = prepare_document(document, metadata)
    assert prepared.content == document.read_bytes()
    assert prepared.manifest['files'][0]['size'] == len(prepared.content)
    assert prepared.manifest['version'] == 'Release / A'
    assert 'source' not in prepared.manifest
    assert 'converter' not in prepared.manifest
    verify_prepared(prepared)


def test_named_document_has_optional_requirement_validation_without_a_role(document, metadata):
    metadata.pop('doc_type')
    metadata.pop('structure')
    metadata.update(name='Customer specification', description='Requirements for startup')
    prepared = prepare_document(document, metadata)
    assert 'structure' not in prepared.manifest and 'doc_type' not in prepared.manifest
    verify_prepared(prepared)
    metadata['requirements'] = {'pattern': r'^REQ-\d+$'}
    with pytest.raises(ValidationError, match='No matching requirement IDs'):
        prepare_document(document, metadata)
    document.write_text('# Synthetic specification\nREQ-123: Start correctly.\n')
    prepared = prepare_document(document, metadata)
    assert prepared.manifest['requirements'] == metadata['requirements']
    verify_prepared(prepared)


@pytest.mark.parametrize('text', ['', 'Body\n# Title', '```\n# Fake\n```', '# \ntext',
                                  '# Title\n## Repeat\n## Repeat'])
def test_invalid_heading_structure(document, metadata, text):
    document.write_text(text)
    with pytest.raises(ValidationError) as error:
        prepare_document(document, metadata)
    assert 'headings' in error.value.errors


def test_setext_skips_and_distinct_ancestors(document, metadata):
    document.write_text('Title\n=====\n### Registers\n## Other\n### Registers\n')
    assert len(prepare_document(document, metadata).headings) == 4


def test_inline_requirements(document, metadata):
    document.write_text('# Spec\n**REQ-FLASH-0100**: shall work.\n')
    metadata.update(structure='requirement', requirements={'pattern': r'^REQ-FLASH-\d{4}$'})
    prepare_document(document, metadata)
    document.write_text('# Spec\nNo IDs.\n')
    with pytest.raises(ValidationError):
        prepare_document(document, metadata)


def test_review_is_invalidated_by_file_or_payload_change(document, metadata):
    prepared = prepare_document(document, metadata)
    changed = copy.deepcopy(prepared.manifest)
    changed['labels']['public'] = False
    with pytest.raises(ValidationError):
        verify_prepared(replace(prepared, manifest=changed))
    document.write_text('# Changed\n')
    with pytest.raises(ValidationError):
        verify_prepared(prepared)


@pytest.mark.parametrize('field,value', [('source', {'filename': 'secret.pdf'}),
    ('source', {'pages': True}), ('source', {'sha256': 'bad'}),
    ('converter', {'hosted': 'false'}), ('issuer', '../bad'), ('program', 'also-a-program')])
def test_invalid_metadata(document, metadata, field, value):
    metadata[field] = value
    with pytest.raises(ValidationError):
        prepare_document(document, metadata)


def test_partial_provenance(document, metadata):
    metadata.update(source={'pages': 10}, converter={'name': 'external'})
    result = prepare_document(document, metadata)
    assert result.manifest['source'] == {'pages': 10}
    assert result.manifest['converter'] == {'name': 'external'}


def test_requirement_pattern_can_include_brackets(document, metadata):
    document.write_text('# Spec\n**R[123]**: The synthetic device shall reply.\n')
    metadata.update(structure='requirement', requirements={'pattern': r'^R\[\d+\]$'})
    prepare_document(document, metadata)


def test_lost_compartment_never_becomes_public(document, metadata):
    metadata['labels'] = {'public': False, 'compartments': ['synthetic-alpha']}
    prepared = prepare_document(document, metadata)
    assert not prepared.manifest['labels']['public']
    metadata['labels'].pop('compartments')
    with pytest.raises(ValidationError):
        prepare_document(document, metadata)


def test_invalid_utf8_and_unreadable_file(document, metadata):
    document.write_bytes(b'# Title\n\xff')
    with pytest.raises(ValidationError):
        prepare_document(document, metadata)
    with pytest.raises(ValidationError):
        prepare_document(document.parent / 'missing.md', metadata)


def test_fake_duplicate_headings_in_fence_ignored(document, metadata):
    document.write_text('# Title\n```md\n# Title\n```\n')
    assert len(prepare_document(document, metadata).headings) == 1


@pytest.mark.parametrize('pattern', ['[', '^$'])
def test_invalid_requirement_patterns(document, metadata, pattern):
    metadata.update(structure='requirement', requirements={'pattern': pattern})
    with pytest.raises(ValidationError):
        prepare_document(document, metadata)


@pytest.mark.parametrize('field,value', [
    ('labels', {'public': False, 'compartments': []}),
    ('files', [{'path': '../escape.md', 'sha256': '0' * 64, 'size': 0}]),
    ('schema', 'unknown'), ('original_filename', 'different.md'),
    ('unexpected', 'extra'), ('ingested_at', 'invalid')])
def test_forged_prepared_manifests_rejected(document, metadata, field, value):
    prepared = prepare_document(document, metadata)
    changed = copy.deepcopy(prepared.manifest)
    changed[field] = value
    forged = replace(prepared, manifest=changed, manifest_digest=digest(canonical_json(changed)))
    with pytest.raises(ValidationError):
        verify_prepared(forged)


def test_document_schema_literal_is_current_and_older_spellings_still_read(tmp_path):
    """The literal is a table entry, not an f-string over kind and number (D-13)."""
    path = tmp_path / 'manual.md'
    path.write_text('# Manual\n\n## Registers\nSynthetic text\n')
    prepared = prepare_document(path, {
        'issuer': 'synthetic', 'part': 'chip', 'doc_type': 'manual', 'version': 'v1',
        'structure': 'prose', 'labels': {'public': True, 'compartments': []}})
    assert prepared.manifest['schema'] == current_schema('document') == 'caiman.document.v2'
    assert is_schema('document', 'caiman.document/1')
    assert is_schema('document', 'caiman.document.v1')
    assert not is_schema('document', 'caiman.document.v3')
    assert not is_schema('document', current_schema('board'))
