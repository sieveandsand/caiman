# Decisions

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

Session management, worktree isolation, terminal multiplexing, and
hardware-in-the-loop execution are permanently somebody else's job. Caiman
assembles context, writes it into a worktree, and gets out of the way. The agent
is whichever you already use; the harness is whichever you already run.

This is a positioning decision as much as a scoping one. Platforms in this space
bundle the agent, orchestration, test execution, and knowledge layer and are
adopted together (D-04). Choosing the layer buys adoption in an afternoon rather
than a procurement cycle, no lock-in to an agent or model or harness, and a scope
one engineer can keep correct — the actual constraint here. It is a distribution
and scope argument, not a claim of technical superiority; whether layer or
platform is the better bet is unsettled. See `VISION.md` §5.

### S-02. Documents are immutable, versioned artifacts

Git's model — one version is HEAD, the rest is history — cannot express "many
silicon revisions are simultaneously live". Content-addressed artifacts can.

### S-03. Labels come from provenance, assigned to whole documents at ingest

Never inferred from content. There is no classifier for "confidential hardware
specification" and there will not be one, because confidentiality is a property
of where the text came from rather than what it looks like. `SECURITY-MODEL.md`
§4.

### S-04. Filesystem plus grep is the primary retrieval path

Exact-identifier lookup is a lexical problem. Semantic search is a fallback, not
the default. Extended to its conclusion by S-18.

### S-05. Fail closed, everywhere

Missing or unreadable labels produce unreachable content, not public content.
This is I-1.

### S-06. Citations are mandatory; requirement IDs where available, heading path as the floor

A citation is `(document identity, document version, locator)`. All three are
required.

Page anchors were originally mandatory and were relaxed: conversion happens
outside Caiman (S-08) and page boundaries frequently do not survive it, while
headings do. A heading path is also more useful in practice — a human finds a
section faster than a page.

**For requirement-structured documents the locator is the requirement ID**, and
that is strictly better: stable within a release line, greppable, unambiguous,
and durable across re-conversion. Swap the converter later and every existing
citation still resolves, which a heading path or page number would not. This also
gives the normative side the same lexical exact-lookup property register
identifiers give the descriptive side, which is what lets the whole design work
without a retrieval service (S-18).

What is **not** relaxed is document identity and version. A citation reading "the
S32K3 manual says" without a version is worthless — and on the normative side
worse than worthless, because a program is contractually frozen at a release.

All input documents require usable headings, including requirement-structured
documents; the latter additionally require matching requirement IDs. S-25 and
`ARCHITECTURE.md` §6.4.2 define admission. Line numbers aid navigation but do not
replace the heading or requirement-ID locator.

*Settled 2026-08-20; extended with requirement-ID locators 2026-08-20;
whole-file heading admission clarified 2026-09-15 by S-25.*

### S-07. A project version is the complete pin set; there is no repo-side lockfile

An earlier design put a `caiman.lock` in the firmware repository. Selection is
per *session* — concurrent sessions may work two programs and two board versions
from one checkout — which a repository-level file cannot express. Worse, a
repository file naming one project while the session ran against another
manufactures the "right fact, wrong board" failure the tool exists to prevent.

Pinning lives in the version artifacts: a board version pins vendor
documentation, a project version composes a board version and pins specification
releases, so `project @ version` resolves everything transitively.
`ARCHITECTURE.md` §6.7.

*Settled 2026-08-20; amended for the project/board split (S-13).*

### S-08. PDF → markdown conversion is out of scope

Caiman ingests already-converted Markdown plus document metadata. Original-source
and converter provenance are optional (S-26). The conversion category is competitive and
improving monthly; maintaining another parser is not where the gap is.

Converter identity, when supplied, is useful provenance
(`ARCHITECTURE.md` §6.4.1). Converting a confidential document through a
hosted service is a disclosure outside Caiman's control, which becomes a
documented user responsibility (`SECURITY-MODEL.md` §7.2).

*Settled 2026-08-20. Supersedes D-01.*

### S-09. The brief is open and metadata only

That a board contains a secure element, and that a program requires SecOC, are
structure; what the manual and the specification *say* is content. So the brief
is an ordinary unclassified file — one brief, not an open one and a sealed one —
and the agent knows the restricted parts and features exist rather than being
unaware of components on its own board.

Customer identity is the exception: "we are building for OEM X" is frequently
itself under NDA, so the brief names the program by **codename**. The customer
stays in a compartmented project manifest.

The counterpart is I-6: the generator reads manifests only and has no access to
document content, so it cannot leak even by accident. `SECURITY-MODEL.md` §5.5.

*Settled 2026-08-20; extended to project briefs and codenames 2026-08-20.*

### S-10. Version labels are opaque; lineage is declared

`2.1` supersedes `2.0` at one company and is a variant of it at another; a third
uses `Rev B` or `EVT2`. Caiman stores labels verbatim, never parses, orders,
computes "latest", or matches wildcards.

Where lineage matters — choosing a baseline for the brief's change summary — it
is an explicit `derives_from` edge with a free-text `relation` that Caiman
displays and never branches on. The registry records semantics; the code does not
compute on them.

Corollary: a bare board or project name never resolves to a version; it returns
the list. This is I-7.

### S-11. Versions are stored whole and authored by delta

Authoring says "start from 2.0, change these three things". Storage holds a
complete, self-contained, immutable snapshot. No inheritance resolution at read
time, no version that fails to resolve because its parent was mislinked, and the
brief's change summary is a comparison of two complete snapshots.

This is also what keeps hand-declared features from rotting: a new project
version starts from its predecessor, so features carry forward as a delta rather
than being re-derived.

### S-12. Parts are identified by role

`U4` is a fact about a schematic; `safety-companion` is a fact about the design
and is what a human or an agent can reason with. A reference designator may ride
along as optional cross-reference metadata but is never the identity and never
the display name. Peripheral instance names (`LPSPI1`) stay exactly as the vendor
writes them, because that is what you search the manual for.

### S-13. Board is hardware; Project is the session unit

A `Board` describes hardware and knows nothing about customers or specifications.
A `Project` is what a session is *about*: a board version, a specification set, a
declared precedence order, a feature set, and compartments.

They were fused in an earlier draft. The split is required because the same
hardware ships into more than one customer program. Fusing would force physically
identical boards to be registered twice — a lie about the hardware — and would
put customer identity into the hardware model where it cannot be compartmented.

*Settled 2026-08-20.*

### S-14. Features are first-class; they declare scope, never status

An agent cannot make a good decision about secure flashing if it does not know
the program requires it, which specification governs it, and that it shares a key
hierarchy with secure boot. A `Feature` carries `governed_by`, `realized_on`, and
`related`, and is the join between the normative and hardware sides. Without it a
brief is two disconnected lists.

A feature declares **scope** — `required` or `not-used` — and never **status**.
`not-used` is valuable: telling an agent the program does not use OTA update
stops it from helpfully adding it. `in-progress`, `implemented`, and `verified`
are compliance tracking, which is ALM's job and an explicit non-goal. This line
will get pushed on; it is recorded so the answer already exists.

There is no per-customer feature catalogue — an OEM's programs do not reliably
share a feature set — so features are declared per project version, once, and
carried forward by S-11.

*Settled 2026-08-20.*

### S-15. Declared relationships are rendered, never inferred

Lineage between versions, precedence among specification documents, and
relationships between features are all supplied by a human with an explanation.
Caiman displays them and never computes on them.

One principle, not three coincidences, and it is load-bearing: it keeps Caiman
out of interpreting contracts, inferring one company's numbering convention, and
detecting conflicts between specifications — all tempting, all unreliable, and
all of which would make Caiman's output something to check rather than something
to cite.

Corollary: no automatic conflict detection between specifications, ever. If a
deviation amends a requirement, a human names the requirement IDs and retrieval
surfaces both. That is a retrieval behavior, not a precedence engine. This is I-8.

*Settled 2026-08-20.*

### S-16. Classification asks whose secret this is, not how secret it is

There is no sensitivity scale. A document is either asserted **public** or
carries one or more **compartments** naming the counterparty it belongs to;
visibility requires the session to hold every compartment a document carries.

A scale cannot express what this data needs: two customers' specifications are
equally confidential and must be mutually invisible, and whatever numbers you
assign, one is greater than or equal to the other and sees it.

Underneath sits an asymmetry. **Vendor documentation is treated as public** —
nominally confidential, practically semi-public, and expensive to gate for close
to no benefit. **Customer material is compartmented** — few holders, contents
identify whose it is, and the agreement is with the party whose business you are
keeping. One mechanism for both forced the expensive treatment onto the cheap
case. If a genuinely restricted vendor document arrives, compartments handle it
with no new machinery. `SECURITY-MODEL.md` §2.1, §3.

The mechanism needed no invention: access labels were already a frozen set of
prefixed strings with an `is_public` flag. Missing metadata is neither, and stays
unreachable (I-1).

*Settled 2026-08-20; replaced the tier scale 2026-08-20.*

### S-17. Licensed standards are not hosted

ISO, AUTOSAR, and MISRA documents stay out of the document set. Licensing aside,
customer specifications are largely self-contained in practice — they state their
own requirements rather than layering deviations over a standard — so the
precedence chain does not lose a layer by their absence. Where a specification
cites a standard, that is a citation in its text like any other.

An earlier draft proposed identity-only stubs for referenced standards so a
citation could read "OEM 3.2 §7.2.1, overriding ISO 14229 §11.4". Dropped as
unnecessary once self-containment was confirmed.

*Settled 2026-08-20.*

### S-18. The filesystem is the interface; there is no server in the MVP

`caiman sync` writes the brief, the resolved structure, and the documents into
the session workspace. The agent reads and greps them with the tools it has.

This is S-04 followed to its conclusion. Exact-identifier lookup is lexical, and
stable requirement IDs (S-06) made the normative half lexically exact too. With
both halves greppable, a retrieval service adds a round-trip to do worse than
`grep` while its tool schemas occupy context on every turn.

What a service would genuinely add is the concept-known, identifier-unknown
query. The MVP relies on existing source headings and selective reading; it
generates no maps (S-25, `ARCHITECTURE.md` §6.4.3).

**The published evidence is mixed and should not be cherry-picked.** Anthropic
reports agentic search outperforming RAG substantially for code, on precision,
freshness, and having no index to drift. Cursor measured the opposite on their
own benchmark: +12.5% average accuracy for semantic search over grep alone
(6.5%–23.5% by model), with online A/B showing code retention up 2.6% on
codebases over 1,000 files and dissatisfied follow-ups up 2.2% when it was
withheld — and concluded explicitly hybrid. The sharpest framing available is
that you trade latency and tokens for flexibility: grep wins where the keyword is
known or derivable, embeddings win where you can only reference an oblique aspect
of the thing.

Two factors put this document set on the favourable side. Cursor's failure
example is grepping `validate` and drowning in hits — ambiguous, repeated names.
This set has `LPSPI1_CR` and `REQ-DIAG-0412`: unique, unambiguous, and literally
the subject of the question. Their gains also concentrated in large codebases.

One factor does not. The oblique-reference query exists here too — "how do I stop
the watchdog resetting during flash programming" contains no identifier — and
existing headings may not give the agent the vocabulary it needs. So the deferred tool is
**more likely to be needed than this decision's framing suggests**, and the
trigger is specific:

> Build it when concept-known, identifier-unknown queries defeat search and
> selective reading of source documents more than occasionally in real use. Log the
> misses; do not decide from intuition.

If the trigger fires, `ByteAsk-Embedded-MCP` (MIT) is a plausible starting point:
an MCP server for page-cited firmware retrieval whose corpus and engine sit
behind a pluggable `SearchBackend` seam, which is the shape needed to point it at
Caiman-materialized documents.

*Settled 2026-08-20. Supersedes D-06 and D-11. Retrieval trigger updated
2026-09-15 when S-25 removed generated maps.*

### S-19. The human declares the session mode; Caiman holds no agent policy

`caiman sync --mode open|sealed` takes the decision directly. `open`
materializes public documents only; `sealed` materializes everything the project
version pins. The flag is required and has no default.

Every enforcement mechanism considered — a server that refuses, a kernel that
returns `EACCES`, a filter that excludes — acts at the moment of *read*, when
nothing knows what the work is for. At session start the human knows exactly, and
the harness is already asking which project. Asking one more question costs
nothing.

**An earlier version of this decision had Caiman own an agent map**
(`~/.config/caiman/agents.toml`), translating agent names into what they could
receive. Removed, for three reasons in ascending order of seriousness: it had to
be hand-maintained and did not travel with the store, so machines could diverge;
it invented a vocabulary of agent names that nothing else defined; and it could
be **silently wrong**, because a profile keyed on an agent name asserts something
about the model, and one harness can drive either kind.

The third is disqualifying on this project's own terms. A control that can be
systematically wrong while appearing authoritative is the "shape of a gate with
none of the substance" that S-19 already rejects model-identity checks for.
Removing the map is that principle applied consistently, not a relaxation of it.

What is lost is a guardrail against a momentary lapse — with a map, a distracted
engineer could not hand a frontier session the full document set. Accepted,
because the guardrail only worked when the map was right. A convenience layer may
return later on one condition: **it may narrow the mode, never widen it.**

An optional `--agent-label`, supplied by the harness-specific hook adapter, is
recorded in the materialization log as an **unverified annotation**. It names the
harness, not the model, and is not an input to any decision.

Caiman remains explicitly **not an enforcement boundary**. Filesystem hardening
is an option, not the design. `SECURITY-MODEL.md` §5.

*Settled 2026-08-20; agent map removed 2026-09-15.*

### S-20. Documents are linked from a content-addressed cache, not copied

A reference manual is roughly 20 MB of markdown; a project pinning twenty is a
few hundred MB per session, and cheap session startup is the premise the design
rests on. `sync` links from a per-compartment cache keyed by digest: APFS
`clonefile` on macOS, `cp --reflink` on btrfs/XFS, hardlink with mode `0444`
otherwise, real copy across filesystems.

Three rules are not negotiable, each recorded because it has bitten somebody: no
symlinked directories in the documents tree, cache keyed by compartment, and
blobs and materialized documents kept read-only. They are I-9; the mechanics are
`STORAGE.md` §7.3.

*Settled 2026-08-20.*

### S-21. A filesystem content-addressed store, laid out as an OCI subset

Blobs by digest, manifests by digest, refs as tags, compartments partitioned at
the top level. No database and no running service.

S-18 shrank the store's job to: hold immutable artifacts, resolve name to digest,
fetch, keep compartments apart, never lose a pinned digest. At hundreds of
documents that is not a database problem. The layout is a deliberate OCI subset
so graduating to a registry is mechanical rather than a migration.

Full specification and the alternatives analysis are in `STORAGE.md`.

*Settled 2026-09-14. Resolves D-02 and D-10 for the MVP; the graduation trigger
remains open as D-02.*

### S-22. The store is kept in one private git repository

The whole store — every compartment — lives in a single private git repository,
with compartments as directories inside it. Push refuses a non-private remote.

**An earlier version of this decision used one repository per compartment.** That
was reversed. Separate repositories buy host-enforced access control *between*
compartments, which matters only when a person should see one and not another —
and there is no such person. Compartments here are one engineer holding several
counterparties' secrets, not multi-tenancy, and this project's own convention
says not to build abstraction for hypothetical tenants.

Two facts settled it. **Every store repository is private regardless** — `public`
in this design means visible to every session, not publishable, since vendor
manuals are under click-through agreements and redistributing them is a licensing
violation. So the per-compartment boundary was separating the engineer from
themselves. And **GitHub has no per-directory read permission**, so within git
the choice is repository-level or nothing.

The cost of the earlier design was recurring: per customer, create a repository,
set visibility, wire a remote, clone it on every machine. One repository makes a
new compartment a `mkdir`.

**What makes the simple default safe is that splitting is cheap.** Git is
transport and backup; the content-addressed tree is the source of truth, and
history is not load-bearing. When a real access boundary appears, copy that
compartment's directory into a new private repository and repoint its remote. The
configuration supports per-compartment remote overrides for exactly this, and for
the counterparty whose agreement forbids third-party storage. If the migration is
cheap, do not build it early.

**What it costs:** one visibility mistake now exposes every compartment rather
than one, and repository size grows faster. The first is why push verifies
privacy and `init` deliberately does not create the repository.

**And what git costs regardless:** history is permanent. A mislabeled document,
once pushed, requires history rewriting on every clone rather than a delete, and
forks and host caches may retain it. Two consequences are load-bearing — **ingest
never pushes**, with a label review between, so the cheap fix exists in the window
where mistakes are found; and a compartment correction after push is an incident
rather than a chore (`SECURITY-MODEL.md` §8).

Git does not carry file modes, so `0444` on blobs and `0700` on compartment
directories are restored after every clone and pull, before anything else runs.

Full specification in `STORAGE.md` §6.6, §7.5, §7.6, §9.4, §9.5.

*Settled 2026-09-14; revised from per-compartment repositories to a single
repository the same day.*

### S-23. Session integration is via harness hooks, as thin adapters over the CLI

Caiman registers callbacks at the harness's own extension points: session start
to configure or warn, tool-use events to record reads, stop events to close the
record.

This does not reopen S-01. Caiman is not managing sessions; it is using
extension points a harness already publishes, and a harness with no hook
mechanism degrades to the manual path (D-07) rather than breaking.

**All logic lives in `caiman session start|record|end`.** The hook adapter only
translates the harness's event format. Hook mechanisms are harness-specific — the
shapes differ and some harnesses have none — so keeping logic in the CLI makes a
second harness a new adapter rather than a second implementation. This is the
line that stops session integration from becoming harness coupling.

Two consequences worth stating. **The hook cannot prompt the engineer**: hooks
run non-interactively, so the start hook injects context and the *agent* asks
which project to use. Selection is conversational rather than a startup dialog.
And **Caiman now runs during a session**, which an earlier version of
`ARCHITECTURE.md` denied; the form is narrow — string parsing and an append, no
store access, no resolution.

`ARCHITECTURE.md` §6.10, §9.2.

*Settled 2026-09-14.*

### S-24. Audit has two layers: what could be read, and what was read

The materialization log is written by `sync`, is deterministic, is complete, and
does not depend on the agent cooperating. The access log is written by hooks
during the session, has finer granularity, and is **incomplete** — `Bash` reads
cannot be reliably attributed, hooks may not be installed, subagent coverage is
unverified, and anything outside the harness is invisible.

They are complementary. An earlier version of `SECURITY-MODEL.md` argued against
tool-call logging *as a replacement* for materialization logging, and that
argument still holds; adding it as a second layer is a different proposition.

**The access log's strongest justification is forensic, not compliance.**
`harness.md` establishes that transcripts persist plaintext of everything read,
outside Caiman's reach. Until now, "which compartmented documents are in which
transcript" had no answer. The access log answers it, converting residue from an
unbounded unknown into an enumerable list. That is the difference between a gap
you can act on and one you can only worry about.

Because it is incomplete, **absence of a record is never proof of non-access**,
and that must be stated wherever the log is surfaced rather than only in the
design documents. The logs are also metadata-sensitive — a path naming a
customer's specification reveals the relationship — so they live outside the
worktree under restrictive permissions and are never committed to any repository.

`SECURITY-MODEL.md` §9.

*Settled 2026-09-14.*

---

### S-25. Ingest registers one unchanged Markdown file

A document version contains one user-prepared Markdown file plus human-supplied
metadata. Store the exact input bytes in one content blob; apply explicit access
labels to the entire document. Retain document-level provenance and immutable
manifest pins.

**Usable headings are required.** Admission validates nonempty, unambiguous
heading paths covering the document. Requirement-structured documents must also
contain IDs matching their declared pattern. Invalid input is rejected with
locations and reasons; Caiman does not fix it or use line-only citations.
`ARCHITECTURE.md` §6.4.2 owns the detailed admission rules.

The workflow is **select file → supply metadata → review → register**. Importing
a manual does not require board or project authoring. Those declarations remain
separate. S-27 defines ingestion through a TUI; S-28 defines board/project
authoring through a TUI and editable JSON drafts. This decision does not require an AI service or an AI-assisted
preparation workflow.

No splitting, stored chunks, generated maps or outlines, summaries, semantic
tagging, or content rewriting. Conversion and cleanup happen outside Caiman.
Agents search existing headings and identifiers and read selected line ranges;
a several-hundred-page file does not need to be loaded whole into context.

**Alternatives considered:** whole-file registration with a generated outline;
deterministic heading-based splitting; accepting externally prepared chapter
bundles. The MVP chooses whole-file registration alone. Navigation improvements
must earn their scope through real retrieval failures, rather than being bundled
into ingest.

**Costs accepted:** no chapter-level deduplication across revisions, potentially
larger blobs for the remote, and dependence on source headings for navigation.
Heading validation establishes structure, not conversion fidelity, completeness,
or correct application of a requirement. G08 and G09 remain evaluation work.

This resolves the stored-Chunk question in ARCHITECTURE.md and STORAGE.md,
replaces the former splitting/map responsibilities, and narrows I-5's admission
implementation without weakening its citation requirement.

*Settled 2026-09-15 by user choice of whole-file registration with usable headings.*

---

### S-26. Original-source and converter provenance are optional

Registration requires the Markdown artifact and its document metadata, not the
source PDF or conversion history. Both `source` and `converter` objects, and
their individual fields, are optional. Omit unknown values. Missing information
must not imply local conversion, public access, or verified source identity.

Keep only `original_filename`, automatically captured from the input Markdown.
The author convention is that conversion retains the source basename; do not
store or request a second source filename. Optional source metadata consists of
a checksum and page count. Optional converter metadata consists of name, version,
and hosted/local information. The Markdown digest and size are always computed.

This gives up source-file and converter traceability where provenance is absent,
while retaining exact identification of the bytes the agent reads. Supplied
optional fields are validated, but omitted fields never block registration.
`STORAGE.md` §6.4.1 owns the stored representation.

*Settled 2026-09-15 by user instruction.*

### S-27. Ingestion uses a TUI; the future GUI is a native macOS app

`caiman ingest [markdown]` opens a terminal form for document metadata, optional
provenance, and review before local registration. With no file argument, select
the file in the TUI. Explicit access labels have no default. Invalid entries are
shown with actionable errors; cancelling publishes no version and changes no ref.
`ARCHITECTURE.md` §6.4.3 owns the workflow and field contract.

This is required MVP scope: the manifest needs enough human input that a long
flag list or hand-authored sidecar is not the initial user interface. A
noninteractive ingestion format is deferred; invocation without an interactive
terminal fails with an explanation and no writes.

Keep validation and registration independent of terminal widgets. The planned
GUI is a native macOS app using the same operations and manifest rules, not a
separate storage or validation implementation. The app's implementation and
schedule are post-MVP. Board/project authoring is specified by S-28.
A TUI framework is an implementation choice, not settled here.

*Settled 2026-09-15 by user instruction. Resolves D-09's form-factor choice.*

---

### S-28. Board and project authoring use a TUI and editable JSON drafts

The user chose both a terminal UI and configuration files. JSON drafts map to
board/project manifest fields, with schema fields generated when absent. The TUI
uses top-level forms and JSON collection editors for parts, links, documents,
precedence, and features. Both paths call shared validators and registration
logic; `AUTHORING.md` owns the concrete workflow and field contract.

Document selectors may use an explicit ref or digest and compartment. Review
resolves missing digests within the allowed scope. Board documents are public;
project documents must fit the project's declared compartments. Governing feature
references bind to the project's already selected documents or precedence set.
Digests are authoritative thereafter, even if diagnostic refs move.

A new-version command copies the complete selected snapshot into the TUI,
retaining its pins and adding human-declared lineage. Registration stores the
whole edited snapshot. No version ordering, inheritance resolution, obligation
inference, or compliance status is introduced. Read-only validation, version
listing, and private JSON export make the result inspectable outside the TUI.

Both TUIs use a shared sparse terminal theme inspired by Claude Code: warm orange
accents, muted secondary text, simple controls, and keyboard navigation. Respect
terminal color preferences, including NO_COLOR. Caiman keeps its own branding.
Input fields use full borders and a subtle fill so their boundaries remain
visible without focus; the active field has an orange border. This refines the
initial bottom-border layout following user feedback about unclear boundaries.

*Settled 2026-09-15 by user instruction: TUI plus config files and a Claude
Code-inspired terminal appearance. Resolves ARCHITECTURE.md §8.6 Gap B / G13.*

---

### S-29. Create boards and projects on demand; choose them explicitly every time

Opening `caiman` goes straight to the home screen. There is **no default board or
project**: nothing is preselected, nothing is remembered as "current", and every
action that operates on one — view (and edit from there), create a project on a board —
asks the engineer to choose it. The board declares hardware parts; the project
pins the board version the engineer chose and declares its customer and
compartments. Document lists can start empty, so creation does not depend on
manuals already being stored.

Ingestion offers existing project and board versions, plus actions to create
new ones and return to the document form. Selecting a board part supplies its
declared issuer/part identity; selecting a project supplies its program and
compartment context. Version labels remain opaque and pinned board identities
remain authoritative. No hardware facts or classification are derived from text.
Access remains an explicit human choice reviewed before document registration.

The terminal may remember the compartments of explicitly chosen projects locally
for the next launch, but never which board or project was chosen. These preferences are not shared manifests, session modes, or
an authorization boundary. Catalog discovery never expands them by scanning for
other private compartments. Document registration does not silently revise
existing board or project snapshots; adopting a document into their pinned sets
remains an explicit configuration edit.

The interface says **compartment**, the same word as the stored field, the CLI
flag and the design documents. An earlier revision of this decision renamed it
to “access group” in the TUI only, on the grounds that “compartment” reads as
jargon. That was reverted: two names for one concept cost more than the jargon
did, because error messages are machine-shaped but human-read, so a user who
had only ever seen “access groups” was told that “projects must carry named
compartments” on failure. One word everywhere, with the customer examples in
the hint text carrying the explanation instead.

Rejected alongside it: **ip**, which in firmware names an IP block or IP core
long before it suggests anything about confidentiality, and Internet Protocol
after that. A compartment also names a party rather than a thing owned, so the
word is the wrong shape for what S-16 says the model is. **counterparty** is
accurate and is what this document already calls it in prose, but it is not
worth a breaking change to the stored `compartments` field in
`caiman.document/1` and `caiman.project/1`.

*Settled 2026-09-15 by user instruction: guide first-time board/project setup,
then offer existing selections and creation actions during ingestion. Amended
2026-09-16 by user instruction: the interface says “compartment” everywhere,
reverting the “access group” wording; remove the concept of a default board
and project;
the forced first-launch setup and saved selection went with it.*

---

### S-30. The bare command is a dashboard with shared Vim-style navigation

Running `caiman` opens the primary human interface: a grid of implemented
document, board, and project capabilities. Boards and projects each get only
**Create** and **View**; editing starts from the item being viewed, and JSON
import, export, validation, and templates stay direct commands (amended
2026-09-16 by user instruction: too many options). Home tiles share the dotted
card border.
Individual commands remain available for direct invocation and agent tooling;
this does not make currently interactive commands noninteractive.

Edits start from a complete pinned snapshot. The user chooses a new opaque
version with declared lineage, or explicitly repoints the selected version tag,
then reviews the full edited configuration before registration. Existing digest
pins remain resolvable. Editing a board does not silently change a project.

The terminal uses a pure black canvas, bright green accents, and full
field outlines — a real caiman's colouring (amended 2026-09-16 by user
instruction, replacing the original pure black canvas and warm orange accents). Shared keyboard controls use `hjkl` for directional tile navigation
and previous/next control movement in forms. Enter or `i` starts text editing;
Escape returns to navigation. Editing preserves ordinary `hjkl` text input.
Dropdowns support `j/k` to move, Enter or `l` to select, and Escape or `h` to close.
In navigation mode, `q` closes the current menu or returns from a form, and quits
from the dashboard. An open dropdown closes first. During text editing `q`
remains ordinary input; cancellation guards still prevent interrupted writes.
Navigation is Vim keys only: no Ctrl+Q/Ctrl+R shortcuts, no key footer, and no
command palette. The mode hint is the one prompt at the bottom of every screen
(amended 2026-09-16 by user instruction, for consistency).

*Settled 2026-09-15 by user instruction: expose features in a grid on bare
`caiman`, support board/project modification, Vim keys, and a black background
with a Claude Code-inspired appearance.*

---

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

No longer "assemble components or install a RAG product" but "build a layer or
adopt a platform".

| Option | For | Against |
|---|---|---|
| **Build the layer** | Fits the domain exactly; minimal ops; adoption is an afternoon; no lock-in; every hour goes to the normative half nobody serves | The descriptive and structural halves must be built competently despite not being differentiated |
| **Embedder** | Datasheet-aware agent; schematic graph parsed from native EDA files — automatic derivation, better than a hand-maintained registry; HIL execution; on-prem and air-gapped; actively seeking design partners | A platform adopted whole. No visible model of specification sets, program freeze, deviations, or per-counterparty compartmentation. Procurement rather than a `sync` command. Early-stage |
| **RAGFlow / Onyx** | General document platforms with permissions and citations | No notion of a board, a program, or a feature; chat-product-shaped; Onyx's permission-sync is `ee/`-licensed |
| **Open-source pieces** (`ByteAsk-Embedded-MCP`, `sheetsdata-mcp`, generic RAG-over-MCP, `kicad-sch-api`) | MIT-licensed, composable, no procurement | Each covers one slice; the good corpora behind them are hosted and proprietary; none models a board, program, or compartment. Parts, not an answer |

This straddles two questions. As an *internal tool* it is build-versus-buy,
turning on whether a platform's descriptive and structural layers are good enough
on your documents and EDA format — empirical, and not settleable from marketing
copy. As a *product* the remaining gap is narrow enough that a platform could
close it.

*Leaning: build the layer.* The scope stays small enough for one engineer, the
normative half is where the unserved problem is, and files-on-disk is adoptable
without procurement. Revisit if the descriptive half consumes more than its
allotted two weeks. See `VISION.md` §4, re-surveyed 2026-09-16: Embedder's
published scope grew, silicon vendors began serving their own catalogues to agents
over MCP, and the versioned, compartmented and normative gaps all held.

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

### D-08. Sample / test project

Requirements: open-source hardware and software, freely obtainable
specifications, several distinct parts in distinguishable roles, documents
markable as *pretend-confidential*, and **at least two board versions** with a
part swapped or a silicon revision changed, so the change summary and the "right
fact, wrong board" failure can be demonstrated rather than asserted.

Gaggiuino is under consideration — an espresso-machine controller with an MCU,
sensors, and a display. Confirm part diversity and version history.

The normative half has no open-source analogue: there is no public customer
specification set to borrow and real ones cannot be committed (I-3). So the
sample needs a **synthetic specification set** — invented requirement IDs, a
handful of features, a deviation amending two or three requirements, and two
releases so the freeze rule can be exercised. This is a feature rather than a
compromise: synthetic specifications let the negative tests assert exact
behavior, and building two exercises compartment isolation with no exposure.

*Open: confirm part diversity and multi-version availability; write the synthetic
specification sets.*

### D-09. Front-end form factor *(resolved 2026-09-15 by S-27)*

The MVP requires a TUI for document ingestion. The future GUI is a native macOS
app for authoring and curation. Both use shared validation and registration
operations; no local web frontend is planned. S-28 now defines board/project editing through a TUI and JSON drafts. The
Mac app's schedule remains to be designed.

This changes the human authoring interface, not the filesystem interface used
by coding agents. Semantic retrieval remains deferred under S-18, and a separate
human-facing documentation browser remains a non-goal.

### D-12. How program deviations are represented

For now, assume deviations arrive as a single document at the top of the declared
precedence order, naming the requirement IDs it amends so `grep` surfaces the
override. That is enough for the MVP and is what the current design assumes.

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

### D-13. How far the board schema should follow industry board descriptions

G14 asks which engineering source to import from. Surveying what board-level
description files actually carry answers a prior question: what a board file
should contain at all.

They fall into two families that barely overlap. **Software-facing** — devicetree
and its bindings, Zephyr `board.yml`, CMSIS-Pack PDSC `<boards>`, PlatformIO
board JSON, Arduino `boards.txt`, mbed `targets.json`, Yocto machine `.conf` —
describe a board so firmware can boot on it. **Hardware-facing** — KiCad
schematics and netlists, Altium, IPC-2581 (DPMX), ODB++, CycloneDX HBOM —
describe a board so it can be built and bought. Nothing bridges them.

What they commonly carry: board identity and revision; a component inventory;
interconnect, as either bus hierarchy or nets; addressing and register data;
capability flags; assembly variants; toolchain, flash and debug glue; a
machine-readable schema; and vendor extension points. Of all of them, only
CMSIS-Pack links a component to its documentation, and only as a bare URL.

What none carry: design intent, so no counterpart to a part's role (S-12);
document linkage with a version and a locator (I-5); immutability or pinning
(I-4); silicon-revision applicability for a document; a rationale paired with a
declared relationship (S-15); cross-domain identity across schematic, devicetree
and orderable part number; compartmentation; and any normative program context at
all. Most of that list Caiman already answers, which is evidence for D-04.

Four gaps are real and open in `caiman.board/1`:

- A document about the **assembly** — board user guide, schematic, stackup,
  assembly errata — cannot be pinned at all, because `_pin` requires a document's
  `issuer/part` to match a part instance. For a vendor evaluation board this is
  usually the most useful document there is.
- **Links carry no explanation**, though every other declared relationship pairs
  with one: `derives_from` with `relation`, `features[].related` with `relation`,
  `precedence[].note`. `ARCHITECTURE.md` §6.5.1 says peripheral names stay verbatim
  because renaming them would break "the one thing a link description is useful
  for", and then there is no field to put that description in.
- **No place for cross-domain identifiers** beyond `refdes`, so the schematic,
  devicetree and procurement names for one part cannot sit together.
- **Part identity is a packed string.** `"part": "nxp/s32k344"` fuses two fields
  that `caiman.document/1` already stores separately, and the format is implicit —
  nothing in the field name says the slash is meaningful. So `_pin` rebuilds the
  string it compares against, `document.get("part", "")` papers over documents that
  carry a `program` instead of a `part`, and the ingest rule that a document has
  exactly one of the two is invisible at the board.

| Option | For | Against |
|---|---|---|
| **Leave `/1` alone** | No migration; the model stays minimal | Assembly documents stay unpinnable, which is a real hole rather than a deferred nicety |
| **Notes only** — `note` on links and on document selectors | Two lines of validator; closes the inconsistency with every other declared relationship; no decision needed | Leaves assembly documents unpinnable |
| **`caiman.board.v2` as drafted below** | Closes all four gaps; stored `caiman.board/1` snapshots stay valid and unmigrated (S-11), with readers accepting both | Splitting part identity makes v2 a breaking authoring change rather than a purely additive one; board-level documents contradict "a board version pins the vendor documentation for its parts" (`ARCHITECTURE.md` §6.5.1); moving `refdes` into `aliases` amends S-12's wording |
| **Industry parity** — features, nets, register data, toolchain glue | Importers map nearly field-for-field | Breaks S-01, I-5 and I-8 at once. Rejected |

Draft of the third option. New and changed fields marked:

```jsonc
{
  "schema": "caiman.board.v2",
  "board": "falcon-mainboard",
  "version": "2.1",
  "vendor": "acme",                                    // NEW
  "notes": "Dual-MCU safety mainboard.",               // NEW, unstructured
  "derives_from": "2.0",
  "relation": "Adds the secure element; boot flash moved to QSPI.",

  "documents": [                                       // NEW, board level
    { "ref": "acme/falcon-mainboard/board-user-guide/2.1",
      "compartment": "public",
      "notes": "Connector pinout and jumper defaults." }  // NEW on selectors
  ],

  "parts": [
    { "role": "application-mcu",
      "vendor": "nxp",                                 // CHANGED, was "nxp/s32k344"
      "part": "s32k344",
      "silicon_revision": "1.1",
      "aliases": { "refdes": "U1", "mpn": "S32K344EHTAR", "devicetree": "cpu0" },  // NEW; refdes moved here
      "notes": "Runs the safety-rated application image.",         // NEW, unstructured
      "documents": [
        { "ref": "nxp/s32k344/reference-manual/Rev%204",
          "compartment": "public",
          "notes": "Errata 051234 applies at this mask revision." } ] },
    { "role": "safety-companion",
      "vendor": "ti",
      "part": "tps65313",
      "silicon_revision": "A",
      "documents": [] }
  ],

  "links": [
    { "name": "safety-link",
      "between": ["application-mcu.LPSPI1", "safety-companion.SPI"],
      "notes": "Watchdog handshake; the companion resets the MCU if the question and answer sequence stops." }  // NEW
  ]
}
```

`vendor` and `part` are separate on a part. The name is `vendor` because it is
the word an engineer reaches for and the one CMSIS-Pack uses (`Dvendor`). The
cross-check in `_pin` becomes two field comparisons instead of rebuilt string
equality, and a board part document can be required to carry a `part` rather than
a `program`, which the packed form cannot express.

This diverges from `caiman.document/1`, which calls the same identity `issuer`, so
the check compares `document.issuer` with `part.vendor`. That makes explicit an
assumption the packed form hid: a board part's documents are issued by the part's
vendor. It holds for vendor documentation, which is what a board pins; a
third-party application note about a vendor's part would fail it. Reconcile the
two words when `caiman.document` next revises, rather than leave a second
`compartment`/access-group split in the stored schemas.

Board-level documents would resolve against `<vendor>/<board>`, mirroring the
per-part rule, which makes the board's `vendor` required whenever they are
present.

**`notes` is the one place for unstructured information**, on the board, on each
part, on each link and on each document selector. Nothing parses it, validates its
content, or branches on it; it is rendered, like every other human declaration
under S-15. Every other field stays structured, so an agent or a reader can tell
at a glance which text is a declared fact and which is commentary. The project
schema still spells its equivalent `precedence[].note`, singular — reconcile it
when `caiman.project` next revises.

**`refdes` is removed as a field.** A reference designator moves into `aliases`
alongside the other cross-domain identifiers, so `aliases` is justified by a real
use rather than an imagined one: every `caiman.board/1` part carrying `refdes`
maps to `aliases.refdes` in v2. S-12's rule is unchanged — a designator is still
cross-reference metadata, never the identity and never the display name — but its
wording, which names `refdes` as a field, should point at `aliases` once this is
adopted. `aliases` keys and values are declared strings that nothing interprets.

Migration follows from S-11 rather than needing machinery. Stored snapshots are
immutable, so existing boards keep `caiman.board/1` and are never rewritten; the
loader accepts both literal strings and authoring emits `caiman.board.v2`. Nothing
re-registers, and `schema` earns its place in the manifest.

The string changes shape at v2: `caiman.board.v2`, not `caiman.board/2`. That
leaves the board out of step with `caiman.document/1` and `caiman.project/1`,
which still carry the slash, and it stops the value being derivable from kind and
number by the single f-string `_base` uses today — a table of accepted literals
replaces it. Worth settling for all three kinds here rather than rediscovering it
at the next project or document revision.

Deliberately excluded, each on an existing decision:

| Excluded | Offered by | Why not |
|---|---|---|
| Build flags, flash algorithms, upload and debug config | PlatformIO, Arduino, CMSIS `<debugInterface>` | S-01 |
| Register maps, `reg` and `interrupts` | Devicetree, CMSIS-SVD | I-5 — facts come from documents with a locator, not restated uncited in config |
| Capability and feature lists | CMSIS `<feature>`, mbed `device_has`, Yocto | Anything on the board that matters is a part with a role; a feature list is a second, uncitable way to say it, and collides with project features under S-14 |
| Nets and pin-level connectivity | EDA netlists, IPC-2581 | Links are declared intent, not extracted topology (I-8) |
| Fitted/DNP and assembly variants | Altium variants, KiCad | A variant is another opaque board version (S-11, I-7) |
| Lifecycle status | PLM, vendor packs | Status that rots — the S-14 argument |
| Compartment labels on a board | — | Boards are public by construction (S-13) |

Each field added here competes for the brief's context budget, which `VISION.md`
§4.3 puts at roughly 150 lines by the convention's own hard-won guidance. That is
an argument for adding fields the brief can omit, and against any field it would
have to carry for every part on every turn.

*Leaning: take the notes now — they need no decision and close an inconsistency
the design documents already assume is closed. Decide board-level documents
against a real vendor evaluation board, not in the abstract; that is the half
that changes §6.5.1. `aliases` no longer needs holding: absorbing `refdes` gives
it a concrete first use from existing boards.*

---

## Retired

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
