# kotoba-lang/knp

KNP: KAMI Network Protocol — a custom UDP-based multiplayer protocol. Zero-dep portable
`.cljc` restored from the legacy `kami-engine/kami-knp` Rust crate (deleted in
`kotoba-lang/kami-engine` PR #82) as part of ADR-2607010930 (`com-junkawasaki/root`,
kami-engine Rust-workspace restoration to CLJC).

Wire format: 5-byte header post-session (7-byte pre-session with `"KN"` magic), 4 channel
kinds (`Unreliable` / `ReliableOrdered` / `ReliableUnordered` / `Voice`).

## What was ported vs. excluded

The original crate had 9 source files. Only the pure state-machine / wire-format logic
(no socket I/O, no real crypto, no browser bindings) was ported:

| Original file        | Status        | CLJC namespace  | Notes |
|-----------------------|--------------|-----------------|-------|
| `lib.rs`              | **Ported** (folded in) | `knp` | Just Rust module wiring (`pub mod`/`pub use` + `#[cfg]` gates), no logic of its own. Its public re-exports became `knp`'s re-exports of the portable surface. |
| `packet.rs`           | **Ported**   | `knp.packet`    | Wire header (5B) encode/decode, `Channel` enum, `Flags` bitflags, packet framing. Pure byte-format logic, no I/O — ported in full. |
| `channel.rs`          | **Ported**   | `knp.channel`   | `ReliableChannel` / `ChannelManager`: per-channel sequence counters, peer-ACK bookkeeping, retransmit-due scheduling. Pure state machine — the Rust file itself performs no socket I/O, so it ported in full (CLJC represents mutation functionally: `(fn state -> [result state'])` instead of `&mut self`). |
| `session.rs`          | **Ported**   | `knp.session`   | `HandshakeState`, `ClientSession`, `SessionManager` (accept/get/assign-entity/broadcast-addrs/prune) + hello/welcome handshake message encode/decode. Pure bookkeeping over an addr-keyed map + byte-format logic — ported in full. The Rust `SocketAddr` key is represented as an opaque CLJC value (any hashable identifier the caller supplies); address parsing/binding itself is native-only and out of scope. |
| `crypto.rs`           | **Excluded** | — | ChaCha20-Poly1305 AEAD via the `ring` crate. No portable data format of its own — the handshake message shapes it *would* need already live in `session.rs`/`knp.session`. The nonce derivation is a trivial LE-counter-in-12-bytes transform, not substantial enough to warrant a module. Real encrypt/decrypt operations have no CLJC equivalent. |
| `socket.rs`           | **Excluded** | — | Platform-abstracted raw UDP socket trait + BSD/PS5/Switch/WebTransport backends. Pure native syscalls/FFI, no portable logic. |
| `client.rs`           | **Excluded** | — | Async I/O event loop (`poll`) driving a real `KnpSocket`. Uses the ported `knp.channel`/`knp.session` logic internally but the loop itself is native-only. |
| `server.rs`           | **Excluded** | — | Async I/O event loop (`poll`/`broadcast`/`relay`) driving a real `KnpSocket`. Same rationale as `client.rs`. |
| `webtransport.rs`     | **Excluded** | — | `wasm_bindgen` browser WebTransport API bindings (`#[cfg(target_arch = "wasm32")]`). JS interop glue, no portable logic of its own beyond what `knp.channel` already covers. |

## Layout

```
src/knp.cljk           ;; root: re-exports the portable public surface
src/knp/packet.cljk     ;; wire packet header + payload framing
src/knp/channel.cljk    ;; 4-channel send/receive/retransmit bookkeeping
src/knp/session.cljk    ;; handshake state machine + hello/welcome messages
```

Binary encode/decode uses `#?(:clj java.nio.ByteBuffer :cljs js/DataView)` reader
conditionals to stay portable across JVM and JS.

## Test coverage

17 tests / 45 assertions, `kbb -M:test`, 0 failures / 0 errors.

- `test/knp/packet_test.cljk` — ports the original `packet.rs` `#[cfg(test)]` block
  (`header_roundtrip`, `packet_roundtrip`) 1:1, plus channel/flags bit-roundtrip and
  short-input coverage.
- `test/knp/channel_test.cljk` — new coverage for `knp.channel` (the original
  `channel.rs` shipped with no unit tests).
- `test/knp/session_test.cljk` — new coverage for `knp.session` (the original
  `session.rs` shipped with no unit tests).
- `test/knp_test.cljk` — namespace-loads smoke test for the root `knp` namespace and
  its re-exported surface.

## Develop

```bash
kbb -M:test
```
