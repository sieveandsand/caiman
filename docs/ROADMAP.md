# Roadmap

This document owns MVP success criteria, delivery order, and validation context. [GAPS.md](GAPS.md) owns
review tasks; [DECISIONS.md](DECISIONS.md) owns unsettled choices. The original
six-week estimate was a planning assumption, not a current delivery commitment.

## Current status

Local document ingestion and board/project authoring are implemented: TUIs, JSON
drafts, validation, immutable pins, local registration, and guided board editing.
See [README.md](../README.md) for usable commands.

Pod folders and Git clone/sync, plus local startup guidance hooks, are implemented.
Still planned: workspace initialization, portable adapters, context catalogs,
per-session materialization and switching, brief generation, and detailed audit
hooks. S-39 settles the session workflow; [CONTAINER-CONTEXT.md](CONTAINER-CONTEXT.md)
is the implementation contract. Phase labels below are planning sequence, not
claims of shipped behavior or current calendar estimates.

## Success Criteria for the MVP

1. Each session receives the selected project, board versions, features, and
   complete pinned document set in its own context folder.
2. Answers cite the correct document, body version, and source locator.
3. Requirement answers identify the governing source and declared deviations.
4. Different project or silicon versions produce appropriately different answers.
5. Two sessions sharing a worktree retain independent selections during switches;
   this is not a claim of filesystem isolation.
6. Missing dependencies, stale requests, and invalid destinations never publish
   partial or substituted context.
7. The engineer spends less time opening manuals and correcting context mistakes.

The last criterion measures usefulness. [GAPS.md](GAPS.md) defines the baseline
comparison, governing-source evaluation, and remaining validation work.

## Phase 0 — Answer the expensive question (day 1)

Before using real restricted material, establish which processing and storage
arrangements each counterparty permits. [PODS.md](PODS.md) owns the current
local-folder and optional Git-sharing model. Verify the actual hosting and
filesystem boundaries before using confidential material in sessions.

Product validation is also outstanding (G01–G07). G26 proposes moving an
end-to-end baseline comparison earlier; its evaluation and continue/stop criteria
still need agreement. Do not treat the implementation checkpoint as product
validation.

## Phase 1 — Documents in pods, citable (weeks 1–2)

Local registration, pod initialization, and Git clone/sync are implemented.
Multi-machine validation and any further publication protocol remain separate
from the planned session workflow.

Contracts: [Architecture §6.4](ARCHITECTURE.md#64-ingest) for admission;
[Storage §7](STORAGE.md#7-data-flows) for writes and transport;
[Security §10](SECURITY-MODEL.md#10-test-fixtures-and-security-tests) for negative tests.

Exit criteria:

- Registration accepts any readable file unchanged; destination pod and metadata are validated.
- Cancellation leaves no version or ref update; unknown provenance is accepted.
- Registered bytes are unchanged and resolve to the same digest on a second machine.
- Sharing is explicit and per pod; saving locally never commits or pushes.
- Clone/pull restores permissions before other operations and reports ref conflicts.

## Phase 2 — The project, and the brief (weeks 3–4)

Board/project authoring and manual adoption are implemented. Remaining work:

- Specify and implement reviewed document-adoption cascades (G15).
- Add workspace status and store verification commands.
- Generate the metadata-only brief, including features and declared
  changes, with no access to document text or customer legal identity.

Contracts: [Configuration guide](../README.md#configure-boards-and-projects), [Architecture §6.7](ARCHITECTURE.md#67-resolve)
and [§6.9](ARCHITECTURE.md#69-the-brief). Resolve agent-facing formats through G16.

Exit: two projects sharing a board but using different specification sets each
produce the correct pinned structure and brief. Existing pins survive ref updates.
The visibility assumption for brief metadata remains G17.

## Phase 3 — Sessions

Implement the accepted [session workflow](CONTAINER-CONTEXT.md), in this order:

1. Host worktree initialization, Git/build guards, catalog publication, and the
   portable workspace adapter with verified harness activation.
2. Stable session registration and independent context folders; preserve resume
   identity and define fork/subagent behavior.
3. Complete host-side materialization, brief generation, request/result handling,
   recoverable installation, and installed/acknowledged revision tracking.
4. TUI and conversational switching through that same provisioner, with retries,
   stale-request rejection, listener unavailability, and explicit cleanup.

Run the canonical acceptance scenarios through supported container bind mounts,
including two sessions in one worktree and recovery after interruption.
[Storage §7.3](STORAGE.md#73-materialize) owns storage mechanics;
[Security](SECURITY-MODEL.md) owns trust boundaries and negative tests.

Detailed access auditing is separate work. Settle content-free shell logging
(G22) and measure hook/subagent coverage (G21) before relying on access records.
Record retrieval misses so S-18's semantic-search trigger has evidence, then
measure the MVP success criteria.

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

Keep ingestion review, session registration, explicit context selection, complete
materialization, recoverable switching, citations, and the board/project brief.
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
