# io-ipni-specs

**InterPlanetary Network Indexer** — Advertisement / EntryChunk / SignedHead
IPLD, metadata codecs (especially `0x0920` `transport-ipfs-gateway-http`),
the announce message, and injected HTTP clients for `PUT /announce`,
`GET /cid/{cid}`, and `GET /routing/v1/providers/{cid}`. Portable `.cljc`.
No crypto, no sockets, no clock.

Origin plane of [ipni.io](https://ipni.io) (GitHub org `ipni`). Production
indexer is [cid.contact](https://cid.contact); that host is not the spec
authority. ipni.org is a plant-name index and a different thing.

ADR: `ADR-2608160300`.

## What this is, and what it is not — read this first

| | status |
|---|---|
| CID → provider discovery | **yes** — an index, not identity |
| Advertisement chain a publisher serves | **yes** — `ipni.ad` |
| HTTP announce to an indexer | **yes** — `ipni.advertise`, injected `http-fn` |
| `GET /cid/{cid}` with ContextID / Metadata | **yes** — `ipni.find/get-cid` |
| Delegated Routing V1 providers | **yes** — `ipni.find/find-providers` |
| **this process being an IPNI indexer** | **no** |
| **this process being a DHT node** | **no** |
| gossip `/indexer/ingest/mainnet` | **no** |
| `kotoba.protocol.discover` algebra | **no** — that stays in kotoba-protocol |
| pinning worker pin→advertise wiring | **no** — pinning owns that |
| public URI / UnixFS path / peer-ID custody | **no** |

A record in this library does not change the content CID. Public identity
stays `ipfs://{cid}`. IPNI never appears in that URI.

## The announce wire form, measured

Sent to production `https://cid.contact/ingest/announce` on 2026-08-20; the
right column is what came back. All three shapes were wrong in this library
before, and each fails as a bare HTTP 400 — a publisher recording only the
status code would log `:rejected` and learn nothing.

| sent | cid.contact answered |
| --- | --- |
| `{"cid": "bafk…"}` | `json: cannot unmarshal string into Go value of type struct { CidTarget string "json:\"/\"" }` |
| `{"addrs": ["/dns4/host/tcp/443/https"]}` | `illegal base64 data at input byte 10` |
| an address with no `/p2p/` | `invalid p2p multiaddr` |

So `cid` is a dag-json link `{"/": "bafy…"}`, `addrs` are base64 of the
**binary** multiaddr, and every publisher address must carry
`/p2p/{peer-id}` — the indexer attributes a chain to a peer, not to a host.

`addr-encode-fn` is injected (`multiformats.multiaddr/->octets` is one)
because parsing a multiaddr needs a table this library does not depend on.
Base64 is here, because the wire is what this namespace owns; it is checked
against Node's encoder by a golden vector rather than against itself.

**`/p2p/{peer-id}` means a publisher identity is required before anything
can be announced.** That is not wired yet — see ADR-2608160300.

## Modules

| ns | role |
|---|---|
| `ipni.metadata` | multicodec identifiers; `0x0920` gateway-http |
| `ipni.ad` | Advertisement + EntryChunk. `:mutates-cid? false` |
| `ipni.announce` | announce message. `:ad-cid` ≠ content CID |
| `ipni.head` | SignedHead. `sign-fn` injected |
| `ipni.http` | `/ipni/v1/ad/{cid}`, `/head`, `/cid/{cid}`, announce URLs |
| `ipni.find` | query client. Default indexer `https://cid.contact` |
| `ipni.advertise` | putter for `discover/advertise-live` |
| `ipni.hamt` | HAMT-as-set is specified; not implemented. Not an empty success |

## Seams (existing, not moved)

Lookup today is still kad:

```text
(lookup-live cid
  (fn [cid]
    (kad.routing/find-providers http-fn cid opts)))
```

`kad.routing` default-routers may include `https://cid.contact/routing/v1`.
Gateway fetch only needs routing v1. Switch the finder to
`ipni.find/get-cid` when ContextID / Metadata are required.

Advertise production write is the advertisement chain, not historic
Bitswap `PUT /providers`:

```text
(advertise-live rec
  (fn [rec]
    (ipni.advertise http-fn rec opts)))
```

`kotoba.protocol.discover` requires neither kad nor ipni. Finder and
putter are injected.

## Transport is injected

`http-fn` is `(fn [{:keys [method url headers body]}] -> {:status :headers :body})`.
`hash-fn` turns encoded advertisement bytes into the advertisement CID.
`sign-fn` / `encode-fn` / `put-fn` / clocks are the caller's. A library
that owned them would be untestable without one, and would forge a
protocol the way a kad-owned IPIP-0526 signer would.

## Publisher vs retrieval addresses

An advertisement's `Addresses` are retrieval multiaddrs (for kotobase:
`/dns4/ipfs.kotobase.net/tcp/443/https`). An announce message's `addrs`
are where the indexer `GET`s `/ipni/v1/ad/{ad-cid}`. Mixing them makes
the indexer 404 the chain.

## Default announce URL

Spec name: `PUT /announce`. Production cid.contact ingest:
`https://cid.contact/ingest/announce`. `ipni.http/announce-url` defaults
to the production ingest path so a first call is not a 404 dressed as a
pass. Override `:path` if you are talking to a spec-shaped indexer.

## Tests

```bash
kbb -M:test
kbb -M:lint
```
