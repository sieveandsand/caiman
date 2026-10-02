# Roadmap

This document owns MVP success criteria, delivery order, and validation context. [GAPS.md](GAPS.md) owns
review tasks; [DECISIONS.md](DECISIONS.md) owns unsettled choices. The original
six-week estimate was a planning assumption, not a current delivery commitment.

## Current status

Local document ingestion and board/project authoring are implemented: TUIs, JSON
drafts, validation, immutable pins, local registration, and guided board editing.
See [README.md](../README.md) for usable commands.

Still planned: Git transport, automatic adoption cascades, workspace status and
verification, brief generation, session materialization, and harness hooks.
The phases below describe completion criteria, not claims that a whole phase
has shipped.

## Success Criteria for the MVP

1. A session starts with the selected board, features, specification release,
   project version, and explicit mode correctly represented.
2. Register-field answers cite the correct document, version, and locator.
3. Requirement answers identify the governing source and any declared deviation.
4. Different project or silicon versions produce appropriately different answers.
5. Tests show that `open` materialization writes no compartmented documents and
   each project's workspace excludes other compartments. This is a workspace
   property, not proof of model authorization or process isolation.
6. Missing labels never make content available.
7. The engineer spends less time opening manuals and correcting context mistakes.

The last criterion measures usefulness. [GAPS.md](GAPS.md) defines the baseline
comparison, governing-source evaluation, and remaining validation work.

## Phase 0 — Answer the expensive question (day 1)

Before using real restricted material, establish which processing and storage
arrangements each counterparty permits. S-33 resolves G23 with one private
repository per compartment; implement and validate the adopted publication
protocol (S-35, [Storage §14](STORAGE.md#14-implementation-sequence-and-migration)) before sharing real material.

Product validation is also outstanding (G01–G07). G26 proposes moving an
end-to-end baseline comparison earlier; its evaluation and continue/stop criteria
still need agreement. Do not treat the implementation checkpoint as product
validation.

## Phase 1 — Documents in, labeled, citable (weeks 1–2)

Local registration is implemented. Remaining work is store initialization,
reviewed publication, pull/clone, and multi-machine validation.

Contracts: [Architecture §6.4](ARCHITECTURE.md#64-ingest) for admission;
[Storage §7](STORAGE.md#7-data-flows) for writes and transport;
[Security §10](SECURITY-MODEL.md#10-test-fixtures-and-security-tests) for negative tests.

Exit criteria:

- Invalid labels or locators cannot publish a document version.
- Cancellation leaves no version or ref update; unknown provenance is accepted.
- Registered bytes are unchanged and resolve to the same digest on a second machine.
- Publication requires label review and a permitted private destination.
- Clone/pull restores permissions before other operations and reports ref conflicts.

## Phase 2 — The project, and the brief (weeks 3–4)

Board/project authoring and manual adoption are implemented. Remaining work:

- Specify and implement reviewed document-adoption cascades (G15).
- Add workspace status and store verification commands.
- Generate the metadata-only brief, including features, precedence, and declared
  changes, with no access to document text or customer legal identity.

Contracts: [Configuration guide](../README.md#configure-boards-and-projects), [Architecture §6.7](ARCHITECTURE.md#67-resolve)
and [§6.9](ARCHITECTURE.md#69-the-brief). Resolve agent-facing formats through G16.

Exit: two projects sharing a board but using different specification sets each
produce the correct pinned structure and brief. Existing pins survive ref updates.
The visibility assumption for brief metadata remains G17.

## Phase 3 — Sessions (weeks 5–6)

Implement explicit-mode materialization, dry runs, omission notices,
reclassification, and the two audit layers. Add thin harness adapters for session
start, observed reads, and session end; keep manual brief injection available.

Contracts: [Architecture §9](ARCHITECTURE.md#9-interfaces),
[Storage §7.3](STORAGE.md#73-materialize), and
[Security §9](SECURITY-MODEL.md#9-audit). Settle content-free shell logging (G22)
and measure hook/subagent coverage (G21) before relying on access records.

Record retrieval misses so the S-18 semantic-search trigger has evidence.

Exit: independent workspaces contain the correct brief and complete permitted
pin set. `open` writes no compartmented documents; missing mode writes nothing.
These tests establish materialization behavior, not process isolation or model
authorization. Then evaluate [MVP success criteria](#success-criteria-for-the-mvp).

## After the MVP

| Item | Trigger or condition |
|---|---|
| Registry backend (D-02) | Git history or deletion requirements become the constraint |
| Git LFS | Blob growth approaches the remote's limits |
| Semantic retrieval (S-18/D-03) | Logged concept-based queries repeatedly defeat ordinary search |
| Structured deviations (D-12) | Real documents no longer work as ID-linked amendments |
| Machine-readable specification companions | A concrete need for ARXML, DBC, ODX/PDX, Fibex, or CDD inputs |
| Native macOS authoring app (S-27) | Reuse shared validation/registration; schedule undecided |
| Harness adoption (D-07) | Verify per-session model selection and transcript handling |
| Cross-document reasoning | Validate the underlying model and retrieval first |
| Multi-user administration and SSO | A real second-user requirement |

## Cut Order Under Time Pressure

The recorded candidates, in order, are linking optimizations (copy instead),
access logging, materialization logging, then the brief's change summary.

Keep ingestion review, session-start integration, fail-closed labels and mode
selection, citations, differential materialization, and the board/project brief.
Splitting, generated maps, and AI ingestion are already outside scope (S-25).

## Schedule Risks

| Risk | Response |
|---|---|
| Basic document/board work consumes the program-context budget | Revisit build-versus-buy (D-04) |
| A platform serves the same use case | Recheck differentiation with evidence (G04) |
| Sample lacks part diversity or multiple versions | Confirm D-08 before evaluating version behavior |
| Requirement IDs vary or deviations omit them | Test real formats early; resolve D-12/G06 |
| Hosting permission is absent | Decide an allowed destination before publication |
| Retrieval misses go unrecorded | Include measurement in session delivery |

Design risks remain in Architecture §15, Storage §13, and Security §7.

## Competitive landscape (historical)

Historical survey: 2026-08-20, updated 2026-09-16. These are the recorded survey
findings, not verified current capabilities. Recheck them before making a
build-versus-buy decision (D-04/G04).

| | BYO docs | Descriptive | Structural | Normative | Domain model |
|---|---|---|---|---|---|
| `ByteAsk-Embedded-MCP` | ✗ hosted, not yours | ✓ | ✗ | ✗ | none |
| `sheetsdata-mcp` | ✗ | ✓ component-level | ✗ | ✗ | none |
| Generic RAG-over-MCP | ✓ | agnostic | agnostic | agnostic | none |
| Onyx / RAGFlow | ✓ | agnostic | agnostic | agnostic | none, but real ACLs |
| `kicad-happy` / `kicad-sch-api` | ✓ design files | ✗ | ✓ design-side | ✗ | schematic only |
| `AutonomousGuy` | ✗ ships standards | ✗ | ✗ | ✓ public standards only | none |
| *Embedder* (not open source) | ✓ | ✓ | ✓ EDA-derived | ✗ | board |
| *Microchip MCP server* (vendor-hosted) | ✗ its own catalogue | ✓ its own parts | ✗ | ✗ | vendor catalogue |
| *Veecle*, *Embroid* (not open source) | ✗ | ✗ | ✓ target model | ✗ | execution target |

“Agnostic” means a system can index these documents without explicitly modelling
boards, frozen releases, features, or program precedence. The survey found the
closest overlap in Embedder's hardware/document context. It did not establish
that no competitor could serve the program use case.

The context-file mechanism itself is established. Caiman's proposed value is
generating it from pinned declarations. Keep the brief short and load detailed
structure on demand; the earlier survey used roughly 150 lines as a working
budget, not a guaranteed harness limit.

Detailed observations remain in [board context research](research/agents_md_research.md)
and [Embedder research](research/embedder_research.md). They are historical
references, not implementation requirements. Silicon-vendor document interfaces
and external hardware execution tools are possible complements, outside Caiman's
own service and orchestration scope.
