# kotoba-lang/org-nist-sha3

**SHA-3 and SHAKE ([NIST FIPS 202](https://doi.org/10.6028/NIST.FIPS.202)) over
Keccak-f[1600], in portable `.cljk` with no dependencies.**

```clojure
(require '[sha3.core :as sha3])

(sha3/sha3-256 bytes)            ; => 32 unsigned bytes     (also -224 -384 -512)
(sha3/sha3-256-hex bytes)        ; => lowercase hex
(sha3/shake128 bytes 64)         ; => 64 bytes of SHAKE128  (also shake256)

;; incremental XOF: absorb in pieces, squeeze in pieces
(let [x (-> (sha3/xof :shake128) (sha3/xof-absorb seed) (sha3/xof-absorb more))
      [x a] (sha3/xof-squeeze x 168)
      [x b] (sha3/xof-squeeze x 168)]
  [a b])
```

## Why this repo exists

FIPS 203 (ML-KEM) and FIPS 204 (ML-DSA) are built on SHAKE and SHA-3. The workspace
had no portable Keccak, so the post-quantum primitives that `kotoba-lang/kagi` needs
could only come from a host (the JDK, BouncyCastle, or `@noble/*`). This is the first
step of removing that dependency (Linear JUN-352, phase P1): Keccak, then ML-KEM-768,
then ML-DSA-65.

## How it is checked

- **NIST CAVP known-answer tests**, committed as data: every ShortMsg vector for all
  four SHA-3 functions and both SHAKEs, the first LongMsg vectors, the SHAKE
  VariableOut vectors (outputs that cross the rate boundary), and the first three
  Monte Carlo checkpoints of each SHA-3 function. Provenance, URLs, and archive
  hashes: [`test/cavp/PROVENANCE.md`](test/cavp/PROVENANCE.md).
- **The tables are computed from the standard, not typed**: the 24 round constants by
  the LFSR of FIPS 202 Algorithm 5, the 25 rotation offsets by Algorithm 2. The suite
  also pins both against the published tables.
- **An independent sweep** against Python's `hashlib` over every message length 0-420
  and output lengths up to 1000 bytes: 2,048 lines, 0 mismatches.
- **Mutation check** (2026-10-23): four deliberately broken copies (a lost `0x80`
  padding byte at the one-byte-room boundary, a wrong theta rotation, a wrong rho
  offset, a wrong SHAKE suffix) are each caught. The padding case is caught only by the
  CAVP boundary vectors, not by the published digests, which is why they are there.
- Both integer models agree: ClojureScript (nbb / `kbb --backend sci`, int32 bit
  operators) and the JVM (int64) give the same 14 tests, 1,768 assertions, 0 failures.

```sh
kbb --backend sci --classpath src:test run-tests.cljk
```

## Representation and speed

The 1600-bit state is 25 lanes of 64 bits held as a vector of 50 unsigned 32-bit
halves, so the same code is correct under int32 and int64 bit operators. Measured
2026-10-23 on one machine: about 3 ms per permutation on nbb/sci and 0.5 ms on the
JVM. It favours clarity over speed.

## Non-claims

- **Not constant time.** Persistent vectors and data-dependent allocation make no
  timing guarantee. That is fine for hashing public data. Callers that hash secrets
  (ML-KEM and ML-DSA seeds) need the timing question answered where they run.
- **`.cljk` is a migration input.** Amu's contract (2026-10-22, `docs/selfhost-priority.md`)
  makes `.kotoba` the canonical source and builds one native image in which the
  runtime and providers are Kotoba code linked with the program; there is no separate
  host. This library is not yet in `.kotoba`, so it does not compile with `amu` to a
  native image. The algorithm and the known-answer tests are settled here first; the
  `.kotoba` port is the next step (JUN-352, P1b).
- Byte-oriented only: inputs and outputs are whole bytes. SHA-3 variants with
  non-byte bit lengths (the `Len` values that are not multiples of 8) are not
  implemented, and neither are `cSHAKE`, `KMAC`, `TupleHash` or `ParallelHash`
  (NIST SP 800-185).
