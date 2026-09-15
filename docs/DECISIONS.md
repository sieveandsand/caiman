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

### S-03. Labels come from provenance, assigned at ingest

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

*Settled 2026-08-20; extended with requirement-ID locators 2026-08-20.*

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

Caiman ingests already-converted markdown plus asserted provenance including
converter identity and version. The conversion category is competitive and
improving monthly; maintaining another parser is not where the gap is.

Two consequences are load-bearing: converter identity is provenance
(`ARCHITECTURE.md` §6.4.1), and converting a confidential document through a
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
query. Generated per-document maps cover part of that without an embedding model
or a process (`ARCHITECTURE.md` §6.4.3).

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
maps are a weaker instrument than embeddings against it. So the deferred tool is
**more likely to be needed than this decision's framing suggests**, and the
trigger is specific:

> Build it when concept-known, identifier-unknown queries defeat both grep and
> the generated maps, observed more than occasionally in real use. Log the
> misses; do not decide from intuition.

If the trigger fires, `ByteAsk-Embedded-MCP` (MIT) is a plausible starting point:
an MCP server for page-cited firmware retrieval whose corpus and engine sit
behind a pluggable `SearchBackend` seam, which is the shape needed to point it at
Caiman-materialized documents.

*Settled 2026-08-20. Supersedes D-06 and D-11.*

### S-19. The human picks the agent; Caiman owns the map

Every enforcement mechanism considered — a server that refuses, a kernel that
returns `EACCES`, a filter that excludes — acts at the moment of *read*, when
nothing knows what the work is for. At session start the human knows exactly, and
the harness is already asking which project.

So the engineer picks the agent, and Caiman makes it consequential by
materializing a different document set depending on the choice. Both error
directions fail safe.

The agent map lives in Caiman (`~/.config/caiman/agents.toml`) rather than the
harness: one place to answer "what could this session see", an unknown name fails
closed rather than receiving whatever the harness asserted, policy survives
harness changes, and the brief can state session mode truthfully because the same
code computed it.

Caiman is explicitly **not an enforcement boundary**. Filesystem hardening is
available as an option and is not the design. `SECURITY-MODEL.md` §5.

*Settled 2026-08-20. Resolves D-05.*

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

---

## Open

### D-02. When to move the store to an OCI registry

The backend is decided (S-21). What remains is the threshold for change, stated
in `STORAGE.md` §12.3:

> Move to an OCI registry when compartment separation must be real
> authentication rather than POSIX permissions — a second person, a second
> machine with different trust, or a store that stops living on hardware you
> control.

At that point ORAS earns its keep: compartments map to repositories with separate
credentials, immutability is enforced by the system rather than by convention,
and retention becomes configuration rather than discipline. For a single engineer
on one machine it is operational surface with no corresponding benefit.

*Open: nothing to decide until the threshold is met. Recorded so the trigger is
not forgotten.*

### D-03. Index backend — deferred, not chosen

S-18 removed the semantic index from the MVP, so this is off the critical path.
It becomes live only if the miss log shows grep plus generated maps failing.

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
allotted two weeks. See `VISION.md` §4.

### D-07. Harness strategy

The harness asks which project *and which agent*, creates the worktree, calls
`caiman sync`, and launches. Caiman does not build it.

One hard requirement on any candidate: **per-session agent and model selection**.
A harness driving a single backend cannot express the choice S-19 rests on. Verify
before adopting.

Caiman's obligation is an interface clean enough for someone else to drive:
`caiman sync --project P --version V --agent A --into DIR`, with no assumption
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

### D-09. Front-end form factor

CLI for the MVP. Three later surfaces, not to be conflated:

- **Admin / curation** — register boards and projects, cut versions, declare
  features and precedence, upload documents with provenance and compartments,
  correct a mislabel. A human workflow the CLI serves badly past a few dozen
  documents, and the place where a typo becomes a mislabeled document or a
  cross-compartment leak. Feature and precedence declaration are structured
  editing, which is the form a CLI serves worst. Wanted.
- **An MCP server for semantic fallback only** — S-18.
- **A documentation browser for humans** — still a non-goal.

*Open: form factor and timing for the admin surface. A local web app contradicts
nothing, since the non-goal was always about serving document content for
reading. Do not start before the layers beneath it are correct.*

### D-12. How program deviations are represented

For now, assume deviations arrive as a single document at the top of the declared
precedence order, naming the requirement IDs it amends so `grep` surfaces the
override. That is enough for the MVP and is what the current design assumes.

It will not hold forever. Deviations are often a spreadsheet or a letter, they
arrive incrementally over a program's life, and they may be per-part-number
rather than per-program.

| Option | For | Against |
|---|---|---|
| **A document, like any other** | Zero new machinery; ingests, splits, and cites identically | Incremental deviations mean re-ingesting a growing document; no structured "which requirements are amended" query |
| **Structured amendments on requirement IDs** | Exact override lookup; incremental additions are cheap | A second content path, and hand entry is where mislabels happen |
| **Both — document is the artifact, amendments a declared index over it** | Citation stays to the real document; override lookup is exact | Two things to keep in sync, mitigated if the index is derived at ingest |

*Leaning: the third, once the first becomes painful. Do not build before there is
a real deviation document to look at.*

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
can — recording converter identity so a bad conversion can be traced, and
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
