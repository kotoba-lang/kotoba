# JUN-31 acceptance chain: pinned source graph -> rebuilt compiler -> kernel object -> EFI/GPT image -> QEMU boot (2026-10-24)

One bound chain, measured this tick end to end.

1. **Compiler rebuilt from its pinned Kotoba source graph** (`amu` tree eacafb13,
   `scripts/seed/selfhost-bootstrap.py`, loaderless, podman linux/arm64):
   `PASS_LOADERLESS_SELFHOST_BOOTSTRAP`, S1=S2=S3=root=`8256bfd8...`,
   `rootReproduces: true`, 24 runtime cases, hardening enforced natively
   (SIGSYS/SIGXCPU/SIGALRM/SIGSEGV /120), `cCompilerOrLoader=false`,
   `JVMNodeOrGraalFallback=false`, `emulation=false`. The rebuilt
   `S-x86_64.elf` (1,532,416 B) is **byte-identical** to the JUN-31 compiler
   pin `f74fd09b...` — the rebuild reproduces the same compiler.
2. **Kernel object rebuilt by that binary**: `kernel-probe-abi.kotoba`
   (`e9b45e45...`) -> `kernel-probe-abi.o` (841 B) = `0e04108e...` byte-identical
   to the pinned probe fixture; `AIUEOS_KOTOBA_OBJECT_OK export=kotoba_aiueos_probe
   imports=0 relocations=1`.
3. **EFI/GPT image** (`smoke-qemu-uefi.sh` -> `build-uefi.sh`,
   `AIUEOS_KOTOBA_KERNEL_OBJECT=<fresh object>`, IMAGE-FRESH artifacts=3
   head=7fc0401): BOOTX64.EFI `68919d1f...`, KERNEL.ELF `e21a79e5...` (762,504 B),
   INITRD.IMG `df2d916e...`. Containment proven: the probe body is byte-contained
   at KERNEL.ELF offset **206912** (`lea r9,[rip+0x83801]`, disp32 was 0 unlinked)
   — unique match among 95 lea-prefix hits.
4. **QEMU/OVMF boot (guest-browser profile, real input)**: full marker set
   `AIUEOS_GUEST_INPUT_OK synthetic=0` through
   `AIUEOS_GUEST_BROWSER_*_OK` (FRAME/INPUT/TEXT/TYPE/PREEDIT/IME_TOGGLE/DRAG/
   RESIZE/LOOP/CARET/LAUNCH/DICT/CURSOR/FOCUS/SCROLL/SELECTION/CLIPBOARD/DAMAGE/
   UIUX/KEYS/MAX/MAX_CTL/CURSOR_SHAPE/PRESSED). 116 QMP screendumps this run;
   representative: guest-browser-preedit-committed.ppm, guest-browser-selection.ppm, guest-browser-typed.ppm.

Termination: GUEST-NO-EXIT after 321s — the 320s wall clock ended a still-live
persistent loop (last byte T+319s); SMOKE-EXIT=1 is the wall-clock, not a gate
failure, and explicitly not aiueos#108.

## Boundary (say this, do not round it up)

* `kernel/*.c` is still compiled by zig cc; the C-free claim covers the
  compiler lineage and the kotoba object route only. The "no C path in the
  accepted build" criterion is therefore **not** fully met (open, JUN-64).
* Objects other than `kernel-probe-abi.o` are the previously pinned committed
  objects, not rebuilt this tick.
* x86-64 seccomp/rlimit enforcement under qemu-user is unmeasured (JUN-34).
* The #108 process-phase stall is not reproduced or fixed here.
