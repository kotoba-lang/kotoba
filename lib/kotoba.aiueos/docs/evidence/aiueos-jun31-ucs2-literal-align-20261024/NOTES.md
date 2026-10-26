# JUN-31: the UCS-2 literal pool landed ODD in the PE32+ image — the entry shim, not the layout pass (2026-10-24)

Question this tick answered (continuing `aiueos-jun31-kotoba-loader-reachability-20261024`):
where does the observed odd placement of the loader's UCS-2 literals come from,
and does fixing it keep the fs-stage smoke green.

## 1. Measured before: every UCS-2 literal in BOOTX64.EFI started ODD

Built with the pinned lineage (`amu` 74ca4aa6, JUN-29 seed runner, host
`bin/amu` nbb route `--jvm-free`), `loader-probe.kotoba` + the fs stage at
`--fuel 200000000`:

```
BOOTX64.EFI 46,080 bytes  sha256 73b9809cb4ed86dfb99401cb40fd3d2cf26193fdded5f448d716b015fc6b0131
PE32+ machine 0x8664, 3 sections, entry_rva 0x1000,
SectionAlignment 0x1000, FileAlignment 0x200
.text raw 0x200, virtual-size 27,707
```

UTF-16LE literal starts in `.text` (section-relative file offsets):

| literal | offset | mod 8 | mod 2 |
|---|---|---|---|
| `\EFI\AIUEOS\KERNEL.ELF` | 26,299 | 3 | 1 |
| `AIUEOS KOTOBA LOADER\r\n` | 26,387 | 3 | 1 |
| `\r\nentry ` | 26,435 | 3 | 1 |
| `\r\nverdict` | 26,627 | 3 | 1 |
| `\r\n` / `window` | 27,531 / 27,539 | 3 | 1 |
| `\r\ndigest` | 27,555 | 3 | 1 |
| `\EFI\AIUEOS\MISSING.ELF` | 27,643 | 3 | 1 |
| `\r\nesp` | 27,691 | 3 | 1 |

Every entry ≡ 3 (mod 8) — the entries are 8-aligned **relative to each other**
(pool spacing multiples of 8) but the pool BASE is shifted by 3. UCS-2 needs
2-alignment and even that is violated: a CHAR16 at an odd address.

## 2. Root cause: the PE32+ entry shim, not the layout pass

Both layout resolvers are aligned and were ruled out last tick
(`kotoba.native.machine-ir/resolve-program-layout` aligns every pool entry to
`kotoba.gmir/rodata-alignment` = 8 **relative to the code buffer's start**;
selfhost `seed/42-layout.kotoba` likewise). The break is one layer up, in
`amu/src/kotoba/compiler/packaging/pe32plus.cljk` `package-efi`:

```clojure
shim (entry-shim (:arity export) source-rva data-rva)   ;; 21 bytes (0-arity) / 35 bytes (2-arity)
text (into shim (:code artifact))                        ;; buffer shifted by shim-size
```

The loader probe's `efi-main` is two-arity, so the shim is **35 bytes ≡ 3
(mod 8)**. The artifact's pool is 8-aligned inside `(:code artifact)`; prepending
35 bytes moves the whole buffer to base ≡ 3, and every literal inherits it —
exactly the measured mod 8 = 3. The `lea r9,[rip+disp32]` references stay
correct (RIP-relative is shift-invariant), which is why the loader **worked**
on unaligned x86 while violating the pool's own contract ("an entry's alignment
is a property of the image", machine_ir.cljk) — and why the earlier probes
never failed functionally.

## 3. Fix: pad the shim to a multiple of 8 (amu, one file)

`amu` branch `hermes/jun31-pe-shim-align` (PR), patch applied identically on
`origin/main` 20d79279 and the JUN-31 pin 74ca4aa6 (`pe32plus.cljk` is
byte-identical between them; measurement run on the pin lineage):

- `shim-pad = (align shim-size 8) - shim-size` (21→24, 35→40),
- shim bytes + `shim-pad` INT3 (`0xCC`, never executed — the shim CALLs the
  source entry and returns past them),
- `source-rva` / `text-size` computed from `shim-total`,
- the size-agreement check declares `shim-total`.

## 4. Measured after: every literal 8-aligned

```
BOOTX64.EFI 46,080 bytes  sha256 7ec670716b668cc249491aef1b956301699e3031aaf81764faf1633c492c1f65
.text virtual-size 27,712 (= 27,707 + 5 pad)
first 40 bytes: 35-byte two-arity shim + cc cc cc cc cc, then the artifact code
```

| literal | offset | mod 8 |
|---|---|---|
| `\EFI\AIUEOS\KERNEL.ELF` | 26,304 | 0 |
| `\r\nentry ` | 26,440 | 0 |
| `window` | 27,544 | 0 |
| `\EFI\AIUEOS\MISSING.ELF` | 27,648 | 0 |
| `\r\nesp` | 27,696 | 0 |

## 5. Smoke green, full fs stage, with the discrimination budget

`kbb --backend sci os/aiueos/scripts/smoke-qemu-uefi-loader.cljk <amu pin worktree
with the patch>`, fuel 200,000,000 (the flag's comment in the smoke is this
tick's commit):

```
BOOTX64.EFI 46080 bytes KERNEL.ELF 110872 bytes
exit=33 debugcon="KHSCNAbcdefPWghvonkrxZ"
entry="0000000000101000" verdicts="0 2 5 24 23 41" esp="0 0 3 0 0 0"
AIUEOS_UEFI_LOADER_OK markers=KHSCNAbcdefPWghvonkrxZ verdicts=0,2,5,24,23,41
  entry=0000000000101000 esp=0,0,3,0,0,0
```

All nineteen markers reached (the fs stage's `v o n k r x` included — the first
open-read the 8M budget died inside now completes), the six elf verdicts and
the six esp reasons each answer their own number, and the fixture kernel's
e_entry is read out of the literal pool as 0x101000.

## Boundary (say this, do not round it up)

* The alignment defect was **spec/contract** (and portability: an odd CHAR16
  faults on strict-alignment consumers), not an x86 functional failure — the
  pre-fix loader read its strings correctly.
* Boot is still NOT reached (JUN-31 stays In Progress): the loader decides and
  reports; `exit` / `kernel-jump-to` are still missing per ADR-0180's list.
* The 200M budget is a discrimination budget, not a floor: the run proves the
  stop is no longer fuel.
* The rebuilt BOOTX64.EFI bytes necessarily differ from every previously pinned
  loader image (the shim pad is in `.text`); old goldens of this artifact shift.
