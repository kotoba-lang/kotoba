# gov.nist.mlDsa — ML-DSA-65 (FIPS 204) in native .kotoba

`kotoba/mldsa/core.kotoba` (`ns mldsa.core`) is ML-DSA-65 written directly in native
`.kotoba` (JUN-352 P1b), on the native SHA-3 port in
`../gov.nist.sha3/kotoba/sha3/core.kotoba`. Bytes are `:vector-i64` of 0..255.

| function | result |
|---|---|
| `keygen xi` | pk (1952) ++ sk (4032), from the 32-byte seed (Algorithm 6) |
| `sign sk m ctx rnd` | signature (3309), pure ML-DSA with a context of at most 255 bytes; `rnd` is 32 bytes, all zero for the deterministic variant |
| `verify pk m ctx sig` | true for a valid signature |
| `sign-internal` / `verify-internal` | the same with M' given (Algorithms 7 and 8) |
| `sign-mu` / `verify-mu` | the same with the 64-byte mu given ("external mu") |
| `zetas` | the NTT table, 1753^BitRev8(i) mod q |

Bad lengths, values outside 0..255 and a context over 255 bytes give an empty signature
or false. The signing loop is bounded at 814 iterations, the smallest bound FIPS 204
allows, and gives an empty signature there.

## Native gate

`kotoba/mldsa/native_gate.kotoba` returns a bitmask (31 = pass):

1. keyGen tc 26 and 27;
2. sigGen: pure deterministic (tg 3 tc 41), internal deterministic (tg 10 tc 147),
   pure hedged (tg 15 tc 214) and external-mu hedged (tg 21 tc 301);
3. sigVer: pure tc 43 (valid) and 38 (modified hint), external-mu tc 121 (valid), 126
   (modified z) and 129 (modified hint), internal tc 137 (modified hint), and two
   crafted signatures under the keyGen tc 26 key (below);
4. the NTT table recomputed, a keyGen / sign / verify round trip, and a changed
   message, context or signature byte failing to verify;
5. refusal of bad input.

The vectors are from usnistgov/ACVP-Server commit `975de31eb83d87039ec88934fdc47d8c312b892d`
(`gen-val/json-files/ML-DSA-{keyGen,sigGen,sigVer}-FIPS204/internalProjection.json`),
ML-DSA-65 groups. Long values are compared by SHA3-256 digest. `tools/gen_gate.py`
writes the gate from those files. `tools/reference.py` is an independent Python
reference; it agreed with every ACVP case it was run on: 5 keyGen cases, the
first 3 cases of each non-pre-hash sigGen group (3, 9, 10, 15, 21, 22) and sigVer groups
3, 9 and 10 in full and makes the two crafted signatures. Every ACVP negative
also fails the challenge comparison, so a verifier that skipped the hint-order or
`||z||` check would still reject them. The crafted ones isolate those checks: two hint
indices swapped in an otherwise valid signature, and a signature that passes everything
except `||z|| < gamma1 - beta`.

```sh
G=/Users/junkawasaki/github/workspaces/<agent>/<task>   # a new task-owned directory
{ echo '(ns mldsa-gate (:export [main]))'
  sed '/^(ns /,/))$/d' ../gov.nist.sha3/kotoba/sha3/core.kotoba
  sed '/^(ns /,/))$/d' kotoba/mldsa/core.kotoba | sed 's/sha3\///g'
  sed '/^(ns /,/))$/d' kotoba/mldsa/native_gate.kotoba; } > "$G/gate.kotoba"
# compile with the Amu root (Mac: --target aarch64-macos, extract-native main,
# package fs2-cli-stdio-general, sign) and run with FD 3 = $G
```

Measured 2026-10-30 on Apple M1 Max with the Amu Mac root of main `91faa123`
(`amu-full-root.macho`, packaged `fs2-cli-stdio-general`); the gate image ran in about
1 s:

| image | change | exit |
|---|---|---|
| gate | none | **31** |
| ctl-zeta | second NTT zeta + 1 | 133 (trap: signing never accepts and the image runs out of heap) |
| ctl-kappa | mask counter advanced by 1, not l | 29 |
| ctl-ctx | pure prefix byte 0 -> 1 | 9 |
| ctl-sib | SampleInBall sign inverted | 9 |
| ctl-hint | hint index order not checked | 27 |
| ctl-znorm | `||z||` bound not checked in verify | 27 |

## Non-claims

- **Not constant time.** Data-dependent loops and allocation; no timing guarantee.
- **No random source.** The caller supplies the seed and `rnd`.
- **ML-DSA-65 only.** ML-DSA-44 and ML-DSA-87 are not implemented, nor is HashML-DSA
  (pre-hash) or the external-mu sigGen interface with a separate `tr`.
- **Heap.** Inside one image a signing that rejects 500-700 times traps (no output)
  before the 814-iteration bound.
- **Coverage.** The gate runs 12 ACVP cases natively, not the full groups; no x86_64 run
  and no CI job yet.
