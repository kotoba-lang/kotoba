#!/usr/bin/env python3
"""Build and verify the aiueos install-USB GPT image (install-v1.edn, root ADR
adr-2608251418).

The install USB is the release image plus intent plus installer, as ONE disk:

  LBA 0            protective MBR, byte-identical BIOS refusal stub
  LBA 1..33        new primary GPT (three partitions)
  LBA 2048..       ESP + recovery, byte-identical to the release image slices
  LBA 131072..     payload partition (FAT32, Microsoft basic data):
                     RELEASE.IMG  the whole release GPT image
                     RECEIPT.JSN  its build receipt
                     INTENT.JSN   the install intent
                     INSTALL.TGZ  installer bundle (mjs + scripts + runbook)
                     SHA256S.TXT  digests of everything above
                     README.TXT   runbook
  tail             new backup GPT

Because the ESP and recovery slices are byte-identical and keep their LBAs,
GUIDs and names, the stick boots exactly what usb-boot-v1.edn proved -- the
firmware reads partition entries, not the disk size. The payload partition is
Microsoft basic data so any rescue Linux mounts it read-only without tooling.

The receipt closes the I1 digest chain: release build receipt -> release image
-> intent -> payload files -> final USB image. `verify` re-derives all of it
from the image alone, so a stick flashed from a drifted image cannot match.
"""

import argparse
import binascii
import gzip
import hashlib
import io
import json
import os
import struct
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

SECTOR = 512
ALIGN = 2048  # 1 MiB
GPT_ENTRY_COUNT = 128
GPT_ENTRY_SIZE = 128
GPT_ENTRY_SECTORS = GPT_ENTRY_COUNT * GPT_ENTRY_SIZE // SECTOR
RELEASE_SECTORS = 131072  # geometry of the release image this consumes
PAYLOAD_FIRST = RELEASE_SECTORS  # 64 MiB boundary, already 1 MiB aligned
NAMESPACE = uuid.UUID("18b3fb94-8713-54c4-9e3a-f0c78a88d192")
DISK_GUID = uuid.uuid5(NAMESPACE, "aiueos-install-usb-disk-v1")
PAYLOAD_GUID = uuid.uuid5(NAMESPACE, "aiueos-install-payload-v1")
LIVE_ESP_GUID = uuid.uuid5(NAMESPACE, "aiueos-live-esp-v1")
# The node's own writable state. A separate partition rather than a corner of
# the payload: the payload is mounted read-only on purpose, and the filesystem
# being written when the power goes should not be the one that boots.
NODE_STATE_GUID = uuid.uuid5(NAMESPACE, "aiueos-node-state-v1")
BASIC_DATA_TYPE = uuid.UUID("ebd0a0a2-b9e5-4433-87c0-68b6b72699c7")
ESP_TYPE = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))

PAYLOAD_NAMES = ["RELEASE.IMG", "RECEIPT.JSN", "INTENT.JSN",
                 "INSTALL.TGZ", "SHA256S.TXT", "README.TXT"]
# A guided stick carries no intent: it is authored at the machine by
# guided-install.cljs (aiueos ADR-0208/0210). The two products differ by
# exactly this one file, so the name list is derived from what is present
# rather than assumed, and SHA256S.TXT is what decides -- see verify_image.
GUIDED_PAYLOAD_NAMES = [n for n in PAYLOAD_NAMES if n != "INTENT.JSN"]


def payload_names_for(guided):
    return GUIDED_PAYLOAD_NAMES if guided else PAYLOAD_NAMES

README_TEXT = """aiueos install USB payload (install-v1.edn)

This stick boots aiueos directly (the ESP is the release image's, unchanged).
This partition additionally carries everything an INSTALL to an internal disk
needs. Nothing here runs by itself; the target machine is erased only through
the guarded installer, and only for the one disk INTENT.JSN names.

From any Linux environment on the target machine:

  MEDIA=/path-to-this-partition                    # wherever this FAT is mounted
  mkdir -p /tmp/aiueos && cd /tmp/aiueos           # do NOT run from the FAT mount
  tar xzf "$MEDIA"/INSTALL.TGZ && cd aiueos-installer
  sh offline-linux-installer.sh \
    --device /dev/nvmeXn1 \
    --image "$MEDIA"/RELEASE.IMG --receipt ./release-receipt.json
  # That is a DRY RUN: it inspects, refuses, and prints the exact three
  # destructive arguments a real install additionally needs. Read its report
  # before adding them. With nbb available, prefer the intent-checking
  # orchestrator instead:
  #   kbb --backend sci install-to-disk.cljk --intent ./install-intent.json \
  #     --device /dev/nvmeXn1 --image "$MEDIA"/RELEASE.IMG \
  #     --receipt ./release-receipt.json
All digests are in SHA256S.TXT; verify before trusting anything here.
"""

GUIDED_README_TEXT = """aiueos install USB payload, guided (install-v1.edn)

This stick boots aiueos directly and carries everything an INSTALL needs
EXCEPT the one thing that says which machine and which disk. There is no
INTENT.JSN here on purpose: this stick asks.

Booted as the live installer, /init hands over to install-live.cljk, which
finds no intent and runs guided-install.cljk -- a screen sequence (network,
storage, identity, ssh, confirm) that ends by writing an intent into the
tmpfs. Every guard downstream is unchanged: the intent is verified against a
fresh probe, the device-level refusals in install.mjs all still run, and the
erase still needs its confirmation.

A stick that asks cannot be left plugged in and forgotten: it installs
nothing without a person. That is the difference from the unattended
product, not an accident of packaging.

From any Linux environment on the target machine, the same bundle also works
by hand:

  MEDIA=/path-to-this-partition
  mkdir -p /tmp/aiueos && cd /tmp/aiueos
  tar xzf "$MEDIA"/INSTALL.TGZ && cd aiueos-installer
  kbb --backend sci guided-install.cljk --release-receipt ./release-receipt.json \
    --out-intent ./install-intent.json --out-answers ./install-answers.json
  kbb --backend sci install-to-disk.cljk --intent ./install-intent.json \
    --device /dev/nvmeXn1 --image "$MEDIA"/RELEASE.IMG \
    --receipt ./release-receipt.json

All digests are in SHA256S.TXT; verify before trusting anything here.
"""


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fat_name(name):
    stem, dot, suffix = name.partition(".")
    return (stem.upper().ljust(8) + (suffix.upper() if dot else "").ljust(3)).encode("ascii")


def dirent(name, attr, cluster, size=0):
    entry = bytearray(32)
    entry[:11] = fat_name(name)
    entry[11] = attr
    struct.pack_into("<H", entry, 16, 0x0021)  # fixed 1980-01-01, as the release ESP does
    struct.pack_into("<H", entry, 18, 0x0021)
    struct.pack_into("<H", entry, 24, 0x0021)
    struct.pack_into("<H", entry, 20, cluster >> 16)
    struct.pack_into("<H", entry, 26, cluster & 0xFFFF)
    struct.pack_into("<I", entry, 28, size)
    return bytes(entry)


def make_payload_fat32(total_sectors, files, first_lba=PAYLOAD_FIRST, names=None):
    """A FAT32 volume with the given {8.3-name: bytes} in the root directory.
    Same construction as the release ESP (make-release-image.py make_fat32),
    generalized to arbitrary root files and an adaptive cluster size so the
    FAT32 floor of 65525 clusters holds for any payload size."""
    reserved, fats = 32, 2
    spc = 8
    while spc > 1 and (total_sectors - reserved) // spc < 65525 + 8:
        spc //= 2
    denominator = spc * SECTOR + fats * 4
    fat_sectors = ((total_sectors - reserved + 2 * spc) * 4 + denominator - 1) // denominator
    data_start = reserved + fats * fat_sectors
    clusters = (total_sectors - data_start) // spc
    if clusters < 65525:
        raise ValueError("payload partition is too small for FAT32")

    image = bytearray(total_sectors * SECTOR)
    boot = bytearray(SECTOR)
    boot[:3] = b"\xeb\x58\x90"
    boot[3:11] = b"AIUEOS  "
    struct.pack_into("<HBHBHHBHHHII", boot, 11, SECTOR, spc, reserved, fats, 0, 0,
                     0xF8, 0, 63, 255, first_lba, total_sectors)
    struct.pack_into("<IHHIHH", boot, 36, fat_sectors, 0, 0, 2, 1, 6)
    boot[64] = 0x80
    boot[66] = 0x29
    struct.pack_into("<I", boot, 67, 0x41495553)
    boot[71:82] = b"AIUEOS INST"
    boot[82:90] = b"FAT32   "
    boot[510:512] = b"\x55\xaa"
    image[:SECTOR] = boot
    image[6 * SECTOR:7 * SECTOR] = boot

    fsinfo = bytearray(SECTOR)
    struct.pack_into("<I", fsinfo, 0, 0x41615252)
    struct.pack_into("<I", fsinfo, 484, 0x61417272)
    struct.pack_into("<II", fsinfo, 488, 0xFFFFFFFF, 0xFFFFFFFF)
    struct.pack_into("<I", fsinfo, 508, 0xAA550000)
    image[SECTOR:2 * SECTOR] = fsinfo
    image[7 * SECTOR:8 * SECTOR] = fsinfo

    fat = [0] * (clusters + 2)
    fat[0], fat[1] = 0x0FFFFFF8, 0x0FFFFFFF
    fat[2] = 0x0FFFFFFF  # root directory, one cluster
    next_cluster = 3
    cluster_bytes = spc * SECTOR

    def allocate(payload):
        nonlocal next_cluster
        count = max(1, (len(payload) + cluster_bytes - 1) // cluster_bytes)
        first = next_cluster
        for index in range(count):
            cluster = next_cluster + index
            fat[cluster] = 0x0FFFFFFF if index == count - 1 else cluster + 1
            offset = (data_start + (cluster - 2) * spc) * SECTOR
            chunk = payload[index * cluster_bytes:(index + 1) * cluster_bytes]
            image[offset:offset + len(chunk)] = chunk
        next_cluster += count
        return first

    root = bytearray()
    # The install payload has a fixed set; a node payload has a different one.
    # Taking the order from the caller rather than a module constant is what
    # lets one FAT builder serve both without either guessing.
    for name in (names or PAYLOAD_NAMES):
        data = files[name]
        root += dirent(name, 0x20, allocate(data), len(data))
    if len(root) > cluster_bytes:
        raise ValueError("root directory exceeds one cluster")
    root_offset = data_start * SECTOR
    image[root_offset:root_offset + len(root)] = root

    fat_bytes = bytearray(fat_sectors * SECTOR)
    for index, value in enumerate(fat):
        if index * 4 >= len(fat_bytes):
            break
        struct.pack_into("<I", fat_bytes, index * 4, value)
    for copy in range(fats):
        offset = (reserved + copy * fat_sectors) * SECTOR
        image[offset:offset + len(fat_bytes)] = fat_bytes
    return bytes(image)


def read_payload_fat32(volume):
    """Return {name: bytes} for the root files of a volume make_payload_fat32
    built. Independent walk (boot-sector parameters, FAT chains), so verify
    does not trust the builder's in-memory state."""
    if volume[82:90] != b"FAT32   " or volume[510:512] != b"\x55\xaa":
        raise ValueError("payload is not the expected FAT32 volume")
    spc = volume[13]
    reserved = struct.unpack_from("<H", volume, 14)[0]
    fats = volume[16]
    fat_sectors = struct.unpack_from("<I", volume, 36)[0]
    data_start = reserved + fats * fat_sectors
    fat = volume[reserved * SECTOR:(reserved + fat_sectors) * SECTOR]
    cluster_bytes = spc * SECTOR

    def read_chain(first, size):
        output = bytearray()
        cluster = first
        while cluster < 0x0FFFFFF8 and len(output) < size:
            offset = (data_start + (cluster - 2) * spc) * SECTOR
            output += volume[offset:offset + cluster_bytes]
            cluster = struct.unpack_from("<I", fat, cluster * 4)[0] & 0x0FFFFFFF
        return bytes(output[:size])

    files = {}
    # Follow the whole root-directory chain, and tolerate what one mount on a
    # host OS leaves behind: long-name entries (attr 0x0F), deleted markers
    # (0xE5), volume labels, and non-ASCII names from indexer droppings. The
    # named payload files are what this walk answers for; foreign entries are
    # skipped, never fatal -- a stick that has been mounted once must still
    # verify.
    root = read_chain(2, 1 << 30)
    for entry_offset in range(0, len(root), 32):
        entry = root[entry_offset:entry_offset + 32]
        if entry[0] == 0:
            break
        if entry[0] == 0xE5 or entry[11] == 0x0F or entry[11] & 0x08:
            continue
        try:
            name = entry[:8].decode("ascii").rstrip()
            suffix = entry[8:11].decode("ascii").rstrip()
        except UnicodeDecodeError:
            continue
        cluster = struct.unpack_from("<H", entry, 20)[0] << 16 | struct.unpack_from("<H", entry, 26)[0]
        size = struct.unpack_from("<I", entry, 28)[0]
        files[name + ("." + suffix if suffix else "")] = read_chain(cluster, size)
    return files


def make_live_esp(total_sectors, uki):
    """A FAT32 ESP whose whole content is EFI/BOOT/BOOTX64.EFI = the live
    installer UKI. Same construction as the payload volume, plus the two
    directory levels the removable-media fallback path requires."""
    reserved, fats = 32, 2
    spc = 8
    while spc > 1 and (total_sectors - reserved) // spc < 65525 + 8:
        spc //= 2
    denominator = spc * SECTOR + fats * 4
    fat_sectors = ((total_sectors - reserved + 2 * spc) * 4 + denominator - 1) // denominator
    data_start = reserved + fats * fat_sectors
    clusters = (total_sectors - data_start) // spc
    if clusters < 65525:
        raise ValueError("live ESP is too small for FAT32")

    image = bytearray(total_sectors * SECTOR)
    boot = bytearray(SECTOR)
    boot[:3] = b"\xeb\x58\x90"
    boot[3:11] = b"AIUEOS  "
    struct.pack_into("<HBHBHHBHHHII", boot, 11, SECTOR, spc, reserved, fats, 0, 0,
                     0xF8, 0, 63, 255, 2048, total_sectors)
    struct.pack_into("<IHHIHH", boot, 36, fat_sectors, 0, 0, 2, 1, 6)
    boot[64] = 0x80
    boot[66] = 0x29
    struct.pack_into("<I", boot, 67, 0x4C495645)
    boot[71:82] = b"AIUEOS LIVE"
    boot[82:90] = b"FAT32   "
    boot[510:512] = b"\x55\xaa"
    image[:SECTOR] = boot
    image[6 * SECTOR:7 * SECTOR] = boot

    fsinfo = bytearray(SECTOR)
    struct.pack_into("<I", fsinfo, 0, 0x41615252)
    struct.pack_into("<I", fsinfo, 484, 0x61417272)
    struct.pack_into("<II", fsinfo, 488, 0xFFFFFFFF, 0xFFFFFFFF)
    struct.pack_into("<I", fsinfo, 508, 0xAA550000)
    image[SECTOR:2 * SECTOR] = fsinfo
    image[7 * SECTOR:8 * SECTOR] = fsinfo

    fat = [0] * (clusters + 2)
    fat[0], fat[1] = 0x0FFFFFF8, 0x0FFFFFFF
    root_cluster, efi_cluster, boot_cluster = 2, 3, 4
    for cluster in (root_cluster, efi_cluster, boot_cluster):
        fat[cluster] = 0x0FFFFFFF
    next_cluster = 5
    cluster_bytes = spc * SECTOR
    count = max(1, (len(uki) + cluster_bytes - 1) // cluster_bytes)
    uki_cluster = next_cluster
    for index in range(count):
        cluster = next_cluster + index
        fat[cluster] = 0x0FFFFFFF if index == count - 1 else cluster + 1
        offset = (data_start + (cluster - 2) * spc) * SECTOR
        chunk = uki[index * cluster_bytes:(index + 1) * cluster_bytes]
        image[offset:offset + len(chunk)] = chunk

    def write_dir(cluster, payload):
        offset = (data_start + (cluster - 2) * spc) * SECTOR
        image[offset:offset + len(payload)] = payload

    write_dir(root_cluster, dirent("EFI", 0x10, efi_cluster))
    write_dir(efi_cluster, dirent(".", 0x10, efi_cluster) + dirent("..", 0x10, 0) +
              dirent("BOOT", 0x10, boot_cluster))
    write_dir(boot_cluster, dirent(".", 0x10, boot_cluster) + dirent("..", 0x10, efi_cluster) +
              dirent("BOOTX64.EFI", 0x20, uki_cluster, len(uki)))

    fat_bytes = bytearray(fat_sectors * SECTOR)
    for index, value in enumerate(fat):
        if index * 4 >= len(fat_bytes):
            break
        struct.pack_into("<I", fat_bytes, index * 4, value)
    for copy in range(fats):
        offset = (reserved + copy * fat_sectors) * SECTOR
        image[offset:offset + len(fat_bytes)] = fat_bytes
    return bytes(image)


def read_live_esp_uki(volume):
    """Independent walk of a make_live_esp volume: return the BOOTX64.EFI
    bytes by following EFI/BOOT through the FAT."""
    if volume[82:90] != b"FAT32   ":
        raise ValueError("live ESP is not FAT32")
    spc = volume[13]
    reserved = struct.unpack_from("<H", volume, 14)[0]
    fats = volume[16]
    fat_sectors = struct.unpack_from("<I", volume, 36)[0]
    data_start = reserved + fats * fat_sectors
    fat = volume[reserved * SECTOR:(reserved + fat_sectors) * SECTOR]
    cluster_bytes = spc * SECTOR

    def cluster_data(cluster):
        offset = (data_start + (cluster - 2) * spc) * SECTOR
        return volume[offset:offset + cluster_bytes]

    def find(directory_cluster, name):
        entries = cluster_data(directory_cluster)
        wanted = fat_name(name)
        for entry_offset in range(0, len(entries), 32):
            entry = entries[entry_offset:entry_offset + 32]
            if entry[0] == 0:
                break
            if entry[:11] == wanted:
                cluster = struct.unpack_from("<H", entry, 20)[0] << 16 | \
                    struct.unpack_from("<H", entry, 26)[0]
                return cluster, struct.unpack_from("<I", entry, 28)[0]
        raise ValueError("live ESP is missing " + name)

    efi_dir, _ = find(2, "EFI")
    boot_dir, _ = find(efi_dir, "BOOT")
    cluster, size = find(boot_dir, "BOOTX64.EFI")
    output = bytearray()
    while cluster < 0x0FFFFFF8 and len(output) < size:
        output += cluster_data(cluster)
        cluster = struct.unpack_from("<I", fat, cluster * 4)[0] & 0x0FFFFFFF
    return bytes(output[:size])


def release_partition_entries(release):
    """The release image's own GPT entries (ESP at 0, recovery at 1) with
    their first/last LBAs, read from the image rather than re-derived."""
    entries = release[2 * SECTOR:2 * SECTOR + 256]
    esp_first, esp_last = struct.unpack_from("<QQ", entries, 32)[:2]
    rec_first, rec_last = struct.unpack_from("<QQ", entries, 160)[:2]
    return entries, (esp_first, esp_last), (rec_first, rec_last)


def make_bundle_tgz(installer_dir, scripts_dir, intent_bytes, receipt_bytes, node_binary,
                    nbb_dir=None, classpath_dirs=(), default_ssh_key=None,
                    selfhost_elfs=None):
    """Deterministic gzip'd tar of the installer bundle. Determinism is what
    lets the receipt digest mean anything: same inputs, same bytes.

    `classpath_dirs` are source roots the bundled .cljs REQUIRE. They are not
    optional in practice: on 2026-09-09 this repository's tooling moved from
    clojure.string to kotoba.lang.text, the fix was written into nbb.edn, and
    nbb.edn is not on the USB. Measured 2026-09-10 on main: /init hands over to
    install-live.cljk and it dies with `Could not find namespace:
    kotoba.lang.text` before doing anything -- as do install-to-disk.cljk,
    install-intent.cljk and make-provision-record.cljk, the whole chain. The
    node bundle beside this one already carried a cp/ root and already passed
    --classpath; only the install bundle did not.

    A source a script cannot see is not a dependency it has (AGENTS.md). The
    USB is the sharpest case of that: nothing else on the stick declares
    anything."""
    buffer = io.BytesIO()
    entries = []
    seen = {}

    def add(name, data, mode):
        # Two roots merge into one cp/, so a shared relative path would make
        # one file silently replace the other -- and the survivor is whichever
        # root was passed last. Refuse instead.
        if name in seen and seen[name] != data:
            raise ValueError("bundle entry written twice with different bytes: " + name)
        seen[name] = data
        entries.append(("aiueos-installer/" + name, data, mode))

    for path in sorted(Path(installer_dir).iterdir()):
        if path.is_file():
            mode = 0o755 if path.suffix == ".sh" else 0o644
            add(path.name, path.read_bytes(), mode)
    live_dir = Path(installer_dir) / "live"
    if live_dir.is_dir():
        for path in sorted(live_dir.iterdir()):
            if path.is_file():
                add(path.name, path.read_bytes(), 0o644)
    for name in ("install-intent.cljk", "install-to-disk.cljk",
                 "make-provision-record.cljk"):
        add(name, (Path(scripts_dir) / name).read_bytes(), 0o644)
    for src in classpath_dirs:
        base = Path(src)
        # .cljk since the 2026-09-11 rename (root ADR adr-2609111500): every
        # Clojure-shaped source in the workspace carries that extension now,
        # and the scripts the bundle carries are .cljk too. The nbb tree given
        # as --nbb-dir must therefore be the org-babashka-nbb fork, which is
        # the only nbb whose classpath search resolves .cljk; stock nbb loads
        # the entry script and then fails on its first require, which is
        # exactly the ADR-0209 shape. The old extensions stay for a root that
        # still has them.
        sources = (sorted(base.rglob("*.cljk")) + sorted(base.rglob("*.cljc"))
                   + sorted(base.rglob("*.cljs")))
        # A root that contributed nothing must not look like a root nobody
        # asked for. Measured while writing the test for this very function: a
        # misquoted argument passed one path that did not exist, rglob returned
        # empty, the bundle was produced clean, and the scripts on it could not
        # load. The build was green and the stick was dead.
        if not sources:
            raise ValueError("classpath root carries no .cljk/.cljc/.cljs sources: " + str(src))
        for path in sources:
            add("cp/" + path.relative_to(base).as_posix(), path.read_bytes(), 0o644)
    # A guided stick carries no intent: the bundle must not contain one
    # either, or install-live.cljs would find one in the tmpfs and never ask.
    if intent_bytes is not None:
        add("install-intent.json", intent_bytes, 0o644)
    add("release-receipt.json", receipt_bytes, 0o644)
    # The key the guided SSH screen offers as its default (aiueos ADR-0240). A
    # public key, so carrying it is not the secret floor's concern; the person
    # at the console can still type another.
    if default_ssh_key is not None:
        add("default-authorized-key.pub", default_ssh_key, 0o644)
    if selfhost_elfs:
        # The selfhost product (owner direction 2026-10-18, JUN-70 S5):
        # the install chain is amu-compiled kotoba ELFs and the bundle
        # carries NO node-linux-x64 and NO nbb-bundle. The ELFs' spawn
        # grants are sealed at their compile time and name their own
        # bundle paths -- build them with the layout the stick extracts to.
        for elf in selfhost_elfs:
            ep = Path(elf)
            if not ep.is_file():
                raise ValueError("--selfhost-elf is not a file: " + str(ep))
            add(ep.name, ep.read_bytes(), 0o755)
    if node_binary and not selfhost_elfs:
        add("node-linux-x64", Path(node_binary).read_bytes(), 0o755)
    if nbb_dir:
        base = Path(nbb_dir)
        # The fork's version marker, checked where the mistake is made: the
        # prerequisite text says "npm install nbb", which installs stock nbb,
        # and stock nbb resolves no .cljk. Measured 2026-09-15 (aiueos
        # ADR-0217): a stick built against stock nbb 1.5.212 extracted clean,
        # passed install-bundle-test (which runs from the repository, where
        # nbb.edn resolves), and died on the machine with the ADR-0209 shape.
        # A build-time refusal turns that into a red build instead.
        pkg = base / "nbb" / "package.json"
        if not pkg.exists():
            raise ValueError("--nbb-dir does not contain nbb/package.json (is this the nbb tree?): " + str(base))
        version = json.loads(pkg.read_text()).get("version", "")
        if "cljk" not in version:
            raise ValueError(
                "bundled nbb is not the org-babashka-nbb fork (version "
                + version + " carries no cljk marker; stock nbb resolves no "
                ".cljk and the bundle dies on the machine -- aiueos ADR-0217)")
        # A symlinked nbb tree is refused, not followed. `npm install
        # <folder>` (the natural way to install the fork from a sibling
        # checkout) leaves node_modules/nbb as a SYMLINK, and the copy below
        # walks real files only -- the symlink itself is a directory, so
        # nothing under it is copied and the bundle contains no engine while
        # every guard above stays green (the version check reads through the
        # symlink). Measured 2026-10-18: the stick built clean, boot1 reached
        # AIUEOS_LIVE_HANDOVER, and node died with
        #   Error: Cannot find module
        #   '/run/aiueos-installer/nbb-bundle/node_modules/nbb/cli.js'
        # Install the fork from its tarball (npm pack, then install the
        # .tgz) so node_modules/nbb is a real directory.
        if (base / "nbb").is_symlink():
            raise ValueError(
                "--nbb-dir contains nbb as a symlink (" + str(base / "nbb")
                + "); the bundle copy skips symlinked directories and the "
                "stick would carry no nbb engine (measured: boot dies with "
                "MODULE_NOT_FOUND on nbb/cli.js). Install the fork from its "
                "tarball so node_modules/nbb is a real directory.")
        for path in sorted(base.rglob("*")):
            if path.is_symlink() and ".bin" not in path.parts:
                # .bin holds npm's own bin shims, which are symlinks and are
                # excluded from the copy below; only a symlink where a real
                # file must be copied is the silent-drop defect.
                raise ValueError(
                    "--nbb-dir contains a symlink (" + str(path) + "); "
                    "symlinked entries are skipped by the bundle copy and "
                    "the stick would be missing this file at runtime.")
            if path.is_file() and ".bin" not in path.parts:
                add("nbb-bundle/node_modules/" + path.relative_to(base).as_posix(),
                    path.read_bytes(), 0o644)
        # PATH shims for the live environment: install-to-disk.cljs spawns
        # `nbb` and `node` by name, and the tmpfs the bundle lands in is the
        # only writable, executable place on the box.
        add("bin/node", b'#!/bin/sh\nDIR=$(dirname "$(readlink -f "$0")")/..\n'
                        b'exec "$DIR/node-linux-x64" "$@"\n', 0o755)
        # The classpath belongs in the shim, not only in /init: install-live.cljs
        # spawns `kbb --backend sci install-to-disk.cljk` BY NAME, so the second hop resolves
        # through PATH and would otherwise start with an empty classpath even
        # when the first hop had one.
        cp_flag = (b'--classpath "$DIR/cp" ' if classpath_dirs else b'')
        add("bin/nbb", b'#!/bin/sh\nDIR=$(dirname "$(readlink -f "$0")")/..\n'
                       b'exec "$DIR/node-linux-x64" "$DIR/nbb-bundle/node_modules/nbb/cli.js" '
                       + cp_flag + b'"$@"\n',
            0o755)

    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=EPOCH) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            for name, data, mode in sorted(entries):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = mode
                info.mtime = EPOCH
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


NODE_README = """aiueos node USB

Boots the live environment, brings up a network, mints a device identity and
answers its enrolment challenge. It is NOT an installer: it writes nothing to
any internal disk.

The device key is generated into a tmpfs, so it does not survive a reboot --
this stick makes a claimable box, not a durable node identity. See
os/aiueos/scripts/node-boot.cljk.
"""


def make_node_bundle_tgz(scripts_dir, classpath_dirs, node_binary, nbb_dir):
    """The payload a node USB carries: the boot entry, the attest agent, and
    the pure sources both of them decide with -- not restated here, copied from
    the repositories that own them."""
    buffer = io.BytesIO()
    entries = []

    def add(name, data, mode):
        entries.append(("aiueos-node/" + name, data, mode))

    for name in ("node-boot.cljk", "device-attest-agent.cljk"):
        add(name, (Path(scripts_dir) / name).read_bytes(), 0o644)
    for src in classpath_dirs:
        base = Path(src)
        for path in (sorted(base.rglob("*.cljk")) + sorted(base.rglob("*.cljc"))
                     + sorted(base.rglob("*.cljs"))):
            add("cp/" + path.relative_to(base).as_posix(), path.read_bytes(), 0o644)
    if node_binary:
        add("node-linux-x64", Path(node_binary).read_bytes(), 0o755)
    if nbb_dir:
        base = Path(nbb_dir)
        for path in sorted(base.rglob("*")):
            if path.is_file() and ".bin" not in path.parts:
                add("nbb-bundle/node_modules/" + path.relative_to(base).as_posix(),
                    path.read_bytes(), 0o644)
    add("bin/node", b'#!/bin/sh\nDIR=$(dirname "$(readlink -f "$0")")/..\n'
                    b'exec "$DIR/node-linux-x64" "$@"\n', 0o755)
    add("bin/nbb", b'#!/bin/sh\nDIR=$(dirname "$(readlink -f "$0")")/..\n'
                   b'exec "$DIR/node-linux-x64" "$DIR/nbb-bundle/node_modules/nbb/cli.js" "$@"\n',
        0o755)

    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=EPOCH) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            for name, data, mode in sorted(entries):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = mode
                info.mtime = EPOCH
                tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def protective_mbr(total_sectors):
    """A GPT protective MBR with no boot code. The install USB copies the
    release image's, which carries a BIOS refusal stub; a node stick has no
    release image to copy from, so it gets the plain protective entry."""
    mbr = bytearray(SECTOR)
    mbr[446 + 4] = 0xEE
    struct.pack_into("<II", mbr, 446 + 8, 1, min(total_sectors - 1, 0xFFFFFFFF))
    mbr[510:512] = b"\x55\xaa"
    return bytes(mbr)


def build_node_image(args):
    """A bootable node USB: p1 is the live UKI, p2 is the node payload. No
    release image and no install intent, because this stick installs nothing --
    which is also why it can exist while the bare-metal image still does not
    boot on real hardware."""
    uki = Path(args.live_uki).read_bytes()
    scripts_dir = Path(__file__).resolve().parent
    classpath = [d for d in (args.classpath or []) if d]
    bundle = make_node_bundle_tgz(scripts_dir, classpath, args.node_binary, args.nbb_dir)
    config = json.dumps({"schema": "aiueos.node-config.v1",
                         "endpoint": args.endpoint,
                         "intervalSeconds": args.interval}, indent=2, sort_keys=True) + "\n"
    files = {"NODE.JSN": config.encode("utf-8"), "NODE.TGZ": bundle}
    names = ["NODE.JSN", "NODE.TGZ"]
    files["SHA256S.TXT"] = "".join(
        "%s  %s\n" % (sha256_bytes(files[n]), n) for n in names).encode("ascii")
    files["README.TXT"] = NODE_README.encode("utf-8")

    content = sum(len(v) for v in files.values())
    payload_sectors = ((content + content // 4) // SECTOR // ALIGN + 9) * ALIGN
    payload_sectors = max(payload_sectors, 68 * 1024 * 2)
    esp_sectors = max(((len(uki) * 2) // SECTOR // ALIGN + 2) * ALIGN, 68 * 1024 * 2)
    esp_first = 2048
    payload_first = ((esp_first + esp_sectors + ALIGN - 1) // ALIGN) * ALIGN
    payload_last = payload_first + payload_sectors - 1
    # p3: writable node state. FAT32 needs 65525 clusters, so it inherits the
    # same floor the payload has -- the price of a filesystem every rescue
    # environment can already read.
    state_sectors = 68 * 1024 * 2
    state_first = ((payload_last + 1 + ALIGN - 1) // ALIGN) * ALIGN
    state_last = state_first + state_sectors - 1
    total = ((state_last + 1 + GPT_ENTRY_SECTORS + 1 + ALIGN - 1) // ALIGN) * ALIGN

    disk = bytearray(total * SECTOR)
    disk[:SECTOR] = protective_mbr(total)

    entries = bytearray(GPT_ENTRY_SECTORS * SECTOR)
    esp_name = "aiueos live esp".encode("utf-16le")
    entries[:16] = ESP_TYPE.bytes_le
    entries[16:32] = LIVE_ESP_GUID.bytes_le
    struct.pack_into("<QQQ", entries, 32, esp_first, esp_first + esp_sectors - 1, 0)
    entries[56:56 + len(esp_name)] = esp_name
    payload_name = "aiueos node payload".encode("utf-16le")
    entries[128:144] = BASIC_DATA_TYPE.bytes_le
    entries[144:160] = PAYLOAD_GUID.bytes_le
    struct.pack_into("<QQQ", entries, 160, payload_first, payload_last, 0)
    entries[184:184 + len(payload_name)] = payload_name
    state_name = "aiueos node state".encode("utf-16le")
    entries[256:272] = BASIC_DATA_TYPE.bytes_le
    entries[272:288] = NODE_STATE_GUID.bytes_le
    struct.pack_into("<QQQ", entries, 288, state_first, state_last, 0)
    entries[312:312 + len(state_name)] = state_name
    entries_crc = binascii.crc32(entries) & 0xFFFFFFFF

    disk[esp_first * SECTOR:(esp_first + esp_sectors) * SECTOR] = make_live_esp(esp_sectors, uki)
    disk[payload_first * SECTOR:(payload_last + 1) * SECTOR] = \
        make_payload_fat32(payload_sectors, files, payload_first,
                           names=["NODE.JSN", "NODE.TGZ", "SHA256S.TXT", "README.TXT"])
    # Empty writable volume: one root entry so the FAT is valid, and otherwise
    # free space for the key the node mints on its first boot.
    disk[state_first * SECTOR:(state_last + 1) * SECTOR] = make_payload_fat32(
        state_sectors,
        {"README.TXT": b"aiueos node state. The device key lives here.\r\n"},
        state_first, names=["README.TXT"])
    disk[2 * SECTOR:(2 + GPT_ENTRY_SECTORS) * SECTOR] = entries
    disk[SECTOR:2 * SECTOR] = gpt_header(1, total - 1, 2, entries_crc, total)
    backup_entries_lba = total - 1 - GPT_ENTRY_SECTORS
    disk[backup_entries_lba * SECTOR:(backup_entries_lba + GPT_ENTRY_SECTORS) * SECTOR] = entries
    disk[-SECTOR:] = gpt_header(total - 1, 1, backup_entries_lba, entries_crc, total)

    Path(args.output).write_bytes(disk)
    receipt = {
        "schema": "aiueos.node-usb-receipt.v1",
        "created": datetime.fromtimestamp(EPOCH, timezone.utc).isoformat().replace("+00:00", "Z"),
        "boot": {"mode": "live-node", "espFirstLba": esp_first, "espSectors": esp_sectors,
                 "uki": {"bytes": len(uki), "sha256": sha256_bytes(uki)}},
        "disk": {"bytes": len(disk), "sha256": sha256_bytes(bytes(disk))},
        "node": {"endpoint": args.endpoint,
                 "keyDurability": "stick-state-partition",
                 "stateGuid": str(NODE_STATE_GUID),
                 "stateFirstLba": state_first, "stateSectors": state_sectors},
        "payload": {"firstLba": payload_first, "lastLba": payload_last,
                    "type": str(BASIC_DATA_TYPE), "guid": str(PAYLOAD_GUID),
                    "files": {n: {"bytes": len(files[n]), "sha256": sha256_bytes(files[n])}
                              for n in names}},
    }
    if args.receipt:
        Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8")
    print(args.output)


def gpt_header(current, backup, entries_lba, entries_crc, total_sectors):
    header = bytearray(SECTOR)
    last_usable = total_sectors - GPT_ENTRY_SECTORS - 2
    struct.pack_into("<8sIIIIQQQQ16sQIII", header, 0, b"EFI PART", 0x00010000, 92, 0, 0,
                     current, backup, 34, last_usable, DISK_GUID.bytes_le,
                     entries_lba, GPT_ENTRY_COUNT, GPT_ENTRY_SIZE, entries_crc)
    struct.pack_into("<I", header, 16, binascii.crc32(header[:92]) & 0xFFFFFFFF)
    return header


def build(args):
    # Before any I/O: an argument error should not cost 64 MiB of reading, and
    # more importantly it should not be reported after a release image failed
    # to open, which is a different problem with a different fix.
    if args.guided and args.intent:
        raise ValueError("--guided and --intent name two different products; pick one")
    if not args.guided and not args.intent:
        raise ValueError("give --intent <file>, or --guided for a stick that asks")
    release = Path(args.release_image).read_bytes()
    release_receipt_bytes = Path(args.release_receipt).read_bytes()
    receipt_json = json.loads(release_receipt_bytes)
    if len(release) != RELEASE_SECTORS * SECTOR:
        raise ValueError("release image is not the expected 64 MiB geometry")
    if (len(release) != receipt_json["disk"]["bytes"]
            or sha256_bytes(release) != receipt_json["disk"]["sha256"]):
        raise ValueError("release image does not match its build receipt")
    # Not "intent if given": a forgotten --intent would quietly produce a
    # different product, and the two differ in who is allowed to erase a disk
    # without being asked. The absence of an intent has to be stated, not
    # inferred. (Checked at the top of this function, before any I/O.)
    if args.guided:
        intent_bytes = None
        intent = None
    else:
        intent_bytes = Path(args.intent).read_bytes()
        intent = json.loads(intent_bytes)
        if intent.get("schema") != "aiueos.install-intent.v1":
            raise ValueError("intent is not aiueos.install-intent.v1")
        if intent["release"]["disk"]["sha256"] != receipt_json["disk"]["sha256"]:
            raise ValueError("intent names a different release image digest")
    names = payload_names_for(args.guided)
    default_ssh_key = None
    if args.default_ssh_key:
        if not args.guided:
            raise ValueError("--default-ssh-key only means something on a --guided stick; "
                             "an intent already names its key")
        default_ssh_key = Path(args.default_ssh_key).read_bytes()
        if not default_ssh_key.startswith(b"ssh-ed25519 "):
            raise ValueError("--default-ssh-key must be one OpenSSH ssh-ed25519 public key line")

    scripts_dir = Path(__file__).resolve().parent
    bundle = make_bundle_tgz(args.installer_dir, scripts_dir, intent_bytes,
                             release_receipt_bytes, args.node_binary, args.nbb_dir,
                             classpath_dirs=[d for d in (args.classpath or []) if d],
                             default_ssh_key=default_ssh_key,
                             selfhost_elfs=args.selfhost_elf)
    files = {
        "RELEASE.IMG": release,
        "RECEIPT.JSN": release_receipt_bytes,
        "INSTALL.TGZ": bundle,
    }
    if intent_bytes is not None:
        files["INTENT.JSN"] = intent_bytes
    sha_lines = "".join("%s  %s\n" % (sha256_bytes(files[n]), n)
                        for n in names if n not in ("SHA256S.TXT", "README.TXT"))
    files["SHA256S.TXT"] = sha_lines.encode("ascii")
    files["README.TXT"] = (GUIDED_README_TEXT if args.guided
                           else README_TEXT).encode("utf-8")

    content = sum(len(v) for v in files.values())
    payload_sectors = ((content + content // 4) // SECTOR // ALIGN + 9) * ALIGN
    payload_sectors = max(payload_sectors, 68 * 1024 * 2)  # FAT32 floor with margin

    uki = Path(args.live_uki).read_bytes() if args.live_uki else None
    if uki is not None:
        # Live-installer layout: p1 boots the installer UKI, p2 keeps the
        # release recovery volume (aiueos itself, as the independent
        # fallback), p3 carries the payload. LBAs are fresh; only the
        # recovery *bytes* and its type/GUID/name are the release image's.
        _, _, (rec_first, rec_last) = release_partition_entries(release)
        rec_sectors = rec_last - rec_first + 1
        esp_sectors = max(((len(uki) * 2) // SECTOR // ALIGN + 2) * ALIGN, 68 * 1024 * 2)
        esp_first = 2048
        p2_first = ((esp_first + esp_sectors + ALIGN - 1) // ALIGN) * ALIGN
        payload_first = ((p2_first + rec_sectors + ALIGN - 1) // ALIGN) * ALIGN
    else:
        payload_first = PAYLOAD_FIRST
    payload = make_payload_fat32(payload_sectors, files, payload_first, names)

    payload_last = payload_first + payload_sectors - 1
    total = payload_last + 1 + GPT_ENTRY_SECTORS + 1
    total = ((total + ALIGN - 1) // ALIGN) * ALIGN

    disk = bytearray(total * SECTOR)
    mbr = bytearray(release[:SECTOR])
    struct.pack_into("<II", mbr, 446 + 8, 1, total - 1)
    disk[:SECTOR] = mbr

    entries = bytearray(GPT_ENTRY_SECTORS * SECTOR)
    if uki is not None:
        esp = make_live_esp(esp_sectors, uki)
        name = "aiueos live esp".encode("utf-16le")
        entries[:16] = ESP_TYPE.bytes_le
        entries[16:32] = LIVE_ESP_GUID.bytes_le
        struct.pack_into("<QQQ", entries, 32, esp_first, esp_first + esp_sectors - 1, 0)
        entries[56:56 + len(name)] = name
        entries[128:256] = release[2 * SECTOR + 128:2 * SECTOR + 256]
        struct.pack_into("<QQ", entries, 160, p2_first, p2_first + rec_sectors - 1)
        disk[esp_first * SECTOR:(esp_first + esp_sectors) * SECTOR] = esp
        disk[p2_first * SECTOR:(p2_first + rec_sectors) * SECTOR] = \
            release[rec_first * SECTOR:(rec_last + 1) * SECTOR]
    else:
        # ESP and recovery entries verbatim from the release image's own GPT:
        # same type GUIDs, partition GUIDs, LBAs and names, so the boot path
        # the usb-boot contract proved is untouched.
        entries[:256] = release[2 * SECTOR:2 * SECTOR + 256]
        esp_first = 2048
        release_backup_lba = RELEASE_SECTORS - 1 - GPT_ENTRY_SECTORS
        disk[esp_first * SECTOR:release_backup_lba * SECTOR] = \
            release[esp_first * SECTOR:release_backup_lba * SECTOR]
    name = "aiueos install payload".encode("utf-16le")
    entries[256:272] = BASIC_DATA_TYPE.bytes_le
    entries[272:288] = PAYLOAD_GUID.bytes_le
    struct.pack_into("<QQQ", entries, 288, payload_first, payload_last, 0)
    entries[312:312 + len(name)] = name
    entries_crc = binascii.crc32(entries) & 0xFFFFFFFF

    disk[2 * SECTOR:(2 + GPT_ENTRY_SECTORS) * SECTOR] = entries
    disk[SECTOR:2 * SECTOR] = gpt_header(1, total - 1, 2, entries_crc, total)
    backup_entries_lba = total - 1 - GPT_ENTRY_SECTORS
    disk[backup_entries_lba * SECTOR:(backup_entries_lba + GPT_ENTRY_SECTORS) * SECTOR] = entries
    disk[-SECTOR:] = gpt_header(total - 1, 1, backup_entries_lba, entries_crc, total)
    disk[payload_first * SECTOR:(payload_last + 1) * SECTOR] = payload

    Path(args.output).write_bytes(disk)
    verify_image(args.output, args.release_image)

    receipt = {
        "schema": "aiueos.install-usb-receipt.v1",
        "created": datetime.fromtimestamp(EPOCH, timezone.utc).isoformat().replace("+00:00", "Z"),
        "boot": ({"mode": "live-installer",
                  "runtime": ("selfhost" if getattr(args, "selfhost_elf", None)
                              else "node"),
                  "espFirstLba": esp_first, "espSectors": esp_sectors,
                  "uki": {"bytes": len(uki), "sha256": sha256_bytes(uki)}}
                 if uki is not None else {"mode": "aiueos-direct"}),
        "disk": {"bytes": len(disk), "sha256": sha256_bytes(bytes(disk))},
        "release": {"receiptSha256": sha256_bytes(release_receipt_bytes),
                    "diskSha256": receipt_json["disk"]["sha256"]},
        # The key is always present. A reader that had to tell "guided stick"
        # from "receipt written before guided existed" by an absent key would
        # be guessing.
        "intent": ({"authoring": "guided-at-the-machine", "sha256": None}
                   if intent_bytes is None else
                   {"authoring": "authored-ahead-of-time",
                    "sha256": sha256_bytes(intent_bytes),
                    "hostname": intent.get("hostname"),
                    "mode": intent.get("mode")}),
        "payload": {"firstLba": payload_first, "lastLba": payload_last,
                    "type": str(BASIC_DATA_TYPE), "guid": str(PAYLOAD_GUID),
                    "files": {n: {"bytes": len(files[n]), "sha256": sha256_bytes(files[n])}
                              for n in names}},
    }
    Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8")
    print(args.output)


def check_payload_consistency(files):
    """Decide which product a payload is, and refuse anything in between.

    A guided stick carries no INTENT.JSN. That absence is the entire
    difference between "installs unattended" and "installs nothing without a
    person", so it is cross-checked against SHA256S.TXT rather than read off
    the file list: a payload that carries an intent nobody digested, or
    digests one it does not carry, is not a product this builder makes and
    must not be verified into one.

    Returns True for a guided payload, False for one carrying an intent."""
    listed = set()
    for line in files["SHA256S.TXT"].decode("ascii").splitlines():
        digest, name = line.split("  ", 1)
        listed.add(name)
        if name not in files:
            raise ValueError("SHA256S.TXT lists a file the payload does not carry: " + name)
        if sha256_bytes(files[name]) != digest:
            raise ValueError("payload digest mismatch for " + name)
    carried = {n for n in files if n not in ("SHA256S.TXT", "README.TXT")}
    if carried != listed:
        raise ValueError("payload carries files SHA256S.TXT does not list: "
                         + ",".join(sorted(carried - listed)))
    return "INTENT.JSN" not in files


def verify_image(path, release_image):
    disk = Path(path).read_bytes()
    release = Path(release_image).read_bytes()
    total = len(disk) // SECTOR
    if len(disk) % SECTOR:
        raise ValueError("image is not sector-aligned")
    header = disk[SECTOR:2 * SECTOR]
    if header[:8] != b"EFI PART":
        raise ValueError("missing GPT header")
    checked = bytearray(header[:92])
    stored = struct.unpack_from("<I", checked, 16)[0]
    struct.pack_into("<I", checked, 16, 0)
    if binascii.crc32(checked) & 0xFFFFFFFF != stored:
        raise ValueError("invalid primary GPT header CRC")
    if header[56:72] != DISK_GUID.bytes_le:
        raise ValueError("disk GUID is not the install-USB GUID")
    entries = disk[2 * SECTOR:(2 + GPT_ENTRY_SECTORS) * SECTOR]
    if binascii.crc32(entries) & 0xFFFFFFFF != struct.unpack_from("<I", header, 88)[0]:
        raise ValueError("invalid GPT entry-array CRC")
    live = entries[16:32] == LIVE_ESP_GUID.bytes_le
    if live:
        if entries[:16] != ESP_TYPE.bytes_le:
            raise ValueError("live ESP entry has the wrong type GUID")
        esp_first, esp_last = struct.unpack_from("<QQ", entries, 32)[:2]
        uki = read_live_esp_uki(disk[esp_first * SECTOR:(esp_last + 1) * SECTOR])
        if uki[:2] != b"MZ" or b".linux" not in uki[:4096] or b".initrd" not in uki[:4096]:
            raise ValueError("live ESP BOOTX64.EFI is not a UKI")
        rel_entries, _, (rec_first, rec_last) = release_partition_entries(release)
        if entries[128:160] != rel_entries[128:160] or \
                entries[184:256] != rel_entries[184:256]:
            raise ValueError("recovery entry type/GUID/name differ from the release image")
        p2_first, p2_last = struct.unpack_from("<QQ", entries, 160)[:2]
        if (disk[p2_first * SECTOR:(p2_last + 1) * SECTOR]
                != release[rec_first * SECTOR:(rec_last + 1) * SECTOR]):
            raise ValueError("recovery bytes differ from the release image")
    else:
        if entries[:256] != release[2 * SECTOR:2 * SECTOR + 256]:
            raise ValueError("ESP/recovery entries differ from the release image")
    if entries[256:272] != BASIC_DATA_TYPE.bytes_le or entries[272:288] != PAYLOAD_GUID.bytes_le:
        raise ValueError("invalid payload partition entry")
    payload_first, payload_last = struct.unpack_from("<QQ", entries, 288)[:2]
    if payload_first % ALIGN:
        raise ValueError("payload partition is not 1 MiB aligned")
    if not live and payload_first != PAYLOAD_FIRST:
        raise ValueError("payload partition does not start at the release boundary")
    backup_entries_lba = total - 1 - GPT_ENTRY_SECTORS
    if disk[backup_entries_lba * SECTOR:(backup_entries_lba + GPT_ENTRY_SECTORS) * SECTOR] != entries:
        raise ValueError("backup GPT entry array differs")
    backup = bytearray(disk[-SECTOR:][:92])
    stored = struct.unpack_from("<I", backup, 16)[0]
    struct.pack_into("<I", backup, 16, 0)
    if disk[-SECTOR:][:8] != b"EFI PART" or binascii.crc32(backup) & 0xFFFFFFFF != stored:
        raise ValueError("invalid backup GPT header CRC")

    if not live:
        esp_first = 2048
        release_backup_lba = RELEASE_SECTORS - 1 - GPT_ENTRY_SECTORS
        if (disk[esp_first * SECTOR:release_backup_lba * SECTOR]
                != release[esp_first * SECTOR:release_backup_lba * SECTOR]):
            raise ValueError("ESP/recovery bytes differ from the release image")

    payload = disk[payload_first * SECTOR:(payload_last + 1) * SECTOR]
    files = read_payload_fat32(payload)

    # Which product this is, decided from the image alone. A guided stick
    # carries no INTENT.JSN; the absence is the whole difference, so it is
    # cross-checked against SHA256S.TXT rather than taken at face value --
    # a stick that carries an intent nobody digested, or digests one it does
    # not carry, is not a product this builder makes.
    guided = check_payload_consistency(files)
    for name in payload_names_for(guided):
        if name not in files:
            raise ValueError("payload is missing " + name)
    if files["RELEASE.IMG"] != release:
        raise ValueError("embedded RELEASE.IMG differs from the release image")
    release_receipt = json.loads(files["RECEIPT.JSN"])
    if sha256_bytes(files["RELEASE.IMG"]) != release_receipt["disk"]["sha256"]:
        raise ValueError("embedded RELEASE.IMG does not match embedded receipt")
    if not guided:
        intent = json.loads(files["INTENT.JSN"])
        if intent["release"]["disk"]["sha256"] != release_receipt["disk"]["sha256"]:
            raise ValueError("embedded intent names a different release digest")
    # The runtime is decided from the bundle's own names (image alone):
    # selfhost = the chain is kotoba ELFs and the bundle carries no
    # node-linux-x64 (owner direction 2026-10-18, JUN-70 S5).
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(files["INSTALL.TGZ"]))) as tar:
        bundle_names = tar.getnames()
    if any(n == "node-linux-x64" for n in bundle_names):
        runtime = "node"
    elif any(n.endswith(".elf") for n in bundle_names):
        runtime = "selfhost"
    else:
        runtime = "scripts"
    if runtime == "selfhost" and any(n == "node-linux-x64" for n in bundle_names):
        raise ValueError("selfhost bundle carries node-linux-x64")
    print("AIUEOS_INSTALL_USB_IMAGE_OK mode=%s authoring=%s runtime=%s bytes=%d files=%d"
          % ("live-installer" if live else "aiueos-direct",
             "guided-at-the-machine" if guided else "authored-ahead-of-time",
             runtime, len(disk), len(files)))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build")
    b.add_argument("--release-image", required=True)
    b.add_argument("--release-receipt", required=True)
    b.add_argument("--intent",
                   help="the install intent this stick carries. Exactly one of "
                        "--intent / --guided.")
    b.add_argument("--guided", action="store_true",
                   help="build a stick that carries NO intent and asks at the "
                        "machine (guided-install.cljk, ADR-0208/0210).")
    b.add_argument("--installer-dir", required=True)
    b.add_argument("--classpath", action="append",
                   help="a source root the bundled .cljs require (repeatable): "
                        "text/src, the aiueos src root. Without them the bundle "
                        "extracts and every script dies on a missing namespace.")
    b.add_argument("--node-binary")
    b.add_argument("--nbb-dir")
    b.add_argument("--selfhost-elf", action="append",
                   help="an install-chain ELF to bundle (repeatable); the "
                        "selfhost product then carries no node/nbb")
    b.add_argument("--live-uki")
    b.add_argument("--default-ssh-key",
                   help="guided sticks only: an ssh-ed25519 public key file the SSH "
                        "screen offers as its default (ADR-0240)")
    b.add_argument("--output", required=True)

    b.add_argument("--receipt", required=True)

    n = sub.add_parser("node-image", help="bootable node USB: live UKI + node payload")
    n.add_argument("--live-uki", required=True)
    n.add_argument("--endpoint", required=True)
    n.add_argument("--interval", type=int, default=15)
    n.add_argument("--classpath", action="append",
                   help="a source root to carry (repeatable): grant/src, text/src, sekisho/src")
    n.add_argument("--node-binary", required=True)
    n.add_argument("--nbb-dir", required=True)
    n.add_argument("--receipt")
    n.add_argument("--output", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--image", required=True)
    v.add_argument("--release-image", required=True)
    args = parser.parse_args()
    if args.command == "build":
        build(args)
    elif args.command == "node-image":
        build_node_image(args)
    else:
        verify_image(args.image, args.release_image)


if __name__ == "__main__":
    main()
