#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
log="$out/uefi-debug.log"
serial_log="$out/kernel-serial.log"
blk_image="$out/virtio-blk-smoke.img"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
plc_signing=
cleanup_plc_signing() {
  [ -z "$plc_signing" ] || [ ! -d "$plc_signing" ] || {
    rm -f "$plc_signing/key.pem" "$plc_signing/signature.der" \
      "$plc_signing/public.der" "$plc_signing/signature.raw" \
      "$plc_signing/public.raw"
    rmdir "$plc_signing"
  }
}
# One cleanup, one pair of traps. A second `trap ... EXIT` anywhere below would
# REPLACE these rather than add to them, and cleanup_plc_signing would silently
# stop running -- so anything else needing teardown hangs itself here instead.
tpm_state=
tpm_pid=
cleanup_tpm() {
  [ -z "$tpm_pid" ] || kill "$tpm_pid" 2>/dev/null || true
  [ -z "$tpm_state" ] || rm -rf "$tpm_state"
}
cleanup_all() { cleanup_plc_signing; cleanup_tpm; }
trap cleanup_all 0
trap 'cleanup_all; exit 1' HUP INT TERM

if [ "${AIUEOS_PLC_RT_SMOKE:-0}" = 1 ]; then
  # build-plc-native-program.sh writes build/aiueos-plc/<name>/, and this
  # defaulted to build/plc-motor/ -- a directory nothing in the tree produces.
  # The documented profile therefore could not run unless the caller passed
  # both paths by hand, which is a gate that is green because it was never
  # reached. Measured 2026-09-10: with the paths corrected the same command
  # boots and the kernel prints AIUEOS_PLC_RT_OK.
  plc_default="$repo/build/aiueos-plc/motor"
  AIUEOS_PLC_ELF=${AIUEOS_PLC_ELF:-"$plc_default/program.elf"}
  AIUEOS_PLC_RECEIPT=${AIUEOS_PLC_RECEIPT:-"$plc_default/program-receipt.json"}
  if { [ -n "${AIUEOS_PLC_SIGNATURE:-}" ] && [ -z "${AIUEOS_PLC_PUBLIC_KEY:-}" ]; } || \
     { [ -z "${AIUEOS_PLC_SIGNATURE:-}" ] && [ -n "${AIUEOS_PLC_PUBLIC_KEY:-}" ]; }; then
    echo "error: PLC signature and public key must be supplied together" >&2
    exit 1
  fi
  if [ -z "${AIUEOS_PLC_SIGNATURE:-}" ]; then
    command -v openssl >/dev/null 2>&1 || {
      echo "error: openssl is required to create RT smoke signature material" >&2
      exit 1
    }
    plc_signing=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-plc-signing.XXXXXX")
    openssl ecparam -name prime256v1 -genkey -noout \
      -out "$plc_signing/key.pem" 2>/dev/null
    openssl dgst -sha256 -sign "$plc_signing/key.pem" \
      -out "$plc_signing/signature.der" "$AIUEOS_PLC_ELF"
    openssl ec -in "$plc_signing/key.pem" -pubout -conv_form uncompressed \
      -outform DER -out "$plc_signing/public.der" 2>/dev/null
    python3 "$aiueos/scripts/make-plc-signature-material.py" \
      "$plc_signing/signature.der" "$plc_signing/public.der" \
      "$plc_signing/signature.raw" "$plc_signing/public.raw" >/dev/null
    AIUEOS_PLC_SIGNATURE="$plc_signing/signature.raw"
    AIUEOS_PLC_PUBLIC_KEY="$plc_signing/public.raw"
  fi
  export AIUEOS_PLC_ELF AIUEOS_PLC_RECEIPT \
    AIUEOS_PLC_SIGNATURE AIUEOS_PLC_PUBLIC_KEY
fi

# --- freshness floor (ADR-0155) ---------------------------------------------
#
# Three outcomes, and they must be distinguishable from the exit status alone:
#
#   0  the image booted and every assertion below held
#   1  a real boot failure -- named, with the marker that was missing
#   3  COULD-NOT-RUN -- the build failed, or qemu/OVMF/python3 is not here. This is
#      NOT a pass and NOT a boot failure: nothing was measured
#   4  REFUSED stale-image -- the artifact about to boot is not the one this run
#      produced (propagated from image-freshness.cljs)
#
# Measured 2026-09-02 on c9f7506, which is why the deletions come FIRST: when
# `build-uefi.sh` fails, everything the previous run wrote is still on disk --
# `esp/EFI/AIUEOS/KERNEL.ELF` and, worse, `kernel-serial.log` with the previous
# kernel's `NIC-PARITY ok` / `DEVCLIENT-PARITY canonical ok` /
# `AIUEOS_TLS13_RECORD_OK` in it. Every stream in the K16 programme collects its
# evidence by grepping that file, so a build that never ran answered with a
# kernel that is not in the tree.
receipt="$out/image-receipt.edn"
efi_image="$out/esp/EFI/BOOT/BOOTX64.EFI"
kernel_image="$out/esp/EFI/AIUEOS/KERNEL.ELF"
initrd_image="$out/esp/EFI/AIUEOS/INITRD.IMG"
rm -f "$receipt" "$efi_image" "$kernel_image" "$initrd_image" "$log" "$serial_log"

# python3 absent is could-not-run, never a quiet skip: without it the receipt
# is neither written nor checked, and the boot below would be unattributed
# again. The checker is the Node-free port (image-freshness.py); the nbb
# original is a dev-time oracle only (JUN-31 acceptance).
command -v python3 >/dev/null 2>&1 || {
  echo "COULD-NOT-RUN python3-missing: the image freshness receipt cannot be checked" >&2
  exit 3
}

# Guest browser desktop (ADR-0223) is guest-input plus a virtio-tablet: the
# same real keyboard (no synthetic event compiled in), and a pointer press the
# QMP injector below sends through the tablet.
if [ "${AIUEOS_GUEST_BROWSER:-0}" = 1 ]; then
  AIUEOS_GUEST_INPUT=1
fi
# A plain full-suite boot must reach its terminal #UD evidence. The kernel's
# production build keeps the desktop alive, so only this smoke harness arms the
# probe by default. Interactive gates and an explicit loop-terminal gate keep
# the persistent desktop; an explicit caller choice always wins.
if [ -z "${AIUEOS_SMOKE_FINAL_PROBE+x}" ]; then
  if [ "${AIUEOS_GUEST_INPUT:-0}" = 1 ] || [ -n "${AIUEOS_LOOP_EXIT_OK:-}" ]; then
    AIUEOS_SMOKE_FINAL_PROBE=0
  else
    AIUEOS_SMOKE_FINAL_PROBE=1
  fi
fi
export AIUEOS_SMOKE_FINAL_PROBE
build_status=0
if [ "${AIUEOS_GUEST_INPUT:-0}" = 1 ]; then
  AIUEOS_CATALOG_POLICY_SELFTEST=1 \
    "$aiueos/scripts/build-uefi.sh" >/dev/null || build_status=$?
else
  AIUEOS_INPUT_SMOKE_SYNTHETIC=1 AIUEOS_CATALOG_POLICY_SELFTEST=1 \
    "$aiueos/scripts/build-uefi.sh" >/dev/null || build_status=$?
fi
# The build's own exit status, not the presence of a file. `set -e` already
# stopped a build that exits non-zero, but it stopped it SILENTLY -- one line of
# bash's stderr and nothing that says which of the three outcomes this was.
[ "$build_status" = 0 ] || {
  echo "COULD-NOT-RUN build-failed: build-uefi.sh exited $build_status" >&2
  echo "               no image was booted and no evidence was produced" >&2
  exit 3
}

# The other half: the artifact the boot is about to consume must be the one the
# build just produced, from the tree in front of us. Deleting first cannot say
# that -- a build could still write an image from a different source path, or
# hand back a cached one.
#
# Run HERE, before the deliberate-corruption blocks below: those exist to feed
# the loader a damaged image on purpose, so they are allowed to move these bytes
# afterwards. What is asserted is that they damaged a FRESH image.
freshness_status=0
python3 "$aiueos/scripts/image-freshness.py" assert \
  --receipt "$receipt" --root "$repo" \
  "$efi_image" "$kernel_image" "$initrd_image" || freshness_status=$?
[ "$freshness_status" = 0 ] || exit "$freshness_status"

if [ "${AIUEOS_CORRUPT_KERNEL:-0}" = 1 ]; then
  python3 - "$out/esp/EFI/AIUEOS/KERNEL.ELF" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
data = bytearray(path.read_bytes())
data[-1] ^= 0x01
path.write_bytes(data)
PY
fi
if [ "${AIUEOS_CORRUPT_INITRAMFS:-0}" = 1 ]; then
  python3 - "$out/esp/EFI/AIUEOS/INITRD.IMG" <<'PYC'
from pathlib import Path
import sys
path = Path(sys.argv[1])
data = bytearray(path.read_bytes())
data[-1] ^= 0x01
path.write_bytes(data)
PYC
fi
command -v "$qemu" >/dev/null 2>&1 || {
  echo "COULD-NOT-RUN qemu-missing: qemu-system-x86_64 is required" >&2
  exit 3
}

if [ -z "${OVMF_CODE:-}" ]; then
  for candidate in \
    /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
    /opt/homebrew/Cellar/qemu/*/share/qemu/edk2-x86_64-code.fd \
    /usr/share/OVMF/OVMF_CODE_4M.fd \
    /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/edk2/x64/OVMF_CODE.fd; do
    if [ -f "$candidate" ]; then OVMF_CODE=$candidate; break; fi
  done
fi
[ -f "${OVMF_CODE:-}" ] || {
  echo "COULD-NOT-RUN ovmf-missing: OVMF firmware not found; set OVMF_CODE" >&2
  exit 3
}

rm -f "$log" "$serial_log"
if [ "${AIUEOS_PRESERVE_BLK_IMAGE:-0}" != 1 ] || [ ! -f "$blk_image" ]; then
python3 "$aiueos/scripts/make-aiuefs-image.py" \
  --entry "app/hello,$aiueos/kotoba/user-smoke.elf,$aiueos/kotoba/user-smoke.sig" \
  --entry "app/worker,$aiueos/kotoba/user-smoke.elf,$aiueos/kotoba/user-smoke.sig" \
  --catalog-signature "$aiueos/kotoba/app-catalog.sig" --output "$blk_image"
fi
if [ "${AIUEOS_CORRUPT_KOTOBA_APP:-0}" = 1 ]; then
python3 - "$blk_image" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); b=bytearray(p.read_bytes()); b[4*512+64]^=1; p.write_bytes(b)
PY
fi
if [ "${AIUEOS_CORRUPT_KOTOBA_SIGNATURE:-0}" = 1 ]; then
python3 - "$blk_image" <<'PY'
from pathlib import Path
import struct, sys
p=Path(sys.argv[1]); b=bytearray(p.read_bytes()); catalog_sector=struct.unpack_from('<I',b,36)[0]
signature_sector=struct.unpack_from('<I',b,catalog_sector*512+16+56)[0]
b[signature_sector*512+17]^=1; p.write_bytes(b)
PY
fi
if [ "${AIUEOS_CORRUPT_KOTOBA_CATALOG:-0}" = 1 ]; then
python3 - "$blk_image" <<'PY'
from pathlib import Path
import struct,sys
p=Path(sys.argv[1]);b=bytearray(p.read_bytes());sector=struct.unpack_from('<I',b,36)[0]
b[sector*512+20]^=1;p.write_bytes(b)
PY
fi
# Boot transport (ADR-0019): `disk` attaches the medium as a fixed drive the
# firmware enumerates directly; `usb` attaches it behind an xHCI controller as
# a REMOVABLE USB mass-storage device, which is the path a physical USB stick
# actually takes — the firmware must run its USB stack, enumerate the device,
# and boot the removable-media fallback `\EFI\BOOT\BOOTX64.EFI`. Only the
# transport differs: every other device and every evidence assertion below is
# identical, so the two runs' logs are directly comparable.
boot_transport=${AIUEOS_BOOT_TRANSPORT:-disk}
case "$boot_transport" in
  disk|usb) ;;
  *)
    echo "error: AIUEOS_BOOT_TRANSPORT must be disk or usb: $boot_transport" >&2
    exit 1
    ;;
esac
usb_args=
# H1's second drive is attached from the branch below whichever medium boots,
# so its argument list is initialised HERE: `set -u` reaches the QEMU line on
# every route, and only the AIUEOS_DISK_IMAGE route assigned it (measured
# 2026-10-26: the default ESP boot died with `update_drive_args: unbound
# variable` before QEMU ever started).
update_drive_args=
# F5 USB storage (JUN-140): a UHCI host controller with a usb-storage disk
# behind it. The guest probes the UHCI controller (class 0c/03/00); the disk
# carries AIUEOS_USB_STORAGE as its raw contents.
if [ -n "${AIUEOS_USB_STORAGE:-}" ]; then
  [ -f "$AIUEOS_USB_STORAGE" ] || {
    echo "error: AIUEOS_USB_STORAGE does not exist: $AIUEOS_USB_STORAGE" >&2
    exit 1
  }
  usb_args="$usb_args -device piix3-usb-uhci,id=aiueos_uhci -drive if=none,id=aiueos_usb,file=$AIUEOS_USB_STORAGE,format=raw -device usb-storage,drive=aiueos_usb,bus=aiueos_uhci.0"
fi
if [ -n "${AIUEOS_CDROM_IMAGE:-}" ]; then
  [ -f "$AIUEOS_CDROM_IMAGE" ] || {
    echo "error: AIUEOS_CDROM_IMAGE does not exist: $AIUEOS_CDROM_IMAGE" >&2
    exit 1
  }
  [ "$boot_transport" = disk ] || {
    echo "error: AIUEOS_BOOT_TRANSPORT=usb does not apply to an El Torito ISO" >&2
    exit 1
  }
  # El Torito boot from the release ISO; cdrom media is opened read-only.
  boot_drive="format=raw,media=cdrom,file=$AIUEOS_CDROM_IMAGE"
elif [ -n "${AIUEOS_DISK_IMAGE:-}" ]; then
  [ -f "$AIUEOS_DISK_IMAGE" ] || {
    echo "error: AIUEOS_DISK_IMAGE does not exist: $AIUEOS_DISK_IMAGE" >&2
    exit 1
  }
  # OVMF may open the boot medium writable; snapshot keeps the release artifact immutable.
  if [ "$boot_transport" = usb ]; then
    boot_drive="if=none,id=aiueosusb,format=raw,snapshot=on,file=$AIUEOS_DISK_IMAGE"
    usb_args="-device qemu-xhci,id=xhci -device usb-storage,bus=xhci.0,drive=aiueosusb,removable=on"
  else
    # AIUEOS_DISK_SNAPSHOT=off makes writes persist (H1/H2 multi-boot tests);
    # the default stays on so the release artifact is immutable.
    boot_drive="format=raw,snapshot=${AIUEOS_DISK_SNAPSHOT:-on},file=$AIUEOS_DISK_IMAGE"
  fi
# H1: an update volume attached as a second fixed drive (a FAT16 image the
# loader's update scan looks for \\UPDATE.ID on).
if [ -n "${AIUEOS_UPDATE_IMAGE:-}" ]; then
  [ -f "$AIUEOS_UPDATE_IMAGE" ] || {
    echo "error: AIUEOS_UPDATE_IMAGE does not exist: $AIUEOS_UPDATE_IMAGE" >&2
    exit 2
  }
  update_drive_args="-drive format=raw,file=$AIUEOS_UPDATE_IMAGE"
fi
else
  [ "$boot_transport" = disk ] || {
    echo "error: AIUEOS_BOOT_TRANSPORT=usb requires AIUEOS_DISK_IMAGE" >&2
    exit 1
  }
  boot_drive="format=raw,file=fat:rw:$out/esp"
fi
iommu_args=
if [ "${AIUEOS_TEST_DMAR:-0}" = 1 ]; then iommu_args="-device intel-iommu,intremap=on"; fi
# The board's own IOMMU class. The K16 is an AMD Ryzen 7 7735HS, so every VT-d
# marker this suite can prove is proved against silicon the machine does not
# have -- isolation reads 6/6 on hardware that would score 0. This mode boots
# the same guest behind AMD-Vi instead, which QEMU 10.0.3 provides as
# `amd-iommu`, and asserts NOTHING yet: no AMD path exists to assert. It is
# here to observe what the guest does on the platform it will actually run on,
# which had never been executed. Assertions arrive with the IVRS parser.
#
# MEASURED 2026-09-09: this does not yet exercise the AMD path. QEMU accepts
# the device on q35 without complaint, with or without intremap=on, but the
# guest reports AIUEOS_IVRS_ABSENT -- no IVRS table reaches it through OVMF.
# So the device exists in QEMU and the TABLE does not, and the AMD-Vi path
# stays unexercisable here until that changes or the board is powered. Kept
# because the boot itself is worth having: it is the only way to run this OS
# on its own platform's IOMMU class without the hardware.
if [ "${AIUEOS_TEST_IVRS:-0}" = 1 ]; then iommu_args="-device amd-iommu"; fi

# TPM2 the same way IVRS is done: attach the device only when asked for, so
# every existing gate boots the machine it booted before. swtpm supplies the
# device; whether the guest ever SEES a TPM2 ACPI table is the firmware's
# decision, and that is the thing actually under test here -- the taxonomy
# records TPM2 as blocked on "a firmware this machine does not have", which is
# a claim about OVMF, not about the device, and was never measured.
tpm_args=
if [ "${AIUEOS_TEST_TPM2:-0}" = 1 ]; then
  if command -v swtpm >/dev/null 2>&1; then
    tpm_state=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-swtpm.XXXXXX")
    swtpm socket --tpm2 --tpmstate "dir=$tpm_state" \
      --ctrl "type=unixio,path=$tpm_state/sock" --flags startup-clear \
      >"$tpm_state/swtpm.log" 2>&1 &
    tpm_pid=$!
    tpm_wait=0
    while [ ! -S "$tpm_state/sock" ] && [ "$tpm_wait" -lt 50 ]; do
      tpm_wait=$((tpm_wait + 1)); sleep 0.1
    done
    if [ -S "$tpm_state/sock" ]; then
      tpm_args="-chardev socket,id=chrtpm,path=$tpm_state/sock -tpmdev emulator,id=tpm0,chardev=chrtpm -device tpm-tis,tpmdev=tpm0"
    else
      echo "error: swtpm did not create its control socket" >&2
      exit 1
    fi
  else
    echo "error: AIUEOS_TEST_TPM2=1 but swtpm is not installed" >&2
    exit 1
  fi
fi
# A NIC is attached only when asked for, so every existing gate keeps booting
# the exact machine it booted before. SLIRP ("-netdev user") is a real peer with
# a fixed topology — it answers ARP for 10.0.2.2 — which is what lets the first
# packet aiueos ever sends be checked against an actual reply rather than a
# loopback of itself. No host network access is involved.
# ADR-0272: a virtio sound card whose output goes to a WAV file next to the serial log, so the sound the guest plays can be measured on the host.
audio_args=
if [ "${AIUEOS_TEST_AUDIO:-0}" = 1 ]; then
  audio_args="-audiodev wav,id=aiueossnd,path=$out/audio.wav -device virtio-sound-pci,audiodev=aiueossnd"
fi
net_args=
if [ "${AIUEOS_TEST_NET:-0}" = 1 ]; then
  # `guestfwd` gives the guest a TCP peer without any external network: QEMU
  # accepts a connection to 10.0.2.100:9000 and pipes the stream through
  # `cat`, so it echoes. That is what lets the TCP gate prove a real
  # handshake -- sequence numbers, ACKs and both checksums all have to be
  # right or nothing comes back -- rather than a self-echo the OS produced.
  net_args="-netdev user,id=aiueosnet,guestfwd=tcp:10.0.2.100:9000-cmd:/bin/cat -device virtio-net-pci,netdev=aiueosnet,disable-legacy=on"
  # AIUEOS_SSH_HOSTFWD=<host-port> additionally forwards that host port into the
  # guest's :22, so an external client can reach the SSH listener (ADR-0102).
  # It only ADDS a hostfwd to the same netdev; the guestfwd the other net gates
  # depend on is untouched.
  if [ -n "${AIUEOS_SSH_HOSTFWD:-}" ]; then
    net_args="-netdev user,id=aiueosnet,guestfwd=tcp:10.0.2.100:9000-cmd:/bin/cat,hostfwd=tcp:127.0.0.1:${AIUEOS_SSH_HOSTFWD}-10.0.2.15:22 -device virtio-net-pci,netdev=aiueosnet,disable-legacy=on"
  fi
fi
# A hung guest must fail fast with diagnostics rather than pinning CI until
# the job-level timeout. 124 from timeout(1) is handled below.
#
# Two limits now, and the second one is the one that fires (ADR-0200).
#
#   qemu_timeout  the wall clock. 360s, not 600. Measured on this host with
#                 measure-boot-flake-rate.cljs: 16 consecutive boots of one
#                 already-built image, ALL PASS, min 68.5 / p50 85.1 / p90
#                 122.0 / max 165.5 seconds, at load average 67-125. 360 is
#                 2.2x the slowest boot observed. 600 was never measured here
#                 -- it was the ubuntu CI job budget from issue #108, and
#                 three attempts at it is what turned a deterministic #UD into
#                 half an hour of "known flake".
#
#   quiet_limit   how long the guest may write NOTHING on EITHER transport
#                 before the attempt is ended. This is what makes a dead guest
#                 fail fast, and it does not scale with how slow the host is.
#
# 150s for the quiet limit, and the number is justified by the boot's phase
# structure rather than by a single reading. A healthy full-evidence boot has
# exactly one long silent phase -- PCI enumeration under TCG, between
# AIUEOS_APIC_TIMER_OK and AIUEOS_PCI_OK -- measured byte-for-byte at 47s, with
# the longest silence over n=7 good boots at 66.5s (BISECT-SHA256, 2026-09-03).
# 150 is 2.25x that. It is deliberately NOT tight: 66.5s is an observed maximum
# over seven runs, not a bound, the gap grows with load and not monotonically
# (largest at load 84-87, not 96-99), and the run that took 165.5s above was at
# load 124.9 -- higher than anything in that n=7. A quiet limit that kills a
# healthy boot converts this fix into the bug it is fixing.
#
# These are this workstation's numbers under concurrent agent load. The METHOD
# transfers; re-measure the numbers per host with measure-boot-flake-rate.cljs.
qemu_timeout=${AIUEOS_QEMU_TIMEOUT:-360}
quiet_limit=${AIUEOS_QEMU_QUIET:-150}
# kotoba-lang/aiueos#108 is a REAL bug with a NAMED signature: the ring-3
# process phase loses a wakeup and the serial log stops at
# AIUEOS_KOTOBA_ELF_PROCESS_OK. The issue also records where it was seen --
# "~1 boot in ~15-25 on ubuntu runners; never reproduced locally (macOS,
# QEMU 10, faster host)" -- and those runners are gone (this workspace
# retired GitHub Actions).
#
# What was wrong here was not the retry, it was its WIDTH. ANY timeout was
# retried, so a guest that had already died of #UD on the first boot was
# reported three times as a flake and only then as a failure. A retry now
# requires the signature, or no guest output at all; every other timeout is a
# result and is reported immediately. Each attempt still restarts from a
# pristine data disk so a partially-written disk cannot change its outcome.
qemu_attempts=${AIUEOS_QEMU_ATTEMPTS:-3}
flake_signature=${AIUEOS_FLAKE_SIGNATURE:-AIUEOS_KOTOBA_ELF_PROCESS_OK}
boot_times="$out/boot-times.log"
# QEMU 10.1 virtio-gpu sets enabled_output_bitmask=1 at realize. Extra
# heads become enabled only when a UI frontend calls ui_info with a
# non-zero size (hw/display/virtio-gpu-base.c). `-display none` never
# does that, so GET_DISPLAY_INFO stays one-scanout. cocoa only ui_info's
# the front window (head 0). dbus SetUIInfo on Console_1 enables head 1.
# Default stays none so gpu/guest-gpu-two do not pop a window.
display_backend=${AIUEOS_QEMU_DISPLAY:-none}
aiueos_dbus_pid=
if [ "${AIUEOS_GUEST_SCANOUT_TWO:-0}" = 1 ]; then
  display_backend=dbus
  command -v gdbus >/dev/null 2>&1 || {
    echo "error: gdbus is required for guest-scanout-two" >&2
    exit 1
  }
  command -v dbus-daemon >/dev/null 2>&1 || {
    echo "error: dbus-daemon is required for guest-scanout-two (brew install dbus)" >&2
    exit 1
  }
  # Own a bus under $out. An inherited DBUS_SESSION_BUS_ADDRESS may
  # point at a dead unix socket (macOS launchd session socket is empty;
  # a previous probe in the same shell leaves a stale path). QEMU then
  # fails with "failed to connect to DBus" before GET_DISPLAY_INFO.
  rm -f "$out/guest-scanout.sock" "$out/dbus.addr" "$out/dbus.pid"
  dbus-daemon --session --fork --nopidfile \
    --address="unix:path=$out/guest-scanout.sock" \
    --print-address=3 --print-pid=4 3>"$out/dbus.addr" 4>"$out/dbus.pid"
  DBUS_SESSION_BUS_ADDRESS=$(cat "$out/dbus.addr")
  export DBUS_SESSION_BUS_ADDRESS
  unset DBUS_LAUNCHD_SESSION_BUS_SOCKET || true
  aiueos_dbus_pid=$(cat "$out/dbus.pid")
fi
if [ "$display_backend" = dbus ]; then
  display_opt="dbus,gl=off"
else
  display_opt="$display_backend"
fi
qmp_path="$out/guest-input.qmp"
qmp_args=""
kbd_args="-device virtio-keyboard-pci,disable-legacy=on"
if [ "${AIUEOS_GUEST_INPUT:-0}" = 1 ]; then
  kbd_args="-device virtio-keyboard-pci,disable-legacy=on,id=kbd0"
  if [ "${AIUEOS_GUEST_BROWSER:-0}" = 1 ]; then
    kbd_args="$kbd_args -device virtio-tablet-pci,disable-legacy=on,id=tab0"
  fi
  # The QMP socket path comes from $out, and a UNIX socket path is capped at
  # 104 bytes. The default out leaves FIVE bytes of headroom, so a checkout
  # directory a few characters longer silently makes this documented profile
  # unrunnable -- and the symptom is a QEMU startup error naming neither the
  # profile nor the cause. Refuse here, where the message can say both.
  qmp_len=$(printf '%s' "$qmp_path" | wc -c | tr -d ' ')
  if [ "$qmp_len" -ge 104 ]; then
    echo "error: AIUEOS_GUEST_INPUT needs a QMP socket at $qmp_path" >&2
    echo "       that path is $qmp_len bytes and the UNIX limit is 104." >&2
    echo "       Set AIUEOS_OUT to a shorter directory." >&2
    exit 1
  fi
  qmp_args="-qmp unix:${qmp_path},server,nowait"
fi
pristine_blk=
if [ -f "$blk_image" ]; then
  pristine_blk="$blk_image.pristine"
  cp "$blk_image" "$pristine_blk"
fi
# Both transports, before every attempt, not once before the first. A retry
# that inherits the previous attempt's debugcon log starts its clock about
# fifty seconds early (the build is inside the gap) and reports the guest
# silent while it is in fact writing to the other stream. Measured by the
# BISECT-SHA256 stream, 2026-09-03, while it was building the distribution
# that set the timeout above.
attempt=1
while :; do
  rm -f "$log" "$serial_log"
  [ -n "$pristine_blk" ] && cp "$pristine_blk" "$blk_image"
  inject_pid=
  if [ "${AIUEOS_GUEST_INPUT:-0}" = 1 ]; then
    rm -f "$qmp_path"
    AIUEOS_QMP_POINTER="${AIUEOS_GUEST_BROWSER:-0}" AIUEOS_SERIAL_LOG="$serial_log" \
    AIUEOS_QMP_PATH="$qmp_path" AIUEOS_QMP_LOG="$out/guest-input-qmp.log" python3 - <<'PY' &
import json, os, socket, sys, time
path = os.environ["AIUEOS_QMP_PATH"]
log_path = os.environ.get("AIUEOS_QMP_LOG", "")
def log(msg):
    if not log_path:
        return
    try:
        with open(log_path, "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass
deadline = time.time() + 60
sock = None
while time.time() < deadline:
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(path)
        break
    except OSError:
        time.sleep(0.05)
        sock = None
if sock is None:
    log("connect-timeout")
    sys.exit(0)
sock.settimeout(1.0)
buf = b""
def recv_obj():
    global buf
    while True:
        nl = buf.find(b"\n")
        if nl >= 0:
            line, buf = buf[:nl], buf[nl+1:]
            line = line.strip()
            if line:
                return json.loads(line)
        try:
            chunk = sock.recv(4096)
        except socket.timeout:
            return None
        if not chunk:
            return None
        buf += chunk
banner = recv_obj()
log("banner " + json.dumps(banner)[:400])
sock.sendall(b'{"execute":"qmp_capabilities"}\n')
log("caps " + json.dumps(recv_obj())[:400])
# QEMU 10.1 input-send-event `device` is a *display console* name, not the
# virtio-keyboard-pci id. Passing id=kbd0 aborts with
# qemu-fixed-text-console.device. Broadcast (no device) reaches the
# virtio-keyboard input handler. send-key is the PS2 path and is not this gate.
status_deadline = time.time() + 30
while time.time() < status_deadline:
    sock.sendall(b'{"execute":"query-status"}\n')
    st = recv_obj()
    if st and st.get("return", {}).get("running"):
        log("running")
        break
    time.sleep(0.1)
key = {"type": "qcode", "data": "a"}
events = [
    {"type": "key", "data": {"down": True, "key": key}},
    {"type": "key", "data": {"down": False, "key": key}},
]
# Guest browser desktop (ADR-0223): a left press through the virtio-tablet at
# absolute (1536, 2048) of 0..32767. The guest scales by its own surface, so
# on 1280x800 that is pixel (60, 50), and on any surface the hosted
# boot-desktop fits (>= 752x572) it lands inside window 1 and outside window 2
# -- the press that must raise the back window.
#
# Separate commands, and the release on its own: QEMU's virtio-input queues a
# device's events up to the SYN and drops the whole batch unless that many
# buffers are posted. The driver posts four, so x + y + press + SYN fits and
# x + y + press + release + SYN (measured 2026-09-24: used=0 for the whole
# boot) does not.
batches = [events]
if os.environ.get("AIUEOS_QMP_POINTER") == "1":
    batches += [
        [{"type": "abs", "data": {"axis": "x", "value": 1536}},
         {"type": "abs", "data": {"axis": "y", "value": 2048}},
         {"type": "btn", "data": {"down": True, "button": "left"}}],
        [{"type": "btn", "data": {"down": False, "button": "left"}}],
    ]
payloads = [json.dumps({"execute": "input-send-event", "arguments": {"events": b}}) + "\n"
            for b in batches]
# The keyboard takes the first key it sees, so ninety seconds of repeats were
# enough for guest-input. The tablet is brought up AFTER the keyboard has its
# event, and measured 2026-09-24 it saw used=0 when this window closed at 90 s
# -- so with a pointer the injector keeps sending until QEMU goes away (the
# send fails and the loop breaks) or well past the boot's own timeout.
end = time.time() + (900 if os.environ.get("AIUEOS_QMP_POINTER") == "1" else 90)
i = 0
while time.time() < end:
    try:
        # Guest browser typing (ADR-0225): once the kernel says TYPE_READY the
        # repeated keys stop (they would be typed), and after TYPE_GO the
        # sequence n i h o n n g o Enter k u w a w a r u Space Enter is typed
        # exactly once (ADR-0235: くわわる -> 加 through the Unihan dictionary).
        typing = os.environ.get("AIUEOS_QMP_POINTER") == "1"
        serial_now = b""
        if typing:
            try:
                serial_now = open(os.environ.get("AIUEOS_SERIAL_LOG", ""), "rb").read()
            except OSError:
                serial_now = b""
        if not (typing and b"AIUEOS_GUEST_BROWSER_TYPE_READY" in serial_now):
            for payload in payloads:
                sock.sendall(payload.encode())
                reply = recv_obj()
                if reply and i < 8:
                    log("reply " + json.dumps(reply)[:400])
        # The preedit (ADR-0227): `k a n` at PREEDIT_GO, and Enter at
        # PREEDIT_ENTER only once the composition's frame has been dumped.
        for go, keys, after in ((b"AIUEOS_GUEST_BROWSER_TYPE_GO",
                                 ["n", "i", "h", "o", "n", "n", "g", "o", "ret",
                                  "k", "u", "w", "a", "w", "a", "r", "u", "spc", "ret"], None),
                                (b"AIUEOS_GUEST_BROWSER_PREEDIT_GO", ["k", "a", "n"], None),
                                (b"AIUEOS_GUEST_BROWSER_PREEDIT_ENTER", ["ret"], "guest-browser-preedit.ppm"),
                                # ADR-0228: Hankaku/Zenkaku is evdev 41, qcode grave_accent.
                                (b"AIUEOS_GUEST_BROWSER_IME_TOGGLE_GO",
                                 ["grave_accent", "k", "a", "grave_accent", "k", "a", "ret"], None),
                                # ADR-0235: やま converts, and after that frame's dump the
                                # candidates cycle, Escape puts the reading back, and
                                # 山 and 償 (しょう's second) are committed.
                                (b"AIUEOS_GUEST_BROWSER_DICT_GO", ["y", "a", "m", "a", "spc"], None),
                                (b"AIUEOS_GUEST_BROWSER_DICT_NEXT",
                                 ["spc", "esc", "spc", "ret", "s", "h", "o", "u", "spc", "spc", "ret"],
                                 "guest-browser-dictionary-converting.ppm")):
            if not (typing and go in serial_now) or globals().get(go) or (after and not globals().get(after)):
                continue
            globals()[go] = True
            for q in keys:
                for down in (True, False):
                    sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": [
                        {"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": q}}}]}})
                                  + "\n").encode())
                    recv_obj()
                    time.sleep(0.15)
            log("typed " + str(len(keys)) + " keys at " + go.decode())
        # The titlebar drag (ADR-0229): press at (60, 50) on 1280x800, moves to
        # (140, 90) (220, 120) (300, 150), release, one move after it. One
        # batch per event: the press batch is x + y + BTN + SYN, exactly the
        # four buffers the guest posts, so it only fits once the guest has
        # drained the ring (it does before DRAG_GO).
        if typing and b"AIUEOS_GUEST_BROWSER_DRAG_GO" in serial_now and not globals().get("drag_sent"):
            globals()["drag_sent"] = True
            def at(x, y):
                return [{"type": "abs", "data": {"axis": "x", "value": x}},
                        {"type": "abs", "data": {"axis": "y", "value": y}}]
            for b in (at(1536, 2048) + [{"type": "btn", "data": {"down": True, "button": "left"}}],
                      at(3584, 3687), at(5632, 4916), at(7680, 6144),
                      [{"type": "btn", "data": {"down": False, "button": "left"}}],
                      at(9728, 8192)):
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": b}})
                              + "\n").encode())
                recv_obj()
                time.sleep(0.3)
            log("dragged 6 pointer events at DRAG_GO")
        # The resize (ADR-0230): press at (984, 664) -- window 1's resize
        # handle after the drag -- moves to (784, 564) (300, 200) (504, 324),
        # release, one move after it. Same batching as the drag.
        if typing and b"AIUEOS_GUEST_BROWSER_RESIZE_GO" in serial_now and not globals().get("resize_sent"):
            globals()["resize_sent"] = True
            def at(x, y):
                return [{"type": "abs", "data": {"axis": "x", "value": x}},
                        {"type": "abs", "data": {"axis": "y", "value": y}}]
            for b in (at(25191, 27198) + [{"type": "btn", "data": {"down": True, "button": "left"}}],
                      at(20071, 23102), at(7680, 8192), at(12903, 13272),
                      [{"type": "btn", "data": {"down": False, "button": "left"}}],
                      at(23040, 28672)):
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": b}})
                              + "\n").encode())
                recv_obj()
                time.sleep(0.3)
            log("resized with 6 pointer events at RESIZE_GO")
        # The event loop (ADR-0231): k a Enter, a press on window 2's titlebar
        # at (150, 85), a move to (250, 185), a release, n i Enter. Each event
        # goes only after the guest's frame line for the one before it (and
        # that frame's screendump), half a second later: the order is ours,
        # and the loop is seen waiting between events.
        if typing and b"AIUEOS_GUEST_BROWSER_LOOP_GO" in serial_now and globals().get("loop_sent", 0) < 9:
            k = globals().get("loop_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_LOOP_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-loop-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                def at(x, y):
                    return [{"type": "abs", "data": {"axis": "x", "value": x}},
                            {"type": "abs", "data": {"axis": "y", "value": y}}]
                ev = (["k"], ["a"], ["ret"],
                      at(3840, 3482) + [{"type": "btn", "data": {"down": True, "button": "left"}}],
                      at(6400, 7578),
                      [{"type": "btn", "data": {"down": False, "button": "left"}}],
                      ["n"], ["i"], ["ret"])[k]
                if isinstance(ev[0], str):
                    for down in (True, False):
                        sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": [
                            {"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": ev[0]}}}]}})
                                      + "\n").encode())
                        recv_obj()
                        time.sleep(0.05)
                else:
                    sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                                  + "\n").encode())
                    recv_obj()
                globals()["loop_sent"] = k + 1
                log("loop event " + str(k + 1) + " sent")
        # The caret (ADR-0232): k a, then Backspace three times, each after
        # the guest's frame line for the key before (and its screendump).
        if typing and b"AIUEOS_GUEST_BROWSER_CARET_GO" in serial_now and globals().get("caret_sent", 0) < 5:
            k = globals().get("caret_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_CARET_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-caret-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                q = ("k", "a", "backspace", "backspace", "backspace")[k]
                for down in (True, False):
                    sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": [
                        {"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": q}}}]}})
                                  + "\n").encode())
                    recv_obj()
                    time.sleep(0.05)
                globals()["caret_sent"] = k + 1
                log("caret key " + str(k + 1) + " sent")
        # Launcher and close (ADR-0233): a press on launcher button 3 at
        # (258, 14), release, a press on window 3's close control at (584, 94),
        # release, the launcher again, release, a press on window 2's close
        # control at (820, 186), release -- each after the guest's frame line
        # for the one before (and its screendump).
        if typing and b"AIUEOS_GUEST_BROWSER_LAUNCH_GO" in serial_now and globals().get("launch_sent", 0) < 8:
            k = globals().get("launch_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_LAUNCH_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-launch-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                def press(x, y):
                    return [{"type": "abs", "data": {"axis": "x", "value": x}},
                            {"type": "abs", "data": {"axis": "y", "value": y}},
                            {"type": "btn", "data": {"down": True, "button": "left"}}]
                up = [{"type": "btn", "data": {"down": False, "button": "left"}}]
                ev = (press(6605, 574), up, press(14951, 3851), up,
                      press(6605, 574), up, press(20992, 7619), up)[k]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["launch_sent"] = k + 1
                log("launch event " + str(k + 1) + " sent")
        # The pointer (ADR-0236): moves to (400, 300) (700, 450) (1276, 796),
        # a press at (1000, 600) on no window, the release -- each after the
        # guest's frame line for the one before (and its screendump).
        if typing and b"AIUEOS_GUEST_BROWSER_CURSOR_GO" in serial_now and globals().get("cursor_sent", 0) < 5:
            k = globals().get("cursor_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_CURSOR_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-cursor-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                def at(x, y):
                    return [{"type": "abs", "data": {"axis": "x", "value": x}},
                            {"type": "abs", "data": {"axis": "y", "value": y}}]
                ev = (at(10240, 12288), at(17920, 18432), at(32666, 32605),
                      at(25600, 24576) + [{"type": "btn", "data": {"down": True, "button": "left"}}],
                      [{"type": "btn", "data": {"down": False, "button": "left"}}])[k]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["cursor_sent"] = k + 1
                log("cursor event " + str(k + 1) + " sent")
        # Alt+Tab (ADR-0237): a press on launcher button 2 at (150, 14), the
        # release, Alt down, Tab down / up three times, Alt up, a lone Tab down
        # and up -- each after the guest's frame line for the one before (and
        # its screendump). One key event per command: key + SYN fits the four
        # buffers the guest posts, and the guest reads releases here.
        if typing and b"AIUEOS_GUEST_BROWSER_FOCUS_GO" in serial_now and globals().get("focus_sent", 0) < 12:
            k = globals().get("focus_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_FOCUS_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-focus-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                def key(q, down):
                    return [{"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": q}}}]
                ev = ([{"type": "abs", "data": {"axis": "x", "value": 3840}},
                       {"type": "abs", "data": {"axis": "y", "value": 574}},
                       {"type": "btn", "data": {"down": True, "button": "left"}}],
                      [{"type": "btn", "data": {"down": False, "button": "left"}}],
                      key("alt", True), key("tab", True), key("tab", False),
                      key("tab", True), key("tab", False), key("tab", True), key("tab", False),
                      key("alt", False), key("tab", True), key("tab", False))[k]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["focus_sent"] = k + 1
                log("focus event " + str(k + 1) + " sent")
        # The keyboard stage (ADR-0247, 0248, 0249, 0250): after the damage stage,
        # F10 down and up twice (the high-contrast palette on, off), F6 down and
        # up twice (the focus ring on launcher button 1, 2), Shift+F6 (back to 1),
        # F6 (2), Enter down and up (button 2 pressed), Escape down and up (the
        # focused window closed), then the tablet: a double press on window 1's
        # titlebar at (380, 142) -- press, release, press, release -- and one at
        # (380, 40), a press on the maximize control at (476, 146), F11 down and up --
        # each after the guest's line for the one before.
        if typing and b"AIUEOS_GUEST_BROWSER_UIUX_GO" in serial_now and globals().get("uiux_sent", 0) < 106:
            k = globals().get("uiux_sent", 0)
            seen = ((b"AIUEOS_GUEST_BROWSER_HC n=%d " % k) if k <= 4 else
                    (b"AIUEOS_GUEST_BROWSER_KEY n=%d " % k) if k <= 18 else
                    (b"AIUEOS_GUEST_BROWSER_MAX n=%d " % k))
            if k == 0 or seen in serial_now:
                time.sleep(0.5)
                if k < 18:
                    qcode = ("f10", "f10", "f10", "f10", "f6", "f6", "f6", "f6", "shift", "f6", "f6", "shift",
                             "f6", "f6", "ret", "ret", "esc", "esc")[k]
                    down = (True, False, True, False, True, False, True, False, True, True, False, False,
                            True, False, True, False, True, False)[k]
                    ev = [{"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": qcode}}}]
                elif k < 26:
                    t = k - 18
                    if t % 2 == 0:
                        ay = 5817 if t < 4 else 1639
                        ev = [{"type": "abs", "data": {"axis": "x", "value": 9728}},
                              {"type": "abs", "data": {"axis": "y", "value": ay}},
                              {"type": "btn", "data": {"down": True, "button": "left"}}]
                    else:
                        ev = [{"type": "btn", "data": {"down": False, "button": "left"}}]
                elif k < 28:
                    # ADR-0251: a press on window 1's maximize control at (476, 146)
                    if k == 26:
                        ev = [{"type": "abs", "data": {"axis": "x", "value": 12186}},
                              {"type": "abs", "data": {"axis": "y", "value": 5981}},
                              {"type": "btn", "data": {"down": True, "button": "left"}}]
                    else:
                        ev = [{"type": "btn", "data": {"down": False, "button": "left"}}]
                elif k < 30:
                    # F11 down and up: the maximized window's control pressed from the keyboard
                    ev = [{"type": "key", "data": {"down": k == 28, "key": {"type": "qcode", "data": "f11"}}}]
                elif k < 32:
                    # ADR-0252: the pointer onto window 1's resize handle at (500, 320), then away
                    # to (380, 142): two abs events, no button
                    x, y = (12800, 13108) if k == 30 else (9728, 5817)
                    ev = [{"type": "abs", "data": {"axis": "x", "value": x}},
                          {"type": "abs", "data": {"axis": "y", "value": y}}]
                elif k == 32:
                    # ADR-0253: the button goes down on launcher button 1 at (54, 14)
                    ev = [{"type": "abs", "data": {"axis": "x", "value": 1383}},
                          {"type": "abs", "data": {"axis": "y", "value": 574}},
                          {"type": "btn", "data": {"down": True, "button": "left"}}]
                elif k >= 90:
                    # ADR-0259: Ctrl+Alt+Q signs out, then the PIN 4 2 4 2 and Enter sign in again
                    j = k - 90
                    if j < 6:
                        qc, dn = (("ctrl", True), ("alt", True), ("q", True), ("q", False), ("alt", False), ("ctrl", False))[j]
                    else:
                        qc = ("4", "4", "2", "2", "4", "4", "2", "2", "ret", "ret")[j - 6]
                        dn = (j - 6) % 2 == 0
                    ev = [{"type": "key", "data": {"down": dn, "key": {"type": "qcode", "data": qc}}}]
                elif k >= 60:
                    # ADR-0258: Ctrl+Alt+L locks; a press at (456, 146) and a key (x) are swallowed; a
                    # wrong PIN (4 2 4 3, Enter) is refused; the right one (4 2 4 2, Enter) unlocks
                    j = k - 60
                    if j < 6:
                        qc, dn = (("ctrl", True), ("alt", True), ("l", True), ("l", False), ("alt", False), ("ctrl", False))[j]
                        ev = [{"type": "key", "data": {"down": dn, "key": {"type": "qcode", "data": qc}}}]
                    elif j == 6:
                        ev = [{"type": "abs", "data": {"axis": "x", "value": 11674}},
                              {"type": "abs", "data": {"axis": "y", "value": 5981}},
                              {"type": "btn", "data": {"down": True, "button": "left"}}]
                    elif j == 7:
                        ev = [{"type": "btn", "data": {"down": False, "button": "left"}}]
                    else:
                        seq = ["x", "x", "4", "4", "2", "2", "4", "4", "3", "3", "ret", "ret",
                               "4", "4", "2", "2", "4", "4", "2", "2", "ret", "ret"]
                        qc = seq[j - 8]
                        ev = [{"type": "key", "data": {"down": (j - 8) % 2 == 0, "key": {"type": "qcode", "data": qc}}}]
                elif 44 <= k < 48:
                    # ADR-0256: Alt down, '-' down, '-' up, Alt up
                    qc = ("alt", "minus", "minus", "alt")[k - 44]
                    ev = [{"type": "key", "data": {"down": k in (44, 45), "key": {"type": "qcode", "data": qc}}}]
                elif k >= 34 and k % 2 == 0:
                    # ADR-0254: a press on window 1's minimize control at (456, 146), one at
                    # (380, 142) where the minimized window was, one on app 1's dock icon at
                    # (574, 772); each followed by the release
                    x, y = {34: (11674, 5981), 36: (9728, 5817), 38: (14695, 31622), 40: (11674, 5981), 42: (1536, 31949), 48: (1536, 31949), 50: (11674, 5981), 52: (13927, 3851), 54: (14951, 3851), 56: (1536, 31949), 58: (1536, 31949)}[k]
                    ev = [{"type": "abs", "data": {"axis": "x", "value": x}},
                          {"type": "abs", "data": {"axis": "y", "value": y}},
                          {"type": "btn", "data": {"down": True, "button": "left"}}]
                else:
                    ev = [{"type": "btn", "data": {"down": False, "button": "left"}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["uiux_sent"] = k + 1
                log("uiux event " + str(k + 1) + " sent")
        # ADR-0263: seventy-two keys for the text editing stage, after the keyboard-only stage: a short text typed,
        # then caret moves, insertion, selection, deletion, Enter and Ctrl+Z (see the frame model's edit-steps).
        if typing and b"AIUEOS_GUEST_BROWSER_EDIT_GO" in serial_now and globals().get("edit_sent", 0) < 72:
            k = globals().get("edit_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_EDIT n=%d " % k) in serial_now:
                time.sleep(0.5)
                qs = ['a', 'a', 'b', 'b', 'spc', 'spc', 'c', 'c', 'd', 'd', 'home', 'home', 'right', 'right', 'right', 'right', 'ctrl', 'right', 'right', 'ctrl', 'ctrl', 'left', 'left', 'ctrl', 'left', 'left', 'x', 'x', 'ctrl', 'z', 'z', 'ctrl', 'shift', 'right', 'right', 'shift', 'shift', 'right', 'right', 'shift', 'backspace', 'backspace', 'ctrl', 'z', 'z', 'ctrl', 'delete', 'delete', 'ret', 'ret', 'e', 'e', 'left', 'left', 'left', 'left', 'end', 'end', 'home', 'home', 'end', 'end', 'right', 'right', 'end', 'end', 'shift', 'home', 'home', 'shift', 'left', 'left']
                ds = [True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, True, False, False, True, True, False, False, True, False, True, False, True, True, False, False, True, True, False, False, True, True, False, False, True, False, True, True, False, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, False, True, True, False, False, True, False]
                ev = [{"type": "key", "data": {"down": ds[k], "key": {"type": "qcode", "data": qs[k]}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["edit_sent"] = k + 1
                log("edit event " + str(k + 1) + " sent")
        # ADR-0262: twenty-eight keys for the keyboard-only stage, after the scale stage: F6, Enter and Escape, down and up.
        if typing and b"AIUEOS_GUEST_BROWSER_RING_GO" in serial_now and globals().get("ring_sent", 0) < 28:
            k = globals().get("ring_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_RING n=%d " % k) in serial_now:
                time.sleep(0.5)
                press = (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24)
                # F6 F6 Enter  F6 F6 F6 F6  Enter  F6  Enter  F6  Enter  F6  Esc, each down then up
                keys = ["f6", "f6", "ret", "f6", "f6", "f6", "f6", "ret", "f6", "ret", "f6", "ret", "f6", "esc"]
                qc = keys[k // 2]
                ev = [{"type": "key", "data": {"down": k % 2 == 0, "key": {"type": "qcode", "data": qc}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["ring_sent"] = k + 1
                log("ring event " + str(k + 1) + " sent")
        # ADR-0261: sixteen keys for the UI scale stage, after the sign-out stage: F11, Ctrl down, '=' three
        # times (125, 150, 150), '-' twice (125, 100), Ctrl up, F11. Each waits for the guest's line for the one before.
        if typing and b"AIUEOS_GUEST_BROWSER_SCALE_GO" in serial_now and globals().get("scale_sent", 0) < 16:
            k = globals().get("scale_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_SCALE n=%d " % k) in serial_now:
                time.sleep(0.5)
                qc = ("f11", "f11", "ctrl", "equal", "equal", "equal", "equal", "equal", "equal",
                      "minus", "minus", "minus", "minus", "ctrl", "f11", "f11")[k]
                dn = (True, False, True, True, False, True, False, True, False,
                      True, False, True, False, False, True, False)[k]
                ev = [{"type": "key", "data": {"down": dn, "key": {"type": "qcode", "data": qc}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["scale_sent"] = k + 1
                log("scale event " + str(k + 1) + " sent")
        # ADR-0267: thirty-six key events for the layout stage, after the clock stage: US shift+2, 2, shift+a, shift+;, shift+',
        # F9 (JIS), shift+2, shift+', [, shift+;, F9 (US). Each waits for the guest's line for the one before.
        if typing and b"AIUEOS_GUEST_BROWSER_LAYOUT_GO" in serial_now and globals().get("layout_sent", 0) < 36:
            k = globals().get("layout_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_LAYOUT n=%d " % k) in serial_now:
                time.sleep(0.5)
                keys = []
                for mod, q in (("shift", "2"), (None, "2"), ("shift", "a"), ("shift", "semicolon"), ("shift", "apostrophe"),
                               (None, "f9"), ("shift", "2"), ("shift", "apostrophe"), (None, "bracket_left"),
                               ("shift", "semicolon"), (None, "f9")):
                    if mod: keys.append((mod, True))
                    keys.append((q, True)); keys.append((q, False))
                    if mod: keys.append((mod, False))
                qc, dn = keys[k]
                ev = [{"type": "key", "data": {"down": dn, "key": {"type": "qcode", "data": qc}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["layout_sent"] = k + 1
                log("layout event " + str(k + 1) + " sent")
        # ADR-0268: twelve key events for the notification stage, after the layout stage: F8 (dismiss the newest), F7 F7 (open and
        # close the list), F8, F7 F7, each down then up, each after the guest's line for the one before (the stage's first
        # three lines are its own frames: the baseline and the two posts).
        if typing and b"AIUEOS_GUEST_BROWSER_NOTIFY_GO" in serial_now and globals().get("notify_sent", 0) < 12:
            k = globals().get("notify_sent", 0)
            if (k == 0 and b"AIUEOS_GUEST_BROWSER_NOTIFY n=3 " in serial_now) or (k > 0 and (b"AIUEOS_GUEST_BROWSER_NOTIFY n=%d " % (k + 3)) in serial_now):
                time.sleep(0.5)
                qc = ("f8", "f7", "f7", "f8", "f7", "f7")[k // 2]
                ev = [{"type": "key", "data": {"down": k % 2 == 0, "key": {"type": "qcode", "data": qc}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["notify_sent"] = k + 1
                log("notify event " + str(k + 1) + " sent")
        # ADR-0273: the suspend stage, after the audio stage. The host takes a screendump of the awake desktop, presses the sleep key (the lid),
        # takes a screendump of the sleeping screen, presses the wake key, times the resume (key sent -> the guest's RESUME line) and takes a
        # screendump of the awake desktop again; the files and the timing sit beside the serial log.
        if typing and b"AIUEOS_GUEST_BROWSER_SUSPEND_GO" in serial_now and globals().get("suspend_phase", 0) == 0:
            time.sleep(1.0)
            def _shot(name):
                f = os.path.join(os.path.dirname(path), name)
                sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": f}}) + "\n").encode())
                recv_obj()
            def _key(qc):
                for dn in (True, False):
                    ev = [{"type": "key", "data": {"down": dn, "key": {"type": "qcode", "data": qc}}}]
                    sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}}) + "\n").encode())
                    recv_obj()
            _shot("suspend-before.ppm")
            _key("sleep")
            globals()["suspend_phase"] = 1
            globals()["suspend_key"] = _key
            globals()["suspend_shot"] = _shot
            log("suspend: sleep key sent")
        if typing and b"AIUEOS_GUEST_BROWSER_SUSPEND_ENTER" in serial_now and globals().get("suspend_phase", 0) == 1:
            time.sleep(1.0)
            globals()["suspend_shot"]("suspend-during.ppm")
            globals()["suspend_t0"] = time.time()
            globals()["suspend_key"]("wake")
            globals()["suspend_phase"] = 2
            log("suspend: wake key sent")
        if typing and b"AIUEOS_GUEST_BROWSER_SUSPEND_RESUME" in serial_now and globals().get("suspend_phase", 0) == 2:
            ms = int((time.time() - globals()["suspend_t0"]) * 1000)
            with open(os.path.join(os.path.dirname(path), "suspend-timing.txt"), "w") as tf:
                tf.write("resume_ms=%d\n" % ms)
            time.sleep(0.5)
            globals()["suspend_shot"]("suspend-after.ppm")
            globals()["suspend_key"]("f1")      # the guest holds the resumed frame until this
            globals()["suspend_phase"] = 3
            log("suspend: resumed in %d ms" % ms)
        # ADR-0272: four key events for the audio stage (when a sound card is attached): the volume-down key twice, down then up, after the
        # guest has played the first tone burst and each after the guest's line for the one before.
        if typing and b"AIUEOS_GUEST_BROWSER_AUDIO_PLAY n=1 " in serial_now and globals().get("audio_sent", 0) < 4:
            k = globals().get("audio_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_AUDIO_VOLUME n=%d " % k) in serial_now:
                time.sleep(0.5)
                ev = [{"type": "key", "data": {"down": k % 2 == 0, "key": {"type": "qcode", "data": "volumedown"}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["audio_sent"] = k + 1
                log("audio event " + str(k + 1) + " sent")
        # ADR-0270: ten key events for the passkey stage, after the notification stage: Ctrl+Alt+L (the lock), F3 (a passkey of
        # another device: refused), F4 (this device's passkey: the session opens), each down then up, each after the guest's line
        # for the one before.
        if typing and b"AIUEOS_GUEST_BROWSER_PASSKEY_GO" in serial_now and globals().get("passkey_sent", 0) < 10:
            k = globals().get("passkey_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_PASSKEY n=%d " % k) in serial_now:
                time.sleep(0.5)
                qc, dn = (("ctrl", True), ("alt", True), ("l", True), ("l", False), ("alt", False), ("ctrl", False),
                          ("f3", True), ("f3", False), ("f4", True), ("f4", False))[k]
                ev = [{"type": "key", "data": {"down": dn, "key": {"type": "qcode", "data": qc}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["passkey_sent"] = k + 1
                log("passkey event " + str(k + 1) + " sent")
        # ADR-0260/0265/0269: two keys (second boot) or six pointer events (first boot) after the notification stage. First boot (AIUEOS_SETTINGS_PHASE=1): F10 down and up,
        # the high-contrast choice goes on and is written to the volume. Second boot of the same volume
        # (PHASE=2): Alt down and up, which change nothing -- the frame is high-contrast because the
        # stored record says so.
        if typing and b"AIUEOS_GUEST_BROWSER_SETTINGS_GO" in serial_now and globals().get("settings_sent", 0) < (6 if os.environ.get("AIUEOS_SETTINGS_PHASE", "1") == "1" else 2):
            k = globals().get("settings_sent", 0)
            # the stage's first line (n=1) is the window opening by itself; each event waits for the line before it
            if (b"AIUEOS_GUEST_BROWSER_SETTINGS n=%d " % (k + 1)) in serial_now:
                time.sleep(0.5)
                phase = os.environ.get("AIUEOS_SETTINGS_PHASE", "1")
                if phase == "1":
                    # ADR-0269: first boot, three clicks on the lines of the settings window's body, each a press and a release:
                    # line 1 (contrast) at (200, 131), line 2 (scale) at (200, 151) -- both in the 1280 x 800 viewport -- and, after
                    # the scale is 125 % (viewport 1024 x 640), line 3 (network) at (200, 171). Absolute values are the pixel times
                    # 32768 over the viewport, rounded up so the guest's floor lands on the pixel.
                    pts = ((5120, 5366), (5120, 6185), (6400, 8756))
                    ax, ay = pts[k // 2]
                    if k % 2 == 0:
                        ev = [{"type": "abs", "data": {"axis": "x", "value": ax}},
                              {"type": "abs", "data": {"axis": "y", "value": ay}},
                              {"type": "btn", "data": {"down": True, "button": "left"}}]
                    else:
                        ev = [{"type": "btn", "data": {"down": False, "button": "left"}}]
                else:
                    ev = [{"type": "key", "data": {"down": k == 0, "key": {"type": "qcode", "data": "alt"}}}]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["settings_sent"] = k + 1
                log("settings event " + str(k + 1) + " sent")
        # Wheel scroll (ADR-0238): a press on launcher button 4 at (360, 14),
        # the release, a wheel notch toward the end there (over no window), a
        # move to (300, 300), six notches toward the end, seven toward the
        # start -- each after the guest's frame line for the one before (and
        # its screendump). A notch is the wheel button's press and release in
        # one command: REL_WHEEL (or the gear key), the release, SYN -- three
        # events, inside the four buffers the guest posts.
        if typing and b"AIUEOS_GUEST_BROWSER_SCROLL_GO" in serial_now and globals().get("scroll_sent", 0) < 17:
            k = globals().get("scroll_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_SCROLL_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-scroll-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                def notch(b):
                    return [{"type": "btn", "data": {"down": True, "button": b}},
                            {"type": "btn", "data": {"down": False, "button": b}}]
                ev = ([{"type": "abs", "data": {"axis": "x", "value": 9216}},
                       {"type": "abs", "data": {"axis": "y", "value": 574}},
                       {"type": "btn", "data": {"down": True, "button": "left"}}],
                      [{"type": "btn", "data": {"down": False, "button": "left"}}],
                      notch("wheel-down"),
                      [{"type": "abs", "data": {"axis": "x", "value": 7680}},
                       {"type": "abs", "data": {"axis": "y", "value": 12288}}])
                ev = (ev + (notch("wheel-down"),) * 6 + (notch("wheel-up"),) * 7)[k]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["scroll_sent"] = k + 1
                log("scroll event " + str(k + 1) + " sent")
        # Selection (ADR-0240): five wheel notches toward the end at the
        # pointer (300, 300) -- window 4's offset to 100, line 20 inside it --
        # then Shift down, Left down / up, Left down / up, Right down / up,
        # Left down / up, Shift up, Backspace down / up, each after the
        # guest's frame line for the one before (and its screendump). One key
        # event per command, as for Alt+Tab.
        if typing and b"AIUEOS_GUEST_BROWSER_SELECTION_GO" in serial_now and globals().get("selection_sent", 0) < 17:
            k = globals().get("selection_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_SELECTION_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-selection-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                def notch(b):
                    return [{"type": "btn", "data": {"down": True, "button": b}},
                            {"type": "btn", "data": {"down": False, "button": b}}]
                def key(q, down):
                    return [{"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": q}}}]
                ev = ((notch("wheel-down"),) * 5
                      + (key("shift", True), key("left", True), key("left", False),
                         key("left", True), key("left", False), key("right", True), key("right", False),
                         key("left", True), key("left", False), key("shift", False),
                         key("backspace", True), key("backspace", False)))[k]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["selection_sent"] = k + 1
                log("selection event " + str(k + 1) + " sent")
        # Clipboard (ADR-0241): Shift down, Left down / up three times, Shift
        # up, Ctrl down, C down / up, Ctrl up, Backspace down / up, Ctrl down,
        # V down / up three times, Ctrl up -- each after the guest's frame line
        # for the one before (and its screendump). One key event per command.
        if typing and b"AIUEOS_GUEST_BROWSER_CLIPBOARD_GO" in serial_now and globals().get("clipboard_sent", 0) < 22:
            k = globals().get("clipboard_sent", 0)
            if k == 0 or (b"AIUEOS_GUEST_BROWSER_CLIPBOARD_FRAME n=%d " % k) in serial_now:
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-clipboard-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                def key(q, down):
                    return [{"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": q}}}]
                def tap(q):
                    return (key(q, True), key(q, False))
                ev = ((key("shift", True),) + tap("left") * 3 + (key("shift", False), key("ctrl", True))
                      + tap("c") + (key("ctrl", False),) + tap("backspace") + (key("ctrl", True),)
                      + tap("v") * 3 + (key("ctrl", False),))[k]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["clipboard_sent"] = k + 1
                log("clipboard event " + str(k + 1) + " sent")
        # Damage (ADR-0242): after the clipboard, a tablet move to (320, 310),
        # Alt down, Tab down, Tab up, Alt up. After each FRAME line (the
        # damage only) the display is screendumped and F12 sent -- down, then
        # up, one command each; after the FULL line (the whole screen) it is
        # screendumped again and the next event sent. The gate compares
        # guest-browser-damage-<n>.ppm with guest-browser-damage-full-<n>.ppm.
        if typing and b"AIUEOS_GUEST_BROWSER_DAMAGE_GO" in serial_now:
            k = globals().get("damage_sent", 0)
            f = globals().get("damage_framed", 0)
            def key(q, down):
                return [{"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": q}}}]
            if f < k and (b"AIUEOS_GUEST_BROWSER_DAMAGE_FRAME n=%d " % k) in serial_now:
                shot = os.path.join(os.path.dirname(path), "guest-browser-damage-%d.ppm" % k)
                sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                              + "\n").encode())
                recv_obj()
                for down in (True, False):
                    sock.sendall((json.dumps({"execute": "input-send-event",
                                              "arguments": {"events": key("f12", down)}})
                                  + "\n").encode())
                    recv_obj()
                globals()["damage_framed"] = k
                log("damage frame " + str(k) + " screendumped, F12 sent")
            elif k < 5 and (k == 0 or (b"AIUEOS_GUEST_BROWSER_DAMAGE_FULL n=%d " % k) in serial_now):
                if k:
                    shot = os.path.join(os.path.dirname(path), "guest-browser-damage-full-%d.ppm" % k)
                    sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                                  + "\n").encode())
                    recv_obj()
                time.sleep(0.5)
                ev = ([{"type": "abs", "data": {"axis": "x", "value": 8192}},
                       {"type": "abs", "data": {"axis": "y", "value": 12698}}],
                      key("alt", True), key("tab", True), key("tab", False), key("alt", False))[k]
                sock.sendall((json.dumps({"execute": "input-send-event", "arguments": {"events": ev}})
                              + "\n").encode())
                recv_obj()
                globals()["damage_sent"] = k + 1
                log("damage event " + str(k + 1) + " sent")
            elif k == 5 and not globals().get("damage_full_last") and b"AIUEOS_GUEST_BROWSER_DAMAGE_FULL n=5 " in serial_now:
                shot = os.path.join(os.path.dirname(path), "guest-browser-damage-full-5.ppm")
                sock.sendall((json.dumps({"execute": "screendump", "arguments": {"filename": shot}})
                              + "\n").encode())
                recv_obj()
                for down in (True, False):
                    sock.sendall((json.dumps({"execute": "input-send-event",
                                              "arguments": {"events": key("f12", down)}})
                                  + "\n").encode())
                    recv_obj()
                globals()["damage_full_last"] = True
                log("damage frame 5 whole screen screendumped, F12 sent")
        i += 1
        # Guest browser desktop (ADR-0224): the screens a person can look at.
        # The kernel holds each desktop frame for a few seconds in this
        # profile; the injector watches the serial log and dumps the console
        # the moment the frame's line appears. Periodic dumps missed both
        # frames: the desktop is drawn in the last second before QEMU exits.
        if os.environ.get("AIUEOS_QMP_POINTER") == "1":
            try:
                serial_text = open(os.environ.get("AIUEOS_SERIAL_LOG", ""), "rb").read()
            except OSError:
                serial_text = b""
            outdir = os.path.dirname(path)
            for marker, name in ((b"AIUEOS_GUEST_BROWSER_TEXT_OK", "guest-browser-text.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_TEXT_RAISED_OK", "guest-browser-text-raised.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_TYPE_OK", "guest-browser-typed.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_PREEDIT_SHOWN", "guest-browser-preedit.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_PREEDIT_OK", "guest-browser-preedit-committed.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_IME_TOGGLE_OK", "guest-browser-ime-toggle.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_DRAG_OK", "guest-browser-drag.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_RESIZE_OK", "guest-browser-resize.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_LOOP_OK", "guest-browser-loop.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_CARET_OK", "guest-browser-caret.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_LAUNCH_OK", "guest-browser-launch.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_DICT_SHOWN", "guest-browser-dictionary-converting.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_DICT_OK", "guest-browser-dictionary.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_CURSOR_OK", "guest-browser-cursor.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_FOCUS_OK", "guest-browser-focus.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_SCROLL_OK", "guest-browser-scroll.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_SELECTION_OK", "guest-browser-selection.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_CLIPBOARD_OK", "guest-browser-clipboard.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_DAMAGE_OK", "guest-browser-damage.ppm"),
                                 (b"AIUEOS_GUEST_BROWSER_FLOW_OK", "guest-browser-flow.ppm")):
                if marker in serial_text and not globals().get(name):
                    globals()[name] = True
                    sock.sendall((json.dumps({"execute": "screendump",
                                              "arguments": {"filename": os.path.join(outdir, name)}})
                                  + "\n").encode())
                    log("screendump " + name + " " + json.dumps(recv_obj())[:200])
    except OSError as e:
        log("send-error " + str(e))
        break
    time.sleep(0.05)
log("sent " + str(i))
PY
    inject_pid=$!
  fi
  scanout_pid=
  if [ "${AIUEOS_GUEST_SCANOUT_TWO:-0}" = 1 ]; then
    AIUEOS_SCANOUT_DBUS_LOG="$out/guest-scanout-dbus.log" python3 - <<'PY' &
import os, subprocess, time
log_path = os.environ.get("AIUEOS_SCANOUT_DBUS_LOG", "")
def log(msg):
    if not log_path:
        return
    try:
        with open(log_path, "a") as f:
            f.write(msg + "\n")
    except OSError:
        pass
def gdbus(path, xoff):
    return subprocess.run(
        ["gdbus", "call", "--session", "-d", "org.qemu",
         "-o", path, "-m", "org.qemu.Display1.Console.SetUIInfo",
         "0", "0", str(xoff), "0", "1280", "800"],
        capture_output=True, text=True)
end = time.time() + 90
while time.time() < end:
    ping = subprocess.run(
        ["gdbus", "call", "--session", "-d", "org.qemu",
         "-o", "/org/qemu/Display1/VM",
         "-m", "org.freedesktop.DBus.Peer.Ping"],
        capture_output=True, text=True)
    if ping.returncode == 0:
        a = gdbus("/org/qemu/Display1/Console_0", 0)
        b = gdbus("/org/qemu/Display1/Console_1", 1280)
        log("set0 rc=%s %r set1 rc=%s %r" % (
            a.returncode, (a.stdout + a.stderr)[:200],
            b.returncode, (b.stdout + b.stderr)[:200]))
    time.sleep(0.05)
PY
    scanout_pid=$!
  fi
  set +e
  qemu_started=$(date +%s)
  quiet_fired=
  loop_reached=
  # shellcheck disable=SC2086 # intentional optional groups of QEMU arguments
  timeout "$qemu_timeout" "$qemu" \
    -machine q35,accel=tcg -cpu max -m 128M -smp 2 \
    -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
    -drive "$boot_drive" $update_drive_args \
    -device isa-debugcon,iobase=0xe9,chardev=debug \
    -chardev file,id=debug,path="$log" \
    -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
    $iommu_args \
    $tpm_args \
    $usb_args \
    $net_args \
    $audio_args \
    -device virtio-rng-pci \
    -drive if=none,id=aiueosblk,format=raw,file="$blk_image" \
    -device virtio-blk-pci,drive=aiueosblk,disable-legacy=on \
    $kbd_args \
    -device virtio-vga,id=aiueosvga,disable-legacy=on,max_outputs=2 \
    $qmp_args \
    -display "$display_opt" -serial "file:$serial_log" -monitor none -no-reboot &
  qemu_pid=$!
  # The watchdog. It reads the mtime of BOTH logs, because measuring quiet on
  # debugcon alone reports the guest silent while it is writing to serial --
  # and on this firmware the OVMF exception dump goes to serial, so a
  # debugcon-only reader concludes a dying guest said nothing at all.
  # Before any output the clock runs from QEMU start, so a guest that never
  # writes is caught too (that one IS retryable: nothing was measured).
  while kill -0 "$qemu_pid" 2>/dev/null; do
    sleep 5
    kill -0 "$qemu_pid" 2>/dev/null || break
    #54ac566 (S4, JUN-144) changed the end of a NORMAL boot: the end-of-boot
    # probe no longer exits the machine -- it yields its slot to the
    # persistent desktop loop and the guest stays up (aiueos#436). A gate
    # whose evidence is complete at that marker opts in with
    # AIUEOS_LOOP_EXIT_OK=1: the attempt ends here and is scored as the
    # normal boot it replaces, instead of running out the wall clock and
    # being normalised to a 124 timeout. Gates that drive the loop (key
    # injection, post-loop exits) leave the flag unset and are untouched.
    if [ -n "${AIUEOS_LOOP_EXIT_OK:-}" ] && [ -z "$loop_reached" ]; then
      for loop_file in "$serial_log" "$log"; do
        if [ -f "$loop_file" ] && grep -a -q -F "AIUEOS_DESKTOP_LOOP_OK" "$loop_file" 2>/dev/null; then
          loop_reached=1
          break
        fi
      done
      if [ -n "$loop_reached" ]; then
        sleep 2   # let the marker's own writes land on both transports
        kill -TERM "$qemu_pid" 2>/dev/null || true
        break
      fi
    fi
    watchdog_now=$(date +%s)
    watchdog_seen=$qemu_started
    for watchdog_file in "$serial_log" "$log"; do
      if [ -f "$watchdog_file" ]; then
        # Pick the mtime by VALIDATING THE FORMAT, not the exit code. GNU
        # coreutils stat (which is first on PATH here) reads -f as "filesystem
        # status", complains that %m is not a filesystem format, prints the
        # blob for the file anyway -- and EXITS 0. So an exit-code fallback
        # never fires and watchdog_t silently becomes that blob.
        watchdog_t=$(stat -f %m "$watchdog_file" 2>/dev/null | head -1)
        case ${watchdog_t:-} in ''|*[!0-9]*)
          watchdog_t=$(stat -c %Y "$watchdog_file" 2>/dev/null | head -1) ;;
        esac
        case ${watchdog_t:-} in ''|*[!0-9]*) watchdog_t=0 ;; esac
        # Both operands defaulted: an empty one makes `[ -gt ]` print
        # "<number>: integer expression expected" once per watchdog tick, which
        # buried the SSH gates' actual verdict under hundreds of lines of it.
        # The watchdog then also silently stops advancing, so a quiet guest is
        # measured from the wrong instant.
        [ "${watchdog_t:-0}" -gt "${watchdog_seen:-0}" ] && watchdog_seen=$watchdog_t
      fi
    done
    if [ $(( watchdog_now - watchdog_seen )) -ge "$quiet_limit" ]; then
      quiet_fired=$(( watchdog_now - watchdog_seen ))
      kill -TERM "$qemu_pid" 2>/dev/null || true
      break
    fi
  done
  wait "$qemu_pid"
  status=$?
  # Keep every scenario's serial output, not just the last one's. AFTER
  # status=$? on purpose -- a cat here would clobber the exit code this whole
  # function is built to read.
  #
  # $serial_log is one path reused by every scenario, so each run overwrites the
  # last and no surviving file holds what the suite proved. That is not a
  # cosmetic loss: measured 2026-09-09, a run with AIUEOS_TEST_NET=1 and
  # AIUEOS_TEST_DMAR=1 exited 0 -- which those switches only permit when
  # AIUEOS_DHCP_OK, AIUEOS_VTD_OK and AIUEOS_DMA_POLICY_OK are all present,
  # since the gates below assert them by grep -- yet the file left on disk
  # afterwards held four markers from a later, shorter scenario and none of
  # those three. The suite proved capabilities its own evidence could not show.
  # BOTH logs. The guest writes to two transports and they do not carry the
  # same markers: the loader stage reports AIUEOS_KERNEL_OK and
  # AIUEOS_LOADER_INTEGRITY_OK on debugcon and never on serial, so an
  # accumulator that took only $serial_log was collecting half the evidence and
  # reporting the other half as unproven. Measured 2026-09-09.
  cat "$serial_log" >> "$out/evidence-all.log" 2>/dev/null || true
  cat "$log"        >> "$out/evidence-all.log" 2>/dev/null || true
  # Normalised to 124 on purpose: every branch below, and fifteen sibling
  # scripts, already know what 124 means. WHICH limit ended the attempt is
  # carried in $quiet_fired and reported, not encoded in a new status nobody
  # downstream reads.
  if [ -n "$quiet_fired" ]; then status=124; fi
  # The persistent desktop loop is the normal boot's terminal state since
  # 54ac566; when the gate opted in and the marker was reached, the attempt
  # is scored as the end-of-boot success the machine used to exit with (97).
  # Every other status keeps its exact per-mode contract (133/255/209/251/
  # 185/227 below), and a 124 without the marker stays a real failure.
  if [ -n "$loop_reached" ]; then status=97; fi
  qemu_elapsed=$(( $(date +%s) - qemu_started ))
  # Every boot's wall clock, appended, so the timeout above stays a
  # measurement. A run that reports "timed out" without saying how long it
  # waited cannot be compared with the runs that passed.
  echo "boot status=$status elapsed=${qemu_elapsed}s attempt=$attempt" >> "$boot_times"
  if [ -n "$inject_pid" ]; then
    kill "$inject_pid" 2>/dev/null || true
    wait "$inject_pid" 2>/dev/null || true
  fi
  if [ -n "$scanout_pid" ]; then
    kill "$scanout_pid" 2>/dev/null || true
    wait "$scanout_pid" 2>/dev/null || true
  fi
  set -e
  if [ "$status" -ne 124 ]; then break; fi

  # The guest did not terminate. WHICH of three things happened is decided
  # here, from what the guest actually wrote, and only two of them are
  # retried. Before ADR-0200 this branch asked one question -- "was it a
  # timeout?" -- and a dead kernel and a lost wakeup gave the same answer.
  timeout_kind=
  # WHEN the guest last wrote, on either stream -- the write timeline, not the
  # exit status, is what separates a dead guest from a slow one. It is
  # reported and never used to kill a boot: a healthy full-evidence boot has a
  # genuine ~60s stretch with no write on either transport immediately before
  # its final marker (measured by BISECT-SHA256, 2026-09-03), so any
  # quiet-threshold short enough to be useful would also be short enough to
  # kill boots that are working.
  last_write=0
  for f in "$serial_log" "$log"; do
    if [ -f "$f" ]; then
      t=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f" 2>/dev/null || echo 0)
      # Same coreutils-stat trap the watchdog loop guards against (0b79c66):
      # `stat -f %m` exits 0 printing a non-numeric blob, so the `|| stat -c`
      # fallback never fires and `[ "$t" -gt ... ]` reports "Illegal number"
      # once -- and last_write silently stays 0, misreporting quiet_for.
      case ${t:-} in ''|*[!0-9]*)
        t=$(stat -c %Y "$f" 2>/dev/null) ;;
      esac
      case ${t:-} in ''|*[!0-9]*) t=0 ;; esac
      [ "$t" -gt "$last_write" ] && last_write=$t
    fi
  done
  if [ "$last_write" -gt 0 ]; then
    quiet_for=$(( $(date +%s) - last_write ))
    wrote_at=$(( last_write - qemu_started ))
  else
    quiet_for=$qemu_elapsed
    wrote_at=-1
  fi
  fatal_line=$(grep -a -h -m1 -F "AIUEOS_FATAL_EXCEPTION" "$serial_log" "$log" 2>/dev/null | \
                 tr -d '\r' || true)
  last_serial=$(tr -d '\r' < "$serial_log" 2>/dev/null | grep -a -v '^[[:space:]]*$' | tail -1 || true)
  last_debug=$(tr -d '\r' < "$log" 2>/dev/null | grep -a -v '^[[:space:]]*$' | tail -1 || true)
  if [ -n "$fatal_line" ]; then
    # The kernel named its own death and then failed to leave: isa-debug-exit
    # is absent or the write did not take. Either way it is not a flake.
    timeout_kind=GUEST-DIED
  elif [ -n "$last_serial" ] || [ -n "$last_debug" ]; then
    case "$last_serial" in
      # AIUEOS_PROCESS_PHASE_ (2026-10-24): the guest now names its ring-3
      # wait-loop silence point (#108), so a #108 hang's last line is one of
      # those diagnostics rather than the marker itself. Same signature.
      "$flake_signature"*|AIUEOS_PROCESS_PHASE_*) timeout_kind=HOST-FLAKE-SIGNATURE ;;
      *) timeout_kind=GUEST-NO-EXIT ;;
    esac
  else
    # Not one byte on either transport: the firmware never reached the debug
    # console. Nothing about the guest was measured, so this is the one
    # timeout a second attempt can legitimately answer.
    timeout_kind=HOST-NO-OUTPUT
  fi
  case "$timeout_kind" in
    HOST-FLAKE-SIGNATURE|HOST-NO-OUTPUT)
      if [ "$attempt" -lt "$qemu_attempts" ]; then
        echo "warning: ${timeout_kind} on attempt ${attempt}/${qemu_attempts} after ${qemu_elapsed}s; retrying" >&2
        echo "         last serial line: ${last_serial:-<none>}" >&2
        attempt=$((attempt + 1))
        continue
      fi
      ;;
  esac
  break
done
[ -n "$pristine_blk" ] && rm -f "$pristine_blk"
if [ -n "$aiueos_dbus_pid" ]; then
  kill "$aiueos_dbus_pid" 2>/dev/null || true
fi

if [ "$status" -eq 124 ]; then
  # Outcome (b): the guest ran and then stopped. Named, with the elapsed time
  # and the last thing the guest said, so a reader can tell a dead kernel from
  # a slow one without re-running anything.
  case "$timeout_kind" in
    GUEST-DIED)
      echo "GUEST-DIED after ${qemu_elapsed}s: the kernel reported a fatal exception and did not exit" >&2
      echo "  $fatal_line" >&2
      ;;
    GUEST-NO-EXIT)
      echo "GUEST-NO-EXIT after ${qemu_elapsed}s (attempts=${attempt}): the guest produced output and then stopped" >&2
      echo "  last serial: ${last_serial:-<none>}" >&2
      echo "  last debug : ${last_debug:-<none>}" >&2
      echo "  NOT kotoba-lang/aiueos#108: that hang stops at ${flake_signature}." >&2
      ;;
    HOST-FLAKE-SIGNATURE)
      echo "GUEST-NO-EXIT after ${qemu_elapsed}s (attempts=${attempt}): every attempt stopped at ${flake_signature}" >&2
      echo "  This IS the kotoba-lang/aiueos#108 signature and it did not clear on a retry." >&2
      ;;
    HOST-NO-OUTPUT)
      echo "HOST-NO-OUTPUT after ${qemu_elapsed}s (attempts=${attempt}): the guest wrote nothing on either transport" >&2
      ;;
    *)
      echo "GUEST-NO-EXIT after ${qemu_elapsed}s: unclassified timeout" >&2
      ;;
  esac
  if [ -n "$quiet_fired" ]; then
    echo "  ended by: the quiescence watchdog, after ${quiet_fired}s with no byte on either transport (limit ${quiet_limit}s)" >&2
  else
    echo "  ended by: the wall clock, ${qemu_timeout}s" >&2
  fi
  if [ "$wrote_at" -ge 0 ]; then
    echo "  write timeline: last byte on either transport at T+${wrote_at}s, then ${quiet_for}s of silence" >&2
  else
    echo "  write timeline: no byte on either transport in ${qemu_elapsed}s" >&2
  fi
  echo "--- debug log tail ---" >&2
  test -f "$log" && tail -40 "$log" >&2
  echo "--- serial log tail ---" >&2
  test -f "$serial_log" && sed 's/\x1b\[[0-9;=]*[A-Za-z]//g' "$serial_log" | tail -40 >&2
  exit 1
fi

if [ "${AIUEOS_PLC_RT_SMOKE:-0}" = 1 ]; then
  [ "$status" -eq 133 ] || {
    echo "error: PLC RT smoke produced unexpected QEMU status $status" >&2
    test -f "$serial_log" && tail -30 "$serial_log" >&2
    exit 1
  }
  grep -F "AIUEOS_PLC_RT_OK profile=aiueos-plc-v1 scheduler=fixed-priority-preemptive priority=5 program=signed-cpl3-elf signature=ecdsa-p256-sha256 tamper=rejected scans=100 inputs=alternating-enable,sensor41..140 transport=syscall release=apic-absolute-ticks cycle=10ticks input=snapshot output=atomic-safe-state capabilities=16,17,18,19 failures=stage,watchdog,budget,deadline,program timing=logical-unqualified" "$serial_log" >/dev/null || {
    echo "error: native PLC RT provider evidence was not observed" >&2
    exit 1
  }
  echo "AIUEOS_PLC_RT_QEMU_OK scans=100 signed-elf tamper-rejected fixed-priority-preemption native-provider apic-release transactional-output safe-state"
  exit 0
fi

if [ "${AIUEOS_CORRUPT_KERNEL:-0}" = 1 ]; then
  [ "$status" -eq 255 ] || {
    echo "error: corrupted kernel produced unexpected QEMU status $status" >&2
    exit 1
  }
  grep -F "AIUEOS_LOADER_FAIL kernel-sha256" "$log" >/dev/null || {
    echo "error: corrupted kernel was not rejected by loader" >&2
    exit 1
  }
  echo "AIUEOS_KERNEL_INTEGRITY_REJECTION_OK"
  exit 0
fi

if [ "${AIUEOS_CORRUPT_INITRAMFS:-0}" = 1 ]; then
  [ "$status" -eq 255 ] || {
    echo "error: corrupted initramfs produced unexpected QEMU status $status" >&2
    exit 1
  }
  grep -F "AIUEOS_LOADER_FAIL initramfs-sha256" "$log" >/dev/null || {
    echo "error: corrupted initramfs was not rejected by loader" >&2
    exit 1
  }
  echo "AIUEOS_INITRAMFS_INTEGRITY_REJECTION_OK"
  exit 0
fi

if [ "${AIUEOS_CORRUPT_RECOVERY_SIG:-0}" = 1 ]; then
  # The kernel policy rejection writes 0x68; isa-debug-exit maps it to 209.
  [ "$status" -eq 209 ] || {
    echo "error: corrupted recovery signature produced unexpected QEMU status $status" >&2
    test -f "$serial_log" && tail -20 "$serial_log" >&2
    exit 1
  }
  grep -F "AIUEOS_INITRAMFS_RECOVERY_ADMISSION_FAIL rsa2048-policy" "$serial_log" >/dev/null || {
    echo "error: recovery payload with a bad signature was not rejected by the kernel policy" >&2
    exit 1
  }
  echo "AIUEOS_INITRAMFS_RECOVERY_REJECTION_OK rsa2048-policy"
  exit 0
fi

if [ "${AIUEOS_EXPECT_FAULT:-0}" = 1 ]; then
  # The unexpected-exception path writes 0x7d; isa-debug-exit maps it to 251.
  [ "$status" -eq 251 ] || {
    echo "error: synthetic fault produced unexpected QEMU status $status" >&2
    test -f "$serial_log" && tail -20 "$serial_log" >&2
    exit 1
  }
  grep -F "AIUEOS_FAULT_SMOKE synthetic unexpected-ud2" "$serial_log" >/dev/null || {
    echo "error: synthetic fault trigger marker was not observed" >&2
    exit 1
  }
  grep -F "AIUEOS_FAULT_RECEIPT_OK polled try-lock written readback pending" "$serial_log" >/dev/null || {
    echo "error: fault-context crash receipt write evidence was not observed" >&2
    exit 1
  }
  echo "AIUEOS_FAULT_BOOT_OK synthetic-fault polled-receipt-written"
  exit 0
fi

if [ "${AIUEOS_EXPECT_CRASH:-0}" = 1 ]; then
  # The synthetic panic writes 0x5c; isa-debug-exit maps it to (0x5c << 1) | 1.
  [ "$status" -eq 185 ] || {
    echo "error: synthetic panic produced unexpected QEMU status $status" >&2
    test -f "$serial_log" && tail -20 "$serial_log" >&2
    exit 1
  }
  grep -F "AIUEOS_PANIC synthetic reason=42" "$serial_log" >/dev/null || {
    echo "error: synthetic panic marker was not observed" >&2
    exit 1
  }
  grep -F "AIUEOS_PANIC_RECEIPT_OK synthetic reason=42 written readback pending" "$serial_log" >/dev/null || {
    echo "error: durable crash receipt write evidence was not observed" >&2
    exit 1
  }
  echo "AIUEOS_CRASH_PANIC_BOOT_OK synthetic-panic receipt-written"
  exit 0
fi

# Outcome (b) by the other road: the guest DID exit, deliberately, because a
# CPU exception was fatal. Say so with the kernel's own line FIRST -- this
# used to arrive as an eighty-line dump of a debug log whose last useful entry
# had been written by the firmware. AIUEOS_EXPECT_FAULT is the gate that asks
# for exactly this, so it keeps its own handling below.
guest_fatal=$(grep -a -h -m1 -F "AIUEOS_FATAL_EXCEPTION" "$serial_log" "$log" 2>/dev/null | \
                tr -d '\r' || true)
if [ -n "$guest_fatal" ] && [ "${AIUEOS_EXPECT_FAULT:-0}" != 1 ]; then
  echo "GUEST-DIED after ${qemu_elapsed}s: the guest terminated on a fatal CPU exception" >&2
  echo "  $guest_fatal" >&2
  echo "--- serial log tail ---" >&2
  test -f "$serial_log" && sed 's/\x1b\[[0-9;=]*[A-Za-z]//g' "$serial_log" | tail -20 >&2
  exit 1
fi

# The #UD handler writes 0x30; isa-debug-exit maps it to (0x30 << 1) | 1 = 97.
[ "$status" -eq 97 ] || {
  if [ "${AIUEOS_CORRUPT_KOTOBA_CATALOG:-0}" = 1 ] && [ "$status" -eq 227 ]; then
    ! grep -F "AIUEOS_KOTOBA_APP_ADMISSION_OK" "$serial_log" >/dev/null || {
      echo "error: corrupted Kotoba catalog reached admission" >&2; exit 1;
    }
    echo "AIUEOS_KOTOBA_APP_AUTH_REJECTION_OK catalog"
    exit 0
  fi
  echo "error: unexpected QEMU exit status $status" >&2
  test -f "$log" && sed -n '1,80p' "$log" >&2
  exit 1
}

if [ "${AIUEOS_ECDSA_PUBLIC_KAT:-0}" = 1 ]; then
  grep -F "AIUEOS_ECDSA_PUBLIC_OK rfc6979-a2.5 x||y-match" "$serial_log" >/dev/null || {
    echo "error: Kotoba P-256 public-key derivation KAT marker was not observed" >&2
    test -f "$serial_log" && tail -40 "$serial_log" >&2
    exit 1
  }
  echo "AIUEOS_ECDSA_PUBLIC_SMOKE_OK rfc6979-a2.5 x||y-match"
  exit 0
fi

if [ "${AIUEOS_ECDSA_SIGN_KAT:-0}" = 1 ]; then
  grep -F "AIUEOS_ECDSA_SIGN_OK rfc6979-a2.5 r||s-match" "$serial_log" >/dev/null || {
    echo "error: Kotoba P-256 signature KAT marker was not observed" >&2
    test -f "$serial_log" && tail -40 "$serial_log" >&2
    exit 1
  }
  echo "AIUEOS_ECDSA_SIGN_SMOKE_OK rfc6979-a2.5 r||s-match"
  exit 0
fi

# A corrupted application payload or signature is no longer fatal: the kernel
# must restore it from the initramfs recovery materials under the catalog
# digest and RSA policy, then pass the complete evidence gate below.
if [ "${AIUEOS_CORRUPT_KOTOBA_APP:-0}" = 1 ] || [ "${AIUEOS_CORRUPT_KOTOBA_SIGNATURE:-0}" = 1 ]; then
  grep -F "AIUEOS_OBJECT_STORE_RESTORE_OK apps=1 source=initramfs catalog-digest-bound rsa2048 write-readback" "$serial_log" >/dev/null || {
    echo "error: corrupted application was not restored from the initramfs" >&2
    exit 1
  }
fi
grep -F "AIUEOS_LOADER_OK" "$log" >/dev/null || {
  echo "error: loader identity was not observed" >&2
  exit 1
}
grep -F "AIUEOS_GOP_HANDOFF_OK framebuffer-v1" "$log" >/dev/null || {
  echo "error: loader did not hand off a validated GOP mode" >&2
  exit 1
}
grep -F "AIUEOS_LOADER_INTEGRITY_OK sha256-v1" "$log" >/dev/null || {
  echo "error: kernel integrity evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KERNEL_OK memory-map-v1" "$log" >/dev/null || {
  echo "error: kernel handoff was not observed" >&2
  exit 1
}
grep -F "AIUEOS_INITRAMFS_OK newc entries=5 sha256-admitted bounded" "$serial_log" >/dev/null || {
  echo "error: bounded initramfs validation evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK elf digest=kotoba-sha256 signature=kotoba-rsa2048-pkcs1 policy=public-key" "$serial_log" >/dev/null || {
  echo "error: recovery payload admission evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SERIAL_OK stack-v1 memory-map-v1" "$serial_log" >/dev/null || {
  echo "error: kernel COM1 evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,80p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_NATIVE_OK elf64-relocatable sysv-v1 result=42" "$serial_log" >/dev/null || {
  echo "error: Kotoba compiler-emitted native probe did not execute" >&2
  exit 1
}
grep -F "AIUEOS_DESCRIPTOR_TABLES_OK gdt-v1 idt-v1" "$serial_log" >/dev/null || {
  echo "error: kernel descriptor-table evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp" "$serial_log" >/dev/null || {
  echo "error: kernel-owned paging evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_FRAMEBUFFER_OK gop-owned retained-rectangles hash-verified" "$serial_log" >/dev/null || {
  echo "error: kernel did not validate and render the GOP framebuffer" >&2
  exit 1
}
grep -F "AIUEOS_DESKTOP_SURFACE_OK envelope-v1 opaque-handle full-damage hash-verified" "$serial_log" >/dev/null || {
  echo "error: bounded desktop surface envelope was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PHYSICAL_ALLOCATOR_OK pages=2 zeroed" "$serial_log" >/dev/null || {
  echo "error: physical page allocator evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_ACPI_RETAIN_OK source=firmware copy=low-identity tables=APIC+DMAR" "$log" >/dev/null || {
  echo "error: loader did not retain ACPI below the bootstrap identity limit" >&2
  exit 1
}
grep -F "AIUEOS_ACPI_OK rsdp-xsdt-madt cpu>=2" "$serial_log" >/dev/null || {
  echo "error: validated ACPI CPU discovery evidence was not observed" >&2
  exit 1
}
if [ "${AIUEOS_TEST_DMAR:-0}" = 1 ]; then
  grep -F "AIUEOS_VTD_OK tes=1 root-context-slpt domain=1 aperture=128MiB" "$serial_log" >/dev/null || {
    echo "error: VT-d translation-enable register evidence was not observed" >&2; exit 1;
  }
  grep -F "AIUEOS_DMA_POLICY_OK dmar=validated dma=vtd-isolated" "$serial_log" >/dev/null || {
    echo "error: isolated VT-d DMA policy evidence was not observed" >&2; exit 1;
  }
else
  grep -F "AIUEOS_DMA_POLICY_OK dmar=absent test-only-unisolated" "$serial_log" >/dev/null || {
    echo "error: explicit no-IOMMU test DMA policy evidence was not observed" >&2; exit 1;
  }
fi
grep -F "AIUEOS_APIC_TIMER_OK vector=32 eoi-v1" "$serial_log" >/dev/null || {
  echo "error: Local APIC timer interrupt evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SMP_OK cpus=2 init-sipi-v1 per-cpu-stack" "$serial_log" >/dev/null || {
  echo "error: BSP-to-AP INIT/SIPI evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PCI_OK bounded-scan virtio-vendor=1af4" "$serial_log" >/dev/null || {
  echo "error: bounded PCI/virtio discovery evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,160p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_VIRTIO_RNG_OK modern-pci caps-bounded dma=4pages completion=32" "$serial_log" >/dev/null || {
  echo "error: modern virtio-rng DMA completion evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,120p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_VIRTIO_RNG_MSIX_OK vector=34 irq=1 table-pba-bounded" "$serial_log" >/dev/null || {
  echo "error: interrupt-driven virtio-rng MSI-X evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,140p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_VIRTIO_BLK_OK capacity-bounded sector=0 bytes=512 readonly" "$serial_log" >/dev/null || {
  echo "error: modern virtio-blk bounded read evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,140p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_VIRTIO_BLK_MSIX_OK vector=35 irq-completions-bounded table-pba-bounded" "$serial_log" >/dev/null || {
  echo "error: interrupt-driven virtio-blk MSI-X completion evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,160p' "$serial_log" >&2
  exit 1
}
if [ "${AIUEOS_TEST_DMAR:-0}" = 1 ]; then
  grep -F "AIUEOS_VTD_IR_OK irta=256 source-validated vector=35 remappable-msix" "$serial_log" >/dev/null || {
    echo "error: VT-d interrupt-remapped MSI-X evidence was not observed" >&2; exit 1;
  }
fi
grep -F "AIUEOS_OBJECT_STORE_OK aiuefs-v3 objects=3 catalog=2apps" "$serial_log" >/dev/null || {
  echo "error: bounded read-only object-store evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_APP_ADMISSION_OK catalog=rsa2048 apps=2 digest=kotoba-sha256 signature=kotoba-rsa2048-pkcs1 policy=public-key" "$serial_log" >/dev/null || {
  echo "error: authenticated object-store Kotoba app admission was not observed" >&2
  exit 1
}
# The catalog-policy self-test is a test-only compile gate. The update-flow
# smoke boots a previous-version image built without it and asserts the
# marker's absence to prove which version booted.
if [ "${AIUEOS_EXPECT_CATALOG_POLICY_SELFTEST:-1}" = 1 ]; then
  grep -F "AIUEOS_KOTOBA_CATALOG_POLICY_SELFTEST_OK malformed=6" "$serial_log" >/dev/null || {
    echo "error: Kotoba catalog policy malformed-input evidence missing" >&2
    cat "$serial_log" >&2
    exit 1
  }
else
  ! grep -F "AIUEOS_KOTOBA_CATALOG_POLICY_SELFTEST_OK" "$serial_log" >/dev/null || {
    echo "error: unexpected catalog-policy self-test evidence in previous-version boot" >&2
    exit 1
  }
fi
grep -F "AIUEOS_JOURNAL_OK dual-slot committed append-readback" "$serial_log" >/dev/null || {
  echo "error: journal write/readback evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_OBJECT_TXN_OK journal-first sector=3 apply-readback route=kotoba fixed-stack" "$serial_log" >/dev/null || {
  echo "error: journal-backed object transaction evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_JOURNAL_PLAN_OK" "$serial_log" >/dev/null || {
  echo "error: Kotoba-native journal planning evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_FNV_OK bounded-load journal-object-validation" "$serial_log" >/dev/null || {
  echo "error: Kotoba-native bounded FNV evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_RECORD_VALIDATION_OK journal transaction bounded-u32" "$serial_log" >/dev/null || {
  echo "error: Kotoba-native record validation evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_STORAGE_READ_VALIDATION_OK superblock mutable-object" "$serial_log" >/dev/null || {
  echo "error: Kotoba-native storage read validation evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_STORAGE_WRITE_OK journal mutable-object bounded-store" "$serial_log" >/dev/null || {
  echo "error: Kotoba-native storage write evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_PCI_PLANNER_OK cap extent msix-region" "$serial_log" >/dev/null || {
  echo "error: Kotoba-native PCI planner evidence was not observed" >&2
  exit 1
}
if [ "${AIUEOS_GUEST_INPUT:-0}" = 1 ]; then
  grep -F "AIUEOS_VIRTIO_INPUT_OK modern-pci eventq configured used-ring" "$serial_log" >/dev/null || {
    echo "error: virtio-input used-ring evidence was not observed" >&2; exit 1;
  }
  grep -F "AIUEOS_GUEST_INPUT_OK eventq-used=1 synthetic=0" "$serial_log" >/dev/null || {
    echo "error: guest-input used-ring serial was not observed" >&2; exit 1;
  }
  if [ "${AIUEOS_GUEST_BROWSER:-0}" = 1 ]; then
    grep -F "AIUEOS_GUEST_BROWSER_INPUT_OK eventq-used=1 kind=pointer-down" "$serial_log" >/dev/null || {
      echo "error: guest browser pointer serial was not observed" >&2; exit 1;
    }
  fi
else
  grep -F "AIUEOS_VIRTIO_INPUT_OK modern-pci eventq configured synthetic-smoke" "$serial_log" >/dev/null || {
    echo "error: modern virtio-input configuration/synthetic transport evidence was not observed" >&2; exit 1;
  }
fi
grep -F "AIUEOS_DESKTOP_INPUT_OK envelope-v1 sequence=1 kind=key ime-neutral" "$serial_log" >/dev/null || {
  echo "error: validated browser desktop input envelope was not observed" >&2; exit 1;
}
grep -F "AIUEOS_VIRTIO_GPU_OK modern-pci controlq display-info bounded" "$serial_log" >/dev/null || {
  echo "error: bounded virtio-gpu display-info completion was not observed" >&2
  exit 1
}
grep -F "AIUEOS_BROWSER_DESKTOP_TRANSPORT_OK surface-v1 gpu-scanout-bound input-v1" "$serial_log" >/dev/null || {
  echo "error: framebuffer/browser desktop transport binding was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SCHEDULER_OK tasks=2 policy=round-robin preemption=apic-timer" "$serial_log" >/dev/null || {
  echo "error: preemptive round-robin scheduler evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SCHEDULER_CR3_OK roots=3 private-pages=2 kernel-return" "$serial_log" >/dev/null || {
  echo "error: scheduler-driven address-space switching evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SERVICE_RUNTIME_OK services=2 descriptors=8 kotoba-policy spawn-restart-terminate task=generic generation=2 budget=bounded" "$serial_log" >/dev/null || {
  echo "error: persistent service runtime evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SERVICE_IPC_OK mailbox=bounded capability=owner-domain cross-cr3 sequence=1" "$serial_log" >/dev/null || {
  echo "error: capability-checked cross-address-space service IPC evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SERVICE_REGISTRY_OK journal-object ids=2 generation=2,1 restart=1,0 decoder=kotoba fixed-stack" "$serial_log" >/dev/null || {
  echo "error: durable service registry transaction evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_IOAPIC_OK pit-gsi vector=33 eoi-v1" "$serial_log" >/dev/null || {
  echo "error: IOAPIC external timer IRQ evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SYSCALL_OK int80-cpl0 abi-v1" "$serial_log" >/dev/null || {
  echo "error: CPL0 syscall evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_SYSCALL_PLANNER_OK bootstrap user overflow" "$serial_log" >/dev/null || {
  echo "error: Kotoba syscall range planner evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_COPY_IN_OK cpl0 hash bounded-256" "$serial_log" >/dev/null || {
  echo "error: Kotoba bounded copy-in evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_CAPABILITY_OK table owner generation type rights revoke reissue derivation=multi-hop recursive-revoke" "$serial_log" >/dev/null || {
  echo "error: capability negative evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_DYNAMIC_CAPABILITY_OK page-backed slots>=256 owner=3 reuse generation retirement" "$serial_log" >/dev/null || {
  echo "error: dynamic page-backed capability table evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PROCESS_FOUNDATION_OK tss-descriptor user-wx guard-page" "$serial_log" >/dev/null || {
  echo "error: process isolation foundation evidence was not observed" >&2; exit 1;
}
grep -F "AIUEOS_ADDRESS_SPACE_OK processes=2 distinct-cr3 private-pages cross-access-fault" "$serial_log" >/dev/null || {
  echo "error: per-process address-space isolation evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_RING3_OK processes=2 preemptive roots=2 domains=2,3 kernel-stacks=2 syscall-sysret" "$serial_log" >/dev/null || {
  echo "error: CPL3 syscall and kernel-return evidence was not observed" >&2; exit 1;
}
grep -F "AIUEOS_PROCESS_CREATE_OK descriptors=8 entry-argument-stack domain-address-space-task" "$serial_log" >/dev/null || {
  echo "process-create ABI evidence missing" >&2
  exit 1
}
grep -F "AIUEOS_SYSRET_OK star-lstar-fmask canonical-rip-rsp rflags-sanitized per-task-stack" "$serial_log" >/dev/null || {
  echo "error: native syscall/sysret evidence missing" >&2
  exit 1
}
grep -F "AIUEOS_CAPABILITY_TRANSFER_OK source=2 target=3 attenuated atomic-claim transferred-use owner-exit=descendants-revoked" "$serial_log" >/dev/null || {
  echo "error: atomic process capability transfer evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PROCESS_REAP_OK tasks=4 services=2-persistent process-slots=8 task-slots=8 generations=reused owner-caps-revoked allocator-pages=24 stack-pages=reused zero-reused" "$serial_log" >/dev/null || {
  echo "error: process exit/reap/reuse evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_ELF_PROCESS_OK source=catalog apps=2 et-exec segments=rx,rw result=42 domains=4,5" "$serial_log" >/dev/null || {
  echo "Kotoba ELF process evidence missing" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_USER_RUNTIME_OK abi=v2 transport=syscall capabilities=2,3,4,5 object=service-registry,user-store service-ipc=mailbox domains=4,5 result=42" "$serial_log" >/dev/null || {
  echo "error: Kotoba user runtime syscall evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_SERVICE_IPC_OK senders=4,5 recipients=service0,service1 payload=42 sequence=1 bounded=2 persistent-services=2" "$serial_log" >/dev/null || {
  echo "error: Kotoba to persistent service IPC evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_OBJECT_WRITE_OK domains=4,5 journals=44-47 objects=42,43 value=42 receipt=readback transaction=journal-first serializer=kotoba validator=kotoba decoder=kotoba materializer=kotoba fixed-stack" "$serial_log" >/dev/null || {
  echo "error: Kotoba user object transaction evidence was not observed" >&2; exit 1;
}
grep -F "AIUEOS_APP_CATALOG_LOOKUP_OK ids=app/hello,app/worker unknown=denied extents=nonoverlap" "$serial_log" >/dev/null || {
  echo "catalog lookup evidence missing" >&2
  exit 1
}
grep -F "AIUEOS_USER_SYSCALL_OK valid-log copied-payload too-big stale-generation foreign-owner wrong-type no-rights invalid-pointer" "$serial_log" >/dev/null || {
  echo "error: CPL3 syscall positive/negative evidence was not observed" >&2; exit 1;
}
grep -F "AIUEOS_COPYIN_OK noncanonical-and-unmapped-denied" "$serial_log" >/dev/null || {
  echo "error: invalid-pointer evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PAGE_FAULT_OK write-protect vector=14" "$serial_log" >/dev/null || {
  echo "error: write-protect page-fault evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PAGE_FAULT_OK no-execute vector=14" "$serial_log" >/dev/null || {
  echo "error: no-execute page-fault evidence was not observed" >&2
  exit 1
}
# A loop-terminated boot never arms the final #UD probe. Require the marker
# that actually ended this mode; a probe-armed run must still prove exception
# dispatch, even when its caller also supplied AIUEOS_LOOP_EXIT_OK.
if [ -n "${AIUEOS_LOOP_EXIT_OK:-}" ] && [ "${AIUEOS_SMOKE_FINAL_PROBE:-0}" != 1 ]; then
  grep -F "AIUEOS_DESKTOP_LOOP_OK persistent input service" "$serial_log" >/dev/null || {
    echo "error: persistent desktop loop evidence was not observed" >&2
    exit 1
  }
else
  grep -F "AIUEOS_EXCEPTION_OK vector=6 invalid-opcode" "$serial_log" >/dev/null || {
    echo "error: kernel exception dispatch evidence was not observed" >&2
    exit 1
  }
fi
# SHA-STREAM-PARITY (ADR-0155). The full line, not a prefix: a run that printed
# `SHA-STREAM-PARITY mismatch case=6` would satisfy a prefix match, and case 6
# is the 131,080-byte hash that is the entire reason these objects exist.
grep -F "SHA-STREAM-PARITY ok fips-abc fips-448 one-block region-vs-sha256-12288 stream-192-blocks region-131080 dwd-input-4 dwd-output-3 dwd-input-32768 refusals" "$serial_log" >/dev/null || {
  echo "error: streaming SHA-256 parity evidence was not observed" >&2
  sed 's/\r$//' "$serial_log" | grep -E '^SHA-STREAM-PARITY' >&2 || \
    echo "       (no SHA-STREAM-PARITY marker at all)" >&2
  exit 1
}
# With a NIC attached, QEMU always runs a DHCP server, so a boot that fails to
# configure an address has a real defect. Asserted HERE and not only in
# smoke-qemu-dhcp.sh, because a check that lives only in a gate nobody runs by
# habit is a check that goes quiet. Skipped when the reply is being deliberately
# broken -- those runs are supposed to be refused, and that is what the DHCP gate
# asserts instead.
if [ "${AIUEOS_TEST_NET:-0}" = 1 ] && \
   { [ -z "${AIUEOS_DHCP_TAMPER:-}" ] || [ "${AIUEOS_DHCP_TAMPER}" = 0 ]; }; then
  grep -F "AIUEOS_DHCP_OK offer-ack kotoba-admitted address=10.0.2.15 mask=255.255.255.0 router=10.0.2.2 server=10.0.2.2 lease=" "$serial_log" >/dev/null || {
    echo "error: DHCPv4 lease evidence was not observed" >&2
    sed 's/\r$//' "$serial_log" | grep -E '^AIUEOS_DHCP_' >&2 || \
      echo "       (no AIUEOS_DHCP_ marker at all)" >&2
    exit 1
  }
  grep -F "AIUEOS_DHCP_CONSUMED src=10.0.2.15" "$serial_log" >/dev/null || {
    echo "error: DHCPv4 lease was recorded but not consumed as a source address" >&2
    sed 's/\r$//' "$serial_log" | grep -E '^AIUEOS_DHCP_CONSUMED' >&2 || \
      echo "       (no AIUEOS_DHCP_CONSUMED marker at all)" >&2
    exit 1
  }
fi
echo "AIUEOS_UEFI_SMOKE_OK"
