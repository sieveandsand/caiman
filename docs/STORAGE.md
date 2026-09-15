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
| G-9 | Keep an off-machine copy, and let the same store be reachable from more than one machine |

## 4. Non-Goals

These are capabilities the store deliberately does not provide. Each was required
by an earlier design and became unnecessary when S-18 removed the retrieval
service.

| Not provided | Rationale |
|---|---|
| Query, search, or ranking over content | Retrieval happens with `grep` over the materialized documents (S-04, S-18) |
| Partial fetch within an object | Fetch whole files into the local store; agents can read selected ranges locally (§6.3) |
| Concurrent-writer safety | Single engineer, single machine. Ingest is serialized by the CLI |
| High throughput | Volume is hundreds of documents, not millions |
| Authentication | POSIX permissions only. §12.3 states the threshold at which this becomes insufficient |
| Deleting unreachable objects | Garbage collection is specified (§8.5) but not implemented for the MVP; disk is cheaper than the risk of breaking a pin |

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
| R-11 | The store remote is private; a non-private remote is a hard error at push | S-16, I-1 |
| R-12 | Nothing is pushed to a remote until its labels have been reviewed | §9.5 |
| R-13 | File modes are restored after a clone or pull — `0444` on blobs, `0700` on compartment directories. Git carries neither | I-9, S-16 |
| R-14 | A pull that would change an existing blob's content is an error, not a merge | R-1 |

### 5.2 Environmental constraints

| Constraint | Consequence for the design |
|---|---|
| Primary platform is macOS on APFS | Use `clonefile(2)` as the preferred link mechanism (§7.3) |
| Worktrees may live on a different volume from the store | Must fall back to copying; cross-volume clones and hardlinks are not possible |
| Separate APFS volumes within one container are distinct filesystems | Volume co-location cannot be assumed from "same disk" |
| Markdown documents are large — a 2,000-page reference manual is roughly 20 MB | Keep whole files; prefer CoW/link-based materialization to per-session copying |
| The user supplies already-converted markdown | Source and converter provenance are optional; compute the Markdown digest regardless (S-26) |
| Session harnesses persist plaintext copies of files the agent reads, outside the store | Re-materialization does not fully revoke access; see §9.6 |

---

## 6. Design

### 6.1 Object model

The store holds three object kinds. Two are immutable and named by digest; one is
mutable and named by a path.

| Object | Mutable | Named by | Contains |
|---|---|---|---|
| **Blob** | No | SHA-256 of its bytes | One unchanged Markdown document |
| **Manifest** | No | SHA-256 of its serialized JSON | One version of a document, board, or project: its metadata and its references to other objects |
| **Ref** | Yes | A human-readable path | A single line holding one manifest digest |

The two-level split between blob and manifest is the central structural decision,
and it is worth stating precisely because the terms are easy to conflate.

- A **blob is one file.** The entire input manual is a blob. Its digest covers
  the exact input bytes.
- A **manifest is one version of one document.** "NXP S32K344 reference manual,
  rev-4" is a manifest. It references one content blob, with its materialized
  filename, and carries all metadata: issuer, version, applicable
  silicon revisions, access labels, provenance.

```
manifest sha256:9f3c22de…71        nxp/s32k344 reference-manual rev-4
  └── document.md      → blob sha256:3f9c1a8e…b2 (complete unchanged manual)
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

### 6.3 One document, one content blob

S-25 registers a single Markdown file unchanged. A document manifest references
exactly one content blob, materialized as `document.md`. There is no splitting,
chunk entity, generated map, or stored navigation index.

A large manual need not be read whole: the agent searches its identifiers and
headings, then reads a bounded range around the result. Usable source headings
are required at admission (`ARCHITECTURE.md` §6.4.2).

Identical whole documents deduplicate within a compartment. A changed revision
has a new whole-file blob even if only a paragraph changed; chapter-level
storage savings are deliberately given up for a smaller registration pipeline.
CoW/link-based materialization still avoids per-session copies where supported.
Whole-file size and accumulated revisions must be evaluated against remote
limits (§6.6); ingest must not silently split files to fit them.

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
  "original_filename": "S32K3XXRM.md",
  "pipeline_version": "caiman-ingest/0.3",
  "ingested_at": "2026-08-21T09:14:22Z",
  "files": [
    { "path": "document.md", "sha256": "3f9c1a8e…b2", "size": 20000000 }
  ]
}
```

A requirement-structured document — a customer specification — differs in two
fields:

```json
  "structure": "requirement",
  "requirements": {
    "pattern": "^REQ-FLASH-\\d{4}$"
  },
```

| Field | Purpose |
|---|---|
| `structure` | All documents require usable headings. `requirement` additionally requires a valid declared ID pattern and matching IDs (I-5); no generated ID index |
| `labels` | Human-supplied access labels for the entire document. Included in the manifest digest, per R-4 |
| `source` | Optional original-source metadata: `sha256` and `pages`, each optional. No source filename is stored. The Markdown digest is separate and always computed |
| `converter` | Optional provenance: `name`, `version`, and `hosted`, each optional. Missing values mean unknown, including missing `hosted`; see `SECURITY-MODEL.md` §7.2 |
| `silicon_revisions` | Which mask revisions this document applies to. Distinct from document version and board version — see `ARCHITECTURE.md`, Data model |
| `files` | Exactly one entry in the MVP: `document.md`, with the digest and size of the unchanged input. No generated files |
| `original_filename` | Automatically captured Markdown input basename, the only filename retained. The source basename is assumed to carry over by convention, not verified. Does not determine labels or the materialized path |

The example above is complete without `source` or `converter`. When provided,
optional provenance may add these fields:

```json
{
  "source": { "sha256": "d4e1…", "pages": 2184 },
  "converter": { "name": "marker", "version": "1.8.2", "hosted": false }
}
```

Omit unknown subfields and omit an object if it has no supplied fields. Do not
store empty strings, null placeholders, or a default `hosted: false`. Validate
supplied values (e.g. a full SHA-256 digest, positive page count, boolean hosted
flag); the shortened digest above is illustrative. Neither an absent source
checksum nor an unknown converter blocks registration. A checksum, when supplied,
is asserted provenance; the original file is not required to verify it at ingest.
Matching filenames alone do not prove which source produced the Markdown.

The TUI's optional provenance fields map directly to these objects. The required
content checksum in `files[0].sha256` always identifies the unchanged Markdown,
independently of whether provenance was supplied (S-26).

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

Draft document entries accept a `ref` or `digest`, with an optional
`compartment`. The implemented authoring contract is in `AUTHORING.md`. Review
resolves and stores an explicit digest and storage compartment for every entry.
A supplied `ref` is retained; digest-only selectors need not invent one. The digest is
authoritative and is what resolution uses. The ref is retained for diagnostics —
it lets a human read a manifest and understand it without dereferencing every
digest — and must never be used to resolve at consumption time (I-4).

Board manifests live under public; project manifests live under their declared
compartments. Configuration refs use `refs/boards/<name>/<version>` or
`refs/projects/<name>/<version>`. Components are reversibly percent-encoded,
including special handling of dot-only labels. Version semantics remain opaque.
Registering a configuration verifies all pinned manifests and document blobs
before writing. There is no reliance on current ref targets after review.
Catalog and version listings omit entries that require additional compartments;
explicit reads still deny access, and corruption is reported rather than hidden.

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
└── config.toml         store_root, cache_root, link strategy, compartments
```

| Setting | Default | Notes |
|---|---|---|
| `store_root` | `~/.local/share/caiman/store` | The only path that requires backup |
| `cache_root` | `~/.cache/caiman` | Unused while the store is local (§7.4) |
| `link_strategy` | `auto` | `auto` selects per §7.3; may be forced to `copy` for debugging |

The roots are separated by lifetime rather than by content type:

| Root | Holds | Lifetime | Backup |
|---|---|---|---|
| `~/.config/caiman/` | `config.toml` | Hand-edited, rarely changes | With dotfiles |
| `~/.local/share/caiman/` | The store | Append-only, grows | Required |
| `~/.local/state/caiman/` | Audit logs | Append-only, grows | If you need the record |
| `~/.cache/caiman/` | Fetched blobs | Derived | Never; safe to delete at any time |

The state root holds the materialization and access logs
(`SECURITY-MODEL.md` §9.4). It is deliberately not inside the store: the logs are
not content-addressed, they are not versioned, and they must never be committed —
git's permanence (§9.5) would make an accidental inclusion of a log naming a
customer's specifications irreversible.

Because the store is immutable and content-addressed, backup can be a plain
`rsync`. A second machine is a copy rather than a synchronization problem: two
stores can be unioned by copying objects, and the only conflict possible is a ref
pointing to two different digests, which is visible as a one-line difference.

### 6.6 Git-backed remote

The store is kept off-machine in git: **one private repository containing the
whole store**, compartments as directories inside it.

```
caiman-store/              one private repository
├── public/
├── oem-alpha/
├── oem-beta/
└── .gitattributes
```

#### 6.6.1 Why one repository

An earlier version of this design used one repository per compartment. Separate
repositories buy exactly one thing: host-enforced access control *between*
compartments, which matters when a person should see one and not another.

There is no such person. Compartments here are one engineer holding several
counterparties' secrets, not multi-tenancy. The separation that does the work is
differential materialization (`SECURITY-MODEL.md` §5.2) and local file modes,
neither of which needs a repository boundary.

Two facts settle it:

**Every store repository is private regardless.** `public` in this design means
*visible to every session*, not publishable. Vendor reference manuals are under
click-through agreements and redistributing them is a licensing violation
(`VISION.md` §8). So a per-compartment boundary would be separating the engineer
from themselves.

**GitHub has no per-directory read permission.** Within git the choice is
repository-level or nothing, so there is no middle option to reach for.

The cost of the earlier design was recurring and real: per customer, create a
repository, set its visibility, wire a remote, and clone it on every machine. One
repository makes a new compartment a `mkdir`.

#### 6.6.2 Splitting later, when a real boundary appears

Because git here is transport and backup — the content-addressed tree is the
source of truth (§6.1) — splitting is cheap:

1. Create a new private repository.
2. Copy `store/<compartment>/` into it and commit.
3. Point that compartment's remote at it in `config.toml`.
4. Remove the directory from the original repository.

You lose commit history for that compartment, which is tamper evidence rather
than correctness, and nothing else. No history rewriting is involved because you
are not trying to erase anything — you are relocating a subtree whose contents
are already immutable.

This is the test that makes the simple default safe: **if the migration is cheap,
do not build it early.**

Note step 4 does not remove the directory from the original repository's
*history*, which is fine for a split (the data is not being revoked, only
relocated) and not fine for a mislabel (§9.5).

The configuration therefore supports a per-compartment remote override, even
though the default is one remote for everything:

```toml
[remote]
default = "git@github.com:me/caiman-store.git"

# [remote.overrides]
# oem-gamma = "git@github.com:me/caiman-store-gamma.git"
```

An override is also how a counterparty whose agreement forbids third-party
storage is handled — that compartment gets a self-hosted remote, or none (§9.4).

#### 6.6.3 What git adds

| Property | How |
|---|---|
| Off-machine copy | `git push` |
| Multi-machine access | `git clone` on a second machine |
| Authentication | Repository permissions. Weaker than per-compartment, and sufficient while there is one user |
| Tamper evidence | Commit history records what was added, when |
| Conflict-free concurrent ingest | See below |

**Merge conflicts are confined to `refs/`.** Blobs and manifests are named by
content, so two machines ingesting the same document produce the same filename
with the same bytes and git sees no conflict. The only file that can genuinely
diverge is a ref, where two machines repointed the same name to different
digests. That surfaces as a one-line text conflict naming both digests, which a
human resolves by deciding which conversion wins. This follows from §6.2 keeping
mutable state in one directory, and it is the main reason the layout tolerates a
distributed store at all.

#### 6.6.4 What git does not do

**Git does not carry file modes.** Only the executable bit is tracked, so the
`0444` on blobs (R-6) is lost on clone and must be reapplied (R-13). The `0700`
on compartment directories is likewise not carried — with a single repository
this matters more than before, because a fresh clone produces every compartment
at default permissions until Caiman fixes them.

**Git history is permanent.** The significant cost, analyzed in §9.5.

**Git does not compress this store usefully.** Blobs are immutable and never
modified, so delta compression finds nothing. Repository size is the sum of every
blob ever committed and only grows (§10).

**Git is not the source of truth for immutability.** The content-addressed layout
is. Do not use branches or tags to express document, board, or project versions —
that is the model S-02 rejected, and the version axes in `ARCHITECTURE.md` §7.1
do not map onto one HEAD.

#### 6.6.5 Size limits

| Limit | Value | Consequence |
|---|---|---|
| GitHub per-file hard block | 100 MB | A whole manual may exceed this limit. Report it before push; use a supported alternative remote/storage arrangement rather than splitting at ingest |
| GitHub per-file warning | 50 MB | Expect warnings on large whole-document blobs |
| GitHub repository soft limit | ~1 GB recommended; 5 GB draws attention | One repository holds every compartment, so this arrives sooner than it would have with a split store |

Git LFS is the standard answer and is **not adopted yet** — see §13.1.

---

## 7. Data Flows

### 7.1 Ingest

Input: one UTF-8 Markdown file plus the reviewed TUI manifest draft, with
explicit document labels and optional source/converter provenance.
Output: one immutable document version manifest reachable by a ref.

1. Validate metadata and explicit labels. Validate usable headings for every
   document and the declared ID pattern for `requirement` documents, following
   `ARCHITECTURE.md` §6.4.2. Reject failures without registering a version.
2. Compute the digest of the exact input bytes and prepare the registration
   summary for the TUI review step (§6.4.3 of `ARCHITECTURE.md`). No transformation,
   generated map, or AI call occurs.
3. After the engineer submits the TUI review, write the single unchanged content
   blob to `blobs/sha256/<aa>/<digest>` in the target compartment, mode `0444`.
   An existing identical blob is a no-op.
4. `fsync` the blob.
5. Serialize and write the manifest canonically, with exactly one `files` entry
   named `document.md`, the original filename, and whole-document metadata.
6. `fsync` the manifest.
7. Write or repoint `refs/documents/<issuer>/<part>/<doc_type>/<version>`.

Validate, hash, and store the same byte snapshot. If the input changes during
registration, fail and ask the engineer to retry; do not publish a manifest for
bytes other than those validated and reviewed.

Blob → manifest → ref write ordering guarantees that every manifest reachable
from a ref has its content present. Failure recovery is specified in §8.1.

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

1. Read `--mode`. **If absent, fail and write nothing** (I-1, S-19). There is no
   default and no lookup — the human states the mode per session.
2. Compute the visible set: `open` yields public documents only; `sealed` yields
   every document the project version pins, across its compartments.
3. For each visible document, create its directory under `documents/` and link
   its single content blob as `document.md`.
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
    │   │   └── document.md            complete unchanged manual
    │   └── errata@rev-6/
    │       └── document.md
    ├── ti/tps65313/datasheet@2024-03/document.md
    └── oem-alpha/                      present only when --mode sealed
        ├── flash-spec@3.2/
        │   └── document.md
        └── deviations-falcon@2026-06/
            └── document.md
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
place. A workspace missing one document is indistinguishable, to an agent, from a
document that never contained it.

#### The document path is the citation

`documents/nxp/s32k344/reference-manual@rev-4/document.md` encodes issuer, part,
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

### 7.5 Initialization

`caiman init` prepares a store on a machine that does not have one.

1. Create `store_root` and the state and cache roots.
2. Write `config.toml` with default paths and, if `--remote` was given, the
   default remote.
3. Create `store/public/` with `blobs/`, `manifests/`, and `refs/`.
4. `git init` at `store_root`, and write `.gitattributes` marking `blobs/` and
   `manifests/` as binary so git attempts no line-ending conversion or textual
   merge on them.
5. Write `.gitignore` excluding nothing — the store is entirely tracked — but
   present so it is obvious that omission was deliberate.

Adding a compartment is now a local operation:

```
caiman compartment add oem-alpha
```

1. Create `store/oem-alpha/` at mode `0700` with the three subdirectories.
2. Record it in `config.toml`.

No repository to create, no visibility to choose, no remote to wire. A
compartment with an agreement forbidding third-party storage takes
`--remote <url>` or `--no-remote` to override the default (§6.6.2).

**`caiman init` does not create the GitHub repository.** Creating it is a
decision about visibility, and a store repository accidentally created public
exposes every compartment at once. Caiman prints the command or URL and verifies
on first push that the remote is private. A public remote is a hard error, never
a warning.

Joining an existing store on a second machine:

```
caiman clone --remote git@github.com:me/caiman-store.git
```

This clones, then restores file modes — `0444` on blobs, `0700` on compartment
directories (R-13). The mode restoration is not cosmetic: a fresh clone has every
compartment world-readable until it runs.

### 7.6 Push and pull

Deliberately separate verbs from `caiman sync`, which materializes a session
workspace. These move the store; `sync` builds a workspace from it.

```
caiman push [--compartment NAME]   # default: the whole store, one commit
caiman pull
```

With a single repository these are ordinary `git push` and `git pull` with
checks around them. `--compartment` restricts the *review output*, not the push —
git pushes commits, not directories — and exists so that a review of one
customer's additions is readable. A compartment with an override remote (§6.6.2)
is pushed separately and does appear as its own operation.

**Push** is not automatic on ingest (R-12). Ingest writes locally; push is a
separate, deliberate act. The reason is §9.5: a mislabeled document that has only
been committed locally can be removed with `git reset`. Once pushed, it is in the
remote's history. Putting a human step between the two makes the cheap fix
available in the window where mistakes are actually found.

Push therefore:

1. Verifies the remote is private. Hard error if not — one repository holds every
   compartment, so this check protects all of them at once.
2. Reports what would be pushed: documents by name and version, and the
   compartment each lands in. This is the label-review step.
3. Commits anything uncommitted, with a message naming the added refs.
4. Pushes.

**Pull** fetches, then:

1. **Restores file modes before anything else** (R-13). On a first clone every
   compartment arrives world-readable.
2. **Rejects any change to an existing blob or manifest** (R-14). Content
   addressing means the same path always holds the same bytes, so a differing
   blob at a known digest is corruption or tampering, not a merge. Fail and name
   the object.
3. Merges `refs/`. Conflicts are possible here and only here (§6.6.3); a conflict
   lists both digests and requires a human decision.
4. Verifies digests of newly fetched objects (§8.2).

---

## 8. Failure Handling and Edge Cases

### 8.1 Interrupted ingest

The write order in §7.1 bounds what a crash can leave behind.

| Interrupted after | State | Consequence | Recovery |
|---|---|---|---|
| Content blob written | Blob present, no manifest | Unreferenced blob consumes disk. No correctness impact — nothing references it | Re-run ingest; identical content is a no-op |
| Blob and manifest written | Manifest present, no ref | Object is complete but unreachable by name. Resolvable by digest | Re-run ingest; reuse complete objects and write the ref |
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
revocation is not achievable for any `sealed` session through this mechanism
alone. See `harness.md` §*Implications*, and
`SECURITY-MODEL.md` for whether the procedure there should be extended.

### 8.4 Git-specific failure modes

| Condition | Behavior | Rationale |
|---|---|---|
| Pull would change an existing blob or manifest | Fail; name the object | Content addressing means a path always holds the same bytes. A difference is corruption or tampering (R-14) |
| Ref conflict on pull | Fail; show both digests and both document identities | Two machines repointed the same name. A human decides which conversion wins; guessing would silently change what a name means |
| Store remote is not private | Hard error on push | Not a warning. One repository holds every compartment, so a public remote exposes all of them at once |
| File modes wrong after clone or pull | Reapply `0444` on blobs and `0700` on compartment directories, before any other step | Git carries neither (R-13). A writable blob breaks I-9; a world-readable compartment directory breaks the local half of S-16 |
| Push rejected because the remote moved ahead | Pull, resolve, push again | Normal git; no special handling |
| Repository approaching host size limits | Warn at push | §6.6. Growth is monotonic and the warning needs to arrive before the wall |

### 8.5 Reference counting and deletion

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

### 8.6 Cross-volume workspaces

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
| Compartment separation on the remote | None. One repository, one access boundary | **This is the deliberate gap.** Adequate while there is one user; §6.6.2 is the migration when that stops being true |

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

### 9.4 Hosting compartmented material on a third party

Putting a compartmented store on GitHub means a third party holds a customer's
specification. **This is a question for the agreement, not a technical detail**,
and it is the same class of question `ROADMAP.md` Phase 0 asks about model
providers — extended from processing to storage.

What the design does about it:

- **The default remote is one private repository**, so the decision is made once
  — but a **per-compartment remote override** (§6.6.2) exists precisely for the
  counterparty whose agreement forbids third-party storage. That compartment gets
  a self-hosted remote or `--no-remote`, and the rest of the store is unaffected.
- **Push verifies visibility** before sending anything (§7.6). With a single
  repository this check covers every compartment at once, which makes it more
  important rather than less.

What it does not do: decide whether the agreement permits it. Read the agreement.

### 9.5 Git history is permanent, and revocation is worse because of it

The reclassification procedure in `SECURITY-MODEL.md` §8 assumes the wrongly
placed object can be deleted. On a local filesystem that is `rm`. In git it is
not.

| Where the mistake is | Cost to fix |
|---|---|
| Working tree, uncommitted | Delete the file |
| Committed locally, not pushed | `git reset`; nothing left the machine |
| Pushed | History rewrite (`git filter-repo`), force push, every clone re-cloned or reset, and a request to the host to clear cached views. Forks and CI caches may retain it regardless |

Three consequences:

1. **Push is a separate, deliberate step with a label-review stage** (§7.6,
   R-12). The cheap fix only exists in the window before push, so the design puts
   a human there.
2. **A push of a compartmented document is effectively irreversible.** Treat it
   with the same care as sending the document to a third party, because it is
   that.
3. **`SECURITY-MODEL.md` §8 step 7 is incomplete for a pushed store** and says
   so. A compartment correction after push is an incident, not a chore.

This is a real cost of using git, accepted because the off-machine copy and the
real authentication are worth more at this stage. §13.1 records what would change
the answer.

### 9.6 What this design does not protect against

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
Two boards sharing a reference manual store it once within a compartment.
Different revisions store distinct whole-file blobs; unchanged chapters are not
deduplicated separately. Sessions consume essentially no additional
space unless materialization falls back to copying (§8.6).

**Resolution** reads one ref and a handful of manifests — tens of small JSON
files. At the stated volume (tens of boards, tens of projects, hundreds of
documents) there is no reason to build an index, which is the substance of the
D-10 decision.

**Ingest** is bounded by hashing and writing the converted markdown, so it is I/O
bound and proportional to document size. It runs once per document version.

**Repository size grows monotonically.** Blobs are immutable and never modified,
so git's delta compression finds nothing to compress, and deleting a blob from
the working tree does not reclaim space in history. Repository size is the sum of
every blob ever committed. At hundreds of documents this is workable; it is the
first thing to become uncomfortable, and §13.1 records Git LFS as the option.

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
| T-6 | Materialize a project in compartment A with `--mode sealed` | No file from compartment B appears in the workspace (R-9) |
| T-7 | Materialize with `--mode open` | No compartmented document is written, for any project |
| T-8 | Materialize with `--mode` omitted | Nothing is written at all; no default applied (I-1) |
| T-9 | Ingest a document with neither `public` nor a compartment | Materialized nowhere |
| T-10 | Materialize where one blob is unreadable | `sync` fails, names the file, leaves no partial workspace (R-8) |
| T-11 | Walk a materialized document tree for symlinked directories | None exist (R-7) |
| T-12 | Check modes of every materialized file | All `0444` (R-6) |
| T-13 | Resolve a project name with no version | Returns the version list; does not resolve (R-3) |
| T-14 | Resolve a project version whose board ref was repointed after pinning | Resolves the originally pinned board digest (I-4) |
| T-15 | Ingest a `requirement` document with headings but no matching requirement IDs | Rejected at ingest (I-5) |
| T-16 | Register and materialize Markdown with CRLF, tables, and code fences | Input and output bytes match exactly; one content blob and no generated map (S-25) |

T-14 is the test that directly covers §2.2, and it should exist before the store
is considered done.

---

## 12. Alternatives Considered

### 12.1 Name-addressed directories

Store documents under readable paths:
`store/documents/nxp/s32k344/reference-manual/rev-4/document.md`

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

**That trigger has since been partly met, and git answered it instead.** The
condition was compartment separation needing real authentication rather than
POSIX permissions. Per-compartment git repositories with host-enforced access
(§6.6) provide exactly that, at the cost of a remote rather than a service.

What a registry would still add over git: immutability enforced by the system
rather than by this design's conventions, retention as configuration rather than
discipline, and **deletion that actually deletes** — which §9.5 shows git cannot
do. The revised trigger:

> Move to a registry when history permanence becomes the binding constraint —
> when compartment corrections happen often enough that irreversible pushes are a
> recurring incident, or when a counterparty requires demonstrable deletion.

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

**Document granularity was resolved by S-25 (2026-09-15).** Each document is one
unchanged Markdown blob with document-level labels. There are no stored chunks
or generated maps. A future retrieval design can derive its own index without
changing the registered source artifact.

### 13.2 Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Reclassification cascades into new board and project versions (§8.3) | A correction is more expensive than an edit, and may be avoided for that reason | Accept for the MVP. Make the CLI perform the cascade in one command so the cost is machine time, not human decision |
| Garbage collection implemented naively later | Permanently broken pins (§8.5) | Do not implement GC for the MVP. If added, drive it from the transitive walk, never from refs alone |
| Canonical serialization drifts between versions | Same logical manifest yields two digests; deduplication and comparison silently degrade | T-3, and treat the serializer as a versioned interface tied to `schema` |
| Workspace on a different volume | Silent loss of CoW benefit; slow startup, high disk use | Detect and report at `sync` time (§8.6) |
| Harness residue outside the store (§9.6) | Revocation is incomplete for `sealed` sessions | Out of scope here. Tracked in `harness.md`; policy decision belongs to `SECURITY-MODEL.md` |
| The store repository created public by mistake | **Every** customer's specifications published, irreversibly. One repository concentrates this risk relative to a split store | Push verifies visibility before sending anything (§7.6); `caiman init` deliberately does not create the repository, so visibility stays an explicit human act. This is the accepted cost of §6.6.1 |
| A mislabeled document pushed before the error is found | History rewrite, or permanent residue (§9.5) | Label review sits between ingest and push (R-12). This is the whole reason push is not automatic |
| Repository growth outruns host limits | Pushes start failing | Warn at push (§8.4); Git LFS is the option (§13.1) |
| Agreement forbids third-party storage of a customer's material | That compartment cannot use the default remote | Per-compartment remote overrides (§6.6.2); the compartment gets a self-hosted remote or none |
| A collaborator needs one compartment and not others | The single-repository model no longer holds | Split that compartment out (§6.6.2). Cheap by construction: copy a directory into a new repository, repoint the remote. History is lost for that compartment; content is not |
| A fresh clone leaves compartments world-readable until modes are restored | A window where local separation does not hold | Mode restoration runs before any other step of `clone` and `pull` (§7.6). Do not reorder it |
