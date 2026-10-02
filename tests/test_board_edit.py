from copy import deepcopy
import pytest
from textual.widgets import Static

from caiman.boards.edit import BoardEditReviewApp, run_board_gallery
from caiman.configurations.service import ConfigurationService
from caiman.storage.store import Store


@pytest.fixture
def board_setup(tmp_path):
    root = tmp_path / 'store'
    service = ConfigurationService(Store(root))
    original = service.prepare('board', {'board': 'demo', 'version': 'v1', 'parts': [
        {'role': 'mcu', 'vendor': 'synthetic', 'part': 'chip', 'documents': [], 'aliases': {'refdes': 'U1'}}], 'links': []})
    service.register(original)
    edited = deepcopy(original.manifest)
    edited['parts'][0]['aliases'] = {'refdes': 'U2'}
    prepared = service.prepare('board', edited)
    return root, service, original, prepared


def snapshot(root):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob('*') if path.is_file()}


async def wait_for(pilot, predicate):
    for _ in range(40):
        if predicate():
            return
        await pilot.pause(0.025)
    assert predicate()


@pytest.mark.asyncio
async def test_review_cancel_has_no_writes(board_setup):
    root, service, original, prepared = board_setup
    before = snapshot(root)
    app = BoardEditReviewApp(root=root, original=original.manifest, prepared=prepared)
    async with app.run_test(size=(110, 45)) as pilot:
        await pilot.pause()
        assert snapshot(root) == before
        await pilot.click('#cancel')
    assert app.return_value is None
    assert snapshot(root) == before
    assert service.load('board', 'demo', 'v1') == original.manifest


@pytest.mark.asyncio
async def test_register_requires_explicit_button_and_preserves_old_digest(board_setup):
    root, service, original, prepared = board_setup
    before = snapshot(root)
    app = BoardEditReviewApp(root=root, original=original.manifest, prepared=prepared)
    async with app.run_test(size=(110, 45)) as pilot:
        await pilot.pause()
        assert snapshot(root) == before
        assert service.load('board', 'demo', 'v1') == original.manifest
        await pilot.click('#register')
        await wait_for(pilot, lambda: app.return_value is not None)
    assert app.return_value == {'manifest': prepared.manifest, 'digest': prepared.digest, 'pod': prepared.pod}
    assert service.load('board', 'demo', 'v1') == prepared.manifest
    assert service.load_digest('board', original.digest) == original.manifest


@pytest.mark.asyncio
async def test_renaming_board_to_an_existing_version_is_blocked(board_setup):
    root, service, original, _ = board_setup
    existing = deepcopy(original.manifest)
    existing.update(version='v2', notes='Existing v2')
    existing = service.prepare('board', existing)
    service.register(existing)
    edited = deepcopy(original.manifest)
    edited.update(version='v2', notes='Edited from v1')
    prepared = service.prepare('board', edited)
    before = snapshot(root)

    app = BoardEditReviewApp(root=root, original=original.manifest, prepared=prepared)
    async with app.run_test(size=(110, 45)) as pilot:
        await pilot.click('#register')
        status = app.query_one('#status', Static)
        await wait_for(pilot, lambda: 'already uses this name and version' in str(status.content))
        assert app.is_running
        await pilot.click('#cancel')

    assert app.return_value is None
    assert snapshot(root) == before
    assert service.load('board', 'demo', 'v1') == original.manifest
    assert service.load('board', 'demo', 'v2') == existing.manifest


@pytest.mark.asyncio
async def test_invalid_review_offers_reedit_but_cannot_register(board_setup):
    root, service, original, prepared = board_setup
    before = snapshot(root)
    app = BoardEditReviewApp(root=root, original=original.manifest, error='Malformed JSON at line 3')
    async with app.run_test(size=(110, 45)) as pilot:
        await pilot.pause()
        assert not app.query('#register')
        await pilot.click('#edit')
    assert app.return_value == 'edit'
    assert snapshot(root) == before


def gallery_once(monkeypatch, selection):
    import caiman.boards.gallery as gallery
    choices = [selection, None]
    class Gallery:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return choices.pop(0)
    monkeypatch.setattr(gallery, 'BoardGalleryApp', Gallery)


def form_returning(monkeypatch, outcomes, seen=None):
    """Stand in for the guided form, recording the draft it was handed."""
    import caiman.boards.form as form
    class Form:
        def __init__(self, **kwargs):
            if seen is not None:
                seen.append(kwargs)
        def run(self):
            return outcomes.pop(0)
    monkeypatch.setattr(form, 'BoardFormApp', Form)


@pytest.mark.parametrize('cancelled', [True, False])
def test_guided_form_cancel_or_unchanged_draft_never_reviews_or_registers(board_setup, monkeypatch, cancelled):
    import caiman.boards.edit as editing
    import caiman.configurations.editor as editor
    root, service, original, prepared = board_setup
    before = snapshot(root)
    gallery_once(monkeypatch, {'manifest': original.manifest, 'digest': original.digest})
    # Cancelling leaves; an unchanged draft returns to the form, and the second
    # visit cancels. Neither reaches review, so neither can register.
    outcomes = [None] if cancelled else [('review', deepcopy(original.manifest)), None]
    seen = []
    form_returning(monkeypatch, outcomes, seen)
    monkeypatch.setattr(editor, 'VimDraft', lambda *a, **k: pytest.fail('Unexpected Vim'))
    monkeypatch.setattr(editing, 'BoardEditReviewApp', lambda **kwargs: pytest.fail('Unexpected review'))
    assert run_board_gallery(root) is None
    assert snapshot(root) == before
    if not cancelled:
        assert 'nothing to register' in seen[1]['message']


def test_raw_json_returns_to_the_form_and_an_invalid_draft_keeps_its_file(board_setup, monkeypatch):
    """Vim is the escape hatch at the bottom of the form, not a separate path:
    what it returns is reviewed by the same guided form it came from."""
    import caiman.boards.edit as editing
    import caiman.configurations.editor as editor
    root, service, original, prepared = board_setup
    before = snapshot(root)
    gallery_once(monkeypatch, {'manifest': original.manifest, 'digest': original.digest})
    calls = {'created': 0, 'entered': 0, 'edits': 0, 'reads': 0, 'errors': 0, 'reviews': 0, 'closed': 0}
    class Draft:
        def __init__(self, manifest):
            calls['created'] += 1
            assert manifest == original.manifest
        def __enter__(self):
            calls['entered'] += 1
            return self
        def __exit__(self, *args):
            calls['closed'] += 1
        def edit(self):
            calls['edits'] += 1
            return True
        def read(self):
            calls['reads'] += 1
            if calls['reads'] == 1:
                raise ValueError('Invalid JSON retained for retry')
            return deepcopy(prepared.manifest)
    class Review:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        def run(self):
            assert snapshot(root) == before
            if self.kwargs.get('prepared') is None:
                calls['errors'] += 1
                assert 'Invalid JSON' in self.kwargs['error']
                return 'edit'
            calls['reviews'] += 1
            reviewed = self.kwargs['prepared']
            registration = service.register(reviewed)
            return {'manifest': reviewed.manifest, 'digest': registration.digest}
    seen = []
    form_returning(monkeypatch, [('raw', deepcopy(original.manifest)), ('review', deepcopy(prepared.manifest))], seen)
    monkeypatch.setattr(editor, 'VimDraft', Draft)
    monkeypatch.setattr(editing, 'BoardEditReviewApp', Review)
    assert run_board_gallery(root) == {'manifest': prepared.manifest, 'digest': prepared.digest}
    # One Vim file across both edits, then the form again carrying what it read.
    assert calls == {'created': 1, 'entered': 1, 'edits': 2, 'reads': 2, 'errors': 1, 'reviews': 1, 'closed': 1}
    assert seen[1]['draft'] == prepared.manifest
    assert service.load_digest('board', original.digest) == original.manifest


def test_abandoning_vim_returns_to_the_form_with_the_draft_it_left(board_setup, monkeypatch):
    import caiman.boards.edit as editing
    import caiman.configurations.editor as editor
    root, service, original, prepared = board_setup
    before = snapshot(root)
    gallery_once(monkeypatch, {'manifest': original.manifest, 'digest': original.digest})
    edited = deepcopy(original.manifest)
    edited['notes'] = 'Typed in the guided form, not yet registered.'
    class Draft:
        def __init__(self, manifest):
            assert manifest == edited
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def edit(self):
            return False
        def read(self):
            pytest.fail('An abandoned Vim session is never read')
    seen = []
    form_returning(monkeypatch, [('raw', deepcopy(edited)), None], seen)
    monkeypatch.setattr(editor, 'VimDraft', Draft)
    monkeypatch.setattr(editing, 'BoardEditReviewApp', lambda **kwargs: pytest.fail('Unexpected review'))
    assert run_board_gallery(root) is None
    assert seen[1]['draft'] == edited
    assert snapshot(root) == before


def test_invalid_draft_reports_in_the_form_without_writing(board_setup, monkeypatch):
    import caiman.boards.edit as editing
    import caiman.configurations.editor as editor
    root, service, original, prepared = board_setup
    before = snapshot(root)
    gallery_once(monkeypatch, {'manifest': original.manifest, 'digest': original.digest})
    broken = deepcopy(original.manifest)
    broken['parts'][0]['vendor'] = ''
    seen = []
    form_returning(monkeypatch, [('review', broken), None], seen)
    monkeypatch.setattr(editor, 'VimDraft', lambda *a, **k: pytest.fail('Unexpected Vim'))
    monkeypatch.setattr(editing, 'BoardEditReviewApp', lambda **kwargs: pytest.fail('Unexpected review'))
    assert run_board_gallery(root) is None
    assert 'parts.0.vendor' in seen[1]['message']
    assert seen[1]['draft'] == broken
    assert snapshot(root) == before
