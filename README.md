# Caiman

A context layer for agentic firmware development. It assembles what a coding
agent needs to know about **the hardware**, **the board**, and **the customer's
specification**, writes it into the session's worktree as ordinary files, and
gets out of the way.

## The problem

Coding agents are competent at firmware code and unreliable about firmware
*context*. That shows up as three failures, in ascending order of cost:

| Failure | What happens | Found |
|---|---|---|
| **Wrong fact** | A hallucinated register offset. Compiles cleanly, fails on hardware | In an afternoon |
| **Right fact, wrong board** | Configures a peripheral the board does not route, or reads documentation for a silicon revision never populated. The retrieved text was accurate; the work is still discarded — and because it is confident and well-cited, it survives review | At integration |
| **Correct and non-compliant** | Right by the datasheet, right for the board, in violation of the customer's specification — an unknown mandated feature, a default applied where a deviation amended it, or a newer specification release than the program is frozen at | At the customer's acceptance test, months later |

Retrieval quality fixes only the first. The other two need an explicit model of
what you are building and who you are building it for.

## What Caiman does

1. **Models the board.** Parts in named roles, wired together, at a stated
   version. Versions are immutable and their labels are opaque — `2.1`,
   `Rev B`, `EVT2-B`; Caiman never interprets them — with lineage declared
   rather than inferred.
2. **Models the program.** A *project* composes a board version with a customer
   specification release, the features that program requires, and a declared
   precedence order putting deviations above the base specification. The same
   hardware ships to two customers as two projects, in two compartments.
3. **Ingests** already-converted markdown plus asserted provenance. No PDF
   parsing; that category is well served elsewhere.
4. **Pins.** A project version *is* the pin set — resolving it yields the board,
   every document digest, the specification release, the precedence order, and
   the feature set. No lockfile in your code repo to drift out of sync.
5. **Writes the session's context to disk.** A one-page brief loaded into the
   agent before turn one, the resolved structure as JSON, and the documents with
   a generated map each. No server, no retrieval service, no tool schemas eating
   context every turn. Exact-identifier lookup is a lexical problem and `grep` is
   good at those — register identifiers on one side, requirement IDs on the
   other. Grepping a requirement ID returns the base requirement *and* any
   deviation amending it, together.
6. **Makes the agent choice consequential.** You pick the agent for the task — a
   frontier harness for generic work, a local model for work touching customer
   material. Caiman materializes a different document set depending on which, so
   a wrong choice surfaces as a missing file rather than a silent disclosure.
   Both error directions fail safe.

Every returned fact carries a citation: document, version, and locator.

## What Caiman is not

- **Not a platform.** Not an agent, not a harness, not a test runner. Platforms
  in this category bundle all of it — see `docs/VISION.md` §4. Caiman is one
  layer, deliberately.
- Not a PDF converter. You convert; Caiman ingests markdown.
- Not a requirements or compliance tool. It cites a requirement; it does not
  track whether you have met it.
- Not a conflict detector. Precedence is declared by a human, never computed —
  inferring it means interpreting contracts.
- Not an enforcement boundary. The human picks the agent; Caiman makes that
  choice have physical effect. It does not police it, and does not pretend to.

## Status

Pre-MVP. Target: a working version in roughly six weeks, single-engineer scope.

## Documentation

Each document owns one topic and cross-references the rest rather than restating
it.

| File | Owns |
|---|---|
| [`docs/VISION.md`](docs/VISION.md) | Why this exists, the competitive landscape, product non-goals, MVP success criteria |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | System design: components, models, data flows, interfaces |
| [`docs/STORAGE.md`](docs/STORAGE.md) | On-disk layout: blobs, manifests, refs, and the session workspace |
| [`docs/SECURITY-MODEL.md`](docs/SECURITY-MODEL.md) | Threat model, compartments, agent selection, and the honest limits |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Settled, open, and retired decisions with their alternatives |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phasing, exit criteria, cut order, schedule risk |
| [`docs/harness.md`](docs/harness.md) | Measured harness transcript behavior and what it implies |
| [`CLAUDE.md`](CLAUDE.md) | Hard invariants and working rules for AI agents in this repo |

## Name

A caiman is a small crocodilian — armored, patient, and comfortable in murky
water. Reference manuals are murky water.
