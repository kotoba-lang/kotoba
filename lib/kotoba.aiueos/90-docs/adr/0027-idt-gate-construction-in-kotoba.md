# ADR-0027 — IDT gate construction moves to Kotoba, and a build that had been broken for two commits

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0026 (MSR access, the first mechanism to move)

## Context

`set_idt_gate` split a 64-bit handler address across an interrupt descriptor's
three offset fields. Getting that packing wrong points a vector at the **wrong
address** — a silent, exploitable failure rather than a crash — which is why it
belongs on the Kotoba side. Seven call sites: vectors 6, 14, 32, 33, 34, 35, 128.

## Decision

Move the whole descriptor construction into `kotoba/idt-gate-build.kotoba`,
writing the 16-byte descriptor into a caller-owned region. C keeps the wrapper,
so the seven call sites are untouched.

**Validate rather than trust the caller**, with domains derived from what this
kernel actually has:

- **`selector` = 8 only.** `0x20` is the dangerous rejection: it is a *valid*
  64-bit code segment at DPL 3, so a gate naming it is well-formed and would run
  the kernel's handler at CPL 3. A structural "is it a code segment?" predicate
  admits it; an enumerated set does not.
- **`ist` = 0 only.** `tss.ist[0..6]` is never assigned in this kernel, so a
  non-zero IST loads RSP=0 during delivery → #DF → triple fault with no
  diagnostic.
- **`attributes` = 0x8E only.** Excludes `0x8F` (trap gate — silently makes a
  handler re-entrant) and `0xEE` (DPL-3 gate — makes any vector `int`-callable
  from ring 3; this kernel enters through `syscall`/LSTAR).
- **`handler` non-zero and canonical.** Zero is what an unlinked function
  pointer looks like; a non-canonical address raises `#GP(0)` *during delivery*,
  so the symptom points at the IDT rather than at the interrupt that fired.

A refused call writes **nothing** — a partially written descriptor is worse than
none.

## Consequences

- **All interrupt paths verified through Kotoba-built gates**:
  `AIUEOS_DESCRIPTOR_TABLES_OK`, `AIUEOS_APIC_TIMER_OK vector=32`,
  `AIUEOS_SYSCALL_OK` / `AIUEOS_USER_SYSCALL_OK` (vector 128), and
  `AIUEOS_EXCEPTION_OK vector=6` — three different vectors delivering through
  descriptors this object packed. Full boot exit 0.

- **The canonical check is cheaper in signed arithmetic than in C.** "Bits 63:47
  all equal bit 47" is exactly "as a signed i64, within [−2^47, 2^47)" — one
  interval where an unsigned language needs two comparisons.

- **The high half must subtract before dividing, not just mask.** `quot`
  truncates toward zero where `>>` on a `uint64_t` shifts in zeros. Measured
  counterfactual for the naive form:

  | address | divide-first | correct | C |
  |---|---|---|---|
  | `0xffffffff80100000` | `00000000` | `ffffffff` | `ffffffff` |
  | `0xffff800000001234` | `ffff8001` | `ffff8000` | `ffff8000` |

  The second is the nastier one: off by one in the top half is a gate **4 GiB**
  from its handler. aiueos links at 0x100000 today so handlers are small
  positives, but the object is correct for the general case rather than for
  today's link address.

- **One intended divergence from the C**: it happily packs a non-canonical
  address; the object refuses.

- **`build-multiboot.sh` had been broken since ADR-0024 and nothing caught it.**
  That script compiles `kernel/acpi.c`, which since the ACPI move calls two
  Kotoba symbols, and the script never linked them. It cannot have linked. The
  UEFI smoke does not exercise the multiboot path, so the gate was silent —
  the *same* shape as the `apic.c` near-miss one iteration earlier, which should
  have been the warning. Fixed here.

  **Correction, measured the following iteration.** The lesson above said this
  path "has no gate" and "needs a smoke of its own". Both halves were wrong.
  `smoke-qemu-multiboot.sh` and `smoke-qemu-grub-multiboot.sh` both exist —
  **nothing invokes them**, and GitHub Actions was removed by ADR-2607300900, so
  there is nowhere they were being run from.

  Worse, running it revealed the multiboot smoke is **red on its own account,
  and was red before the link break**: it dies with exit 219 after
  `AIUEOS_MULTIBOOT_ACPI_OK`, inside `install_idt_and_time_lapic`, via
  `aiueos_mb_isr_default` (`multiboot/entry.S:152`) — the fail-fast handler every
  vector except 32 traps to, so an unexpected interrupt is being delivered.
  Reproduced identically at f91b903, which predates ADR-0024 and every change in
  this line of work.

  So the accurate statement is narrower than the one first written: the link
  break was mine and is fixed; the runtime failure is not mine and is not fixed.
  The three scripts are now registered in `scripts/tasks.edn` so they are at
  least findable, with the red one labelled red.

- **`multiboot/main.c` keeps its own copy of the packing, deliberately.** It is
  a separate, textually identical `set_gate`, and `install_idt_and_time_lapic`
  calls it **257 times per boot** against an unreplenished 512 — a different
  safety story from seven, which belongs with a `bounded-memory?` decision
  rather than being smuggled in here.

- Fuel: 1 per invocation, measured two ways — two `decq` sites in the
  disassembly, and the fuel word reading 511 after every call, admitted and
  refused alike. The object is one function with no helpers precisely because
  fuel is charged per function entry: a `store-byte` helper called 16 times
  would cost 17 per gate.
