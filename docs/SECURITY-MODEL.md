# Security Model

**Status:** Current design under [PODS.md](PODS.md) and S-39. Local pod storage
and optional Git sharing are implemented. Per-session materialization, the
portable workspace adapter, and detailed audit hooks remain planned.
**Owns:** Trust boundaries, limitations, and security validation.
**Related:** [Session context](CONTAINER-CONTEXT.md) owns the accepted workflow
and request protocol; [Storage](STORAGE.md) owns materialization mechanics;
[harness observations](harness.md) record dated measurements of retained data.

## 1. Summary

Caiman runs on the host and prepares a complete selected document set for each
session. Agents in containers read it through the worktree bind mount. The host
TUI authorizes published choices and processes requests while open. No store,
full Caiman installation, Docker socket, or host shell access is needed inside
the container.

Pods define ownership and dependency routes. Git-host permissions govern remote
access; filesystem permissions govern local access. There is no application
access-label layer, agent map, or open/sealed mode. Caiman does not verify that a
model is authorized to receive the selected documents.

**Separate session folders are not permission boundaries.** An agent able to
read the shared worktree may read another session's context. Use separate
filesystem/process boundaries when workloads require isolation.

## 2. Threat Model

### 2.1 What is being defended

The design guards against wrong-context selection, stale or substituted pins,
partial installations, accidental publication of generated documents, and
untrusted request files causing writes beyond the registered workspace.
Document bodies remain fixed; approved metadata follows the document model.

### 2.2 The failure being prevented

Several concurrent sessions must retain independent selections. Changing one
session must not silently change another. A retry, crash, stale catalog entry,
or moved version label must not select different documents without an explicit
context change.

### 2.3 Out of scope

Caiman does not isolate processes, attest models, prevent a user from copying
files, erase previous conversation content, manage transcripts, or revoke copies
already fetched. Container/worktree creation and automatic harness interruption
remain external. Container behavior and hook activation must be tested in the
supported environment, not inferred from configuration files alone.

## 3. Classification

The former document classification and compartment scheme is retired. Each
artifact has one owning pod; references may target that pod or public, including
transitive dependencies. Public remains self-contained. Missing dependencies
are errors, never permission to copy or substitute them. [PODS.md](PODS.md)
owns these rules; public storage does not grant redistribution rights.

## 4. Why Content Inspection Cannot Work

A destination pod is chosen by the user, never inferred from document text or
provenance. Registration accepts readable input unchanged; it does not certify
technical correctness, conversion fidelity, or suitability for a model.

## 5. The Control

### 5.1 Human selection and delegation

During initialization, the host user publishes available contexts and chooses
whether workspace requests can automatically select among them. Enabling that
behavior delegates to processes able to write request files. An agent-written
request cannot prove the user approved it in conversation.

### 5.2 Host-owned rules

The host validates requests against its own workspace registration and allowed
choices. Editing shared catalog, workspace, or session JSON cannot add host
permissions, expose another pod, or redirect an installation. Validate size,
shape, protocol version, identities, catalog entry/digest, expected revision,
expiry, and destination containment. Reject path traversal and symlink escapes;
never execute commands supplied by requests.

### 5.3 Selection is per session

Resume reuses a stable session identity and its installed selection. New and
forked sessions get new folders; copying a selection is explicit. Subagents
share their parent's context unless separately selected. The canonical rules
are in [Session context §3](CONTAINER-CONTEXT.md#session-identity).

### 5.4 Installed and acknowledged are different

The host publishes a complete context and matching result. The agent rereads the
brief and acknowledges that revision. An older acknowledgement cannot mark a
newer revision adopted. Acknowledgement does not prove that old information has
been erased. Direct TUI changes require coordination with the affected agent and
its dependent subagents; the host does not automatically interrupt them.

### 5.5 Brief visibility and its assumptions

The generator reads metadata only and uses the project codename, excluding
customer legal identity (I-6). Metadata may still be sensitive. G17 covers the
visibility of catalog choices, resolved JSON, and brief fields. Do not treat a
metadata-only rule as evidence that every field is suitable for every reader.

## 6. Enforcement Points, Ranked Honestly

| Boundary | Mechanism | Limit |
|---|---|---|
| Remote pod access | Git-host permissions | A repository reader can obtain its retained history |
| Local files | OS permissions and actual mounts | Same-user processes may have wider access |
| Dependency routes | Owning pod plus public | Does not isolate an agent from other readable files |
| Context requests | Host-owned registration, choices, and input validation | Shared files are untrusted; request text cannot prove human intent |
| Per-session context | Separate directories, revisions, and serialized changes | Separates selections, not permissions |
| Generated content | Git exclusions, commit guards, and build-context exclusions | Cannot retract existing commits, images, or other copies |
| Read-only documents | Clones preferred; files use `0444` | Owner/root writes can defeat read-only hardlinks |

## 7. Known Gaps

### 7.1 Prior context survives switching

Switching affects the files the session should use next. Conversation history,
results, summaries, and derived answers may retain prior information. Use a fresh
session when old context must be excluded; a fresh session does not by itself
prove that harness memory or filesystem access is isolated (G20).

### 7.2 Conversion happens outside Caiman

Converters can omit or alter technical facts. Ingest stores supplied bytes and
optional provenance, with no conversion, text inspection, or certification.
The user must validate technical fidelity outside ingestion (G08).

### 7.3 The store is hosted by a third party, and its history is permanent

Choose hosting permitted for the documents before sharing a pod. Saving locally
never commits or pushes. Removing a file or revoking membership cannot erase
prior clones, Git history, host backups, or other retained copies. A pod may stay
local where remote hosting is unsuitable.

### 7.4 Harness residue

Harnesses may retain document text in transcripts, summaries, caches, or memory
outside the worktree. [harness.md](harness.md) contains dated observations, not a
complete inventory or current compatibility guarantee. Transcript management and
retention policy remain G20 and are outside the first session-context version.

## 8. Reclassification and Revocation

Pods replace classification edits. Metadata changes create complete immutable
manifests while references retain fixed bodies; this is not an access revocation
mechanism. [DOCUMENT-METADATA.md](DOCUMENT-METADATA.md) owns edit semantics.

Changing a published catalog does not rewrite installed contexts. Explicitly
switch or clean up affected sessions as appropriate. Never delete a session with
an installation in progress. Removing a context directory does not remove
transcripts, copies, images, or remote history. Review those locations separately
without claiming complete revocation.

## 9. Audit

Detailed auditing is separate planned work, not a prerequisite for the initial
request/result workflow. Installation state and acknowledgements are operational
records, not proof of every read or of forgetting previous context.

| Record | Answers | Does not establish |
|---|---|---|
| Materialization record | What Caiman installed for a session revision | All files the agent could access elsewhere |
| Observed-read log | Which managed reads were observed | Complete read coverage or absence of unrecorded reads |

### 9.1 Materialization log

Record workspace/session identity, selected pod and project snapshot, exact
resolved metadata and body digests, context identity/revision, completion state,
and time. Record switches and cleanup without document content. Agent/harness
names are unverified annotations, not model attestation.

### 9.2 Access log

Planned hooks record document identities and locators, never content. They never
block tools or fail a session (I-10). Do not store raw shell commands or search
strings: they can contain document text. Content-free shell representation and
subagent coverage remain G22/G21.

**Absence of a record is not proof that a document was not read.** Show that limit
wherever the log is surfaced. Shell reads, absent hooks, and out-of-harness reads
can escape observation.

### 9.3 What the access log actually buys

Observed reads provide leads for locating retained copies. They are not a
complete inventory of transcripts or proof of model authorization.

### 9.4 Storage and sensitivity

Audit records stay outside the worktree and pod Git repositories, with
restrictive permissions. They can reveal project relationships even without
content. Per-session operational request/result and revision files remain in the
shared worktree as defined in [Session context §3](CONTAINER-CONTEXT.md#3-one-worktree-several-sessions);
they are not the durable audit log. Container-to-host audit collection is separate
work and must not require mounting the store into the agent environment.

## 10. Test Fixtures and Security Tests

Use synthetic confidential inputs. Public examples must retain redistribution
rights and provenance. Write negative tests before implementing the behavior.
These are current acceptance criteria, not claims that session support ships.
The IDs below are retained for cross-references; retired mode/label expectations
have been replaced by pod and session behavior.

| ID | Test | Asserts |
|---|---|---|
| S-T1 | Resolve a missing pod | Explicit error; no substitution |
| S-T2 | Resolve a missing pinned body | Prior complete context retained |
| S-T3 | Provision a project in pod B | Only its pinned dependency set from B and public appears |
| S-T4 | Switch A with B in the same worktree | B's selection and files remain unchanged |
| S-T5 | Request without a valid session or selection | No installation |
| S-T6 | Reference a different private pod | Rejected, including transitively |
| S-T7 | Edit shared catalog/workspace/session metadata to expand choices | Host-owned rules remain authoritative |
| S-T8 | Generate a brief | No document body text appears |
| S-T9 | Search the brief for customer legal identity | Absent |
| S-T10 | Remove installed context | No claim that transcript or external copies were removed |
| S-T11 | Supply retired document structure/requirement-pattern metadata | New metadata rejected; old bytes preserved |
| S-T12 | Resolve a bare project or board name | Lists versions; resolves nothing |
| S-T13 | Save locally | No commit or push |
| S-T14 | Sync a pod repository | Only that pod's data is shared; dependencies are not copied |
| S-T15 | Diverged Git sync | Fails safely and preserves local work |
| S-T16 | Fail every hook | No tool denial or failed harness session |
| S-T17 | Search audit records for source text | No document content |
| S-T18 | Compare direct and shell reads | Coverage gaps explicit; no raw shell command content logged |
| S-T19 | Inspect tracked files and container build inputs | No generated session documents or audit logs |
| S-T20 | Disable automatic context requests | Requests cannot independently enable it |
| S-T21 | Select a pod during ingestion | No destination inference from content |
| S-T22 | Attach another private pod's document to a collection | Rejected; owning pod/public rule preserved |
| S-T23 | Edit metadata | Fixed bodies and immutable history preserved |
| S-T24 | Submit traversal or symlink-escape paths | No writes outside the registered destination |
| S-T25 | Retry or expire a request | No duplicate installation; unaccepted expired request rejected |
| S-T26 | Submit a stale revision or catalog digest | Rejected without silent substitution |
| S-T27 | Crash during installation | Complete revision and consistent result recovered |
| S-T28 | Acknowledge an older revision | Newer installation remains unacknowledged |
| S-T29 | Start/resume/fork sessions in a real container | Stable independent identities; no store/package/socket requirement |

Architecture tests are in [Architecture §13](ARCHITECTURE.md#13-testing-and-validation),
storage tests in [Storage §11](STORAGE.md#11-testing-and-validation), and lifecycle
acceptance scenarios in [Session context §9](CONTAINER-CONTEXT.md#acceptance-scenarios).

## 11. Optional Hardening

Separate worktrees, OS users, containers, or machines can supply actual access
boundaries if their permissions and mounts are configured accordingly. Include
transcripts and other harness state when evaluating those boundaries. Disk
encryption protects stored data under its own assumptions; it does not attest
model authorization or prevent content leaving a running session.
