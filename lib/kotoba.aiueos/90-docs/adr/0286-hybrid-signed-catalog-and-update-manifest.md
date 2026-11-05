# ADR-0286 — Signed catalog and update manifest: Ed25519 + ML-DSA-65 together

Date: 2026-11-05

## Status

Proposed (JUN-812, JUN-813). Design only: nothing here is implemented and no row is claimed. It fills what ADR-0283 and
ADR-0284 left open for the catalog and update artifacts, and it asks the owner for the decisions in the last section. It
registers no origin, creates no key and changes no kernel. The installed-state schema is ADR-0284 and is not repeated.

## Context

Measured in the source (2026-11-05):

- `native/update.kotoba` admits an `AIUEIMG1` image: a 128-byte header (64-byte manifest, Ed25519 signature) and the image.
  The verifier is classical Ed25519 only and keeps no installed version (rollback check is `version >= 1`).
- `gov.nist.mlDsa` (`kotoba/mldsa/core.kotoba`) is ML-DSA-65 (FIPS 204) in native `.kotoba` with an ACVP gate (keyGen,
  sigGen, sigVer). It works on heap `:vector-i64` values. The kernel modules (`aiueos.ed25519`, `aiueos.lib.sha256-stream`)
  work on fixed kernel regions and do not allocate, so the library cannot be linked into the kernel unchanged. The "ML-DSA-65
  verifier is open work" in `update-policy.json` therefore means a region-based port, not a missing algorithm.
- ADR-0277 already states the rule: Ed25519 together with ML-DSA-65, both verified, no classical-only downgrade.
- The kernel-v3 text margin after amu#1825 is about 511 KB (kotoba#1228 build), so code size no longer blocks this.

## Decision

1. **Both signatures, always.** A catalog or image is accepted only if its Ed25519 and its ML-DSA-65 signature both verify
   under the pinned keys. One valid signature never suffices, and a missing one is a refusal, not a downgrade.
2. **`AIUEIMG2` header.** 4096 bytes: 0 `"AIUEIMG2"`, 8 version (u64 LE), 16 size, 24 key id (u32) and reserved zero, 32 SHA-256
   of the image (as `AIUEIMG1`, the 64-byte manifest), 64 Ed25519 signature (64 bytes), 128 ML-DSA-65 signature (3309 bytes),
   rest zero. Both signatures cover the 64-byte manifest, with ML-DSA context `"AIUEIMG2"` so a signature made for another
   object type does not verify here. The image follows the header. `AIUEIMG1` is refused once `AIUEIMG2` ships.
3. **Pinned keys.** Ed25519 public key (32 B) and ML-DSA-65 public key (1952 B), indexed by key id, are baked into the
   kernel. Packed 8 bytes per word, the ML-DSA key is about 244 words (order of 40 KB of text at the measured
   ~160 B per packed word: affordable). Rotation = a new key id in a new image signed by the old keys; no network supplied key
   is ever a root.
4. **Rollback.** The highest accepted `version` per channel is stored in the sealed NVMe state and signed by the device key
   (ADR-0284's append-only chain, one more record kind `image-version`). A manifest with `version` not above it is refused.
5. **Catalog object `AIUECAT1`.** Same header shape: version, count (1..64), key id, SHA-256 of the body, both signatures over
   the manifest. Body entries, each fixed 128 bytes: dock id (u32, installable apps start at 19), title (ASCII, 32), manifest
   CID (36), bundle CID (36), size (u32), reserved. The packed catalog compiled into the kernel (JUN-811) stays the default and
   offline list; a fetched catalog only adds entries, and each entry is admitted by CID (`aiueos.cid-v1-admit`) before use.
6. **Operations.** `fetch-catalog`, `download-app` and the update `check`/`download`/`install` stay separate each-operation
   approvals. Verification is local and sends nothing.

## ML-DSA-65 verify in the kernel: sizing (estimate, to be measured)

From FIPS 204 ML-DSA-65 (k=6, l=5, q=8380417; public key 1952 B, signature 3309 B = 48 c-tilde + 5x640 z + 61 hint):

- Raw inputs held in regions: pk 1952 B + signature 3309 B.
- Working set if verify streams row by row (generate A[i][*] from rho with SHAKE128, accumulate A*z - c*t1*2^d for row i,
  UseHint, pack w1): z in NTT form 5 KiB, c 1 KiB, accumulator 1 KiB, one temp polynomial 1 KiB, w1 bytes 768 B, SHA-3 state
  200 B. About 9 KiB plus the inputs: roughly 15 KiB, which exceeds the 8 KiB browser context and the 4 KiB owned page the
  Ed25519 verifier uses, so it needs its own owned window.
- Work: 5 forward NTTs of z, 1 of c, 6 x 5 pointwise products, 6 inverse NTTs, one SHAKE256 over mu and w1 (about 6 x 256
  coefficients). The gate must show it completes within the desktop frame budget or runs in the update flow only (it is
  not on the interactive path).
- Gate: the ACVP sigVer cases already in `gov.nist.mlDsa` plus the two crafted hint/`||z||` cases, run on the kernel build, and a
  differential run against the library's heap verifier on random signatures. Negative controls: one flipped byte in pk, c-tilde,
  z and hint each refuses; Ed25519-only and ML-DSA-only images refuse.

## Order of work

1. This ADR accepted; owner decisions below.
2. Region-based `aiueos.mldsa65-verify` (new module), its own QEMU profile like `ed25519`, ACVP + differential gate.
3. `AIUEIMG2` in `update.kotoba` with the self-test fixtures signed by published test keys (the fixtures prove the path, not a key).
4. Version record in the sealed state; `auto-install` may then be called qualified.
5. `AIUECAT1` reader and the installer's `fetch-catalog`/`download-app` once an origin and key exist.

## Not decided here (owner)

- **Origins.** The catalog origin, the artifact origin and the update origin (full https origins; they also fix the static CSP of
  the dapp). None is registered.
- **Key custody.** Who generates the Ed25519 and ML-DSA-65 signing keys (the operator's Mac as for `AIUEIMG1`, or a
  hardware token), their key ids, and the rotation rule. The seeds must never enter this repository.
- Acceptance of the `AIUEIMG2` layout and of retiring `AIUEIMG1`.
- Whether a publisher catalog (third-party) may exist beside the distribution catalog (ADR-0284 keeps publisher trust a user choice).
