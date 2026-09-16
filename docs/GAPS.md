# Project assessment checklist

Review date: 2026-09-15.

Ingest scope updated 2026-09-15: [S-25](DECISIONS.md#s-25-ingest-registers-one-unchanged-markdown-file)
selects one unchanged Markdown file, usable headings, and human-supplied
whole-document labels. Splitting, maps, stored chunks, and AI processing are
removed. S-26 makes source/converter provenance optional and keeps only the
Markdown input filename. S-27 specifies an ingestion TUI for the MVP and a
future native macOS GUI. These decisions narrow the tasks below; they do not
close untested workflows.

Tracks the 26 gaps identified in the project assessment. Some are already named
in the design docs; others challenge assumptions that need validation. These are
review tasks, not changes to settled decisions or commitments to expand scope.

Check an item when its completion criterion is met. Add a link to the resulting
decision, document, or evaluation beside it. An explicit, justified deferral or
accepted limitation can close an item without implementing a new feature.

Suggested starting order: **G01, G06, G13, G17, G23, G25**.

## Product and validation

- [ ] **G01 — Demonstrate improvement over a simple baseline.** Compare the same
  agent using a maintained brief and document folder with Caiman-generated
  context. Record governing-source accuracy, confidently wrong answers, human
  corrections, and review time on representative firmware tasks.
- [ ] **G02 — Validate the problem with external users.** Interview or run trials
  with three to five engineers outside the originating workflow. Record mistake
  frequency, consequences, existing workarounds, and willingness to maintain the
  model; distinguish stated interest from repeated use.
- [ ] **G03 — Measure maintenance economics.** Measure initial registration and
  ongoing document, board, and feature-update effort against engineering time
  saved. Document where the workflow pays for itself and where it does not.
- [ ] **G04 — Update the competitive analysis and differentiation.** Recheck
  private-document retrieval, firmware platforms, requirements baselines and
  variants, and requirements-to-agent integrations. Cite current sources and
  distinguish verified capabilities from unclear or untested ones in VISION.md.
- [ ] **G05 — Identify the commercial buyer.** State the initial user, buyer,
  purchasing trigger, and evidence needed to establish willingness to pay. If
  commercial adoption is not a goal, record that explicitly.

## Core correctness

- [ ] **G06 — Validate deviation handling.** Evaluate real deviation formats or
  representative synthetic equivalents, including prose without requirement IDs.
  Resolve or explicitly bound D-12; document how an approved amendment is linked
  to its governing requirement and how missing links are surfaced.
- [ ] **G07 — Evaluate governing-source selection.** Test whether agents apply
  precedence and applicability when multiple plausible sources are present.
  Include tasks where the base requirement is easy to find and the amendment is
  easy to miss. Record failures and the limits of the resulting claims.
- [ ] **G08 — Define conversion-fidelity validation.** Establish checks and a
  review procedure for dropped table rows, changed values, missing qualifications,
  and omitted requirements. Document what locator validation cannot establish.
- [ ] **G09 — Test concept-based retrieval.** Evaluate questions whose register
  or requirement identifiers are unknown to the engineer. Record source-document search and selective-reading
  misses and define a measurable trigger for revisiting semantic retrieval.
- [ ] **G10 — Address model drift.** Define how board, feature, and applicability
  declarations are reviewed against approved engineering sources when those
  sources change. State who maintains them and how stale declarations surface.
- [ ] **G11 — Decide code-to-context traceability.** Specify how a code change
  can be associated with the exact project digest used, or document the accepted
  consequences of deferring that association. Keep session selection distinct
  from repository-wide configuration.

## Authoring and integration

- [x] **G12 — Specify provenance input.** [Architecture §6.4.3](ARCHITECTURE.md#643-registration-and-reading-workflow)
  specifies the TUI fields, review, errors, and cancellation;
  [Storage §6.4.1](STORAGE.md#641-document-version) specifies optional provenance
  and omission rules. S-26/S-27 settle the input contract. Implementation and
  workflow validation remain roadmap work; this closes the specification gap.
- [x] **G13 — Specify board and project authoring.** [Authoring guide](AUTHORING.md)
  and S-28 define and implement TUI plus JSON drafts, shared validation, review,
  local registration, export, and deriving a new complete snapshot. S-29 adds
  board/project creation from the home screen and choosing existing configurations
  during ingestion, with no default selection. Remote
  publication and automated document-adoption cascades remain separate work.
- [ ] **G14 — Decide import paths from existing engineering sources.** Identify
  the first useful schematic export and requirements-baseline input, their
  ownership, and how imported data would be reviewed. Either scope an import path
  or explicitly accept and measure manual duplication for the MVP. D-13 surveys
  what industry board descriptions carry and what they omit, and drafts the board
  schema changes that survey implies.
- [ ] **G15 — Specify document adoption and version cascades.** Define the
  behavior of the roadmap's adoption command, including affected board/project
  versions, review of the proposed changes, failure behavior, and preservation of
  existing pins. Reconcile the command surface across the docs.
- [ ] **G16 — Specify agent-facing formats.** Provide schemas or stable examples
  for project.json, omission notices, and access logs. Document maps were removed
  by S-25; they no longer need a format. Include distinctions between absent,
  restricted, and unavailable information.

## Security and isolation

- [ ] **G17 — Reassess always-visible metadata.** Review whether part selections,
  topology, feature names, document identities, and specification versions can
  be confidential. Record the visibility decision and reconcile the brief's
  guarantees with it; metadata-only generation does not itself establish safety.
- [ ] **G18 — Clarify session mode versus model authorization.** Document that
  sealed materialization does not verify the selected model's authorization.
  Describe the human responsibility, wrong-mode outcomes, and any explicitly
  accepted limitation without implying model attestation.
- [ ] **G19 — Bound workspace isolation claims.** State what prevents, or does
  not prevent, an agent from reading the underlying store or another workspace.
  Scope tests and guarantees to the actual filesystem and process boundaries.
- [ ] **G20 — Resolve treatment of harness residue.** Decide how transcripts and
  other persisted session state affect cleanup, revocation, and compartment use.
  Document supported procedures and accepted limits; distinguish measured
  behavior from unverified risks in harness.md.
- [ ] **G21 — Verify audit coverage.** Measure direct reads, shell reads,
  subagent reads, missing hooks, and hook failures in supported harnesses. Record
  coverage gaps and make them visible wherever audit results are presented.
- [ ] **G22 — Reconcile shell logging with content-free logs.** Resolve the
  instruction to log commands verbatim: commands may contain confidential text.
  Specify a log representation consistent with I-10 and examples covering inline
  content, search strings, and shell commands whose document access is unknown.

## Documentation and delivery

- [ ] **G23 — Reconcile repository isolation rules.** Resolve the conflict
  between CLAUDE.md's per-compartment repository invariant and S-22's single
  private repository design. Update all affected references consistently.
- [ ] **G24 — Remove stale agent-policy assumptions.** Review roadmap criteria,
  harness discussion, and other references to the retired agent map. Mark
  historical observations as historical and align current behavior with S-19.
- [ ] **G25 — Narrow unsupported safety claims.** Review claims such as both
  mode mistakes being harmless, documents being unreachable, and sessions
  provably excluding customer information. State the relevant assumptions and
  distinguish materialization guarantees from agent behavior and isolation.
- [ ] **G26 — Move product validation earlier in the roadmap.** Add an early
  end-to-end evaluation of board/program selection and deviations before the
  full storage and synchronization investment. Define what results justify
  continuing, changing direction, or stopping.

## Reference documents

- [Vision and competitive landscape](VISION.md)
- [Architecture, workflow gaps, and interfaces](ARCHITECTURE.md)
- [Storage design](STORAGE.md)
- [Security model](SECURITY-MODEL.md)
- [Settled and open decisions](DECISIONS.md)
- [Roadmap](ROADMAP.md)
- [Harness observations](harness.md)
- [Project invariants](../CLAUDE.md)
