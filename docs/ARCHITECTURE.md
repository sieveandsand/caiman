# Architecture

## Shape

Four layers, and no server.

```
  converted markdown + provenance      board definition     project definition
  (user supplies; conversion             parts, roles,       board version +
   is external)                          links               specs + features
        │                                     │                     │
   [1] INGEST ── chunk, label,           [1b] REGISTER ─────────────┘
        │        attach locators              │
        │                                     │
   [2] STORE ────── immutable versioned artifacts
        │           documents, board versions, project versions
        │
   [3] RESOLVE ──── a project version *is* the pin set
        │
   [4] MATERIALIZE ── into the session's workspace, filtered by agent profile
        │
        │     .caiman/project.md      the brief — loaded into agent context
        │     .caiman/project.json    resolved structure, for the agent to read
        │     .caiman/corpus/         documents + generated maps
        │
   harness ──> coding agent   (reads, greps, cites)
```

**The filesystem is the interface.** There is no MCP server in the MVP and no
retrieval service. `caiman sync` writes a session's context to disk; the agent
uses the file tools it already has.

This is S-04 followed to its conclusion. Exact-identifier lookup is a lexical
problem — that was always the argument for register identifiers, and stable
requirement IDs (S-06) made the normative half lexically exact too. With both
halves greppable, a retrieval service would be adding a round-trip to do worse
than `grep`, while its tool schemas sat in context on every turn costing more
than the brief they were meant to supplement.

The harness — a session manager, eventually something Xirp-shaped — asks which
project and which agent, creates the worktree, calls `caiman sync`, and launches
the session. Caiman does not manage sessions. It answers questions and writes
files.

## [1] Ingest

Input: **markdown that has already been converted from the source document**,
plus an assertion of its provenance — issuer (vendor or OEM), part or program,
document type, document version, applicable silicon revisions, **public or
compartment labels**, source checksum, and the identity and version of the
converter that produced it.

Conversion is explicitly outside Caiman (`DECISIONS.md` D-01, retired). Two
consequences follow, and both matter:

**Converter identity is provenance.** Record which tool and version produced the
markdown. When a better converter arrives you need to know which artifacts
predate it, and when a conversion turns out to have dropped content you need to
know everything it touched.

**A compartmented document must be converted locally, and Caiman cannot enforce
that.** See `SECURITY-MODEL.md`; a documented user responsibility, plus an
ingest-time lint, rather than a property of the pipeline.

What ingest owns:

- **Chunking**, preserving the document's own structure. Register tables,
  bitfield descriptions, and individual requirements must not be split across
  chunk boundaries.
- **Labeling.** `public`, or one or more compartments. An *input* to ingestion,
  recorded on the artifact, carried onto every chunk, never re-derived from
  content.
- **Locator attachment.** Every chunk carries a resolvable locator.
- **Map generation.** A per-document map, described below.
- **Admission check.** A chunk with no resolvable locator is not ingestible. The
  document is rejected, not warned about. A chunk that cannot be cited cannot be
  used, so admitting it only creates a way to produce uncitable answers later.

### Locators

A citation is `(document identity, document version, locator)`. All three are
required.

| Document kind | Locator | Notes |
|---|---|---|
| Requirement-structured (OEM specs) | **Requirement ID** — `REQ-DIAG-0412` | The best case. Stable within a release line, greppable, and durable across re-conversion |
| Prose and reference manuals | **Heading path** — `§12.4.3 → LPSPI Control Register (CR)` | The floor. Survives conversion where page boundaries often do not |
| Any | Page number | Carried *alongside* a locator when the conversion supplied one, never instead of one |

A document declared requirement-structured has a stronger admission check: its
chunks must carry requirement IDs, which is a regular and verifiable pattern.

Requirement IDs matter more than they look. They give the specification side the
same property register identifiers give the datasheet side, and they are why the
whole design works without a retrieval service. Note also that
`grep -rn "REQ-DIAG-0412"` returns the base requirement *and* the deviation that
amends it in one shot — the "what governs here, and what did it override"
behavior largely falls out of the filesystem, provided the deviation names the
requirement IDs it amends.

### Generated maps

For each document, ingest emits a companion map: the heading tree, the
requirement-ID ranges it contains, and an index of register and identifier
mentions. Plain markdown, materialized alongside the document, greppable.

This is what replaces semantic search for the one query grep genuinely cannot
serve — the engineer or agent knows the concept but not the identifier. A map
gives a route from concept to identifier without an embedding model, a vector
store, or a service. It costs one pass at ingest and it is inspectable when it
goes wrong.

It is also the weakest part of this design, and S-18 says so with the numbers.
Published measurements on code retrieval put semantic search meaningfully ahead
of grep alone for exactly this class of query. The bet here is that a corpus of
unique, unambiguous identifiers (`LPSPI1_CR`, `REQ-DIAG-0412`) sits on the
favourable side of that trade where a codebase full of repeated names like
`validate` does not. Log the queries where maps and grep both miss — that log is
the trigger for building the one deferred tool, and it should be evidence rather
than intuition.

## [1b] Register a board and a project

### Board — hardware only

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
  secure-element    ...

links:
  safety-link   application-mcu (LPSPI1) <-> safety-companion (SPI)
  boot-flash    application-mcu (QSPI)   <-> boot-flash
  clock-tree    clock-generator -> application-mcu, safety-companion
```

A board version pins the vendor documentation for its parts. It knows nothing
about customers, programs, or specifications.

**Parts are identified by role, not by reference designator.** `U4` is a fact
about a schematic; `safety-companion` is a fact about the design, and it is what
a human or an agent can reason with. A refdes may ride along as optional
cross-reference metadata, but it is never the identity and never the display
name. Peripheral instance names (`LPSPI1`) stay exactly as the vendor writes
them, because that is what you search the manual for.

### Project — the session unit

```
project:      falcon                      # internal codename
customer:     <OEM>                       # compartmented; never in the brief
compartments: oem-alpha, falcon
version:      "B-sample"
derives_from: "A-sample"
relation:     "spec set moved 3.0 -> 3.2; secure flashing added"

board:        zonal-ctrl-rear @ "2.1"

spec_set:     OEM release 3.2             # frozen for this program
precedence:                               # highest authority first
  1. program deviations — DEV-2026-014
  2. OEM spec set 3.2

features:
  secure-boot                     required
    governed_by:  OEM SEC-BOOT 2.4 REQ-SB-0100..0240
    realized_on:  application-mcu (HSM)
  secure-onboard-communication    required
    governed_by:  OEM SECOC 3.1
    realized_on:  application-mcu (HSM), safety-companion
  secure-flashing                 required
    governed_by:  OEM FLASH 3.2, DEV-2026-014
    realized_on:  application-mcu, boot-flash
    related:      secure-boot, secure-onboard-communication
                  "shared HSM key hierarchy on the application MCU"
  ota-update                      not-used
```

**A project is not a board.** The same hardware ships into more than one customer
program, with different spec sets, different mandated features, and different
compartments. Fusing them would force physically identical boards to be
registered twice and would put customer identity into the hardware model, where
it cannot be compartmented.

**Features are the join between the normative and hardware sides.** Without them
a project brief is two disconnected halves — a parts table and a document list —
and the agent must guess how they relate. With them, "implement secure flashing"
resolves to: these specs govern, these parts are involved, these two other
features share state.

A feature declares **scope**, never **status**. `required` and `not-used` are
facts about the program; `in-progress`, `implemented`, and `verified` are
compliance tracking, which is ALM's job. `not-used` earns its place: telling an
agent the program does not use OTA update stops it from helpfully adding it.

Features are declared per project version by a human, once. There is no OEM
feature catalogue — an OEM's programs do not reliably share a feature set — but
they do not need re-deriving either, because cutting a new project version starts
from the previous one, so features carry forward as a delta.

### Rules shared by both

**Version labels are opaque** (I-7). `2.1`, `Rev B`, `EVT2-B`, `B-sample` and
`P3-redundant-can` are all valid and none is interpreted. Caiman never parses a
version string, never infers that one version relates to another, never computes
"latest", and supports no wildcard matching. On the normative side this is not a
modelling preference: a program is contractually frozen at a specification
release, so "newer" is not "better."

**Relationships are declared, never inferred** (I-8). `derives_from` between
versions, the precedence order among specification documents, and the `related`
edges between features are all supplied by a human with a free-text explanation.
Caiman renders them and never computes on them.

**Stored whole, authored by delta.** Authoring says "start from B-sample and
change these three things"; storage holds a complete, self-contained, immutable
snapshot. No inheritance resolution at read time, no version that fails to
resolve because its parent was mislinked, and the brief's diff is a comparison of
two complete snapshots.

## [2] Store

Artifacts are immutable and content-addressed. A new document version is a new
artifact, never a mutation; so are new board and project versions. This is what
lets several silicon revisions, board versions, and spec releases be
simultaneously live — which git, whose model is "one version is HEAD and the rest
is history," cannot express without abuse.

Documents, boards, and projects live in the same store: one backend, one auth
model, one immutability guarantee.

Each document artifact carries: issuer, part or program, document type, document
version, applicable silicon revisions, public flag or compartment set, source
checksum, converter identity and version, and ingest pipeline version.

> Backing store is **open** — see `DECISIONS.md` D-02.

## [3] Resolve

**A project version is the complete pin set.** There is no lockfile in the
firmware code repository. Resolving `falcon @ B-sample` yields the board version,
every `(role, part, silicon revision, document version, digest)` tuple that board
pins, every specification document version the program pins, the declared
precedence order, and the feature set.

Selection is *per session*: concurrent sessions may work two programs and two
board versions from one checkout. A repo-level file cannot express that, and a
repo file claiming one project while the session was launched against another is
the "right fact, wrong project" failure manufactured by the tool built to prevent
it.

- **The human-facing name is a tag; the digest is the pin.** "B-sample" is a
  moving reference — you add a deviation to it a month after cutting it. The
  immutable digest is what the brief header records and what a session runs
  against. This is I-4 applied one level up.
- **A session pins at startup.** Resolved once, when the workspace is
  materialized, and unchanged under a running session. Picking up newly added
  documentation means starting a new session, which is the honest behavior:
  otherwise the agent's context and the brief it was given silently diverge.
- **A bare name never resolves silently.** `falcon` with no version returns the
  list, not a guess.
- **Traceability, if wanted later,** is a commit trailer written by the harness
  from the live session (`Caiman-Project: falcon@sha256:9f3c…`). It cannot drift,
  because it is written at commit time from what was actually loaded. Not built
  for the MVP.

## [4] Materialize

```
caiman sync --project falcon --version B-sample \
            --agent claude-code --into .caiman/
```

Two inputs, two independent scopings that compose:

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

Caiman owns this map rather than the harness, so there is one place to answer
"what could this session see," and so an unrecognized agent name **fails closed**
rather than receiving whatever the harness happened to assert. See
`SECURITY-MODEL.md` for the full reasoning; the short version is that the human
picks the agent and Caiman makes the choice consequential.

### What lands in the workspace

```
.caiman/
  project.md        the brief — loaded into agent context before turn one
  project.json      resolved project structure, for the agent to read directly
  corpus/
    nxp/s32k344/reference-manual/…      documents, as markdown
    nxp/s32k344/reference-manual.map.md generated map
    oem-alpha/flash-spec/…              only if the agent profile allows
```

`project.json` is why there is no `describe_feature` tool: the resolved feature
graph, precedence order, and pin set are a file the agent can read.

### The brief

An **orientation document, not a data dump**. Injected context is paid for on
every turn of every session, so its job is to make the agent know what it is
working on and know that it must look things up rather than recall them.

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
Corpus: .caiman/corpus/ — grep it. Every document has a `.map.md` companion
listing its heading tree and requirement-ID ranges.
Resolved structure: .caiman/project.json

## Rules
- The OEM spec set is frozen at release 3.2. Later revisions do not apply to
  this program, even where they are newer.
- Where a program deviation amends a requirement, the deviation governs. Look
  requirements up by ID; grep will return the base requirement and any
  deviation that amends it together.
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

**The brief is open.** That a board contains a secure element and that a program
requires SecOC are structure, not content. The agent knows the restricted parts
and features exist rather than being unaware of components on its own board.

**The customer appears only by codename.** "We are building for OEM X" is
frequently itself under NDA. Programs have codenames precisely so people can talk
about them. There is a test asserting customer identity does not appear in a
generated brief.

**The brief is metadata only** (I-6). The generator reads the project and board
artifacts and the document *manifest*, and has no access to chunk text at all, so
it cannot leak restricted content even if someone later adds a helpful summary
feature. Enforced by construction and by test, not by review.

### Linking, not copying

A reference manual as markdown runs 10–20MB; a project pinning twenty of them is
a few hundred MB per session. Copying that for every worktree is slow and
wasteful, and cheap session startup is the premise the whole design rests on.

So `sync` links from a content-addressed blob cache — which the store already
provides, since everything is keyed by digest:

```
~/.cache/caiman/blobs/<compartment>/<sha256>     one copy, read-only
.caiman/corpus/…                                 links into it
```

After the first session, materialization is nearly free.

| Platform | Mechanism |
|---|---|
| macOS / APFS | `clonefile(2)` — `cp -c`. Zero space until divergence, and a write diverges instead of corrupting the shared original. The right answer here |
| Linux / btrfs, XFS | `cp --reflink` |
| Otherwise, same filesystem | Hardlink, blob mode `0444` |
| Across filesystems | Real copy |

Three traps, in descending order of severity:

**Never symlink a directory into the corpus.** Ripgrep does not follow symlinks
without `-L`, and GNU `grep -r` does not follow symlinked directories encountered
during traversal. The agent would search, get results, and have no indication
that part of the corpus was skipped. That is *silent incompleteness* — the same
failure class the parser discussion named as the enemy, and worse here because
there is no error to notice. Copy for real rather than crossing a filesystem
boundary with a symlink.

**Hardlinks share an inode, so they share permissions.** Mode lives on the inode,
not the path, so linking a compartmented blob from a shared cache into a
restricted directory does not restrict it — the content stays reachable through
the cache path. Keying the cache by compartment, as above, avoids this and the
cross-compartment version of the same mistake.

**Blobs are read-only and the corpus is read-only.** With hardlinks specifically,
an in-place edit propagates to every session sharing that inode and poisons the
cache. Mode `0444` plus "the agent never writes to the corpus" covers it; APFS
clones do not have the problem at all, which is another reason to prefer them.

Both clones and hardlinks require cache and worktrees on the same volume. Note
that separate APFS *volumes* in one container still count as separate filesystems
for this purpose.

A compartment note that resolves itself pleasantly: a vendor datasheet shared by
two customer projects is public, so it lives in the public cache and is shared by
both with no special case.

## Data model

```
Issuer ──< Part ──────< Document ──< DocumentVersion ──< Chunk
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

Four axes that do not nest cleanly, and conflating them is the classic mistake:

1. **Document version** — reference manual rev 3 vs rev 4; OEM release 3.0 vs 3.2
2. **Silicon revision** — mask revision of a part
3. **Board version** — which parts are populated, in which roles, wired how
4. **Project version** — which board, which spec release, which features, for
   which customer

Board *revision* and board *variant* are deliberately **not** separate axes. An
earlier draft split them, which forced Caiman to decide which one a given label
meant — precisely the company-specific convention it must not encode. One axis
with opaque labels and declared lineage expresses both.

## Access labels

Adopted from Onyx's model (`onyx/access/models.py`, MIT-licensed):

- A frozen label set per chunk, with an `is_public` flag
- Prefixed label strings to prevent namespace collisions (`compartment:`,
  `project:`, `part:` rather than bare values)
- One function generates labels for both write-time and filter-time — I-2
- Empty label set + `is_public=False` as the fail-closed default — I-1

The set rather than a scalar is what makes compartments work at no additional
cost. "How sensitive is this" is the wrong question when two customers' material
is equally sensitive and mutually invisible; "whose secret is this" is the right
one, and set membership answers it while a number cannot.

The mechanism transfers; the machinery around it does not. Onyx's
`external_permissions/` subsystem exists to mirror permissions from Slack, Drive,
and Confluence. Caiman has no upstream system to mirror — labels come from ingest
provenance, which is strictly simpler. Note also that Onyx's permission-sync code
lives under `ee/` and is **not** MIT-licensed: read for design, do not copy.

## Command surface

```
caiman ingest <markdown> --provenance …     add a document version
caiman board  list | show | version new     register hardware
caiman project list | show | version new    register a program
caiman sync --project P --version V --agent A --into DIR
caiman brief  --project P --version V       render only the brief
```

`sync` is the one the harness calls. `--dry-run` prints what would be
materialized without writing, which is how you answer "what could this session
see."

## Front end

CLI for the MVP. Three later surfaces, distinct and often conflated:

- **An admin/curation surface** for registering boards and projects, cutting
  versions, declaring features and precedence, and uploading converted documents
  with provenance and compartments. A human workflow that a CLI serves badly past
  a few dozen documents, and the place where a typo becomes a mislabeled document
  or a cross-compartment leak. On the roadmap, after the MVP.
- **An MCP server, for semantic fallback only.** The one job the filesystem
  genuinely cannot do. Build it if and only if grep plus generated maps proves
  insufficient in real use — that is a much better trigger than an architecture
  diagram having a serve layer.
- **A human documentation browser.** Still a non-goal; `mkdocs serve` covers it.
