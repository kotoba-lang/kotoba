# ADR-0199 — a kernel that dies must say so, and then leave

- Status: accepted
- Date: 2026-09-03
- Closes the open item ADR-0190 recorded and did not fix: *"A trapping or
  non-terminating kernel object is INDISTINGUISHABLE FROM A QEMU FLAKE (after
  `#UD` the firmware halts and QEMU never exits, so the smoke spends 3 x 600 s
  reporting 'known flake')."*
- Pairs with ADR-0200 (the harness half) and ADR-0201 (the flake claim).

## What was actually wrong

Not the exception handler. `aiueos_exception_dispatch` already wrote `0x7d` to
`isa-debug-exit` and QEMU already exited when it ran. **The defect was WHERE
the handler was installed.**

`set_idt_gate(6, aiueos_isr_invalid_opcode)` sat at `main.c:1311`. Counted on
the tree it was written against, **fifty-one `kotoba_aiueos_*` calls run before
that line.** Every one of them executes with OVMF's IDT still loaded, and OVMF
answers `#UD` with a register dump and `CpuDeadLoop()`. The process does not
exit. The smoke can only time out.

The kernel already knew this and said so, one comment above the gap
(`main.c:1341`, unchanged here):

> a `#UD` raised while the FIRMWARE's handler is still installed produces an
> OVMF dump with no vector and no address. After the `lidt` it reaches
> `set_idt_gate(6, aiueos_isr_invalid_opcode)` and names itself.

That reasoning was applied to move ONE self-test after the `lidt`. It was never
applied to the other fifty.

Two more holes were in the same shape:

- **Only vectors 6, 14, 32-35 and 128 had gates at all.** A `#GP`, a `#DF`, a
  `#DE` — anywhere in the boot, at any time — went to the firmware handler and
  dead-looped, exactly like an early `#UD`.
- **The page-fault handler's default arm printed nothing.** Not one of the
  three deliberate probes meant `outl $0x7b, %eax` and a jump into a halt loop:
  one number, no vector, no faulting address, no line in either log.

## The decision

**Every fatal CPU exception prints one greppable line carrying the vector, the
error code and the faulting RIP, on both transports, and then terminates the
machine through `isa-debug-exit`. The gates that do that are installed before
the first Kotoba object runs.**

Three parts, all mechanism:

1. `entry.S` generates a stub for every vector in 0..31 that this kernel does
   not otherwise service. Two shapes, because the CPU pushes an error code for
   ten of the thirty-two and not for the rest; the no-error shape pushes a zero
   so that **one** frame layout reaches the reporter and the common path has no
   branch that could read the RIP out of the wrong slot.
2. `aiueos_exception_dispatch` takes the frame (vector, error, RIP, RSP, CR2,
   RFLAGS), renders one line into a static buffer, writes it to 0xe9 and to
   COM1, and exits. The expected end-of-boot `#UD` probe keeps its own branch
   and its own `AIUEOS_EXCEPTION_OK` line; nothing about that path changes.
3. `aiueos_kernel_main` loads the GDT and that whole gate table immediately
   after `serial_init()`, before the boot-info check and therefore before
   every Kotoba call. The historical install site is kept and now calls the
   same table, so `AIUEOS_DESCRIPTOR_TABLES_OK` keeps its position and its
   meaning.

The GDT must be loaded first and that is not incidental: the gates carry
selector `0x08`, and a gate whose selector is not a present 64-bit code segment
turns the fault into `#GP`, then `#DF`, then a triple fault — which QEMU
reports as a machine reset, not as a status, and `-no-reboot` makes that look
like a clean shutdown. A silent zero is worse than a hang.

## The line

```
AIUEOS_FATAL_EXCEPTION vector=6 mnemonic=#UD/invalid-opcode error=0x00000000 \
  rip=0x000000000010190e rsp=0x00000000001a6960 rflags=0x00010056 \
  cr2=0x0000000000000000 rip-text=0x0000190e insn=0f0b4885 ud2=yes
```

(one line in the log; wrapped here). Field by field, and why each is there:

| field | why |
|---|---|
| `vector` / `mnemonic` | ADR-0190's reproducer had neither. `mnemonic` carries no space so every field is one `key=value` |
| `error` | zero when the CPU pushes none, so its slot is always meaningful |
| `rip` | **BISECT-SHA256 recovered `RIP 0x165075` by relinking the image without `--strip-all` and doing arithmetic.** The kernel has it at trap time |
| `rip-text` | RIP minus `aiueos_text_start`, so the `nm` offset needs no subtraction |
| `insn` | four bytes at RIP, read only when RIP is inside this kernel's own text. `0f 0b` **is** `ud2` |
| `ud2` | `yes` / `no` / `unknown`, so a Kotoba fuel guard is one grep away from a page fault |
| `cr2` | the faulting address on `#PF`; zero elsewhere |

**What the line cannot say.** Amu emits `ud2` for a fuel guard *and* for a
kernel-window bounds check. `ud2=yes` does not distinguish them — that
distinction is not available at the trap, and claiming it would be a guess
printed in the same font as a measurement.

## Evidence

Red and green are the same image built two ways, through
`AIUEOS_EARLY_FAULT_SMOKE`, which exists only under that define and is never
set in production. Mode 2 is mode 1 with this ADR's early table compiled out —
i.e. it is *literally* the pre-ADR-0199 kernel — so the two halves differ in
the fix and not in the fault.

| build | harness | outcome | wall clock |
|---|---|---|---|
| mode 2 (`#UD`, early table OFF) | pre-ADR-0200 | `known flake kotoba-lang/aiueos#108` x2, then a timeout | **198 s** at `AIUEOS_QEMU_TIMEOUT=60`; **3 x 600 s** at the shipped default |
| mode 2 (`#UD`, early table OFF) | this branch | `GUEST-NO-EXIT after 60s (attempts=1)` + the write timeline | 77 s |
| mode 1 (`#UD`, early table ON) | this branch | `GUEST-DIED after 6s` + the line above | **22 s** |
| mode 3 (`int3`) | this branch | `GUEST-DIED after 5s`, `vector=3 mnemonic=#BP/breakpoint error=0x00000000` — a GENERATED no-error stub | 20 s |
| mode 4 (`mov $0x48,%ds`) | this branch | `GUEST-DIED after 7s`, `vector=13 mnemonic=#GP/general-protection error=0x00000048` — a GENERATED error-code stub | 25 s |
| `AIUEOS_EXPECT_FAULT=1` | this branch | `AIUEOS_FAULT_BOOT_OK synthetic-fault polled-receipt-written`, exit 0 | 118 s |
| unmodified | this branch | `AIUEOS_UEFI_SMOKE_OK`, every marker | 102 s |

Modes 3 and 4 are not decoration. A reporter exercised only through vector 6
has never shown that it reads the frame correctly: an error-code stub that
forgot its extra push would print the error code where the RIP goes, and **both
fields would still look like plausible addresses**. Mode 4 picks a selector
past this GDT's limit so the error code is a value chosen here, `0x48`, and a
misread frame cannot agree with it by accident.

## What is still indistinguishable

Named, because the point of this ADR is that silence is not a pass.

1. **The gate-building object itself.** The early table's sixteen bytes come
   from `kotoba_aiueos_idt_gate_build`, the same Kotoba object every other gate
   uses — deliberately, because the alternative is a second, C-authored answer
   to a bit-packing question whose failure mode is a well-formed gate pointing
   at the wrong ring-0 address. The cost is that this one object still executes
   under the firmware's IDT. Fifty-one down to one.
2. **A guest that dies before the early table is loaded still hangs, and the
   harness now says so distinctly.** ADR-0200's quiescence watchdog ends that
   attempt after 150 s of silence with `ended by: the quiescence watchdog` and
   `write timeline: last byte at T+6s`, on one attempt, instead of three
   ten-minute rounds of `known flake`. Measured: 174 s including the build.
3. **A `#DF` on a broken stack.** The TSS has no IST populated, so the
   double-fault stub runs on whatever `%rsp` is. If that is the reason we are
   here, the stub faults again and the CPU triple-faults. QEMU then *resets*,
   and with `-no-reboot` that is an exit, not a hang — ADR-0200's harness sees
   a status with no `AIUEOS_FATAL_EXCEPTION` line and calls it a failure, but
   it cannot say which vector. Fixing it needs an IST stack, which is a
   separate change to the TSS.
4. **Anything before `aiueos_kernel_entry`.** `BOOTX64.EFI` is a UEFI
   application and runs under the firmware's IDT by construction. A fault in
   the loader still dead-loops.
5. **Fuel guard versus bounds check**, above.

## Consequences

- `AIUEOS_EXCEPTION_FAIL unexpected-vector vector=N` is kept verbatim. Three
  ADRs and the `AIUEOS_EXPECT_FAULT` gate name that literal, and QWEN-KERNELS-2
  read a `d=128` non-terminating loop off it. The new line is printed before
  it, not instead of it.
- `qemu_exit(0x7d)` -> status 251 is kept for **every** fatal vector rather than
  giving each vector its own code. One status means "the guest died of a CPU
  exception"; which one is in the line. Splitting it would have broken the
  existing gate and put the vector in two places.
- A boot that reaches `AIUEOS_FATAL_IDT_OK early vectors=0-31` has covered
  everything after that marker. That is why the marker is printed after the
  `lidt` and not before it.
