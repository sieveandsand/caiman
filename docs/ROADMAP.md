# Roadmap

**Owns:** what works today, what comes next, MVP success criteria, and open
questions (G-items). Open design choices are in [Decisions](DECISIONS.md#open).

## Status

| Area | State |
|---|---|
| Document ingestion, metadata editing, history, collections | Done |
| Board and project authoring (TUI, JSON drafts, guided editors) | Done |
| Pods, per-pod Git clone, connect, sync, removal | Done |
| Start hook for Claude Code and Codex; `caiman session list / load / status` | Done |
| Metadata-only brief and complete per-session install | Done |
| Little caiman (transcript-based usage view) | Done |
| Agents in containers ([design](CONTAINERS.md)) | Planned |
| Workspace status and store verification commands | Planned |
| Reviewed document-adoption cascades (G15) | Planned |

## MVP success criteria

1. Each session receives the selected project, its board versions, and the
   complete pinned document set in its own folder.
2. Answers cite the correct document, body version, and locator.
3. Requirement answers identify the governing source and declared deviations.
4. Different project or silicon versions produce correspondingly different answers.
5. Two sessions in one worktree keep independent selections.
6. Missing dependencies never produce partial or substituted context.
7. The engineer spends less time opening manuals and correcting context mistakes.

Criterion 7 measures usefulness and needs G01.

## Next

1. **Product validation (G01, G02, G26).** Run an end-to-end comparison against
   a hand-maintained brief and document folder before larger investments.
   Agree on what result means continue, change, or stop.
2. **Adoption cascades (G15).** Today a changed board or document is adopted by
   editing each consumer. Specify the reviewed command: affected versions,
   review, failure behavior, pin preservation.
3. **Status and verification.** `caiman` commands to show a workspace's sessions
   and to verify every object in the store.
4. **Pull summary.** After Sync, report the objects added and refs changed.
5. **Containers.** Implement [Agents in containers](CONTAINERS.md) after G27.

## Open questions

### Product

- **G01. Beat a simple baseline.** Same agent, maintained brief versus Caiman
  context. Measure source accuracy, confidently wrong answers, corrections, and
  review time.
- **G02. External users.** Trials with three to five engineers outside the
  originating workflow: mistake frequency, workarounds, willingness to maintain
  the model.
- **G03. Maintenance cost.** Registration and update effort against time saved.
- **G04. Competition.** Recheck private-document retrieval, firmware platforms,
  and requirements tools with current sources.
- **G05. Buyer.** Initial user, buyer, and purchase trigger, or state that
  commercial adoption is not a goal.
- **G26. Validate earlier.** Move G01 ahead of further storage work.

### Correctness

- **G06. Deviations.** Test real deviation formats, including prose with no
  requirement IDs. Bounds D-12.
- **G07. Governing source.** Do agents pick the right source when several are
  plausible, especially when the amendment is easy to miss?
- **G08. Conversion fidelity.** A review procedure for dropped rows, changed
  values, and omitted requirements.
- **G09. Concept retrieval.** Questions where the identifier is unknown. Log
  misses; this is the trigger for revisiting S-18.
- **G10. Model drift.** Who reviews board and project declarations when sources
  change, and how stale ones surface.
- **G11. Code-to-context traceability.** Whether to tie a code change to the
  project digest used.

### Authoring and integration

- **G14. Import paths.** First useful schematic export and requirements-baseline
  import, or accept manual entry for the MVP.
- **G15. Adoption cascades.** See Next.
- **G16. Agent-facing formats.** Stable schemas for `project.json` and
  `_index.md`, including absent versus unavailable information.
- **G27. Container adapter.** Runtime, protocol versions, unsupported-version
  behavior, harness trust and activation.
- **G28. Stale pins per session.** How to show a session whose installed version
  label has since moved.
- **G29. Multi-repository roots.** Zephyr `west`, `repo`, and `kas` roots are not
  Git repositories. Choose where `.caiman/` goes and what guards apply.

### Security

- **G17. Metadata visibility.** Part selections, topology, and document names
  can be confidential. Decide what the brief and `project.json` may show.
- **G20. Harness residue.** How transcripts and harness memory affect cleanup
  and pod use.
- **G21. Observation coverage.** Measure what little caiman sees for direct,
  shell, and subagent reads in each harness.
- **G25. Safety claims.** Keep every claim about isolation or exclusion tied to
  a stated mechanism and its limit.

## After the MVP

| Item | Trigger |
|---|---|
| OCI registry backend (D-02) | Git's permanent history becomes the binding constraint |
| Git LFS | Blob size approaches remote limits |
| Semantic retrieval (D-03) | Logged concept queries repeatedly defeat search |
| Structured deviations (D-12) | Real deviations stop working as ID-linked documents |
| Machine-readable spec inputs (ARXML, DBC, ODX) | A concrete need |
| Native macOS app (S-27) | Reuses shared validation and registration |
| Multi-user administration, SSO | A real second-user requirement |
