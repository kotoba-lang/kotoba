# Itonami OS W3e slice: Ed25519 signatures in the guest (2026-10-28)

`aiueos.ed25519` now also signs (RFC 8032 section 5.1.6), after TweetNaCl: SHA-512 of the seed gives the
clamped scalar `a` and the prefix; `r = SHA-512(prefix || M) mod L`; `R = r*B`; `k = SHA-512(R || A || M) mod L`;
`S = (r + k*a) mod L`; the signature is `R || S`. The reductions use TweetNaCl's `modL` over a 64-limb integer held
in workspace words (the floor shifts by 4 and 8 are built from `u64-shift-right` and a bias, since the subset has no
arithmetic shift). The scalar multiply-add is a 32x32 byte product accumulated into the same limbs. The point
multiplication is the one of the public-key slice (mask-select swap, no branch on a scalar bit).
Messages up to 64 bytes (a 1024-byte working buffer); the hash input regions have runtime-computed lengths.

`--profile ed25519` now also signs, before the desktop starts, the three RFC 8032 section 7.1 messages
(lengths 0, 1 and 2: empty, `72`, `af82`) with their seeds and leaves the 64-byte signatures at words 768.. of the
browser context. The QEMU gate compares them byte for byte with the published signatures:

| case | message | signature (equal to RFC 8032 section 7.1) |
| -- | -- | -- |
| test 1 | (empty) | e5564300c360ac72...e7a100b |
| test 2 | 72 | 92a009a9f0d4cab8...b0c00 |
| test 3 | af82 | 6291d657deec2402...1ec40a |

The public-key comparison of the previous slice is unchanged and still passes in the same run. Evidence:
`native-ed25519-qemu.json` (QEMU TCG, Apple Silicon, no network, no input), built from the Amu checkout's pinned
root alone (signed compiler `9d023d99...`); kernel/EFI reproduced; 34 modules. A wrong modL carry, scalar
multiply-add, hash input layout or encoding changes the signature and fails the comparison; the gate also requires
the three signatures to differ.

What it is not: no verification (there is no verifier in the guest yet, so a signature is checked only against
the published values), the seeds are the public RFC test vectors so no device key exists, nothing is stored,
nothing is wired into a consent flow, no message over 64 bytes, and no constant-time qualification (memory access
timing and the data-dependent loop bounds of modL are not analysed). QEMU TCG only; diagnostic. Source change and
built candidate with a QEMU result; not deployed.
