"""Project edits reach the store only through prepare, review, and Register."""

from copy import deepcopy

import pytest

from caiman.configurations.project_edit import ProjectDeleteApp, ProjectEditReviewApp, edit_project
from caiman.configurations.service import ConfigurationService
from caiman.documents.ingest import prepare_document
from caiman.storage.store import Store


@pytest.fixture
def project_setup(tmp_path):
    root = tmp_path / 'store'
    store = Store(root)
    service = ConfigurationService(store)
    source = tmp_path / 'spec.md'
    source.write_text('# Specification\n\n## Boot\nREQ-1 Synthetic.\n')
    registered = store.register(prepare_document(source, {
        'issuer': 'synthetic-oem', 'program': 'flight', 'doc_type': 'spec', 'version': '1',
        'pod': ('alpha')}))
    ref = registered.ref_path.relative_to(root / 'alpha' / 'refs' / 'documents').as_posix()
    service.register(service.prepare('board', {'board': 'demo', 'version': 'v1', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': []}], 'links': []}))
    original = service.prepare('project', {
        'project': 'flight', 'version': 'A', 'customer': 'Synthetic customer', 'pod': 'alpha',
        'boards': [{'name': 'demo', 'version': 'v1'}], 'spec_set': 'release A',
        'documents': [{'ref': ref}], 'features': [{'name': 'boot', 'scope': 'required'}]})
    service.register(original)
    return root, service, {'manifest': original.manifest, 'digest': original.digest, 'pod': original.pod}, ref


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


def form_returning(monkeypatch, outcomes, seen):
    import caiman.configurations.project_form as form
    class Form:
        def __init__(self, **kwargs):
            seen.append(kwargs)
        def run(self):
            return outcomes.pop(0)
    monkeypatch.setattr(form, 'ProjectFormApp', Form)


@pytest.mark.parametrize('cancelled', [True, False])
def test_cancel_or_unchanged_draft_never_reviews_or_registers(project_setup, monkeypatch, cancelled):
    import caiman.configurations.project_edit as editing
    root, service, selection, _ = project_setup
    before = snapshot(root)
    seen = []
    outcomes = [None] if cancelled else [('review', deepcopy(selection['manifest'])), None]
    form_returning(monkeypatch, outcomes, seen)
    monkeypatch.setattr(editing, 'ProjectEditReviewApp', lambda **kwargs: pytest.fail('Unexpected review'))
    assert edit_project(root, service, selection, deepcopy(selection['manifest'])) is None
    assert snapshot(root) == before
    if not cancelled:
        assert 'nothing to register' in seen[1]['message']


def test_invalid_draft_returns_to_the_form_with_the_draft(project_setup, monkeypatch):
    import caiman.configurations.project_edit as editing
    root, service, selection, _ = project_setup
    before = snapshot(root)
    invalid = deepcopy(selection['manifest'])
    invalid['features'][0]['scope'] = 'implemented'
    seen = []
    form_returning(monkeypatch, [('review', invalid), None], seen)
    monkeypatch.setattr(editing, 'ProjectEditReviewApp', lambda **kwargs: pytest.fail('Unexpected review'))
    assert edit_project(root, service, selection, deepcopy(selection['manifest'])) is None
    assert seen[1]['draft'] == invalid
    assert 'required or not-used' in seen[1]['message']
    assert snapshot(root) == before


@pytest.mark.asyncio
async def test_review_registers_only_on_the_explicit_button(project_setup):
    root, service, selection, _ = project_setup
    edited = deepcopy(selection['manifest'])
    edited['spec_set'] = 'release A, deviation 1'
    prepared = service.prepare('project', edited, pod=selection['pod'])
    before = snapshot(root)
    app = ProjectEditReviewApp(root=root, original=selection['manifest'], prepared=prepared)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        assert snapshot(root) == before
        await pilot.click('#register')
        for _ in range(40):
            if not app.is_running:
                break
            await pilot.pause(0.025)
    assert app.return_value == {'manifest': prepared.manifest, 'digest': prepared.digest, 'pod': prepared.pod}
    assert service.load('project', 'flight', 'A', pods={'alpha'}) == prepared.manifest
    # The label moved; the snapshot it used to name is still there by digest.
    assert service.load_digest('project', selection['digest'], pod='alpha',
                               pods={'alpha'}) == selection['manifest']


@pytest.mark.asyncio
async def test_form_completes_refs_from_the_project_catalog(project_setup):
    from caiman.configurations.project_form import ProjectFormApp
    root, _, selection, ref = project_setup
    app = ProjectFormApp(original=selection['manifest'], root=root)
    async with app.run_test(size=(110, 50)) as pilot:
        await app.workers.wait_for_complete()
        assert app.suggestions.refs.refs == [ref]
        assert await app.suggestions.refs.get_suggestion(ref[:4]) == ref
        assert app.collect() == selection['manifest']


def test_renaming_a_project_updates_it_in_place(project_setup):
    root, service, selection, _ = project_setup
    edited = deepcopy(selection['manifest'])
    edited['version'] = 'B'
    prepared = service.prepare('project', edited, pod=selection['pod'])
    service.register(prepared, replaces=selection)
    records = service.list_configs('project', pods={'alpha'})
    assert [(record['name'], record['version'], record['digest']) for record in records] == [
        ('flight', 'B', prepared.digest)]
    # The old snapshot survives by digest for anything that pinned it (I-4).
    assert service.load_digest('project', selection['digest'], pod='alpha',
                               pods={'alpha'}) == selection['manifest']


def test_renaming_onto_another_project_is_refused(project_setup):
    root, service, selection, _ = project_setup
    other = deepcopy(selection['manifest'])
    other['version'] = 'B'
    service.register(service.prepare('project', other, pod=selection['pod']))
    before = snapshot(root)
    edited = deepcopy(selection['manifest'])
    edited.update(version='B', spec_set='release B')
    with pytest.raises(ValueError, match='already uses this name and version'):
        service.register(service.prepare('project', edited, pod=selection['pod']), replaces=selection)
    assert snapshot(root) == before


def test_edit_rejects_a_label_repointed_elsewhere(project_setup):
    root, service, selection, _ = project_setup
    moved = deepcopy(selection['manifest'])
    moved['spec_set'] = 'release A, deviation 1'
    service.register(service.prepare('project', moved, pod=selection['pod']))
    edited = deepcopy(selection['manifest'])
    edited['version'] = 'B'
    before = snapshot(root)
    with pytest.raises(ValueError, match='changed since opening'):
        service.register(service.prepare('project', edited, pod=selection['pod']), replaces=selection)
    assert snapshot(root) == before
    assert {record['version'] for record in service.list_configs('project', pods={'alpha'})} == {'A'}


def test_delete_removes_the_project_but_keeps_its_snapshot(project_setup):
    root, service, selection, _ = project_setup
    service.unregister('project', selection['manifest'], selection['digest'], pod=selection['pod'])
    assert service.list_configs('project', pods={'alpha'}) == []
    assert service.load_digest('project', selection['digest'], pod='alpha',
                               pods={'alpha'}) == selection['manifest']


def test_delete_refuses_a_project_changed_since_it_was_opened(project_setup):
    root, service, selection, _ = project_setup
    moved = deepcopy(selection['manifest'])
    moved['spec_set'] = 'release A, deviation 1'
    service.register(service.prepare('project', moved, pod=selection['pod']))
    before = snapshot(root)
    with pytest.raises(ValueError, match='changed since it was opened'):
        service.unregister('project', selection['manifest'], selection['digest'], pod=selection['pod'])
    assert snapshot(root) == before


@pytest.mark.parametrize('confirmed', [True, False])
def test_delete_from_the_form_asks_first(project_setup, monkeypatch, confirmed):
    import caiman.configurations.project_edit as editing
    root, service, selection, _ = project_setup
    before = snapshot(root)
    outcomes = [('delete', deepcopy(selection['manifest']))] + ([] if confirmed else [None])
    form_returning(monkeypatch, outcomes, [])
    asked = []
    class Confirm:
        def __init__(self, **kwargs):
            asked.append(kwargs)
        def run(self):
            if confirmed:
                ConfigurationService(Store(root)).unregister('project', selection['manifest'], selection['digest'], pod=selection['pod'])
            return confirmed
    monkeypatch.setattr(editing, 'ProjectDeleteApp', Confirm)
    assert edit_project(root, service, selection, deepcopy(selection['manifest'])) is None
    assert asked == [{'root': root, 'selection': selection}]
    if confirmed:
        assert service.list_configs('project', pods={'alpha'}) == []
    else:
        assert snapshot(root) == before


@pytest.mark.asyncio
async def test_delete_screen_deletes_only_on_the_explicit_button(project_setup):
    root, service, selection, _ = project_setup
    before = snapshot(root)
    app = ProjectDeleteApp(root=root, selection=selection)
    async with app.run_test(size=(110, 40)) as pilot:
        await pilot.pause()
        assert snapshot(root) == before
        await pilot.click('#delete')
        for _ in range(40):
            if not app.is_running:
                break
            await pilot.pause(0.025)
    assert app.return_value is True
    assert service.list_configs('project', pods={'alpha'}) == []


@pytest.mark.parametrize('color_system', ['truecolor', '256', 'standard'])
def test_gallery_edit_starts_disabled_and_tracks_real_changes(project_setup, monkeypatch, color_system):
    import asyncio
    from rich.console import COLOR_SYSTEMS
    from textual.widgets import Button, Input
    from caiman.configurations.project_form import ProjectFormApp
    from caiman.configurations.project_edit import edit_project

    root, service, selection, _ = project_setup
    assert 'pod' not in selection['manifest']
    before = snapshot(root)

    async def inspect(app):
        app.console._color_system = COLOR_SYSTEMS[color_system]
        async with app.run_test(size=(110, 50)) as pilot:
            await app.workers.wait_for_complete()
            await pilot.pause()
            review = app.query_one('#review-changes', Button)
            assert review.disabled
            disabled_style = review.rich_style
            pod = app.query_one('#project-pod')
            assert not pod.can_focus
            assert str(pod.content) == service.store.pod_name(selection['pod'])
            assert app.collect()['pod'] == selection['pod']
            version = app.query_one('#project-version', Input)
            version.value = 'changed'
            await pilot.pause()
            assert not review.disabled
            assert review.rich_style != disabled_style
            review.focus()
            await pilot.pause()
            assert app.focused is review
            version.value = selection['manifest']['version']
            await pilot.pause()
            assert review.disabled
            assert app.focused is not review
        return None

    monkeypatch.setattr(ProjectFormApp, 'run', lambda app: asyncio.run(inspect(app)))
    assert edit_project(root, service, selection) is None
    assert snapshot(root) == before
