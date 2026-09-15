# Roadmap

**Purpose:** Sequencing, exit criteria, and what gets cut under time pressure.
**Owns:** Phasing and schedule risk. Product non-goals are in `VISION.md` §8;
design risks are in `ARCHITECTURE.md` §15 and `STORAGE.md` §13.

Target: a working MVP in roughly six weeks, single-engineer scope.

**Phasing rule:** if work stops at any phase boundary, what exists is coherent
and correct. Never end up with three half-built layers and a security model that
has never been tested end to end.

Two decisions shrank this considerably. Conversion left scope (S-08), removing
the parser bake-off. The server left scope (S-18), removing the serve layer, the
semantic index, and the MCP tool surface.

---

## Phase 0 — Answer the expensive question (day 1)

Read the actual agreement language, for the customer specifically. Vendor
documentation is treated as public (S-16), so the question is narrow: what does
the OEM agreement permit regarding processing by third-party models, and does a
zero-retention arrangement satisfy it?

**Compartmentation does not collapse whatever the answer.** One customer's
specifications must not reach another customer's session regardless of any
model-provider agreement. That is an internal correctness property, not a routing
one.

One hour, potentially large payoff. Do it before writing code.

---

## Phase 1 — Documents in, labeled, citable (weeks 1–2)

| Deliverable | Reference |
|---|---|
| Ingest converted markdown plus asserted provenance, including converter identity and version | `ARCHITECTURE.md` §6.4 |
| Labels assigned at ingest — `public` or compartments — and carried through | I-1, S-16 |
| Access-label model: frozen set, prefixed strings, one generator for write and filter paths | I-2 |
| Fail-closed default, with the two failure paths tested separately | I-1, S-T1, S-T2 |
| Splitting that does not divide register tables, bitfield descriptions, or requirements | `ARCHITECTURE.md` §6.4.1 |
| Locators: requirement IDs where available, heading paths as the floor | I-5, S-06 |
| Admission check: no resolvable locator means rejection, not a warning | S-T11 |
| Generated per-document maps | `ARCHITECTURE.md` §6.4.3 |
| Content-addressed store: blobs, manifests, refs, write ordering | `STORAGE.md` §6, §7.1 |

**Exit:** an unlabeled record is unreachable, nothing from one compartment is
reachable from another, and uncitable content cannot be ingested — all enforced
by tests rather than inspection.

---

## Phase 2 — The project, and the brief (weeks 3–4)

The differentiated half. Where "I'm working on program X" becomes real.

| Deliverable | Reference |
|---|---|
| Board model: versions with opaque labels, parts in roles, per-instance silicon revisions, links | `ARCHITECTURE.md` §6.5.1 |
| Project model: codenames, compartments, board composition, pinned specification releases, declared precedence | `ARCHITECTURE.md` §6.5.2 |
| Features: `governed_by`, `realized_on`, `related`, scope of `required` or `not-used` — never status | S-14 |
| Declared lineage on both; nothing inferred anywhere | I-8 |
| Versions stored whole, authored by delta | S-11 |
| Resolution: `project @ version` yields the complete transitive pin set | S-07 |
| Bare names return the version list rather than resolving | I-7 |
| Brief rendering: parts, features, precedence, change summary, rules block | `ARCHITECTURE.md` §6.9 |
| Brief generator has no access to document content and never emits customer identity | I-6, S-T8, S-T9 |

**Exit:** two project versions sharing one board version but different customers
each render a correct brief, and the change summary correctly describes what
differs between two project versions.

---

## Phase 3 — Sessions (weeks 5–6)

Where it becomes a tool you use rather than a model you admire.

| Deliverable | Reference |
|---|---|
| `caiman sync --project P --version V --agent A --into DIR` | `ARCHITECTURE.md` §9.1 |
| Agent profile map in Caiman; unknown name fails closed | S-19, S-T5 |
| Differential materialization by project compartments × agent profile | `SECURITY-MODEL.md` §5.2 |
| Session mode in the brief, including the stop-and-ask rule | `SECURITY-MODEL.md` §5.4 |
| Workspace layout: `project.md`, `project.json`, `documents/` with maps | `STORAGE.md` §7.3 |
| Blob cache keyed by compartment; clone/reflink/hardlink by platform | S-20, I-9 |
| `--dry-run`, the answer to "what could this session see" | `ARCHITECTURE.md` §9.1 |
| Reclassification path: re-materialization, cache eviction, brief regeneration | `SECURITY-MODEL.md` §8 |
| Sync audit log: project, version, agent, profile, compartments, digests | `SECURITY-MODEL.md` §9 |
| **Retrieval miss log** | See below |
| Manual injection path documented: `@.caiman/project.md` | `DECISIONS.md` D-07 |

The **miss log** records queries where grep and the generated maps both fail.
S-18 defers the semantic tool on a specific trigger, and that trigger is only
usable if the misses are recorded. Cheap now, impossible to reconstruct later.

**Exit:** two sessions, on two projects sharing one board version but different
customers, each start with a correct brief and correct document set, and neither
can reach the other's specifications. A session started with a frontier-agent
profile contains no specification on disk.

Then validate against the seven success criteria in `VISION.md` §7 on a real
project.

---

## After the MVP

| Item | Trigger or condition |
|---|---|
| **Artifact store backend swap** (D-02) | When compartment separation needs real authentication rather than POSIX permissions — a second person, a second machine, or a store off hardware you control |
| **MCP server for semantic fallback** (S-18, D-03) | When the miss log shows concept-known, identifier-unknown queries defeating grep and maps more than occasionally. Evaluate `ByteAsk-Embedded-MCP`'s pluggable backend before writing one |
| **Structured deviation handling** (D-12) | When deviations stop arriving as one document naming the requirement IDs it amends |
| **Machine-readable specification companions** | ARXML, DBC, ODX/PDX, Fibex, CDD. A different pipeline — structured and queryable rather than split and searched. The artifact model should not assume every document is markdown |
| **Admin / curation surface** (D-09) | When the CLI stops serving document registration well — past a few dozen documents, or once feature and precedence declaration becomes routine |
| **Harness integration** (D-07) | Requires a harness with per-session agent selection. Caiman does not build it |
| **Cross-document reasoning** | Depends on everything below it being correct. The project and feature models are the prerequisite that was previously missing |
| **Multi-user, teams, SSO** | No second user yet |

---

## Cut Order Under Time Pressure

Cut from the bottom:

1. **Blob cache and linking** — copy instead. Wasteful, not wrong; the I-9 rules
   still apply to copied documents
2. **Sync audit log** — valuable, not load-bearing for a solo MVP
3. **Change summary in the brief** — lineage is informational by design and the
   brief is correct without it
4. **Generated maps** — documents stay greppable by identifier; only
   concept-to-identifier navigation suffers

Never cut:

- Fail-closed labels, and the unknown-agent refusal
- Citations, and the ingest-time locator requirement behind them
- Differential materialization by agent profile
- The board and project models, the feature set, and the brief

The first two make an answer trustworthy. The third is the only thing between a
wrong agent choice and a silent disclosure. The fourth makes an answer
trustworthy *for this board and this program* — without it Caiman is a faster way
to produce a confident, well-cited answer about the wrong hardware or against the
wrong specification, which is worse than no tool because it survives review.

---

## Schedule Risks

Design and operational risks live with their designs — `ARCHITECTURE.md` §15.3,
`STORAGE.md` §13.2, `SECURITY-MODEL.md` §7. These are risks to the plan.

| Risk | Impact on schedule | Response |
|---|---|---|
| The descriptive and structural halves consume more than their two weeks | Phase 2, the differentiated half, gets squeezed | They are substrate, not differentiator (D-04). Overrun is the signal to re-examine build-versus-buy, not to push through |
| A platform closes the normative gap first | The project's premise weakens mid-build | Not controllable. The hedge is scope: a small, files-on-disk, harness-agnostic layer is adoptable where a platform is not, and its ideas are portable |
| Phase 0 is skipped because building tiering is more interesting | Weeks spent on a distinction the agreement may not require | One hour, day one, before code |
| The sample project turns out to lack part diversity or version history | Phase 2 cannot be demonstrated | Confirm D-08 before phase 2 begins; the synthetic specification sets are writable in a day regardless |
| Requirement IDs turn out to be renumbered between releases | The citation model needs rework mid-phase | Verify early against a real specification set. The existing version-pinning model should handle it, but that is untested |
| The miss log is skipped as non-essential | The S-18 trigger cannot fire; the decision reverts to intuition | It is a phase-3 deliverable, not an optional extra |
