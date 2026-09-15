"""Exercise real key dispatch, including dropdowns and ordinary text editing."""

import pytest
from textual.widgets import Input, Select, TextArea

from caiman.config_tui import ConfigApp
from caiman.onboarding import LauncherApp, SetupApp
from caiman.tui import IngestApp


@pytest.mark.asyncio
async def test_hjkl_moves_fields_without_editing_and_i_preserves_letters(tmp_path):
    app = SetupApp(kind='board', store_root=tmp_path / 'store')
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        app.query_one('#name', Input).focus()
        await pilot.pause()
        await pilot.press('j')
        assert app.focused.id == 'version'
        await pilot.press('k')
        assert app.focused.id == 'name'
        await pilot.press('l')
        assert app.focused.id == 'version'
        await pilot.press('h')
        assert app.focused.id == 'name'
        await pilot.press('x', 'backspace')
        assert app.text('name') == ''
        await pilot.press('i', 'h', 'j', 'k', 'l')
        assert app.text('name') == 'hjkl'
        assert app.editing
        await pilot.press('escape', 'j')
        assert not app.editing
        assert app.focused.id == 'version'
        assert app.text('name') == 'hjkl'
        await pilot.press('ctrl+q')
    assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_select_menu_hjkl_and_enter(tmp_path):
    app = IngestApp(tmp_path / 'store')
    async with app.run_test(size=(100, 36)) as pilot:
        app.step = 1
        app.show_step()
        await pilot.pause()
        selector = app.query_one('#identity_source', Select)
        await pilot.press('enter', 'j', 'k', 'j', 'l')
        await pilot.pause()
        assert selector.value == 'board'
        assert not selector.expanded
        selector.focus()
        await pilot.press('enter', 'h')
        assert not selector.expanded
        await pilot.press('ctrl+q')
    assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_json_editor_enter_edit_escape_and_tab(tmp_path):
    app = ConfigApp('board', tmp_path / 'store')
    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        area = app.query_one('#parts', TextArea)
        area.load_text('')
        area.focus()
        await pilot.pause()
        await pilot.press('enter', 'h', 'j', 'k', 'l', 'enter')
        assert area.text == 'hjkl\n'
        await pilot.press('escape', 'j')
        assert app.focused.id == 'links'
        assert not app.editing
        app.query_one('#board', Input).focus()
        await pilot.pause()
        await pilot.press('enter', 'a', 'tab')
        assert not app.editing
        assert app.focused.id == 'version'
        await pilot.press('ctrl+q')
    assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_home_hjkl_and_enter_activate_button():
    context = {'board': {'manifest': {'board': 'demo', 'version': 'A'}},
               'project': {'manifest': {'project': 'demo', 'version': 'A'}}}
    app = LauncherApp(context=context)
    async with app.run_test(size=(100, 30)) as pilot:
        app.query_one('#ingest').focus()
        await pilot.press('l', 'h', 'j', 'enter')
    assert app.return_value == 'create-board'


@pytest.mark.asyncio
async def test_mouse_editing_and_read_only_catalog(tmp_path):
    app = ConfigApp('board', tmp_path / 'store')
    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        await pilot.click('#board')
        await pilot.press('h', 'j', 'k', 'l')
        assert app.query_one('#board', Input).value == 'hjkl'
        assert app.editing
        await pilot.press('escape')
        app.query_one('#parts', TextArea).read_only = True
        app.query_one('#parts').focus()
        await pilot.pause()
        before = app.query_one('#parts', TextArea).text
        await pilot.press('i', 'j')
        assert app.query_one('#parts', TextArea).text == before
        assert not app.editing
        assert app.focused.id == 'links'


@pytest.mark.asyncio
@pytest.mark.parametrize('editor', ['input', 'json'])
async def test_q_types_while_editing_and_returns_from_form_when_navigating(tmp_path, editor):
    app = ConfigApp('board', tmp_path / 'store')
    async with app.run_test(size=(100, 36)) as pilot:
        await pilot.pause()
        widget = app.query_one('#board', Input) if editor == 'input' else app.query_one('#parts', TextArea)
        if editor == 'json':
            widget.load_text('')
        widget.focus()
        await pilot.pause()
        await pilot.press('i', 'q')
        assert (widget.value if editor == 'input' else widget.text) == 'q'
        assert app.is_running
        await pilot.press('escape', 'q')
        assert not app.is_running
    assert app.registration is None
    assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_q_closes_dropdown_before_leaving_setup(tmp_path):
    app = SetupApp(kind='board', store_root=tmp_path / 'store')
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        select = app.query_one('#existing', Select)
        select.focus()
        await pilot.press('enter')
        assert select.expanded
        await pilot.press('q')
        assert not select.expanded
        assert app.is_running
        await pilot.press('q')
        assert not app.is_running
    assert not (tmp_path / 'store').exists()


@pytest.mark.asyncio
async def test_q_does_not_interrupt_registration(tmp_path):
    app = ConfigApp('board', tmp_path / 'store')
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.pause()
        app.saving = True
        await pilot.press('q')
        assert app.is_running
        app.saving = False
        await pilot.press('q')
        assert not app.is_running


@pytest.mark.asyncio
async def test_q_quits_dashboard():
    app = LauncherApp(context={})
    async with app.run_test(size=(100, 32)) as pilot:
        await pilot.press('q')
    assert app.return_value == 'quit'
