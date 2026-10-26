# ADR-0026 — MSR access moves out of C: the first mechanism, and a reviewed register list

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0025; root ADR-2608060100 (`kernel-in-*`, the same recipe)

## Context

Every kernel C file now has its *decisions* in Kotoba (ADR-0023/0024/0025).
What remains is mechanism, and removing that needs primitives.
`kernel-read-msr` / `kernel-write-msr` landed in the compiler with **no
execution evidence** — they encoded and admitted correctly, and had never run.

MSR access was also duplicated as inline assembly in three separate files
(`apic.c`, `paging.c`, `process.c`), each with its own `read_msr`/`write_msr`
pair.

## Decision

Replace all three with two Kotoba objects — and **carry a decision along with
the mechanism**: each object admits only the MSR indices this kernel has an
actual reason to touch, derived from the call sites rather than from the SDM.

| index | register | used by |
|---|---|---|
| 0x1B | IA32_APIC_BASE | `apic.c` |
| 0xC0000080 | IA32_EFER | `paging.c` (NXE), `process.c` (SCE) |
| 0xC0000081/2/4 | STAR / LSTAR / FMASK | `process.c` |

**0xC0000083 (IA32_CSTAR) is refused, and that is the point of the list.** It
sits *between* two admitted indices; a list written as "the SYSCALL block" would
have admitted it. Nothing here programs the compatibility-mode syscall entry.
So does FS/GS_BASE (no `swapgs` anywhere in the tree), TSC, PAT, MISC_ENABLE.

The set of model-specific registers this kernel can reach is now a reviewed list
enforced by compiler-emitted code.

## Consequences

- **First on-target execution of the MSR primitives**, and each marker is
  downstream of a *different* MSR, so they are independent confirmations:
  `AIUEOS_PAGING_OK … nx-wp` (EFER.NXE), `AIUEOS_APIC_TIMER_OK vector=32`
  (APIC_BASE read-modify-write), `AIUEOS_SYSCALL_OK` and
  `AIUEOS_USER_SYSCALL_OK` (STAR/LSTAR/FMASK plus EFER.SCE). Full boot exit 0.

- **A refused read returns 0, and 0 is not a sentinel.** The guarantee is that
  no `rdmsr` executes — an unreviewed index cannot fault and cannot deliver a
  register this kernel has not reviewed. The *return value* cannot carry that
  news: 0 is a legal MSR value (FMASK is 0 at reset, EFER is 0 pre-long-mode,
  STAR is 0 until written), and so is every other pattern. **A caller cannot
  distinguish refusal from "the register holds zero" and must not try.** Callers
  pass admitted indices; `aiueos-msr-write` returns a real 1/0 status and can say
  no. 0 was chosen over −1 because both sites that examine a read fail closed on
  it, where −1 masks to a plausible-looking APIC address.

- **`paging.c` is the site that does not examine its read** — it ORs NXE in and
  writes straight back, so a refusal there would clear LME and SCE. That
  asymmetry is exactly why EFER is on the list and why the list lives in the
  object rather than at the call site; that write's status is now checked.

- **Values are never examined, deliberately.** No compare, mask, `quot` or
  arithmetic touches an MSR *value* in either object. That is what removes the
  mask-before-divide hazard `vtd-admit` needed: an MSR value with bit 63 set is a
  negative i64, and the safest handling is not to look at it. Adding value
  predicates (e.g. refusing an EFER write that clears LME) would be several
  decisions wearing one name and would reintroduce arithmetic on the one operand
  whose bit 63 is hardware-controlled.

- **`ap_trampoline.S` keeps its MSR assembly, correctly.** The genuinely
  per-CPU MSR access is the long-mode transition, which runs in 32-bit protected
  mode — there is no 64-bit frame to call a Kotoba object from. `apic.c`'s pair
  turned out *not* to be per-CPU: `aiueos_apic_timer_initialize` runs once on the
  BSP before AP startup, and `aiueos_ap_entry` reads the APIC through MMIO.

- **`build-multiboot.sh` had to be wired too.** It compiles `apic.c` verbatim but
  linked no Kotoba objects beyond the probe, so this change would have broken
  that link with two undefined symbols. Its comment claiming `apic.c` is
  "self-contained" was already false and is corrected.

- Fuel: 1 unit per invocation on every path including refusal (the charge
  precedes the comparison), counted from the disassembly. 7 reads and 6 writes
  across a whole boot, against 512 each. No tier needed.
