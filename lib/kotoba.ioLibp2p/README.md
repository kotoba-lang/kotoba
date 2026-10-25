# kotoba-net

**P2P content-distribution *semantics* (gossip/GossipSub-equivalent + bitswap-equivalent) in pure Clojure/EDN.**

This repo is the CLJC re-implementation of the semantic layer that used to
live in the (now-deleted, see `kotoba-lang/kotoba` PR #259 and
`docs/rust-crate-migration.md`) Rust crate `kotoba-net`, which combined
libp2p (QUIC transport + Noise handshake + GossipSub) with a bitswap-style
block exchange.

## libp2p connection (`kotoba.net.libp2p.*`)

Every layer of a libp2p connection already existed in this workspace as a pure
state machine with no socket — `libp2p.multistream` and `libp2p.yamux`
(`io-libp2p-specs-transport`), the XX pattern (`kotoba-lang/noise`), the
addresses (`multiformats.multiaddr`), the DHT protocol
(`io-libp2p-specs-kad-dht`). What was missing was a socket and the thing that
runs them in order:

```
TCP → multistream(/noise) → Noise XX → multistream(/yamux) → Yamux
                                                               ↓
                                 multistream(<protocol>) per stream
```

| ns | role |
|---|---|
| `handshake` | libp2p's identity binding: the `noise-libp2p-static-key:` signature that ties a peer id to a Noise static key |
| `keys` | JVM verification for Ed25519 / RSA / ECDSA identity keys |
| `identify` | `/ipfs/id/1.0.0`, and the one claim in it that can be checked |
| `connection` | the driver: three stacked framings, in order, over an injected port |
| `mux` | concurrent Yamux driver: one socket reader, independently negotiated inbound/outbound streams |
| `socket` | TCP mechanism only — connect, read exactly n, write, close |
| `dial` | assembly: multiaddr in, authenticated connection out |
| `serve` | what to answer: identify snapshot, kad replies from a routing table |
| `node` | listen, answer, remember, and look up — `kad.table` + `kad.lookup` driven over a socket |
| `fetch` | `/libp2p/fetch/0.0.1`, protobuf + unsigned-varint framing for persistent IPNS records |
| `pubsub` / `pubsub-stream` | full GossipSub RPC/control protobuf and long-lived unidirectional `/meshsub/1.1.0` streams |
| `gossipsub` / `gossipsub-host` | mesh, cache, heartbeat, GRAFT/PRUNE, IHAVE/IWANT, v1.1 scoring and socket host |
| `dnsaddr` | `/dnsaddr/…` TXT resolution, filtered to the peer id it names |
| `store` | records (validated, deny-by-default) and providers (expiring), both bounded |
| `validate` | concrete validators — `/ipns/` (signature, expiry, sequence) and `/pk/` |

`node` also accepts a deny-by-default `:protocol-handlers` map. Only named
protocols are advertised and negotiated; each handler receives the live stream
plus the remote identity proven by Noise (`:peer` and derived `:peer-id`). This
is the host boundary for higher protocols such as GraphSync: application bytes
cannot choose the principal whose capability is evaluated.

### What is verified against the real network

Measured 2026-08-04 against public IPFS peers and a local Kubo 0.41 node — the
whole stack, end to end:

| | result |
|---|---|
| TCP + multistream + Noise XX + identity verification | Ed25519 peer (`megaphone`) and RSA peer (`kubo/0.32.1/mars.i.ipfs.io`) |
| Yamux stream + `/ipfs/id/1.0.0` | `kubo/0.41.0/Homebrew`, 12 protocols; identity consistent with the handshake |
| `/ipfs/kad/1.0.0` FIND_NODE | real reply, 20 closer peers |
| `/meshsub/1.1.0` | current `go-libp2p` reference peer subscribed, GRAFTed, and received `GO_REFERENCE_OK` over one bidirectional connection |

It is now a **node**, not only a client. Measured against Kubo 0.41:

```
$ ipfs swarm connect /ip4/127.0.0.1/tcp/45021/p2p/12D3KooWKYvKSgn…
connect 12D3KooWKYvKSgn… success
$ ipfs id 12D3KooWKYvKSgn…
"AgentVersion": "kotoba-libp2p/0.1"
```

go-libp2p dialed us, completed the responder handshake, identified us, and
lists us as a peer. A node also answers `/ipfs/kad/1.0.0` from its routing
table (verified between two of our own nodes: a FIND_NODE served from a table
of three peers, and the caller learned five). `kad.table` owns the eviction
rule and `kad.lookup` the iterative search; neither is reimplemented here.

It now serves the rest of what a participant owes:

- **records**, with validation **injected and deny-by-default**. The DHT has no
  universal notion of a valid record — only per-namespace rules — and a node
  that accepts what it cannot check is worse than one that accepts nothing: it
  becomes a confident source of whatever it was handed. `/pk/` is included
  because it is self-validating; everything else is the operator's decision.
- **providers**, which expire (48 h). Nobody can verify a provider claim from
  here and it is not meant to be verifiable — it is checked by going and
  asking. What matters is that it stops being advertised when it goes stale.
  The provider is recorded under the **connection's** peer id, never the one in
  the message, or anyone could advertise anyone else.
- **`/ipfs/ping/1.0.0`**, both directions. `ipfs ping` against this node
  returns a Pong.
- **probes**: a full bucket returns an instruction to ping the least recently
  seen incumbent, and that now happens. Returning it and doing nothing kept the
  safe half of Kademlia's rule (the incumbent stays) and lost the other: a
  table full of dead peers never makes room.
- **bucket refresh**, so the table learns from more than the traffic it happens
  to see.

Both stores are bounded — an unbounded one is a memory-exhaustion vector
reachable by anyone who can send a message.

`validate/validators` supplies the `/ipns/` rule, whose three parts are checked
separately because two of them are the ones usually skipped: the signature must
verify **under the key the DHT key names** (a record carrying its own key would
verify perfectly and prove nothing); the record must not be expired; and a newer
record must beat an older one, or an attacker who cannot forge a signature can
still pin the network to an old value by racing to publish it.

`announce!` sends ADD_PROVIDER to the peers closest to the key — which is what
makes a provider record findable by someone who does not know us — and records
the claim locally, since a node that told the network but not itself would
answer GET_PROVIDERS without naming itself. `republish!` re-announces only what
*we* provide; provider records expire, so announcing once means being advertised
until the TTL and then silently not. The interval belongs to the caller.

**Transports**: TCP/Noise/Yamux is the built-in JVM socket backend. Native QUIC,
WebTransport, and WebRTC engines remain host dependencies, but
`kotoba.net.libp2p.transport` now supplies their bounded selection boundary:
each backend returns its native muxed connection and must attest the
authenticated remote PeerId. `kotoba.net.libp2p.dcutr` supplies the standard
CONNECT/CONNECT/SYNC protobuf exchange over a relay stream, with the 4 KiB
message ceiling and three-candidate direct-dial ceiling enforced locally.

### The two bugs that cost the most, and how they presented

Both were silent, and both looked like the peer's fault.

`yamux/decode` returns `{:frame … :rest …}`, not the frame. Reading its fields
off the wrapper yielded nil for every one, so nothing looked like DATA, no
payload was ever consumed, and the next read took that payload as a header. The
connection desynchronized on the first frame and the peer — which had just
accepted us — reset it. What made this hard was the symptom: a `Connection
reset` immediately after a handshake that had visibly succeeded, pointing
attention at the crypto rather than at a `get` on the wrong map.

The second is that **a connection is not one stream**. go-libp2p opens
`/ipfs/id/1.0.0` at us the moment it accepts, and it pings. A reader that
waited only for its own stream dropped all of it; the peer's negotiation timed
out after 5 s and it tore the connection down. Only the peer's own logs said
so — from this side it was another unexplained reset. Inbound streams are now
reset explicitly, which answers in one frame instead of making the peer wait
out a timeout that is indistinguishable from a hang.

## Scope

**In scope — pure, transport-independent, deterministic functions:**

- `kotoba.net.gossip` — peer/topic bookkeeping, content-hash based message
  dedup via a bounded FIFO seen-cache, deterministic fanout peer selection,
  and `route-message` (dedup + fanout combined).
- `kotoba.net.bitswap` — want-list / have-list bookkeeping,
  want∩have intersection (`respond-to-want`), and the `WantSince` delta-sync
  request/response applied against a local commit-log (`commits-since`).
- `kotoba.net.ipns-router` — executes the standard `ipns.pubsub` state/effect
  core over this repo's current gossip host: validate/select/persist,
  fan-out, and persistence Fetch request/response commands.
- `kotoba.net.ipns-standard` — executes the same state machine over standard
  StrictNoSign GossipSub RPCs and `/libp2p/fetch/0.0.1`; validation and record
  selection remain single-sourced in `tech-ipfs-specs-ipns`.
- `kotoba.net.libp2p.gossipsub` — the v1.1 mesh/control/security algorithm as
  pure state transitions, including bounded caches, extended validation,
  backoff, outbound quota, P1–P7 scoring inputs, graylisting, and heartbeat.

The older `kotoba.net.ipns-router` EDN envelope remains as a compatibility
adapter. New interoperable hosts use `ipns-standard`, `gossipsub-host`, and the
Fetch protocol handler; they do not translate records through the EDN envelope.

**Real I/O, on top of `kotoba-lang/wire` — `kotoba.net.transport.tcp`:**

- A plain-TCP "gossip node" (`src/kotoba/net/transport/tcp.cljk`,
  Node-only/nbb) that actually moves the `:kotoba.net.gossip`/
  `:kotoba.net.bitswap` protocol messages above between real peers over
  real sockets, delegating all framing/socket-pool mechanics to
  [`kotoba-lang/wire`](https://github.com/kotoba-lang/wire) — the same
  dependency [`kotoba-lang/dtn`](https://github.com/kotoba-lang/dtn)'s own
  TCP transport already runs on. See "Real TCP transport" below.

**Still out of scope:**

- Concrete native QUIC/TLS, WebTransport, WebRTC datachannel, and Circuit
  Relay v2 engines. Their registered connection contract and DCUtR direct
  upgrade are implemented; deployment still has to inject and qualify each
  engine. Autonomous ambient peer discovery is likewise a deployment concern.
- Tit-for-tat / bandwidth accounting, ledger/session bookkeeping for bitswap.

The premise (see `orgs/kotoba-lang/kotoba/docs/rust-crate-migration.md`): a
full libp2p-equivalent stack is not realistic to build from scratch in
Clojure/ClojureScript. What *is* tractable, and worth being the semantic
source of truth, is the protocol logic — fanout selection, dedup, want/have
resolution, delta-sync — as pure functions that any transport (JVM socket,
browser WebRTC, native Rust/Go adapter, etc.) can drive. See
`docs/ADR-kotoba-net-p2p-semantics.md` for the full rationale.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 68 tests / 201 assertions, all green (`kbb -M:test`) |
| Real TCP transport (`kotoba.net.transport.tcp`) | yes — plain TCP via nbb, built on `kotoba-lang/wire`; E2E demo green (3/3 scenarios), see below |
| Gossip fanout + dedup over real sockets | yes — real multi-node mesh delivery, seen-cache dedup proven to suppress redundant re-delivery across real OS processes |
| Bitswap want/have over real sockets | yes — real request/response round-trip, matches pure `respond-to-want` |
| Bitswap delta-sync over real sockets | yes — real request/response round-trip, matches pure `commits-since` |
| IPNS Fetch + GossipSub standard wire | yes — real TCP/Noise/Yamux; current go-libp2p reference delivery verified |
| Peer discovery / DHT | Kademlia query/serve yes; autonomous ambient discovery is still host-configured |
| NAT traversal / QUIC | no — direct TCP multiaddrs only |

## Usage

```clojure
(require '[kotoba.net.gossip :as gossip])

(def state (-> (gossip/empty-peer-state)
               (gossip/add-peer "p1" #{"topic-a"})
               (gossip/add-peer "p2" #{"topic-a"})))

(def cache (gossip/empty-seen-cache 1000))

(gossip/route-message state cache
  {:topic "topic-a" :payload "hello" :from "p1" :self "me" :d 6})
;; => {:seen-cache {...} :forward [{:to "p2" :payload "hello"}]}
```

```clojure
(require '[kotoba.net.bitswap :as bitswap])

(bitswap/respond-to-want #{"cid-1" "cid-2"} #{"cid-2" "cid-3"})
;; => ["cid-2"]

(bitswap/commits-since commit-log (bitswap/make-want-since "graph-1" 1 "cid-head"))
;; => entries with seq > 1
```

## Real TCP transport (`kotoba.net.transport.tcp`)

Everything above is intentionally I/O-free. `kotoba.net.transport.tcp`
(`src/kotoba/net/transport/tcp.cljk`) is the real network-I/O adapter this
repo's own founding scope explicitly deferred: a "gossip node" that
actually moves `kotoba.net.gossip`/`kotoba.net.bitswap` protocol messages
between real peers over real TCP sockets. It's `.cljs`, not `.cljc` — it
only runs under a Node-hosted ClojureScript runtime
([`nbb`](https://github.com/babashka/nbb) in this repo) and is never
loaded by the JVM `kbb -M:test` suite, so it cannot regress the 56
pure-data assertions above.

**Wire framing and socket-pool plumbing come from
[`kotoba-lang/wire`](https://github.com/kotoba-lang/wire)** — the same
shared library [`kotoba-lang/dtn`](https://github.com/kotoba-lang/dtn)'s
own TCP transport already runs on (`kotoba.wire.tcp/start-server!` /
`connect-or-reuse!` / `send-framed!` / `close-all!`). This namespace never
hand-rolls length-prefix framing, buffer accumulation/defragmentation, or
an outbound socket pool — the entire point of depending on `wire` instead
of re-implementing that plumbing a second time.

```clojure
(require '[kotoba.net.transport.tcp :as tcp])

;; Node A: knows about B and C, both subscribed to "topic-a"
(def node-a
  (tcp/start-node! {:node-id "a" :port 5300
                     :peers {"b" {:host "127.0.0.1" :port 5301 :topics #{"topic-a"}}
                             "c" {:host "127.0.0.1" :port 5302 :topics #{"topic-a"}}}}))

;; Real fanout over real sockets -- returns the peers actually written to
(tcp/publish! node-a "topic-a" "hello")
;; => [{:to "b" :payload "hello"} {:to "c" :payload "hello"}]

;; Bitswap want/have and delta-sync round-trip over a real socket
(tcp/want! node-a "b" #{"cid-1" "cid-2"})                              ;; => Promise<vector>
(tcp/request-commits-since! node-a "b" (bitswap/make-want-since "g" 1 "head"))  ;; => Promise<vector>

(tcp/stop-node! node-a)
```

`start-node!` accepts `:have-set` (a `#{cid ...}` this node responds to
`:bitswap-want` requests from, since this transport layer has no idea what
content a real host actually holds — that's host-injected) and
`:commit-log` (a `[{:seq n :cid c} ...]` vector this node answers
`:bitswap-commits-since` delta-sync requests from, same reasoning). See the
namespace docstring for the full contract, including one real gap
discovered in `kotoba.net.gossip` while wiring this up — not fixed by
editing `gossip.cljc` (out of scope for this transport work; worked around
entirely from `kotoba.net.transport.tcp` instead):

1. `content-hash`'s `:cljs` branch calls a real Google Closure Library
   class (`goog.crypt.Sha256`) that a full Closure-Compiler build
   (shadow-cljs) provides for free but plain `nbb` does not bundle.
   `src/goog/crypt/Sha256.cljk` is an nbb-classpath-only shim (Node's
   built-in `node:crypto`, no npm dependency — the same pattern
   `kotoba-lang/dtn`'s `kotoba.dtn.auth` already uses for its own
   HMAC-SHA256 under nbb) that supplies exactly the two methods
   `content-hash` calls, verified against known SHA-256 test vectors.
   `kbb -M:test` and a shadow-cljs build are unaffected — this shim is
   never on either of those classpaths.

A second gap that used to live here has since been **fixed at the source**:
`route-message` used to build its exclude set via the literal `#{from
self}` syntax, which threw `Duplicate key` (real Clojure/ClojureScript/SCI
behavior, reproduced identically under plain JVM `kbb -M -e`, not an
nbb-only quirk) whenever `:from` and `:self` evaluated to the same value —
exactly what a locally-originated `publish!` naturally produces (there's no
previous hop to exclude, only self). `route-message` now builds that set
with `(hash-set from self)`, which silently dedupes equal values instead of
throwing, so `kotoba.net.transport.tcp` no longer needs to route around it
— every call-site hands `route-message` its real `:from`/`:self` values
directly (the `safe-from` workaround that used to live in the namespace
source has been removed).

### E2E demo (`test/kotoba/net/transport/tcp_demo.cljk`)

An executable proof, not a unit test — run it and read the output:

```bash
kbb --backend sci --classpath "src:test:../wire/src:../bytes/src" \
  test/kotoba/net/transport/tcp_demo.cljk
```

(`--classpath` mirrors `deps.edn`'s sibling `:local/root` layout — this
repo checked out next to `kotoba-lang/wire` and `kotoba-lang/bytes`.)

Three scenarios, printing `PASS`/`FAIL` per scenario and a final
`RESULT: N/3 scenarios passed` line (exit 0 iff 3/3):

1. **3-node gossip fanout + dedup, real TCP.** Node A (in-process) knows
   B and C; B and C also know each other (a full mesh, not just A→B) and
   both are spawned as real, separate `nbb` OS processes via
   `bin/net_node.cljk listen` — mirroring `kotoba-lang/dtn`'s own
   strongest-form scenario 1 (spawn a real child process, verify via its
   own stdout, not just a local return value). A `publish!`s one message;
   the demo confirms both B and C actually receive it (grepping each
   child's own stdout for its `NET-GOSSIP-RECV` log line) — and, because B
   and C also gossip to each other, each node genuinely receives a SECOND,
   redundant copy over the wire via the other's re-forward. The demo
   confirms each node's receipt count stays at exactly 1 (not 2), proving
   `route-message`'s seen-cache dedup is real, not just that no redundant
   copy happened to be sent (verified with a negative-control run — the
   dedup-gate log line temporarily forced to always fire — before this
   demo was finalized: the assertion correctly flipped to FAIL with a
   receipt count of 2, confirming it isn't vacuously true).
2. **Bitswap want/have, real TCP.** Node A has a `:have-set`; node B
   `want!`s a set including a CID A doesn't have. The demo confirms B's
   real `:bitswap-have` response over the wire is exactly the intersection
   pure `bitswap/respond-to-want` would compute — the missing CID is
   genuinely excluded, not just locally assumed.
3. **Bitswap delta-sync, real TCP.** Node A has a `:commit-log`; node B
   `request-commits-since!`s from a known sequence point. The demo
   confirms B's real `:bitswap-commits` response is exactly what pure
   `bitswap/commits-since` would compute.

### CLI (`bin/net_node.cljk`)

A minimal demo/dev tool — no config file, no auth, no encryption — used by
the E2E demo above to spawn real listening nodes as separate OS processes:

```bash
kbb --backend sci --classpath "src:../wire/src:../bytes/src" bin/net_node.cljk listen \
  --node-id b --port 5301 \
  --peer a:127.0.0.1:5300:topic-a --peer c:127.0.0.1:5302:topic-a
```

## Test

```bash
kbb -M:test    # pure .cljc — kotoba.net.gossip, kotoba.net.bitswap,
                    # kotoba.net.transport.envelope
kbb -M:lint     # clj-kondo, 0 errors
```

`kotoba.net.transport.tcp` (real socket I/O) is `.cljs`-only and is
exercised by the E2E demo above rather than having its own JVM-runnable
test suite — the same split `kotoba-lang/dtn`'s transport uses. Its
peer-id-resolution and envelope-construction logic is pure enough to
factor out (`kotoba.net.transport.envelope`) and IS covered by
`kbb -M:test`.

## License

Apache-2.0.
