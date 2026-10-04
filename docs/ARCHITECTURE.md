# Caiman Architecture

**Current pod model:** [PODS.md](PODS.md) supersedes the access-label,
compartment, catalog-authorization, and separate-repository-mirror rules below.
Pods are local folders with optional Git sharing; the Git host owns remote
permissions. Older sections are retained as design history.

**Current document model:** [DOCUMENT-METADATA.md](DOCUMENT-METADATA.md) supersedes
the historical document-manifest pin semantics and hardware attachment restrictions.
All metadata edits create complete manifests; references keep bodies fixed and
show current approved metadata.

**Status:** Design reference; local ingestion and authoring are implemented.
Session materialization, hooks, and Git transport remain planned. Provisioning
local and Docker worktrees (§6.11) is proposed and awaits a `DECISIONS.md` entry.
The newer [session context proposal](CONTAINER-CONTEXT.md) describes host-side
provisioning, per-session folders, and automatic context-switch requests from
agents inside containers; it proposes revisions to the worktree-wide flow below.
**Scope:** Product rationale, scope, and the design that turns supplied documents
and declared structure into a session workspace a coding agent can use.
**Related:** [ROADMAP.md](ROADMAP.md) (success criteria and delivery),
`STORAGE.md` (on-disk layout),
`SECURITY-MODEL.md` (threat model), `DECISIONS.md` (settled and open decisions),
`harness.md` (measured harness behavior).

---

## 1. Summary

Embedded development is complicated by hardware and software evolving independently
across board versions, silicon revisions, software releases, and customer-specific
requirements. Much of the supporting documentation is also protected by NDAs,
making it increasingly difficult to keep the correct context isolated as the
number of concurrent projects grows.

Caiman manages this complexity by assembling only the hardware, design, and
requirement context applicable to a given project and writing it directly into
the worktree for coding agents to consume. Project structure is explicitly defined
by humans rather than inferred, while NDA-protected documents remain isolated and
require explicit access. The result is a minimal, project-correct set of ordinary
files that agents can read and search without relying on a server, index, or
intermediary service.

## 2. Background and Problem

| Missing context | Example failure |
|---|---|
| Descriptive: what the hardware does | The agent invents a register offset |
| Structural: what this board contains | It configures a peripheral this board does not route |
| Normative: what this program requires | It follows the datasheet but misses a customer deviation or frozen specification release |

Better document search helps with the first. The others also need an explicit
board and program model. An accurate citation can still refer to the wrong
hardware revision or governing requirement.

The summary describes the target system. Today, local ingestion, storage, and
board/project authoring are implemented; workspace generation and session hooks
are planned. [README.md](../README.md) documents available commands, and
[ROADMAP.md](ROADMAP.md) defines the remaining milestones.

### 2.1 Who this is for

A firmware engineer working on a multi-chip board built to a customer's
specifications, already using coding agents and repeatedly correcting their
hardware or program assumptions. Team administration and SSO are deferred.

### 2.2 Product rationale

The useful contribution is connecting a board to a program's frozen specification
set, required features, and declared deviations. Document ingestion and search
support that model. Whether this saves enough review and maintenance time remains
to be demonstrated; G01–G03 define the evaluation.

An open product question is how much parts management belongs here. The original
need was managing documents; board structure should help engineers find and apply
the right sources. Evaluate additional parts-management features against that need.

### 2.3 Positioning and principles

Caiman assembles context as files. It does not own the agent, worktree management,
or hardware execution. This keeps adoption and maintenance small, but also leaves
integration work to the engineer. Whether to build this layer or adopt a platform
remains D-04.

The user supplies the documents; Caiman does not redistribute them. Humans
declare relationships and classification. Answers must be verifiable against a
versioned source. The brief contains metadata only and uses a program codename;
the safety of exposing that metadata remains an explicit review item (G17).

[CLAUDE.md](../CLAUDE.md) owns agent invariants. [DECISIONS.md](DECISIONS.md)
records the reasons behind technical choices.

The [historical competitive survey](ROADMAP.md#competitive-landscape-historical)
provides context for D-04; it is not a verified current product comparison.

## 3. Goals

The system must resolve one stable project pin set, prepare a brief and document
workspace, and integrate through the CLI without owning the agent session.
[Roadmap’s MVP success criteria](ROADMAP.md#success-criteria-for-the-mvp) define product acceptance;
§5 below owns the technical requirements.

## 4. Non-Goals

| Not doing | Why | Decision |
|---|---|---|
| Agent orchestration, session or worktree management | Commodity, and where the platforms compete | S-01 |
| Hardware-in-the-loop test execution or scheduling | A real problem; not the context layer | S-01 |
| PDF to markdown conversion | Supplied externally; Caiman accepts any file format | S-08 |
| Splitting, generated maps, summaries, or AI processing at ingest | Register one unchanged file of any format and document-level labels; evaluate navigation on real tasks | S-25 |
| Requirements or compliance management | Caiman cites a requirement; it does not track whether you met it | S-14 |
| Conflict detection between specifications | Precedence is declared, not computed. Inferring it means interpreting contracts | S-15 |
| Hosting licensed standards (ISO, AUTOSAR, MISRA) | Licensing, and customer specifications are largely self-contained | S-17 |
| Acting as an enforcement boundary | The human picks the agent; Caiman makes the choice consequential | S-19 |
| A human-facing documentation browser | The consumer is an agent. Authoring uses an ingestion TUI in the MVP; a native macOS app is the future curation GUI | S-27 |
| Bundling or redistributing vendor or customer documentation | Licensing, and it breaks the core design commitment | — |
| Content-inspection-based confidentiality detection | Text cannot establish disclosure permission (`SECURITY-MODEL.md` §4) | S-03 |
| Interpreting version numbering | Varies per company; encoding one convention breaks the rest | S-10 |
| A sync or merge system | Git already does this. The store is a git repository; Caiman wraps it, it does not reimplement it | S-22 |
| Multi-user, team, or SSO features | No second user yet | — |

The MVP also has no retrieval server (S-18) or repository-side lockfile (S-07).
[DECISIONS.md](DECISIONS.md) records the rationale behind these boundaries.

## 5. Requirements and Constraints

### 5.1 Requirements

| ID | Requirement | Source |
|---|---|---|
| R-1 | Register readable files unchanged; document structure and requirement-pattern metadata are retired | I-5 |
| R-2 | Labels are supplied at ingest from provenance and never derived from content | I-8, S-03 |
| R-3 | Content that is neither public nor compartmented is materialized nowhere | I-1 |
| R-4 | A project version resolves to a complete pin set, including everything its board version pins | S-07 |
| R-5 | A bare board or project name returns the list of versions and does not resolve | I-7 |
| R-6 | Resolution happens once per session and holds digests thereafter | I-4 |
| R-7 | `--mode` is required; omitting it causes `sync` to fail and write nothing | I-1, S-19 |
| R-8 | The brief generator has no access to document content | I-6 |
| R-9 | A generated brief contains no customer identity, only the program codename | I-6 |
| R-10 | Lineage, precedence, and feature relationships are declared and rendered, never computed | I-8 |
| R-11 | Every document permitted by the project pins and declared mode is materialized; partial materialization is an error | I-9 |
| R-12 | Ordinary recursive search reaches every materialized document — no symlinked directories or silent omissions | I-9 |
| R-13 | Hooks never deny a tool call and never fail a session | I-10, S-19 |
| R-14 | The access log records document identities, never document content | I-10, I-6 |
| R-15 | A session whose brief no longer matches its project version is told so at start | I-4 |
| R-16 | A repository with no Caiman configuration has its sessions unaffected | — |
| R-17 | Provisioning writes only to a host folder at the top of a guarded git worktree; never into a container's filesystem or an image | I-3, I-9 |
| R-18 | The store and Caiman's configuration never enter a container | I-3, S-19 |
| R-19 | Every session start in a provisioned worktree restates the declared project, version, and mode | I-1, S-19 |
| R-20 | Clearing or re-provisioning warns that running sessions keep what they already read, and is logged | I-10, §11.4 |

### 5.2 Constraints

| Constraint | Consequence |
|---|---|
| Documents arrive already converted into a descriptive markdown format, by a tool Caiman does not control | Optional converter provenance can help trace conversion defects; unknown provenance is accepted (S-26) |
| Harness transcripts can retain document text outside Caiman's control | Workspace cleanup cannot revoke those copies; see §11.4 and the dated observations in `harness.md` |
| The consumer is an agent with a bounded context window | The brief must be an orientation document, not a data dump |
| A 2,000-page reference manual is roughly 20 MB of markdown | Keep the file whole; agents search and read selected ranges rather than loading the entire manual |
| Version semantics differ per company | No parsing, ordering, or "latest" resolution anywhere in the system |

---

## 6. System Overview

### 6.1 Shape

The target pipeline registers documents and configuration snapshots, stores them
by digest, resolves a project into a complete pin set, then materializes the
permitted documents and metadata. It writes files and exits; optional hooks
observe the subsequent session.

```
  prepared markdown + metadata        board definition      project definition
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
                documents/      unchanged document files
                           │
                           ▼
              harness → coding agent (reads, greps, cites)
                           │
                           ├── SessionStart  → caiman session start
                           ├── PostToolUse   → caiman session record
                           └── Stop / SubagentStop → caiman session end
                                       │
                           ~/.local/state/caiman/audit/session/<session>.jsonl
```

### 6.2 Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| **Ingest** | Metadata validation, hashing, unchanged-file registration | Conversion, splitting, maps, AI processing, classification decisions |
| **Register** | Board and project models, features, precedence, lineage | Inferring any of them |
| **Store** | Immutability, content addressing, compartment separation | Query, search, ranking |
| **Resolve** | Name→digest, transitive pin set, version listing | Choosing a version on the user's behalf |
| **Materialize** | Workspace assembly, mode filtering, linking, brief rendering | Session lifecycle, agent process |
| **Provision** | Choosing and checking the target worktree, resolving a container path to its host folder, clearing and re-provisioning (§6.11) | Creating worktrees or containers; writing into a container |
| **Session integration** | Start-time configuration and staleness check; access recording | Blocking tools or managing the agent process; the per-read recorder never accesses the store |
| **Harness and environment** (external) | Worktree and container creation, launching, publishing hook events | Deciding what an agent may see |

### 6.3 Why there is no server

The agent searches ordinary files. [S-18](DECISIONS.md#s-18-the-filesystem-is-the-interface-there-is-no-server-in-the-mvp)
records the decision; §15.2 defines when to revisit retrieval.

Searching a requirement ID can return both its base specification and an
amending deviation, provided the deviation names that ID. For example:

```bash
rg -n 'REQ-FLASH-0142' .caiman/documents/
```

Missing amendment IDs break this correlation; see §10.2 and D-12.

### 6.4 Ingest

#### 6.4.1 Inputs and responsibilities

Input is **one file of any format**, already prepared outside Caiman, plus
human-supplied metadata: name, description, issuer, part or program, and version,
applicable silicon revisions, and access labels. Original-source and converter
information are optional. The ingestion TUI collects these fields; §6.4.3
defines the form and `STORAGE.md` §6.4.1 defines their stored representation.

Ingest is registration, not document processing (S-25). It owns:

1. Validating required metadata and explicit whole-document access labels.
2. Reading the selected file without content admission checks (§6.4.2).
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

#### 6.4.2 File admission and citations

Ingest accepts any readable file, including binary, empty, extensionless, and
non-UTF-8 files. There are no heading, heading-path uniqueness, front-matter,
or requirement-ID admission checks. Documents have no `structure` or `requirements` metadata.

Each input is preserved byte-for-byte. Registration does not convert, repair,
or certify content. Reading and searching depend on tools that support the
source format; binary registration does not provide automatic text extraction.

Citations still identify the document and immutable version, with a locator
appropriate to the source: requirement ID, heading path, page, sheet/cell,
line range, or another precise location. Never invent missing source structure.
Markdown headings can aid navigation when present but are not required.

#### 6.4.3 Registration and reading workflow

**Select file → supply metadata → review → register.** The engineer reviews the
document identity, version, applicability, and explicit access labels before
local registration in a terminal UI (TUI), launched by `caiman ingest [file]`.
The file argument is optional; without it the TUI asks for a file. Bare `caiman`
opens the dashboard. Ingestion allows manual metadata entry, selection of an
existing board/project, or creation of one without leaving the flow. Setup is
not mandatory, and no board or project becomes a default (S-29). Document lists
may start empty. Push remains a separate act with its own label review.

The form has four steps:

1. **File.** Select one file of any format. Show its basename and file-read
   results; do not ask for a second original-source filename.
2. **Document.** Pick an existing project or board part to populate declared
   metadata, or enter document identity manually. Offer creation of a new board
   or project and return to the retained ingestion form. Enter a document name,
   description, and version. All roles use the same document form. Project selection supplies
   the program and compartment context; board-part selection supplies issuer,
   part, and any declared silicon revision. Silicon revisions are optional when
   not applicable or unknown; display that absence honestly. Choose public
   access or named compartments explicitly, with no preselected access label.
3. **Optional provenance.** A skippable section for original-source checksum and
   page count, and converter name. Each
   may be left unknown. Never infer these from the filename or missing fields.
4. **Review and register.** Show entered metadata and labels, unknown optional
   fields, and the computed file digest and size. Allow back/edit or cancel.
   Register only on explicit submit; cancellation creates no document version
   and does not repoint a ref. Report field errors inline and file errors
   with source locations, retaining entered values for correction.

The Documents gallery shows single document cards and stacked collection cards,
with separate add cards. Collections are named groups selected from existing
documents, with a review/save editor and automatic immutable snapshots; users
do not enter collection versions. See `STORAGE.md` §6.4.1a for pin and access rules.

Opening a document card launches the guided metadata editor, using the same
top-level fields, collapsible card grids, inline fields, and separate review/save
flow as boards and projects. Applicability, source provenance, and converter
provenance are fixed detail groups. File bytes and pod location
are read-only. Registration details remain available in a collapsed read-only
section. Cancellation and unchanged drafts write nothing. Every metadata edit
saves a complete immutable manifest under a stable document ID. Existing references
show its current approved metadata without rewriting consumer snapshots. File
bytes remain fixed. The review lists known local usages, reports incomplete scans,
and rejects stale reviews and name collisions. Attachment to boards/parts is a
user declaration: issuer, part/program, and silicon applicability do not gate it.
The editor also lazily loads a read-only Metadata History section, ordered by
manifest lineage, with complete saved fields and JSON. Browsing revisions keeps
the working draft intact; unavailable history is reported within that section.
[DOCUMENT-METADATA.md](DOCUMENT-METADATA.md) owns this workflow.

The TUI fills a manifest draft. Caiman supplies `original_filename` (the input
basename), content digest and size, schema and pipeline versions, and
ingestion timestamp. Source and converter fields are optional individually and
as groups; omitted values stay absent, not invented or encoded as safe defaults.
When importing a converted file, matching basenames are not proof of source
identity. No separate original-source filename is stored.

The TUI calls shared validation and registration logic rather than writing blobs
or manifests itself. A future native macOS app will use the same operations and
field rules (S-27). A noninteractive flag/sidecar format is not an MVP requirement;
without an interactive terminal, explain that the TUI requires one and write
nothing. Board/project creation uses the shared authoring workflow
([Configuration guide](../README.md#configure-boards-and-projects), S-28, S-29). Selecting a configuration during
ingestion does not change its immutable document pins; adoption is an explicit
configuration edit.

The stored content is materialized at its manifest file path under the versioned
document directory: `document` plus the input extension for new registrations.
Preserve legacy paths and the original input filename metadata. Agents search
text documents for identifiers, phrases, or existing headings and read bounded
ranges around hits, including relevant qualifications. Other formats require
a suitable reader. A several-hundred-page manual stays one file;
its full contents need not enter the context window.

No `_map.md` or other navigation artifact is generated. Concept-known,
identifier-unknown queries remain an evaluation risk (§15.2). If the original
headings are poor, the engineer prepares a corrected file externally and
registers a new immutable version; Caiman does not repair it in place.

### 6.5 Register

A board describes hardware; a project combines pinned boards with specifications,
features, and compartments. [README.md](../README.md#configure-boards-and-projects) owns editing workflows; [Storage §6.4](STORAGE.md#64-manifest-schemas) owns the
serialized manifests.

#### 6.5.1 Board — hardware only

Parts are identified by role. Aliases connect those roles to schematic or
procurement identifiers. Boards pin public documents for both parts and the
assembly; they contain no customer or program fields. Preserve vendor peripheral
names so they can be searched in the manual.

#### 6.5.2 Project — the session unit

A project pins one or more board versions and a specification set, with its
compartments. It declares no precedence among documents (S-36). A program may run on several boards, or on
one board at several versions; each pin is explicit (S-34). Separate projects can
share a board while carrying different customers' requirements.

#### 6.5.3 Features

Features connect requirements to board roles through `governed_by`, `realized_on`,
and `related`. A `realized_on` entry names the board, version, and role, because
role names repeat across boards. Their scope is `required` or `not-used`; implementation and
verification status are outside Caiman's scope (S-14).

#### 6.5.4 Rules shared by both models

Version labels are opaque. Lineage and relationships are declared by a human.
Editing starts from a complete snapshot; registration stores another complete
snapshot, with no inheritance at read time (S-10, S-11, S-15).

### 6.6 Store

The store holds immutable blobs and complete manifests plus mutable refs. Board
and project pins identify exact configuration manifests. Document references carry
a stable pod ID, document ID, and fixed blob digest; normal reads follow the
current approved manifest. Exact revision reads retain original metadata.
[STORAGE.md](STORAGE.md) owns layout, schemas, write ordering, and Git transport.

S-33 resolves repository isolation: one private Git repository per compartment,
with a separate private public-material repository. Each document is public or
belongs to one compartment. S-35 adopts the transport protocol; it is not yet
implemented.

### 6.7 Resolve

**A project version is the complete pin set** (R-4). Resolving
`falcon @ B-sample` yields:

- every board version, and every `(role, part, silicon revision, document version,
  digest)` tuple each one pins
- assembly-level documents pinned directly by the board
- every specification document version in the project’s documents list
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
| Resolution checks declared access | Project and document reads require the caller’s declared compartments. This does not isolate a process that can read the underlying store directly (§11.4) |

Code-to-context traceability remains open (G11). One proposal is a commit trailer
written by the harness from the session's project digest, such as
`Caiman-Project: falcon@sha256:9f3c…`. Neither that mechanism nor a firmware-release
model is implemented.

### 6.8 Materialize

```
caiman sync --project falcon --version B-sample \
            --mode sealed --into .caiman/
```

The project selects the pinned documents and allowed compartments. The mode
then determines whether compartmented documents are written. A document's entire
compartment set must be included in the project's set; one matching compartment
is not sufficient. Neither stage adds unrelated documents from the store.

“Minimal” means this explicitly selected set, not automatic relevance ranking,
summarization, or removal of passages. Each permitted document stays whole.

| Mode | Materializes |
|---|---|
| `open` | Public documents in the project's pin set |
| `sealed` | Everything the project version pins |

**`--mode` is required and has no default** (R-7). Omitting it is an error, never
an implicit `open`. There is no agent map, no profile lookup, and no policy file:
the human states what this session gets, at the moment they know what model they
are running and what the work touches. `SECURITY-MODEL.md` §5.3 records why the
map that used to sit here was removed, and what that costs.

An optional `--agent-label` is carried into the materialization log as an
unverified annotation. It names the harness, not the model, and is not an input
to the decision.

When and where `sync` runs, and how a Docker container's worktree is targeted,
is specified in §6.11.

The workspace layout, link mechanism, and the three materialization constraints
are specified in [Storage §7.3](STORAGE.md#73-materialize). Prefer filesystem
clones, then read-only hardlinks; copy when crossing filesystems. Cache entries
are scoped by compartment. Blobs and materialized documents use mode `0444`,
and the document tree has no symlinked directories. If a permitted pinned file
cannot be written, fail without leaving a partial workspace (I-9, R-11, R-12).
Intentional omissions in `open` mode are recorded in `documents/_index.md`.

`project.json` is intended to expose the resolved feature graph and pin set on
demand. Its schema and visibility rules remain open (G16/G17): it must
not be treated as permission to dump a compartmented project manifest into an
open workspace. The brief's codename rule alone does not settle other outputs.

### 6.9 The brief

An orientation document, not a data dump. Injected context is paid for on every
turn of every session, so the brief's job is narrow: make the agent know what it
is working on, and know that it must look things up rather than recall them.
The example below illustrates the planned content, not a final output schema
(G16). Detailed declarations and document pins belong in the resolved JSON.

```markdown
# Project: Falcon — B-sample
Board: zonal controller (rear) 2.1 · OEM spec set frozen at release 3.2
Generated by caiman from falcon@sha256:9f3c… — do not edit.
Derived from A-sample: "spec set moved 3.0 → 3.2; secure flashing added"

## Session mode: sealed
Full pinned document set for this program is available.
This mode does not verify which model is running or whether it is authorized.

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

## Where things are
Documents: .caiman/documents/ — each document directory contains one unchanged
file at its manifest path, preserving its extension. For text, search identifiers
or headings and read the relevant range with surrounding qualifications.
Use a suitable reader for other formats. Paths identify the document and version; cite
a source-appropriate locator. Do not read a whole manual
into context. There are no generated maps.
Resolved structure: .caiman/project.json

## Rules
- The OEM spec set is frozen at release 3.2. Later revisions do not apply to
  this program, even where they are newer.
- Where a program deviation amends a requirement, the deviation governs. Look
  requirements up by ID; search can return the base requirement and deviations
  that explicitly name that ID. Missing matches do not prove no deviation exists.
- This is board 2.1. Facts specific to other board versions do not apply.
- The application MCU is silicon rev 1.1. Documentation for rev 2.x does not
  apply to this board.
- Never state a register offset, bitfield position, timing value, or
  requirement without a citation. If it cannot be cited, do not state it.
- Caiman supplies requirement documents and declared feature scope. Tracking
  implementation or verification status belongs in the team's ALM tooling.
```

In a public-only session the mode block reads instead:

```markdown
## Session mode: open
OEM specifications for this program are not available in this session.
If a task requires them, stop and tell the engineer to start a sealed
session — do not infer, approximate, or work around a specification you
cannot read.
```

The brief has three constraints:

- **Always visible under S-09.** It names restricted context so an open session
  can recognize what is missing. Whether those names and other metadata are
  safe to expose remains G17; metadata is not automatically non-confidential.
- **Codename only.** Customer legal identity stays in the compartmented project
  manifest (R-9).
- **Metadata only.** The generator reads board, project, and document manifests,
  never document bodies (R-8, I-6). This prevents body-text excerpts; it does not
  establish that every manifest field is suitable for the brief.

### 6.10 Session integration

Planned hooks run during a session as well as at its start. They configure the
session and record observed reads of managed documents.

This does not reopen S-01. Caiman is not managing sessions; it is registering
callbacks with a harness it does not own, at extension points that harness
already publishes. `sync` produces the workspace; hooks produce context messages and audit records.

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
directory and the harness's session identifier. Session start **reports**
provisioned context; selecting context normally happens earlier, at
provisioning (§6.11). Five outcomes:

| State | Behavior |
|---|---|
| `.caiman/` exists | Inject the brief reference and restate the declaration: project, version, digest, mode, compartments, and when it was provisioned (R-19). With the store reachable, check whether the version ref moved; without it (inside a container), say staleness is unverified |
| `.caiman/` exists and the selected version's ref now points to another digest | Warn with both digests. Keep the workspace pinned until the engineer explicitly provisions new context |
| No `.caiman/`, store reachable (local fallback) | Inject the available projects and versions, and an instruction for the agent to ask the engineer **which project and which mode**, then run `caiman sync` |
| No `.caiman/`, no store (inside a container) | Inject that no documents are provisioned and that the engineer provisions this worktree from Caiman on the host. List no projects, because none are visible |
| Caiman not installed or not configured | Inject nothing. A repository without Caiman must not have its sessions disrupted |

**The hook cannot prompt the engineer directly.** Hooks run non-interactively —
stdin carries the event payload, not a terminal. So in the local fallback the
hook injects context and the *agent* asks, which is the only path that works
with the grain of the harness. The engineer answers both questions in their
first message: which project, and whether this worktree is `open` or `sealed`.

Whichever entry point is used, the mode is declared by a human and never looked
up from a policy file (S-19). The declaration covers the worktree until it is
cleared or re-provisioned; §6.11.5 explains that lifetime and why every session
start restates it. This replaces the earlier proposal for a
`.caiman/session.toml` resume record.

A moved version ref does not invalidate the workspace's pinned digest. The hook
may report that a new ref target exists, but must not adopt it automatically.
The startup inventory and staleness lookup still need a defined data source;
the no-store-access rule applies to per-tool access recording, not a substitute
for specifying startup behavior.

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
| Answers | What Caiman materialized | Which managed reads were observed |
| Produced by | `sync`, deterministically | Hooks, during the session |
| Complete? | Yes | **No** — see below |
| Depends on the agent cooperating? | No | Partly |

Three ways a read escapes the access log:

1. **`Bash` reads.** `PostToolUse` fires for `Bash`, but the payload is a command
   string. Extracting which files a `cat`, `rg`, or shell script read is
   heuristic at best and defeated by pipes and indirection. Log the command
   using a content-free representation, still to be specified in G22. Do not
   store the command verbatim: it can contain restricted text.
2. **Hooks not installed**, or installed for one harness and not another.
3. **Anything outside the harness.** An editor, another process, a second tool.

So: **absence of a record is not proof of non-access.** The access log is
evidence, not an accounting. Stated plainly wherever it is used, because the
opposite reading is the one that causes harm.

As described in [Security §9](SECURITY-MODEL.md#9-audit), observed reads provide
leads for locating transcript residue, not a complete inventory of it.

#### 6.10.5 Hooks observe; they never block

`PreToolUse` can deny a tool call. Caiman does not use it, and this is an
invariant (I-10), not a current limitation.

This follows S-19: workspace filtering is not process enforcement. A file omitted
from the workspace may still be accessible elsewhere to the same OS user.

Two further rules follow from the same reasoning:

**A hook failure never fails the session.** Logging is best-effort. A broken
audit hook that halts work would be traded away within a week, which is worse
than a log with gaps that is known to have gaps.

**The access log records identities, never content.** Paths, document names,
versions, compartments — the same metadata-only rule as the brief (I-6). An audit
record containing an excerpt of a specification would be a copy of the
specification in a file nobody thinks of as one.

### 6.11 Provisioning a worktree

*Proposed in D-14.* This section covers two setups, defined by **where the
agent process runs**, not where the toolchain runs:

| Setup | Agent runs | Examples |
|---|---|---|
| **Local** | On the machine that holds the store | A plain CLI session; a host agent in Claude Code's sandbox runtime; a host agent that builds with `docker exec` into a toolchain container |
| **Docker** | In a container or microVM that mounts a worktree from that machine | A dev container with the agent installed; one container per worktree; Docker Sandboxes |

A host agent with only its toolchain in a container is the local setup: the
container never reads documents, so Caiman ignores it. Remote machines, cloud
development environments, cloud agents, and CI are out of scope until Git
transport exists (§15.1). A dated survey of which setups are common is in
[research/agent_container_landscape.md](research/agent_container_landscape.md).

**Provisioning** means running `sync` into a worktree. **Clearing** removes the
provisioned context. **Re-provisioning** is clearing followed by provisioning.

#### 6.11.1 When and where

Provisioning happens after the worktree exists, and for Docker after its
container exists — not at agent session start. Two reasons:

- `sync` needs the store. In the Docker setup only the host has the store, and
  agent sessions start inside the container, where the chance to provision has
  already passed.
- A worktree is one line of work on one project version. Its agent sessions are
  restarted, cleared, resumed, and switched between harnesses; they should all
  see one pin set (I-4) instead of selecting again each time.

**The target is always a folder on the host: the top of a git worktree.**
Provisioned context belongs to that folder, never to a container. Containers are
recreated; several containers can mount one worktree, and one container can mount
several worktrees. A container is only a way of finding the folder.

Caiman creates neither worktrees nor containers (S-01). The engineer's own tools
do that; Caiman is visited afterwards.

#### 6.11.2 Entry points

| Entry point | Setups | Who declares the mode | Who runs `sync` |
|---|---|---|---|
| **Host TUI** (primary) | Local and Docker | The engineer, in the TUI | Caiman, on the host |
| **Session-start fallback** | Local only, when the session can reach the store and the worktree has no `.caiman/` | The engineer, answering the agent (§6.10.2) | The agent |

The fallback is the weaker path. The mode reaches `sync` through the agent,
and the agent's OS user can read the whole store anyway (§11.4). It exists so
that a local session without prior provisioning still works.

The TUI flow, from the dashboard:

1. **Target.** Choose one source:
   - a running Docker container, then a path inside it (§6.11.3);
   - a worktree listed by `git worktree list` for a repository the engineer
     names;
   - a typed host path.
2. **Checks.** Run the target checks (§6.11.4). A failed check stops here with
   its reason.
3. **Project and version.** Choose a project, then a version from its list.
   Nothing is preselected: no "latest" (I-7) and no remembered default
   project (S-29).
4. **Mode.** Choose `open` or `sealed`. Nothing is preselected (I-1, R-7).
5. **Review.** Show:
   - the host path, plus the container and container path when used;
   - `project@version` and the digest it resolves to;
   - the mode, and the documents to be written and omitted;
   - the link mechanism: clone, hardlink, or copy.
6. **Provision.** Run `sync --into <host path>/.caiman` and write the
   materialization log.

If the target already has `.caiman/`, step 3 onward becomes re-provisioning
(§6.11.6).

#### 6.11.3 Resolving a container target

Docker use is read-only: `docker ps` to list containers, and `docker inspect`
for their mounts and configured user. Caiman never creates, starts, execs into,
copies into, or commits a container. It invokes the `docker` CLI rather than
adding a Python dependency (D-04). If the CLI is missing, lacks permission, or
the daemon is unreachable, the TUI falls back to a typed host path.

The chosen container path must fall inside a mount of type `bind`. Its host
folder is the mount's source plus the remainder of the path. Refuse:

| Container path is in | Why it is refused |
|---|---|
| The container's writable layer (no mount) | No host folder exists. Documents written there are a full copy per session, sit outside every worktree guard, disappear with the container, and are baked into an image by `docker commit` |
| A named volume | The host path lives under Docker's data directory, is not a worktree, and is not a folder the engineer manages |
| A `tmpfs` mount | Not on disk |
| Any mount, when the daemon is not local (`DOCKER_HOST` or a non-local context) | The mount source is a path on another machine |

Docker Desktop on macOS or Windows bind-mounts real host folders, so the same
resolution applies there.

Docker Sandboxes (`sbx`) run agents in microVMs, not containers, so `docker ps`
does not list them. They mount the workspace at the same absolute path as on
the host, with no sync step. Provision them by choosing the worktree or typing
its host path; no sandbox lookup is proposed.

This is why provisioning never uses `docker cp`: every row in the table above
applies to what it writes. The container name and ID are recorded in the
materialization log as an annotation only; `.caiman/` belongs to the folder
(§6.11.1).

Mounting the worktree at the same absolute path inside the container is
recommended, not required. Git worktrees record absolute paths to the main
repository, so git — and the commit guard — only works in the container when
those paths resolve. Identical paths also let host-side tools match transcript
paths to host files.

#### 6.11.4 Target checks

| Check | On failure | Reason |
|---|---|---|
| The host folder is the top of a git worktree | Refuse | The commit guards are per repository |
| `git check-ignore` covers `.caiman/` | Refuse | I-3 |
| The pre-commit guard is installed and active for this worktree, honouring `core.hooksPath` | Refuse | I-3 |
| No container mount targets `.caiman/` or a path below it | Refuse | A separate mount pins the directory it was given. Re-provisioning installs a new generation by rename (`STORAGE.md` §7.3), so the container would keep the old, possibly sealed, set |
| The worktree is on the store's filesystem | Report, then copy | Clones and hardlinks cannot cross filesystems (`STORAGE.md` §8.6) |
| The container runs as root, and the link mechanism would be hardlink | Warn: recommend a non-root container user or a filesystem with reflink support | `0444` does not stop root. One in-place write changes the shared inode for every session and the store's cache (I-9) |
| The worktree has a `Dockerfile` or `Containerfile`, and `.dockerignore` does not exclude `.caiman/` | Warn | A build with `COPY . .` puts the documents into an image layer, and images get pushed to registries |

The refusals are not overridable. The I-3 guards admit no exceptions, including
for testing.

#### 6.11.5 Mode lifetime

The mode declared at provisioning applies to every agent session in the worktree
until the worktree is cleared or re-provisioned. This is still S-19: a human
declares the mode explicitly, with no default and no policy file. The
declaration covers a worktree instead of a single session.

What this costs: a session started later may run an agent the engineer would not
have cleared for the worktree's compartments. Caiman cannot prevent that (I-10,
S-19). It makes the declaration visible every time: session start restates the
project, version, mode, compartments, and provisioning time, and instructs the
agent to tell the engineer to stop if this agent should not see those
compartments (R-19). A reminder narrows nothing and widens nothing.

The declaration is recorded in the workspace beside the brief. Its file and
format fall under G16 with the rest of the workspace formats.

#### 6.11.6 Clearing and re-provisioning

Both are available in every mode, from the TUI and the CLI (§9.1).

- **Clear** removes the whole `.caiman/` directory.
- **Re-provision** installs the new workspace as a new generation
  (`STORAGE.md` §7.3), so no partial workspace is ever visible.

Before either, the TUI states that **agent sessions that are running keep what
they already read**, in their context and their transcripts (R-20). Switching a
worktree from `sealed` to `open` does not make a running session open; start a
new agent session after the change. Transcripts are outside Caiman's reach
(§11.4). Caiman cannot reliably detect running sessions — inside a container
their transcripts are not on the host — so the warning is unconditional.

Every provision and every clear is written to the materialization log. The log
then shows when each document set was available in the worktree, not only when
it appeared.

The container sees the result through its worktree mount without a restart.

#### 6.11.7 What runs inside the container

| Inside the container | Needs the store |
|---|---|
| `caiman session start`, working from `.caiman/` alone | No |
| `caiman session record` (planned) | No, by design (§6.10.3) |
| Little caiman, run with `docker exec` | No. Its integrity check reports `unverified` |

The image contains Caiman and nothing else of Caiman's: no store, no Caiman
configuration, and never a materialized document (R-18). Mounting the store,
even read-only, would put every compartment within an `open` session's reach
and make the mode meaningless.

Two locations in the container home need a decision per setup:

| Location | If not mounted from the host | Recommendation |
|---|---|---|
| Caiman state (`$XDG_STATE_HOME/caiman`, holding the access log) | Lost with the container | Mount a per-worktree host folder, so the compliance record survives |
| Harness transcripts (for Claude Code, `~/.claude`) | Lost with the container | Undecided (G20). Deleting them helps revocation; keeping them helps audit, and they hold copies of what the agent read |

Run little caiman inside the container. Dev containers keep `~/.claude` in a
Docker named volume by default, so the transcripts are usually not in any host
folder. Little caiman run on the host against a container's transcript sees
container paths. If the transcript's working directory does not exist on the
host, it says that reads cannot be matched here, rather than reporting that no
`.caiman/` exists. A silent zero is the failure to avoid (I-9's reasoning,
applied to the audit view).

**The host and the container can run different Caiman versions.** The image's
Caiman is fixed when the image is built; the host's is upgraded separately. The
workspace therefore carries a format version, written by `sync`. When
`session start` or little caiman meets a format version it does not know, it
says so and names both versions — never silence, never a failed session (R-13).
The format itself is part of G16; the compatibility rule is G27.

#### 6.11.8 Long-lived containers

A container per worktree usually lives as long as the branch: days to weeks,
stopped and started freely, and rebuilt — as a new container — whenever its
image definition changes. Disposable containers (`docker run --rm`, Docker
Sandboxes) need nothing extra, because `.caiman/` is in the worktree. Long
lifetimes change three things:

| Effect | Consequence | Response |
|---|---|---|
| One provisioning serves weeks of sessions, possibly with different agents | A stale mode declaration is more likely | Restating it at every session start (R-19) |
| A version ref moves while the worktree keeps its pin | Correct (I-4), but inside the container nobody can see it, because there is no store | The host TUI lists provisioned worktrees from the materialization log and marks those whose version ref now points elsewhere (G28) |
| Transcripts accumulate in the container for weeks | More copies of more documents outside Caiman's control | G20 decides; §6.11.7 lists the mount choice |

---

## 7. Data Model

```
Issuer ──< Part ──────< Document ──< DocumentVersion ───> Blob
   │                        │              │               │
 vendor              issued_by        document labels    unchanged file
 or OEM              part | program   silicon revs       source locators
                                      manifest digest   content digest

BoardVersion ──> assembly DocumentVersions
Board ──< BoardVersion ──< PartInstance ──> Part
              │     │            │
     derives_from   │       silicon revision
     + relation     │       pinned DocumentVersions
                  Link ──> PartInstance, PartInstance

Project ──< ProjectVersion ──< BoardVersion (one or more)
   │              │  │
codename          │  ├──> pinned spec DocumentVersions
customer          │  └──< Feature
compartments      │            │
           derives_from   governed_by ──> DocumentVersion + requirement IDs
           + relation     realized_on ──> PartInstance on a pinned BoardVersion
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
*pins* specification document versions. Boards also pin assembly-level documents.

The software releases mentioned in the summary are part of the engineering
problem, not a fifth modeled version axis. The current schema has no firmware
release, source commit, or build artifact entity. Associating a code change with
the project digest used remains G11; do not infer that association from a version
label.

Board *revision* and board *variant* are deliberately **not** separate axes. An
earlier draft split them, which forced the system to decide which one a given
label meant — precisely the company-specific convention it must not encode. One
axis with opaque labels and declared lineage expresses both.

### 7.2 Access labels

Labels are a frozen compartment set plus `is_public`, with an empty non-public
default. One function generates prefixed labels for storage and filtering (I-2).
For a document, the set has exactly one entry when private and none when public.
The collection representation is retained for compatibility; multi-compartment
documents are rejected, including on read. Project/session scopes may contain
several compartments because they reference separately classified documents.
[Security §3](SECURITY-MODEL.md#3-classification) owns visibility rules.

The design was informed by Onyx's MIT-licensed access model. Its enterprise
permission-sync subsystem is not part of this design and must not be copied as
MIT-licensed code.

## 8. End-to-End Flow

### 8.1 Adding a document

Use the [README quickstart](../README.md#first-launch-and-document-ingestion).
The admission contract is in §6.4 and storage write ordering in
[Storage §7.1](STORAGE.md#71-ingest). Registration does not automatically adopt a
document into a board or project, or publish it remotely.

### 8.2 Registering hardware and a program

Use [Configuration guide](../README.md#configure-boards-and-projects) to create, edit, validate, and inspect snapshots.
Document selectors resolve to immutable pins before registration.

### 8.3 Provisioning and starting a session

Both setups use the provisioning design in §6.11. Available local configurations
can be browsed in the dashboard; `caiman project show NAME --compartment NAME`
lists a project's versions. The CLI does not currently provide `project list` or
`project versions`.

**Docker**

1. The engineer's own tools create the worktree and start its container with
   the worktree bind-mounted. Caiman is not involved (S-01).
2. In Caiman on the host, the engineer picks the container and the path inside
   it. Caiman resolves the host folder and runs the target checks (§6.11.3,
   §6.11.4).
3. The engineer picks the project, version, and mode; reviews; and provisions.
   `sync` resolves the pin set (§6.7) and writes `project.md`, `project.json`,
   and `documents/` into the host folder. The container sees them through the
   mount.
4. The agent starts in the container. `session start` restates the declaration
   (§6.10.2).

**Local**

1. The engineer's tools create the worktree.
2. Either provision from the host TUI as above, choosing the worktree instead of
   a container, or start the agent and use the session-start fallback: the agent
   asks for the project and mode, then runs `sync` (§6.10.2).
3. Later sessions in the worktree reuse the declaration and are reminded of it.

In both setups, changing the project, version, or mode means clearing or
re-provisioning (§6.11.6), then starting a new agent session.

### 8.4 During the session

The agent greps the documents, reads files, and cites by path plus locator.
Nothing resolves and nothing changes underneath the session (R-6).

Planned tool-use and stop hooks append to the access log (§6.10.3). These
recording hooks read no store, resolve nothing, and never block.

### 8.5 First run, end to end

For the implemented local workflow, follow [README.md](../README.md). Planned remote setup is in
[Storage §7.5](STORAGE.md#75-initialization-and-onboarding); the planned session flow is §8.3.
[ROADMAP.md](ROADMAP.md) owns sequencing and completion status.

### 8.6 Gaps in the end-to-end workflow

[GAPS.md](GAPS.md) tracks review tasks and their completion criteria.

#### Gap A — Ingestion input *(resolved by S-26 and S-27)*

Specified in §6.4.3; tracked as G12.

#### Gap B — Board and project authoring input *(resolved by S-28)*

Implemented in [Configuration guide](../README.md#configure-boards-and-projects); tracked as G13.

#### Gap C — Nothing reports what a pull brought

The planned pull workflow needs a summary of added objects and changed refs.

#### Gap D — Adopting a newer document into a project

Manual adoption is supported. Automated board/project version cascades still
need a reviewed interface and failure behavior; tracked as G15.

#### Gap E — No status or verification command

Standalone workspace-status and store-verification commands remain planned.
`sync --dry-run` describes a proposed workspace; it does not verify the store.

## 9. Interfaces

### 9.1 Command-line surface

Local commands are implemented; see [README.md](../README.md#configure-boards-and-projects)
for arguments and examples:

```text
caiman
caiman ingest [file]
caiman documents [--compartment NAME]
caiman board   configure | template | validate | show | export | new-version
caiman project configure | template | validate | show | export | new-version
```

The following surface is proposed and is not available yet. Remote configuration
and compartment setup follow S-33; final arguments remain to be
reconciled with [Storage §7.5](STORAGE.md#75-initialization-and-onboarding).

```text
caiman init [--remote URL]
caiman clone --remote URL
caiman compartment add|clone …
caiman push [compartment…]
caiman pull [compartment…]
caiman sync --project P --version V --mode open|sealed --into DIR
caiman clear --into DIR
caiman brief --project P --version V
```

`sync` and `clear` take a host path. Resolving a container path to its host
folder is a TUI convenience (§6.11.3); no container flag is proposed for the CLI.
Both commands run the target checks in §6.11.4.

Three groups, and the separation is deliberate:

| Group | Commands | Moves what |
|---|---|---|
| Store lifecycle | `init`, `clone`, `compartment add/clone`, `push`, `pull` | The store, between machines |
| Authoring | `ingest`, `board`, `project` | Content into the local store |
| Session | `sync`, `clear`, `brief` | The store into a workspace, and out of it |

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

Three proposed commands read JSON events on stdin and may write JSON to stdout.
Adapters translate harness-specific events; event schemas and coverage must be
specified and tested before this becomes a stable interface (G16/G21).

| Command | Fired on | Reads | Writes | May fail the session |
|---|---|---|---|---|
| `caiman session start` | Session start or resume | `cwd`, `session_id` | Context to inject: the restated declaration, a staleness warning, project choices, or an instruction to provision from the host (§6.10.2) | No |
| `caiman session record` | After a tool call | `session_id`, `tool_name`, `tool_input` | Nothing | No |
| `caiman session end` | Stop, SubagentStop | `session_id` | Nothing | No |

`caiman hooks install` writes the adapter configuration into the harness's
settings file. It prints exactly what it will add and requires confirmation,
because it modifies a file Caiman does not own.

The installed command calls `caiman` from `PATH`. It embeds no interpreter path
and no store path, so the same settings file works on the host and inside a
container. The current installer embeds both; inside a container the command
then fails and, correctly under R-13, injects nothing — which hides the
misconfiguration. This must change before the Docker setup is supported.

Two properties are contractual, not incidental: **no command exits non-zero in a
way that blocks a tool call** (R-13), and **`session record` performs no store
access** (§6.10.3), because it runs on every tool call.

### 9.3 Workspace contract

The harness and the agent both depend on the workspace layout, so it is an
interface rather than an implementation detail. It is specified in `STORAGE.md`
§7.3. The properties other components rely on:

- `project.md` exists and is loadable as agent context
- `project.json` carries resolved structure; its schema and visibility are pending G16/G17
- `documents/` paths identify the document and version; citations also need a
  source-appropriate locator (§6.4.2)
- `documents/_index.md` states what was omitted and why

The final path format must identify both part- and program-scoped documents and
support unambiguous access recording. The examples do not yet define how every
compartment set and digest is represented (G16/G21).

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
| Retired document `structure` or `requirements` metadata supplied | Reject new metadata | Existing snapshots are adapted in memory |
| Any pinned file cannot be materialized | `sync` fails and names the file | A document set missing one manual is indistinguishable, to an agent, from a document that never had it (R-11) |
| Project pins a digest no longer in the store | `sync` fails and names the digest | Broken pin. See `STORAGE.md` §8.5 for why this should be impossible |
| `push` to a remote that is not private | Hard error; nothing sent | Prevent publishing store contents publicly; repository boundaries follow S-33 (`STORAGE.md` §7.6) |
| `pull` brings a ref conflict | Fail; show both digests and document identities | Two machines repointed one name. Guessing would silently change what a name means |
| A hook fails, times out, or Caiman is not installed | The session continues; nothing is logged | R-13. A broken audit hook that halts work gets removed within a week, which is worse than a log with known gaps |
| `session start` finds a changed project ref or an unavailable pinned digest | Report the changed ref with both digests, or name the unavailable digest; do not block or repin | A moved label and a broken pin are different conditions (§6.10.2, R-15) |
| `session record` receives a `Bash` call | Representation unresolved (G22); I-10 prohibits content in logs | Commands can contain document text; do not implement the former verbatim-logging proposal |
| Two sessions log concurrently | Separate files keyed by session id | No contention, no locking |
| A provisioning target fails a check | Refuse or warn as §6.11.4 specifies; write nothing on refusal | The guards protect permanent history (I-3); a warning covers risks Caiman cannot rule out |
| The `docker` CLI is missing, lacks permission, or cannot reach the daemon | Offer a typed host path instead | Docker is a convenience for finding the folder, not a requirement |
| Clear or re-provision while agent sessions may be running | Warn unconditionally, then proceed; log the change | Running sessions keep what they read; Caiman cannot see container transcripts to tell (R-20) |

### 10.2 Edge cases worth naming

**A deviation document that does not cite requirement IDs.** The single-grep
correlation described in §6.3 depends on the deviation naming the requirement IDs
it amends. If a customer supplies deviations as prose without IDs, that behavior
silently does not happen: the agent finds the base requirement and never learns
it was amended. This is the most serious quality dependency in the design.
A proposed mitigation is an ingest warning for deviations without requirement-ID
references. It is not an implemented admission rule; D-12/G06 must settle how to
handle real deviation formats before adding it.

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

**Two sessions, same worktree.** They share one provisioned context and one
declared mode (§6.11.5). Re-provisioning replaces it for both, and neither
running session forgets what it read. Sessions that need different projects,
versions, or modes use separate worktrees.

**Several containers on one worktree, or one container on several.** The
context belongs to each worktree folder (§6.11.1). Which containers mount it
does not change what is in it.

---

## 11. Security Considerations

[SECURITY-MODEL.md](SECURITY-MODEL.md) owns the threat model and limitations.
The architectural requirements are R-3, R-7–R-9, R-13–R-14, and R-17–R-20.

### 11.1 Differential materialization is the mechanism

The explicit `open` or `sealed` mode determines which pinned documents are
written. It does not verify model authorization or isolate the agent process.

### 11.2 Fail-closed points

Missing mode writes nothing; missing labels exclude the document; a project
cannot materialize documents outside its declared compartments.

### 11.3 The brief is the one always-visible artifact

The generator reads metadata only and excludes customer identity (I-6).
Whether the remaining metadata can be public is under review in G17.

### 11.4 What the architecture does not protect against

An agent may have access to the underlying store or another workspace. Harness
transcripts can retain text after workspace cleanup. See Security §7 and G19–G20.

I-3 also requires materialized documents and caches to stay out of firmware Git
history, with ignore rules and a commit guard. This repository's design docs are
ordinary tracked files. S-33 separately defines the per-compartment store
repository boundary.

Label corrections create new manifest digests and require updated pins, cache
eviction, and workspace/brief regeneration. The procedure and its limits belong
in [Security §8](SECURITY-MODEL.md#8-reclassification-and-revocation); deleting a
workspace cannot retract transcripts or copies already published.

### 11.5 The Docker setup

In the local setup, workspace filtering is not a process boundary: the agent's
OS user can read the store. In the Docker setup, the store never enters the
container (R-18), so an `open` container has no compartmented document anywhere
in its filesystem — provided nothing else mounted into it holds one. This is
the first setup where the scope of G19's isolation claim can be stated as a
mount list rather than as good behavior. The mode is still a human declaration
(S-19); Docker enforces the result of that declaration, not its correctness.

Two new copies of documents appear with containers, and §6.11 addresses each:
the container's writable layer and images built from the worktree
(§6.11.3, §6.11.4). A root container with hardlinked documents can also modify
the store's cache (§6.11.4).

The local setup has a comparable option without Docker. Claude Code's sandbox
runtime wraps the whole agent process, including hooks, in an OS sandbox; a
configuration that denies reads of the store folder would keep the store out of
a local agent's reach. The cost is the session-start fallback, in which the
agent runs `sync` and therefore must read the store. Whether to document this
as a supported local configuration is open (§15.1).

## 12. Performance and Resource Considerations

| Operation | Cost driver | Notes |
|---|---|---|
| Ingest | Reading, hashing, and writing unchanged files | I/O bound, proportional to document size. Runs once per document version |
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
| A-1 | Ingest headingless content, content before the first heading, empty headings, duplicate full heading paths, and headings only inside code blocks | Accepted byte-for-byte without structural checks (§6.4.2) |
| A-2 | Supply retired document `structure` or `requirements` metadata; read and edit older snapshots containing them | New metadata rejected; old bytes and pins preserved; changed snapshots omit retired fields |
| A-3 | Resolve a project version; compare against its manifest | Includes board assembly and part documents plus project document pins, transitively (R-4) |
| A-4 | Resolve a bare project name | Returns the version list; resolves nothing (R-5) |
| A-5 | `sync` without `--mode` | Fails; workspace not created (R-7) |
| A-6 | `sync --mode open` against a project with specifications | No compartmented document in the workspace; `_index.md` records the omission |
| A-7 | Generate a brief for a project with compartmented documents | No document body text appears in the output (R-8) |
| A-8 | Generate a brief; search for the customer string from the project manifest | Absent (R-9) |
| A-9 | Materialize, then grep for a requirement ID amended by a deviation | Both the base requirement and the deviation are returned (§6.3) |
| A-10 | Materialize two project versions differing only in silicon revision; ask the same question | Corpora differ correspondingly |
| A-11 | Walk a materialized document tree for symlinked directories | None (R-12) |
| A-12 | Regenerate a workspace after repointing a document ref | The previously pinned digest still materializes (R-6, I-4) |
| A-13 | Run `session start` with the store reachable, in a worktree with no `.caiman/` | Injects project choices; does not fail, does not create anything |
| A-14 | Run `session start` after the selected project ref moves | Warns with old/new digests without changing existing workspace pins (R-15) |
| A-15 | Run `session start` in a repository with no Caiman configuration | Injects nothing; exits zero (R-16) |
| A-16 | `session record` for a read inside `documents/` | One access-log line with document, version, and compartment derived from the path |
| A-17 | `session record` for a read outside `documents/` | Nothing logged |
| A-18 | `session record` for a `Bash` call | Pending G22: represent unknown access without storing command content |
| A-19 | Make every hook command fail | The session completes normally (R-13) |
| A-20 | Grep an access log for content from any document it references | No document body text present (R-14) |
| A-21 | Ingest valid ATX/Setext headings, skipped levels, and repeated names under distinct parents | Accepted without changing the input; heading paths resolve (§6.4.2) |
| A-22 | Search a large materialized manual, read a bounded range, and cite a fact | Correct heading or requirement-ID citation without loading the entire file |
| A-23 | Submit a valid TUI form with source and converter sections empty or partially filled | Unknown fields omitted; registration succeeds without the original source file (S-26) |
| A-24 | Edit after review, cancel, or submit with missing labels/invalid fields | Edits are revalidated; cancellation and invalid input publish no version or ref; labels have no default (S-27) |
| A-25 | Invoke ingestion without an interactive terminal | Actionable error; no writes (S-27) |
| A-26 | Open the guided board editor and review without typing anything | The collected draft equals the manifest it was given, field for field (S-32) |
| A-27 | Type into the guided form, leave for raw JSON, and return | The Vim draft starts from what was typed, and what Vim returns comes back into the same form (S-32) |
| A-28 | Open a stored `caiman.board/1` board, or one with a `from`/`to` link, in the guided editor | Shown but not authored; only raw JSON is offered, so no endpoint is dropped and no stored version is migrated (S-31) |
| A-29 | Edit a board with declared lineage in the guided form, which has no lineage field | `derives_from` and `relation` survive unchanged (S-32) |
| A-30 | Type a vendor that is not in the common list, in any case | Accepted as declared; the list suggests a canonical spelling and constrains nothing (I-8, S-32) |
| A-31 | Point little caiman at a transcript whose tool results and shell commands contain a restricted string | Counts and locators only; the string is not retained or shown, and nothing is written (R-14, I-10) |
| A-32 | Show little caiman's usage view | The absence-of-record notice is visible; a materialized file whose bytes match no stored blob is flagged as modified (§6.10.4, R-6) |
| A-33 | Provision into a container path that is in the writable layer, a named volume, or `tmpfs`, or through a non-local daemon | Refused with the reason; nothing written anywhere (R-17) |
| A-34 | Provision into a container path on a bind mount | Written to the resolved host folder; no `docker cp`, `exec`, or other write command is invoked (R-17, §6.11.3) |
| A-35 | Provision into a folder that is not a worktree top, where `.caiman/` is not ignored, or where the pre-commit guard is inactive | Refused; nothing written (R-17, I-3) |
| A-36 | Provision a worktree whose container mounts a path at or below `.caiman/` | Refused (§6.11.4) |
| A-37 | Provision a worktree whose root container would receive hardlinks, or whose `Dockerfile` has no `.dockerignore` entry for `.caiman/` | Warning shown before writing (§6.11.4) |
| A-38 | Open the provisioning TUI with a remembered compartment and a previously provisioned project | No project, version, or mode is preselected (R-7, I-7, S-29) |
| A-39 | Run with the `docker` CLI missing or failing | Typed host path is offered; no error ends the flow |
| A-40 | Run `session start` in a container with no store and no `.caiman/` | Says to provision from the host; lists no projects; exits zero |
| A-41 | Run `session start` in a provisioned worktree, with and without the store | Restates project, version, digest, mode, and compartments; staleness is checked or reported as unverified (R-19) |
| A-42 | Clear and re-provision a worktree | The running-session warning is shown; both acts appear in the materialization log; no partial workspace is visible at any point (R-20, R-11) |
| A-43 | Inspect the command written by `hooks install` | Calls `caiman` from `PATH`; contains no interpreter or store path (§9.2) |
| A-44 | Point little caiman on the host at a transcript whose working directory does not exist on the host | States that reads cannot be matched here; does not report an absent `.caiman/` (§6.11.7) |
| A-45 | List the container's filesystem after provisioning in `open` mode | No store path and no compartmented document (R-18) |
| A-46 | Run `session start` and little caiman against a workspace with an unknown format version | Both name the found and supported versions; `session start` exits zero (§6.11.7, R-13) |
| A-47 | Provision a worktree, then repoint its project version ref | The host TUI marks the worktree as pinned to a digest its ref no longer names; the workspace is unchanged (§6.11.8, I-4) |

A-9 is the test that covers the highest-value normative behavior, and A-12 covers
the reproducibility property the whole pinning model exists for.

---

## 14. Alternatives Considered

Rationale belongs in [DECISIONS.md](DECISIONS.md): S-18 rejects an MVP retrieval
server; S-07 rejects a repository lockfile; S-13 separates boards and projects;
S-15 rejects inferred precedence; D-03 defers semantic indexing.

## 15. Risks and Open Questions

### 15.1 Open questions

Track unresolved formats (`project.json`, omission notices, access logs) in G16,
subagent and shell-read audit coverage in G21, and content-free shell logging in
G22. G16/G17 must also define metadata visibility for resolved JSON and omission
notices; G16/G21 must define document-path attribution and startup lookup inputs.
G18 covers safe reuse of saved selections on resume versus a new session; §6.11.5
proposes an answer.

Provisioning (§6.11) is proposed in D-14, which must be settled before
implementation. It changes three recorded positions:

| Position | Today | Proposed |
|---|---|---|
| Primary selection path (S-23) | Session-start hooks inject choices; the agent asks | The host TUI provisions the worktree; the session-start path is a local-only fallback |
| Scope of a mode declaration (G18, §6.10.2) | One session; a saved selection must not authorize a new session | The worktree, until cleared or re-provisioned; restated at every session start |
| Docker and S-01 | Not addressed | Read-only `docker ps` and `docker inspect` are inside S-01; creating, starting, execing into, or copying into containers is not |

Also open for these setups:

- **Multi-repository firmware workspaces.** Zephyr `west`, Yocto `repo`/`kas`, and
  Android `repo` workspaces have a root that is not a git repository, so §6.11.4
  refuses it, while agents often run in a member repository whose `.caiman/`
  is absent. Options: provision into the manifest or application repository, or
  let session start search parent folders, which risks finding another
  project's context. Blocks Caiman on these workspaces (G29).
- **Transcript mounts in containers.** Keeping or discarding container
  transcripts is G20's decision (§6.11.7).
- **Host/container version compatibility.** Which workspace format versions a
  given `session start` accepts, and what it says otherwise (G27).
- **Stale pins in long-lived worktrees.** How the host TUI surfaces them (G28).
- **The sandbox runtime as a local configuration.** Whether to document a
  store-denying sandbox runtime setup, at the cost of the session-start
  fallback (§11.5).
- **Cloud-synced worktrees.** A worktree inside an iCloud Drive, Dropbox, or
  OneDrive folder uploads the documents. Detection is possible only for known
  locations; whether §6.11.4 should warn on them is undecided.
- **Other setups.** Remote SSH machines, cloud development environments, cloud
  agents, and CI all need a store on another machine. They wait for Git
  transport (S-35) and a decision on `sealed` mode on hardware the engineer does
  not control.
Repository boundaries are settled by S-33; code-to-context traceability remains G11.
Decide how to collect retrieval misses before relying on the §15.2 trigger.
[GAPS.md](GAPS.md) owns completion criteria; [DECISIONS.md](DECISIONS.md) records
any resulting policy choice.

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
| A deviation document without requirement IDs (§10.2) | Search may miss an amendment | D-12/G06 must decide representation and warnings; ingest lint is proposed |
| Hand-declared features drift from the program | The brief asserts something false, with authority | Author-by-delta means a new project version starts from its predecessor (S-11); the brief is regenerated per session and never hand-edited |
| A converter silently drops content | Wrong facts that look right, with valid citations | Converter provenance, when supplied, helps identify affected artifacts; ingest does not validate content or completeness. Spot-check against the source outside ingest |
| Source-document navigation proves inadequate and the miss log is not implemented | The trigger in §15.2 cannot fire; the decision reverts to intuition | Implement the miss log with the rest of phase 3 |
| Harness residue (§11.4) | Materialization is not reversible | Out of scope here. Tracked in `harness.md`; the policy question belongs to `SECURITY-MODEL.md` |
| Hook latency on every tool call (§12) | Perceptible slowdown across a whole session; pressure to remove the hooks | Constrain `session record` to string parsing and an append. Measure before shipping; fall back to transcript-derived logging at `Stop` if needed |
| The access log is read as an accounting rather than as evidence | A false negative treated as proof a document was never read | State the incompleteness wherever the log is surfaced, not only in this document (§6.10.4) |
| Subagent reads missing from the log | An audit gap that looks like completeness | Verify coverage before relying on it (§15.1) |
| `hooks install` writes to a settings file Caiman does not own | Surprising edits to the engineer's configuration | Print the exact change and require confirmation (§9.2) |
| A worktree's declared mode outlives the decision behind it | A later session runs an agent not cleared for the worktree's compartments | Restate the declaration at every session start (R-19); clearing is always available (§6.11.5) |
| The store is mounted into a container to make hooks or `sync` work there | Every compartment within reach of an `open` session | R-18; §6.11.7 lists what runs in the container without a store |
| Docker CLI output differs across versions, Podman, or Docker Desktop | A container path resolves to the wrong host folder | Accept only `bind` mounts with an absolute local source; show both paths at review (§6.11.2) |
| Context budget growth in the brief | Every added line is paid on every turn of every session | Keep detail in `project.json` and the documents; treat brief size as a reviewed budget, not an incidental outcome |
