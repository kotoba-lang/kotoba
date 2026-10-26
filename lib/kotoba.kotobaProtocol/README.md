# Kotoba Protocol

The normative ownership map and executable algebra for Kotoba's sovereign,
content-addressed application and data stack. It is spec-first, portable
`.cljk`, and has zero runtime dependencies.

This repository owns declarations, pure validation, and tests. Implementations
live in focused sibling repositories. It does **not** open sockets, run a DHT,
persist a database, hash graph commits, or verify CACAO signatures. Those
boundaries are deliberate: drift between the declared model and its consumers
must become visible in tests rather than creating a second implementation here.

Architecture decisions: ADR-2607071500, ADR-2608145100, ADR-2608145200, and
ADR-2608145800 in the [`com-junkawasaki/root`](https://github.com/com-junkawasaki/root)
superproject.

## Start here

The five-stage hash-addressed object network is a path through the larger model:

```text
identity        content hash / CID          docs/identity.md
    ↓
structure       DAG / two link kinds        docs/content-protocol.md
    ↓
mutable name    ref / IPNS / branch         docs/naming.md
    ↓
discovery       DHT / IPNI / gossip         docs/discovery.md
    ↓
transport       TCP / QUIC / WebRTC / Tor   docs/transport.md
```

A path is never identity at any stage. The canonical public resource forms are
`ipfs://{cidv1-base32}` for immutable identity and `ipns://{k51}` for a mutable,
key-derived name. HTTPS is a retrieval location, not proof that two resources
are identical.

## Eight orthogonal planes

The communication planes are orthogonal to the L0-L5 data ladder. URL, DNS,
HTTP, Git, package-manager, and RPC concerns must not be collapsed into one
Merkle DAG.

| Plane | Contract | Algebra | Live seam |
|---|---|---:|---:|
| identity | [Identity](docs/identity.md) | ready | n/a |
| naming | [Naming](docs/naming.md) | ready | ready |
| routing | [Routing](docs/routing.md) | ready | ready |
| discovery | [Discovery](docs/discovery.md) | ready | ready |
| transport | [Transport](docs/transport.md) | ready | blocked on a DHT-node transport |
| session | [Mux and head](docs/mux-and-head.md) | ready | blocked on transport |
| authorization | [Who may write](docs/who-may-write.md) | ready | n/a |
| content protocol | [Content protocol](docs/content-protocol.md) | ready | n/a |

`ready` for a live seam means the pure protocol accepts an injected adapter; it
does not mean this process has become a network node. The machine-readable
authority is `kotoba.protocol.layers/planes`, `link-kinds`, and
`plane-maturity`.

## L0-L5 data ladder

| Layer | Responsibility | Implementation owners |
|---|---|---|
| L0 address | bytes to CID | `io-multiformats`, `io-ipld`, `dag-cbor` |
| L1 fact | append-only datoms, including overlay edges | `datom` |
| L2 graph | ordered action log and committed graph CID | `chain`, `kotobase-peer`, `prolly-tree`, `mst`, `arrangement` |
| L3 authority | `did:key`, key-derived IPNS, CACAO write authority | `org-chainagnostic-cacao`, `org-ietf-ed25519`, `tech-ipfs-specs-ipns` |
| L4 distribution | retrieval, pinning, B2 offload, provider discovery, IPNS publish/resolve | `kotobase`, `ipfs-pinner`, `io-libp2p-specs-kad-dht` |
| L5 application | actor execution, app manifests, appviews, embeds | `kototama`, `wasm-webcomponent`, this repository |

Agent-centric reading (proposed in root ADR-2610082200, not yet implemented):
L2 also holds each cell's source chain (糸 ito, built on `chain`), L4 also
holds the per-mon DHT (布 nuno, keyed on `io-libp2p-specs-kad-dht`) next to
the yataverse bytes lake, and L5's app manifest becomes the kotoba app (kind
`:app`, roles, UI, `:provides` / `:requires`). `kotobase-peer` has been feature
frozen since 2026-08-04 and does not take new L2 behaviour.

The L2 graph CID is supplied by an injected `chain.core/commit!`-shaped
function. `kotoba-protocol` does not hash it. An archive `Location` may be the
raw CID of the same bytes, while the graph identity CID may use another codec;
codec choice does not turn a location into identity.

## Two link kinds

The model preserves both forms instead of pretending they are interchangeable:

| Kind | Stored in | Parent CID | Analogues |
|---|---|---|---|
| `:merkle` | block content | changes | IPLD link, Git tree, Nix closure |
| `:action` | signed metadata | unchanged | Holochain CreateLink, datom assertion, IPNS pointer |

Adding a Merkle child produces a new parent object and therefore a new parent
CID. Adding an action/overlay edge advances the ordered action log while the
referenced object remains unchanged. `kotoba.protocol.graph` makes this
distinction executable and rejects a different body or link set under the same
CID with `:cid-mismatch`.

## Executable surface

- `kotoba.protocol.layers` — layers, planes, link kinds, ownership, maturity
- `kotoba.protocol.boundary` — judgment-free boundary wire declaration (`:kotoba.lisp-machine/boundary-v1`): value/message/receipt canonical forms (tagged dag-cbor), write order canonical-bytes → CID, the six inherited boundary rules. Declarations only; codecs stay with io-ipld/dag-cbor, judgments stay with rule Form and grant.
- `kotoba.protocol.ref` — strict `ipfs://` and `ipns://` public references
- `kotoba.protocol.cid` — CIDv1/sha2-256 parsing and digest comparison; no hashing
- `kotoba.protocol.address` — output- versus input-addressed identity
- `kotoba.protocol.graph` — Merkle nodes, overlay actions, walks, log commits
- `kotoba.protocol.sealed` — client-held confidentiality composition (envelope + org-signal + IPNS mailbox); no crypto runtime
- `kotoba.protocol.surfaces` — URL/DNS/HTTP/Git/package/RPC plane projections
- `kotoba.protocol.discover` — provider-record algebra and injected discovery
- `kotoba.protocol.route` — peer lookup without rewriting the requested peer ID
- `kotoba.protocol.naming` — IPNS lookup/publish without rewriting the name
- `kotoba.protocol.govern` — fail-closed overlay-write admission
- `kotoba.protocol.transport` — multiaddr hops; deliberately no socket dialer
- `kotoba.protocol.mux` — authenticated stream and causal head as separate coordinates
- `kotoba.protocol.vocab` — `:kotoba.actor/*`, `:kotoba.graph/*`, `:kotoba.app/*`, and `:kotoba.link/*`
- `kotoba.protocol.app` — signed, history-bearing L5 app manifests and capability requests. Optional `:kotoba.app/cells` entries map app-local reverse-DNS IDs to CIDv1/dag-cbor DNA bundle CIDs; runtime owns agent-specific cell creation and admission.
- `kotoba.protocol.install` — domain-to-release identity checks, install-lock identity, publisher/sequence update checks, explicit capability-consent deltas, cell-migration gates, and offline launch decisions. It consumes verified adapter facts; it does not verify signatures or retrieve content. See [the app installation contract](docs/app-installation.md).
- `kotoba.protocol.bridge` — host-mediated capability messages for embedded apps
- `kotoba.protocol.a2a` — A2A v1.0 Agent Card, text-task admission, Task and JSON-RPC projections
- `kotoba.protocol.slim` — authority-free, idempotent A2A-over-AGNTCY-SLIM application envelopes

The naming, routing, and discovery live functions normalize injected adapter
results and fail closed on identity mismatches. Transport and session live
operations return named blocked states; they do not fake network maturity.

## Repository boundaries

- [`kotoba-lang/kotoba-lang`](https://github.com/kotoba-lang/kotoba-lang) owns the language specification, grammar, public CLI contract, and conformance.
- [`kotoba-lang/kotoba`](https://github.com/kotoba-lang/kotoba) owns the installable CLI, runtime/host implementations, providers, and integration qualification.
- [`kotoba-lang/kotobase`](https://github.com/kotoba-lang/kotobase) owns the persistent Datalog and content-addressed database.
- [`kotoba-lang/kototama`](https://github.com/kotoba-lang/kototama) owns component admission and capability binding at execution.
- [`kotoba-lang/atprotocol`](https://github.com/kotoba-lang/atprotocol) is an AT Protocol projection over this model, not this repository's core.
- `io-libp2p-specs-kad-dht`, `io-libp2p-specs-transport`, `noise`, `org-chainagnostic-cacao`, `org-ietf-ed25519`, and `tech-ipfs-specs-ipns` own their focused network or cryptographic implementations.
- [`kotoba-lang/envelope`](https://github.com/kotoba-lang/envelope) owns object-at-rest encryption (Storj-Uplink analog). [`kotoba-lang/org-signal`](https://github.com/kotoba-lang/org-signal) owns X3DH + Double Ratchet. IPFS/IPLD/IPNS core specs do not.

## Development

```bash
kbb -M:test
kbb -M:lint
```

The test suite is the executable drift detector for the declared boundaries.
New behavior should strengthen a named plane or layer without importing a
network runtime into this repository.

## 日本語概要

`kotoba-protocol` は、Kotoba の content-addressed application/data stack における
層・通信面・責務分離の正本です。このrepoはpure `.cljk` の宣言・代数・検証のみを
持ち、DHT node、socket、永続DB、暗号鍵管理を実装しません。日本語から参照する場合も、
上の英語本文と `kotoba.protocol.layers` のmachine-readable dataを正とします。

## Target-neutral and distributed stack architecture

Owns the orthogonal communication planes and L0–L5 data model, not sockets, a DHT runtime, persistent DB or a consensus implementation. Holochain-inspired agent history/integrity, IPFS/IPLD content/distribution and EVM-inspired deterministic execution/order are composed at explicit boundaries. Missing validation dependencies are unresolved, never accepted by fallback. Policy governance retains explicit decentralized consensus domains.

See the [owner integration guide and dependency direction](docs/stack-architecture.md),
[composition metadata](spec/stack-integration.edn), and
[whole-stack refactor procedure](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-refactor-procedure.md).
The direction is adopted; runtime contract migration and qualification remain
explicit, separately verified work. Tier labels are responsibility axes, not
a single dependency ranking.
