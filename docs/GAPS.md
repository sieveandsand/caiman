# Project assessment checklist

Review date: 2026-09-15.

This is the review backlog: each item needs evidence, a recorded decision, or an
explicitly accepted limitation. [ROADMAP.md](ROADMAP.md) owns delivery order;
[DECISIONS.md](DECISIONS.md) owns policy choices. Checked items close only the
stated criterion, not every related implementation task.

Check an item when its completion criterion is met. Add a link to the resulting
decision, document, or evaluation beside it. An explicit, justified deferral or
accepted limitation can close an item without implementing a new feature.

Suggested starting order: **G01, G06, G17, G25**. G13 is complete.

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
  distinguish verified capabilities from unclear or untested ones in ROADMAP.md’s historical survey.
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
  and omission rules. S-26/S-27 settle the input contract. Local ingestion is implemented; this item closes the specification gap,
  not end-to-end session validation.
- [x] **G13 — Specify board and project authoring.** [Configuration guide](../README.md#configure-boards-and-projects)
  and S-28 define and implement TUI plus JSON drafts, shared validation, review,
  local registration, export, and deriving a new complete snapshot. S-29 adds
  board/project creation from the home screen and choosing existing configurations
  during ingestion, with no default selection. Remote
  publication and automated document-adoption cascades remain separate work.
- [ ] **G14 — Decide import paths from existing engineering sources.** Identify
  the first useful schematic export and requirements-baseline input, their
  ownership, and how imported data would be reviewed. Either scope an import path
  or explicitly accept and measure manual duplication for the MVP. D-13 surveyed
  what industry board descriptions carry and what they omit; S-31 settled the
  board schema changes that survey implied. What remains open here is the import
  path itself, not the shape of the target.
- [ ] **G15 — Specify document adoption and version cascades.** Define the
  behavior of the roadmap's adoption command, including affected board/project
  versions, review of the proposed changes, failure behavior, and preservation of
  existing pins. Reconcile the command surface across the docs.
- [ ] **G16 — Specify agent-facing formats.** Provide schemas or stable examples
  for project.json, document inventories, and access logs. Document maps were removed
  by S-25; they no longer need a format. Include distinctions between absent,
  restricted, and unavailable information. Define metadata visibility for resolved
  JSON and document inventories, the document-path identity format, and startup
  inventory/staleness inputs before implementing their producers.
- [ ] **G27 — Specify workspace adapter compatibility.** S-39 uses a portable
  adapter, not a second Caiman installation in the container. Define its runtime,
  protocol versions, unsupported-version behavior, and harness trust/activation.
  See [Session context §9](CONTAINER-CONTEXT.md#9-implementation-scope-and-remaining-decisions).
- [ ] **G28 — Surface stale pins per session.** Define how the host TUI presents
  installed selections whose version labels moved, and how published choices are
  refreshed. Catalog refresh must not change installed revisions; stale requests
  fail rather than substituting another digest (S-39).
- [ ] **G29 — Decide provisioning for multi-repository workspaces.** Zephyr
  `west`, Yocto `repo`/`kas`, and Android `repo` roots are not git repositories,
  and agents often run in a member repository. Choose between provisioning into
  the manifest or application repository and searching parent folders, and state
  the guard implications (I-3). See [Architecture §15.1](ARCHITECTURE.md#151-open-questions).

## Security and isolation

- [ ] **G17 — Reassess always-visible metadata.** Review whether part selections,
  topology, feature names, document identities, and specification versions can
  be confidential. Record the visibility decision and reconcile the brief's
  guarantees with it; metadata-only generation does not itself establish safety.
- [x] **G18 — Clarify saved selection and model authorization.** S-39 and
  [Session context](CONTAINER-CONTEXT.md#session-identity) settle independent
  session selection, same-session resume, new/forked folders, and explicit
  switching. Caiman does not attest models. Open/sealed modes are retired under
  pods. Harness-specific identity verification remains implementation work.
- [x] **G19 — Bound workspace isolation claims.**
  [Session context §8](CONTAINER-CONTEXT.md#8-boundaries-and-lifecycle) and
  [Security](SECURITY-MODEL.md) state that session folders do not isolate
  permissions, shared-worktree agents may read other sessions' documents, and
  actual isolation requires filesystem/process boundaries. Container verification
  remains required; this closes the design claim, not validation.
- [ ] **G20 — Resolve treatment of harness residue.** Decide how transcripts and
  other persisted session state affect cleanup, revocation, and pod content use.
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

- [x] **G23 — Reconcile repository isolation rules.** S-33 settles one private
  repository per compartment and one compartment per private document, with no
  separate domain abstraction. Updated the design references; Git transport
  was proposed at resolution on 2026-09-24. The current pod model supersedes
  those compartment rules and implements optional per-pod Git clone/sync.
- [x] **G24 — Remove stale agent-policy assumptions.** Session workflow, roadmap,
  harness notes, and security contracts now use pods and S-39. The old agent map
  and open/sealed modes are retired; historical measurements are not policy.
- [ ] **G25 — Narrow unsupported safety claims.** Review claims such as both
  mode mistakes being harmless, documents being unreachable, and sessions
  provably excluding customer information. State the relevant assumptions and
  distinguish materialization guarantees from agent behavior and isolation.
- [ ] **G26 — Move product validation earlier in the roadmap.** Add an early
  end-to-end evaluation of board/program selection and deviations before the
  full storage and synchronization investment. Define what results justify
  continuing, changing direction, or stopping.

## Reference documents

- [Product rationale and scope](ARCHITECTURE.md#2-background-and-problem)
- [Historical competitive landscape](ROADMAP.md#competitive-landscape-historical)
- [Architecture, workflow gaps, and interfaces](ARCHITECTURE.md)
- [Storage design](STORAGE.md)
- [Security model](SECURITY-MODEL.md)
- [Settled and open decisions](DECISIONS.md)
- [Roadmap](ROADMAP.md)
- [Harness observations](harness.md)
- [Project invariants](../CLAUDE.md)
