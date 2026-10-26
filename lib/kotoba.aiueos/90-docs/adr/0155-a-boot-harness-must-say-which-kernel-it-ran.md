# ADR-0155: A boot harness must say which kernel it ran

## Status

Accepted (2026-09-02)

## Context

Every acceptance claim the K16 programme has made is a string read off a serial
log. `TLS-PARITY ok` (ADR-0134). `DEVCLIENT-PARITY canonical ok`. `NIC-PARITY ok
rtl8125 identify link-up ring-build program tx-submit rx-poll` (ADR-0140).
`DISRP`. `AIUEOS_DOT_F32_QEMU_OK both-arms-executed and-agree-with-kotoba-kir`
(ADR-0138). `AIUEOS_QWEN35_ADMISSION_OK tensors=866` (ADR-0136). `KHSTCUGLWOZ`.
Each of them was produced by `os/aiueos/scripts/smoke-qemu-*`, which builds an
image and then boots it.

Nothing connected the two halves. The build wrote into `build/aiueos`; the boot
opened `build/aiueos/esp`; and no step compared what came out of the first with
what went into the second. A harness in that shape answers the same way whether
it measured the tree in front of you or a kernel from three commits ago -- root
AGENTS.md's recurring failure, "a check that could not run returns the same
value as a check that ran and found nothing wrong."

Two measurements on `c9f7506`, both reproduced before anything was changed:

**A harness that boots without building passes on a stale image.**
`smoke-qemu-firmware-matrix.sh` checked that `$esp` is a DIRECTORY and booted
it. Editing `kernel/main.c` so that the string
`AIUEOS_PCI_OK bounded-scan virtio-vendor=1af4` no longer appears anywhere in
the tree, and then running the script unchanged, gave:

```
firmware dir: /opt/homebrew/share/qemu
RUN     default-nonvram exit=97 evidence-lines=98 distinct-markers=85
RUN     default-nvram exit=97 evidence-lines=98 distinct-markers=85
RUN     secure-nvram exit=97 evidence-lines=98 distinct-markers=85
MATCH   default-nonvram == default-nvram
MATCH   default-nonvram == secure-nvram
AIUEOS_FIRMWARE_MATRIX_OK configurations=3 byte-identical-evidence-lines
EXIT=0
```

A full pass, three configurations deep, over a kernel that is not in the tree,
still printing a marker the tree no longer contains. The comparison it makes --
that three firmware builds produce byte-identical evidence -- was true. It was
just true of the wrong kernel.

**A failed build leaves the previous run's evidence in place.** With
`build-uefi.sh` carrying conflict markers (the state aiueos `main` was actually
in earlier the same day, `sh -n` exit 2 at line 151), `smoke-qemu-uefi.sh` did
stop: `set -eu` caught the non-zero exit. But it stopped after printing one line
of bash's stderr and nothing else, and it left behind
`build/aiueos/esp/EFI/AIUEOS/KERNEL.ELF` from the previous run *and*
`build/aiueos/kernel-serial.log` with that kernel's `NIC-PARITY ok`,
`DEVCLIENT-PARITY canonical ok` and `AIUEOS_TLS13_RECORD_OK` still in it. Every
stream in this programme collects its evidence by grepping that file. The
harness's refusal and the harness's evidence pointed in opposite directions, and
only the refusal was on stderr.

So the reported defect was half right and the half that was wrong matters. The
exit status of `build-uefi.sh` **was** checked. What was never checked was
whether the bytes QEMU opened were the bytes that build produced -- and for the
harnesses that do not build at all, nothing was checked but existence.

## Decision

**A harness that boots an image must refuse to boot one it cannot attribute.**

`os/aiueos/scripts/image-freshness.cljk` is the attribution. The builder runs
`record` immediately after producing the artifacts; the boot harness runs
`assert` immediately before QEMU. The receipt carries two things, and both are
compared:

1. **the artifacts** -- sha256 and size of `BOOTX64.EFI`, `KERNEL.ELF`,
   `INITRD.IMG`. This is what catches a build that reports success and hands
   back a cached image.
2. **the tree they were built from** -- the commit, a digest of the `os/aiueos`
   index, and the working-tree bytes of everything git reports as changed or
   untracked under that scope. This is what catches the firmware-matrix case: an
   artifact can be byte-identical to its receipt and still be stale, because the
   receipt was written before the edit.

The second input is why `git ls-files -s` alone is not enough: that reports the
INDEX, so a modified-but-unstaged `kernel/main.c` would hash identically to the
file the image was built from.

**Three outcomes, and they are distinguishable from the exit status alone.**
The same three codes everywhere in the harness:

| code | meaning |
|---|---|
| 0 | fresh, and every assertion in the harness held |
| 1 | a real boot failure -- named, with the marker that was missing |
| 3 | `COULD-NOT-RUN` -- build failed, or no qemu / no OVMF / no nbb / no receipt |
| 4 | `REFUSED stale-image` -- the artifact or the tree moved |

Exit 3 is the one this ADR is really about. Before it, `smoke-qemu-uefi.sh`
returned 1 for "OVMF firmware not found" and 1 for "the write-protect
page-fault marker was not observed", and `smoke-qemu-dot-f32.cljs` returned 1
for "the compiler failed" and 1 for "the AVX2 arm computed a different dot
product". Those are not the same answer.

**Deleting first is half of it, and only half.** `smoke-qemu-uefi.sh` now
removes the three artifacts, the receipt and both logs BEFORE the build, so a
build that fails cannot leave evidence that reads as clean. That closes the
serial-log residue. It does not close a build that succeeds and writes the wrong
bytes, which is what the sha256 comparison is for.

**`nbb` absent is `COULD-NOT-RUN`, not a skip.** A build that quietly shipped no
receipt would put every downstream assert into could-not-run, which is the state
this file exists to make impossible. `build-uefi.sh` refuses without it.

**The remaining harnesses are written down, not forgotten.**
`os/aiueos/scripts/verify-smoke-freshness.cljk` classifies all 42
`smoke-qemu-*` scripts. 30 boot an image: 15 are attested (4 assert directly, 11
inherit it by delegating to `smoke-qemu-uefi.sh`), and 15 are not. Those 15 are
recorded in `os/aiueos/contracts/smoke-freshness-baseline.edn`, the gate refuses
when the set GROWS, and it refuses when a baseline entry stops booting or stops
existing. A new harness that boots an image without a freshness assert goes red
on the commit that adds it.

A comment that merely mentions `smoke-qemu-uefi.sh` does not count as
delegation. Counting one would be this ADR's own defect in miniature: a harness
that talks about the attested path recorded as taking it.

## Consequences

- `NIC-PARITY ok` and its siblings now mean "this tree", for every harness that
  runs through `smoke-qemu-uefi.sh`. They did not before.
- A stale-image refusal is a distinct, greppable outcome:
  `REFUSED stale-image artifact=<path> expected=<sha> found=<sha>` or
  `REFUSED stale-image tree=os/aiueos expected=<digest> found=<digest>`.
- Boot-only harnesses now require a rebuild after any edit under `os/aiueos`.
  That is the intended cost. Booting a pre-built image after editing the source
  is the defect, not a workflow.
- The deliberate-corruption paths (`AIUEOS_CORRUPT_KERNEL`,
  `AIUEOS_CORRUPT_INITRAMFS`, ...) still work: the freshness assert runs BEFORE
  them, so what they damage is a demonstrably fresh image.

## What this does NOT do

- **`AIUEOS_CDROM_IMAGE` / `AIUEOS_DISK_IMAGE` are unattested.** When those are
  set, `smoke-qemu-uefi.sh` boots a release medium instead of the ESP. The ESP
  is still built and asserted, but the medium that actually boots has no receipt
  of its own. `build-release-image.sh` should record one.
- **15 of the 30 image-booting harnesses are still unattested**, listed in the
  baseline. Most build media this workstation cannot exercise (PXE, USB, GRUB,
  multiboot).
- **The tree digest is scoped to `os/aiueos`.** A change to the compiler pin in
  `deps.edn`, or to a `kotoba-*` dependency, does not move it. The committed
  `.o` files under `os/aiueos/kotoba` DO move it, and those are what the image
  links -- but the toolchain that produced them is outside the scope.
- **It says nothing about whether the object was rebuilt.** `build-uefi.sh`
  links committed `.o` files; a `.kotoba` source edited without recompiling its
  object changes the tree digest (so a boot-only harness refuses) but a
  build-then-boot harness will happily link the old object. `verify-kotoba-
  kernel-object.py`'s sha256 pins are the check for that, and several objects
  are verified with an empty pin.
