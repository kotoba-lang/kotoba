# io-libp2p-specs-kad-dht

[![CI](https://github.com/kotoba-lang/io-libp2p-specs-kad-dht/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/io-libp2p-specs-kad-dht/actions/workflows/ci.yml)

**libp2p Kademlia DHT** — the keyspace, the `/ipfs/kad/1.0.0` wire messages, the
iterative lookup as a pure state machine, and an **HTTP delegated-routing**
client that reads and writes the real DHT today. Portable `.cljc`; no crypto, no
sockets, no clock.

Built so [`ipns.record`](https://github.com/kotoba-lang/tech-ipfs-specs-ipns)
records can stop resolving through one proprietary registry.

## What this is, and what it is not — read this first

| | status |
|---|---|
| IPNS records that any IPFS implementation validates | **yes** — `tech-ipfs-specs-ipns`'s `ipns.record` |
| records published to and read from the real DHT | **yes**, via `kad.routing` (HTTP delegated routing) |
| resolution that does not depend on one server | **yes** — `kad.routing/resolve` requires a quorum across independently-operated routers, and validates every record itself |
| **this process being a DHT node** | **no** — see below |

A delegated router is an HTTP endpoint that *is* a DHT node and answers on your
behalf. A record published through it is the same signed record, at the same DHT
key, that any Kubo node would fetch, and any peer can resolve it. But you do not
hold a routing table, you answer nobody's queries, and you see the network only
through the endpoints you ask.

That is a real improvement over a single proprietary registry — the records
become interoperable and the routers are replaceable, plural, and run by
different people — and it is **not** the same thing as joining the DHT. Claiming
otherwise is the kind of thing this workspace exists to avoid.

**What full participation still needs**, precisely: multiaddr parsing, a TCP or
QUIC transport, a security handshake (Noise XX — [`kotoba-lang/noise`](https://github.com/kotoba-lang/noise)
already implements the pattern), multistream-select 1.0.0, a stream muxer
(Yamux), and the identify protocol. The **protocol half is here**:
`kad.message` speaks `/ipfs/kad/1.0.0`, `kad.lookup` is the algorithm, and
`kad.table` is the routing table. The gap is transport.

## Modules

| ns | role |
|---|---|
| `kad.key` | record key → DHT key (`SHA-256`), XOR distance, closeness ordering, bucket index |
| `kad.message` | the `/ipfs/kad/1.0.0` `Message` and the libp2p `Record` it carries |
| `kad.lookup` | the iterative α=3 lookup, as `state + responses → state + next-queries` |
| `kad.table` | the k-bucket routing table a *node* keeps, with Kademlia's eviction rule |
| `kad.routing` | HTTP delegated routing (`/routing/v1`): IPNS records **and** CID providers. multi-router with quorum |

## The eviction rule is the eclipse defence

`kad.table` holds `k` peers at *every distance scale* — bucket 0 covers half
the keyspace, bucket 255 a single point — rather than the `k` globally-closest
peers. A table of the closest peers knows nothing about the far half of the
keyspace and cannot route a query there at all.

When a bucket is full, Kademlia §2.2 does **not** evict the oldest peer for the
new one. It pings the least recently seen peer; if it answers, it **stays and
the newcomer is discarded**. That looks backwards until you see what it
defends: long-lived peers are empirically likelier to stay up, and an attacker
who can mint identities must not be able to displace established peers merely
by showing up. A table that evicted on arrival would let anyone replace a
node's entire view of the network — the eclipse attack.

So `note-seen` never evicts on its own. It returns a `:probe` instruction and
waits for `probe-alive` or `probe-dead`. There is a test that fifty fresh
identities cannot take over a table whose incumbents keep answering.

Order inside a bucket **is** the recency record, so there is no separate
timestamp that can drift out of sync with it. And `closest` searches the whole
table rather than the target's own bucket — the bucket index says where a peer
lives, not that it is the closest thing we know.

## Details that fail silently

**There are two byte strings and conflating them is the classic bug.** The
*record key* is `/ipns/<binary multihash>`; the *DHT key* is `SHA-256` of that.
Distance is measured on the second. A node measuring on raw record keys computes
a different topology from the whole network — not an error, just lookups that
return the wrong peers and records stored where nobody queries.

**Hashing is mandatory, not an optimization.** Every IPNS record key shares the
six-octet `/ipns/` prefix — 54 bits of agreement between two arbitrary names, as
the test suite measures. Unhashed, every IPNS name piles into one corner of the
keyspace and Kademlia's guarantees evaporate.

**Progress is measured against the closest peer, not the shortlist.** A round
returning fifty new peers, none closer than the current best, is *no progress* —
that is the termination condition. Measuring "did the shortlist grow" never
terminates on a large network.

**Failed peers are remembered as failed.** Otherwise the closest unreachable peer
is selected every round forever: never marked queried, so always eligible, and
always closest.

**A response answering a different key is detectable, and must be checked.** A
peer may return whatever it likes. Without `key-matches?`, a lookup for one name
can be answered with a valid, correctly-signed record for a *different* name —
every signature check passes and the resolver returns the wrong value. A
signature proves who wrote a record, never which question it answered.

**Quorum counts *validated* records.** `kad.routing/resolve` takes a
`validate-fn` and this library holds no crypto, so it cannot be the thing that
decides a record is genuine. Counting unvalidated records would let any router
win a name by answering first.

**`:not-found` and `:all-routers-failed` are different answers.** The obvious
spelling — "was every failed response a 404?" — returns true when there were no
failures at all, reporting "nobody has this name" for a case where every router
answered and nothing validated. There is a test.

## Usage

```clojure
(require '[kad.routing :as routing] '[ipns.record :as rec])

(routing/resolve http-fn "k51qzi5uqu5d…"
  {:routers ["https://my-kubo.internal/routing/v1"     ; run your own
             "https://delegated-ipfs.dev/routing/v1"]
   :quorum 2
   :validate-fn (fn [octets]
                  (let [r (rec/parse octets)
                        v (rec/validate r name {:verify-fn ed25519-verify
                                                :now-ms (now)})]
                    (when (:valid? v) (:fields v))))
   :select-fn rec/select})
;; => {:ok? true :record {…} :agreed 2 :routers ["https://my-kubo…" …]}
```

`http-fn` is `(fn [{:keys [method url headers body]}] -> {:status :headers :body})`.
No HTTP client is imported: the caller owns the network, the timeouts and the
TLS.

**Providers are an index, not a signed record.** `find-providers` unions
`GET /routing/v1/providers/{cid}` across routers. Quorum counts routers that
*answered*, not peers found. Empty union with quorum met means we asked and
nobody provides — that is not an outage. JSON parsing is injected
(`parse-fn`); this library holds no JSON parser. Tests pass already-parsed
maps as `:body`.

```clojure
(routing/find-providers http-fn "bafybei…"
  {:routers ["https://delegated-ipfs.dev/routing/v1"
             "https://cid.contact/routing/v1"]
   :quorum 1
   :parse-fn parse-json})
;; => {:ok? true :cid "bafybei…" :providers [{:plane :discovery :peer "12D3KooW…"
;;                                           :addrs […] :mutates-cid? false}] …}
```

This process is still not a DHT node.

**Peer lookup is specified.** `find-peers` unions `GET /routing/v1/peers/{peer-id}`
across routers. Spec: 404 is 200 with 0 results. Empty with quorum met means
we asked and nobody knows that peer. This is routing, not discovery — no CID.

```clojure
(routing/find-peers http-fn "12D3KooW…"
  {:routers ["https://delegated-ipfs.dev/routing/v1"]
   :quorum 1
   :parse-fn parse-json})
;; => {:ok? true :asked "12D3KooW…" :peers [{:plane :routing :peer "12D3KooW…" :addrs […] …}] …}
```

**Provide over HTTP is historic, not a routing-v1 write.** The spec
documents `GET /routing/v1/providers/{cid}` and `PUT /routing/v1/ipns/{name}`.
It does not document a vendor-agnostic provide. `provide` talks to
`PUT /routing/v1/providers` (no CID in the path — the CID is in
`Payload.Keys`) with the bitswap envelope IPNI used. This library does
not sign and does not invent a clock. There is **no default sign-fn**:
IPIP-0526 is historic; DAG-JSON vs DAG-CBOR was never settled. Forging
one would be theater. A router that requires a signature returns 400;
that is a rejection, not a silent pass. `encode-fn` is injected; this
library holds no JSON encoder. Succeeds if any router accepted, same
rule as IPNS `publish`.

```clojure
(routing/provide http-fn {:cid "bafybei…" :peer "12D3KooW…" :addrs ["/ip4/…/tcp/4001"]}
  {:routers ["https://delegated-ipfs.dev/routing/v1"]
   :encode-fn encode-json})
;; => {:ok? true :cid "bafybei…" :accepted ["https://delegated-ipfs.dev/routing/v1"] …}
```

**A synchronous `http-fn` is not universal.** A JVM job can supply one; a
Cloudflare Worker cannot — `fetch` there is a Promise and nothing can await it
inside a synchronous function. So the scoring is split out as `routing/score`,
which takes responses **already fetched**:

```clojure
;; Worker: do the fetches concurrently, then score
(-> (js/Promise.all (map fetch-one routers))
    (.then (fn [responses]
             (routing/score responses {:quorum 2 :validate-fn … :select-fn …}))))
```

`resolve` is exactly `score` plus fetching, and a test asserts the two reach
the same verdict from the same inputs. Keeping the scoring pure also means
quorum, validation, selection and the `:not-found` / `:all-routers-failed` /
`:no-valid-record` distinction are testable with no transport at all.

## Test

```
kbb -M:test
```

59 tests / 182 assertions, including a lookup converging over a simulated
200-peer network and one that terminates against a wholly unreachable one.
