# org-ietf-turn

[![CI](https://github.com/kotoba-lang/org-ietf-turn/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/org-ietf-turn/actions/workflows/ci.yml)

**TURN relay (RFC 8656) — pure Clojure/EDN protocol core (`.cljc`, JVM +
ClojureScript) plus a real, running UDP relay listener (`.cljs`, Node).**
Closes the STUN-only NAT-traversal gap for 1:1 real-media WebRTC calls
behind symmetric NAT. This repo is the **message layer + credential layer +
relay state model + the listener that actually drives real UDP sockets
with them**: STUN (RFC 8489) parse/encode, ephemeral-credential mint/verify,
MESSAGE-INTEGRITY / FINGERPRINT, the allocation/permission/channel-binding
state machine (RFC 8656 §5-§11), ChannelData framing (§12.4), STUN/
ChannelData datagram classification, and (`kotoba.turn.listener`, see
"The real relay listener" below) a `node:dgram` listener that actually
relays data between a client and a peer end to end. See
`docs/ADR-kotoba-turn-relay.md` for the phase history (the listener was the
one deliberately-deferred piece named there).

This supersedes the Rust `kotoba-turn` crate (`kotoba-lang/kotoba`, removed in
PR #259, 2026-07-01 — see `kotoba-lang/kotoba/docs/rust-crate-migration.md`):
new kotoba protocol implementations are CLJC/EDN-first; a native adapter may
be added later but is never the semantic authority.

```clojure
(require '[kotoba.turn.credential :as cred])

(cred/mint-credential "shared-secret" "alice" 600 1700000000)
;; => {:username "1700000600:alice" :credential "..."}  (base64 HMAC-SHA1)

(cred/verify-credential "shared-secret" username credential now)
;; => true / false (checks expiry AND signature)
```

```clojure
(require '[kotoba.turn.stun :as stun]
         '[kotoba.bytes :as bytes])

(def msg (-> (stun/encode-header {:typ stun/binding-request :length 0 :txid (vec (repeat 12 0))})
             (stun/push-attr stun/attr-software (bytes/utf8-encode "kotoba"))
             stun/set-attr-length
             (stun/append-message-integrity key-bytes)
             stun/append-fingerprint))

(stun/verify-message-integrity msg key-bytes) ;=> true
(stun/verify-fingerprint msg)                 ;=> true
```

```clojure
(require '[kotoba.turn.allocation :as alloc]
         '[kotoba.turn.channeldata :as cd]
         '[kotoba.turn.demux :as demux])

;; Everything below is `now`-injected (a caller-supplied ms timestamp) —
;; nothing in these three namespaces reads a clock or touches a socket.
(def a (alloc/allocate now five-tuple relayed-address))
(alloc/expired? a now)                              ;=> false
(def a (alloc/create-permission a peer-address now)) ;; RFC 8656 §9, own 300s expiry
(alloc/permission-active? a peer-address now)        ;=> true
(def a (alloc/channel-bind a 0x4001 peer-address now)) ;; nil if channel-num out of range
(alloc/peer-for-channel a 0x4001 now)                ;=> peer-address

(cd/decode (cd/encode 0x4001 payload-bytes))         ;=> {:channel-number 0x4001 :data payload-bytes}
(demux/classify-datagram raw-datagram)               ;=> :stun | :channel-data | :unknown
```

```clojure
;; Node only (nbb / any Node-hosted cljs runtime) — the real relay.
(require '[kotoba.turn.listener :as listener])

(-> (listener/start-listener! {:port 3478 :shared-secret "server-side-secret"})
    (.then (fn [handle]
             ;; handle => {:state <atom> :socket <node:dgram socket> :port N :sweep-id N}
             (println "TURN relay listening on" (:port handle)))))
;; ... later:
(listener/stop-listener! handle)
```

## The real relay listener

`kotoba.turn.listener` (`.cljs`, Node-only — real socket I/O only exists on
a Node-hosted ClojureScript runtime, so `kbb -M:test`'s JVM suite never
loads it) is what makes this repo an actually-running TURN relay rather
than a protocol/state library: `start-listener!` binds a real `node:dgram`
UDP socket and, for each received datagram, classifies it
(`kotoba.turn.demux`) and drives the appropriate namespace above with real
bytes off a real wire — Allocate (verified via
`kotoba.turn.credential`/`kotoba.turn.stun`'s MESSAGE-INTEGRITY check),
Refresh, CreatePermission, ChannelBind, Send indications, and ChannelData,
against `kotoba.turn.allocation`'s state machine. On a successful Allocate
it opens a second, per-allocation `node:dgram` socket (the "relayed
transport address") and relays real application data **in both
directions**: client → peer (a Send indication or bound-channel
ChannelData relayed out to the peer) and — just as necessary to prove, and
the direction most integrations get lazy about — peer → client (the
relay socket's own inbound datagrams relayed back to the client as a Data
indication or, when a channel is bound, as ChannelData). A periodic sweep
drops expired allocations. See the namespace's own docstring for the full
design (the "five-tuple simplification" this single-UDP-port listener
uses, the peer-address shapes chosen for permissions vs. channel bindings,
and exactly what's covered).

Proven end to end by `test/kotoba/turn/listener_demo.cljk` — not a unit
test, an **executable demo** against real sockets (mirrors the rigor
`kotoba-lang/dtn`'s `tcp_demo.cljs` established: PASS/FAIL per scenario, a
final `RESULT: N/3 scenarios passed` line, exit 0 iff all pass). It starts
a real listener, a real non-TURN-aware UDP "peer" (a raw `node:dgram`
socket that just echoes whatever it receives), and a real client socket
that hand-builds every STUN message directly from `kotoba.turn.stun`'s
primitives (never by calling the listener's own internal functions — the
only honest way to prove the listener's own parsing/relay logic is real).
Run from this repo's root:

```bash
kbb --backend sci --classpath "src:test:../bytes/src" test/kotoba/turn/listener_demo.cljk
```

(relative `--classpath` entries mean this must run with cwd at this repo's
root, with `kotoba-lang/bytes` checked out as a sibling — same layout
`deps.edn` already assumes.) Three scenarios:

1. Authenticated Allocate → CreatePermission → Send indication: asserts the
   peer's own raw socket actually received the client's payload (hop 1),
   AND that the client's own raw socket actually received a real STUN Data
   indication carrying the peer's echoed reply (hop 2 — the harder
   direction, proven explicitly rather than assumed symmetric).
2. ChannelBind fast path: binds a channel, sends the client → peer leg as
   raw ChannelData (no STUN framing at all), and confirms the peer → client
   return leg arrives as ChannelData too — checked with
   `kotoba.turn.demux/classify-datagram` on the actually-received bytes, not
   just by trusting a decode to succeed, so it's a real proof the fast path
   uses different wire framing, not a re-skin of scenario 1.
3. An Allocate signed with a credential minted under the WRONG shared
   secret is rejected (checked against the listener's own exposed state
   atom: no allocation was created — not just "we got an error response"),
   and a follow-up Send indication from that same unauthenticated address
   relays nothing to the peer.

What the listener deliberately still does **not** cover (same gaps the
founding ADR and every earlier phase already named — this listener does
not silently close any of them):

- The long-term credential mechanism (RFC 8489 §9.2) — only the coturn-style
  ephemeral short-term scheme (`kotoba.turn.credential`) is implemented.
- IPv6 — `kotoba.turn.stun`'s XOR-address codec, and this listener's own
  dotted-quad conversion helpers, are IPv4-only.
- Per-client allocation quotas / DoS / rate limits of any kind.
- `REQUESTED-TRANSPORT` / `DONT-FRAGMENT` / `EVEN-PORT` /
  `RESERVATION-TOKEN` request-validation logic — an Allocate's
  REQUESTED-TRANSPORT attribute, if present, is never inspected; this
  listener always allocates a UDP relay socket.
- Exact RFC 8489 §14.8 ERROR-CODE payload fidelity beyond the minimal shape
  `kotoba.turn.stun/encode-error-code` already provides — no REALM/NONCE
  challenge flow, and error responses never carry MESSAGE-INTEGRITY (only
  a successfully-verified Allocate's success response does). Error
  response TYPES for Refresh/CreatePermission/ChannelBind failures are
  derived locally in the listener via the same `request-type | 0x0110 =
  error-type` arithmetic `kotoba.turn.stun/allocate-error` already encodes,
  since the codec only defines that one dedicated error-type constant.
- TCP or TLS on the client-facing side — the listener's main socket is
  `udp4` only.
- Authentication scope: only the Allocate request is cryptographically
  verified (USERNAME + MESSAGE-INTEGRITY). Refresh / CreatePermission /
  ChannelBind are authorized purely by "does a live allocation exist for
  this client's observed address/port" — narrower than a production TURN
  server (which re-verifies MESSAGE-INTEGRITY on every request). See the
  namespace docstring's "AUTHENTICATION SCOPE" section for the exact
  disclosed threat this leaves open and why it's out of scope for this
  phase.
- `:relay-host` (the address each per-allocation relay socket binds to,
  reported in XOR-RELAYED-ADDRESS) defaults to `127.0.0.1` — correct for
  local dev/the demo above, but a real deployment reaching remote peers
  MUST override it to the server's actual externally-reachable IP (this
  listener does not auto-detect a public IP, the same `--relay-ip`-style
  configuration every production TURN server needs).

## Design

- **Byte-vector and SHA-1/HMAC-SHA1 primitives now live in
  [`kotoba-lang/bytes`](https://github.com/kotoba-lang/bytes)**
  (`kotoba.bytes` / `kotoba.bytes.sha1`), not in this repo. They were
  extracted out of `kotoba.turn.bytes` / `kotoba.turn.sha1` (Phase 1 of a
  shared-lib consolidation across kotoba-lang protocol libraries) because
  neither was actually TURN/STUN-specific — both are generic
  `vector<int 0..255>` byte-vector primitives and a pure, portable SHA-1 +
  HMAC-SHA1 implementation (no platform crypto API, identical code on the JVM
  and in ClojureScript). This repo depends on `kotoba-lang/bytes` via a
  `:local/root` sibling checkout (see `deps.edn`).
- **`kotoba.turn.credential`** — ephemeral TURN credential mint/verify, the
  coturn `use-auth-secret` scheme:
  `username = "<expiry-unix-ts>:<user>"`,
  `credential = base64(HMAC-SHA1(shared-secret, username))`. The HMAC
  primitive is reader-conditional (`:clj` → `javax.crypto.Mac`, `:cljs` → the
  pure `kotoba.bytes.sha1` impl from `kotoba-lang/bytes`); `credential_test.clj`
  cross-checks both branches against the *same* RFC 2202 vector and against
  each other directly to pin them to byte-identical output.
- **`kotoba.turn.stun`** — RFC 8489 20-byte header + attribute TLV iteration
  (4-byte padding), XOR-MAPPED-ADDRESS (IPv4), MESSAGE-INTEGRITY
  (HMAC-SHA1 over the message up to but not including the attribute, with the
  header length field patched first), FINGERPRINT (CRC-32, self-implemented,
  XORed with `0x5354554E`).
- **`kotoba.turn.allocation`** — the RFC 8656 §5-§11 allocation / permission /
  channel-binding **state model**: a plain EDN map per allocation
  (`:turn/five-tuple` `:turn/relayed-address` `:turn/expiry`
  `:turn/permissions` `:turn/channel-bindings`), plus pure functions
  (`allocate` `expired?` `refresh` `create-permission` `permission-active?`
  `channel-bind` `refresh-channel-binding` `channel-for-peer`
  `peer-for-channel`). Every function is deterministic and `now`-injected
  (a caller-supplied ms timestamp) — same discipline as `kotoba.turn.stun`
  and the deleted Rust reference implementation's `allocation.rs`. This
  namespace owns nothing: callers store/index allocations themselves and
  garbage-collect anything `expired?` reports true for. It does **not**
  relay any data — there is no socket I/O anywhere in this repo.
- **`kotoba.turn.channeldata`** — RFC 8656 §12.4 ChannelData framing
  (`encode`/`decode`): the lightweight binary format TURN uses once a
  channel is bound, distinct from a full STUN message. 4-byte header
  (channel number + length, big-endian) + payload, padded to a 4-byte
  boundary the same way `kotoba.turn.stun/push-attr` pads STUN attribute
  values. `decode` returns `nil` (never throws) on malformed/too-short
  input.
- **`kotoba.turn.demux`** — RFC 8656 §12.4's datagram classification
  (`classify-datagram`): a listener multiplexes STUN and ChannelData on one
  port and must tell which is which before parsing either. Implements the
  real bit-level check (RFC 8489 §5: STUN's leading 2 bits are always `00`;
  a valid channel number's leading 2 bits are `01`), not a length guess or
  try/parse/fallback — see the namespace docstring for the exact reasoning.
- **`kotoba.turn.listener`** (`.cljs`, Node-only) — the real `node:dgram`
  UDP relay listener that wires every namespace above together against
  actual sockets. See "The real relay listener" above for what it does and
  what it deliberately still doesn't.

## Scope

In scope: STUN message codec, ephemeral-credential mint/verify,
MESSAGE-INTEGRITY / FINGERPRINT, the allocation/permission/channel-binding
state machine (RFC 8656 §5-§11), ChannelData framing (§12.4), STUN/
ChannelData datagram classification, and (as of `kotoba.turn.listener`) a
real UDP client↔relay↔peer data path, allocation lifecycle, permissions,
and channel binding driven by actual `node:dgram` sockets. **Out of scope
(still deferred, per `docs/ADR-kotoba-turn-relay.md` and
`kotoba.turn.listener`'s own namespace docstring):** the long-term-credential
mechanism (RFC 8489 §9.2), IPv6 XOR-addresses, per-client allocation
quotas/DoS limits, the `REQUESTED-TRANSPORT`/`DONT-FRAGMENT`/`EVEN-PORT`/
`RESERVATION-TOKEN` request-validation logic around allocation creation,
exact RFC 8489 §14.8 ERROR-CODE payload fidelity beyond a minimal shape, and
TCP/TLS on the client-facing side (UDP only). See "The real relay listener"
above for the full, current list — **this repo is now an actually-running
TURN relay** (proven end to end by `test/kotoba/turn/listener_demo.cljk`),
not merely the protocol + state contract a listener would implement
against.

## Correctness

`kbb -M:test` (cognitect test-runner), 41 tests / 94 assertions
(unaffected by the listener — it's `.cljs`, which this JVM test runner
never loads): STUN header round-trip + attribute TLV parse/padding/overrun
+ XOR-MAPPED-ADDRESS (RFC 5769 §2.2) + MESSAGE-INTEGRITY round-trip/
tamper-detect (survives a trailing FINGERPRINT) + FINGERPRINT round-trip/
corruption-detect (CRC-32/IEEE check value `0xCBF43926`) + credential
mint/verify round-trip, tamper/wrong-secret/malformed-username rejection,
expiry-boundary (`>=` inclusive), and the `:clj`/`:cljs` HMAC-SHA1 branches
cross-checked against each other and against an RFC 2202 §3 vector
(SHA-1/HMAC-SHA1's own FIPS 180-1 + RFC 2202 vector suite lives in
`kotoba-lang/bytes`); allocation lifetime/expiry/refresh (including
refresh-with-lifetime-0 deleting via `nil`), permission independent-expiry,
channel-bind range validation and both-direction expiry-aware lookup;
ChannelData encode/decode round-trip (including a non-4-aligned payload
and a zero-length payload) and malformed/truncated/invalid-channel-number
rejection; datagram classification of a real `kotoba.turn.stun`-encoded
message, a real `kotoba.turn.channeldata`-encoded message, and
garbage/short/wrong-leading-bits input.

`kbb -M:lint` (clj-kondo), 0 errors / 0 warnings across `src` and
`test` (including the `.cljs` listener/demo — see `.clj-kondo/config.edn`
for the `promesa.core/let` → `clojure.core/let` `:lint-as` hint this
requires, the same fix `kotoba-lang/dtn`'s own `.clj-kondo/config.edn`
applies for its structurally identical `p/let`-based demo).

`kbb --backend sci --classpath "src:test:../bytes/src" test/kotoba/turn/listener_demo.cljk`
— see "The real relay listener" above for what its 3 scenarios prove;
`RESULT: 3/3 scenarios passed`, exit 0.

## License

Apache-2.0.
