# Security Model

**Purpose:** What the system defends against, what it does not, and where
enforcement actually lives.
**Owns:** The threat model, the classification scheme, the agent-selection
control, and the security test list.
**Related:** `ARCHITECTURE.md` §11 (what the architecture contributes),
`STORAGE.md` §9 (what the layout enforces), `harness.md` (measured residue).

---

## 1. Summary

**The human picks the agent, and Caiman makes that choice consequential.** There
is no software boundary here, by design.

What exists instead is a decision made at the moment the human knows what the
work is, plus a materialization step that makes a wrong choice surface as a
missing file rather than a silent disclosure. Both error directions fail safe.

Being precise about the limits matters more than claiming broad protection. A
control that feels enforced but is not is worse than no control, because it
invites false confidence.

---

## 2. Threat Model

### 2.1 What is being defended

Two kinds of document arrive under something called an NDA, and treating them the
same forces the expensive treatment onto the cheap case.

| | Chip vendor documentation | Customer specifications |
|---|---|---|
| Examples | Reference manuals, datasheets, errata | Requirements for secure boot, SecOC, flashing, diagnostics; program deviations |
| Who holds it | Hundreds of suppliers, click-through agreements, widely mirrored | A handful of suppliers |
| Identifiable as whose? | No | Yes, from the contents |
| Likely already in model training data | Yes | No |
| Cost of a leak | Low | Commercial event with the party whose business you are keeping |
| **Treatment** | **Public** | **Compartmented** |

This is a deliberate prioritization. If a genuinely restricted vendor document
arrives, the compartment mechanism handles it with no new machinery.

### 2.2 The failure being prevented

The realistic failure is accidental, not adversarial: six sessions in flight, one
quietly pulls a customer specification into a frontier-model request, and nobody
notices for a week. Making that require a deliberate act is worth engineering.

### 2.3 Out of scope

| Not defended | Reason |
|---|---|
| A determined local operator | Every control here is defeatable in minutes by someone with admin access to their own machine — which is the machine's owner |
| A human pasting a specification into a chat window | Always a deliberate act; outside the model by design, not by concession |
| Anything after the agent reads a file | Caiman controls what is available, not what is done with it |
| Harness residue | Documented in §7.4. Real, measured, and outside the store's reach |
| A third party holding the store | GitHub holds compartmented repositories. Mitigated per-counterparty, not eliminated (§7.3) |

If the requirement is genuinely "cannot leak", the control is physical: a machine
with no route to any model API. That is what air-gapped chip teams do. Everything
else is contract plus diligence, with software raising the friction.

---

## 3. Classification

There is no sensitivity scale. A document is either **public** or carries one or
more **compartments** naming whose secret it is.

A sensitivity scale cannot express what this data needs. Two customers'
specifications are equally confidential and must be mutually invisible; whatever
numbers you assign, one is greater than or equal to the other and sees it.
Compartments are categories, not levels — membership in one tells you nothing
about another.

| Document | Label |
|---|---|
| NXP S32K3 reference manual | `public` |
| OEM Alpha base spec set 3.2 | `compartment:oem-alpha` |
| Falcon program deviations | `compartment:oem-alpha`, `compartment:falcon` |
| OEM Beta spec set 2.0 | `compartment:oem-beta` |

A project declares its compartments; a session inherits them from its project. A
document is visible when its compartments are a **subset** of the session's. A
Falcon session holds `oem-alpha` and `falcon`, so it sees rows one through three
and never row four — not because row four is more secret, but because it belongs
to someone else.

**Default to per-counterparty.** That is how the agreement is written, and it
lets a base specification be shared across that customer's programs. Add a
program compartment only to documents needing tighter scope, as in row three.
Nothing needs migrating if you start simple and tighten later.

**Missing labels mean unreachable.** Neither public nor compartmented is not a
third state; it is invisible (I-1). Both labels are supplied by a human at registration from
provenance, never inferred from content, and never widened downstream. The label
set applies to the entire unchanged Markdown document (S-25); there are no
section- or chunk-level labels.

---

## 4. Why Content Inspection Cannot Work

Commercial AI gateways classify by inspecting content — PII, PHI, credentials,
regulated identifiers. None of those detectors fires on a register offset. There
is no classifier for "confidential hardware specification", and there will not
be, because confidentiality here is a property of *where the text came from*, not
what it looks like.

Chunking makes it worse: confidentiality is contextual, and a fragment stripped
of its document is unclassifiable on its face.

Hence provenance-carried labels. The label is deterministic and is the actual
control. Content inspection, if ever added, is a second net and never the first.

---

## 5. The Control

### 5.1 Why the decision sits with the human

Every mechanism considered and rejected — a server that refuses, a kernel that
returns `EACCES`, a filter that excludes — acts at the moment of *read*. At read
time nothing knows what the work is for.

At session start the human knows exactly: "I'm adding a diagnostic routine for
Falcon" or "I'm fixing a CAN driver bug." The harness is already interrupting
them to ask which project. Asking which agent costs nothing.

There is also no alternative. **Model identity cannot be verified.** A process
cannot tell which model is behind a caller; there is no attestation and no signed
model identity. A check of the form "only allow self-hosted models" is the caller
asserting its own identity, which is not a control.

### 5.2 Differential materialization makes it consequential

Human routing alone would be a policy in a document. What makes it a control is
that Caiman materializes a different document set depending on the mode the human
declares.

| Mistake | Consequence |
|---|---|
| Chose `open`; work needs specifications | Material is absent. The agent reports it and the engineer restarts sealed. Loud, harmless, self-correcting |
| Chose `sealed`; work was generic | A local model did work it did not need to. Slower; no disclosure |

### 5.3 The human declares the mode; Caiman stores no policy

`sync` takes the decision directly:

```
caiman sync --project falcon --version B-sample --mode sealed --into .caiman/
```

| Mode | Materializes |
|---|---|
| `open` | Public documents only |
| `sealed` | Everything the project version pins |

**`--mode` is required and has no default.** Omitting it is an error, never an
implicit `open`. That is the fail-closed point (I-1); there is nothing else to
fail closed *about*, because there is no lookup.

#### Why there is no agent map

An earlier version of this design had Caiman own
`~/.config/caiman/agents.toml`, mapping agent names to what they could receive:
`claude-code → public`, `codex-local → all`. It was removed.

The map was an indirection between the human's decision and its effect, and it
introduced three problems that the direct form does not have:

1. **It had to be hand-maintained**, and it did not travel with the store, so two
   machines could silently hold different policy.
2. **It invented a vocabulary** — agent names — that nothing else defined and no
   user could discover.
3. **It could be wrong, silently.** A profile keyed on an agent name asserts
   something about the *model*, and one harness can drive either kind. A map
   saying `claude-code → public` is false the moment that harness is pointed at a
   local model, and false in the other direction too.

The third is disqualifying. A control that can be systematically wrong while
appearing authoritative is the "shape of a gate with none of the substance" this
document warns about in §5.1 — the same reason model identity checks were
rejected. Removing it is not a relaxation of §5.1; it is §5.1 applied
consistently.

What replaces it is what §5.1 already argued for: the human knows, at session
start, what model they are about to run and what the work touches. Asking them
directly is strictly more accurate than asking a file that was written months ago
about a name.

#### What this costs

**A guardrail against a momentary lapse.** With a map, `claude-code` always
resolved to `open`, so a distracted engineer could not accidentally hand a
frontier session the full document set. Now they can, by typing `sealed`.

That is a real loss, and it is accepted because the guardrail only worked when
the map was right, and problem 3 says it cannot be relied on to be. A convenience
layer could return later — a per-machine default a human opts into — on one
condition: **it may narrow the mode, never widen it.** A file that can silently
grant more than the human intended reintroduces exactly the failure just removed.

#### The audit annotation

The hook adapter passes `--agent-label claude-code` because it is
harness-specific and therefore knows which harness it is. This is recorded in the
materialization log (§9.1) and is **not** an input to any decision.

It is unverified as to the model — it names the harness, not what the harness is
pointed at — and the log records it that way. A label is documentation; the mode
is the decision.

### 5.4 The agent is told, not merely constrained

A public-only session's brief carries:

```markdown
## Session mode: open
OEM specifications for this program are not available in this session.
If a task requires them, stop and tell the engineer to start a sealed
session — do not infer, approximate, or work around a specification you
cannot read.
```

Twenty tokens, and it makes the agent a participant rather than something to be
contained. It catches the case differential materialization alone would leave as
a confusing absence.

Nothing enforces it. An agent can still guess, and a guess about a customer
requirement is precisely the failure this system exists to prevent. That is a
residual risk of the model, not a defect to be fixed.

### 5.5 The brief is open, and that is safe

The brief describes parts, roles, links, mandated features, and the frozen
specification release. It is public for every project, including those whose
documentation is entirely compartmented.

The reasoning is that existence is structure and detail is content. That a board
contains a secure element, and that a program requires SecOC, are facts about the
design. What the part's register map and the customer's specification *say* are
facts from confidential documents.

This buys one brief instead of two, and an agent that knows the restricted parts
and features exist rather than being unaware of components on its own board —
a different and arguably worse failure than knowing the wrong thing about them.

Two obligations follow:

**The generator cannot read document content** (I-6). It reads manifests only:
names, versions, labels, digests. It cannot quote a register name, a timing
value, or a requirement, because it cannot see them. Structural, not a filter —
a filter can be bypassed by a later feature; a missing capability cannot.

**The customer appears only by codename.** "We are building for OEM X" is
frequently itself under NDA, and the customer *is* structure, so the reasoning
above would wave it straight through. Programs have codenames precisely so people
can discuss them. The legal identity stays in a compartmented project manifest.

A residual case: if the existence of a program is secret to the point that a
codename in a shared repository is too much, this model does not cover it. That
would mean compartmenting the registry's listing, not just its contents. Not in
scope; recorded so it is a decision rather than an oversight.

---

## 6. Enforcement Points, Ranked Honestly

| # | Point | What it is | Strength |
|---|---|---|---|
| 1 | Human agent selection | The real decision, made with full knowledge of the task | Not enforced. It is a choice |
| 2 | Differential materialization | A property of what exists on disk, not a claim any caller makes | Strong against accidents. An agent cannot read a file that was never written |
| 3 | Store permissions | Compartments are separate trees at mode `0700` | Enforced by the kernel. A process without access fails at `open()` |
| 3b | Remote repository access | One private repository for the whole store | Enforced by the host, at store granularity rather than per compartment. Adequate while there is one user; §7.3 states the migration |
| 4 | Label correctness | One generator for write-time and filter-time (I-2); fail closed on absence (I-1) | Strong for correctness. Does nothing about a session bypassing Caiman |

There are exactly three fail-closed points, and they are distinct failure paths
tested separately:

1. `--mode` omitted → `sync` writes nothing
2. Unlabeled content → materialized nowhere, for any agent
3. Content labeled for a compartment the project does not hold → not materialized

---

## 7. Known Gaps

### 7.1 No hybrid session

If a local model reads a specification and returns a requirement, a confidential
*fact* has moved even though no confidential *document* has. The rule is
therefore: a task either touches customer material and runs entirely on the local
model, or it does not and runs normally.

A "sanitized channel" that lets customer facts reach a frontier model in derived
form is the design hardest to reason about and easiest to get quietly wrong.

This rule is carried entirely by human discipline. It is stated here rather than
implied to be enforced.

The brief is not an exception. It carries no confidential facts — only the
structure of the board and program — which is exactly why it goes to any session.

### 7.2 Conversion happens outside Caiman

Caiman registers one already-converted Markdown file unchanged (S-08, S-25).
It makes no AI calls for splitting, labeling, or navigation generation.
**Handing a confidential PDF to a hosted conversion service is a disclosure,
and Caiman cannot prevent it.** By
the time markdown reaches ingest, the document has already been wherever it was
going to go.

This matters more for customer specifications than vendor manuals, per §2.1: a
leaked reference manual is the vendor's widely-held document; a leaked
specification is identifiable as that customer's.

Original-source and converter information are optional (S-26). When converter
information is supplied, it can help identify affected documents and support a
lint for reported or known hosted conversion. Without it, the conversion history
is unknown. Skip that lint when there is insufficient information; absence is
not evidence of local processing or permission to widen access.

The TUI labels this section optional and permits skipping it. Explicit access
labels for the document remain mandatory and independent of provenance. Missing
source or converter fields must never become a missing access label or a default
public label.

The operating rule is human: convert compartmented documents locally. It belongs
in the ingest checklist, not in the list of enforced controls.

### 7.3 The store is hosted by a third party, and its history is permanent

The store is kept in git, in one private repository on GitHub (S-22). Three
things follow.

**A third party holds the material.** Putting a customer's specification on
GitHub means GitHub holds it. This is a question for the agreement, not a
technical detail, and it is the same question Phase 0 asks about model providers
— extended from processing to storage.

The default is one remote for everything, so this is one decision rather than
one per counterparty. A customer whose agreement forbids third-party storage is
handled by a **per-compartment remote override** — self-hosted, or none at all —
without changing anything else (`STORAGE.md` §6.6.2).

**There is no compartment separation on the remote.** One repository means one
access boundary: anyone who can read it reads every compartment. This is
deliberate and is adequate while there is one user — the separation that does the
work is differential materialization (§5.2) and local file modes. It stops being
adequate the moment a collaborator needs one compartment and not others, and the
migration is to split that compartment into its own repository
(`STORAGE.md` §6.6.2). Cheap by construction, because the store's value is its
current tree rather than its history.

One consequence today: a visibility mistake exposes everything rather than one
customer. Push verifies the remote is private before sending anything, and
`caiman init` deliberately does not create the repository, so the visibility
choice stays an explicit human act.

**Push is effectively irreversible.** Git history is permanent, so the deletion
step in §8 is only cheap before a push:

| Where the mistake is | Cost to fix |
|---|---|
| Working tree, uncommitted | Delete the file |
| Committed locally, not pushed | `git reset`; nothing left the machine |
| Pushed | History rewrite, force push, every clone reset, and a request to the host to clear cached views. Forks and CI caches may retain it regardless |

So **ingest never pushes**. Publishing is a separate command with a label-review
step, placed there deliberately: it is the only window in which the cheap fix
exists (`STORAGE.md` §7.6, §9.5).

Treat a push of a compartmented document with the same care as sending that
document to a third party, because that is what it is.

### 7.4 Harness residue

`harness.md` records measured evidence that session harnesses write plaintext
copies of every file an agent reads into an append-only transcript under `$HOME`,
which persists after documents are re-materialized.

Consequences:

- **Materialization is not reversible.** The revocation procedure in §8 removes
  the copy Caiman controls, not the transcript.
- The gap is bounded for `public`-only profiles, because there is nothing
  compartmented to copy. It is **not** bounded for any agent with
  a `sealed` session.

Whether the procedure in §8 should be extended to cover harness paths is an open
policy question. `harness.md` proposes options; none is adopted here.

---

## 8. Reclassification and Revocation

Content-addressed artifacts freeze their labels with their digest, so changing a
label produces a new document identity over unchanged bytes (`STORAGE.md` §6.1).
That is the signal this procedure triggers on.

A **compartment correction** — a document ingested against the wrong customer —
is the likeliest hand-entry error and the one with the worst consequence. Treat
it exactly as a reclassification.

1. Re-ingest with corrected labels into the correct compartment. Blobs are
   byte-identical; the manifest digest is new.
2. Repoint the ref.
3. Update every board and project version that pinned the old digest. Because
   versions are immutable this creates **new** versions; it is not an edit. This
   is a real cost and the honest consequence of immutability.
4. Re-materialize affected workspaces. **Incomplete** — see §7.3, and note it
   also cannot reach a running session's already-read context. Only a new session
   is genuinely clean.
5. Evict the affected digests from every compartment cache.
6. Regenerate briefs. A brief lists what is available; a stale one tells an agent
   that material is on disk when it is not, which is both wrong and confusing to
   debug.
7. Delete the incorrectly-placed objects from the wrong compartment, verifying
   first that no manifest there still references those blobs. **If the store has
   been pushed, deletion is not enough** — the objects remain in that
   repository's history, and removing them requires a history rewrite, a force
   push, and re-cloning everywhere, with forks and host caches potentially
   retaining them anyway (§7.3). A compartment correction after push is an
   incident, not a chore.

Design this while it is a procedure. After three projects have live sessions it
is a migration.

---

## 9. Audit

Audit exists to make human routing reviewable, not to back up imperfect
prevention. It has two layers, and conflating them is the mistake to avoid.

| | Materialization log | Access log |
|---|---|---|
| Question | What could this session read? | What did it read? |
| Written by | `sync`, before the session | Hooks, during the session |
| Complete | Yes | **No** |
| Depends on cooperation | No | Partly |
| Granularity | Document | Document, per read |

### 9.1 Materialization log

Every `sync` records: timestamp, project and project version, declared mode,
compartments materialized, the document digests written, and the `--agent-label`
if one was supplied — marked as an unverified annotation, because it names the
harness rather than the model behind it (§5.3).

This is deterministic and does not depend on the agent cooperating. It is the
authoritative answer to *"which of our specifications did your engineers'
sessions have access to"* — the question a customer actually asks — and
document-level but provably complete beats line-level but conditional.

### 9.2 Access log

Hooks on the harness's tool-use events append one line per read of a managed
document, deriving document identity from the materialized path
(`ARCHITECTURE.md` §6.10.3).

**Three properties are contractual.** The hooks never block a tool call, never
fail a session, and record identities but never content (I-10). An audit record
containing an excerpt of a specification would be a copy of that specification in
a file nobody thinks of as one.

**It is incomplete, and must always be described that way.** Reads through
`Bash` cannot be reliably attributed to files; hooks may not be installed; a
subagent's coverage is unverified; anything outside the harness is invisible.

> **Absence of a record is not proof that a document was not read.**

That sentence belongs wherever the log is surfaced, not only here. The failure
this guards against is someone treating a gap as an all-clear.

### 9.3 What the access log actually buys

The strongest argument for it is not compliance reporting. It is §7.4.

Harness transcripts persist plaintext of every file an agent reads, outside
Caiman's reach, indefinitely. Until now the forensic question — *which
compartmented documents are sitting in which transcript* — had no answer, which
made the residue an unbounded unknown.

The access log answers it. If session `a3f9` recorded reads of three OEM Alpha
documents, those three are what its transcript holds. That converts residue from
"unknown quantity of unknown material" into an enumerable list, which is the
difference between a gap you can act on and one you can only worry about.

It is imperfect in the same ways §9.2 lists. It is still the only instrument
pointed at that gap.

### 9.4 Storage and sensitivity

Logs live outside both the store and the worktree, one file per session:

```
~/.local/state/caiman/audit/
├── sync/<timestamp>-<project>-<version>.json
└── session/<session-id>.jsonl
```

Outside the worktree because a compliance record should survive the worktree
being deleted. One file per session because it removes write contention between
concurrent sessions entirely.

**The logs are metadata and are themselves sensitive.** A line reading
`documents/oem-alpha/flash-spec@3.2/…` reveals a customer relationship even
though it contains no specification text. Treat the audit directory as
compartment-bearing: restrictive permissions, and never committed to any
repository — including a store repository, where git's permanence (§7.3) would
make an accidental inclusion irreversible.

## 10. Test Fixtures and Security Tests

**Synthetic fixtures only.** Never commit real vendor or customer documents, not
even for testing (I-3).

The sample project (`DECISIONS.md` D-08) uses open hardware with freely available
specifications. The normative half has no open-source analogue and real
specifications can never be committed, so it uses **synthetic specification
sets** — invented requirement IDs, a few features, a deviation amending a handful
of requirements. Two of them, for two fictional customers, so compartment
isolation is exercised with zero exposure. Synthetic beats borrowed here: the
tests can assert exact behavior against content you control.

Write these before the mechanism they test.

| ID | Test | Asserts |
|---|---|---|
| S-T1 | A record neither marked public nor carrying a compartment | Returned to nobody, materialized nowhere |
| S-T2 | A record whose compartment label was lost, other fields intact | Same — tested separately from S-T1, because the two fail through different paths |
| S-T3 | Materialize for a project in compartment B | Nothing from compartment A appears |
| S-T4 | Materialize with `--mode open` | No compartmented document, for any project |
| S-T5 | Materialize with `--mode` omitted | Fails; nothing written. No implicit default |
| S-T6 | A document carrying two compartments, session holds one | Not materialized |
| S-T7 | Write-time and filter-time label generation, property-tested | Identical output across generated inputs |
| S-T8 | Generate a brief for a project with compartmented documents | No document body text appears |
| S-T9 | Generate a brief; search for the customer string from the project manifest | Absent |
| S-T10 | Reclassify or compartment-correct a document | Gone from re-materialized documents and every cache; brief regenerated |
| S-T11 | Register a document without usable headings; register a requirement-structured document with headings but no matching requirement IDs | Both rejected; no repair or line-only citation fallback |
| S-T12 | Resolve a bare project or board name | Returns the version list; resolves nothing |
| S-T13 | `push` a compartment whose remote is public | Hard error; nothing sent |
| S-T14 | `push` with unreviewed labels | Reports what would be published, by document and compartment, before sending |
| S-T15 | `pull` a ref that diverged on two machines | Fails with both digests named; does not pick one |
| S-T16 | Make every hook command fail during a session | The session completes normally; no tool call is blocked |
| S-T17 | Grep an access log for content from the documents it references | No document body text present |
| S-T18 | Read a managed document through `Read`, then through `Bash cat` | The first is attributed; the second is recorded as `unresolved` rather than dropped or guessed |
| S-T19 | Attempt to commit the audit directory to a store repository | Refused by the same guard as I-3 |
| S-T20 | Open the authoring catalog with no scopes, then with one of a project's two required compartments | Private project is absent in both cases; discovery does not widen the declared scope |
| S-T21 | Select an existing board or project during document ingestion | Metadata reuse does not assert public access; registration still requires explicit document labels |

Architecture-level tests are in `ARCHITECTURE.md` §13; storage-level tests are in
`STORAGE.md` §11. These three lists do not overlap.

---

## 11. Optional Hardening

Not part of the design. Available if the accident rate warrants it; recorded so
the options are not rediscovered.

| Option | Mechanism | Assessment |
|---|---|---|
| **Separate OS user** | Compartmented documents materialized to a path owned by a second uid, mode `0700`. A normal session gets `EACCES` from the kernel; a sealed session runs as that uid and its ordinary file reads work | Strong, and genuinely painful on macOS: separate home directory, credentials, and shell config, plus `sudo -u` per session. Give the sealed session its own worktree rather than sharing one across uids |
| **Encrypted disk image (macOS)** | `hdiutil create -encryption AES-256 -type SPARSEBUNDLE`, mounted only for sealed work, key in Keychain | Detached, the documents are ciphertext rather than merely unreadable. Sidesteps the multi-user pain; "did I unmount" is easier discipline than "am I the right user". The better option on this platform |
| **Egress control** | Point the harness at a self-hosted gateway; block direct egress to model APIs at the firewall | An existing product category. Relevant only if human routing proves insufficient in practice |

Note that none of these reaches harness residue (§7.3), which lives under `$HOME`
rather than in the document tree.
