# Itonami OS W3b slice: SHA-512 in the guest (2026-10-28)

ADR-0277 needs Ed25519, which needs SHA-512. This slice adds `aiueos.sha512`
(`os/aiueos/kotoba/aiueos/sha512.kotoba`), a FIPS 180-4 SHA-512 in the native Kotoba subset: u64 words in i64
arithmetic (the adds rely on two's-complement wrap-around, the rotates on `u64-shift-right`), multi-block with the
128-bit length padding, input bound 12288 bytes, a 4096-byte caller-owned workspace region, output 64 bytes.

`--profile sha512` boots `sha512-entry.kotoba`: before the desktop starts, the guest hashes three messages and
leaves the digests in browser-context words 320..367 (marker word 99 = "SH51", written last). The QEMU gate
compares them with `hashlib.sha512` computed on the host:

| message | words | result |
| -- | -- | -- |
| "abc" | 320..335 | equals hashlib (ddaf35a1...) |
| the 112-byte FIPS 180-4 two-block message | 336..351 | equals hashlib (8e959b75...) |
| "abd" (negative control) | 352..367 | equals hashlib of "abd" and differs from "abc" |

Evidence: `native-sha512-qemu.json` (QEMU TCG, Apple Silicon, no network, no input), built from the Amu
checkout's pinned root alone (signed compiler `9d023d99...`); kernel/EFI reproduced; 32 modules. A broken
rotate, carry or padding changes the digest and fails the comparison; the first run of this gate caught a
wrong offset in the gate itself (digests read as zeros), which was fixed before the passing run.

Limits: three messages only (a 3-byte and a 112-byte message, so one and two blocks); no RFC 8032 Ed25519
vectors yet, no key, no signature, nothing is stored; the object is not yet wired into any consent flow.
QEMU TCG only; diagnostic. Source change and built candidate with a QEMU result; not deployed.
