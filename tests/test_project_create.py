"""Creation uses the shared guided editor and explicit registration."""
from copy import deepcopy

import pytest
from rich.console import COLOR_SYSTEMS
from textual.widgets import Button, Input, Label, SelectionList

from caiman.configurations.project_edit import ProjectEditReviewApp, create_project
from caiman.configurations.project_form import ProjectFormApp, PinnedBoardCard, ProjectDocumentCard
from caiman.documents.picker import DocumentPicker
from test_document_picker import library, board, snapshot


@pytest.mark.parametrize('mode', ['truecolor', '256', 'standard'])
@pytest.mark.parametrize('size', [(110, 50), (65, 30)])
async def test_creation_uses_editor_cards_and_registers_attachments(library, mode, size, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    library.store.pods.ensure('customer')
    library.register(library.prepare('board', board()))
    initial = dict(project='', version='', customer='', pod='customer', boards=[], documents=[])
    before = snapshot(library)
    app = ProjectFormApp(original=initial, root=library.store.root, creating=True)
    app.console._color_system = COLOR_SYSTEMS[mode]
    async with app.run_test(size=size) as pilot:
        await pilot.pause()
        assert not app.query('#delete')
        assert not app.query('Input#project-pod')
        assert 'Program name' in [str(label.content) for label in app.query(Label)]
        assert not app.query_one('#review-changes', Button).disabled
        for key, value in dict(project='program', version='A', customer='Customer').items():
            app.query_one(f'#project-{key}', Input).value = value
        app.query_one('#add-board', Button).press()
        await pilot.pause()
        app.screen.query_one(SelectionList).select_all()
        await pilot.pause()
        app.screen.query_one('#picker-attach', Button).press()
        await pilot.pause()
        assert len(app.query(PinnedBoardCard)) == 1
        add = app.query_one('#add-project-document', Button)
        add.press()
        await pilot.pause()
        assert isinstance(app.screen, DocumentPicker)
        listing = app.screen.query_one(SelectionList)
        listing.focus()
        await pilot.press('space')
        attach = app.screen.query_one('#picker-attach', Button)
        attach.focus()
        await pilot.pause()
        assert len(listing.selected) == 1
        assert 'Selected' in app.export_screenshot()
        assert attach.styles.border_top[0] == 'double'
        attach.press()
        # Attachment resolution and the deferred focus callback finish asynchronously.
        for _ in range(40):
            if len(app.query(ProjectDocumentCard)) == 1 and app.focused is add:
                break
            await pilot.pause(0.025)
        assert app.focused is add
        assert len(app.query(ProjectDocumentCard)) == 1
        app.query_one('#review-changes', Button).press()
        await pilot.pause()
    action, draft = app.return_value
    assert action == 'review' and draft['pod'] == 'customer'
    assert len(draft['boards']) == len(draft['documents']) == 1
    prepared = library.prepare('project', draft)
    review = ProjectEditReviewApp(root=library.store.root, original=initial, prepared=prepared, creating=True)
    async with review.run_test(size=size) as pilot:
        await pilot.pause()
        assert snapshot(library) == before
        assert str(review.query_one('#register', Button).label) == 'Create project'
        review.query_one('#register', Button).press()
        for _ in range(40):
            if review.return_value:
                break
            await pilot.pause(0.025)
    assert review.return_value['manifest']['documents'] == draft['documents']
    assert library.load('project', 'program', 'A', pods={'customer'}) == prepared.manifest


def test_creation_retains_invalid_draft_review_return_and_entry_pod(library, monkeypatch):
    import caiman.configurations.project_form as forms
    import caiman.configurations.project_edit as editing

    library.store.pods.ensure('customer')
    prepared = library.prepare('board', board())
    library.register(prepared)
    handed_board = dict(manifest=prepared.manifest, digest=prepared.digest, pod=prepared.pod)
    before = snapshot(library)
    seen = []

    class Form:
        def __init__(self, **kwargs):
            self.options = kwargs
            seen.append(deepcopy(kwargs))
        def run(self):
            draft = self.options['draft']
            if len(seen) == 1:
                draft['project'] = 'program'
                return 'review', draft  # Required version/customer still missing.
            if len(seen) == 2:
                draft.update(version='A', customer='Customer')
                return 'raw', draft
            if len(seen) == 3:
                return 'review', draft
            return None

    def raw(root, original, draft, **kwargs):
        return dict(draft, pod='public')

    reviews = []
    class Review:
        def __init__(self, **kwargs):
            reviews.append(kwargs)
        def run(self):
            return 'edit'

    monkeypatch.setattr(forms, 'ProjectFormApp', Form)
    monkeypatch.setattr(editing, 'ProjectEditReviewApp', Review)
    monkeypatch.setattr('caiman.configurations.editor.vim_excursion', raw)
    assert create_project(library.store.root, pod='customer', board=handed_board) is None
    assert seen[1]['message']
    assert seen[1]['draft']['project'] == 'program'
    assert all(options['creating'] and options['draft']['pod'] == 'customer' for options in seen)
    assert seen[-1]['draft']['boards'][0]['digest'] == prepared.digest
    assert reviews[0]['prepared'].pod == 'customer' and reviews[0]['creating']
    assert snapshot(library) == before
