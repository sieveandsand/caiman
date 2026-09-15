# Vision

**Purpose:** Why this project exists, who it is for, what "done" means, and how
it relates to what else is being built.
**Owns:** The problem statement, the competitive landscape, product-level
non-goals, and the MVP success criteria. Other documents reference this one
rather than restating it.

---

## 1. Summary

Coding agents are competent at firmware code and unreliable about firmware
*context*. Caiman supplies that context — what the hardware does, what this
board is, and what this customer's program requires — as ordinary files in the
session's worktree.

It is a **layer, not a platform**. The agent, the harness, and the test rig stay
whatever you already use.

---

## 2. The Problem

Three kinds of context are missing, and each produces a different failure with a
different cost.

| Context | What it answers | Failure when absent | Detected |
|---|---|---|---|
| **Descriptive** | What the hardware does. Datasheets, reference manuals, errata | **Wrong fact** — a register offset that is not what the manual says. Compiles cleanly, fails on hardware | Hours, on the bench |
| **Structural** | What this design is. Parts in roles, links, silicon revisions, board version | **Right fact, wrong board** — correct for the part, wrong for the design. The retrieved text was accurate; the work is discarded rather than repaired | Days to weeks, at integration |
| **Normative** | What this program must do. Customer specifications, mandated features, deviations, the frozen release | **Correct and non-compliant** — right by the datasheet, right for the board, in breach of the specification | Months, at customer acceptance |

*Normative* is the standards term of art: ISO, IEEE, and AUTOSAR mark binding
requirement clauses **normative** and explanatory material **informative**. A
datasheet states a fact about the world; a specification states an obligation
imposed by a contract.

The discriminator across the three is what "wrong" means. Violate a datasheet and
the silicon fails you — physics imposes the obligation. Violate a specification
and everything works, and you are in breach — your customer imposes it. You can
negotiate a deviation with an OEM; you cannot negotiate one with a setup-and-hold
time.

Two things follow, and they shape everything downstream:

**Cost rises with the length of the feedback loop, and so does plausibility.**
The third failure produces confident, well-cited, reasonable-looking work that
survives review and propagates into everything built on top of it.

**Only the first is a retrieval problem.** The second and third need an explicit
model of the board and the program. No amount of retrieval quality substitutes,
because the retrieved text was correct.

---

## 3. Thesis

**Context is the product, and the normative layer is the part nobody supplies.**

The framing comes from Spotify's Xirp, which pairs agent orchestration with
Portal, a service catalog that grounds each session in institutional context. The
useful half transfers — context is the product, the agent is interchangeable. The
orchestration half does not: worktree isolation solves contention over a working
tree, and firmware's contended resources are one dev board, one debug probe, one
CAN interface. Fifty agents can compile in parallel and cannot flash in parallel.

The descriptive and structural layers are necessary substrate and are
increasingly well served by others (§4). Build them competently, not inventively.

What remains unserved is everything downstream of the customer: the specification
set, the features it mandates, the release the program is frozen at, the
deviations that amend it, and the requirement that one customer's material be
unreachable from another customer's session. That last point has an external
driver — TISAX brings AI data access into assessment scope for suppliers handling
OEM data, with access-management and logging requirements — so compartmentation
is increasingly something a supplier has to demonstrate rather than merely
practice.

---

## 4. Landscape

Surveyed 2026-08-20. **Re-run this before relying on it.** An earlier draft
asserted that nobody was building the hardware documentation layer; that became
false within months and stayed in the document until someone checked.

### 4.1 The question asked

Is there a single open-source project that takes **your own documents** and
models all three kinds of context? No.

| | BYO docs | Descriptive | Structural | Normative | Domain model |
|---|---|---|---|---|---|
| `ByteAsk-Embedded-MCP` | ✗ hosted, not yours | ✓ | ✗ | ✗ | none |
| `sheetsdata-mcp` | ✗ | ✓ component-level | ✗ | ✗ | none |
| Generic RAG-over-MCP | ✓ | agnostic | agnostic | agnostic | none |
| Onyx / RAGFlow | ✓ | agnostic | agnostic | agnostic | none, but real ACLs |
| `kicad-happy` / `kicad-sch-api` | ✓ design files | ✗ | ✓ design-side | ✗ | schematic only |
| `AutonomousGuy` | ✗ ships standards | ✗ | ✗ | ✓ public standards only | none |
| *Embedder* (not open source) | ✓ | ✓ | ✓ EDA-derived | ✗ | board |

"Agnostic" is the important cell. A general-purpose retrieval system ingests a
datasheet, a schematic export, and a customer specification equally well — bytes
in, chunks out. It covers all three layers only in the sense that it does not
distinguish them, and it has no notion of a board, a silicon revision, a program
frozen at a release, a feature, or a compartment.

So "covers all three" has two meanings and only one is unserved:

- **Indexes documents of all three kinds.** Many options. Do not build another.
- **Models all three domains.** Nothing.

### 4.2 Notable entries

**Embedder** (YC-backed, in production 2026) is the closest overall: a
datasheet-aware agent over vendor documentation, a knowledge graph built from
datasheets and internal documents, a schematic graph parsed from native EDA files
into components, nets, pin assignments and power topology, hardware-in-the-loop
test execution, multi-agent orchestration, and on-premises and air-gapped
deployment. Several things an earlier draft claimed nobody was building, it
builds — including a structural model derived automatically from EDA source,
which is a better mechanism than a hand-maintained registry.

**`ByteAsk-Embedded-MCP`** (MIT) is the closest open-source analogue to the
document half: a source-grounded, page-cited retrieval server for coding agents
writing firmware. What is open is the server shell; the corpus and retrieval
engine sit behind a pluggable `SearchBackend` seam serving a hosted endpoint over
their own licensed material. That seam is why it is a candidate if Caiman ever
needs the deferred semantic tool (`DECISIONS.md` S-18).

**`AutonomousGuy`** ships open-source agent skills for AUTOSAR, MISRA C, and
ISO 26262 — the same *pattern* as Caiman's brief, applied to standards: public,
static, identical for every supplier. The rest of the normative neighbourhood is
compliance *checking* (CodeQL's AUTOSAR C++ queries, NaiveSystems Analyze,
Artop), which is static analysis after the fact rather than the governing
requirement at implementation time.

Not related despite the name collision: GitHub's `spec-kit` is *spec-driven
development* — you author a specification for the feature you are building. That
is the opposite direction from conforming to a customer's binding specification.

### 4.3 What the landscape settles

**The documents are a solved problem; the model is not, and that is the whole
project.** This is the sentence to return to when scope feels uncertain.

**The brief mechanism is commodity, and that is fine.** `AGENTS.md` is an open
format used by tens of thousands of projects, with generators that scan a repo
and emit one. The value is entirely in *what goes in the file*.

**The descriptive layer is substrate, not moat.** If an MIT-licensed server doing
page-cited firmware retrieval adds bring-your-own-documents, it covers most of
that half. Build it cheaply rather than lovingly.

Note that S-18 already dissolved most of the build-versus-buy question by
accident. With the filesystem as the interface, the descriptive layer reduces to
*validate headings, register unchanged Markdown with human-supplied labels,
materialize the pinned file* (S-25). There is no retrieval service, chapter
splitter, or map generator to build or buy. The agent searches and selectively
reads the source document. The build-versus-buy question survives for deferred
retrieval improvements.

---

## 5. Positioning: Layer, Not Platform

Platforms in this category bundle the agent, the orchestration, the test
execution, and the knowledge layer, and are adopted together. Caiman is one layer
— context assembly — that writes files into a worktree and gets out of the way.

| | Platform | Caiman |
|---|---|---|
| Adoption | Procurement cycle | `caiman sync` writes a directory |
| Agent | Theirs | Whichever you already use |
| Orchestration | Theirs | Whichever harness you already run |
| Test execution | Included | Somebody else's, permanently |
| Scope | Team-sized | Small enough for one engineer to keep correct |

This is a distribution and scope argument, not a claim of technical superiority.
Whether layer or platform is the better bet is genuinely unsettled. If the
platform bet is right, the ideas here are portable and little is lost.

---

## 6. Who This Is For

A firmware engineer working on a multi-chip embedded project — a zonal
controller with several MCUs, a clock generator, a safety companion chip, and
external NVM — built to a customer's specification, with vendor and customer
documentation under separate agreements, who already uses coding agents daily and
is losing time to the agent being confidently wrong about the hardware, the
board, or the program.

Design for that person. Multi-user, team, and SSO features are deferred until a
second user exists.

---

## 7. Success Criteria for the MVP

`ROADMAP.md` phases the work toward these; it does not restate them.

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

**Criterion 7 is the real one.** The others are how you get there.

---

## 8. Non-Goals

Product-level. `ARCHITECTURE.md` §4 lists the architectural non-goals that follow
from these; `DECISIONS.md` carries the reasoning for each.

| Not doing | Why | Decision |
|---|---|---|
| Agent orchestration, session or worktree management | Commodity, and where the platforms compete | S-01 |
| Hardware-in-the-loop test execution or scheduling | A real problem; not the context layer | S-01 |
| PDF to markdown conversion | Supplied externally; Caiman accepts prepared Markdown | S-08 |
| Splitting, generated maps, summaries, or AI processing at ingest | Register one unchanged file with usable headings and document-level labels; evaluate navigation on real tasks | S-25 |
| Requirements or compliance management | Caiman cites a requirement; it does not track whether you met it | S-14 |
| Conflict detection between specifications | Precedence is declared, not computed. Inferring it means interpreting contracts | S-15 |
| Hosting licensed standards (ISO, AUTOSAR, MISRA) | Licensing, and customer specifications are largely self-contained | S-17 |
| Acting as an enforcement boundary | The human picks the agent; Caiman makes the choice consequential | S-19 |
| A human-facing documentation browser | The consumer is an agent. Authoring uses an ingestion TUI in the MVP; a native macOS app is the future curation GUI | S-27 |
| Bundling or redistributing vendor or customer documentation | Licensing, and it breaks the core design commitment | — |
| Content-inspection-based confidentiality detection | Cannot work on this data (`SECURITY-MODEL.md` §4) | S-03 |
| Interpreting version numbering | Varies per company; encoding one convention breaks the rest | S-10 |
| A sync or merge system | Git already does this. The store is a git repository; Caiman wraps it, it does not reimplement it | S-22 |
| Multi-user, team, or SSO features | No second user yet | — |

---

## 9. Principles

Four commitments that are not engineering decisions and therefore do not live in
`DECISIONS.md`.

**The user supplies the documents.** Caiman ships nothing. Vendor and customer
documentation is under agreement and cannot be redistributed. This is a
constraint and also the moat: a tool that works with documents you already have
is adoptable without a procurement conversation.

**Existence is structure; detail is content.** That a board has a secure element
and that a program requires SecOC are facts about the design. What the manual and
the specification *say* is content. This is what lets the brief be an ordinary
unclassified file.

**Declared, never inferred.** Version lineage, specification precedence, and
relationships between features come from a human with a free-text explanation.
Rendering a person's declaration is defensible in a design review; a computed
inference is not.

**An uncitable fact is worthless.** A value the engineer cannot verify against
the original document is unusable in a design review, an audit, a safety case, or
a customer acceptance test. Citations are the acceptance criterion, not a
feature.
