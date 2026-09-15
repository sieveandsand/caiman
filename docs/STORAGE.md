# Storage Design

**Status:** Proposed. Resolves `DECISIONS.md` D-02 and D-10 for the MVP.
**Scope:** The on-disk representation of documents, boards, and projects, and the
procedure that builds a session workspace from them.
**Related:** `ARCHITECTURE.md` §2 (Store) and §4 (Materialize), `SECURITY-MODEL.md`,
`harness.md`.

---

## 1. Summary

Caiman stores three kinds of versioned object — document versions, board
versions, and project versions — and assembles a subset of them into a
per-session workspace on disk.

This document specifies a **content-addressed store on the local filesystem**,
laid out as a strict subset of the OCI registry model: immutable objects named by
their SHA-256 digest, plus a small mutable layer mapping human-readable names to
digests. Access partitions, called **compartments**, are separate directory trees
at the top level of the store.

Three properties drive the design:

1. A session pins a **digest**, not a name, so the documentation it saw remains
   resolvable after the name is repointed.
2. Changing a document's access labels changes its identity, which is what makes
   reclassification detectable downstream.
3. The store's on-disk shape is the same shape the materialization step needs,
   so no separate caching concept is required while the store is local.

The design uses no database and no running service.

---

## 2. Background and Problem

### 2.1 What changed

An earlier design had the store feeding a retrieval service, which implied a
queryable backend. `DECISIONS.md` S-18 removed that service: the filesystem is
now the interface between Caiman and the coding agent. The store's remaining job
is much narrower, and the backend decision should be re-made against the narrower
job rather than inherited.

### 2.2 The failure this design prevents

`CLAUDE.md` I-4 requires that a session pin an immutable digest rather than a
mutable name. The concrete scenario that makes this necessary is **re-conversion**.

Caiman does not convert PDFs (S-08). The user converts documents with an external
tool and supplies markdown. Those tools improve, and documents get converted
again:

| Date | Action | Result |
|---|---|---|
| August | Convert `S32K3XXRM.pdf` with `marker` 1.8.2 | Ingested as reference manual `rev-4` |
| November | `marker` 2.0 fixes register-table extraction; re-convert the same PDF | Ingested as reference manual `rev-4` again |

Both ingests are legitimately "reference manual rev-4". Same source PDF, same
vendor document version, different bytes.

If documents are stored under their human-readable names, the second ingest
either overwrites the first or needs an ad-hoc `rev-4-v2` convention. In the
overwrite case, **every session that recorded "rev-4" silently changes meaning**.
A session from August, revisited in December, now resolves documentation that did
not exist when it ran. Any citation produced by that session becomes unverifiable.

Content addressing removes the ambiguity: August's session pinned
`sha256:9f3c22de…71`, which still resolves to the exact bytes that were in
context. November's conversion is a different digest. The name `rev-4` is
repointed for new sessions, and both versions continue to exist.

### 2.3 Why access labels must be part of object identity

`SECURITY-MODEL.md` requires a defined procedure when a document is
reclassified — most importantly when a document was ingested against the wrong
compartment, which is the likeliest hand-entry error and the one with the worst
consequence.

That procedure needs a signal: something must change so that downstream steps
(re-materialization, cache eviction, brief regeneration) know what to act on. If
labels live outside the pinned identity, they can change with no observable
effect on any pin, and the procedure has nothing to trigger on.

The design therefore hashes labels together with the rest of a document's
metadata, so a label change produces a new object identity over unchanged
content. §6.1 describes the mechanism.

---

## 3. Goals

| ID | Goal |
|---|---|
| G-1 | Store document, board, and project versions immutably, so a pinned reference resolves to identical bytes indefinitely |
| G-2 | Resolve a human-readable name and version to a digest, and a digest to its content |
| G-3 | Make a change to a document's access labels produce a new object identity |
| G-4 | Keep compartments separated by a mechanism the operating system enforces, not by application logic |
| G-5 | Materialize a session workspace without copying document bytes per session |
| G-6 | Never lose an object that a board version or project version references |
| G-7 | Require no running service and no database |
| G-8 | Use a layout that maps directly onto an OCI registry, so migrating later is mechanical |

## 4. Non-Goals

These are capabilities the store deliberately does not provide. Each was required
by an earlier design and became unnecessary when S-18 removed the retrieval
service.

| Not provided | Rationale |
|---|---|
| Query, search, or ranking over content | Retrieval happens with `grep` over the materialized documents (S-04, S-18) |
| Partial fetch within an object | Documents are split into per-chapter objects at ingest, which provides the same benefit more simply (§6.3) |
| Concurrent-writer safety | Single engineer, single machine. Ingest is serialized by the CLI |
| High throughput | Volume is hundreds of documents, not millions |
| Authentication | POSIX permissions only. §12.3 states the threshold at which this becomes insufficient |
| Deleting unreachable objects | Garbage collection is specified (§8.4) but not implemented for the MVP; disk is cheaper than the risk of breaking a pin |

---

## 5. Requirements and Constraints

### 5.1 Functional requirements

| ID | Requirement | Source |
|---|---|---|
| R-1 | Objects are immutable once written | I-4 |
| R-2 | A name plus version resolves to exactly one digest at a given time | I-4 |
| R-3 | A bare name without a version does not resolve; it returns the list of versions | I-7 |
| R-4 | Changing a document's labels yields a new document version digest | `SECURITY-MODEL.md` |
| R-5 | A project version resolves transitively to a complete pin set, including everything its board version pins | S-07 |
| R-6 | Materialized files are read-only | I-9 |
| R-7 | No symbolic links to directories appear in the materialized documents | I-9 |
| R-8 | A document version that cannot be fully materialized causes `sync` to fail | I-9 |
| R-9 | Content for compartment A is never written into a workspace for a session that does not hold A | I-1, S-16 |
| R-10 | A document with neither a public assertion nor a compartment is unreachable | I-1 |

### 5.2 Environmental constraints

| Constraint | Consequence for the design |
|---|---|
| Primary platform is macOS on APFS | Use `clonefile(2)` as the preferred link mechanism (§7.3) |
| Worktrees may live on a different volume from the store | Must fall back to copying; cross-volume clones and hardlinks are not possible |
| Separate APFS volumes within one container are distinct filesystems | Volume co-location cannot be assumed from "same disk" |
| Markdown documents are large — a 2,000-page reference manual is roughly 20 MB | Per-session copying is wasteful; split documents into per-chapter objects |
| The user supplies already-converted markdown | Converter identity must be recorded as provenance (S-08) |
| Session harnesses persist plaintext copies of files the agent reads, outside the store | Re-materialization does not fully revoke access; see §9.4 |

---

## 6. Design

### 6.1 Object model

The store holds three object kinds. Two are immutable and named by digest; one is
mutable and named by a path.

| Object | Mutable | Named by | Contains |
|---|---|---|---|
| **Blob** | No | SHA-256 of its bytes | One file: a chapter of a document, an errata sheet, or a generated map |
| **Manifest** | No | SHA-256 of its serialized JSON | One version of a document, board, or project: its metadata and its references to other objects |
| **Ref** | Yes | A human-readable path | A single line holding one manifest digest |

The two-level split between blob and manifest is the central structural decision,
and it is worth stating precisely because the terms are easy to conflate.

- A **blob is one file.** `12-lpspi.md` is a blob. Its digest covers only that
  file's bytes.
- A **manifest is one version of one document.** "NXP S32K344 reference manual,
  rev-4" is a manifest. It lists the blobs that make up the document, each with
  its intended filename, and carries all metadata: issuer, version, applicable
  silicon revisions, access labels, provenance.

```
manifest sha256:9f3c22de…71        nxp/s32k344 reference-manual rev-4
  ├── 00-overview.md    → blob sha256:3f9c1a8e…b2
  ├── 12-lpspi.md       → blob sha256:7d02ff41…9a
  ├── 31-watchdog.md    → blob sha256:e18b77c0…04
  └── _map.md           → blob sha256:5b1d99ae…c3
```

**Pins reference the manifest digest, never a blob digest.** A board version pins
document manifests; a project version pins a board manifest and specification
document manifests; a session records the project manifest digest.

This satisfies R-4 directly. Correcting a compartment or changing a label
rewrites the manifest JSON, which changes the manifest digest, while every blob
digest stays the same. The result is a new document identity over identical
content — visible to anything holding a pin, and cheap to store because no bytes
are duplicated.

### 6.2 Directory layout

```
~/.local/share/caiman/store/
├── public/
│   ├── blobs/sha256/
│   │   ├── 3f/3f9c1a8e…b2                        mode 0444
│   │   ├── 7d/7d02ff41…9a
│   │   └── e1/e18b77c0…04
│   ├── manifests/sha256/
│   │   ├── 9f/9f3c22de…71                        document version
│   │   └── c4/c4a10b93…88                        board version
│   └── refs/
│       ├── documents/
│       │   ├── nxp/s32k344/reference-manual/rev-4   → sha256:9f3c22de…71
│       │   ├── nxp/s32k344/reference-manual/rev-3   → sha256:5a71e0cc…13
│       │   ├── nxp/s32k344/errata/rev-6             → sha256:b8d4109f…2e
│       │   └── ti/tps65313/datasheet/2024-03        → sha256:44ce8a71…d0
│       └── boards/
│           ├── zonal-ctrl-rear/2.0                  → sha256:71ba0e4d…9c
│           └── zonal-ctrl-rear/2.1                  → sha256:c4a10b93…88
│
├── oem-alpha/                                       mode 0700
│   ├── blobs/sha256/…
│   ├── manifests/sha256/…
│   └── refs/
│       ├── documents/
│       │   ├── oem-alpha/flash-spec/3.2             → sha256:2d90ac17…a5
│       │   ├── oem-alpha/secoc-spec/3.1             → sha256:6e3f1180…77
│       │   └── oem-alpha/deviations-falcon/2026-06  → sha256:aa47c3b2…19
│       └── projects/
│           ├── falcon/A-sample                      → sha256:1c8e4470…3b
│           └── falcon/B-sample                      → sha256:9e21ffa6…c7
│
└── oem-beta/
    └── (same structure, no shared objects)
```

The two-character directory level (`3f/`, `9f/`) is the first two hex characters
of the digest. It exists only to keep any single directory from accumulating tens
of thousands of entries, which degrades directory operations on most filesystems.
It carries no meaning and is derivable from the digest.

Four consequences of this layout are load-bearing:

**Mutable state is confined to one directory.** `refs/` is the only part of the
store that ever changes after a write. Everything under `blobs/` and `manifests/`
is created once and never modified. This makes R-1 a structural property rather
than a rule the code has to remember, and it makes the distinction between a tag
and a pin — the subject of I-4 — visible in the directory structure.

**Compartments are separate trees, so access control is `chmod`.** Satisfying R-9
locally requires only `chmod 0700 store/oem-alpha`. Application code does not
mediate access to compartmented content; the kernel does. This composes with the
optional hardening described in `SECURITY-MODEL.md` (a dedicated uid, or a
per-compartment encrypted disk image) without any change to the layout.

Manifests are partitioned along with blobs, not left in a shared tree. A project
manifest contains the customer's legal name; a document manifest names the
specification and its version. Both are compartment-sensitive even when no
document content is read.

**Boards are public; projects are compartmented.** Hardware carries no customer
identity, which follows from S-13. The practical benefit is that one board
version is shared by several customers' projects with no duplication and no
cross-compartment reference: each project manifest holds the same public board
digest.

**The layout is an OCI subset.** Blobs correspond to layers, manifests to
manifests, refs to tags. G-8 is satisfied by construction rather than by a
planned migration path. §12.3 describes when to make that move.

### 6.3 Why a document is many blobs

Two reasons, both quantitative.

*Context size.* A 2,000-page reference manual is roughly 20 MB of markdown.
Splitting by chapter lets an agent read one section into context. A single file
of that size cannot be read at all and can only be grepped.

*Deduplication across revisions.* Reference manual revisions are typically
mostly-unchanged documents. Chapters that do not change between rev 3 and rev 4
hash identically and are stored once. The saving scales with the number of
revisions retained, which is exactly the dimension this project expects to grow:
several silicon revisions and board versions are simultaneously live (S-02).

The chapter split is produced at ingest and recorded in the manifest's `files`
list. Splitting is not required to follow any particular boundary, but
`ARCHITECTURE.md` §1 constrains it: register tables, bitfield descriptions, and
individual requirements must not be divided across files.

### 6.4 Manifest schemas

All manifests are JSON with a `schema` field carrying a name and version, so the
format can evolve without ambiguity about how to parse an old object.

Serialization must be **canonical** — sorted keys, fixed separators, UTF-8, no
insignificant whitespace — because the digest is taken over the serialized bytes.
Two manifests with the same logical content must produce the same digest.

#### 6.4.1 Document version

`public/manifests/sha256/9f/9f3c22de…71`

```json
{
  "schema": "caiman.document/1",
  "issuer": "nxp",
  "part": "s32k344",
  "doc_type": "reference-manual",
  "version": "rev-4",
  "structure": "prose",
  "labels": { "public": true, "compartments": [] },
  "silicon_revisions": ["1.0", "1.1"],
  "source": { "filename": "S32K3XXRM.pdf", "sha256": "d4e1…", "pages": 2184 },
  "converter": { "name": "marker", "version": "1.8.2", "hosted": false },
  "pipeline_version": "caiman-ingest/0.3",
  "ingested_at": "2026-08-21T09:14:22Z",
  "files": [
    { "path": "00-overview.md", "sha256": "3f9c1a8e…b2", "size": 41203 },
    { "path": "12-lpspi.md",    "sha256": "7d02ff41…9a", "size": 288104 },
    { "path": "31-watchdog.md", "sha256": "e18b77c0…04", "size": 96551 }
  ],
  "map": { "path": "_map.md", "sha256": "5b1d99ae…c3" }
}
```

A requirement-structured document — a customer specification — differs in two
fields:

```json
  "structure": "requirement",
  "requirements": {
    "pattern": "^REQ-FLASH-\\d{4}$",
    "count": 412,
    "ranges": ["REQ-FLASH-0001..0412"]
  },
```

| Field | Purpose |
|---|---|
| `structure` | Selects the admission check at ingest. `requirement` documents are rejected unless requirement IDs appear where the pattern says they should (I-5) |
| `labels` | The access decision input. Included in the digest, per R-4 |
| `source.sha256` | Digest of the original PDF. Lets you determine whether two ingests came from the same source file, which is what identifies a re-conversion |
| `converter` | Provenance. Answers "which documents went through which converter" when one is found to have dropped content, and is the field the hosted-converter lint in `SECURITY-MODEL.md` reads |
| `silicon_revisions` | Which mask revisions this document applies to. Distinct from document version and board version — see `ARCHITECTURE.md`, Data model |
| `map` | The generated navigation aid: heading tree, requirement-ID ranges, identifier index (`ARCHITECTURE.md` §1) |

#### 6.4.2 Board version

`public/manifests/sha256/c4/c4a10b93…88`

```json
{
  "schema": "caiman.board/1",
  "board": "zonal-ctrl-rear",
  "version": "2.1",
  "derives_from": "2.0",
  "relation": "special variant — adds redundant CAN, drops display header",
  "parts": [
    { "role": "application-mcu", "part": "nxp/s32k344",
      "silicon_revision": "1.1", "refdes": "U1",
      "documents": [
        { "ref": "nxp/s32k344/reference-manual/rev-4",
          "digest": "sha256:9f3c22de…71" },
        { "ref": "nxp/s32k344/errata/rev-6",
          "digest": "sha256:b8d4109f…2e" }
      ] },
    { "role": "safety-companion", "part": "ti/tps65313",
      "silicon_revision": "A", "refdes": "U4",
      "documents": [
        { "ref": "ti/tps65313/datasheet/2024-03",
          "digest": "sha256:44ce8a71…d0" }
      ] }
  ],
  "links": [
    { "name": "safety-link",
      "between": ["application-mcu.LPSPI1", "safety-companion.SPI"] },
    { "name": "clock-tree",
      "from": "clock-generator",
      "to": ["application-mcu", "safety-companion"] }
  ]
}
```

`role` is the identity of a part instance; `refdes` is optional cross-reference
metadata for schematic lookup and is never used as an identifier (S-12).

Each document entry carries both a `ref` and a `digest`. The digest is
authoritative and is what resolution uses. The ref is retained for diagnostics —
it lets a human read a manifest and understand it without dereferencing every
digest — and must never be used to resolve at consumption time (I-4).

`derives_from` and `relation` are declared by a human and are never computed
(I-8). The stored manifest is a complete snapshot, not a delta against its
parent: authoring may express a change as "start from 2.0 and modify these three
parts", but what is written is the full part list (S-11). Deleting the
`derives_from` edge would cost only the brief's change summary; everything still
resolves.

#### 6.4.3 Project version

`oem-alpha/manifests/sha256/9e/9e21ffa6…c7`

```json
{
  "schema": "caiman.project/1",
  "project": "falcon",
  "version": "B-sample",
  "customer": "OEM Alpha Motors GmbH",
  "compartments": ["oem-alpha", "falcon"],
  "derives_from": "A-sample",
  "relation": "spec set moved 3.0 → 3.2; secure flashing added",

  "board": { "name": "zonal-ctrl-rear", "version": "2.1",
             "digest": "sha256:c4a10b93…88" },

  "spec_set": "OEM release 3.2",
  "documents": [
    { "ref": "oem-alpha/flash-spec/3.2", "digest": "sha256:2d90ac17…a5" },
    { "ref": "oem-alpha/secoc-spec/3.1", "digest": "sha256:6e3f1180…77" }
  ],
  "precedence": [
    { "ref": "oem-alpha/deviations-falcon/2026-06",
      "digest": "sha256:aa47c3b2…19", "note": "program deviations" },
    { "ref": "oem-alpha/flash-spec/3.2", "digest": "sha256:2d90ac17…a5" }
  ],

  "features": [
    { "name": "secure-flashing", "scope": "required",
      "governed_by": [
        { "ref": "oem-alpha/flash-spec/3.2",
          "requirements": ["REQ-FLASH-0100..0180"] },
        { "ref": "oem-alpha/deviations-falcon/2026-06" }
      ],
      "realized_on": ["application-mcu", "boot-flash"],
      "related": [
        { "feature": "secure-boot",
          "relation": "shared HSM key hierarchy on the application MCU" }
      ] },
    { "name": "ota-update", "scope": "not-used" }
  ]
}
```

Two fields deserve specific attention.

`board` holds a **public** digest from inside a **compartmented** manifest. This
is the only cross-compartment reference in the model and it is deliberate: it is
what allows one board version to serve several customers. The reference direction
matters — a compartmented manifest may name a public object, but no public
manifest ever names a compartmented one. That asymmetry is what keeps the public
tree readable by any session.

`customer` is the only place the customer's legal identity is stored. It never
appears in a generated brief, which names the program by codename (I-6). Storing
it in a compartmented manifest is what makes the codename convention enforceable
rather than aspirational.

`precedence` is an ordered list, highest authority first, declared by a human
(I-8). Caiman renders it into the brief and does not compute over it.

### 6.5 Configuration

```
~/.config/caiman/
├── agents.toml         agent → material map (S-19)
└── config.toml         store_root, cache_root, link strategy
```

| Setting | Default | Notes |
|---|---|---|
| `store_root` | `~/.local/share/caiman/store` | The only path that requires backup |
| `cache_root` | `~/.cache/caiman` | Unused while the store is local (§7.4) |
| `link_strategy` | `auto` | `auto` selects per §7.3; may be forced to `copy` for debugging |

The three roots are separated by lifetime rather than by content type:

| Root | Lifetime | Backup |
|---|---|---|
| `~/.config/caiman/` | Hand-edited, rarely changes | With dotfiles |
| `~/.local/share/caiman/` | Append-only, grows | Required |
| `~/.cache/caiman/` | Derived | Never; safe to delete at any time |

Because the store is immutable and content-addressed, backup can be a plain
`rsync`. A second machine is a copy rather than a synchronization problem: two
stores can be unioned by copying objects, and the only conflict possible is a ref
pointing to two different digests, which is visible as a one-line difference.

---

## 7. Data Flows

### 7.1 Ingest

Input: converted markdown files, plus asserted provenance. Output: one new
document version manifest, reachable by a ref.

1. Validate the admission check for the declared `structure`. A `prose` document
   must yield a heading path for every part of its content; a `requirement`
   document must additionally yield requirement IDs matching its declared
   pattern. **Reject the document if this fails** — do not store it with a
   warning (I-5).
2. Generate the navigation map for the document.
3. Write each content file and the map to `blobs/sha256/<aa>/<digest>` in the
   target compartment, mode `0444`. Writing an object that already exists is a
   no-op, which is how deduplication happens.
4. `fsync` the blobs.
5. Serialize the manifest canonically, including the `files` list with each
   blob's digest, and write it to `manifests/sha256/<aa>/<digest>`, mode `0444`.
6. `fsync` the manifest.
7. Write or repoint `refs/documents/<issuer>/<part>/<doc_type>/<version>`.

**The order in steps 3–7 is a correctness requirement, not a preference.** It
guarantees that every manifest reachable from a ref has all of its blobs present.
The failure modes it produces are analyzed in §8.1.

### 7.2 Resolve

Input: a project name and version. Output: a complete, digest-pinned set of
everything the session may materialize.

1. Read `refs/projects/<project>/<version>` in a compartment the caller can
   access. If the path does not exist, fail. If no version is supplied, list the
   available versions and stop — a bare name never resolves (R-3, I-7).
2. Read the project manifest at the resulting digest.
3. Read the board manifest at `board.digest` from the `public` tree.
4. Collect every document digest from the board manifest's part entries and from
   the project manifest's `documents` and `precedence` lists.
5. Read each document manifest and collect its blob digests.

The result is the complete pin set. Nothing in steps 2–5 consults a ref: once
step 1 has produced the project manifest digest, resolution is entirely by
digest, which is what makes the operation reproducible (I-4).

Resolution is also the point where access is decided. A caller that cannot read
`store/oem-alpha/` fails at step 1 with `EACCES` and never learns whether the
project exists.

### 7.3 Materialize

Input: a resolved pin set, an agent name, and a destination directory. Output: a
session workspace.

1. Look up the agent in `agents.toml`. **If the name is absent, fail and write
   nothing** (I-1, S-19). Do not default to `public`.
2. Compute the visible set: every document whose labels are satisfied by the
   intersection of the project's compartments and what the agent profile permits.
3. For each visible document, create its directory under `documents/` and link each blob to
   its recorded filename.
4. Write `_index.md`, listing what was materialized and **what was omitted and
   why**.
5. Write `project.json` — the resolved project structure, fully expanded.
6. Render `project.md`, the brief. The renderer reads manifests only and has no
   access to blob content (I-6).

Resulting workspace:

```
<worktree>/.caiman/
├── project.md                          the brief, loaded into agent context
├── project.json                        resolved structure, machine-readable
└── documents/
    ├── _index.md
    ├── nxp/s32k344/
    │   ├── reference-manual@rev-4/
    │   │   ├── 00-overview.md          link to blob 3f9c1a8e…b2
    │   │   ├── 12-lpspi.md             link to blob 7d02ff41…9a
    │   │   ├── 31-watchdog.md
    │   │   └── _map.md
    │   └── errata@rev-6/
    │       ├── errata.md
    │       └── _map.md
    ├── ti/tps65313/datasheet@2024-03/…
    └── oem-alpha/                      present only if the agent profile allows
        ├── flash-spec@3.2/
        │   ├── 04-programming-session.md
        │   ├── 07-verification.md
        │   └── _map.md
        └── deviations-falcon@2026-06/
            ├── deviations.md
            └── _map.md
```

#### Link mechanism

| Condition | Mechanism | Reason |
|---|---|---|
| macOS, store and workspace on the same APFS volume | `clonefile(2)` via `cp -c` | Copy-on-write. Consumes no additional space until modified, and a modification diverges the copy instead of corrupting the shared original |
| Linux, same btrfs or XFS volume | `cp --reflink` | Same property |
| Same filesystem, no CoW support | Hardlink; blob remains `0444` | Shares the inode, so a write would affect every session — mode `0444` prevents that |
| Different filesystem | Full copy | Neither clone nor hardlink can cross a filesystem boundary |

Clones are preferred over hardlinks wherever available because they eliminate the
shared-inode failure mode entirely rather than relying on file mode to prevent it.

#### Three constraints on materialization

**Never symlink a directory into the documents tree (R-7).** `ripgrep` does not follow
symbolic links unless given `-L`, and `grep -r` does not descend into symlinked
directories. An agent searching a document tree containing a symlinked directory would
receive results with no indication that part of the document set was skipped. This
failure is silent: there is no error, and the answer looks complete. Everything
downstream assumes `grep` over the documents returns the whole truth (I-9).

**Materialized files are read-only (R-6).** With hardlinks, an in-place edit
propagates to every session sharing the inode and corrupts the store's copy.

**Partial materialization is an error (R-8).** If any pinned file cannot be
written, `sync` fails, names the file, and does not leave a partial workspace in
place. A workspace missing one chapter is indistinguishable, to an agent, from a
document that never contained it.

#### The document path is the citation

`documents/nxp/s32k344/reference-manual@rev-4/12-lpspi.md` encodes issuer, part,
document type, and version. A `grep` hit therefore yields document identity and
version directly from the file path; the locator — a heading path or a
requirement ID — comes from the matched text.

This satisfies I-5 through the directory layout rather than through a metadata
lookup. There is no sidecar file to read, nothing that can fall out of sync with
the content, and the property holds even when an agent reads a file by a route
Caiman did not anticipate.

The `@version` suffix is required for this to work. A bare
`reference-manual/` directory would make a stale workspace and a current one
produce identical citations.

`_index.md` records omissions explicitly — for example, *"OEM specifications: not
materialized (session mode: open)"*. Without it, a missing directory is
ambiguous: an agent cannot distinguish "this project has no specifications" from
"this session may not see them", and the distinction determines whether it should
stop and ask (S-19).

### 7.4 Cache

```
~/.cache/caiman/
└── blobs/
    ├── public/sha256/…
    └── oem-alpha/sha256/…
```

**While the store is local, this directory is not used.** Materialization links
directly out of `store/<compartment>/blobs/`, which already has the required
shape. The cache exists for the case where the store is remote — an OCI registry
— and objects must be fetched before linking.

The code path should be written as *fetch to cache, link from cache* from the
start, with a local store satisfying the fetch step trivially. Moving to a remote
store then becomes a configuration change rather than a restructuring.

The cache is keyed by compartment for the same reason the store is. Hardlinks
share an inode and therefore share permissions: a single shared cache directory
would leave a compartmented blob readable through the cache path regardless of
the permissions on the directory it was linked into (I-9).

---

## 8. Failure Handling and Edge Cases

### 8.1 Interrupted ingest

The write order in §7.1 bounds what a crash can leave behind.

| Interrupted after | State | Consequence | Recovery |
|---|---|---|---|
| Some blobs written | Blobs present, no manifest | Unreferenced blobs consume disk. No correctness impact — nothing can reach them | Re-run ingest; identical blobs are no-ops |
| All blobs, manifest written | Manifest present, no ref | Object is complete but unreachable by name. Resolvable by digest | Re-run ingest; converges on the same digest and writes the ref |
| Ref written | Complete | None | — |

The order makes the dangerous state unreachable. A manifest is never written
before its blobs, so **a reachable manifest always has complete content**. The
inverse — a manifest whose blobs are missing — would fail at materialization,
possibly weeks later, in a session that has no context for the error.

Orphaned blobs are acceptable. Orphaned manifests are not, and the write order is
what prevents them.

### 8.2 Integrity

Verify the digest of every blob and manifest on read. A mismatch means the store
is corrupt or has been modified outside Caiman; fail loudly rather than
materializing content that does not match its name.

The cost is one hash per file read, which is negligible relative to the I/O
already being performed.

### 8.3 Reclassification and compartment correction

The procedure required by `SECURITY-MODEL.md`, expressed in terms of this design.
A document ingested against the wrong compartment is the motivating case.

1. Re-ingest the document with corrected labels into the correct compartment.
   The blobs are byte-identical and so may already exist there; the manifest
   digest is new because labels are inside it (R-4).
2. Repoint the ref to the new manifest digest.
3. Update every board and project version that pinned the old digest. Because
   versions are immutable, this creates **new** board and project versions — it
   is not an edit. This is a real cost and is the honest consequence of
   immutability.
4. Re-materialize affected workspaces, which removes the materialized copy.
5. Delete the incorrectly-placed objects from the wrong compartment's tree. This
   is the one sanctioned deletion in the design, and it must verify that no
   manifest in that compartment still references the blobs.

**Step 4 is incomplete, and the limitation is external to this design.**
`harness.md` documents measured evidence that session harnesses write plaintext
copies of every file an agent reads into an append-only transcript under `$HOME`,
which persists after the documents are removed. Re-materialization removes the copy
the store controls; it does not remove harness residue. The consequence is that
revocation is not achievable for any agent profile with `receives = "all"`
through this mechanism alone. See `harness.md` §*Implications*, and
`SECURITY-MODEL.md` for whether the procedure there should be extended.

### 8.4 Reference counting and deletion

The store never deletes objects during normal operation. If garbage collection is
implemented later, it must:

1. Enumerate every ref under `refs/projects/` and `refs/boards/` in every
   compartment.
2. Walk transitively: project manifest → board manifest → document manifests →
   blobs.
3. Delete only objects not reached by the walk.

The hazard is specific. A project version pins document manifest digests
directly. If a document ref is repointed after a re-conversion, the old manifest
becomes unreferenced *by any ref* while still being pinned *by project versions*.
Garbage collection driven by refs alone would delete it and break those pins
permanently. This is the same hazard that registry garbage collection presents
for untagged manifests, noted in D-02.

Deferring garbage collection entirely is the safe choice for the MVP: the objects
are markdown, the volume is hundreds of documents, and disk is cheaper than a
broken pin.

### 8.5 Cross-volume workspaces

If the workspace is not on the store's filesystem, clone and hardlink both fail
and materialization falls back to a full copy. This is correct but consumes disk
proportional to sessions × document set size.

Note that separate APFS volumes within a single container are distinct
filesystems for this purpose, so co-location cannot be inferred from the disk
being the same physical device. `sync` should detect the fallback and report it,
because the symptom otherwise is slow session startup with no stated cause.

---

## 9. Security Considerations

### 9.1 What the layout enforces

| Control | Mechanism | Strength |
|---|---|---|
| Compartment separation in the store | Directory permissions (`0700`) | Enforced by the kernel. A process without access fails at `open()` |
| Compartment separation in a workspace | Documents outside the session's compartments are never written | Enforced by absence. An agent cannot read a file that does not exist |
| Unknown agent | `sync` fails, writes nothing | Fail-closed, per I-1 |
| Unlabeled document | Neither public nor compartmented; materialized nowhere | Fail-closed, per I-1, R-10 |
| Tampering with stored content | Digest verification on read | Detects modification; does not prevent it |

### 9.2 Metadata is compartmented, not only content

Manifests live inside the compartment tree because they are themselves sensitive.
A project manifest contains the customer's legal name. A document manifest names
a specification and its version, which can identify a customer relationship even
without the document body. Placing manifests in a shared tree would leak this
while appearing to protect the content.

### 9.3 The public/compartmented reference asymmetry

A compartmented manifest may reference a public object. A public manifest must
never reference a compartmented one. This is what allows the public tree to be
readable by every session while compartmented trees remain isolated, and it is
the property to check when adding any new reference to the model.

### 9.4 What this design does not protect against

**Harness residue.** As described in §8.3, materializing a document causes a
second plaintext copy to be written outside the store by the session harness. The
store's guarantees end at the workspace boundary.

**A determined local user.** Every control here is defeatable by someone with
administrative access to the machine, which is the machine's owner. This matches
the threat model stated in `SECURITY-MODEL.md`: the objective is to make an
accidental disclosure require a deliberate act, not to make disclosure
impossible.

**Authentication.** There is none. Separation is POSIX permissions, which is
sufficient for one engineer on one machine and insufficient the moment a second
person or a second trust domain is involved (§12.3).

---

## 10. Performance and Resource Considerations

**Session startup** is dominated by the number of files linked, not by their
size, because CoW clones and hardlinks do not copy bytes. A document set of a few
thousand files is a few thousand `clonefile` calls.

**Disk usage** is one copy of each unique blob, plus manifests, which are small.
Two boards sharing a reference manual store it once. Two revisions of a manual
store only the chapters that differ. Sessions consume essentially no additional
space unless materialization falls back to copying (§8.5).

**Resolution** reads one ref and a handful of manifests — tens of small JSON
files. At the stated volume (tens of boards, tens of projects, hundreds of
documents) there is no reason to build an index, which is the substance of the
D-10 decision.

**Ingest** is bounded by hashing and writing the converted markdown, so it is I/O
bound and proportional to document size. It runs once per document version.

---

## 11. Testing and Validation

Tests are written before the mechanism they cover, per `CLAUDE.md`. These are the
storage-specific cases; the full negative-test list is in `SECURITY-MODEL.md`.

| ID | Test | Asserts |
|---|---|---|
| T-1 | Ingest the same content twice; compare blob digests | Deduplication and deterministic hashing |
| T-2 | Ingest the same content with different labels; compare manifest digests | R-4: labels are inside object identity |
| T-3 | Canonical serialization round-trip with keys in different input orders | One logical manifest yields one digest |
| T-4 | Kill ingest after blob write, before manifest write; then resolve | No reachable manifest with missing blobs (§8.1) |
| T-5 | Corrupt a blob on disk, then materialize | Digest verification fails the operation |
| T-6 | Materialize a project in compartment A with an agent profile permitting all | No file from compartment B appears in the workspace (R-9) |
| T-7 | Materialize with an agent profile of `public` | No compartmented document is written, for any project |
| T-8 | Materialize with an agent name absent from `agents.toml` | Nothing is written at all (I-1) |
| T-9 | Ingest a document with neither `public` nor a compartment | Materialized nowhere |
| T-10 | Materialize where one blob is unreadable | `sync` fails, names the file, leaves no partial workspace (R-8) |
| T-11 | Walk a materialized document tree for symlinked directories | None exist (R-7) |
| T-12 | Check modes of every materialized file | All `0444` (R-6) |
| T-13 | Resolve a project name with no version | Returns the version list; does not resolve (R-3) |
| T-14 | Resolve a project version whose board ref was repointed after pinning | Resolves the originally pinned board digest (I-4) |
| T-15 | Ingest a `requirement` document whose chunks lack requirement IDs | Rejected at ingest (I-5) |

T-14 is the test that directly covers §2.2, and it should exist before the store
is considered done.

---

## 12. Alternatives Considered

### 12.1 Name-addressed directories

Store documents under readable paths:
`store/documents/nxp/s32k344/reference-manual/rev-4/12-lpspi.md`

Simpler, browsable with `ls`, and no digest machinery.

Rejected because of §2.2. A re-conversion under the same vendor version either
overwrites the previous ingest — silently changing what every existing pin means
— or requires an ad-hoc naming convention that reintroduces the same problem one
level down. Labels would also sit outside object identity, leaving the
reclassification procedure with nothing to trigger on (§2.3).

The secondary losses are deduplication across revisions and immutability by
construction, which would become a convention the code must uphold.

This alternative would be defensible if re-conversion never happened. Given that
Caiman explicitly does not own conversion and expects converter quality to
improve (S-08), it will.

### 12.2 Object store plus a relational manifest database

Put blobs in object storage and model documents, boards, projects, and features
as relational tables.

Rejected for the MVP. D-10 already establishes that canonical JSON is the source
of truth and any relational view is derived; at this volume, reading manifests
directly is faster than maintaining a derived index, so the database has no work
to do. It would also add a service to operate, which D-04 identifies as the
scarcest resource on this project.

This becomes attractive if queries across projects and features become routine —
for example, "which programs require secure flashing" across many customers. That
is a reporting need, not a session need.

### 12.3 OCI registry via ORAS, immediately

Use a registry from the start: compartments map to repositories with separate
credentials, immutability is enforced by the registry, and retention is
configuration rather than discipline.

Rejected for now because it adds a service and an authentication system to a
single-user, single-machine deployment, and provides nothing the filesystem
layout does not already provide at that scale. Registry listing by name is also
awkward compared with a directory walk.

**The trigger for revisiting is specific:** move to a registry when compartment
separation must be real authentication rather than POSIX permissions — that is,
when a second person or a second machine with a different trust boundary is
involved, or when the store stops living on hardware you control.

Because §6.2 is a strict OCI subset, that migration maps directly: blobs become
layers, manifests become manifests, refs become tags.

### 12.4 lakeFS or DVC

Both provide versioning over object storage. Rejected as substantial systems
whose primary abstraction — branching — is the wrong axis for this data. Board
and project versions are not branches; they are independent immutable snapshots
that coexist indefinitely. DVC's metadata and access-control model is also built
for ML datasets and does not express compartments.

---

## 13. Risks and Open Questions

### 13.1 Open questions

**Should refs repeat the issuer inside an already-compartmented store?**
`refs/documents/oem-alpha/flash-spec/3.2` inside `store/oem-alpha/` names the
compartment twice. Keeping it means a ref string is portable if a document ever
changes compartment, and makes the document path mirror the ref exactly. Dropping
it (`refs/documents/flash-spec/3.2`) removes redundancy. Mild preference for
keeping it; low cost either way; decide before the first ingest.

**Does `Chunk` need to exist as a stored object?** Chunks were introduced when
the design included a semantic index and were the unit the index was built over.
With S-18 there is no index, materialization is whole-document, and the agent
greps markdown. Locators are carried natively by the format: headings are
headings and requirement IDs appear in the text.

If chunks are removed, labels attach per document rather than per chunk, and the
admission check becomes document-level validation rather than a property of
stored chunk records. That simplifies the data model, the wording of I-1, and
this layout. The counter-argument is that chunk boundaries return if the deferred
semantic tool is ever built — but chunking is deterministic and cheap, so it can
be recomputed at that point rather than stored now.

This changes the wording of an invariant, so it requires its own decision rather
than being absorbed into this one.

### 13.2 Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Reclassification cascades into new board and project versions (§8.3) | A correction is more expensive than an edit, and may be avoided for that reason | Accept for the MVP. Make the CLI perform the cascade in one command so the cost is machine time, not human decision |
| Garbage collection implemented naively later | Permanently broken pins (§8.4) | Do not implement GC for the MVP. If added, drive it from the transitive walk, never from refs alone |
| Canonical serialization drifts between versions | Same logical manifest yields two digests; deduplication and comparison silently degrade | T-3, and treat the serializer as a versioned interface tied to `schema` |
| Workspace on a different volume | Silent loss of CoW benefit; slow startup, high disk use | Detect and report at `sync` time (§8.5) |
| Harness residue outside the store (§9.4) | Revocation is incomplete for `receives = "all"` profiles | Out of scope here. Tracked in `harness.md`; policy decision belongs to `SECURITY-MODEL.md` |
