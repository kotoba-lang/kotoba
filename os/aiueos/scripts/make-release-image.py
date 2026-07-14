#!/usr/bin/env python3
"""Build and verify the deterministic aiueos GPT/ESP release image."""

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
ESP_LAST = GPT_BACKUP_ENTRIES - 1
ESP_SECTORS = ESP_LAST - ESP_FIRST + 1
ESP_TYPE = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
NAMESPACE = uuid.UUID("18b3fb94-8713-54c4-9e3a-f0c78a88d192")
DISK_GUID = uuid.uuid5(NAMESPACE, "aiueos-release-disk-v1")
ESP_GUID = uuid.uuid5(NAMESPACE, "aiueos-esp-v1")
VOLUME_ID = 0x41495545


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


def make_fat32(efi, kernel):
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
    efi_file_cluster = allocate(efi_bytes)
    kernel_file_cluster = allocate(kernel_bytes)

    directories = {
        root_cluster: dirent("EFI", 0x10, efi_cluster),
        efi_cluster: dirent(".", 0x10, efi_cluster) + dirent("..", 0x10, root_cluster) +
                     dirent("BOOT", 0x10, boot_cluster) + dirent("AIUEOS", 0x10, aiueos_cluster),
        boot_cluster: dirent(".", 0x10, boot_cluster) + dirent("..", 0x10, efi_cluster) +
                      dirent("BOOTX64.EFI", 0x20, efi_file_cluster, len(efi_bytes)),
        aiueos_cluster: dirent(".", 0x10, aiueos_cluster) + dirent("..", 0x10, efi_cluster) +
                        dirent("KERNEL.ELF", 0x20, kernel_file_cluster, len(kernel_bytes)),
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


def gpt_header(current, backup, entries_lba, entries_crc):
    header = bytearray(SECTOR)
    struct.pack_into("<8sIIIIQQQQ16sQIII", header, 0, b"EFI PART", 0x00010000, 92, 0, 0,
                     current, backup, 34, GPT_BACKUP_ENTRIES - 1, DISK_GUID.bytes_le,
                     entries_lba, GPT_ENTRY_COUNT, GPT_ENTRY_SIZE, entries_crc)
    struct.pack_into("<I", header, 16, binascii.crc32(header[:92]) & 0xFFFFFFFF)
    return header


def build_image(output, efi, kernel):
    esp = make_fat32(efi, kernel)
    disk = bytearray(DISK_SECTORS * SECTOR)
    mbr = bytearray(SECTOR)
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
    entries_crc = binascii.crc32(entries) & 0xFFFFFFFF
    disk[2 * SECTOR:(2 + GPT_ENTRY_SECTORS) * SECTOR] = entries
    backup_offset = GPT_BACKUP_ENTRIES * SECTOR
    disk[backup_offset:backup_offset + len(entries)] = entries
    disk[SECTOR:2 * SECTOR] = gpt_header(1, DISK_SECTORS - 1, 2, entries_crc)
    disk[-SECTOR:] = gpt_header(DISK_SECTORS - 1, 1, GPT_BACKUP_ENTRIES, entries_crc)
    disk[ESP_FIRST * SECTOR:(ESP_LAST + 1) * SECTOR] = esp
    Path(output).write_bytes(disk)


def verify_image(path, expected_efi=None, expected_kernel=None):
    disk = Path(path).read_bytes()
    if len(disk) != DISK_SECTORS * SECTOR or disk[510:512] != b"\x55\xaa":
        raise ValueError("invalid disk size or protective MBR")
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
    embedded_efi, embedded_kernel = read_file(efi_cluster, efi_size), read_file(kernel_cluster, kernel_size)
    if embedded_efi[:2] != b"MZ" or embedded_kernel[:4] != b"\x7fELF":
        raise ValueError("ESP boot artifacts have invalid magic")
    if expected_efi and embedded_efi != Path(expected_efi).read_bytes():
        raise ValueError("BOOTX64.EFI content mismatch")
    if expected_kernel and embedded_kernel != Path(expected_kernel).read_bytes():
        raise ValueError("KERNEL.ELF content mismatch")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--efi", required=True); build.add_argument("--kernel", required=True)
    build.add_argument("--output", required=True); build.add_argument("--receipt", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--image", required=True); verify.add_argument("--efi"); verify.add_argument("--kernel")
    args = parser.parse_args()
    if args.command == "verify":
        verify_image(args.image, args.efi, args.kernel)
        print("AIUEOS_RELEASE_IMAGE_OK")
        return
    build_image(args.output, args.efi, args.kernel)
    verify_image(args.output, args.efi, args.kernel)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    receipt = {
        "schema": "aiueos.build-receipt.v1",
        "created": datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z"),
        "disk": {"bytes": Path(args.output).stat().st_size, "sha256": sha256(args.output)},
        "esp": {"first_lba": ESP_FIRST, "last_lba": ESP_LAST, "type": str(ESP_TYPE)},
        "artifacts": {
            "EFI/BOOT/BOOTX64.EFI": {"bytes": Path(args.efi).stat().st_size, "sha256": sha256(args.efi)},
            "EFI/AIUEOS/KERNEL.ELF": {"bytes": Path(args.kernel).stat().st_size, "sha256": sha256(args.kernel)},
        },
    }
    Path(args.receipt).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
