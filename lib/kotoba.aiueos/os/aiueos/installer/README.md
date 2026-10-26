# aiueos installer

Three things live here: the **guided installer** (the screens a person answers
at the machine), the **encrypted local-data image format**, and the
**second-disk installer mechanism** that the whole chain writes through.

## Guided installer (ADR-0208)

The ubuntu-server installer's shape -- a screen sequence, an answer file, and
`interactive-sections` -- on this repository's admission rules. It is an
AUTHORING tool: it opens no block device, writes no partition table and erases
nothing. What it produces is one `aiueos.install-intent.v1`, the artifact that
already existed, which then goes through every guard described further down
this file unchanged.

```sh
# ask every screen, write the intent and the answer file that reproduces it
kbb --backend sci os/aiueos/installer/live/guided-install.cljk \
  --release-receipt build/aiueos/aiueos-x86_64-build-receipt.json \
  --out-intent install-intent.json --out-answers install-answers.json

# replay that run on the next identical machine, asking nothing
kbb --backend sci os/aiueos/installer/live/guided-install.cljk \
  --answers install-answers.json \
  --release-receipt build/aiueos/aiueos-x86_64-build-receipt.json \
  --out-intent install-intent.json

# take everything from the file except the disk, which is this machine's
kbb --backend sci os/aiueos/installer/live/guided-install.cljk \
  --answers install-answers.json --interactive-sections storage \
  --release-receipt ... --out-intent install-intent.json
```

Screens: `network`, `storage`, `identity`, `ssh`, `confirm`. A section already
present in the answer file is skipped unless `--interactive-sections` names it
(`*` re-asks everything); `confirm` is asked whenever any other screen was.

**The storage screen does not record the disk it lists.** subiquity's
autoinstall admits `path: /dev/sda`; decision 2 of `install-v1.edn` does not,
because a bare device name eventually names the wrong machine's disk. The pick
is recorded as the MATCH it implies -- model, transport, inclusive capacity
bounds, and optionally the serial digest -- and the emitted intent contains no
`/dev/` path at all. On the target machine `install-live.cljs` re-derives the
device from that match and refuses unless exactly one disk matches.

Exit codes: `0` intent written, `2` refused with named reasons on stdout
(`AIUEOS_GUIDED_REFUSE <reason>`), `3` could-not-answer -- no probe, or stdin
ended mid-question. `3` is neither `0` nor `1` on purpose: a run that could not
ask must not look like a run that asked and got answers.

The answer file is validated **before** the first probe, so a malformed
unattended run fails while the target disk is untouched.

```sh
kbb --backend sci os/aiueos/scripts/test-guided-install.cljk   # 53 cases, offline
```

### A stick that asks (ADR-0210)

`--guided` builds an install USB carrying **no** `INTENT.JSN`:

```sh
kbb --backend sci os/aiueos/scripts/run-install-usb-build.cljk --guided \
  --node-binary <linux-node> --nbb-dir <nbb tree> --live-uki <uki>
```

Booted as the live installer, `/init` hands over to `install-live.cljs`, which
finds no intent and runs `guided-install.cljs` with the console attached. The
intent the operator authors then goes through the SAME fresh-probe
verification, the same single-candidate target selection and the same
device-level refusals. An intent authored ten seconds ago is not more trusted
than one authored last week.

`--guided` and `--intent` are exclusive and one is required: a forgotten
`--intent` must not quietly build the other product. `verify` decides which
product an image is from the image alone and cross-checks it against
`SHA256S.TXT`, so a payload between the two is refused by name.

Guided exit codes are propagated by `install-live.cljs`, not flattened: `2` is
a named refusal, `3` is nobody answered.

### Installing from the console, and the account link (ADR-0239)

When the intent was authored at this console, `install-live.cljk` does not
stop at the dry run. After every admission passes it offers to link the
machine to a kotoba.cloud account -- `account-sync.cljk` draws the approval
URL as a QR on the console, a phone approves with its Passkey, and the device
keys generated here go into the provision zone -- and then asks the person to
type `ERASE <device> FOR AIUEOS`, which `install.mjs` checks exactly as it
checks the unattended phrase. Declining the link installs without an account
and says so. An interactive intent carried ON the stick still only dry-runs.

```sh
# the link on its own, from any host with node + fetch (starts a real flow)
kbb --backend sci --classpath src:../text/src:../security/src \
  os/aiueos/installer/live/account-sync.cljk --model gmktec-k16 --out account.json
```

What is not claimed: no hardware run and no QEMU run (the interactive path is
measured against a piped answer script, which takes the same fd-0 code path as
a terminal); no fleet gate; gate I3's evidence still predates the 2026-09-09
namespace move (ADR-0209).

---

# aiueos encrypted storage and second-disk installer (first slice)

> Ported to `main` 2026-08-25 from unmerged branch commit `95719d66`
> (root ADR adr-2608251418, aiueos ADR-0097). The `.mjs`/`.sh` files here are
> **scope-frozen legacy assets**: they keep exactly the guarded
> second-empty-internal-disk contract described below. New behavior — install
> intents, the target receipt, repeat-erase refusal, and the install-USB
> artifact — lives in nbb orchestration (`os/aiueos/scripts/install-intent.cljk`,
> `install-to-disk.cljs`, `run-install-usb-build.cljs`) under the contract
> `os/aiueos/contracts/install-v1.edn`. Prefer `install-to-disk.cljs`, which
> wraps `install.mjs` and adds the intent admission, over calling `install.mjs`
> directly.

This directory contains two deliberately separate host-side tools:

1. `encrypted-image.mjs` defines `aiueos.encrypted-chunks.v1`, a deterministic,
   canonical container format for encrypted local data images.
2. `install.mjs` validates an existing aiueos release-image receipt and can
   copy that boot image only to an explicitly named, empty, second internal
   disk after layered destructive confirmation.

Neither tool is a native aiueos block driver. The encrypted data image is not
yet mounted by the bare-metal kernel, and the installer does not create an
encrypted root filesystem. TPM sealing, automatic unlock, Secure Boot key
management, partition resizing, and in-place Windows dual boot are **not
implemented**.

## Encrypted image format

The v1 format uses AES-256-GCM chunks because authenticated AES-XTS is not a
single safe primitive exposed by the chosen standard Node runtime. A 256-bit
recovery key is expanded by HKDF-SHA-256 into separate metadata-authentication,
data-encryption, and key-verification keys. Each data chunk uses a random
64-bit image nonce prefix plus its unsigned 32-bit chunk index as a unique
96-bit GCM nonce. Index `0xffffffff` is reserved for metadata under its separate
metadata key and is never a data-chunk index. Canonical metadata is authenticated, and every chunk
binds its index, clear length, and metadata digest as additional authenticated
data. Truncation, reordering, extension, wrong keys, and byte tampering fail
closed.

Fresh images randomly generate both a 256-bit salt and nonce prefix. Tests may
inject fixed values to produce byte-identical vectors; production callers
must not reuse such values with a recovery key. Recovery keys use the checked,
versioned representation `AIUEOS1-...-CHECKSUM`. Store that key offline: there
is no TPM or escrow path in this slice.

```sh
umask 077
node os/aiueos/installer/encrypted-image-cli.mjs keygen > recovery-key.txt
node os/aiueos/installer/encrypted-image-cli.mjs encrypt \
  --input data.img --output data.aiueenc --recovery-key-file recovery-key.txt
node os/aiueos/installer/encrypted-image-cli.mjs decrypt \
  --input data.aiueenc --output recovered.img --recovery-key-file recovery-key.txt
```

Output files are created with mode `0600` and are never overwritten.
The current host implementation reads the complete clear/encrypted image into
memory; it is a format and integrity slice, not yet a large-volume streaming
implementation. Command-line recovery keys are refused. The key file must be a
regular file with no group/other permissions (normally mode `0600`).

## Internal-disk installer

The installer never lists-and-picks a target. `--device`, `--image`, and
`--receipt` are mandatory. Without `--install` it only validates and reports.

```sh
node os/aiueos/installer/install.mjs \
  --device /dev/diskN \
  --image build/aiueos/aiueos-x86_64-gpt.img \
  --receipt build/aiueos/aiueos-x86_64-build-receipt.json
```

An install is refused unless OS inspection establishes all of these facts:

- target is a whole internal disk, not a partition;
- target has no partition table, child partitions, filesystem signature, or
  mount;
- target differs from every detected current boot/system disk;
- at least one current system disk was positively identified, proving this is
  a second disk;
- release-image size and SHA-256 match its build receipt.

Only after a successful dry run may the operator add all three destructive
arguments. The phrase printed by dry-run includes the exact canonical device.

```sh
sudo node os/aiueos/installer/install.mjs --install \
  --device /dev/diskN --confirm-device /dev/diskN \
  --destructive-phrase 'ERASE /dev/diskN FOR AIUEOS' \
  --image build/aiueos/aiueos-x86_64-gpt.img \
  --receipt build/aiueos/aiueos-x86_64-build-receipt.json
```

The complete written extent is read back and checked against the validated
digest. Real writes are Linux-only: the target block device must accept an
exclusive, no-symlink open, is inspected again while that descriptor remains
open, and is written and read back through that same descriptor. macOS can run
the dry inspection but real internal-disk writes are refused because this
implementation cannot obtain the equivalent exclusive block-device lock there.
Any identity or safety-state change aborts. The tool intentionally cannot
install beside Windows on the same disk;
use a physically separate empty disk. Firmware boot-order changes remain a
manual operation.

The fake backend is gated by both `NODE_ENV=test` and
`AIUEOS_INSTALLER_ALLOW_FAKE=1`; it exists only for isolated automated tests.

## Tests

```sh
node --test os/aiueos/installer/test/*.test.mjs
```

Tests use temporary regular files and injected fake devices. They never open a
real block device.

## The bundled Node.js runtime, and what "pinned" means

`smoke-qemu-install.cljs` and the node agent both want a linux-x64 Node binary,
and the prerequisite hint says "download the pinned linux-x64 node binary (see
installer README)". Until 2026-09-10 this README named no version and no digest,
so the hint pointed at a file that did not answer it and the next person picked
a different runtime. What is actually used is recorded here.

    version   v26.7.0
    tarball   https://nodejs.org/dist/v26.7.0/node-v26.7.0-linux-x64.tar.xz
    tarball   sha256 982aa24dd8be4c889c6a8ab337ddff3b0896645b20f4239356e80552c16277ee
    bin/node  sha256 ad19784f7e90ba789a099eccba77ede8dc90a778c424f1c10a70fed3ff903fdc
    nbb       1.5.212  (npm install nbb --prefix build/aiueos/nbb-bundle)

```sh
cd <scratch>
curl -fsSLO https://nodejs.org/dist/v26.7.0/SHASUMS256.txt
curl -fsSLO https://nodejs.org/dist/v26.7.0/node-v26.7.0-linux-x64.tar.xz
grep node-v26.7.0-linux-x64.tar.xz SHASUMS256.txt | shasum -a 256 -c -   # verify, then extract
tar xJf node-v26.7.0-linux-x64.tar.xz node-v26.7.0-linux-x64/bin/node
install -m 755 node-v26.7.0-linux-x64/bin/node <repo>/build/aiueos/node-linux-x64
```

Verify the tarball against `SHASUMS256.txt` from the same directory rather than
against the line above: this README is a record of what was used, and a digest
copied into prose is a digest nobody re-checked. The `bin/node` digest is here
for the other direction — to tell whether a `build/aiueos/node-linux-x64` that
is already sitting in a tree is this runtime or some other one.

This is a version, not a requirement. Another runtime may work; it will produce
a different bundle digest, and the receipt will say so.

## Offline Linux bundle

`offline-linux-installer.sh` runs the same installer with a bundled official
Linux x86_64 Node.js runtime and adjacent release image/receipt. The runtime is
copied to a private temporary directory because removable FAT media does not
preserve executable mode bits. Run it first without `--install`; all normal
second-empty-internal-disk and destructive-confirmation gates remain active.
