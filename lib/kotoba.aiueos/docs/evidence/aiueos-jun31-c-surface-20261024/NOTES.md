# JUN-31 acceptance decision + C-surface inventory (2026-10-24)

Decision tick. The acceptance chain itself was measured last tick
(`docs/evidence/aiueos-jun31-acceptance-chain-20261024/receipt.json`, commit
`026fe7c`). This note decides completion and bounds what is left.

## Acceptance criteria (JUN-31 body) — status

| # | criterion | status | evidence |
|---|-----------|--------|----------|
| 1 | Amu compiler rebuilt from its pinned Kotoba source graph, then that binary rebuilds the AIUEOS kernel and the EFI/GPT image | **MET** | acceptance-chain receipt: fixed point S1=S2=S3=root=`8256bfd8…`; rebuilt `S-x86_64.elf` `f74fd09b…` byte-identical to the compiler pin; `kernel-probe-abi.o` `0e04108e…` byte-identical to the probe fixture pin; KERNEL.ELF `e21a79e5…` with the probe body relocated at file offset 206912 (unique 74 B match) |
| 2 | Receipts distinguish compiler / kernel / packaging routes and bind all source and artifact hashes; **no C, NBB/Node, JVM or GraalVM path appears in the accepted build** | **NOT MET** (route+hash half MET, "no C path" half open) | routes and hashes: acceptance-chain receipt. C path: `inventory.json` — `build-uefi.sh` compiles **34 C/ASM units, 27,818 lines, with `zig cc`** into the bootable build |
| 3 | QEMU/OVMF boots the generated disk and the native GOP desktop responds to input | **MET** | guest-browser run, real input (`synthetic=0`): `AIUEOS_GUEST_INPUT_OK` … `BROWSER_PRESSED_OK`, 116 QMP screendumps |
| 4 | QEMU logs and a screenshot preserved with the receipts | **MET** | `kernel-serial.log`, `uefi-debug.log`, `smoke-run.log`, `screens/` in the acceptance-chain dir |

## Decision

**JUN-31 stays In Progress. No completion claim.** Criterion 2 is binary and its
"no C … path appears in the accepted build" half is false today: the accepted
bootable build is produced by `zig cc` / `zig ld.lld`.

Closing condition (either one):
1. the whole chain (compiler rebuild → kernel → EFI/GPT image → QEMU/OVMF boot +
   GOP desktop input response) is re-measured through a build path with **zero**
   `zig cc` compile units; or
2. the owner re-scopes criterion 2 in writing (e.g. accepts the C-free compiler /
   kotoba-object route as the boundary while `kernel/*.c` remains, tracked by
   JUN-64).

## The remaining gate, bounded by measurement

`inventory.json` (derived from `os/aiueos/scripts/build-uefi.sh` at `026fe7c`,
`script_line` per unit):

* **34 compile units / 27,818 lines** total in the build script's C surface.
  * kernel C+ASM → KERNEL.ELF: **32 units / 26,199 lines** (largest: `kernel/main.c` 7,545, `kernel/pci.c` 6,305).
  * UEFI loader → BOOTX64.EFI: **2 units / 1,619 lines** (`uefi/main.c` 1,222, `uefi/model_slots.c` 397).
* Bounds: this is an upper bound — some units are profile-conditional
  (`device_result.c` / `device_worker_protocol.c` behind
  `AIUEOS_MURAKUMO_DEVICE_RESULT`, `qwen35_*` behind parity profiles). The
  conditional/unconditional split is not derived here. Every listed unit is
  compiled by `zig cc`, i.e. a C toolchain, wherever it participates.
* The script's own count of the ordinary kernel link is "the 33 C/ASM objects"
  (ADR-0131 comment).

Two named missing artifacts, and the boundary is already machine-checked at one
point (`AIUEOS_K16_PURE_NATIVE=1`, ADR-0131):

1. **A Kotoba/Amu-produced PE32+ UEFI loader.** The pure-native profile restricts
   the kernel link to Kotoba objects + Amu stubs and then *refuses to emit a
   loader* — `REFUSED foreign-code: uefi/main.c` — unless
   `AIUEOS_KOTOBA_LOADER_EFI` points at a non-C PE32+. That slot is the
   machine-checked acceptance point for criterion 2's loader half.
2. **A bootable kernel whose link carries no C.** The pure-native `kernel.elf` is
   a boundary-check artifact ("this profile does NOT produce a bootable image and
   is not trying to"); a functional kernel without the 32 C/ASM units is the
   JUN-64 refactor. Waves ADR-0219/0220/0221 already move *decisions* into Kotoba
   objects (inference_status / model_handoff / device_worker_protocol, job_protocol
   mode word, micro_infer table, tls_aes_gcm KAT, qwen35 matvec/norm/attention);
   the C callers remain.

## Provenance

* `inventory.json` — machine-derived from `build-uefi.sh` (`zig cc` invocations,
  per-unit line counts from the sources themselves).
* Chain receipt for criteria 1/3/4 —
  `../aiueos-jun31-acceptance-chain-20261024/receipt.json` (commit `026fe7c`).
* No credentials, signing keys or customer data in this record.
