# ADR — Browser query is CID-addressed: read needs reachability, not peers

Status: **Accepted — read plane ships with zero new transport; P2P deferred to an availability layer**
Date: 2026-06-13
Supersedes the framing in the earlier "browser participates in the libp2p mesh"
discussion (it conflated *query* with *peering*).

## 0. The insight that reframes everything

> Query is content-addressed (by CID). Therefore a browser can query any data
> that is **pinned and reachable by CID** — it does **not** need to be a libp2p
> peer, join Kademlia, or hold a WebRTC/QUIC connection to anyone.

The browser read engine already verifies every block against its CID
(`CID == sha2-256(dag-cbor(bytes))`, `crates/kotoba-wasm/src/lib.rs:64`), so
*whoever serves the bytes is untrusted*. Content-addressing collapses the trust
question that P2P transport security would otherwise solve. Once trust is moved
into the CID, "where did the bytes come from" stops mattering for correctness —
HTTP from a random gateway is exactly as safe as bitswap from a verified peer.

This ADR records the resulting split:

- **Read plane** — CID-over-HTTP. Works **today**, no libp2p, no WebRTC.
- **持ち合い / live plane** — P2P. An **availability/liveness optimization**,
  not a correctness requirement. Deferred.

## 1. Read plane — already designed and wired

The query path for a browser node, end to end, with no peering:

```
resolve HEAD          KotobaNode.verifyIpnsRecord(json)         lib.rs:956
   │                  member-signed IPNS record; the apex/gateway
   │                  serving it is NOT trusted (no-server-key).
   ▼
root CID
   │
   ▼  ┌── loop until empty ──────────────────────────────────────────┐
   │  │  missing = node.missingBlockCids(root)        lib.rs:847      │
   │  │  for cid in missing:                                          │
   │  │     bytes = GET /xrpc/com.etzhayyim.apps.kotoba.block.get     │  xrpc.rs:7561
   │  │            ?cid=<multibase>          (UNAUTH for Public)      │  xrpc.rs:6008
   │  │     node.ingestBlock(cid, bytes)     CID-verified  lib.rs:819 │
   │  └──────────────────────────────────────────────────────────────┘
   ▼
node.hydrateFromProlly(root)                            lib.rs:829
   │  same Prolly/IPLD scan_prefix path as the server
   ▼
node.datomicQ(query_edn, inputs_json)                   lib.rs:1118
   │  full Datalog over EAVT/AEVT/AVET/VAET, same engine as datomic.q
   ▼
results — entirely local, zero round-trips after the blocks are in
```

Key properties:

- **Already implemented and shipping — not a plan.** The fetch loop is
  `hydrateViaBlocks()` in `crates/kotoba-wasm/web/kotoba-blocks.js`, and the
  Service Worker `crates/kotoba-wasm/web/kotoba-sw.js` already:
  (a) calls `datomic.sync` for the covering EAVT root,
  (b) `hydrateViaBlocks(node, eavtRoot, {remote})` — `block.get` loop,
      CID-verified, persisted to IndexedDB,
  (c) **intercepts `datomic.q` POST and answers it locally in wasm**
      (`node.datomicQ`, response tagged `x-kotoba-sw: local-wasm-datomic`).
  A browser already serves Datalog queries against a pinned graph it pulled
  purely over `block.get`, with no peer connection.
- **No new Rust.** `block.get`, `ingestBlock`, `missingBlockCids`,
  `hydrateFromProlly`, `datomicQ`, `verifyIpnsRecord` all exist.
- **Server is consulted only for what the local engine genuinely can't answer:**
  time-travel (`as_of` / `since` / `history`) and federation (`remote_peer` /
  `remote_ipns_name`) fall through to the server (`kotoba-sw.js:213`); everything
  at the current head is local.
- **The byte source is interchangeable.** `block.get` on any `kotoba-server`
  self-pin, the kotobase fanout pin (when F-4 lands), or *any* IPFS gateway
  (`/ipfs/<cid>`) all serve the same CID. CID verification makes them equivalent.
- **HEAD is gateway-untrusted.** The IPNS head is a member-signed record verified
  in-wasm; a malicious gateway can withhold but cannot forge a newer head.
- **Offline-first.** Once blocks are in IndexedDB (`IdbBlockStore`), query runs
  with the network fully down.

### Correctness invariant

A browser can answer a query **iff** every block reachable from the resolved root
is retrievable by CID from **at least one** reachable holder. Pinning is exactly
the act of guaranteeing "at least one holder." Therefore:

> **Pinned + one reachable `block.get`/gateway ⇒ query works. Peer connectivity is
> not in this condition.**

## 2. What P2P is actually for (and is NOT)

P2P (libp2p over WebRTC/WebTransport — never QUIC; browsers have no UDP socket)
buys exactly three things, all orthogonal to query correctness:

| Capability | Why it needs P2P | Without it |
|---|---|---|
| **持ち合い** — browsers serve blocks to each other | removes single-holder dependency; survives the central pin/gateway being down | query still works as long as one `block.get`/gateway is up |
| **live push** — subscribe to head updates (gossip firehose) | server-initiated; no polling | poll the IPNS head on an interval |
| **provider discovery** — find a CID no known gateway holds | Kademlia provider records | query fails only for un-gatewayed CIDs |

None of these change *what answers are correct*. They change *availability*
(does a holder exist that I can reach) and *freshness latency* (how fast I learn
of a new head). That is the correct altitude for P2P here: an availability layer,
not the query substrate.

## 3. Decision

1. **The read plane already ships, with zero new transport.** The driver
   (`datomic.sync → block.get loop → hydrateFromProlly → datomicQ`) exists as
   `kotoba-blocks.js` + `kotoba-sw.js`. "A browser queries the global pinned
   graph" is **already true today**. Remaining read-plane work is incremental:
   IPNS-head resolution as a first-class JS helper (so a cold browser can start
   from a signed head, not a server `datomic.sync` round-trip), and surfacing
   `as_of`/`since` history locally instead of falling through to the server.
2. **Do NOT build a libp2p wasm swarm for query.** It was over-scoped — query is
   CID-addressed, so HTTP reachability is sufficient and strictly simpler.
3. **Defer P2P to the availability layer.** When 持ち合い / live push / provider
   discovery become requirements, add a wasm transport — and even then the choice
   is **WebRTC (browser↔browser) / WebTransport / WSS (browser↔server)**, because
   the server's `/udp/quic-v1` transport (`crates/kotoba-net`) is undialable from
   a browser. The existing WebRTC signaling relay (`kotoba-rt`, `realtime.rs:452`)
   and TURN core (`kotoba-turn`) are reusable rendezvous primitives when that day
   comes.
4. **Pinning is the availability contract.** The guarantee a querying browser
   relies on is "the blocks are pinned somewhere CID-reachable," currently
   satisfied by `kotoba-server` self-pin via `IpfsPinClient`. kotobase fanout
   (`kotobase.etzhayyim.com`, `KOTOBA_PIN_TOKEN`) is a *replication* of that
   guarantee for off-pod durability — still dormant (F-3, see
   `deps.toml:391`), and not on the query critical path.

## 4. Consequences

- The "browser node" is a **trustless read replica of the pinned graph**, not a
  network peer. That is a simpler and more honest mental model.
- Availability of query == availability of *any* CID holder, decoupled from peer
  topology. A single highly-available `block.get`/gateway is enough for read.
- The P2P work (WebRTC mesh, gossip subscribe) is now clearly optional and
  independently schedulable, justified only by the three capabilities in §2 —
  not by "let the browser query."
- Next concrete step is JS, not Rust: wire the fetch loop and demonstrate a
  browser answering a `datomicQ` against a graph it never had locally, pulled
  purely over `block.get`.

## 4a. Implementation pointers

- Registry: this ADR is entry `:adr-browser-cid-query` in `docs/adr.edn`
  (machine-readable status + follow-ups).
- Read-plane glue is **ClojureScript** (per the migration decision): the new
  IPNS-head resolver and query orchestrator live in
  `crates/kotoba-wasm/web/cljs/` (`kotoba.ipns` / `kotoba.node`), built by
  shadow-cljs to ESM at `crates/kotoba-wasm/web/cljs-out/kotoba-node.js`. The
  existing `kotoba-blocks.js` / `kotoba-sw.js` remain until ported (follow-up
  `:cljs-port-lower-modules`).
- The signed-head endpoint **now exists**:
  `GET /xrpc/com.etzhayyim.apps.kotoba.ipns.head?graph=<cid>` (`xrpc::ipns_head`,
  lexicon `ipns/head.json`, e2e `ipns_head_resolves_signed_record_for_committed_graph`).
  It returns the member-signed `IpnsRecord` (UNAUTHENTICATED, self-verifying), so
  `kotoba.ipns/resolve-head` → `hydrate-and-query-verified!` is wired end to end.
- The EAVT root is now **derived from the verified head**, not trusted from
  `datomic.sync`: `KotobaNode.commitIndexRoots(commit_cid, bytes)` CID-verifies
  the head commit block and decodes its `index_roots` in-wasm, so
  `hydrate-and-query-verified!` is signature- or CID-checked at every hop
  (head signature → commit CID → index roots → each Prolly block). `datomic.sync`
  is no longer on the verified path.
- The lower browser modules are now **ClojureScript**: `kotoba.idb` (snapshots +
  rawblocks at DB v2) and `kotoba.blocks` (CID-verified, IndexedDB-cached block
  sync). `kotoba.node` delegates block sync to `kotoba.blocks`. Build is 0 cljs
  warnings.

## 4b. Write path — symmetric, signature-authorized, no server trust

Reads moved trust into the CID + the signed head. Writes use the **same trust
model in reverse**: the browser builds a content-addressed, member-signed commit
entirely locally and publishes it to an untrusted holder.

```
KotobaNode.assert → commitHeadSigned(seq, valid_until)   ← member Ed25519 sig
   │                  → signed IpnsRecord + captured blocks
   ▼
kotoba.write/publish!:
   block.put   each block        → server RECOMPUTES the CID (can't substitute bytes)
   ipns.publish signed record    → xrpc::ipns_publish
                                    require_verified_signature (unsigned → 401)
                                    registry sequence CAS      (rollback   → 409)
```

**Authority is the signature over a key-derived IPNS name, not a server
credential.** The holder is a relay: it cannot forge a head (no key) nor roll one
back (CAS). This is takeover-proof **exactly when the IPNS name binds to the
signing key** — a sovereign / DID-scoped graph. For a **shared** graph whose head
name is `k51-kotoba-<graph_cid>` (not key-derived), a valid self-signature does
not prove authorization, so those writes stay on the **CACAO-gated
`datomic.transact`** path. Two write paths, by design:

| graph kind | head name | write authority | path |
|---|---|---|---|
| sovereign / DID-scoped | key-derived | member Ed25519 signature | `ipns.publish` (trustless, browser-local) |
| shared / operator | `k51-kotoba-<graph>` | CACAO capability | `datomic.transact` (server-gated) |

Implemented: `xrpc::ipns_publish` (lexicon `ipns/publish.json`, e2e
`ipns_publish_advances_head_and_round_trips_via_ipns_head` — publish 200 → round-
trips via `ipns.head`, stale → 409, unsigned → 401); `kotoba.write/publish!`
(block.put loop + ipns.publish). Block push reuses the existing `block.put`.

## 5. Non-goals (explicitly out of scope here)

- Private/Authenticated graph reads from the browser (block.get is unauth only
  for Public; CACAO-gated cold reads are a separate path).
- 持ち合い mesh — browsers serving blocks to *each other* (the P2P layer, deferred
  per §3). Sovereign write *publish* to a holder is done (§4b); browser-to-browser
  block hosting is not.
- Replacing the server QUIC transport (it stays; it is the server↔server plane).
