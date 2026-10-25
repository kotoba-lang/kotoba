# ADR: kotoba-net scope — P2P semantics only, no transport

Date: 2026-07-01
Status: Accepted

## Context

`kotoba-lang/kotoba` used to contain a Rust crate `kotoba-net` built on
libp2p: QUIC transport, Noise encrypted handshake, GossipSub pub/sub, and a
bitswap-style block exchange. That crate was deleted in PR #259 as part of a
repo-wide move away from Rust as the semantic source of truth (see
`orgs/kotoba-lang/kotoba/docs/rust-crate-migration.md`): new implementations
are to be CLJC/EDN-first contracts, with native adapters (if any) layered on
top later and never treated as the authoritative semantics.

Re-implementing the *entire* libp2p stack (QUIC, Noise, NAT traversal, real
socket I/O) in Clojure/ClojureScript from scratch is not realistic — that is
transport/crypto/OS-networking engineering, not protocol semantics, and
duplicating it well would be a multi-year undertaking with little payoff
over just calling out to a native adapter later.

## Decision

`kotoba-lang/kotoba-net` implements **only the protocol semantics** as pure,
deterministic, transport-independent functions over plain EDN data:

- **Gossip layer** (`kotoba.net.gossip`): peer/topic state, content-hash
  based dedup via a bounded seen-cache, deterministic fanout peer selection,
  and message routing (`route-message` = dedup + fanout).
- **Bitswap layer** (`kotoba.net.bitswap`): want-list/have-list state,
  want∩have intersection (`respond-to-want`), and a `WantSince` delta-sync
  request applied against a local commit-log (`commits-since`).

Fanout selection is **deterministic** (sorted peer list, capped at degree
`d`), not randomized, so it is unit-testable with exact expected peer sets.
A production adapter that wants randomized/weighted fanout can pre-shuffle
the peer list (e.g. keyed by an epoch seed) before calling `gossip-fanout`;
the selection function itself stays pure and order-driven.

## Explicitly out of scope

- QUIC/TCP/WebRTC transport, socket binding, connection lifecycle.
- Noise/TLS handshake and any transport-level encryption.
- NAT traversal, peer discovery, DHT.
- Wire framing/serialization of these EDN shapes onto actual bytes.
- Tit-for-tat bandwidth accounting / session ledgers for bitswap.

These are left as **future native adapter** work (e.g. a JVM adapter using
Java NIO/QUIC libraries, or a Rust/Go sidecar speaking the same EDN
contract over a local IPC boundary). When/if such an adapter exists, this
CLJC layer remains the semantic source of truth it must conform to — the
adapter is not authoritative, per the org-wide `rust-crate-migration.md`
policy.

## Consequences

- Correctness of dedup/fanout/want-have/delta-sync logic is fully unit
  testable without any network, exactly as required by this repo's tests
  (`test/kotoba/net/gossip_test.cljk`, `test/kotoba/net/bitswap_test.cljk`).
- Anyone building a transport adapter (JVM, browser, native) implements
  *against* this contract rather than re-deriving the semantics themselves.
- No manifest registration is performed by this ADR/commit; `kotoba-net` is
  registered into `manifest/repos.edn` / `manifest/west.yml` by a separate
  process, per the superproject's standing west workflow.
