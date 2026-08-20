# CLAUDE.md — Caiman

Instructions for AI agents working in this repository.

Read this file, then `docs/VISION.md` and `docs/ARCHITECTURE.md` before making
non-trivial changes. `docs/DECISIONS.md` records what is settled, what is still
open, and what was retired — do not silently resolve an open decision in code.

---

## What Caiman is

Caiman supplies the three kinds of context coding agents lack in firmware work:

1. **Descriptive** — what the hardware does. Datasheets, reference manuals,
   errata. Failure mode: *wrong fact*. Fails on the bench in hours.
2. **Structural** — what this design is. Board, parts in roles, links, silicon
   revisions, board version. Failure mode: *right fact, wrong board*. Costs a
   review cycle; the work is thrown away rather than repaired.
3. **Normative** — what this program must do. Customer specifications, required
   features, program deviations, the frozen specification release. Failure mode:
   *correct and non-compliant*. Works on the bench, survives review, surfaces at
   the customer's acceptance test months later.

   *Normative* is used here in the standards sense — ISO and AUTOSAR documents
   mark binding requirement clauses **normative** and explanatory material
   **informative**. A datasheet states a fact about the world; a specification
   states an obligation imposed by a contract. Getting a fact wrong breaks the
   build; getting an obligation wrong produces working, non-conforming firmware.

The first two are necessary substrate and are increasingly well served by others
(`VISION.md`, Adjacent work) — build them competently, not inventively. **The
normative layer is where the unserved problem is.**

**Caiman is a layer, not a platform.** `sync` writes files into a worktree and
gets out of the way. The agent is whichever you already use; the harness is
whichever you already run. Session orchestration and hardware-in-the-loop test
execution are permanently somebody else's job (S-01).

Caiman does **not** convert PDFs (S-08), and there is **no server** in the MVP —
the filesystem is the interface (S-18).

Key entities: a **Board** is hardware. A **Project** is what a session is about —
a board version plus a customer specification set, a feature set, a precedence
order, and compartments. See `docs/ARCHITECTURE.md`.

---

## Hard invariants

A change that violates one of these is a bug even if every test passes.

### I-1. Fail closed on labels

A chunk, document, or artifact that is neither asserted **public** nor carries a
**compartment** is unreachable. The default `AccessLabel` is the empty set with
`is_public=False`. If either label is lost anywhere in the ingest → chunk →
materialize chain, the affected content must become unreachable, not
world-readable.

The two failure paths are distinct and are tested separately: a record with no
labels at all, and a record whose compartment was dropped while other fields
survived.

The same rule covers agent profiles. An agent name absent from
`~/.config/caiman/agents.toml` resolves to nothing — `sync` fails and
materializes no documents at all. Never default an unknown agent to `public`;
refuse.

### I-2. One function generates both write-time and filter-time labels

The strings written into a chunk's access list and the strings used to decide
what materializes MUST come from the same prefixing code, over `is_public` and
compartments alike. If they diverge, the filter silently under- or over-matches
and nobody notices. Never hand-roll a label string at a call site.

### I-3. Compartmented documents never enter git

The blob cache, the materialized corpus, and the session's `.caiman/` directory
are gitignored **and** guarded by a pre-commit hook. Git history is permanent; an
accidental `git add .` that commits a customer's specification is unrecoverable
and is a commercial event, not just an embarrassment.

Do not weaken either guard, do not add exceptions "just for testing", and do not
commit fixture documents that came from a real vendor or a real customer. Use the
synthetic fixtures in `fixtures/`, including the synthetic specification sets,
which exist precisely so this never comes up (D-08).

Note: `docs/` at the repo root is Caiman's *own* design documentation and is
committed normally. The corpus lives elsewhere. Do not conflate them.

### I-4. Pin digests, not tags

Board versions, project versions, and document references resolve to immutable
content digests. Tags are mutable — and a human-facing version name like `2.1` or
`B-sample` **is a tag**: you add a deviation to it a month after cutting it. Any
code path that resolves a name at consumption time rather than at pin time is a
reproducibility bug. A session resolves once, at sync, and holds the digest.

### I-5. Never guess a hardware or requirement fact

Every returned fact carries `(document identity, document version, locator)`.
All three are required. Locator by document kind:

- **Requirement-structured documents** (customer specs): the **requirement ID**.
- **Everything else**: a **heading path**, which is the floor.
- A page number rides alongside when the conversion supplied one, never instead
  of a locator.

Corollary at ingest: a chunk with no resolvable locator is rejected, not stored
without one. For a document declared requirement-structured, chunks lacking
requirement IDs are rejected.

### I-6. The brief is metadata only

The project brief is open — always, including for projects whose documentation is
entirely compartmented — because existence is structure and detail is content.
That guarantee only holds if the brief generator **cannot see document text**. It
reads the project and board artifacts and the document manifest: roles, part
numbers, silicon revisions, links, feature names, document identities, versions,
digests.

Never give the brief generator access to chunk content, not even to produce a
helpful summary. The brief names the program by **codename only**; customer
identity stays in the registry. There are property tests asserting that neither
document body text nor customer identity appears in a generated brief.

### I-7. Version labels are opaque

Never parse a board or project version string. Never infer that `2.1` relates to
`2.0`, never order them, never compute "latest", never implement wildcard
matching. Version semantics vary per company; encoding one convention breaks
every other.

On the normative side this is not a modelling preference: a program is
contractually frozen at a specification release, so "newer" is not "better" and
silently resolving to latest is a compliance failure, not a convenience.

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

### I-9. The corpus must be complete and greppable

Everything downstream depends on `grep` over the materialized corpus returning
the whole truth. So:

- **Never symlink a directory into the corpus.** Ripgrep does not follow symlinks
  without `-L`, and `grep -r` does not follow symlinked directories encountered
  during traversal. The agent would search, get results, and have no indication
  part of the corpus was skipped. Silent incompleteness is the worst failure this
  system can have — there is no error to notice.
- **Key the blob cache by compartment.** Hardlinks share an inode, so mode lives
  on the inode; linking a compartmented blob out of a shared cache leaves it
  reachable by the cache path.
- **Blobs and the corpus are read-only** (`0444`). An in-place edit propagates
  through every hardlink and poisons the cache for every session.
- **A partial materialization is an error, not a warning.** If any pinned
  document cannot be written, `sync` fails and says which.

---

## Working conventions

- **Small, reviewable changes.** Single-engineer project; keep diffs readable six
  weeks from now.
- **Prefer boring dependencies.** Operational surface is the scarcest resource
  here (D-04). Adding a service needs a written reason — and "no server" is a
  settled decision, not a default.
- **Do not add abstraction for hypothetical multi-tenancy.** Compartments are not
  multi-tenancy; they are one engineer holding several counterparties' secrets.
- **Tests before gates.** Security behavior is specified by a failing test first
  — especially negative tests.
- **Ask before resolving an open decision.**

### Negative tests are first-class

- an unlabeled chunk is materialized nowhere and returned to nobody
- a chunk that lost its compartment fails independently of one that lost all
  labels
- nothing from one compartment appears in another's materialized corpus
- syncing with a `public` agent profile materializes no compartmented document
- syncing with an unknown agent name materializes nothing at all
- a document carrying two compartments does not appear for a session holding one
- no document body text and no customer identity appear in a generated brief
- a chunk with no resolvable locator is not ingestible
- a bare project or board name does not resolve to a version

Write these before the mechanism they test.

---

## Layout

```
caiman/
  cli/            # sync, brief, ingest, board, project — the command surface
  project/        # project model, versions, features, precedence, brief rendering
  board/          # board model, versions, part instances, links
  ingest/         # chunking, locators, labels, generated maps
  store/          # artifact store client, manifest, resolution, blob cache
  materialize/    # workspace assembly, linking, agent-profile filtering
  fixtures/       # synthetic documents and synthetic spec sets ONLY
  docs/           # project design documentation (VISION, ARCHITECTURE, …)
```

No `server/`. If semantic fallback is ever built (S-18), it arrives as one tool
behind one server, and not before grep plus generated maps has demonstrably
failed on a real query.

---

## What not to do

- Do not build session/worktree orchestration or HIL test execution. Permanently
  out of scope (S-01). Others are competing there; Caiman is a layer.
- Do not add an MCP server, a retrieval service, or any process between the agent
  and the corpus (S-18).
- Do not build a PDF → markdown converter, or add one as a dependency (S-08).
- Do not track compliance status. A feature declares `required` or `not-used`;
  `in-progress`, `implemented`, and `verified` are ALM's job (S-14). This is the
  likeliest place for scope to creep and the answer is already recorded.
- Do not build conflict detection between specifications, in any form (S-15, I-8).
- Do not host or model licensed standards content — ISO, AUTOSAR, MISRA (S-17).
- Do not treat Caiman as an enforcement boundary. The human picks the agent;
  Caiman makes the choice consequential (S-19). Do not add checks that pretend
  otherwise — a gate with no substance invites false confidence.
- Do not reintroduce a repo-side `caiman.lock`. Selection is per session (S-07).
- Do not fuse Board and Project. The same hardware ships to more than one
  customer, and fusing puts customer identity into the hardware model where it
  cannot be compartmented (S-13).
- Do not implement content-inspection–based classification. Labels come from
  provenance, never from text.
- Do not treat an annotation as an access control. Annotations are labels.
