# Pods

A pod is a local folder of Caiman documents, collections, boards, and projects.
It can optionally be shared through one Git repository. Caiman has no access
labels, authorized-compartment lists, or application membership checks. Local
files are available through the filesystem; the Git host controls remote reads
and writes. `public` is the permanent default pod, with no repository-visibility meaning.
It is available from initialization and cannot be replaced or removed. Switching
the current gallery tab or choosing a destination pod never changes the default.

This design supersedes the compartment/access rules in the older storage,
security, and architecture design sections. Those sections remain historical
context for superseded storage/transport designs. The accepted workspace
materialization and switching workflow is [Session context](CONTAINER-CONTEXT.md)
(S-39), using this pod model. It is not yet implemented. Pod Git sync is separate
from session materialization.

## Local layout and identity

```text
store/
  .pods.json                   legacy preference (ignored)
  public/
    pod.json                   schema, stable id, display name
    blobs/sha256/<prefix>/<digest>
    manifests/sha256/<prefix>/<digest>
    refs/documents/...
    refs/document-heads/...     current complete manifest per stable document ID
    refs/collections/...
    refs/boards/...
    refs/projects/...
  alpha/
    pod.json
    blobs/...
    manifests/...
    refs/...
    .gitattributes             created when Git is connected
    .git/                      optional; this folder is the repository
```

Pods are discovered from headers or existing store folders containing refs.
Browsing an empty store shows a virtual `public` tab without writing files.
Creation or the first save creates the public folder/header as well as the
chosen destination. Read-only browsing keeps initialization virtual. IDs initially
use the chosen pod slug; retain the ID when renaming a folder or changing its display
name. IDs must be unique within a store; cloning a second copy of an existing
ID is rejected. A clone may have a different local folder name. No paths or
credentials are embedded in document manifests.

The current implementation keeps pods beneath the configured store root. The
root itself must not be shared as one Git repository. Documents retain exact
input bytes, content hashes, canonical manifest JSON, and immutable snapshots.
A document's location lives in its catalog record and registration context,
not in its manifest. Boards, projects, and collections likewise have one owning
pod. A draft may include `pod` to choose its destination; preparation removes it
from the stored manifest.

## Document metadata

Registration accepts one readable file of any format without content validation.
Bytes are preserved unchanged; new manifest file paths use `document` plus the
input’s final extension (or `document` for extensionless inputs). Old paths stay
unchanged. Registration does not convert files or make binary content searchable.

Documents no longer have `structure` or `requirements` fields. New ingestion
and metadata edits reject them as unknown fields; there is no requirement-ID
pattern control or validation. Existing snapshots containing those fields are
adapted in memory, preserving original stored bytes and digest pins. Unchanged
edits preserve the original digest. All metadata edits create complete manifest
revisions. Old references follow the current approved metadata while their bodies
stay fixed; no consumer snapshots are rewritten. Document metadata never gates
board/part attachment. See [DOCUMENT-METADATA.md](DOCUMENT-METADATA.md).

## References

Board pins use `{ "pod": "alpha", "digest": "sha256:…" }` with name/version.
Document references use `{ "pod": "alpha", "document": "stable-id", "blob": "sha256:…" }`.
Named refs or manifest digests are resolved at authoring time.
An artifact may reference its own pod or `public` only. Here “current pod” means
that artifact's owning/destination pod, not a remembered global preference.
`public` artifacts reference only `public`; two distinct non-public pods cannot
reference each other. This applies to board and project pins, assembly and part
documents, project and feature documents, live project collection references, and collection
members. Both the collection edge and its current member edges are checked. Project board
dependencies obey the same rule recursively, so a public board cannot introduce
a dependency on another non-public pod.

Unqualified authoring selectors search only the owning pod and public. An
ambiguous name requires an explicit pod; Caiman never substitutes a different
version. Validation runs during preparation and again at save time. Historical
snapshots remain byte-for-byte unchanged and visible in catalogs, but incompatible
references cannot be reused when preparing a configuration or resolving collection
members. Local availability alone does not make a reference valid.

Catalogs can show projects and collections whose dependencies are unavailable.
Preparing or reconstructing their complete contents fails with a missing
object/pod error. Sharing a project never copies referenced objects into its
repository. Teammates must clone each dependency pod separately. Project and
collection metadata, including dependency identities, is visible to everyone
who can read their owning repository.

## UI and commands

Documents, Projects, and Boards have one tab per pod, including empty pods.
New records use the active tab. Press `/` anywhere in a gallery for the next pod, or `[` and `]` for the
previous and next pods. On the tab bar, use Left/Right or `h` / `l` to switch and `j` to enter the
cards. Tab and Shift+Tab move between controls. Forms show a single Pod field. The Pods page offers local
creation, cloning, Git connection, sync, disconnection, and removal.
New pod asks for a pod name and an optional Git remote. Back cancels; Create
creates the pod and returns to the pod list without a review step. Supplying a
remote enables Git locally; use Sync to commit and share the pod.
Clone pod asks for a local pod name and a repository URL. Back cancels; Clone
clones the pod and returns to the pod list without a review step.
All local pods are available without entering authorization names.

The Pods page isolates Git errors to the affected pod. The default is always
the stable pod ID `public`, even after its folder or display name changes. Legacy
`.pods.json` default preferences are ignored. Attempts to change the default fail.

Git working-tree status and publication status are separate. A clean working
tree can still have unpushed commits. The list reports the last sync failure,
unpushed commits relative to the last verified remote commit, and **Published at
last check** after a successful clone or sync. **Publication unconfirmed** means
there is no recorded state for that remote yet. Status refresh is local-only;
use Sync to check for newer remote changes. Publication metadata stays in the
pod's local Git configuration and is not shared with teammates.

```bash
caiman pod create alpha
caiman pod connect alpha git@example.com:team/alpha.git
caiman pod sync alpha
caiman pod clone team-alpha git@example.com:team/alpha.git
caiman pod list
caiman documents --pod alpha
caiman pod disconnect alpha
```

Run the clone example in a different store or on a teammate's machine. Each
command accepts `--store PATH`. SSH, HTTPS with existing Git credentials, and
absolute local repository paths are supported. The user supplies the remote;
Caiman does not create hosted repositories or change their permissions.

Saving never commits or pushes. Connect enables Git in the existing pod folder;
Sync commits pending changes, fetches `caiman-store`, merges, then pushes without
force. A local Git pod without a remote can still commit through Sync. Sync
validates allowed paths, object digests, headers, and transport attributes.
Git hooks and downloaded scripts are not executed by this transport.

Concurrent additions merge using Git. Conflicting named refs stop sync: the
local commit and fetched remote history are retained, and the attempted merge
is aborted. Resolve with Git in the pod folder, then retry Sync. A rejected
push or network failure retains local work. Publication is per repository, not
an atomic multi-pod transaction; sync dependency pods before their consumers.

Disconnection removes the remote, preserving local files and history. Removing
remote permission cannot revoke an existing clone. Git LFS, partial clones,
remote repository provisioning, and an in-app merge editor are not implemented.

## Existing data

Existing compartment folders are discovered as pods. Read adapters translate
legacy `compartment` routes and access labels in memory; stored object bytes
and digests remain unchanged. Invalid multi-compartment document labels are
rejected instead of guessing a destination. Legacy projects replicated across
folders remain visible in each location; editing uses the chosen record's pod.
Importing a legacy multi-compartment project draft requires an explicit owning
pod. Older authoring authorization preferences are ignored.

Old `.repositories/` mirrors and `.repositories.json` are retained but are not
used as the data folder. Connect Git on the real pod folder. Cloning an old repository with a valid `store.json` header creates `pod.json`
in the local clone, retaining the same ID and all historical object bytes. The
header migration reaches the remote only on the next explicit Sync. Existing
local folders are adapted without contacting a remote.

## Verification

`tests/test_pods.py` covers local availability, one owner, cross-pod dependencies,
legacy byte preservation, renamed clone folders, two-writer Git sync, conflicts,
failed publication, binary document round-trips, document tabs, and the fixed
public default. `tests/test_pod_policy.py` covers reference boundaries and default
protection.
`tests/test_document_metadata_retirement.py` covers retired-field rejection and
legacy snapshot compatibility, including cross-pod pins after metadata edits. Repository tests cover
invalid URLs, unsafe paths, remote format admission, review invalidation, and
credential handling. Existing document/configuration tests continue to cover
hash integrity, immutable pins, applicability, and review/save behavior.

## Removing a pod

**Remove pod** checks current boards, projects, and collections in the remaining
pods. Current means every named version, not a guessed latest version. A board
snapshot pinned by a current project is still current for dependency checks,
even if its own named ref is gone. References entirely within the removed pod
leave with it. Unreferenced historical snapshots do not block removal.
Unreadable catalogs or pinned boards block removal because the check is incomplete.
The check runs again under the store lock when applying the reviewed operation.

Removal moves the folder, including all content and Git history, into
`store/.removed-pods/<stable-id>/<unique-id>/`; no files or remote repositories
are deleted. Historical snapshots remain unchanged but may have unavailable
dependencies. Move the archived folder back under the store root to restore it.
The public pod cannot be removed. Removing another pod never changes the default.
`caiman pod remove <pod>` uses the same checks;
`caiman pod disconnect <pod>` continues to disconnect only Git.
