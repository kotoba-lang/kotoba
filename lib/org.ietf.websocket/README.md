# kotoba-lang/org-ietf-websocket

**[RFC 6455](https://www.rfc-editor.org/rfc/rfc6455) framing and handshake in
portable `.cljc`, with no dependencies.**

Two nodes in this workspace — `inga-node` and `torihiki-node` — depend on the
npm package `ws` for one thing: turning a payload into WebSocket frames and
back. That is arithmetic over bytes, and `ws` is a Node addon boundary, so the
framing simply disappears the moment a build targets the JVM or kotoba-WASM.
This library is the in-language replacement.

## Surface

```clojure
(require '[websocket.frame :as f]
         '[websocket.handshake :as h])
```

`websocket.frame` — §5

| | |
|---|---|
| `encode` / `encode!` | frame map → bytes. Refuses over-long or fragmented control frames |
| `decode` | bytes → `{:status :ok :frame … :consumed n}` / `{:status :incomplete :need n}` / `{:status :error :reason kw}` |
| `decode-all` | drain a read buffer, returning whole frames and the partial tail |
| `mask-payload` | §5.3 masking, which is its own inverse |
| `close-payload` / `parse-close` | §5.5.1 status code + UTF-8 reason |
| `string->bytes` / `bytes->string` / `hex` | conversions, re-exported from `websocket.bytes` |

`websocket.handshake` — §4

| | |
|---|---|
| `accept-key` | `base64(SHA-1(key + GUID))`, with SHA-1 injected |
| `valid-key?` | §4.1 — the key must be base64 of exactly 16 bytes |
| `client-request` / `server-response` | header maps |
| `validate-server-response` | checks status, `Upgrade`, `Connection`, and the accept value |
| `base64-encode` / `base64-decode` | RFC 4648 §4 |

## Two decisions worth knowing before you use it

**Errors are returned, not thrown.** `decode` answers a map whose `:status` is
`:ok`, `:incomplete`, or `:error`, and an error carries a keyword `:reason`
naming the rule that rejected the frame — `:control-frame-too-long`,
`:reserved-opcode`, `:non-minimal-length`, `:fragmented-control-frame`,
`:length-msb-set`, `:length-unrepresentable`, `:truncated-close-payload`.
**Those keywords are contract.** Pin them in your tests; renaming one is a
breaking change here. A caller that must send a Close frame naming the failure
needs the rule, not a message string.

**SHA-1 is injected.** `kotoba-lang/hash` owns SHA-1 for this workspace and is
written in `.kotoba`, which a `.cljc` leaf cannot require; and duplicating a
hash to avoid one seam is the worse trade. Both runtimes already ship it:

```clojure
;; JVM
(fn [bs] (vec (map #(bit-and % 0xFF)
                   (.digest (java.security.MessageDigest/getInstance "SHA-1")
                            (byte-array (map unchecked-byte bs))))))
;; Node
(fn [bs] (let [h (.createHash (js/require "node:crypto") "sha1")]
           (.update h (js/Uint8Array.from (clj->js (vec bs))))
           (vec (array-seq (js/Uint8Array.from (.digest h))))))
```

Base64 *is* implemented here — 30 lines of table lookup with no security
surface. Pulling a dependency for it would pin this leaf to one runtime.

## Bytes

Everything is a `Sequential` of ints in 0..255, in and out. That is the one
representation both runtimes agree on without typed arrays, and it keeps a
frame a *value*: comparable, printable, usable as a fixture. Convert at your
own edge.

## Verify

```sh
kbb -M:test                                          # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

**Run both.** They are not redundant, and this is not a formality — the
ClojureScript runner caught two real bugs in this library that the JVM
reported as green:

1. **Shift width.** ClojureScript takes a bit-shift count mod 32, so a 64 KiB
   frame's length encoded with `>>> 48` came back as `>>> 16` and announced
   itself as `0x0001000000010000`. The 64-bit length path is now written with
   division, not shifts. Reintroducing the shift leaves `kbb -M:test`
   green and turns the ClojureScript run red — that asymmetry is measured, not
   asserted.
2. **`(map int s)`.** Correct on the JVM; under ClojureScript a character is a
   one-character string and `int` of one is not a code point, so
   `Sec-WebSocket-Accept` was computed over a vector of zeros. The
   concatenation is ASCII, so UTF-8 encoding is the same bytes and right on
   both.

A third bug went the other way: the 64-bit length guards were originally
placed *after* the eight bytes were folded into a number, where on the JVM the
fold throws `long overflow` before the guard can run. A guard that is
unreachable in the one case it exists for is not a guard.

## Test vectors

Every framing test is RFC 6455 §5.7 verbatim — the only frames in the
specification written out on both sides, and so the only ones that can tell an
encoder that agrees with its own decoder from one that agrees with the RFC.
The handshake test is the §1.3 key/accept pair; base64 is RFC 4648 §10.

## Not here

Extension negotiation (`permessage-deflate` and friends) is not implemented.
The RSV bits are carried through faithfully in both directions so an extension
layer can sit on top, but nothing here interprets them. Deflate itself is
`kotoba-lang/org-ietf-deflate`.

Sockets are not here either. This library never opens one — it turns bytes
into frames and frames into bytes. Connecting, reading and writing belong to
the caller's transport capability.
