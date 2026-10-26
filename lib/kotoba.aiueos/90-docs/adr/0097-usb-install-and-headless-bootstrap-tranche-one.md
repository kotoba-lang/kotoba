# 0097 — USB install and headless bootstrap, tranche one

Accepted 2026-08-25. Component-side execution of root ADR
`adr-2608251418-aiueos-usb-install-and-headless-bootstrap`, which is the
authority for the product contract. This ADR records what this tranche landed,
what it measured, and what stays red.

## What the root ADR asked first

Sync the contract with the tree. `contracts/usb-boot-v1.edn` still said
`:network :absent` while `kernel/pci.c` had carried virtio-net, DHCPv4, DNS,
TCP, TLS 1.3 and an HTTPS GET since the ADR-0020..0087 chain — a claim that
was true on 2026-08-05 and stale ever since. The gap is now split instead of
deleted: virtio networking is present and QEMU-proven, a **physical** NIC
driver is absent, so a real machine still boots on the offline floor. README
and ADR-0019 carry the same correction in place.

## Landed in this tranche

- **`contracts/install-v1.edn`** — the install product contract (gate I0):
  the nine-step completion chain, the intent schema and its refusal reasons,
  the installer refusal classes, the target receipt, the headless floor, and
  the exit-gate matrix mirroring the root ADR.
- **`os/aiueos/installer/`** — ported from unmerged branch commit `95719d66`
  (`agent/aiueos-dospara-native-install`) as scope-frozen legacy assets:
  receipt validation, whole-internal-empty-second-disk admission, exclusive
  open with TOCTOU re-inspection, write + same-descriptor readback, and the
  encrypted-image v1 slice. 18/18 node tests pass on main.
- **`scripts/install-intent.cljs`** (nbb) — create/verify install intents.
  An intent binds release digest, machine profile, target model / capacity
  bounds / transport, an optional serial *digest* (the serial itself is a
  comparison value, never logged), hostname, SSH key + fingerprint, network
  policy, mode and expiry. Verify refuses with named literals.
- **`scripts/install-to-disk.cljs`** (nbb) — the orchestrator: inspect via
  the ported installer, intent admission, repeat-safety, guarded install,
  then a target receipt in the last MiB of the disk, read back. Exit codes
  separate refuse (2), could-not-answer (3), and existing-install (4).
- **`scripts/make-install-usb-image.py` + `run-install-usb-build.cljs`** —
  one GPT image: release ESP + recovery byte-identical at their original
  LBAs (the boot path usb-boot-v1 proved is untouched), plus a FAT32
  payload partition carrying RELEASE.IMG, receipts, INTENT.JSN, and the
  installer bundle with a pinned Linux Node runtime. The receipt closes the
  I1 digest chain and `verify` re-derives it from the image alone.
- **`scripts/test-install-chain.cljs`** (nbb) — 18 cases, every refusal
  pinned to its named reason, plus the fake-device end-to-end: install →
  receipt present → reinserted-USB unattended re-erase refused (exit 4) even
  when inspection wrongly claims the disk is empty. Gates I2/I5, offline.
- **hw-probe** ported (`os/aiueos/hw-probe/`, build/smoke scripts,
  `hardware_qualification.cljc` + tests) as I6 tooling.

## Measured

- installer node suite: 18/18; install-chain nbb suite: 18/18 (`ran=18`
  asserted against the expected count — a shorter run fails).
- install-USB image build + verify: `AIUEOS_INSTALL_USB_IMAGE_OK`.
- QEMU dual-transport boot of the *install USB image itself* via
  `smoke-qemu-usb-boot.cljs` — see the flash/boot receipt lines in the tree
  history for this commit; the ESP is byte-identical to the release image's,
  and the equivalence gate is the same one ADR-0019 landed.

## Still red, and why that is stated here

- **I3**: the USB does not yet boot a live installer environment; the
  payload installs from an operator-run Linux environment on the target.
- **I4**: no physical-NIC driver, no first-boot provisioning service, no
  sshd — the headless floor in install-v1.edn refuses "SSH ready" until an
  external client completes a real handshake, and none has.
- **I7**: no physical machine has been probed or installed on this chain.
  The qualification target names in the root ADR are spec-sheet names, not
  probe receipts.

A green build, a green flash, and a green QEMU boot do not sum to "install
complete"; the completion chain in install-v1.edn is the only thing that may
say that, and it is red until I3–I7 close.
