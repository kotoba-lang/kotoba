# kotobase-engine

Database engine facade over `kotobase-peer` internals. Applications use the
provider-neutral **`kotobase.datomic.client`** namespace as a drop-in for
published `datomic.client.api` (same arg-maps and return shapes), or the
lower-level `kotobase.datomic` grammar facade. Neither depends on the
historical “peer” naming, XRPC, or a storage provider SDK.

The `:kotobase` server type is a real HTTP client for
`https://datomic.kotobase.net/api/*`. It carries immutable database values
(`db-name`, graph, basis, as-of/since/history filters) as ordinary EDN while
the edge re-derives the graph from the authenticated tenant. JVM Clojure uses
`java.net.http.HttpClient`; tests and other hosts can inject `:request-fn`.

```clojure
(require '[kotobase.datomic.client :as d])

(def client (d/client {:server-type :kotobase
                       :endpoint "https://datomic.kotobase.net"
                       :token #(System/getenv "KOTOBASE_TOKEN")}))
(def conn (d/connect client {:db-name "production"}))
(def snapshot (d/as-of (d/db conn) 42))
(d/q '[:find ?e :where [?e :person/name _]] snapshot)
```

This is published-API shape compatibility, not Cognitect proprietary wire
compatibility. A stock `com.datomic/client-cloud` binary cannot be redirected
to this endpoint.

The Datomic-shaped surface includes immutable `db` values, `transact`, `with`,
`q`, `pull`/`pull-many`, `entity`/`touch`, all four `datoms` index orders,
`seek-datoms`, `index-range`, `entid`/`ident`, `basis-t`, `as-of`, `since`, and
`history`. `at-cid` pins an immutable value to an exact content-addressed
commit; reads verify its blocks and never fall back to the mutable head.
`commit-at!` appends against an exact basis without reading or publishing a
mutable ref, so concurrent writers form explicit branches instead of silently
rebasing.
`merge-at!` deterministically merges such branches into one multi-parent
commit (kotobase ADR-2610101200, rule in `kotobase-engine-contract`'s
`kotobase.engine.merge`); `merge!` does the same with the current ref head and
advances the ref through the provider's compare-and-set. See
[Multi-parent merge](#multi-parent-merge).
`tx-range` exposes committed transaction reports and `listen` /
`unlisten` provide in-process post-commit listeners. Transactions resolve
negative tempids, lookup refs and `:db.unique/identity` upserts before
publication. Cardinality, uniqueness and value types are enforced from schema
datoms, including homogeneous, heterogeneous, and composite tuple attributes.
Built-in transaction functions include `:db.fn/cas`,
`:db.fn/retractAttribute`, and `:db.fn/retractEntity`; applications can
register additional pure transaction functions in `engine/open` under
`:tx-functions` or persist a portable `:db.type/fn` value using the bounded
`kotobase/tx-ir-v1` declarative format. Both use the same
`[:function-ident arg ...]` transaction syntax. Persisted functions may emit
only Datomic transaction operations; arbitrary host-language evaluation is
deliberately unavailable.

The JVM facade is synchronous. The ClojureScript facade returns Promises and
trampolines synchronous IPLD traversal over asynchronous S3/R2/IPFS reads.
It awaits every immutable block write before publishing the mutable database
ref.

## Multi-parent merge

Two writers that `commit-at!` on the same basis offline produce sibling
commits. After exchanging blocks, either writer runs

```clojure
(def conn (engine/open {... :merge {:database-id "tenant/db"
                                    :schema {":doc/status" {:db/cardinality :db.cardinality/one}}}
                           :trust-scope "tenant-key-1"}))
(engine/merge-at! conn [left right])
```

and both get the same merge commit (argument order and duplicates do not
matter). `branch-heads` reduces a set of known commit CIDs to the siblings a
merge must name. `merge!` merges them with the ref head and publishes through
CAS. Merging is implemented on the Promise facade only. On the JVM the entry
points and `open`'s `:merge` option throw `:kotobase.engine/unsupported-platform`.
JVM reads and log readers do not detect merge commits: open merged
databases on the Promise facade.

- **Settings are identity and have no defaults.** `:database-id` and
  `:schema` are written into every logical commit, so converging writers
  must agree on them. Configure them once at `open` under `:merge` (reads
  need them too) or pass them per call. Schema keys are the *stored*
  attribute strings (`":doc/status"`). Only `:db/cardinality`
  (`:db.cardinality/one|many`) and `:db/unique` (`:db.unique/value|identity`)
  are accepted, and keyword keys or other keys are rejected (`:invalid-schema`).
  `:database-id` is a label: the contract's single-genesis rule, not the
  label, is what stops unrelated histories from merging.
- **One semantics for storage and merge.** kotobase-peer stores raw quads, so
  every attribute behaves as cardinality-many and non-unique. The merge
  contract applies the schema. These agree only when every linear
  transaction is valid for a serial executor:
  - a cardinality-one value is replaced by an explicit retract plus an
    assert;
  - a `:db/unique` value is never asserted while another entity holds it.

  The `kotobase.datomic` layer writes exactly this. Any history that breaks
  either rule is rejected with `:schema-violation` by merging, verification
  and reads through merges. This was chosen over re-interpreting raw quads,
  which would make `q` and the merge disagree about the same commit.
- **Logical identity.** Each physical chain commit maps to one logical
  commit, with no new bytes:
  - a commit that adds a transaction is a `kotobase.logical-commit/v1`
    commit over its `prev`;
  - a `fold!` commit is logically its `prev`;
  - a merge is the contract's `kotobase.logical-commit/v2` commit,
    recomputed every time the merge is projected.

  `logical-projection` returns the contract graph.
- **Physical merge commit.**
  - Parents: chain `prev` is the parent with the greatest `[seq cid]`, so
    `t` never goes backwards; chain `causes` are the other parents in CID
    order. Commits without `causes` keep byte-identical CIDs.
  - State: a fresh indexed snapshot of the merged datoms.
  - Views: the union of the parents' materialized views, re-derived over
    the merged state. Views are derived projections, so the union cannot
    change data. One view name with different specs is refused
    (`:incompatible-views`). A view removed on one branch only is kept.
- **Trust model for reads (no cost without merges).**
  - Every merge commit writes a `"merge"` marker `{policy, parents}` into its
    state. kotobase-peer's `commit!` copies unknown state keys, and leaves
    `indexed` and `views` unchanged. So every linear descendant of a merge
    reads exactly that merge's snapshot and carries its marker, until a
    `fold!` rebuilds the state.
  - A read looks only at the head block it fetches anyway.
    - If the head has neither `causes` nor the marker, the read is the same
      as on `main`: no extra fetch, no closure bound.
    - Otherwise the head names its merge snapshot (`{parents indexed views}`).
      The snapshot is verified once:
      - the contract merge of the parents;
      - the snapshot's quads;
      - **all four covering indexes** (`spo`/`pso`/`pos`/`ocp`), each leaf
        key re-derived from its decrypted value with the connection's
        `blind-fn`;
      - the views re-derived from the merged state;
      - the stored schema.

      The result is cached by snapshot, not by head, so every later head on
      that snapshot costs nothing extra and no history is walked. Measured
      with 150 transactions after a merge:
      | read | block requests |
      |---|---|
      | merge-free control | 163 |
      | first read through the merge | 180 |
      | next head | 164 |
  - **`:trust-scope` is required with `:merge`.** It is a string or keyword
    naming the key material (for example a key id). Verified snapshots are
    cached process-wide per scope, so per-request connections with fresh
    closures share one verification, and connections with other keys verify
    for themselves. Without it, `open` throws: a default tied to the
    `decrypt-fn` object would re-verify on every request. Only strings are
    held, never closures. Both levels (64 scopes, 4096 snapshots per scope)
    are LRU, so evicting one scope never clears the others. Concurrent cold
    reads in one scope share a single in-flight verification.
  - Without `:merge` settings, reading or writing through a merge is
    refused (`:unverified-merge`).
  - Writers enforce the same rule. `transact!`, `commit-at!` and `fold!`
    refuse to build on an unverified snapshot, and that includes the head
    returned by kotobase-peer's internal CAS retry in `fold!`. So honest
    writers never launder a forged merge into an unmarked (linear-trust)
    snapshot.
  - A merge commit that carries pending transactions is refused even when
    its snapshot is trusted, because `merge-at` never writes any.
  - **Residual.** A commit with neither `causes` nor the marker is read on
    the linear trust model kotobase-peer always had: its CID-verified
    snapshot is trusted. That covers a forged linear commit, a forged
    `fold!`, and a child that an older, unguarded writer put on a forged
    merge without a valid marker; each equals forging the child directly.
    Pending transactions on a linear descendant of an honest merge are
    novelty, read like any linear commit's; `verify-at` recomputes the
    head's logical state and catches them. A
    fast-forward returned by the immutable `merge-at!` is checked for quads
    but not for views. kotobase-peer's `rebase-fold!` over a merge snapshot
    keeps the marker but changes the snapshot, so reads of it fail closed.
- **Write-time checks with `:merge` settings.** `transact!` and
  `commit-at!` refuse a transaction that is not serial-valid for the merge
  schema (`:schema-violation`). The check uses point lookups only
  (`[e a]`, `[a v]`, and the schema entity of any schema datom touched)
  through kotobase-peer's range-pruned snapshot index plus its novelty
  backlog, never a full hydrate. A one-leaf probe first checks that the
  connection's `blind-fn` produces the snapshot's keys; otherwise every lookup
  would silently come back empty (`:blinding-mismatch`). Writing one
  cardinality-one datom to a folded 300-datom database takes 9 block requests
  against 1 without `:merge`. With an unfolded backlog of 300 it takes 327,
  which is the backlog scan a read also pays: the pinned kotobase-peer cannot
  prune novelty. Committed bytes are identical with or without `:merge`; a
  `:merge` connection only adds the refusal. Schema datoms that
  contradict the settings are refused (`:schema-mismatch`), including an
  ident and its cardinality written in separate transactions. Merging and
  merge verification cross-check the settings against the schema datoms
  stored in the heads' state, in the `kotobase.datomic` form
  (`[e ":db/ident" a]`, `[e ":db/cardinality" ..]`, `[e ":db/unique" ..]`).
- **The ref only moves forward.** `merge!` keeps the current head when the
  merge is logically that head: an ancestor, a pre-`fold!` commit, or a
  forged look-alike. For a fast-forward to a logical descendant T it writes
  a carry commit over T. The carry's snapshot is built from T's *verified
  logical* state, plus the union of the current head's and T's views. The
  ref therefore never moves onto a snapshot `merge!` did not build. This
  keeps the fold's compaction and views on a branch from before a `fold!`,
  and never publishes a snapshot or view block forged on T.
- **Log readers do not span merges.** `tx-range`, `since`, `history` and
  `as-of` follow `prev` only. When their range reaches a merge they reject
  with `:history-spans-merge` instead of dropping the other parents'
  transactions. A range that starts above the latest merge is served, and
  only the lineage the range reaches is checked. Cross-branch history is the logical graph.
- **One budget.** `:max-closure` bounds commits walked. `:max-work` is one
  budget for the whole call. It covers the projection (charged before
  transaction blocks are fetched), retractEntity expansion, checkpoints and
  every contract call, each of which gets only the budget still unspent.
  Merge cost is O(commits × state) because of the reference replay; the
  ADR's open gates (incremental checkpoint root, trusted snapshot start)
  are the fix.
- **Convergence.** The physical merge CID is equal across writers only with
  deterministic `encrypt-fn`/`blind-fn`. The logical root is always equal.
