#!/usr/bin/env python3
"""Build and verify the deterministic aiueos GPT/ESP release image and ISO."""

import argparse
import binascii
import hashlib
import json
import os
import struct
import uuid
from datetime import datetime, timezone
from pathlib import Path

SECTOR = 512
DISK_SECTORS = 131072  # 64 MiB
ESP_FIRST = 2048
GPT_ENTRY_COUNT = 128
GPT_ENTRY_SIZE = 128
GPT_ENTRY_SECTORS = GPT_ENTRY_COUNT * GPT_ENTRY_SIZE // SECTOR
GPT_BACKUP_ENTRIES = DISK_SECTORS - 1 - GPT_ENTRY_SECTORS
# The recovery partition is a second, independent FAT16 ESP at the end of the
# disk carrying known-good copies of the boot artifacts. Firmware falls back
# to it when the primary ESP's kernel fails loader admission.
RECOVERY_SECTORS = 32768  # 16 MiB, byte-identical to the ISO El Torito boot image
RECOVERY_LAST = GPT_BACKUP_ENTRIES - 1
RECOVERY_FIRST = RECOVERY_LAST - RECOVERY_SECTORS + 1
ESP_LAST = RECOVERY_FIRST - 1
ESP_SECTORS = ESP_LAST - ESP_FIRST + 1
ESP_TYPE = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
NAMESPACE = uuid.UUID("18b3fb94-8713-54c4-9e3a-f0c78a88d192")
DISK_GUID = uuid.uuid5(NAMESPACE, "aiueos-release-disk-v1")
ESP_GUID = uuid.uuid5(NAMESPACE, "aiueos-esp-v1")
RECOVERY_GUID = uuid.uuid5(NAMESPACE, "aiueos-recovery-esp-v1")
VOLUME_ID = 0x41495545

ISO_BLOCK = 2048
# The El Torito EFI boot image is FAT16 so its 512-byte virtual sector count
# (32768) stays inside the catalog entry's 16-bit field; the on-disk GPT ESP
# stays FAT32.
ISO_BOOT_SECTORS = 32768  # 16 MiB
ISO_PVD_LBA = 16
ISO_BRVD_LBA = 17
ISO_TERMINATOR_LBA = 18
ISO_CATALOG_LBA = 19
ISO_ROOT_LBA = 20
ISO_LPATH_LBA = 21
ISO_MPATH_LBA = 22
ISO_BOOT_IMAGE_LBA = 23
ISO_BOOT_BLOCKS = ISO_BOOT_SECTORS * SECTOR // ISO_BLOCK
ISO_VOLUME_BLOCKS = ISO_BOOT_IMAGE_LBA + ISO_BOOT_BLOCKS


def sha256(path):
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
    entry[:11] = fat_name(name) if name not in (".", "..") else name.encode().ljust(11, b" ")
    entry[11] = attr
    # Fixed 1980-01-01 00:00 FAT timestamps (all time fields remain zero).
    struct.pack_into("<H", entry, 16, 0x0021)
    struct.pack_into("<H", entry, 18, 0x0021)
    struct.pack_into("<H", entry, 24, 0x0021)
    struct.pack_into("<H", entry, 20, cluster >> 16)
    struct.pack_into("<H", entry, 26, cluster & 0xFFFF)
    struct.pack_into("<I", entry, 28, size)
    return bytes(entry)


def make_fat32(efi, kernel, initramfs):
    reserved, fats = 32, 2
    # Solve fat_sectors >= ceil((data_clusters + 2) * 4 / sector_size)
    # directly; a fixed-point iteration can oscillate between adjacent values.
    denominator = SECTOR + fats * 4
    fat_sectors = ((ESP_SECTORS - reserved + 2) * 4 + denominator - 1) // denominator
    data_start = reserved + fats * fat_sectors
    clusters = ESP_SECTORS - data_start
    if clusters < 65525:
        raise ValueError("ESP is too small for FAT32")

    image = bytearray(ESP_SECTORS * SECTOR)
    boot = bytearray(SECTOR)
    boot[:3] = b"\xeb\x58\x90"
    boot[3:11] = b"AIUEOS  "
    struct.pack_into("<HBHBHHBHHHII", boot, 11, SECTOR, 1, reserved, fats, 0, 0,
                     0xF8, 0, 63, 255, ESP_FIRST, ESP_SECTORS)
    struct.pack_into("<IHHIHH", boot, 36, fat_sectors, 0, 0, 2, 1, 6)
    boot[64] = 0x80
    boot[66] = 0x29
    struct.pack_into("<I", boot, 67, VOLUME_ID)
    boot[71:82] = b"AIUEOS ESP "
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
    next_cluster = 2

    def allocate(payload):
        nonlocal next_cluster
        count = max(1, (len(payload) + SECTOR - 1) // SECTOR)
        first = next_cluster
        for index in range(count):
            cluster = next_cluster + index
            fat[cluster] = 0x0FFFFFFF if index == count - 1 else cluster + 1
            offset = (data_start + cluster - 2) * SECTOR
            image[offset:offset + len(payload[index * SECTOR:(index + 1) * SECTOR])] = payload[index * SECTOR:(index + 1) * SECTOR]
        next_cluster += count
        return first

    # Allocate directories first so their stable cluster numbers can be referenced.
    root_cluster, efi_cluster, boot_cluster, aiueos_cluster = 2, 3, 4, 5
    for cluster in range(2, 6):
        fat[cluster] = 0x0FFFFFFF
    next_cluster = 6
    efi_bytes, kernel_bytes = Path(efi).read_bytes(), Path(kernel).read_bytes()
    initramfs_bytes = Path(initramfs).read_bytes()
    efi_file_cluster = allocate(efi_bytes)
    kernel_file_cluster = allocate(kernel_bytes)
    initramfs_file_cluster = allocate(initramfs_bytes)

    directories = {
        root_cluster: dirent("EFI", 0x10, efi_cluster),
        efi_cluster: dirent(".", 0x10, efi_cluster) + dirent("..", 0x10, root_cluster) +
                     dirent("BOOT", 0x10, boot_cluster) + dirent("AIUEOS", 0x10, aiueos_cluster),
        boot_cluster: dirent(".", 0x10, boot_cluster) + dirent("..", 0x10, efi_cluster) +
                      dirent("BOOTX64.EFI", 0x20, efi_file_cluster, len(efi_bytes)),
        aiueos_cluster: dirent(".", 0x10, aiueos_cluster) + dirent("..", 0x10, efi_cluster) +
                        dirent("KERNEL.ELF", 0x20, kernel_file_cluster, len(kernel_bytes)) +
                        dirent("INITRD.IMG", 0x20, initramfs_file_cluster, len(initramfs_bytes)),
    }
    for cluster, payload in directories.items():
        offset = (data_start + cluster - 2) * SECTOR
        image[offset:offset + len(payload)] = payload

    fat_bytes = bytearray(fat_sectors * SECTOR)
    for index, value in enumerate(fat):
        if index * 4 >= len(fat_bytes):
            break
        struct.pack_into("<I", fat_bytes, index * 4, value)
    for copy in range(fats):
        offset = (reserved + copy * fat_sectors) * SECTOR
        image[offset:offset + len(fat_bytes)] = fat_bytes
    return bytes(image)


# Legacy-BIOS stage-1 test fixture placed in the protective MBR's boot-code
# area. aiueos does not support BIOS boot; this stub makes the legacy path an
# explicit, deterministic refusal instead of a firmware hang. Real-mode
# disassembly (org 0x7C00, message at 0x7C1E):
#   FA                cli
#   FC                cld
#   31 C0             xor  ax, ax
#   8E D8             mov  ds, ax
#   BE 1E 7C          mov  si, 0x7C1E
#   AC                lodsb                 ; loop
#   84 C0             test al, al
#   74 04             jz   done
#   E6 E9             out  0xE9, al         ; QEMU isa-debugcon
#   EB F7             jmp  loop
#   66 B8 0B 00 00 00 mov  eax, 0x0B        ; done
#   66 E7 F4          out  0xF4, eax        ; QEMU isa-debug-exit -> status 23
#   F4                hlt                   ; no debug-exit device: halt forever
#   EB FD             jmp  hlt
BIOS_STUB_MESSAGE = b"AIUEOS_BIOS_STUB uefi-required\n\x00"
BIOS_STUB = (bytes.fromhex("fafc31c08ed8be1e7cac84c07404e6e9ebf7"
                           "66b80b00000066e7f4f4ebfd") + BIOS_STUB_MESSAGE)

FAT16_RESERVED = 4
FAT16_FATS = 2
FAT16_FAT_SECTORS = 32
FAT16_ROOT_SECTORS = 32
FAT16_CLUSTER_SECTORS = 4
FAT16_DATA_START = FAT16_RESERVED + FAT16_FATS * FAT16_FAT_SECTORS + FAT16_ROOT_SECTORS
FAT16_CLUSTERS = (ISO_BOOT_SECTORS - FAT16_DATA_START) // FAT16_CLUSTER_SECTORS


def make_fat16(efi, kernel, initramfs, recovery_marker=False, extra_files=None):
    if not 4085 <= FAT16_CLUSTERS <= 65524:
        raise ValueError("boot image cluster count is not FAT16")
    if (FAT16_CLUSTERS + 2) * 2 > FAT16_FAT_SECTORS * SECTOR:
        raise ValueError("boot image FAT does not cover its clusters")
    image = bytearray(ISO_BOOT_SECTORS * SECTOR)
    boot = bytearray(SECTOR)
    boot[:3] = b"\xeb\x3c\x90"
    boot[3:11] = b"AIUEOS  "
    struct.pack_into("<HBHBHHBHHHII", boot, 11, SECTOR, FAT16_CLUSTER_SECTORS,
                     FAT16_RESERVED, FAT16_FATS, FAT16_ROOT_SECTORS * SECTOR // 32,
                     ISO_BOOT_SECTORS, 0xF8, FAT16_FAT_SECTORS, 63, 255, 0, 0)
    boot[36] = 0x80
    boot[38] = 0x29
    struct.pack_into("<I", boot, 39, VOLUME_ID)
    boot[43:54] = b"AIUEOS ISO "
    boot[54:62] = b"FAT16   "
    boot[510:512] = b"\x55\xaa"
    image[:SECTOR] = boot

    fat = [0] * (FAT16_CLUSTERS + 2)
    fat[0], fat[1] = 0xFFF8, 0xFFFF
    next_cluster = 2

    def allocate(payload, cluster_count=None):
        nonlocal next_cluster
        count = cluster_count or max(
            1, (len(payload) + FAT16_CLUSTER_SECTORS * SECTOR - 1) // (FAT16_CLUSTER_SECTORS * SECTOR))
        first = next_cluster
        for index in range(count):
            cluster = next_cluster + index
            fat[cluster] = 0xFFFF if index == count - 1 else cluster + 1
            offset = (FAT16_DATA_START + (cluster - 2) * FAT16_CLUSTER_SECTORS) * SECTOR
            chunk = payload[index * FAT16_CLUSTER_SECTORS * SECTOR:(index + 1) * FAT16_CLUSTER_SECTORS * SECTOR]
            image[offset:offset + len(chunk)] = chunk
        next_cluster += count
        return first

    efi_bytes, kernel_bytes = Path(efi).read_bytes(), Path(kernel).read_bytes()
    initramfs_bytes = Path(initramfs).read_bytes()
    efi_dir = allocate(dirent(".", 0x10, 0) + dirent("..", 0x10, 0), 1)
    boot_dir = allocate(dirent(".", 0x10, 0) + dirent("..", 0x10, efi_dir), 1)
    aiueos_dir = allocate(dirent(".", 0x10, 0) + dirent("..", 0x10, efi_dir), 1)
    efi_file = allocate(efi_bytes)
    kernel_file = allocate(kernel_bytes)
    initramfs_file = allocate(initramfs_bytes)
    # H3: the recovery volume carries a marker file the loader looks for on
    # its own volume before reinstalling the boot chain to the system ESP.
    recovery_id_bytes = b"aiueos-recovery-volume-v1\n"
    recovery_id_file = allocate(recovery_id_bytes) if recovery_marker else 0

    def write_directory(cluster, payload):
        offset = (FAT16_DATA_START + (cluster - 2) * FAT16_CLUSTER_SECTORS) * SECTOR
        image[offset:offset + len(payload)] = payload

    write_directory(efi_dir, dirent(".", 0x10, efi_dir) + dirent("..", 0x10, 0) +
                    dirent("BOOT", 0x10, boot_dir) + dirent("AIUEOS", 0x10, aiueos_dir))
    write_directory(boot_dir, dirent(".", 0x10, boot_dir) + dirent("..", 0x10, efi_dir) +
                    dirent("BOOTX64.EFI", 0x20, efi_file, len(efi_bytes)))
    write_directory(aiueos_dir, dirent(".", 0x10, aiueos_dir) + dirent("..", 0x10, efi_dir) +
                    dirent("KERNEL.ELF", 0x20, kernel_file, len(kernel_bytes)) +
                    dirent("INITRD.IMG", 0x20, initramfs_file, len(initramfs_bytes)))
    root = dirent("EFI", 0x10, efi_dir)
    if recovery_marker:
        root += dirent("RECOVERY.ID", 0x20, recovery_id_file, len(recovery_id_bytes))
    if extra_files:
        for extra_name, extra_bytes in extra_files.items():
            extra_cluster = allocate(extra_bytes)
            root += dirent(extra_name, 0x20, extra_cluster, len(extra_bytes))
    root_offset = (FAT16_RESERVED + FAT16_FATS * FAT16_FAT_SECTORS) * SECTOR
    image[root_offset:root_offset + len(root)] = root

    fat_bytes = bytearray(FAT16_FAT_SECTORS * SECTOR)
    for index, value in enumerate(fat):
        struct.pack_into("<H", fat_bytes, index * 2, value)
    for copy in range(FAT16_FATS):
        offset = (FAT16_RESERVED + copy * FAT16_FAT_SECTORS) * SECTOR
        image[offset:offset + len(fat_bytes)] = fat_bytes
    return bytes(image)


def both_endian_32(value):
    return struct.pack("<I", value) + struct.pack(">I", value)


def both_endian_16(value):
    return struct.pack("<H", value) + struct.pack(">H", value)


def iso_directory_record(name, extent, size, flags):
    identifier = name if isinstance(name, bytes) else name.encode("ascii")
    length = 33 + len(identifier)
    length += length % 2
    record = bytearray(length)
    record[0] = length
    record[2:10] = both_endian_32(extent)
    record[10:18] = both_endian_32(size)
    record[18:25] = bytes([80, 1, 1, 0, 0, 0, 0])  # fixed 1980-01-01 00:00 UTC
    record[25] = flags
    record[28:32] = both_endian_16(1)
    record[32] = len(identifier)
    record[33:33 + len(identifier)] = identifier
    return bytes(record)


def build_iso(output, efi, kernel, initramfs):
    boot_image = make_fat16(efi, kernel, initramfs)
    iso = bytearray(ISO_VOLUME_BLOCKS * ISO_BLOCK)

    root_record = iso_directory_record(b"\x00", ISO_ROOT_LBA, ISO_BLOCK, 0x02)
    pvd = bytearray(ISO_BLOCK)
    pvd[0] = 1
    pvd[1:6] = b"CD001"
    pvd[6] = 1
    pvd[8:40] = b"AIUEOS".ljust(32)
    pvd[40:72] = b"AIUEOS".ljust(32)
    pvd[80:88] = both_endian_32(ISO_VOLUME_BLOCKS)
    pvd[120:124] = both_endian_16(1)
    pvd[124:128] = both_endian_16(1)
    pvd[128:132] = both_endian_16(ISO_BLOCK)
    path_table = bytes([1, 0]) + struct.pack("<I", ISO_ROOT_LBA) + struct.pack("<H", 1) + b"\x00\x00"
    pvd[132:140] = both_endian_32(len(path_table))
    struct.pack_into("<I", pvd, 140, ISO_LPATH_LBA)
    struct.pack_into(">I", pvd, 148, ISO_MPATH_LBA)
    pvd[156:156 + len(root_record)] = root_record
    for offset, width in ((190, 128), (318, 128), (446, 128), (574, 128),
                          (702, 37), (739, 37), (776, 37)):
        pvd[offset:offset + width] = b" " * width
    # All-zero digit dates mean "not specified" and keep the image reproducible.
    for offset in (813, 830, 847, 864):
        pvd[offset:offset + 16] = b"0" * 16
    pvd[881] = 1
    iso[ISO_PVD_LBA * ISO_BLOCK:(ISO_PVD_LBA + 1) * ISO_BLOCK] = pvd

    brvd = bytearray(ISO_BLOCK)
    brvd[0] = 0
    brvd[1:6] = b"CD001"
    brvd[6] = 1
    brvd[7:39] = b"EL TORITO SPECIFICATION".ljust(32, b"\x00")
    struct.pack_into("<I", brvd, 71, ISO_CATALOG_LBA)
    iso[ISO_BRVD_LBA * ISO_BLOCK:(ISO_BRVD_LBA + 1) * ISO_BLOCK] = brvd

    terminator = bytearray(ISO_BLOCK)
    terminator[0] = 255
    terminator[1:6] = b"CD001"
    terminator[6] = 1
    iso[ISO_TERMINATOR_LBA * ISO_BLOCK:(ISO_TERMINATOR_LBA + 1) * ISO_BLOCK] = terminator

    validation = bytearray(32)
    validation[0] = 0x01
    validation[1] = 0xEF  # EFI platform
    validation[4:10] = b"AIUEOS"
    validation[30:32] = b"\x55\xaa"
    checksum = (-sum(struct.unpack_from("<16H", validation))) & 0xFFFF
    struct.pack_into("<H", validation, 28, checksum)
    default_entry = bytearray(32)
    default_entry[0] = 0x88  # bootable
    default_entry[1] = 0x00  # no emulation
    struct.pack_into("<H", default_entry, 6, ISO_BOOT_SECTORS)
    struct.pack_into("<I", default_entry, 8, ISO_BOOT_IMAGE_LBA)
    catalog_offset = ISO_CATALOG_LBA * ISO_BLOCK
    iso[catalog_offset:catalog_offset + 32] = validation
    iso[catalog_offset + 32:catalog_offset + 64] = default_entry

    root_dir = bytearray(ISO_BLOCK)
    entries = (iso_directory_record(b"\x00", ISO_ROOT_LBA, ISO_BLOCK, 0x02) +
               iso_directory_record(b"\x01", ISO_ROOT_LBA, ISO_BLOCK, 0x02) +
               iso_directory_record("ESP.IMG;1", ISO_BOOT_IMAGE_LBA, len(boot_image), 0x00))
    root_dir[:len(entries)] = entries
    iso[ISO_ROOT_LBA * ISO_BLOCK:(ISO_ROOT_LBA + 1) * ISO_BLOCK] = root_dir

    lpath = bytearray(ISO_BLOCK)
    lpath[:len(path_table)] = path_table
    iso[ISO_LPATH_LBA * ISO_BLOCK:(ISO_LPATH_LBA + 1) * ISO_BLOCK] = lpath
    mpath = bytearray(ISO_BLOCK)
    mpath[:len(path_table)] = (bytes([1, 0]) + struct.pack(">I", ISO_ROOT_LBA) +
                               struct.pack(">H", 1) + b"\x00\x00")
    iso[ISO_MPATH_LBA * ISO_BLOCK:(ISO_MPATH_LBA + 1) * ISO_BLOCK] = mpath

    boot_offset = ISO_BOOT_IMAGE_LBA * ISO_BLOCK
    iso[boot_offset:boot_offset + len(boot_image)] = boot_image
    Path(output).write_bytes(iso)


def verify_iso(path, expected_efi=None, expected_kernel=None, expected_initramfs=None):
    iso = Path(path).read_bytes()
    if len(iso) != ISO_VOLUME_BLOCKS * ISO_BLOCK:
        raise ValueError("invalid ISO size")
    pvd = iso[ISO_PVD_LBA * ISO_BLOCK:(ISO_PVD_LBA + 1) * ISO_BLOCK]
    if pvd[0] != 1 or pvd[1:6] != b"CD001":
        raise ValueError("missing ISO9660 primary volume descriptor")
    if struct.unpack_from("<I", pvd, 80)[0] != ISO_VOLUME_BLOCKS:
        raise ValueError("ISO volume space size mismatch")
    brvd = iso[ISO_BRVD_LBA * ISO_BLOCK:(ISO_BRVD_LBA + 1) * ISO_BLOCK]
    if brvd[0] != 0 or brvd[1:6] != b"CD001" or not brvd[7:30].startswith(b"EL TORITO SPECIFICATION"):
        raise ValueError("missing El Torito boot record volume descriptor")
    catalog_lba = struct.unpack_from("<I", brvd, 71)[0]
    catalog = iso[catalog_lba * ISO_BLOCK:(catalog_lba + 1) * ISO_BLOCK]
    if catalog[0] != 0x01 or catalog[1] != 0xEF or catalog[30:32] != b"\x55\xaa":
        raise ValueError("invalid El Torito validation entry")
    if sum(struct.unpack_from("<16H", catalog)) & 0xFFFF != 0:
        raise ValueError("invalid El Torito validation checksum")
    if catalog[32] != 0x88 or catalog[33] != 0x00:
        raise ValueError("invalid El Torito default boot entry")
    sectors = struct.unpack_from("<H", catalog, 38)[0]
    image_lba = struct.unpack_from("<I", catalog, 40)[0]
    if sectors != ISO_BOOT_SECTORS or image_lba != ISO_BOOT_IMAGE_LBA:
        raise ValueError("El Torito boot image extent mismatch")
    esp = iso[image_lba * ISO_BLOCK:image_lba * ISO_BLOCK + sectors * SECTOR]

    root_dir = iso[ISO_ROOT_LBA * ISO_BLOCK:(ISO_ROOT_LBA + 1) * ISO_BLOCK]
    offset = root_dir[0] + root_dir[root_dir[0]]
    record = root_dir[offset:offset + root_dir[offset]]
    if record[33:33 + record[32]] != b"ESP.IMG;1":
        raise ValueError("missing ESP.IMG directory record")
    if (struct.unpack_from("<I", record, 2)[0] != image_lba or
            struct.unpack_from("<I", record, 10)[0] != sectors * SECTOR):
        raise ValueError("ESP.IMG directory record extent mismatch")
    verify_fat16_volume(esp, "ISO", expected_efi, expected_kernel, expected_initramfs)


def fat16_locate(esp, name_path):
    """Walk a FAT16 boot volume and return each path component's
    (first_cluster, size). The final component must be a file."""
    if esp[54:62] != b"FAT16   " or esp[510:512] != b"\x55\xaa":
        raise ValueError("invalid FAT16 boot volume")
    fat = esp[FAT16_RESERVED * SECTOR:(FAT16_RESERVED + FAT16_FAT_SECTORS) * SECTOR]

    def cluster_bytes(cluster):
        start = (FAT16_DATA_START + (cluster - 2) * FAT16_CLUSTER_SECTORS) * SECTOR
        return esp[start:start + FAT16_CLUSTER_SECTORS * SECTOR]

    def find(entries, name):
        wanted = fat_name(name)
        for entry_offset in range(0, len(entries), 32):
            entry = entries[entry_offset:entry_offset + 32]
            if entry[0] == 0:
                break
            if entry[:11] == wanted:
                return struct.unpack_from("<H", entry, 26)[0], struct.unpack_from("<I", entry, 28)[0]
        raise ValueError("missing boot-volume path component: " + name)

    root_offset = (FAT16_RESERVED + FAT16_FATS * FAT16_FAT_SECTORS) * SECTOR
    entries = esp[root_offset:root_offset + FAT16_ROOT_SECTORS * SECTOR]
    cluster, size = 0, 0
    for component in name_path:
        cluster, size = find(entries, component)
        entries = cluster_bytes(cluster)
    return cluster, size, fat, cluster_bytes


def verify_fat16_volume(esp, label, expected_efi=None, expected_kernel=None,
                        expected_initramfs=None):
    embedded = {}
    for name, path in (("BOOTX64.EFI", ("EFI", "BOOT", "BOOTX64.EFI")),
                       ("KERNEL.ELF", ("EFI", "AIUEOS", "KERNEL.ELF")),
                       ("INITRD.IMG", ("EFI", "AIUEOS", "INITRD.IMG"))):
        cluster, size, fat, cluster_bytes = fat16_locate(esp, path)
        output = bytearray()
        while cluster < 0xFFF8 and len(output) < size:
            output += cluster_bytes(cluster)
            cluster = struct.unpack_from("<H", fat, cluster * 2)[0]
        embedded[name] = bytes(output[:size])
    if embedded["BOOTX64.EFI"][:2] != b"MZ" or embedded["KERNEL.ELF"][:4] != b"\x7fELF":
        raise ValueError(label + " boot artifacts have invalid magic")
    if embedded["INITRD.IMG"][:6] != b"070701":
        raise ValueError(label + " initramfs is not a newc archive")
    if expected_efi and embedded["BOOTX64.EFI"] != Path(expected_efi).read_bytes():
        raise ValueError(label + " BOOTX64.EFI content mismatch")
    if expected_kernel and embedded["KERNEL.ELF"] != Path(expected_kernel).read_bytes():
        raise ValueError(label + " KERNEL.ELF content mismatch")
    if expected_initramfs and embedded["INITRD.IMG"] != Path(expected_initramfs).read_bytes():
        raise ValueError(label + " INITRD.IMG content mismatch")


def gpt_header(current, backup, entries_lba, entries_crc):
    header = bytearray(SECTOR)
    struct.pack_into("<8sIIIIQQQQ16sQIII", header, 0, b"EFI PART", 0x00010000, 92, 0, 0,
                     current, backup, 34, GPT_BACKUP_ENTRIES - 1, DISK_GUID.bytes_le,
                     entries_lba, GPT_ENTRY_COUNT, GPT_ENTRY_SIZE, entries_crc)
    struct.pack_into("<I", header, 16, binascii.crc32(header[:92]) & 0xFFFFFFFF)
    return header


def build_image(output, efi, kernel, initramfs):
    esp = make_fat32(efi, kernel, initramfs)
    recovery = make_fat16(efi, kernel, initramfs, recovery_marker=True)
    disk = bytearray(DISK_SECTORS * SECTOR)
    mbr = bytearray(SECTOR)
    mbr[:len(BIOS_STUB)] = BIOS_STUB
    mbr[446 + 4] = 0xEE
    struct.pack_into("<II", mbr, 446 + 8, 1, DISK_SECTORS - 1)
    mbr[510:512] = b"\x55\xaa"
    disk[:SECTOR] = mbr

    entries = bytearray(GPT_ENTRY_SECTORS * SECTOR)
    name = "aiueos ESP".encode("utf-16le")
    entries[:16] = ESP_TYPE.bytes_le
    entries[16:32] = ESP_GUID.bytes_le
    struct.pack_into("<QQQ", entries, 32, ESP_FIRST, ESP_LAST, 0)
    entries[56:56 + len(name)] = name
    recovery_name = "aiueos recovery".encode("utf-16le")
    entries[128:144] = ESP_TYPE.bytes_le
    entries[144:160] = RECOVERY_GUID.bytes_le
    struct.pack_into("<QQQ", entries, 160, RECOVERY_FIRST, RECOVERY_LAST, 0)
    entries[184:184 + len(recovery_name)] = recovery_name
    entries_crc = binascii.crc32(entries) & 0xFFFFFFFF
    disk[2 * SECTOR:(2 + GPT_ENTRY_SECTORS) * SECTOR] = entries
    backup_offset = GPT_BACKUP_ENTRIES * SECTOR
    disk[backup_offset:backup_offset + len(entries)] = entries
    disk[SECTOR:2 * SECTOR] = gpt_header(1, DISK_SECTORS - 1, 2, entries_crc)
    disk[-SECTOR:] = gpt_header(DISK_SECTORS - 1, 1, GPT_BACKUP_ENTRIES, entries_crc)
    disk[ESP_FIRST * SECTOR:(ESP_LAST + 1) * SECTOR] = esp
    disk[RECOVERY_FIRST * SECTOR:(RECOVERY_LAST + 1) * SECTOR] = recovery
    Path(output).write_bytes(disk)


UNSET = object()


def verify_image(path, expected_efi=None, expected_kernel=None,
                 expected_initramfs=None,
                 recovery_efi=UNSET, recovery_kernel=UNSET,
                 recovery_initramfs=UNSET):
    """Verify the release image. The recovery partition is compared against
    the primary expectations unless distinct recovery artifacts are given
    (an applied update leaves the previous version there); passing None
    checks the recovery volume structurally only."""
    if recovery_efi is UNSET:
        recovery_efi = expected_efi
    if recovery_kernel is UNSET:
        recovery_kernel = expected_kernel
    if recovery_initramfs is UNSET:
        recovery_initramfs = expected_initramfs
    disk = Path(path).read_bytes()
    if len(disk) != DISK_SECTORS * SECTOR or disk[510:512] != b"\x55\xaa":
        raise ValueError("invalid disk size or protective MBR")
    if disk[:len(BIOS_STUB)] != BIOS_STUB:
        raise ValueError("missing legacy-BIOS stage-1 refusal stub")
    header = disk[SECTOR:2 * SECTOR]
    if header[:8] != b"EFI PART":
        raise ValueError("missing GPT header")
    stored_crc = struct.unpack_from("<I", header, 16)[0]
    checked = bytearray(header[:92]); struct.pack_into("<I", checked, 16, 0)
    if binascii.crc32(checked) & 0xFFFFFFFF != stored_crc:
        raise ValueError("invalid primary GPT header CRC")
    entries_crc = struct.unpack_from("<I", header, 88)[0]
    entries = disk[2 * SECTOR:(2 + GPT_ENTRY_SECTORS) * SECTOR]
    if binascii.crc32(entries) & 0xFFFFFFFF != entries_crc:
        raise ValueError("invalid GPT entry-array CRC")
    backup_header = disk[-SECTOR:]
    backup_checked = bytearray(backup_header[:92])
    backup_crc = struct.unpack_from("<I", backup_checked, 16)[0]
    struct.pack_into("<I", backup_checked, 16, 0)
    if (backup_header[:8] != b"EFI PART" or
            binascii.crc32(backup_checked) & 0xFFFFFFFF != backup_crc):
        raise ValueError("invalid backup GPT header CRC")
    backup_entries = disk[GPT_BACKUP_ENTRIES * SECTOR:(GPT_BACKUP_ENTRIES + GPT_ENTRY_SECTORS) * SECTOR]
    if backup_entries != entries:
        raise ValueError("primary and backup GPT entry arrays differ")
    if entries[:16] != ESP_TYPE.bytes_le or struct.unpack_from("<QQ", entries, 32) != (ESP_FIRST, ESP_LAST):
        raise ValueError("invalid ESP GPT entry")
    if (entries[128:144] != ESP_TYPE.bytes_le or
            entries[144:160] != RECOVERY_GUID.bytes_le or
            struct.unpack_from("<QQ", entries, 160) != (RECOVERY_FIRST, RECOVERY_LAST)):
        raise ValueError("invalid recovery GPT entry")
    recovery = disk[RECOVERY_FIRST * SECTOR:(RECOVERY_LAST + 1) * SECTOR]
    verify_fat16_volume(recovery, "recovery", recovery_efi, recovery_kernel,
                        recovery_initramfs)

    embedded_efi, embedded_kernel = read_primary_artifacts(disk)
    if embedded_efi[:2] != b"MZ" or embedded_kernel[:4] != b"\x7fELF":
        raise ValueError("ESP boot artifacts have invalid magic")
    if expected_efi and embedded_efi != Path(expected_efi).read_bytes():
        raise ValueError("BOOTX64.EFI content mismatch")
    if expected_kernel and embedded_kernel != Path(expected_kernel).read_bytes():
        raise ValueError("KERNEL.ELF content mismatch")


def read_primary_artifacts(disk):
    """Walk the primary FAT32 ESP and return the embedded
    (BOOTX64.EFI, KERNEL.ELF) bytes."""
    esp = disk[ESP_FIRST * SECTOR:(ESP_LAST + 1) * SECTOR]
    if esp[82:90] != b"FAT32   " or esp[510:512] != b"\x55\xaa":
        raise ValueError("invalid FAT32 ESP")
    reserved = struct.unpack_from("<H", esp, 14)[0]
    fats = esp[16]
    fat_sectors = struct.unpack_from("<I", esp, 36)[0]
    data_start = reserved + fats * fat_sectors
    fat = esp[reserved * SECTOR:(reserved + fat_sectors) * SECTOR]

    def cluster_bytes(cluster):
        return esp[(data_start + cluster - 2) * SECTOR:(data_start + cluster - 1) * SECTOR]

    def find(directory, name):
        wanted = fat_name(name)
        for offset in range(0, SECTOR, 32):
            entry = cluster_bytes(directory)[offset:offset + 32]
            if entry[0] == 0:
                break
            if entry[:11] == wanted:
                cluster = struct.unpack_from("<H", entry, 20)[0] << 16 | struct.unpack_from("<H", entry, 26)[0]
                return cluster, struct.unpack_from("<I", entry, 28)[0]
        raise ValueError("missing ESP path component: " + name)

    def read_file(first, size):
        output = bytearray(); cluster = first
        while cluster < 0x0FFFFFF8 and len(output) < size:
            output += cluster_bytes(cluster)
            cluster = struct.unpack_from("<I", fat, cluster * 4)[0] & 0x0FFFFFFF
        return bytes(output[:size])

    efi_dir, _ = find(2, "EFI")
    boot_dir, _ = find(efi_dir, "BOOT")
    aiueos_dir, _ = find(efi_dir, "AIUEOS")
    efi_cluster, efi_size = find(boot_dir, "BOOTX64.EFI")
    kernel_cluster, kernel_size = find(aiueos_dir, "KERNEL.ELF")
    return read_file(efi_cluster, efi_size), read_file(kernel_cluster, kernel_size)


def apply_update(image, efi, kernel, initramfs, output, receipt_path):
    """Write a new loader/kernel pair into the primary ESP only. The recovery
    partition keeps the previous known-good pair, so a failed update rolls
    back through the existing firmware/loader fallback paths."""
    verify_image(image)
    disk = bytearray(Path(image).read_bytes())
    recovery_before = bytes(disk[RECOVERY_FIRST * SECTOR:(RECOVERY_LAST + 1) * SECTOR])
    previous_efi, previous_kernel = read_primary_artifacts(bytes(disk))
    disk[ESP_FIRST * SECTOR:(ESP_LAST + 1) * SECTOR] = make_fat32(efi, kernel, initramfs)
    Path(output).write_bytes(disk)
    verify_image(output, efi, kernel, initramfs,
                 recovery_efi=None, recovery_kernel=None, recovery_initramfs=None)
    updated = Path(output).read_bytes()
    if updated[RECOVERY_FIRST * SECTOR:(RECOVERY_LAST + 1) * SECTOR] != recovery_before:
        raise ValueError("update touched the recovery partition")
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    receipt = {
        "schema": "aiueos.update-receipt.v1",
        "created": datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z"),
        "disk": {"bytes": len(updated), "sha256": hashlib.sha256(updated).hexdigest()},
        "previous": {
            "EFI/BOOT/BOOTX64.EFI": {"bytes": len(previous_efi),
                                     "sha256": hashlib.sha256(previous_efi).hexdigest()},
            "EFI/AIUEOS/KERNEL.ELF": {"bytes": len(previous_kernel),
                                      "sha256": hashlib.sha256(previous_kernel).hexdigest()},
        },
        "updated": {
            "EFI/BOOT/BOOTX64.EFI": {"bytes": Path(efi).stat().st_size, "sha256": sha256(efi)},
            "EFI/AIUEOS/KERNEL.ELF": {"bytes": Path(kernel).stat().st_size, "sha256": sha256(kernel)},
        },
        "recovery": {"unchanged": True,
                     "sha256": hashlib.sha256(recovery_before).hexdigest()},
    }
    Path(receipt_path).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                                  encoding="utf-8")
    print(output)


def corrupt_image(image, output, target):
    """Copy the release image with one deterministic byte flipped inside the
    selected boot artifact, for fail-closed and recovery-fallback gates."""
    disk = bytearray(Path(image).read_bytes())
    volume, component = target.split("-", 1)
    path = {"loader": ("EFI", "BOOT", "BOOTX64.EFI"),
            "kernel": ("EFI", "AIUEOS", "KERNEL.ELF")}[component]
    if volume == "recovery":
        recovery = disk[RECOVERY_FIRST * SECTOR:(RECOVERY_LAST + 1) * SECTOR]
        cluster, _, _, _ = fat16_locate(recovery, path)
        offset = (RECOVERY_FIRST + FAT16_DATA_START +
                  (cluster - 2) * FAT16_CLUSTER_SECTORS) * SECTOR
    else:
        esp_offset = ESP_FIRST * SECTOR
        reserved = struct.unpack_from("<H", disk, esp_offset + 14)[0]
        fats = disk[esp_offset + 16]
        fat_sectors = struct.unpack_from("<I", disk, esp_offset + 36)[0]
        data_start = reserved + fats * fat_sectors

        def cluster_offset(cluster):
            return esp_offset + (data_start + cluster - 2) * SECTOR

        def find(directory, name):
            wanted = fat_name(name)
            base = cluster_offset(directory)
            for entry_offset in range(0, SECTOR, 32):
                entry = disk[base + entry_offset:base + entry_offset + 32]
                if entry[0] == 0:
                    break
                if entry[:11] == wanted:
                    return (struct.unpack_from("<H", entry, 20)[0] << 16 |
                            struct.unpack_from("<H", entry, 26)[0])
            raise ValueError("missing primary ESP path component: " + name)

        cluster = 2
        for name in path:
            cluster = find(cluster, name)
        offset = cluster_offset(cluster)
    disk[offset] ^= 1
    Path(output).write_bytes(disk)
    print("%s corrupted at byte %d" % (target, offset))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--efi", required=True); build.add_argument("--kernel", required=True)
    build.add_argument("--initramfs", required=True)
    build.add_argument("--data")
    build.add_argument("--iso")
    build.add_argument("--output", required=True); build.add_argument("--receipt", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--image"); verify.add_argument("--iso")
    verify.add_argument("--efi"); verify.add_argument("--kernel")
    verify.add_argument("--initramfs")
    verify.add_argument("--recovery-efi"); verify.add_argument("--recovery-kernel")
    verify.add_argument("--recovery-initramfs")
    update = sub.add_parser("apply-update")
    update.add_argument("--image", required=True)
    update.add_argument("--efi", required=True); update.add_argument("--kernel", required=True)
    update.add_argument("--initramfs", required=True)
    update.add_argument("--output", required=True); update.add_argument("--receipt", required=True)
    corrupt = sub.add_parser("corrupt")
    corrupt.add_argument("--image", required=True)
    corrupt.add_argument("--output", required=True)
    corrupt.add_argument("--target", required=True,
                         choices=["primary-loader", "primary-kernel",
                                  "recovery-loader", "recovery-kernel"])
    args = parser.parse_args()
    if args.command == "corrupt":
        corrupt_image(args.image, args.output, args.target)
        return
    if args.command == "apply-update":
        apply_update(args.image, args.efi, args.kernel, args.initramfs, args.output, args.receipt)
        return
    if args.command == "verify":
        if not args.image and not args.iso:
            parser.error("verify requires --image or --iso")
        if args.image:
            recovery_expectations = {}
            if args.recovery_efi or args.recovery_kernel or args.recovery_initramfs:
                recovery_expectations = {"recovery_efi": args.recovery_efi,
                                         "recovery_kernel": args.recovery_kernel,
                                         "recovery_initramfs": args.recovery_initramfs}
            verify_image(args.image, args.efi, args.kernel, args.initramfs, **recovery_expectations)
            print("AIUEOS_RELEASE_IMAGE_OK")
        if args.iso:
            verify_iso(args.iso, args.efi, args.kernel, args.initramfs)
            print("AIUEOS_RELEASE_ISO_OK")
        return
    build_image(args.output, args.efi, args.kernel, args.initramfs)
    verify_image(args.output, args.efi, args.kernel, args.initramfs)
    if args.iso:
        build_iso(args.iso, args.efi, args.kernel, args.initramfs)
        verify_iso(args.iso, args.efi, args.kernel, args.initramfs)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    receipt = {
        "schema": "aiueos.build-receipt.v1",
        "created": datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z"),
        "disk": {"bytes": Path(args.output).stat().st_size, "sha256": sha256(args.output)},
        "esp": {"first_lba": ESP_FIRST, "last_lba": ESP_LAST, "type": str(ESP_TYPE)},
        "recovery": {"first_lba": RECOVERY_FIRST, "last_lba": RECOVERY_LAST,
                     "type": str(ESP_TYPE), "guid": str(RECOVERY_GUID),
                     "sha256": hashlib.sha256(
                         Path(args.output).read_bytes()[
                             RECOVERY_FIRST * SECTOR:(RECOVERY_LAST + 1) * SECTOR]).hexdigest()},
        "artifacts": {
            "EFI/BOOT/BOOTX64.EFI": {"bytes": Path(args.efi).stat().st_size, "sha256": sha256(args.efi)},
            "EFI/AIUEOS/KERNEL.ELF": {"bytes": Path(args.kernel).stat().st_size, "sha256": sha256(args.kernel)},
            "EFI/AIUEOS/INITRD.IMG": {"bytes": Path(args.initramfs).stat().st_size,
                                      "sha256": sha256(args.initramfs)},
        },
    }
    if args.data:
        receipt["artifacts"]["AIUEOS-DATA.IMG"] = {
            "bytes": Path(args.data).stat().st_size, "sha256": sha256(args.data)}
    if args.iso:
        receipt["iso"] = {
            "bytes": Path(args.iso).stat().st_size,
            "sha256": sha256(args.iso),
            "el_torito": {"platform": "efi", "media": "no-emulation",
                          "image_lba": ISO_BOOT_IMAGE_LBA,
                          "virtual_sectors": ISO_BOOT_SECTORS},
        }
    Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
