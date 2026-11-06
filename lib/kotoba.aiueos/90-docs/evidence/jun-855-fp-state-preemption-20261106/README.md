# JUN-855: does AIUEOS preserve x87/SSE state across a CPL3 switch or preemption?

Date: 2026-11-06. Question from ADR-0287 (render in a user domain): "f64 in the user domain holds only if the
kernel saves and restores floating-point state on a CPL3 process switch."

## Answer

**No. The stock AIUEOS UEFI kernel does not preserve x87, SSE or MXCSR state across CPL3 preemption, and
it leaks one process's register contents into the other.** Measured under QEMU TCG: two CPL3 processes each
hold a different value in xmm0/xmm7, x87 st0, the x87 control word and MXCSR; each found the other process's
values in its own registers about 50 to 70 times during 414 user task switches, in all three registers classes.
A small experimental FXSAVE64/FXRSTOR64 in the APIC timer ISR brought that to 0 events in about 2.9 million
checks and about 420 switches. So the f64 condition in ADR-0287 is **not met today**, and it is a kernel change
of known size rather than an open question.

There is a second, earlier blocker that is independent of the kernel: **no `x86_64-aiueos-user-*` target
can compile a float at all** (section 1).

What was and was not run:

| claim | status |
|---|---|
| user-v1..v5 refuse f64 and f32 with E7101 (detail 33 and 36) | **measured** (compiler run, section 1) |
| stock C UEFI kernel loses and leaks x87/SSE/MXCSR on timer preemption | **measured** (QEMU, section 2) |
| a probe that cannot fail is not what produced that result | **measured** (poison control and tampered-log controls, section 3) |
| FXSAVE64/FXRSTOR64 in the timer ISR fixes it for this scenario | **measured** for the timer path with two processes; other paths not measured (section 4) |
| the pure-Kotoba native kernel (amu seed 95) does the same | **not run, inferred from reading** (section 5) |
| the plan for the native kernel (section 6) | **inferred**, nothing of it was built |

## 1. The compiler cannot express floats in a user target (measured)

Compiler: `amu-full-root.macho` from the read-only checkout `wt/claude/amu-merged`
(HEAD `385bab04447643144cdf2e6710f60e842eec96a0`), sha256
`88623412d4470e7090037ea6b35f2176e5d6edff322e90843b84bce61f17a229`. `compiler/ac.py` runs it with the source
directory as its FD3 file root, the way `scripts/seed/check-aiueos-user-macos-native.py` does. Sources are the
float cases of `seed/float-cases.json` (`compiler/*.kotoba`); full output is `compiler/results.txt`.

```
python3 -I ac.py DIR compile f64m.kotoba --target x86_64-aiueos-user-v1 --output f64m.out
seed-x86_64-aiueos-object: E7101 unsupported object profile or code limit; detail 33     (f64 multiply)
python3 -I ac.py DIR compile f32t.kotoba --target x86_64-aiueos-user-v1 --output f32t.out
seed-x86_64-aiueos-object: E7101 unsupported object profile or code limit; detail 36     (f32)
python3 -I ac.py DIR compile f64cmp.kotoba --target x86_64-aiueos-user-v1 --output ...
seed-x86_64-aiueos-object: E7101 unsupported object profile or code limit; detail 33     (f64 compare)
```

The same three results hold for `user-v2`, `v3`, `v4` and `v5`. The control is the scalar program
(`(defn main [] :i64 42)`), which compiles with `{:ok true ... :format :elf64-exec, :bytes 8280}` under the same
driver, so the refusal is the float and not the driver. `x86_64-aiueos-user-plc-v1` was not tried.

`x86_64-aiueos-kernel-v1` does admit SSE floats: the f32 program and the f64 compare compile (592 and 604 text
bytes), while f64-to-i64 truncation is refused with detail 32. That matches the comment above `xo-float-sir?` in
amu `seed/74-x86_64-aiueos-object.kotoba`: min/max and f64-to-i64 stay refused and an export keeps scalar types.
Detail numbers 33 and 36 are the codes `float-cases.json` documents (33 f64-domain, 36 f32-domain SIR); that
mapping is from that file, I did not trace it in the compiler.

Consequence: for f64 to exist in a user domain, the user targets need the float SIR admission that the kernel
object route already has, **and** the kernel must save FP state. Neither alone is enough. I did not modify the
compiler.

## 2. The kernel does not save or restore FP state (measured)

ADR-0175's `AIUEOS_RING3_OK processes=2 preemptive ...` comes from the **C UEFI kernel**
(`os/aiueos/kernel/*.c`, `main.c:7858`), not from the pure-Kotoba native kernel. Its APIC timer ISR
(`entry.S: aiueos_isr_apic_timer`) pushes the 15 general registers, calls `aiueos_scheduler_on_timer`, switches
stack and CR3, pops and `iretq`s. A search of `kernel/*.c`, `entry.S` finds no `fxsave`, `fxrstor`, `xsave` or
`fninit`; that is reading, the run below is the measurement.

Probe (compiled only with `AIUEOS_FP_PROBE`, see section 7): `process.c` replaces the final
`for(;;){scheduled_runs++; pause}` of the two existing CPL3 processes (domains 2 and 3) by
`aiueos_fp_probe_loop`, hand-written x86-64 assembly in `.user.text`. Per process it loads

| | domain 2 | domain 3 |
|---|---|---|
| xmm0 = {pat, ~pat}, xmm7 = xmm0 | pat `0xC0DE0200A5A5A5A5` | pat `0xC0DE0300A5A5A5A5` |
| x87 st0 (double) | 2.5 `0x4004000000000000` | 3.5 `0x400C000000000000` |
| x87 control word | `0x037f` | `0x027f` |
| MXCSR | `0x3f80` (round down) | `0x5f80` (round up) |

and then loops forever re-reading all of them. A disagreement counts **one event** for its class, records the
value it saw, and reloads the expected state (so a counter is a number of clobberings, not of iterations spent in
a wrong state). Every 1024 iterations it also issues a SYSCALL ABI query. The kernel wait loop in
`aiueos_process_enter` is extended so the processes keep running until the scheduler has switched user tasks 400
more times, then `fp_probe_report` prints one `AIUEOS_FP_PROBE` line.

Commands (from `lib/kotoba.aiueos`, `S` = a scratch directory; the pinned Amu is fetched with the repository's own
`scripts/fetch-native-amu.sh`, which prints `AMU_PINNED_OK revision=ce98270...`):

```
sh ../../scripts/fetch-native-amu.sh $S/amu-pinned
AIUEOS_FP_PROBE=measure AIUEOS_AMU_SOURCE=$S/amu-pinned AIUEOS_OUT=$S/out-measure \
  QEMU_SYSTEM_X86_64=/opt/homebrew/bin/qemu-system-x86_64 sh os/aiueos/scripts/smoke-qemu-uefi.sh
```

Each run: about 67 s wall, `AIUEOS_UEFI_SMOKE_OK`, exit 0, `AIUEOS_RING3_OK processes=2 preemptive ...` present.
QEMU is `-machine q35,accel=tcg -cpu max -m 128M -smp 2` (set by the smoke script). Result, stock kernel
(`serial/measure.txt`, repeated in `serial/measure2.txt`):

```
mode=measure
p0{domain=2 checks=1417777 xmm_events=51 x87_events=68 mxcsr_events=70 bad_xmm0_lo=0xc0de0300a5a5a5a5
   bad_st0=0x400c000000000000 bad_cw=0x027f bad_mxcsr=0x5f80 tsc_gaps=70 syscalls=1415}
p1{domain=3 checks=1403447 xmm_events=47 x87_events=64 mxcsr_events=70 bad_xmm0_lo=0xc0de0200a5a5a5a5
   bad_st0=0x4004000000000000 bad_cw=0x037f bad_mxcsr=0x3f80 tsc_gaps=70 syscalls=1370}
user_switches_during=414
```

Reading it: the "last bad" values are exactly the **other** domain's configured values (domain 2 saw domain
3's xmm pattern, st0, control word and MXCSR, and the reverse). So the registers are not zeroed or scribbled by
kernel code; the incoming process simply inherits the outgoing process's registers. That is both a correctness
failure (f64 results change) and an information leak across address spaces. `tsc_gaps` (a TSC jump over 200000 in
the loop) is 70 per process, the same order as the event counts, i.e. the events line up with being descheduled.
The second run gave 48/66/69 and 46/60/70 with 414 switches: same picture, not identical numbers. I did not
explain why xmm events are somewhat fewer than x87 events.

The syscall path alone is not shown to be a source: events occur per preemption, and I did not isolate
SYSCALL-only runs.

## 3. Negative controls

* **Kernel-side mutant (`AIUEOS_FP_PROBE=poison`)**: the timer ISR additionally runs `pxor %xmm0,%xmm0; fninit`.
  Probe reports events in every class for both processes, with `bad_xmm0_lo=0` (`serial/poison.txt`). The probe
  therefore detects a kernel that really does clobber state.
* **Gate** `os/aiueos/scripts/check-fp-state-probe.py --expect preserved|clobbered` and its 7 unit tests
  `test_check_fp_state_probe.py` (run: `python3 -I os/aiueos/scripts/test_check_fp_state_probe.py`, `Ran 7 tests
  ... OK`). Controls: `preserved` on the stock log exits 1 and `clobbered` on the fixed log exits 1; one
  injected event in the fixed log makes `preserved` exit 1; a run with 3 user switches or 10 checks is refused as
  vacuous even though its counters are zero; a missing or duplicated probe line exits 2; a missing
  `AIUEOS_RING3_OK` fails. The real raw serial logs (with CR/LF) also pass the gate.
* **Default build untouched**: with `AIUEOS_FP_PROBE` unset the build prints no probe line and reaches
  `AIUEOS_RING3_OK`. I compared the object files of `entry`, `scheduler`, `process` and `main` of a build of the
  unmodified tree with a build of the edited tree (probe off): ELF code/data sections are identical (the
  `.o` files differ only in non-allocated sections; I compared section payloads, not relocations or debug info).

## 4. Fixed experiment: FXSAVE64/FXRSTOR64 around the timer ISR (measured, for that path only)

`AIUEOS_FP_PROBE=fxsave` (`serial/fxsave.txt`):

```
mode=measure+fxsave
p0{domain=2 checks=1466938 xmm_events=0 x87_events=0 mxcsr_events=0 ... tsc_gaps=71 syscalls=1479}
p1{domain=3 checks=1442780 xmm_events=0 x87_events=0 mxcsr_events=0 ... tsc_gaps=72 syscalls=1423}
user_switches_during=420
```

Change: `entry.S` runs `fxsave64 aiueos_fx_isr_scratch(%rip)` right after the 15 pushes and before any C;
`aiueos_scheduler_on_timer` copies the scratch into a per-slot 512-byte area for the outgoing task and loads the
incoming task's area (the architectural reset image, FCW `0x037f`, MXCSR `0x1f80`, on its first dispatch) into the
scratch; `entry.S` runs `fxrstor64 aiueos_fx_isr_scratch(%rip)` right after `mov %rax,%rsp`. The per-slot areas
are a separate array because `tasks[]` is an ABI of the Kotoba dispatch object.

Limits of this experiment, all unmeasured: one global scratch (not per CPU, so not SMP-safe if an AP takes this
ISR); only the APIC timer ISR is covered, not `aiueos_isr_external_timer`, the virtio ISRs, exception handlers or
any other C that runs at CPL0 with SSE enabled between a SYSCALL entry and SYSRET (the probe's SYSCALL is only the
cheapest query, `n=0`); QEMU TCG, not KVM or hardware; CR4.OSFXSR relied on the firmware having set it (OVMF did,
since FXSAVE ran without a fault; the C kernel's default path never sets it, the Kotoba `xstate-setup.kotoba`
that does is only linked into the model-handoff image); x87/SSE only, no AVX (that model-handoff image also
enables XCR0 SSE|AVX, whose upper YMM halves FXSAVE does not cover).

## 5. The pure-Kotoba native kernel (not run; inferred from reading amu `seed/`)

The user-domain path there is amu `seed/95-aiueos-user-context.kotoba`:

* `uv-enable` sets CR4 `|= 0x600` (OSFXSR, OSXMMEXCPT), writes an FP image at `uv-fpu` with
  `66c7077f03` (FCW `0x037f`) and `c74718801f0000` (MXCSR `0x1f80`), and **refuses** (jumps to its zero exit) when
  CR4 has bit 12 (LA57) or bit 18 (OSXSAVE): `0f20e0 a9 00100400 0f85`. So XSAVE state is out of scope there.
* `uv-enter` runs `480fae0f` = **FXRSTOR64 [rdi]** from that image on every entry, then builds an `iretq` frame
  `6a1b 50 6a02 6a23 52` (SS `0x1b`, RFLAGS = **2**, i.e. IF clear, CS `0x23`).
* There is no FXSAVE: `grep` for `0fae` across seeds 74, 86, 88, 92, 95 and 96 finds only that one FXRSTOR64.

So, for that kernel: a domain starts every entry from the reset image (no leakage in, no preservation), and with
IF clear at CPL3 the timer cannot preempt it; what matters there is domain exit and re-entry, and the SYSCALL
round trip. I did not build or run that kernel with an SSE-using user program (and cannot, because of section 1).

## 6. Minimal plan for the native kernel (inferred, nothing built)

Per user domain keep a 512-byte, 16-byte-aligned FXSAVE image (4 domains today; `uv-fpu` is one image).

1. **Entry points**: at the start of the native SYSCALL handler and of the private fault entry (before any
   Kotoba kernel code runs, since `kernel-v1` objects may use SSE), emit **FXSAVE64 [domain image]**
   = `48 0F AE /0`, e.g. `48 0F AE 07` for `[rdi]`, `48 0F AE 06` for `[rsi]`. On return (before SYSRET, and in
   `uv-enter`) emit **FXRSTOR64 [domain image]** = `48 0F AE /1` (`48 0F AE 0F` for `[rdi]`; this exact byte
   string already exists at `seed/95` line 226).
2. **Seed file changes**: `seed/95` only: allocate four images instead of one (`uv-fpu`/`UV-FPU`/`UV-V5-FPU` offsets
   and the context size, which the layout gate pins), initialise each to the reset image in `uv-enable`, make
   `uv-enter` restore the image of the domain being entered instead of the shared one, and add FXSAVE64 to the
   syscall-entry and fault-entry stubs, where the hand-assembled bytes are emitted with `iv-hex`. Because seed 95
   already emits FXRSTOR64 through `iv-hex`, **no new op class in `seed/74` appears to be needed** (the earlier
   note that 74 has no FXSAVE class op is true but that op is not what emits this). If domain images must live in
   the context entry, `seed/88` (328-byte context entry) is touched; keeping them beside `uv-fpu` avoids that.
3. **Keep out of scope**: OSXSAVE/AVX (95 refuses it today); user code is limited to x87/SSE2.
4. **Gate**: the C-kernel probe above, ported as a native QEMU profile, is blocked until a user target can emit
   SSE (section 1) or a hand-assembled probe image is allowed in the user-code staging path.

For the C UEFI kernel the experiment in section 4 is the minimal change; a production version needs per-CPU
scratch, coverage of every CPL0 entry that can reach SSE-using C, and setting CR4.OSFXSR itself.

## 7. Files

* `kernel/process.c`, `kernel/scheduler.c`, `kernel/entry.S`, `scripts/build-uefi.sh`: probe, poison and fxsave
  hooks, all behind `AIUEOS_FP_PROBE=measure|poison|fxsave` (`-DAIUEOS_FP_PROBE[_POISON|_FXSAVE]`); off by default.
* `scripts/check-fp-state-probe.py`, `scripts/test_check_fp_state_probe.py`: gate and its negative controls.
* `serial/*.txt`: the `AIUEOS_FP_PROBE`, `AIUEOS_RING3_OK` and `AIUEOS_SCHEDULER_OK` lines of the four runs
  (CR removed). `compiler/`: sources, driver and output of section 1.
* `local-changes.json` pins refreshed (`check-library-local-changes-pins.py`: `PASS_SOURCE_PIN_AUDIT`).

## 8. Discrepancies found (code wins)

* The task note said no FXRSTOR/XSAVE support existed. `seed/95-aiueos-user-context.kotoba:226` emits
  FXRSTOR64 (`480fae0f`); what is missing is FXSAVE and per-domain images.
* ADR-0287 states the f64 question as only a kernel one. By the compiler's own refusal (section 1) the user
  targets cannot produce a float, so it is also a compiler question.
* ADR-0175's `AIUEOS_RING3_OK` is the C UEFI kernel's, not the native Kotoba kernel's; they are different
  kernels with different user-context code.
