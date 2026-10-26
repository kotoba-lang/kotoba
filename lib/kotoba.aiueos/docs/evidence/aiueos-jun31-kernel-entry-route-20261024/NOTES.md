# JUN-31: where `aiueos_kernel_entry` comes from — route decision (2026-10-24)

Question this tick answered (continuing `aiueos-jun31-kotoba-loader-reachability-20261024`):
the pure-native link ends with `ld.lld: warning: cannot find entry symbol
aiueos_kernel_entry`, so before the loader's `fs`/`exit`/`kernel-jump-to` modules
can be written it must be settled **which artifact carries the boot entry, and
whether the entry-symbol gap is on the C-free boot path at all**. Measured on
branch `hermes/jun31-image-route-node-free-20261022`, amu checkout `74ca4aa6`,
host `bin/amu` route `--jvm-free` (measurement tooling only; the acceptance run
still requires the selfhost-built compiler).

## 1. The two kernel artifacts, measured side by side

**The ADR-0131 loose-object link** (`build/aiueos-pure-withloader/
aiueos-k16-pure-native-kernel.elf`, 445,992 B — `pure-link-elf-measure.txt`):

```
e_entry=0   e_phnum=3   (PT_GNU_STACK 0x6474e551 + 2 PT_LOAD)
seg0 PT_LOAD flags=5 paddr=0x100000 memsz=430751  entry_inside=False
seg1 PT_LOAD flags=6 paddr=0x16a000 memsz=7440    entry_inside=False
```

`e_entry` is literally **0**. The linker did not just warn; it left the file
with no entry point at all. `aiueos_kernel_entry` lives in `kernel/entry.S`,
which the pure-native profile excludes as foreign code (ADR-0131 says so).

**The amu kernel image route** — the artifact the loader contract is written
against. Fresh build this tick (`image-build.log`, `image-elf-measure.txt`):

```
amu compile examples/i64-semantics.kotoba --target x86_64-aiueos-kernel-v1
    --artifact image --jvm-free --fuel 32768
TESTKERN.ELF 110,872 B  sha256 a3315fec041b096878dde05ff4b416ddc52c4469e62b38f3514cfcdf01607a06
e_entry=1052672 (0x101000)  e_phnum=2
seg0 PT_LOAD flags=5 paddr=0x101000 filesz=memsz=208    entry_inside=True
seg1 PT_LOAD flags=6 paddr=0x108000 filesz=memsz=77824
```

Every clause of `aiueos.uefi.elf`'s admission (ADR-0180: two PT_LOAD,
`filesz == memsz`, `paddr` at or above 1 MiB and page-aligned, `memsz` at most
1 MiB, `paddr+memsz` under 1 GiB, entry inside segment 0) passes on this image,
**and the entry is set**.

Three independent records already name this entry `aiueos_kernel_entry`:
`contracts/value-runtime-kernel-image-v1.edn` (`:entry :aiueos_kernel_entry`),
`verify-kotoba-native-kernel.py` (`"entry": "aiueos_kernel_entry"`, pinning
`e_entry == 0x101000` for `KERNEL.ELF`), and the loader smoke itself, which
prints `entry="0000000000101000"` from the fixture (previous tick's
`smoke-qemu-uefi-loader-canonical.log`).

## 2. The kernel OBJECT route cannot supply the symbol — measured

`kernel/entry.S` cannot be replaced by "a Kotoba object that exports
`aiueos_kernel_entry`" under the current codegen (`object-probes.log`):

| probe | result |
|---|---|
| export `[aiueos_kernel_entry]`, no `main` | exit 65 `entryless libraries currently require…` (the target's declared entry must exist) |
| export `[aiueos_kernel_entry]` + `main` present | exit 65 `main entrypoint must be exported` |
| export `[main]`, `main` is the entry | exit 0, 864 B ET_REL — but `nm` shows the public symbol is **`kotoba_aiueos_probe`** (local `kotoba_source_entry`) |

The kernel profile's one public symbol is canonical (amu README: "writes a
linkable ELF64 object exporting `kotoba_aiueos_probe`"), whatever the source
exports. So under amu `74ca4aa6` no kernel object can be named
`aiueos_kernel_entry`, and closing the **loose-link** gap needs a codegen/profile
change (name the public symbol) or a `linker.ld` `ENTRY` realignment — i.e.
JUN-102's compiler-emitted substrate work, not boot-path work.

## 3. Decision

**The C-free boot path does not load the ld.lld loose-object link, and its
jump target is contractually available today.** The K16 boot route
(`build-k16-pure-native.cljk --compiler` → `build-kotoba-native-boot.sh`) embeds
the image-route `KERNEL.ELF` via `amu package-aiueos-boot`; the loader admits
exactly what that packager emits and reads the entry from `e_entry`
(0x101000 = `aiueos_kernel_entry`). The `cannot find entry symbol` warning is a
property of the ADR-0131 gate artifact only; it is honest there (the profile
still does not boot from that link) and it is **not** the JUN-31 boot blocker.

The JUN-31 critical path therefore stays what the previous tick named it — the
loader's three missing modules — and the entry question is closed:

* `fs` (read the kernel from the ESP): **startable now.** ADR-0180 blocked
  `memory`/`fs`/`exit` on "cannot PLACE a kernel image" (an `AllocatePages`
  base arrives through a load and region provenance refused it).
  `kotoba/aiueos/uefi/memory.kotoba` has since closed exactly that primitive —
  `kernel-uefi-alloc-region` makes the allocation itself the provenance root
  (kotoba-gmir ADR-0030 / kotoba-sema ADR-0030), so a checked `kernel-store-*`
  write can place loaded segments. The decision half (where pages may land,
  window bounds) is implemented and exported.
* `exit` (GetMemoryMap + ExitBootServices): startable on the same primitive
  (out-pointer buffer = allocated region / `kernel-scratch-region`).
* `kernel-jump-to`: its target is `e_entry` of the admitted image — measured
  present (§1). ADR-0180's "it cannot go there, because it cannot load the
  kernel first" is now only about `fs`, not about the entry.

JUN-31 item 2 (a bootable kernel with no C in the acceptance path) remains
NOT MET: nothing boots yet. What changed this tick is the map of what is left:
the entry-symbol wall is off the critical path, and `fs` is unblocked.

## Files

| file | what |
|---|---|
| `image-build.log` | fresh `--artifact image` build, oracle `:verified`, 110,872 B |
| `image-elf-measure.txt` | ELF header/segments of TESTKERN.ELF + every loader admission clause |
| `pure-link-elf-measure.txt` | same measurement on the ADR-0131 loose-link artifact (e_entry=0) |
| `object-probes.log` | the three kernel-OBJECT probes and `nm` of the admitted one |
| `TESTKERN.ELF.provenance.edn` / `.publication.edn` | amu's own provenance for the image |
