# Itonami OS W3d slice: Ed25519 public keys from seeds in the guest (2026-10-28)

`aiueos.ed25519` (`os/aiueos/kotoba/aiueos/ed25519.kotoba`) derives an Ed25519 public key from a 32-byte seed
(RFC 8032 section 5.1.5), after TweetNaCl, on top of `aiueos.sha512` and `aiueos.gf25519`: SHA-512 of the seed, clamp
(`h[0] &= 248`, `h[31] = (h[31] & 127) | 64`), scalar multiplication of the base point by double-and-add over
extended twisted Edwards coordinates (add formula with 2d, a 64-word point in the workspace), affine conversion with
one field inverse, and encoding (y with the sign of x in the top bit). The conditional swap of the two points is a mask
select (`mask = -bit`, `t = mask & (p ^ q)`), so there is no branch on a scalar bit; the SHA-512 and field routines
branch only on loop counters. Limits of that claim: memory access timing is not analysed, and this is not a
constant-time qualification.

`--profile ed25519` boots `ed-entry.kotoba`: before the desktop starts, the guest derives the public keys for the
three RFC 8032 section 7.1 test seeds and leaves 128 bytes per case from word 320 of the browser context (the first
32 bytes are the encoded key; marker word 99 = "ED25"). The QEMU gate compares them with the published public keys:

| case | public key (equal to RFC 8032 section 7.1) |
| -- | -- |
| test 1 | d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a |
| test 2 | 3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c |
| test 3 | fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025 |

Evidence: `native-ed25519-qemu.json` (QEMU TCG, Apple Silicon, no network, no input), built from the Amu checkout's
pinned root alone (signed compiler `9d023d99...`); kernel/EFI reproduced; 34 modules. A wrong field operation, point
formula, clamp or encoding changes the key and fails the comparison; the gate also requires the three keys to differ.
The `gf25519` profile of the previous slice was re-run after the library refactor below and still passes.

Refactor on the way: the compiler refuses a library that exports a function whose region arguments it cannot trace
when another profile links the library without calling it. So `aiueos.gf25519` now exports only what Ed25519 uses
(`ld st gf-add gf-sub gf-mul gf-inv gf-pack`), and the field self-test and the unpack helper moved into `gf-entry.kotoba`.

What it is not: no signing, no verification, no reduction mod the group order L, no device key (the seeds are the
public RFC test vectors), nothing stored, nothing wired into a consent flow. QEMU TCG only; diagnostic. Source change
and built candidate with a QEMU result; not deployed.
