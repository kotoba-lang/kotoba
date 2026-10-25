# kotoba-lang/proto

Protocol Buffers in portable `.cljc` — the **schema** and the **bytes**.

| Namespace | What it owns |
|---|---|
| `proto.core` | Schema as data → `.proto` source text. "Hiccup for wire schemas." |
| `proto.wire` | The encoding itself: decode and encode protobuf bytes. |
| `kotoba.proto` | Compatibility facade over `proto.core`. |

Neither namespace touches a host: no `byte-array`, no `Uint8Array`, no
reader conditionals. Bytes go in and out as seqs of unsigned ints 0-255, the
convention the rest of this workspace's portable `.cljc` uses.

## `proto.wire` — lossless by design

The decoder keeps every field's exact byte slice, so re-encoding reproduces
the input byte for byte:

```clojure
(require '[proto.wire :as w])

(w/decode [0x08 0x96 0x01])
;; => [{:field-number 1 :wire-type :varint :value [0x96 0x01] :raw [0x08 0x96 0x01]}]

(w/varint-value (w/field (w/decode [0x08 0x96 0x01]) 1))  ;; => 150
```

That property is not politeness, it is the reason the namespace exists.
Protocols that sign a message — Storj's order limits, most S3-adjacent
schemes — serialize it, sign the bytes, and store the signature in a field of
that same message. Verifying means removing the signature field and
reproducing the remaining bytes **exactly**:

```clojure
(-> signed-bytes w/decode (w/remove-field 3) w/encode)   ;; the bytes that were signed
```

A decoder that discards fields it does not recognise, or that rewrites a
varint into its own canonical form, produces different bytes and every
signature fails with no indication why. So unknown fields survive, repeated
fields keep their order, and a non-canonically encoded length prefix comes
back out exactly as it went in. `test/proto/wire_test.cljk` asserts that with
a field only `:raw` can carry — and the suite has been checked to fail when
`:raw` is ignored.

Interpretation is the caller's job: this namespace never guesses what a field
number means. Groups (proto2 wire types 3 and 4) are rejected rather than
mis-parsed, because a group body has no length prefix and guessing would
desynchronise everything after it.

## Test

```sh
kbb -M:test                                   # JVM
kbb --backend sci --classpath src:test scripts/verify-cljs.cljk # ClojureScript
kbb -M:lint
```

Both runtimes are run in CI. The ClojureScript job is not redundant: varints
are exactly where the two disagree — JavaScript's bitwise operators truncate
to int32, and a double stops holding integers exactly past 2^53 — and a JVM
long exercises neither path.
