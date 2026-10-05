# Caiman Architecture

**Current pod model:** [PODS.md](PODS.md) owns local folders, optional per-pod
Git sharing, and the owning-pod/public reference boundary. Filesystem and Git-host
permissions govern access; Caiman has no separate application authorization layer.

**Current document model:** [DOCUMENT-METADATA.md](DOCUMENT-METADATA.md) supersedes
the historical document-manifest pin semantics and hardware attachment restrictions.
All metadata edits create complete manifests; references keep bodies fixed and
show current approved metadata.

**Status:** Local ingestion, authoring, pod Git clone/sync, and startup guidance
hooks are implemented. Session materialization and the portable workspace adapter
remain planned. S-39 settles the workflow; [CONTAINER-CONTEXT.md](CONTAINER-CONTEXT.md)
is its canonical specification for both local and container agents.

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
set and declared deviations, with collections helping organize the documents. Document ingestion and search
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
| Acting as an enforcement boundary | The human selects context and a suitable agent; Caiman does not attest models | S-19 |
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
| R-2 | Destination pods are selected explicitly, never inferred from content | I-8 |
| R-3 | References stay within the owning pod and public; missing dependencies fail | I-1, I-2 |
| R-4 | A project version resolves to a complete pin set, including everything its board version pins | S-07 |
| R-5 | A bare board or project name returns the list of versions and does not resolve | I-7 |
| R-6 | Each installed context revision records resolved identities and fixed document bodies; only an explicit switch installs another revision | I-4, S-39 |
| R-7 | Provisioning requires an explicit session and a host-authorized context selection | S-39 |
| R-8 | The brief generator has no access to document content | I-6 |
| R-9 | A generated brief contains no customer identity, only the program codename | I-6 |
| R-10 | Lineage, precedence, and feature relationships are declared and rendered, never computed | I-8 |
| R-11 | Every pinned document is materialized; partial materialization is an error | I-9 |
| R-12 | Ordinary recursive search reaches every materialized document — no symlinked directories or silent omissions | I-9 |
| R-13 | Hooks never deny a tool call and never fail a session | I-10, S-19 |
| R-14 | The access log records document identities, never document content | I-10, I-6 |
| R-15 | Catalog refresh and moved version labels never silently change installed session pins | I-4, S-39 |
| R-16 | A repository with no Caiman configuration has its sessions unaffected | — |
| R-17 | Provisioning writes only to a host folder at the top of a guarded git worktree; never into a container's filesystem or an image | I-3, I-9 |
| R-18 | The store and host configuration stay on the host; only the workspace adapter and published session files enter the container | S-39 |
| R-19 | Startup reports that session’s installed selection and available choices; resume retains identity and new sessions get independent folders | S-39 |
| R-20 | Switches coordinate readers, recover complete installations, and distinguish installed from acknowledged revisions | S-39, I-9 |

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
complete selected document set and metadata on the host. The open host TUI
processes registrations and context requests; agents read ordinary files directly.

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
                  │ 5 MATERIALIZE    │  complete selected pin set
                  └────────┬─────────┘
                           ▼
              <worktree>/.caiman/sessions/<session-id>/context/
                project.md      brief, loaded into agent context
                project.json    resolved structure, machine-readable
                documents/      unchanged document files
                           │
                           ▼
              harness → coding agent (reads, greps, cites)
                           │
                           └── workspace adapter → request/result files
                                                   ↕
                                              host Caiman TUI
```

Detailed read auditing is separate planned work (§6.10.3).

### 6.2 Component responsibilities

| Component | Owns | Does not own |
|---|---|---|
| **Ingest** | Metadata validation, hashing, unchanged-file registration | Conversion, splitting, maps, AI processing, classification decisions |
| **Register** | Board and project models, features, declared relationships, lineage | Inferring any of them |
| **Store** | Immutability, content addressing, pod ownership | Query, search, ranking |
| **Resolve** | Name→digest, transitive pin set, version listing | Choosing a version on the user's behalf |
| **Materialize** | Per-session context assembly, linking, brief rendering | Session lifecycle, agent process |
| **Provision** | Initializing the host worktree and publishing session context revisions (§6.11) | Creating worktrees or containers; writing into a container |
| **Session integration** | Session registration, context requests, and acknowledgements; separate planned access recording | Blocking tools or managing the agent process; the per-read recorder never accesses the store |
| **Harness and environment** (external) | Worktree and container creation, launching, publishing hook events | Deciding what an agent may see |

### 6.3 Why there is no server

The agent searches ordinary files. [S-18](DECISIONS.md#s-18-the-filesystem-is-the-interface-there-is-no-server-in-the-mvp)
records the decision; §15.2 defines when to revisit retrieval.

Searching a requirement ID can return both its base specification and an
amending deviation, provided the deviation names that ID. For example:

```bash
rg -n 'REQ-FLASH-0142' .caiman/sessions/<session-id>/context/documents/
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
may start empty. Pod Git sharing remains explicit and separate from saving.

The form has four steps:

1. **File.** Select one file of any format. Show its basename and file-read
   results; do not ask for a second original-source filename.
2. **Document.** Pick an existing project or board part to populate declared
   metadata, or enter document identity manually. Offer creation of a new board
   or project and return to the retained ingestion form. Enter a document name,
   description, and version. All roles use the same document form. Project selection supplies
   the program and destination pod; board-part selection supplies issuer,
   part, and any declared silicon revision. Silicon revisions are optional when
   not applicable or unknown; display that absence honestly. Choose a destination
   pod; public is the permanent default. No access labels are collected.
3. **Optional provenance.** A skippable section for original-source checksum and
   page count, and converter name. Each
   may be left unknown. Never infer these from the filename or missing fields.
4. **Review and register.** Show entered metadata and destination pod, unknown optional
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

A board describes hardware; a project combines pinned boards with documents
in one owning pod. [README.md](../README.md#configure-boards-and-projects) owns editing workflows; [Storage §6.4](STORAGE.md#64-manifest-schemas) owns the
serialized manifests.

#### 6.5.1 Board — hardware only

Parts are identified by role. Aliases connect those roles to schematic or
procurement identifiers. Boards pin documents from their owning pod or public for both parts and the
assembly; they contain no customer or program fields. Preserve vendor peripheral
names so they can be searched in the manual.

#### 6.5.2 Project — the session unit

A project owns one pod and pins one or more board versions and a specification set
from that pod or public. It declares no precedence among documents (S-36). A program may run on several boards, or on
one board at several versions; each pin is explicit (S-34). Separate projects can
share a board while carrying different customers' requirements.

#### 6.5.3 Collections and retained features

Collections organize documents by capability, subsystem, or workflow. The shared
picker shows documents and collections together. Projects retain stable collection
references and read their current membership; direct document attachments remain
independent. Membership additions/removals and collection renames reach referencing
projects without rewriting their snapshots. Historical collection resolution uses
the original digest retained with each reference. Overlaps are deduplicated and
missing dependencies fail the complete set. Boards and parts still expand selected
groups into direct documents. Collection editors offer individual documents only.

Structured features are no longer part of normal authoring (S-14). Existing
`features` declarations are preserved and validated, and raw JSON remains available
to edit them. New projects omit the optional field. Collections do not acquire
feature scope, requirement IDs, hardware mappings, or implementation status.

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

Each pod is a local folder with optional Git sharing. A pod repository contains
only that pod's data; dependencies are referenced without copying. The Git host
owns remote permissions. [PODS.md](PODS.md) supersedes the older S-33/S-35
compartment transport design.

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
| Each context revision pins once | Refreshing a catalog or moving a label does not change installed context. Explicit switching installs another revision and requires an agent reread (S-39) |
| A bare name never resolves | `falcon` with no version returns the version list (R-5) |
| Resolution checks pod routes | References may target only the owning pod and public; missing pods or fixed bodies are errors (I-1, I-2) |

Code-to-context traceability remains open (G11). One proposal is a commit trailer
written by the harness from the session's project digest, such as
`Caiman-Project: falcon@sha256:9f3c…`. Neither that mechanism nor a firmware-release
model is implemented.

### 6.8 Materialize

The host provisioner resolves the selected project and writes its complete pinned
document set to `.caiman/sessions/<session-id>/context/`, together with a
metadata-only brief and resolved structure. There is no open/sealed mode or
silent filtering of missing dependencies. Pods and document references follow
[PODS.md](PODS.md) and [DOCUMENT-METADATA.md](DOCUMENT-METADATA.md).

[Session context](CONTAINER-CONTEXT.md) owns initialization, selection, requests,
installation coordination, and acknowledgements. [Storage §7.3](STORAGE.md#73-materialize)
owns staging, linking, recovery, and complete-file guarantees. Final command and
wire schemas remain to be specified; this is not an available CLI command.

Clones are preferred, then read-only hardlinks where appropriate; cross-filesystem
copying is supported. Documents are read-only, document directories are never
symlinks, and a missing pinned file fails the entire installation. `project.json`
and the document index describe the installed revision; their final schemas and
metadata visibility remain G16/G17.

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

## Session context
Full pinned document set for this selected project is available.
Selection does not verify which model is running or whether it is authorized.

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
Documents: .caiman/sessions/<session-id>/context/documents/ — each document directory contains one unchanged
file at its manifest path, preserving its extension. For text, search identifiers
or headings and read the relevant range with surrounding qualifications.
Use a suitable reader for other formats. Paths identify the document and version; cite
a source-appropriate locator. Do not read a whole manual
into context. There are no generated maps.
Resolved structure: .caiman/sessions/<session-id>/context/project.json

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

If the task requires documents outside the selected context, the agent asks the
user to select an appropriate published context. It must not invent missing
facts. A failed installation preserves the prior context and reports the missing
dependency; it does not publish a brief claiming an incomplete set is ready.

The brief has three constraints:

- **Metadata visibility under S-09.** The brief describes the selected session
  context. Whether every proposed metadata field is safe to expose remains G17;
  metadata is not automatically non-confidential.
- **Codename only.** Customer legal identity stays in the owning pod’s project
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

The workspace adapter translates harness events and exchanges request/result
files with the host TUI. Provisioning and store access stay on the host; the
container uses a supported runtime without the full Caiman package. Existing
startup guidance hooks are not this adapter. The accepted lifecycle, runtime
verification, and fallback behavior are in [Session context](CONTAINER-CONTEXT.md).

#### 6.10.2 Session start

Startup registers a stable session identity and supplies its installed context,
exact brief path, available catalog choices, and instructions for the agent to
ask the user. A hook stays short and never waits for interactive selection.
The agent submits requests after the user answers, waits for installation, then
rereads and acknowledges the revision. The same flow applies locally and in
containers; there is no separate agent-side provisioning fallback.

Resume reuses the session folder. New and forked sessions get independent
folders; subagents share their parent's context unless explicitly given their
own. When the host is unavailable, installed context remains usable but new
provisioning waits. Uninitialized worktrees receive setup guidance. Hook failure
never blocks the harness. [Session context §§3–7](CONTAINER-CONTEXT.md#3-one-worktree-several-sessions)
own the detailed contract.

#### 6.10.3 Observed reads (separate planned work)

Detailed read auditing is not part of the initial workspace adapter. A later
harness adapter can attribute direct reads from session-relative document paths
and append content-free identity records. The exact path encoding and event
schema must be defined in G16/G21 before relying on them. Record stable pod and
document identities, fixed body versions, session identity, and context revision;
never query the host store on every tool call.

Shell reads, missing hooks, and subagent coverage require explicit measurement.
Do not infer a complete document-read history from hook installation or a stop
event. Container-to-host collection and runtime dependencies remain separate
implementation work; they cannot introduce a store or full Caiman requirement
into the accepted initial adapter workflow.

[Security §9](SECURITY-MODEL.md#9-audit) owns log content and storage limits.

#### 6.10.4 What the access log is and is not

It is a **second layer** over the materialization log, not a replacement.

| | Materialization log | Access log |
|---|---|---|
| Answers | What Caiman materialized | Which managed reads were observed |
| Produced by | `sync`, deterministically | Hooks, during the session |
| Complete? | Installed set only; not all reachable files | **No** — see below |
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
versions, pods — the same metadata-only rule as the brief (I-6). An audit
record containing an excerpt of a specification would be a copy of the
specification in a file nobody thinks of as one.

### 6.11 Provisioning a worktree

S-39 settles the workflow. [CONTAINER-CONTEXT.md](CONTAINER-CONTEXT.md) is the
single specification for initialization, session identity, context selection,
request/result files, switching, recovery, and cleanup.

The host TUI initializes an existing worktree and publishes context choices.
Each session has its own folder; the host prepares documents and a container
reads them through the worktree bind mount. The TUI remains open to process
requests. The container needs only the workspace adapter's verified runtime,
not Caiman, the store, a Docker socket, or host shell access.

Local agents use the same session contract. Worktree and container creation,
agent execution, transcript management, and automatic interruption remain
external. Worktree/mount checks are specified in
[Session context §4](CONTAINER-CONTEXT.md#worktree-and-mount-checks).

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

### 7.2 Pod ownership

Each artifact belongs to one pod. Dependencies may target that pod or public;
public is self-contained. Stable pod IDs prevent folder/display-name changes
from retargeting references. No document access labels, caller compartment lists,
or model policy are part of the current design. [PODS.md](PODS.md) owns the
format; [Security](SECURITY-MODEL.md) owns its limits.

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

Follow the accepted [session workflow](CONTAINER-CONTEXT.md#4-first-time-setup):
initialize the host worktree, publish choices, keep the TUI open, register each
agent session through its adapter, and select context in the TUI or conversation.
The host installs that session's files; the agent reads its exact brief path.
This workflow is planned, not an available command sequence.

### 8.4 During the session

The agent searches and reads its session's documents and cites source locators.
An explicit context switch uses the same host provisioner and requires a reread
and acknowledgement. Other sessions retain their selections. Pausing affected
readers and handling old conversation content follow
[Session context §6](CONTAINER-CONTEXT.md#6-changing-context-during-a-session).
Detailed tool-use auditing remains separate planned work (§6.10.3).

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
A provisioning preview would describe the selected context; it would not
replace store verification. Final CLI arguments remain unspecified.

## 9. Interfaces

### 9.1 Command-line surface

Local commands are implemented; see [README.md](../README.md#configure-boards-and-projects)
for arguments and examples:

```text
caiman
caiman ingest [file]
caiman documents [--pod NAME]
caiman board   configure | template | validate | show | export | new-version
caiman project configure | template | validate | show | export | new-version
```

Pod setup and Git sharing follow [PODS.md](PODS.md) and the implemented commands
in README. Workspace initialization and per-session provisioning are planned.
Their final CLI arguments are not settled. `sync` in design discussions denotes
the host materializer, distinct from pod Git sync; it is not a command the
container agent must run. TUI changes and adapter requests call the same host
service with an explicit session and context choice.

### 9.2 Hook contract

The portable adapter contract is defined in
[Session context](CONTAINER-CONTEXT.md#5-starting-a-session). Hooks register
sessions and return guidance; subsequent agent tool calls submit requests and
acknowledgements. Wire schemas, supported runtimes, and harness activation need
verification before implementation.

The current hook installer provides local startup guidance and embeds the host
Python executable and store path. It cannot be used unchanged in containers.
The planned workspace adapter runs using the container's verified runtime and
shared-worktree paths. Initialization preserves existing harness hooks.

Hooks never deny tools or fail sessions. Planned read-recording hooks are
content-free and perform no store access; they are outside the initial adapter
scope. No claim of audit coverage follows from installing startup guidance.

### 9.3 Workspace contract

The harness and the agent both depend on the workspace layout, so it is an
interface rather than an implementation detail. [Session context §3](CONTAINER-CONTEXT.md#3-one-worktree-several-sessions)
owns the workspace layout; Storage §7.3 owns each session context’s files. The properties other components rely on:

- `project.md` exists and is loadable as agent context
- `project.json` carries resolved structure; its schema and visibility are pending G16/G17
- `documents/` paths identify the document and version; citations also need a
  source-appropriate locator (§6.4.2)
- `documents/_index.md` inventories the complete installed document set; missing dependencies fail installation

The final path format must identify both part- and program-scoped documents and
support unambiguous access recording. The examples do not yet define how every
stable pod identity and body digest is represented (G16/G21).

---

## 10. Failure Handling and Edge Cases

Storage-level failures — interrupted ingest, corruption, cross-volume
materialization — are covered in `STORAGE.md` §8. This section covers failures in
the layers above it.

### 10.1 Error conditions

| Condition | Behavior | Rationale |
|---|---|---|
| Missing session or context choice | Reject provisioning; nothing written | No implicit shared-worktree selection (R-7) |
| Bare project or board name | Return the version list; do not resolve | Resolving to "latest" against a frozen program is a compliance failure (R-5) |
| Document lacks source structure or text extraction | Accept readable bytes unchanged; require a source-appropriate locator when citing | Registration is not certification of readability or factual correctness (I-5) |
| Retired document `structure` or `requirements` metadata supplied | Reject new metadata | Existing snapshots are adapted in memory |
| Any pinned file cannot be materialized | `sync` fails and names the file | A document set missing one manual is indistinguishable, to an agent, from a document that never had it (R-11) |
| Project pins a digest no longer in the store | `sync` fails and names the digest | Broken pin. See `STORAGE.md` §8.5 for why this should be impossible |
| Pod Git sync fails | Report the failure and preserve local work | Git-host permissions own remote access; public pod does not mean public repository |
| `pull` brings a ref conflict | Fail; show both digests and document identities | Two machines repointed one name. Guessing would silently change what a name means |
| A hook fails, times out, or Caiman is not installed | The session continues; nothing is logged | R-13. A broken audit hook that halts work gets removed within a week, which is worse than a log with known gaps |
| A catalog selection is stale or a dependency unavailable | Reject the request, retain installed context, and explain the error | No silent substitution |
| `session record` receives a `Bash` call | Representation unresolved (G22); I-10 prohibits content in logs | Commands can contain document text; do not implement the former verbatim-logging proposal |
| Two sessions log concurrently | Separate files keyed by session id | No contention, no locking |
| A provisioning target fails worktree/mount checks | Refuse publication and name the failed check | Session context §4 owns the checks |
| The host TUI is closed | Existing context stays usable; new requests report unavailable/expiry | No hidden daemon |
| Change context while readers may be active | Coordinate the affected agent and subagents before installation | The host cannot automatically interrupt a harness |

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

**An agent that ignores the stop-and-ask rule.** In a session lacking a needed source the
brief instructs the agent to stop rather than work around an unavailable
specification. Nothing enforces this. The material is genuinely absent, so the
agent cannot cite what it does not have — but it can still guess, and a guess
about a customer requirement is exactly the failure mode the system exists to
prevent. This is a residual risk of the human-routing model (S-19), not a defect
to be fixed in the architecture.

**Two sessions, same worktree.** Each has an independent context folder and
selection. Switching A does not change B. Shared filesystem access can still
let either agent read the other folder, so separate selections do not provide
permission isolation. Use separate filesystem boundaries where isolation is
required. Several containers mounting a worktree see the same session folders;
container identity does not determine context ownership.

---

## 11. Security Considerations

[SECURITY-MODEL.md](SECURITY-MODEL.md) owns the threat model and limitations.
The architectural requirements are R-3, R-7–R-9, R-13–R-14, and R-17–R-20.

### 11.1 Pod and session boundaries

Pods define ownership and permitted dependency routes. The host controls the
choices published for a worktree and whether requests can select them
automatically. Shared metadata cannot expand that delegation. The host validates
requests and rejects destination traversal and symlink escapes. Caiman does not
attest models or enforce document permissions between sessions.

### 11.2 Complete context and metadata

Every pinned document must be available before installing a revision. The brief
reads metadata only and excludes customer identity (I-6); field visibility remains
G17. Invalid or stale requests preserve installed context.

### 11.3 Filesystem and container limits

The store remains on the host. The shared worktree exposes its session folders
to any process able to read it. Keep generated content out of firmware Git
history and container images. Read-only hardlinks do not resist owner/root
writes. Mount and guard requirements belong to
[Session context §4](CONTAINER-CONTEXT.md#worktree-and-mount-checks).

### 11.4 Cleanup is not revocation

A context switch or folder deletion cannot erase conversation content,
transcripts, copied files, or Git history. Use a fresh session when previous
context must be excluded; filesystem isolation is a separate requirement.
See [Security §7](SECURITY-MODEL.md#7-known-gaps) and G19–G20.

### 11.5 Local and Docker agents

Both use host provisioning and the same adapter protocol. A local process may
have wider filesystem access than a container. Neither setup gains an access
boundary merely by using per-session folders. Document the actual mount and
filesystem permissions before claiming isolation.

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
| A-5 | Request provisioning without a session or context selection | Rejected; no documents written (R-7) |
| A-6 | Provision a project from one pod plus public | Every pinned document present; unrelated documents absent |
| A-7 | Generate a brief for a project with private-pod documents | No document body text appears in the output (R-8) |
| A-8 | Generate a brief; search for the customer string from the project manifest | Absent (R-9) |
| A-9 | Materialize, then grep for a requirement ID amended by a deviation | Both the base requirement and the deviation are returned (§6.3) |
| A-10 | Materialize two project versions differing only in silicon revision; ask the same question | Corpora differ correspondingly |
| A-11 | Walk a materialized document tree for symlinked directories | None (R-12) |
| A-12 | Regenerate a workspace after repointing a document ref | The previously pinned digest still materializes (R-6, I-4) |
| A-13 | Start a session in an initialized worktree | Adapter registers it and supplies its selection and catalog choices |
| A-14 | Refresh the catalog after a project label moves | Existing session pins unchanged; stale requests rejected |
| A-15 | Start without workspace initialization | Installed adapter gives setup guidance; absent hooks leave harness unaffected |
| A-16 | `session record` for a read inside `documents/` | One access-log line with document, body version, and pod derived from the session document path |
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
| A-33 | Target a container layer or named volume instead of a host bind-mounted worktree | Unsupported; no provisioning there |
| A-34 | Provision through the host worktree | Container reads session files through the bind mount; no Docker write commands |
| A-35 | Initialize without Git exclusion or the commit guard | No document publication until worktree checks pass |
| A-36 | Mount a replaceable context directory separately | Unsupported mount configuration reported before publication |
| A-37 | Use hardlinks or a container build context | Link risks reported; generated documents excluded from builds |
| A-38 | Start two sessions in one worktree | Independent folders and visible selections; changing A leaves B unchanged |
| A-39 | Initialize without Docker CLI installed | Host-path initialization works without Docker discovery |
| A-40 | Start an adapter in an uninitialized container worktree | Setup guidance; no hook failure blocks the harness |
| A-41 | Resume a registered session | Exact session identity and installed revision recovered |
| A-42 | Switch context with a coordinated agent | Complete recoverable installation, matching result, then reread and acknowledgement |
| A-43 | Inspect the portable workspace adapter configuration | No embedded host interpreter/store path; runtime validated in target container |
| A-44 | Use different host/container paths | Relative protocol paths resolve correctly; unsupported audit mapping reported separately |
| A-45 | Inspect container dependencies | No store, host configuration, Docker socket, or full Caiman package required |
| A-46 | Use an unsupported protocol version | Compatibility error; installed context preserved; harness continues |
| A-47 | Move a project version ref after installation | No automatic repinning (I-4) |

The request, retry, crash-recovery, stale-acknowledgement, and container checks
in [Session context §9](CONTAINER-CONTEXT.md#acceptance-scenarios) are also required.

A-9 is the test that covers the highest-value normative behavior, and A-12 covers
the reproducibility property the whole pinning model exists for.

---

## 14. Alternatives Considered

Rationale belongs in [DECISIONS.md](DECISIONS.md): S-18 rejects an MVP retrieval
server; S-07 rejects a repository lockfile; S-13 separates boards and projects;
S-15 rejects inferred precedence; D-03 defers semantic indexing.

## 15. Risks and Open Questions

### 15.1 Open questions

The host/per-session workflow is settled by S-39. Remaining implementation
choices are tracked in [Session context §9](CONTAINER-CONTEXT.md#9-implementation-scope-and-remaining-decisions):
adapter runtime, harness identity and activation, request schema, catalog
management, and recovery through real bind mounts.

G16/G17 cover generated formats and metadata visibility; G21/G22 cover audit
coverage and content-free logging. G27 covers protocol compatibility, G28 stale
pin presentation, G29 multi-repository workspace roots, and G20 transcript
retention. Remote/cloud agents and CI need their own supported filesystem and
host-provisioning arrangement; they are not established by local Docker support.
Code-to-context traceability remains G11. [GAPS.md](GAPS.md) owns completion
criteria; record any new policy decisions in DECISIONS.md.

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
| Hook latency on every tool call (§12) | Perceptible slowdown across a whole session; pressure to remove the hooks | Keep any future read recorder content-free and bounded. Measure before shipping; fall back to transcript-derived logging at `Stop` if needed |
| The access log is read as an accounting rather than as evidence | A false negative treated as proof a document was never read | State the incompleteness wherever the log is surfaced, not only in this document (§6.10.4) |
| Subagent reads missing from the log | An audit gap that looks like completeness | Verify coverage before relying on it (§15.1) |
| `hooks install` writes to a settings file Caiman does not own | Surprising edits to the engineer's configuration | Print the exact change and require confirmation (§9.2) |
| An agent keeps using an older context after a switch | Wrong sources inform work | Separate installed and acknowledged revisions; require reread; use fresh sessions to exclude old context |
| The store is mounted into a container to make integration work | Unselected source documents become reachable | Keep provisioning on the host and validate the portable adapter (S-39) |
| Bind-mount behavior or adapter runtime differs across environments | Requests or updates fail | Verify the acceptance scenarios in the supported container setup |
| Context budget growth in the brief | Every added line is paid on every turn of every session | Keep detail in `project.json` and the documents; treat brief size as a reviewed budget, not an incidental outcome |
