# JUN-31: the C-free build gate, started — measured baseline of `zig cc` in the image build (2026-10-24)

着手 of the C-free re-measurement path (§6 of
`aiueos-jun31-kernel-swap-judgment-20261024`): "gate the toolchain, not the
claim". New `os/aiueos/scripts/cfree-build-gate.py` (Python = build
orchestration only) runs a build with every C/C++ compiler on PATH
(`zig cc`/`zig c++`, `cc`, `gcc`, `clang`, `c++`, `g++`) replaced by a
recording shim — each invocation appends one JSON line to
`tool-invocations.jsonl` before the real tool runs — then tallies the log into
the `cFreeRoute` block the chain receipts bind.

## Measured baseline (this run, machine-measured, not estimated)

Command: `build-uefi.sh` with `AIUEOS_KOTOBA_KERNEL_OBJECT=kernel-probe-abi.o`
(same route as `aiueos-kernel-image-selfhost-20261024`), under the gate.
Build **exit 0** — the shim is transparent; the image built to
`build/aiueos/esp/EFI/BOOT/BOOTX64.EFI` exactly as ungated.

```
totalToolInvocations 27
zigCcInvocations     25   -> cCompilerInvocations 25   -> verdict FAIL
zigLinkerInvocations  2   (zig ld.lld kernel link, zig lld-link BOOTX64.EFI)
cUnitCount           25
```

The 25 C/S units, by name (`receipt.json` holds the full paths):
23 `os/aiueos/kernel/*.c` + `kernel/entry.S` + `kernel/ap_trampoline.S` +
`kernel-identity.c` (generated) + `os/aiueos/uefi/main.c` = the whole remaining
C surface of this route. The kotoba object route is inside the same link line
(`kernel-probe-abi.o` plus the ~90 `AIUEOS_KOTOBA_OBJECT_OK` objects) — the
C-free gap is exactly these 25 compile invocations, not the link.

Self-test of the PASS path: `selftest-pass.jsonl` (a `zig version` +
`zig ld.lld --version` build) tallies `zigCcInvocations 0` → **verdict PASS**,
exit 0; the linker is counted separately and does not trip the gate.

## What this closes and what it does not

* The gate exists, is machine-enforced on a real build run, and its PASS path
  is demonstrated. From here "zero `zig cc`" is a measurement of a build, not
  a claim in a receipt.
* Verdict is **FAIL** on the current image route, as the c-surface inventory
  predicted. The route's default 25 units match the inventory's "25 units /
  22,359 lines default route" (the 9 profile-gated / 5,542-line units compile
  only in the guest-browser profile and were not in this build).
* Not done: replacing the 25 units with kotoba/amu objects (per the §6 path:
  one counterpart each, `entry.S`' `aiueos_kernel_entry` symbol included —
  ADR-0131 excludes entry.S), and the end-to-end recount (compiler rebuild
  G1=G2=G3 → kernel object(s) → image with zero `zig cc` → boot markers).

## Boundary

* The shim wraps `zig` and the common C compiler names; a build invoking an
  unwrapped compiler name would evade it. The gate is a measurement instrument
  on PATH, not a sandbox.
* This run measured the object-route build (`AIUEOS_KOTOBA_KERNEL_OBJECT`).
  The default route (checked-in `kernel-probe.o`) and the guest-browser
  profile build have their own counts and were not measured here.
* QEMU was not run for this evidence; `gated-build.log` is the build only.
