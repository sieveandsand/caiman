"""Interactive launcher; catalogs discover available local pods."""

from copy import deepcopy
from pathlib import Path



STATE_FILE = '.authoring-state.json'


def load_state(root: Path) -> dict:
    return {'pods': []}


def run_workflow(root: Path, source_path: Path | None = None, *, ingest=False) -> int:
    """Home screen loop. Every action names its board or project; none is remembered.

    An action started from a category page or gallery returns there afterwards.
    """
    from caiman.dashboard.actions import run_dashboard_action
    from caiman.dashboard.onboarding import CATEGORY_MENUS, CategoryApp, LauncherApp, SetupApp
    from caiman.documents.tui import IngestApp

    state = load_state(root)
    action = 'ingest' if ingest else None
    resume = None
    ingest_state = None
    ingest_context = {}
    selected_pod = None
    action_pod = None
    while True:
        if action is None:
            action = LauncherApp().run()
        if action is None or action == 'quit':
            return 0
        if action in CATEGORY_MENUS:
            options = {'selected_pod': selected_pod} if action == 'repos' and selected_pod else {}
            chosen = CategoryApp(action, store_root=root, **options).run()
            action_pod = None
            if isinstance(chosen, dict):
                action_pod = selected_pod = chosen['pod']
                chosen = chosen['action']
            action, resume = (chosen, action) if chosen else (None, None)
            continue
        if action in {'create-board', 'create-project'}:
            kind = action.split('-')[1]
            setup_options = {'pod': ingest_context['pod']} if ingest_context.get('pod') else {}
            selection = SetupApp(kind=kind, store_root=root, board=ingest_context.get('board'), **setup_options).run()
            if selection is not None:
                ingest_context[kind] = selection
            if ingest_state is not None:
                action = 'ingest'
            else:
                action, resume = resume, None
            continue
        if action in {'hooks-claude', 'hooks-codex'}:
            from caiman.hooks.tui import HooksApp

            HooksApp(harness=action.removeprefix('hooks-'), store_root=root).run()
            action, resume = resume, None
            continue
        if action == 'little-caiman':
            from caiman.little_caiman.tui import run_little_caiman

            run_little_caiman(root)
            action = None
            continue
        if action in {'repo-add', 'repo-remove', 'repo-initialize', 'repo-create', 'repo-sync', 'repo-default', 'repo-unregister'}:
            from caiman.repositories.tui import RepoManagerApp

            options = {'pod': action_pod} if action_pod else {}
            RepoManagerApp(store_root=root, action=action.removeprefix('repo-'), **options).run()
            action_pod = None
            action, resume = resume, None
            continue
        if action != 'ingest':
            result = run_dashboard_action(action, root, state['pods'])
            if isinstance(result, dict) and 'action' in result:
                # A gallery's add card: run it, then come back to that gallery.
                if result.get('pod'):
                    ingest_context['pod'] = result['pod']
                action, resume = result['action'], action
            else:
                action = None
            continue
        result = IngestApp(store_root=root, source_path=source_path,
                           state=ingest_state, context=ingest_context,
                           pods=state['pods'], pod=ingest_context.get('pod')).run()
        ingest_state, ingest_context = None, {}
        if isinstance(result, dict):
            # Inline creation hands the form's values and choices back afterwards.
            if result.get('action') in {'create-board', 'create-project'}:
                ingest_state = result['ingest_state']
                ingest_context = deepcopy(result.get('context', {}))
                action = result['action']
                continue
        if ingest:
            return 0
        action, resume = resume, None
