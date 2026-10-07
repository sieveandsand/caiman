# CLAUDE.md — Caiman

Instructions for AI agents working in this repository.

**This file owns the invariants.** Everything else is a pointer.

| Before you | Read |
|---|---|
| Make any non-trivial change | This file, then `docs/ARCHITECTURE.md` |
| Touch `storage/`, `documents/`, `configurations/`, `pods/`, `repositories/`, or `sessions/` | `docs/STORAGE.md` |
| Touch container integration or a workspace adapter | `docs/CONTAINERS.md` (planned, S-39) |
| Resolve something that looks undecided | `docs/DECISIONS.md`. Do not silently resolve an open decision in code |

---

## What Caiman is

Caiman supplies three kinds of context coding agents lack in firmware work:
**descriptive** (what the hardware does), **structural** (what this design is),
and **normative** (what this program must do). `docs/ARCHITECTURE.md` §1 has the
failure each one prevents. The normative layer is the unserved problem; the
first two are substrate to build competently rather than inventively.

Three framing facts constrain most changes:

- **Caiman is a layer, not a platform.** `caiman session load` writes files into
  a worktree and gets out of the way. Session orchestration and
  hardware-in-the-loop execution are permanently somebody else's job (S-01).
- **The filesystem is the interface.** No server, no index, no process between
  the agent and the documents (S-18).
- **A Board is hardware; a Project is a program**: one or more board versions
  plus a program document set in one owning pod. Collections group documents;
  existing feature declarations are kept as compatibility data (S-13, S-14, S-34, S-36).

---

## Hard invariants

A change that violates one of these is a bug even if every test passes.

### I-1. One owning pod; no application authorization layer

A pod is a local folder, optionally its own Git repository. The Git host owns
remote access; the local filesystem owns local access. `public` is the
permanent default pod, always available, never replaceable or removable.
References may target only the owning pod or `public`; public artifacts
reference only public. This applies to transitive dependencies too. Do not
reintroduce document access labels, session membership lists, or public-only
board or collection rules.

### I-2. Stable routes and immutable identities

Each artifact lives in one pod. Board and project pins carry a stable pod ID
and an immutable manifest digest. Document references carry a stable pod ID,
document ID, and fixed blob digest, and resolve current metadata. Folder or
display-name changes must not retarget references. Old snapshots keep their
original bytes and hashes; legacy adapters work in memory. Project collection
references keep stable pod and collection IDs plus the snapshot digest from save
time: normal reads follow current membership, historical reads use the
recorded snapshot (S-14). Missing dependencies are reported, never silently
substituted or copied.

### I-3. Sharing is explicit and per pod

Saving locally never commits or pushes. A pod's Git repository contains only
that pod's data. Sync never force-pushes and preserves local work on failure.
Do not copy dependencies into a repository to make them reachable. Keep
installed content out of firmware repositories and preserve their guards. Never
commit customer documents or vendor content without redistribution rights to
this source repository; licensed examples keep their provenance and notices.

### I-4. Pin digests, not tags

Board and project versions resolve to immutable manifest digests. Version labels
are mutable and resolve at pin time, not at consumption time. Document
references pin a stable document ID and fixed blob digest. All editable document
metadata lives in complete immutable manifests; every approved edit publishes a
new current manifest. Old boards show current document metadata with their
original bodies. Exact manifest reads keep history. Document metadata never
restricts attachment to a board or part. Missing or changed bodies are errors.
Project collection references follow current membership (S-14), so a project's
effective document set may change without rewriting its snapshot.

### I-5. Never guess a hardware or requirement fact

Every returned fact carries `(document identity, document version, locator)`.
All three are required.

Use a locator the source actually has: requirement ID, heading path, page,
sheet/cell, line range, or another precise location. Never invent one.

Ingest accepts any readable file byte-for-byte, including binary, empty, and
non-UTF-8 files. No extension, heading, front-matter, or requirement-ID check
may block registration. Documents have no `structure` or `requirements`
metadata. Acceptance does not certify readability, searchability, conversion
fidelity, or technical correctness.

Registration stores one input file as one blob (S-25). The user chooses the
destination pod. No splitting, chunks, generated maps, summaries, or AI calls
belong in ingest. Original-source and converter information are optional (S-26).

### I-6. The brief is metadata only

The brief exists for every project because existence is structure and detail is
content. That holds only if the generator **cannot see document content**. It
reads manifests: names, versions, roles, part numbers, document paths, digests.

Never give the brief generator access to document text, not even for a helpful
summary. The brief names the program by **codename only**; customer identity
stays in the project manifest.

### I-7. Version labels are opaque

Never parse a board or project version string. Never infer that `2.1` relates to
`2.0`, never order them, never compute "latest", never implement wildcard
matching. Version semantics vary per company; encoding one convention breaks
every other.

On the normative side this is not a modelling preference: a program is
contractually frozen at a specification release, so "newer" is not "better",
and silently resolving to latest is a compliance failure.

Corollary: a bare board or project name never resolves to a version. It returns
the list.

### I-8. Declared, never inferred

Version lineage, precedence among specifications, and relationships between
features are supplied by a human with a free-text explanation. Caiman renders
them; it never computes them.

Do not write code that infers a relationship: not version ordering, not "this
spec looks like it supersedes that one", and above all not conflict detection
between specifications. If a deviation amends a requirement, a human says so by
naming the requirement IDs, and `grep` surfaces both together.

The destination pod is chosen at registration, never inferred from content.

### I-9. The document set must be complete

Install every pinned document. Text files must stay searchable with `grep`;
binary formats need suitable readers and are never silently omitted.

- **Never symlink a directory into the documents tree.** Ripgrep does not follow
  symlinks without `-L`, and `grep -r` does not follow symlinked directories.
  The agent would search, get results, and have no sign that part of the set was
  skipped. Silent incompleteness is the worst failure this system can have.
- **Blobs and installed documents are read-only** (`0444`). Installed documents
  are copies today. If hardlinks or a blob cache are ever added, key the cache
  by pod: a hardlink shares its inode, so an in-place edit or mode change
  reaches every link.
- **A partial install is an error, not a warning.** If any pinned document
  cannot be written, the load fails, names it, and keeps the previous context.

### I-10. Hooks observe; they never block, and they log identities only

Caiman registers a harness start hook to configure each session, and little
caiman reads transcripts to show which managed documents were used. Three rules,
none negotiable:

**Never deny a tool call.** `PreToolUse` can block; Caiman does not use it.
Caiman is not an enforcement boundary (S-19). Session folders separate
selections, not permissions. Actual isolation needs filesystem or process
boundaries.

**Never fail a session.** Hook failures, timeouts, and a missing Caiman
installation leave the session running. A broken hook that halts work gets
deleted within a week, which is worse than known gaps.

**Never record content.** Usage records hold paths, document names, versions,
and pods only, the same rule as the brief (I-6). A record containing an excerpt
of a specification is a copy of that specification in a file nobody thinks of
as one.

A fourth rule, about how it is described: **absence of a record is not proof a
document was not read.** Reads through scripts, other processes, and anything
outside the harness are invisible. Say so wherever usage is shown.

---

## Working conventions

- **Small, reviewable changes.** Single-engineer project; keep diffs readable
  six weeks from now.
- **Support truecolor, 256-color, and 16-color terminals.** Selection, keyboard
  focus, and status indicators must remain distinguishable after color
  reduction. Do not rely only on subtle background differences: `#102210` and
  `#000000` both map to black in 16/256 colors. Use a visible border, marker, or
  text cue, and check changed UI states in all three color modes, including
  selection retained after focus moves to action controls.
- **Review only changed drafts.** Every edit page disables (greys out)
  `Review changes` while the effective draft equals the original. Recompute
  after field edits, picker results, and nested additions or removals; reverting
  all edits disables it again. Retained drafts from raw editing or validation
  retries must reflect their changes immediately. Invalid changed input still
  reaches review validation. Include externally stored context (such as the
  owning pod) in both sides of the comparison; populating that context is not
  an edit. Exercise the real editor entry path with stored records, not only
  standalone forms. Creation flows remain able to review a new record.
- **Prefer boring dependencies.** Operational surface is the scarcest resource
  (D-04). Adding a service needs a written reason, and "no server" is a settled
  decision, not a default.
- **Pods are not multi-tenancy.** They are one engineer holding several
  counterparties' material. Do not add abstraction for hypothetical tenants.
- **Tests before gates.** Specify security behavior with a failing test first,
  especially negative tests: something is *not* reachable, *not* present, or
  *not* inferred. `docs/ARCHITECTURE.md` §10 maps invariants to test files.
- **Keep docs current, not historical.** Docs describe the code as it is. When
  code and a doc disagree, fix the doc. Do not record change history in docs;
  Git has it.
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
  documents/      # document models, ingestion, metadata editing and history, collections
  boards/         # board gallery, guided form, and reviewed editing
  configurations/ # shared board/project models, drafts, storage service, and TUI
  dashboard/      # home screen, setup, workflow state, and dashboard actions
  pods/           # pod discovery, identity, reference routes, removal checks
  repositories/   # per-pod Git transport and the Pods TUI
  hooks/          # harness hook and skill installation, the start callback, and TUI
  sessions/       # per-session context folders: registration, resolution, installation
  little_caiman/  # read-only sidecar: a session's managed-document use, from its transcript
  storage/        # immutable blobs, manifests, refs, locking, and journaled publication
  ui/             # shared navigation, theme, mascot, and fullwidth headings
```

Tests live under `tests/`, public example datasets under `fixtures/`, and design
documentation under `docs/`. Host agents load context through the start hook
and `caiman session` commands (S-40). The container workflow (S-39,
`docs/CONTAINERS.md`) is planned; create new feature packages when its
implementation arrives. No board or project is a remembered default.

No `server/`. If semantic fallback is ever built (S-18) it arrives as one tool
behind one server, and not before search and selective reading of the source
documents have demonstrably failed on real queries.

---

## What not to do

`docs/ARCHITECTURE.md` §2 and `docs/DECISIONS.md` explain why; this is the
operational form.

| Do not | Decision |
|---|---|
| Build session or worktree orchestration, or HIL execution | S-01 |
| Add an MCP server, retrieval service, or any process between agent and documents | S-18 |
| Build a PDF → Markdown converter, or add one as a dependency | S-08 |
| Split, rewrite, summarize, or generate maps for ingested documents; add AI to ingest | S-25 |
| Track compliance status. Preserved feature declarations use `required` or `not-used`, never `in-progress`, `implemented`, or `verified` | S-14 |
| Build conflict detection between specifications, in any form | S-15, I-8 |
| Host or model licensed standards content (ISO, AUTOSAR, MISRA) | S-17 |
| Add checks that pretend Caiman is an enforcement boundary; a gate with no substance invites false confidence | S-19 |
| Reintroduce a repo-side `caiman.lock`; selection is per session | S-07 |
| Fuse Board and Project; the same hardware ships to more than one customer, and fusing puts customer identity in a shared artifact | S-13 |
| Choose a pod, or any access decision, from document content | I-8 |

S-14 is the likeliest place for scope to creep. The answer is already recorded.
