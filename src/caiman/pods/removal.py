"""Removal checks rooted at current catalogs, never orphaned snapshots."""
from caiman.configurations.models import project_boards
from caiman.configurations.service import ConfigurationService
from caiman.documents.collections import CollectionService
from caiman.documents.usages import document_pins


def check_removal(store, pod):
    owner = store.pods.resolve(pod)['id']
    if owner == 'public':
        raise ValueError('The default public pod cannot be removed')
    if owner not in {record['id'] for record in store.pods.list()}:
        raise ValueError('Pod is unavailable')
    configurations = ConfigurationService(store)
    collections = CollectionService(store)
    blockers = []
    # References within the removed pod leave with it. Only remaining roots matter.
    remaining = [record['id'] for record in store.pods.list() if record['id'] != owner]
    for source in remaining:
        for kind in ('board', 'project', 'collection'):
            records = (collections.list_collections(pods=[source]) if kind == 'collection'
                       else configurations.list_configs(kind, pods=[source]))
            for record in records:
                manifest = record['manifest']
                pins = document_pins(kind, manifest)
                if kind == 'project':
                    for board in project_boards(manifest):
                        if store.pods.resolve(board.get('pod', 'public'))['id'] == owner:
                            pins.append(board)
                        else:
                            dependency = configurations.load_digest(
                                'board', board['digest'], pod=board.get('pod', 'public'))
                            pins.extend(document_pins('board', dependency))
                if any(store.pods.resolve(pin.get('pod', 'public'))['id'] == owner for pin in pins):
                    name = manifest.get(kind, manifest.get('name', ''))
                    version = f" @ {manifest['version']}" if 'version' in manifest else ''
                    blockers.append(f'{kind.title()}: {source}/{name}{version}')
    if blockers:
        raise ValueError('Cannot remove pod; current references remain:\n' + '\n'.join(blockers))
    return owner
