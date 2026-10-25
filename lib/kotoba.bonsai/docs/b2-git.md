# Git commands with Bonsai/Nekko B2 history

This adapter keeps Git's byte-exact objects under Bonsai raw CIDs and publishes
Nekko signed ref events. The authoritative object and event history is in B2.
Native Git implements commits, staging, line diffs, branches and file restores.
This is the existing CLJK/kbb operational runtime; no native Kotoba compiler
qualification is implied.

## Installation

Install `bin/git-kotoba-b2`, `bin/git-remote-kotoba-b2`,
`bin/git-remote-kotoba-b2-object` and `bin/kotoba-b2-git-adapter` on PATH as
symlinks to a retained checkout or a release directory exported with `git archive`
from the merged commit. Preserve `deps.edn`, `src/` and `bin/` together. Keep that
directory available: kbb resolves its pinned
dependencies from the executable's real path. The existing
`git-remote-kotoba` installation is independent and need not change.

Requires Git with partial-clone/promisor support, kbb and rclone. Resolve kbb's
dependencies once with `git kotoba-b2 help`. rclone uses an existing private
configuration and a bucket-scoped read/write/delete key; no credential enters
the URL, Git config or repository. Configuration creates a local, mode-0600
Nekko signing seed, never a B2 application key.

```sh
git kotoba-b2 configure BUCKET RCLONE_REMOTE /absolute/mount /absolute/b2-storage
git kotoba-b2 init project-name /absolute/mount/project-name
cd /absolute/mount/project-name
git add .
git commit -m 'Initial snapshot'
git push -u origin main
```

Git's control directory is on APFS under
`~/Library/Application Support/Kotoba/b2-git/repositories/`. Only the small
`.git` pointer lives in the mounted working directory. This preserves Git's
required empty control directories after GC/remount and supplies normal local
locking for the index and refs. Existing repositories are refused by `init`;
this command does not migrate a checkout or change global Git defaults.

The profile is restricted to one configured bucket/rclone remote. For another
installation set absolute `KOTOBA_B2_STATE` and `KOTOBA_B2_CACHE` roots explicitly.
The signing seed is authoritative local state: preserve it to keep write access.
The B2 transport cache can be rebuilt. Never store the seed on the mount.

## Normal Git workflow

```sh
git status
git diff
git add src/example.js
git commit -m 'Change example'
git push
git log --oneline
git diff HEAD^ HEAD -- src/example.js
git restore --source=HEAD^ -- src/example.js
git restore --source=HEAD -- src/example.js
git fetch origin
git kotoba-b2 status
```

`git commit` creates local history, and `git push` makes it durable in B2.
Publication occurs in a pre-receive hook and completes its B2 readback before
native Git acknowledges success. A failed upload rejects the push. A connection
or local ref failure after durable publication can still leave a successful B2
publication with a failed client acknowledgement; fetch to discover the result.
The private transport repository pins its own `core.hooksPath`. Client `git -c`
configuration and object/worktree environment are cleared before running its
Git services, so client/global hook selection cannot bypass B2 publication.

Create another working directory using:

```sh
git kotoba-b2 clone kotoba-b2://BUCKET/GENESIS-CID /absolute/new-working-directory
```

This is a native `git clone --filter=blob:none --separate-git-dir ...`.
The URL is the `origin` printed by `init` or `git remote get-url origin`.
An equivalent native clone command with those options is also supported.
For mounted working copies, always use a separate APFS Git control directory.
An unqualified `git clone URL mount/path` would put `.git` on the mount again.

Commit/tree/tag metadata is materialized with Bonsai's pack writer;
blob contents are hydrated when native Git needs them. A normal checkout reads
the current version of its files. Comparing/restoring an older file fetches its
older blob. Git's own object cache retains objects it has already read; this
version does not impose an eviction limit on the client `.git/objects` store.
Directory scans, builds and content searches read the files they actually use.

## Cache eviction

```sh
cd /an/APFS/directory/outside/the/mount
git kotoba-b2 evict --repo /absolute/mount/project-name src/example.js assets/large.dat
cd /absolute/mount/project-name
git kotoba-b2 evict --history-cache
```

File eviction checks that the selected files are tracked and clean and that
HEAD is published. It delegates to the configured `b2-storage` controller,
which waits for uploads, normally unmounts, refuses dirty/busy state, removes
only the selected clean VFS cache and verifies unchanged cloud file metadata.
It briefly interrupts the whole mount. A shell/process whose working directory
is in the mount holds it busy. Use `--repo` from outside the mount, as above;
`git -C mount/path ...` also leaves Git's parent process in the mount and cannot
complete a normal unmount. Close other shells/processes holding the mount.
Pending/untracked/modified files are refused. File deletion and cache eviction
are different operations.

`--history-cache` removes only this remote's disposable materialized bare repo,
downloaded CID blocks and cached publication events under the transport cache.
It preserves the workspace, client Git control directory, signing seed and B2
history. The next fetch rebuilds metadata and obtains required blobs lazily.
It does not evict Git's own client object cache.

## Storage, authority and current limits

- B2 prefix: `.kotoba/git/GENESIS-CID/{blocks,events}`. The genesis identity CID
  is part of the remote URL; changes to its contents fail CID verification.
- Git objects are exact `<type> <size>\0<body>` bytes. Both their Git SHA-1 OID
  and raw CID are verified before materialization. Metadata uses canonical
  DAG-CBOR. New object transfers and missing-object requests use batched B2 API
  copies with bounded concurrency. The backend never stores a live `.git` DB.
- Git 2.50.1 can leave receive-pack waiting on a sideband fd when an existing
  ref target is in a server-side promisor pack. Real server metadata therefore
  uses ordinary packs; disjoint, derived promise-tree packs declare missing
  blobs. These synthetic trees exist only in the disposable transport cache,
  never in the source manifest or B2 history. Clients use normal filtered-clone
  promisor packs and a direct OID/CID-verified missing-object helper.
  The helper sets `GIT_NO_LAZY_FETCH=0` only in its process tree: upload-pack
  serves our private generated cache, whose fixed B2 promisor helper verifies
  each requested object. This also lets native initial clone hydrate blobs
  before it reloads newly installed client promisor configuration.
- Every publication contains a complete OID/CID inventory and ref projection.
  It binds the previous publication and one signed Nekko event per changed ref.
  Signature, owner, sequence, old target, parent and closure are checked.
  Closure edges enforce commit/tree/blob/tag target types. Tree names and
  commit messages remain opaque bytes, including non-UTF-8 names/messages.
- Small persistent observed-head receipts refuse removal/rollback of history
  this installation has already verified. These remain with the signing state
  when disposable transport caches are evicted.
- Version 1 is single-owner. Local sessions serialize by remote; shared-cache
  lock files contain their owning PID. A crash leaves a lock for explicit
  process inspection rather than automatically breaking a live operation.
- Separate hosts can race between the final head check and publication. Both
  immutable tips remain in B2; subsequent reads refuse the fork. This is not a
  distributed compare-and-swap service. Automatic fork reconciliation and
  delegated multi-device writers are not implemented.
- Updates to existing branches must fast-forward. Existing tags cannot be
  overwritten. Snapshots/objects are append-only; automatic history GC and B2
  lifecycle changes are not included.
- This first inventory format is metadata proportional to stored history and
  uses bounded in-memory command buffers (256 MiB). It is not qualified for
  huge repositories. Filesystem metadata follows Git's normal tree model;
  empty untracked directories are not versioned.
- Symlink, hardlink, executable-mode and lock limitations of the existing NFS
  mount still apply to tools and working files. APFS Git control state does not
  change npm/Go/build filesystem requirements. Keep those build/dependency
  areas on APFS or materialize the active project there.
- B2 content is private to the bucket key but not encrypted by this client.
  Existing Bonsai private-repository encryption is a separate adapter.

The release's concrete command/readback evidence is recorded separately from
source implementation and any future GitHub merge/publication.

## Regression checks

Run `kbb -M:b2-test` from the repository root. It uses native Git and an isolated
local rclone protocol stub; it requires no B2 account, credentials or mount.
It covers hook overrides, durable push/ref deletion/recreation, failed uploads,
cold filtered clone, missing historical blobs, single-file restore, diff and
fsck, plus corrupt CIDs and invalid closure types. Live B2/VFS eviction remains
a separate operational check against the configured Mac mount. Local eviction
tests verify dirty-file refusal and retention of client history and signing state.
