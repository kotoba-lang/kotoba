# ADR-0214 — a second box, and the arguments nobody wrote down

- Status: accepted
- Date: 2026-09-10
- Follows ADR-0208/0210 (the guided stick) and the node-agent tranche. Reuses
  ADR-0207's reason for not pointing a second identity at an admitted name.

## What was asked, and what turned out to be needed

"Rebuild the K16 installer for an AMD Ryzen 5 6600HS box."

The installer needed no rebuilding. `make-node-autoinstall-iso.cljs` is Ubuntu
Server plus an autoinstall plus the agent bundle, and **nothing in it is CPU- or
NIC-specific** — that was the point of standing on a distribution rather than on
a hand-built initramfs. Measured before writing anything: the only per-box inputs
are six arguments (`--hostname`, `--target-serial`, `--ssh-key`, `--endpoint`,
`--console-password*`, `--tailscale-authkey-file`) plus the ISO's codename.

And the CPU change justifies none of them. **6600HS is Rembrandt; the K16's
7735HS is Rembrandt-R — the same silicon rebadged.** Same family 19h, same Zen 3+
core, same RDNA2 gfx1035 display block. The useful form of that fact is negative
and is now recorded where someone will hit it: this board needs no new kernel
argument, no new firmware package and no new driver on account of its CPU. A boot
failure here that the K16 did not have is the BOARD — its NIC, its BIOS, its disk
controller mode.

So what was missing is what the node-agent commit said was missing in its own
first line: *"the box exists and the means to make another one did not."* The
means are the ARGUMENTS, and they lived in one session's shell history.

## The decision

`contracts/node-machines-v1.edn` holds the boxes, and every box-specific field
carries its own provenance: `:measured` (read off the machine, by a named command,
on a named date), `:owner-stated` (the owner said so; nobody has read it off the
box), `:unverified` (nobody has looked — **not absent, not false**).

Writing the 6600HS entry is what made the file worth having. Every field in it is
unverified, because nobody has met the box — and the one that matters is the disk
serial. A stick built from a plausible-looking serial installs unattended onto
whatever disk matches, which is the single failure the whole install chain exists
to prevent (install-v1 already refuses "largest disk" and "first NVMe" for this
reason). So:

> `make-node-installer.cljs --machine <id>` builds the stick that **ASKS** unless
> that box's disk serial is measured. `--unattended` demands the measured field
> and refuses without it, naming the command that would measure it.

That is the whole product difference, and it is now decided by a recorded
measurement rather than by how confidently someone typed.

The driver also prints every fact with its provenance before building, so
"the stick built" cannot be read as "these facts about the box are right". For
the 6600HS today it prints `0 measured`.

## The box measures itself

A new box has no measured fields and the cheapest moment to read its NIC, disk
serial and board off it is the one boot that is happening anyway. The autoinstall
now writes `/var/log/aiueos-node-hwprobe.txt` (and prints it on the installer
console); `record-node-machine-probe.cljs` turns it into `:measured` fields.

From **sysfs and util-linux only**, deliberately: `lspci` and `dmidecode` live in
packages the live installer is not required to carry, and a probe that reports
nothing because a tool was absent looks exactly like a box with no NICs. `lspci`
is appended if it happens to exist, as a bonus and never as the source.

Read-only, additive, and **not on the critical path** — no `set -eu`, every
command guarded, the block ends in `exit 0`. A measurement that can fail an
install costs more than it measures. `--no-hw-record` turns it off, because a
default-on measurement nobody can decline is a default nobody chose.

Two things in that block were wrong when first written and are recorded because
both were found by running it rather than by reading it:

- a single `pci=%s:%s` printf emits a bare `:` for a NIC with no PCI parent, and
  `:` reads as a PCI id to anything that only checks for non-blank. Two
  independently blank fields now.
- the internal-disk rule keyed on `nvme*`. A box with a SATA SSD has no `nvme*`
  at all, so its serial could **never** be measured. It now asks lsblk
  (`RM`/`HOTPLUG`) — and excludes the virtual devices that pass that test, `zram`
  being the one that did.

## Evidence

`scripts/test-node-installer.cljs`, 55 cases, offline, registered as
`:node-installer-test` and run through `scripts/run-task.cljk`. It ingests a
probe into a registry COPY and then requires the driver to build the unattended
stick with the serial that probe carried — "the ingest printed six fields" is not
"an unattended stick can now be built". The probe block is extracted from the
builder's own output and executed.

Four mutations, and the cases each turned red, measured 2026-09-10:

| break | what turned red |
|---|---|
| the `--unattended` serial guard deleted | exactly the 2 cases that name it |
| `measured?` loses its provenance half (a value is enough) | exactly `driver-reports-zero-measured-facts-for-a-new-box` |
| the removable test dropped from the internal-disk rule | 9, including both stick-exclusion cases |
| the whole-fact registry rewrite restored | exactly the 4 commentary cases |

The third and fourth are the ones worth keeping, because both were **green
before**:

- The first version of "the stick is not a target" compared the recorded serial
  to the stick's. That passes whenever the field is nil, so dropping the
  removable test left it green. The exclusion is now measured on a probe whose
  only disk IS removable — the one shape where admitting it produces a confident
  wrong answer rather than an ambiguous one.
- The first rewriter replaced each fact map WHOLE. It measured correctly and
  silently deleted the commentary, the `:measure-by` that says how to read the
  field off a box again, and the `:same-silicon-as` above. The suite was green:
  the only thing it checked was a string in the file's HEADER, which survived.
  Only the fact's head is rewritten now, and the tail is copied byte for byte.

One more thing the read-back guard caught rather than the author: the 6600HS
entry already carried an `:on` from when the owner stated its CPU, so appending
a second one produced `Map literal contains duplicate key: :on`. Nothing was
written. The head now consumes `:on`/`:by` if present, and the read-back stays as
the net — it re-reads the rewrite, compares the machine and fact key sets, and
checks each value landed, before anything reaches the disk.

## Registered, which it was not

`make-node-agent-bundle.cljs` and `make-node-autoinstall-iso.cljs` were not in
`scripts/tasks.edn`. The registry is how anything here is found and run, so the
tooling that produced the working node could not be found by the task that is
supposed to list it. Four entries now: `:node-agent-bundle`,
`:node-installer-build`, `:node-machine-probe-record`, `:node-installer-test`.

## The stick was built, and it boots

Added 2026-09-10, later the same day. The section below said "no ISO was built,
not once, for this box or any other", and that is no longer true — it is
corrected here rather than left standing, since a false line in an accepted ADR
outlives the session that wrote it.

    iso     aiueos-node-autoinstall-amd-6600hs.iso
    bytes   3,453,515,776
    sha256  bbaef5040acc8e67bec70b83b1978175c508a10ebc9e4575e39f3ec7aa5aec83
    source  ubuntu-24.04.4-live-server-amd64.iso
            sha256 e907d92eeec9df64163a7e454cbc8d7755e8ddc7ed42f99dbc80c40f1a138433,
            compared against SHA256SUMS fetched from releases.ubuntu.com rather
            than against a digest anyone typed
    runtime node v26.7.0 linux-x64 + nbb 1.5.212 (installer/README.md records both)
    bundle  48,984,857 bytes, sha256 e487a7b6dc69085fc08666065fd46efa461514f2c1c5a55260219898291d8aa6

Read back **out of the finished image**, not off the build's own claims: the
agent bundle extracted from the ISO is byte-identical to the one that went in,
`/casper/vmlinuz` is still there, and the `autoinstall.yaml` in the image carries
the hostname, the exact public key passed, three late-commands (tailscale, agent,
hw-record) and a console hash that recomputes from `260308` and not from `260309`.

### Booted, as a removable USB device

QEMU 10.1.0, `q35` + OVMF with a writable VARS pflash, the ISO attached behind
`qemu-xhci` as `usb-storage,removable=on` — a stick goes through the firmware's
USB stack and the removable-media fallback path, and none of that is exercised by
attaching the same bytes as a fixed drive. Apple M4 host, so **TCG: no
acceleration is available for x86_64 here**, and the boot takes minutes.

    BdsDxe: starting Boot0001 "UEFI QEMU QEMU USB HARDDRIVE 1-0000:00:02.0-1"
    GNU GRUB version 2.12  ->  Try or Install Ubuntu Server
    EFI stub: Loaded initrd from LINUX_EFI_INITRD_MEDIA_GUID device path
    ...
    [ Guided storage configuration ]   <- and ONLY this screen

**That last line is the measurement.** Reaching the storage screen first means
subiquity read `/autoinstall.yaml` off the media: language, keyboard, network,
mirror and profile were all answered from the file, and only `storage` was left
interactive. It is also the product decision working end to end — the 6600HS has
no measured disk serial, so this stick asks.

The control makes it non-vacuous. The **pristine** Ubuntu ISO, booted by the same
script with only the image path changed, stops at "Willkommen! Bienvenue!
Welcome!" — the language screen. Same firmware, same USB attachment, same target
NVMe; the only difference is the two files added to the ISO.

Two more things measured rather than assumed:

- **Nothing was installed.** The 16 GB qcow2 target was 196K on disk before the
  boot and 196K after it. A stick that asks cannot be left plugged in and
  forgotten, and this is that claim with a number against it.
- **GRUB prints `error: file /boot/ not found` and `error: can't find command
  grub_platform`** — and prints both, identically, on the pristine Ubuntu ISO.
  They are not the repack. Checking that took one more boot and is the difference
  between a known-harmless message and a defect attributed to the wrong change.

### Repeating it

Manual, and not registered as a gate: the verdict is a TUI screenshot that a
person reads, and a gate whose pass condition is "someone looked at a picture"
would be a gate in name. The invocation is here so it is repeatable.

```sh
qemu-system-x86_64 -machine q35 -accel tcg -cpu max -smp 4 -m 4096 \
  -drive if=pflash,format=raw,unit=0,readonly=on,file=<edk2-x86_64-code.fd> \
  -drive if=pflash,format=raw,unit=1,file=<a writable copy of edk2-i386-vars.fd> \
  -drive if=none,id=stick,format=raw,readonly=on,file=<the built iso> \
  -device qemu-xhci,id=xhci -device usb-storage,bus=xhci.0,drive=stick,removable=on \
  -drive if=none,id=nvme0,format=qcow2,file=<blank 16G qcow2> \
  -device nvme,drive=nvme0,serial=QEMUTARGET0001 \
  -netdev user,id=n0 -device virtio-net-pci,netdev=n0 \
  -display none -vga std -serial file:serial.log \
  -monitor unix:mon.sock,server,nowait
```

Then `screendump <file>.ppm` on the monitor socket. Run it a second time against
the pristine Ubuntu ISO; without that half, "it reached the storage screen" is
compatible with the installer having reached it for its own reasons.

## The convenience could fail the install, and did not have to be able to

Added 2026-09-11, after an install error on the 6600HS that I have not seen the
text of. This section records a defect **measured in the shipped stick**, not a
diagnosis of that error — the two are only connected by suspicion.

The registry's `:nic` note already named this shape: "a NIC Ubuntu cannot drive
turns into a late-command failure rather than a clear 'no network'". It was
written as a property of the situation. It was also true of the code, and nobody
checked.

The tailscale late-command ran bare under `set -eu`:

    set -eu
    curtin in-target --target=/target -- sh -c 'curl … && apt-get -qq update && …'

`apt-get update` inside the target needs the network. Measured with a stub
`curtin` that exits 1: **the block exits 1, and curtin fails the install.** So a
box with no network during the install gets a generic installer failure, and the
operator is told nothing about the one thing they could act on.

Tailscale is not what makes this box a node. A convenience that can fail the
install it rode in on is a defect however well it works when it works — and the
hw-record block two lines below it already knew that, which is why it is guarded
and ends in `exit 0`.

The failure is now TESTED rather than allowed to abort, the join unit is armed
only if the package actually arrived, and every outcome is written to the install
log — including `AIUEOS_TAILSCALE_NOT_INSTALLED … most often that means this box
had no network during the install`.

**The `if` is the operative change, not the missing `set -eu`**, and that is
recorded because getting it wrong was measured. My first break test put `set -eu`
back at the top of the fixed block and the block still exited 0: `set -e` does
not abort on a command whose status an `if` consumes. A green mutation read as
"the fix was unnecessary" until the right break — the shipped block itself, run
with a failing `curtin` — turned it red.

Evidence: four cases in `:node-installer-test`, run rather than read (a stub
`curtin` on `PATH`, the block executed, its exit status taken). The shipped
builder turns exactly those four red and leaves the agent-block control green.
That control is the reason this is not "guard every late-command": the agent IS
the point of the stick, still runs under `set -eu`, and is still allowed to fail
the install.

⚠ **This does not explain the 6600HS error.** I have not seen it. What is
measured is that the stick which was flashed carries a block that can fail an
install, and that it no longer can.

## The bundled runtime is not self-contained

Added 2026-09-11, from installing the agent on the 6600HS by hand.

`make-node-agent-bundle` says it carries "what decides something, plus a runtime
to decide it with", and `install`'s usage says to run it with that runtime "so it
works before any package is installed". Measured: the bundled `node-linux-x64`
needs `libatomic.so.1`, and Ubuntu Server 24.04 does not ship `libatomic1`.

    6600HS   libatomic1 absent  ->  error while loading shared libraries
    K16      libatomic1 ii      ->  ldd reports 0 missing

So the property held on the first box by accident. It is not a property of the
bundle, and the ISO's agent late-command would have hit the same wall on this
box even if the tailscale block had not failed first. Not fixed here -- the fix
is either a statically linked runtime or a declared dependency, and choosing
between those is a decision with its own evidence. Recorded so the next person
does not read the docstring as a guarantee.

## Where this stands, 2026-09-11

The 6600HS is a murakumo node. Not "installed" -- answering, on a schedule
nobody triggers:

    aiueos-6600hs   tailscale 100.92.201.91   LAN 192.168.1.8 (netplan, persistent)
    did:key:z6Mkf33VwWzUSWuBJ5eoj1ofjE177xx1vevEhoBqDh8c5VGj
    register  201  {"state":"claimed"}
    heartbeat 202  {"accepted":true}   <- from a timer run nobody started

Verified by reboot, twice over: the box came back at `booted 2026-09-11
03:35:55` with its address and its tailnet membership restored by itself, and
`RunSSH`/`WantRunning` survived. The commands that measured it were run over
that restored tailscale SSH, with no jump host -- the session is its own
evidence.

Registration is an operator step and was the only one that needed a credential:
`accept-heartbeat` refuses `:unknown-device` before a row exists and
`:not-claimed` until one has an owner, and the agent owns only the back half of
the claim ceremony. What it took is now in the secrets index (root
`9d077a2`), including the thing that cost the detour -- an absent entry in that
index is not evidence the vault lacks the item.

### Landed

    cb77858  the registry, the driver, the ingest, the probe, 55 offline cases
    f5b0753  the stick was built, and it boots (QEMU, removable USB, OVMF)
    847b51d  a convenience must not be able to fail the install it rode in on
    ba10659  the 6600HS measured itself; the .cljk literals in scripts/; the
             test suite decoupled from the live contract
    e4cc6e5  the node agent's own .cljk literals, incl. the unit's ExecStart

    root df137de  the wired LAN, fully accounted for
    root 9d077a2  the devices console admin token, in the index at last
    west pin advanced with each; verify-west-pins green

### What the install actually did, and did not

The first install failed, and the box is the evidence: `/etc/netplan/` empty,
`/var/log/installer/` holding two files where a completed run holds ten, and
nothing at all from the late-commands -- no agent, no hw-record, no install log.
Identity applied, everything after the first late-command did not. That is the
shape of the tailscale block aborting under `set -eu` with no network, which is
the defect `847b51d` fixed.

⚠ **Reconstructed from state, not read.** The installer's own log was never
copied to the target, so the error TEXT is unrecovered and this remains an
inference with a very good fit rather than a measurement.

### Open, in the order they will bite

1. **`nbb` cannot resolve a namespace from a `.cljk` file.** Measured:
   `demo/a.cljk` alone gives `Could not find namespace: demo.a`; adding
   `demo/a.cljs` resolves it. So today's rename broke every nbb script that
   requires a repo namespace -- `scripts/west-pin-put.cljk` and
   `scripts/root-worktree.cljk` among them, both worked around here with a
   throwaway classpath. This is the largest open item and it is not aiueos-only.
2. **451 `.cljs` literals across 119 files, and zero `.cljs` files.** 38 sit in
   runnable scripts. Fixed only where measured broken (13 in this repo). A
   blanket rewrite would also hit docstrings and ADR text where `.cljs` is
   historically correct, so it needs a rule, not a sed.
3. **The bundled runtime needs `libatomic1`**, which Ubuntu Server does not
   ship. Installed by hand here. Static runtime versus declared dependency is
   the decision.
4. **`node-boot-test` `it-reports-claimable` is red on main**, identically
   before and after anything done here.

### Resume point

    ssh aiueos@100.92.201.91            # the node, over tailscale, keyless
    journalctl -u aiueos-node.service -n 20 --no-pager

The next box needs no browser and no detour: mint an ephemeral pre-authorized
tailnet key, pass it as `--tailscale-authkey-file`, and register the device
before first boot with the token now named in the secrets index. The 6600HS's
disk serial is measured, so `--unattended` builds a stick that no longer asks.

## What this does not claim

- **No physical hardware.** TCG emulation of an x86_64 machine says nothing about
  the 6600HS board — not its NIC, not its BIOS, not its disk controller mode.
  Those are exactly the fields its registry entry marks `:unverified`.
- **No completed install and no node.** The run stops where the product is meant
  to stop, at a person. Nothing has installed, booted from an internal disk,
  written a hardware record, enrolled, or heart-beaten.
- **Nothing about the 6600HS board is measured.** Its registry entry says so in
  six places. Its CPU is `:owner-stated`.
- **The K16 entry is not a receipt for the box that was working on 2026-09-10.**
  Its hardware facts are measured and were paid for while the bespoke installer
  was failing on it. Whether that board is the one the first Ubuntu node ran on
  is not recorded in this repository, and this entry does not decide it.
- **The K16 entry's hostname is `aiueos-k16-ubuntu`, not `gmktec-k16-lan2`.**
  That name belongs to the native PXE relay's enrolment, and pointing a second
  identity at an admitted name is what ADR-0207 measured the plane refusing (409,
  a name cannot be re-pointed to a different DID).
- **I6 and I7 are unchanged.** No physical probe receipt, no physical install.
