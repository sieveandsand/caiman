# Decisions

Three sections: **settled** (do not relitigate without a reason), **open**
(choose deliberately, and record the choice here when you do), and **retired**
(decisions the scope no longer requires — kept so the reasoning is not
rediscovered).

Each open decision lists the options and their real trade-offs. Where there is
a leaning, it is marked as a leaning, not a conclusion.

---

## Settled

### S-01. Caiman is a layer, not a platform

Session management, worktree isolation, terminal multiplexing, and
hardware-in-the-loop test execution are all somebody else's job, permanently.
Caiman assembles context, writes it into a worktree, and gets out of the way. The
agent is whichever you already use; the harness is whichever you already run.

This is now a positioning decision as much as a scoping one. Platforms in this
space bundle the agent, the orchestration, the test execution, and the knowledge
layer and are adopted together (see D-04). Choosing the layer buys adoption in an
afternoon rather than a procurement cycle, no lock-in to an agent or model or
harness, and a scope one engineer can keep correct — which is the actual
constraint here. It is a distribution and scope argument, not a claim of
technical superiority, and whether layer or platform is the better bet is
unsettled.

### S-02. Documents are immutable, versioned artifacts

Git's model — one version is current, the rest is history — cannot express
"many silicon revisions are simultaneously live." Content-addressed artifacts
can. Pin digests, never tags.

### S-03. Classification comes from provenance, assigned at ingest

Not inferred from content, ever. See `SECURITY-MODEL.md` for why content
inspection cannot work on this data.

### S-04. Filesystem + grep is the primary retrieval path

Exact-identifier lookup is a lexical problem. Semantic search is the fallback,
not the default. The MCP server does not sit in front of file reads; only model
calls and semantic queries go through it.

### S-05. Fail closed, everywhere

Missing or unreadable classification produces an unreachable chunk, not a
public one. This is invariant I-1 in `CLAUDE.md`.

### S-06. Citations are mandatory; requirement IDs where available, heading path as the floor

A citation is `(document identity, document version, locator)`. All three are
required. The locator is the most specific thing available, and the floor is a
**heading path** — `§12.4.3 → LPSPI Control Register (CR)` — with a page number
included when the conversion supplied one.

Page anchors were originally mandatory. They were relaxed because conversion
now happens outside Caiman (S-08) and page boundaries frequently do not survive
it, while headings do. A heading path is also the more useful locator in
practice: a human finds a section faster than a page.

**For requirement-structured documents — OEM specifications — the locator is the
requirement ID**, and that is strictly better. Requirement IDs are stable across
releases within a line, greppable, unambiguous, and durable across
re-conversion: swap the converter later and every existing citation still
resolves, which a heading path or page number would not. They also give the
normative side the same lexical exact-lookup property register identifiers give
the datasheet side. That symmetry is what lets the whole design work without a
retrieval service (S-18): both halves of the corpus are greppable, and grepping
a requirement ID returns the base requirement and any deviation amending it
together.

What is **not** relaxed is document identity and version. A citation reading
"the S32K3 manual says" without a version is worthless, because versioning is
the entire problem — and on the normative side it is worse than worthless,
because a program is contractually frozen at a specification release.

*Settled 2026-08-20; extended with requirement-ID locators 2026-08-20.*

### S-07. A project version is the complete pin set; there is no repo-side lockfile

An earlier design put a `caiman.lock` in the firmware code repository. It was
removed. Selection is per *session* — concurrent sessions may work on two
programs and two board versions from the same checkout — and a repo-level file
cannot express that. Worse, a repo file claiming one project while the session
was launched against another is the "right fact, wrong project" failure
manufactured by the tool built to prevent it. Two sources of truth for "which
project am I on" is one too many.

Pinning lives in the version artifacts. A board version pins the vendor
documentation for its parts; a project version composes a board version and pins
the OEM specification releases, so resolving `project @ version` yields
everything transitively. Traceability, if it is ever wanted, is a commit trailer
the harness writes from the live session, which cannot drift.

*Settled 2026-08-20; amended for the project/board split 2026-08-20 (see S-13).*

### S-08. PDF → markdown conversion is out of scope

Caiman ingests markdown that has already been converted, plus asserted
provenance including converter identity and version. The conversion category is
competitive and improving monthly; maintaining another parser is not where the
gap is.

Two consequences are load-bearing and recorded elsewhere: converter identity is
part of provenance (`ARCHITECTURE.md` §1), and converting a confidential
document through a hosted service is a disclosure outside Caiman's control, so
it becomes a documented user responsibility (`SECURITY-MODEL.md`).

*Settled 2026-08-20. Supersedes D-01.*

### S-09. The brief is open and metadata only

That a board contains a secure element, and that a program requires SecOC, are
structure; what the part's manual and the OEM's specification *say* is content.
Only the second is confidential. So the brief is an ordinary unclassified file —
one brief, not an open one and a sealed one — and the agent knows the restricted
parts and features exist and that their details are behind the server.

Customer identity is the one thing this does not cover: "we are building for OEM
X" is frequently itself under NDA. The brief therefore refers to the program by
its internal **codename**, which is what codenames are for. The customer stays in
the registry, compartmented, and there is a test asserting customer identity does
not appear in a generated brief.

The counterpart is invariant I-6: the brief generator reads the project and board
artifacts and the document manifest and has no access to chunk text, so it cannot
leak restricted content even by accident.

*Settled 2026-08-20; extended to project briefs and codenames 2026-08-20.*

### S-10. Version labels are opaque; lineage is declared

`2.1` supersedes `2.0` at one company and is a special variant of it at
another; a third uses `Rev B` or `EVT2`. Caiman stores the label verbatim,
never parses it, never orders it, never computes "latest", and supports no
wildcard matching.

Where lineage matters — choosing a baseline for the brief's diff section — it
is an explicit `derives_from` edge a human declares, with a free-text
`relation` that Caiman displays and never branches on. The registry records
semantics; the code does not compute on them.

This applies to project versions (`B-sample`, `PVT`) exactly as it does to board
versions. A corollary: a bare board or project name never resolves to a version.
It returns the list.

*Settled 2026-08-20.*

### S-11. Versions are stored whole and authored by delta

Authoring says "start from 2.0, change these three things." Storage holds a
complete, self-contained, immutable snapshot. No inheritance resolution at read
time, no version that fails to resolve because its parent was mislinked, and the
brief's diff is a comparison of two complete snapshots.

This applies to project versions too, and it is what keeps hand-declared features
from rotting: cutting a new project version starts from the previous one, so
features carry forward by default and the human edits a delta rather than
re-deriving a list.

*Settled 2026-08-20.*

### S-12. Parts are identified by role

`U4` is a fact about a schematic; `safety-companion` is a fact about the design
and is what a human or agent can reason with. Reference designators may ride
along as optional cross-reference metadata, but they are never the identity and
never the display name. Peripheral instance names (`LPSPI1`) stay exactly as
the vendor writes them, because that is what you search the manual for.

*Settled 2026-08-20.*

### S-13. Board is hardware; project is the session unit

They are separate entities. A `Board` describes hardware — parts in roles, links,
silicon revisions — and knows nothing about customers or specifications. A
`Project` is what a session is *about*: it composes a board version with an OEM
specification set, a declared precedence order, a feature set, and a
confidentiality compartment.

They were fused in an earlier draft. The split is required because the same
hardware ships into more than one customer program. Fusing them would force
physically identical boards to be registered twice — a lie about the hardware —
and would put customer identity into the hardware model, where it cannot be
compartmented.

The naming was always pointing here: the brief has been `.caiman/project.md`
throughout, and a board is a component of a project rather than a synonym for
one.

*Settled 2026-08-20.*

### S-14. Features are first-class; they declare scope, never status

An agent cannot make a good decision about secure flashing if it does not know
the program requires secure flashing, which specification governs it, and that it
shares a key hierarchy with secure boot. A `Feature` carries exactly that:
`governed_by` (specification document versions, and requirement IDs where
available), `realized_on` (part instances), and `related` (other features, with a
free-text explanation).

Features are the join between the normative and hardware sides. Without them a
project brief is two disconnected lists and the agent has to guess how they
relate.

A feature declares **scope** — `required` or `not-used` — and never
**status**. `not-used` is valuable: telling an agent the program does not use OTA
update stops it from helpfully adding it. `in-progress`, `implemented`, and
`verified` are compliance tracking, which is ALM's job and is an explicit
non-goal. This line will get pushed on; it is written down so the answer is
already recorded.

There is no OEM feature catalogue. An OEM's programs do not reliably share a
feature set, so features are declared per project version by a human, once. They
do not need re-deriving, because S-11 makes a new project version start from its
predecessor.

*Settled 2026-08-20.*

### S-15. Declared relationships are rendered, never inferred

Three things now work the same way: lineage between versions (`derives_from` plus
free-text `relation`), the precedence order among specification documents, and
the relationships between features. All three are supplied by a human with an
explanation. Caiman displays them and never computes on them.

This is one principle, not three coincidences, and it is load-bearing. It is what
keeps Caiman out of interpreting contracts, inferring one company's version
numbering, and detecting conflicts between specifications — all of which are
tempting, all of which are unreliable, and all of which would make Caiman's
output something you have to check rather than something you can cite.

Corollary: no automatic conflict detection between specifications, ever. If a
program deviation amends a requirement, a human says so by naming the requirement
IDs; retrieval then surfaces it. That is a retrieval behavior, not a precedence
engine.

*Settled 2026-08-20.*

### S-16. Classification asks whose secret this is, not how secret it is

There is no tier scale. A document is either asserted **public** or carries one
or more **compartments** naming the counterparty it belongs to. Visibility
requires a session to hold every compartment a document carries.

A sensitivity scale cannot express what this data needs. Two customers'
specifications are equally confidential and must be mutually invisible; whatever
numbers you assign, one is greater than or equal to the other and sees it.
Compartments are categories, not levels — being read into one tells you nothing
about another.

Underneath this sits an asymmetry worth stating plainly. **Vendor documentation
is treated as public**: nominally confidential, practically semi-public
(click-through agreements, wide mirroring, hundreds of suppliers holding
identical copies, every frontier model having almost certainly seen the family),
and expensive to gate for close to no benefit. **Customer material is
compartmented**: a handful of suppliers hold it, its contents identify whose it
is, and the agreement is with the party whose business you are trying to keep.
Building one mechanism for both forced the expensive treatment onto the cheap
case. If a genuinely restricted vendor document ever arrives, the compartment
mechanism handles it with no new machinery.

Default to per-counterparty compartments, since that is how the agreement is
written and it lets a base specification be shared across that customer's
programs. A document may carry several compartments, so tightening a specific
document to a single program later requires no migration.

The mechanism needs no invention: access labels were already a frozen *set* of
prefixed strings with an `is_public` flag. Missing metadata is neither public nor
compartmented and stays unreachable — I-1 is untouched.

*Settled 2026-08-20; replaced the tier scale 2026-08-20.*

### S-17. Licensed standards are not hosted

ISO, AUTOSAR, and MISRA documents stay out of the corpus. Licensing aside, OEM
specifications are largely self-contained in practice: they state their own
requirements rather than layering deviations over a standard, so the precedence
chain does not lose a layer by their absence. Where a specification does cite a
standard, that is a citation in its text like any other and Caiman does not model
it.

An earlier draft proposed identity-only stubs for referenced standards so a
citation could read "OEM 3.2 §7.2.1, overriding ISO 14229 §11.4." Dropped as
unnecessary once self-containment was confirmed.

*Settled 2026-08-20.*

### S-18. The filesystem is the interface; there is no server in the MVP

`caiman sync` writes the brief, the resolved project structure, and the corpus
into the session's workspace. The agent reads and greps them with the file tools
it already has.

This is S-04 followed to its conclusion. Exact-identifier lookup is a lexical
problem — always the argument for register identifiers, and stable requirement
IDs (S-06) made the normative half lexically exact too. With both halves
greppable, a retrieval service adds a round-trip to do worse than `grep`, while
its tool schemas sit in context on every turn costing more than the brief they
were meant to supplement.

What a service would genuinely add is semantic fallback for the one query grep
cannot serve: the concept is known, the identifier is not. Generated per-document
maps — heading tree, requirement-ID ranges, identifier index, emitted at ingest
as plain markdown — cover much of that without an embedding model, a vector
store, or a process. Not as good as good semantic search; considerably better
than nothing; inspectable when wrong.

**The published evidence is genuinely mixed and should not be cherry-picked.**
Anthropic's reported finding is that agentic search outperformed RAG by a wide
margin for code, on precision, freshness, and the absence of an index to drift.
Cursor measured the opposite on their own benchmark: semantic search gave +12.5%
average accuracy over grep alone (6.5%–23.5% by model), with online A/B showing
code retention up 2.6% on codebases over 1,000 files and dissatisfied follow-ups
up 2.2% when it was withheld. Their conclusion was explicitly hybrid — heavy use
of grep *and* semantic search, combined. The sharpest available framing is that
you trade latency and tokens for flexibility: grep wins where the keyword is
known or easily derived, embeddings win where you can only reference some oblique
aspect of the thing.

Two things put this corpus on the favourable side of that line. Cursor's example
of grep failing is searching `validate` and drowning in hits — ambiguous, repeated
names in a codebase. This corpus has `LPSPI1_CR` and `REQ-DIAG-0412`: unique,
unambiguous, and literally the subject of the question. And their gains
concentrated in large codebases, with modest effect elsewhere.

One thing does not. The oblique-reference query exists here too — "how do I stop
the watchdog resetting during flash programming" contains no identifier — and
generated maps are a weaker instrument against it than embeddings. So the honest
position is that the deferred semantic tool is **more likely to be needed than
this decision's framing suggests**, and the trigger should be specific rather
than vague:

> Build it when a real query, of the concept-known-identifier-unknown kind,
> defeats both grep and the generated maps and this is observed more than
> occasionally in actual use. Log the misses; do not decide from intuition.

If that trigger fires, `ByteAsk-Embedded-MCP` (MIT) is a plausible starting
point rather than a from-scratch build: it is an MCP server for page-cited
firmware document retrieval whose corpus and retrieval engine sit behind a
pluggable `SearchBackend` seam, which is exactly the shape needed to point it at
a Caiman-materialized corpus. Worth evaluating before writing one.

*Settled 2026-08-20. Supersedes D-06 and D-11.*

### S-19. The human picks the agent; Caiman owns the map

Every enforcement mechanism considered — a server that refuses, a kernel that
returns `EACCES`, a filter that excludes — acts at the moment of *read*, when
nobody knows what the work is for. At session start the human knows exactly, and
the harness is already interrupting them to ask which project they are on.

So: the engineer is responsible for picking the right agent for the task, and
Caiman makes that choice consequential by materializing a different corpus
depending on it. Get it wrong toward the open side and the specifications are
absent, the agent says so, and you restart sealed — loud, harmless,
self-correcting. Get it wrong toward the sealed side and a weaker model did work
it did not need to. Both directions fail safe.

The agent-to-material map lives in Caiman (`~/.config/caiman/agents.toml`), not
in the harness: one place to answer "what could this session see", an unknown
agent name fails closed rather than receiving whatever the harness asserted,
policy survives harness changes, and the brief can state the session mode
truthfully because the same code computed it.

Caiman is explicitly **not an enforcement boundary**. Filesystem hardening — a
separate uid, an encrypted image — is available as optional hardening and is not
the design.

*Settled 2026-08-20. Resolves D-05.*

### S-20. The corpus is linked from a content-addressed cache, not copied

A reference manual as markdown runs 10–20MB; a project pinning twenty of them is
a few hundred MB per session, and cheap session startup is the premise the design
rests on. `sync` links from a per-compartment blob cache keyed by digest: APFS
`clonefile` (`cp -c`) on macOS, `cp --reflink` on btrfs/XFS, hardlink with mode
`0444` otherwise, real copy across filesystems.

Three rules that are not negotiable, recorded because each has bitten somebody:
never symlink a directory into the corpus (ripgrep skips symlinks without `-L`
and `grep -r` skips symlinked directories, producing *silent* incompleteness);
key the cache by compartment (hardlinks share an inode, so mode lives on the
inode and a shared cache path defeats a restricted directory); keep blobs and the
corpus read-only (an in-place edit propagates through every hardlink and poisons
the cache).

*Settled 2026-08-20.*

---

## Open

### D-02. Artifact store backend

Now stores board *and project* versions as well as documents, which changes the
weighting: these are small JSON-ish objects, read on every session start, needing
cheap listing by name and cheap diffing against a parent.

| Option | For | Against |
|---|---|---|
| **OCI registry via ORAS** | Immutable digests free; per-path auth free; annotations carry metadata; reference types can attach errata to a manual; likely already exists at work; boring and battle-tested | Whole-layer pulls; GC can prune untagged manifests; listing or searching by board name is awkward |
| **Object store + Postgres manifest** | Schema fully under your control — matters more now that board versions, lineage edges, and part instances need modeling; consolidates with the index | More code; you rebuild immutability and auth semantics yourself |
| **lakeFS** | Git-like branching over object storage | Another substantial system; branching is the wrong axis for board versions anyway |
| **DVC** | Familiar, git-adjacent | Built for ML datasets; weak metadata and auth story here |

*Leaning shifted toward Postgres.* The model — board versions, project versions,
declared lineage, part instances with per-instance silicon revisions, links,
features with edges to both documents and parts — is relational and is queried on
every session start. That was the stated tiebreaker in the original version of
this decision ("Postgres if variant modeling turns out to be the hard part"), and
the scope changes made it central rather than peripheral.

### D-03. Index backend — deferred, not chosen

S-18 removed the semantic index from the MVP entirely, so this decision is no
longer on the critical path. It becomes live only if grep plus generated maps
proves insufficient in real use.

| Option | For | Against |
|---|---|---|
| **Postgres + pgvector + Postgres FTS** | One service; hybrid lexical + semantic; trivial ops; consolidates with the manifest and the registry | Weaker ranking than dedicated engines at scale |
| **OpenSearch** | Strong hybrid retrieval; Onyx's ACL filter implementation applies directly | Another cluster to operate |
| **Qdrant / Weaviate / Milvus** | Good vector stores | Vector-only; you still need lexical alongside |

Corpus size here is tens of thousands of chunks, not hundreds of millions.

*Leaning: Postgres if it is ever needed, and more strongly now that D-02 leans
the same way. Do not build it speculatively — the trigger is in S-18, and it
requires logged misses rather than a hunch. Note that S-18 now judges this more
likely to become live than the original framing implied, and that an existing
MIT-licensed server with a pluggable backend may remove the need to choose a
backend at all.*

### D-04. Build the context layer, or adopt a platform?

The shape of this decision changed once it became clear the category has funded
entrants. It is no longer "assemble components or install a RAG product" but
"build a layer or adopt a platform."

| Option | For | Against |
|---|---|---|
| **Build the layer** (store + registry + brief + materialization) | Fits the domain exactly; minimal ops; adoption is an afternoon; no lock-in to an agent, model, or harness; every hour goes to the normative half nobody serves | The descriptive and structural halves have to be built competently even though they are not differentiated |
| **Embedder** (YC-backed, in production 2026) | Datasheet-aware agent over vendor documentation; schematic graph parsed from native EDA files into components, nets, pin assignments and power topology — automatic derivation, better than a hand-maintained registry; HIL execution; multi-agent orchestration; on-prem and air-gapped deployment; actively seeking design partners | A platform, adopted whole: agent, orchestration, and test execution come with it. No visible model of customer specification sets, program freeze, deviations, or per-counterparty compartmentation. Procurement conversation rather than a `sync` command. Early-stage, so roadmap and longevity are open |
| **RAGFlow / Onyx** | General document platforms with permissions and citations | No notion of a board, a program, or a feature; chat-product-shaped; Onyx's permission-sync is `ee/`-licensed |
| **Open-source pieces** (`ByteAsk-Embedded-MCP`, `sheetsdata-mcp`, generic RAG-over-MCP, `kicad-sch-api`) | MIT-licensed, composable, no procurement; several are exactly the substrate this project would otherwise write | Each covers one slice; the good corpora behind them are hosted and proprietary; none models a board, a program, or a compartment. Useful as parts, not as an answer |

Worth being honest that this straddles two questions. As an *internal tool*, the
question is build versus buy and the answer turns on whether the platform's
descriptive and structural layers are good enough on your actual documents and
EDA format — an empirical question that marketing copy cannot settle. As a
*product*, the remaining gap is narrow enough that a platform could close it.

*Leaning: build the layer.* The scope stays small enough for one engineer to keep
correct, the normative half is where the unserved problem is, and files-on-disk
is adoptable inside a company without procurement — which is exactly the friction
a platform carries. Revisit if the descriptive half turns out to consume more
than its allotted two weeks. See `VISION.md`, Adjacent work.

### D-07. Harness strategy

Load-bearing: the harness asks the engineer which project *and which agent* a
session is for, creates the worktree, calls `caiman sync`, and launches. Caiman
does not build it.

That places one hard requirement on the candidate: **per-session agent and model
selection**. A harness that drives a single backend cannot express the choice
S-19 is built on, which narrows the field and should be verified before adopting
anything.

The obligation on Caiman is an interface clean enough for someone else to drive:
`caiman sync --project P --version V --agent A --into DIR`, with no assumption
that Caiman owns the file or knows what a session is. Until a harness exists, the
same command plus a one-line `@.caiman/project.md` import is the manual path —
which is good, because it exercises the interface from day one.

Candidates by maintenance health: `ccmanager` (MIT, tidy, small), `agent-deck`
(MIT, responsive maintainer), `emdash` (Apache-2.0, funded team). Avoid
`claude-squad` (AGPL-3.0 is a real constraint for anything that might ship
internally). `Crystal` is effectively dead — renamed to Nimbalyst. Xirp itself
has been discussed as a model; whether it is obtainable outside Spotify and under
what licence is **unverified** and should be checked before planning around it.

Note that worktree isolation, the primitive these are built on, does not address
the actual bottleneck in firmware: one board, one probe, one CAN interface.

*Open: adopt one and contribute project selection upstream, or write a thin
launcher that shells out to `caiman sync` and then to an existing harness.*

### D-08. Sample / test project

Requirements: open-source hardware and software, freely obtainable
specifications, several distinct parts in distinguishable roles, and suitability
for marking some documents *pretend-confidential* to exercise compartment
behavior end to end. Plus **at least two board versions**, ideally with a part swapped or a
silicon revision changed between them, so the brief's diff section and the
"right fact, wrong board" failure can be demonstrated rather than asserted.

Gaggiuino is under consideration — an espresso-machine controller with an MCU,
sensors, and a display. Worth confirming it has enough part diversity and enough
version history.

The normative half has no open-source analogue: there is no public OEM
specification set to borrow, and real ones cannot be committed (I-3). So the
sample project needs a **synthetic OEM spec set** — invented requirement IDs, a
handful of features, a deviation document amending two or three requirements, and
two spec releases so the freeze rule can be exercised. This is a feature, not a
compromise: synthetic specs let the negative tests assert exact behavior, and
building two of them exercises compartment isolation with no NDA exposure at all.

*Open: confirm part diversity and multi-version availability; write the synthetic
spec sets.*

### D-09. Front-end form factor

CLI for the MVP. Three later surfaces, and they must not be conflated:

- **Admin/curation** — register boards and projects, cut versions, declare
  features and precedence, upload converted documents with provenance and
  compartments, correct a mislabel. A human workflow that CLI flags serve badly
  past a few dozen documents, and the place where a typo becomes a mislabeled
  document or a cross-compartment leak. Feature and precedence declaration are
  structured editing, which is the form a CLI serves worst. This is wanted.
- **An MCP server for semantic fallback only** — see S-18. Built only if grep
  plus generated maps demonstrably falls short.
- **A documentation browser for humans** — still a non-goal.

*Open: form factor and timing for the admin surface. A local web app is the
obvious answer and contradicts nothing, since the non-goal was always about
serving document content for reading, not about curation. Do not let it start
before the layers beneath it are correct.*

### D-10. How a board or project version is represented in the store

Independent of D-02's backend choice. These artifacts need to be
content-addressed, small, listable by name, and diffable against their parent.

| Option | For | Against |
|---|---|---|
| **A JSON/TOML document, hashed** | Trivial to diff, review, and hand-edit; readable in a store browser | Needs an external index to list boards by name efficiently |
| **Relational rows + a computed digest** | Natural queries, cheap listing | Digest must be computed over a canonical serialization or immutability is a lie |
| **OCI artifact with a config blob** | Consistent with documents if D-02 goes ORAS | Awkward listing; overkill for a 4KB object |

*Leaning: a canonical JSON document is the source of truth and the thing that is
hashed, with relational rows as a derived index. That keeps immutability honest —
the digest covers exactly one artifact — and keeps listing fast. It also means
reshaping the model later (features gaining a field, say) is a change to a
derived view rather than a store migration.*

### D-12. How program deviations are represented

For now, assume a program's deviations arrive as a single document that sits at
the top of the declared precedence order, and that it names the requirement IDs
it amends so `find_requirement` can surface the override. That is enough for the
MVP and it is what the current shape assumes.

It will not hold forever. Deviations are often a spreadsheet or a letter rather
than a specification, they arrive incrementally over a program's life, and they
may be per-part-number rather than per-program. The open question is whether they
stay documents or become annotations attached to requirement IDs.

| Option | For | Against |
|---|---|---|
| **A document, like any other** | Zero new machinery; ingests, chunks, and cites identically | Incremental deviations mean re-ingesting a growing document; no structured "which requirements are amended" query without parsing |
| **Structured amendments on requirement IDs** | Exact override lookup; incremental additions are cheap; a deviation is small and structured by nature | A second content path; someone has to enter them, and hand entry is where mislabels happen |
| **Both — document is the artifact, amendments are a declared index over it** | Citation stays to the real document; override lookup is exact | Two things to keep in sync, mitigated if the index is derived at ingest |

*Leaning: the third, but only once the first becomes painful. Do not build it
before there is a real deviation document to look at.*

---

## Retired

### D-05. Routing enforcement *(resolved 2026-08-20 by S-19)*

Weighed a self-hosted AI gateway, a separate OS user with stdio transport, a
sealed sandbox containing the harness, and doing nothing under a zero-retention
agreement. All four tried to enforce, at read time, a judgement the human had
already made at session start.

Resolved by moving the decision to the human and making it consequential through
differential materialization. The gateway and separate-uid options survive as
optional hardening in `SECURITY-MODEL.md` rather than as the design.

### D-06. MCP tool granularity *(retired 2026-08-20, superseded by S-18)*

Weighed few fat tools against many thin ones, and had settled on roughly five fat
working tools plus a session-startup trio. Moot once the server left the MVP:
six of the seven tools duplicated file operations the harness already performs
better, and the seventh (semantic search) is deferred. If a server is ever built
for semantic fallback, it will have one tool and this decision will not need
reopening.

### D-11. What the harness calls at session start *(resolved 2026-08-20 by S-18)*

Weighed shelling out to the CLI against an MCP call against both. Resolved to the
CLI by S-18, which removed the server. The byte-identical-output concern that
motivated "both" disappears with it.

### D-01. PDF → markdown parser *(retired 2026-08-20, superseded by S-08)*

Originally the highest-risk component: everything downstream inherits a
parser's errors, and layout-aware parsers are known to drop content silently
rather than erroring — a missing register table row becomes a wrong answer that
looks right. The plan was a bake-off between LlamaParse, Docling, MinerU,
OpenDataLoader, and PaddleOCR against a real reference manual, with a leaning
toward a local parser for confidential material regardless of how the
candidates scored on public documents.

Retired because conversion left Caiman's scope. The underlying risk did not
disappear, it moved: it now lives in the user's choice of converter, and Caiman
addresses what it still can — recording converter identity in provenance so a
bad conversion can be traced, and rejecting documents whose chunks lack
resolvable locators (`ARCHITECTURE.md` §1). The confidentiality observation
survives as a security note rather than a parser choice: **a compartmented
document must not be sent to a hosted converter**, and Caiman cannot enforce
that.

---

## Recording a decision

When an open item is resolved, move it to **Settled** with a one-paragraph
rationale and the date. When scope removes the need for one, move it to
**Retired** with what the risk was and where it went. Keep rejected options
visible — future-you will want to know what was already considered and why it
lost.
