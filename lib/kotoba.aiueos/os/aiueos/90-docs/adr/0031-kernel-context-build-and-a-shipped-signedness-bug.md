# ADR-0031 — `initial_context` in Kotoba, a signedness bug in shipped code, and why `lgdt`/`lidt` were built and discarded

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0030 (CPU feature detection)

## Context

The obvious next step after ADR-0030 was `lgdt`/`lidt`, the last descriptor-table
instructions with no primitive. That turned out to be wrong, and finding out why
reframed the whole effort.

**Porting individual `asm("cli")` statements into Kotoba calls from C is not
progress.** It is a function call per instruction, and those instructions carry
no decision content. The path to an all-Kotoba OS is porting **whole functions**.
A survey of the kernel against that standard produced two results worth keeping.

## Decision 1 — `lgdt`/`lidt` were implemented, verified, and deliberately not landed

Both primitives were built across all four repos, tested green, and their
encodings verified against an assembler:

```
0f 01 10   lgdtq  (%rax)     ; /2
0f 01 18   lidtq  (%rax)     ; /3
0f 01 38   invlpg (%rax)     ; /7  <- what the codebase already emits
```

They are the same opcode as `invlpg` differing only in the ModRM `/r` field, so
the existing memory-operand precedent fit exactly. The work was correct.

**It was discarded because no caller exists, and none can.** `lgdt`, `lidt`,
`ltr`, `lldt`, `sgdt`, `sidt` and every segment load appear in **no `.c` file at
all** — only in `kernel/entry.S`. And `aiueos_load_gdt` (entry.S:27) is:

```asm
lgdt aiueos_gdt_pointer(%rip)
pushq $0x08 ; lea 2f(%rip),%rax ; pushq %rax ; lretq   ; far return reloads CS
2: mov $0x10,%ax ; mov %ax,%ds ; %es ; %ss ; xor %eax,%eax ; %fs ; %gs
```

The `lgdt` is inseparable from a far return and six segment-register loads, none
of which have primitives and all of which are irreducibly assembly. A `lgdt`
primitive could never be called by anything.

Landing it would have produced exactly the state ADR-0030 was written to avoid:
an operation that encodes correctly, is admitted end-to-end, and that no CPU
ever executes. **A negative result that prevents future work is worth recording;
the encodings above are here so redoing it costs an hour if far-return and
segment-load primitives ever land.**

The general lesson: after ADR-0015 succeeded in moving the decisions out, what
remains in C genuinely *is* mechanism — sequenced I/O, pointer plumbing, global
state. Chasing new instruction primitives buys 0–25 lines each. The leverage is
in restructuring, not in instructions.

## Decision 2 — `initial_context` becomes `kernel-context-build`

`kernel/scheduler.c:236` builds an interrupt-return frame for a kernel task.
Directly below it, `initial_user_context` **already** called
`kotoba_aiueos_user_context_build`, so the object needed was the kernel-selector
twin of one already compiled into the image: arity 3 `(stack entry argument)`,
no user-stack argument, `cs = 0x08`, `ss = 0x10`, `rflags = 512|2 = 514`.

Frame base is `((stack + 4096) & ~15) - 8 - 160` = `stack + 3928` when aligned —
8 lower than the ring-3 frame, which is the `RSP % 16 == 8` invariant `iret`
needs when entering a C function.

There is no `bit-not`, so `x & ~15` is written `x - (x & 15)`. Note the ring-3
twin had **no alignment handling to copy**: its `& ~15` was a no-op on a
page-aligned stack and the original port simply dropped it.

## Decision 3 — a signedness bug in already-shipped code, found and fixed

`store64` in `user-context-build.kotoba` — **in the image and executing on every
boot since it landed** — decomposed a 64-bit value with:

```clojure
(quot value 256)   ; and so on, seven times
```

`quot` emits a signed `idivq` that truncates **toward zero**. It is not an
arithmetic shift. For any value with bit 63 set, every byte above the first
comes out wrong. Demonstrated by executing the compiled object, not by argument:

| input | naive `store64` stores |
|---|---|
| `0xFFFFFFFF80100000` | `0x81100000` |
| `0xDEADBEEFCAFEBABE` | `0xDFAEBFF0CBFFBBBE` |

The fix is to mask the low byte off before each divide,
`(quot (bit-and value -256) 256)`, which makes every division **exact** — and an
exact division *is* the shift. One `and` per step.

**This was harmless only because every address stored is currently below 2^63.**
`0xFFFFFFFF80100000` is the canonical higher-half kernel address; the first move
of the kernel out of the identity map would have corrupted every task's `rip`.

This is the same hazard recorded in ADR-0021, ADR-0026 and ADR-0030 — **i64 is
signed, C is unsigned, mask before dividing** — and this is the first time it was
found in code already shipping rather than in code under review. Both objects now
carry the masked form.

## Consequences

- `initial_context` is one call into compiled Kotoba; `AIUEOS_KERNEL_CODE_SELECTOR`
  and `AIUEOS_INTERRUPT_FLAG` are deleted from `scheduler.c`, since a macro that
  can be edited with no effect is a trap.

- **Differential evidence, by execution rather than reasoning.** The `.o` was
  flattened, its relocation resolved, mapped RWX and called through SysV against
  the pre-port C. All 16 stack misalignments swept: the frame lands at
  `stack+3928` down to `stack+3913` and `rsp` at `stack+4088` down to
  `stack+4073`, matching C at every one — the unaligned path is the same
  arithmetic, not an approximation. Poisoned arenas confirm no byte outside the
  160-byte frame is touched. Inputs include `0x8000000000000000`,
  `0xFFFFFFFF80100000` and `0xFFFFFFFFFFFFFFFF`, the values that break the naive
  form.

- **Fuel: 168 per call, measured** by reading the fuel word out of the mapped
  `.data` after a call (65,536 − 65,368), decomposing exactly as 1 entry +
  161 `zero-frame` + 6 `store64`. Input-independent, so 168 is both typical and
  worst case. Called 6 times per boot (3 from `aiueos_scheduler_initialize`,
  2 from `aiueos_scheduler_restore_service_registry`, 1 from the deterministic
  restart). The `context-fuel?` tier gives 390× headroom.

- **`build-multiboot.sh` does not compile `scheduler.c`**, so neither context
  object is linked there — verified by linking and checking `MULTIBOOT.ELF` has
  no `*_context_build` symbol, not by reading the script. Recorded as a comment,
  since a missed link there broke the build silently at ADR-0024.

- **`scripts/reproduce-kotoba-kernel-object.sh` is behind.** It carries
  hard-coded digests and was not updated for the three cpuid objects at
  ADR-0030 either. These objects therefore have no reproducibility check.
  Recorded rather than papered over.

- **Honest arithmetic on how far this can go.** Fully-portable-today functions
  total roughly 190 lines out of 4,532 in `kernel/*.c`, and the largest is 21
  lines. `pci.c` is now ~9% thin-wrapper-over-Kotoba and ~80% genuine device
  mechanism. Irreducible assembly and pre-kernel C is ~824 lines (`entry.S` 372,
  `ap_trampoline.S` 62, `uefi/main.c` 390), plus roughly 250 lines of in-kernel
  orchestration — `aiueos_kernel_main`, `aiueos_syscall_dispatch`,
  `aiueos_scheduler_on_timer`, `aiueos_process_enter` — which is a *script*:
  neither mechanism nor decision, a category ADR-0015's dichotomy has no slot
  for. The two highest-leverage changes are object→object linking (~133 lines
  across 9 functions) and a named-region story for C statics with an out-region
  convention (~156 lines across 9), each worth several times any remaining
  instruction primitive.

- **The survey that produced those numbers read a stale checkout** and reported
  that `kernel-read-msr` and `kernel-cpuid-*` do not exist, and that
  `nx_supported` and `syscall_transport_initialize` are blocked on them. Both
  were ported in ADR-0026 and ADR-0030 and observed executing. The structural
  analysis stands; the per-function "blocked by" column is dated where it
  touches those. Local `orgs/` checkouts lag `origin/main` and must be treated as
  evidence of the past, not the present.
