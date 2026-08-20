# Vision

## Origin

Caiman started from a question about Spotify's Xirp: what would the equivalent
look like for hardware? The answer turned out not to be "Xirp with a different
logo." Xirp solves an organizational problem — coordinating dozens of concurrent
agent sessions across thousands of engineers — and pairs it with Portal, a
service catalog that grounds each session in institutional context.

Firmware work has a different shape:

- **Parallelism is bounded by physics, not filesystems.** Worktree isolation
  works in web development because the only contended resource is the working
  tree. In firmware there is one dev board, one debug probe, one CAN interface.
  Fifty agents can compile in parallel; they cannot flash in parallel.
- **The context that matters is documentation, the board, and the program.**
  Portal answers "who owns this service and what depends on it." The firmware
  equivalents are "what is the correct value for this field on *this* silicon
  revision," "what is actually on the board I am working on," and "what has the
  customer mandated for this program."

So Caiman keeps the insight — context is the product, the agent is
interchangeable — and applies it to the context firmware engineers lack.

## Three kinds of context, three failure modes

**Descriptive context** — what the hardware *does*. Datasheets, reference
manuals, errata. Missing it produces a **wrong fact**: a register offset that is
not what the manual says. Compiles cleanly, fails on hardware. Feedback loop:
hours.

**Structural context** — what *this* design is. Parts in roles, links, silicon
revisions, board version. Missing it produces **right fact, wrong board**: a
peripheral the board does not route, a bus arrangement from a different board
version, a silicon revision never populated. The retrieved text was accurate;
the work is thrown away rather than repaired. Feedback loop: a review cycle or
an integration.

**Normative context** — what this program *must* do. *Normative* is the standards
term of art: ISO, IEEE and AUTOSAR documents mark their binding requirement
clauses **normative** and their explanatory material **informative**, and a
customer specification is normative end to end. Where a datasheet states a fact
about the world, a specification states an obligation imposed by a contract.

So: the customer's specifications for secure boot, secure onboard communication,
secure flashing, diagnostics; which features apply here; which spec release the
program is frozen at; which requirements a program deviation has amended. Missing it produces
**correct and non-compliant**: right by the datasheet, right for the board, and
in violation of the specification — because the agent did not know the feature
was mandated at all, or applied a default in an area a deviation amended, or
used a newer release than the one the program is contractually frozen at.
Feedback loop: the customer's acceptance test, months later.

The discriminator across the three is what "wrong" means. Violate a datasheet and
the silicon fails you — that is physics imposing the obligation. Violate a
specification and everything works, and you are in breach — that is your customer
imposing it. You can negotiate a deviation with an OEM; you cannot negotiate one
with a setup-and-hold time.

Cost rises with the length of the feedback loop, and so does plausibility. The
third failure produces confident, well-cited, entirely reasonable-looking work
that survives review and propagates into everything built on top of it. That is
precisely why it needs a tool rather than more diligence.

## Thesis

**Context is the product, and the normative layer is the part nobody is
supplying.**

The descriptive and structural layers are necessary substrate. They are also
increasingly well served (see *Adjacent work*), and Caiman should treat them as
table stakes rather than as the differentiator — building them competently, not
inventively.

What remains genuinely unserved is everything downstream of the customer: the
specification set, the features it mandates, the release the program is frozen
at, the deviations that amend it, and the requirement that one customer's
material be unreachable from another customer's session. That last point has an
external driver — TISAX brings AI data access into assessment scope for
suppliers handling OEM data, with access-management and logging requirements —
so compartmentation is not merely prudent, it is increasingly something a
supplier has to be able to demonstrate.

## Adjacent work

Caiman is not alone in this space and these documents should not pretend
otherwise. The useful way to read the landscape is by layer: the descriptive and
structural layers are being filled in from several directions at once, the
hardware-interaction layer is crowded, and the normative layer is empty.

### Platforms

**Embedder** (YC-backed, in production as of 2026) is the closest. It ships a
datasheet-aware agent grounded in vendor documentation, a knowledge graph built
from datasheets and internal documents, a schematic graph parsed from native EDA
files into components, nets, pin assignments and power topology, hardware-in-the-
loop test execution against real probes and analyzers, multi-agent orchestration,
and on-premises and air-gapped deployment. Several things an earlier draft of
this document claimed nobody was building, it builds — including a structural
model derived automatically from EDA source, which is a better mechanism than a
hand-maintained registry.

### Open source, by layer

**Descriptive — open plumbing, closed corpora.** `ByteAsk-Embedded-MCP` (MIT) is
the closest open-source analogue to Caiman's document half, describing itself as
a source-grounded, page-cited evidence-retrieval server for coding agents writing
firmware and driver code. What is open is the server shell: the retrieval engine
and corpus sit behind a pluggable `SearchBackend` seam and power a hosted
endpoint over their own licensed materials, with no bring-your-own-documents
story. `sheetsdata-mcp` does component datasheets on demand, from their
extraction rather than yours. Below that sits a tier of generic RAG-over-MCP
servers that ingest documents and return citations but know nothing of hardware,
boards, versions, or compartments — building blocks rather than competitors.

**Structural — readers exist, nobody assembles them.** `kicad-happy` gives
coding agents KiCad skills (schematic analysis, PCB review, EMC pre-compliance,
datasheet cross-referencing), and `kicad-sch-api` is a plain library for reading
schematic files. Both are *design-side*: helping you design a board, not telling a
firmware agent what is on one. The maintainer of the curated
`awesome-mcp-hardware` list reaches the same conclusion independently — nothing
there models complete boards, project-level context, board revisions, or document
access control.

**Hardware interaction — crowded.** `embedded-mcp` (cross-vendor bring-up,
flashing, diagnostics, UART capture), `stm32-mcp`, `scope-mcp`. The piecemeal
open-source counterpart to what the platforms bundle as HIL. Reassuring rather
than threatening: the job Caiman permanently declines is well served at both ends
of the market.

**Normative — only the public half.** `AutonomousGuy` ships open-source agent
skills for AUTOSAR Classic and Adaptive, MISRA C, and ISO 26262, framed as giving
coding agents the domain context they lack. That is the *same pattern* as the
brief, which is worth noticing — but it covers standards: public, static, and
identical for every supplier. The rest of the neighbourhood is compliance
*checking* rather than context (CodeQL's AUTOSAR C++ and CERT C++ queries,
NaiveSystems Analyze, Artop) — static analysis after the fact, not the governing
requirement at implementation time.

Nothing found models a customer specification set, a program frozen at a release,
deviations amending requirements by ID, or compartmentation between customers.

### The landscape at a glance

Surveyed 2026-08-20. The question asked was narrow: is there a single open-source
project that both takes **your own documents** and models all three kinds of
context? There is not.

| | BYO docs | Descriptive | Structural | Normative | Domain model |
|---|---|---|---|---|---|
| `ByteAsk-Embedded-MCP` | ✗ hosted corpus | ✓ | ✗ | ✗ | none |
| `sheetsdata-mcp` | ✗ | ✓ component-level | ✗ | ✗ | none |
| Generic RAG-over-MCP | ✓ | agnostic | agnostic | agnostic | none |
| Onyx / RAGFlow | ✓ | agnostic | agnostic | agnostic | none, but real ACLs |
| `kicad-happy` / `kicad-sch-api` | ✓ design files | ✗ | ✓ design-side | ✗ | schematic only |
| `AutonomousGuy` | ✗ ships standards | ✗ | ✗ | ✓ public standards only | none |
| *Embedder* (not open source) | ✓ | ✓ | ✓ EDA-derived | ✗ | board |

"Agnostic" is the important cell. A general-purpose retrieval system will happily
ingest a datasheet, a schematic export, and a customer specification — bytes in,
chunks out. It covers all three layers only in the sense that it does not
distinguish them. It has no notion of a board, a silicon revision, a program
frozen at a specification release, a feature and what governs it, or a
compartment.

So "covers all three" has two meanings, and only one of them is unserved:

- **Indexes documents of all three kinds.** Many options. Do not build another.
- **Models all three domains.** Nothing.

One disambiguation, because it surfaces in any search here: GitHub's `spec-kit`
is *spec-driven development* — you author a specification for the feature you are
building and generate from it. That is the opposite direction. It concerns specs
you write, not a customer's binding specification you must conform to.

### What this landscape settles

**The documents are a solved problem; the model is not, and that is the whole
project.** This is the sentence to come back to when the scope feels uncertain.

**The brief mechanism is commodity, and that is fine.** `AGENTS.md` is an open
format used by tens of thousands of projects, with generators that scan a repo
and emit one. Caiman should not claim the injected-context file as an innovation.
It confirms the filesystem-first decision (S-18) and locates all the value in
*what goes in the file*, which is where these documents put it.

**The descriptive layer is substrate, not moat.** If an MIT-licensed server that
already does page-cited firmware retrieval adds bring-your-own-documents, it
covers most of that half. Build it cheaply rather than lovingly.

Note that S-18 already collapsed most of that build-versus-buy question by
accident. With the filesystem as the interface, the descriptive layer reduces to
*chunk, label, write markdown to disk* — there is no retrieval service left to
build or to buy, because the deliverable is files. The question survives in only
two places: the deferred semantic tool (S-18 names a candidate), and ingest
chunking, where the work is small and domain-specific enough — do not split a
register table, do not split a requirement — that borrowing would not help.

**This survey will go stale.** An earlier draft of this document asserted that
nobody was building the hardware documentation layer; that was false within
months and stayed in the docs until someone checked. Re-run the question before
relying on the answer, and date the result when you do.

### Layer, not platform

**The difference in ambition is deliberate.** Embedder is a *platform*: the
agent, the orchestration, the test execution, and the knowledge layer, adopted
together. Caiman is one *layer* — context assembly — that writes files into a
worktree and gets out of the way. The agent is whichever you already use. The
orchestration is whichever harness you already run. Session management, test
execution, and hardware scheduling are all somebody else's job, permanently.

What follows from choosing the layer over the platform:

- Adoption is an afternoon, not a procurement cycle. `caiman sync` writes a
  directory; nothing else changes.
- No lock-in to an agent, a model, or a harness. When the frontier moves — and
  it moves quarterly — you change one config line.
- The scope stays small enough for one engineer to keep correct, which is the
  actual constraint here.
- If the platform bet turns out to be right, the ideas are portable and little
  is lost.

This is a distribution and scope argument, not a claim of technical superiority,
and it should stay labelled as such. Whether platform or layer is the better bet
is unsettled.

## Who this is for

A firmware engineer working on a multi-chip embedded project — a zonal
controller, say, with several MCUs, a clock generator, a safety companion chip,
and external NVM — built to a customer's specification, with vendor and customer
documentation under separate agreements, who already uses coding agents daily and
is losing time to the agent being confidently wrong about the hardware, the
board, or the program.

Design for that person. Multi-user, multi-tenant, and team features are deferred
until a second user exists.

## Design commitments

**The project is the unit of context.** Not the chip, and not the board. A
project composes a board version with a customer specification set and the
features that program requires. That is what a session is *about*, and it is
what gets handed to the agent before the first turn.

**Board is hardware; project is program.** Deliberately separate, because the
same hardware ships into more than one customer program, with different spec
sets, different mandated features, and different confidentiality compartments.

**A project version is the pin set.** A project version names exactly which board
version, which document versions, which silicon revisions, and which
specification release it consumes. There is no second place where pinning
happens, because two sources of truth for "which program am I on" is one too
many.

**Features are first-class.** An agent cannot make a good decision about secure
flashing if it does not know the program requires it, which specification governs
it, and that it shares a key hierarchy with secure boot. Features are the join
between the normative and hardware sides.

**The filesystem is the interface.** `sync` writes a brief, the resolved project
structure, and the corpus into the session's workspace. The agent uses the file
tools it already has. No server, no retrieval service, no tool schemas consuming
context on every turn. Exact-identifier lookup — register identifiers on one
side, requirement IDs on the other — is a lexical problem, and `grep` is very
good at lexical problems.

**The human picks the agent; Caiman makes the choice consequential.** Generic
work starts a session on a frontier harness; work touching customer material
starts a session on a local model. Caiman does not adjudicate that decision — it
materializes a different corpus depending on it, so a wrong choice surfaces as a
missing file rather than as a silent disclosure. Both error directions fail safe.

**Caiman records declared relationships and renders them. It never infers them.**
Version lineage, specification precedence, and relationships between features are
supplied by a human with a free-text explanation. This keeps Caiman out of
interpreting contracts, inferring one company's version numbering, and detecting
conflicts between specifications — all tempting, all wrong.

**The user supplies the documents, already converted.** Caiman ships no corpus
and does no PDF parsing. Conversion is a solved, competitive, fast-moving
category. This is a constraint and also the moat: a tool that works with
documents you already have is adoptable without a procurement conversation.

**Version semantics belong to the company.** One organization's 2.1 supersedes
2.0; another's is a variant of a base 2.0; a third uses `Rev B` or `EVT2`. Caiman
stores the label verbatim, never parses it, and records lineage only where a
human declares it.

**Classification asks whose secret this is, not how secret it is.** Vendor
documentation is treated as public — nominally confidential, practically
semi-public, and expensive to gate for almost no benefit. Customer material is
compartmented per counterparty, because two customers' specifications are equally
sensitive and mutually invisible, which a sensitivity scale cannot express.

**Existence is structure; detail is content.** That a board has a secure element
and that a program requires SecOC are facts about the design. What the manual and
the specification *say* is content. This is what lets the brief be an ordinary
unclassified file. Customer identity is handled by referring to the program by
codename.

**An uncitable fact is worthless.** A retrieved value the engineer cannot verify
against the original document is not usable in a design review, an audit, a
safety case, or a customer acceptance test. Citations are the acceptance
criterion.

## Success criteria for the MVP

1. A session starts, the engineer picks a project and an agent, and the agent
   begins with an accurate picture of the board, the mandated features, and which
   specification release the program is frozen at.
2. An agent asked for a register field returns the correct value with a document,
   version, and locator citation the engineer can open and confirm.
3. An agent asked what governs a requirement returns the governing text, cited by
   requirement ID, and says so when a program deviation amended it.
4. Asking the same question against two project versions with different board
   versions or silicon revisions returns two correctly different answers.
5. A session started with a frontier agent provably contains no customer
   specification on disk, and a session for one customer provably contains
   nothing belonging to another — both by negative test, not by inspection.
6. A document with missing labels is materialized nowhere and returned to nobody.
7. The engineer stops opening reference manuals and specifications by hand for
   lookups they used to do manually, and stops correcting the agent about which
   board and which program it is working on.

Criterion 7 is the real one. The others are how you get there.

## Explicit non-goals

| Not doing | Why |
|---|---|
| Agent orchestration, session or worktree management | Commodity, and where the platforms are competing. Caiman produces the brief; a harness injects it |
| Hardware-in-the-loop test execution or scheduling | A real problem, and one others are already solving. Not the context layer |
| PDF → markdown conversion | Solved elsewhere and moving fast |
| Requirements or compliance management | ALM's job. Caiman cites a requirement; it does not track whether you met it |
| Conflict detection between specifications | Precedence is declared, not computed. Inferring it means interpreting contracts |
| Hosting licensed standards (ISO, AUTOSAR, MISRA) | Licensing, and customer specifications are largely self-contained in practice |
| Being an enforcement boundary | The human picks the agent. Caiman makes that consequential; it does not police it |
| A human-facing documentation *browser* | The consumer is an agent. An admin surface for curation is a different thing and is on the roadmap |
| Bundling or redistributing vendor or customer documentation | Licensing, and it breaks the core design commitment |
| Content-inspection-based confidentiality detection | Cannot work for this data; see `SECURITY-MODEL.md` |
| Interpreting version numbering | Varies per company; encoding one convention breaks the rest |
| Team, multi-tenant, or SSO features | No second user yet |
