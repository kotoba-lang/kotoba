# ADR-0035 — The reproducibility rebuild does not boot, and the skipped differential is why we know

- Status: accepted
- Date: 2026-08-09
- Extends: ADR-0032, ADR-0033, ADR-0034

## Context

ADR-0032 found that objects shipping in the image could not be rebuilt from
their own source. ADR-0034 measured the exact remainder: **20 of 57 shipped
objects** are unreproducible — 4 fail the subset checker outright, 16 compile
to different bytes.

The plan was one task: repair the 4, rebuild the 16, re-pin, and derive the
reproduce script's coverage from `build-uefi.sh` so an object can never enter
the image without entering the check. The stated gate before landing was a
**per-object differential** — shipped `.o` vs rebuilt `.o`, executed in a forked
child against a `MAP_SHARED` arena, with live negative controls.

That work was done up to the differential, and then the session was
interrupted. This ADR records what happened when the result was gated anyway.

## The finding

**The rebuild does not boot.** Builds are clean and the multiboot gate passes
3/3, but the UEFI gate fails:

```
AIUEOS_LOADER_OK loading kernel.elf
AIUEOS_SERIAL_OK stack-v1 memory-map-v1
AIUEOS_KOTOBA_NATIVE_OK elf64-relocatable sysv-v1 result=42
AIUEOS_KOTOBA_FNV_VECTOR_OK abc
AIUEOS_INITRAMFS_OK newc entries=3 sha256-admitted bounded
!!!! X64 Exception Type - 06(#UD - Invalid Opcode) !!!!
RIP - 0000000000131682 … R9 - 000000000013C038
```

Five markers, then dead. It dies **after** `AIUEOS_INITRAMFS_OK` and **before**
`AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK` — the RSA-2048/SHA-256 signature
admission step. A good boot emits ~70 markers.

`#UD` in this kernel is not a random crash: it is the opcode the Kotoba
prologue's fuel guard and the bounded-memory checks both trap with, and R9 is
the fuel-context pointer.

**It is not a fuel-tier regression.** Measured directly, the tier replenish is
byte-identical between shipped and rebuilt:

| object | shipped | rebuilt |
|---|---|---|
| `rsa2048` | `movq $0xee6b280, 0x8(%r9)` (250M) | identical |
| `sha256` | `movq $0x989680, 0x8(%r9)` (10M) | identical |

So a rebuilt object **traps at runtime where the shipped one does not** — either
a bounds check that now fails, or fuel exhaustion in an object carrying the
1024 default. The rebuild is *not* behaviour-preserving.

## Decision

**Do not land the rebuild.** It is preserved on branch
`agent/repro-wip-broken` (`cad8619`) with its failure recorded in the commit
message, not merged and not pinned. `origin/main` stays at `fd371d7`
(ADR-0034), which boots.

## Consequences

- **The inherited assumption was wrong, and this is the correction.** ADR-0033
  characterised the codegen drift as benign — the old compiler re-evaluated each
  `let` binding at every use site, the current one materialises it once — and
  backed that with 1,088,877 comparisons. But it fuzzed **2 of the 8** objects
  it examined and said so explicitly. `rsa2048` and `sha256` were among the
  untested. "Benign for the two we measured" was carried forward as "benign",
  and it is not.

- **The skipped step is the one that mattered.** Every prior iteration's
  durable finding came from checking a claim rather than from the port itself.
  Here the check was defined, deferred, and the deferral is precisely what let a
  non-booting tree reach the point of being a merge candidate. The differential
  was not bureaucracy; it was the only thing standing between this and a broken
  `main`.

- **Reproducibility and correctness are separate properties, and this project
  had been conflating them.** Every ADR since 0032 treated "rebuilds to
  identical bytes" as the goal. It is not: the goal is a tree that boots *and*
  can be rebuilt. A rebuild that reproduces byte-for-byte from a frozen compiler
  proves nothing about the current compiler, and a rebuild at the current
  compiler that changes behaviour is worse than the drift it removes. Whatever
  finally lands here must be gated on **the boot**, not on the digest.

- **What is still true and unchanged**: the 4 subset-reject repairs are almost
  certainly correct in isolation (they are the same `(if (= a b) 1 0)` type
  bridge already used by 9 sibling objects, and the same repair landed cleanly
  in ADR-0032). The likely culprit is among the 16 rebuilt binaries, not the 4
  repaired sources. Splitting the two is the obvious next move.

## Resume point

1. From `agent/repro-wip-broken`, **bisect**: land the 4 source repairs alone,
   gate; then add rebuilt objects in small batches, gating each. That isolates
   the offender in ~4 boots instead of guessing.
2. Run the per-object differential on the offender — `rsa2048` and `sha256`
   first, since the failure sits in signature admission and neither was ever
   behaviourally tested.
3. Only then re-pin, bump the reproduce script's compiler pin, and derive its
   object list from `build-uefi.sh`.

`reproduce-kotoba-kernel-object.sh` remains pinned to compiler `0b16d9b6` and
covers 36 of 57 objects. That is unchanged from ADR-0032 and remains the open
item.
