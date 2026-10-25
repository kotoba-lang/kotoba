# nio

[![CI](https://github.com/kotoba-lang/nio/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/nio/actions/workflows/ci.yml)

`kotoba.nio.bytebuffer` — a portable byte buffer with java.nio.ByteBuffer
semantics (position / limit / relative get / put), identical on JVM
Clojure and ClojureScript, for kotoba-lang protocol libraries.

## Why

Every library that touches wire bytes needs the same trio — read a
little-endian u64, write one back, walk a cursor — and each hand-rolled
version quietly disagreed with the others. The JVM side reached for
java.nio.ByteBuffer (JVM-only, and **big-endian by default** — the real
bug this library was extracted from, in kotoba-vm's keccak), the
ClojureScript side reached for DataView, and the two had to be kept
honest separately. This namespace does it once.

## Contract

- `allocate` / `wrap` produce a buffer at position 0, limit = capacity.
  `wrap` **copies** — it never aliases the caller's mutable memory.
- Relative `get-byte` / `put-byte` / `get-u64` / `put-u64` / `get-bytes`
  / `put-bytes` move position; the `-at` absolute forms take an index and
  do not.
- A relative read past the limit throws `:nio/underflow`; a relative
  write past the limit throws `:nio/overflow` (the
  BufferUnderflowException / BufferOverflowException equivalents).
- `flip` sets limit = position, position = 0 (the write-then-read turn).
  `rewind` / `clear` / `position!` / `limit!` follow java.nio semantics.
- **Little-endian everywhere.** The JVM default (big-endian) is the trap
  this library exists to close.
- u64 values: `long` (two's-complement bits) on :clj, `BigInt` on :cljs —
  they cannot be plain JS numbers past 2^53. Host code treats them
  opaquely and hands them straight back (keccak lanes do exactly this);
  `->u64` and `u64->hex` are the explicit seams.

Backing store: a plain vector of ints in [0,255] behind an atom — the
byte shape every kotoba-lang library already speaks. No platform buffer,
no signed-byte surprises; the reader conditional survives only where the
runtimes genuinely disagree (unsigned 64-bit arithmetic).

```clojure
(require '[kotoba.nio.bytebuffer :as bb])

(def b (bb/allocate 24))
(bb/put-u64 b 1)                ; cursor -> 8
(bb/flip b)
(bb/get-u64 b)                  ; => 1 (long on :clj, BigInt on :cljs)

;; keccak's actual shape: a 136-byte pad block as 17 LE u64 words
(def w (bb/wrap (into [0x01] (into (vec (repeat 134 0)) [0x80]))))
(vec (for [_ (range 17)] (bb/get-u64 w)))
```

## Tests

The CI runs the same suite twice — `kbb -M:test` on the JVM and the
same deftests under nbb — because the u64 seam is exactly where the two
runtimes disagree, and a green JVM suite is not evidence for
ClojureScript.

```sh
kbb -M:test          # JVM
kbb -M:lint          # clj-kondo
kbb --backend sci --classpath src:test scripts/cljs_test_runner.cljk
```

## Background

Extracted from kotoba-vm while building keccak-256 for the EVM
compatibility profiles: the first working version used
java.nio.ByteBuffer directly, read it big-endian by accident, and burned
a debugging session proving the permutation was fine while the buffer
seam wasn't. The lesson generalized: any kotoba-lang library doing wire
arithmetic wants this once, portably.
