# ADR-0028 — The multiboot gate was flaky, not red: an inherited 8259 racing the LAPIC timer

- Status: accepted
- Date: 2026-08-06
- Follows: ADR-0027 (which mischaracterised this failure twice)

## Context

`smoke-qemu-multiboot.sh` failed with QEMU exit 219 after
`AIUEOS_MULTIBOOT_ACPI_OK`. 219 is `(0x6D << 1) | 1`, and `0x6D` is written by
`aiueos_mb_isr_default` — the fail-fast handler every vector except 32 pointed
at — so an unexpected interrupt was being delivered inside
`install_idt_and_time_lapic`.

Two of this ADR's premises turned out wrong, both of them mine:

1. **It is not deterministic.** Measured on pristine sources: **7 failures in 32
   boots**, about 22%. ADR-0027 called it "red"; the accurate word is **flaky**.
   Two observations that both happened to fail is a ~5% coincidence, which is
   not rare enough to have noticed without counting.
2. **Vector 8 here is not `#DF`.** It is IRQ0 arriving as an external interrupt,
   which pushes **no error code** — unlike the double fault that shares the
   vector number.

That second point produced the diagnosis. The first probe printed a *shifted*
exception frame (`error=0x0010287c rip=0x08 cs=0x246`) because the stub assumed
an error code was present. The shift was the tell that this was hardware, not a
CPU exception.

## Diagnosis

**IRQ0 — the 8254 PIT — delivered through LAPIC LINT0 in ExtINT mode and
INTA-cycled to vector `0x08 + 0 = 8`.**

QEMU's `-kernel` Multiboot support still runs SeaBIOS before handing off.
SeaBIOS programs the 8259s with master base `0x08` and leaves channel 0 ticking
at ~18.2 Hz. The kernel inherits a live legacy controller and never touches it —
there is no PIC handling anywhere in this tree. `sti` opens the window, and the
boot fails whenever the PIT tick beats the LAPIC timer's own vector-32 tick.

Register evidence, captured by forcing the race deterministically (masking the
LAPIC timer LVT so the PIT was the only source that could fire):

```
pic-master-imr=0xb8 pic-slave-imr=0x8e lvt-lint0=0x00008700
vector=8 error=none-external-interrupt rip=0x10280c cs=0x0008
rflags=0x00000246 pic-isr=0x0001
```

`pic-isr=0x0001` names the line directly: master 8259 ISR bit 0, IRQ0 in
service. `lvt-lint0=0x8700` is delivery mode 7 (ExtINT), unmasked. `rflags` has
IF set, so it arrived after `sti`.

## Decision

`legacy_pic_disable()` at the top of `install_idt_and_time_lapic`, so both the
MB1 and GRUB MB2 paths get it: ICW1–ICW4, then `OCW1 = 0xFF` on both chips.

**The vector bases are moved before masking, deliberately.** A masked PIC
delivers nothing, so the remap is not what fixes the bug — but if a line is ever
unmasked later, the vector then reports as itself instead of aliasing onto a CPU
exception vector or onto 32, which this path uses for the timer. IRQ0
masquerading as `#DF` is exactly what made this opaque for as long as it was.

> **Correction (ADR-0029): the bases chosen here were 0xF0/0xF8, and 0xF8 does
> not meet that aim.** `0xF8 + 7 = 255`, which is the **LAPIC spurious vector**
> (`apic.c` sets SVR to `0x100 | 0xff`) — so an unmasked IRQ15 would have been
> indistinguishable from a spurious interrupt. The identical masquerade this
> paragraph claims to prevent, one chip over. Both callers now pass 0xE0/0xE8,
> and the Kotoba object that replaced this C **refuses 248** so the mistake
> cannot be made again.

Independently, the silent `aiueos_mb_isr_default` is replaced by 256 per-vector
stubs reporting vector, error code, RIP, CS, RFLAGS, CR2 and the PIC ISR. The
reporter is self-checking: a CS that is not `0x08` means the frame is shifted,
so it re-decodes rather than lying. **A fail-fast handler that says nothing is
why this sat undiagnosed**, and that is worth fixing whether or not the cause
had turned out to be here.

## Consequences

- **0 failures in 80 boots** (72 by the implementer, 8 independently) against
  7/32 before. At the measured base rate, 72 clean runs is ~10⁻⁸.
- **The UEFI path has the same latent gap.** It never masks the PIC either; it
  is green only because **OVMF masks it before handing off**. Nothing in
  `apic.c` protects it — which is why diffing the two paths' pre-`sti` state was
  the productive move rather than reading `apic.c` harder. Not changed here, and
  worth knowing: that path's correctness currently depends on its firmware.
- **A single green run of this smoke is weak evidence from now on.** It is a
  race; only repeat boots mean anything. Anyone re-running it should count.
- `smoke-qemu-grub-multiboot.sh` shares the fixed function but **could not be
  run** — `grub-mkrescue` is not installed here (`xorriso` is). Still unmeasured.
- The UEFI gate was re-run in full and stays green
  (`AIUEOS_APIC_TIMER_OK vector=32 eoi-v1`, exit 0). The diff touches only
  `multiboot/`, so it could not have affected it, but it was confirmed rather
  than argued.
