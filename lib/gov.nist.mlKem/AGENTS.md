# AGENTS.md — org-nist-ml-kem

ML-KEM-768 (FIPS 203), portable `.cljk`. Depends only on `org-nist-sha3`. Part of the
post-quantum primitive work for `kotoba-lang/kagi` (Linear JUN-352, phase P1).

## Invariants

- **No host crypto in `src/`.** No JCA, no BouncyCastle, no `@noble`, no OpenSSL. They
  appear only under `tools/` as oracles. Hashing is `sha3.core` only.
- **Constants are computed, never typed.** Zetas and gammas come from `17^BitRev7(i) mod
  3329`; the tests pin the first entries against FIPS 203 Appendix A.
- **The ACVP vectors are data, generated.** Do not edit `test/mlkem/acvp/*.cljk`;
  re-run `tools/import_acvp.py` (see `test/acvp/PROVENANCE.md`).
- **Both integer models are gated**: `kbb --backend sci --classpath
  src:test:../org-nist-sha3/src run-tests.cljk` and the JVM (copy `src`, `test` and
  the sha3 `src` to `.cljc`, then `clojure.test`). A bug that only one shows is real.
- **Arithmetic stays small.** Only `+ - * mod quot` on values below 2^40, so doubles
  and longs agree; bit operators only on values below 2^21. Do not "optimise" the
  encode/decode loops with shifts on large accumulators.
- **Implicit rejection is not an error.** A wrong ciphertext of the right length returns
  `J(z || c)`. Only malformed *lengths* and failed section 7 checks throw. Keep these
  two apart.
- `.cljk` here is a migration input; the canonical source is `.kotoba` (Amu
  `docs/selfhost-priority.md`). Keep plain loops over vectors of integers so that the
  port stays mechanical.

## Traps

- **`G(d || k)` carries the parameter byte** (`k` = 3) in the final standard. Drafts used
  `G(d)`; a mutant with the draft form fails all 25 key generations.
- **`A[i][j] = SampleNTT(rho || j || i)`**: the indices are swapped in the seed. In
  encryption the transpose is used, `u = NTT^-1(A^T y)`.
- **Decompress is `round(q * y / 2^d)`**, computed exactly as
  `(2 q y + 2^d) quot 2^(d+1)`. Flooring instead of rounding fails the ACVP vectors.
- **`ByteDecode_12` reduces mod q**, so the modulus check re-encodes and compares; a
  length check alone accepts a key with a coefficient of 4095.
- **The comparison `c = c'` must not short-circuit** (it is a XOR-OR over all bytes) and
  the key is chosen with a mask, not an `if`.
