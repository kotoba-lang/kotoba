# ADR-0133: The TLS 1.3 record layer becomes a Kotoba object

## Status

Accepted (2026-09-02)

## Context

ADR-0132 moved the AEAD and the key schedule out of C.  `protect` and
`unprotect` in `kernel/tls13.c` (:311 and :335) stayed, and they are not
plumbing around the AEAD -- they are the part of a record layer that gets
exploited:

* the 5-byte header is the ADDITIONAL AUTHENTICATED DATA, so a length taken
  from the wrong place is a forgery the AEAD will happily authenticate;
* the sequence number is XORed into the nonce, so a reused or mis-derived
  sequence is a reused keystream;
* the inner content type is the last non-zero byte of the plaintext, so a
  padding strip that stops one byte early hands the caller the wrong record
  type -- and RFC 8446 5.4 says a record whose plaintext is entirely padding
  has no type at all and must be alerted on.

## Decision

`aiueos-tls13-record` (`kotoba_aiueos_tls13_record`, arity 5, 17,592 bytes,
sha256 `46d7bf41d9c50f519ef499134f0c021d06ab7dea256002f0c56e43f83391c46f`),
`--jvm-free` compiled for `x86_64-aiueos-kernel-v1`, one export, zero imports,
one relocation.  Contract: `os/aiueos/contracts/tls13-record-v1.edn`.

Reason codes, zero for success, as ADR-0132's two objects: 1 ctx too small,
2 bad mode, 3 rec-len outside 22..12310, 4 seal plaintext does not fit,
5 the record's own length field disagrees or the body is past the AEAD's bound,
6 tag mismatch, 7 the inner plaintext is all zeros.

### The base IV gets its own slot, and the nonce another

The nonce is `iv XOR seq` over the IV's last eight bytes.  An object that XORed
in place would corrupt the IV on the second record under the same key, and the
corruption would present as a peer that stopped decrypting rather than as a bug
here.  The base IV at ctx+16 is never modified; the derived nonce goes to
ctx+480, which is the only offset where this object's AEAD differs from
`aes128-gcm.kotoba`'s.

### The record is transformed in place

SEAL expects the plaintext already at `rec+5`; it appends the content type,
encrypts in place, writes the header and appends the tag.  OPEN decrypts in
place.  The C used a separate `out` and a 12 KiB `decrypt_plain` in
`.high_bss`.  In-place is exact rather than a shortcut because CTR mode is an
XOR, and it removes 12 KiB of kernel BSS.

### OPEN takes the AAD from the wire

Not from what the caller believes the header to be.  Those differ exactly when
someone has rewritten the header, which is the case the AEAD exists to catch.
`open-length-field-disagrees-with-the-buffer` refuses when the header and the
caller disagree, without deciding which of them is right.

### The AEAD is copied, not imported

A kernel object exports one symbol and cannot call another, and a namespace
declaring `(:require ...)` cannot be packaged for this target at all (measured
in ADR-0132).  So the AEAD is `aes128-gcm.kotoba`'s source, copied.  The copy
is mechanical and its differences are stated in the object's header so the two
files can be diffed and every change accounted for: `set-j0` reads the nonce
from 480 rather than from the IV slot, and `data` is spelled `body`.  That is
the whole diff.

## Measured

2026-09-02, amu `b1fdaad2` with its kotoba-native pin advanced to `81d6644`,
machine at load average ~120-150.

```
amu compile os/aiueos/kotoba/tls13-record.kotoba \
  --target x86_64-aiueos-kernel-v1 --output tls13-record.o --jvm-free
  -> :ok true, artifact-bytes 17592
python3 os/aiueos/scripts/verify-kotoba-kernel-object.py tls13-record.o <sha> \
  kotoba_aiueos_tls13_record
  -> AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1
     export=kotoba_aiueos_tls13_record imports=0 relocations=1
```

`aes128-gcm.o` and `hkdf-sha256.o` were recompiled at the advanced pin and are
BYTE-IDENTICAL to the ones ADR-0132 committed -- the added allowlist row does
not move an object that does not use it.

### The vectors are whole encrypted records from RFC 8448

Four of them: the client's and the server's `application_data` records and both
`alert` records from section 3, complete and encrypted, beside the traffic keys
that produced them.  SEAL is handed the payload and produces the entire record
byte for byte; OPEN is handed the record and produces the payload, the content
type and the length.

**The sequence numbers were recovered, not assumed.**  Each record was opened
with OpenSSL through node at sequences 0..3 and the one that authenticated was
taken.  The client's alert is sequence 1 -- it follows the client's
`application_data` on the same key -- and the server's is sequence 2, because
the server's NewSessionTickets record and its `application_data` came first.
Those non-zero sequences are the point: a vector at sequence 0 passes whether
or not the nonce XOR exists.

Two vectors are SYNTHETIC and say so in the contract, because RFC 8448 section
3 contains no record of either shape: one with padded inner plaintext
(`41 42 43 16 00 00`), and one whose inner plaintext is a single zero byte.
Both were sealed with OpenSSL.  The first is the only thing here that exercises
the padding strip; the second is reason 7.

### A dead clause, found by trying to reach it

The object refuses `clen < 17` under reason 5, transcribing the guard the C
had.  It cannot fire: `rec-len >= 22` and `clen + 5 = rec-len` together force
`clen >= 17`.  This was found by writing the vector for it and watching it come
back 3.

It is recorded in the contract as `:dead-clause` rather than as
`:unreachable-by-construction`, because that key names a whole reason code and
reason 5 IS reachable through its two live clauses.  The check stays: it guards
`(- clen 16)` from going negative if the 22-byte floor is ever lowered, and
deleting a check to make a vector reachable is the wrong direction.

The live third clause needed the largest record the object admits (12,310
bytes, header claiming a 12,289-byte body).  It costs nothing, because the
refusal happens before any crypto -- which is itself the property worth having.

## The provenance manifest calls all three unattested, and that is correct

`os/aiueos/kotoba/provenance.edn` (ADR-0131, regenerated here) now carries 70
objects, 47 recorded and 23 unattested -- the three TLS objects among the
latter.  That is not an oversight to fix by typing a SHA in.

The generator attributes a compiler by asking whether a RECIPE SCRIPT in this
repository names the object, and the only kernel recipe is
`reproduce-kotoba-kernel-object.sh`, which pins amu `9cf3a0a`.  These three
CANNOT be built at that pin: it predates the `kernel-object-entries` rows they
need, so it refuses their exports outright.  `:recipe :unrecorded` therefore
states something true -- no script here reproduces them -- and the K16
pure-native gate refuses them with `reason=compiler-unrecorded`, which is also
correct: nothing should link an object the repository cannot rebuild.

What IS recorded is in ADR-0132 and in
`qualification/jvm-free-object-parity-tls13.edn`: the amu revision, the
kotoba-native revision, and both routes' digests.  Closing the gap properly
means a recipe that can pin a newer compiler, which is a change to how this
repository reproduces objects and not a side effect of adding three.

## What is NOT done

* **The C is unchanged.**  `tls13.c` is still 827 lines with `protect` and
  `unprotect` in it; nothing links this object; `build-uefi.sh` is untouched.
* **This object has never run on a CPU.**  Every result above is the KIR
  reference interpreter with a supplied memory image.
* **The handshake state machine is still C** -- ClientHello construction,
  ServerHello parsing, EncryptedExtensions, Certificate, CertificateVerify,
  Finished and the transcript.  That is stage 4 and it is not started.  Note
  that a handshake object cannot call this one: kernel objects cannot call each
  other, so it would have to copy the record layer as this one copied the AEAD,
  or the C would keep the sequencing and call both.  Which of those is right is
  a decision stage 4 has to make and this ADR does not.
* **The key schedule has no orchestrator, and cannot have one here.**
  `aiueos-hkdf-sha256` derives ONE secret per call and `aiueos-sha256` hashes
  the transcript; the loop that walks Early -> Handshake -> Master and derives
  eight secrets is a sequence of calls, and a Kotoba object cannot make calls
  to another object.  That sequencing stays in C by construction, not by
  omission -- the DECISIONS inside it have all moved.
* **The largest record executed is 72 bytes.**  The object's bound is 12,310.
  The refusal path at 12,310 is executed; the crypto path at that size is not.
* **Nothing here says K16 HTTPS works natively.**  It does not.
