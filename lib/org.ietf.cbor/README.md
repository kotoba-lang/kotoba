# dag-cbor-clj

[![CI](https://github.com/kotoba-lang/dag-cbor/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dag-cbor/actions/workflows/ci.yml)

**Definite-length CBOR (RFC 8949) encode/decode — with both a canonical
(dag-cbor key-sorted) encoder and an order-preserving one for signing
payloads. No deps, babashka-friendly, and real `.cljc`: verified on both
the JVM and ClojureScript, byte-identically.**

CBOR keeps getting hand-rolled in kotoba/IPLD codebases (CACAO issuers, Pregel
coordinators each open-code the major-type headers). This is that once.

```clojure
(require '[cbor.core :as cbor])

(cbor/encode {"a" 1 "b" [2 3]})        ;=> bytes, map keys sorted dag-cbor style
(cbor/decode bytes)                     ;=> {"a" 1 "b" [2 3]}
(cbor/encode-ordered [["b" 1] ["a" 2]]) ;=> bytes, keys in the GIVEN order
```

- **`encode`** — deterministic: map keys sorted shorter-first-then-bytewise (dag-cbor),
  so the same data always yields the same bytes (content addressing, IPLD).
- **`encode-ordered`** — a map from an ordered `[k v]` seq, keys emitted as given.
  CAIP-122 CACAO and other insertion-order-sensitive wire formats need this;
  canonical sorting would corrupt the signature payload.
- **`decode`** — exactly one top-level value; maps → `{}`, arrays → `[]`,
  text → `String`, byte-strings → bytes (byte-array on JVM, `Uint8Array` on
  cljs), ints/finite float64 → numbers, true/false/null. Trailing bytes fail.

### The typed encoder (Kotoba)

`encode` works out each value's type at run time. Kotoba has no value whose
type is only known at run time, so the Kotoba module is a typed encoder
instead (adr-2609242330 S1c): one function per CBOR type, with types resolved
statically. Each function returns a *fragment*, which is a vector of ints
holding one encoded item. The same functions exist on the hosts and give the
same bytes as `encode` (`test/cbor/core_typed_test.cljk`,
`scripts/verify-pure-leaves.cljk`, `scripts/verify-kotoba-golden.cljk`).

```clojure
(cbor/fragment-bytes
 (cbor/encode-map
  (-> (cbor/map-entries)
      (cbor/map-entry "a" (cbor/encode-uint 1))
      (cbor/map-entry "b" (cbor/encode-array
                           (-> (cbor/array-items)
                               (cbor/array-item (cbor/encode-uint 2))
                               (cbor/array-item (cbor/encode-text "x"))))))))
;=> the bytes of (cbor/encode {"a" 1 "b" [2 "x"]})
```

The scalar encoders are `encode-null`, `encode-bool`, `encode-uint`,
`encode-nint`, `encode-int`, `encode-f64` (always 8 bytes), `encode-text`,
`encode-bytes` and `encode-tag n fragment`. Arrays are built with
`array-items`, `array-item` and `encode-array`. Maps are built with
`map-entries` and `map-entry` (string keys), then closed with `encode-map`
(canonical DAG-CBOR key order) or `encode-map-ordered` (insertion order).
On the hosts only, you also get `encode`, `encode-ordered`, `decode`,
`tagged` and `ordered`.

Supported major types: 0 uint · 1 negint · 2 byte-string · 3 text · 4 array ·
5 map · 6 explicit tags · 7 (false/true/null/finite float64). No indefinite
lengths. Floats always encode as IEEE-754 binary64; NaN and infinities are
rejected. `io-ipld` layers DAG-CBOR's tag-42-only and string-key rules on top.

## Portability

`cbor.core` used to be `cbor.core.clj` — JVM-only despite living in a
`.cljc`-named ecosystem. It is now portable and its byte plumbing is pure
(adr-2609242330 S1, 2026-09-24): the encoder builds a vector of ints 0..255
and the decoder threads a position through the reads. What differs per host
is a small set of leaves (UTF-8, float64 bits, the byte container), each
with a `:default` clause that is a Kotoba body (`f64-to-bits`,
`string-code-point-at`, ...). `test/cbor/golden.edn` pins the encoded bytes
of a 2,367-value corpus to the pre-rewrite encoder, and
`scripts/verify-pure-leaves.cljk` runs every `:default` body on nbb against
its host twin. Two leaves have no `:default` on purpose -- UTF-8 bytes to a
string (Kotoba has no string constructor from bytes) and "is this a byte
string" (the Kotoba bytes representation is not decided) -- so the compiler
names them as `function body is empty`.

One correctness pitfall worth calling out because it's easy to reintroduce:
**big-endian multi-byte integers (the `uint32`/`uint64` header forms) must be
built with arithmetic (`+`/`*`/`quot`/`mod`), not `bit-and`/`bit-shift-*`.**
JavaScript's bitwise operators coerce their operand to Int32/Uint32 *before*
operating, so e.g. `(unsigned-bit-shift-right 4294967296 24)` silently
truncates `4294967296` (2^32) to `0` first — the bit pattern above 32 bits is
gone before the shift even happens. This is invisible on the JVM (`long` is
genuinely 64-bit) and only shows up as silently-wrong CBOR bytes for values
≥ 2^32 on `:cljs`. `byte-at` (encode) and `read-n` (decode) use
division/mod and `+`/`*` specifically to stay correct up to
`Number.MAX_SAFE_INTEGER` (2^53) on both platforms.

## Correctness

```bash
kbb -M:test                    # JVM — 13 tests / 75 assertions
npm install && npm run test:cljs   # real ClojureScript, via shadow-cljs node-test
```

The `kbb -M:test` alternative that used to be noted here is **unavailable**:
babashka was retired as this workspace's script host (ADR-2607173000) and the
conversion left `scripts/tasks.edn` empty, so it has had no runnable path since
2026-07-17 (ADR-2608131600). `kbb -M:test` is unaffected.

```
Ran 7 tests containing 55 assertions.
0 failures, 0 errors.
```

on both platforms — including RFC 8949 Appendix-A vectors, canonical
key-ordering, order preservation, byte-string round-trips, and the
`uint32`/`uint64` boundary values (`0xffffffff`, `0x100000000`) that the
JS-bitwise-truncation pitfall above would otherwise silently corrupt.

Verification note: an initial ClojureScript check via `nbb` (a fast
SCI-based cljs interpreter, good for quick smoke tests) reported a false
failure on the nested-`OrderedMap` case — nbb's `deftype` support doesn't
implement direct `.-field` access, which this namespace's `OrderedMap`
uses. That is an `nbb` interpreter limitation, not a bug here: the CI job
above compiles with real `shadow-cljs` (the same toolchain `net-kotobase`/
`app-aozora` deploy with) and passes all 7 tests with 0 failures. Lesson
kept here on purpose: a fast interpreter is a good first pass, not a
substitute for compiling with the real target toolchain before trusting a
"portable" claim.

## License

Apache-2.0.
