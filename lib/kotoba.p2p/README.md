# p2p

[![CI](https://github.com/kotoba-lang/p2p/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/p2p/actions/workflows/ci.yml)

**P2P graph-sync protocol for kotoba's content-addressed commit chains —
pure state machine, transport injected, verified on JVM and real
ClojureScript (shadow-cljs).**

Composition, not reimplementation:

| layer | supplies |
|---|---|
| [`kotoba-lang/net`](https://github.com/kotoba-lang/net) | gossip routing semantics (content-hash dedup, deterministic fanout) + bitswap `commits-since` delta |
| [`kotoba-lang/chain`](https://github.com/kotoba-lang/chain) (renamed from `commit-dag`, ADR-2607050800) | chain walk + tamper/seq verification |
| [`kotoba-lang/kotoba-client`](https://github.com/kotoba-lang/kotoba-client) | CID-verified block ingest + the generic tag-42 missing-blocks walk |
| [`kotoba-lang/io-ipld`](https://github.com/kotoba-lang/io-ipld) | Selector Data Model/DAG-CBOR codec + bounded, CID-verifying graph traversal |

The tag-42 migration ([`kotoba-lang/ipld`](https://github.com/kotoba-lang/ipld))
is what makes this protocol small: chain `prev`, snapshot `state`, index
roots and tree children are all real IPLD links, so **"sync a graph"
collapses to "hydrate the announced head CID to convergence, then
`verify-chain`"** — there is no per-schema transfer logic anywhere.

## Protocol

There are now two explicit protocol surfaces:

- `kotoba.p2p.sync` is the existing Kotoba commit-chain convergence state
  machine described below.
- `kotoba.p2p.graphsync` is the interoperable
  **`/ipfs/graphsync/2.0.0`** message boundary: the `gs2` IPLD Schema shape,
  DAG-CBOR encoding, unsigned-varint stream framing, request/response metadata,
  CID-prefix blocks, and successful bounded fulfillment through
  `ipld.graph/select-blocks`.

The GraphSync adapter supports Matcher, ExploreAll, ExploreFields,
ExploreIndex, ExploreRange, ExploreUnion, ExploreRecursive, and
ExploreRecursiveEdge plus CIDv1 DAG-CBOR SHA2-256 blocks. Recursive requests
remain subject to mandatory traversal budgets. Draft conditions and other
block prefixes fail closed. Stream negotiation, multi-message scheduling,
cancellation/update state, and extension semantics remain transport/runtime
responsibilities; this does not claim a full go-graphsync engine.

`kotoba.p2p.graphsync-prolly` defines the admitted
`kotoba.graphsync/prolly-base-root/1` extension. A requester names the Prolly
root it already holds as an IPLD Link; the responder walks the requested target
root, skips CID-equal subtrees, and returns a root-first delta under mandatory
responder-owned block, byte, and read budgets. The receiver checks the exact
metadata/block set and rehashes every block before landing it, then proves
completion by reading the target through its combined base + delta store. The
extension changes transfer cost, not content identity or authorization.

`kotoba.p2p.graphsync-extension` is the host-owned registry for additional
extensions. A host registers each name with its allowed `:new`, `:update`, or
`:response` phases and an IPLD-value validator, plus a mandatory maximum count.
The scheduler admits only registered request/update values; unknown names,
wrong phases, invalid values, and over-budget maps fail closed. Thus custom
extensions remain open-ended without turning receipt of an arbitrary wire map
into authority.

`kotoba.p2p.graphsync-scheduler` adds the responder lifecycle above that wire
codec: bounded active-request admission, acknowledgement, stable
priority-ordering, block-count/byte-bounded chunks, partial/paused/full
statuses, cancellation, and extension updates. Unknown cancel/update messages
are ignored as in go-graphsync. Admission creates a read-free
`ipld.graph/selection-cursor`; each scheduler step advances it under an explicit
CPU work budget and reads at most one new CID-verified block. Cancelling drops
that cursor, so neither unsent wire chunks nor future storage reads occur.
`persist-checkpoint!` writes the CID-addressed cursor through a caller-owned
block-store capability and returns `kotoba.graphsync/checkpoint/1`; receiving
that Link in an update fetches it with CID verification and restores only when
request id, root, selector, and limits match. Storage replication, retention,
and authorization remain host policy rather than extension semantics.

`kotoba.p2p.graphsync-checkpoint-store` supplies the bounded local policy
state: mandatory per-item/count/total-byte limits, TTL leases, explicit GC
receipts, and a required host authorization hook on put/get/gc. Its canonical
snapshot survives process restart. GC returns CIDs and reclaimed bytes; a host
must perform and verify physical deletion. No replication or HA claim follows
from a local snapshot.

`kotoba.p2p.graphsync-replication` turns checkpoint replication into explicit
host effects and evidence. Placement is capability-authorized; receipts count
only from planned, distinct replica identities after a host signature verifier
accepts them. `qualification` is true only while the configured number of
receipts remain unexpired. Candidate nodes, transfer attempts, duplicate
receipts, or stale receipts never imply availability.
`execute-effects` drives the planned transfers through a caller-owned
`replicate-fn`, verifies that each returned receipt matches the effect, then
lands it through the signature verifier. Per-replica transport failures remain
explicit and cannot contribute to qualification. The adapter is transport
neutral; an in-memory two-store integration test proves byte landing, not a
live network or production HA deployment.

`kotoba.p2p.graphsync-stream` closes the real transport seam without coupling
GraphSync to a socket implementation. It registers `/ipfs/graphsync/2.0.0` as
an `io-libp2p` custom protocol, authorizes the PeerId proven by Noise before
reading application bytes, drives the bounded scheduler, and CID-verifies each
block before the requester lands it. The integration suite crosses real OS TCP,
Noise XX, Yamux, and multistream between independent block stores; this is a
single-host interoperability slice, not yet multi-machine availability proof.

Five message types, all handled by the pure step
`(sync/handle node msg) → {:node node' :effects [{:to peer :msg m} …]}`:

```
:head-announce ──gossip fanout + dedup──▶ every mesh peer
      │ (announced seq > local seq)
      ▼
:want-since ──▶ origin           bitswap WantSince over the chain log
      ▼
:commits ◀── delta entries + head
      ▼
:want-blocks ──▶ origin          missing CIDs from the generic tag-42 walk
      ▼
:blocks ◀── {cid bytes}          CID-verified ingest; loop until no missing,
      ▼                          then verify-chain → adopt → re-announce
adopt + re-announce (hop-by-hop propagation)
```

Trust model: blocks are CID-verified on ingest (a lying peer's bytes are
skipped, never stored) and a head is adopted only after `verify-chain`
passes over fully-local blocks. A malicious peer can stall sync
(liveness) — including the repeated-want stall guard dropping the pending
head — but never corrupt state (safety). Trust lives in the CID, not the
transport, exactly as the browser read-plane ADR put it.

## Use

```clojure
(require '[kotoba.p2p.sync :as sync]
         '[kotoba.p2p.loopback :as lb])

(def a (-> (sync/new-node "a" store-a)          ; {:put! :get-fn} ports
           (sync/add-peer "b" #{"my-graph"})
           (sync/set-head "my-graph" chain-cid 1)))
(def b (-> (sync/new-node "b" store-b)
           (sync/add-peer "a" #{"my-graph"})))

(def net (lb/announce-and-run (lb/network {"a" a "b" b}) "a" "my-graph"))
(sync/head (get-in net [:nodes "b"]) "my-graph") ;=> {:head-cid … :seq 1}
```

`kotoba.p2p.loopback` is the in-memory reference transport (deterministic,
breadth-first, quiescence-bounded). A real transport (QUIC / WebRTC /
WebTransport / HTTP long-poll) implements the same two duties — deliver
`:effects`, feed incoming messages to `sync/handle` — as host glue outside
this repo.

## Signed head announces

`new-node` optionally takes `:sign-announce` (fn [msg] -> msg', applied to
every self-originated announce before it's gossiped) and
`:verify-announce?` (fn [msg] -> boolean, checked before a peer's announce
is trusted enough to chase with `want-since` — an unverified announce is
still relayed, gossip-style, just not acted on locally). Both default to
a no-op (`identity` / `(constantly true)`), so 2-arity `new-node` callers
are unaffected. This namespace carries no crypto/identity scheme of its
own — `kotoba-lang/kotoba-rad`'s `kotoba-rad.announce` provides a
did:key/sigref-based pair of hooks that plug in here directly.

## Profile boundary

The implemented GraphSync profile is complete for bounded CIDv1 DAG-CBOR
selection over authenticated TCP/Noise/Yamux: the v2 wire codec, request queue,
priority scheduling, pause/partial/full status, cancellation, extension update,
checkpoint persistence/restore, signed replica receipts, and CID-verified real
socket requester/responder path are all present and tested.

The following are deliberately outside that correctness profile, rather than
unfinished parts of it:

- **Alternate transports and ambient reachability** — QUIC, WebRTC,
  WebTransport, relay/NAT traversal, and autonomous peer discovery belong to
  the host transport profile. `io-libp2p` supplies the current TCP/Noise/Yamux
  seam plus Kademlia protocol primitives; configured peer addresses remain a
  deployment responsibility.
- **Optional GraphSync extensions beyond the checkpoint and Prolly contracts** — an
  extension must define its own bounded semantics and admission policy before
  it is enabled; unknown extensions do not silently gain authority.

## Test

The e2e suite syncs a **real kotobase-peer commit chain** (`kotobase-engine`
until ADR-2607050700 renamed it; transact → commit! ×2) between in-memory
nodes: two-node convergence + local
re-read via prolly-tree on the receiver's store, three-node line topology
(hop-by-hop propagation through re-announce), stale/duplicate announce
inertness, and a lying-peer safety/termination case.

```bash
kbb -M:test                     # JVM
npm install && npm run test:cljs    # real ClojureScript (shadow-cljs node-test)
```

## License

MIT
