# Release signing key — custody

This directory holds the **qualification** release signing key (RSA-2048),
created 2026-10-25 with the owner's OK to resolve the JUN-140 signed-release
blocker.

## The split

`src/aiueos/sbom.cljk` and `os/aiueos/scripts/verify-release-signature.py`
both document the same rule: **the signing key never enters the repository or
the image builder; signing happens offline.** The verifier performs only the
public-key operation. `sign-release-image.py` is the *caller* that signs.

## Qualification vs production

- `release-signing-key.pem` — the qualification private key (mode 0600). It is
  in-tree so the qualification receipts can be reproduced and read back. This
  is the one deliberate exception, made for JUN-140's `:release` rows, and it
  qualifies nothing outside this repository's own gates.
- `release-signing-key.pub` — the matching public key. The verifier takes it
  explicitly (`--public-key`); nothing in the image trusts it by default.
- The production release key is separate and stays offline. When the owner
  swaps it in, the qualification receipts remain historical evidence and the
  release rows need re-signing with the production key.

## Scheme

RSASSA-PKCS1-v1_5 over SHA-256, 256-byte signatures — identical to the
application-catalog admission (`make-aiuefs-image.py`) so the machine's one
RSA verifier covers both.
