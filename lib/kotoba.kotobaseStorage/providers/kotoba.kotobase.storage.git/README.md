# kotobase-storage-git

**Git as the storage engine for a Datalog database** — not a place to keep a
dump of one. `kotobase.storage.git/open` returns a backend implementing
`kotobase.storage.core`'s `IBlockStore` + `IRefStore`, so `kotobase-engine`
transacts and queries against a bare git repository the same way it does
against PostgreSQL, SQLite, D1, S3/R2 or IPFS.

```clojure
(require '[kotobase.storage.git :as git] '[kotobase.engine :as engine])

(def db (engine/open {:storage (git/open {:path "/srv/kotobase/store.git"})
                      :encrypt-fn identity :decrypt-fn identity
                      :blind-fn pr-str :visible? (constantly true)}))

(engine/transact! db [["kawaraban" "kind" "news-medium"]
                      ["kawaraban" "storage" "git"]])

(engine/q db ["kawaraban" nil nil])
;; #{{:s "kawaraban" :p "kind" :o "news-medium"}
;;   {:s "kawaraban" :p "storage" :o "git"}}
```

And the database is, at the same time, an ordinary repository:

```console
$ git --git-dir=store.git log --oneline refs/kotobase/blocks
be812c4 kotobase blocks: 1 placement(s)
051495d kotobase blocks: 1 placement(s)

$ git --git-dir=store.git for-each-ref --format='%(refname) -> %(objecttype)'
refs/kotobase/blocks -> commit
refs/kotobase/db/main -> blob

$ git --git-dir=store.git ls-tree -r refs/kotobase/blocks | head -1
100644 blob 979323f…  blocks/ba/bbafyreicb24fw7rkthpfwgnevr7gbyzg32khqweqiwlxii4jdh7aqxh2sf4
```

## Why git fits this contract particularly well

`IRefStore/-compare-and-set-ref!` asks for exactly one hard thing: publish a new
head only if the current head is what you expected, atomically, and tell the
loser who won. That is `git update-ref <ref> <new> <old>` — a primitive git has
had since before the word "linearizable" was fashionable, implemented with a
lock file and an fsync.

This is worth stating plainly because kotobase's own
`docs/storage-architecture.md` notes the opposite case: IPNS offers no
general multi-writer compare-and-set, so the IPFS provider must declare a
single-writer profile and multi-writer deployments have to put a linearizable
ref service in front of it. Git needs no such caveat on a single filesystem.

The block half is equally natural. Git objects are immutable and keyed by their
content; a re-put of the same bytes is a no-op at the object layer without any
work from this provider.

## The part that is easy to get wrong

Git will delete your data. `git gc` prunes any object no ref can reach, so
`git hash-object -w` alone is *not* storage — it produces a loose object the
next gc is entitled to remove.

Every batch therefore also commits its blocks into a tree under
`refs/kotobase/blocks`, which is what makes them durable. There is a test that
runs `git gc --prune=now --aggressive` and then reads the block back, because
this distinction is the whole difference between using git as a database and
merely writing objects into one.

## Design notes

**Reachability.** Blocks live at `blocks/<fan>/<encoded-cid>` in a tree
committed to `refs/kotobase/blocks`. The two-character fan-out matters: git
rewrites trees whole, so one flat directory would make every write cost
O(all blocks).

**Name encoding is injective.** CIDs and ref names are opaque strings; git paths
and ref names are not. Safe names take a `b` prefix, unsafe ones a hex `x` form.
The prefixes are not decoration — without them the literal CID `x41` would
collide with the hex encoding of `A`, and one block would silently overwrite
another. There is a test for exactly that pair.

**Ref names.** `storage/scoped-ref` yields `(pr-str [:kotobase/ref tenant db])`,
which contains characters git forbids in refs. Everything outside `[A-Za-z0-9_-]`
is percent-encoded — including `.`, which disposes of the leading-dot and
`.lock` hazards without special cases.

**Concurrency.** Ref CAS is git's. Block publication is a read-modify-write of a
tree, so a lost race is retried rather than dropped; a test writes eight blocks
from eight threads and asserts all eight survive. Within one filesystem this is
safe. Across NFS, git's own locking caveats apply and this provider inherits
them rather than pretending to fix them.

**Committer identity** is supplied explicitly instead of read from git config. A
bare repository created by a service may have no `user.name`, and a storage
backend quietly adopting whoever ran it would make the audit trail say something
untrue.

## What it is good and bad at

Good: durable, replicable (`git push` / `git fetch` *are* the replication
protocol), fully auditable — every published head is a commit you can read with
`git log` — works offline, needs no server, and git is already installed
everywhere. A database whose entire storage layer is inspectable with ordinary
tools is a different operational posture from one behind a JDBC URL.

Bad: throughput. Each batch rewrites a tree and writes a commit, and
`-get-blocks` currently spawns one `cat-file` per CID instead of using
`cat-file --batch`. That optimisation is deliberately not done yet — it is a
contained change behind this same protocol, and correctness came first.

Capabilities reported: the required `:immutable-blocks :cid-addressed-read
:conditional-ref`, plus `:history :replication :offline`, which are claims this
backend can actually back rather than aspirations.

## Test

```sh
kbb -M:test
```

Covers the shared `kotobase.storage.contract` suite, CID-collision refusal,
concurrent genesis CAS, concurrent block writers, survival of
`gc --prune=now`, git-illegal ref names, the encoding-collision pair, and a
transact → reopen → query round-trip through `kotobase-engine` so the Datalog
path is exercised end to end and not merely assumed from the protocol.
