import json
import stat

import pytest

from caiman.workflow import load_state, save_state, remember_context, run_workflow


def test_state_missing_does_not_write(tmp_path):
    root = tmp_path / 'store'
    assert load_state(root) == {'context': {}, 'authorized_compartments': []}
    assert not root.exists()


def test_state_remembers_explicit_project_scopes_privately(tmp_path):
    state = {'context': {}, 'authorized_compartments': []}
    context = {'project': {'manifest': {'project': 'demo', 'version': 'v1', 'customer': 'Private synthetic customer',
                                      'compartments': ['synthetic-alpha']}, 'digest': 'sha256:' + 'a' * 64}}
    remember_context(state, context)
    save_state(tmp_path / 'store', state)
    assert load_state(tmp_path / 'store') == state
    assert stat.S_IMODE((tmp_path / 'store/.authoring-state.json').stat().st_mode) == 0o600
    assert 'customer' not in (tmp_path / 'store/.authoring-state.json').read_text()


def test_state_does_not_discover_private_directories(tmp_path):
    (tmp_path / 'secret-customer').mkdir()
    assert load_state(tmp_path)['authorized_compartments'] == []


def test_invalid_or_symlinked_state_rejected(tmp_path):
    path = tmp_path / '.authoring-state.json'
    path.write_text(json.dumps({'authorized_compartments': ['public'], 'context': {}}))
    with pytest.raises(ValueError):
        load_state(tmp_path)
    path.unlink()
    target = tmp_path / 'elsewhere'
    target.write_text('{}')
    path.symlink_to(target)
    with pytest.raises(ValueError):
        load_state(tmp_path)


def test_cancel_initial_setup_writes_nothing(tmp_path, monkeypatch):
    import caiman.onboarding as onboarding

    class CancelSetup:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return None

    monkeypatch.setattr(onboarding, 'SetupApp', CancelSetup)
    root = tmp_path / 'store'
    assert run_workflow(root, ingest=True) == 0
    assert not root.exists()


def configurations(root):
    from caiman.config_store import ConfigurationService
    from caiman.store import Store
    service = ConfigurationService(Store(root))
    board = service.prepare('board', {'board': 'demo', 'version': 'v1',
        'parts': [{'role': 'main', 'part': 'synthetic/chip', 'documents': []}], 'links': []})
    service.register(board)
    project = service.prepare('project', {'project': 'program', 'version': 'A', 'customer': 'Synthetic',
        'compartments': ['alpha'], 'board': {'name': 'demo', 'version': 'v1'},
        'spec_set': 'release A', 'documents': [], 'features': []})
    service.register(project)
    return {'board': {'manifest': board.manifest, 'digest': board.digest},
            'project': {'manifest': project.manifest, 'digest': project.digest}}


def test_cancel_project_resumes_after_registered_board(tmp_path, monkeypatch):
    import caiman.onboarding as onboarding
    import caiman.tui as tui
    root = tmp_path / 'store'
    context = configurations(root)
    choices = [context['board'], None]
    requested = []
    class Setup:
        def __init__(self, **kwargs):
            requested.append(kwargs['kind'])
        def run(self):
            return choices.pop(0)
    monkeypatch.setattr(onboarding, 'SetupApp', Setup)
    assert run_workflow(root, ingest=True) == 0
    assert set(load_state(root)['context']) == {'board'}
    choices.append(context['project'])
    class Ingest:
        def __init__(self, **kwargs):
            assert kwargs['authorized_compartments'] == ['alpha']
        def run(self):
            return None
    monkeypatch.setattr(tui, 'IngestApp', Ingest)
    assert run_workflow(root, ingest=True) == 0
    assert requested == ['board', 'project', 'project']
    assert set(load_state(root)['context']) == {'board', 'project'}


def test_inline_create_cancel_restores_ingest_values(tmp_path, monkeypatch):
    import caiman.onboarding as onboarding
    import caiman.tui as tui
    root = tmp_path / 'store'
    context = configurations(root)
    state = {'context': {}, 'authorized_compartments': []}
    remember_context(state, context)
    save_state(root, state)
    inputs = {'version': 'typed-version', 'issuer': 'typed-issuer'}
    calls = []
    class Ingest:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def run(self):
            return {'action': 'create-project', 'ingest_state': inputs} if len(calls) == 1 else None
    class Cancel:
        def __init__(self, **kwargs):
            assert kwargs['kind'] == 'project'
        def run(self):
            return None
    monkeypatch.setattr(tui, 'IngestApp', Ingest)
    monkeypatch.setattr(onboarding, 'SetupApp', Cancel)
    assert run_workflow(root, ingest=True) == 0
    assert calls[1]['state'] == inputs
    assert calls[1]['context'] == context


def test_saved_selection_uses_digest_after_ref_moves(tmp_path):
    from caiman.config_store import ConfigurationService
    from caiman.store import Store
    from caiman.workflow import _validated_context
    root = tmp_path / 'store'
    context = configurations(root)
    state = {'context': {}, 'authorized_compartments': []}
    remember_context(state, context)
    service = ConfigurationService(Store(root))
    changed = dict(context['board']['manifest'])
    changed['relation'] = 'A declared change'
    changed['derives_from'] = 'previous'
    service.register(service.prepare('board', changed))
    assert _validated_context(root, state)['board'] == context['board']
