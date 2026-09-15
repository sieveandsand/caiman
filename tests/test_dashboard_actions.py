from copy import deepcopy

import pytest

from caiman.dashboard_actions import revision_draft, run_dashboard_action


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


def test_edit_cancel_does_not_return_context_update(tmp_path, monkeypatch):
    import caiman.dashboard_actions as actions
    class Cancel:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return None
    monkeypatch.setattr(actions, 'RevisionApp', Cancel)
    context = {'board': {'manifest': {'board': 'demo', 'version': 'v1'}, 'digest': 'sha256:' + 'a' * 64}}
    assert run_dashboard_action('edit-board', tmp_path, context, []) is None


def test_board_edit_updates_only_board_selection(tmp_path, monkeypatch):
    import caiman.dashboard_actions as actions
    import caiman.config_tui as config_tui
    from types import SimpleNamespace
    original = {'board': {'manifest': {'board': 'demo', 'version': 'v1'}, 'digest': 'sha256:' + 'a' * 64},
                'project': {'manifest': {'board': {'digest': 'sha256:' + 'a' * 64}}}}
    before = deepcopy(original)
    revised = {'board': 'demo', 'version': 'v2', 'derives_from': 'v1', 'relation': 'Hardware update'}
    class Revision:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return revised
    class Editor:
        def __init__(self, **kwargs):
            assert kwargs['draft'] == revised
            self.registration = SimpleNamespace(digest='sha256:' + 'b' * 64)
            self.prepared = SimpleNamespace(manifest=revised)
        def run(self):
            pass
    monkeypatch.setattr(actions, 'RevisionApp', Revision)
    monkeypatch.setattr(config_tui, 'ConfigApp', Editor)
    result = run_dashboard_action('edit-board', tmp_path, original, [])
    assert set(result) == {'board'}
    assert result['board']['manifest']['version'] == 'v2'
    assert original == before


@pytest.mark.asyncio
async def test_revision_form_uses_explicit_mode_and_preserves_opaque_versions():
    from caiman.dashboard_actions import RevisionApp
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
async def test_export_file_action_keeps_existing_files(tmp_path):
    from caiman.dashboard_actions import FileActionApp
    from textual.widgets import Input, Static
    path = tmp_path / 'existing.json'
    path.write_text('existing work')
    app = FileActionApp(operation='export', kind='board', root=tmp_path,
                        selection={'manifest': {'board': 'demo', 'version': 'v1'}})
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        app.query_one('#path', Input).value = str(path)
        await pilot.click('#run')
        await pilot.pause(0.1)
        assert 'exists' in str(app.query_one('#status', Static).content)
        assert app.return_value is None
        await pilot.click('#cancel')
    assert path.read_text() == 'existing work'


@pytest.mark.asyncio
async def test_catalog_launch_with_no_store_writes_nothing(tmp_path):
    from caiman.dashboard_actions import DocumentCatalogApp
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
    from caiman.config_store import ConfigurationService
    from caiman.store import Store
    from caiman.dashboard_actions import RevisionApp
    from textual.widgets import Input, Static
    service = ConfigurationService(Store(tmp_path))
    data = {'board': 'demo', 'version': 'v1', 'parts': [{'role': 'mcu', 'part': 'synthetic/chip', 'documents': []}]}
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
