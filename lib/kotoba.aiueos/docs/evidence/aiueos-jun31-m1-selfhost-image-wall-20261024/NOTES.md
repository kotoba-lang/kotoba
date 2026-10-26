# JUN-31 M1: the selfhost-built window-fitting kernel — first failed element measured, and the image contract pinned to its emitter (2026-10-24)

Question this tick answered (continuing `aiueos-jun31-window-classification-20261024` §4
M1): can the C-free selfhost compiler (`S-x86_64.elf`, the loaderless fixed
point) produce the window-fitting kernel image whose boot proof already exists,
and if not, what exactly is missing?

Answer: **not yet — two measured walls, both inside the selfhost seed closure.**
No bytes were booted for this note. M1's receipt requirement
("compiler/kernel/packaging routes + hashes") cannot be honestly assembled
until the packaging route exists on the selfhost side; recording the wall, the
reference layout, and the implementation spec is this tick's forward motion.

## 0. The reference is exactly reproducible (control)

`os/aiueos/uefi/boot-fixture.kotoba` (source `018a939c…`) rebuilt through the
shim-pinned `bin/amu` image route reproduces the boot-proven KERNEL.ELF
**byte-identically**: `e7ee95b9f8992b679af7dc10ba14eb0460ead81b508be05fdb6feb43b9b72212`,
110,872 B (`selfhost-route-attempts.log` §0). So M1's target artifact and its
boot behaviour (T/U pass → `kernel-jump-to` → kernel-owned exit 43,
`aiueos-jun31-boot-jump-qemu43-20261024`) are pinned; what is missing is a
**selfhost packaging route** that reaches the same bytes (or an equally
window-fitting image).

## 1. W1 — the selfhost compiler refuses the IMAGE route (measured)

`S-x86_64.elf` (`f74fd09b…`, the fixed point's x86_64 static compiler:
`selfhost-bootstrap.py`, S1=S2=S3=root `8256bfd8…`, `rootReproduces: true`)
answers the image request with its driver's grammar:

```
$ S-x86_64.elf compile boot-fixture.kotoba --target x86_64-aiueos-kernel-v1 \
      --artifact image --fuel 32768 --output KERNEL.selfhost.elf
exit 2
seed-x86_64-aiueos-object: E7100 expected compile SOURCE --target x86_64-aiueos-kernel-v1 --output NEW_OBJ [--fuel POSITIVE_BUDGET]
```

The kernel-v1 route in the selfhost closure is the **object** ABI only
(`selfhost-unity.kotoba:13574` carries `kotoba.native.elf64's
package-kernel-object shape`; no image packager). This matches JUN-30's
recorded split ("slice-1 landed = object route; **slice-2 = kernel IMAGE route
/ allowlist / tier**" and `seed/74`'s own note "not the kernel IMAGE route
(boot shim, ISR region, sealed fuel)"). M1 as defined needs slice-2.

## 2. W2 — the fixture's boot-evidence ops are unexpressible in the object route (measured)

The object route's own export profile does not save the fixture: the same body
under `(:export [kotoba_aiueos_…])` is refused at the same head —

```
boot-fixture.kotoba      at 1120 -> E2101   (offset = the head `(kernel-out-u8 233 66)`)
boot-fixture-obj.kotoba  at  303 -> E2101   (same head)
```

E2101 is the seed's "head not in the library" refusal. `kernel-out-u8` /
`kernel-out-u32` — the contract's `:boot` evidence operations
(`contracts/value-runtime-kernel-image-v1.edn`) — are emitted only by
kotoba-native's native backend (`src/kotoba/native/x86_64.cljk:2058`
`emit-kernel-out`; `machine_ir.cljk:826`), i.e. the `bin/amu` route. A kernel
that must answer the debug console cannot even be *expressed* through the seed
route today, let alone packaged.

## 3. The image contract, pinned to its emitter (closes window-classification §1)

`KERNEL.ref-image.elf` facts (`elf-facts-ref-image.txt`, all fixture clauses
pass):

```
e_type=2 ET_EXEC  e_machine=62  e_entry=0x101000  e_phnum=2
ph[0] PT_LOAD RX  poff=4096   vaddr=paddr=0x101000  filesz=memsz=144
ph[1] PT_LOAD RW  poff=32768  vaddr=paddr=0x108000  filesz=memsz=77824
tail 280 B = pad + 4 section headers at e_shoff=110616
```

The layout rule observed across three artifacts
(`max(32768, page-align(4096 + seg0size))`, fixed 77,824 B seg1) is now located
in `kotoba-native/src/kotoba/native/elf64.cljc.cljk` `package-kernel`
(1091-1182): `image-base 0x100000` (:20) + `text-offset` 4096 (:21) → entry
0x101000; seg0 = `entry-shim` (77 B non-live, :1116) + code (144-77 = 67 B);
`kernel-data-offset-for` (:60-62) = `max minimum-kernel-data-offset,
page-align(text-offset + text-size)` → seg1 offset; `kernel-runtime-data-size`
(:52) = stack offset + stack bytes → the fixed 77,824 B context / sealed-fuel
region; headers/sections assembled :1146-1161.

## 4. Slice-2 scope for M1 (what enters the selfhost seed closure)

1. **boot ops**: `kernel-out-u8` / `kernel-out-u32` in the seed x86 emitter
   (reference: kotoba-native `x86_64.cljk:2058` `emit-kernel-out` —
   `out dx, al` / `out dx, eax`).
2. **image packager**: the non-live path of `elf64/package-kernel` — entry
   shim (77 B) + code + optional ISR region + `kernel-runtime-data` (77,824 B
   context with sealed fuel) + ELF header/phdrs/shdrs at the §3 layout.
   (`package-kernel-object`'s shape is already in the closure; this is its
   sibling.)
3. **requalification**: fixed-point rebuild (S1=S2=S3 + `rootReproduces`) and
   the amu qualification gates, because the closure change moves the pinned
   root. Then compile `boot-fixture.kotoba` on the new seed route, stage the
   image in the loader smoke (`AIUEOS_SWAP_KERNEL`), and take the T/U marks,
   `kernel-jump-to`, exit-43 boot proof with the three-route receipts.

## Boundary (say this, do not round it up)

* **Nothing new was booted this tick.** The exit-43 boot proof on record is the
  `bin/amu`-packaged fixture (nbb route); M1's point is to reproduce that boot
  with the **selfhost** compiler and packaging, and that packaging does not
  exist yet (W1). The 841 B probe object the fixed point emits
  (`aiueos-jun31-acceptance-chain-20261024`) has still not run in a kernel —
  M1 is exactly what closes that, and it remains open.
* W1's `--artifact image` refusal is a **grammar** refusal (E7100 names the
  expected command line); it is not a claim that the closure could package if
  asked differently — the closure demonstrably carries only the object
  packager (§1).
* W2's E2101 offsets point at the `(kernel-out-u8 …)` head in both files
  (byte-exact, recorded in the attempts log). The `:i64 42` probe profile is
  expressible (the four measured probe objects); what is missing is the boot
  op specifically.
* The reference image's provenance (`ref-image.provenance.edn`) binds builder
  `kotoba-compiler/v1`, target `:x86_64-aiueos-kernel-v1`, output
  `:kotoba.kexe/v1` — the sealed artifact whose container is the 110,872 B
  image. The seed route emits no kexe; slice-2 must decide whether it packages
  a sealed artifact or a raw object (the loader's admit reads only the ELF
  headers, so either satisfies the contract; the receipts differ).
