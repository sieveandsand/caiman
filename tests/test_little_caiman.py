"""Little caiman observes managed-document use from transcript tool-call inputs only."""

import hashlib
import json
import os
from pathlib import Path

import pytest
from textual.widgets import Button, Static

from caiman.little_caiman.service import ABSENCE_NOTICE, Session, UsageTracker, list_sessions
from caiman.little_caiman.tui import DocumentUsageCard, SessionPickerApp, UsageApp
from caiman.sessions.service import register_session


DOCUMENT = '''# Flash Controller

Overview.

## Erase

Line six.
Line seven.

## Program

Line eleven.
'''
SECRET = 'REQ-FLASH-SECRET-0142'
DOCUMENTS = '.caiman/sessions/claude-abc12345/context/documents'


@pytest.fixture
def workspace(tmp_path):
    cwd = tmp_path / 'firmware'
    document = cwd / DOCUMENTS / 'oem-alpha' / 'flash-spec@3.2' / 'flash-spec.md'
    document.parent.mkdir(parents=True)
    document.write_text(DOCUMENT)
    document.chmod(0o444)
    store = tmp_path / 'store'
    digest = hashlib.sha256(DOCUMENT.encode()).hexdigest()
    blob = store / 'oem-alpha' / 'blobs' / 'sha256' / digest[:2] / digest
    blob.parent.mkdir(parents=True)
    blob.write_text(DOCUMENT)
    return cwd, document, store


def claude_call(name, arguments, cwd):
    return {'type': 'assistant', 'cwd': str(cwd), 'timestamp': '2026-09-25T10:00:00Z',
            'message': {'content': [{'type': 'tool_use', 'name': name, 'input': arguments}]}}


def write_lines(path, entries, mode='w'):
    with path.open(mode) as stream:
        for entry in entries:
            stream.write(json.dumps(entry) + '\n')


def claude_session(tmp_path, cwd, entries):
    transcript = tmp_path / 'session.jsonl'
    write_lines(transcript, entries)
    return Session('claude', transcript, 'abc12345', cwd, 'Fix flash erase', 0, cwd / DOCUMENTS)


def test_claude_reads_searches_and_edits_are_attributed_to_sections(tmp_path, workspace):
    cwd, document, store = workspace
    relative = f'{DOCUMENTS}/oem-alpha/flash-spec@3.2/flash-spec.md'
    session = claude_session(tmp_path, cwd, [
        claude_call('Read', {'file_path': str(document), 'offset': 5, 'limit': 3}, cwd),
        claude_call('Read', {'file_path': str(document)}, cwd),
        claude_call('Grep', {'pattern': SECRET, 'path': str(document)}, cwd),
        claude_call('Bash', {'command': f'sed -n 10,12p {relative}'}, cwd),
        claude_call('Bash', {'command': f"rg -n '{SECRET}' {DOCUMENTS}/"}, cwd),
        claude_call('Bash', {'command': f'ls {DOCUMENTS}'}, cwd),
        claude_call('Bash', {'command': 'cat README.md'}, cwd),
        claude_call('Edit', {'file_path': str(document), 'old_string': SECRET, 'new_string': 'x'}, cwd),
    ])
    tracker = UsageTracker(session, store)
    assert tracker.poll()
    [usage] = tracker.ranked()
    assert (usage.ref.name, usage.ref.version, usage.ref.title) == ('oem-alpha/flash-spec', '3.2', 'flash-spec')
    assert (usage.reads, usage.whole_reads, usage.searches, usage.edits, usage.via_shell) == (3, 1, 1, 1, 1)
    assert usage.sections == {'Flash Controller › Erase': 1, 'Flash Controller › Program': 1}
    # Listing a directory is not a search; only the rg across the tree counts.
    assert tracker.tree_searches == 1
    assert tracker.integrity(usage.ref).state == 'intact'
    assert not tracker.integrity(usage.ref).writable


def test_tool_results_and_command_text_are_never_retained(tmp_path, workspace):
    cwd, document, store = workspace
    result = {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': f'{document}: {SECRET}'}]}}
    session = claude_session(tmp_path, cwd, [
        result, claude_call('Bash', {'command': f"grep '{SECRET}' {document}"}, cwd)])
    tracker = UsageTracker(session, store)
    tracker.poll()
    [usage] = tracker.ranked()
    assert (usage.reads, usage.searches) == (0, 1)
    assert SECRET not in repr(vars(tracker)) and SECRET not in repr(usage)


def test_absent_workspace_or_unrelated_paths_record_nothing(tmp_path, workspace):
    cwd, document, store = workspace
    elsewhere = tmp_path / 'other'
    elsewhere.mkdir()
    session = Session('claude', tmp_path / 'session.jsonl', 'abc12345', elsewhere, '', 0)
    write_lines(session.transcript, [
        claude_call('Read', {'file_path': str(elsewhere / 'document.md')}, elsewhere),
        claude_call('Grep', {'pattern': 'x', 'path': str(elsewhere)}, elsewhere)])
    tracker = UsageTracker(session, store)
    assert not tracker.poll()
    assert tracker.documents == {} and tracker.tree_searches == 0
    assert not tracker.has_workspace


def test_modified_and_writable_documents_are_flagged(tmp_path, workspace):
    cwd, document, store = workspace
    session = claude_session(tmp_path, cwd, [claude_call('Read', {'file_path': str(document)}, cwd)])
    tracker = UsageTracker(session, store)
    tracker.poll()
    [usage] = tracker.ranked()
    document.chmod(0o644)
    document.write_text(DOCUMENT + '\nAn in-place edit.\n')
    assert tracker.integrity(usage.ref).state == 'modified'
    assert tracker.integrity(usage.ref).writable
    document.unlink()
    assert tracker.integrity(usage.ref).state == 'missing'
    assert UsageTracker(session, tmp_path / 'no-store').integrity(usage.ref).state == 'missing'


def test_direct_store_blob_reads_are_observed(tmp_path, workspace):
    cwd, _, store = workspace
    [blob] = [path for path in store.rglob('*') if path.is_file()]
    session = claude_session(tmp_path, cwd, [claude_call('Bash', {'command': f'head -n 4 {blob}'}, cwd)])
    tracker = UsageTracker(session, store)
    tracker.poll()
    [usage] = tracker.ranked()
    assert usage.ref.location == 'store' and usage.ref.pod == 'oem-alpha' and usage.ref.version is None
    assert usage.sections == {'Lines 1–4': 1}
    assert tracker.integrity(usage.ref).state == 'intact'


def test_polling_reads_only_appended_complete_lines(tmp_path, workspace):
    cwd, document, store = workspace
    session = claude_session(tmp_path, cwd, [claude_call('Read', {'file_path': str(document)}, cwd)])
    tracker = UsageTracker(session, store)
    assert tracker.poll()
    assert not tracker.poll()
    line = json.dumps(claude_call('Read', {'file_path': str(document), 'offset': 10, 'limit': 1}, cwd))
    with session.transcript.open('a') as stream:
        stream.write(line[:20])
    assert not tracker.poll()
    with session.transcript.open('a') as stream:
        stream.write(line[20:] + '\n')
    assert tracker.poll()
    assert tracker.ranked()[0].reads == 2


def test_claude_subagent_transcripts_count_toward_the_session(tmp_path, workspace):
    cwd, document, store = workspace
    session = claude_session(tmp_path, cwd, [])
    subagents = session.transcript.with_suffix('') / 'subagents'
    subagents.mkdir(parents=True)
    write_lines(subagents / 'agent-1.jsonl', [claude_call('Read', {'file_path': str(document)}, cwd)])
    tracker = UsageTracker(session, store)
    tracker.poll()
    assert tracker.ranked()[0].reads == 1


def test_codex_code_mode_commands_and_patches(tmp_path, workspace):
    cwd, document, store = workspace
    relative = f'{DOCUMENTS}/oem-alpha/flash-spec@3.2/flash-spec.md'
    transcript = tmp_path / 'rollout.jsonl'
    exec_input = f'text(await tools.exec_command({{cmd:{json.dumps("nl -ba " + relative + " | sed -n 5,7p")}, workdir:{json.dumps(str(cwd))}}}));'
    write_lines(transcript, [
        {'type': 'session_meta', 'payload': {'id': 'codex-1', 'cwd': str(cwd)}},
        {'type': 'response_item', 'timestamp': '2026-09-25T10:00:00Z',
         'payload': {'type': 'custom_tool_call', 'name': 'exec', 'input': exec_input}},
        {'type': 'response_item', 'payload': {'type': 'custom_tool_call', 'name': 'apply_patch',
                                              'input': f'*** Begin Patch\n*** Update File: {relative}\n@@\n-x\n+y\n*** End Patch'}},
        {'type': 'response_item', 'payload': {'type': 'function_call', 'name': 'shell',
                                              'arguments': json.dumps({'command': ['rg', SECRET, relative], 'workdir': str(cwd)})}},
    ])
    tracker = UsageTracker(Session('codex', transcript, 'codex-1', cwd, '', 0, cwd / DOCUMENTS), store)
    tracker.poll()
    [usage] = tracker.ranked()
    assert (usage.reads, usage.searches, usage.edits) == (1, 1, 1)
    assert usage.sections == {'Flash Controller › Erase': 1}


def register(cwd, harness, session_id):
    cwd.mkdir(parents=True, exist_ok=True)
    register_session(cwd, harness, session_id)


def test_only_registered_sessions_are_listed_newest_first_across_harnesses(tmp_path):
    home = tmp_path / 'home'
    work = tmp_path / 'work'
    claude = home / '.claude' / 'projects' / '-work-firmware' / 'abc.jsonl'
    claude.parent.mkdir(parents=True)
    write_lines(claude, [{'type': 'user', 'cwd': str(work / 'firmware' / 'src')},
                         {'type': 'ai-title', 'aiTitle': 'Erase timing'}])
    codex = home / '.codex' / 'sessions' / '2026' / '09' / '25' / 'rollout-x.jsonl'
    codex.parent.mkdir(parents=True)
    write_lines(codex, [{'type': 'session_meta', 'payload': {'id': 'codex-1', 'cwd': str(work / 'bootloader')}}])
    unregistered = home / '.claude' / 'projects' / '-work-other' / 'zzz.jsonl'
    unregistered.parent.mkdir(parents=True)
    write_lines(unregistered, [{'type': 'user', 'cwd': str(work / 'bootloader')}])
    register(work / 'firmware', 'claude', 'abc')
    (work / 'firmware' / 'src').mkdir()
    register(work / 'bootloader', 'codex', 'codex-1')
    os.utime(claude, (1000, 1000))
    os.utime(codex, (2000, 2000))
    os.utime(unregistered, (3000, 3000))
    sessions = list_sessions(home)
    assert [(s.harness, s.cwd, s.session_id, s.title) for s in sessions] == [
        ('codex', work / 'bootloader', 'codex-1', ''),
        ('claude', work / 'firmware' / 'src', 'abc', 'Erase timing')]
    assert sessions[1].documents == work / 'firmware' / '.caiman' / 'sessions' / 'claude-abc' / 'context' / 'documents'
    assert list_sessions(tmp_path / 'empty') == []


@pytest.mark.asyncio
async def test_picker_is_one_column_in_a_narrow_pane_and_returns_the_session(tmp_path):
    home = tmp_path / 'home'
    for name in ('a', 'b'):
        path = home / '.claude' / 'projects' / f'-work-{name}' / f'{name}.jsonl'
        path.parent.mkdir(parents=True)
        write_lines(path, [{'type': 'user', 'cwd': str(tmp_path / 'work' / name)}])
        register(tmp_path / 'work' / name, 'claude', name)
    app = SessionPickerApp(home=home)
    async with app.run_test(size=(36, 50)) as pilot:
        await pilot.pause()
        cards = list(app.query('.card-face'))
        assert len(cards) == 2
        assert cards[0].region.x == cards[1].region.x and cards[0].region.y < cards[1].region.y
        assert all(card.region.right <= 36 for card in cards)
        await pilot.press('j', 'enter')
    assert app.return_value.session_id == app.sessions[1].session_id


@pytest.mark.asyncio
async def test_usage_view_shows_counts_sections_and_the_absence_notice(tmp_path, workspace):
    cwd, document, store = workspace
    session = claude_session(tmp_path, cwd, [
        claude_call('Read', {'file_path': str(document), 'offset': 5, 'limit': 3}, cwd)])
    app = UsageApp(session=session, store_root=store)
    async with app.run_test(size=(40, 50)) as pilot:
        await pilot.pause()
        [card] = app.query(DocumentUsageCard)
        text = card.label.plain
        assert 'Read 1×' in text and '1× Flash Controller › Erase' in text and 'oem-alpha' in text
        assert 'Modified' not in text
        assert card.region.right <= 40
        assert ABSENCE_NOTICE in str(app.query_one('#notice', Static).render())
        summary = str(app.query_one('#session-summary', Static).render())
        # At 40 columns the summary breaks between facts, never inside one.
        assert '1 Docs · 1 Reads\n0 Searches · 0 Edits' in summary
        # A new read appears on the next poll without restarting the sidecar.
        write_lines(session.transcript, [claude_call('Grep', {'pattern': 'x', 'path': str(document)}, cwd)], 'a')
        await app.refresh_usage()
        await pilot.pause()
        assert 'Searched 1×' in card.label.plain
        await pilot.press('q')
    assert app.return_value is None


@pytest.mark.asyncio
async def test_usage_card_collapses_long_section_lists(tmp_path, workspace):
    cwd, document, store = workspace
    document.chmod(0o644)
    document.write_text('# Top\n' + ''.join(f'\n## Section {n}\n\nText.\n' for n in range(8)))
    session = claude_session(tmp_path, cwd, [claude_call('Read', {'file_path': str(document), 'offset': 1, 'limit': 50}, cwd)])
    app = UsageApp(session=session, store_root=store)
    async with app.run_test(size=(40, 60)) as pilot:
        await pilot.pause()
        [card] = app.query(DocumentUsageCard)
        assert '+5 more' in card.label.plain and 'Modified' in card.label.plain
        card.focus()
        await pilot.press('enter')
        await pilot.pause()
        assert 'more' not in card.label.plain and 'Top › Section 7' in card.label.plain


@pytest.mark.parametrize('filename', ['document.pdf', 'document.docx', 'document'])
def test_resolver_identifies_arbitrary_document_formats(tmp_path, filename):
    from caiman.little_caiman.service import Resolver

    path = tmp_path / 'documents' / 'issuer' / 'manual@v1' / filename
    ref = Resolver(tmp_path / 'documents', None).identify(path)
    assert ref.path == path
    assert ref.name == 'issuer/manual'
    assert ref.version == 'v1'


@pytest.mark.parametrize('filename,content', [
    ('document.pdf', b'%PDF-1.7\n# Not a Markdown heading\n'),
    ('document.docx', b'PK\x00\xff\n# Not a Markdown heading\n'),
    ('document.md', b'\xff\n# Not valid UTF-8 Markdown\n'),
    ('document', b'\x00\n# Binary bytes\n'),
])
def test_binary_reads_do_not_invent_markdown_sections(tmp_path, filename, content):
    path = tmp_path / DOCUMENTS / 'issuer' / 'manual@v1' / filename
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    session = claude_session(tmp_path, tmp_path, [
        claude_call('Read', {'file_path': str(path), 'offset': 2, 'limit': 1}, tmp_path)])
    tracker = UsageTracker(session, None)
    tracker.poll()
    [usage] = tracker.ranked()
    assert usage.reads == 1
    assert usage.sections == {'Lines 2–2': 1}


def load_state(cwd, harness, session_id, **state):
    path = cwd / '.caiman' / 'sessions' / f'{harness}-{session_id}' / 'state.json'
    defaults = dict(kind='project', name='kestrel', version='dvt-1', revision=2, documents=12)
    path.write_text(json.dumps(defaults | state))


@pytest.mark.asyncio
async def test_cards_show_each_sessions_loaded_context(tmp_path, workspace):
    home = tmp_path / 'home'
    for name in ('a', 'b'):
        path = home / '.claude' / 'projects' / f'-work-{name}' / f'{name}.jsonl'
        path.parent.mkdir(parents=True)
        write_lines(path, [{'type': 'user', 'cwd': str(tmp_path / 'work' / name)}])
        os.utime(path, (1000 if name == 'a' else 2000,) * 2)
        register(tmp_path / 'work' / name, 'claude', name)
    load_state(tmp_path / 'work' / 'a', 'claude', 'a')
    app = SessionPickerApp(home=home)
    async with app.run_test(size=(60, 50)) as pilot:
        await pilot.pause()
        newer, older = [card.label.plain for card in app.query('.card-face')]
        assert 'No context loaded' in newer
        assert 'Project kestrel @ dvt-1 · Revision 2' in older and '12 Installed' in older
        await pilot.press('q')
    # The usage view follows a switch made while it is open.
    cwd, _, store = workspace
    register(cwd, 'claude', 'abc12345')
    session = claude_session(tmp_path, cwd, [])
    app = UsageApp(session=session, store_root=store)
    async with app.run_test(size=(60, 60)) as pilot:
        await pilot.pause()
        loaded = app.query_one('#loaded-context', Button)
        assert 'NO CONTEXT LOADED' in loaded.label.plain
        install_contents(cwd, documents=8)
        await app.refresh_usage()
        await pilot.pause()
        text = loaded.label.plain
        assert 'KESTREL @ DVT-1' in text and 'Revision 3' in text
        assert '── BOARDS · 2 ──' in text and '── DOCUMENTS · 8 ──' in text
        assert text.index('BOARDS') < text.index('demo-board @ Rev A') < text.index('DOCUMENTS')
        assert 'demo-board @ Rev A\n  pod public\n\ndemo-board @ Rev B\n  pod alpha' in text
        assert 'manual 0 @ Rev 1\n  nxp/s32k344\n\nmanual 1 @ Rev 1' in text and '+2 more · Enter to show' in text
        assert 'manual 7' not in text
        loaded.focus()
        await pilot.press('enter')
        await pilot.pause()
        assert 'manual 7 @ Rev 1\n  nxp/s32k344' in loaded.label.plain and 'more' not in loaded.label.plain
        await pilot.press('q')


def install_contents(cwd, documents):
    context = cwd / '.caiman' / 'sessions' / 'claude-abc12345' / 'context'
    context.mkdir(parents=True, exist_ok=True)
    (context / 'project.json').write_text(json.dumps({
        'kind': 'project', 'name': 'kestrel', 'version': 'dvt-1', 'revision': 3,
        'boards': [{'name': 'demo-board', 'version': 'Rev A', 'pod': 'public'},
                   {'name': 'demo-board', 'version': 'Rev B', 'pod': 'alpha'}],
        'documents': [{'path': f'documents/nxp/s32k344/manual%20{n}@Rev%201/document.pdf'}
                      for n in range(documents)]}))
