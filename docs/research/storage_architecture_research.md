# Shared storage research

Research date: 2026-09-24. This report supports the proposed
[team storage design](../proposals/TEAM-STORAGE.md). It does not change the
implemented storage format or settle earlier decisions by itself.

## Subsequent design decision

The initial research below evaluated multi-label documents and access domains.
**S-33 supersedes that assumption:** each document is explicitly public or has
exactly one compartment; each compartment is its own private repository. There
is no separate domain, intersection audience, or multi-repository document copy.
The user first clarified OR access, then removed the multi-label case entirely.
The current [team storage proposal](../proposals/TEAM-STORAGE.md) reflects that
simplification. The domain/intersection analysis below is retained as research
history, not the recommended implementation. Ingestion, registration and reads
now reject multi-compartment documents; source observations below describe the
pre-change implementation.

## Requirements that drive the recommendation

The user wants teammates to share documents and configurations, prefers Git
remotes with minimal infrastructure, and needs access to vary by customer and
project. The user also requested that the Merkle-tree discussion become part of
the design. These requirements favor a Git-backed content-addressed store with
separate repository access boundaries. A custom hosted API is a future option,
not the first delivery target.

The research uses primary documentation. Product capabilities below were checked
on the research date; host plans and limits need checking again at deployment.
Architectural conclusions are Caiman-specific inferences, not vendor promises.
No production workload, hosted repository, or cloud deployment was benchmarked.

## Existing implementation: what is reusable

| Evidence | Finding | Implication |
|---|---|---|
| `src/caiman/documents/models.py`, `canonical_json` | Sorted-key Python JSON encoded as UTF-8 | Preserve existing bytes; specify a cross-language format before adding native writers |
| `src/caiman/storage/store.py`, `_read_object` | SHA-256 checked against stored bytes | Reuse integrity verification after transport |
| `src/caiman/storage/store.py`, `register` | Copies a multi-compartment document into every named compartment | Unsafe as a template for repositories with different readers |
| `src/caiman/configurations/service.py`, `_pin` | Pins board and document manifest digests transitively | Existing project structure is already a Merkle DAG |
| `src/caiman/configurations/service.py`, `register` | Individual refs replaced atomically; no expected-old-value comparison | Shared publication needs conflict detection |
| `src/caiman/configurations/models.py` | Boards require public document selection | Confidential hardware needs a new schema and policy |
| `docs/STORAGE.md` §6.6 and `CLAUDE.md` I-3 | One repository versus per-compartment repositories | Existing conflict must be resolved before implementing transport |

These are observations about the current working tree, which already contained
uncommitted changes when the research began.

## Alternatives

| Approach | Useful properties | Missing work / cost | Recommendation |
|---|---|---|---|
| One private Git repository | Familiar authentication, history, offline clones | Every reader can obtain every stored object; cannot isolate customers with directory labels | Only for a genuinely single audience; not the team-wide default |
| Git repository per access domain | Host enforces coarse read boundaries; no new service | Repository setup, cross-repository dependencies, conflicts, persistent history | First backend |
| Git plus LFS | Retains Git workflow while moving large payloads out of Git | Separate payload availability, tooling, quotas, backup and hydration | Add only when measured file sizes require it |
| OCI registry | Digest-addressed artifacts and existing distribution tools | Caiman policy, config semantics, cross-repository closure, retention and ref conflicts remain | Plausible later transport, not a complete backend by itself |
| Object storage plus PostgreSQL and a small API | Central permissions, transactional catalog/refs, selective downloads | Operate a service, identity integration, database, backup and object lifecycle | Upgrade path if Git boundaries or scale become the constraint |
| SQLite behind one service | Small single-host deployment | Still needs a service and backups; one writer at a time | Viable small-service variant, not needed for Git-first delivery |
| IPFS / custom Merkle synchronization | Content identity, DAG traversal, reusable blocks | Private discovery, authorization, durable pinning and operations | Borrow the model; no peer network needed |
| Backup tool as primary store | Mature retention and encrypted backup patterns | Not a document/config publication and discovery API | Use for backup, not the application model |

## Findings and their design consequences

### 1. A Merkle identity does not provide storage or discovery

IPFS describes Merkle DAG nodes as content-addressed objects connected by hashes.
Its persistence documentation separately requires pinning to retain data. The
distinction is directly relevant: a Caiman project digest commits to a graph,
but a remote locator and retained objects are still required to retrieve it.
Sources: [Merkle DAGs](https://docs.ipfs.tech/concepts/merkle-dag/),
[persistence](https://docs.ipfs.tech/concepts/persistence/).

Recommendation: retain Caiman's whole-document objects and digest-linked
manifests. Add explicit context snapshots and retrieval descriptors; do not add
binary trees or chunking merely to get a root hash.

### 2. Git authorization is a repository boundary

GitHub assigns people and teams repository roles. A reader can obtain the
repository's content; Caiman cannot make a directory private by hiding it from
its own catalog. Deploy keys also need separate attention because removing a
person does not invalidate a key they possess.
Source: [repository roles](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization).

Recommendation: use one repository for each actual access domain. A requirement
for membership in both A and B means an intersection audience; granting the A
team and B team independently would grant their union. Provision the correct
intersection group explicitly. Do not replicate the document into A-only and
B-only repositories.

### 3. Git offers local atomicity, not a distributed publication transaction

Git push supports atomic updates of multiple refs on a supporting remote and
rejects ordinary non-fast-forward branch updates. These properties do not form
a transaction spanning separate repositories.
Source: [git-push](https://git-scm.com/docs/git-push).

Recommendation: publish dependencies first and the project root last. Keep
published objects append-only during normal operation. Caiman must compare
application reference generations when rebuilding a publication after another
writer advances the branch. It must never silently choose a winner.

### 4. Branch protection is useful but not application validation

GitHub branch protection can restrict pushes, force pushes and deletions; private
repository availability depends on the host's plan. A normal fast-forward commit
can still delete or misclassify application files unless separately validated.
Sources: [protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches),
[availability](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches).

Recommendation: trusted publishers plus client verification for the minimal
deployment. A receive hook can enforce application invariants on a host that
supports it. Post-push CI cannot prevent disclosure: the bytes have arrived by
the time it runs. Neither client checks nor branch protection prevent a trusted
writer from leaking material they can already read.

### 5. Git storage needs measurement, not the assumption that deltas cannot work

Git's packer can delta-compress distinct objects and uses heuristics including
path and size. Digest filenames may affect candidate selection; immutability
does not make delta compression impossible.
Source: [git-pack-objects](https://git-scm.com/docs/git-pack-objects).

GitHub currently warns above 50 MiB and blocks ordinary Git files above 100 MiB.
Its guidance favors repositories ideally below 1 GB and strongly recommends
below 5 GB. These are host-specific guidance and constraints, not Caiman's
format limits. Source: [large files](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github).

LFS collaborators need LFS payload support; a Git pointer alone is not the file.
Source: [Git Large File Storage collaboration](https://docs.github.com/en/repositories/working-with-files/managing-large-files/collaboration-with-git-large-file-storage).

Recommendation: benchmark representative synthetic manuals before transport
release. Start with plain Git; never silently introduce LFS or split a document.

### 6. OCI compatibility needs an adapter

OCI Distribution defines repository-scoped blob/manifest retrieval by digest.
OCI image manifests have prescribed fields and can carry non-container
artifacts. Caiman's custom JSON is not an OCI manifest simply because its
directory contains `blobs`, `manifests` and `refs`.
Sources: [Distribution 1.1.1](https://github.com/opencontainers/distribution-spec/blob/v1.1.1/spec.md),
[Image manifest 1.1.1](https://github.com/opencontainers/image-spec/blob/v1.1.1/manifest.md).

Recommendation: if a registry is adopted, wrap unchanged Caiman bytes as
artifacts and preserve the Caiman digest independently of the wrapper digest.
Prove registry retention of the dependency graph before replacing Git.

### 7. Object storage and SQL are a credible future backend

S3 documents strong read-after-write consistency and atomic updates to one key,
but no atomic update across keys. Conditional writes can reject an existing key
or a changed ETag. These do not atomically commit a database transaction and a
blob upload together. Sources: [consistency](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html),
[conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html).

ETags and multipart checksum representations must not substitute for Caiman's
SHA-256 of the complete plaintext bytes.
Source: [upload integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html).

PostgreSQL supports transaction isolation and locking suitable for concurrent
metadata updates; serializable failures require whole-transaction retries. Row
security has privileged-role bypasses, so it is not automatic protection merely
because a table has policies.
Sources: [transactions](https://www.postgresql.org/docs/current/transaction-iso.html),
[row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

SQLite is reasonable behind a small single-host service, but its docs caution
against many network clients sharing the database file and note the single
writer limitation. Source: [appropriate SQLite uses](https://www.sqlite.org/whentouse.html).

Recommendation: preserve a transport-independent object model. Do not deploy
these components for the first Git backend.

### 8. Deletion and durable history are different requirements

S3 Object Lock can prevent deletion for a retention period; this can conflict
with correcting accidental disclosure. Presigned URLs are bearer credentials
with a validity window. A future service cannot promise instantaneous revocation
while handing out independently valid download URLs.
Sources: [Object Lock](https://docs.aws.amazon.com/AmazonS3/latest/userguide/object-lock.html),
[presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html).

Restic documents ordering writes so data precedes snapshots. That is useful
precedent for Caiman's root-last publication protocol; it does not supply team
permissions or Caiman-specific graph validation.
Source: [restic repository design](https://github.com/restic/restic/blob/master/doc/design.rst).

Recommendation: distinguish retention, withdrawal from Caiman's catalog,
revocation of future repository access, and physical deletion. Git cannot
provide per-object revocation from authorized repository readers.

### 9. Canonical JSON needs a versioned contract

RFC 8785 specifies deterministic serialization, including number encoding and
UTF-16 property ordering, while preserving Unicode strings without normalization.
Python's `sort_keys=True` is not a general implementation of that standard.
Source: [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html).

Recommendation: preserve legacy manifest bytes and their digests. Use an explicit
RFC 8785 encoding contract for new schema versions, with golden vectors shared
between Python and any future native client. Sort only schema-defined sets;
precedence arrays and other ordered fields retain their declared order.

## Local experiments

The reproducible [experiment script](storage_git_experiment.py) ran successfully
on 2026-09-24 with Git 2.45.0. It uses temporary local bare repositories and
synthetic content only; it does not exercise a hosted provider or Caiman's future
transport implementation.

```bash
python3 docs/research/storage_git_experiment.py
```

| Experiment | Observed result |
|---|---|
| Two clones publish different changes from one base | First accepted; second non-fast-forward push rejected; first value retained |
| Store and retrieve digest-named document files through Git | Original bytes preserved |
| Repack two similar digest-named synthetic files, 637,830 total bytes | One delta-compressed blob observed with an expanded candidate window |
| Sort/deduplicate an illustrative document set before hashing | Reordering and duplicates preserve the root |
| Change one referenced document | Root changes |

The compression experiment demonstrates possibility, not default-packing savings
or production performance. The ASCII-only hashing example is intentionally not
a complete schema validator or RFC 8785 implementation. Repository permissions,
cross-repository publication and rollback recovery still need integration tests.

## What remains to validate

- Actual Git host, private-repository protection availability, identity model,
  and approved hosting locations.
- Real number of distinct access audiences; how often membership changes.
- Largest whole Markdown files, revision similarity, clone size and fetch time.
- Native-client canonicalization interoperability.
- Two-machine conflict handling and recovery at every publication boundary.
- Restoring a project and its external dependencies from independent backups.

The proposal specifies acceptance tests for these uncertainties. It does not
claim that a documented mechanism has already been implemented or validated.
