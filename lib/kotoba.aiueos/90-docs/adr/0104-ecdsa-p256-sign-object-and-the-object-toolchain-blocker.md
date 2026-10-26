# 0104 — The ECDSA P-256 sign object, and the object-toolchain blocker

Accepted 2026-08-25. Tranche six of root ADR
`adr-2608251418-aiueos-usb-install-and-headless-bootstrap`; it follows the
entropy API and the ECDSA crypto-path decision of ADR-0103. It writes the one
crypto object the SSH login needs, proves its algorithm against RFC 6979, and
records — honestly — that this checkout's object toolchain cannot compile it.

## What was written

`os/aiueos/kotoba/ecdsa-p256-sign.kotoba` — bounded ECDSA P-256 / SHA-256
deterministic (RFC 6979) **sign**. It reuses, by copying (a kernel object may
not call another, ADR-0030), the P-256 field, point and modular-inverse
arithmetic that `ecdsa-p256.kotoba` already carries for verify. The RFC 6979
HMAC_DRBG nonce loop runs in C (which has `hmac_sha256`); the object takes the
nonce k and computes, in the same 16-bit-limb representation as verify:

    r = (k * G).x mod n
    s = k^-1 * (h + r * d) mod n

ABI `[priv-32, digest-32, k-32, out-64 (r||s BE), workspace-2048]`, returning 1
unless r or s is zero (on which the caller retries with the next RFC 6979 k).

## What was proved

`os/aiueos/scripts/ecdsa-sign-oracle.cljk` — the FORMULA and ABI, against the
RFC 6979 A.2.5 P-256/SHA-256 "sample" published vector. A BigInt reference
computes r,s the exact way the object does and reproduces the published
`efd48b2a…716` / `f7cb1c94…da8` byte-for-byte. So the design is not drifting
from RFC 6979: given the object toolchain, this is what the object must emit.

## What is blocked, and why it is not this code's fault

The object **cannot be compiled, linked or boot-tested in this checkout.** Three
independent measurement paths were tried and all fail:

1. **Kernel object.** `bin/kotoba-compiler ... --target x86_64-aiueos-kernel-v1`
   throws `ELF region exceeds its allocation` (size 32768, actual 52309). This
   is not specific to the new object — it happens when recompiling the SHIPPED
   `ecdsa-p256.kotoba` (verify) too. The pinned amu (`9cf3a0a`) this workspace
   uses now emits a ~52 KB code region for the ecdsa objects, over the
   32768-byte kernel-object limit. Smaller objects (fnv1a 1.3 KB, sha256
   17.8 KB) still compile. This is the condition
   `reproduce-kotoba-kernel-object.sh` already documents: the compiler advance
   "was measured and not taken", and the checked-in `.o` bytes can no longer be
   reproduced.
2. **KIR interpreter.** `ir/execute` has no way to provide linear memory, so a
   memory-using object traps `:kernel-memory-unavailable` before running.
3. **wasm32.** Compiling a kernel-memory object to `:wasm32-kotoba-v1` throws an
   internal NPE — the `kernel-load-u8-4k` family does not lower for that target.

So there is no path in this checkout to run the object's limb arithmetic. The
source is landed with its status stated in its own header; the contract marks
the brick `:source-written-algorithm-verified-compile-blocked`. **Do not treat
its presence as a working brick.**

## The unblock

The dependency that has to move is the object toolchain, not this repository:
either the amu/kotoba-object revision regains a code region large enough for the
ecdsa objects (or the objects are split under the 32768 limit), or a
kernel-memory execution harness is added so a compiled object can be
vector-tested off the boot. When either lands, the follow-up is small: compile
`ecdsa-p256-sign.o`, pin its digest in `build-uefi.sh`, wire a C caller that
runs the RFC 6979 DRBG for k and calls the object, and gate it with the A.2.5
known answer (already encoded in the oracle) in a QEMU boot.

## I4 status

Unchanged: RED. The remaining login path is now down to this one object plus
the SSH binary-packet transport (X25519 + SHA-256 + the ADR-0103 entropy, all
present) and the publickey userauth (existing ECDSA verify). No SHA-512, no
Ed25519. The only thing between here and a signed handshake is an object
toolchain that can build a 52 KB kernel object.
