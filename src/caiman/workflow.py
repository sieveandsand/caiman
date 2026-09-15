"""Interactive launcher and explicit, private authoring preferences."""

from copy import deepcopy
import json
from pathlib import Path

from .models import canonical_json, valid_identifier
from .store import Store, StoreError


STATE_FILE = '.authoring-state.json'


def load_state(root: Path) -> dict:
    store = Store(root)
    path = store.root / STATE_FILE
    if not path.exists() and not path.is_symlink():
        return {'context': {}, 'authorized_compartments': []}
    state = json.loads(store._read(path))
    if not isinstance(state, dict) or set(state) != {'context', 'authorized_compartments'}:
        raise StoreError('Invalid local authoring state')
    scopes = state['authorized_compartments']
    if (not isinstance(scopes, list) or any(not valid_identifier(s) or s == 'public' for s in scopes)
            or not isinstance(state['context'], dict) or set(state['context']) - {'board', 'project'}):
        raise StoreError('Invalid local authoring context or explicit compartments')
    return state


def save_state(root: Path, state: dict) -> None:
    store = Store(root)
    store._atomic_write(store.root / STATE_FILE, canonical_json(state), immutable=False)


def remember_context(state: dict, context: dict) -> None:
    state['context'] = {}
    for kind, selection in context.items():
        manifest = selection['manifest']
        state['context'][kind] = {'name': manifest[kind], 'version': manifest['version'],
                                 'digest': selection['digest'],
                                 'compartment': 'public' if kind == 'board' else manifest['compartments'][0]}
    project = context.get('project')
    if project:
        scopes = set(state['authorized_compartments'])
        scopes.update(project['manifest']['compartments'])
        state['authorized_compartments'] = sorted(scopes)


def _validated_context(root, state):
    from .config_store import ConfigurationService

    service = ConfigurationService(Store(root))
    result = {}
    scopes = set(state['authorized_compartments'])
    for kind, selection in state['context'].items():
        if not isinstance(selection, dict) or set(selection) != {'name', 'version', 'digest', 'compartment'}:
            raise StoreError('Invalid saved configuration selection')
        stored = service.load_digest(kind, selection['digest'], compartment=selection['compartment'], compartments=scopes)
        if stored[kind] != selection['name'] or stored['version'] != selection['version']:
            raise StoreError('Saved selection does not match its pinned configuration')
        result[kind] = {'manifest': stored, 'digest': selection['digest']}
    if 'project' in result and 'board' not in result:
        pin = result['project']['manifest']['board']
        result['board'] = {'manifest': service.load_digest('board', pin['digest']), 'digest': pin['digest']}
    return result


def run_workflow(root: Path, source_path: Path | None = None, *, ingest=False) -> int:
    from .onboarding import LauncherApp, SetupApp
    from .tui import IngestApp

    state = load_state(root)
    context = _validated_context(root, state)

    def select(kind, *, create=False):
        selection = SetupApp(kind=kind, store_root=root, board=context.get('board'),
                             compartments=state['authorized_compartments'], create=create).run()
        if selection is None:
            return False
        context[kind] = selection
        if kind == 'project':
            from .config_store import ConfigurationService
            service = ConfigurationService(Store(root))
            board_pin = selection['manifest']['board']
            board = service.load_digest('board', board_pin['digest'])
            context['board'] = {'manifest': board, 'digest': board_pin['digest']}
        remember_context(state, context)
        save_state(root, state)
        return True

    # A cancelled project step leaves a saved board, so the next launch resumes.
    for kind in ('board', 'project'):
        if kind not in context and not select(kind):
            return 0

    action = 'ingest' if ingest else None
    ingest_state = None
    while True:
        if action is None:
            action = LauncherApp(context=context).run()
        if action is None or action == 'quit':
            return 0
        if action in {'create-board', 'create-project', 'select-board', 'select-project'}:
            select(action.split('-')[1], create=action.startswith('create-'))
            action = 'ingest' if ingest_state is not None or ingest else None
            continue
        if action != 'ingest':
            from .dashboard_actions import run_dashboard_action
            changes = run_dashboard_action(action, root, context, state['authorized_compartments'])
            if changes:
                context.update(changes)
                remember_context(state, context)
                save_state(root, state)
            action = None
            continue
        result = IngestApp(store_root=root, source_path=source_path,
                           state=ingest_state, context=context,
                           authorized_compartments=state['authorized_compartments']).run()
        if isinstance(result, dict):
            if 'context' in result:
                context.update(result['context'])
                remember_context(state, context)
                save_state(root, state)
                context = _validated_context(root, state)
            if result.get('action') in {'create-board', 'create-project'}:
                ingest_state = result.get('ingest_state')
                action = result['action']
                continue
        if ingest:
            return 0
        ingest_state = None
        action = None
