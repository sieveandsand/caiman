# Decisions

**Owns:** settled decisions and their reasons, and decisions still open.
Each entry states the decision and why. Design detail lives in the linked doc.
Settled entries are not relitigated without a new reason. Ask before resolving
an open one in code.

The invariants in [CLAUDE.md](../CLAUDE.md) (I-1 to I-10) are not repeated here.

## Settled

### Scope

**S-01. Caiman is a layer, not a platform.** It writes files into a worktree.
Session management, worktrees, agent execution, and hardware-in-the-loop testing
belong to other tools. *Why:* keeps maintenance small and lets engineers keep
their harness.

**S-08. No document conversion.** Files are registered as supplied, including
externally converted Markdown. *Why:* a converter is a project of its own.
Optional converter provenance helps trace bad conversions.

**S-14. Projects are boards plus documents; no compliance tracking.** Project
authoring covers pinned boards, documents, and collections. A project's
collection reference follows current membership and keeps the snapshot digest
from save time for historical reads. Existing `features` data is kept and
editable as raw JSON, with `scope` limited to `required` or `not-used`. *Why:*
structured features cost more to maintain than any current consumer justifies.

**S-15. Relationships are declared, never inferred.** Lineage and feature
relations come from a human with a written explanation. There is no conflict
detection between specifications. A deviation names the requirement IDs it
amends, so `grep` finds both. *Why:* inferred precedence is a compliance risk.

**S-17. Licensed standards are not hosted.** No ISO, AUTOSAR, or MISRA content.
*Why:* redistribution rights.

**S-18. The filesystem is the interface.** No server, index, or MCP tool. Agents
search with `rg` and read bounded ranges. *Why:* register and requirement IDs
suit lexical search; a service adds upkeep without proven need. Revisit only
when logged concept queries repeatedly defeat search (D-03).

**S-19. The human chooses context; Caiman enforces nothing.** Caiman does not
attest models or gate tools. Session folders separate selections, not
permissions. *Why:* a gate without substance invites false confidence.

### Documents and storage

**S-21. Filesystem content-addressed store.** Blobs and manifests by digest,
mutable refs by name, one tree per pod. *Why:* no database is needed at this
scale. [Storage](STORAGE.md).

**S-25. Ingest registers one unchanged file of any format.** No heading,
front-matter, or requirement-ID checks; no splitting, maps, summaries, or AI.
Documents have no `structure` or `requirements` fields. *Why:* a small
pipeline; acceptance does not imply readability or correctness.

**S-26. Provenance is optional.** Original-source and converter fields may be
omitted individually. Missing values stay absent. *Why:* simpler registration.

**S-37. One document concept; collections group documents.** Manuals, notes, and
requirements use the same form: name and description. Collections are named,
unversioned sets of existing documents with a stable ID.

**S-41. Metadata edits create complete manifest revisions.** A document has a
stable ID and a fixed body. Every metadata edit writes a full new manifest
linked to the previous one. References pin ID and body and show current
metadata, including from old boards. Document metadata never restricts
attachment. Changed bytes need a new document. *Why:* one save path, full
history, no rewriting of consumers.

**S-11. Versions are stored whole and never rewritten.** Editing starts from a
snapshot but stores a complete result. Schema literals are a table; old literals
stay readable and are never migrated in place. *Why:* immutable pins.

### Boards and projects

**S-12. Parts are identified by role.** For example `safety-companion`.
Reference designators go in `aliases`. Vendor peripheral names stay unchanged so
they match source documents.

**S-13. Board is hardware; project is the program.** *Why:* one board ships to
several customers; keeping customer identity out of the board keeps it shareable.

**S-31. Board schema.** Assembly documents, separate `vendor` and `part`,
cross-domain `aliases`, and free-text `notes`. Register maps, nets, build flags,
and lifecycle status are excluded.

**S-34. A project pins one or more boards.** Including one board at several
versions; the same version twice is rejected.

**S-36. No precedence among project documents.** *Why:* not needed yet. If it
returns, a human declares it (S-15).

### Pods

**S-38. Pods replace access labels.** One folder per pod, optionally one Git
repository. References stay within the owning pod or `public`. `public` is the
permanent default. The Git host and filesystem own access. *Why:* access was
already enforced by repository permissions; a second layer added only
confusion. [Architecture §6](ARCHITECTURE.md#6-pods-and-sharing).

### Interface

**S-27. Ingestion is a TUI.** Shared validation and registration stay free of
widgets so a future native macOS app can reuse them. No local web frontend.

**S-28. Boards and projects use a TUI and editable JSON drafts.** Both share
validation and registration. Review resolves selectors to pins.

**S-29. Always choose explicitly.** No default board or project is remembered
or preselected.

**S-30. The bare command is a dashboard.** One card per category, Vim-style
navigation with an explicit editing mode, no Ctrl shortcuts or command palette.
Black and green theme that survives 16-color terminals.

**S-32. Guided editor with raw JSON as the escape hatch.** Fields the form does
not show, such as lineage, pass through unchanged. Legacy boards are shown but
edited only as JSON.

### Sessions

**S-07. Selection is per session; no repository lockfile.** *Why:* one checkout
can host several sessions on different project versions.

**S-23. Hooks register and orient; they never provision.** The start hook
registers the session and says what is loaded. It never waits for input and
never reads document bodies.

**S-39. Container agents use host provisioning and request files.** Planned.
[Agents in containers](CONTAINERS.md).

**S-40. Host agents load context with the CLI.** The start hook creates
`.caiman/` on first use. The agent asks the user, then runs `caiman session
list` and `caiman session load`. Loading returns when the context is complete,
so there is no acknowledgement step. *Why:* no listener or adapter is needed
when the agent runs on the host.

**S-41. Idle sessions are pruned at the next start.** Each start in a worktree
deletes the other session folders there that have not started or loaded for 14
days. It skips a session whose lock is held, one whose times are unreadable, and
any folder Caiman did not name. A session resumed after that finds nothing
loaded and asks again. *Why:* every session folder is one more set of
documents a careless search or file listing can reach; no extra hook is needed,
and both harnesses can resume within the window.

**S-42. A user-level skill carries the procedure; the hook carries the
session.** The hook screen installs `caiman/SKILL.md` under `~/.claude/skills`
or `~/.codex/skills` beside the hook, reviewed as a diff. It names no paths:
the start message gives the session folder and this machine's command. *Why:*
agents without it browsed `.caiman/sessions/` and cited another session's
documents; installing in the user's home adds nothing to firmware repositories
(I-3).

## Open

**D-02. Moving the store to an OCI registry.** Git cannot delete history. Move
when that becomes the binding constraint, such as a counterparty requiring
demonstrable deletion.

**D-03. Search index backend.** Not needed (S-18). If logged misses ever justify
one, the leaning is Postgres with full-text and vector search.

**D-04. Build the layer or adopt a platform.** Leaning build, but revisit if
basic document and board handling consumes the effort meant for program
context. Test platforms with real documents (G01, G04).

**D-07. Harness strategy.** Choose harnesses on verified session IDs,
resume/fork/subagent events, hook activation, and transcript handling.

**D-12. How deviations are represented.** Today a deviation is an ordinary
document that names the requirement IDs it amends.

| Option | For | Against |
|---|---|---|
| Ordinary document | No new machinery; cites like anything else | No structured query for amended requirements |
| Structured amendments on requirement IDs | Exact lookup; cheap incremental additions | Second content path; hand entry invites mislabels |
| Document plus a declared amendment index | Real citation and exact lookup | Two things to keep in sync |

Leaning: the third, once the first becomes painful. Wait for a real deviation
document.
