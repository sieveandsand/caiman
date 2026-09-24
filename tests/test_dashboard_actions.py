from copy import deepcopy

import pytest

from caiman.dashboard.actions import revision_draft, run_dashboard_action


def test_revision_copy_preserves_pins_and_original():
    current = {'schema': 'caiman.board/1', 'board': 'demo', 'version': 'old / label',
               'parts': [{'documents': [{'digest': 'sha256:' + 'a' * 64}]}]}
    draft = revision_draft(current, mode='new', version='new / label', relation='Explicit revision')
    assert draft['parts'] == current['parts']
    assert draft['derives_from'] == 'old / label'
    assert draft['relation'] == 'Explicit revision'
    assert current['version'] == 'old / label'
    assert revision_draft(current, mode='replace') == current


@pytest.mark.parametrize('version,relation', [('old', 'Reason'), ('new', ''), ('', 'Reason')])
def test_new_version_requires_distinct_label_and_declared_reason(version, relation):
    with pytest.raises(ValueError):
        revision_draft({'version': 'old'}, mode='new', version=version, relation=relation)


@pytest.mark.parametrize('action', ['edit-board', 'export-project', 'template-board', 'validate-project'])
def test_removed_home_actions_are_unknown(tmp_path, monkeypatch, action):
    import caiman.dashboard.actions as actions
    shown = []
    class Viewer:
        def __init__(self, **kwargs):
            shown.append(kwargs)
        def run(self):
            return None
    monkeypatch.setattr(actions, 'ViewerApp', Viewer)
    assert run_dashboard_action(action, tmp_path / 'store', []) is None
    assert 'Unknown' in shown[0]['content']
    assert not (tmp_path / 'store').exists()


def test_view_project_cancel_writes_nothing(tmp_path, monkeypatch):
    import caiman.dashboard.actions as actions
    class Choose:
        def __init__(self, **kwargs):
            assert kwargs['kind'] == 'project'
        def run(self):
            return None
    monkeypatch.setattr(actions, 'ChooseApp', Choose)
    assert run_dashboard_action('show-project', tmp_path / 'store', []) is None
    assert not (tmp_path / 'store').exists()


def test_project_edit_starts_from_view_and_returns_to_the_new_snapshot(tmp_path, monkeypatch):
    import caiman.dashboard.actions as actions
    import caiman.configurations.tui as config_tui
    from types import SimpleNamespace
    chosen = {'manifest': {'project': 'demo', 'version': 'v1'}, 'digest': 'sha256:' + 'a' * 64}
    before = deepcopy(chosen)
    revised = {'project': 'demo', 'version': 'v2', 'derives_from': 'v1', 'relation': 'Spec update'}
    viewed = []
    class Choose:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return chosen
    class Viewer:
        def __init__(self, **kwargs):
            assert kwargs['editable']
            viewed.append(kwargs['content'])
        def run(self):
            return 'edit' if len(viewed) == 1 else None
    class Revision:
        def __init__(self, **kwargs):
            assert kwargs['selection'] == chosen
        def run(self):
            return revised
    class Editor:
        def __init__(self, **kwargs):
            assert kwargs['draft'] == revised
            self.registration = SimpleNamespace(digest='sha256:' + 'b' * 64)
            self.prepared = SimpleNamespace(manifest=revised)
        def run(self):
            pass
    monkeypatch.setattr(actions, 'ChooseApp', Choose)
    monkeypatch.setattr(actions, 'ViewerApp', Viewer)
    monkeypatch.setattr(actions, 'RevisionApp', Revision)
    monkeypatch.setattr(config_tui, 'ConfigApp', Editor)
    result = run_dashboard_action('show-project', tmp_path, [])
    assert result == {'manifest': revised, 'digest': 'sha256:' + 'b' * 64}
    assert 'sha256:' + 'b' * 64 in viewed[1]
    assert chosen == before


@pytest.mark.asyncio
async def test_viewer_e_edits_only_when_editable():
    from caiman.dashboard.actions import ViewerApp
    app = ViewerApp(title='Project snapshot', content='{}', editable=True)
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press('e')
    assert app.return_value == 'edit'
    plain = ViewerApp(title='Note', content='text')
    async with plain.run_test(size=(80, 24)) as pilot:
        await pilot.pause()
        await pilot.press('e')
        assert plain.is_running
        assert not plain.query('#edit')
        await pilot.press('q')
    assert plain.return_value is None


@pytest.mark.asyncio
async def test_choose_lists_projects_only_in_entered_access_groups(tmp_path):
    from caiman.configurations.service import ConfigurationService
    from caiman.dashboard.actions import ChooseApp
    from caiman.storage.store import Store
    from textual.widgets import Select
    root = tmp_path / 'store'
    service = ConfigurationService(Store(root))
    service.register(service.prepare('board', {'board': 'demo', 'version': 'v1',
        'parts': [{'role': 'main', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}], 'links': []}))
    project = service.prepare('project', {'project': 'program', 'version': 'A', 'customer': 'Synthetic',
        'compartments': ['alpha'], 'board': {'name': 'demo', 'version': 'v1'},
        'spec_set': 'release A', 'documents': [], 'features': []})
    service.register(project)
    hidden = ChooseApp(kind='project', root=root, compartments=[])
    async with hidden.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert hidden.records == []
        await pilot.click('#continue')
        assert hidden.is_running
    app = ChooseApp(kind='project', root=root, compartments=['alpha'])
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.query_one('#choice', Select).value == Select.NULL
        app.query_one('#choice', Select).value = '0'
        await pilot.click('#continue')
    assert app.return_value['digest'] == project.digest


@pytest.mark.asyncio
async def test_revision_form_uses_explicit_mode_and_preserves_opaque_versions():
    from caiman.dashboard.actions import RevisionApp
    from textual.widgets import Input, Static
    app = RevisionApp(kind='board', selection={'manifest': {'board': 'demo', 'version': 'v1'},
                                              'digest': 'sha256:' + 'a' * 64})
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        app.query_one('#version', Input).value = 'release / B'
        app.query_one('#relation', Input).value = 'Declared hardware revision'
        await pilot.click('#continue')
        await pilot.pause()
    assert app.return_value['version'] == 'release / B'
    assert app.return_value['derives_from'] == 'v1'


@pytest.mark.asyncio
async def test_catalog_launch_with_no_store_writes_nothing(tmp_path):
    from caiman.dashboard.actions import DocumentCatalogApp
    from textual.widgets import Static
    root = tmp_path / 'absent-store'
    app = DocumentCatalogApp(root=root, compartments=[])
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause(0.1)
        assert '0 accessible' in str(app.query_one('#status', Static).content)
        await pilot.click('#close')
    assert not root.exists()


@pytest.mark.asyncio
async def test_new_version_rejects_existing_label_before_editor(tmp_path):
    from caiman.configurations.service import ConfigurationService
    from caiman.storage.store import Store
    from caiman.dashboard.actions import RevisionApp
    from textual.widgets import Input, Static
    service = ConfigurationService(Store(tmp_path))
    data = {'board': 'demo', 'version': 'v1', 'parts': [{'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}]}
    first = service.prepare('board', data)
    service.register(first)
    service.register(service.prepare('board', {**data, 'version': 'v2'}))
    app = RevisionApp(kind='board', root=tmp_path,
                      selection={'manifest': first.manifest, 'digest': first.digest})
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        app.query_one('#version', Input).value = 'v2'
        app.query_one('#relation', Input).value = 'Declared revision'
        await pilot.click('#continue')
        await pilot.pause(0.1)
        assert app.return_value is None
        assert 'already exists' in str(app.query_one('#status', Static).content)
        await pilot.click('#cancel')
