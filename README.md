# Caiman

A context layer for agentic firmware development. It assembles what a coding
agent needs to know about **the hardware**, **the board**, and **the customer's
specification**, writes it into the session's worktree as ordinary files, and
gets out of the way.

## Status

Pre-MVP. Local document ingestion and board/project authoring are implemented,
with TUIs, JSON drafts, validation, and immutable digest pins. Session
materialization, brief generation, and access-log hooks are planned.
Pods support local folders and optional Git clone/sync.
Startup guidance hooks can be installed for Claude Code and Codex from the home menu.

Caiman models hardware as boards and customer programs as projects. Each project
pins one or more boards and its documents, with collections available to group
and select related documents. The planned session workflow writes that context as ordinary files
for the agent to search and cite.

[Architecture](docs/ARCHITECTURE.md#2-background-and-problem) explains the problem and product boundaries;
[Roadmap](docs/ROADMAP.md) tracks remaining work.

The accepted [session and Docker workflow](docs/CONTAINER-CONTEXT.md) is planned:
Caiman runs on the host, each agent session receives its own context folder in
an initialized worktree, and containers read it through the existing bind mount.
The open host TUI processes context-switch requests from a portable workspace
adapter. The current startup guidance hooks do not implement this workflow.

## First launch and document ingestion

Requires Python 3.11+ and an interactive terminal.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/caiman
```

Caiman opens a home screen; create a board, then a project that uses it. Neither
becomes a default: later actions ask which board or project to use.

For a populated example workspace, import the [public example dataset](fixtures/README.md):

```bash
.venv/bin/python scripts/load_examples.py --check
.venv/bin/python scripts/load_examples.py --install
.venv/bin/caiman
```

This adds micro:bit v1/v2 hardware, Zephyr's sound application, and two Adafruit
MacroPad applications with their hardware context, pinned upstream source, and
Caiman-authored acceptance examples. It registers 11 public documents, 3 board
snapshots, 4 project snapshots, and 2 document collections. Their `demo-microbit` and `demo-macropad` pods appear automatically.
Existing entries are preserved; identical imports are a no-op, and conflicting
names/versions stop the import. Close other Caiman writers during installation.
Use `--store /absolute/path` to try a separate store. This does not install or
run firmware on a device.

A **pod** is a folder of documents and configurations, optionally shared through
its own Git repository. The Git host handles sharing permissions. `public` is
the permanent default pod; it cannot be changed or removed. References may
target only the owning pod or public, and public stays self-contained. Documents,
collections, boards, and projects each belong to one pod. See [Pods](docs/PODS.md) for the current backend design.

The home screen shows one card per category: Documents, Boards, Projects,
Hooks, and Pods. Opening Documents, Boards, or Projects shows that
category's cards with add cards at the end; press Enter or `e` on a board
or project to edit it. After adding, you return to the same category. Use
`hjkl` to move between cards and Enter to open one. In a form, Enter or `i`
starts editing; Escape returns to navigation. Press `q` to go back while
navigating, or to quit from the dashboard. The direct command equivalent for
ingestion is:

```bash
.venv/bin/caiman ingest fixtures/documents/microbit-v2-hardware.md
```

Documents has separate **+ Add document** and **+ Add collection** cards. Give
each document a name and description; manuals, design notes, and requirements
all use the same document form. Any readable file is accepted, including PDF,
Office documents, plain text, binary, empty, and non-UTF-8 files. There are no
heading or requirement-ID checks. Bytes and file extensions are preserved;
registration does not add conversion or text extraction.

Documents have no `structure` or
`requirements` metadata fields. Existing registrations remain readable.

Open a document card to edit any metadata, review changed fields and known local
usages, then **Save metadata**. Every edit saves a complete immutable manifest.
All references, including older boards, show the latest approved metadata while
keeping the same file bytes. Document metadata does not restrict attachment to
boards or parts. Existing board/project/collection snapshots remain unchanged.
Changed file content requires a new document name or version.
Expand **Metadata History** in the document editor to browse earlier saved
metadata, including each revision's complete manifest JSON. History is read-only
and does not change your draft.
[Document manifest workflow](docs/DOCUMENT-METADATA.md) explains stable document
IDs, current views, immutable history, and interrupted-save recovery.

A collection appears as a stack of cards. Name it, describe it, choose its
pod, and select documents already in the catalog. **Choose documents** opens
the searchable picker with individual documents only. The editor shows only included
documents. Use the **+ Choose documents** tile to add more, or expand a document
card to access **Remove from collection**. Review and save; opening
the stack lets you edit its membership. Collections have no version field:
each save retains an immutable snapshot of the selected document IDs and bodies.
Re-registering a document does not update collection membership automatically.
Collections contain documents directly, without nested collections, and may
reference documents from their own pod or public. Their owning pod is fixed after
creation. References do not copy document contents between pods.

Documents, Projects, and Boards have **pod tabs** at the top. Press `/` for the next pod, or use
`[` and `]` for the previous and next pods, or Left/Right and `h` / `l` when the tabs have focus. Press `j`
from the tabs to enter the cards. The active tab selects which
items are shown and the destination for new documents, collections, projects, or boards.

Open **Pods** on the home screen to create a local pod, clone a team's pod,
connect Git, sync, set the default, or disconnect a remote. Git is optional:
local pods are ordinary folders. Each connected pod folder is its own repository.
Connect never publishes data; **Sync** commits, fetches, merges, and pushes.
Conflicts preserve local and remote history for resolution with Git.

```bash
caiman pod create alpha
caiman pod default alpha
caiman pod connect alpha git@example.com:team/alpha.git
caiman pod sync alpha
caiman pod list
```

Teammates use `caiman pod clone alpha URL`. Git host permissions control fetching
and pushing; local copies remain usable offline. Each command accepts `--store`.
[Pods](docs/PODS.md) documents references, migration, and conflict behavior.

Use **Hooks → Claude Code** or **Hooks → Codex** to add a startup hook to a
project directory. Choose **Preview** to review the exact settings diff, then
**Install**. Existing settings and hooks are preserved; repeated installation
does not add duplicates. Claude Code uses `.claude/settings.json`; Codex uses
`.codex/hooks.json`. Restart the harness after installation. In Codex, open
`/hooks` to review and trust the hook (the project must also be trusted).
See the official [Claude Code hook reference](https://code.claude.com/docs/en/hooks)
and [Codex hook reference](https://learn.chatgpt.com/docs/hooks).

The hook introduces available Caiman commands without reading document bodies
or private catalogs. It does not yet sync a workspace or log document access.
It uses the Python installation running Caiman and the selected store, so
reinstall it if that Python environment moves. A missing store produces no
context, and a missing installation or callback error leaves the session running.

For manual ingestion, use the metadata for that document in
[`fixtures/dataset.json`](fixtures/dataset.json). The hardware documents are
integration notes with attributed upstream source, not semiconductor reference
manuals. The requirement documents are explicitly Caiman-authored examples;
they do not claim to be official upstream or customer specifications. The loader
above registers the whole set in dependency order and is the easiest starting point.

The default store is `~/.local/share/caiman/store` (or beneath `XDG_DATA_HOME`).
Override it with `caiman ingest manual.md --store /path/to/store`, or set
`store_root` to an absolute path in `~/.config/caiman/config.toml`
(`XDG_CONFIG_HOME` is respected). Keep document stores outside firmware code
repositories. Registration creates local objects only: it does not initialize a
Git repository, commit, or push. No original PDF or converter information is
required, and document contents are never sent to a service.

The store currently supports a single writer. Each ref update is atomic, but
updates across multiple pods are not one transaction; a failed operation
can leave complete objects or some refs written. It never publishes a ref before
that ref's objects are complete. Store readers verify digests; local file modes
are not an isolation boundary against another process running as the same user.

## Configure boards and projects

After importing the dataset above, open the micro:bit v2 board or its R2 project:

```bash
.venv/bin/caiman board configure fixtures/board.json
.venv/bin/caiman project configure fixtures/project.json
```

Projects select board versions, documents, and collections. **Choose documents**
shows individual documents and named collections together. Selecting a collection
attaches its stable identity to the project; its current membership is resolved
when the project is read. Saving collection edits therefore updates every project
referencing that collection, without rewriting project snapshots.

For example, if a referenced collection changes from A/B to B/C, the project's
collection contributes B/C automatically. If A is also attached directly, A stays.
Overlapping collections and direct attachments contribute each document once.
Collection renames also appear automatically. Document metadata edits remain
visible through existing references; each member's body stays fixed. Replacing a
member with a newly registered document explicitly changes the body supplied by
that collection.

Saved collection references also retain the original collection snapshot digest
for historical resolution. Normal views follow the current collection; exact
project manifests and their original collection snapshots remain unchanged.
Existing projects with previously expanded document lists keep those direct
attachments: select the collection again to establish a live reference and remove
any unwanted direct attachments. Caiman does not infer the old grouping.

Boards, parts, and collection editing still expand selected collections into
individual document attachments. Collections cannot contain nested collections.

Features are no longer part of normal project authoring. Existing feature data is
preserved and can be edited through raw JSON; new projects do not require it.
Collections remain document groups, without feature scope or hardware mappings.

The top-level JSON files are copies of the micro:bit v2 and sound R2 drafts.
The full dataset also demonstrates v1 hardware and two projects sharing the
MacroPad board. Use a new version label to retain the imported snapshot when
experimenting. The TUI supports top-level fields, nested JSON collections, a
document catalog, and review before registration.

For a fresh draft, run `caiman board configure` or `caiman project configure`.
Both use the same validation as JSON drafts. **Review** resolves document and
board references into digest pins; **Register** checks those pins again and
stores a complete snapshot. Going back to edit invalidates the previous review.
Cancelling before registration writes no version; loading a JSON file never
modifies that file.

**Refresh catalog** lists documents from every local pod. Boards and projects
can both pin documents in their own pod or public. Selecting a board or project during ingestion reuses metadata but
does not add the document to its existing pins. Adopt it through a configuration
edit. A customer's name is not automatically a document's publisher.

Caiman discovers local pods automatically. The default pod is permanently public;
there is no remembered default board or project and no application membership list.

### Keyboard navigation

| Context | Keys |
|---|---|
| Dashboard or board grid | `h/j/k/l` moves; Enter opens; `q` returns or quits |
| Form navigation | `h/k` previous control; `j/l` next; Enter or `i` edits |
| Text editing | Letters type normally; Escape returns to navigation |
| Dropdown | `j/k` moves; Enter or `l` selects; Escape or `h` closes |

Tab and Shift+Tab also move between controls. Clicking a text field starts
editing. In navigation mode, `q` closes a dropdown first, otherwise leaves the
form; while editing it types normally. Leaving discards unsubmitted changes but
cannot interrupt a registration already being written. The mode hint shows the
available controls; there are no Ctrl shortcuts or command palette.

### Edit an existing board or project

Choose **Boards**, select a card, then press Enter or `e` for the guided
editor. Cards emphasize the board name and version with fullwidth uppercase headings
where they fit, and show only part names and counts of parts, links, and document
pins (board and part documents combined). Page Up/Down scroll long cards.
Board-level fields stay at the top;
board documents, parts, and links each appear in a responsive card grid. Click
a card or press Enter to expand its editor in place, and choose **Done** to
collapse it while keeping draft edits. Each grid has a large **+** card for
adding an entry. For board documents and inside a part, **Choose documents** opens a searchable list
from all locally available pods. Select documents with Space or a click, then
**Attach selected**. Selections survive search changes; Cancel adds nothing.
Already attached documents are excluded. Attached rows show names, versions,
and pods, with optional notes and Remove controls; part reference fields live under
**Reference details**. Empty rows do not count as document pins. Register new
documents from the Documents page before attaching them.

**Delete board** opens a confirmation for the selected board version and pod.
Confirming removes it from the gallery; its stored snapshot remains available
to projects that already pin it. **Keep board** returns to the current draft.

Enter aliases as comma-separated `name = value` pairs. Vendor completion suggests
common spellings and vendors already on the board, but accepts any value.

**Review changes** shows a field-level diff before registration. Across edit
pages, the button stays greyed out until the draft changes and becomes disabled
again when all edits are reverted. Fields the form does not expose survive unchanged,
including lineage (`derives_from` and `relation`). To edit lineage, use raw JSON,
`board configure`, or `board new-version`.

**Edit raw JSON in Vim** opens the whole current draft, including unregistered
form edits. Vim must be on `PATH`. Use `:wq` to return changes or `:cq` to keep
the prior form draft. Invalid JSON reopens in the same temporary file so edits
are not lost. Legacy `caiman.board/1` boards and boards with `from`/`to` links
are shown without guided editing; use raw JSON to preserve their shape.

For projects, choose **View projects**, select a snapshot, and press `e` or
**Edit**. Boards and documents each appear as a card grid.
Use **Choose documents** for individual documents and named collections in one
searchable picker. Overlapping groups add each document once. Existing feature
declarations are retained and remain editable through **Edit raw JSON in Vim**.
A project may pin several boards, including one board at more than one version.
A project registered with a
single `board` (`caiman.project.v1`) opens restated with that board spelled out;
any document it listed only under `precedence` moves to documents, and precedence
order and notes are dropped. The review shows the rewrite. Choose a new version label
or explicitly replace the selected label's ref, then review and register.
Repointing a label never changes an existing digest pin. Editing a board does
not update projects that pin it; adopt the changed board in each project explicitly.

### JSON drafts and document selectors

The configuration-authoring screen also offers **Choose documents** and **Choose
part documents** beside board JSON fields, and **Choose documents** for projects.
Each picker includes both documents and collections. For part attachments, select the part first. Confirming fills its
document references; canceling leaves the JSON unchanged. The normal review and
registration step still saves the configuration.

```bash
caiman board template --output .caiman/board.json
caiman board validate .caiman/board.json
caiman board configure .caiman/board.json
```

The same commands work with `project`. Templates are incomplete: fill them in
before validation. `validate` prints a resolved configuration without writing a
version; `configure` opens it for review. Unknown fields, duplicate JSON keys,
and invalid relationships are errors. Template and export files use mode `0600`
and never overwrite an existing file. Keep private drafts in `.caiman/` or
outside the firmware repository.

List all local document selectors with `caiman documents`, or filter with `--pod NAME`. For the imported micro:bit v2 integration notes:

```json
{"ref": "microbit/bbc-microbit/micro%3Abit%20v2%20integration%20notes/v2-zephyr-4.2.0", "pod": "public"}
```

Use the catalog's encoded ref, or a full `sha256:…` manifest digest. A supplied
digest selects that document even if the ref moves. Saving stores its stable
document ID and fixed blob hash; normal reads show its latest approved metadata.
A stored selector has the form `{"pod": "public", "document": "stable-id", "blob": "sha256:…"}`. See [board fields](docs/STORAGE.md#board-fields),
[project fields](docs/STORAGE.md#project-fields), and
[selector rules](docs/STORAGE.md#document-selectors) for the field contract.

### Inspect, export, and derive versions

```bash
caiman board show bbc-microbit
caiman board show bbc-microbit --version v2-zephyr-lsm303agr
caiman board export bbc-microbit --version v2-zephyr-lsm303agr --output .caiman/exported-board.json
caiman board new-version bbc-microbit --from-version v2-zephyr-lsm303agr --version Lab-A \
  --relation 'Local experiment based on the imported v2 model'
caiman project show microbit-sound --version R2-v2 --pod demo-microbit
caiman project export microbit-sound --version R2-v2 \
  --pod demo-microbit --output .caiman/exported-project.json
```

Omitting the version on `show` lists labels; it never chooses the latest.
`new-version` works for boards and projects: it opens a complete copy in the TUI,
with the supplied lineage and existing pins. Pins change only when explicitly
edited. Use `--pod` to filter a catalog or disambiguate a name. Store-backed commands accept `--store /absolute/path/to/store`.
These operations register locally and never commit or push.

## Development

```bash
.venv/bin/python -m pytest
```

The shared preparation and registration code is separate from Textual widgets so
the future native macOS app can use the same rules. Tests cover metadata and
arbitrary-file admission, byte preservation, storage integrity, and the interactive
workflow. Most unit tests construct small synthetic inputs. `tests/test_examples.py`
validates the public demo dataset and its repeatable import. Reviewed open-source
excerpts in `fixtures/` retain pinned provenance and license notices; never add
private customer documents or vendor material without redistribution rights.

## Documentation

Source code is grouped by feature under `src/caiman/`: `documents`, `boards`,
`configurations`, `dashboard`, `repositories`, `hooks`, `storage`, and `cli`.
Shared terminal components live in `ui`. See the [source layout](CLAUDE.md#layout)
for package responsibilities.

Start with the guide for the task; there is no need to read the whole folder.

| If you need to… | Read |
|---|---|
| Use the implemented board/project workflows | [Configuration guide](#configure-boards-and-projects) |
| See what works and what comes next | [ROADMAP.md](docs/ROADMAP.md) |
| Understand the product rationale and scope | [Architecture §2–4](docs/ARCHITECTURE.md#2-background-and-problem) |
| Evaluate MVP success | [Roadmap criteria](docs/ROADMAP.md#success-criteria-for-the-mvp) |
| Change components, resolution, or session interfaces | [ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Change stored objects or workspace layout | [STORAGE.md](docs/STORAGE.md) |
| Understand pods and Git sharing | [Pods](docs/PODS.md) |
| Review labels, visibility, audit, or revocation | [SECURITY-MODEL.md](docs/SECURITY-MODEL.md) |
| Understand a choice or resolve an open decision | [DECISIONS.md](docs/DECISIONS.md) |
| Find outstanding validation and review tasks | [GAPS.md](docs/GAPS.md) |
| Work as an AI agent in this repository | [CLAUDE.md](CLAUDE.md) |

[harness.md](docs/harness.md) and [research/](docs/research/) contain historical
observations, not implementation requirements. Design docs include planned
features; use this README for commands available today.

Keep each topic in its owning document and link to it elsewhere. Decisions record
why, guides explain how, and the roadmap records delivery status. Preserve decision
IDs and distinguish proposed behavior from implemented commands.

## Name

A caiman is a small crocodilian — armored, patient, and comfortable in murky
water. Reference manuals are murky water.
