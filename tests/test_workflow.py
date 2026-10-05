import json
import stat

import pytest


@pytest.mark.parametrize('action', ['add', 'remove', 'initialize'])
def test_home_routes_repo_manager(tmp_path, monkeypatch, action):
    import caiman.dashboard.onboarding as onboarding
    import caiman.repositories.tui as repo_tui
    actions = ['repo-' + action, 'quit']
    calls = []

    class Home:
        def run(self):
            return actions.pop(0)

    class Manager:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def run(self):
            return None

    monkeypatch.setattr(onboarding, 'LauncherApp', Home)
    monkeypatch.setattr(repo_tui, 'RepoManagerApp', Manager)
    assert run_workflow(tmp_path) == 0
    assert calls == [{'store_root': tmp_path, 'action': action}]

from caiman.dashboard.workflow import load_state, run_workflow


def test_state_missing_does_not_write(tmp_path):
    root = tmp_path / 'store'
    assert load_state(root) == {'pods': []}
    assert not root.exists()


def test_legacy_authorization_state_is_ignored(tmp_path):
    (tmp_path / '.authoring-state.json').write_text('{"authorized_compartments": ["alpha"]}')
    assert load_state(tmp_path) == {'pods': []}


def test_launch_opens_home_without_setup_or_writes(tmp_path, monkeypatch):
    import caiman.dashboard.onboarding as onboarding

    launched = []

    class Home:
        def __init__(self, **kwargs):
            assert kwargs == {}
            launched.append(True)
        def run(self):
            return 'quit'

    class NoSetup:
        def __init__(self, **kwargs):
            raise AssertionError('launch must not force board or project setup')

    monkeypatch.setattr(onboarding, 'LauncherApp', Home)
    monkeypatch.setattr(onboarding, 'SetupApp', NoSetup)
    root = tmp_path / 'store'
    assert run_workflow(root) == 0
    assert launched == [True]
    assert not root.exists()


def test_ingest_starts_without_a_preselected_board_or_project(tmp_path, monkeypatch):
    import caiman.documents.tui as tui

    calls = []

    class Ingest:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def run(self):
            return None

    monkeypatch.setattr(tui, 'IngestApp', Ingest)
    root = tmp_path / 'store'
    assert run_workflow(root, ingest=True) == 0
    assert calls[0]['context'] == {}
    assert calls[0]['state'] is None
    assert not root.exists()


def configurations(root):
    from caiman.configurations.service import ConfigurationService
    from caiman.storage.store import Store
    service = ConfigurationService(Store(root))
    board = service.prepare('board', {'board': 'demo', 'version': 'v1',
        'parts': [{'role': 'main', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}], 'links': []})
    service.register(board)
    project = service.prepare('project', {'project': 'program', 'version': 'A', 'customer': 'Synthetic',
        'pod': 'alpha', 'boards': [{'name': 'demo', 'version': 'v1'}],
        'spec_set': 'release A', 'documents': [], 'features': []})
    service.register(project)
    return {'board': {'manifest': board.manifest, 'digest': board.digest},
            'project': {'manifest': project.manifest, 'digest': project.digest}}


def test_selections_do_not_carry_into_the_next_ingest(tmp_path, monkeypatch):
    import caiman.dashboard.onboarding as onboarding
    import caiman.documents.tui as tui
    root = tmp_path / 'store'
    context = configurations(root)
    actions = ['ingest', 'ingest', 'quit']
    calls = []

    class Home:
        def run(self):
            return actions.pop(0)

    class Ingest:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def run(self):
            return {'context': context} if len(calls) == 1 else None

    monkeypatch.setattr(onboarding, 'LauncherApp', Home)
    monkeypatch.setattr(tui, 'IngestApp', Ingest)
    assert run_workflow(root) == 0
    assert calls[1]['context'] == {}
    assert calls[1]['pods'] == []


def test_inline_create_cancel_restores_ingest_values(tmp_path, monkeypatch):
    import caiman.dashboard.onboarding as onboarding
    import caiman.documents.tui as tui
    root = tmp_path / 'store'
    context = configurations(root)
    inputs = {'version': 'typed-version', 'issuer': 'typed-issuer'}
    calls = []
    class Ingest:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def run(self):
            return {'action': 'create-project', 'ingest_state': inputs, 'context': context} if len(calls) == 1 else None
    class Cancel:
        def __init__(self, **kwargs):
            assert kwargs['kind'] == 'project'
            assert kwargs['board'] == context['board']
        def run(self):
            return None
    monkeypatch.setattr(tui, 'IngestApp', Ingest)
    monkeypatch.setattr('caiman.configurations.project_edit.create_project',
                        lambda root, **kwargs: Cancel(kind='project', **kwargs).run())
    assert run_workflow(root, ingest=True) == 0
    assert calls[1]['state'] == inputs
    assert calls[1]['context'] == context


def test_inline_create_hands_new_configuration_back_to_ingest(tmp_path, monkeypatch):
    import caiman.dashboard.onboarding as onboarding
    import caiman.documents.tui as tui
    root = tmp_path / 'store'
    context = configurations(root)
    calls = []
    class Ingest:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def run(self):
            return {'action': 'create-board', 'ingest_state': {}, 'context': {}} if len(calls) == 1 else None
    class Create:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return context['board']
    monkeypatch.setattr(tui, 'IngestApp', Ingest)
    monkeypatch.setattr(onboarding, 'SetupApp', Create)
    assert run_workflow(root, ingest=True) == 0
    assert calls[1]['context'] == {'board': context['board']}


@pytest.mark.parametrize('harness', ['claude', 'codex'])
def test_home_routes_hooks_and_returns_to_home(tmp_path, monkeypatch, harness):
    import caiman.dashboard.onboarding as onboarding
    import caiman.hooks.tui as hooks_tui

    actions = [f'hooks-{harness}', 'quit']
    calls = []

    class Home:
        def run(self):
            return actions.pop(0)

    class Hooks:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def run(self):
            return None

    monkeypatch.setattr(onboarding, 'LauncherApp', Home)
    monkeypatch.setattr(hooks_tui, 'HooksApp', Hooks)
    assert run_workflow(tmp_path) == 0
    assert calls == [{'harness': harness, 'store_root': tmp_path}]


@pytest.mark.parametrize('category, chosen', [('hooks', 'hooks-codex'), ('repos', 'repo-add'),
    ('repos', {'action': 'repo-sync', 'pod': 'alpha'})])
def test_category_page_runs_its_action_then_returns_to_the_category(tmp_path, monkeypatch, category, chosen):
    import caiman.dashboard.onboarding as onboarding
    import caiman.hooks.tui as hooks_tui
    import caiman.repositories.tui as repo_tui
    homes = [category, 'quit']
    menus = [chosen, None]
    ran = []

    class Home:
        def run(self):
            return homes.pop(0)

    class Category:
        def __init__(self, name, *, store_root, selected_pod=None):
            assert name == category
            assert store_root == tmp_path
            if isinstance(chosen, dict) and len(menus) == 1:
                assert selected_pod == 'alpha'
        def run(self):
            return menus.pop(0)

    class Tool:
        def __init__(self, **kwargs):
            ran.append(kwargs)
        def run(self):
            return None

    monkeypatch.setattr(onboarding, 'LauncherApp', Home)
    monkeypatch.setattr(onboarding, 'CategoryApp', Category)
    monkeypatch.setattr(hooks_tui, 'HooksApp', Tool)
    monkeypatch.setattr(repo_tui, 'RepoManagerApp', Tool)
    assert run_workflow(tmp_path) == 0
    assert len(ran) == 1 and menus == [] and homes == []
    if isinstance(chosen, dict):
        assert ran[0]['pod'] == 'alpha' and ran[0]['action'] == 'sync'


def test_gallery_add_card_creates_then_returns_to_the_gallery(tmp_path, monkeypatch):
    import caiman.dashboard.actions as actions
    import caiman.dashboard.onboarding as onboarding
    project = {'manifest': {'project': 'demo', 'version': 'v1', 'pod': 'alpha'},
               'digest': 'sha256:' + 'a' * 64}
    homes = ['show-project', 'quit']
    galleries = [{'action': 'create-project', 'registered': None}, None]
    created = []

    class Home:
        def run(self):
            return homes.pop(0)

    class Setup:
        def __init__(self, **kwargs):
            created.append(kwargs['kind'])
        def run(self):
            return project

    def gallery(action, root, pods):
        assert action == 'show-project'
        return galleries.pop(0)

    monkeypatch.setattr(onboarding, 'LauncherApp', Home)
    monkeypatch.setattr('caiman.configurations.project_edit.create_project',
                        lambda root, **kwargs: Setup(kind='project', **kwargs).run())
    monkeypatch.setattr(actions, 'run_dashboard_action', gallery)
    assert run_workflow(tmp_path) == 0
    assert created == ['project'] and galleries == [] and homes == []
    assert load_state(tmp_path)['pods'] == []
