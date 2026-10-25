# kotoba-wire

[![CI](https://github.com/kotoba-lang/wire/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/wire/actions/workflows/ci.yml)

EDN-over-TCP framing and socket-pool primitives shared across kotoba-lang
protocol libraries — extracted from
[`kotoba-lang/dtn`](https://github.com/kotoba-lang/dtn)'s transport layer
so [`kotoba-lang/turn`](https://github.com/kotoba-lang/turn) and
[`kotoba-lang/net`](https://github.com/kotoba-lang/net) don't have to
reinvent the same plumbing when they gain real I/O.

Built on [`kotoba-lang/bytes`](https://github.com/kotoba-lang/bytes)
(portable byte-vector primitives) rather than any platform-specific byte
type, so the framing/codec layers are pure, portable `.cljc` — testable
under plain JVM `kbb -M:test`, not only under a Node-hosted
ClojureScript runtime.

## Wire format

Unchanged from what `kotoba-lang/dtn`'s TCP transport already used before
this extraction, so this library is provably wire-compatible with `dtn`'s
existing behavior: each message on the socket is a **4-byte big-endian
length prefix** followed by that many bytes of **UTF-8 `pr-str`'d EDN**.
Decoded on the read side with `clojure.edn/read-string`.

```
[ 4 bytes: length N, big-endian ][ N bytes: UTF-8 pr-str'd EDN ]
```

## Contract

Three namespaces, layered strictly bottom-up — each one knows nothing
about the layer above it:

- **`kotoba.wire.framing`** (pure `.cljc`) — length-prefix framing over
  plain `kotoba.bytes`-shaped byte-vectors. Knows nothing about EDN or
  sockets.
- **`kotoba.wire.edn`** (pure `.cljc`) — EDN-map <-> length-prefixed-frame
  codec, built on `kotoba.wire.framing` + `kotoba.bytes`. Knows nothing
  about sockets.
- **`kotoba.wire.tcp`** (Node-only `.cljs`) — the actual `node:net` socket
  I/O: server, lazy connect-or-reuse outbound socket pool, framed write.
  Generic — no bundles, no e164, no `:dtn/*` (or any other protocol's)
  message shape.

```clojure
;; kotoba.wire.framing — pure length-prefix framing over byte-vectors
(require '[kotoba.wire.framing :as framing])

(framing/frame-length-prefix [104 105])
;; => [0 0 0 2 104 105]   ; 4-byte BE length prefix + payload

(framing/defragment [0 0 0 2 104 105 0 0 0 1])
;; => {:frames [[104 105]] :remainder [0 0 0 1]}
;; one complete frame extracted, plus a trailing incomplete
;; length-prefix (waiting for more bytes) carried forward as :remainder
```

```clojure
;; kotoba.wire.edn — EDN <-> framed-byte-vector codec
(require '[kotoba.wire.edn :as edn])

(def framed (edn/encode {:hello "wire"}))
;; => a length-prefixed byte-vector

(edn/decode-frames [(subvec framed 4)])  ; caller has already defragmented
;; => [{:hello "wire"}]
```

```clojure
;; kotoba.wire.tcp — Node-only socket I/O (nbb)
(require '[kotoba.wire.tcp :as tcp])

(def server (tcp/start-server! 5100
              (fn [decoded-map socket] (println "got:" decoded-map))))

(def pool (atom {}))
(def sock (tcp/connect-or-reuse! pool "peer-a" "127.0.0.1" 5100))
(tcp/send-framed! sock {:hello "wire"})

(tcp/close-all! pool)
```

## Background

This repo is Phase 2 of a shared-library consolidation across
`kotoba-lang` protocol repos. Phase 1 (already landed) extracted
[`kotoba-lang/bytes`](https://github.com/kotoba-lang/bytes) out of
`kotoba-lang/turn`: portable byte-vector primitives and pure
SHA-1/HMAC-SHA1, generic enough that any protocol-message codec or
credential/HMAC path can depend on them instead of re-implementing them.

Phase 2 (this repo) does the same for `kotoba-lang/dtn`'s TCP transport:
`dtn` had its own inline 4-byte-big-endian-length-prefix framing built
directly on Node `Buffer`s, its own per-connection buffer-accumulation /
defragmentation logic, and its own ad-hoc socket pool (lazy
connect-or-reuse). None of that plumbing is actually DTN-specific — it's
generic "move EDN maps over a TCP byte stream" machinery that
`kotoba-lang/turn` (relay I/O) and `kotoba-lang/net` (gossip I/O) will
need too once they gain real I/O of their own. `kotoba-lang/dtn` has been
refactored to depend on this library instead of maintaining its own copy
of this logic — see `dtn`'s README ("Internet-overlay transport (real
I/O)" section) and `dtn`'s `src/kotoba/dtn/transport/tcp.cljs` for what
now consumes this library (DTN-specific behavior — store-and-forward,
relay, auth, replay protection — all stays in `dtn`; only the low-level
"how do bytes actually get framed and pushed down a socket" mechanics
moved here).

## Test

```bash
kbb -M:test
kbb -M:lint
```

`kotoba.wire.framing` and `kotoba.wire.edn` are pure `.cljc` and fully
covered by `kbb -M:test` (JVM), including `defragment`'s boundary
cases: empty input, fewer than 4 bytes (no complete length prefix yet), a
frame split across two/many `defragment` calls, multiple complete frames
arriving in a single call, and zero-length-payload frames.
`kotoba.wire.tcp` is `.cljs`-only (real `node:net` I/O) and is exercised
indirectly through `kotoba-lang/dtn`'s E2E transport demo rather than
having its own nbb-only test suite in this repo.

## License

Apache License 2.0. See `LICENSE`.
