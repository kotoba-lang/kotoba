# ADR — Pure-Rust TURN relay for real-media calls (`kotoba-turn`)

Status: **Accepted — socket-free core implemented; listener shell pending**
Context: 1:1 real-media WebRTC calling shipped as `@etzhayyim/kami-engine-sdk/call`
(browser owns the media plane; `kotoba-rt` relays SDP/ICE). STUN alone is not
enough for production — this ADR specifies the relay that closes the gap.

## 0. Implementation status (2026-06-09)

The entire socket-free core of `kotoba-turn` is implemented and unit-tested
(`cargo test -p kotoba-turn` → 28 tests, pinned to RFC 2202 / RFC 5769 / CRC-32
vectors):

| Module | Status | Verified by |
|---|---|---|
| `lib.rs` — ephemeral-credential mint/verify (HMAC-SHA1) | ✅ done | RFC 2202 vector, shared byte-for-byte with the JS SDK |
| `stun.rs` — header, attribute TLV, XOR-MAPPED-ADDRESS, MESSAGE-INTEGRITY, FINGERPRINT | ✅ done | RFC 5769 §2.2 + CRC-32 check value |
| `allocation.rs` — 5-tuple allocations, permissions, channels, expiry/GC | ✅ done | state-machine unit tests |
| `channel.rs` — ChannelData framing + STUN/ChannelData demux | ✅ done | round-trip + demux tests |
| `server.rs` — datagram classify + method classify + auth gate | ✅ done | auth accept/reject/stale tests |
| UDP/TCP listener shell + relay-port pool + packet forwarding | ⬜ pending | integration/manual (out of unit-test scope) |

The JS client side (`mintTurnCredential` / `buildIceServers`) already consumes
this scheme; the only work left to take 1:1 calls past STUN-only reachability is
the thin async I/O shell that drives `server.rs` + `allocation.rs` over real
sockets.

## 1. Problem

A WebRTC call needs an ICE path between peers. With only STUN (host +
server-reflexive candidates), ~10–20% of real-world pairs fail to connect:
symmetric NAT, carrier-grade NAT (CGNAT), and restrictive corporate firewalls
have no direct path. The fix is a **TURN relay** (RFC 8656 / RFC 5766): a server
both peers can reach that forwards their media. It is the single biggest blocker
to taking 1:1 calls beyond LAN/demo.

`kotoba-net` already runs a libp2p **QUIC** stack, but that is the data/graph
transport — it does not speak STUN/TURN and a browser `RTCPeerConnection` cannot
use it as an ICE server. TURN is its own UDP/TCP/TLS protocol and must be served
as such.

## 2. Goals / Non-goals

**Goals**
- A pure-Rust TURN server crate `kotoba-turn` (no coturn dependency), consistent
  with the existing Rust/WASM stack and our supply-chain story.
- Short-lived, per-room credentials so a leaked credential cannot relay forever.
- Deployable on a `donated-mesh` supernode (the same tier that would later host
  an SFU), not required to be browser-local.
- A clean client contract: the call SDK receives `iceServers` (incl. TURN) and
  needs no other change.

**Non-goals**
- Not an SFU. TURN only relays a peer-to-peer flow; multi-party fan-out is a
  separate ADR (pure-Rust SFU).
- Not PSTN/SIP media. Telecom interconnect stays a separate track.
- No TURN-over-QUIC experiment in v1 (RFC interest exists; defer).

## 3. Design

### 3.1 Crate `kotoba-turn`

```
crates/kotoba-turn/
  src/
    lib.rs        # ephemeral HMAC credential mint/verify (DONE)
    stun.rs       # RFC 8489 header + attribute TLV + XOR-MAPPED-ADDRESS
                  #   + MESSAGE-INTEGRITY (HMAC-SHA1) + FINGERPRINT (CRC-32) (DONE; RFC 5769/CRC vectors)
    allocation.rs # 5-tuple allocations, permissions, channel bindings, expiry/GC (DONE; pure state machine)
    channel.rs    # ChannelData framing (RFC 8656 §12.4) + STUN/ChannelData demux (DONE)
    server.rs     # socket-free request core: datagram demux + method classify
                  #   + ephemeral-credential authenticate gate (DONE)
    # remaining:
    # the thin socket shell: UDP/TCP recv loop + relay-port pool that drives
    # server.rs's decisions and allocation.rs (integration-tested, not unit)
```

Recommended base: build on the well-audited **`webrtc-rs/turn`** + `stun`
crates rather than hand-rolling the STUN codec (matches the pure-Rust SFU choice
of `str0m`/`webrtc-rs`). `kotoba-turn` wraps them with our auth and config.

### 3.2 Transports

- **UDP** `:3478` — primary relay transport.
- **TCP** `:3478` — fallback for UDP-blocked networks.
- **TLS (TURNS)** `:5349` — required to traverse firewalls that only allow 443;
  reuse the node's existing TLS cert. (`turns:host:443?transport=tcp` is the
  candidate that gets through almost everywhere.)

### 3.3 Authentication — ephemeral credentials

Do **not** ship static TURN passwords. Mirror the coturn `use-auth-secret`
scheme (the de-facto WebRTC standard, RFC 7635 flavored), keyed off the SAME
shared secret the realtime control plane already uses:

```
username  = "<expiry_unix>:<room>:<player>"     # expiry-prefixed, room/player scoped
password  = base64( HMAC_SHA1( RT_TURN_SECRET, username ) )
```

The Worker (or node) that already mints room tokens (`RT_TOKEN_SECRET`) gains a
sibling `RT_TURN_SECRET` and a tiny endpoint returning
`{ urls, username, credential, ttl }`. `kotoba-turn` validates the HMAC and the
expiry on every allocation — no per-user state, no database. A credential is
typically valid for the call's lifetime + slack (e.g. ttl 1h).

### 3.4 Allocation lifecycle

Standard TURN: `Allocate` → `CreatePermission` / `ChannelBind` → relayed data →
`Refresh` (keepalive) → timeout/`Refresh(lifetime=0)` to free. Enforce per-node:
- max allocations, max bytes/s and total bytes per allocation (anti-abuse),
- idle timeout (default 600 s, refreshed by client keepalive),
- relay-port range bounded to a configured pool.

## 4. Client contract (call SDK)

Already supported — `createKotobaCall({ iceServers })`. The app fetches
ephemeral creds and passes:

```ts
const { urls, username, credential } = await fetch('/xrpc/…turn.creds').then(r => r.json());
const call = createKotobaCall({
  endpoint, room, player, token,
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls, username, credential }, // e.g. ["turn:node:3478","turns:node:443?transport=tcp"]
  ],
});
```

`iceTransportPolicy: 'relay'` can be set to force-test the TURN path in CI/staging.

## 5. Deployment

- Runs on a public-IP `donated-mesh` supernode (needs a routable address; pure
  browser-local nodes cannot serve TURN).
- One relay per region keeps RTT low; the creds endpoint returns the nearest.
- Metrics: active allocations, relayed bytes, allocation failures, auth
  rejections → existing observability.

## 6. Phasing

0. **v0 auth core — DONE.** `crates/kotoba-turn` ships `mint` / `verify` /
   `hmac_sha1_base64` (HMAC-SHA1, expiry + scope, constant-time check). A shared
   RFC 2202 vector pins it byte-for-byte to the SDK's `mintTurnCredential`, so a
   credential minted in either runtime verifies in the other. No network layer
   yet (deps: `hmac` + `sha1` + `base64` only).
1. **v0 listeners** — wrap `webrtc-rs/turn`, UDP + TCP, wire the auth core into
   the `Allocate` handler, single node, env-configured. Creds endpoint in the
   control plane.
2. **v1** — TLS/TURNS on 443, quotas + idle GC, metrics, multi-region creds.
3. **v2** — co-locate with the pure-Rust SFU supernode; shared auth + deploy.

## 7. Testing

- Unit: STUN codec round-trips; HMAC cred accept/reject incl. expiry.
- Integration: spin `kotoba-turn` in-process; drive an `Allocate` →
  `ChannelBind` → relayed datagram loopback over UDP and TCP.
- E2E: two headless Chromium with `iceTransportPolicy:'relay'` forced to the
  local relay — proves the SDK ↔ relay contract end to end.

## 8. Security

- Constant-time HMAC verify; reject expired/wrong-room/wrong-player usernames.
- Bind relay ports to the configured pool only; never relay to private/loopback
  ranges (SSRF guard).
- Per-allocation byte/rate quotas to bound abuse; alarm on auth-reject spikes.
- `RT_TURN_SECRET` is node-side only; rotate independently of `RT_TOKEN_SECRET`.

## 9. Alternatives considered

- **coturn** — battle-tested but a C dependency that breaks the pure-Rust /
  supply-chain story; rejected for the default path (still a valid stop-gap).
- **TURN over the existing QUIC stack** — appealing reuse, but browsers can't
  use it as an ICE server today; deferred.
- **Public/managed TURN (Twilio, Cloudflare Calls)** — fastest to working
  calls; acceptable interim, but recurring cost and an external dependency the
  donated-mesh model is meant to avoid.
