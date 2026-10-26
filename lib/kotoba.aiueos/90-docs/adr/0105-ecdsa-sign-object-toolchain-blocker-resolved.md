# 0105 — The ECDSA sign object toolchain blocker, resolved

Accepted 2026-08-26. Follows ADR-0104, which wrote the ECDSA P-256 sign object,
proved its algorithm against RFC 6979, and reported that this checkout's object
toolchain could not compile it. This resolves that blocker: the object now
compiles to a valid kernel `.o`, links into the kernel, and passes a boot
known-answer test.

## What the blocker actually was

ADR-0104 named the symptom — `ELF region exceeds its allocation` (52309 >
32768) — but not the cause. The cause is two absences in the pinned toolchain,
neither in the object:

1. **The 32768 was a red herring.** It is the `.text` region of the bootable
   single-object IMAGE (`kotoba.native.elf64/package-kernel`), padded to a
   fixed `kernel-data-offset` = 8 pages. `compile-source` for the kernel target
   eagerly builds BOTH that image and the relocatable object; the image throws
   first. **aiueos links the relocatable object and never uses that image** —
   the shipped `.text` is already 48219 bytes, far over 32768. Stubbing
   `package-kernel` lets the object build.
2. **The pinned `kotoba-native` (a60da444) does not know the ecdsa objects.**
   Its `kernel-object-entries` allowlist has no `aiueos-ecdsa-p256-sign` (so
   `package-kernel-object` would stamp the wrong symbol, `kotoba_aiueos_probe`),
   and its fuel tiers do not put the ecdsa objects in the 250,000,000 tier a
   scalar multiplication needs (the tier `x25519` already uses; without it the
   object spends its 512 and hits the prologue `ud2`). The shipped
   `ecdsa-p256.o` (verify) does not reproduce under this pin either — it was
   built by a newer, uncached toolchain. This is exactly the
   `reproduce-kotoba-kernel-object.sh` "the full advance was measured and not
   taken" condition.

## The fix

`os/aiueos/scripts/reproduce-ecdsa-sign-object.cljk` patches those two absences
into the pinned toolchain in-process — adds the two ecdsa entries to
`kernel-object-entries`, adds them to the 250M fuel tier, stubs `package-kernel`
— then compiles. Result:

- `os/aiueos/kotoba/ecdsa-p256-sign.o` — a valid ET_REL kernel object, 50864
  bytes, `.text` 50020, global symbol `kotoba_aiueos_ecdsa_p256_sign`, fuel
  immediate `250,000,000`. Digest pinned in `build-uefi.sh`.
- The proper long-term home for the two patches is `kotoba-native` upstream;
  the recipe documents and reproduces the fix until that pin advances.

## Measured

- `main.c` `aiueos_ecdsa_sign_kat` (behind `-DAIUEOS_ECDSA_SIGN_KAT`) calls the
  linked object with the RFC 6979 A.2.5 private key, SHA256("sample") and nonce
  k, and requires the 64-byte output to equal the published r||s
  (`efd48b2a…716` ‖ `f7cb1c94…da8`).
- Built into the kernel (1028112 bytes, under the 1 MiB ceiling) and run under
  QEMU: `AIUEOS_ECDSA_SIGN_OK rfc6979-a2.5 r||s-match`. (See the gate evidence
  for this commit.) The object is behind its own flag, not `AIUEOS_SSH_LISTEN`:
  at ~50 KiB it does not fit alongside the listener under 1 MiB, so the two are
  measured in separate builds until the sshd needs both — at which point the
  kernel will have to shrink or the object split.

## I4 status

RED, but the last crypto object is now a working, boot-verified kernel brick.
What remains for a login is the SSH binary-packet transport (X25519 + SHA-256 +
the ADR-0103 entropy, all present), the host-key signature over the exchange
hash using this object, `aes128-gcm@openssh.com` record protection, and the
publickey userauth (existing ECDSA verify) — plus fitting the listener and this
object into one kernel under 1 MiB. No SHA-512, no Ed25519.
