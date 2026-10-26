# JUN-31 C-surface: the accepted build's exact surface, and the profile split (2026-10-24)

Follows `docs/evidence/aiueos-jun31-c-surface-20261024/` (inventory at `026fe7c`),
which counted `build-uefi.sh`'s 34 `zig cc`/asm units as an **upper bound** and
recorded "the conditional/unconditional split is not derived here". This note
derives the split and binds it to the route the accepted chain actually built.

Tree: PR #489 branch tip `bda1c892` (`origin/main` `f481e9e` merged, 0 behind).
Measurement: `split.json` (per-unit lines at this tree, gate per unit).

## The route binding

`docs/evidence/aiueos-jun31-acceptance-chain-20261024/receipt.json`
(`packagingRoute.build`) records the accepted image build as
`smoke-qemu-uefi.sh` → `build-uefi.sh` with `AIUEOS_KOTOBA_KERNEL_OBJECT=<fresh>`
and `AIUEOS_OUT=build/aiueos-j` and **no profile environment**. That is
`build-uefi.sh`'s default route, so the accepted build's C surface is the
default-route set, not the 34-unit upper bound.

## Numbers at this tree (wc -l per source)

| set | units | lines |
|---|---:|---:|
| upper bound: every unit `build-uefi.sh` can compile | 34 | 27,901 |
| **the accepted build (default route)** | **25** | **22,359** |
| — kernel C+ASM | 23 | 20,740 |
| — UEFI loader (`uefi/main.c` + `uefi/model_slots.c`) | 2 | 1,619 |
| gated out (opt-in profiles only) | 9 | 5,542 |

Drift since the 2026-10-24 inventory: upper bound 27,818 → **27,901 (+83)**, all
of it `kernel/main.c` 7,545 → 7,628 (PR #490 suspend/resume). No other unit
moved. The surface is not static; each feature land moves it.

## The 9 gated units and their gates (from `build-uefi.sh`'s own conditionals)

| gate | units | lines |
|---|---|---:|
| `AIUEOS_MURAKUMO_DEVICE_RESULT=1` | `kernel/device_result.c` (541), `kernel/device_worker_protocol.c` (40) | 581 |
| `AIUEOS_PHYSICAL_QUALIFICATION=1` | `kernel/qualification.c` (154), `kernel/qualification_entry.S` (114) | 268 |
| `AIUEOS_PLC_RT_SMOKE=1` | `kernel/plc_runtime.c` (157) | 157 |
| `AIUEOS_QWEN38_MODEL_HANDOFF=1` or `AIUEOS_MODEL_NVME_SLOTS=1` | `kernel/model_handoff.c` (101), `kernel/qwen35_runtime.c` (1,073), `kernel/qwen35_quant.c` (637), `kernel/qwen35_infer.c` (2,725) | 4,536 |

Compile and link are gated together (e.g. `model_handoff.c` compiles inside
`if [ -n "$model_handoff_link" ]`): a default build run this tick
(`./os/aiueos/scripts/build-uefi.sh`, exit 0, 12 s) produced **no** object for
any of the 9, and every object it did build appears in `build/aiueos/kernel.map`
— no compiled-but-unlinked waste on this route.

## What this changes for JUN-31 criterion 2

The gate is **25 `zig cc`/asm units / 22,359 lines** (23 kernel + 2 loader),
not 34 / 27,818. The 5,542 gated lines are opt-in profiles and do not appear in
the accepted build at all; the zero-`zig cc` closing condition still has to
clear the 25.

## What is actually left to remove (measured, and why the wrappers do not move)

Every one of the 25 default-route units is live in the link. The
decision-migrated marshalling wrappers among them (`micro_infer.c` 29,
`inference_status.c` 83, `job_protocol.c` 133, `tls_aes_gcm.c` 116) call Kotoba
objects only, but each has a C caller (`pci.c`, `main.c`, `framebuffer.c`,
`tls13.c` — symbol-level greps recorded this tick), and ADR-0212 keeps a file
from moving while it calls C. Folding a wrapper into its caller is code motion,
not reduction: `micro_infer.c`'s 29 lines are exactly the 8-byte record unpack
its single call site would otherwise carry inline. Consequences:

1. ADR-0220's ordered next step — "convert `qualification.c`'s 19 judgment
   lines" — sits in the `AIUEOS_PHYSICAL_QUALIFICATION` profile and **does not
   move the accepted build's number at all**. Worth doing for the programme;
   irrelevant to criterion 2's count.
2. The two routes that do move criterion 2's number are unchanged: the
   Kotoba/Amu PE32+ UEFI loader (removes the loader's 2 units / 1,619 lines at
   the machine-checked `AIUEOS_KOTOBA_LOADER_EFI` slot, currently
   `REFUSED foreign-code: uefi/main.c`), and converting caller judgment in
   `pci.c` / `main.c` (the cycle; ADR-0212 orders it last).

## Receipts

- inventory + split: `split.json` in this dir (per-unit lines, gate, deltas).
- default build run: `./os/aiueos/scripts/build-uefi.sh` exit 0 at `bda1c892`;
  link map `build/aiueos/kernel.map` (118 objects, all built C/ASM units
  present). No source changed this tick — the boot behaviour of this tree is
  PR #490's verified boot (`receipts/vm-20261024/` on `origin/main`).
