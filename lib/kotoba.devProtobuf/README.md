# dev-protobuf

[![CI](https://github.com/kotoba-lang/dev-protobuf/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dev-protobuf/actions/workflows/ci.yml)

**Protocol Buffers wire format** (protobuf.dev, *Encoding*) — encode and decode,
schema-driven, portable `.cljc`, zero dependencies, **no code generation**.

Deliberately only the wire format. No `.proto` parser, no descriptor set, no
generated classes. A schema is an ordinary EDN map:

```clojure
(def ipns-entry
  {1 {:name :value        :type :bytes}
   5 {:name :sequence     :type :uint64}
   8 {:name :signature-v2 :type :bytes}
   9 {:name :data         :type :bytes}})

(pb/encode ipns-entry {:value (pb/utf8-bytes "/ipfs/bafy…") :sequence 3})
(pb/decode ipns-entry octets)
```

That is enough for the two things this workspace needs protobuf for — IPNS
records and Kademlia DHT messages — and it keeps the schema reviewable next to
the spec it came from instead of hidden in generated output.

## Unknown fields survive byte-for-byte

The rule that makes or breaks this library.

Protobuf is designed so a reader can skip fields it does not know, and every
real deployment relies on it: a record written by a newer Kubo carries fields
your schema has never heard of. A decoder that drops them and an encoder that
cannot put them back means the message **cannot round-trip** — and for a
*signed* message that is not a compatibility inconvenience, it is a validation
failure. The signature covers bytes that no longer exist.

```clojure
(pb/round-trips? my-schema bytes-from-a-newer-writer)  ; => true
```

Unknown fields are kept as `{field-number [wire-type payload]}` under
`:protobuf/unknown` and re-emitted in field-number order. A *known* field that
arrives with the wrong wire type is also kept rather than coerced — coercing
would silently reinterpret someone else's data.

## Encoding is deterministic

The spec permits any field order and defines no canonical form. This library
always emits ascending field number and never emits an absent field. A
signature is over bytes, so "the same message" has to mean the same octets on
every host and every run.

## Stated limits

**Negative varints are refused, on both hosts.** Encoding one needs the full
unsigned 64-bit pattern (ten groups); decoding one needs a value past
`Long/MAX_VALUE` on the JVM and past 2^53 on ClojureScript. Supporting it would
mean a big-integer path on both sides for a case no schema here has — and a
half-supported signed path is worse than none, because it would encode on one
host and fail to decode on the other. Declare the field `sint32`/`sint64` and
it is zigzag-encoded correctly, at one octet for small negatives.

`decode-varint` refuses past nine groups for the same reason, so the two
directions agree about exactly which values exist. The guard runs *before* the
multiplier advances — 128^9 is exactly `Long/MAX_VALUE + 1`, so checking
afterwards would overflow before it refused.

**Values above 2^53-1 are refused, on both hosts.** Varints and fixed fields
alike, in both directions.

This paragraph used to say the opposite — that values are host integers, exact
to 2^64 on the JVM and 2^53 on ClojureScript, and that "IPNS sequence numbers,
TTLs in nanoseconds and Kademlia cluster levels are all far inside it."
Measured 2026-08-17, both halves were wrong. The edge was enforced nowhere:

```
octets for 2^53+1  ->  JVM 9007199254740993    CLJS 9007199254740992
octets for 2^63-1  ->  JVM 9223372036854775807 CLJS 9223372036854776000
```

returned as ordinary values with no error, so the same octets were two
different numbers depending on where they were read. And the example given as
safely inside the range is the one that is not: **an IPNS TTL is in
nanoseconds, and 2^53 ns is 104 days.** A record with a one-year TTL is an
ordinary record.

So the edge is enforced now, for the same reason negatives are refused: a
value one host accepts and the other silently corrupts is worse than a value
neither accepts. A caller who genuinely needs the top eleven bits of a uint64
should read the field's raw octets — growing a big-integer path here is a
decision with a cost, not an oversight.

`fixed64` was broken outright on ClojureScript in both directions:
`bit-shift-right` operates on int32 there **and** takes its shift count modulo
32, so encoding emitted the low four octets twice and decoding added them
twice. That path is arithmetic now. `fixed32` had the same shape — a top octet
of `0xFF` decoded negative.

**Groups (wire types 3 and 4) are absent.** They were deprecated by proto2
itself.

## Test

**Both runtimes, every time.**

```
kbb -M:test                                    # JVM
kbb --backend sci --classpath src:test test/run.cljk         # ClojureScript
```

18 tests / 66 assertions, identical on both, including the spec's own varint
examples.

Running only the JVM is what let the three defects above sit in the green for
months: this library's callers (`tech-ipfs-specs-ipns`,
`io-libp2p-specs-kad-dht`) run in Workers and browsers, so ClojureScript is
the runtime it actually ships to, and it was the one nothing ran. Two of the
assertions were host-dependent in the test itself — `(dec (bit-shift-left 1
31))` is 2^31-1 on the JVM and -2147483649 on ClojureScript, and `(int \A)`
is 65 on the JVM and 0 on ClojureScript — so they compared different things
on the two hosts and passed on both.
