# Architecture

**Status:** Proposed. Describes the MVP as scoped by `DECISIONS.md`.
**Scope:** How Caiman turns supplied documents and declared structure into a
session workspace a coding agent can use.
**Related:** `VISION.md` (why), `STORAGE.md` (on-disk layout),
`SECURITY-MODEL.md` (threat model), `DECISIONS.md` (settled and open decisions),
`harness.md` (measured harness behavior).

---

## 1. Summary

Caiman assembles the context a coding agent needs for firmware work and writes it
into the session's worktree as ordinary files. There is no server, no index, and
no process between the agent and the content.

The system has four stages:

| Stage | Input | Output |
|---|---|---|
| **Ingest** | Converted markdown plus asserted provenance | Immutable document versions with labels, locators, and a navigation map |
| **Register** | Human declarations about hardware and programs | Immutable board versions and project versions |
| **Resolve** | A project name and version | A complete, digest-pinned set of documents and structure |
| **Materialize** | A pin set plus an agent name | A session workspace: a brief, a machine-readable structure file, and the documents |

The central architectural decision is that **the filesystem is the interface**.
The agent reads and greps files using tools it already has. Everything else in
this document follows from that choice or supports it.

---

## 2. Background and Problem

`VISION.md` §2 states the problem: three kinds of context are missing —
descriptive, structural, and normative — and each produces a different failure at
a different cost. This section covers only what that means for the architecture.

The three failures place different demands on the system:

| Failure | Demand |
|---|---|
| **Wrong fact** | A retrieval problem. Needs correct, version-scoped, citable text reachable at the moment of use |
| **Right fact, wrong board** | Not a retrieval problem — the retrieved text was accurate. Needs an explicit model of the board, handed to the agent before it starts work |
| **Correct and non-compliant** | Both: a model of what the program requires, plus governing specification text scoped to the release the program is frozen at |

The second and third are why this is not a document search tool with a hardware
corpus attached. Roughly half the design is structure, and no amount of retrieval
quality substitutes for it.

Two consequences run through every section below:

1. **Structure must be explicit and declared.** A board, a program, its features,
   and their relationships are modeled objects, not inferences over documents.
2. **Version scope is part of correctness, not metadata.** "Which board" and
   "which specification release" determine whether an accurate fact is also the
   right one.

## 3. Goals

| ID | Goal |
|---|---|
| G-1 | Give an agent an accurate picture of the board and program before its first turn |
| G-2 | Make every returned fact citable: document identity, document version, and locator |
| G-3 | Keep several board versions, silicon revisions, and specification releases simultaneously live and independently resolvable |
| G-4 | Scope a session to one project version, resolved once and stable for the session's life |
| G-5 | Make the choice of coding agent determine what material is available on disk |
| G-6 | Add no process between the agent and the content |
| G-7 | Integrate with any harness through a command-line interface, owning no part of session management |

## 4. Non-Goals

`VISION.md` §8 lists the product-level non-goals and the reasoning for each.
These are the architectural consequences — capabilities this system deliberately
does not have.

| Not provided | Consequence of |
|---|---|
| A retrieval service, MCP server, or semantic index | S-18. Deferred with a specific trigger; see §15.2 |
| A repository-side lockfile | S-07. Selection is per session |
| Any process between the agent and the documents | S-18. `sync` writes files and exits |
| Inference over documents — precedence, lineage, conflicts | S-15, I-8 |
| A PDF conversion stage | S-08. Ingest starts from markdown |
| Session or agent-process lifecycle | S-01. A harness owns it; the boundary is a CLI call |

---

## 5. Requirements and Constraints

### 5.1 Requirements

| ID | Requirement | Source |
|---|---|---|
| R-1 | Every chunk of ingested content carries a resolvable locator; content that cannot produce one is rejected at ingest | I-5 |
| R-2 | Labels are supplied at ingest from provenance and never derived from content | I-8, S-03 |
| R-3 | Content that is neither public nor compartmented is materialized nowhere | I-1 |
| R-4 | A project version resolves to a complete pin set, including everything its board version pins | S-07 |
| R-5 | A bare board or project name returns the list of versions and does not resolve | I-7 |
| R-6 | Resolution happens once per session and holds digests thereafter | I-4 |
| R-7 | An agent name absent from the agent map causes `sync` to fail and write nothing | I-1, S-19 |
| R-8 | The brief generator has no access to document content | I-6 |
| R-9 | A generated brief contains no customer identity, only the program codename | I-6 |
| R-10 | Lineage, precedence, and feature relationships are declared and rendered, never computed | I-8 |
| R-11 | The materialized document set is complete; partial materialization is an error | I-9 |
| R-12 | `grep` over the documents returns the whole truth — no symlinked directories, no silent omissions | I-9 |

### 5.2 Constraints

| Constraint | Consequence |
|---|---|
| Documents arrive already converted, by a tool Caiman does not control | Converter identity must be recorded; conversion quality is a risk to be traced, not prevented |
| A session harness writes plaintext copies of every file the agent reads, outside Caiman's control | Materialization is not revocable; see §11.4 and `harness.md` |
| The consumer is an agent with a bounded context window | The brief must be an orientation document, not a data dump |
| A 2,000-page reference manual is roughly 20 MB of markdown | Documents are split per chapter; no single file is readable whole |
| Version semantics differ per company | No parsing, ordering, or "latest" resolution anywhere in the system |

---

## 6. System Overview

### 6.1 Shape

```
  converted markdown + provenance     board definition      project definition
  (supplied by the user)              parts, roles, links   board + specs + features
        │                                    │                      │
        ▼                                    ▼                      ▼
  ┌───────────┐                        ┌──────────────────────────────┐
  │ 1 INGEST  │                        │ 2 REGISTER                   │
  │ label     │                        │ boards (hardware)            │
  │ locate    │                        │ projects (programs)          │
  │ map       │                        │ features                     │
  └─────┬─────┘                        └───────────────┬──────────────┘
        │                                              │
        └───────────────────┬──────────────────────────┘
                            ▼
                  ┌──────────────────┐
                  │ 3 STORE          │  immutable, content-addressed
                  │ documents        │  (layout: STORAGE.md)
                  │ boards, projects │
                  └────────┬─────────┘
                           ▼
                  ┌──────────────────┐
                  │ 4 RESOLVE        │  project version → complete pin set
                  └────────┬─────────┘
                           ▼
                  ┌──────────────────┐
                  │ 5 MATERIALIZE    │  filtered by agent profile
                  └────────┬─────────┘
                           ▼
              <worktree>/.caiman/
                project.md      brief, loaded into agent context
                project.json    resolved structure, machine-readable
                documents/      markdown and generated maps
                           │
                           ▼
              harness → coding agent (reads, greps, cites)
```

### 6.2 Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| **Ingest** | Splitting, labeling, locator validation, map generation | Conversion, classification decisions |
| **Register** | Board and project models, features, precedence, lineage | Inferring any of them |
| **Store** | Immutability, content addressing, compartment separation | Query, search, ranking |
| **Resolve** | Name→digest, transitive pin set, version listing | Choosing a version on the user's behalf |
| **Materialize** | Workspace assembly, agent filtering, linking, brief rendering | Session lifecycle, agent process |
| **Harness** (external) | Asking which project and agent, worktree creation, launching | Deciding what an agent may see |

### 6.3 Why there is no server

`sync` writes files; the agent uses its existing file tools. This follows S-04 to
its conclusion.

Exact-identifier lookup is a lexical problem. That was always the argument on the
descriptive side — a register identifier is unique and unambiguous — and stable
requirement IDs (S-06) extended it to the normative side. With both halves
greppable, a retrieval service would add a network round-trip to do worse than
`grep`, while its tool schemas occupied context on every turn, costing more than
the brief they were meant to supplement.

One behavior falls out of this for free and is worth naming, because it is the
highest-value normative capability in the system:

```
grep -rn "REQ-FLASH-0142" .caiman/documents/
  documents/oem-alpha/flash-spec@3.2/04-programming-session.md:212:REQ-FLASH-0142 …
  documents/oem-alpha/deviations-falcon@2026-06/deviations.md:88:Amends REQ-FLASH-0142 …
```

A single search returns the base requirement and the deviation that amends it.
"What governs here, and what did it override" is a property of the document set rather
than a feature to be built — **provided the deviation document names the
requirement IDs it amends.** That proviso is a real dependency on document
quality, and §10.2 covers what happens when it does not hold.

What a service would genuinely add is the concept-known, identifier-unknown
query. §6.4.3 describes the partial substitute, and §15.2 states the trigger for
revisiting.

### 6.4 Ingest

#### 6.4.1 Inputs and responsibilities

Input is markdown already converted from the source document, plus asserted
provenance: issuer, part or program, document type, document version, applicable
silicon revisions, access labels, source checksum, and the identity and version
of the converter.

Ingest owns five things:

1. **Splitting** into per-chapter files, preserving the document's own structure.
   Register tables, bitfield descriptions, and individual requirements must not be
   divided across file boundaries.
2. **Labeling** — `public`, or one or more compartments. An input, recorded on
   the artifact, never re-derived from content (R-2).
3. **Locator validation** — see below.
4. **Map generation** — see §6.4.3.
5. **Admission** — reject documents that fail validation rather than storing
   them with a warning.

Conversion is deliberately outside the system (D-01, retired). Two consequences
follow:

**Converter identity is provenance, not trivia.** It answers "which documents
went through which converter" when one is later found to have dropped content,
and "which artifacts predate the current converter" when a better one arrives.

**A compartmented document must be converted locally, and Caiman cannot enforce
it.** By the time markdown reaches ingest, the source has already been wherever
it was going to go. This is a documented user responsibility plus an ingest-time
lint, not a pipeline property. See `SECURITY-MODEL.md`.

#### 6.4.2 Locators

A citation is `(document identity, document version, locator)`. All three are
required (G-2, R-1).

| Document kind | Locator | Properties |
|---|---|---|
| Requirement-structured — customer specifications | Requirement ID, e.g. `REQ-DIAG-0412` | Unique, greppable, stable within a release line, and durable across re-conversion |
| Prose — reference manuals, datasheets, errata | Heading path, e.g. `§12.4.3 → LPSPI Control Register (CR)` | The floor. Survives conversion, where page boundaries frequently do not |
| Any | Page number | Recorded *alongside* a locator when the conversion supplied one, never instead of one |

Requirement IDs are durable in a way the alternatives are not: re-converting a
document with a better tool preserves every existing citation, because the anchor
is in the text rather than in the layout.

**Admission check.** A document whose content cannot produce a resolvable locator
is rejected. A document declared requirement-structured is rejected unless
requirement IDs appear matching its declared pattern. The reasoning is that
content which cannot be cited cannot be used for firmware work, so storing it
only creates a path to producing uncitable answers later.

#### 6.4.3 Generated maps

For each document, ingest emits a companion map as plain markdown: the heading
tree, the requirement-ID ranges the document contains, and an index of register
and identifier mentions. It is materialized alongside the document and is
greppable like anything else.

The map exists to serve the one query `grep` cannot: the engineer or agent knows
the concept but not the identifier. A map provides a route from concept to
identifier with no embedding model, vector store, or service. It costs one pass
at ingest and it is inspectable when it produces a bad answer.

**This is the weakest component in the design, and the evidence says so.**
Published measurements on code retrieval put semantic search meaningfully ahead
of `grep` alone for exactly this query class; S-18 records the numbers. The
argument that this document set sits on the favorable side of that trade-off is that
its identifiers are unique and unambiguous — `LPSPI1_CR`, `REQ-FLASH-0142` —
where a codebase full of repeated names like `validate` is not. That argument is
plausible and unverified. §15.2 states how it gets tested.

### 6.5 Register

Two models, deliberately separate.

#### 6.5.1 Board — hardware only

```
board:        zonal-ctrl-rear
version:      "2.1"
derives_from: "2.0"
relation:     "special variant — adds redundant CAN, drops display header"

parts:
  application-mcu   nxp/s32k344   silicon rev 1.1
  safety-companion  ti/tps65313   silicon rev A
  clock-generator   sil/si5332
  boot-flash        mic/mt25ql
  secure-element    …

links:
  safety-link   application-mcu (LPSPI1) <-> safety-companion (SPI)
  boot-flash    application-mcu (QSPI)   <-> boot-flash
  clock-tree    clock-generator -> application-mcu, safety-companion
```

A board version pins the vendor documentation for its parts. It contains no
reference to customers, programs, or specifications.

**Parts are identified by role.** `U4` is a fact about a schematic;
`safety-companion` is a fact about the design and is what a human or an agent can
reason with (S-12). A reference designator may ride along as optional
cross-reference metadata but is never the identity and never the display name.

**Peripheral instance names stay as the vendor writes them.** `LPSPI1` is what
you would search the reference manual for; renaming it would break the one thing
a link description is useful for.

#### 6.5.2 Project — the session unit

```
project:      falcon                      internal codename
customer:     <OEM>                       compartmented; never in the brief
compartments: oem-alpha, falcon
version:      "B-sample"
derives_from: "A-sample"
relation:     "spec set moved 3.0 -> 3.2; secure flashing added"

board:        zonal-ctrl-rear @ "2.1"
spec_set:     OEM release 3.2             frozen for this program

precedence:                               highest authority first
  1. program deviations — DEV-2026-014
  2. OEM spec set 3.2

features:
  secure-boot                     required
    governed_by:  OEM SEC-BOOT 2.4 REQ-SB-0100..0240
    realized_on:  application-mcu (HSM)
  secure-flashing                 required
    governed_by:  OEM FLASH 3.2, DEV-2026-014
    realized_on:  application-mcu, boot-flash
    related:      secure-boot "shared HSM key hierarchy on the application MCU"
  ota-update                      not-used
```

**A project is not a board.** The same hardware ships into more than one customer
program, with different specification sets, mandated features, and compartments.
Fusing them would require registering physically identical boards twice and would
place customer identity inside the hardware model, where it cannot be
compartmented (S-13).

#### 6.5.3 Features

A feature is the join between the normative and hardware sides. Without it, a
brief is two disconnected lists — parts and documents — and the agent must guess
how they relate. With it, "implement secure flashing" resolves to: these
specifications govern, these parts are involved, these other features share
state.

| Field | Meaning |
|---|---|
| `scope` | `required` or `not-used` on this program |
| `governed_by` | Specification document versions, with requirement IDs where available |
| `realized_on` | Part instances, by role |
| `related` | Other features, each with a free-text explanation of the relationship |

**`scope` is never status.** `in-progress`, `implemented`, and `verified` are
compliance tracking and belong to ALM (S-14). `not-used` earns its place: telling
an agent the program does not use OTA update prevents it from helpfully adding
it.

Features are declared per project version by a human, once. There is no
per-customer feature catalogue, because an OEM's programs do not reliably share a
feature set. They do not need re-deriving either: cutting a new project version
starts from its predecessor (§6.5.4), so features carry forward as a delta.

#### 6.5.4 Rules shared by both models

**Version labels are opaque** (I-7). `2.1`, `Rev B`, `EVT2-B`, `B-sample`, and
`P3-redundant-can` are equally valid and none is interpreted. No parsing, no
ordering, no "latest", no wildcards. On the normative side this is not a modeling
preference: a program is contractually frozen at a specification release, so
newer is not better, and resolving to latest would be a compliance failure.

**Relationships are declared, never inferred** (I-8, R-10). Lineage between
versions, precedence among specification documents, and relationships between
features are supplied by a human with a free-text explanation. Caiman renders
them and never computes over them. This is what keeps the system out of
interpreting contracts and detecting specification conflicts.

**Stored whole, authored by delta** (S-11). Authoring says "start from B-sample
and change these three things"; storage holds a complete, self-contained,
immutable snapshot. There is no inheritance resolution at read time, no version
that fails to resolve because its parent was mislinked, and the brief's change
summary is a comparison of two complete snapshots.

### 6.6 Store

Documents, board versions, and project versions are immutable and
content-addressed, in one store with one access model. A new document version is
a new artifact, never a mutation — which is what allows several silicon
revisions, board versions, and specification releases to be simultaneously live.
Git, whose model is that one version is HEAD and the rest is history, cannot
express that without abuse.

Two levels of hashing, and the distinction is load-bearing: a **blob** is one
file, hashed over its bytes; a **manifest** is one version of one object — its
file list plus all metadata — hashed over that. **Pins reference manifest
digests.** Changing a label produces a new manifest digest over unchanged blobs,
which is the signal the reclassification procedure in `SECURITY-MODEL.md`
depends on.

> The on-disk layout, manifest schemas, write ordering, garbage collection, and
> the full storage rationale are specified in `STORAGE.md`. The backend decision
> is `DECISIONS.md` D-02. This document does not repeat them.

### 6.7 Resolve

**A project version is the complete pin set** (R-4). Resolving
`falcon @ B-sample` yields:

- the board version, and every `(role, part, silicon revision, document version,
  digest)` tuple it pins
- every specification document version the program pins
- the declared precedence order
- the feature set

There is no lockfile in the firmware code repository (S-07). Selection is per
session: concurrent sessions may work two programs and two board versions from
one checkout, which a repository-level file cannot express. Worse, a repository
file naming one project while the session was launched against another is the
"right fact, wrong board" failure manufactured by the tool built to prevent it.

Four properties:

| Property | Detail |
|---|---|
| The name is a tag; the digest is the pin | "B-sample" moves — you add a deviation to it a month after cutting it. The digest is what the brief header records and what the session runs against (I-4) |
| A session pins once, at `sync` | Resolution does not re-run under a live session. Picking up newly added documentation requires a new session, which is the honest behavior: otherwise the agent's context and its brief silently diverge |
| A bare name never resolves | `falcon` with no version returns the version list (R-5) |
| Resolution is the access decision point | A caller without access to a compartment fails at the store and does not learn whether the project exists |

Traceability, if wanted later, is a commit trailer the harness writes from the
live session (`Caiman-Project: falcon@sha256:9f3c…`). It cannot drift, because it
is written at commit time from what was actually loaded. Not built for the MVP.

### 6.8 Materialize

```
caiman sync --project falcon --version B-sample \
            --agent claude-code --into .caiman/
```

Two inputs produce two independent scopings that compose:

- **The project** determines which compartments are in play.
- **The agent profile** determines whether compartmented material may be written
  at all.

```toml
# ~/.config/caiman/agents.toml
[agent.claude-code]
receives = "public"      # sends prompts to a third party

[agent.codex-local]
receives = "all"         # self-hosted model, no egress
```

The harness passes an agent **name**, not a policy decision. Caiman owns the map
for four reasons, given in full in `SECURITY-MODEL.md`: one place to answer "what
could this session see", an unknown name fails closed rather than receiving
whatever the harness asserted (R-7), policy survives harness changes, and the
brief can state the session mode truthfully because the same code computed it.

The workspace layout, link mechanism, and the three materialization constraints
are specified in `STORAGE.md` §7.3. In summary: documents are linked rather than
copied, files are read-only, no symlinked directories appear in the documents tree, and a
partial materialization fails rather than producing an incomplete document set (R-11,
R-12).

`project.json` — the resolved structure, fully expanded — is why there is no
`describe_feature` tool. The feature graph, precedence order, and pin set are a
file the agent reads directly.

### 6.9 The brief

An orientation document, not a data dump. Injected context is paid for on every
turn of every session, so the brief's job is narrow: make the agent know what it
is working on, and know that it must look things up rather than recall them.

```markdown
# Project: Falcon — B-sample
Board: zonal controller (rear) 2.1 · OEM spec set frozen at release 3.2
Generated by caiman from falcon@sha256:9f3c… — do not edit.
Derived from A-sample: "spec set moved 3.0 → 3.2; secure flashing added"

## Session mode: sealed
Local model. Full document set for this program is available.

## Parts
| Role              | Part         | Silicon rev |
|-------------------|--------------|-------------|
| application MCU   | nxp/s32k344  | 1.1         |
| safety companion  | ti/tps65313  | A           |
| clock generator   | sil/si5332   | —           |
| boot flash        | mic/mt25ql   | —           |
| secure element    | …/…          | —           |

## Links
- safety link — application MCU (LPSPI1) ↔ safety companion (SPI)
- boot flash  — application MCU (QSPI) ↔ boot flash
- clock tree  — clock generator → application MCU, safety companion

## Required OEM features
| Feature                      | Governed by      | Realized on                   |
|------------------------------|------------------|-------------------------------|
| secure boot                  | OEM SEC-BOOT 2.4 | application MCU (HSM)         |
| secure onboard communication | OEM SECOC 3.1    | application MCU, safety comp. |
| secure flashing              | OEM FLASH 3.2    | application MCU, boot flash   |
| diagnostics                  | OEM DIAG 3.2     | application MCU               |

- secure flashing ↔ secure boot ↔ secure onboard communication:
  "shared HSM key hierarchy on the application MCU"
- Not used on this program: OTA update, external authentication.

## Changed from A-sample
- OEM spec set 3.0 → 3.2
- added feature: secure flashing
- application MCU silicon rev 1.0 → 1.1

## Precedence (highest authority first)
1. Program deviations — DEV-2026-014
2. OEM spec set 3.2

## Where things are
Documents: .caiman/documents/ — grep them. Every document directory carries a `_map.md`
listing its heading tree and requirement-ID ranges. Paths include the document
version, so a grep hit is a citation.
Resolved structure: .caiman/project.json

## Rules
- The OEM spec set is frozen at release 3.2. Later revisions do not apply to
  this program, even where they are newer.
- Where a program deviation amends a requirement, the deviation governs. Look
  requirements up by ID; grep returns the base requirement and any deviation
  that amends it together.
- This is board 2.1. Facts specific to other board versions do not apply.
- The application MCU is silicon rev 1.1. Documentation for rev 2.x does not
  apply to this board.
- Never state a register offset, bitfield position, timing value, or
  requirement without a citation. If it cannot be cited, do not state it.
- Requirements and compliance status are not in Caiman. They live in the
  team's ALM tooling.
```

In a public-only session the mode block reads instead:

```markdown
## Session mode: open
OEM specifications for this program are not available in this session.
If a task requires them, stop and tell the engineer to start a sealed
session — do not infer, approximate, or work around a specification you
cannot read.
```

Three properties are load-bearing:

**The brief is open, always.** That a board contains a secure element and that a
program requires SecOC are structure; what the manual and specification *say* is
content. Only the second is confidential. The consequence is that the agent knows
the restricted parts and features exist, rather than being unaware of components
on its own board — a different and arguably worse failure than knowing the wrong
thing about them.

**The customer appears only by codename** (R-9). "We are building for OEM X" is
frequently itself under NDA. Programs have codenames precisely so people can
discuss them; the customer's legal identity stays in a compartmented manifest.

**The brief is metadata only** (R-8, I-6). The generator reads project and board
manifests and the document manifest — names, versions, labels, digests — and has
no access to document content. It cannot leak restricted material even if someone
later adds a summarization feature, because it cannot read any. Enforced by
construction and by test, not by review.

---

## 7. Data Model

```
Issuer ──< Part ──────< Document ──< DocumentVersion ──< Chunk *
   │                        │              │                │
 vendor              issued_by        public | compartments  labels
 or OEM              part | program   silicon revs          locator
                                      digest                (doc_id, digest)

Board ──< BoardVersion ──< PartInstance ──> Part
              │     │            │
     derives_from   │       silicon revision
     + relation     │       pinned DocumentVersions
                  Link ──> PartInstance, PartInstance

Project ──< ProjectVersion ──> BoardVersion
   │              │  │
codename          │  ├──> pinned spec DocumentVersions
customer          │  ├──> precedence order (declared)
compartments      │  └──< Feature
                  │            │
           derives_from   governed_by ──> DocumentVersion + requirement IDs
           + relation     realized_on ──> PartInstance
                          related     ──> Feature + relation
                          scope: required | not-used
```

`*` `Chunk` is under review as a stored entity — see §15.1.

### 7.1 Four independent version axes

These do not nest, and conflating them is the classic modeling error in this
domain.

| Axis | Example | Determined by |
|---|---|---|
| Document version | Reference manual rev 3 vs rev 4; OEM release 3.0 vs 3.2 | The issuer |
| Silicon revision | Mask revision of a part | The chip vendor |
| Board version | Which parts are populated, in which roles, wired how | Your hardware team |
| Project version | Which board, which specification release, which features, for which customer | Your program |

The relations between them: a document version *applies to* a set of silicon
revisions. A board version *pins* vendor document versions and names a silicon
revision per part instance. A project version *composes* a board version and
*pins* specification document versions.

Board *revision* and board *variant* are deliberately **not** separate axes. An
earlier draft split them, which forced the system to decide which one a given
label meant — precisely the company-specific convention it must not encode. One
axis with opaque labels and declared lineage expresses both.

### 7.2 Access labels

Adapted from Onyx's model (`onyx/access/models.py`, MIT-licensed):

- A frozen label **set** per labeled unit, with an `is_public` flag
- Prefixed label strings to prevent namespace collisions — `compartment:`,
  `project:`, `part:` rather than bare values
- One function generates labels for both write-time and filter-time (I-2)
- Empty set plus `is_public=False` as the fail-closed default (I-1, R-3)

A set rather than a scalar is what makes compartments work at no additional cost.
"How sensitive is this" is the wrong question when two customers' material is
equally sensitive and mutually invisible. "Whose secret is this" is the right
one, and set membership answers it where a sensitivity number cannot.

The mechanism transfers; the surrounding machinery does not. Onyx's
`external_permissions/` subsystem mirrors permissions from Slack, Drive, and
Confluence. Caiman has no upstream system to mirror — labels come from ingest
provenance, which is strictly simpler. Onyx's permission-sync code also lives
under `ee/` and is **not** MIT-licensed: read for design, do not copy.

---

## 8. End-to-End Flow

### 8.1 Adding a document

1. The engineer converts a PDF with an external tool.
2. `caiman ingest` validates locators, splits the markdown, generates the map,
   and writes an immutable document version carrying the asserted labels and
   converter identity.
3. A ref maps `<issuer>/<part>/<doc_type>/<version>` to the new manifest digest.

At this point nothing references the document. It becomes reachable when a board
or project version pins it.

### 8.2 Registering hardware and a program

1. `caiman board version new` writes a board version: parts in roles, silicon
   revisions, links, and the document digests each part pins.
2. `caiman project version new` writes a project version: a board digest,
   specification document digests, declared precedence, and the feature set.

Both are complete snapshots. Both are immutable.

### 8.3 Starting a session

1. The harness asks the engineer **which project and version**, using
   `caiman project list` and `caiman project versions <name>`.
2. The harness asks **which agent**, from the backends it can drive.
3. The harness creates the worktree.
4. The harness calls `caiman sync --project … --version … --agent … --into …`.
5. Caiman resolves the project version to a complete pin set (§6.7).
6. Caiman looks up the agent. **An unknown name fails here, and nothing is
   written** (R-7).
7. Caiman materializes the permitted subset, writes `project.json`, writes
   `_index.md` recording what was omitted and why, and renders `project.md`.
8. The harness launches the agent with `project.md` in context.

Steps 5–7 are the only ones Caiman owns. Steps 1–4 and 8 belong to the harness,
and the boundary is a command-line call (G-7).

### 8.4 During the session

The agent greps the documents, reads files, and cites by path plus locator. Caiman
is not running. Nothing resolves, and nothing changes underneath the session
(R-6).

---

## 9. Interfaces

### 9.1 Command-line surface

```
caiman ingest <markdown…> --provenance …        add a document version
caiman board   list | versions | show | version new
caiman project list | versions | show | version new
caiman sync --project P --version V --agent A --into DIR
caiman brief --project P --version V            render only the brief
```

`sync` is the integration point a harness calls. Two flags matter beyond the
obvious:

| Flag | Purpose |
|---|---|
| `--dry-run` | Prints what would be materialized without writing. This is how a human answers "what could this session see" |
| `--agent` | Required. There is no default; omitting it is an error, not an implicit `public` |

### 9.2 Workspace contract

The harness and the agent both depend on the workspace layout, so it is an
interface rather than an implementation detail. It is specified in `STORAGE.md`
§7.3. The properties other components rely on:

- `project.md` exists and is loadable as agent context
- `project.json` is machine-readable and contains the full resolved structure
- `documents/` paths encode issuer, part, document type, and version, so a `grep`
  hit is a citation
- `_index.md` states what was omitted and why

---

## 10. Failure Handling and Edge Cases

Storage-level failures — interrupted ingest, corruption, cross-volume
materialization — are covered in `STORAGE.md` §8. This section covers failures in
the layers above it.

### 10.1 Error conditions

| Condition | Behavior | Rationale |
|---|---|---|
| Agent name not in `agents.toml` | `sync` fails; nothing written | Fail closed. Defaulting to `public` would make an unconfigured backend silently work (R-7) |
| Bare project or board name | Return the version list; do not resolve | Resolving to "latest" against a frozen program is a compliance failure (R-5) |
| Document produces no resolvable locator | Reject at ingest | Uncitable content creates a path to uncitable answers (R-1) |
| Requirement-structured document lacks requirement IDs | Reject at ingest | The declared structure is part of the contract |
| Any pinned file cannot be materialized | `sync` fails and names the file | A document set missing one chapter is indistinguishable, to an agent, from a document that never had it (R-11) |
| Project pins a digest no longer in the store | `sync` fails and names the digest | Broken pin. See `STORAGE.md` §8.4 for why this should be impossible |
| Map generation fails for a document | Materialize without the map; warn | The map is a navigation aid, not correctness-bearing. Failing the whole sync would be disproportionate |

### 10.2 Edge cases worth naming

**A deviation document that does not cite requirement IDs.** The single-grep
correlation described in §6.3 depends on the deviation naming the requirement IDs
it amends. If a customer supplies deviations as prose without IDs, that behavior
silently does not happen: the agent finds the base requirement and never learns
it was amended. This is the most serious quality dependency in the design.
Mitigation is at ingest: a document declared as a deviation should be linted for
requirement-ID references, and the absence reported at registration time rather
than discovered during a session. D-12 tracks the structured alternative.

**A brief that disagrees with the workspace.** The brief records the project
digest it was generated from. Any regeneration of the workspace must regenerate
the brief. A brief claiming documents are available when they were not
materialized is the "right fact, wrong project" failure produced by the tool
itself.

**An agent that ignores the stop-and-ask rule.** In a public-only session the
brief instructs the agent to stop rather than work around an unavailable
specification. Nothing enforces this. The material is genuinely absent, so the
agent cannot cite what it does not have — but it can still guess, and a guess
about a customer requirement is exactly the failure mode the system exists to
prevent. This is a residual risk of the human-routing model (S-19), not a defect
to be fixed in the architecture.

**Two sessions, same worktree.** Not supported. `sync --into .caiman/` overwrites.
Concurrent sessions are expected to use separate worktrees, which is what the
harness provides.

---

## 11. Security Considerations

The threat model, the compartment scheme, and the reasoning behind human agent
selection are in `SECURITY-MODEL.md`. This section covers only what the
architecture contributes.

### 11.1 Differential materialization is the mechanism

Human agent selection is the decision; materializing a different document set per agent
profile is what makes it consequential. An agent cannot read a file that was
never written into its worktree.

Both error directions fail safe:

| Mistake | Consequence |
|---|---|
| Picked a public-only agent, work needs specifications | Material is absent. The agent reports it and the engineer restarts sealed. Loud and self-correcting |
| Picked a sealed agent, work was generic | A local model did work it did not need to. Slower; no disclosure |

### 11.2 Fail-closed points

There are three, and they are distinct failure paths tested separately:

1. Unknown agent name → `sync` writes nothing (R-7)
2. Unlabeled content → materialized nowhere, for any agent (R-3)
3. Content labeled for a compartment the project does not hold → not materialized

### 11.3 The brief is the one always-visible artifact

It is open by design, loaded into every session, and plausibly committed
somewhere. Its safety rests entirely on the generator having no access to
document content (R-8). This is a structural property — the generator reads
manifests only — rather than a filter applied to generated output, because a
filter can be bypassed by a later feature and a missing capability cannot.

### 11.4 What the architecture does not protect against

**Harness residue.** `harness.md` documents measured evidence that session
harnesses write plaintext copies of every file an agent reads into an append-only
transcript under `$HOME`, outside the store and outside every invariant here. The
architecture's guarantees end at the workspace boundary. In particular,
re-materialization removes the materialized copy but not the transcript, so
materializing a compartmented document is not reversible.

**Anything after the agent reads the file.** Caiman controls what is available,
not what is done with it. This is the stated scope of S-19: Caiman is not an
enforcement boundary.

---

## 12. Performance and Resource Considerations

| Operation | Cost driver | Notes |
|---|---|---|
| Ingest | Hashing and writing converted markdown | I/O bound, proportional to document size. Runs once per document version |
| Resolve | Reading one ref and tens of small JSON manifests | Negligible at the stated volume; this is why no index exists (D-10) |
| Materialize | Number of files linked, not their size | CoW clones and hardlinks copy no bytes. A few thousand files is a few thousand syscalls |
| Agent retrieval | `ripgrep` over the documents | No network hop, no embedding call, no ranking |

The context budget is the resource that constrains design most tightly. The brief
is paid for on every turn of every session, which is why it is an orientation
document rather than a structural dump, and why `project.json` exists as a
separate file the agent reads on demand.

---

## 13. Testing and Validation

Storage-level tests are in `STORAGE.md` §11. The security negative tests are in
`SECURITY-MODEL.md`. These cover the architecture's own behavior.

| ID | Test | Asserts |
|---|---|---|
| A-1 | Ingest a document whose content yields no locator | Rejected, not stored (R-1) |
| A-2 | Ingest a `requirement` document with no requirement IDs | Rejected (R-1) |
| A-3 | Resolve a project version; compare against its manifest | Pin set includes everything the board pins, transitively (R-4) |
| A-4 | Resolve a bare project name | Returns the version list; resolves nothing (R-5) |
| A-5 | `sync` with an agent absent from the map | Fails; workspace not created (R-7) |
| A-6 | `sync` with a `public` profile against a project with specifications | No compartmented document in the workspace; `_index.md` records the omission |
| A-7 | Generate a brief for a project with compartmented documents | No document body text appears in the output (R-8) |
| A-8 | Generate a brief; search for the customer string from the project manifest | Absent (R-9) |
| A-9 | Materialize, then grep for a requirement ID amended by a deviation | Both the base requirement and the deviation are returned (§6.3) |
| A-10 | Materialize two project versions differing only in silicon revision; ask the same question | Corpora differ correspondingly |
| A-11 | Walk a materialized document tree for symlinked directories | None (R-12) |
| A-12 | Regenerate a workspace after repointing a document ref | The previously pinned digest still materializes (R-6, I-4) |

A-9 is the test that covers the highest-value normative behavior, and A-12 covers
the reproducibility property the whole pinning model exists for.

---

## 14. Alternatives Considered

### 14.1 An MCP server exposing retrieval tools

The original design. A small number of fat tools — `find_register`,
`find_requirement`, `search_docs`, `describe_feature`, `compare_versions`,
`list_documents` — plus a session-startup trio for the harness.

Rejected (S-18). Six of the seven tools duplicated file operations the harness
already performs, and performs better: the agents in question have heavily
optimized file search. The startup trio is a CLI call. Only semantic search
needed a service, and it was already the first thing on the cut list. The tool
schemas would also have occupied context on every turn — plausibly more than the
brief itself.

Retained as a future option for one job only; §15.2 gives the trigger.

### 14.2 A lockfile in the code repository

Pin document versions in `caiman.lock`, committed next to the firmware.

Rejected (S-07). Selection is per session: concurrent sessions may target two
programs and two board versions from one checkout, which a repository-level file
cannot express. A repository file claiming one project while the session ran
against another manufactures the exact failure the system exists to prevent.
Pinning moved up into the project version artifact, which resolves transitively.

### 14.3 Fusing Board and Project

One entity covering hardware and program.

Rejected (S-13). The same hardware ships to more than one customer. Fusing would
require registering physically identical boards twice and would put customer
identity into the hardware model, where it cannot be compartmented.

### 14.4 Computing precedence and detecting conflicts

Analyze specifications to determine which supersedes which, and flag
contradictions.

Rejected (S-15, I-8). It is unreliable, and it places the system in the position
of interpreting contracts. Precedence is a short declared list; a deviation names
the requirement IDs it amends and `grep` surfaces both. Rendering a human's
declaration is defensible in a review; a computed inference is not.

### 14.5 A semantic index in the MVP

Build the fallback index alongside the documents from the start.

Deferred, not rejected (D-03). It is the first item on the cut list, and the
evidence on whether it is needed for *this* document set is genuinely mixed (§6.4.3).
Building it speculatively would add a service, an embedding model, and a
reindexing pipeline to serve a query class that may be rare here. §15.2 replaces
intuition with a trigger.

---

## 15. Risks and Open Questions

### 15.1 Open questions

**Does `Chunk` need to exist as a stored entity?** Chunks were introduced when
the design included a semantic index and were the unit that index was built over.
With S-18 there is no index, materialization is whole-document, and the agent
greps markdown. Locators are carried natively by the format: headings are
headings and requirement IDs appear in the text.

If chunks are removed, labels attach per document rather than per chunk, and the
admission check becomes document-level validation rather than a property of
stored chunk records. That simplifies this data model, the wording of I-1, and
the storage layout. The counter-argument is that chunk boundaries return if the
deferred semantic tool is built — but chunking is deterministic and cheap, so it
can be recomputed then.

This changes the wording of an invariant and therefore needs its own decision.
Tracked identically in `STORAGE.md` §13.1.

**Should the brief carry a session-scoped miss log path?** §15.2 depends on
recording queries where grep and the maps both fail. Whether the agent can be
asked to record them, or whether it must be inferred from harness transcripts, is
undecided.

**Four interface formats are named but not specified.** Each is described by its
purpose and referenced by other components, but no schema or example exists.
They are interfaces (§9.2), so leaving them implicit means two implementations
could disagree.

| Format | Referenced by | What is missing |
|---|---|---|
| `project.json` | §6.8, §9.2, the brief's *Where things are* block | Schema. It is the resolved project structure "fully expanded", which is not a specification |
| `_map.md` | §6.4.3, §9.2 | Layout of the heading tree, requirement-ID ranges, and identifier index. Its usefulness depends on being predictable enough to grep |
| `_index.md` | §6.8, `STORAGE.md` §7.3 | Wording of omission entries. An agent must be able to distinguish "this project has none" from "this session may not see them" reliably, which is a format question |
| Ingest provenance input | §6.4.1 | How a human asserts issuer, version, labels, and converter identity — CLI flags, a sidecar file, or an interactive prompt. This is the surface where a typo becomes a mislabeled document, so it bears on D-09 |

None of these blocks the design. All four should be specified before the code
that writes them, and `project.json` is the one to do first, because the agent
reads it directly and `describe_feature` was dropped on the assumption that it
would be sufficient.

### 15.2 The generated-maps bet, and how it gets settled

The concept-known, identifier-unknown query is served by generated maps rather
than by semantic search, and the published evidence does not clearly support that
choice in general (§6.4.3). The argument is domain-specific and untested.

The trigger for revisiting, stated so the decision is evidence-driven:

> Build the deferred semantic tool when concept-known, identifier-unknown queries
> defeat both `grep` and the generated maps, and this is observed more than
> occasionally in real use. Record the misses; do not decide from intuition.

`ROADMAP.md` carries the miss log as a phase-3 deliverable for this reason. If
the trigger fires, `ByteAsk-Embedded-MCP` (MIT) has a pluggable backend seam and
should be evaluated before writing a server.

### 15.3 Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A deviation document without requirement IDs (§10.2) | The correlation behavior silently does not occur; the agent never learns a requirement was amended | Lint at ingest and report at registration, not during a session. D-12 tracks a structured alternative |
| Hand-declared features drift from the program | The brief asserts something false, with authority | Author-by-delta means a new project version starts from its predecessor (S-11); the brief is regenerated per session and never hand-edited |
| A converter silently drops content | Wrong facts that look right, with valid citations | Converter identity in provenance bounds the blast radius; locator and requirement-ID admission checks catch structural loss; spot-check a register table by hand on first use of any new converter |
| Maps prove inadequate and the miss log is not implemented | The trigger in §15.2 cannot fire; the decision reverts to intuition | Implement the miss log with the rest of phase 3 |
| Harness residue (§11.4) | Materialization is not reversible | Out of scope here. Tracked in `harness.md`; the policy question belongs to `SECURITY-MODEL.md` |
| Context budget growth in the brief | Every added line is paid on every turn of every session | Keep detail in `project.json` and the documents; treat brief size as a reviewed budget, not an incidental outcome |
