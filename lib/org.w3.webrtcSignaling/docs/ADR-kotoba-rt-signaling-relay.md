# ADR: kotoba-rt as a pure CLJC WebRTC signaling relay contract

**Status**: accepted
**Date**: 2026-07-01
**Deciders**: Jun Kawasaki

## Context

`kotoba-lang/kotoba` removed its Rust crate workspace in PR #259
(2026-07-01). Per `docs/rust-crate-migration.md`, the successor policy is:
new implementations are CLJC/EDN-first — the `.cljc` contract is the
semantic authority — and native adapters (Rust, or anything else) may be
reintroduced later only to *host* that contract over a real transport,
never to redefine it.

One of the deleted crates, `kotoba-rt`, implemented a WebRTC signaling
relay: clients in a room exchanged `ClientMsg::Signal` frames (SDP
offer/answer, ICE candidates) that the relay forwarded verbatim — either
to a named peer (`to` present) or broadcast to the rest of the room
(`to` absent). `kami-engine-sdk/src/lib/call/call.ts` is the known client
of this relay (see `90-docs/adr/2606271500-kotoba-stage-obs-live-aozora.md`,
which lists `kotoba-rt` among the components a live-streaming stack
(kotoba-stage / OBS→app-aozora ingestion) depends on for its WebRTC
signaling plane).

## Decision

Reimplement `kotoba-rt`'s routing logic as a standalone repository,
`kotoba-lang/kotoba-rt`, containing only:

- Pure room-membership state (`room-id -> #{client-id}`) and pure
  `join`/`leave`/`apply-event` operations over it.
- A pure `route-message` function: `rooms + signal-message -> deliveries |
  error`. No I/O, no mutable state, no transport.

This is deliberately **not** a WebSocket server. The rationale:

1. **Testability.** The entire routing contract — unicast, broadcast,
   "sender not in room", "recipient not in room", "room doesn't exist" —
   is exercised by ordinary `clojure.test` assertions with zero network
   harness, mocking, or async plumbing.
2. **Portability.** As `.cljc` it runs unmodified on the JVM and in
   ClojureScript (e.g. compiled to a Cloudflare Worker / browser-side test
   double / edge relay), matching the kotoba-lang project-wide preference
   for CLJC contracts over single-runtime native code.
3. **Adapter independence.** Any transport (WebSocket now, WebTransport or
   QUIC later, or a mock harness for kami-engine-sdk client tests) can host
   this contract by wiring socket connect/disconnect to `apply-event` and
   inbound frames to `route-message`, without kotoba-rt ever needing to
   know about sockets.

## Scope

In scope (this repo, this ADR):
- Room membership pure data + operations (`join`, `leave`, `room-members`,
  `in-room?`, `apply-event`, `apply-events`).
- Message routing pure function (`route-message`) with data-valued errors.
- Unit tests covering the full routing contract.

Out of scope (left to a future adapter repo/PR, explicitly not this repo):
- WebSocket (or other transport) server implementation.
- Wire/serialization format for frames.
- TURN/ICE ephemeral credential minting (was `kotoba-turn`, a separate
  former crate — out of scope here too).
- Media-plane (SRTP/DTLS) concerns — `kotoba-rt` only ever relayed the
  SDP/ICE control-plane blobs used to *establish* that transport.
- Persistence/replication of room state across multiple relay instances.

## Consequences

- `kotoba-rt` has no runtime dependencies and no native/FFI surface;
  `deps.edn` is `{:paths ["src"]}` plus a test-runner dev alias.
- Adding a transport later (Rust, Clojure server, edge worker, whatever) is
  additive: it depends on `kotoba-rt`'s pure functions and cannot change
  their semantics without changing this contract and its tests first.
- If `kami-engine-sdk`'s `call.ts` needs a wire-level shape different from
  the `{:type :signal :room-id :from :to? :payload}` EDN map used here,
  that's a serialization-layer concern for the adapter, not this contract.
