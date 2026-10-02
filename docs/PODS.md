# Pods

A pod is a local folder of Caiman documents, collections, boards, and projects.
It can optionally be shared through one Git repository. Caiman has no access
labels, authorized-compartment lists, or application membership checks. Local
files are available through the filesystem; the Git host controls remote reads
and writes. `public` is the initial default pod name, with no special permission
or repository-visibility meaning.

This design supersedes the compartment/access rules in the older storage,
security, and architecture design sections. Those sections remain historical
context for features that have not been implemented, including workspace
materialization. Pod Git sync is separate from future workspace materialization.

## Local layout and identity

```text
store/
  .pods.json                   local default-pod preference
  public/
    pod.json                   schema, stable id, display name
    blobs/sha256/<prefix>/<digest>
    manifests/sha256/<prefix>/<digest>
    refs/documents/...
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
Creation or the first save creates the folder/header. IDs initially use the
chosen pod slug; retain the ID when renaming a folder or changing its display
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

## References

Pins use `{ "pod": "alpha", "digest": "sha256:…" }`. A document selector may
also carry its encoded `ref`; a board selector carries its name and version.
References can cross any locally available pods. An unqualified ambiguous name
requires an explicit pod; Caiman never substitutes a different version.

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
creation, cloning, Git connection, sync, default selection, and disconnection.
All local pods are available without entering authorization names.

The Pods page isolates Git errors to the affected pod. If the configured default
pod is missing, it still lists available pods and lets you select a replacement
with **Set default**; browsing does not rewrite the preference.

Git working-tree status and publication status are separate. A clean working
tree can still have unpushed commits. The list reports the last sync failure,
unpushed commits relative to the last verified remote commit, and **Published at
last check** after a successful clone or sync. **Publication unconfirmed** means
there is no recorded state for that remote yet. Status refresh is local-only;
use Sync to check for newer remote changes. Publication metadata stays in the
pod's local Git configuration and is not shared with teammates.

```bash
caiman pod create alpha
caiman pod default alpha
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
failed publication, document tabs, and default selection. Repository tests cover
invalid URLs, unsafe paths, remote format admission, review invalidation, and
credential handling. Existing document/configuration tests continue to cover
hash integrity, immutable pins, applicability, and review/save behavior.
