# AGENTS.md — gov.nist.mlDsa

ML-DSA-65 (FIPS 204) in native `.kotoba`. Depends only on the native SHA-3 port in
`../gov.nist.sha3/kotoba/sha3/core.kotoba`. Part of the post-quantum primitive work
for `kotoba-lang/kagi` (Linear JUN-352, phase P1b). Unlike `gov.nist.mlKem`, there is
no `.cljk` predecessor: the library started in `.kotoba`.

## Invariants

- **No host crypto in `kotoba/`.** Hashing is the native `sha3.core` only. Python
  `hashlib` appears only under `tools/`, as the oracle that wrote the gate.
- **The gate is generated.** Do not edit `kotoba/mldsa/native_gate.kotoba` by hand;
  re-run `tools/gen_gate.py` on the pinned ACVP-Server commit it names.
- **The NTT table is checked, not trusted.** The gate recomputes `1753^BitRev8(i) mod q`.
- **Arithmetic stays below 2^47.** Products of two values below q are about 2^46; keep
  the reduction after every product.
- **Refuse, do not throw.** Bad lengths, values outside 0..255 and a context over 255
  bytes give an empty signature or false.

## Traps

- **ACVP-Server hex is uppercase.** The gate's hex reader takes lowercase only, so the
  generator lowercases every value.
- **A vector literal holds at most 64 items** (E2116); the NTT table is four literals.
- **The signing loop allocates per iteration** and nothing is reclaimed inside one
  image: a signing that rejects 500-700 times runs out of heap and traps before the
  814-iteration bound returns an empty vector. An honest signature needs about five.
- **Hint and `||z||` checks are invisible to the ACVP negatives**, which also fail the
  challenge comparison. The two crafted signatures in the gate are what catch a missing
  check.
