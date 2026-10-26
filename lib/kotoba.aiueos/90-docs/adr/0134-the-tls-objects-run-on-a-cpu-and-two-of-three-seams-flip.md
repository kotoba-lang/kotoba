# ADR-0134: The TLS objects run on a CPU, and two of the three seams flip

## Status

Accepted (2026-09-02)

## Context

ADR-0132 and ADR-0133 landed three Kotoba objects holding this kernel's TLS 1.3
crypto -- `aiueos-aes128-gcm`, `aiueos-hkdf-sha256`, `aiueos-tls13-record` --
and both ADRs closed with the same sentence: *this object has never run on a
CPU*.  Every claim about them came from the KIR reference interpreter with a
supplied memory image.  Nothing linked them, `kernel/tls_aes_gcm.c` still held
the cipher and `kernel/tls13.c` still held the framing and the key schedule, so
384 lines of crypto existed twice.

This ADR is the stage that executes them and moves the call sites.

## The harness was already here

`os/aiueos/scripts/smoke-qemu-uefi.sh` boots the production UEFI kernel under
QEMU (TCG, q35, OVMF, `isa-debugcon` on 0xe9 and a serial file), and
`kernel/main.c` already runs boot-time KNOWN-ANSWER self-tests immediately
after the kernel owns its own IDT and page tables -- X25519 against RFC 7748,
AES-GCM against SP 800-38D, HMAC/HKDF against RFC 4231 and 5869, ECDSA against
RFC 6979.  Placed there on purpose: a `ud2` raised while the firmware's handler
is still installed produces an OVMF dump with no vector and no address.

Nothing had to be invented.  The baseline was captured first, before any object
was linked and before any call site moved:

```
AIUEOS_X25519_OK rfc7748-base-point 32-bytes
AIUEOS_AES_GCM_OK aes-128-gcm nist
AIUEOS_HMAC_HKDF_OK sha256 rfc4231-rfc5869
AIUEOS_ECDSA_P256_OK rfc6979-sample s+1-refused
```

## Decision

1. `aiueos-aes128-gcm` and `aiueos-tls13-record` are linked into the UEFI
   kernel and are what `kernel/tls_aes_gcm.c` and `kernel/tls13.c` call.
2. `aiueos-hkdf-sha256` is NOT linked and the C keeps its own HMAC and HKDF.
   That is a measurement, recorded below, not a decision to defer.

### The flip was made against a measurement, not against a reading

A transition harness, `aiueos_tls13_kotoba_parity`, ran the same inputs through
the C and through the objects and reported the first case that disagreed.  It
ran BEFORE any call site moved, with both implementations present, and it is
deleted in the same change that deletes the C it compared against.

```
TLS-PARITY case=1 .. case=6
TLS-PARITY ok aes-gcm record 6-cases
```

Six cases: the AEAD's empty-plaintext, 64-byte and 64-byte-with-20-byte-AAD
seals (whole ciphertext and tag compared, not the return value); an open, a
flipped-tag refusal, and the assertion that the refused buffer still holds the
CIPHERTEXT -- the object GHASHes before it decrypts and the C it replaces did
not; and the record layer sealing RFC 8448 section 3's client
`application_data` record byte for byte at sequence 0 and opening it back, with
a flipped ciphertext byte refused under reason 6.

**That line is the first time any of this repository's TLS crypto has executed
on a processor.**

### What is left in C, and why it is not plumbing that got renamed

`tls_aes_gcm.c` 275 -> 180 lines.  The S-box, the key schedule, the cipher,
GHASH, CTR and the tag comparison are gone; what remains is 55 lines of
marshalling into the object's one caller-owned region and a 100-line
known-answer self-test whose vectors are published.

`tls13.c` 827 -> 882 lines, and the direction of that number is honest: 52
lines of record framing (`make_nonce`, `protect`, `unprotect`) became 40 lines
of marshalling, `decrypt_plain` -- 12 KiB of `.high_bss` -- and `protect`'s
2 KiB `inner` stack buffer are both gone because the object transforms the
record in place, and 55 lines of a NEW boot self-test were added for a layer
that never had one.  The line count went up; the duplicated crypto went to
zero.

Two shapes had to be crossed at every call site rather than transcribed:

* **The objects return a reason code and ZERO IS SUCCESS.**  The C returns 1.
  A transcribed `if (aes(...))` accepts exactly the records the object refuses.
  The inversion happens on the `return` lines of four wrappers and nowhere
  else.
* **The objects work in place on one region.**  The C entry points take
  separate input and output pointers, so the input is copied to the output
  first and the object is asked to transform the output.  That is exact -- CTR
  is an XOR -- and it needs no bounce buffer, because every caller already owns
  an output region of the right size.

`kernel/pci.c`'s SSH transport (`ssh_seal` / `ssh_open`) is a second consumer of
the AEAD and was NOT rewritten: it calls the same two entry points, which now
reach the object.  Keeping their signature is what made that possible in one
change instead of two.

## `aiueos-hkdf-sha256` does not return on this machine

Compiled into the same kernel, linked, and handed the RFC 4231 test case 1 that
its own contract runs in the interpreter, the object does not come back.  It
exhausts its 10,000,000-fuel budget and traps `ud2`; with the budget patched in
the `.o` to 2,147,483,647 it exhausts that too, after about eleven minutes of
TCG.

The faulting instruction was recovered with `qemu -d int` and mapped back into
the image:

```
v=06 e=0000 i=0 cpl=0 IP=0008:0000000000145270
  145269: 49 83 79 08 00   cmpq $0x0, 0x8(%r9)
  14526e: 75 02            jne  0x145272
  145270: 0f 0b            ud2
  145272: 49 ff 49 08      decq 0x8(%r9)
```

That is the fuel guard every Kotoba object carries in every function prologue,
inside the object's own `store32`.  The object was identified by the window
literal in its accessor -- `movl $0x320, %edx` is 800, this object's region
size, where `aes128-gcm` uses 1280.

Three refusal paths of the same object were exercised in the same boot and
answered correctly: `ctx-len` 799 returned 1, `mode` 2 returned 2, `key-len` 65
returned 3.  The entry, the ctx loads at offsets 96..99 and the return path all
work; only the path that runs SHA-256 does not.

**The size of the gap, stated as a ratio rather than as a guess.**  The SAME
SHA-256 core, in `sha256.kotoba`, is on the SAME 10,000,000-fuel tier, and this
kernel hashes the 8,560-byte recovery ELF with it at every boot -- 134 block
compressions -- and reports `AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK`.  So that
core costs at most ~74,600 fuel per compression.  The HMAC of a 20-byte key
over an 8-byte message is FOUR compressions.  The object spent more than
2,147,483,647.

**What this evidence does and does not establish.**  It establishes that the
compiled artifact does not answer, on hardware, an input its source answers in
the interpreter, and that the artifact is the one both compile routes produced
(`qualification/jvm-free-object-parity-tls13.edn` records
`d1330d6f...` for all three).  It does NOT distinguish a non-terminating
lowering from a lowering that is four orders of magnitude more expensive than
the same source compiled inside `sha256.o`; the fuel guard reports both the
same way.  **Raising the tier is therefore NOT the fix, and no
`kotoba-native` change was landed** -- a tier is a bound on work, and 2.1
billion function calls for four SHA-256 compressions is not a bound problem.

The object stays out of the link.  An object nothing may call has no business
adding 13 KiB to an image, and `test/aiueos/kotoba_object_reachability_test.cljk`
carries the measurement as its `not-built-here` reason so that the next reader
finds the number rather than the word "pending".

## Measured

2026-09-02, QEMU 10.1.0 (TCG, `-cpu max -m 128M -smp 2`), OVMF
`edk2-x86_64-code.fd`, machine load average 90-220.

After the flip, with the C bodies deleted:

```
AIUEOS_AES_GCM_OK aes-128-gcm nist
AIUEOS_TLS13_RECORD_OK rfc8448-s3 seq0 seal-open tamper-refused
```

The first line is now computed by `kotoba_aiueos_aes128_gcm`; it was computed
by 185 lines of C when the baseline above was taken.  The second is new: the
record layer had no boot self-test at all.

The host route was re-measured too, because `smoke-tls13-murakumo-profile.sh`
compiles the same `tls13.c` for macOS.  `tls13_host_probe.c` already substitutes
OpenSSL for every Kotoba object (sha256, x25519, ecdsa); two more substitutions
were added for the same reason, and an x86-64 kernel object cannot be linked
into an arm64 probe.  With the rewired call sites:

```
profile ok host=api.murakumo.cloud path=/infer/queue clienthello=163
handshake ok
certverify ok scheme=ecdsa_secp256r1_sha256
fin=58 get=159
app len=693 nst=0 first=HTTP/1.1 200 OK..
```

A complete TLS 1.3 handshake and an authenticated HTTP response, through the
ctx layout, the in-place semantics, the sequence handling and the reason-code
inversion this change introduced.  **Those shims are not evidence about the
objects** -- they are OpenSSL -- and the ADR says so where they are defined.

The new record self-test was shown to DISCRIMINATE before it was landed.  It is
now part of the host probe's self-test gate, so the demonstration costs a
compile rather than a boot: with the last byte of the published record changed
from `0xe4` to `0xe5` the probe prints `selftest fail`; restored, it prints
`profile ok ... AIUEOS_TLS13_MURAKUMO_PROFILE_OK` and exits 0.

## What is NOT done

* **The key schedule is still C**, and so is the handshake state machine --
  ClientHello construction, ServerHello parsing, Certificate, CertificateVerify,
  Finished and the transcript.  Stage 4 is not started, and it now has a
  prerequisite it did not have this morning: whatever makes
  `aiueos-hkdf-sha256` fail to return will affect any object that inlines
  SHA-256, which a handshake object must.
* **No `kotoba-native` change was made.**  The defect is localised to an
  instruction and an object; it is not diagnosed.
* **The largest record executed on the CPU is 72 bytes.**  The object's bound
  is 12,310 and the AEAD's fuel tier was computed for 12,288.  Neither was
  executed at that size here.
* **K16 HTTPS is not claimed.**  Nothing in this change ran on the physical
  node; the network path was not exercised under QEMU either.
