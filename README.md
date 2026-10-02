# Caiman

A context layer for agentic firmware development. It assembles what a coding
agent needs to know about **the hardware**, **the board**, and **the customer's
specification**, writes it into the session's worktree as ordinary files, and
gets out of the way.

## Status

Pre-MVP. Local Markdown ingestion and board/project authoring are implemented,
with TUIs, JSON drafts, validation, and immutable digest pins. Session
materialization, brief generation, access-log hooks, and document Git transport are planned.
Repo Manager supports repository validation and initialization with an optional metadata push.
Startup guidance hooks can be installed for Claude Code and Codex from the home menu.

Caiman models hardware as boards and customer programs as projects. Each project
pins one or more boards and its specification documents, with human-declared
features. The planned session workflow writes that context as ordinary files
for the agent to search and cite.

[Architecture](docs/ARCHITECTURE.md#2-background-and-problem) explains the problem and product boundaries;
[Roadmap](docs/ROADMAP.md) tracks remaining work.

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
snapshots, 4 project snapshots, and 2 document collections. It also remembers
`demo-microbit` and `demo-macropad` so their projects appear in the gallery.
Existing entries are preserved; identical imports are a no-op, and conflicting
names/versions stop the import. Close other Caiman writers during installation.
Use `--store /absolute/path` to try a separate store. This does not install or
run firmware on a device.

A compartment keeps one customer's private documents separate from another's;
usually use one per customer. Each document is explicitly public or belongs to
exactly one compartment. Projects may reference documents from several
compartments. The demo projects need named compartments under the current schema,
but all their documents are explicitly public, including the example requirements.

The home screen shows one card per category: Documents, Boards, Projects,
Hooks, and Repo Manager. Opening Documents, Boards, or Projects shows that
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
all use the same document form. Requirement-ID validation is optional under
the provenance step, without a document-type selector. Existing registrations
remain readable.

Open a document card to edit its name, version, description, applicability,
requirement-ID pattern, and optional provenance. The guided page follows the
board/project editor: expandable detail cards, **Review changes**, then
**Register changes**. Stored file bytes, access, and registration details are
read-only. Edits reuse the stored file, so the original import path is not
needed. Existing digest pins retain their old snapshots; a changed name/version
creates a separate catalog label, and an existing label cannot be overwritten
by renaming another document onto it.

A collection appears as a stack of cards. Name it, describe it, choose its
access, and select documents already in the catalog. Review and save; opening
the stack lets you edit its membership. Collections have no version field:
each save retains an immutable snapshot of the exact selected document revisions.
Re-registering a document does not update collection membership automatically.
Collections contain documents directly, without nested collections. Public
collections contain public documents; a private collection may also contain
documents in its own compartment. Collection access is fixed after creation.

Open **Repo Manager** on the home screen to manage one repository per compartment:

- **Add repo**: enter the compartment and an existing SSH or HTTPS URL. Caiman
  fetches the `caiman-store` branch into a temporary private directory and checks
  its format, compartment, file layout, and transport attributes before saving it.
- **Remove repo**: unregister the repository. Local files and the hosted
  repository are preserved.
- **Initialize repo**: create a local compartment repository. Optionally select
  **Push initial metadata to this remote** and supply an empty private remote
  that you have created on your Git host. Only the initial Caiman metadata is
  pushed. You can also initialize locally and return later to push.

Each action has a review before applying. Git and working SSH or HTTPS
authentication are required for remote operations. Remote privacy and teammate
permissions are managed on the Git host; a format check does not verify them.
Use `public` for the separate repository of public documents.
The registry lives at `<store>/.repositories.json`, with local repositories at
`<store>/.repositories/<compartment>/`. Registration grants no document access.
Document/configuration publication and retrieval remain planned. If an initial
push fails, the local setup is retained and Initialize can retry the push.

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
updates across multiple compartments are not one transaction; a failed operation
can leave complete objects or some refs written. It never publishes a ref before
that ref's objects are complete. Store readers verify digests; local file modes
are not an isolation boundary against another process running as the same user.

## Configure boards and projects

After importing the dataset above, open the micro:bit v2 board or its R2 project:

```bash
.venv/bin/caiman board configure fixtures/board.json
.venv/bin/caiman project configure fixtures/project.json
```

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

**Refresh catalog** lists registered documents. Boards can select public
documents; projects can also select documents within their explicitly entered
compartments. Selecting a board or project during ingestion reuses metadata but
does not add the document to its existing pins. Adopt it through a configuration
edit. A customer's name is not automatically a document's publisher.

Caiman remembers compartments from projects you explicitly choose, but never a
default board or project. It does not scan undeclared compartments for private
projects. These preferences do not select a session mode.

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
adding an entry. Part document pins are edited inside the part card; enter
aliases as comma-separated `name = value` pairs. Vendor completion suggests
common spellings and vendors already on the board, but accepts any value.

**Review changes** shows a field-level diff before registration. An unchanged
draft returns to the form. Fields the form does not expose survive unchanged,
including lineage (`derives_from` and `relation`). To edit lineage, use raw JSON,
`board configure`, or `board new-version`.

**Edit raw JSON in Vim** opens the whole current draft, including unregistered
form edits. Vim must be on `PATH`. Use `:wq` to return changes or `:cq` to keep
the prior form draft. Invalid JSON reopens in the same temporary file so edits
are not lost. Legacy `caiman.board/1` boards and boards with `from`/`to` links
are shown without guided editing; use raw JSON to preserve their shape.

For projects, choose **View projects**, select a snapshot, and press `e` or
**Edit**. Boards, documents, and features each appear as a card grid.
A project may pin several boards, including one board at more than one version.
Each part a feature is realized on names its board, version, and role; a new part
starts on the board when exactly one is pinned. A project registered with a
single `board` (`caiman.project.v1`) opens restated with that board spelled out;
any document it listed only under `precedence` moves to documents, and precedence
order and notes are dropped. The review shows the rewrite. Choose a new version label
or explicitly replace the selected label's ref, then review and register.
Repointing a label never changes an existing digest pin. Editing a board does
not update projects that pin it; adopt the changed board in each project explicitly.

### JSON drafts and document selectors

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

List document selectors with `caiman documents`, adding `--compartment NAME`
for private documents. For the imported micro:bit v2 integration notes:

```json
{"ref": "microbit/bbc-microbit/micro%3Abit%20v2%20integration%20notes/v2-zephyr-4.2.0", "compartment": "public"}
```

Use the catalog's encoded ref, or a full `sha256:…` manifest digest. A supplied
digest is authoritative even if the ref moves. See [board fields](docs/STORAGE.md#board-fields),
[project fields](docs/STORAGE.md#project-fields), and
[selector rules](docs/STORAGE.md#document-selectors) for the field contract.

### Inspect, export, and derive versions

```bash
caiman board show bbc-microbit
caiman board show bbc-microbit --version v2-zephyr-lsm303agr
caiman board export bbc-microbit --version v2-zephyr-lsm303agr --output .caiman/exported-board.json
caiman board new-version bbc-microbit --from-version v2-zephyr-lsm303agr --version Lab-A \
  --relation 'Local experiment based on the imported v2 model'
caiman project show microbit-sound --version R2-v2 --compartment demo-microbit
caiman project export microbit-sound --version R2-v2 \
  --compartment demo-microbit --output .caiman/exported-project.json
```

Omitting the version on `show` lists labels; it never chooses the latest.
`new-version` works for boards and projects: it opens a complete copy in the TUI,
with the supplied lineage and existing pins. Pins change only when explicitly
edited. Project reads require every declared compartment; repeat `--compartment`
when needed. Store-backed commands accept `--store /absolute/path/to/store`.
These operations register locally and never commit or push.

## Development

```bash
.venv/bin/python -m pytest
```

The shared preparation and registration code is separate from Textual widgets so
the future native macOS app can use the same rules. Tests cover metadata and
heading admission, byte preservation, storage integrity, and the interactive
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
| Understand the shared Git backend and Merkle session identity | [Storage §6.6–§6.7](docs/STORAGE.md#66-team-storage-one-git-repository-per-compartment) |
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
