# ADR-0029 — PIC shutdown becomes a Kotoba object, shared by both boot paths

- Status: accepted
- Date: 2026-08-06
- Amends: ADR-0028 (whose 0xF8 base is wrong, see below)

## Context

ADR-0028 fixed a ~22% flaky multiboot boot by masking the 8259s the firmware
left running, in C, on the multiboot path only. It also recorded that **the UEFI
path has the same gap** — it never masks the PIC and is green only because OVMF
does it before handoff. That is firmware-dependent correctness.

PIC programming is pure port I/O, which Kotoba can now express (`kernel-out-u8`,
ADR-2608060100). So the fix belongs in one object shared by both paths, before a
second C copy could drift from the first.

## Decision

`kotoba/pic-disable.kotoba` performs ICW1–ICW4 and masks both chips, called from
`multiboot/main.c` (replacing yesterday's C) and from `kernel/main.c` (the UEFI
path's first-ever PIC shutdown).

**The vector bases are validated, not trusted.** Seven clauses per chip plus one
joint, each earning its place:

| clause | why |
|---|---|
| `base ≥ 32` | above the CPU exception range — base 0x08 is what put IRQ0 on vector 8. **Also the signedness clause**: i64 is signed where the C was unsigned, and a negative under an unsigned compare becomes huge and sails past a lone upper bound. The disassembly emits `setge`/`setle`, so −8 is refused here rather than by luck. |
| `base ≤ 248` | the span is `base..base+7`; 250 would put IRQ7 at 257, past the 256-entry IDT. |
| `base & 7 == 0` | ICW2 latches only bits 7:3. Unaligned does not fail, it **truncates** — 0xE2 silently becomes 0xE0. Cannot substitute for the range check: −8 is 8-aligned. |
| `≠ 32` | 32..39 holds the LAPIC timer (32), IOAPIC/PIT (33), virtio (34, 35). |
| `≠ 128` | 128..135 holds the syscall gate. |
| `≠ 248` | 248..255 holds the **LAPIC spurious vector (255)**. |
| `master ≠ slave` | both spans are 8-aligned and exactly 8 wide, so overlapping and coinciding are the same thing — equality is the exact test. |

The used-vector clauses come from grepping the tree, not from assumption.

## Consequences

- **ADR-0028's chosen bases were wrong, and this ADR is partly why they were
  found.** That change moved the PIC to 0xF0/0xF8 with the stated aim that an
  unmasked line "reports as itself instead of aliasing onto a CPU exception
  vector or onto 32". **0xF8 + 7 = 255 = the LAPIC spurious vector**, so an
  unmasked IRQ15 would have been indistinguishable from a spurious interrupt —
  the identical masquerade the paragraph claims to prevent, one chip over.
  Both callers now pass **0xE0/0xE8**, and the object **refuses 248**, so the
  mistake cannot be repeated. Keeping 0xF8 and adding the clause were mutually
  exclusive; the clause won.

- **Both gates green**: UEFI `AIUEOS_PIC_OK remapped=0xe0/0xe8 masked=both`
  followed by `AIUEOS_APIC_TIMER_OK` and `AIUEOS_IOAPIC_OK`, exit 0; multiboot
  10/10 repeat boots (plus 13 by the implementer). Repeat counts matter here —
  the failure this descends from was a race, so a single green run proves little.

- **The UEFI gap was real but not total.** `aiueos_ioapic_route_legacy_timer`
  already masks both chips — but it does not run until well *past* the first
  `sti`, and it masks without ever remapping. Between `sti` and there, that path
  had nothing but OVMF's goodwill.

- **Placement on the UEFI path is after `lidt`, deliberately.** A Kotoba object's
  prologue guards fuel with `ud2`; a `#UD` raised while the *firmware's* IDT is
  still installed produces an OVMF dump with no vector and no address — the same
  argument `kernel/main.c` already makes for the X25519 self-test. After `lidt`
  it reaches this kernel's own vector-6 handler and names itself.

- Fuel: **1 unit per call**, measured — two `decq` sites in the object, one being
  `main`'s. `kernel-out-u8` is emitted inline as `out %al,%dx` and charges
  nothing, so all twenty writes are free and the cost is per function entry. This
  is why the object is one function with no helper: a "write then delay" helper
  called ten times would cost 11 per call and make the cost a function of
  sequence length.

- The I/O delay is preserved as the port-0x80 write the C used — ten writes and
  ten delays, matching position for position.
