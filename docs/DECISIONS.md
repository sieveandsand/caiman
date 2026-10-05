# Decisions

## Complete document manifests and flexible attachments (2026-10-03)

User-approved: every editable metadata field uses one complete immutable manifest
revision. A stable document ID and fixed blob identify the document; all references,
including old boards, resolve its latest approved metadata. Preserve earlier
manifests for explicit history. Metadata edits do not rewrite consumer snapshots.
Remove issuer/part/vendor/silicon matching restrictions on board attachments.
Known local usages are informational; incomplete enumeration does not block edits.
Existing test data and overlays require no migration. This supersedes the prior
split between shared description/provenance and identity/applicability adoption.
[DOCUMENT-METADATA.md](DOCUMENT-METADATA.md) owns the design and publication rules.

## Document structure and requirement-pattern metadata removed (2026-10-03)

User-approved: remove document `structure` and `requirements` fields from
authoring, editing, and validation. Requirement IDs remain ordinary source
content; project feature `governed_by[].requirements` references are unchanged.
Existing document snapshots retain their bytes and digests; read adapters omit
the retired fields in memory. This supersedes the requirement-pattern admission
rules in S-25 and I-5. [PODS.md](PODS.md) describes compatibility.

## Pods replace access labels and compartments (2026-10-01)

User-approved: one local folder per pod, optionally one Git repository per pod.
`public` is the permanent default pod. Caiman removes its separate authorization
layer, discovers local pods, and pins cross-pod dependencies without copying
them. Each configuration has one owning pod. This supersedes the access and
compartment portions of S-16, S-22, S-29, S-33, and S-35. Existing immutable
snapshots remain readable without rewriting their bytes. [PODS.md](PODS.md)
owns the implemented format, UI, Git workflow, and migration limits.


**Purpose:** The record of what was decided, when, and why.
**Owns:** Decision history and the trade-off analysis for decisions still open.
Settled entries state the decision and its rationale and point at the design
document that implements it; they do not restate the design.

Three sections: **Settled** (do not relitigate without a reason), **Open**
(choose deliberately; record the choice here), and **Retired** (the scope no
longer requires them — kept so the reasoning is not rediscovered).

---

## Settled

### S-01. Caiman is a layer, not a platform

Caiman assembles context and writes files into a worktree. Session management,
worktrees, agent execution, and hardware testing belong to external tools.
Keeping that boundary limits maintenance and lets engineers use their existing
harness. [Architecture §2.3](ARCHITECTURE.md#23-positioning-and-principles).

### S-02. Documents are immutable, versioned artifacts

Several document releases must remain usable at once. Content-addressed artifacts
preserve each version independently of a mutable name or Git HEAD.

### S-03. Labels come from provenance, assigned to whole documents at ingest

Humans assign explicit labels to the whole document at registration. Its text
cannot establish who may receive it. [Security §4](SECURITY-MODEL.md#4-why-content-inspection-cannot-work).

### S-04. Filesystem plus grep is the primary retrieval path

Use ordinary file search for exact identifiers. Semantic retrieval remains a
possible fallback under S-18.

### S-05. Fail closed, everywhere

Missing or unreadable labels exclude content from resolution and materialization;
they never imply public access. This is I-1.

### S-06. Citations identify the document, version, and source location

Use a source-appropriate locator: requirement ID, heading path, page, sheet/cell,
line range, or another precise location. Ingest does not require source structure.
[Architecture §6.4.2](ARCHITECTURE.md#642-file-admission-and-citations) owns admission.

Updated 2026-10-03 by user choice to accept documents of any format.

### S-07. A project version is the complete pin set; there is no repo-side lockfile

A project pins its board and specifications transitively. A repository lockfile
cannot represent concurrent sessions using different project versions from one
checkout, so selection stays per session.
[Architecture §6.7](ARCHITECTURE.md#67-resolve).

Settled 2026-08-20; amended for S-13.

### S-08. PDF → markdown conversion is out of scope

Accept files as supplied, including externally converted Markdown. Maintaining a
converter would expand the
project beyond context assembly. Optional conversion provenance supports tracing
errors; conversion confidentiality remains the user's responsibility.

Settled 2026-08-20; supersedes D-01.

### S-09. The brief is open and metadata only

Generate one always-visible brief from metadata only, with the program codename
instead of customer identity. The generator cannot read document bodies (I-6).
This lets an open session know that restricted context exists.

The assumption that the remaining metadata is safe to expose is under review
in G17; metadata-only generation does not prove it.
[Security §5.5](SECURITY-MODEL.md#55-brief-visibility-and-its-assumptions).

Settled 2026-08-20.

### S-10. Version labels are opaque; lineage is declared

Store labels verbatim: no ordering, parsing, wildcards, or “latest”. Companies use
incompatible version conventions. Lineage is an explicit `derives_from` and
free-text `relation`; a bare name lists versions. This is I-7.

### S-11. Versions are stored whole and authored by delta

Start editing from a selected snapshot, but store the complete result. Existing
pins survive and reads need no inheritance resolution. Features and other
unchanged declarations carry forward without being entered again.

### S-12. Parts are identified by role

Identify a part by its design role, such as `safety-companion`. Reference
designators belong in `aliases`, not the identity or display name. Keep vendor
peripheral names unchanged so they remain searchable in source documents.

### S-13. Board is hardware; Project is the session unit

A board describes hardware. A project combines a board version with customer
specifications, features, precedence, and compartments. Separate models let
multiple customer programs share hardware without putting customer identity in
the public board manifest.

Settled 2026-08-20; amended 2026-09-25 by S-34 (several boards) and S-36 (no precedence).

### S-14. Features are first-class; they declare scope, never status

Project features connect specifications to board roles. They declare `required`
or `not-used`, never implementation or verification status. Compliance tracking
belongs outside Caiman. Features are declared per project version and carried
forward with S-11, without a separate customer feature catalog.
[Project fields](STORAGE.md#project-fields).

Settled 2026-08-20.

### S-15. Declared relationships are rendered, never inferred

Humans declare lineage, precedence, and feature relationships with explanations.
Caiman renders them without inferring contractual meaning or detecting conflicts.
A deviation can name amended requirement IDs so search returns both documents.

Settled 2026-08-20. This is I-8.

### S-16. Classification asks whose secret this is, not how secret it is

Use public access or exactly one named compartment per document, not sensitivity
levels (S-33). A project must include that compartment to select the document. The initial policy treats
ordinary vendor documentation as public and customer specifications as
compartmented; restricted vendor material can also use compartments.
[Security §3](SECURITY-MODEL.md#3-classification) owns the rules.

Settled 2026-08-20; replaces the tier scale.

### S-17. Licensed standards are not hosted

Do not host ISO, AUTOSAR, or MISRA content. Customer documents may cite those
standards, but Caiman does not redistribute them. Identity-only standard stubs
were considered and dropped as unnecessary for the assumed specification sets.

Settled 2026-08-20.

### S-18. The filesystem is the interface; there is no server in the MVP

Materialize ordinary files and let the agent search them. Exact register and
requirement identifiers suit lexical search; a service would add maintenance
and tool context without an established need.

Concept-based questions may still need semantic retrieval. Published comparisons
were mixed, so the decision depends on Caiman's own tasks: record misses and
revisit when identifier-unknown queries repeatedly defeat search and selective
reading. D-03 remains deferred. A pluggable retrieval backend is an option if
that trigger fires; do not add splitting or generated maps to ingest by default.

Settled 2026-08-20; supersedes D-06/D-11. Trigger updated 2026-09-15 for S-25.

### S-19. The human declares the session mode; Caiman holds no agent policy

Require `sync --mode open|sealed`, with no default. The human selects the mode;
Caiman does not attest the model or enforce its authorization.

The former agent-name map was removed because it required maintenance, could
differ across machines, and could silently misidentify a harness's model.
This accepts the risk of a mistaken mode choice. Any future convenience layer
may narrow access, never widen it. `--agent-label` is an unverified audit
annotation, not policy. [Security §5](SECURITY-MODEL.md#5-the-control).

Settled 2026-08-20; agent map removed 2026-09-15.

### S-20. Documents are linked from a content-addressed cache, not copied

Prefer filesystem clones or read-only hardlinks to repeated large copies; copy
across filesystems when necessary. The cache is compartment-scoped and document
directories cannot be symlinks, because ordinary recursive search may skip them.
[Storage §7.3](STORAGE.md#73-materialize) owns the mechanics (I-9).

Settled 2026-08-20.

### S-21. A filesystem content-addressed store, laid out as an OCI subset

Store blobs and manifests by digest, refs by name, and compartments in separate
trees. At this scale a database is unnecessary; the OCI-like layout leaves a
registry migration possible. [STORAGE.md](STORAGE.md) owns the format.

Settled 2026-09-14; resolves D-10 and the MVP backend choice. D-02 remains the
future migration decision.

### S-22. Git transport for the store

The 2026-09-14 design changed from per-compartment repositories to one private
repository for a single engineer. **S-33 supersedes that topology**: team access
varies by customer/project, so the planned backend uses one private repository
per compartment, plus a private public-material repository. Ingest never pushes;
publication remains separate and reviewed. This resolves the G23 conflict with
I-3. S-35 adopts the protocol; [Storage §6.6](STORAGE.md#66-team-storage-one-git-repository-per-compartment) owns it.

Settled 2026-09-14; topology superseded 2026-09-24 by user instruction.

### S-23. Session integration is via harness hooks, as thin adapters over the CLI

Keep session logic in `caiman session start|record|end`; adapters translate
harness events. Start hooks inject context so the agent can ask for selection;
they cannot prompt interactively. Hooks observe, never block, and degrade to the
manual workflow if unavailable. [Architecture §6.10](ARCHITECTURE.md#610-session-integration).

Settled 2026-09-14.

### S-24. Audit has two layers: what could be read, and what was read

The materialization log records the available document set. Hook access logs
record observed reads and are incomplete: shell reads, missing hooks, and
unverified subagent coverage leave gaps. Absence of a record is not proof of
non-access. Both logs contain sensitive metadata and stay outside repositories.
[Security §9](SECURITY-MODEL.md#9-audit) owns the audit contract.

Settled 2026-09-14.

### S-25. Ingest registers one unchanged file of any format

Register one readable file byte-for-byte, including binary, empty, extensionless,
and non-UTF-8 inputs. Do not enforce headings, unique heading paths, front matter,
or requirement IDs. Documents have no structure or requirement-pattern metadata.
Do not split, rewrite, summarize, generate maps, or call AI during ingest.
Preserve the extension in the manifest file path (`document` plus the source's
final extension), and keep the original basename in `original_filename`.
Existing snapshots and their paths remain unchanged.

Acceptance does not establish conversion fidelity, retrieval quality, or support
for reading a format. [Architecture §6.4](ARCHITECTURE.md#64-ingest) owns workflow.

Updated 2026-10-03 by user choice.

### S-26. Original-source and converter provenance are optional

The document file and metadata are required; original-source and
converter provenance are optional, including individual fields. Unknown values
stay absent and never imply public access or local conversion. Record only the
input file basename as `original_filename`, plus its computed digest/size.
This trades missing provenance for a simpler registration workflow.
[Storage §6.4.1](STORAGE.md#641-document-version) owns the fields.

Settled 2026-09-15 by user instruction.

### S-27. Ingestion uses a TUI; the future GUI is a native macOS app

Use an ingestion TUI with explicit labels, validation, review, and cancellation.
A long flag list or sidecar is not the initial interface; noninteractive ingest
is deferred. Shared validation and registration must remain independent of
widgets for a future native macOS app. No local web frontend is planned.
[Architecture §6.4.3](ARCHITECTURE.md#643-registration-and-reading-workflow).

Settled 2026-09-15 by user instruction; resolves D-09.

### S-28. Board and project authoring use a TUI and editable JSON drafts

Support both a TUI and editable JSON drafts over shared validation and
registration. Review resolves selectors to immutable pins; new-version authoring
copies a full snapshot. [README.md](../README.md#configure-boards-and-projects) owns commands;
[Storage §6.4](STORAGE.md#64-manifest-schemas) owns fields.
S-30 supersedes the original orange terminal styling; S-32 refines board editing.

Settled 2026-09-15 by user instruction; resolves G13 and Architecture Gap B.

### S-29. Create boards and projects on demand; choose them explicitly every time

Create boards and projects on demand, including during ingestion. Always ask
which configuration to use; never save or preselect a default. Document lists
may start empty. Reusing configuration metadata does not classify a document
or update existing pins.

Remember only compartments from explicitly chosen projects, without discovering
others by scanning. Use “compartment” consistently: the brief “access group”
rename caused confusion with errors and stored fields; “ip” was ambiguous in
firmware and “counterparty” did not justify a schema rename.

Settled 2026-09-15; amended 2026-09-16 to remove forced setup/saved selection
and restore “compartment”. [First launch](../README.md#first-launch-and-document-ingestion).

### S-30. The bare command is a dashboard with shared Vim-style navigation

Bare `caiman` opens a dashboard with one card per category. Boards and projects
each have Create and View: viewing opens the category's cards, creating is the
add card at the end of them, and editing starts from the viewed item. JSON utility commands remain directly
available. Use shared Vim-style navigation with an explicit text-editing mode,
a single mode hint, and no Ctrl shortcuts or command palette.

The current theme is black with green accents and outlined fields. This replaced
the original orange styling. [Keyboard navigation](../README.md#keyboard-navigation)
owns controls; S-32 owns the board editing decision.

Settled 2026-09-15; dashboard scope, controls, and colours amended 2026-09-16;
category cards amended 2026-09-25.

### S-31. The board schema is `caiman.board.v2`; schema literals are a table

Adopt board v2 to support assembly documents, separate vendor/part identity,
cross-domain aliases, and unstructured notes. Industry-parity fields such as
register maps, nets, build flags, and lifecycle status remain excluded.
[Board fields](STORAGE.md#board-fields) owns authoring fields;
[Storage §6.4](STORAGE.md#64-manifest-schemas) owns serialized forms.

Use a table of accepted schema literals. New writes use `caiman.board.v2`,
`caiman.document.v1`, and `caiman.project.v1`; readers accept legacy slash
spellings. Preserve declared literals and old snapshots byte-for-byte. A missing
literal defaults to the current schema; never infer it from the body.

Settled 2026-09-18 by user instruction; resolves D-13. The breaking authoring
change is accepted; stored v1 boards remain valid without migration.

### S-32. Boards are edited in a guided form; raw JSON is the escape hatch

Edit boards in a guided form, with raw JSON in Vim available for the whole
current draft. Preserve fields the form does not render. Show legacy v1 boards
and `from`/`to` links without authoring them in the form, to avoid migration or
lost endpoints. Validation, pin resolution, diff review, and registration remain
shared with raw editing.

Lineage stays out of the form and passes through unchanged; edit it in JSON or
with `new-version`. Vendor completion suggests spellings but accepts any value.
[Editing guide](../README.md#edit-an-existing-board-or-project) owns the workflow.

Settled 2026-09-18; amended 2026-09-19 to omit lineage controls, lead parts with
their name, and suggest vendor spellings.

### S-33. Each document has one compartment; compartments are repository boundaries

A document is explicitly public or belongs to exactly one compartment. Reject
multiple entries, including duplicates, on ingestion, registration and read.
Keep the existing array representation with zero public/one private entry so
valid stored snapshots keep their bytes and hashes. Legacy multi-compartment
documents require explicit re-ingestion and repinning, not silent narrowing.
Projects and sessions may still refer to documents from multiple compartments.

Use one private Git repository per compartment; do not introduce a separate
access-domain abstraction. This replaces the initial AND/intersection proposal
and the subsequently discussed OR/replication option: neither is needed for a
single-compartment document. Repository permissions enforce teammate access;
Caiman performs classification checks and session selection. No transport is
implemented by this decision. [Security §3](SECURITY-MODEL.md#3-classification)
owns the rule; [Storage §6.6](STORAGE.md#66-team-storage-one-git-repository-per-compartment) owns the transport.

Settled 2026-09-24 by user instruction; resolves G23's repository-boundary choice.

### S-34. A project pins one or more boards; realized parts name their board version

A program may run on several boards, or on one board at several versions, so a
project lists `boards` instead of one `board`. Pinning the same name and version
twice is rejected. Role names are chosen per board and need not be unique across
boards, so each `realized_on` entry is `{board, version, role}` and is checked
against the named board version only. Labels match exactly (I-7). An object
rather than a `board/role` string, because version labels are free text and
could contain any separator.

New writes use `caiman.project.v2`. Stored v1 projects remain valid and are never
rewritten; editors open them restated with their single board spelled out, and
registering the edit writes a new v2 snapshot. Ingestion takes its board from a
project only when the project pins exactly one; otherwise the board stays an
explicit choice. [Project fields](STORAGE.md#project-fields) owns the fields.

Settled 2026-09-25 by user instruction; amends S-13 and the project literal in S-31.

### S-35. Team storage: per-compartment Git publication and a Merkle DAG

Adopt the team storage design. Each compartment's private repository carries a
managed `caiman-store` branch. Publication is a reviewed plan, sent
dependency-first and root-last, and application refs carry generations so
concurrent publishers conflict instead of overwriting. Fetch verifies every
object before advancing the local view. Document-set and context digests
identify what a session selected, separately from its local receipt. There is no
service. Git holds whole history and cannot delete what was fetched; that cost
is accepted until the triggers in Storage §12.1. Configuration ownership,
classified boards, a classified brief, and the hardlink fallback remain open.
None of them is resolved by this decision. [Storage](STORAGE.md) owns the design;
§14 sets the phases. The earlier proposal document is merged into it.

Settled 2026-09-25 by user instruction; builds on S-22 and S-33.

### S-36. Projects declare no precedence among documents, for now

Remove `precedence` from `caiman.project.v2`; it is not needed yet. A v2 project
that declares it, even as an empty list, is rejected. A feature's governing
document must be one of the project's `documents`. Stored v1 projects keep their
declared precedence and are never rewritten; editors restate them with any
document pinned only in precedence moved to `documents`, so no pin is lost,
while order and notes are dropped and shown in the review diff.

If precedence returns, it is declared by a human and never computed (I-8, S-15);
this decision removes the field, not that rule. D-12 assumed deviations sit at
the top of the declared order; until it is resolved, a deviation is an ordinary
project document that names the requirement IDs it amends, so `grep` still
returns it with the base requirement.

Settled 2026-09-25 by user instruction; amends S-13 and S-34.

### S-37. Documents and collections share one gallery

All file roles use one document concept, identified by a name and description.
Agents can interpret purpose from those fields and the source; Caiman adds no
AI dependency or role inference during ingestion. Optional requirement-ID
validation remains a capability of any document. New registrations use
`caiman.document.v2`; existing v1 snapshots and refs remain readable unchanged.

The Documents gallery has single document cards, persistent stacked collection
cards, and separate add cards. Collections select existing documents and have
no user-facing version. Saves create content-addressed snapshots with exact
member digests and a stable collection reference. Focus uses a separate dotted
shadow. Collection storage and access rules are in `STORAGE.md` §6.4.1a.

Settled 2026-10-01 by user instruction.

### S-38. Public is the permanent default; references stay within one pod plus public

Initialize with public as the default and disallow changing or removing it.
Artifacts reference their owning pod or public, and public stays self-contained.
This limits the dependency graph to the current pod plus public, including
transitive board dependencies. Legacy default preferences are ignored; stored
snapshots are never rewritten. [PODS.md](PODS.md) owns the current rules.

Settled 2026-10-04 by user instruction; narrows the earlier arbitrary cross-pod model.

## Open

### D-02. When to move the store to an OCI registry

The backend is decided (S-21) and the remote is git (S-22). The original trigger
— compartment separation needing real authentication — has been met, and git
answered it more cheaply than a registry would have.

What a registry would still add: immutability enforced by the system rather than
by this design's conventions, retention as configuration rather than discipline,
and **deletion that actually deletes**, which git cannot do (`STORAGE.md` §9.5).

Revised trigger:

> Move to a registry when history permanence becomes the binding constraint —
> compartment corrections happening often enough that irreversible pushes are a
> recurring incident, or a counterparty requiring demonstrable deletion.

*Open: nothing to decide until then. Recorded so the trigger is not forgotten,
and so the reason it changed is visible.*

### D-03. Index backend — deferred, not chosen

S-18 removed the semantic index from the MVP, so this is off the critical path.
It becomes live only if the miss log shows search and selective reading of
source documents failing on real tasks (S-18).

| Option | For | Against |
|---|---|---|
| **Postgres + pgvector + FTS** | One service; hybrid lexical and semantic; trivial ops | Weaker ranking than dedicated engines at scale |
| **OpenSearch** | Strong hybrid retrieval; Onyx's ACL filter applies directly | Another cluster to operate |
| **Qdrant / Weaviate / Milvus** | Good vector stores | Vector-only; you still need lexical alongside |

Indexed volume here would be tens of thousands of chunks, not hundreds of
millions.

*Leaning: Postgres if ever needed. Do not build speculatively — the trigger is in
S-18 and requires logged misses. Note an existing MIT-licensed server with a
pluggable backend may remove the need to choose at all.*

### D-04. Build the context layer, or adopt a platform?

Compare building the layer with adopting a firmware platform or a general document
system. The trade-off is control over program/version/compartment models versus
maintaining ingestion and hardware structure ourselves. Product capabilities
must be tested with our documents, not inferred from marketing.

The historical landscape is in [Roadmap’s historical survey](ROADMAP.md#competitive-landscape-historical); G01–G05 track
validation. Leaning: build the small layer, but revisit if basic document and
board handling consumes the effort intended for program context.

### D-07. Harness strategy

The harness asks which project *and which agent*, creates the worktree, calls
`caiman sync`, and launches. Caiman does not build it.

One hard requirement on any candidate: **per-session agent and model selection**.
A harness driving a single backend cannot express the choice S-19 rests on. Verify
before adopting.

Caiman's obligation is an interface clean enough for someone else to drive:
`caiman sync --project P --version V --mode open|sealed --into DIR`, with no assumption
that Caiman owns the file or knows what a session is. Until a harness exists, the
same command plus a one-line `@.caiman/project.md` import is the manual path —
which is good, because it exercises the interface from day one.

Candidates by maintenance health: `ccmanager` (MIT, tidy, small), `agent-deck`
(MIT, responsive maintainer), `emdash` (Apache-2.0, funded team). Avoid
`claude-squad` (AGPL-3.0 is a real constraint for anything shipping internally).
`Crystal` is effectively dead. Xirp has been discussed as a model; whether it is
obtainable outside Spotify and under what licence is **unverified**.

Note that worktree isolation, the primitive these are built on, does not address
the actual bottleneck in firmware: one board, one probe, one CAN interface.

*Open: adopt one and contribute project selection upstream, or write a thin
launcher that shells out to `caiman sync` and then to an existing harness.*

### D-08. Sample / test projects

Selected, following the request to replace synthetic demonstration hardware:
Zephyr's micro:bit sound sample at v4.2.0, plus Adafruit's MacroPad keyboard/mouse
and tone-keypad examples. [Dataset guide](../fixtures/README.md) owns usage,
provenance, exact source commits, file-level licensing, and modeling limitations.

The micro:bit v1.3 and v2 firmware-facing models change the MCU, sensor population,
button/display wiring, and sound route. The v1 model needs an external piezo;
the v2 uses its built-in speaker. These provide concrete "right fact, wrong
board" cases. MacroPad's HID and tone applications share one board snapshot but
require different features. Board models deliberately omit unsupported BOM or
register details rather than inventing them.

The normative layer remains explicitly Caiman-authored: acceptance baselines
and a micro:bit R2 deviation amending two R1 hardware requirements. These are not
customer contracts or official upstream specifications. Both sound releases
remain available with immutable pins. No automatic precedence or conflict
inference is introduced; D-12 remains separate.

Upstream files use Apache-2.0, MIT, or Unlicense, checked at file level and bundled
with notices. The examples are all public; named project compartments are schema
requirements and demonstration groupings, not assertions of confidentiality.
Synthetic private inputs remain in unit tests for isolation checks. No actual
customer documents or restricted vendor manuals may be committed. The earlier
Gaggiuino candidate is not used.

The offline loader validates the entire graph in a temporary store before
adding missing objects. It preserves existing refs, refuses name/version
conflicts, reuses unchanged document digests, and remembers the explicitly
imported demo compartments. It does not push or install firmware.

### D-12. How program deviations are represented

For now, assume deviations arrive as a single document at the top of the declared
precedence order, naming the requirement IDs it amends so `grep` surfaces the
override. That is enough for the MVP and is what the current design assumes.
S-36 has since removed declared precedence; a deviation is an ordinary project
document in the meantime. This question stays open.

It will not hold forever. Deviations are often a spreadsheet or a letter, they
arrive incrementally over a program's life, and they may be per-part-number
rather than per-program.

| Option | For | Against |
|---|---|---|
| **A document, like any other** | Zero new machinery; registers unchanged and cites identically | Incremental deviations mean re-ingesting a growing document; no structured "which requirements are amended" query |
| **Structured amendments on requirement IDs** | Exact override lookup; incremental additions are cheap | A second content path, and hand entry is where mislabels happen |
| **Both — document is the artifact, amendments a declared index over it** | Citation stays to the real document; override lookup is exact | Two things to keep in sync; a future index needs an explicit authoring decision and is not part of S-25 ingest |

*Leaning: the third, once the first becomes painful. Do not build before there is
a real deviation document to look at.*

### D-14. When and where documents are provisioned into a worktree

Raised 2026-09-25 by agents running in a Docker container per worktree. `sync`
needs the store, which only the host holds; agent sessions start inside the
container, where it is too late to provision without exposing the store.

Proposed resolution — the engineer has agreed the direction; not yet settled:

1. **Provision when the worktree exists, not at session start.** Creating
   worktrees and containers stays outside Caiman (S-01). The engineer then opens
   Caiman on the host, picks the target, project, version, and mode, and
   provisions.
2. **The target is the worktree folder on the host.** Provisioned context
   belongs to the folder, never to a container; a container is only a way to
   find the folder, through read-only `docker ps` and `docker inspect`.
   Creating, starting, execing into, copying into, or committing containers
   stays out of scope.
3. **The store never enters a container.** Caiman in the image runs without a
   store or configuration.
4. **Session-start selection becomes a local-only fallback.** This amends S-23,
   which made hook-driven selection the main path.
5. **A mode declaration covers the worktree** until it is cleared or
   re-provisioned, and every session start restates it. This answers G18's
   resume question: the declaration is still made by a human, explicitly, with
   no default (S-19), but for a worktree rather than one session.
6. **Clearing and re-provisioning are always available**, warn that running
   sessions keep what they read, and are logged.

| Option | For | Against |
|---|---|---|
| **Provision per worktree from the host (proposed)** | Works when the agent cannot reach the store; one pin set for all of a worktree's sessions; an `open` container holds no compartmented file at all | The mode outlives the moment it was chosen; a later session may run an agent not cleared for it |
| **Select at every session start (S-23 as written)** | The engineer declares the mode knowing which model runs | Impossible in a container without mounting the store; asks again on every restart |
| **Mount the permitted store repositories into the container and run `sync` there** | Keeps session-start selection | The agent can read unpinned store objects directly; the mount set fixes the mode at `docker run`; links across mounts fail with `EXDEV`, forcing full copies |
| **Copy documents into the container (`docker cp`)** | No host-path lookup | Full copies; outside every git guard; lost with the container; baked into images by `docker commit` |

What would settle it: accepting the cost in the first row's "Against" column,
with the per-session restatement as its mitigation.
[Architecture §6.11](ARCHITECTURE.md#611-provisioning-a-worktree) holds the
design. D-07's launcher still applies: a launcher may call `sync` itself after
creating a worktree, with the mode typed by a human.

---

## Retired

### D-09. Front-end form factor *(resolved 2026-09-15 by S-27)*

The MVP requires a TUI for document ingestion. The future GUI is a native macOS
app for authoring and curation. Both use shared validation and registration
operations; no local web frontend is planned. S-28 now defines board/project editing through a TUI and JSON drafts. The
Mac app's schedule remains to be designed.

This changes the human authoring interface, not the filesystem interface used
by coding agents. Semantic retrieval remains deferred under S-18, and a separate
human-facing documentation browser remains a non-goal.


### D-13. How far the board schema should follow industry board descriptions *(resolved 2026-09-18 by S-31)*

The survey compared software-facing board formats (devicetree, CMSIS-Pack,
PlatformIO and others) with hardware-facing EDA/BOM formats. It identified four
local gaps: assembly documents, explanations on links, cross-domain identifiers,
and separate vendor/part fields.

Options were leaving v1 unchanged, adding notes only, adopting the full v2
proposal, or matching industry schemas. The user chose v2 on 2026-09-18 (S-31).
The field contract now lives in [Storage's board schema](STORAGE.md#642-board-version),
rather than a second draft here.

Future schema revisions should consider the remaining naming differences:
`document.issuer` versus `part.vendor`, and project `precedence[].note` versus
board `notes`. Do not rename fields in existing snapshots. G14 still tracks
import paths; choosing the target schema did not decide an importer.

### D-01. PDF → markdown parser *(retired 2026-08-20, superseded by S-08)*

Originally the highest-risk component: everything downstream inherits a parser's
errors, and layout-aware parsers are known to drop content silently. The plan was
a bake-off between LlamaParse, Docling, MinerU, OpenDataLoader, and PaddleOCR
against a real reference manual, leaning toward a local parser for confidential
material regardless of how candidates scored on public documents.

Retired because conversion left scope. The risk did not disappear, it moved: it
now lives in the user's choice of converter, and Caiman addresses what it still
can — optionally recording converter identity so a bad conversion can be traced
when that information is supplied (S-26), and
rejecting documents whose content lacks resolvable locators. The confidentiality
observation survives as a security note: a compartmented document must not be
sent to a hosted converter, and Caiman cannot enforce that.

### D-05. Routing enforcement *(resolved 2026-08-20 by S-19)*

Weighed a self-hosted AI gateway, a separate OS user with stdio transport, a
sealed sandbox containing the harness, and doing nothing under a zero-retention
agreement. All four tried to enforce, at read time, a judgement the human had
already made at session start.

Resolved by moving the decision to the human and making it consequential through
differential materialization. The gateway and separate-uid options survive as
optional hardening in `SECURITY-MODEL.md` §11.

### D-06. MCP tool granularity *(retired 2026-08-20, superseded by S-18)*

Weighed few fat tools against many thin ones, settling on roughly five fat
working tools plus a session-startup trio. Moot once the server left the MVP: six
of seven duplicated file operations the harness performs better, and the seventh
(semantic search) was already first on the cut list. If a server is ever built
for semantic fallback it will have one tool, and this will not need reopening.

### D-10. Board and project version representation *(resolved 2026-09-14 by S-21)*

A canonical JSON manifest is the source of truth and the thing that is hashed;
its digest is what a project version pins. No relational index for the MVP — at
tens of boards and projects, reading manifests beats maintaining a derived view,
and one can be added later without touching the source of truth.

### D-11. What the harness calls at session start *(resolved 2026-08-20 by S-18)*

Weighed shelling out to the CLI against an MCP call against both. Resolved to the
CLI by S-18, which removed the server. The byte-identical-output concern that
motivated "both" disappeared with it.

---

## Recording a decision

Resolved: move to **Settled** with a one-paragraph rationale and the date, and a
pointer to the design document that implements it. Do not restate the design
here.

Made unnecessary by scope: move to **Retired** with what the risk was and where
it went.

Keep rejected options visible. Future-you will want to know what was already
considered and why it lost.
