# Security Model

**Current pod model:** [PODS.md](PODS.md) supersedes the access-label,
compartment, catalog-authorization, and separate-repository-mirror rules below.
Pods are local folders with optional Git sharing; the Git host owns remote
permissions. Older sections are retained as design history.

**Purpose:** What the system defends against, what it does not, and where
enforcement actually lives.
**Owns:** The threat model, the classification scheme, the agent-selection
control, and the security test list.
**Related:** `ARCHITECTURE.md` §11 (what the architecture contributes),
`STORAGE.md` §9 (what the layout enforces), `harness.md` (measured residue).

---

## 1. Summary

Caiman filters the documents written into a workspace according to explicit
labels, project compartments, and a human-selected mode. It does not verify the
model's authorization or isolate its process. A mistaken `sealed` choice can
expose restricted documents.

This is the target design; session materialization and audit hooks are not yet
implemented. G17–G25 track unresolved assumptions and conflicting requirements.

## 2. Threat Model

### 2.1 What is being defended

The initial policy treats ordinary vendor manuals as public to sessions and
customer specifications as compartmented (S-16). Restricted vendor documents
can also be compartmented. “Public” here does not grant redistribution rights.
Labels must be explicitly supplied; neither document contents nor missing
provenance establishes permission.

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

Every document is either explicitly **public** or belongs to **exactly one
compartment**. A compartment names the group permitted to access it, such as a
customer or project. Compartments are the storage and remote access boundaries;
there is no separate domain abstraction (S-33).

| Document | Label |
|---|---|
| NXP S32K3 reference manual | `public` |
| OEM Alpha base spec set 3.2 | `compartment:oem-alpha` |
| Falcon program deviations | `compartment:falcon` |
| OEM Beta spec set 2.0 | `compartment:oem-beta` |

A project/session may refer to several compartments because its documents can
belong to different groups. A private document is eligible only when its one
compartment is in the declared scope; public documents remain eligible in open
mode. A Falcon session with `oem-alpha` and `falcon` can include the first three
rows. Each teammate also needs host permission to fetch the corresponding private
repositories. Config access does not grant access to its document dependencies.

The stored `labels.compartments` array is retained: public documents have `[]`,
private documents have exactly one name. Multiple entries, including duplicates,
are rejected at ingestion, registration and read time. Do not silently select a
label or reinterpret an old multi-compartment object. Explicitly re-ingest it
with one reviewed classification and update dependent pins; old bytes are not
rewritten. Missing labels still fail closed.

Choose a customer compartment for shared customer material or a project
compartment for project-specific material. Access to several groups belongs on
the user/project/session, not as multiple labels on one document. The proposed
Git backend uses one private repository per compartment, with a separate private
repository for explicitly public material.

Labels apply to the entire unchanged document and are supplied by a
human from provenance, never inferred from its contents or filename. The generic
scope representation and current multi-compartment project validation remain
unchanged by the document-cardinality rule.

---

## 4. Why Content Inspection Cannot Work

Document text does not establish who may receive it. The same technical fact can
appear in a public manual or a restricted customer specification. Humans assign
labels from provenance and the applicable agreement; content inspection cannot
replace that declaration (S-03).

## 5. The Control

### 5.1 Why the decision sits with the human

The engineer selects the model and decides which material it may receive.
Caiman has no model-attestation mechanism. [S-19](DECISIONS.md#s-19-the-human-declares-the-session-mode-caiman-holds-no-agent-policy)
records why the former agent-name policy was removed.

### 5.2 Differential materialization makes it consequential

An `open` workspace omits compartmented documents. A `sealed` workspace includes
eligible project pins. Missing documents can prompt a correction, but the agent
may still guess. Selecting `sealed` does not imply a local or authorized model;
that remains the engineer's responsibility.

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

See S-19 for the retired map and its trade-offs. Any future convenience layer
may narrow the selected mode, never widen it.

#### What this costs

There is no automatic guard against selecting `sealed` for an unauthorized
model. Caiman must not describe either mode as model attestation.

#### The audit annotation

`--agent-label` records an unverified harness name in the materialization log.
It is never an input to access decisions.

### 5.4 The agent is told, not merely constrained

A public-only session's brief carries:

```markdown
## Session mode: open
OEM specifications for this program are not available in this session.
If a task requires them, stop and tell the engineer to start a sealed
session — do not infer, approximate, or work around a specification you
cannot read.
```

This explains an omission that would otherwise look like missing project data.

Nothing enforces it. An agent can still guess, and a guess about a customer
requirement is precisely the failure this system exists to prevent. That is a
residual risk of the model, not a defect to be fixed.

<a id="55-the-brief-is-open-and-that-is-safe"></a>

### 5.5 Brief visibility and its assumptions

S-09/I-6 require an always-visible brief generated from manifests, with no access
to document bodies and no customer legal identity. The program uses a codename.

Part selections, topology,
feature names, document identities, and release names may themselves be
confidential. G17 tracks review of that assumption; no visibility-policy change
is settled here.

## 6. Enforcement Points, Ranked Honestly

| # | Point | What it is | Strength |
|---|---|---|---|
| 1 | Human agent selection | The real decision, made with full knowledge of the task | Not enforced. It is a choice |
| 2 | Differential materialization | A property of what exists on disk, not a claim any caller makes | Limits the workspace document set; does not block access through other paths |
| 3 | Store permissions | Compartments are separate trees at mode `0700` | Separates OS users; does not isolate processes running as the owner |
| 3b | Remote repository access | One private repository per compartment | Planned transport; the Git host enforces repository access. Caiman does not hide files from a repository reader |
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

The brief follows the metadata-only rule; its visibility assumption is under
review in G17 (§5.5).

### 7.2 Conversion happens outside Caiman

Caiman registers one file of any format unchanged (S-08, S-25). Conversion is
optional and happens outside Caiman.
It makes no AI calls for splitting, labeling, or navigation generation.
**Handing a confidential PDF to a hosted conversion service is a disclosure,
and Caiman cannot prevent it.** By
the time a converted file reaches ingest, the document has already been wherever it was
going to go.

This matters more for customer specifications than vendor manuals, per §2.1: a
leaked reference manual is the vendor's widely-held document; a leaked
specification is identifiable as that customer's.

Original-source and converter information are optional (S-26). When converter
name is supplied, it can help identify affected documents. Caiman does not
record converter versions or hosted/local status. A name or its absence is not
evidence of local processing or permission to widen access.

The TUI labels this section optional and permits skipping it. Explicit access
labels for the document remain mandatory and independent of provenance. Missing
source or converter fields must never become a missing access label or a default
public label.

The operating rule is human: convert compartmented documents locally. It belongs
in the ingest checklist, not in the list of enforced controls.

### 7.3 The store is hosted by a third party, and its history is permanent

A private remote still gives the host a copy of the material. Check hosting
permission per counterparty before publication. Privacy settings do not answer
that question.

S-33 supersedes the one-repository proposal: teammates have different access,
so each compartment has its own private repository. Anyone with repository read
access can obtain its entire history; local catalog filtering is not a remote
access control. Repository administration and transport remain to be implemented.

Git deletion does not remove earlier copies from history, clones, or host caches.
Ingest therefore never pushes. Publication is separate and requires label review;
[Storage §7.6](STORAGE.md#76-push-and-pull) owns that workflow and
[§9.5](STORAGE.md#95-git-history-is-permanent-and-revocation-is-worse-because-of-it)
explains its limits.

### 7.4 Harness residue

`harness.md` records measured evidence that session harnesses write plaintext
copies of every file an agent reads into an append-only transcript under `$HOME`,
which persists after documents are re-materialized.

Consequences:

- **Materialization is not reversible.** The revocation procedure in §8 removes
  the copy Caiman controls, not the transcript.
- The gap is bounded for `open` sessions, because there is nothing
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

Observed reads help identify documents that may remain in session transcripts.
They provide leads for an investigation, not a complete inventory of transcript
contents or proof that unrecorded documents were never read.

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
| S-T6 | A document carries multiple compartment entries, including duplicates | Rejected on ingestion, registration and read, even if the caller holds every named compartment; no refs published |
| S-T7 | Write-time and filter-time label generation, property-tested | Identical output across generated inputs |
| S-T8 | Generate a brief for a project with compartmented documents | No document body text appears |
| S-T9 | Generate a brief; search for the customer string from the project manifest | Absent |
| S-T10 | Reclassify or compartment-correct a document | Gone from re-materialized documents and every cache; brief regenerated |
| S-T11 | Supply retired document `structure` or `requirements` metadata | New metadata rejected; historical snapshots remain readable without rewriting bytes |
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
| S-T22 | Save a collection without labels, include a private document in a public or different-compartment collection, or read a private collection outside its scope | Rejected before writes; private collections are absent from out-of-scope catalogs (`tests/test_collections.py`) |
| S-T23 | Edit a document outside authorized scope, change or drop its access labels, or alter its stored file descriptor through metadata editing | Rejected before writes; metadata edits cannot reclassify or replace content (`tests/test_document_edit.py`) |

Architecture-level tests are in `ARCHITECTURE.md` §13; storage-level tests are in
`STORAGE.md` §11. Some tests cover more than one layer; preserve their IDs when cross-referencing.

---

## 11. Optional Hardening

Not part of the design. Available if the accident rate warrants it; recorded so
the options are not rediscovered.

| Option | Mechanism | Assessment |
|---|---|---|
| **Separate OS user** | Compartmented documents materialized to a path owned by a second uid, mode `0700`. A normal session gets `EACCES` from the kernel; a sealed session runs as that uid and its ordinary file reads work | Strong, and genuinely painful on macOS: separate home directory, credentials, and shell config, plus `sudo -u` per session. Give the sealed session its own worktree rather than sharing one across uids |
| **Encrypted disk image (macOS)** | `hdiutil create -encryption AES-256 -type SPARSEBUNDLE`, mounted only for sealed work, key in Keychain | Detached, the documents are ciphertext rather than merely unreadable. Sidesteps the multi-user pain; "did I unmount" is easier discipline than "am I the right user". The better option on this platform |
| **Egress control** | Point the harness at a self-hosted gateway; block direct egress to model APIs at the firewall | An existing product category. Relevant only if human routing proves insufficient in practice |

Note that none of these reaches harness residue (§7.4), which lives under `$HOME`
rather than in the document tree.
