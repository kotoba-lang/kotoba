# AGENTS.md — org-nist-sha3

SHA-3 and SHAKE (FIPS 202), portable `.cljk`, zero dependencies. Part of the
post-quantum primitive work for `kotoba-lang/kagi` (Linear JUN-352, phase P1).

## Invariants

- **No host hash in `src/`.** `MessageDigest`, `hashlib` and `shasum` appear only
  under `tools/` and in this repo's notes, as oracles.
- **Tables are computed, never typed.** Round constants come from the LFSR of FIPS 202
  Algorithm 5 and rotation offsets from Algorithm 2. The tests pin them against the
  published tables; do not replace the computation with a literal table.
- **The CAVP vectors are data, generated.** Do not edit `test/sha3/cavp/*.cljk`;
  re-run `tools/import_cavp.py` (see `test/cavp/PROVENANCE.md`).
- **Both integer models are gated**: `kbb --backend sci --classpath src:test run-tests.cljk`
  (int32) and the JVM (int64; copy `src` and `test` to `.cljc` and run
  `clojure.test`). A bug that only one model shows is a real bug.
- No `:kotoba/export` metadata in the `ns` form until a `.kotoba` reading exists: the
  JVM evaluates an `ns` attr-map, so the exported names must already be defined.
- `.cljk` here is a migration input. The canonical source is `.kotoba` (Amu
  `docs/selfhost-priority.md`, 2026-10-22), with no separate host or guest. Keep the
  code in plain loops over vectors of integers and avoid host-only forms, so that the
  port stays mechanical.

## Traps

- **Padding at one byte of room.** When exactly one byte is left in the block, the
  domain suffix and the final `0x80` land in the same byte (`suffix | 0x80`). Only the
  CAVP boundary vectors catch a mistake here.
- **cljs bitwise operators are int32.** Everything is normalised through `u32` after any
  operation that can leave the unsigned range, including `bit-not`.
- **Squeeze continues where it stopped.** `xof-squeeze` keeps an offset into the current
  block; squeezing 10 then 20 bytes must equal squeezing 30. Tested across the
  SHAKE128 (168) and SHAKE256 (136) rate boundaries.
- **A Monte Carlo test is slow** (about 12,000 permutations); it is the bulk of the
  roughly 40 s the nbb run takes.
