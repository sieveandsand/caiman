"""The public demo dataset must resolve and be safe to add to a populated store."""

import importlib.util
import json
from pathlib import Path
import re
import sys

import pytest

from caiman.configurations.service import ConfigurationService
from caiman.dashboard.workflow import load_state
from caiman.documents.collections import CollectionService
from caiman.storage.store import Store, StoreError

spec = importlib.util.spec_from_file_location('load_examples', Path(__file__).parents[1] / 'scripts/load_examples.py')
examples = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = examples
spec.loader.exec_module(examples)


def snapshot(root):
    return {path.relative_to(root): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob('*') if path.is_file()}


def test_example_graph_and_repeat_import(tmp_path):
    root = tmp_path / 'store'
    plan = examples.prepare_plan(root)
    assert not root.exists()  # Dry run has no destination side effects.
    assert plan.counts == {'documents': 11, 'boards': 3, 'projects': 4, 'collections': 2}
    examples.install(root)
    before = snapshot(root)
    repeated = examples.install(root)
    assert not repeated.documents and not repeated.configurations and not repeated.collections
    assert snapshot(root) == before  # No timestamp churn, ref rewrites, or duplicate objects.

    service = ConfigurationService(Store(root))
    projects = service.list_configs('project', compartments={'demo-microbit', 'demo-macropad'})
    assert len(projects) == 4
    assert service.list_configs('project') == []
    documents = service.list_documents()
    assert len(documents) == 11
    assert len(CollectionService(Store(root)).list_collections()) == 2
    # Feature IDs really exist in their pinned governing documents; the generic
    # service validates selector shape but deliberately does not interpret IDs.
    store = Store(root)
    for record in projects:
        for feature in record['manifest']['features']:
            for pin in feature['governed_by']:
                manifest = store.read_manifest('public', pin['digest'])
                body = store.read_blob('public', 'sha256:' + manifest['files'][0]['sha256']).decode()
                for requirement in pin['requirements']:
                    assert re.search(r'^' + re.escape(requirement) + ':', body, re.MULTILINE)
    sound1 = service.load('project', 'microbit-sound', 'R1-v1.3', compartments={'demo-microbit'})
    sound2 = service.load('project', 'microbit-sound', 'R2-v2', compartments={'demo-microbit'})
    assert sound1['boards'][0]['digest'] != sound2['boards'][0]['digest']
    assert set(d['digest'] for d in sound1['documents']) < set(d['digest'] for d in sound2['documents'])
    hid = service.load('project', 'macropad-hid', 'R1', compartments={'demo-macropad'})
    tone = service.load('project', 'macropad-tone', 'R1', compartments={'demo-macropad'})
    assert hid['boards'] == tone['boards']


def test_preserves_existing_data_and_authoring_state(tmp_path):
    root = tmp_path / 'store'
    store = Store(root)
    state = {'authorized_compartments': ['existing-customer'], 'context': {'legacy': 'kept'}}
    previous = json.dumps(state).encode()
    store._atomic_write(root / '.authoring-state.json', previous, immutable=False)
    service = ConfigurationService(store)
    service.register(service.prepare('board', {
        'board': 'my-board', 'version': 'A', 'parts': [
            {'role': 'mcu', 'vendor': 'mine', 'part': 'chip', 'documents': []}], 'links': []}))
    before = snapshot(root)
    examples.install(root)
    after = snapshot(root)
    for path, value in before.items():
        if str(path) != '.authoring-state.json':
            assert after[path] == value
    assert load_state(root)['authorized_compartments'] == ['demo-macropad', 'demo-microbit', 'existing-customer']
    assert json.loads((root / '.authoring-state.json').read_bytes())['context'] == state['context']
    assert next((root / '.example-import-backups').glob('*.json')).read_bytes() == previous


def test_retry_after_partial_import_reuses_completed_document(tmp_path):
    root = tmp_path / 'store'
    plan = examples.prepare_plan(root)
    result = Store(root).register(plan.documents[0])
    before = snapshot(root)
    examples.install(root)
    after = snapshot(root)
    for path, value in before.items():
        assert after[path] == value
    assert result.manifest_digest in {
        record['digest'] for record in ConfigurationService(Store(root)).list_documents()}


def test_quickstart_copies_match_canonical_examples():
    root = examples.ROOT / 'fixtures'
    for alias, canonical in [
        ('board.json', 'boards/microbit-v2.json'),
        ('project.json', 'projects/microbit-sound-r2.json'),
        ('reference-manual.md', 'documents/microbit-v2-hardware.md'),
        ('customer-specification.md', 'documents/microbit-sound-r1.md'),
    ]:
        assert (root / alias).read_bytes() == (root / canonical).read_bytes()


@pytest.mark.parametrize('kind', ['document', 'board', 'project', 'collection'])
def test_conflicting_ref_aborts_before_any_destination_write(tmp_path, kind):
    root = tmp_path / 'store'
    examples.install(root)
    store = Store(root)
    service = ConfigurationService(store)
    if kind == 'document':
        record = service.list_documents()[0]
        ref = root / 'public/refs/documents' / record['ref']
    elif kind == 'collection':
        record = CollectionService(store).list_collections()[0]
        ref = root / 'public/refs/collections' / record['manifest']['id']
    else:
        record = service.list_configs(kind, compartments={'demo-microbit', 'demo-macropad'})[0]
        ref = service._config_path(kind, record['name'], record['version'], record['compartment'])
    store._atomic_write(ref, ('sha256:' + '0' * 64 + '\n').encode(), immutable=False)
    before = snapshot(root)
    with pytest.raises((StoreError, FileNotFoundError)):
        examples.install(root)
    assert snapshot(root) == before
