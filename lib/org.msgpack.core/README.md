# kotoba-lang/org-msgpack

**[MessagePack](https://msgpack.org) encode and decode in portable `.cljc`,
with no dependencies.**

MessagePack already existed twice in this workspace and neither copy could be
shared. `checkpointer` carries a hand-rolled codec that is `#?(:clj ...)`
throughout with throwing ClojureScript stubs; the same repository's JavaScript
side depends on npm `@msgpack/msgpack`. So the wire format is implemented once
per runtime, and a fix to either is a fix to one. MessagePack is a byte
format; it has no reason to be host-shaped.

## Use

```clojure
(require '[msgpack.core :as mp])

(mp/encode! {"op" "put" "n" 60000})   ;=> [0x82 0xa2 0x6f 0x70 …]
(mp/decode! [0xa2 0x68 0x69])         ;=> "hi"
```

| | |
|---|---|
| `encode` / `encode!` | value → `{:status :ok :bytes […]}`, or throw |
| `decode` / `decode!` | bytes → `{:status :ok :value v :consumed n}` / `{:status :incomplete :need n}` / `{:status :error :reason kw}` |
| `decode-all` | drain a stream, returning values and the partial tail |
| `max-safe-integer` / `min-safe-integer` | the integer domain, see below |

## The value mapping

| msgpack | Clojure |
|---|---|
| nil | `nil` |
| bool | `true` / `false` |
| int | integer |
| float 32/64 | double |
| str | string |
| bin | `{:msgpack/bin [bytes]}` |
| array | vector |
| map | map |
| ext | `{:msgpack/ext {:type n :data [bytes]}}` |

`bin` and `ext` are tagged because they would otherwise be indistinguishable
from an array of small integers and from a map. The tag is a plain map, so a
decoded value stays comparable and printable.

Bytes are `Sequential` collections of ints in 0..255, in and out — the one
representation both runtimes agree on without typed arrays.

## Three things to know before you use it

**Integers are the exact-integer intersection of the two runtimes**:
`-(2^53-1) .. 2^53-1`. Outside that, `encode` and `decode` both refuse with
`:integer-unrepresentable`. A JVM `long` reaches 2^63-1 and a ClojureScript
number does not, so supporting the wider range would mean this codec answers
differently depending on where it runs — silently. If you need the full 64-bit
range on the wire, carry it as `bin` or `ext`.

**Whether `3.0` is an integer is a property of the host, not of this codec.**
ClojureScript has one numeric type, so `3.0` is `integer?` there and encodes as
a fixint, while the JVM sees a double and writes a float64. Nothing here can
reconcile that. Do not put a whole-valued double on a wire where the
distinction matters.

**Map entry order is the map's own seq order.** For a `hash-map` that order is
unspecified, so two encodes of an equal map may differ in bytes. MessagePack is
a wire format, not a content-addressing scheme, and every conformant decoder
reads either — but if you need stable bytes, hand this an `array-map` or a
`sorted-map`.

## Errors

Returned, never thrown. `:reason` is a keyword naming the rule that rejected
the value: `:integer-unrepresentable`, `:never-used-byte` (0xc1, which the
spec reserves and forbids), `:unknown-type-byte`, `:unsupported-type`. **Those
keywords are contract.** Pin them in your tests; renaming one is a breaking
change here.

## Verify

```sh
kbb -M:test                                                        # JVM
kbb --backend sci --classpath "$(kbb -A:cljs -Spath)" scripts/verify-cljs.cljk   # ClojureScript
```

Twenty of the assertions are **known answers from the real
`@msgpack/msgpack`** — `scripts/gen-mst-vectors.mjs` in
`kotoba-lang/checkpointer` imports the npm package, encodes a fixed list of
values, and writes the hex. Both halves are transcribed into
`test/msgpack/vectors.cljk`: the values from the generator's source, the bytes
from its output. They are the only vectors here with independent provenance,
and everything else is round-trip — which on its own can only tell an encoder
that agrees with its own decoder from one that agrees with MessagePack.

Run both runtimes. Three things in this library are a different operation on
each: the UTF-8 codec, IEEE 754 conversion, and integer width.

## What the JVM caught, and what it hid

Two defects in the 64-bit paths were found on the JVM and would have been
invisible under ClojureScript, which is the reverse of the usual asymmetry and
worth stating:

- `read-int` folded the bytes unsigned and subtracted `2^(8n)` afterwards.
  For an 8-byte value that constant overflows a `long`, so the correction
  threw before it could run. The sign is now taken from the top byte and
  carried through the fold.
- Encoding a negative int64 formed `n + 2^64`, which overflows the same way.
  It now uses floored `mod`, which returns the two's-complement word directly
  on both runtimes.

The decode guards for out-of-range integers are in two stages for the same
reason: a byte pre-check that bounds the magnitude so the fold cannot
overflow, then an exact range check on the folded value. A guard placed only
after the fold is unreachable in precisely the case it exists for.

## Not here

The msgpack **timestamp extension** (ext type -1 with 4/8/12-byte payloads) is
carried through as a plain `{:msgpack/ext {:type -1 …}}` and not interpreted.
Time is `kotoba-lang/time`'s subject, and a codec that silently turned bytes
into an instant would be making a calendar decision on the caller's behalf.
