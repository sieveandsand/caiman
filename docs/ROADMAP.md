# Roadmap

**Purpose:** Sequencing, exit criteria, and what gets cut under time pressure.
**Owns:** Phasing and schedule risk. Product non-goals are in `VISION.md` §8;
design risks are in `ARCHITECTURE.md` §15 and `STORAGE.md` §13.

Target: a working MVP in roughly six weeks, single-engineer scope.

**Implementation checkpoint (2026-09-15):** local document ingestion and
board/project configuration are implemented with TUIs, editable JSON drafts,
validation, immutable pins, and local version registration. The home screen
creates boards and projects without a default selection; ingestion reuses
existing configurations or offers creation (S-29). Phase 1 is not
complete: Git initialization, remote review/push/pull/clone, and multi-machine
validation remain. Phase 2 still needs automated adoption cascades, status/verify,
and briefs; session integration remains Phase 3. README.md and AUTHORING.md
describe the implemented commands.

**Phasing rule:** if work stops at any phase boundary, what exists is coherent
and correct. Never end up with three half-built layers and a security model that
has never been tested end to end.

Two decisions shrank this considerably. Conversion left scope (S-08), removing
the parser bake-off. The server left scope (S-18), removing the serve layer, the
semantic index, and the MCP tool surface.

---

## Phase 0 — Answer the expensive question (day 1)

Read the actual agreement language, for the customer specifically. Vendor
documentation is treated as public (S-16), so the questions are narrow — and
there are now two:

1. **Processing.** What does the agreement permit regarding third-party models,
   and does a zero-retention arrangement satisfy it?
2. **Storage.** Does it permit the material to sit in a private repository on a
   third party's infrastructure? S-22 puts the store on GitHub, and git history
   is permanent, so this is harder to walk back than a model choice.

The default is one remote for everything, so question 2 is one decision. A
customer whose agreement forbids it gets a per-compartment remote override — self
hosted, or none — and nothing else in the design changes.

**Compartmentation does not collapse whatever the answer.** One customer's
specifications must not reach another customer's session regardless of any
model-provider agreement. That is an internal correctness property, not a routing
one.

One hour, potentially large payoff. Do it before writing code.

---

## Phase 1 — Documents in, labeled, citable (weeks 1–2)

| Deliverable | Reference |
|---|---|
| **Ingestion TUI** — file selection, metadata form, optional provenance section, inline validation, review/back/cancel/submit; shared registration logic independent of terminal widgets | `ARCHITECTURE.md` §6.4.3, S-27 |
| Register one unchanged Markdown file plus human-supplied metadata; source and converter information optional, input filename automatic; no AI dependency | `ARCHITECTURE.md` §6.4, S-25 |
| Labels supplied by a human for the whole document — `public` or compartments — and carried through | I-1, S-16 |
| Access-label model: frozen set, prefixed strings, one generator for write and filter paths | I-2 |
| Fail-closed default, with the two failure paths tested separately | I-1, S-T1, S-T2 |
| Byte-preserving registration: one content blob per document; no splitting, rewriting, or generated artifacts | S-25, T-16 |
| Locators: requirement IDs where available, heading paths as the floor | I-5, S-06 |
| Admission: usable headings on every document; requirement-structured documents additionally need a declared pattern and matching IDs. Actionable rejection; no automatic repair | `ARCHITECTURE.md` §6.4.2, S-T11 |
| Registration workflow: select file, supply metadata, review identity/version/labels, register locally; board and project authoring are separate | `ARCHITECTURE.md` §6.4.3 |
| Content-addressed store: blobs, manifests, refs, write ordering | `STORAGE.md` §6, §7.1 |
| `caiman init` / `compartment add`: store directories, `git init` at the store root, remote wiring. `compartment add` is local only — no repository to create. `init` does **not** create the remote repository; visibility stays an explicit human act | `STORAGE.md` §7.5 |
| `caiman push` / `pull`: label review before publishing, private-remote verification, mode restoration (`0444` blobs, `0700` compartments) before any other step, ref-conflict handling | `STORAGE.md` §7.6 |
| `caiman clone`: join an existing store from a second machine | `STORAGE.md` §7.5 |

**Exit:** an unlabeled record is unreachable, nothing from one compartment is
reachable from another, and uncitable content cannot be ingested — all enforced
by tests rather than inspection. The TUI can register a document with no
original-source or converter information; cancellation leaves no version or ref
update. A second machine can clone the store and resolve
the same digests. A large manual registers as one blob and materializes
byte-for-byte unchanged; no split files or generated maps appear.

---

## Phase 2 — The project, and the brief (weeks 3–4)

The differentiated half. Where "I'm working on program X" becomes real.

| Deliverable | Reference |
|---|---|
| **Board and project authoring input** — implemented TUI plus JSON drafts, validation/review/register, private export, and new-version copying | S-28, `AUTHORING.md` |
| Board model: versions with opaque labels, parts in roles, per-instance silicon revisions, links | `ARCHITECTURE.md` §6.5.1 |
| Project model: codenames, compartments, board composition, pinned specification releases, declared precedence | `ARCHITECTURE.md` §6.5.2 |
| Features: `governed_by`, `realized_on`, `related`, scope of `required` or `not-used` — never status | S-14 |
| Declared lineage on both; nothing inferred anywhere | I-8 |
| Versions stored whole, authored by delta | S-11 |
| Resolution: `project @ version` yields the complete transitive pin set | S-07 |
| **`caiman project version new --adopt <doc>`** — the version cascade in one command. Without it the most common operation is the most painful, and stale pins are the predictable outcome | `ARCHITECTURE.md` §8.6 Gap D |
| **`caiman status` and `caiman verify`** — is this workspace current; is the store internally consistent | `ARCHITECTURE.md` §8.6 Gap E |
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
| `caiman sync --project P --version V --mode open\|sealed --into DIR` | `ARCHITECTURE.md` §9.1 |
| `--mode` required, no default, no policy file. Omitting it fails closed | S-19, I-1, S-T5 |
| `--agent-label` recorded in the materialization log as an unverified annotation | S-19 |
| Differential materialization by project compartments × declared mode | `SECURITY-MODEL.md` §5.2 |
| Session mode in the brief, including the stop-and-ask rule | `SECURITY-MODEL.md` §5.4 |
| Workspace layout: `project.md`, `project.json`, `documents/` with one unchanged `document.md` per document | `STORAGE.md` §7.3 |
| Blob cache keyed by compartment; clone/reflink/hardlink by platform | S-20, I-9 |
| `--dry-run`, the answer to "what could this session see" | `ARCHITECTURE.md` §9.1 |
| Reclassification path: re-materialization, cache eviction, brief regeneration | `SECURITY-MODEL.md` §8 |
| Materialization log: project, version, agent, profile, compartments, digests | `SECURITY-MODEL.md` §9.1 |
| `caiman session start`: confirm, warn on staleness, or inject project **and mode** choices | `ARCHITECTURE.md` §6.10.2 |
| `caiman session record` / `end`: access log, identities only, never blocking | `ARCHITECTURE.md` §6.10.3, I-10 |
| `caiman hooks install`: adapter config, printed and confirmed before writing | `ARCHITECTURE.md` §9.2 |
| **Verify subagent tool-call coverage before relying on the access log** | `ARCHITECTURE.md` §15.1 |
| **Retrieval miss log** | See below |
| Manual injection path documented: `@.caiman/project.md` | `DECISIONS.md` D-07 |

The **miss log** records queries where search and selective reading of source documents fail.
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
| **Artifact store backend swap** (D-02) | When history permanence becomes the binding constraint — compartment corrections frequent enough that irreversible pushes are a recurring incident, or a counterparty requiring demonstrable deletion. The original trigger (real authentication) was met by S-22 instead |
| **Git LFS for blobs** (`STORAGE.md` §13.1) | At the first push warning about repository size. Growth is monotonic |
| **MCP server for semantic fallback** (S-18, D-03) | When the miss log shows concept-known, identifier-unknown queries defeating source-document search and selective reading more than occasionally. Evaluate `ByteAsk-Embedded-MCP`'s pluggable backend before writing one |
| **Structured deviation handling** (D-12) | When deviations stop arriving as one document naming the requirement IDs it amends |
| **Machine-readable specification companions** | ARXML, DBC, ODX/PDX, Fibex, CDD. A different pipeline — structured and queryable rather than Markdown searched as text. The artifact model should not assume every document is markdown |
| **Native macOS app for authoring / curation** (S-27) | Future GUI, reusing the TUI's shared validation and registration operations; schedule and detailed editing flows to be designed |
| **Harness integration** (D-07) | Requires a harness with per-session agent selection. Caiman does not build it |
| **Cross-document reasoning** | Depends on everything below it being correct. The project and feature models are the prerequisite that was previously missing |
| **Multi-user, teams, SSO** | No second user yet |

---

## Cut Order Under Time Pressure

Cut from the bottom:

1. **Blob cache and linking** — copy instead. Wasteful, not wrong; the I-9 rules
   still apply to copied documents
2. **Access log** — the materialization log answers the question a customer
   actually asks; the access log is the finer, incomplete second layer. Cut it
   before cutting the first
3. **Materialization log** — valuable, not load-bearing for a solo MVP
4. **Change summary in the brief** — lineage is informational by design and the
   brief is correct without it

Splitting, generated maps, and AI processing at ingest have already been removed
by S-25; they are not deferred MVP deliverables.

The ingestion TUI is required MVP scope (S-27), not a later convenience.

Session-start hooks are **not** on this list. They are the difference between a
tool the engineer must remember to run and one that configures itself, which is
most of whether it gets used at all.

Never cut:

- Fail-closed labels, and the unknown-agent refusal
- Citations, and the ingest-time locator requirement behind them
- Differential materialization by declared mode
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
| Phase 0's storage question comes back negative for a key customer | That compartment needs a self-hosted remote before phase 1 ends | Per-compartment remotes make this a configuration change, not a redesign. Ask the question before the first push, not after |
| The miss log is skipped as non-essential | The S-18 trigger cannot fire; the decision reverts to intuition | It is a phase-3 deliverable, not an optional extra |
