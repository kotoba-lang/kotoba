# JUN-31: the entry contract, measured — a contract-passing kernel at the loader's jump (2026-10-24)

Question this tick answered (continuing `aiueos-jun31-kernel-swap-judgment-20261024`,
route A "grow the boot-path kernel inside the image-route contract", minimal step):
boot **contract-passing** kotoba-native image-route kernels through the Kotoba
loader and measure the entry-contract gap — the T/U fixture-literal binding and
the boot-info handoff — on the machine, not by inspection.

Setup is single-variable against the green boot-jump run: `image-kernel-probe.cljk`
is **byte-identical** to the swap judgment's `swap-probe.cljk` (sha256 `30f26962…`),
and the loader it builds, BOOTX64.EFI 50,688 B, is **byte-identical `bc0696e1…`
across all four runs** (green boot-jump, real-kernel swap, run 1, run 2 —
`built-artifacts*.sha256`). Same amu (`jun31-pe-shim-pin-20261024`, `bin/amu`
`ec532548…`, `--jvm-free`, fuel 200,000,000), same QEMU/OVMF. The only variable
is the kernel file staged at `\EFI\AIUEOS\KERNEL.ELF`.

## 1. Run 1 — the image-route desktop kernel (127,256 B): admitted, placed, refused at the jump

Input `build/aiueos-native-desktop-20261017-repro/KERNEL.ELF` (127,256 B,
sha256 `0a6fef42…`) — passes **every** ADR-0180 admit clause (byte-measured in
`desktop-repro.KERNEL.ELF.elf-facts.txt`):

```
exit=33 debugcon="KHSCNAbcdefPWghvonkrxMXZ"
entry="0000000000101000" verdicts="0 2 5 24 23 41" esp="0 0 3 0 0 0"
map="0 5520 48" boot="0 0 0 127256 127256 1052672 1097728 1052672 1097728"
```

* **`x` is present — first measured disk-admission PASS (reason 0) for a
  non-fixture, real AIUEOS kernel image.** The fs stage read the whole file
  (`kgot == klen == 127,256`) and the same `aiueos.uefi.elf/admit` that refused
  the kernel object route last tick answered 0.
* Placement machinery ran on the real image's own facts: segments placed at
  their parsed `p_paddr` (`s0=0x101000`, `s1=0x10c000`), `c0 == s0`, `c1 == s1`.
* **T and U refused (`tfacts=0 uflags=0`) — the fixture-literal binding.**
  `loader-probe.kotoba`'s clauses vs this image's measured bytes: `s1off` is
  49,152 (clause demands 32,768), `s0mem` 42,368 (clause caps at 4,096 = the
  1-page window), `klen` 127,256 (clause caps at 114,688 = the 28-page buffer).
  Three clauses, each hard-coded to the fixture's placement literal.
* `bootall = 2 ≠ 4` → the loader took the named branch: `out 0xf4, 16` → **QEMU
  33** (xstat was 0, so no `xstat` serial line — that branch prints nothing).
  The jump was refused; nothing of the kernel ran.
* Loader-side fact worth its own line: `fs/read-into` copies `klen` bytes into
  the 28-page `kbuf` **before** U's `at-most klen 114688` verdict looks at the
  number — this run overran the loader's own buffer by 12,568 B and the run
  still completed. The guard is a verdict, not a gate.

## 2. Run 2 — another lineage's returning kernel (110,872 B): the loader entered it

Input `foundation-image-step-probe.KERNEL.ELF` (sha256 `e940f36e…`) — an
image-route kernel from the `aiueos-native-foundation-20261024` workspace (their
boot receipt `aiueos-kotoba-native-boot-receipt/v6` names this exact hash/size;
their `probe.kotoba` is `(defn main [] :i64 42)` and their register-observer
harness measured its return value **42**). It fits the fixture's literal windows
exactly (seg0 397 B @ file 4096 / paddr 0x101000, seg1 77,824 B @ file 32768 /
paddr 0x108000, entry == seg0 paddr — `foundation-image-step-probe.KERNEL.ELF.elf-facts.txt`),
so this run is the one that reaches the jump:

```
exit=0 debugcon="KHSCNAbcdefPWghvonkrxTUMXZ"
entry="0000000000101000" verdicts="0 2 5 24 23 41" esp="0 0 3 0 0 0"
map="0 5520 48" boot="1 1 0 110872 110872 1052672 1081344 1052672 1081344"
```

* `tfacts=1 uflags=1` (T and U marks written), M, X (ExitBootServices EFI_SUCCESS),
  Z all present — `bootall = 4`, so `kernel-jump-to kentry image-handle` executed.
  `B` is absent because `B` is written by the **fixture's** entry, not this kernel's.
* The run ended with **QEMU exit 0** — neither the fixture's exit protocol
  (`out 0xf4, 21` → 43) nor the loader's fallback (33). Consistent with this
  kernel's `main` returning 42 and `ret` finding no return address (the jump
  pushes none — `boot-fixture.kotoba`'s own comment says a returning `main`
  "would leave through `ret` with no return address instead") → a fault/reset
  under `-no-reboot`. The exact fault was **not** captured (no register observer
  on this side) — recorded, not rounded up.
* **What the entry receives, by source line:** `loader-probe.kotoba:399`
  `(kernel-jump-to kentry image-handle)` — the kernel enters at `e_entry` with
  the **EFI image handle** in the jump's argument register. There is no
  boot-info builder: `os/aiueos/uefi/main.c:179` defines
  `typedef void(SYSVABI *kernel_entry)(const struct aiueos_boot_info *)` and
  hands **boot-info v5** (GOP mode/framebuffer, initramfs, ACPI RSDP, GGUF
  handoff) in RDI. The Kotoba loader's kernel gets the handle instead, and no
  return path. A kernel under this loader must take the machine and end the run
  itself (`out 0xf4, 21`) to leave measurable evidence.

## 3. The entry contract as measured

| element | green fixture (`e7ee95b9…`) | run 1 desktop repro (`0a6fef42…`) | run 2 returning kernel (`e940f36e…`) |
|---|---|---|---|
| disk admit (ADR-0180) | pass | **pass (x, reason 0)** | pass (x, reason 0) |
| T/U fixture literals | pass | **refused, 3 clauses** | pass |
| jump | yes | no (named fallback 33) | **yes** |
| at entry | writes B, `out 0xf4,21` → 43 | — | `main` returns → QEMU 0 |
| handoff | image handle in RDI; no boot-info | — | same, measured outcome above |

## 4. Route A's wall is not only `memsz <= 1 MiB` — measured

Last tick stated route A's wall as the C-linked kernel's 3.9 MB BSS vs the
contract's per-segment `memsz <= 1 MiB`. Run 1 measures a **second, closer
wall**: the loader's boot stage hard-codes the fixture's placement literals
(seg0 ≤ 4,096 B at file offset 4096; seg1 ≤ 77,824 B at offset 32768; file ≤
114,688 B; entry == seg0 paddr). A kernel that passes every admit clause can be
refused entry anyway (3 clauses on this image), and the code window caps at
**4 KiB** — the desktop image's 42,368 B seg0 is 10x over. Growing the kernel
inside the contract therefore cannot proceed without the loader's windows
growing with it, which is loader-side change (route B territory, ADR-0180/
ADR-0131) unless the windows are reclassified as part of the kernel's own
build contract. Plus the handoff decision (boot-info v5 builder at the jump vs
a kernel contract that needs none).

## Boundary (say this, do not round it up)

* The two input kernels are earlier artifacts, built by other runs/lineages
  (`build/aiueos-native-desktop-20261017-repro/` in the shared aiueos checkout;
  the `foundation` kernel from `workspaces/codex/aiueos-native-foundation-20261024/`,
  retained **untracked** beside this evidence). Both were byte-measured here
  (`*.elf-facts.txt`); nothing about how they were built is claimed.
* Run 2's exit 0 is "consistent with a returning kernel faulting after the
  jump", not a captured fault: the machine stopped after Z with no kernel- or
  loader-side exit. The jump's arrival is established by `bootall=4` reaching
  `kernel-jump-to` as the only branch that leaves without `out 0xf4`.
* The previous swap run's unattributed exit 0 is narrower now: with a 127,256 B
  file the same loader completes the map-refresh/ExitBootServices sequence and
  names its exit (run 1, exit 33; run 2 shows the same tail works), so that
  run's stop lies inside the map-refresh region after its M mark. Still
  unattributed (fuel spent on the 762,504-byte read is the leading candidate).
* Cross-lineage context, not claimed: their loader (receipt v6, boot_bytes
  129,024) builds a boot-info with GOP framebuffer offsets and their harness
  observes kernel registers. Ours does neither; adopting either is a decision,
  not a tick's patch.
* JUN-31 acceptance criteria remain **NOT MET** (C-free build open = JUN-64).
  OCI (JUN-34) remains blocked on billing approval / read-only.
