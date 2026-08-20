# Roadmap

Target: a minimum working version in roughly six weeks, single-engineer scope.

The phasing rule: **if the work stops at any phase boundary, what exists is
coherent and correct.** Never end up with three half-built layers and a security
model that has never been tested end to end.

Two decisions shrank this roadmap considerably and are worth keeping in view.
Conversion left scope (S-08), removing the parser bake-off. The server left scope
(S-18), removing the entire serve layer, the semantic index, and the MCP tool
surface. What remains is smaller than what the earlier drafts described, and
almost all of it is testable.

---

## Phase 0 — Answer the expensive question (day 1)

Read the actual agreement language, for the customer specifically. Chip vendor
documentation is treated as public (S-16), so the question is narrower than it
was: what does the OEM agreement permit regarding processing by third-party
models, and does a zero-retention arrangement satisfy it?

Note what does **not** collapse whatever the answer: compartmentation. One
customer's specifications must not reach another customer's session regardless of
any model-provider agreement — that is an internal correctness property, not a
routing one.

One hour, potentially large payoff. Do it before writing code.

---

## Phase 1 — Documents in, labeled, citable (weeks 1–2)

Deliverables:

- Ingest of converted markdown plus asserted provenance, including converter
  identity and version
- Labels assigned at ingest — `public`, or one or more compartments — and carried
  onto every chunk
- Access-label model: frozen label set, prefixed strings, one generator for
  write-time and filter-time (I-2)
- Fail-closed default proven by test, with the two failure paths tested
  separately (I-1)
- Chunking that does not split register tables, bitfield descriptions, or
  individual requirements
- Locators: requirement IDs for requirement-structured documents, heading paths
  as the floor, page numbers alongside when available
- Admission check: no resolvable locator means the document is rejected, not
  warned about
- Generated per-document maps — heading tree, requirement-ID ranges, identifier
  index — as plain markdown
- Citation rendering: `(document, version, locator)` on every returned fact

**Exit criterion:** an unlabeled chunk is unreachable, nothing from one
compartment is reachable from another, and an uncitable chunk cannot be ingested
— all enforced by tests rather than by inspection.

---

## Phase 2 — The project, and the brief (weeks 3–4)

The differentiated half. This is where "I'm working on program X" becomes real.

Deliverables:

- Board model: boards, versions with opaque labels, parts in named roles with
  per-instance silicon revisions, links between parts
- Project model: projects with codenames and compartments, versions composing a
  board version, pinned specification releases, and a declared precedence order
- Features: `governed_by` document versions and requirement IDs, `realized_on`
  part instances, `related` edges with free-text relations, scope of `required`
  or `not-used` — and never a status field (S-14)
- Declared lineage on both, and nothing inferred anywhere (I-8)
- Versions stored whole, authored by delta (`caiman project version new --from
  A-sample`)
- Resolution: `project @ version` yields the board version, every vendor document
  digest, every specification digest, the precedence order, and the feature set.
  No repo-side lockfile (S-07)
- Bare names return the version list rather than resolving
- Brief rendering: parts, links, features, precedence, changed-from-parent diff,
  the where-things-are block, and the rules block
- Brief generator has no access to chunk text and never emits customer identity,
  enforced by construction and by test (I-6)

**Exit criterion:** two project versions sharing one board version but different
customers each render a correct, accurate brief, and the diff section correctly
describes what changed between two project versions.

---

## Phase 3 — Sessions (weeks 5–6)

Where it becomes a tool you use rather than a model you admire.

Deliverables:

- `caiman sync --project P --version V --agent A --into DIR`
- The agent profile map in Caiman, with an unknown agent name failing closed
  (S-19, I-1)
- Differential materialization: the project determines which compartments are in
  play, the agent profile determines whether compartmented material is written
  at all
- Session mode stated in the brief, including the stop-and-ask rule for
  public-only sessions
- Workspace layout: `project.md`, `project.json`, `corpus/` with maps alongside
  documents
- Content-addressed blob cache keyed by compartment; clone/reflink/hardlink by
  platform; the three rules in S-20 and I-9
- `--dry-run`, which is how a human answers "what could this session see"
- Reclassification and compartment-correction path: re-materialization, cache
  eviction, brief regeneration
- Sync audit log: project, version, agent, profile, compartments, digests written
- A retrieval miss log. S-18 defers the semantic tool on a specific trigger —
  concept-known, identifier-unknown queries that defeat both grep and the
  generated maps — and that trigger is only usable if the misses are recorded.
  Cheap to add now, impossible to reconstruct later
- The manual injection path documented: `@.caiman/project.md`
- Shakedown against the success criteria in `VISION.md` on a real project

**Exit criterion:** two sessions, on two projects sharing one board version but
different customers, each start with a correct brief and correct corpus, and
neither can reach the other's specifications. A session started with a
frontier-agent profile contains no specification on disk.

---

## After the MVP

**Artifact store backend swap (D-02).** The filesystem store carries phases 1–3.
Swapping in a real content-addressed store is contained if the resolve interface
stayed clean.

**MCP server for semantic fallback (S-18, D-03).** One tool, one job, built
against the miss log rather than a hunch. S-18 judges this more likely to be
needed than the filesystem-first framing suggests — published measurements on
code retrieval put semantic search meaningfully ahead of grep alone for exactly
the oblique-reference query. `ByteAsk-Embedded-MCP` (MIT) has a pluggable
backend seam and is worth evaluating before writing one.

**Structured deviation handling (D-12).** The MVP assumes deviations arrive as
one document naming the requirement IDs it amends. Real programs accumulate them
incrementally.

**Machine-readable specification companions.** Customer specifications ship with
ARXML, DBC, ODX/PDX, Fibex, and CDD alongside the prose, and for some questions
those are worth more than the document — an agent that can query the ODX knows
every DID and DTC exactly, with no retrieval uncertainty at all. A different
pipeline: structured and queryable rather than chunked and searched. The artifact
model should not assume every document is markdown chunks.

**Admin / curation surface (D-09).** Registering boards and projects, cutting
versions, declaring features and precedence, uploading documents with provenance
and compartments. The place where a typo becomes a mislabeled document or a
cross-compartment leak, and the form a CLI serves worst.

**Harness integration (D-07).** A harness that asks which project *and which
agent*, then calls `sync`. Caiman does not build it; per-session agent selection
is a hard requirement on whichever is adopted.

**Cross-document reasoning** — does the clock tree satisfy the NVM's timing
requirement; does this diagnostic implementation satisfy both the customer's
specification and the safety companion's watchdog window. The most interesting
capability and the one most dependent on everything below it being right. The
project and feature models are the prerequisite that was missing before.

**Multi-user, teams, SSO.** No second user yet.

---

## Deliberately not doing

**Agent orchestration and hardware-in-the-loop execution.** Both are real, and
both are being built by platforms in this category (`VISION.md`, Adjacent work).
Earlier drafts described HIL scheduling as unbuilt; that is no longer accurate.
Caiman is a layer and stays one.

**PDF → markdown conversion** (S-08). The residual risk — a bad conversion, or a
compartmented document sent to a hosted converter — is handled by recording
converter identity in provenance and by an ingest-time lint.

**Requirements and compliance management.** Caiman cites a requirement; it does
not track whether you met it (S-14).

**Conflict detection between specifications** (S-15, I-8).

**Hosting licensed standards** — ISO, AUTOSAR, MISRA (S-17).

**Being an enforcement boundary** (S-19). Filesystem hardening exists as an
option in `SECURITY-MODEL.md`, not as the design.

---

## Cut order under time pressure

Cut from the bottom:

1. The blob cache and linking — copy instead. Wasteful, not wrong; the three
   rules in I-9 still apply to a copied corpus
2. Sync audit log — valuable, not load-bearing for a solo MVP
3. The brief's changed-from-parent diff — lineage is informational by design and
   the brief is correct without it
4. Generated maps — the corpus is still greppable by identifier without them;
   only concept-to-identifier navigation suffers

Never cut:

- Fail-closed labels, and the unknown-agent refusal
- Citations, and the ingest-time locator requirement behind them
- Differential materialization by agent profile
- The board and project models, the feature set, and the brief

The first two make an answer trustworthy. The third is the only thing standing
between a wrong agent choice and a silent disclosure. The fourth is what makes an
answer trustworthy *for this board and this program* — without it Caiman is a
faster way to produce a confident, well-cited answer about the wrong hardware or
against the wrong specification, which is worse than no tool because it survives
review.

---

## Principal risks

| Risk | Mitigation |
|---|---|
| A platform closes the normative gap first | Real, and not controllable. The hedge is scope: a layer that is small, files-on-disk, and harness-agnostic is adoptable where a platform is not, and its ideas are portable if the bet goes the other way |
| The descriptive and structural halves eat the schedule | They are substrate, not differentiator (D-04). If they consume more than their two weeks, that is the signal to re-examine buy-versus-build rather than to push through |
| A converter silently drops rows or requirements | Converter identity in provenance so the blast radius is knowable; locator and requirement-ID admission checks; spot-diff a register table and a requirement range by hand on first ingest with any new converter |
| Silent incompleteness in the corpus | I-9. No symlinked directories, partial materialization is an error, and the maps make coverage inspectable |
| A document ingested against the wrong compartment | The likeliest hand-entry mistake with the worst consequence; treated as a reclassification, and the admin surface exists partly to reduce it |
| The human routinely picks the wrong agent | Differential materialization makes it loud rather than silent, and the brief tells the agent to stop rather than improvise. If it still happens often, that is the trigger for the optional hardening |
| Hand-declared features rot as programs evolve | Author-by-delta means a new project version starts from its predecessor (S-11) |
| Definitions drift from reality | The brief is regenerated per session from the registry, never hand-edited; a stale brief is a correctness bug |
| Requirement IDs renumbered between releases | Pins are to document versions, so a renumber is a new version and a frozen program keeps the old one — handled, but worth verifying early on a real specification set |
| Scope creep into compliance tracking | S-14; the line is scope versus status |
| Scope creep into orchestration | S-01, and now a positioning decision as much as a scoping one |
| A company's version convention leaks into code | I-7 |
| Labels lost mid-pipeline | Fail-closed default plus property tests on label generation |
