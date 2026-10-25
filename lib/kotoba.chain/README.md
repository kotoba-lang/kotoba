# chain

**Parent-linked, content-addressed commit chain — pure Clojure, no native deps,
babashka-friendly.** `prev` is a **real tag-42 IPLD link** (null at genesis)
via [`kotoba-lang/ipld`](https://github.com/kotoba-lang/ipld); `state` stays
opaque, and callers that want a walkable state simply put `ipld/link` values
inside it. This replaced the first landing's plain-CID-string encoding —
every commit CID changed (clean break, pre-production, see superproject ADR). Wave 1/2 of
[ADR-2607022600](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607022600-kotoba-database-crates-cljc-migration-roadmap.md)
(migrating the removed `kotoba-lang/kotoba` Rust database crates to CLJC).

**Renamed from `commit-dag`** (ADR-2607050800): the removed Rust
`kotoba-graph::commit` was an append-only, parent-linked chain of
`Commit{root, index_roots, prev, seq}` blocks — per
[ADR-2606041151](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2606041151-kotoba-commitdag-as-wal-and-incremental-query-tier.md),
**the CommitDag IS the write-ahead log**, not a separate journal. Datomic's
own formal architecture term for exactly that immutable, durable,
append-only transaction sequence is the **Log** — the natural rename target,
except `kotoba-lang/log` already exists for something unrelated (structured
logging/telemetry, `kotoba.lang.log`). **`chain`** names what this repo
actually is instead: a parent-linked chain, matching its own `chain`/
`verify-chain`/`head` functions directly. This namespace has no CLJC
predecessor: it commits an opaque `state` value (today, typically a
[`kotoba-lang/prolly-tree`](https://github.com/kotoba-lang/prolly-tree) root
CID string, or [`kotoba-lang/arrangement`](https://github.com/kotoba-lang/arrangement)'s
4-index roots as a map of `{"eavt" cid "aevt" cid ...}`) and never looks
inside it — only chains and verifies.

Storage is injected exactly the way `prolly-tree.core` does it (`put!`
`(cid, bytes) -> ignored` / `get-fn (cid) -> bytes`), so a caller using both
libraries shares one block store with no adapter glue.

## Where this fits / quick use

Stack position: kotoba (language, authority) -> itonami (jobs) -> murakumo
(compute) -> kotobase (state/results) -> optional anchor. `chain` is the small
commit-chain primitive underneath that state layer. The private-network layer,
AWAI DNA (DNA CID = network id, signed per-agent source chains), is a proposed
spec only (network-awai/network-awai-apex PR #14, branch
`dna-private-network-spec`, `awai-dna/`). Interactive figure:
<https://kotoba-lang.org/anatomy/kotoba-murakumo/>.

What it gives you: each commit is a DAG-CBOR block whose CID is its address.
`prev` is an IPLD tag-42 link to the parent commit (null at genesis), `seq`
counts up, and `state` is an opaque value `chain` never looks inside. So a
head CID commits to the whole history behind it, and a store that returns wrong
bytes for a CID, or a spliced-in commit, is detected by `verify-chain`. It is
a library for append-only, tamper-evident history, not a blockchain: there is no
network, consensus or token. Relation to kotobase: kotobase's commit DAG
(signed, multi-parent, CID-addressed) is the richer database-level analogue;
`chain` is the minimal parent-linked form (its optional `causes` field makes a
commit a DAG node too). It does not sign anything or depend on kotobase.

Minimal check against the real `chain.core` API (run offline with `kbb`; the
tampered store is the same example as in "Use" below plus one overwritten block):

```clojure
(require '[chain.core :as cd])
(def store (atom {}))
(def put!   (fn [cid bytes] (swap! store assoc cid bytes)))
(def get-fn (fn [cid] (get @store cid)))
(def c0 (cd/commit! put! get-fn "state-a" nil))
(def c1 (cd/commit! put! get-fn "state-b" c0))
(cd/verify-chain get-fn c1)              ;=> true
(swap! store assoc c0 (get @store c1))   ; store lies about c0's bytes
(cd/verify-chain get-fn c1)              ;=> false
```

## Use

```clojure
(require '[chain.core :as cd])

(def store (atom {}))
(def put!   (fn [cid bytes] (swap! store assoc cid bytes)))
(def get-fn (fn [cid] (get @store cid)))

(def c0 (cd/commit! put! get-fn "prolly-root-a" nil))   ; genesis, seq 0
(def c1 (cd/commit! put! get-fn "prolly-root-b" c0))    ; seq 1

(cd/chain get-fn c1)          ;=> ({:cid c0 :state "prolly-root-a" :prev nil :seq 0}
                              ;    {:cid c1 :state "prolly-root-b" :prev c0  :seq 1})
(cd/head get-fn c1)           ;=> the seq-1 entry above
(cd/verify-chain get-fn c1)   ;=> true — false if a store lies about a CID's bytes
                              ;    or a spliced-in commit skips a seq
```

## Was it allowed?

`verify-causal` answers whether a history is *sound*. `chain.authorized`
answers whether it was *permitted*, by walking the DAG and asking an injected
resolver about the authority each commit names. Issuance stays elsewhere —
this namespace joins, it does not decide.

```clojure
(require '[chain.authorized :as auth])

(auth/verify-authorized get-fn head
                        {:resolve-grant (fn [cid] {:subject "alice" ...})
                         :as-of "2026-08-18T00:00:00Z"
                         :revocation :prospective})
;; {:ok? false :visited 3 :as-of "…" :revocation :prospective
;;  :findings [{:cid "bafy…" :actor "mallory" :reason :revoked}]}
```

Two things the caller must state, with no default:

- **`:as-of`** — a Lamport clock orders events but is not a time, and grants
  expire in wall-clock time. The two are not convertible, so the instant is
  named by the caller and repeated back in the verdict.
- **`:revocation`** — `:retroactive` (the grant was never trustworthy, which
  is what a compromise means) or `:prospective` (history records what was
  permitted then, which is what a receipt means). Neither is right in general.

**Merges do not launder.** `:ok?` is false when any reachable commit fails, so
merging an unauthorized branch into an authorized one yields an unauthorized
history — the merge commit's own authority covers the merge, not what it drags
in.

`:findings` lists every failure rather than the first, and `:visited` is the
evidence floor: a report over zero commits is not a pass.

## Correctness

`kbb -M:test` (no network):

- genesis + multi-commit chain linking, `:seq` values, `head`
- `state` is opaque — a bare CID string and a `{index cid}` map both round-trip
  unchanged (arrangement forward-compatibility)
- `verify-chain` accepts an honest chain
- `verify-chain` rejects a store that returns different bytes for an existing
  CID than what was originally content-addressed under it (tamper-evidence)
- `verify-chain` rejects a spliced-in commit with a `:seq` gap, independent of
  the tamper-evidence check above

```
$ kbb -M:test
Ran 8 tests containing 22 assertions.
0 failures, 0 errors.
```

## Scope

This is the commit-chain primitive only. Not in scope for this landing:
snapshotting/checkpoint-from-seq-N (the original Rust engine's "restart loads
the head + checkpoint and walks commits since" — this namespace only walks
from a given `cid`, callers own persisting "the current head cid" themselves),
garbage collection of unreferenced commits, and multi-writer conflict
resolution (a single linear `prev` chain assumes one writer per graph, which
matches the Datom-log-is-canonical decision in
[ADR-2605312345](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2605312345-kotoba-datom-first-class-canonical-state.md)
but not yet any multi-peer merge story).

## License

Apache-2.0.

## A commit can carry why it was allowed, and what caused it

Root ADR-2608160200 asks a commit to stop being a single line: a
per-principal causal DAG rather than one chain, with the authority that
permitted the write recorded next to it. `commit!` takes an optional map:

```clojure
(chain/commit! put! get-fn state prev-cid
               {:actor "alice"
                :causes [b1]        ; parents from other principals' sequences
                :authority grant})  ; the capability/receipt CID that allowed it
```

| field | what it is |
|---|---|
| `causes` | additional **parents**. `prev` stays this principal's own sequence, so a chain is the special case of a DAG with one parent |
| `authority` | the CID that permitted this write. Without it an audit reaches *who wrote this* and stops short of *why were they allowed to* |
| `actor` | the principal whose sequence `prev` belongs to |
| `lamport` | `1 + max` over parents — **derived, never taken from the caller**, so the clock cannot disagree with the edges it summarises |

**Every added field is written only when supplied**, so a commit made the way
commits were made before this encodes to the same bytes and keeps the same
CID. A test pins two CIDs recorded from the previous implementation, and the
eight tests that existed before pass unchanged — the claim is checked, not
asserted. `commit-info` likewise leaves absent keys absent: *has no causes*
and *carries an empty cause list* are different facts.

A parent is fetched and CID-verified when it is cited, so an edge to
something that does not exist is refused rather than stored — a dangling
edge is worse than no edge, because it reads as provenance.

`walk-causal` follows both `prev` and `causes`, visiting a commit reachable
by several routes once, and **says when it stopped** at its visit bound
instead of returning a short history as if it were the whole one.

`verify-causal` returns a report rather than a boolean, because `false`
cannot distinguish *this history is unsound* from *something threw and we
caught it*, and those need different responses. It checks CID re-derivation,
that every named parent is fetchable, and that `lamport` agrees with the
edges.

**It does not check signatures.** `authority` is a CID whose shape this
namespace verifies; deciding that a grant was validly issued belongs to
`aiueos`, and a chain that pretended to do it would be trusted for something
it never checked.

## Pure Kotoba encoder

`src/chain/commit.kotoba` (`chain.commit`) encodes a commit to DAG-CBOR without
the host: `encode-commit` takes state, prev, seq, causes, authority, actor and
lamport (absent fields as `""`, an empty map, or `-1`) and returns the bytes
`commit!` would store. `next-lamport` is `1 + max` over the parents' clocks.
`src/chain/commit_cid.kotoba` (`chain.commit-cid`) turns those bytes into the
commit CID through `hash/sha256` (capability 3).

`chain.core` stays the oracle: `scripts/commit-oracle-cases.cljk` checks four
commits against `commit!`, byte for byte and CID for CID. Storage, decoding and
chain walks stay host-side; `migration/commit-v1.edn` lists what is ported.
