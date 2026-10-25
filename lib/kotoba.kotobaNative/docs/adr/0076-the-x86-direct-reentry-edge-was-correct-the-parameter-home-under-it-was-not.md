# ADR 0076: the x86 direct reentry edge was correct; the parameter home under it was not

Status: accepted. Date: 2026-09-03.

## Context

`da3b56b` ("Optimize x86 direct self reentry", #94) did two things at once: it
gave `:mc/recur` an `:x86-64/jmp-rel32` back edge instead of the
`:aarch64/b-imm26` it had been spelling unconditionally, and it advanced
kotoba-mir to `3aea0acc`, which is where `x86-direct-reentry?` turns the same
allocator path on for x86-64.

That commit is the first bad commit for aiueos ADR-0150: recompiling
`os/aiueos/kotoba/aiueos/sha256.kotoba` with any compiler that carries it
produces a kernel object that traps with `#UD` when the kernel calls it. Bisect
path: amu `9cf3a0ac` good -> amu `0df9d992` bad (that amu commit changes exactly
one line, this repository's pin `3dab370e` -> `3162d868`) -> this repository
`3dab370e` good, `da3b56b` bad, measured by compiling the same source with amu
held at `886e9408` and only the pin moved.

## What was wrong, and where

Not here. The back edge is right and the object is 45% smaller for it. What was
wrong is one instruction *above* the label it jumps to.

kotoba-mir's `store-at-definition` splices a spill store at the value's
definition, because under SSA a definition dominates every use. `:mir/recur` is
the one edge that breaks that rule: it redefines the parameter homes and
branches back to `:mir/reentry`, which is emitted after the entry plan. So the
store ran once, before the loop, while the body's reloads ran every iteration.
In `round-block`, slot `0x60(%rsp)` held the loop counter's ENTRY value forever,
`(+ i 1)` was 1 on every iteration, `(= i 64)` never held, and the object spun
until its fuel guard fired. Raising the fuel immediate to `2^31-1` does not fix
it — the image then hangs instead, three 600 s QEMU attempts with no exception.

kotoba-mir ADR 0038 carries the fix and its regression test. The test is red on
**both** targets: nothing about this was x86-only, and AArch64 escaped only
because it has enough registers that no shipped aiueos object had ever spilled a
parameter home.

## Decision

Advance the kotoba-mir pin to `0bb174c8` (kotoba-mir ADR 0038). Nothing in this
repository changes: the emitter was doing what it was asked.

The reason this ADR exists rather than a line in the pin's comment is that
`da3b56b` is a commit worth being able to find again. It is the shape where a
*correct* optimisation makes a *latent* defect reachable, and the bisect landed
on it rather than on the defect — so a reader who arrives at `da3b56b` from a
bisect needs to be sent one repository upstream instead of reverting a good
change.

## Consequences

- Objects compiled by a self-tail function that spills a parameter change bytes.
  `sha256.o` at amu `7088dc97`: 9,912 B either way, `db5effa8…` before,
  `e5efb286…` after. Nothing else about the object moves — the 8 body-label-form
  back edges are all still there.
- Boot evidence (aiueos `smoke-qemu-uefi.sh`, q35 + OVMF, only `sha256.o`
  swapped into the committed image): before, `AIUEOS_INITRAMFS_OK` then `#UD`
  with `RIP` at object offset `0x175`, which is a fuel guard's `ud2`. After,
  `AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK elf digest=kotoba-sha256`,
  `AIUEOS_X25519_OK`, `AIUEOS_AES_GCM_OK`, `AIUEOS_ECDSA_P256_OK`,
  `AIUEOS_TLS13_RECORD_OK`, `AIUEOS_UEFI_SMOKE_OK`, exit 0. The admission marker
  is computed BY the object under test, so it is evidence about this object and
  not only about the image.
- Suite at the new pin: 356 tests / 4778 assertions / 0 failures.
- **A non-terminating kernel object is not distinguishable from a QEMU flake in
  today's harness.** The raised-fuel run printed
  `warning: QEMU hung on attempt 1/3 (known flake kotoba-lang/aiueos#108);
  retrying` three times. That retry loop will absorb a real hang. Recorded here
  rather than fixed; it belongs to the aiueos harness.
