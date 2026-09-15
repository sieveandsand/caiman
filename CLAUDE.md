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
and **normative** (what this program must do). `VISION.md` §2 has the failure
mode each one prevents; the normative layer is where the unserved problem is, and
the first two are substrate to build competently rather than inventively.

Three framing facts that constrain most changes:

- **Caiman is a layer, not a platform.** `sync` writes files into a worktree and
  gets out of the way. Session orchestration and hardware-in-the-loop execution
  are permanently somebody else's job (S-01).
- **The filesystem is the interface.** No server, no index, no process between
  the agent and the documents (S-18).
- **A Board is hardware; a Project is a program** — a board version plus a
  customer specification set, features, precedence, and compartments (S-13).

---

## Hard invariants

A change that violates one of these is a bug even if every test passes.

### I-1. Fail closed on labels

Content that is neither asserted **public** nor carries a **compartment** is
unreachable. The default `AccessLabel` is the empty set with `is_public=False`.
If either label is lost anywhere in ingest → store → materialize, the affected
content must become unreachable, not world-readable.

Two distinct failure paths, tested separately: no labels at all, and a
compartment dropped while other fields survived.

The same rule covers the session mode. `sync --mode` is required and has no
default: omitting it fails and materializes nothing. Never infer a mode, never
default to `open`, and do not reintroduce a policy file that maps agents to
modes — S-19 records why that was removed. If a convenience layer ever returns,
it may only narrow the mode, never widen it.

### I-2. One function generates both write-time and filter-time labels

The strings written into an access list and the strings used to decide what
materializes MUST come from the same prefixing code, over `is_public` and
compartments alike. If they diverge, the filter silently under- or over-matches
and nobody notices. Never hand-roll a label string at a call site.

### I-3. Compartmented documents never enter a repository that was not built for them

There is exactly one git repository a compartmented document may live in: **that
compartment's own private store repository** (S-22). Everywhere else it is a
commercial incident.

| Repository | Compartmented documents |
|---|---|
| `store/<compartment>/` — private, one per counterparty | **Yes.** This is what it is for |
| `store/public/` | No. Public documents only |
| The firmware code repository | **Never.** The blob cache, materialized documents, and `.caiman/` are gitignored *and* pre-commit-hook guarded |
| This repository | **Never.** Not even as a fixture |

Git history is permanent, so every one of these is one-way. An accidental
`git add .` that commits a customer's specification cannot be undone by deleting
the file — and once pushed, not by rewriting history either, because clones,
forks, and host caches retain it.

Three rules follow:

- Do not weaken either guard on the code repository, and do not add exceptions
  "just for testing".
- Do not commit fixture documents from a real vendor or a real customer. Use the
  synthetic fixtures in `fixtures/`, including the synthetic specification sets,
  which exist precisely so this never comes up (D-08).
- **Ingest does not push.** Writing to the local store and publishing it to a
  remote are separate acts with a label review between them, because a mislabel
  caught before push costs a `git reset` and one caught after does not
  (`STORAGE.md` §9.5).

`docs/` at the root of *this* repository is Caiman's own design documentation and
is committed normally. Materialized documents live elsewhere. Do not conflate
them.

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
Labels apply to the whole document and are supplied by a human. No splitting,
chunk entities, generated maps, summaries, or AI calls belong in ingest.
Original-source and converter information are optional (S-26). Missing provenance
never implies public access or local conversion; explicit labels remain required.

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

The same applies to compartments: membership is declared at ingest and at project
registration, never derived from content, filename, or directory.

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

The implementation is a Python package under `src/caiman/`: `cli.py`, `tui.py`,
`ingest.py`, `models.py`, and `store.py` for documents; `configuration.py`,
`config_store.py`, `config_files.py`, and `config_tui.py` for board/project
authoring; `onboarding.py` and `workflow.py` for initial setup, the home screen,
and local authoring selections; `dashboard_actions.py` for interactive edit,
file, and catalog actions; `navigation.py` for shared Vim-style form and
dashboard controls; `board_gallery.py`, `board_edit.py`, and `external_editor.py`
for board cards and reviewed Vim edits; `theme.py` for shared appearance. Tests live
under `tests/`.
Python and Textual are implementation choices for local authoring;
the shared core does not depend on terminal widgets. The conceptual component
layout below describes the full planned system, not existing directories.

```
caiman/
  cli/            # sync, brief, ingest, board, project — the command surface
  project/        # project model, versions, features, precedence, brief rendering
  board/          # board model, versions, part instances, links
  ingest/         # unchanged-file registration, heading validation, document labels
  tui/            # ingestion form and review; calls the shared registration logic
  store/          # blobs, manifests, refs, resolution — see docs/STORAGE.md
  materialize/    # workspace assembly, linking, agent-profile filtering
  fixtures/       # synthetic documents and synthetic spec sets ONLY
  docs/           # design documentation
```

No `server/`. If semantic fallback is ever built (S-18) it arrives as one tool
behind one server, and not before search and selective reading of the source documents have
demonstrably failed on real queries.

---

## What not to do

`VISION.md` §8 explains why for each; this is the operational form.

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
