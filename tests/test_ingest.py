import copy
from dataclasses import replace

import pytest

from caiman.documents.ingest import ValidationError, prepare_document, verify_prepared
from caiman.documents.ingest import digest, heading_outline
from caiman.documents.models import canonical_json, current_schema, is_schema


@pytest.fixture
def metadata():
    return dict(issuer='synthetic', part='demo', doc_type='manual', version='Release / A',
                pod='public')


@pytest.fixture
def document(tmp_path):
    path = tmp_path / 'manual.md'
    path.write_bytes(b'# Synthetic\r\n\r\nText.\r\n')
    return path


@pytest.mark.parametrize('labels', [None, {}, {'public': False}, {'public': 'true'},
    {'public': True, 'pods': ['alpha']}, {'pods': ['../alpha']}])
def test_invalid_labels_never_admitted(document, metadata, labels):
    metadata['labels'] = labels
    with pytest.raises(ValidationError):
        prepare_document(document, metadata)


@pytest.mark.parametrize('pods', [['alpha', 'falcon'], ['alpha', 'alpha']])
def test_document_requires_one_pod_without_silent_deduplication(document, metadata, pods):
    metadata['labels'] = {'public': False, 'pods': pods}
    with pytest.raises(ValidationError, match='labels'):
        prepare_document(document, metadata)


def test_unchanged_bytes_and_optional_provenance(document, metadata):
    prepared = prepare_document(document, metadata)
    assert prepared.content == document.read_bytes()
    assert prepared.manifest['files'][0]['size'] == len(prepared.content)
    assert prepared.manifest['version'] == 'Release / A'
    assert 'source' not in prepared.manifest
    assert 'converter' not in prepared.manifest
    verify_prepared(prepared)


def test_named_document_needs_no_type_or_structure(document, metadata):
    metadata.pop('doc_type')
    metadata.update(name='Customer specification', description='Requirements for startup')
    prepared = prepare_document(document, metadata)
    assert 'structure' not in prepared.manifest and 'doc_type' not in prepared.manifest
    verify_prepared(prepared)


@pytest.mark.parametrize('text', ['', 'Body\n# Title', '```\n# Fake\n```', '# \ntext',
                                  '# Title\n## Repeat\n## Repeat'])
def test_unstructured_documents_are_accepted(document, metadata, text):
    document.write_text(text)
    assert prepare_document(document, metadata).content == document.read_bytes()


def test_setext_skips_and_distinct_ancestors(document, metadata):
    document.write_text('Title\n=====\n### Registers\n## Other\n### Registers\n')
    assert len(heading_outline(document.read_text())[0]) == 4


def test_review_is_invalidated_by_file_or_payload_change(document, metadata):
    prepared = prepare_document(document, metadata)
    changed = copy.deepcopy(prepared.manifest)
    changed['issuer'] = 'changed'
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


def test_lost_pod_never_becomes_public(document, metadata):
    prepared = prepare_document(document, metadata, pod='alpha')
    with pytest.raises(ValidationError):
        verify_prepared(replace(prepared, pod='../unsafe'))
    assert 'labels' not in prepared.manifest


def test_invalid_utf8_and_unreadable_file(document, metadata):
    document.write_bytes(b'# Title\n\xff')
    assert prepare_document(document, metadata).content == document.read_bytes()
    with pytest.raises(ValidationError):
        prepare_document(document.parent / 'missing.md', metadata)


def test_fake_duplicate_headings_in_fence_ignored(document, metadata):
    document.write_text('# Title\n```md\n# Title\n```\n')
    assert len(heading_outline(document.read_text())[0]) == 1


@pytest.mark.parametrize('field,value', [
    ('labels', {'public': False, 'pods': []}),
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
        'pod': 'public'})
    assert prepared.manifest['schema'] == current_schema('document') == 'caiman.document.v4'
    assert is_schema('document', 'caiman.document/1')
    assert is_schema('document', 'caiman.document.v1')
    assert not is_schema('document', 'caiman.document.v99')
    assert not is_schema('document', current_schema('board'))


@pytest.mark.parametrize('filename,content', [
    ('manual.pdf', b'%PDF-1.7\n\x00\xff'),
    ('spec.docx', b'PK\x03\x04\x00\xff'),
    ('notes.txt', b'No heading.\n'),
    ('data.bin', bytes(range(256))),
    ('README', b''),
    ('manual.MD', b'---\ntitle: Manual\n---\nBody'),
])
def test_any_file_registers_and_metadata_edits_preserve_bytes(tmp_path, metadata, filename, content):
    from caiman.storage.store import Store
    from caiman.configurations.service import ConfigurationService
    from caiman.documents.edit_service import DocumentEditService

    source = tmp_path / filename
    source.write_bytes(content)
    prepared = prepare_document(source, metadata)
    assert prepared.manifest['files'][0]['path'] == 'document' + source.suffix
    store = Store(tmp_path / 'store')
    registered = store.register(prepared)
    assert store.read_blob('public', registered.blob_digest) == content
    selection = ConfigurationService(store).list_documents()[0]
    service = DocumentEditService(store)
    draft = copy.deepcopy(selection['manifest'])
    draft.update(description='Updated')
    result = service.register(selection, service.prepare(selection, draft))
    assert result['manifest']['files'] == prepared.manifest['files']
    assert source.read_bytes() == content
