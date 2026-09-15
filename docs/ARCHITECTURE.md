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
| **Ingest** | One Markdown file plus human-supplied metadata | Immutable document version with unchanged content, document labels, and validated headings |
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
| G-8 | Configure a session at its start without the engineer remembering to run anything |
| G-9 | Record which managed documents a session actually read |

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
| R-1 | Every document has usable heading paths; requirement-structured documents also contain declared requirement IDs; invalid input is rejected unchanged | I-5 |
| R-2 | Labels are supplied at ingest from provenance and never derived from content | I-8, S-03 |
| R-3 | Content that is neither public nor compartmented is materialized nowhere | I-1 |
| R-4 | A project version resolves to a complete pin set, including everything its board version pins | S-07 |
| R-5 | A bare board or project name returns the list of versions and does not resolve | I-7 |
| R-6 | Resolution happens once per session and holds digests thereafter | I-4 |
| R-7 | `--mode` is required; omitting it causes `sync` to fail and write nothing | I-1, S-19 |
| R-8 | The brief generator has no access to document content | I-6 |
| R-9 | A generated brief contains no customer identity, only the program codename | I-6 |
| R-10 | Lineage, precedence, and feature relationships are declared and rendered, never computed | I-8 |
| R-11 | The materialized document set is complete; partial materialization is an error | I-9 |
| R-12 | `grep` over the documents returns the whole truth — no symlinked directories, no silent omissions | I-9 |
| R-13 | Hooks never deny a tool call and never fail a session | I-10, S-19 |
| R-14 | The access log records document identities, never document content | I-10, I-6 |
| R-15 | A session whose brief no longer matches its project version is told so at start | I-4 |
| R-16 | A repository with no Caiman configuration has its sessions unaffected | — |

### 5.2 Constraints

| Constraint | Consequence |
|---|---|
| Documents arrive already converted, by a tool Caiman does not control | Optional converter provenance can help trace conversion defects; unknown provenance is accepted (S-26) |
| A session harness writes plaintext copies of every file the agent reads, outside Caiman's control | Materialization is not revocable; see §11.4 and `harness.md` |
| The consumer is an agent with a bounded context window | The brief must be an orientation document, not a data dump |
| A 2,000-page reference manual is roughly 20 MB of markdown | Keep the file whole; agents search and read selected ranges rather than loading the entire manual |
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
  │ hash      │                        │ features                     │
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
                  │ 5 MATERIALIZE    │  filtered by declared mode
                  └────────┬─────────┘
                           ▼
              <worktree>/.caiman/
                project.md      brief, loaded into agent context
                project.json    resolved structure, machine-readable
                documents/      unchanged Markdown files
                           │
                           ▼
              harness → coding agent (reads, greps, cites)
                           │
                           ├── SessionStart  → caiman session start
                           ├── PostToolUse   → caiman session record
                           └── Stop / SubagentStop → caiman session end
                                       │
                           ~/.local/state/caiman/audit/<session>.jsonl
```

### 6.2 Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| **Ingest** | Metadata validation, heading validation, hashing, unchanged-file registration | Conversion, splitting, maps, AI processing, classification decisions |
| **Register** | Board and project models, features, precedence, lineage | Inferring any of them |
| **Store** | Immutability, content addressing, compartment separation | Query, search, ranking |
| **Resolve** | Name→digest, transitive pin set, version listing | Choosing a version on the user's behalf |
| **Materialize** | Workspace assembly, agent filtering, linking, brief rendering | Session lifecycle, agent process |
| **Session integration** | Start-time configuration and staleness check; access recording | Blocking, resolving, or reading the store |
| **Harness** (external) | Worktree creation, launching, publishing hook events | Deciding what an agent may see |

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
  documents/oem-alpha/flash-spec@3.2/document.md:212:REQ-FLASH-0142 …
  documents/oem-alpha/deviations-falcon@2026-06/document.md:88:Amends REQ-FLASH-0142 …
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

Input is **one UTF-8 Markdown file**, already prepared outside Caiman, plus
human-supplied metadata: issuer, part or program, document type and version,
applicable silicon revisions, and access labels. Original-source and converter
information are optional. The ingestion TUI collects these fields; §6.4.3
defines the form and `STORAGE.md` §6.4.1 defines their stored representation.

Ingest is registration, not document processing (S-25). It owns:

1. Validating required metadata and explicit whole-document access labels.
2. Validating usable headings and, for requirement-structured documents, the
   declared requirement-ID pattern (§6.4.2).
3. Computing a digest of the exact input bytes and registering one content blob
   and its immutable document manifest. No newline normalization or text edits.

There is no splitting, chunk model, generated outline or map, semantic tagging,
summary generation, or AI dependency. The same human-supplied access label set
covers the entire file. Caiman never derives labels from its content.

PDF conversion and any cleanup happen externally. Optional converter provenance
can help identify affected artifacts when a converter is found to drop content;
without it that history is unknown. Do not require the source PDF to ingest. Compartmented material
must be prepared with tools authorized for that material; ingest cannot undo an
earlier disclosure (`SECURITY-MODEL.md` §7.2).

#### 6.4.2 Usable headings and citations

Every document, including a requirement-structured specification, must have
usable headings. Admission is a deterministic Markdown-structure check:

- The first nonblank block must be a nonempty heading, so all content has a
  heading path. A document title can supply the initial path.
- Recognize Markdown headings through a parser, including ATX and Setext forms;
  heading-like text inside code blocks is not a heading.
- Each heading must have nonempty text and an unambiguous full ancestor path.
  Repeated names under different parent paths are allowed; duplicate full paths
  are rejected with source line numbers so the author can repair them externally.
- Heading levels may skip numbers; the ancestor is the preceding heading of a
  lower level. Caiman does not infer missing headings or semantic chapters.

Reject documents that fail these checks without registering a version or
changing the input. Report the relevant locations and reasons. A title-only
structure may pass mechanically but provide poor navigation: admission does not
certify useful granularity, conversion fidelity, or technical correctness.

A citation remains `(document identity, document version, locator)`:

| Document kind | Locator |
|---|---|
| Reference manuals, datasheets, errata, other prose | Heading path in the unchanged source |
| Requirement-structured specifications | Requirement ID, with headings still required for navigation |
| Any | Source page number when preserved, alongside rather than instead of the locator |

A document declared `requirement` must additionally supply a valid ID pattern
and contain matching IDs. This is syntactic validation, not extraction of a
requirements model or proof that every requirement survived conversion. No
line-range-only citation fallback is introduced: line numbers help retrieve
text, while headings and requirement IDs remain the citation locators (I-5).

#### 6.4.3 Registration and reading workflow

**Select file → supply metadata → review → register.** The engineer reviews the
document identity, version, applicability, and explicit access labels before
local registration in a terminal UI (TUI), launched by `caiman ingest [markdown]`.
The file argument is optional; without it the TUI asks for a file. On first
launch, `caiman` and `caiman ingest` guide setup of a board and project; both can
start with empty document lists (S-29). Subsequent ingestion reuses those
configurations. Push remains a separate act with its own label review.

The form has four steps:

1. **File.** Select one Markdown file. Show its basename and heading-validation
   results; do not ask for a second original-source filename.
2. **Document.** Pick an existing project or board part to populate declared
   metadata, or enter document identity manually. Offer creation of a new board
   or project and return to the retained ingestion form. Enter document type,
   version, and structure (`prose` or `requirement`). Project selection supplies
   the program and compartment context; board-part selection supplies issuer,
   part, and any declared silicon revision. Silicon revisions are optional when
   not applicable or unknown; display that absence honestly. Show a required
   ID-pattern field only for requirement-structured documents. Choose public
   access or named compartments explicitly, with no preselected access label.
3. **Optional provenance.** A skippable section for original-source checksum and
   page count, and converter name, version, and hosted/local information. Each
   may be left unknown. Never infer these from the filename or missing fields.
4. **Review and register.** Show entered metadata and labels, unknown optional
   fields, and the computed Markdown digest and size. Allow back/edit or cancel.
   Register only on explicit submit; cancellation creates no document version
   and does not repoint a ref. Report field errors inline and heading errors
   with source locations, retaining entered values for correction.

The TUI fills a manifest draft. Caiman supplies `original_filename` (the input
Markdown basename), content digest and size, schema and pipeline versions, and
ingestion timestamp. Source and converter fields are optional individually and
as groups; omitted values stay absent, not invented or encoded as safe defaults.
The input convention is that the Markdown retains the source basename; it is
not proof of source identity and no separate source filename is stored.

The TUI calls shared validation and registration logic rather than writing blobs
or manifests itself. A future native macOS app will use the same operations and
field rules (S-27). A noninteractive flag/sidecar format is not an MVP requirement;
without an interactive terminal, explain that the TUI requires one and write
nothing. Board/project creation uses the shared authoring workflow
([AUTHORING.md](AUTHORING.md), S-28, S-29). Selecting a configuration during
ingestion does not change its immutable document pins; adoption is an explicit
configuration edit.

The stored content is materialized as `document.md` under the versioned document
directory. Preserve the original input filename as metadata. Agents search for
identifiers, phrases, or existing headings and read bounded ranges around hits,
including relevant qualifications. A several-hundred-page manual stays one file;
its full contents need not enter the context window.

No `_map.md` or other navigation artifact is generated. Concept-known,
identifier-unknown queries remain an evaluation risk (§15.2). If the original
headings are poor, the engineer prepares a corrected file externally and
registers a new immutable version; Caiman does not repair it in place.

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

The store is kept off-machine in git: **one private repository holding the whole
store**, compartments as directories inside it (S-22). GitHub has no per-directory
read permission, and there is no second person to separate compartments from, so
a repository boundary per compartment would cost real setup work for no benefit
today. Per-compartment remote overrides exist for when that stops being true, and
for a counterparty whose agreement forbids third-party storage.

Git is transport and backup; the content-addressed layout remains the source of
truth for immutability. Do not use branches or tags to express document, board,
or project versions — that is the model S-02 rejected.

> The on-disk layout, manifest schemas, write ordering, the git remote, garbage
> collection, and the full storage rationale are specified in `STORAGE.md`. The
> backend decision is `DECISIONS.md` S-22 and D-02. This document does not repeat
> them.

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
            --mode sealed --into .caiman/
```

Two inputs produce two independent scopings that compose:

- **The project** determines which compartments are in play.
- **The mode** determines whether compartmented material is written at all.

| Mode | Materializes |
|---|---|
| `open` | Public documents only |
| `sealed` | Everything the project version pins |

**`--mode` is required and has no default** (R-7). Omitting it is an error, never
an implicit `open`. There is no agent map, no profile lookup, and no policy file:
the human states what this session gets, at the moment they know what model they
are running and what the work touches. `SECURITY-MODEL.md` §5.3 records why the
map that used to sit here was removed, and what that costs.

An optional `--agent-label` is carried into the materialization log as an
unverified annotation. It names the harness, not the model, and is not an input
to the decision.

The workspace layout, link mechanism, and the three materialization constraints
are specified in `STORAGE.md` §7.3. In summary: documents are linked rather than
copied, files are read-only, no symlinked directories appear in the documents
tree, and a partial materialization fails rather than producing an incomplete
document set (R-11, R-12).

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
Documents: .caiman/documents/ — each document directory contains one unchanged
`document.md`. Search identifiers or headings, then read the relevant line range
and surrounding qualifications. Paths identify the document and version; cite
the heading path or requirement ID as the locator. Do not read a whole manual
into context. There are no generated maps.
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

### 6.10 Session integration

Caiman runs inside the session as well as before it, through the harness's own
hook mechanism. Two jobs: configure the session at start, and record which
managed documents were read.

This does not reopen S-01. Caiman is not managing sessions; it is registering
callbacks with a harness it does not own, at extension points that harness
already publishes. `sync` is still the whole of what Caiman produces.

#### 6.10.1 Boundary and coupling

Hooks are **thin adapters over the CLI**. All logic lives in `caiman` commands;
the adapter translates the harness's event format into a command invocation and
its output back.

This matters because hook mechanisms are harness-specific. Claude Code publishes
`SessionStart`, `PreToolUse`, `PostToolUse`, `Stop`, and `SubagentStop`; other
harnesses have different shapes or none. Keeping logic in the CLI means
supporting a second harness is a new adapter, not a second implementation — and a
harness with no hooks degrades to the manual path (D-07) rather than breaking.

| Layer | Owns | Harness-specific |
|---|---|---|
| `caiman session start`, `caiman session record`, `caiman session end` | All behavior | No |
| Hook adapter | Event translation, stdin/stdout shape | Yes |

#### 6.10.2 Session start

On `SessionStart` the adapter calls `caiman session start` with the working
directory and the harness's session identifier. Four outcomes:

| State | Behavior |
|---|---|
| A valid `.caiman/project.md` exists and its digest still resolves | Confirm and inject the brief reference into context. Nothing to ask |
| A `.caiman/` exists but the brief's project digest no longer matches what that project version resolves to | **Inject a staleness warning naming both digests.** A brief that disagrees with the workspace is the "right fact, wrong project" failure produced by the tool itself |
| No `.caiman/` in this worktree | Inject the available projects and versions, and an instruction for the agent to ask the engineer **which project and which mode**, then run `caiman sync` |
| Caiman not configured on this machine | Inject nothing. A repository without Caiman must not have its sessions disrupted |

**The hook cannot prompt the engineer directly.** Hooks run non-interactively —
stdin carries the event payload, not a terminal. So the hook injects context and
the *agent* asks, which is the only path that works with the grain of the
harness. Selection is conversational rather than a startup dialog, and the
engineer answers both questions in their first message: which project, and
whether this session is `open` or `sealed`.

That the mode is asked rather than looked up is deliberate (S-19). The engineer
answering knows which model this session is running; a configuration file written
months ago does not.

A per-worktree `.caiman/session.toml` records the last selection — project,
version, and mode — so a resumed or repeated session in the same worktree does
not ask again. It is a record of what was chosen, not policy: changing mode means
re-running `sync`, which rewrites it.

#### 6.10.3 Access recording

On `PostToolUse`, the adapter calls `caiman session record` with the tool name
and its inputs. If a path falls inside the session's `documents/` tree, one line
is appended to the session's access log.

`PostToolUse` rather than `PreToolUse` because the question is what was read, not
what was attempted. `PreToolUse` is not used at all, which is deliberate — see
§6.10.5.

**Document identity comes from the path, not from the store.** The materialized
path already encodes issuer, part, document type, and version (§6.8), so the hook
derives identity with string parsing and never opens the store, never resolves,
and never reads a manifest. This is what keeps it cheap enough to run on every
tool call.

```jsonl
{"ts":"2026-09-14T11:02:19Z","session":"a3f9…","event":"read","tool":"Read",
 "path":"documents/oem-alpha/flash-spec@3.2/document.md",
 "document":"oem-alpha/flash-spec","version":"3.2","compartment":"oem-alpha"}
```

`Stop` and `SubagentStop` close the record with a summary: distinct documents
read, per compartment. `SubagentStop` matters because a subagent's reads are
still this session's reads; whether subagent tool calls raise `PostToolUse` in
every harness configuration is **unverified** and must be checked before the
access log is relied on (§15.1).

#### 6.10.4 What the access log is and is not

It is a **second layer** over the materialization log, not a replacement.

| | Materialization log | Access log |
|---|---|---|
| Answers | What the session *could* read | What the session *did* read |
| Produced by | `sync`, deterministically | Hooks, during the session |
| Complete? | Yes | **No** — see below |
| Depends on the agent cooperating? | No | Partly |

Three ways a read escapes the access log:

1. **`Bash` reads.** `PostToolUse` fires for `Bash`, but the payload is a command
   string. Extracting which files a `cat`, `rg`, or shell script read is
   heuristic at best and defeated by pipes and indirection. Log the command
   verbatim and mark the entry `unresolved` rather than pretending to parse it.
2. **Hooks not installed**, or installed for one harness and not another.
3. **Anything outside the harness.** An editor, another process, a second tool.

So: **absence of a record is not proof of non-access.** The access log is
evidence, not an accounting. Stated plainly wherever it is used, because the
opposite reading is the one that causes harm.

What it genuinely buys is in `SECURITY-MODEL.md` §9: it converts harness
transcript residue from an unbounded unknown into an enumerable list.

#### 6.10.5 Hooks observe; they never block

`PreToolUse` can deny a tool call. Caiman does not use it, and this is an
invariant (I-10), not a current limitation.

Blocking would make Caiman look like an enforcement boundary, which S-19 says it
is not. It would also add nothing: differential materialization already means a
document the session may not see is not on disk, so there is no read to deny.
A gate positioned where nothing can pass is the "shape of a gate with none of the
substance" the security model warns against.

Two further rules follow from the same reasoning:

**A hook failure never fails the session.** Logging is best-effort. A broken
audit hook that halts work would be traded away within a week, which is worse
than a log with gaps that is known to have gaps.

**The access log records identities, never content.** Paths, document names,
versions, compartments — the same metadata-only rule as the brief (I-6). An audit
record containing an excerpt of a specification would be a copy of the
specification in a file nobody thinks of as one.

---

## 7. Data Model

```
Issuer ──< Part ──────< Document ──< DocumentVersion ───> Blob
   │                        │              │               │
 vendor              issued_by        document labels    unchanged Markdown
 or OEM              part | program   silicon revs       headings and IDs
                                      manifest digest   content digest

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

A document version references exactly one content blob. Labels belong to the
document manifest; locators remain in the source text. No stored chunks (S-25).

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

- A frozen label **set** per document, with an `is_public` flag
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
2. The engineer supplies metadata and whole-document labels, reviews the
   registration summary, and runs `caiman ingest`. It validates usable headings
   and any declared requirement-ID pattern, hashes the exact input bytes, and
   registers one immutable document version without transforming the file.
3. A ref maps `<issuer>/<part>/<doc_type>/<version>` to the new manifest digest.
4. `caiman push` reviews labels, then publishes to that compartment's remote.
   Separate and deliberate: step 3 is reversible, step 4 is not
   (`STORAGE.md` §9.5).

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
4. The harness calls `caiman sync --project … --version … --mode … --into …`.
5. Caiman resolves the project version to a complete pin set (§6.7).
6. Caiman checks the mode. **A missing `--mode` fails here, and nothing is
   written** (R-7).
7. Caiman materializes the permitted subset, writes `project.json`, writes
   `_index.md` recording what was omitted and why, and renders `project.md`.
8. The harness launches the agent with `project.md` in context.

Steps 5–7 are the only ones Caiman owns. Steps 1–4 and 8 belong to the harness,
and the boundary is a command-line call (G-7).

### 8.4 During the session

The agent greps the documents, reads files, and cites by path plus locator.
Nothing resolves and nothing changes underneath the session (R-6).

Caiman does run, in one narrow form: hook adapters fire on tool use and on stop,
appending to the session's access log (§6.10.3). They read no store, resolve
nothing, and never block. An earlier version of this document said "Caiman is not
running"; that was true before session integration and is no longer accurate.

### 8.5 First run, end to end

The full planned path from nothing to a working session, with the steps that are
**not yet specified** marked. Gap references are to §8.6. The implemented local
entry point is `caiman`: set up a board and project first, then ingest documents.
Remote and session commands below remain roadmap work.

| # | Step | Command | Status |
|---|---|---|---|
| 1 | Create the store on this machine | `caiman init --remote <url>` | Specified (`STORAGE.md` §7.5) |
| 2 | Create the private repository at the host | *manual, by design* | Specified. `init` prints the command; it does not create it |
| 3 | Set up an initial board and project with empty document sets | `caiman` | Implemented; S-29 |
| 4 | Convert externally, then select existing context and review document metadata | `caiman ingest manual.md` | Conversion out of scope (S-08); ingestion §6.4.3, S-26–S-29 |
| 5 | Add a compartment | `caiman compartment add oem-alpha` | Specified. Local only |
| 6 | Register customer specifications; explicitly select their compartments in the TUI | `caiman ingest specification.md` | §6.4.3 |
| 7 | Adopt document pins into a board configuration | `caiman board configure [config.json]` | Manual editing implemented; [authoring workflow](AUTHORING.md), S-28 |
| 8 | Adopt project document pins, features, precedence | `caiman project configure [config.json]` | Manual editing implemented; [authoring workflow](AUTHORING.md), S-28 |
| 9 | Publish | `caiman push` | Specified (`STORAGE.md` §7.6) |
| 10 | Install the harness hooks | `caiman hooks install` | Specified (§9.2) |
| 11 | Start a session in a worktree | *harness* | Specified (§6.10.2) |
| 12 | Agent asks which project and which mode; engineer answers | *conversation* | Specified |
| 13 | Materialize the workspace | `caiman sync --project … --mode …` | Specified (§6.8) |
| 14 | Work: read, grep, cite | *agent* | Specified |
| 15 | Session ends; access log closed | *hooks* | Specified (§6.10.3) |

And the recurring operations after first run:

| Operation | Command | Status |
|---|---|---|
| Set up a second machine | `caiman clone --remote <url>` | Specified |
| Pick up someone else's additions | `caiman pull` | Specified. **Gap C** — nothing reports what arrived |
| Adopt a re-converted or newer document into a project | — | **Gap D.** The most common operation, and it has no command |
| Check whether a workspace is current | — | **Gap E.** Only the session-start hook checks; no standalone command |
| Verify store integrity | — | **Gap E** |

### 8.6 Gaps in the end-to-end workflow

None of these blocks the design. All of them block an implementation, and they
are roughly in priority order.

Two gaps in an earlier version of this section — agent identity, and what a
second machine needs beyond the store — were **removed by S-19 dropping the agent
map**, not solved. With no policy file there is no vocabulary to define, nothing
to keep in sync across machines, and no name that can assert a falsehood about
which model a session is running.

#### Gap A — Ingestion input *(resolved by S-26 and S-27)*

The MVP uses a TUI to fill and review the manifest metadata. §6.4.3 specifies
steps, fields, defaults, errors, cancellation, and submission. Source and
converter provenance are optional; the input filename is captured automatically.
No sidecar file or lengthy flag list is required for ingestion.

Widget layout and TUI library remain implementation choices. Shared registration
logic must remain independent of terminal widgets so the future native macOS app
can reuse it. This resolves document input, not board/project authoring below.

#### Gap B — Board and project authoring input *(resolved by S-28)*

Boards and projects use editable JSON drafts and a TUI over the same shared
validation and registration operations. The UI has top-level fields plus JSON
editors for nested collections. `AUTHORING.md` owns the implemented field and
command contract, including template, configure, validate, show, export, and
new-version workflows.

Review resolves document references and the selected board version into immutable
digest pins; registration revalidates the pinned objects without re-resolving
mutable refs. A new version begins as a complete copy of a selected predecessor,
with an explicitly supplied new label and relation. Only edits form the authoring
delta; the stored result is always a complete snapshot.

The TUI and config-file path both report validation errors without writing a
version. Config-file import does not modify the input file. Explicit exports
create private files and refuse to overwrite existing work. Detailed row editors
may improve the nested JSON editing experience later; no second config format or
GUI-specific validation layer is introduced.

#### Gap C — Nothing reports what a pull brought

`caiman pull` merges. There is no `caiman log` or diff to show which documents,
board versions, or project versions arrived — and because refs are the only
mutable thing, the answer is computable and cheap. Minor, but it makes the
multi-machine story opaque in practice.

#### Gap D — Adopting a newer document into a project

The common operation, and it has no command.

Re-converting a manual (`STORAGE.md` §2.2) produces a new manifest digest and
repoints the ref. Every existing board and project version still pins the **old**
digest, correctly and by design (I-4). Adopting the new one means cutting a new
board version and then a new project version — a cascade the model requires and
nothing automates.

`SECURITY-MODEL.md` §8 step 3 names the same cascade for reclassification and
flags it as "a real cost and the honest consequence of immutability". The
mitigation recorded there is to make the CLI perform the cascade in one command
so the cost is machine time rather than human decision. That command does not
exist in the surface (§9.1). Without it, the friction lands on the operation
people perform most, and the predictable outcome is stale pins.

#### Gap E — No status or verification command

There is no way to ask, outside a session, whether a workspace is current, what a
project version resolves to, or whether the store is internally consistent —
digests matching content, no manifest missing blobs, modes correct after a clone.

The session-start hook checks staleness for its own worktree (§6.10.2) and
`--dry-run` answers "what could this session see", but neither covers the store
itself. `STORAGE.md` §8.2 specifies digest verification on read without a command
that exercises it deliberately.

---

## 9. Interfaces

### 9.1 Command-line surface

The surface below includes planned store and session commands. Local ingestion
and board/project authoring are implemented; see [AUTHORING.md](AUTHORING.md)
for their current arguments and examples.

```
caiman                                        guided setup, then document ingestion
caiman init [--remote URL]                      create a store on this machine
caiman clone --remote URL                       join an existing store
caiman compartment add <name> --remote URL      add an access boundary
caiman compartment clone <name> --remote URL

caiman ingest [markdown]                      open ingestion TUI; register locally
caiman push [compartment…]                      publish to remotes, after review
caiman pull [compartment…]                      fetch from remotes

caiman documents [--compartment NAME]          list accessible documents
caiman board   configure | template | validate | show | export | new-version
caiman project configure | template | validate | show | export | new-version
caiman sync --project P --version V --mode open|sealed --into DIR
caiman brief --project P --version V            render only the brief
```

Three groups, and the separation is deliberate:

| Group | Commands | Moves what |
|---|---|---|
| Store lifecycle | `init`, `clone`, `compartment add/clone`, `push`, `pull` | The store, between machines |
| Authoring | `ingest`, `board`, `project` | Content into the local store |
| Session | `sync`, `brief` | The store into a workspace |

`push`/`pull` are named separately from `sync` because they do a different job:
`sync` builds a session workspace from the store, `push`/`pull` move the store
itself. `push` is never automatic on ingest — see `STORAGE.md` §7.6 for why.

`sync` is the integration point a harness calls. Two flags matter beyond the
obvious:

| Flag | Purpose |
|---|---|
| `--dry-run` | Prints what would be materialized without writing. This is how a human answers "what could this session see" |
| `--mode` | Required. `open` or `sealed`. No default; omitting it is an error, not an implicit `open` |

### 9.2 Hook contract

Three commands, each reading a JSON event on stdin and writing optional JSON to
stdout. The adapter is whatever glue the harness requires; these are stable.

| Command | Fired on | Reads | Writes | May fail the session |
|---|---|---|---|---|
| `caiman session start` | Session start or resume | `cwd`, `session_id` | Context to inject: confirmation, staleness warning, or project choices | No |
| `caiman session record` | After a tool call | `session_id`, `tool_name`, `tool_input` | Nothing | No |
| `caiman session end` | Stop, SubagentStop | `session_id` | Nothing | No |

`caiman hooks install` writes the adapter configuration into the harness's
settings file. It prints exactly what it will add and requires confirmation,
because it modifies a file Caiman does not own.

Two properties are contractual, not incidental: **no command exits non-zero in a
way that blocks a tool call** (R-13), and **`session record` performs no store
access** (§6.10.3), because it runs on every tool call.

### 9.3 Workspace contract

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
| `--mode` omitted | `sync` fails; nothing written | Fail closed. A default would let an unconsidered session silently receive whatever that default was (R-7) |
| Bare project or board name | Return the version list; do not resolve | Resolving to "latest" against a frozen program is a compliance failure (R-5) |
| Document produces no resolvable locator | Reject at ingest | Uncitable content creates a path to uncitable answers (R-1) |
| Requirement-structured document lacks requirement IDs | Reject at ingest | The declared structure is part of the contract |
| Any pinned file cannot be materialized | `sync` fails and names the file | A document set missing one manual is indistinguishable, to an agent, from a document that never had it (R-11) |
| Project pins a digest no longer in the store | `sync` fails and names the digest | Broken pin. See `STORAGE.md` §8.5 for why this should be impossible |
| `push` to a remote that is not private | Hard error; nothing sent | One repository holds every compartment, so a public remote exposes all of them (`STORAGE.md` §7.6) |
| `pull` brings a ref conflict | Fail; show both digests and document identities | Two machines repointed one name. Guessing would silently change what a name means |
| A hook fails, times out, or Caiman is not installed | The session continues; nothing is logged | R-13. A broken audit hook that halts work gets removed within a week, which is worse than a log with known gaps |
| `session start` finds a brief whose digest no longer resolves | Inject a staleness warning naming both digests; do not block | R-15. The agent and engineer decide whether to re-sync; blocking would be disproportionate |
| `session record` receives a `Bash` call | Log the command verbatim, marked `unresolved` | Parsing which files a shell command read is heuristic and defeated by pipes. Recording the gap honestly beats a confident wrong answer |
| Two sessions log concurrently | Separate files keyed by session id | No contention, no locking |

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
| Ingest | Validating headings, hashing, and writing unchanged Markdown | I/O bound, proportional to document size. Runs once per document version |
| Resolve | Reading one ref and tens of small JSON manifests | Negligible at the stated volume; this is why no index exists (D-10) |
| Materialize | Number of files linked, not their size | CoW clones and hardlinks copy no bytes. One content file per document; cross-volume copying still scales with bytes |
| Agent retrieval | `ripgrep` over the documents | No network hop, no embedding call, no ranking |
| `session record` | One process spawn per tool call | The only Caiman code on a hot path. Constrained by design to string parsing plus an append — no store access, no resolution, no manifest read. **Measure it before shipping**; if process spawn alone proves too costly, batch at `Stop` from the transcript instead of hooking every call |

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
| A-1 | Ingest headingless content, content before the first heading, empty headings, duplicate full heading paths, and headings only inside code blocks | Invalid documents rejected with actionable locations (§6.4.2) |
| A-2 | Ingest a `requirement` document with valid headings but missing or invalid ID pattern, or no matching IDs | Rejected (R-1) |
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
| A-13 | Run `session start` in a worktree with no `.caiman/` | Injects project choices; does not fail, does not create anything |
| A-14 | Run `session start` against a brief whose project digest was repointed | Injects a staleness warning naming both digests (R-15) |
| A-15 | Run `session start` in a repository with no Caiman configuration | Injects nothing; exits zero (R-16) |
| A-16 | `session record` for a read inside `documents/` | One access-log line with document, version, and compartment derived from the path |
| A-17 | `session record` for a read outside `documents/` | Nothing logged |
| A-18 | `session record` for a `Bash` call | Logged verbatim and marked `unresolved`, not silently dropped |
| A-19 | Make every hook command fail | The session completes normally (R-13) |
| A-20 | Grep an access log for content from any document it references | No document body text present (R-14) |
| A-21 | Ingest valid ATX/Setext headings, skipped levels, and repeated names under distinct parents | Accepted without changing the input; heading paths resolve (§6.4.2) |
| A-22 | Search a large materialized manual, read a bounded range, and cite a fact | Correct heading or requirement-ID citation without loading the entire file |
| A-23 | Submit a valid TUI form with source and converter sections empty or partially filled | Unknown fields omitted; registration succeeds without the original source file (S-26) |
| A-24 | Edit after review, cancel, or submit with missing labels/invalid fields | Edits are revalidated; cancellation and invalid input publish no version or ref; labels have no default (S-27) |
| A-25 | Invoke ingestion without an interactive terminal | Actionable error; no writes (S-27) |

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

**Document granularity is settled by S-25.** One unchanged Markdown file is one
content blob; document-level labels and source headings replace the former
chunk model. Splitting and generated maps are outside the MVP.

**Does `PostToolUse` fire for subagent tool calls?** `SubagentStop` exists, so
subagents are visible at their boundary, but whether their individual tool calls
raise `PostToolUse` in every harness configuration is unverified. If they do not,
a subagent's reads are missing from the access log while the session appears
fully recorded — the worst shape for an audit gap, because it looks complete.

Verify before the access log is relied on for anything. If coverage is partial,
the honest fallback is to derive the log from the harness transcript at `Stop`
rather than from per-call hooks, accepting higher latency for completeness.

**Should the brief carry a session-scoped miss log path?** §15.2 depends on
recording queries where search and selective reading both fail. Whether the
agent can be asked to record them, or whether it must be inferred from harness
transcripts, is undecided.

**Three interface formats are named but not specified.** Each is described by its
purpose and referenced by other components, but no schema or example exists.
They are interfaces (§9.3), so leaving them implicit means two implementations
could disagree. These are the output side; §8.6 covers the input side and the
missing commands.

| Format | Referenced by | What is missing |
|---|---|---|
| `project.json` | §6.8, §9.3, the brief's *Where things are* block | Schema. It is the resolved project structure "fully expanded", which is not a specification |
| `_index.md` | §6.8, `STORAGE.md` §7.3 | Wording of omission entries. An agent must be able to distinguish "this project has none" from "this session may not see them" reliably, which is a format question |
| Access log schema | §6.10.3, `SECURITY-MODEL.md` §9 | The example line is illustrative. Field names, the `unresolved` marker, and the end-of-session summary shape need fixing before anything reads the log programmatically |

None of these blocks the design. All three should be specified before the code
that writes them, and `project.json` is the one to do first, because the agent
reads it directly and `describe_feature` was dropped on the assumption that it
would be sufficient.

### 15.2 Source-document navigation, and how it gets evaluated

The MVP relies on search and selective reading of unchanged documents, including
their existing headings. It generates no maps. Exact-identifier lookup is the
favorable case; concept-known, identifier-unknown questions remain unproven.

Record misses on real tasks. Revisit navigation or the deferred semantic tool
when these queries defeat search and selective reading more than occasionally.
Generated outlines or splitting would require a new decision rather than being
silently added to ingest. `ROADMAP.md` includes the miss log; S-18 and D-03 keep
semantic retrieval deferred.

### 15.3 Risks

| Risk | Impact | Mitigation |
|---|---|---|
| A deviation document without requirement IDs (§10.2) | The correlation behavior silently does not occur; the agent never learns a requirement was amended | Lint at ingest and report at registration, not during a session. D-12 tracks a structured alternative |
| Hand-declared features drift from the program | The brief asserts something false, with authority | Author-by-delta means a new project version starts from its predecessor (S-11); the brief is regenerated per session and never hand-edited |
| A converter silently drops content | Wrong facts that look right, with valid citations | Converter provenance, when supplied, helps identify affected artifacts; heading and ID checks only validate structure, not completeness. Spot-check against the source outside ingest |
| Source-document navigation proves inadequate and the miss log is not implemented | The trigger in §15.2 cannot fire; the decision reverts to intuition | Implement the miss log with the rest of phase 3 |
| Harness residue (§11.4) | Materialization is not reversible | Out of scope here. Tracked in `harness.md`; the policy question belongs to `SECURITY-MODEL.md` |
| Hook latency on every tool call (§12) | Perceptible slowdown across a whole session; pressure to remove the hooks | Constrain `session record` to string parsing and an append. Measure before shipping; fall back to transcript-derived logging at `Stop` if needed |
| The access log is read as an accounting rather than as evidence | A false negative treated as proof a document was never read | State the incompleteness wherever the log is surfaced, not only in this document (§6.10.4) |
| Subagent reads missing from the log | An audit gap that looks like completeness | Verify coverage before relying on it (§15.1) |
| `hooks install` writes to a settings file Caiman does not own | Surprising edits to the engineer's configuration | Print the exact change and require confirmation (§9.2) |
| Context budget growth in the brief | Every added line is paid on every turn of every session | Keep detail in `project.json` and the documents; treat brief size as a reviewed budget, not an incidental outcome |
