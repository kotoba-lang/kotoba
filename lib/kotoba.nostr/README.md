# nostr

[![CI](https://github.com/kotoba-lang/nostr/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/nostr/actions/workflows/ci.yml)

**A Nostr relay (NIP-01) and Blossom blob store (NIP-98 + BUD-01/02), projected
onto [kotobase](https://github.com/kotoba-lang/kotobase)** — part of the same
kotobase.net storage/protocol-extension effort as
[kotoba-lang/kotobase-protocols](https://github.com/kotoba-lang/kotobase-protocols)
(ADR-2607171700 in `com-junkawasaki/root`; this repo's own decision record is
ADR-2607172210, and its addressing contract is the Kotoba Resource Protocol
0.2 addendum, `90-docs/protocols/kotoba-resource-protocol.edn` §16.3).

Named `nostr` (bare, no reverse-domain prefix) because Nostr has no formal
standards body — NIPs are a community-run GitHub repo, the same reasoning
that keeps names like `openapi` un-reverse-domained elsewhere in this org
(ADR-2607060100).

Two independent namespaces in one repo, per ADR-2607172210:

| Surface | Namespace(s) | Protocol subset | KRP identity |
|---|---|---|---|
| Nostr relay | `nostr.relay` (`.cljc` core) + `nostr.relay.transport` (`.cljs`-only WebSocket) | NIP-01: `EVENT`/`REQ`/`CLOSE` -> `EVENT`/`OK`/`EOSE`/`CLOSED`/`NOTICE` | §3.3 Content (event id) |
| Blossom blobs | `nostr.blossom` (`.cljc`, HTTP) | NIP-98 HTTP Auth + BUD-01/02: `PUT /upload`, `GET /<sha256>`, `DELETE /<sha256>` | §3.3 Content (blob sha256) |

Supporting pure namespaces: `nostr.event` (NIP-01 event validation, id
computation, filter matching), `nostr.crypto` (SHA-256 + secp256k1/BIP-340
Schnorr — see "Cryptography" below), `nostr.json` (dependency-free JSON),
`nostr.http` (ring-shaped request/response glue for `nostr.blossom`).

## Architecture: pure `.cljc` core, `.cljs`-only transport

Every actual protocol decision — event validation, signature verification,
storage, subscription-filter matching — lives in pure `.cljc` namespaces with
**zero socket/network I/O**, over the injected `kotobase.store/IStore` seam
(the same convention `kotobase-protocols` established: `LocalStore`
standalone, `KotobaseStore` against kotobase.net). The WebSocket bytes-on-
the-wire for the relay live entirely in `nostr.relay.transport`, a
**`.cljs`-only** namespace — this follows the exact discipline
ADR-2607161817 (`kotoba-lang/dtn`) and ADR-2607162135
(`kotoba-lang/io-libp2p`) established for real transports in this workspace:

- Hand-rolled RFC 6455 WebSocket handshake and frame codec over Node's raw
  `node:net` + `node:crypto` (the SHA-1 handshake digest) — **not** the `ws`
  npm package. Zero npm dependencies, matching every transport in this
  consolidation series.
- `.cljs`, not `.cljc`, specifically so it can **never** be loaded by the JVM
  `:test` compat suite — a real regression in socket code can never
  regress the pure-data test suite, and vice versa.
- Verified with a genuine two-scenario integration test
  (`test/nostr/relay_transport_test.cljk`, itself `.cljs`-only) using REAL
  sockets: a from-scratch test WebSocket client (also hand-rolled, over
  `node:net`) performs the actual RFC 6455 client handshake, sends a
  **masked** client text frame (client→server frames MUST be masked per
  RFC 6455 §5.1 — the server's `unmask!` is exercised for real, not
  bypassed), and receives a real `OK` frame back. A second scenario proves
  live fan-out: one connection subscribes via `REQ`, a second connection
  publishes a matching `EVENT`, and the first connection receives an
  unsolicited `EVENT` push — not just the static `REQ`/`EOSE` query path.

## Cryptography — honest status

**Real, spec-verified BIP-340 Schnorr signature verification — not a
stand-in, not silently skipped.** `nostr.crypto/schnorr-verify` implements
the full BIP-340 algorithm (secp256k1 field/point arithmetic, `lift_x`,
tagged hashing) from scratch in portable `.cljc` — `:clj` uses
`java.math.BigInteger` (JDK built-in), `:cljs` (nbb/Node) uses native
`js/BigInt` — **zero external elliptic-curve library dependency**.

It is checked in `test/nostr/crypto_test.cljk` against the **official
BIP-340 test vectors**
([bitcoin/bips](https://github.com/bitcoin/bips/blob/master/bip-0340/test-vectors.csv),
fetched directly, not hand-derived), 5 positive and 10 negative cases (the 4
variable-length-message vectors added in 2022-12 are out of scope — see that
file's docstring for why: this repo's `schnorr-verify` requires exactly a
32-byte message by design, matching how Nostr always uses it — the message
is always a NIP-01 event id or NIP-98 auth event id, both 32-byte SHA-256
hashes). It is **not** merely self-consistency-tested — self-consistency
alone would not have caught the one real bug this implementation shipped
during development (a single missing hex digit in the hardcoded secp256k1
generator-point Y coordinate, which put the entire curve off its actual
curve; sign and verify still agreed with each other perfectly, consistently
wrong, until cross-checked against the official vectors — see
`crypto_test.cljc`'s own docstring for the full story).

`nostr.crypto/schnorr-sign` also exists, but is **test-fixture-only** — real
Nostr clients sign; `nostr.relay` and `nostr.blossom` only ever *verify*,
never sign. It exists solely so this repo's own test suite
(`test/nostr/fixtures.cljk`) can build genuinely BIP-340-signed events for
round-trip tests instead of hand-typed (and possibly wrong-shaped) fixture
data. If this workspace later wants a vetted external secp256k1
implementation instead of this hand-rolled one, `schnorr-verify` is the
single swap-in point — every caller in this repo goes through it, never the
field/point internals directly.

SHA-256 (used for event ids, Blossom blob hashes, and internally by
`tagged-hash`) is real too: `java.security.MessageDigest` on `:clj`,
`node:crypto`'s `createHash` on `:cljs` — both platform built-ins, zero
deps.

## NIP-01 relay: what's real

- Full event validation: required-field shape check, id = SHA-256 of the
  **exact** NIP-01 canonical serialization (`nostr.event/canonical-serialize`
  — a dedicated minimal-escape-set serializer, deliberately separate from
  the general-purpose `nostr.json`, since NIP-01 escapes only 7 named
  characters and general JSON escapes every control character; using the
  wrong one would compute a different id than every other Nostr
  implementation), and real BIP-340 signature verification.
- Real NIP-01 kind classification: **regular** events (stored forever, keyed
  by id), **replaceable** (kind 0, 3, 10000–19999: only the newest per
  `(pubkey, kind)` survives — an older-or-equal-timestamp arrival is a no-op,
  a genuinely newer one deletes the old slot), **addressable** / "parameterized
  replaceable" (kind 30000–39999: same rule, scoped to
  `(pubkey, kind, first "d" tag)`), and **ephemeral** (kind 20000–29999:
  accepted and handed to the transport for live fan-out, but never stored).
- `REQ` filter matching: `ids`/`authors`/`kinds`/`#e`/`#p`/`since`/`until`/
  `limit`, multiple filters OR'd and de-duplicated by id, newest-first.

**Known v0.1 scope limits** (disclosed, not silently skipped):
- Replaceable/addressable lookups do a full scan of the events collection
  (`IStore/-list` + `-get` per candidate) to find the existing slot — correct,
  not optimized for scale. Same spirit as `kotobase-protocols/s3.cljc`'s
  `ListObjectsV2` scanning every key in a bucket.
- No NIP-42 (`AUTH`), no NIP-45 (`COUNT`), no NIP-11 relay information
  document, no rate limiting, no persistence beyond whatever `IStore`
  backend is injected.
- Single-frame WebSocket messages only — no fragmented-message reassembly
  across continuation frames (real Nostr clients send each `EVENT`/`REQ`/
  `CLOSE` as one text frame).

## Blossom (NIP-98 + BUD-01/02): what's real

- `PUT /upload` computes the real SHA-256 of the body and stores it; returns
  the Blossom blob descriptor JSON (`url`/`sha256`/`size`/`type`/`uploaded`).
  Does **not** require NIP-98 auth (matches many real Blossom servers'
  public-upload policy, and is what ADR-2607172210 literally specifies —
  only `DELETE` is called out as requiring auth). When an `Authorization`
  header *is* present, it's still verified and its pubkey recorded.
- `GET /<sha256>` is fully public, no auth — matches Blossom's read model.
- `DELETE /<sha256>` requires a valid NIP-98 auth event: `kind:27235`,
  signed, a `u` tag matching the exact request URL, a `method` tag matching
  `DELETE`, and `created_at` within a 60-second window (both directions).
  **Known gap**: it does not additionally check that the deleting pubkey
  matches the original uploader — any holder of a validly-signed, freshly-
  timestamped auth event for the exact blob URL can delete it. A production
  Blossom server should add ownership enforcement; this is a disclosed v0.1
  simplification, not a silently-skipped requirement.
- Bodies are strings (binary upload is a follow-up) — the same documented
  limitation `kotobase-protocols/http.cljc` carries for its own v0.1.

## Develop / test

First-class runtime is **nbb/cljs** (repo-wide runtime priority: kotoba wasm
> clojurewasm > cljs > nbb > jvm/bb):

```bash
git clone https://github.com/kotoba-lang/kotobase .deps/kotobase

# Pure .cljc suite (event/crypto/relay/blossom logic — no sockets)
kbb --backend sci --classpath "src:test:.deps/kotobase/src" bin/run_tests.cljk

# WebSocket transport suite (.cljs-only, real sockets — see
# nostr.relay.transport's docstring for why this is a SEPARATE run)
kbb --backend sci --classpath "src:test:.deps/kotobase/src" test/nostr/relay_transport_test.cljk
```

The `:test` alias in `deps.edn` is the JVM **compat** suite (pure `.cljc`
only — `nostr.relay.transport` is `.cljs`-only and is never loaded there):

```bash
kbb -M:test
```

### Run a relay by hand

```bash
kbb --backend sci --classpath "src:test:.deps/kotobase/src" bin/nostr_relay.cljk listen --port 7777
```

Then connect with any real NIP-01 WebSocket client (a browser
`new WebSocket("ws://localhost:7777")`, `wscat`, etc.) and send
`["EVENT", {...}]` / `["REQ", "sub1", {...filters}]` / `["CLOSE", "sub1"]`.

### REPL example (Blossom)

```clojure
(require '[kotobase.local :as local]
         '[nostr.blossom :as blossom])

(def ctx {:store (local/local-store) :now (quot (System/currentTimeMillis) 1000)
          :base-url "https://blossom.example"})

(blossom/handle ctx {:method :put :path "/upload"
                     :headers {"content-type" "text/plain"} :body "hello"})
;; => {:status 200 :headers {...} :body "{\"url\":\"https://blossom.example/...\", ...}"}
```

## License

Apache-2.0
