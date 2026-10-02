"""Pod discovery and stable identity, including existing store folders.

Headers travel with a pod. Folder names and display names may change without
changing its ID. The default is a local preference, never an access level.
"""
import json
from pathlib import Path

from caiman.documents.models import canonical_json, valid_identifier


class PodRegistry:
    def __init__(self, store):
        self.store = store

    def list(self):
        records = []
        if self.store.root.exists():
            self.store._directory(self.store.root)
            for path in sorted(self.store.root.iterdir()):
                if path.name.startswith('.'):
                    continue
                if path.is_symlink():
                    raise ValueError('Pod folders must not be symlinks')
                if not path.is_dir():
                    continue
                header = path / 'pod.json'
                if header.exists():
                    data = json.loads(self.store._read(header))
                    if (not isinstance(data, dict) or set(data) != {'schema', 'id', 'name'} or
                        data['schema'] != 'caiman.pod.v1' or not valid_identifier(data['id']) or
                        not isinstance(data['name'], str) or not data['name'].strip()):
                        raise ValueError(f'Invalid pod header: {header}')
                elif (path / 'refs').exists() or path.name == 'public':
                    data = {'id': path.name, 'name': path.name}
                else:
                    continue
                records.append({'id': data['id'], 'name': data['name'], 'path': path})
        if len({r['id'] for r in records}) != len(records):
            raise ValueError('Duplicate pod ID; register only one local copy of each pod')
        if not any(r['id'] == 'public' for r in records):
            records.insert(0, {'id': 'public', 'name': 'public', 'path': self.store.root / 'public'})
        return records

    def resolve(self, value):
        if not valid_identifier(value):
            raise ValueError('Pod must be a valid ID or folder name')
        records = self.list()
        exact = next((r for r in records if r['id'] == value), None)
        if exact:
            return exact
        matches = [r for r in records if r['path'].name == value]
        if len(matches) == 1:
            return matches[0]
        return {'id': value, 'name': value, 'path': self.store.root / value}

    @property
    def default(self):
        path = self.store.root / '.pods.json'
        if not path.exists():
            return 'public'
        data = json.loads(self.store._read(path))
        if not isinstance(data, dict) or set(data) != {'default'}:
            raise ValueError('Invalid pod preferences')
        record = self.resolve(data['default'])
        if record['id'] not in {r['id'] for r in self.list()}:
            raise ValueError('Default pod is unavailable')
        return record['id']

    def set_default(self, pod):
        record = self.ensure(pod)
        self.store._atomic_write(self.store.root / '.pods.json', canonical_json({'default': record['id']}), immutable=False)

    def ensure(self, pod, *, name=None):
        record = self.resolve(pod)
        path = record['path'] / 'pod.json'
        if not path.exists():
            self.store._atomic_write(path, canonical_json({'schema': 'caiman.pod.v1',
                'id': record['id'], 'name': name or record['name']}), immutable=False)
        return self.resolve(record['id'])

    def selected(self, pods=None):
        if pods is None or pods == [] or pods == () or pods == set():
            return {r['id'] for r in self.list()}
        if not isinstance(pods, (set, frozenset, list, tuple)):
            raise ValueError('Pods must be a collection of IDs')
        return {self.resolve(p)['id'] for p in pods}
