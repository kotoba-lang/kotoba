# ADR-0019 — USB removable-media boot, and the murakumo.cloud node split across two profiles

- Status: accepted
- Date: 2026-08-05
- Supersedes: nothing. Extends ADR-0013 (native OS ownership and boot) and
  ADR-0011 (PID-1 hosted profile).

## Context

The ask was a single deliverable: an aiueos built with the Kotoba native
toolchain, bootable from a USB stick, with the murakumo CLI integrated so the
node runs as an "AI mining server" — where mining means joining murakumo.cloud
and serving generation work (text, image, video, audio), not proof-of-work.

Three facts, measured rather than assumed, decide the shape of this:

1. **The release image was already a bootable GPT disk, but nothing asserted it
   was reachable the way a USB stick is reached.** `build-release-image.sh`
   emits a 64 MiB GPT raw disk with a protective MBR, a FAT32 ESP, an
   independent FAT16 recovery ESP, and an aiuefs data partition. Every gate
   attached it as a fixed drive. A physical stick goes through the firmware's
   USB stack, reports itself removable, and boots the removable-media fallback
   `\EFI\BOOT\BOOTX64.EFI` with no NVRAM entry pointing at it — none of which
   the existing gates exercised. "Produces a bootable image" and "boots from a
   stick on someone else's machine" are different claims.

2. **The bare-metal profile has no network stack at all.**
   *(Superseded 2026-08 by the ADR-0020..0087 chain, recorded here 2026-08-25,
   root ADR adr-2608251418: the bare-metal boot path now carries virtio-net,
   DHCPv4, DNS, TCP, TLS 1.3 and an HTTPS GET with CID verification, proved
   under QEMU. What this fact still gets right is physical hardware: the only
   link-layer driver is virtio-net-pci, so a real machine boots on the offline
   floor. The rest of this paragraph is the 2026-08-05 measurement.)*
   PCI enumerates
   virtio RNG, BLK, INPUT and GPU; there is no NIC driver, no TCP/IP, no
   sockets. `src/aiueos/net.cljc` is 41 lines of URL allowlist for *host*
   adapters, not a stack. A bare-metal node therefore cannot reach
   murakumo.cloud, cannot connect to a pool or gateway, and cannot serve
   inference over HTTP. No amount of packaging changes this.

3. **murakumo's participation logic is already Kotoba.** The repo carries 33
   `kotoba/*_core.kotoba` pure cores compiled to shipped KIR, including
   `infer_join_core` (tiers, relay need, residency clamp, work-kind
   eligibility) and `infer_credits_core` (the memory×time earning ledger). That
   is the natural seam with an OS whose decisions are already compiler-emitted
   Kotoba objects.

A fourth fact closed off the obvious shortcut: **those cores do not compile to
any aiueos native target today.** Measured, with the current compiler:
`infer_join_core.kotoba` → `x86_64-aiueos-user-v1` is rejected with *"typed
values currently require the kotoba-script web target, typed Wasm/CLJS target,
or the qualified native one-word string/record/variant/option/result slice"*.
The native slice admits `record-get` only on a directly-nested `record-new` of
the same schema, and every upstream core projects records arriving as
*parameters*. Entryless export libraries are separately restricted to the
js/wasm/cljs backends. Reusing the shipped cores verbatim on bare metal is
compiler work in `kotoba-lang/compiler`, not packaging work here.

## Decision

**Split the deliverable across the two profiles that already exist, and make
each profile claim only what it can demonstrate.**

### Bare-metal profile — boot authority (this ADR's implemented half)

1. **Boot transport becomes an explicit axis.** `smoke-qemu-uefi.sh` gains
   `AIUEOS_BOOT_TRANSPORT` (`disk` default | `usb`); `usb` attaches the same
   image behind `qemu-xhci` as `usb-storage` with `removable=on`.

2. **USB boot is proved by equivalence, not by a second green check.**
   `smoke-qemu-usb-boot.cljs` boots the *same image file* over both transports
   and requires: the USB run booted through a USB device path, the disk run did
   not, the aiueos evidence of both is byte-identical, and both reach the same
   terminal state. A USB run that merely also passed could have diverged
   silently; identical evidence cannot. Observed boot path:
   `PciRoot(0x0)/Pci(0x2,0x0)/USB(0x0,0x0)`, 33 identical evidence lines.

   Two things are excluded from the comparison, each for a stated and separately
   asserted reason. The firmware banner *names the boot device*, so it must
   differ — that is the positive proof. And each application processor writes a
   one-character liveness marker straight to the debug port while the bootstrap
   processor writes its evidence, so those characters race (`BAAIUEOS_…` vs
   `ABAIUEOS_…` on consecutive boots of the *same* transport); comparison
   therefore starts at each line's own `AIUEOS_` marker.

3. **The gate does not hardcode a passing status.** It reports
   `AIUEOS_USB_BOOT_EQUIVALENT` with whatever status the two transports shared,
   rather than claiming a pass neither earned, and `AIUEOS_USB_BOOT_OK` when the
   suite passes.

   This originally recorded that on QEMU 10.0.3 the shared UEFI suite fails at
   `AIUEOS_VIRTIO_INPUT_FAIL queue-or-envelope`. **Re-measured 2026-08-22 and it
   does not reproduce**: on one host running QEMU 10.0.3, virtio-input passes
   and the whole suite is green. Five boots whose serial logs were kept say so
   (ADR-0074, ADR-0076); earlier runs the same day agreed and their build
   directories have since been removed, so five is what can be shown rather than
   what was seen. One host is all either measurement covers — the original failure was real somewhere,
   and this one is real here — so the honest statement is that the virtio-input
   result is host-dependent and has to be measured rather than assumed in either
   direction. What does not change is the rule above: the gate reports the
   status it observed.

4. **Flashing is deny-by-default.** `flash-usb.cljs` inspects unless `--confirm`
   repeats the device path; refuses internal disks, non-removable devices and
   partitions; asks the OS whether a device is removable rather than
   pattern-matching its name; requires the image to match its build receipt;
   and re-reads the written bytes, because cheap flash media can acknowledge a
   write and store something else. There is deliberately no device auto-detect.

5. **The node's murakumo participation decision is mirrored as a Kotoba
   object.** `kotoba/murakumo-join-plan.kotoba` reimplements
   `murakumo.infer.join` in the scalar-i64 slice the aiueos object ABI admits,
   packing the record/option/string shapes upstream uses (encoding authority:
   `contracts/murakumo-node-v1.edn`). Parity is checked, not asserted:
   `test/murakumo/aiueos_join_plan_parity_test.clj` in kotoba-lang/murakumo
   drives it across the full tier × kind × memory × residency matrix — **777
   assertions, 0 failures** — and the object's own `main` re-checks five vectors
   so it fails on the node too, not only in someone's CI.

### Hosted profile — workload authority (planned, not implemented here)

Serving generation for murakumo.cloud needs a network stack, TLS, and an
inference runtime. ADR-0011's Linux-hosted PID-1 profile already has the first
two for free and is where that workload belongs. This ADR does not implement it
and does not claim it.

## Consequences

- A USB-booted aiueos node can **decide** its murakumo participation and cannot
  yet **act** on it. That gap is named in `contracts/usb-boot-v1.edn` and
  `contracts/murakumo-node-v1.edn` rather than left implicit, because the
  phrase "AI mining server OS" otherwise reads as though it were serving.
- USB boot is proved **under OVMF in QEMU only**. No physical machine has
  booted this image; real-hardware firmware quirks (USB 2 vs 3 enumeration,
  per-vendor fallback-path handling) are untested. The claim is exactly as
  strong as the evidence.
- The join-plan object is a **verified artifact, not an admitted application**.
  It compiles to `x86_64-aiueos-user-v1`, but `verify-kotoba-user-elf.py` pins
  the runtime-v2 context to the smoke app's shape (fuel 256, capability
  allow-bitmap 60 = cap-call 2,3,4,5, trampoline at 0x1E1020). A pure decision
  object declares no capabilities and is rejected — measured: *"invalid Kotoba
  aiueos runtime-v2 context"*. Admission is a design choice about what a node
  may **do** with the decision, plus the offline RSA signer, not a packaging
  detail.
- Exporting it as a *kernel* object would need an entry in
  `kotoba-lang/kotoba-native`'s `kernel-object-entries` allow-list — a reviewed
  ABI change in a third repo. Not taken: murakumo participation is application
  policy, not kernel mechanism, and probably does not belong in that ABI.
- `scripts/tasks.edn`, empty since the babashka retirement (ADR-2607173000),
  now carries the two USB tasks. The `os/aiueos/scripts` build chain stays sh +
  Python stdlib: pulling it behind nbb would put Node in the boot-evidence path.

## Alternatives considered

- **Compile murakumo's shipped cores directly for aiueos.** Rejected today, on
  measurement rather than preference — see the compiler gate above. This is the
  right long-term answer and becomes available when the native typed slice
  admits record parameters and entryless libraries.
- **Claim the release image was already USB-bootable and stop.** It very likely
  is; nothing asserted it, and "very likely" is not what the rest of this repo
  accepts as evidence.
- **Put the workload on bare metal by writing a NIC driver and TCP/IP stack.**
  Correct eventually, far beyond this change, and it would have delivered a
  half-finished stack instead of a working boot path.
- **Report the USB gate as passing by pinning the transports' shared failure.**
  Rejected: it would convert an environment-specific virtio-input failure into
  a claim that USB boot passes here, which is not true of either transport.
