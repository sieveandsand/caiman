"""Informational current local usages; metadata edits never rewrite consumers."""
from dataclasses import dataclass

from caiman.configurations.models import project_boards
from caiman.configurations.service import ConfigurationService
from caiman.documents.collections import CollectionService


def document_pins(kind, manifest):
    pins = list(manifest.get('documents', []))
    if kind == 'board':
        for part in manifest['parts']:
            pins.extend(part.get('documents', []))
    if kind == 'project':
        pins.extend(manifest.get('precedence', []))
        for feature in manifest['features']:
            pins.extend(feature.get('governed_by', []))
    return pins


@dataclass(frozen=True)
class UsagePlan:
    usages: tuple
    unknown: tuple


class DocumentUsages:
    def __init__(self, store, selection):
        self.store = store
        self.owner = store.pods.resolve(selection['pod'])['id']
        self.document = selection['manifest']['document_id']
        self.configurations = ConfigurationService(store)
        self.collections = CollectionService(store)

    def matches_document(self, pin):
        if self.store.pods.resolve(pin.get('pod', 'public'))['id'] != self.owner:
            return False
        if 'document' in pin:
            return pin['document'] == self.document
        return self.store.read_manifest(self.owner, pin['digest']).get('document_id') == self.document

    def prepare(self):
        usages, unknown = [], []
        for kind in ('board', 'project', 'collection'):
            try:
                records = (self.collections.list_collections() if kind == 'collection'
                           else self.configurations.list_configs(kind))
            except (OSError, ValueError) as error:
                unknown.append(f'{kind.title()} catalog: {error}')
                continue
            for record in records:
                manifest = record['manifest']
                name = manifest.get(kind, manifest.get('name', ''))
                label = f"{kind.title()}: {record['pod']}/{name}" + (f" @ {manifest['version']}" if 'version' in manifest else '')
                touched = False
                try:
                    # Do not short-circuit: missing dependencies must be reported.
                    for pin in document_pins(kind, manifest):
                        touched |= self.matches_document(pin)
                    if kind == 'project':
                        for board in project_boards(manifest):
                            dependency = self.configurations.load_digest('board', board['digest'], pod=board.get('pod', 'public'))
                            for pin in document_pins('board', dependency):
                                touched |= self.matches_document(pin)
                except (OSError, ValueError) as error:
                    unknown.append(f'{label}: {error}')
                if touched:
                    usages.append({'kind': kind, 'pod': record['pod'], 'digest': record['digest'], 'label': label})
        return UsagePlan(tuple(usages), tuple(unknown))
