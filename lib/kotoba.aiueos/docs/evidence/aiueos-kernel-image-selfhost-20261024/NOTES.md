# selfhost kernel object → bootable image (JUN-31, 2026-10-24)

First connection of the C-free selfhost object route to the kernel IMAGE route.

* **Compiler**: `S-x86_64.elf` (`f74fd09b…`) from the loaderless selfhost
  bootstrap (fixed point `8256bfd8…`, receipt `2e1176f0…`), reused from the
  2026-10-22 measurement after re-verifying every pin this run. Runs under
  podman `--platform linux/amd64` (qemu-user binfmt).
* **Naming contract finding**: the checked-in kernel source
  `os/aiueos/kotoba/kernel-probe.kotoba` (`(defn main [] 42)`, `2da98859…`)
  compiles C-free to `kernel-probe-checkedin-selfhost.o` (`4c08eaab…`, 832 B)
  whose export is `main` — the seed route (`seed/74-x86_64-aiueos-object.kotoba`)
  is export-literal ("`main` carries no special meaning"), while the Amu native
  route assigns `kotoba_aiueos_*` through its allow-list and emits
  `kotoba_source_entry`. The `main`-named object **fails** aiueos's fail-closed
  `verify-kotoba-kernel-object.py` (`requires exactly one kotoba_aiueos_probe
  symbol`), so it cannot satisfy `kernel/main.c:2275`.
* **ABI object**: `kernel-probe-abi.kotoba` (`e9b45e45…`) names its export;
  compiled with `--fuel 1024` it emits `kernel-probe-abi.o` (`0e04108e…`, 841 B)
  — byte-identical to the probe fixture pin of both `cfree-kernel-object`
  measurements, and `AIUEOS_KOTOBA_OBJECT_OK … imports=0 relocations=1`.
* **Image**: `build-uefi.sh` with `AIUEOS_KOTOBA_KERNEL_OBJECT=kernel-probe-abi.o`
  built `KERNEL.ELF` (`99f908be…`) whose file offset **324461** holds the
  selfhost probe body with its link-time relocation applied
  (`lea r9,[rip+0x75cf1]`). Containment is byte-proven.
* **Boot** (`smoke-qemu-uefi.sh`, QEMU 10.0.3 + OVMF): 2 attempts × 175 s both
  reached `AIUEOS_KOTOBA_ELF_PROCESS_OK source=catalog apps=2 et-exec
  segments=rx,rw result=42 domains=4,5` and then went quiet at the script's
  default `AIUEOS_FLAKE_SIGNATURE` (`AIUEOS_KOTOBA_ELF_PROCESS_OK` →
  HOST-FLAKE-SIGNATURE, retried). Attempt 3 was cut by the 420 s cron cap.

Boundary (say this, do not round it up): the guest desktop input response and
the screenshot for **this** image are not captured (`guest-browser-flow.ppm` in
`build/aiueos/` is stale 2026-10-22 evidence for the previous image and is not
claimed). The stall attribution is unmeasured — the next measurement is a
control boot of the same tree with the committed `kernel-probe.o`, then a
re-run that gets past the flake signature to the desktop. `kernel/*.c` is still
compiled by zig cc; the C-free claim covers the compiler lineage and the kotoba
object route only.
