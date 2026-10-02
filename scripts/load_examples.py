#!/usr/bin/env python3
"""Validate or add the checked-in examples, offline, through Caiman's services.

Default: validate in a temporary store and check the destination for conflicts.
--install: add missing entries and make example pods available.
Run with the checkout's Python environment. Close other store writers first.
"""

import argparse
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from caiman.cli.commands import store_path
from caiman.configurations.service import ConfigurationService
from caiman.dashboard.workflow import STATE_FILE, load_state
from caiman.storage.legacy import manifest_view
from caiman.documents.collections import CollectionService
from caiman.documents.ingest import prepare_document
from caiman.documents.models import canonical_json
from caiman.storage.store import Store, StoreError


@dataclass
class Plan:
    documents: list
    configurations: list
    collections: list
    state: dict
    counts: dict


def verify_sources(fixtures):
    """Check every vendored source block against the pinned upstream byte hash."""
    lock = json.loads((fixtures / 'sources.lock.json').read_text())
    for entry in lock['files']:
        text = (fixtures / entry['document']).read_text()
        section = text.split('\n## ' + entry['heading'] + '\n', 1)[1]
        source = section.split('````text\n', 1)[1].split('````\n', 1)[0]
        if not entry['final_newline']:
            source = source.removesuffix('\n')
        if hashlib.sha256(source.encode()).hexdigest() != entry['sha256']:
            raise StoreError(f'Upstream source bytes changed: {entry["path"]}')


def document_ref(store, manifest):
    components = [manifest['issuer'], manifest.get('part') or manifest['program'],
                  manifest.get('name') or manifest['doc_type'], manifest['version']]
    return store.root / 'public/refs/documents' / Path(*(quote(s, safe='') for s in components))


def exists(path):
    return path.exists() or path.is_symlink()


def prepare_plan(root, fixtures=ROOT / 'fixtures'):
    """Resolve the whole graph before touching the destination, including on reruns."""
    verify_sources(fixtures)
    dataset = json.loads((fixtures / 'dataset.json').read_text())
    if dataset['format'] != 'caiman.examples.v1':
        raise StoreError('Unknown example dataset format')
    target = Store(root)
    target_configs = ConfigurationService(target)
    target_collections = CollectionService(target)
    # Validate existing preferences before any registration; retain legacy context verbatim.
    load_state(root)
    state_path = target.root / STATE_FILE
    state = json.loads(target._read(state_path)) if exists(state_path) else {'authorized_compartments': []}
    plan = Plan([], [], [], state, {'documents': 0, 'boards': 0, 'projects': 0, 'collections': 0})
    with TemporaryDirectory(prefix='caiman-examples-') as temporary:
        staging = Store(Path(temporary) / 'store')
        configs = ConfigurationService(staging)
        collection_members = {'microbit': [], 'macropad': []}
        for entry in dataset['documents']:
            if entry['metadata'].get('labels') != {'public': True, 'compartments': []}:
                raise StoreError('This example dataset only imports explicitly public documents')
            prepared = prepare_document(fixtures / entry['path'], manifest_view(entry['metadata']))
            ref = document_ref(target, prepared.manifest)
            if exists(ref):
                value = target_configs._read_ref(ref)
                previous = target.read_manifest('public', value)
                expected = dict(prepared.manifest, ingested_at=previous.get('ingested_at'))
                if previous != expected or target.read_blob('public', prepared.blob_digest) != prepared.content:
                    raise StoreError(f'Existing document differs; refusing to repoint {ref}')
                # Reuse the original ingestion timestamp and digest so every dependent pin stays stable.
                prepared = replace(prepared, manifest=previous, manifest_digest=value)
            else:
                plan.documents.append(prepared)
            staging.register(prepared)
            family = 'macropad' if 'macropad' in entry['path'] else 'microbit'
            collection_members[family].append({'pod': 'public', 'digest': prepared.manifest_digest})
            plan.counts['documents'] += 1
        for kind, paths in [('board', dataset['boards']), ('project', dataset['projects'])]:
            for path in paths:
                draft = json.loads((fixtures / path).read_text())
                prepared = configs.prepare(kind, draft)
                refs = [target_configs._config_path(kind, draft[kind], draft['version'], compartment)
                        for compartment in (prepared.pod,)]
                present = [exists(ref) for ref in refs]
                for ref, found in zip(refs, present):
                    if found and target_configs._read_ref(ref) != prepared.digest:
                        raise StoreError(f'Existing configuration differs; refusing to repoint {ref}')
                if any(present):
                    # Verify existing objects and pinned documents, not just ref text.
                    compartment = prepared.pod
                    target_configs._read_config(kind, compartment, prepared.digest,
                                                set(draft.get('compartments', [])))
                if not all(present):
                    plan.configurations.append(prepared)
                configs.register(prepared)
                plan.counts[kind + 's'] += 1
        collections = CollectionService(staging)
        for family, members in collection_members.items():
            prepared = collections.prepare({
                'id': f'caiman-examples-{family}',
                'name': 'micro:bit sound' if family == 'microbit' else 'MacroPad applications',
                'description': 'Pinned upstream source references and clearly identified Caiman acceptance examples.',
                'documents': members,
            })
            ref = target_collections._ref('public', prepared['manifest']['id'])
            if exists(ref):
                if target_configs._read_ref(ref) != prepared['digest']:
                    raise StoreError(f'Existing collection differs; refusing to repoint {ref}')
                target_collections.load_digest('public', prepared['digest'])
            else:
                plan.collections.append(prepared)
            plan.counts['collections'] += 1
    return plan


def install(root, fixtures=ROOT / 'fixtures'):
    # Preflight again immediately before writing. The store supports a single writer.
    plan = prepare_plan(root, fixtures)
    store = Store(root)
    configs = ConfigurationService(store)
    for document in plan.documents:
        store.register(document)
    for config in plan.configurations:
        configs.register(config)
    for collection in plan.collections:
        CollectionService(store).register(collection)
    state_path = store.root / STATE_FILE
    previous = store._read(state_path) if exists(state_path) else None
    updated = canonical_json(plan.state)
    if previous is None or json.loads(previous) != plan.state:
        if previous is not None:
            backup = store.root / '.example-import-backups' / (hashlib.sha256(previous).hexdigest() + '.json')
            store._atomic_write(backup, previous, immutable=True)
        store._atomic_write(state_path, updated, immutable=False)
    # Read all imported snapshots through the normal integrity checks.
    verified = prepare_plan(root, fixtures)
    if verified.documents or verified.configurations or verified.collections:
        raise StoreError('Import verification found missing entries')
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--store', type=Path, help='Destination; defaults to the normal Caiman config/XDG resolution')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='Validate and report only (default)')
    modes.add_argument('--install', action='store_true', help='Add examples to local pods')
    args = parser.parse_args()
    try:
        root = store_path(args.store)
        plan = install(root) if args.install else prepare_plan(root)
    except (OSError, ValueError, KeyError, IndexError) as error:
        parser.exit(1, f'Example import failed: {error}\n')
    print(('Installed and verified' if args.install else 'Validated') + f' examples for {root}')
    print(', '.join(f'{count} {kind}' for kind, count in plan.counts.items()))
    print(f'{len(plan.documents)} new documents, {len(plan.configurations)} new configurations, '
          f'{len(plan.collections)} new collections' + (' added.' if args.install else ' would be added.'))
    print('Project pods: demo-microbit, demo-macropad. All example documents are public.')


if __name__ == '__main__':
    main()
