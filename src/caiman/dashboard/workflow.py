"""Interactive launcher and private, explicitly chosen compartment preferences."""

from copy import deepcopy
import json
from pathlib import Path

from caiman.documents.models import canonical_json, valid_identifier
from caiman.storage.store import Store, StoreError


STATE_FILE = '.authoring-state.json'


def load_state(root: Path) -> dict:
    store = Store(root)
    path = store.root / STATE_FILE
    if not path.exists() and not path.is_symlink():
        return {'authorized_compartments': []}
    state = json.loads(store._read(path))
    # Older files also held a remembered board/project; there is no default
    # selection any more, so that key is accepted and dropped.
    if not isinstance(state, dict) or set(state) - {'context'} != {'authorized_compartments'}:
        raise StoreError('Invalid local authoring state')
    scopes = state['authorized_compartments']
    if not isinstance(scopes, list) or any(not valid_identifier(s) or s == 'public' for s in scopes):
        raise StoreError('Invalid local authoring explicit compartments')
    return {'authorized_compartments': scopes}


def save_state(root: Path, state: dict) -> None:
    store = Store(root)
    store._atomic_write(store.root / STATE_FILE, canonical_json(state), immutable=False)


def remember_compartments(root: Path, state: dict, selections) -> None:
    """Remember compartments of explicitly chosen projects; never which project."""
    scopes = set(state['authorized_compartments'])
    for selection in selections:
        manifest = (selection or {}).get('manifest', {})
        if 'project' in manifest:
            scopes.update(manifest['compartments'])
    if scopes != set(state['authorized_compartments']):
        state['authorized_compartments'] = sorted(scopes)
        save_state(root, state)


def run_workflow(root: Path, source_path: Path | None = None, *, ingest=False) -> int:
    """Home screen loop. Every action names its board or project; none is remembered."""
    from caiman.dashboard.actions import run_dashboard_action
    from caiman.dashboard.onboarding import LauncherApp, SetupApp
    from caiman.documents.tui import IngestApp

    state = load_state(root)
    action = 'ingest' if ingest else None
    ingest_state = None
    ingest_context = {}
    while True:
        if action is None:
            action = LauncherApp().run()
        if action is None or action == 'quit':
            return 0
        if action in {'create-board', 'create-project'}:
            kind = action.split('-')[1]
            selection = SetupApp(kind=kind, store_root=root, board=ingest_context.get('board')).run()
            if selection is not None:
                ingest_context[kind] = selection
                remember_compartments(root, state, [selection])
            action = 'ingest' if ingest_state is not None else None
            continue
        if action in {'hooks-claude', 'hooks-codex'}:
            from caiman.hooks.tui import HooksApp

            HooksApp(harness=action.removeprefix('hooks-'), store_root=root).run()
            action = None
            continue
        if action == 'little-caiman':
            from caiman.little_caiman.tui import run_little_caiman

            run_little_caiman(root)
            action = None
            continue
        if action in {'repo-add', 'repo-remove', 'repo-initialize'}:
            from caiman.repositories.tui import RepoManagerApp

            RepoManagerApp(store_root=root, action=action.removeprefix('repo-')).run()
            action = None
            continue
        if action != 'ingest':
            remember_compartments(root, state, [run_dashboard_action(action, root, state['authorized_compartments'])])
            action = None
            continue
        result = IngestApp(store_root=root, source_path=source_path,
                           state=ingest_state, context=ingest_context,
                           authorized_compartments=state['authorized_compartments']).run()
        ingest_state, ingest_context = None, {}
        if isinstance(result, dict):
            remember_compartments(root, state, result.get('context', {}).values())
            # Inline creation hands the form's values and choices back afterwards.
            if result.get('action') in {'create-board', 'create-project'}:
                ingest_state = result['ingest_state']
                ingest_context = deepcopy(result.get('context', {}))
                action = result['action']
                continue
        if ingest:
            return 0
        action = None
