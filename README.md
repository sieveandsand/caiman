# Caiman

A context layer for agentic firmware development. It assembles what a coding
agent needs to know about **the hardware**, **the board**, and **the customer's
specification**, writes it into the session's worktree as ordinary files, and
gets out of the way.

## The problem

Coding agents are competent at firmware code and unreliable about firmware
*context*. That shows up as three failures, in ascending order of cost:

| Failure | What happens | Found |
|---|---|---|
| **Wrong fact** | A hallucinated register offset. Compiles cleanly, fails on hardware | In an afternoon |
| **Right fact, wrong board** | Configures a peripheral the board does not route, or reads documentation for a silicon revision never populated. The retrieved text was accurate; the work is still discarded — and because it is confident and well-cited, it survives review | At integration |
| **Correct and non-compliant** | Right by the datasheet, right for the board, in violation of the customer's specification — an unknown mandated feature, a default applied where a deviation amended it, or a newer specification release than the program is frozen at | At the customer's acceptance test, months later |

Retrieval quality fixes only the first. The other two need an explicit model of
what you are building and who you are building it for.

## What Caiman does

1. **Models the board.** Parts in named roles, wired together, at a stated
   version. Versions are immutable and their labels are opaque — `2.1`,
   `Rev B`, `EVT2-B`; Caiman never interprets them — with lineage declared
   rather than inferred.
2. **Models the program.** A *project* composes a board version with a customer
   specification release, the features that program requires, and a declared
   precedence order putting deviations above the base specification. The same
   hardware ships to two customers as two projects, in two compartments.
3. **Registers** one already-converted Markdown file unchanged, plus
   document metadata and access labels entered through a TUI. Original-source
   and converter information are optional. Usable headings are required. No PDF
   parsing, splitting, generated maps, or AI processing.
4. **Pins.** A project version *is* the pin set — resolving it yields the board,
   every document digest, the specification release, the precedence order, and
   the feature set. No lockfile in your code repo to drift out of sync.
5. **Writes the session's context to disk.** A one-page brief loaded into the
   agent before turn one, the resolved structure as JSON, and the unchanged
   documents. No server, no retrieval service, no tool schemas eating
   context every turn. Exact-identifier lookup is a lexical problem and `grep` is
   good at those — register identifiers on one side, requirement IDs on the
   other. Grepping a requirement ID returns the base requirement *and* any
   deviation amending it, together.
6. **Configures the session and records what it read.** A session-start hook
   confirms which project the worktree is on — or warns that the brief has gone
   stale, or asks which project to use if there isn't one. Tool-use hooks append
   a per-session log of which managed documents were actually read. The hooks
   observe only: they never block a tool call, never fail a session, and record
   document identities rather than content.
7. **Makes the session's scope consequential.** You declare each session `open`
   or `sealed` — public documents only, or everything the program pins. Caiman
   materializes accordingly, so a wrong call surfaces as a missing file rather
   than a silent disclosure. Both error directions fail safe. There is no policy
   file deciding this on your behalf: the person starting the session knows which
   model it runs and what the work touches, and a config file written months ago
   does not.

Every returned fact carries a citation: document, version, and locator.

## What Caiman is not

- **Not a platform.** Not an agent, not a harness, not a test runner. Platforms
  in this category bundle all of it — see `docs/VISION.md` §4. Caiman is one
  layer, deliberately.
- Not a PDF converter. You convert; Caiman ingests markdown.
- Not a requirements or compliance tool. It cites a requirement; it does not
  track whether you have met it.
- Not a conflict detector. Precedence is declared by a human, never computed —
  inferring it means interpreting contracts.
- Not an enforcement boundary. The human picks the agent; Caiman makes that
  choice have physical effect. It does not police it, and does not pretend to.

## Status

Pre-MVP. Local ingestion and board/project authoring are implemented, with TUIs,
editable JSON configurations, validation, and immutable digest pins. Session
materialization, hooks, and Git remote operations remain roadmap work.

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
customer.

The home screen provides document actions plus **Create** and **View** for
boards and projects; press `e` while viewing a board or project to edit it. Use
`hjkl` to move between tiles and Enter to open one. In a form, Enter or `i`
starts editing; Escape returns to navigation. Press `q` to go back while
navigating, or to quit from the dashboard. The direct command equivalent for
ingestion is:

```bash
.venv/bin/caiman ingest fixtures/reference-manual.md
```

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
Use `template`, `validate`, `show`, `export`, and `new-version` for file authoring
and version management. See [the authoring guide](docs/AUTHORING.md) for fields,
examples, and compartment selection.

## Development

```bash
.venv/bin/python -m pytest
```

The shared preparation and registration code is separate from Textual widgets so
the future native macOS app can use the same rules. Tests cover metadata and
heading admission, byte preservation, storage integrity, and the interactive
workflow. All fixtures are synthetic; do not add vendor or customer documents.

## Documentation

Each document owns one topic and cross-references the rest rather than restating
it.

| File | Owns |
|---|---|
| [`docs/VISION.md`](docs/VISION.md) | Why this exists, the competitive landscape, product non-goals, MVP success criteria |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design: components, models, data flows, interfaces |
| [`docs/AUTHORING.md`](docs/AUTHORING.md) | Implemented board/project TUI and JSON workflows, fields, pinning, and version commands |
| [`docs/STORAGE.md`](docs/STORAGE.md) | On-disk layout: blobs, manifests, refs, and the session workspace |
| [`docs/SECURITY-MODEL.md`](docs/SECURITY-MODEL.md) | Threat model, compartments, agent selection, and the honest limits |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Settled, open, and retired decisions with their alternatives |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phasing, exit criteria, cut order, schedule risk |
| [`docs/GAPS.md`](docs/GAPS.md) | Assessment checklist: validation, correctness, authoring, security, and delivery gaps |
| [`docs/harness.md`](docs/harness.md) | Measured harness transcript behavior and what it implies |
| [`CLAUDE.md`](CLAUDE.md) | Hard invariants and working rules for AI agents in this repo |

## Name

A caiman is a small crocodilian — armored, patient, and comfortable in murky
water. Reference manuals are murky water.
