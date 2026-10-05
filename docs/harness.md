# Harness behaviors

## What this document is for

Historical measurements of session persistence, taken on 2026-09-10. This is
research evidence, not a current harness contract or a source of Caiman policy.
No measurements were repeated during the documentation cleanup.

The observations show that tool output can persist outside Caiman's workspaces.
[Security §7.4](SECURITY-MODEL.md#74-harness-residue) owns the implications for
revocation; G20/G21 track policy and coverage review. The agent map mentioned in
the original analysis was retired by S-19 on 2026-09-15.

## Method

Measured on one macOS machine, 2026-09-10, against real session data — not from
vendor documentation, which does not describe these formats.

- **Claude Code**: 33 transcripts across 20 project directories, 16,636 entries,
  150,094,332 bytes, spanning 2026-08-14 to 2026-09-10. Parsed directly.
- **Codex**: `~/.codex` inspected; SQLite schemas read read-only. No rollout
  files were present (see *Residue*, below, for why that is itself a finding), so
  the transcript format is taken from a session-adapter implementation that reads
  and writes it — `@chirp/squab`, vendored inside Xirp, which is also relevant to
  D-07.

Formats drift. Treat the entry-type inventories as a snapshot with a date on
them, not as a contract.

---

## The shape both harnesses chose

Independently, both converged on the same design:

1. An **append-only JSONL transcript**, one line per event, written as the
   session runs.
2. A **resume flag** that reads it back and reconstructs the conversation.

The consequence that matters here is not the format but the retention: the
transcript is the session's durable state, so it holds **tool results in full**,
not summaries. A `Read` of a document stores that document's contents. There is
no truncation step, no redaction step, and no expiry.

---

## Claude Code

### Location

```
~/.claude/projects/<cwd-with-non-alphanumerics-replaced-by-dashes>/<session-uuid>.jsonl
```

The directory name is derived from the working directory, so a Caiman worktree
gets its own directory and is trivially identifiable.

### What a tool call records

Every call is a `tool_use` block carrying the complete input object, paired with a
`tool_result` carrying the complete output. Measured across 2,746 calls:

| Tool | Calls | Recorded input fields |
|---|---:|---|
| `Bash` | 1,927 | `command`, `description`, `timeout`, … |
| `Read` | 312 | `file_path`, `limit`, `offset` |
| `Edit` | 285 | `file_path`, `old_string`, `new_string` |
| `Write` | 109 | `file_path`, `content` |
| `WebFetch` | 19 | `url`, `prompt` |
| `WebSearch` | 15 | `query` |

So: reads keep the exact path and line range **and the file contents in the
result**; edits keep both the before and after text verbatim; writes keep the
full file body; searches keep the literal query. Because `Bash` dominates, every
shell command run in the session is stored as a plain string, with its stdout.

### Entry types

Beyond `user` / `assistant`, the transcript carries harness state:

| Entry type | Count | Note |
|---|---:|---|
| `assistant` | 5,150 | |
| `attachment` | 3,274 | mostly token reminders; also `edited_text_file`, `diagnostics` |
| `user` | 3,150 | **includes all tool results** |
| `mode`, `permission-mode` | 1,549 | |
| `ai-title`, `last-prompt` | 1,642 | a generated title and the last prompt, stored separately |
| `system` | 481 | |
| `file-history-snapshot` | 232 | see below |
| `file-history-delta` | 141 | see below |
| `cost-state` | 11 | |

Content blocks: 2,751 `tool_use`, 2,751 `tool_result`, **1,419 `thinking`**, 989
`text`. Reasoning is persisted to disk, not ephemeral.

### Separate file tracking

Two dedicated entry types version files the agent modifies, independently of the
`Edit` record:

```json
{ "type": "file-history-delta",
  "trackingPath": "/…/scratchpad/squab-handoff.html",
  "snapshotMessageId": "e0880718-…",
  "backup": { "version": 1, "backupTime": "2026-09-10T17:57:42.776Z",
              "realParentDir": "/…" } }
```

This is the machinery behind rewind. It means an edited file's prior contents can
exist in more than one place inside the transcript.

### Volume, and what dominates it

150 MB across four weeks on one machine. The distribution is the point:

| Entry type | Bytes | Share |
|---|---:|---:|
| `user` | 131,582,019 | 87.7% |
| `assistant` | 14,322,847 | 9.5% |
| `attachment` | 2,859,214 | 1.9% |
| everything else | ~1.3 MB | 0.9% |

Splitting the `user` bytes by what they actually contain:

| | Blocks | Bytes |
|---|---:|---:|
| `tool_result` payloads | 2,753 | 59,085,508 |
| Prompts a human typed | 396 | 148,978 |

**99.7% of recorded user-turn content is tool output, not typed input.** The
transcript is overwhelmingly a copy of files read and commands run. A single repo
directory accounts for 51 MB of it.

This is the number to keep in mind when reasoning about the documents: a session
that greps a materialized specification set does not record *that it grepped* —
it records the matched text.

---

## Codex

Codex splits the same information across a transcript **and** a set of SQLite
databases. Both halves matter; the second is easy to miss.

### Transcript

```
~/.codex/sessions/YYYY/MM/DD/rollout-<timestamp>-<uuid>.jsonl
```

Date-bucketed rather than project-bucketed — the working directory is recorded
*inside* the file, so locating a session for a given directory means opening
candidates.

The file opens with `session_meta` (id, cwd, cli_version, originator,
model_provider) and `turn_context` (model, cwd), then one line per event.
`response_item` entries carry the model-visible conversation:

| `response_item` type | Carries |
|---|---|
| `message` | user and assistant turns |
| `function_call` / `function_call_output` | tool name, arguments, and result |
| `custom_tool_call` / `custom_tool_call_output` | as above |
| `local_shell_call` | shell commands, with the full `action` object |
| `reasoning` | model reasoning, persisted |
| `tool_search_call` | |

A parallel stream of `event_msg` entries records what the UI displayed. So a
Codex transcript, like Claude Code's, contains file contents, shell commands, and
reasoning in full.

### The SQLite layer

Five databases in `~/.codex/`, with no analogue in Claude Code:

| Database | Holds |
|---|---|
| `state_5.sqlite` | `threads`, `thread_sections`, `thread_spawn_edges`, `thread_dynamic_tools` |
| `memories_1.sqlite` | `stage1_outputs`, `jobs` |
| `goals_1.sqlite` | `thread_goals` |
| `logs_2.sqlite` | `logs` |
| `queue_1.sqlite` | `queued_items` |

The `threads` table indexes every session:

```sql
CREATE TABLE threads (
    id TEXT PRIMARY KEY,
    rollout_path TEXT NOT NULL,
    cwd TEXT NOT NULL,
    title TEXT NOT NULL,
    first_user_message TEXT NOT NULL DEFAULT '',
    preview TEXT NOT NULL DEFAULT '',
    sandbox_policy TEXT NOT NULL,
    approval_mode TEXT NOT NULL,
    model TEXT, reasoning_effort TEXT,
    tokens_used INTEGER NOT NULL DEFAULT 0,
    git_sha TEXT, git_branch TEXT, git_origin_url TEXT,
    memory_mode TEXT NOT NULL DEFAULT 'enabled',
    …
);
```

Two fields deserve attention here.

**`git_sha`, `git_branch`, `git_origin_url`.** Sessions are tied to specific repo
state. For a Caiman worktree this records which program was being worked on, in a
database outside the worktree.

**`first_user_message` and `preview`.** A denormalized copy of prompt text,
stored outside the transcript file. Deleting the rollout file does not remove
them.

### The memory pipeline

`memories_1.sqlite` holds `stage1_outputs`:

```sql
CREATE TABLE stage1_outputs (
    thread_id TEXT PRIMARY KEY,
    raw_memory TEXT NOT NULL,
    rollout_summary TEXT NOT NULL,
    rollout_slug TEXT,
    usage_count INTEGER, last_usage INTEGER,
    selected_for_phase2 INTEGER NOT NULL DEFAULT 0,
    …
);
```

This is a two-stage pipeline that distills past threads into reusable memory,
with `usage_count` tracking reuse. It is keyed by thread, not by working
directory, project, or anything resembling a compartment. See *Implications*.

### Residue

On the measured machine the rollout directory was empty and `threads` had zero
rows — both had been deliberately cleaned by a session-migration tool. What
survived that cleanup: 32 rows in `logs_2.sqlite` and a `thread_sections` row.

The general lesson stands on its own: **the transcript file is not the only
copy.** A tool that removes rollout files must also reconcile the catalog, and a
human deleting files by hand will not.

---

## Comparison

| | Claude Code | Codex |
|---|---|---|
| Transcript | one JSONL per session | one rollout JSONL per session |
| Keyed by | working directory | date; cwd stored inside |
| Tool inputs recorded | full | full |
| Tool results recorded | full | full |
| Reasoning persisted | yes (1,419 blocks measured) | yes (`reasoning` items) |
| Shell commands | `Bash` tool input | `local_shell_call` |
| File versioning | `file-history-snapshot` / `-delta` | — |
| Side catalog | none | SQLite `threads` |
| Repo identity recorded | no | `git_sha`, `git_branch`, `git_origin_url` |
| Prompt text outside transcript | `ai-title`, `last-prompt` entries | `first_user_message`, `preview` columns |
| Cross-session memory | none in transcript | `stage1_outputs` |
| Encryption at rest | none | none |

---

## Implications for Caiman

### 1. The transcript is an uncontrolled copy of the materialized documents

I-3 forbids compartmented documents entering git, and is enforced by gitignore
plus a pre-commit hook. **The transcript is not git**, so neither guard applies.
I-9's protections — `0444` blobs, a compartment-keyed cache, no symlinks — are
properties of the documents, and the transcript is a copy taken downstream of all of
them.

Concretely: a session that greps a customer specification writes the
matched requirement text into `~/.codex/sessions/…`, unlabeled, in plaintext,
outside the worktree.

This does not defeat the primary control. The engineer still chooses which model sees the material; Caiman does not
verify that choice. What it defeats is the assumption that a compartment's contents
live only where Caiman put them.

### 2. Revocation is incomplete

`SECURITY-MODEL.md` § *Reclassification and revocation* requires document
re-materialization, cache eviction, brief regeneration, index purge. It already
notes, honestly, that this "cannot reach a running session's already-read
context."

The transcript is the **persisted** form of that same gap, and it is worse in one
specific way: already-read context dies with the process, while the transcript
survives indefinitely and is greppable. After a compartment correction, every
prior session's transcript still holds the misfiled document's contents.

Step 1 of that procedure is therefore incomplete as written. Whether it should be
extended is a policy question for that document, not this one.

### 3. Codex's memory pipeline is a potential compartment-crossing channel

`stage1_outputs` distills a thread into `raw_memory` and `rollout_summary` for
reuse in **later** sessions, and nothing in its schema is scoped to a directory,
project, or compartment. A fact extracted from an OEM Alpha session is, as far as
this schema is concerned, eligible to surface in a later session that holds only
`oem-beta`.

This is another form of retained prior context, covered by Security §7.1. It
can cross session boundaries, so a fresh conversation alone is not evidence that
harness memory is isolated. It is also the reason `memory_mode` on
the `threads` row is worth knowing about.

I have not verified what populates `stage1_outputs` or under what conditions it
is consulted; on the measured machine it was empty. **This is a flagged risk, not
a demonstrated leak**, and it should be verified before it informs any decision.

### 4. What the current agent map already handles

Historical note: this analysis originally assumed an `agents.toml` map with
`receives = "public"` or `"all"`. S-19 retired that map after these measurements.
It is not a current control. Open/sealed modes are also retired under pods.
S-39 uses explicit per-session selection and host provisioning; it does not verify
which model the harness uses. [CONTAINER-CONTEXT.md](CONTAINER-CONTEXT.md) owns
the accepted workflow. The measurements above remain historical observations.

## Open questions

These are inputs to existing decisions, not resolutions. Do not implement any of
them without settling the decision first.

1. **How should session context explain transcript persistence?** Switching or
   deleting context cannot erase prior conversation, transcripts, or memories.
   The accepted boundary is in [Session context §8](CONTAINER-CONTEXT.md#8-boundaries-and-lifecycle);
   harness-specific retention procedures remain G20.
2. **Which harness residue can users locate and clean up?** Define supported
   procedures without promising complete revocation. Caiman does not manage
   transcripts or automatically interrupt harnesses in the first version.
3. **Which filesystem boundary is appropriate for confidential workloads?**
   Protecting only the worktree does not protect transcript locations elsewhere.
   Per-session context folders are not a filesystem access boundary.

4. **Does harness selection (D-07) gain a criterion for transcript handling?**
   See below.

---

## Notes for D-07

D-07 requires per-session agent and model selection from any candidate harness.
This measurement suggests a second criterion worth applying: **where the harness
and its agents write session state, and whether that location is configurable.**
A harness that can point transcript storage inside the worktree brings the
residue back under `.gitignore` and inside whatever protects the documents.

The historical D-07 discussion recorded that Xirp "has been discussed as a model; whether it is
obtainable outside Spotify and under what licence is **unverified**." Partial
evidence from the local install, offered as evidence and not as a conclusion:

- It is a Spotify-built Electron application (`com.spotify.xirp`), internal
  package name `@chirp/electron`, marked `"private": true`, with a `chirpEdition`
  of `external`.
- Startup requires an Auth0 login; the installation record carries a subject and
  an `emailDomain`, and there is a revocation-check mechanism and a forced-update
  channel.
- The session-orchestration engine is a separate vendored package, `@chirp/squab`,
  also marked private.

"External edition" plus an identity-gated login is consistent with a distribution
to people outside Spotify under some agreement, not with open availability. **No
licence file was found in the installed bundle**, so this remains unverified in
these measurements. The obtainability question should be answered by asking,
not by inspecting an install.

Separately, `@chirp/squab` is a good reference implementation for the *session
handoff* problem regardless of whether Xirp itself is adoptable — it moves a live
session between agents by transcoding the transcript, which is the same file
format described above.

---

## Limits of this measurement

- **One machine, one point in time.** Entry-type inventories and schemas are a
  2026-09-10 snapshot. Both tools change their formats without notice.
- **The Codex transcript format is second-hand.** No rollout files were present;
  the inventory comes from an adapter that reads and writes the format, which is
  strong evidence but not a direct observation.
- **`stage1_outputs` behavior is unverified.** The table was empty. Its schema
  supports the concern in Implication 3; nothing here demonstrates it.
- **Not a threat-model change.** Everything above is visible to anyone with the
  user's own filesystem access, which the security model already concedes is
  outside what software can defend. The finding is about *residue and revocation*,
  not about a new adversary.
