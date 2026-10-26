# JUN-31: can the boot stage's kernel be swapped to the real kernel (kernel object route)? Measured judgment + the C-free re-measurement path (2026-10-24)

Question this tick answered (continuing `aiueos-jun31-boot-jump-qemu43-20261024`):
with the loader-driven jump proven on the boot fixture, does the boot path admit
and run the **real** kernel — the kernel object route KERNEL.ELF of the
acceptance chain (`build/aiueos-j/esp/EFI/AIUEOS/KERNEL.ELF`, 762,504 B, sha256
`e21a79e5…`, the artifact whose kotoba probe body was byte-proven contained at
offset 206912) — and if not, which element refuses it first.

## 1. The swap run: same loader bytes, only KERNEL.ELF changed

`swap-probe.cljk` (committed here) is `smoke-qemu-uefi-loader.cljk` with one
variable changed: stage a GIVEN kernel at `\EFI\AIUEOS\KERNEL.ELF` instead of
compiling `boot-fixture.kotoba`. Loader source, amu (`jun31-pe-shim-pin-20261024`,
`--jvm-free`, fuel 200,000,000) and QEMU/OVMF are the committed smoke's. The
resulting BOOTX64.EFI is **byte-identical to the boot-jump run's**
(50,688 B, sha256 `bc0696e1…`), so the comparison against that run's green
result is single-variable: the kernel file.

```
exit=0 debugcon="KHSCNAbcdefPWghvonkrM"
esp  "0 0 3 0 0 7"
boot "0 0 0 762504 762504 1048576 1728512 1048576 1728512"
map  "0 5472 48"
```

**First failing element, measured: the fs stage's admission of the DISK bytes
refuses the kernel object route image with reason 7** (`esp` 6th word = 7). In
`aiueos.uefi.elf/admit` reason 7 is the `phnum == 2` clause: this KERNEL.ELF
carries `e_phnum=6` (5 PT_LOAD + PT_GNU_STACK). Everything before it answered:
device 0, volume 0, the MISSING file's open refused with its own reason 3, the
kernel file opened, and the **whole 762,504-byte file was read**
(`boot` words kstat=0, kgot=klen=762504) — the file is well inside the 1 MiB
`KERNEL_BUFFER_SIZE`, but its headers are not in the loader's contract.

## 2. What did run: the placement machinery accepts this kernel's first two segments

The boot stage ran on regardless of `x` and answered:

* `boot` s0/s1 = 0x100000 / 0x1A6000 — `AllocatePages(AllocateAddress)` answered
  the real kernel's own `p_paddr` for ph[0]/ph[1] (compare the ELF facts file),
  and c0/c1 = s0/s1 (`CopyMem` returns Destination, last tick's fix).
* `tfacts=0 uflags=0`: T/U bind to the probe's **frozen 176-byte fixture
  literal** (the i64-semantics header's placement facts). A swapped kernel
  cannot satisfy them by construction; that is a fixture-contract refusal, not a
  machine-level one — c0==s0 and c1==s1 held.
* `map 0 5472 48` (M mark present). **X, Z, B are absent and neither the
  kernel's exit (43) nor the loader's fallback exit (33) was observed — QEMU
  exited 0**, and the fallback's `xstat` diagnostic line is absent from the
  serial log. Not attributed this tick (candidates: runtime fuel exhaustion
  between M and the X mark on the larger file, or a return into the firmware
  after a successful ExitBootServices). Recorded, not rounded up.

## 3. Static clauses: even past `phnum`, the contract refuses this image

Byte-level parse of the same artifact (`KERNEL.ELF.elf-facts.txt`):

| clause | ph evidence | verdict |
|---|---|---|
| `phnum == 2` | 6 program headers | **refused, reason 7 (the measured one)** |
| `filesz == memsz` | ph[2] 7,672/154,304; ph[4] 4,096/3,923,968 (BSS) | refused, segment-reason 3 |
| `memsz <= 1 MiB` | ph[4] 3,923,968 | refused, segment-reason 5 |
| `paddr >= 1 MiB`, page-aligned | all | pass |
| `paddr+memsz < 1 GiB` | all | pass |
| entry inside segment 0 | 0x100000 in ph[0] | pass |

Also measured: `admit` examines **only the first two program headers** (r0/r1 at
phoff, phoff+56) — relaxing `phnum` alone would silently skip ph[2..4]. The
image's BSS needs a zero-fill the loader has no stage for.

## 4. Handoff: the entry contract differs too

`os/aiueos/uefi/main.c:179`: `typedef void(SYSVABI *kernel_entry)(const struct
aiueos_boot_info *)` — the C loader hands a `aiueos_boot_info` (v5: GOP
mode/framebuffer, initramfs, ACPI RSDP, GGUF model handoff) in RDI. The Kotoba
loader's `kernel-jump-to` jumps with `(kentry image-handle)` and builds no
boot-info. Even a successfully admitted kernel object route image would enter
without its handoff.

## 5. Judgment

**The swap is not possible as-is.** Refusal order, measured: ①`admit` reason 7
(phnum≠2) on the disk bytes; then by inspection ②segment-reason 3 (BSS) and 5
(3.9 MB memsz); ③T/U fixture-literal marks; ④the boot-info v5 handoff is
absent. Two routes to close it — pick one, they are not equivalent:

* **A. Grow the boot-path kernel inside the image-route contract** (preferred:
  no loader contract change): `amu --target x86_64-aiueos-kernel-v1 --artifact
  image` emits 2-PT_LOAD / filesz==memsz / ≤1 MiB images by construction —
  measured passing all clauses on `build/aiueos-native/KERNEL.ELF` (254,232 B)
  and `build/aiueos-native-desktop-20261017-repro/KERNEL.ELF` (127,256 B), both
  `e_entry=0x101000`. The wall for the FULL kernel is the contract's `memsz <=
  1 MiB` per segment vs. the C-linked kernel's 3.9 MB BSS, i.e. the C-free
  kernel (§6) must fit the contract rather than the contract bending.
* **B. Extend the loader** (admit: N PT_LOAD + BSS zero-fill + the >1 MiB
  segments; boot stage: place N segments; a boot-info v5 builder at the jump).
  This is a loader-contract change (ADR-0180/ADR-0131 territory) and needs its
  own decision, not a tick's patch.

## 6. C-free acceptance build (zero zig cc): the re-measurement path

The acceptance chain's open item (JUN-64): `kernel/*.c` is still compiled by
zig cc — 34 units / 27,818 C lines in the accepted build (25 units / 22,359
lines default route + 9 profile-gated / 5,542; `aiueos-jun31-c-surface*-20261024`).
Re-measurement path, in order:

1. **Gate the toolchain, not the claim**: the accepted build's build log must
   contain **zero `zig cc` invocations**, and the output tree zero
   `*.c/*.S/*.o/*.a/*.so` (the loader smoke already enforces exactly this floor
   on its own output — lift it to the whole image build).
2. **Replacement unit is the kotoba object** — `AIUEOS_KOTOBA_KERNEL_OBJECT` is
   measured working for one object (kernel-probe-abi.o, 841 B, byte-identical to
   pin). Each of the 34 C units needs a kotoba/amu object counterpart; profile
   -gated units only move in the guest-browser profile, so measure default and
   profile separately (the existing split stays the inventory).
3. **`kernel/entry.S` / `qualification_entry.S` are foreign too** (ADR-0131
   excludes entry.S; the pure-native loose link measured `e_entry=0` without it).
   The C-free build needs the `aiueos_kernel_entry` symbol from a kotoba/amu
   object, and the boot-info v5 builder from §4/§5-A.
4. **Re-run the chain end to end and count**: compiler rebuild (G1=G2=G3) →
   kernel object(s) → image (zero zig cc) → QEMU boot markers → desktop input
   markers. The chain receipts already record `compilerRoute`/`kernelObjectRoute`/
   `packagingRoute`; add a `cFreeRoute` block with the zig-cc invocation count
   (0) and the C-line count (0) as its own measured fields.

## Boundary (say this, do not round it up)

* The swap kernel here is the acceptance-chain artifact `e21a79e5…` (built
  2026-10-24 08:35 from the rebuilt compiler's fresh probe object). A newer
  844,424 B kernel object route image exists in another session's scratch; it
  was not measured and is not claimed.
* The two contract-passing kernels in §5-A are kotoba-native image-route
  artifacts of earlier desktop runs (2026-10-16/17); only their ELF facts were
  measured here — they were not booted through the Kotoba loader this tick.
* `exit=0` / missing X mark and `xstat` line (§2) is unattributed; the run was
  wall-bounded at 180 s and QEMU exited on its own.
* JUN-31 acceptance criteria remain NOT MET (C-free build open, JUN-64); this
  tick measured a refusal, not a pass. OCI (JUN-34) remains blocked/read-only.
