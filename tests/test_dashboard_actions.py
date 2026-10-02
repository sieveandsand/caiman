from copy import deepcopy

import pytest

from caiman.dashboard.actions import run_dashboard_action


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


def test_project_gallery_opens_the_guided_form_directly(tmp_path, monkeypatch):
    """No viewer or revision page: the selection goes straight to the editor."""
    import caiman.configurations.gallery as gallery
    import caiman.configurations.project_edit as project_edit
    chosen = {'manifest': {'project': 'demo', 'version': 'v1'}, 'digest': 'sha256:' + 'a' * 64}
    registered = {'manifest': {'project': 'demo', 'version': 'v2'}, 'digest': 'sha256:' + 'b' * 64}
    selections = [chosen, None]
    class Gallery:
        def __init__(self, **kwargs):
            assert kwargs['compartments'] == ['alpha']
        def run(self):
            return selections.pop(0)
    edited = []
    def edit(root, service, selection, draft):
        edited.append(selection)
        assert draft == selection['manifest']
        return registered
    monkeypatch.setattr(gallery, 'ProjectGalleryApp', Gallery)
    monkeypatch.setattr(project_edit, 'edit_project', edit)
    assert run_dashboard_action('show-project', tmp_path, ['alpha']) == registered
    assert edited == [chosen]


def test_view_project_cancel_writes_nothing(tmp_path, monkeypatch):
    import caiman.configurations.gallery as gallery
    class Choose:
        def __init__(self, **kwargs):
            assert kwargs['compartments'] == []
        def run(self):
            return None
    monkeypatch.setattr(gallery, 'ProjectGalleryApp', Choose)
    assert run_dashboard_action('show-project', tmp_path / 'store', []) is None
    assert not (tmp_path / 'store').exists()


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
        'compartments': ['alpha'], 'boards': [{'name': 'demo', 'version': 'v1'}],
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
