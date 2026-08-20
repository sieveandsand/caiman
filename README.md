# Caiman

A context layer for agentic firmware development. It assembles what a coding
agent needs to know about **the hardware**, **the board**, and **the customer's
specification**, writes it into your session's worktree, and gets out of the way.

## The problem

Coding agents are good at firmware code and bad at firmware *context*. That shows
up as three distinct failures, in ascending order of cost.

**Wrong fact.** A zonal controller with several MCUs, a clock generator, a safety
companion chip, and external NVM depends on thousands of pages of vendor
documentation that is variant-dependent and structurally hostile to naive RAG.
An agent that hallucinates a register offset produces code that compiles cleanly
and fails on hardware. You find out in an afternoon.

**Right fact, wrong board.** The agent configures a peripheral the board does not
route, assumes a bus arrangement from a different board version, or reads
documentation for a silicon revision that was never populated. The retrieved text
was accurate. The work still gets thrown away — and because it is confident and
well-cited, it survives review. You find out at integration.

**Correct and non-compliant.** The agent implements something right by the
datasheet, right for the board, and in violation of the customer's specification
— because it did not know the OEM mandates secure onboard communication at all,
because it applied a default in an area a program deviation amended, or because
it used a newer specification release than the one the program is contractually
frozen at. It works on the bench. It survives review. It propagates into
everything built on top of it. You find out at the customer's acceptance test,
months later.

Retrieval quality fixes only the first.

## What Caiman does

1. **Models the board.** Parts in named roles, wired together, at a stated
   version. Versions are immutable and their labels are opaque — `2.1`, `Rev B`,
   `EVT2-B`; Caiman never interprets them — with lineage declared, not inferred.
2. **Models the program.** A *project* composes a board version with a customer
   specification release, the features that program requires — secure boot,
   secure flashing, SecOC, diagnostics — and a declared precedence order putting
   program deviations above the base specification. The same hardware ships to
   two customers as two projects, in two compartments.
3. **Ingests** already-converted markdown plus asserted provenance. No PDF
   parsing; that category is well served elsewhere.
4. **Pins.** A project version *is* the pin set. Resolving it yields the board,
   every document digest, the specification release, the precedence order, and
   the feature set — with no lockfile in your code repo to drift out of sync.
5. **Writes the session's context to disk.** `caiman sync` produces a one-page
   brief loaded into the agent before turn one, the resolved project structure as
   JSON, and the corpus with a generated map per document. The filesystem is the
   interface — no server, no retrieval service, no tool schemas eating context on
   every turn. Exact-identifier lookup is a lexical problem, and `grep` is very
   good at those: register identifiers on one side, requirement IDs on the other.
   Grepping a requirement ID returns the base requirement *and* any deviation
   amending it, together.
6. **Makes the agent choice consequential.** You pick the agent for the task — a
   frontier harness for generic work, a local model for work touching customer
   material. Caiman materializes a different corpus depending on which, so a
   wrong choice surfaces as a missing file rather than a silent disclosure. Both
   error directions fail safe.

Every returned fact carries a citation: document, version, and locator.

## What Caiman is not

- **Not a platform.** Not an agent, not a harness, not a test runner. There are
  platforms in this category that bundle all of it — see `docs/VISION.md`,
  Adjacent work. Caiman is one layer, deliberately.
- Not a PDF converter. You convert; Caiman ingests markdown.
- Not a requirements or compliance tool. Caiman cites a requirement; it does not
  track whether you have met it.
- Not a conflict detector. Precedence between specifications is declared by a
  human, never computed — inferring it means interpreting contracts.
- Not an enforcement boundary. The human picks the agent; Caiman makes that
  choice have physical effect. It does not police it, and does not pretend to.
- Not a document browser. The consumer is an agent mid-implementation.

## Status

Pre-MVP. Target: a minimum working version in roughly six weeks, single-engineer
scope.

## Documentation

| File | What's in it |
|---|---|
| [`docs/VISION.md`](docs/VISION.md) | The thesis, the three kinds of context, adjacent work, what success looks like |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Layers, the board and project models, features, the brief, materialization |
| [`docs/SECURITY-MODEL.md`](docs/SECURITY-MODEL.md) | Compartments, human routing, what is and isn't enforceable |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Settled, open, and retired decisions, with trade-offs |
| [`docs/ROADMAP.md`](docs/ROADMAP.md) | Phasing, and what gets cut first |
| [`CLAUDE.md`](CLAUDE.md) | Operating instructions and hard invariants for AI agents in this repo |

## Name

A caiman is a small crocodilian — armored, patient, and comfortable in murky
water. Reference manuals are murky water.
