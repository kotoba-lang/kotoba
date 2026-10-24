# kotoba-lang/org-nist-ml-kem

**ML-KEM-768 ([NIST FIPS 203](https://doi.org/10.6028/NIST.FIPS.203)), the
module-lattice key-encapsulation mechanism, in portable `.cljk`.** The one dependency
is [`org-nist-sha3`](https://github.com/kotoba-lang/org-nist-sha3) (SHAKE and SHA-3).

```clojure
(require '[mlkem.core :as mlkem])

;; The caller supplies the randomness. This library has no random source.
(let [{:keys [ek dk]} (mlkem/keygen d z)     ; d, z: 32 random bytes each
      {:keys [k c]}   (mlkem/encaps ek m)    ; m: 32 random bytes
      k2              (mlkem/decaps dk c)]   ; (= k k2)
  ...)

(mlkem/valid-encapsulation-key? ek)   ; length + modulus check (FIPS 203 section 7.2)
(mlkem/valid-decapsulation-key? dk)   ; length + hash check    (FIPS 203 section 7.3)
```

Everything is a vector of unsigned bytes. For ML-KEM-768: `ek` 1184, `dk` 2400,
ciphertext `c` 1088, shared key `k` 32.

## Implicit rejection

`decaps` of a well-formed but *wrong* ciphertext does not fail. It returns
`J(z || c)` (SHAKE256 of the secret value `z` stored in `dk`, then `c`), which looks
random and differs from the encapsulator's key, as FIPS 203 Algorithm 18 requires.
The comparison and the choice between the two keys are done without branching on the
data. A key or ciphertext of the **wrong length**, a decapsulation key whose stored
`H(ek)` does not match, or an encapsulation key with an unreduced coefficient is a
different thing: it is refused with an exception, because the input checks of
section 7 say so.

## Why this repo exists

`kotoba-lang/kagi` needs ML-KEM-768 to open its vault, and today gets it from the
JDK or BouncyCastle. This is the second primitive of removing that dependency
(Linear JUN-352, phase P1): Keccak (`org-nist-sha3`), then this, then ML-DSA-65.

## How it is checked

- **NIST ACVP known-answer tests**, committed as data: all 25 key generations, all 25
  encapsulations, all 10 decapsulations (four of them modified ciphertexts that test
  implicit rejection), and all 20 key checks, for ML-KEM-768. Provenance, URLs and file
  hashes: [`test/acvp/PROVENANCE.md`](test/acvp/PROVENANCE.md).
- **Independent definitions of the building blocks**: the NTT constants are computed
  (`17^BitRev7(i) mod 3329`) and pinned against Appendix A; NTT multiplication is
  checked against schoolbook multiplication in `Z_q[x]/(x^256+1)`; encode/decode
  round-trips; compression error is checked against its bound for every coefficient.
- **OpenSSL as a second implementation** (`tools/openssl_interop.py`, throwaway keys):
  key generation from OpenSSL's seed gives OpenSSL's decapsulation key; each side
  decapsulates the other's ciphertexts to the same key; a modified ciphertext gives
  the same rejection key. Three keys, all agree (2026-10-23).
- **Mutation check** (2026-10-23): seven deliberately broken copies (rounding in
  compression, a wrong divisor in `SampleNTT`, no implicit rejection, `J(c || z)` for
  `J(z || c)`, the draft `G(d)` without the parameter byte, no modulus check, no hash
  check) are each caught, with between 6 and more than 80 failing assertions each.
- Both integer models agree: ClojureScript (nbb / `kbb --backend sci`) and the JVM
  give the same 16 tests, 208 assertions, 0 failures.

```sh
kbb --backend sci --classpath src:test:../org-nist-sha3/src run-tests.cljk
```

## Speed

Measured 2026-10-23 on one machine, per operation: about 125-155 ms on nbb/sci and
about 32-36 ms on the JVM. It favours clarity over speed.

## Non-claims

- **Not constant time.** Persistent vectors, data-dependent allocation and rejection
  sampling make no timing guarantee. The branch-free key selection in `decaps` is
  written that way, but the language runtime does not promise it. Whoever uses this to
  protect secrets needs the timing question answered where it runs.
- **No random source.** `keygen` and `encaps` take their randomness as arguments. The
  caller must supply 32 uniformly random bytes for each of `d`, `z` and `m`.
- **ML-KEM-768 only.** ML-KEM-512 and ML-KEM-1024 are not implemented.
- **`.cljk` is a migration input.** Amu's contract (2026-10-22,
  `docs/selfhost-priority.md`) makes `.kotoba` the canonical source and builds one
  native image in which the runtime and providers are Kotoba code linked with the
  program; there is no separate host. This library is not yet in `.kotoba`, so it does
  not compile with `amu` to a native image. The algorithm and the known-answer tests
  are settled here first; the `.kotoba` port is the next step (JUN-352, P1b).
- It is the *internal* algorithms of FIPS 203 (16, 17, 18) with explicit randomness,
  plus the section 7 input checks. The standard's key-generation and encapsulation
  wrappers that draw their own randomness are left to the caller.
