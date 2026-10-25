# kotoba-dtn

[![CI](https://github.com/kotoba-lang/dtn/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dtn/actions/workflows/ci.yml)

**RFC 9171 Bundle Protocol Version 7 (Delay/Disruption-Tolerant Networking)
primary-block fields, transport-agnostic store-and-forward routing, and
SMS/RCS interop translation — in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library modeling
the records a DTN store-and-carry node keeps: endpoint identifiers (EIDs)
built on [`kotoba-lang/phone`](https://github.com/kotoba-lang/phone)'s
E.164 numbering, RFC 9171 §4.3.1 primary-block fields, direct-neighbor
routing decisions, and the structural seam that lets a DTN-delivered
payload interoperate with real carrier SMS/RCS.

No network, no I/O. This models primary-block *fields* as EDN, not the
CBOR wire format — it does NOT implement CBOR encoding, block CRC,
fragmentation/reassembly, or BPSec (RFC 9172) security blocks (the
`kotoba.dtn.auth` pre-shared-secret HMAC layer described below is a
narrower, honestly-scoped alternative used only by the TCP transport —
not an implementation of BPSec). Routing is an honestly-scoped
**direct-neighbor-or-store heuristic, plus an optional static
single-hop relay via a caller-configured next-hop table** (`:routes`,
see below) — not full Contact Graph Routing (CGR, RFC 9174), not
automatic route discovery/advertisement, and not epidemic/PRoPHET
multi-hop relay. Portable `.cljc`
across JVM / ClojureScript / SCI / GraalVM.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 226 assertions, all green (`kbb -M:test`, pure `.cljc` only — 147 in the original data-model/transport-support namespaces + 28 in `kotoba.dtn.discovery.presence` + 51 in `kotoba.dtn.transport.turn-relay` (37 original + 14 added alongside automatic TURN allocation/permission refresh, see below), see below) |
| Operator console (UI/UX) | yes |
| Export (CSV/JSON) | yes |
| Shared CSS design system | yes (css.core/operator-theme) |
| Internet-overlay transport (real I/O) | yes — plain TCP via nbb, see below; E2E demo green (7/7 scenarios) |
| Durable store (`:store-path`) | yes — disk-backed, survives process restart; not crash-atomic on the rewrite step, see below |
| Bundle integrity (`:peer-secrets`) | yes — pre-shared-secret HMAC-SHA256, tamper-evidence + origin check; NOT a PKI, NOT TLS, see below |
| Replay protection (`:dtn/sequence-number` high-water mark) | yes — per-source monotonic sequence tracking, layered on `:peer-secrets`; **only applies to authenticated peers**; high-water marks persist to disk when `:replay-state-path` is configured (in-memory only, resets on restart, otherwise), see below |
| Multi-hop relay routing (`:routes`) | yes — static/pre-configured single-hop relay via a caller-supplied next-hop table (`router/route-decision`'s `:relay` action), hop-count/`max-hops` loop prevention; NOT automatic route discovery/advertisement, NOT full Contact Graph Routing (RFC 9174), see below |
| Peer discovery (`kotoba.dtn.discovery`, real I/O) | yes — gossip-based presence broadcast/discovery built directly on [`kotoba-lang/io-libp2p`](https://github.com/kotoba-lang/io-libp2p)'s real gossip transport; E2E demo green (3/3 scenarios); NOT a DHT, NOT authenticated (a presence announcement is trusted at face value), polling-based (not push/callback), see below |
| Mesh-radio / satellite transport | no (no hardware in scope; routing logic only, see demo scenario 3) |
| NAT traversal (`kotoba.dtn.transport.udp`, real I/O) | yes — genuinely scoped: a UDP-native sibling transport (`node:dgram`, no TURN by default) plus an OPTIONAL relay path through a real [`kotoba-lang/org-ietf-turn`](https://github.com/kotoba-lang/org-ietf-turn) TURN listener for exactly ONE configured peer per node; E2E demo green (4/4 scenarios, genuinely bidirectional, including a real wall-clock survival proof past the allocation's original expiry window); automatic periodic Allocate + permission Refresh keeps a `:turn-relay` node reachable indefinitely (closing what used to be this namespace's headline gap — see below); NOT full ICE (RFC 8445) — no NAT-type detection, no candidate gathering/connectivity checks, no multi-peer relaying from one node, see below |

## Contract

```clojure
(require '[kotoba.dtn :as dtn])
(require '[kotoba.dtn.link :as link])
(require '[kotoba.dtn.router :as router])
(require '[kotoba.dtn.gateway :as gateway])

(dtn/eid "+819012345678")                          ; => "dtn:+819012345678"

(dtn/bundle "+819012345678" "+12125550199" {:body "hi"})
;; => {:dtn/version 7 :dtn/source "dtn:+819012345678"
;;     :dtn/destination "dtn:+12125550199" :dtn/lifetime-ms 86400000 ...}

(def b (dtn/bundle "+819012345678" "+12125550199" {:body "hi"}))
(def l (link/link "L1" "+12125550199" :mesh-radio :reachable? true))

(router/route-decision b [l])
;; => {:dtn/action :forward :dtn/via {...L1...}}

;; Resilience-first: prefer mesh/satellite over internet when it's down.
(router/route-decision b [l] :priority [:mesh-radio :satellite :internet-overlay])

;; No direct link to the destination, but a caller-configured static route
;; through a reachable next-hop -> :relay (see "Internet-overlay transport" below).
(def b2 (dtn/bundle "+819012345678" "+12125550199" {:body "hi"}))
(def via-relay (link/link "L2" "+447700900123" :internet-overlay :reachable? true))
(router/route-decision b2 [via-relay]
                        :routes [{:dtn/destination "dtn:+12125550199"
                                  :dtn/next-hop "dtn:+447700900123"}])
;; => {:dtn/action :relay :dtn/via {...L2...} :dtn/next-hop "dtn:+447700900123"}

(gateway/bundle->sms b)                            ; unwrap iff SMS-shaped payload
```

## Operator console (UI/UX)

A read-only HTML dashboard renders bundles currently in store and link
reachability, for a node operator. Built on
[`kotoba-lang/html`](https://github.com/kotoba-lang/html) (Hiccup→HTML) +
[`kotoba-lang/css`](https://github.com/kotoba-lang/css) (EDN→CSS). Pure
data → markup; the console never exposes a write surface (no
`<form>`/`<button>`).

```clojure
(require '[kotoba.dtn.ui :as ui])

(ui/dashboard
  {:bundles [(dtn/bundle "+819012345678" "+12125550199" {:body "hi"})]
   :links [(link/link "L1" "+12125550199" :mesh-radio :reachable? true)]})
;; => "<html>...DTN Store-and-Forward — Operator Console...</html>"
```

## Export (CSV / JSON)

Audit-grade CSV (RFC-4180 quoting) and JSON (every RFC 8259 control
character escaped) for bundles-in-store and link reachability.

```clojure
(require '[kotoba.dtn.export :as ex])

(ex/bundles->csv bundles)
(ex/links->csv links)
(ex/bundles->json bundles)
```

## Why

A message shaped like SMS or RCS should be able to egress over whichever
transport link is actually available — internet-overlay P2P, mesh radio,
or satellite — without depending on any single one of them being up, while
staying wire-compatible with real carrier SMS/RCS at the interop seam.
`kotoba-dtn` is that transport-agnostic layer: `kotoba.dtn` models the RFC
9171 envelope a store-and-carry node reasons over, `kotoba.dtn.router`
decides forward-vs-store from whatever links are currently reachable
(with an overridable transport priority, so a resilience-first caller can
deprioritize internet when it's down), and `kotoba.dtn.gateway` is the
structural seam where a `kotoba.phone/sms` record — or an RCS-shaped
message from the independently-built `kotoba-lang/rcs` sibling library —
unwraps from (or wraps into) a bundle payload with no translation step,
because the payload IS that record shape. `kotoba.dtn.gateway` deliberately
never depends on `kotoba-lang/rcs`: RCS interop is checked structurally
(duck-typed on `:rcs/*` keys) so the two libraries stay independently
buildable.

## Internet-overlay transport (real I/O)

Everything above is intentionally I/O-free — pure `.cljc` data and pure
decisions. `kotoba.dtn.transport.tcp` (`src/kotoba/dtn/transport/tcp.cljk`)
is the first namespace in this library that actually moves bytes between
real OS processes: a plain TCP transport for the `:internet-overlay`
`:dtn/transport-kind` that `kotoba.dtn.link` already models. It's `.cljs`,
not `.cljc` — it only runs under a Node-hosted ClojureScript runtime
([`nbb`](https://github.com/babashka/nbb) in this repo) and is never
loaded by the JVM `kbb -M:test` suite, so it cannot regress the 147
pure-data assertions above. (`kotoba.dtn.store` and `kotoba.dtn.auth`,
below, keep the same split: their format/canonicalization logic
(including `kotoba.dtn.auth`'s replay-protection decision functions,
`replay?` / `update-high-water-mark`, and its high-water-mark
serialize/deserialize pair) is portable `.cljc` and covered by
`kbb -M:test`, only the actual disk I/O / HMAC-vs-platform-crypto-module
calls are Node-`.cljs`-specific, behind reader conditionals.)

**Wire framing and socket-pool plumbing now come from
[`kotoba-lang/wire`](https://github.com/kotoba-lang/wire).** This
namespace used to hand-roll its own length-prefix framing directly on
Node `Buffer`s, its own per-connection buffer-accumulation/defragmentation
logic, and its own ad-hoc outbound socket pool — none of it actually
DTN-specific. That generic "move EDN maps over a TCP byte stream"
plumbing has been extracted into `kotoba-lang/wire` (built on
[`kotoba-lang/bytes`](https://github.com/kotoba-lang/bytes)'s portable
byte-vector primitives), so `kotoba-lang/turn`'s future relay I/O could
share it too instead of re-implementing the same mechanics —
[`kotoba-lang/io-libp2p`](https://github.com/kotoba-lang/io-libp2p)'s real
gossip I/O already does (see "Peer discovery" below: this repo's own
`kotoba.dtn.discovery` is a direct consumer of it). This namespace now calls
`kotoba.wire.tcp/start-server!` / `connect-or-reuse!` / `send-framed!` /
`close-all!` for the actual socket I/O. The wire FORMAT itself is
unchanged (still a 4-byte big-endian length prefix + UTF-8 `pr-str`'d EDN
payload — see `kotoba-lang/wire`'s README for the format spec), so this
refactor is provably wire-compatible with everything below — every
DTN-specific behavior (store-and-forward, relay, auth, replay checking)
is untouched; only the low-level "how do bytes get framed and pushed down
a socket" mechanics moved out.

**Scope.** This namespace, in isolation, is still direct internet-overlay
transport only: a peer's host:port must already be known (passed to
`start-node!` as `:peers`) — `kotoba.dtn.transport.tcp` itself never
learns, advertises, or gossips a peer's address on its own. **The
discovery gap this used to name as future work is now closed, at the
`kotoba.dtn.discovery` layer, not here**: that namespace announces a
node's own reachability over, and consumes peer announcements from, a
real [`kotoba-lang/io-libp2p`](https://github.com/kotoba-lang/io-libp2p)
gossip mesh, and populates a *running* node handle's `:peers` (this exact
option) dynamically — see "Peer discovery" below. NAT traversal via a
`kotoba-lang/org-ietf-turn` relay remains explicitly future work **for
THIS namespace specifically** — TURN is UDP-based and this transport is
TCP-based, bridging them is a materially different, larger problem than
gossip-based discovery, and `kotoba.dtn.transport.tcp` itself is
deliberately unmodified (still TCP-only, no TURN awareness). That gap is
now closed at a NEW, separate UDP-native sibling transport instead — see
"NAT traversal" below.
Mesh-radio and satellite transports are **not implemented** — no such
hardware exists in this dev environment — but `kotoba.dtn.router`'s
priority ordering over transport kinds is still real and tested against a
simulated mesh-radio link (see the demo below, scenario 3).

**Wire framing.** Deliberately the simplest thing that works: each message
on the socket is a 4-byte big-endian length prefix followed by that many
bytes of UTF-8 `pr-str`'d EDN (the bundle map `kotoba.dtn/bundle`
produces), decoded on the read side with `clojure.edn/read-string`. As of
the `kotoba-lang/wire` extraction (above), the actual framing/encoding
implementation lives in `kotoba.wire.edn` + `kotoba.wire.framing` — this
namespace only calls it (`encode-frame`, `kotoba.wire.tcp/send-framed!`)
rather than implementing it inline; the format on the wire is identical.

**Resilience.** `route-and-send!` runs the pure `router/route-decision`,
then actually attempts delivery; if the peer refuses the connection right
now (down, unreachable) — which the pure decision has no way to know in
advance — the bundle falls back to the node's `:store` instead of being
lost. `retry-store!` re-attempts every stored bundle (after dropping
anything past its RFC 9171 lifetime) — this is the actual store-and-carry
property the whole design exists for, exercised for real in the demo.

**Durable store (`:store-path`, `kotoba.dtn.store`).** Until recently
`:store` was an in-memory-only atom: a node process crash or restart
silently lost every undelivered bundle, which directly contradicted this
library's own disaster/carrier-outage resilience purpose. `start-node!`
now accepts an optional `:store-path <file>`. When set:

- On startup, `:store` is seeded from that file (`kotoba.dtn.store/load-store`)
  — a restarted node picks up exactly where it left off.
- Every bundle that falls back into `:store` (a failed forward, or no
  reachable link at all) is also durably `append-bundle!`'d to the same
  file, synchronously, in the same step as the in-memory `swap!`.
- After a `retry-store!` pass settles, the file is `rewrite-store!`'d to
  match the node's resulting in-memory `:store` — so delivered/expired
  entries drop out and the log doesn't grow forever.

**Format**: newline-delimited `pr-str`'d EDN, one bundle per line —
human-diffable, and a truncated last line from a crash mid-append can
only ever corrupt that last line (`deserialize-line` returns `nil` for a
blank/malformed line rather than throwing, so it doesn't take down reads
of everything before it).

**What "restart-safe" does and does NOT mean.** `append-bundle!` uses
`fs.appendFileSync`, so a crash mid-append can, at worst, leave one
truncated trailing line — every previously-flushed line survives intact.
`rewrite-store!` (used after a successful `retry-store!` pass) uses
`fs.writeFileSync`, which truncates-then-writes the whole file: **this
one step is NOT crash-atomic** — a crash during that specific call can
leave the file empty or partially written, losing bundles that were
already durably appended earlier in that same rewrite pass (though never
bundles from a completed prior append/rewrite). This is a disclosed
limitation, not a full write-ahead-log with fsync+rename durability —
see `kotoba.dtn.store`'s docstring. When `:store-path` is omitted,
behavior is unchanged from before this option existed (in-memory only).

**Bundle integrity (`:peer-secrets`, `kotoba.dtn.auth`).** The TCP
transport previously had zero authentication: any TCP client could
connect and inject a bundle claiming to be from any `:dtn/source` E.164,
with no way for the receiver to know it wasn't forged. `start-node!` now
accepts an optional `:peer-secrets {e164 secret-string ...}` map — a
pre-shared symmetric secret per peer. When a secret is configured for a
peer:

- Outbound bundles to that peer are `kotoba.dtn.auth/sign-bundle`'d
  (HMAC-SHA256 over the bundle's canonical `pr-str`, with any prior
  `:dtn/signature` stripped before computing) before the frame is
  written to the socket.
- Inbound bundles claiming that peer as `:dtn/source` are
  `verify-bundle`'d before being accepted into `:inbox`. A
  missing/invalid signature is logged and the bundle is **dropped
  outright** — never added to `:inbox`, and never added to `:store`
  either (a rejected forgery is a security event, not a delivery to
  retry later).

When no secret is configured for a given peer — the common case, and the
only case for the existing CLI/demo scenarios 1-3 — behavior is
unchanged from before this option existed: bundles are sent/accepted
unsigned, exactly as before.

**What this does and does NOT protect against.** This is **shared-secret
HMAC-SHA256 per peer, not a PKI, not TLS**:

- DOES detect a bundle whose body was altered after signing
  (tamper-evidence), and reject a bundle claiming a source this node has
  no secret for or one signed with the wrong secret (origin
  authentication within a small pre-configured peer set).
- Does NOT provide a PKI or certificate issuance/revocation system, does
  NOT provide transport-layer confidentiality (bundle bodies still
  travel in cleartext — this only detects forgery, it doesn't hide the
  payload), and is NOT forward-secret (one leaked shared secret
  compromises every bundle signed with it, past and future, until
  rotated).
- Does **NOT** protect against a peer whose secret has actually leaked —
  a holder of the secret can forge indistinguishable bundles.
- **DOES now provide replay protection — but ONLY for authenticated
  peers** (a `:peer-secrets` entry configured for that source). See the
  next section.

An honest tamper-evidence/origin-check for a small pre-configured peer
set — not a general Internet-security solution.

**Replay protection (`kotoba.dtn.auth/replay?` +
`update-high-water-mark`, wired in by `kotoba.dtn.transport.tcp`).** The
bundle-integrity work above closed forgery/tampering but explicitly
disclosed a real, still-open gap: a legitimately-signed bundle, captured
off the wire, could be re-sent later and would be accepted again as if
it were new — the signature is still valid; nothing checked "have I seen
this exact bundle, or an older one from this source, before." This is
now closed, reusing a field `kotoba.dtn/bundle` already had rather than
inventing a new one: `:dtn/sequence-number` (previously always defaulted
to 0 and never actually incremented by any caller). Because
`sign-bundle` signs the ENTIRE bundle map, `:dtn/sequence-number` is
already covered by the signature once `:peer-secrets` is configured for
a peer — an attacker without the shared secret cannot forge a higher
sequence number.

- **Sending side.** Every `start-node!`'d node keeps its own monotonic
  outbound `:next-sequence-number` counter, seeded from `js/Date.now()`
  (wall-clock milliseconds) at startup. Every LOCALLY-ORIGINATED
  `send-message!` call stamps the next value from that counter onto
  `:dtn/sequence-number` before the bundle is signed. Relaying an inbound
  bundle onward (the destination-mismatch path) does **NOT** touch
  `:dtn/sequence-number` — only `:dtn/hop-count` is incremented — because
  a relay node is not the bundle's source; the original sender's sequence
  number passes through unchanged.
- **Receiving side.** Once a bundle has passed HMAC verification for a
  source this node has a `:peer-secrets` entry for, `handle-inbound-bundle!`
  additionally checks whether `:dtn/sequence-number` is **strictly
  greater** than the highest one already accepted from that exact source
  (a per-source high-water mark kept on the node handle as
  `:replay-high-water-marks`). If not — an exact resend, or an older
  bundle arriving out of order — the bundle is **REJECTED**: logged
  distinctly (`DTN-REPLAY-REJECTED`), never added to `:inbox`, never
  stored, never relayed onward — the same "security event, not a
  legitimate delivery" treatment the existing signature-rejection path
  already gets.
- **Unauthenticated sources are NOT covered.** When no `:peer-secrets`
  entry is configured for a source, replay checking does not apply at
  all — this is a property of authenticated peers only, not a general
  property of the transport. Without a real signature backing it, a
  claimed sequence number proves nothing: an unauthenticated attacker
  could just as easily forge a high one.

**Persistence decision (high-water-mark durability across a restart).**
An in-memory-only high-water-mark map would reset to empty on every node
restart — meaning an attacker who captured an old, legitimately-signed
bundle before the restart could replay it successfully right after,
silently defeating the protection above. This is handled, not left
silent: `start-node!` accepts an optional `:replay-state-path <file>`
(mirrors `:store-path`'s pattern exactly, via new
`kotoba.dtn.auth/load-high-water-marks` /
`kotoba.dtn.auth/save-high-water-marks!` functions, same pure-format/impure-I/O
split as `kotoba.dtn.store`). When set, `:replay-high-water-marks` is
seeded from that file at startup and durably rewritten every time a new
high-water mark is accepted from an authenticated peer — verified for
real (not just in isolated unit tests): a node was started with
`:replay-state-path`, sent one authenticated message, "restarted"
(`stop-node!` + a fresh `start-node!` with the same path), and its
reloaded `:replay-high-water-marks` correctly recovered the prior
high-water mark. **When `:replay-state-path` is omitted (as in this
repo's own demo/CLI usage), the high-water-mark map is in-memory only —
a restart resets it, and a captured bundle from before that restart
could be replayed successfully right after it.** This is a disclosed
limitation of the unconfigured case, not a silently-shipped gap: combine
replay protection with `:replay-state-path` (ideally alongside
`:store-path`, so both durable-state files persist together) whenever a
node's replay protection genuinely needs to survive a restart; a node
that doesn't use `:store-path` either is no worse off than it already
was — in-memory-only replay tracking is consistent with that node's own
already-volatile `:store`/`:inbox`.

**Multi-hop relay routing (`:routes`, `kotoba.dtn.router`'s `:relay`
action).** `route-decision` previously only ever checked whether a
bundle's destination was a *directly* reachable neighbor — if not, its
only other option was `:store`, with no way for a message to travel
through an intermediate node when no direct link to the final
destination existed. `start-node!` now accepts an optional `:routes`
coll (entries shaped `{:dtn/destination eid :dtn/next-hop eid}` — "to
reach `:dtn/destination`, forward to `:dtn/next-hop` instead"),
consulted only when there's no direct link to the bundle's destination:

- If a `routes` entry matches the destination AND a link to that entry's
  next-hop is currently reachable, `route-decision` returns
  `{:dtn/action :relay :dtn/via <link> :dtn/next-hop <eid>}` — a
  distinct action from `:forward` (a relay hop forwards the bundle one
  step closer via a configured intermediate, not a final-hop delivery)
  even though the actual socket write is identical either way. `:routes`
  is consulted by `route-and-send!` for both this node's own
  locally-originated sends and when this node relays an inbound bundle
  addressed to someone else (below).
- If no route entry matches, or the matched next-hop isn't currently
  reachable, behavior is unchanged: falls through to `:store`.

**Scope: STATIC, pre-configured relay only.** `:routes` is a table the
caller supplies (e.g. a node operator's own config) — there is **no
automatic route discovery, no route advertisement/gossip between
nodes, and no dynamic topology learning** here. This is NOT full Contact
Graph Routing (CGR, RFC 9174) and NOT epidemic/PRoPHET-style multi-hop
relay — it's "single-hop-relay-via-a-configured-next-hop", one step
beyond the prior direct-neighbor-or-store heuristic, not a general
multi-hop routing protocol. Automatic ROUTE discovery/advertisement (a
node learning/gossiping *multi-hop routing tables* — who can reach whom
via whom, CGR-style) remains explicitly future work. Do not confuse this
with PEER discovery (a node learning a *direct* neighbor's host:port),
which `kotoba.dtn.discovery` (see "Peer discovery" below) now closes —
that's a materially smaller problem (flat gossip presence broadcast, no
routing-table computation) than the route-advertisement gap named here.
NAT traversal for `kotoba.dtn.transport.tcp` specifically also remains
deferred, same as before — see "NAT traversal" below for the separate UDP
sibling transport that now closes this gap via a real
`kotoba-lang/org-ietf-turn` relay.

**Loop prevention (`:dtn/hop-count`, `max-hops`).** Rather than adding a
`:dtn/hop-count` field to `kotoba.dtn/bundle`'s pure constructor, hop
count is tracked here, at the transport layer: a bundle's `:dtn/hop-count`
(missing/nil treated as 0) is incremented by `handle-inbound-bundle!`
each time this node relays an inbound bundle onward, and passed through
to `route-decision`'s `:hop-count`/`:max-hops` (default
`router/default-max-hops`, currently 8) guard — once hop-count reaches
`max-hops`, `route-decision` refuses to return `:relay` regardless of
`routes`, falling through to `:store` instead, so a bundle that's hopped
too many times without reaching its destination gets held, not endlessly
bounced. This is a simple, honest loop-prevention heuristic — **NOT**
proper DTN routing-loop detection (no per-node "seen this bundle-id
before" dedup is required for it). As a light additional safeguard, each
node also keeps its own `:seen-bundle-ids` set and will not re-relay the
exact same `:dtn/bundle-id` through itself twice — again, node-local
suppression, not cross-node loop detection.

**The destination-mismatch fix.** Before relaying existed, the TCP
transport's inbound handler accepted ANY successfully-decoded (and, when
configured, signature-verified) bundle straight into its own `:inbox`,
regardless of whether the bundle's `:dtn/destination` actually matched
the receiving node's own EID — harmless while every message happened to
be sent directly to its intended recipient (the only usage pattern before
relaying), but wrong once relaying exists: a relay node receiving a
bundle addressed to someone else must not silently absorb it. This is
fixed: `handle-inbound-bundle!` now checks that match. On a match,
behavior is unchanged (added to `:inbox`, `DTN-RECV` logged). On a
mismatch, the bundle is never added to `:inbox` — it's re-routed through
this node's own `route-and-send!` (the same function used for this
node's own locally-originated sends), so it either forwards/relays
onward for real, or falls back to this node's own `:store` if it, too,
has no path right now. This case is logged distinctly as `DTN-RELAY`
(vs. the existing `DTN-RECV`) so logs make the difference legible. See
the E2E demo's scenario 5, below, for a real 3-node A→B→C proof over
actual TCP sockets, including confirmation that the intermediate relay
node's own `:inbox` never absorbs the message.

### CLI (`bin/dtn_node.cljk`)

A minimal demo/dev tool — no config file, no systemd, no TLS:

```bash
# Terminal 1 — long-running node, logs every received message + retry pass
kbb --backend sci --classpath "src:../phone/src:../html/src:../css/src:../wire/src:../bytes/src" bin/dtn_node.cljk \
  listen --e164 +818098765432 --port 5100

# Terminal 2 — send one kotoba.rcs-shaped chat message, then exit
kbb --backend sci --classpath "src:../phone/src:../html/src:../css/src:../wire/src:../bytes/src" bin/dtn_node.cljk \
  send --e164 +819012345678 --port 5101 \
  --peer +818098765432:localhost:5100 \
  --to +818098765432 --body "hello"
```

(`--classpath` mirrors `deps.edn`'s sibling `:local/root` layout — this
repo checked out next to `kotoba-lang/phone`, `/html`, `/css`, `/wire`,
`/bytes`. `/wire` and `/bytes` are needed because
`kotoba.dtn.transport.tcp` delegates its wire framing/socket-pool
mechanics to `kotoba.wire` (`kotoba-lang/wire`, built on
`kotoba-lang/bytes`) — see "Internet-overlay transport" above.)

### E2E demo (`test/kotoba/dtn/transport/tcp_demo.cljk`)

An executable proof, not a unit test — run it and read the output:

```bash
kbb --backend sci --classpath "src:../phone/src:../html/src:../css/src:../wire/src:../bytes/src" \
  test/kotoba/dtn/transport/tcp_demo.cljk
```

Seven scenarios, printing `PASS`/`FAIL` per scenario and a final
`RESULT: N/7 scenarios passed` line (exit 0 iff 7/7):

1. **Real cross-process delivery** — spawns a real second `nbb` OS process
   running `bin/dtn_node.cljk listen`, sends to its real bound port, and
   confirms delivery by grepping that child process's own stdout for its
   `DTN-RECV` log line (not just checking a local return value).
2. **Store-and-forward across a disconnect** — stops a node's server,
   sends to it (falls into `:store`, not delivered), restarts the server
   on the same port, calls `retry-store!`, and confirms the message now
   arrives and `:store` is empty again.
3. **Multi-transport-kind priority** — pure `router/route-decision` only,
   no real radio: proves the router genuinely picks `:internet-overlay`
   by default and would pick a (simulated) `:mesh-radio` link first under
   a resilience-first `:priority` override.
4. **(4a) Durable store survives a process restart** — sends to an
   unreachable peer with `:store-path` configured (the bundle lands in
   `:store` AND is appended to disk), `stop-node!`s the node, then
   `start-node!`s a brand-new node handle with the SAME `:store-path` and
   confirms the reloaded `:store` actually contains the bundle — a real
   restart round-trip through the file, not just the pure
   serialize/deserialize functions checked in isolation.
5. **(4b) Bundle integrity is enforced** — two nodes configured with a
   shared `:peer-secrets` entry exchange a real signed message over TCP
   and confirm it's accepted; then a bundle signed with the WRONG secret
   is written directly to a raw socket via `tcp/encode-frame` (bypassing
   `send-message!`'s normal signing path entirely) and the demo confirms
   it does NOT appear in the receiving node's `:inbox` — rejected, with a
   logged `tcp: REJECTED inbound bundle ...` line.
6. **Static multi-hop relay routing (real TCP, 3 nodes)** — node A is
   configured with NO direct peer/link entry for node C at all, only for
   node B, plus a `:routes` entry saying "to reach C, go via B"; node B
   has a genuine direct peer entry for C. A sends a message to C over
   real TCP. The demo confirms the message does NOT appear via any
   nonexistent A→C link (there isn't one), that it actually flows
   A→B→C (C's `:inbox` receives it for real), that B's `:inbox` does
   **NOT** contain it (B correctly relayed rather than absorbing it —
   directly proving the destination-mismatch fix above), and that B's
   relay was a real routing decision — not an out-of-band cheat — by
   capturing B's own `DTN-RELAY from=... to=... via=...` log line.
7. **Replay protection** — two nodes share a `:peer-secrets` entry; node
   A sends one real, legitimately-signed message to node B over TCP
   (confirmed accepted). The demo captures the EXACT bundle B actually
   decoded off the wire from B's own `:inbox` entry (not a hand-rolled
   reconstruction) and resends those exact same signed bytes a second
   time over a fresh raw socket, bypassing `send-message!`'s normal
   fresh-sequence-number stamping entirely. The demo confirms B's
   `:inbox` still has exactly ONE copy of that message (not two) and
   that a `DTN-REPLAY-REJECTED` line was logged. It then sends a
   genuinely NEW message (a fresh sequence number, via a normal
   `send-message!` call) from A to B and confirms THAT one is accepted
   normally — proving replay rejection doesn't wrongly block legitimate
   subsequent traffic from the same authenticated source.

## Peer discovery (`kotoba.dtn.discovery`, real I/O)

Everything in "Internet-overlay transport" above still requires a peer's
host:port to already be known via `:peers` — this namespace
(`src/kotoba/dtn/discovery.cljk`) closes that gap: dtn nodes **announce**
their own reachability over, and **consume** presence announcements from,
a real [`kotoba-lang/io-libp2p`](https://github.com/kotoba-lang/io-libp2p)
gossip mesh, populating a *running* node handle's `:peers` map
dynamically. Two dtn nodes that were never told about each other's
host:port in advance can exchange a real bundle over
`kotoba.dtn.transport.tcp` purely because gossip-based discovery told them
how to reach each other — see the E2E demo below for the actual proof.

**This is a real, direct dependency on `kotoba-lang/io-libp2p`** — unlike
this repo's deliberately duck-typed, dependency-free relationship to
`kotoba-lang/rcs` (see `kotoba.dtn.gateway`), `io-libp2p` already exists,
is independently stable and versioned, and there's no build-order reason
to avoid depending on it directly here. `deps.edn` gained a
`io.github.kotoba-lang/io-libp2p {:local/root "../io-libp2p"}` entry to
match (this repo now expects `kotoba-lang/io-libp2p` checked out as a
sibling, alongside `phone`/`html`/`css`/`wire`/`bytes`).

**Contract.**

```clojure
(require '[kotoba.dtn.transport.tcp :as tcp])
(require '[kotoba.net.transport.tcp :as net-tcp])
(require '[kotoba.dtn.discovery :as discovery])

;; Two dtn nodes, both started with EMPTY :peers — genuinely no static
;; config — plus a gossip node each, mesh-connected via io-libp2p.
(def dtn-a (tcp/start-node! {:e164 "+819012345678" :port 5100 :peers {}}))
(def dtn-b (tcp/start-node! {:e164 "+818098765432" :port 5101 :peers {}}))
(def gossip-a (net-tcp/start-node!
               {:node-id "a" :port 5110
                :peers {"b" {:host "127.0.0.1" :port 5111 :topics #{"dtn-presence"}}}}))
(def gossip-b (net-tcp/start-node!
               {:node-id "b" :port 5111
                :peers {"a" {:host "127.0.0.1" :port 5110 :topics #{"dtn-presence"}}}}))

;; Wire each dtn node to its own gossip node.
(def handles
  [(discovery/start-announcing! dtn-a gossip-a :advertise-host "127.0.0.1")
   (discovery/start-discovering! dtn-a gossip-a)
   (discovery/start-announcing! dtn-b gossip-b :advertise-host "127.0.0.1")
   (discovery/start-discovering! dtn-b gossip-b)])

;; ... after at least one discovery poll cycle, dtn-a's :peers now
;; genuinely contains a live entry for B, populated purely by gossip:
(:peers @dtn-a)  ;; => {"+818098765432" {:host "127.0.0.1" :port 5101}}

(discovery/stop-discovery! handles)
```

**Scope — explicitly NOT:**

- **A DHT.** No distributed routing table, no key-based lookup — just a
  flat gossip broadcast of "here is how to reach me" on a well-known
  topic (`"dtn-presence"` by default), consumed by every dtn node polling
  that topic on the same gossip mesh.
- **Authenticated.** A presence announcement is trusted at face value —
  this module does not sign or verify who actually sent it, only
  structurally validates its shape
  (`kotoba.dtn.discovery.presence/valid-presence-announcement?`).
  Combining a newly-discovered peer with `kotoba.dtn.auth`'s
  `:peer-secrets` for the *actual bundle traffic* once it's discovered —
  so a forged discovery announcement can, at worst, get itself added as
  an unauthenticated `:peers` entry, never impersonate an already-
  authenticated peer without also holding that peer's real shared secret
  — is the **caller's job**. This module never configures
  `:peer-secrets` on anyone's behalf.
- **Push/callback-based.** `kotoba-lang/io-libp2p`'s transport currently
  exposes no inbound-message callback/hook for an external consumer — its
  only observable integration surface is the plain `:received-messages`
  vector on its own node handle atom. Rather than modify `io-libp2p` to
  add a push hook (out of scope — `io-libp2p` is treated here as a
  stable, already-built dependency to consume, not extend), this
  namespace **polls** that vector on a plain `js/setInterval`, the same
  mechanism `start-announcing!` already uses for its own periodic
  broadcast. A deliberate simplicity choice given `io-libp2p`'s current
  observable-state-only integration surface, not an oversight — and
  exactly why `io-libp2p` itself never needed to change for this to work.

**A real gap discovered while wiring this up (not an `io-libp2p` bug —
accommodated entirely in the shape of the data this module broadcasts).**
`kotoba.net.gossip/route-message`'s dedup is purely content-hash based: a
locally-originated `publish!` marks its own payload's hash `seen` on the
*publishing* node's own seen-cache the moment it's first sent. If a
periodic presence re-announcement carried the exact same
`{:dtn/e164 :dtn/host :dtn/port :dtn/transport-kind}` map on every tick,
every re-announcement after the very first would hash identically to the
first, `route-message` would treat it as already-seen, and `publish!`
would silently stop writing to any peer's socket at all after tick one —
which would have broken exactly the "late-joining node discovers
existing peers" case (see the E2E demo, scenario 3): a peer that joins
the gossip mesh *after* that one-and-only successful broadcast would
never receive a copy. `kotoba.dtn.discovery.presence/presence-announcement`
therefore stamps a real wall-clock `:dtn/announce-ts` (via `js/Date.now()`,
from the one layer — `kotoba.dtn.discovery`'s impure `announce!` — that
actually has a clock, the same seam `kotoba.dtn.transport.tcp/send-message!`
already uses) onto every announcement, so every tick's payload hashes
distinctly and `route-message` never short-circuits a re-announcement as
an already-seen duplicate. See `kotoba.dtn.discovery.presence`'s namespace
docstring for the full writeup — this is the same *kind* of external
workaround `kotoba.net.transport.tcp`'s own `safe-from` already is for a
different `kotoba.net.gossip` landmine, just discovered independently
while building this module, not a change to `gossip.cljc` itself.

**Pure helpers** (announcement shape construction/validation,
self-announcement detection, translating an announcement into the
`{:host .. :port ..}` shape `:peers` already expects, and the
`:received-messages` dedup-index math) live in
`kotoba.dtn.discovery.presence` — portable `.cljc`, covered by
`kbb -M:test` (see Maturity table above: 28 of this repo's 175 total
assertions). `kotoba.dtn.discovery` itself is `.cljs`-only (real socket
I/O via `io-libp2p`, real `js/setInterval`) and, like
`kotoba.dtn.transport.tcp`, is never loaded by the JVM `kbb -M:test`
suite.

### E2E demo (`test/kotoba/dtn/discovery_demo.cljk`)

An executable proof, not a unit test — run it and read the output:

```bash
kbb --backend sci --classpath "src:../phone/src:../html/src:../css/src:../wire/src:../bytes/src:../io-libp2p/src" \
  test/kotoba/dtn/discovery_demo.cljk
```

(the `../io-libp2p/src` classpath entry, beyond what the transport demo
above needs, is required because `kotoba.dtn.discovery` depends directly
on `kotoba.net.transport.tcp`.)

Three scenarios, printing `PASS`/`FAIL` per scenario and a final
`RESULT: N/3 scenarios passed` line (exit 0 iff 3/3):

1. **Zero-static-config discovery, then a real dtn message delivery
   purely from discovered peers.** Three dtn nodes (A, B, C) start with
   `:peers {}` — genuinely no static config — plus three `io-libp2p`
   gossip nodes, mesh-connected. Each dtn node is wired to its own gossip
   node via `start-announcing!`/`start-discovering!`. The demo asserts,
   BEFORE sending anything, that A's `:peers` went from empty (captured
   the instant after `start-node!`, before any discovery loop even ran)
   to genuinely containing real entries for both B and C, with the
   correct host:port — proving discovery, not some other path, populated
   it. A then `send-message!`s to C over real dtn TCP using that
   discovered entry; the demo confirms delivery succeeds and lands in
   C's `:inbox`.
2. **Self-announcements are correctly filtered.** First confirms that a
   normal full-mesh gossip run never puts a node's own e164 into its own
   `:peers` — a real but *weak* proof by itself, since
   `kotoba.net.gossip`'s own fanout already excludes `{from self}` at the
   transport layer, so a full mesh never round-trips a node's own
   broadcast back to it regardless of whether this module's own
   self-filtering code does anything. The demo then closes that gap
   non-vacuously: it directly crafts a syntactically-valid self-
   announcement and injects it straight into a gossip node's own
   `:received-messages` (simulating what a differently-shaped topology —
   a longer relay chain, a ring, a misbehaving peer — genuinely could
   deliver), and confirms `process-presence-updates!` still refuses to
   add it.
3. **A late-joining node discovers existing peers too, not just vice
   versa.** A and B start first, mesh-connected, and discover each other.
   Only then does C start — a real late join: C's own dtn and gossip
   processes/ports do not exist yet when A/B's gossip mesh config already
   lists C's address (matching `io-libp2p`'s own static-`:peers`-at-
   `start-node!`-time scoping — there is no API to add a peer to an
   already-running gossip node). The demo confirms C eventually
   discovers BOTH pre-existing A and B, with the correct host:port —
   proving discovery is symmetric, not just whichever order happened to
   be tested first.

## NAT traversal (`kotoba.dtn.transport.udp`, real I/O)

Every namespace above this point named the same open gap and deliberately
did not attempt it: `kotoba.dtn.transport.tcp` is TCP, TURN relays UDP, and
bridging the two was called "a materially different, larger problem than
gossip-based discovery." This section closes that gap — honestly, at a
genuinely scoped-down level, not with a full ICE implementation.

`src/kotoba/dtn/transport/udp.cljk` (`kotoba.dtn.transport.udp`, `.cljs`,
Node-only, same real-I/O split every transport namespace in this repo
uses) is a UDP-native sibling to `kotoba.dtn.transport.tcp`, deliberately
simpler for the non-relayed case: UDP preserves datagram boundaries, so
unlike TCP there is no stream to frame — a whole `pr-str`'d EDN bundle,
UTF-8 encoded, IS one datagram, with no `kotoba-lang/wire` length-prefix
framing involved at all. It reuses `kotoba.dtn.router`, `kotoba.dtn.auth`,
`kotoba.dtn.store`, and `kotoba.dtn.gateway` for real, exactly as
`kotoba.dtn.transport.tcp` already does (durable `:store-path`,
`:peer-secrets` HMAC-SHA256 signing/verification, `:dtn/sequence-number`
replay protection, `:routes` static relay — all identical semantics,
transport-agnostic). The transport-layer orchestration glue
(`handle-inbound-bundle!`, `links-for`, `route-and-send!`, etc.) is this
namespace's OWN copy, not shared with `kotoba.dtn.transport.tcp` —
`tcp.cljs` is deliberately untouched by this work, byte-for-byte, so a
shared extraction was out of scope (see the namespace's own docstring for
the full rationale). `start-node!` here returns a `Promise<node-handle>`,
not a bare atom like `kotoba.dtn.transport.tcp/start-node!` does — binding
a UDP socket, and (when configured) completing a real multi-round-trip
TURN handshake, are both inherently asynchronous.

**The NAT-traversal capability.** An OPTIONAL `:turn-relay` option on
`start-node!` — `{:server-host .. :server-port .. :shared-secret ..
:peer-address {:address .. :port ..}}` — treats that node as NAT'd: at
startup it performs a REAL RFC 8656 Allocate, then a REAL CreatePermission
for the one configured `:peer-address`, against a REAL, already-running
[`kotoba-lang/org-ietf-turn`](https://github.com/kotoba-lang/org-ietf-turn)
`kotoba.turn.listener` (org-ietf-turn's own real UDP relay — consumed
as-is here, never modified; see that repo's own README for what it
implements). The client-side STUN-message-construction sequence
(`build-allocate-request` / `build-create-permission-request` /
`build-send-indication`) is adapted from org-ietf-turn's own
`test/kotoba/turn/listener_demo.cljs` client-building pattern into a new
pure `.cljc` namespace, `src/kotoba/dtn/transport/turn_relay.cljk`
(`kotoba.dtn.transport.turn-relay`) — zero I/O, testable under plain JVM
`kbb -M:test` (37 of this repo's 212 total assertions), including the
"is this inbound datagram a relayed Data indication or a directly-received
raw bundle" classification decision (`classify-inbound-datagram`) a
TURN-relay-configured node's socket handler needs.

Once the handshake succeeds: every outbound bundle from a `:turn-relay`
node is wrapped in a real STUN Send indication and sent to the TURN
server, addressed to the one permitted peer; every inbound datagram on
that node's socket is classified, and a real STUN Data indication is
unwrapped and delivered into the normal bundle-handling pipeline exactly
as if it had arrived directly. **The real capability this adds:** a dtn
node that is not directly reachable can still have its bundles relayed
through a TURN server to a peer that only ever sends to that node's
TURN-allocated relayed address, and can reply back through the same relay
— genuine bidirectional delivery, proven for real in the E2E demo below,
not simulated.

**Automatic allocation + permission refresh.** This used to be this
namespace's headline disclosed gap: Allocate + CreatePermission were
called exactly ONCE, at `start-node!` time, and never refreshed again — a
`:turn-relay` node that stayed up past ~5-10 minutes would have its
permission (300s default) and then its allocation (600s default) silently
expire server-side, after which relayed traffic in both directions started
being silently dropped by the TURN server with zero warning. This is now
closed: `start-node!` schedules a real, periodic RFC 8656 §7.3 Refresh
(extends the allocation's own expiry) and a periodic re-CreatePermission
(renews the peer permission's own, independent, shorter expiry) via
`js/setInterval`, and `stop-node!` cancels that interval alongside closing
the socket.

**Cadence.** Refreshes fire at HALF of whatever lifetime the server's REAL
initial Allocate response actually granted — read from its LIFETIME
attribute (`kotoba.dtn.transport.turn-relay/response-lifetime`), never
hardcoded/assumed. Half the granted lifetime is a conventional TURN/ICE
client margin (the same rule e.g. libwebrtc's own TURN client uses):
comfortably before the deadline even accounting for one refresh attempt
failing outright and only being retried at the next scheduled tick. This
cadence is computed ONCE, from the ORIGINAL Allocate's granted lifetime,
and stays fixed for the node's entire remaining lifetime — deliberately
NOT recomputed from whatever a later Refresh response happens to grant. A
real, disclosed trade-off follows from that: if a TURN server ever granted
a MUCH shorter lifetime than its usual default at some point mid-run —
roughly anything under 2 seconds — a cadence fixed at half of a different
(probably much longer) original grant could in principle fire its next
tick after that later short-lived grant's own deadline. This is not a gap
against org-ietf-turn's actual listener, which always grants the exact
same fixed lifetime on every Allocate (verified by reading the source, not
assumed) — it is a disclosed limit of this implementation's chosen
approach for a hypothetical server that varies what it grants.

**Failure handling (deliberately scoped down).** A single failed
Refresh/CreatePermission-refresh attempt (relay temporarily unreachable,
one lost UDP datagram, a timeout) is logged and left for the next
scheduled tick — there is NO retry-before-next-tick, NO exponential
backoff, and NO give-up-after-N-failures/circuit-breaker logic. The
interval keeps firing regardless of any individual tick's outcome, so a
transient failure self-heals at the next tick as long as the underlying
reachability problem was itself transient; a genuinely permanent relay
outage is not specially detected or alerted on beyond the ordinary per-tick
log lines. A real production TURN client would need actual retry/backoff/
alerting on top of this — deliberately not built here, per this feature's
own scope.

**A real, documented asymmetry in what org-ietf-turn's listener honors.**
Read directly from `kotoba.turn.listener`'s source (not assumed):
`handle-allocate!` never inspects a LIFETIME attribute on the ORIGINAL
Allocate request at all — it always grants its own fixed
`kotoba.turn.allocation/default-lifetime-s` (600s), regardless of what a
client asks for. `handle-refresh!`, by contrast, genuinely DOES read and
honor a client-requested LIFETIME on Refresh. Production scheduled
refreshes never rely on this (they omit LIFETIME entirely, letting the
server's default apply); it matters for how the E2E demo's Scenario 4
constructs a short, real, observable expiry window for its survival proof,
since the literal initial 600s Allocate grant cannot be shrunk at all — see
that scenario, below, for the full disclosure.

**Test-only tuning knobs.** `:turn-relay` accepts two additional OPTIONAL
keys, `:refresh-interval-ms` and `:refresh-lifetime-s`, that override the
computed cadence and make every scheduled Refresh request an explicit
(typically short) lifetime, respectively — NOT meant for production use,
they exist purely so a demo/test can observe refresh behavior in real
seconds rather than real minutes. See `schedule-turn-refresh!`'s own
docstring and Scenario 4, below.

**What this deliberately is NOT — same "claim exactly what was built"
discipline as every other namespace in this repo:**

- **NOT full ICE (RFC 8445).** No STUN-based own-NAT-type detection, no
  candidate gathering, no connectivity-check exchange between peers to
  pick the best of several candidate pairs. There is exactly ONE candidate
  for reaching a NAT'd peer — its TURN-relayed address — supplied directly
  by the caller, never discovered or negotiated.
- **NOT full production-grade refresh retry/backoff.** See "Failure
  handling" above — a single failed refresh attempt is logged and left to
  the next scheduled tick, nothing more.
- **NOT an explicit allocation teardown on `stop-node!`.** No RFC 8656
  §7.3 Refresh-with-LIFETIME-0 "delete this allocation now" signal is sent
  before closing — the allocation simply expires server-side on its own
  timer once this node stops refreshing it (same as before this revision,
  just delayed by however many refresh cycles already ran).
- **NOT relay-unreachable fallback.** If the TURN server goes down, or a
  Send indication is simply lost (UDP, no retransmission), this namespace
  does not fall back to a direct send and does not retry the relay — there
  is no ICE-style "try the next candidate" logic because there is only
  ever the one candidate. A failed relay send just falls into the node's
  normal `:store` (store-and-carry), same as any other undelivered bundle.
- **NOT multi-peer relaying from one node.** CreatePermission is called
  exactly once, for the single `:peer-address` given in `:turn-relay`'s
  config — this scoped version is single-peer-per-node.
- **NOT the ChannelBind fast path.** Every relayed message pays full STUN
  Send-indication/Data-indication framing overhead; org-ietf-turn's
  listener supports the lighter post-ChannelBind ChannelData format
  server-side, this client just never requests one.
- Inherits org-ietf-turn's own disclosed scope limits (IPv4-only,
  ephemeral-short-term-credential-only, no quotas/DoS limits) by
  construction.

### `deps.edn`

```clojure
io.github.kotoba-lang/org-ietf-turn {:local/root "../org-ietf-turn"}
```

(added alongside this repo's existing `io.github.kotoba-lang/*` sibling
`:local/root` entries — `kotoba.dtn.transport.turn-relay` requires
`kotoba.turn.stun` / `kotoba.turn.demux`, and `kotoba.dtn.transport.udp`
additionally requires `kotoba.turn.credential` and
`kotoba.turn.listener`'s sibling repo checked out alongside this one, same
pattern `phone`/`html`/`css`/`wire`/`io-libp2p` already establish.)

### E2E demo (`test/kotoba/dtn/transport/udp_turn_demo.cljk`)

An executable proof, not a unit test — run it and read the output. This is
the most complex integration in this whole repo: three protocol layers for
real (dtn bundles, a real TURN relay, real UDP socket timing). Requires
`kotoba-lang/phone`, `/html`, `/css`, `/wire`, `/bytes`, and
`org-ietf-turn` checked out as siblings:

```bash
kbb --backend sci --classpath "src:../phone/src:../html/src:../css/src:../wire/src:../bytes/src:../org-ietf-turn/src" \
  test/kotoba/dtn/transport/udp_turn_demo.cljk
```

Four scenarios, printing `PASS`/`FAIL` per scenario and a final
`RESULT: N/4 scenarios passed` line (exit 0 iff 4/4):

1. **Baseline** — two dtn nodes, NEITHER behind NAT (no `:turn-relay`
   config on either), exchange a real message directly over
   `node:dgram` sockets. Proves the new UDP transport itself works before
   TURN enters the picture at all.
2. **The actual NAT-traversal proof** — a real `kotoba.turn.listener` is
   started with a known shared secret. Node A is `:turn-relay`-configured,
   with node B's real address as A's one permitted peer. Node B has NO
   TURN config (B is the directly-reachable one) and is deliberately
   configured to reach A ONLY at A's TURN-allocated relayed address —
   never A's real bound port, simulating "A is unreachable directly, B can
   only reach A through the relay." B sends to A (addressed to A's relay
   address); the demo confirms A's `:inbox` actually receives it, arrived
   via the relay and unwrapped from a real STUN Data indication. A then
   replies to B (sent by A as a real STUN Send indication through the SAME
   relay — A has zero direct-send path in this scoped design); the demo
   confirms B's `:inbox` actually receives A's reply. Genuine
   bidirectionality is proven, not just one direction.
3. **Honesty check** — not a simulated firewall (nothing to literally
   block on loopback), but a mechanical confirmation, against the EXACT
   live node B instance scenario 2 just used (not a fresh unrelated one),
   that B's own config contains A's real port NOWHERE at all — walking the
   entire node-handle map, not just the one `:peers` key this demo happens
   to know to check. Proves scenario 2's success is not an accidental
   direct-connection fallback dressed up as a relay proof.
4. **Survival past the allocation's original expiry window (real
   wall-clock proof) — 4a positive + 4b negative control.** Proves the
   automatic periodic Refresh added above actually keeps a `:turn-relay`
   allocation reachable past a real expiry deadline, using a genuine
   `js/setTimeout`-based wait, not a mocked clock. **Honesty disclosure
   first:** org-ietf-turn's `handle-allocate!` ignores a client-requested
   LIFETIME on the original Allocate request entirely (always grants the
   fixed 600s default — confirmed both by reading the source and by
   scenario 2's own `granted-lifetime-s=600` log line), so this scenario
   cannot shrink the literal initial Allocate grant to make a 600s wait
   practical for an automated demo. Instead it uses `handle-refresh!`'s
   genuinely-honored client-requested LIFETIME — the same real mechanism
   production scheduled refreshes use — to bring a real, live allocation
   down to a short (3s), server-granted expiry window on its very first
   scheduled tick, then proves continued scheduled refreshing keeps
   pushing that real deadline forward. **4a (positive):** node A is
   started with `:refresh-lifetime-s 3` and `:refresh-interval-ms 900`
   (test-only overrides — a real deployment would set neither). A baseline
   message is sent immediately (matches scenario 2's proof the relay
   works at all); the demo then waits 5.5 REAL seconds (multiple scheduled
   refresh ticks fire in the background during the wait) and sends a
   second message; the demo confirms it still arrives — proving the
   allocation is still alive well past the 3s window its first scheduled
   refresh established. **4b (negative control):** a fresh node pair
   establishes the IDENTICAL short window via one manual
   `refresh-turn-allocation!` call, but with the automatic scheduler
   explicitly disabled (its `js/setInterval` cleared) immediately
   afterward — no further refresh is ever sent. After the SAME 5.5s real
   wait, a message sent through that allocation does NOT arrive — the
   TURN listener's own periodic expiry sweep (a `:sweep-interval-ms 300`
   override on this scenario's own listener instance, so the drop is
   observable in seconds — `start-listener!`'s own supported option, not a
   modification to org-ietf-turn) has genuinely dropped the allocation
   server-side by then. This negative control makes 4a's positive proof
   non-vacuous: it demonstrates, empirically, what would have happened to
   4a WITHOUT this whole feature.

## License

Apache License 2.0.

## Test

```bash
kbb -M:test
```
