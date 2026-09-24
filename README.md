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
pins a board and its specification documents, with human-declared features and
precedence. The planned session workflow writes that context as ordinary files
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
becomes a default: later actions ask which board or project to use. They can
start with no documents. Use your hardware and project details, or synthetic
values such as board `example-board`, version `Rev A`, part `example/example-mcu`,
project `example-program`, version `Prototype`, customer `Synthetic Example
Customer`, and compartment `example-customer`. A compartment keeps one
customer's private documents separate from another's; usually use one per
customer. Each document is explicitly public or belongs to exactly one
compartment. Projects may reference documents from several compartments.

The home screen provides document actions plus **Create** and **View** for
boards and projects; press `e` while viewing a board or project to edit it. Use
`hjkl` to move between tiles and Enter to open one. In a form, Enter or `i`
starts editing; Escape returns to navigation. Press `q` to go back while
navigating, or to quit from the dashboard. The direct command equivalent for
ingestion is:

```bash
.venv/bin/caiman ingest fixtures/reference-manual.md
```

Use **Repo Manager** on the home screen to manage one repository per compartment:

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

The example manual contains only synthetic text. Select your existing board and
its `example/example-mcu` part to populate issuer and part. Enter document type
`reference-manual`, version `Rev A`, structure `Prose`, and explicitly select
`Public`. Skip optional provenance, review, and select **Register**. The form
also offers existing projects and creation of a new project or board. Cancel
before document registration to avoid publishing that document; configurations
already explicitly registered during setup remain available.

For the synthetic specification in `fixtures/customer-specification.md`, select
`Requirements` and use the ID pattern `^REQ-FLASH-\d{4}$`.

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

After registering the synthetic manual using the values above:

```bash
.venv/bin/caiman board configure fixtures/board.json
.venv/bin/caiman project configure fixtures/project.json
```

Review and register the board before configuring the project. These fixtures
contain synthetic identities only; the project starts with no customer documents
selected. The TUI supports top-level fields, nested JSON collections, a document
catalog, and review before registration.

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

Choose **View boards**, select a card, then press Enter or `e` for the guided
editor. Cards emphasize the board name and version with dot-matrix headings
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
**Edit**. Nested project collections use JSON editors. Choose a new version label
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
for private documents. For the synthetic manual above:

```json
{"ref": "example/example-mcu/reference-manual/Rev%20A", "compartment": "public"}
```

Use the catalog's encoded ref, or a full `sha256:…` manifest digest. A supplied
digest is authoritative even if the ref moves. See [board fields](docs/STORAGE.md#board-fields),
[project fields](docs/STORAGE.md#project-fields), and
[selector rules](docs/STORAGE.md#document-selectors) for the field contract.

### Inspect, export, and derive versions

```bash
caiman board show example-board
caiman board show example-board --version 'Rev A'
caiman board export example-board --version 'Rev A' --output .caiman/exported-board.json
caiman board new-version example-board --from-version 'Rev A' --version 'Rev B' \
  --relation 'Adds a second serial peripheral'
caiman project show example-program --version Prototype --compartment example-customer
caiman project export example-program --version Prototype \
  --compartment example-customer --output .caiman/exported-project.json
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
workflow. All fixtures are synthetic; do not add vendor or customer documents.

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
| Review the proposed shared Git backend and Merkle session identity | [Team storage proposal](docs/proposals/TEAM-STORAGE.md) |
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
