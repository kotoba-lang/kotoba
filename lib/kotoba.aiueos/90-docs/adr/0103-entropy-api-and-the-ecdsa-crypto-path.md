# 0103 — An entropy API, and the crypto path that avoids Ed25519

Accepted 2026-08-25. Tranche five of root ADR
`adr-2608251418-aiueos-usb-install-and-headless-bootstrap`; it follows the SSH
passive open of ADR-0102. It lands the entropy source an SSH handshake needs,
and — after measuring the toolchain — reroutes the remaining SSH crypto off
Ed25519 and onto the primitive the kernel already has.

## The crypto-path decision (this is the important part)

The SSH contract (ADR-0101) chose `ssh-ed25519` for the host key and userauth
because that is what a modern OpenSSH ships. Building it on this kernel would
mean two large new Kotoba objects — SHA-512 and a whole new Edwards curve, both
verify AND sign — and this tranche measured that the KIR interpreter cannot
even vector-test a memory-using SHA-family object (`ir/execute` has no way to
provide linear memory; the intrinsics trap). So every ed25519 primitive would
have to be measured the hard way, by native compile with the pinned amu plus a
QEMU known-answer boot.

The kernel already has ECDSA P-256 **verify**
(`kotoba_aiueos_ecdsa_p256_sha256_verify`), SHA-256, and HMAC-SHA256. So
`ssh-v1.edn` now specifies `ecdsa-sha2-nistp256` for both the host key and
userauth:

- **userauth** reuses the existing ECDSA verify unchanged — zero new crypto.
- the **host key** needs exactly ONE new object, ECDSA P-256 deterministic
  (RFC 6979) **sign**, and it reuses the P-256 field and scalar-mult arithmetic
  `ecdsa-p256.kotoba` already carries for verify, with HMAC-SHA256 for the
  nonce.

One new object that reuses existing arithmetic, versus two new curves. This is
recorded in `ssh-v1.edn :crypto-bricks`, with the rejected ed25519 route kept
beside it so a later reader does not re-open it without the cost. The
provisioning generator places an `ecdsa-sha2-nistp256` authorized key the same
way it places any other; the owner supplies an ECDSA P-256 public key (or one
is generated for the device pairing).

## Landed and measured: the entropy API

Before this, `virtio_rng` asked the device for 32 bytes once and threw them
away — only the boolean `rng_ok` survived. A handshake needs fresh bytes: an
ephemeral kex scalar and a KEXINIT cookie. So the random device is now kept
alive after enumeration (the queue, its pages and doorbell persisted the way
`blk_backend` persists the block device), and `aiueos_random_bytes(out, n)`
fills `n` bytes by requesting fresh 32-byte batches. A caller that gets 0 has
NO usable bytes and must not proceed with a weak key.

`smoke-qemu-entropy.cljs` boots the kernel and requires `AIUEOS_RANDOM_OK`: the
self-test draws two 32-byte batches and asserts both are non-constant and that
they differ from each other — a fixed-page device, or an API that handed back
the same buffer twice, fails both, which is why it asks twice. Measured green
under QEMU, full boot (`AIUEOS_UEFI_SMOKE_OK`).

Everything is behind `#ifdef AIUEOS_SSH_LISTEN` or is an unused function in the
default build: the persisted `rng_backend` only writes a static struct, and the
self-test + marker compile only under the flag. The shipped kernel is
unchanged.

## Still red

I4 stays RED. What remains for a login is now precise and small: the ECDSA
P-256 sign object (one Kotoba object, reusing existing arithmetic), the SSH
binary-packet transport (KEXINIT + curve25519 kex producing the exchange hash,
using X25519 + SHA-256 + this entropy, all present), the host-key signature
over that hash, `aes128-gcm@openssh.com` record protection, and the publickey
userauth (existing verify). None needs SHA-512 or Ed25519. The listener also
still does not persist past the boot's network phase; a resident sshd is the
same service-loop seam widened.
