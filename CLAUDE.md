# CLAUDE.md — Caiman

Instructions for AI agents working in this repository.

**This file owns the invariants.** Everything else is a pointer.

| Before you | Read |
|---|---|
| Make any non-trivial change | This file, then `docs/ARCHITECTURE.md` |
| Touch `store/`, `ingest/`, or `materialize/` | `docs/STORAGE.md` |
| Touch anything label-, compartment-, or agent-related | `docs/SECURITY-MODEL.md` |
| Resolve something that looks undecided | `docs/DECISIONS.md` — settled, open, and retired. Do not silently resolve an open decision in code |

---

## What Caiman is

Caiman supplies three kinds of context coding agents lack in firmware work:
**descriptive** (what the hardware does), **structural** (what this design is),
and **normative** (what this program must do). `docs/ARCHITECTURE.md` §2 has the failure
mode each one prevents; the normative layer is where the unserved problem is, and
the first two are substrate to build competently rather than inventively.

Three framing facts that constrain most changes:

- **Caiman is a layer, not a platform.** `sync` writes files into a worktree and
  gets out of the way. Session orchestration and hardware-in-the-loop execution
  are permanently somebody else's job (S-01).
- **The filesystem is the interface.** No server, no index, no process between
  the agent and the documents (S-18).
- **A Board is hardware; a Project is a program** — one or more board versions
  plus a customer specification set, features, and compartments (S-13, S-34,
  S-36).

---

## Hard invariants

A change that violates one of these is a bug even if every test passes.

### I-1. One owning pod; no application authorization layer

A pod is a local folder, optionally its own Git repository. The Git host owns
remote access; local filesystem availability owns local access. `public` is an
ordinary default pod. Do not reintroduce document access labels, session
membership lists, or public-only board/collection rules. [PODS.md](docs/PODS.md)
owns the current model and supersedes older compartment policy sections.

### I-2. Stable routes and immutable identities

Each artifact lives in one pod. Cross-pod pins carry a stable pod ID and immutable
manifest digest. Folder/display-name changes must not retarget references. Old
snapshots keep their original bytes and hashes; legacy adapters operate in memory.
Missing dependencies must be reported, never silently substituted or copied.

### I-3. Sharing is explicit and per pod

Saving locally never commits or pushes. A pod's Git repository contains only that
pod's data. Sync uses normal fast-forward protection and preserves local work on
failure. Do not copy dependencies into a repository to make them accessible.
Keep materialized content out of firmware repositories and preserve their guards.
Never commit customer documents or vendor content without redistribution rights
to this source repository; licensed examples retain their provenance and notices.

### I-4. Pin digests, not tags

Board versions, project versions, and document references resolve to immutable
content digests. Tags are mutable — and a human-facing version name like `2.1` or
`B-sample` **is a tag**: you add a deviation to it a month after cutting it. Any
code path that resolves a name at consumption time rather than at pin time is a
reproducibility bug. A session resolves once, at sync, and holds the digest.

### I-5. Never guess a hardware or requirement fact

Every returned fact carries `(document identity, document version, locator)`.
All three are required.

- **Requirement-structured documents** (customer specs): the requirement ID.
- **Everything else**: a heading path, which is the floor.
- A page number rides alongside when the conversion supplied one, never instead
  of a locator.

Corollary at ingest: every document must have usable Markdown headings, as
defined in `ARCHITECTURE.md` §6.4.2. Reject missing or ambiguous heading paths;
do not repair the input or fall back to line-only citations. A document declared
requirement-structured must also contain IDs matching its declared pattern.

Registration stores one input file byte-for-byte as one content blob (S-25).
The destination pod is chosen by the user. No splitting,
chunk entities, generated maps, summaries, or AI calls belong in ingest.
Original-source and converter information are optional (S-26). Missing provenance
never implies public access or local conversion; the chosen pod determines storage.

### I-6. The brief is metadata only

The project brief is open — always, including for projects whose documentation is
entirely compartmented — because existence is structure and detail is content.
That holds only if the generator **cannot see document content**. It reads
manifests: roles, part numbers, silicon revisions, links, feature names, document
identities, versions, digests.

Never give the brief generator access to document text, not even to produce a
helpful summary. The brief names the program by **codename only**; customer
identity stays in the compartmented project manifest.

### I-7. Version labels are opaque

Never parse a board or project version string. Never infer that `2.1` relates to
`2.0`, never order them, never compute "latest", never implement wildcard
matching. Version semantics vary per company; encoding one convention breaks
every other.

On the normative side this is not a modelling preference: a program is
contractually frozen at a specification release, so "newer" is not "better", and
silently resolving to latest is a compliance failure.

Corollary: a bare board or project name never resolves to a version. It returns
the list.

### I-8. Declared, never inferred

Version lineage, precedence among specification documents, and relationships
between features are supplied by a human with a free-text explanation. Caiman
renders them; Caiman never computes them.

Do not write code that infers a relationship — not version ordering, not "this
spec looks like it supersedes that one", and above all not conflict detection
between specifications. If a deviation amends a requirement, a human says so by
naming the requirement IDs, and `grep` surfaces both together.

A destination pod is chosen at registration, never inferred from document content.

### I-9. The document set must be complete and greppable

Everything downstream depends on `grep` over the materialized documents returning
the whole truth.

- **Never symlink a directory into the documents tree.** Ripgrep does not follow
  symlinks without `-L`, and `grep -r` does not follow symlinked directories. The
  agent would search, get results, and have no indication part of the set was
  skipped. Silent incompleteness is the worst failure this system can have —
  there is no error to notice.
- **Key the blob cache by compartment.** Hardlinks share an inode, so mode lives
  on the inode; linking a compartmented blob out of a shared cache leaves it
  reachable by the cache path.
- **Blobs and materialized documents are read-only** (`0444`). An in-place edit
  propagates through every hardlink and poisons the cache for every session.
- **A partial materialization is an error, not a warning.** If any pinned
  document cannot be written, `sync` fails and says which.

### I-10. Hooks observe; they never block, and they log identities only

Caiman registers callbacks with the harness to configure a session at start and
to record which managed documents were read. Three rules, none of them
negotiable:

**Never deny a tool call.** `PreToolUse` can block; Caiman does not use it.
Blocking would make Caiman look like an enforcement boundary, which S-19 says it
is not — and it would add nothing, because a document the session may not see was
never materialized, so there is no read to deny. A gate where nothing can pass is
the shape of a gate with none of the substance.

**Never fail a session.** Hook failures, timeouts, and a missing Caiman
installation all leave the session running and unlogged. A broken audit hook that
halts work gets deleted within a week, which is worse than a log with gaps that
are known.

**Never record content.** The access log holds paths, document names, versions,
and compartments — the same metadata-only rule as the brief (I-6). A log entry
containing an excerpt of a specification is a copy of that specification in a file
nobody thinks of as one.

A fourth rule about how it is described, which matters as much as the code:
**absence of a record is not proof a document was not read.** Reads through
`Bash`, uninstalled hooks, and anything outside the harness are all invisible.
Say so wherever the log is surfaced.

---

## Working conventions

- **Small, reviewable changes.** Single-engineer project; keep diffs readable six
  weeks from now.
- **Prefer boring dependencies.** Operational surface is the scarcest resource
  here (D-04). Adding a service needs a written reason — and "no server" is a
  settled decision, not a default.
- **Compartments are not multi-tenancy.** They are one engineer holding several
  counterparties' secrets. Do not add abstraction for hypothetical tenants.
- **Tests before gates.** Security behavior is specified by a failing test first,
  especially negative tests — the ones asserting something is *not* reachable,
  *not* present, or *not* inferred. The three test lists are
  `SECURITY-MODEL.md` §10, `ARCHITECTURE.md` §13, and `STORAGE.md` §11. They do
  not overlap; add to the one that owns the behavior.
- **Ask before resolving an open decision.**

---

## Layout

The Python implementation is organized by feature. Each feature keeps its
terminal interface beside its supporting logic; shared UI components live in
`ui/`. Board and project validation, drafts, and registration share
`configurations/`, while board-specific visual editing lives in `boards/`.
Core models and services do not depend on terminal widgets.

```
src/caiman/
  __init__.py     # package version
  __main__.py     # python -m caiman entry point
  cli/            # command parsing and dispatch; stable console entry point
  documents/      # document models, ingestion validation, and ingestion TUI
  boards/         # board gallery, guided form, and reviewed editing
  configurations/ # shared board/project models, drafts, storage service, and TUI
  dashboard/      # home screen, setup, workflow state, and dashboard actions
  repositories/   # Repo Manager service and TUI
  hooks/          # harness hook installation, callbacks, and TUI
  little_caiman/  # read-only sidecar: a session's managed-document use, from its transcript
  storage/        # immutable blobs, manifests, refs, and resolution
  ui/             # shared navigation, theme, mascot, and fullwidth headings
```

Tests live under `tests/`, public example datasets under `fixtures/`, and design
documentation under `docs/`. Session materialization remains planned; create
new feature packages when their implementation arrives. The default pod is a local preference; no board or project is a remembered default.

No `server/`. If semantic fallback is ever built (S-18) it arrives as one tool
behind one server, and not before search and selective reading of the source documents have
demonstrably failed on real queries.

---

## What not to do

`docs/ARCHITECTURE.md` §4 explains why for each; this is the operational form.

| Do not | Decision |
|---|---|
| Build session/worktree orchestration or HIL execution | S-01 |
| Add an MCP server, retrieval service, or any process between agent and documents | S-18 |
| Build a PDF → markdown converter, or add one as a dependency | S-08 |
| Split, rewrite, summarize, or generate maps for ingested documents; add AI to ingest | S-25 |
| Track compliance status — a feature declares `required` or `not-used`; `in-progress`, `implemented`, `verified` are ALM's job | S-14 |
| Build conflict detection between specifications, in any form | S-15, I-8 |
| Host or model licensed standards content (ISO, AUTOSAR, MISRA) | S-17 |
| Add checks that pretend Caiman is an enforcement boundary — a gate with no substance invites false confidence | S-19 |
| Reintroduce a repo-side `caiman.lock` — selection is per session | S-07 |
| Fuse Board and Project — the same hardware ships to more than one customer, and fusing puts customer identity where it cannot be compartmented | S-13 |
| Implement content-inspection–based classification — labels come from provenance, never from text | S-03 |
| Treat an annotation as an access control — annotations are labels | — |

S-14 is the likeliest place for scope to creep. The answer is already recorded.
