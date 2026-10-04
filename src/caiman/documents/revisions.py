"""Complete immutable manifest revisions with one current pointer per document."""
from caiman.documents.models import valid_identifier
from caiman.storage.store import StoreError, _hex


class DocumentRevisions:
    def __init__(self, store):
        self.store = store

    def ref(self, pod, document):
        if not valid_identifier(document):
            raise StoreError('Invalid document ID')
        return self.store.pod_path(pod) / 'refs' / 'document-heads' / document

    def current(self, pod, document, blob=None):
        path = self.ref(pod, document)
        try:
            value = self.store._read(path).decode('ascii').strip()
        except (OSError, UnicodeError) as error:
            raise StoreError('Current document manifest is unavailable locally') from error
        _hex(value)
        manifest = self.store.read_manifest(pod, value)
        if manifest.get('document_id') != document:
            raise StoreError('Current manifest belongs to a different document')
        actual = 'sha256:' + manifest['files'][0]['sha256']
        if blob is not None and actual != blob:
            raise StoreError('Current document body does not match the pinned blob')
        return value, manifest

    def history(self, pod, document):
        """Newest first; each entry is an exact stored manifest, never an overlay."""
        value, manifest = self.current(pod, document)
        files = manifest['files']
        seen = set()
        records = []
        while value is not None:
            if value in seen:
                raise StoreError('Document revision history contains a cycle')
            seen.add(value)
            manifest = self.store.read_manifest(pod, value)
            if manifest.get('document_id') != document or manifest['files'] != files:
                raise StoreError('Document history changes identity or body')
            records.append({'digest': value, 'manifest': manifest})
            value = manifest['previous']
        return records
