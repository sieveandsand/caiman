from copy import deepcopy
import pytest

from caiman.board_edit import BoardEditReviewApp, run_board_gallery
from caiman.config_store import ConfigurationService
from caiman.store import Store


@pytest.fixture
def board_setup(tmp_path):
    root = tmp_path / 'store'
    service = ConfigurationService(Store(root))
    original = service.prepare('board', {'board': 'demo', 'version': 'v1', 'parts': [
        {'role': 'mcu', 'part': 'synthetic/chip', 'documents': [], 'refdes': 'U1'}], 'links': []})
    service.register(original)
    edited = deepcopy(original.manifest)
    edited['parts'][0]['refdes'] = 'U2'
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
    assert app.return_value == {'manifest': prepared.manifest, 'digest': prepared.digest}
    assert service.load('board', 'demo', 'v1') == prepared.manifest
    assert service.load_digest('board', original.digest) == original.manifest


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
    import caiman.board_gallery as gallery
    choices = [selection, None]
    class Gallery:
        def __init__(self, **kwargs):
            pass
        def run(self):
            return choices.pop(0)
    monkeypatch.setattr(gallery, 'BoardGalleryApp', Gallery)


@pytest.mark.parametrize('cancel', [True, False])
def test_vim_cancel_or_unchanged_draft_does_not_review_or_register(board_setup, monkeypatch, cancel):
    import caiman.board_edit as editing
    import caiman.external_editor as editor
    root, service, original, prepared = board_setup
    before = snapshot(root)
    gallery_once(monkeypatch, {'manifest': original.manifest, 'digest': original.digest})
    class Draft:
        def __init__(self, manifest):
            self.manifest = manifest
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def edit(self):
            return not cancel
        def read(self):
            assert not cancel
            return self.manifest
    monkeypatch.setattr(editor, 'VimDraft', Draft)
    monkeypatch.setattr(editing, 'BoardEditReviewApp', lambda **kwargs: pytest.fail('Unexpected review'))
    assert run_board_gallery(root) is None
    assert snapshot(root) == before


def test_invalid_vim_draft_reopens_same_session_then_registers_on_review(board_setup, monkeypatch):
    import caiman.board_edit as editing
    import caiman.external_editor as editor
    root, service, original, prepared = board_setup
    before = snapshot(root)
    gallery_once(monkeypatch, {'manifest': original.manifest, 'digest': original.digest})
    calls = {'created': 0, 'entered': 0, 'edits': 0, 'reads': 0, 'reviews': 0, 'closed': 0}
    class Draft:
        def __init__(self, manifest):
            calls['created'] += 1
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
            return prepared.manifest
    class Review:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
        def run(self):
            calls['reviews'] += 1
            assert snapshot(root) == before
            if calls['reviews'] == 1:
                assert self.kwargs['prepared'] is None
                assert 'Invalid JSON' in self.kwargs['error']
                return 'edit'
            assert self.kwargs['error'] is None
            reviewed = self.kwargs['prepared']
            registration = service.register(reviewed)
            return {'manifest': reviewed.manifest, 'digest': registration.digest}
    monkeypatch.setattr(editor, 'VimDraft', Draft)
    monkeypatch.setattr(editing, 'BoardEditReviewApp', Review)
    assert run_board_gallery(root) == {'manifest': prepared.manifest, 'digest': prepared.digest}
    assert calls == {'created': 1, 'entered': 1, 'edits': 2, 'reads': 2, 'reviews': 2, 'closed': 1}
    assert service.load_digest('board', original.digest) == original.manifest
