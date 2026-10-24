# org-ietf-blake2

`blake2.*` — **BLAKE2b, [RFC 7693](https://www.rfc-editor.org/rfc/rfc7693)**, in
portable `.cljc` with **no dependencies**, at any digest length from 1 to 64
bytes.

| Namespace | What it owns |
|---|---|
| `blake2.core` | The hash: parameter block, compression, padding, keyed mode. |
| `blake2.word` | The one file that knows which runtime it is on. |

## Why this exists

Filecoin hashes everything with BLAKE2b, at three different lengths: **4 bytes**
for an address checksum, **20** for an address payload, **32** for every CID on
the chain. Neither runtime this workspace targets can produce those.

- A stock JDK ships no BLAKE2 provider, so `MessageDigest` cannot do it at all.
- Node's `crypto` has `blake2b512` and nothing else — the digest length is not
  a parameter you can pass, and BLAKE2b-256 is **not** the first 32 bytes of
  BLAKE2b-512 (the length goes into the parameter block, so it is a different
  hash). There is a test for exactly that confusion.

So it had to be written. It is its own repo rather than a file inside
`io-filecoin` because `io-filecoin-node` needs it too, and a shared primitive
that lives inside one of its two consumers is how a workspace ends up with two
copies — the lesson ADR-2607254100 recorded when AWS SigV4 turned out to exist
six times here.

## Usage

```clojure
(require '[blake2.core :as blake2])

(blake2/blake2b (blake2/utf8 "abc"))              ; 64 bytes
(blake2/blake2b some-bytes {:digest-size 4})      ; a Filecoin address checksum
(blake2/blake2b-256 some-bytes)                   ; the Filecoin CID hash
(blake2/blake2b msg {:key k :digest-size 64})     ; keyed (MAC) mode
```

Bytes in: a byte-array, a `Uint8Array`, or a seq of `0..255` ints — the three
shapes `multiformats.core` accepts. Bytes out: a byte-array on `:clj`, a
`Uint8Array` on `:cljs` (deliberately not a vector, because `aget`/`alength`
return `nil`/`0` on a `PersistentVector` instead of throwing — the failure mode
`multiformats.core/multihash-sha256` documents having hit).

## Design

**One code path, two arithmetics.** BLAKE2b is defined over 64-bit unsigned
words with wrapping addition. The JVM has that in `long`. JavaScript has
nothing of the kind — `Number` loses integer exactness past 2^53 and every
bitwise operator truncates to *32* bits, so the obvious translation is silently
wrong rather than slow. `BigInt` is the only JS primitive with the right
semantics, so that is what a word is there, wrapped back with
`BigInt.asUintN(64, …)`. All of that lives in `blake2.word`; `blake2.core` is a
single portable algorithm above it.

The cost is real: a compression round performs 96 word operations, and on the
JavaScript side each allocates. For the inputs this exists to serve — a 65-byte
public key, a 21-byte checksum preimage, a block of CBOR — that does not
matter. **Hashing a large file on the ClojureScript side would.**

## What is not here

- **Tree hashing** (RFC 7693 §2.10). Fanout and depth stay at the sequential
  values `1`/`1` and the parameter block's tree fields stay zero. No BLAKE2bp,
  no unlimited-depth mode.
- **BLAKE2s.** The 32-bit variant is a different set of constants and
  rotations; nothing in this workspace has asked for it.
- **Streaming.** `blake2b` takes all its input at once.

## Verification

A hash implementation cannot check itself, and a suite that only compares this
library to this library proves nothing.

- `test/blake2/vectors.cljk` is **generated** by `testdata/gen_vectors.py` from
  **CPython's `hashlib`** — a binding to the BLAKE2 reference implementation, a
  different implementation in a different language. 25 vectors: every digest
  length Filecoin uses, the block boundaries (1/63/64/127/128/129/255/256/257
  bytes), keyed mode including the case where the key block is also the last
  block, and the two Filecoin shapes.
- Two values are pinned **by hand from the documents**, not from the generator:
  RFC 7693 §A.1's `BLAKE2b-512("abc")`, and entry 0 of the BLAKE2 reference
  `blake2b-kat.json`. If CPython ever regressed, the generator would move every
  other assertion in lockstep and nothing would fail. These two would.
- Both runtimes run the whole suite in CI, because they run different
  arithmetic (see above), not because it is tidy.

```sh
kbb -M:test                                              # JVM
npm run test:cljs                                            # nbb
python3 testdata/gen_vectors.py > test/blake2/vectors.cljk   # regenerate
```
