# ADR-0150 — a newer amu miscompiles `sha256.o`, and the retired recipe's pin was telling the truth

- Status: accepted
- Date: 2026-09-03
- Extends ADR-0129 / ADR-0130 (object producer provenance), ADR-0131 (the K16
  pure-native gate), ADR-0146 (the HKDF object was miscompiled), ADR-0149.
- Does not supersede anything. It reverses an intention, not a decision.

## Context

The K16 pure-native gate (ADR-0131) refuses an object it cannot attribute:

```
AIUEOS_K16_PURE_NATIVE_REFUSED scanned=91 kotoba=45 stubs=0 foreign=24 unattested=22
reasons {receipt-missing 24, compiler-unrecorded 22}
```

22 of the Kotoba objects in today's link had no record of which Amu revision
produced them. The plan was the obvious one: recompile every committed object
with one current Amu, write a provenance receipt naming it, commit the bytes
that came out, and drive `unattested` to 0.

That plan is withdrawn. Carrying it out is how the following was found.

## What was measured

**Recompiling everything at a current Amu changes almost everything.** All 74
committed objects, amu `7e8f06d7` (kotoba-native `a5ddd788`), 663 s at
`--jobs 5`: 10 reproduced, 63 differed, 1 could not be compiled at all
(`device-worker-canonical.o` — `:kotoba/artifact-target-rejected`, "declares an
aiueos export with no admitted symbol"; the symbol landed in kotoba-native
`24f43e21`, downstream of amu's pin). Every object that changed got *smaller*,
several by ~45% (`sha256.o` 17,792 → 9,912 B, `rsa2048.o` 18,512 → 9,520 B).

**With one amu that can build all of them, 69 of 74 changed.** amu `370a04e0`
(kotoba-native `279fbc3`, pushed as `agent/k16-attest-amu-local` so the receipts
could name a fetchable revision), 470 s at `--jobs 6`: 5 byte-identical, 69
rewritten. The gate then said what it was asked to say:

```
AIUEOS_K16_PURE_NATIVE_REFUSED scanned=91 kotoba=67 stubs=0 foreign=24 unattested=0
```

**And the image stopped booting.** `smoke-qemu-uefi.sh` under OVMF:

```
AIUEOS_INITRAMFS_OK newc entries=3 sha256-admitted bounded
!!!! X64 Exception Type - 06(#UD - Invalid Opcode)  CPU Apic ID - 00000000 !!!!
RIP  - 00000000001423E5
```

with no `AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK`. Control dies inside
`aiueos_recovery_payload_admission` (`kernel/pci.c:297`), which calls exactly two
Kotoba objects: `sha256` and `rsa2048_sha256_verify`.

### It is one object, and it is not fuel

| `sha256.o` | bytes | sha256 | QEMU |
|---|---|---|---|
| committed | 17,792 | `af378b06…` | `AIUEOS_UEFI_SMOKE_OK` |
| amu `7e8f06d7` / native `a5ddd788` | 9,912 | `db5effa8…` | #UD, no `RECOVERY_ADMISSION_OK` |
| amu `370a04e0` / native `279fbc3` | 9,936 | `3186c098…` | #UD at base+0x695 |
| the same, fuel immediate → 2,147,483,647 | 9,936 | — | #UD at base+0x5cd |

Reverting **only** `sha256.o`, with the other 68 rebuilt objects still linked,
boots clean and the rebuilt TLS objects run on the processor:

```
AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK elf digest=kotoba-sha256 signature=kotoba-rsa2048-pkcs1 policy=public-key
AIUEOS_KOTOBA_STORE_VECTOR_OK journal-sequence=1
AIUEOS_AES_GCM_OK aes-128-gcm nist
AIUEOS_TLS13_RECORD_OK rfc8448-s3 seq0 seal-open tamper-refused
AIUEOS_UEFI_SMOKE_OK
```

Raising the fuel immediate in place moves the trap rather than removing it, so
the tier is not the cause. Neither address is a `ud2`: `base+0x695` is the last
displacement byte of the `jae` at `0x690`, and `base+0x5cd` is inside the
`imulq` at `0x5c9`. **Control lands mid-instruction, twice, at two different
offsets.** Every static branch target in both objects is an instruction
boundary (263 branches in the old object, 261 in the new, 0 bad in either), so
the bad transfer is dynamic — a corrupted return address or an indirect jump,
not a guard being hit.

The trap was located by relinking the same tree without `--strip-all` and
resolving the RIP against the symbol table: `kotoba_aiueos_sha256` at
`0x141D50`, and this object's `kotoba_source_entry` at `0x143F61`, exactly
`0x2211` later — which is where the object's own disassembly puts it.

### The committed objects were reproducible all along

`sha256.kotoba` compiled at amu `9cf3a0ac` — the revision the retired
`reproduce-kotoba-kernel-object.sh` pins in a shell variable — is byte-identical
to the committed `sha256.o`:

```
af378b061725473bf4aa66d02d276973ffc5c7cef4b0ed1f4a0e01fc754a7753  17,792 B
```

So the recipe's pin was a true claim, and the only reason nobody knew was that
nothing checked it. The regression window is amu `9cf3a0ac..7e8f06d7`. It is
**older than all of today's kotoba-native work** — `a5ddd788` already fails, and
#118 / #119 / #120 are downstream of it — so kotoba-native ADR 0049 (a bounded
store answers with the word it stored) is not the cause, though it is a reason
the bytes moved: re-running that PR's audit against this tree measures 23
sources with a bounded store and 17 whose answer decides something, wider than
the table in that ADR, which predates `qwen35-gguf-kv-scan`,
`qwen35-tensor-table-bind` and `tls13-record`.

### Five of the recipe's claims are false, and the gate's number goes UP

`reproduce-kotoba-objects.cljs --git-resolve` recompiled all 47 objects the
recipes name, each at the revision its own receipt records, and compared bytes:

| verdict | n | objects |
|---|---|---|
| MATCH | 39 | the recipe's pin is true for these |
| DIFFERS | 5 | `broker-admit` `ime-romaji` `scanout-bind` `session-restore` `wm-hit` |
| COULD-NOT-RUN | 3 | the `ecdsa-p256` trio |

The five that differ were built by some newer compiler than the manifest names
— four of them are among the five objects that reproduced byte-for-byte at amu
`370a04e0`, which is the other end of the same fact. The three ecdsa objects
cannot be built by an unpatched compiler at all: `reproduce-ecdsa-sign-object.clj`
patches kotoba-native's entry table and fuel tier in-process, and `--git-resolve`
deliberately does not, so it reports `could-not-run` rather than a verdict about
the object.

The generator no longer restates a falsified claim, and that check runs *before*
carry-forward, because a false claim must not survive merely because the digests
it was recorded against did not move. The consequence is that the gate's number
gets worse:

```
                        before   after
kotoba                      45      40
unattested                  35      40
```

Nothing about the tree changed. Five receipts stopped asserting something that
had just been measured to be untrue.

## Decision

**Attesting an object means recording the revision that produced the bytes in
the tree, and proving it by recompiling at that revision. It does not mean
rebuilding at whatever is current.** The rebuild is reverted; the measurement,
the tooling and the manifest shape stay.

1. `os/aiueos/scripts/reproduce-kotoba-objects.cljk` is the one driver.
   `--git-resolve` compiles each object at the revision **its own receipt
   records**, resolved from git by tools.deps, so no one needs that checkout on
   disk and the driver cannot quietly answer about a different compiler. Exit 0
   all reproduce, 3 any differ, 2 could not run.
2. The manifest keeps `:route`, `:source-transform` (the `ecdsa-p256-public`
   rename, as data rather than hidden in a script), and a computed
   `:verification` — `:kir-vectors` when a contract or parity test runs vectors
   against the source, `:attested-unverified` otherwise, with the reason. Both
   kinds run the KIR interpreter; **neither executes the emitted machine code**,
   which is the distinction this ADR exists to keep.
3. `--emit-provenance` seeds `:compiler` from the recipe's pin only for objects
   the recipe names, and carries a measured claim forward only while both
   digests it was made against still hold.
4. `unattested = 0` was **not reachable when this was written**, and the
   reason was named rather than papered over: the objects the old recipe could
   not build need a newer compiler, and every newer compiler measured
   miscompiles `sha256`. **Reachable as of 2026-09-03** -- ADR-0190 bisected the
   regression to kotoba-native `da3b56b` and it is fixed upstream (kotoba-mir
   ADR 0038 / kotoba-native ADR 0076 / amu ADR 0326). Rebuilding at a compiler
   past kotoba-native `d7105581` measures `kotoba=80 unattested=0` AND boots.

## Consequences

- **The compiler regression is CLOSED (2026-09-03, ADR-0190).** The bisect this
  ADR called for landed on kotoba-native `da3b56b` ("Optimize x86 direct self
  reentry"), and the defect under it was in kotoba-mir: a reentry parameter's
  spill store was spliced before the loop header, so `round-block` read its loop
  counter's ENTRY value on every iteration, never reached `(= i 64)`, and spun
  until a fuel guard fired. Fixed by kotoba-mir `0bb174c8`, pinned by
  kotoba-native `d7105581`. **The standing instruction survives the fix**:
  anyone advancing amu for aiueos kernel objects must boot the result, not just
  link it -- linking and `verify-kotoba-kernel-object.py` both passed for an
  object that never returns.
- **This ADR's reading of the trap was wrong in one respect, and ADR-0190 says
  how.** "Control lands mid-instruction, twice" and "not fuel -- raising it
  MOVES the trap" are true observations of the 9,936 B object in a 69-object
  rebuild, but they are what a NON-TERMINATING LOOP looks like when the budget
  runs out somewhere different each time. On an image with only `sha256.o`
  swapped, the trap is at object offset `0x175`, which IS a `ud2`, and IS the
  fuel guard; patching the immediate to `2^31-1` removes the trap and hangs the
  image instead.
- **Nothing else could have caught this.** The image freshness receipt
  (aiueos #246) is scoped to `os/aiueos` and hashes committed `.o` files, so a
  compiler change that alters what those bytes should be leaves the image
  reported fresh. Object-level attestation is the only check in the tree that
  looks at the producer at all.
- **The smoke is weaker evidence than it looks for some objects.** Of the boot
  self-tests, only NIC-PARITY, DEVCLIENT-PARITY, SHA-STREAM-PARITY, DISRP and
  the boot-literal markers have ever been shown to go red; `AES_GCM`, `X25519`
  and `ECDSA_P256` have no measured red direction, so "the smoke still passes"
  does not discriminate for them.
- **Five objects were pinned to nothing.** `build-uefi.sh` verified
  `qwen35-{dot-f32,dequant-row,matvec,activation,norm}` for shape with an empty
  digest argument. They are pinned now, and
  `sync-kernel-object-digests.cljs --check` compares the shell's 86 literals
  against the manifest, refusing (exit 2, `invocation-parse-incomplete`) rather
  than reporting a clean sync over a subset — which is what it did when it
  matched 81 of 86 and the five it missed were exactly the unpinned ones.
- The parity roster is left as `origin/main`'s. This branch measured 73/73 with
  MATCH 72, but at amu `370a04e0`, whose `sha256.o` does not boot; publishing it
  would assert route parity for a compiler shown to miscompile. The roster's own
  defect is fixed: given a relative root it handed the compiler a path relative
  to the *compiler's* directory and recorded the resulting "input could not be
  read" as `:failed` — an answer about the object. Eight in a row, for sources
  that compile by either route alone.
