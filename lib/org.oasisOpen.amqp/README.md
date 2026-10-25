# kotoba-lang/org-amqp

**AMQP 1.0 (OASIS Standard / ISO/IEC 19464:2014) — the type system, frame
layout, and the nine performatives — in portable `.cljc`, with no
dependencies.**

This is AMQP **1.0**, not AMQP **0-9-1**. They are different, unrelated
wire protocols that happen to share a name — 1.0 is a self-describing
binary type system with symmetric peer-to-peer performatives, 0-9-1 is a
class/method RPC-shaped protocol with field tables and `basic.publish`.
This library implements 1.0 only, and does not blur the two.

## Surface

```clojure
(require '[amqp.types :as t] '[amqp.frame :as f] '[amqp.performative :as p])

(:bytes (t/encode-value [:uint 200]))          ;=> [0x52 200]   (smalluint)
(:value (t/decode-value [0x52 200] 0))          ;=> [:uint 200]

(:bytes (p/encode-performative :open {:container-id "c1"}))
(:bytes (f/encode-frame 0 performative-bytes))  ;=> 8-byte header + body
```

| namespace | |
|---|---|
| `amqp.types` | Part 1 §1.6.7 — every primitive format code, described types, `list`/`map`/`array` compounds. `encode-value`/`decode-value`. |
| `amqp.frame` | Part 2 §2.2/§2.3 — protocol header, the 8-byte frame header (SIZE/DOFF/TYPE/CHANNEL). |
| `amqp.performative` | Part 2 §2.7/§2.8.14 — `open begin attach flow transfer disposition detach end close` + `error`, field-table-accurate. |

Bytes are `Sequential` collections of ints in 0..255, in and out (this
workspace's `org-modbus` convention). Every AMQP value is a Clojure vector
`[tag & data]` — `[:uint 200]`, `[:string "hi"]`, `[:described descriptor
value]` — chosen because several wire format codes name the same logical
type (`uint0`/`smalluint`/`uint` are all "an unsigned 32-bit integer", at
0/1/4 bytes); `decode-value` normalizes all of them back to one tag, since
the width was never semantic.

## Three details that are usually got wrong

**`uint0`/`smalluint`/`uint` (and their five siblings) are the same
logical type at different widths, not different types.** A decoder that
treats them as distinct AMQP types breaks the moment a peer picks a
narrower encoding than expected — which every AMQP peer does, for every
integer that happens to be small. `encode-value` always picks the
narrowest form; `decode-value` always normalizes back to one tag.

**A `list`/`map`'s `size` field counts the count field plus every
element's bytes — not the element bytes alone.** Part 1 §1.6.7, verbatim:
"the number of octets used to encode the count and the list elements."
Getting this off by the count-field's own width (1 or 4 bytes) produces a
decoder that silently misreads where the next value starts.

**64-bit fields (`ulong`/`long`/`timestamp`) are built from bytes with
`+`/`*`/`quot`/`mod`, never a 64-bit `bit-shift`/`bit-or`.**
JavaScript's bitwise operators are 32-bit and signed where the JVM's are
64-bit — shifting or OR-ing across the 32-bit boundary silently wraps on
ClojureScript. Even with that discipline, this codec's own round-trip
suite found and fixed three further traps in exactly this territory: (1)
`(mod n 2^64)` — the textbook two's-complement conversion for a negative
signed 64-bit value — itself produces a number near 2^64 that a JS double
cannot represent exactly, even when the *original* value is tiny (see
`amqp.types/signed64->hi-lo`'s docstring, fixed with limb-at-a-time
subtraction instead); (2) reassembling a `double`'s raw bit pattern by
combining its two 32-bit halves into one JS number has the identical
failure for any negative double (fixed in `f64->bytes`/`bytes->f64` by
never combining them at all); (3) on the JVM, the *same* conversion for a
`ulong`/`long` whose literal exceeds `Long/MAX_VALUE` gets parsed as
`clojure.lang.BigInt`, which `bit-and`/`unsigned-bit-shift-right` reject
outright even when the actual value is a single byte (fixed with the
`as-fixnum` coercion). All three were found by this library's own
randomised sweep across primitive format codes, run on *both* runtimes —
not by inspection, and not by the JVM run alone.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule —
`:amqp/buffer-underrun`, `:amqp/unsupported-format-code`,
`:amqp/bad-boolean-octet`, `:amqp/odd-map-entries`,
`:amqp/compound-size-mismatch`, `:amqp/out-of-range`,
`:amqp/missing-mandatory-field`, `:amqp/unknown-performative`,
`:amqp/not-a-performative`, `:amqp/bad-magic`, `:amqp/frame-too-short`,
`:amqp/bad-data-offset` among them. **Those keywords are contract.**

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

**No published byte-level test vectors exist for this codec.** OASIS's
core-types and transport specs give the format-code table and the
performative field tables verbatim (fetched from docs.oasis-open.org and
cited by section in every namespace's docstring — not recalled from
memory), but unlike Modbus's spec, AMQP 1.0's own text contains no worked
hex examples of an encoded value or frame. Correctness here rests on:

1. A fixed corpus spanning every primitive tag, described types, nested
   compounds, and the `list8`→`list32` structural boundary (300 elements),
   round-tripped exactly.
2. **A randomised sweep across every primitive format code** (`:null`
   through `:symbol`, a deterministic LCG seed so the sweep reproduces
   across runs and across the JVM/ClojureScript hosts), 40 seeds each —
   this is what actually found the four bugs described above.
3. Every performative's field table transcribed verbatim from the spec's
   own `<field>` XML (§2.7.1–§2.7.9, §2.8.14), including the
   trailing-null-omission wire optimization and default-value application.
4. Negative tests asserting the *specific* named reason keyword, with a
   discrimination proof for each: break one thing, confirm the exact
   assertion fires (not a different failure), restore, re-verify green.

Where a test value is hand-derived from a table rather than a published
vector, it's commented `constructed, not a published spec vector`.

## Not here

**`decimal32`/`decimal64`/`decimal128`** (IEEE 754-2008 decimal, binary
integer decimal encoding). They're in the format-code table and in
nothing this workspace's performatives use; encoding a base-10 floating
point format nobody can exercise is how a codec acquires untested
branches nobody notices are wrong. Decoding an unrecognized format
code — decimal's included — returns `:amqp/unsupported-format-code`.

**`attach`'s `source`/`target` fields and `transfer`/`disposition`'s
`state` field** are each a described-type value with their own
multi-field composite layout (§3.5.3 Source, §3.5.4 Target, §3.4 Delivery
State) — a second full subsystem this library does not model. They are
passed through opaquely: give `encode-performative` an already-built
`amqp.types` tagged value (or `nil`) for those fields, and
`decode-performative` gives one back the same way.

**Connections, sessions, links, sockets, TLS, SASL negotiation state.**
This is the wire codec — encode a performative to bytes, decode bytes
back to a performative — not a client, not a broker, not a network
server. No IO, no sockets, no threads. Section 5 (SASL) is out of scope;
`amqp.frame` knows the SASL frame `TYPE` byte (0x01) exists and parses
around it, nothing more.

## License

Apache License 2.0.
