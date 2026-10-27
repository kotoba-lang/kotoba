# Itonami OS W3c slice: GF(2^255-19) arithmetic in the guest (2026-10-28)

Ed25519 (ADR-0277, W3) works over GF(2^255-19). This slice adds `aiueos.gf25519`
(`os/aiueos/kotoba/aiueos/gf25519.kotoba`), after TweetNaCl: an element is 16 limbs of nominally 16 bits in u64
words of a 4096-byte caller-owned workspace region (used as signed i64; limbs may go negative after a subtraction
and the carry pass renormalises). The native subset has no arithmetic shift right, so the floor shift by 16 is
`(u64-shift-right (+ v 2^52) 16)` minus 2^36, valid for |v| < 2^52 (the largest intermediate is below 2^45).
Operations: add, sub, copy, carry, multiply (16x16 limb products, fold by 38, two carry passes), inverse
(z^(p-2), 254 squarings), unpack/pack (canonical little-endian, two conditional subtractions of p).

`--profile gf25519` boots `gf-entry.kotoba`: before the desktop starts, the guest runs a self-test on three (a, b)
pairs and leaves a*b, inv(a), a+b and a-b (32 bytes each) in the browser context (128 bytes per case from word 320,
marker word 99 = "GF25"). The QEMU gate compares every result with Python big-integer arithmetic mod p and checks each
is canonical (< p). The pairs: a generic pair, (p-1, p-1) and (1, 2^254) (edges that exercise carries and reduction).

Evidence: `native-gf25519-qemu.json` (QEMU TCG, Apple Silicon, no network, no input), built from the Amu checkout's
pinned root alone (signed compiler `9d023d99...`); kernel/EFI reproduced; 32 modules. 3 cases x 4 operations = 12
comparisons, all equal. A wrong carry, fold or pack changes a result and fails the comparison.

What it is not: three pairs only (no randomised or exhaustive testing), no point arithmetic, no scalar
multiplication, no Ed25519 vectors, no key, no signature, nothing stored. The compile error met on the way
("region extent source" disagreement) came from an unused helper called with a different region extent; removing the
dead helper fixed it.

Limits: QEMU TCG only; diagnostic. Source change and built candidate with a QEMU result; not deployed.
