#!/usr/bin/env python3
"""Build the live-installer boot pieces: a Linux UKI that boots into the
guarded aiueos installer (install-v1.edn, root ADR adr-2608251418 decision 3).

The live environment is deliberately split in two:

  UKI (this build)          mechanism only -- kernel, module list, busybox,
                            lsblk, and /init, which mounts kernel filesystems,
                            loads storage drivers, finds the install-USB
                            payload partition by its fixed GPT partition GUID,
                            extracts INSTALL.TGZ to a tmpfs and hands over.
  payload INSTALL.TGZ       every decision -- the node runtime, the nbb
                            orchestration (install-live.cljk -> intent
                            admission -> guarded install.mjs), the intent.

Linux here is an install-time mechanism, not an aiueos runtime premise; the
kernel and userland come from Debian stable inside a linux/amd64 container,
and every extracted artifact's digest and package version lands in the
receipt. The build is reproducible in spirit (pinned inputs, recorded
versions), not byte-deterministic -- Debian archives move; the receipt is
what pins a given build.

  python3 os/aiueos/scripts/make-live-installer.py build --output-dir build/aiueos/live
  python3 os/aiueos/scripts/make-live-installer.py verify --output-dir build/aiueos/live

Requires a running docker daemon (linux/amd64 emulation is fine).
"""

import argparse
import gzip
import hashlib
import io
import json
import os
import struct
import subprocess
import sys
from pathlib import Path

EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
DEBIAN_IMAGE = "debian:stable-slim"
# Storage + filesystem drivers the installer must have before it can see the
# USB it booted from and the disk it may write. Order does not matter here;
# the container resolves each name to an insmod-ordered dependency closure.
MODULES = ["nvme", "virtio_blk", "virtio_pci", "virtio_scsi", "xhci_pci",
           "ehci_pci", "usb_storage", "uas", "sd_mod", "ahci",
           "vfat", "nls_cp437", "nls_ascii", "nls_iso8859-1",
           # Networking. The live environment installs offline, but a box that
           # is going to become a murakumo node has to be able to answer its
           # own enrolment challenge, and that starts here.
           "virtio_net",                       # QEMU
           "r8169", "igc", "e1000e", "e1000",  # the K16's RTL8125, and common wired NICs
           # A phone shared over USB is the keyboard-free way onto a network
           # for a box with no ethernet run to it (root ADR adr-2609092800 D6
           # route B). These are the classes `aiueos.network-bootstrap` admits
           # to CARRY first boot -- and refuses to record as the machine's own.
           "usbnet", "cdc_ether", "cdc_ncm", "cdc_subset", "rndis_host",
           "ipheth", "r8152"]
# blkid probes PART_ENTRY_UUID directly from the device; lsblk's PARTUUID
# column is udev-fed and comes back EMPTY in this udev-less initramfs
# (measured: all three disks enumerated, every PARTUUID blank).
USERLAND = ["/usr/bin/lsblk", "/usr/bin/findmnt", "/usr/sbin/blkid"]
# The payload partition GUID make-install-usb-image.py stamps
# (uuid5(NAMESPACE, "aiueos-install-payload-v1")). /init searches for it.
PAYLOAD_PARTUUID = "6de0f34d-549a-5d00-92c2-df27f49691be"
# The node stick's writable state partition (uuid5(NAMESPACE,
# "aiueos-node-state-v1")). A node USB has one; an install USB does not, and
# /init says which it found rather than assuming.
NODE_STATE_PARTUUID = "6f9622db-44f5-5cea-8630-bbac5d26341e"

# The shebang names busybox itself: at exec time /bin/sh does not exist yet
# (busybox --install creates it two lines later), and a #!/bin/sh init dies
# with exactly the "Failed to execute /init (error -2)" panic this replaced.
UDHCPC_SCRIPT = """#!/bin/busybox sh
# busybox ships udhcpc but no lease handler; this is that handler. It writes
# only what a node needs to reach an enrolment endpoint: address, default
# route, resolver.
[ -n "$interface" ] || exit 1
case "$1" in
  bound|renew)
    if command -v ip >/dev/null 2>&1; then
      ip addr flush dev "$interface" 2>/dev/null
      ip addr add "$ip/${mask:-24}" dev "$interface" 2>/dev/null
      [ -n "$router" ] && ip route add default via "${router%% *}" dev "$interface" 2>/dev/null
    else
      ifconfig "$interface" "$ip" netmask "${subnet:-255.255.255.0}" up
      [ -n "$router" ] && route add default gw "${router%% *}" dev "$interface"
    fi
    mkdir -p /etc
    : > /etc/resolv.conf
    for d in $dns; do echo "nameserver $d" >> /etc/resolv.conf; done
    ;;
esac
exit 0
"""

INIT_SCRIPT = """#!/bin/busybox sh
# aiueos live-installer init: mechanism only. Mount kernel filesystems, load
# storage drivers, find the install-USB payload by its GPT partition GUID,
# extract the installer bundle to a tmpfs, hand over to the nbb orchestration.
# Every decision (target admission, intent, destruction) lives in the bundle.
export PATH=/bin
/bin/busybox --install -s /bin >/dev/null 2>&1
mkdir -p /proc /sys /dev /payload /run /tmp
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs dev /dev
echo AIUEOS_LIVE_INIT start
while read m; do
  insmod /modules/"$m" 2>/dev/null || echo "AIUEOS_LIVE_INSMOD_SKIP $m"
done < /modules/modules.list
# Networking. Reported in three distinct states on purpose: a lease, no lease,
# and no interface at all are different facts, and an installer that printed
# one marker for all three would look the same whether the box was offline or
# had no NIC driver.
mkdir -p /usr/share/udhcpc /etc
cp /udhcpc.script /usr/share/udhcpc/default.script 2>/dev/null
chmod +x /usr/share/udhcpc/default.script 2>/dev/null
NETIF=""
for i in $(ls /sys/class/net 2>/dev/null); do
  [ "$i" = lo ] && continue
  NETIF="$NETIF $i"
  ip link set "$i" up 2>/dev/null || ifconfig "$i" up 2>/dev/null
done
if [ -z "$NETIF" ]; then
  echo AIUEOS_LIVE_NET_NO_INTERFACE
else
  echo "AIUEOS_LIVE_NET_INTERFACES$NETIF"
  LEASED=""
  for i in $NETIF; do
    if udhcpc -i "$i" -n -q -t 4 -T 2 -s /usr/share/udhcpc/default.script >/dev/null 2>&1; then
      LEASED="$i"
      ADDR=$(ip -4 -o addr show dev "$i" 2>/dev/null | awk '{print $4}')
      [ -z "$ADDR" ] && ADDR=$(ifconfig "$i" 2>/dev/null | awk '/inet /{print $2}')
      echo "AIUEOS_LIVE_NET_LEASE $i $ADDR"
      break
    fi
  done
  [ -z "$LEASED" ] && echo AIUEOS_LIVE_NET_NO_LEASE
fi
export AIUEOS_LIVE_NET_IFACE="$LEASED"

i=0
PAYLOAD=""
while [ "$i" -lt 60 ]; do
  for dev in $(lsblk -rno PATH,TYPE 2>/dev/null | awk '$2=="part"{print $1}'); do
    uuid=$(blkid -p -o value -s PART_ENTRY_UUID "$dev" 2>/dev/null || true)
    if [ "$uuid" = "__PAYLOAD_PARTUUID__" ]; then
      PAYLOAD="$dev"
      break
    fi
  done
  [ -n "$PAYLOAD" ] && break
  sleep 1
  i=$((i+1))
done
if [ -z "$PAYLOAD" ]; then
  echo AIUEOS_LIVE_PAYLOAD_ABSENT
  echo "--- partitions probed:"
  for dev in $(lsblk -rno PATH,TYPE 2>/dev/null | awk '$2=="part"{print $1}'); do
    echo "$dev $(blkid -p -o value -s PART_ENTRY_UUID "$dev" 2>&1)"
  done
  echo "--- /dev block nodes:"
  ls /dev | grep -E "sd|nvme|vd" || true
  sync
  poweroff -f
fi
echo "AIUEOS_LIVE_PAYLOAD $PAYLOAD"
mount -t vfat -o ro "$PAYLOAD" /payload || { echo AIUEOS_LIVE_PAYLOAD_MOUNT_FAIL; poweroff -f; }
mount -t tmpfs tmpfs /run
# The ported installer identifies the boot medium's disk via findmnt on the
# live-media mount points; expose the payload there so the USB counts as the
# system disk without touching the scope-frozen backend.
mkdir -p /run/live/medium
mount -o bind /payload /run/live/medium
# A stick carries one of two payloads, and which one decides what this boot is
# for. NODE.JSN means "become a claimable node"; INSTALL.TGZ means "write a
# system to a disk". They are checked in that order and never both run: an
# installer that also enrolled would make the enrolment a side effect of
# erasing something.
if [ -f /payload/NODE.JSN ]; then
  tar xzf /payload/NODE.TGZ -C /run || { echo AIUEOS_LIVE_NODE_EXTRACT_FAIL; poweroff -f; }
  # The node's own writable state, if this stick has one. Reported in three
  # states for the same reason the network is: a stick without the partition
  # and a stick whose partition would not mount are different problems, and a
  # node that silently fell back to tmpfs would mint a new identity every boot
  # while looking like it had kept one.
  mkdir -p /state
  STATE=""
  for dev in $(lsblk -rno PATH,TYPE 2>/dev/null | awk '$2=="part"{print $1}'); do
    if [ "$(blkid -p -o value -s PART_ENTRY_UUID "$dev" 2>/dev/null)" = "__STATE_PARTUUID__" ]; then
      STATE="$dev"
      break
    fi
  done
  if [ -z "$STATE" ]; then
    echo AIUEOS_LIVE_STATE_ABSENT
  elif mount -t vfat -o rw "$STATE" /state 2>/dev/null; then
    echo "AIUEOS_LIVE_STATE $STATE"
    export AIUEOS_NODE_STATE_DIR=/state
  else
    echo "AIUEOS_LIVE_STATE_MOUNT_FAIL $STATE"
  fi
  cd /run/aiueos-node
  export AIUEOS_LIVE_MEDIA=/payload
  export AIUEOS_NODE_BUNDLE=/run/aiueos-node
  export PATH=/run/aiueos-node/bin:$PATH
  echo AIUEOS_LIVE_HANDOVER node-boot.cljk
  ./node-linux-x64 nbb-bundle/node_modules/nbb/cli.js --classpath /run/aiueos-node/cp node-boot.cljk
  rc=$?
  echo "AIUEOS_LIVE_EXIT rc=$rc"
  sync
  poweroff -f
fi
tar xzf /payload/INSTALL.TGZ -C /run || { echo AIUEOS_LIVE_BUNDLE_EXTRACT_FAIL; poweroff -f; }
cd /run/aiueos-installer
export AIUEOS_LIVE_PAYLOAD_DEV="$PAYLOAD"
export AIUEOS_LIVE_MEDIA=/payload
export PATH=/run/aiueos-installer/bin:$PATH
# Selfhost product (owner direction 2026-10-18, JUN-70 S5): the bundle's
# install chain is kotoba ELFs and carries no node/nbb. The ELFs' spawn
# grants are sealed at compile time and name these bundle paths
# (/run/aiueos-installer/...), so the stick's ELFs must be built for this
# layout. Without the ELF the stick is the node product, unchanged.
if [ -x ./guided-core.elf ]; then
  echo AIUEOS_LIVE_HANDOVER guided-core.elf
  # The console is /dev/console (= the LAST console= line = ttyS0), so a
  # person at the machine saw a BLACK screen: every prompt went to serial
  # only (measured 2026-10-19 from a framebuffer screendump). tee mirrors
  # the flow onto tty0 as well; stdin stays /dev/console so the gate's
  # serial answers keep working. Typing AT the screen still needs the tty0
  # input half (tracked for I7).
  # The console is /dev/console (= the LAST console= line = ttyS0), so a
  # person at the machine saw a BLACK screen: every prompt went to serial
  # only (measured 2026-10-19 from a framebuffer screendump). The fifo +
  # tee mirrors the flow onto tty0 as well AND keeps the real exit status
  # -- a bare `cmd | tee` reports tee's zero and hides a failed install
  # (measured). stdin stays /dev/console so the gate's serial answers keep
  # working. Typing AT the screen still needs the tty0 input half
  # (tracked for I7).
  mkfifo /run/aiueos-installer/.console
  ( { ./guided-core.elf install /run/aiueos-installer/install-answers.json "" "" -1 ""     /run/aiueos-installer /run/aiueos-installer/install-disk.elf     /payload/RELEASE.IMG < /dev/console
      echo AIUEOS_LIVE_HANDOVER install-live.elf
      ./install-live.elf "" /payload/RELEASE.IMG /run/aiueos-installer/install-answers.json.match /run/aiueos-installer /run/aiueos-installer/install-disk.elf "" < /dev/console
    } > /run/aiueos-installer/.console 2>&1; echo $? > /run/aiueos-installer/.rc ) &
  tee /dev/tty0 < /run/aiueos-installer/.console
  rc=$(cat /run/aiueos-installer/.rc)
else
  echo AIUEOS_LIVE_HANDOVER install-live.cljk
  ./node-linux-x64 nbb-bundle/node_modules/nbb/cli.js --classpath /run/aiueos-installer/cp install-live.cljk
fi
rc=$?
echo "AIUEOS_LIVE_EXIT rc=$rc"
sync
poweroff -f
""".replace("__PAYLOAD_PARTUUID__", PAYLOAD_PARTUUID).replace("__STATE_PARTUUID__", NODE_STATE_PARTUUID)

EXTRACT_SCRIPT = r"""
set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update >/dev/null
apt-get -qq install -y --no-install-recommends \
  linux-image-amd64 busybox-static systemd-boot-efi binutils xz-utils util-linux \
  libatomic1 >/dev/null
KVER=$(ls /lib/modules | head -1)
mkdir -p /out/modules /out/bin /out/lib
# Start from a clean module set: a previous build's leftover .ko files would
# satisfy the not-yet-copied test below and silently leave modules.list EMPTY
# (measured: second build in the same output dir shipped an initramfs that
# loaded no storage drivers at all -- zero block devices in the live boot).
rm -f /out/modules/*.ko /out/modules/modules.list
cp "/boot/vmlinuz-$KVER" /out/vmlinuz
cp /bin/busybox /out/bin/busybox
cp /usr/lib/systemd/boot/efi/linuxx64.efi.stub /out/linuxx64.efi.stub
# Dependency-ordered module closure, decompressed so busybox insmod (no xz)
# can load each file directly; /init replays the list in order.
: > /out/modules/modules.list
for m in __MODULES__; do
  modprobe -S "$KVER" --show-depends "$m" 2>/dev/null | while read -r verb path rest; do
    [ "$verb" = insmod ] || continue
    base=$(basename "$path" .xz)
    if [ ! -f "/out/modules/$base" ]; then
      xz -dc "$path" > "/out/modules/$base" 2>/dev/null || cp "$path" "/out/modules/$base"
      echo "$base" >> /out/modules/modules.list
    fi
  done
done
# Userland the installer inspection needs, with its shared-library closure.
for bin in __USERLAND__; do
  cp "$bin" /out/bin/
  ldd "$bin" | awk 'match($0, /\/[^ ]+/) {print substr($0, RSTART, RLENGTH)}' | sort -u | \
  while read -r lib; do cp -n "$lib" /out/lib/ 2>/dev/null || true; done
done
cp -n /lib64/ld-linux-x86-64.so.2 /out/lib/ 2>/dev/null || true
# The node runtime rides in the payload but resolves its shared libraries
# from this initramfs; the official binary needs the C++ runtime on top of
# the util-linux closure (measured: without libstdc++/libgcc_s the handover
# died with rc=127 before a single line of the orchestration ran). libatomic
# joined the closure when the pinned node moved to v26.7.0 (measured 2026-09-15:
# boot1 died rc=127 "libatomic.so.1: cannot open shared object file" with the
# previous list -- the install-smoke gate exists to catch exactly this).
for lib in libstdc++.so.6 libgcc_s.so.1 libm.so.6 libdl.so.2 libpthread.so.0 librt.so.1 libatomic.so.1; do
  cp -n "/usr/lib/x86_64-linux-gnu/$lib" /out/lib/ 2>/dev/null || true
done
{ echo "debian=$(cat /etc/debian_version)"
  echo "kernel=$KVER"
  dpkg-query -W -f '${Package}=${Version}\n' linux-image-amd64 busybox-static systemd-boot-efi util-linux
} > /out/provenance.txt
"""

# The classic objcopy --add-section recipe is NOT used: the current systemd
# stub links at a high ImageBase (measured 0x14df90000), the fixed low VMAs
# wrap, and OVMF refuses the PE -- the firmware then falls through to the EFI
# shell, which is exactly how the breakage was found. ukify computes correct
# section placement against whatever stub it is given.
UKI_SCRIPT = r"""
set -eu
apt-get -qq update >/dev/null
apt-get -qq install -y --no-install-recommends systemd-ukify python3-pefile >/dev/null
cd /out
ukify build --stub=linuxx64.efi.stub --linux=vmlinuz --initrd=initramfs.cpio.gz \
  --cmdline="$(cat cmdline)" --os-release=@osrel --output=uki.efi
"""


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def docker_run(out_dir, script):
    subprocess.run(["docker", "run", "--rm", "--platform", "linux/amd64",
                    "-v", f"{out_dir}:/out", DEBIAN_IMAGE, "sh", "-eu", "-c", script],
                   check=True)


class NewcCpio:
    """Minimal deterministic newc (SVR4) cpio writer -- the format the kernel
    initramfs unpacker reads. Fixed inode numbers, zero mtimes, root
    ownership: the archive digest depends only on the file contents."""

    def __init__(self):
        self.buffer = io.BytesIO()
        self.ino = 720

    def _entry(self, name, mode, data):
        self.ino += 1
        header = "070701" + "".join("%08X" % v for v in (
            self.ino, mode, 0, 0, 1, EPOCH, len(data), 0, 0, 0, 0,
            len(name) + 1, 0))
        self.buffer.write(header.encode("ascii"))
        self.buffer.write(name.encode("ascii") + b"\x00")
        pad = (-(len(header) + len(name) + 1)) % 4
        self.buffer.write(b"\x00" * pad)
        self.buffer.write(data)
        self.buffer.write(b"\x00" * ((-len(data)) % 4))

    def directory(self, name):
        self._entry(name, 0o040755, b"")

    def file(self, name, data, mode=0o644):
        self._entry(name, 0o100000 | mode, data)

    def finish(self):
        self._entry("TRAILER!!!", 0, b"")
        return self.buffer.getvalue()


def build_initramfs(parts):
    cpio = NewcCpio()
    # /tmp is load-bearing: the orchestration writes its inspection report
    # via os.tmpdir(), and a rootfs without /tmp kills the handover with an
    # unexplained exit (measured in the QEMU gate).
    for d in ("bin", "lib", "lib64", "modules", "proc", "sys", "dev", "run", "payload", "tmp"):
        cpio.directory(d)
    cpio.file("init", INIT_SCRIPT.encode(), 0o755)
    # /init copies this to /usr/share/udhcpc/default.script before running the
    # client. Carried as its own file rather than heredoc'd from /init: a
    # here-document inside a here-document is how a shell script quietly stops
    # being the script that was written.
    cpio.file("udhcpc.script", UDHCPC_SCRIPT.encode(), 0o755)
    for name in sorted(p.name for p in (parts / "bin").iterdir()):
        cpio.file(f"bin/{name}", (parts / "bin" / name).read_bytes(), 0o755)
    for name in sorted(p.name for p in (parts / "lib").iterdir()):
        target = "lib64" if name.startswith("ld-linux") else "lib"
        cpio.file(f"{target}/{name}", (parts / "lib" / name).read_bytes(), 0o755)
    # lsblk expects the multiarch path for its libraries.
    cpio.directory("lib/x86_64-linux-gnu")
    for name in sorted(p.name for p in (parts / "lib").iterdir()):
        if not name.startswith("ld-linux"):
            cpio.file(f"lib/x86_64-linux-gnu/{name}", (parts / "lib" / name).read_bytes(), 0o755)
    for name in sorted(p.name for p in (parts / "modules").iterdir()):
        mode = 0o644
        cpio.file(f"modules/{name}", (parts / "modules" / name).read_bytes(), mode)
    payload = cpio.finish()
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=EPOCH) as stream:
        stream.write(payload)
    return gz.getvalue()


def build(args):
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    if not (args.reuse_parts and (out / "vmlinuz").exists()
            and (out / "modules" / "modules.list").exists()):
        docker_run(out.resolve(), EXTRACT_SCRIPT
                   .replace("__MODULES__", " ".join(MODULES))
                   .replace("__USERLAND__", " ".join(USERLAND)))
    (out / "initramfs.cpio.gz").write_bytes(build_initramfs(out))
    (out / "osrel").write_text(
        'NAME="aiueos live installer"\nID=aiueos-live-installer\nVERSION_ID=1\n')
    # The LAST console= becomes /dev/console and receives every line the
    # installer prints (measured: with tty0 last, all AIUEOS_LIVE_* evidence
    # went to the VGA console and the serial gate saw none of it). Default is
    # serial-last for the QEMU gates; --display-console flips the order for a
    # stick an operator will watch on a monitor, where an invisible report
    # would make the interactive dry-run useless.
    order = ("console=ttyS0,115200 console=tty0" if args.display_console
             else "console=tty0 console=ttyS0,115200")
    (out / "cmdline").write_text(order + " loglevel=4\n")
    docker_run(out.resolve(), UKI_SCRIPT)
    provenance = (out / "provenance.txt").read_text().strip().splitlines()
    receipt = {
        "schema": "aiueos.live-installer-receipt.v1",
        "payloadPartuuid": PAYLOAD_PARTUUID,
        "modules": sorted(p.name for p in (out / "modules").iterdir()),
        "provenance": provenance,
        "artifacts": {name: {"bytes": (out / name).stat().st_size,
                             "sha256": sha256_file(out / name)}
                      for name in ("vmlinuz", "initramfs.cpio.gz", "uki.efi",
                                   "linuxx64.efi.stub")},
    }
    (out / "live-installer-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    verify(args)
    print(out / "uki.efi")


def verify(args):
    out = Path(args.output_dir)
    receipt = json.loads((out / "live-installer-receipt.json").read_text())
    for name, expected in receipt["artifacts"].items():
        actual = sha256_file(out / name)
        if actual != expected["sha256"]:
            raise SystemExit(f"{name}: digest {actual} does not match receipt")
    uki = (out / "uki.efi").read_bytes()
    if uki[:2] != b"MZ":
        raise SystemExit("uki.efi is not a PE image")
    pe = struct.unpack_from("<I", uki, 0x3C)[0]
    nsec = struct.unpack_from("<H", uki, pe + 6)[0]
    opt_size = struct.unpack_from("<H", uki, pe + 20)[0]
    size_of_image = struct.unpack_from("<I", uki, pe + 24 + 56)[0]
    sections = {}
    for i in range(nsec):
        o = pe + 24 + opt_size + i * 40
        name = uki[o:o + 8].rstrip(b"\x00")
        vsize, vma = struct.unpack_from("<II", uki, o + 8)
        sections[name] = (vma, vsize)
    for section in (b".linux", b".initrd", b".cmdline", b".osrel"):
        if section not in sections:
            raise SystemExit(f"uki.efi lacks the {section.decode()} section")
        vma, vsize = sections[section]
        if vma + vsize > size_of_image:
            raise SystemExit(
                f"uki.efi section {section.decode()} ends at {vma + vsize:#x}, "
                f"beyond SizeOfImage {size_of_image:#x}: the PE would not load "
                "(the failure mode of the objcopy recipe this build replaced)")
    print("AIUEOS_LIVE_INSTALLER_OK uki_bytes=%d" % len(uki))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--output-dir", required=True)
        p.add_argument("--reuse-parts", action="store_true")
        p.add_argument("--display-console", action="store_true")
    args = parser.parse_args()
    build(args) if args.command == "build" else verify(args)


if __name__ == "__main__":
    main()
