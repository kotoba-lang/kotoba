# ADR: kotoba-turn — CLJC TURN relay protocol core

- Status: accepted
- Date: 2026-07-01
- Repo: `kotoba-lang/kotoba-turn`

## Context

`kotoba-lang/kotoba` shipped a pure-Rust TURN relay crate (`crates/kotoba-turn`,
RFC 8656) for 1:1 real-media WebRTC calls, closing the STUN-only reachability
gap behind symmetric NAT. Its socket-free core (ephemeral-credential
mint/verify, STUN RFC 8489 codec, MESSAGE-INTEGRITY, FINGERPRINT, allocation
state machine, ChannelData framing) was unit-tested (28 tests: RFC 2202 / RFC
5769 / CRC-32 vectors) but the UDP/TCP listener I/O was never finished.

On 2026-07-01, PR #259 deleted the entire Rust workspace
(`kotoba-lang/kotoba`). The successor policy
(`kotoba-lang/kotoba/docs/rust-crate-migration.md`) is: new kotoba protocol
implementations are **CLJC/EDN-first** — native adapters may be added later
for performance, but are never the semantic authority. `kotoba-turn` is
re-founded here as its own repository following that policy, using
`kotoba-lang/cacao` as the repo-structure template (`deps.edn` + `.cljc` +
`clojure.test` + cognitect test-runner + GitHub Actions CI matrix).

## Decision

Re-implement the **message layer** (not the socket layer) as pure `.cljc`
functions, runnable identically on the JVM and in ClojureScript:

1. **`kotoba.turn.bytes`** — byte-vector primitives (`vector<int 0..255>`
   convention, never a platform byte-array) + UTF-8 encode + base64
   encode/decode, all written portably with no reader conditionals, so the
   exact same source runs on both platforms.
2. **`kotoba.turn.sha1`** — pure SHA-1 / HMAC-SHA1, no platform crypto
   dependency. Exists specifically so ClojureScript (browser or Node without
   native crypto bindings) has a working HMAC-SHA1 without a JS dependency.
3. **`kotoba.turn.credential`** — ephemeral TURN credential mint/verify
   (coturn `use-auth-secret`: `username = "<expiry>:<user>"`,
   `credential = base64(HMAC-SHA1(secret, username))`). The HMAC primitive is
   reader-conditional: `:clj` uses `javax.crypto.Mac` (fast, audited), `:cljs`
   uses the pure `kotoba.turn.sha1` implementation. Correctness of the split
   is pinned by testing both branches against the same RFC 2202 vectors *and*
   directly against each other (see `credential_test.clj`).
4. **`kotoba.turn.stun`** — RFC 8489 header + attribute TLV codec,
   XOR-MAPPED-ADDRESS (IPv4), MESSAGE-INTEGRITY (HMAC-SHA1), FINGERPRINT
   (self-implemented CRC-32/IEEE 802.3, `XOR 0x5354554E`).

### What changed vs. the Rust reference implementation

- The Rust `mint`/`verify` used a 3-part username `"<expiry>:<room>:<player>"`
  scoped to a room+player pair (matching `kami-engine-sdk`'s
  `mintTurnCredential`). This repo's task scope specifies a simpler 2-part
  `"<expiry>:<user>"` username. The underlying crypto primitive (HMAC-SHA1,
  base64, coturn `use-auth-secret` shape) is unchanged; only the identity
  payload embedded in the username differs. A room/player-scoped variant can
  be layered on top of `mint-credential`/`verify-credential` (or added as a
  sibling function) without touching the HMAC core, if/when a caller needs
  that shape.
- Byte representation: the Rust implementation used `&[u8]` / `Vec<u8>`
  throughout. This CLJC implementation represents all "bytes" as plain
  Clojure vectors of ints 0-255 (not a platform byte-array), which is what
  makes the STUN/CRC/SHA-1 code identical on both `:clj` and `:cljs` without
  per-platform forks — the only reader-conditional in the whole repo is the
  HMAC primitive itself.

## Remaining / explicitly deferred (follow-up repo work)

- **UDP/TCP/TLS listener I/O.** No socket code in this repo. A listener
  adapter (JVM `java.net.DatagramSocket` / Netty, or a native adapter) is a
  separate follow-up and, per the CLJC-first policy, must treat this repo's
  message-layer functions as the semantic authority rather than
  reimplementing STUN/credential logic natively.
- **Allocation / permission / channel-binding state machine** (RFC 8656
  §5–§11: 5-tuple allocations, permissions, channel bindings, expiry/GC). The
  Rust reference had this (`allocation.rs`, deterministic + `now`-injected);
  it is not yet ported to CLJC.
- **ChannelData framing** (RFC 8656 §12.4) and the STUN/ChannelData demux
  (`classify_datagram` in the Rust `server.rs`). Not yet ported.
- **Long-term credential mechanism** (RFC 8489 §9.2: MD5(username:realm:
  password) key derivation) is not implemented — only the coturn
  ephemeral-secret short-term scheme is. `stun/append-message-integrity` and
  `verify-message-integrity` accept an arbitrary byte-vector key, so a
  long-term-credential key derivation function can be added without changing
  the MESSAGE-INTEGRITY codec itself.
- **IPv6** XOR-MAPPED-ADDRESS/XOR-PEER-ADDRESS/XOR-RELAYED-ADDRESS (family
  `0x02`) — only IPv4 (family `0x01`) is implemented.

## Consequences

- kotoba-turn is usable today as a **credential-minting service** (server
  mints ephemeral TURN credentials for `iceServers`) and as a **STUN message
  codec library** (parse/build STUN messages), both from JVM Clojure or
  ClojureScript, with zero native/platform crypto dependency required on the
  ClojureScript side.
- It is **not yet** a runnable TURN relay server — the socket listener and
  allocation state machine are required before this can replace a coturn-like
  deployment. Treat this repo as the protocol contract that a listener
  adapter (this repo or a sibling) must implement against.
