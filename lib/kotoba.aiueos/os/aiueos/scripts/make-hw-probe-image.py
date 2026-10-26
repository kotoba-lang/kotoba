#!/usr/bin/env python3
"""Build a deterministic GPT/FAT32 removable image containing only BOOTX64.EFI."""

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
DISK_SECTORS = 131072
ESP_FIRST = 2048
ENTRY_COUNT = 128
ENTRY_SIZE = 128
ENTRY_SECTORS = ENTRY_COUNT * ENTRY_SIZE // SECTOR
BACKUP_ENTRIES = DISK_SECTORS - 1 - ENTRY_SECTORS
ESP_LAST = BACKUP_ENTRIES - 1
ESP_SECTORS = ESP_LAST - ESP_FIRST + 1
ESP_TYPE = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
DISK_GUID = uuid.UUID("f7b8ce2c-c21f-54f0-8dca-36090ca43dc1")
ESP_GUID = uuid.UUID("22c92292-905d-57d3-8840-7a97510bd5df")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def fat_name(name):
    stem, dot, suffix = name.partition(".")
    return (stem.upper().ljust(8) + (suffix.upper() if dot else "").ljust(3)).encode("ascii")


def dirent(name, attr, cluster, size=0):
    entry = bytearray(32)
    entry[:11] = fat_name(name) if name not in (".", "..") else name.encode().ljust(11, b" ")
    entry[11] = attr
    for offset in (16, 18, 24):
        struct.pack_into("<H", entry, offset, 0x0021)
    struct.pack_into("<H", entry, 20, cluster >> 16)
    struct.pack_into("<H", entry, 26, cluster & 0xFFFF)
    struct.pack_into("<I", entry, 28, size)
    return bytes(entry)


def make_fat32(efi_bytes):
    reserved, fats = 32, 2
    denominator = SECTOR + fats * 4
    fat_sectors = ((ESP_SECTORS - reserved + 2) * 4 + denominator - 1) // denominator
    data_start = reserved + fats * fat_sectors
    clusters = ESP_SECTORS - data_start
    if clusters < 65525:
        raise ValueError("ESP is too small for FAT32")
    image = bytearray(ESP_SECTORS * SECTOR)
    boot = bytearray(SECTOR)
    boot[:3], boot[3:11] = b"\xeb\x58\x90", b"AIUEHWP "
    struct.pack_into("<HBHBHHBHHHII", boot, 11, SECTOR, 1, reserved, fats, 0, 0,
                     0xF8, 0, 63, 255, ESP_FIRST, ESP_SECTORS)
    struct.pack_into("<IHHIHH", boot, 36, fat_sectors, 0, 0, 2, 1, 6)
    boot[64], boot[66] = 0x80, 0x29
    struct.pack_into("<I", boot, 67, 0x48575052)
    boot[71:82], boot[82:90], boot[510:512] = b"AIUE HWPROB", b"FAT32   ", b"\x55\xaa"
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
    root, efi_dir, boot_dir = 2, 3, 4
    for cluster in (root, efi_dir, boot_dir):
        fat[cluster] = 0x0FFFFFFF
    count = max(1, (len(efi_bytes) + SECTOR - 1) // SECTOR)
    first_file = 5
    if first_file + count > len(fat):
        raise ValueError("BOOTX64.EFI does not fit in ESP")
    for index in range(count):
        cluster = first_file + index
        fat[cluster] = 0x0FFFFFFF if index == count - 1 else cluster + 1
        chunk = efi_bytes[index * SECTOR:(index + 1) * SECTOR]
        offset = (data_start + cluster - 2) * SECTOR
        image[offset:offset + len(chunk)] = chunk

    directories = {
        root: dirent("EFI", 0x10, efi_dir),
        efi_dir: dirent(".", 0x10, efi_dir) + dirent("..", 0x10, root) + dirent("BOOT", 0x10, boot_dir),
        boot_dir: dirent(".", 0x10, boot_dir) + dirent("..", 0x10, efi_dir) +
                  dirent("BOOTX64.EFI", 0x20, first_file, len(efi_bytes)),
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
    header[:8] = b"EFI PART"
    struct.pack_into("<IIIIQQQQ", header, 8, 0x00010000, 92, 0, 0, current, backup,
                     ESP_FIRST, ESP_LAST)
    header[56:72] = DISK_GUID.bytes_le
    struct.pack_into("<QIII", header, 72, entries_lba, ENTRY_COUNT, ENTRY_SIZE, entries_crc)
    struct.pack_into("<I", header, 16, binascii.crc32(header[:92]) & 0xFFFFFFFF)
    return bytes(header)


def build(efi_path, output, receipt_path):
    efi = Path(efi_path).read_bytes()
    if efi[:2] != b"MZ":
        raise ValueError("probe is not PE/COFF")
    disk = bytearray(DISK_SECTORS * SECTOR)
    disk[446:462] = bytes([0, 0, 2, 0, 0xEE, 0xFF, 0xFF, 0xFF]) + struct.pack("<II", 1, DISK_SECTORS - 1)
    disk[510:512] = b"\x55\xaa"
    entries = bytearray(ENTRY_SECTORS * SECTOR)
    entries[:16], entries[16:32] = ESP_TYPE.bytes_le, ESP_GUID.bytes_le
    struct.pack_into("<QQQ", entries, 32, ESP_FIRST, ESP_LAST, 0)
    name = "AIUEOS HW PROBE".encode("utf-16le")
    entries[56:56 + len(name)] = name
    entries_crc = binascii.crc32(entries) & 0xFFFFFFFF
    disk[SECTOR:2 * SECTOR] = gpt_header(1, DISK_SECTORS - 1, 2, entries_crc)
    disk[2 * SECTOR:(2 + ENTRY_SECTORS) * SECTOR] = entries
    disk[BACKUP_ENTRIES * SECTOR:(BACKUP_ENTRIES + ENTRY_SECTORS) * SECTOR] = entries
    disk[-SECTOR:] = gpt_header(DISK_SECTORS - 1, 1, BACKUP_ENTRIES, entries_crc)
    disk[ESP_FIRST * SECTOR:(ESP_LAST + 1) * SECTOR] = make_fat32(efi)
    verify(bytes(disk), efi)
    Path(output).write_bytes(disk)
    epoch = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    receipt = {
        "schema": "aiueos.hw-probe-build-receipt.v1",
        "created": datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z"),
        "disk": {"bytes": len(disk), "sha256": sha256_bytes(disk)},
        "artifacts": {"EFI/BOOT/BOOTX64.EFI": {"bytes": len(efi), "sha256": sha256_bytes(efi)}},
        "safety": {"disk_writes": False, "exit_boot_services": False, "pci_handle_limit": 64},
    }
    Path(receipt_path).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify(disk, expected_efi=None):
    if len(disk) != DISK_SECTORS * SECTOR or disk[510:512] != b"\x55\xaa":
        raise ValueError("invalid disk image")
    header = bytearray(disk[SECTOR:SECTOR + 92])
    stored = struct.unpack_from("<I", header, 16)[0]
    struct.pack_into("<I", header, 16, 0)
    if disk[SECTOR:SECTOR + 8] != b"EFI PART" or binascii.crc32(header) & 0xFFFFFFFF != stored:
        raise ValueError("invalid primary GPT")
    entries = disk[2 * SECTOR:(2 + ENTRY_SECTORS) * SECTOR]
    if binascii.crc32(entries) & 0xFFFFFFFF != struct.unpack_from("<I", disk, SECTOR + 88)[0]:
        raise ValueError("invalid GPT entry array")
    if entries[:16] != ESP_TYPE.bytes_le or struct.unpack_from("<QQ", entries, 32) != (ESP_FIRST, ESP_LAST):
        raise ValueError("invalid ESP entry")
    backup = bytearray(disk[-SECTOR:-SECTOR + 92])
    backup_stored = struct.unpack_from("<I", backup, 16)[0]
    struct.pack_into("<I", backup, 16, 0)
    if (disk[-SECTOR:-SECTOR + 8] != b"EFI PART" or
            binascii.crc32(backup) & 0xFFFFFFFF != backup_stored or
            disk[BACKUP_ENTRIES * SECTOR:(BACKUP_ENTRIES + ENTRY_SECTORS) * SECTOR] != entries):
        raise ValueError("invalid backup GPT")
    esp = disk[ESP_FIRST * SECTOR:(ESP_LAST + 1) * SECTOR]
    if esp[82:90] != b"FAT32   ":
        raise ValueError("missing FAT32 ESP")
    reserved, fats = struct.unpack_from("<H", esp, 14)[0], esp[16]
    fat_sectors = struct.unpack_from("<I", esp, 36)[0]
    data_start = reserved + fats * fat_sectors
    fat = esp[reserved * SECTOR:(reserved + fat_sectors) * SECTOR]

    def cluster_bytes(cluster):
        return esp[(data_start + cluster - 2) * SECTOR:(data_start + cluster - 1) * SECTOR]

    def find(cluster, name):
        wanted = fat_name(name)
        for offset in range(0, SECTOR, 32):
            entry = cluster_bytes(cluster)[offset:offset + 32]
            if entry[0] == 0:
                break
            if entry[:11] == wanted:
                first = struct.unpack_from("<H", entry, 20)[0] << 16 | struct.unpack_from("<H", entry, 26)[0]
                return first, struct.unpack_from("<I", entry, 28)[0]
        raise ValueError("missing " + name)

    efi_dir, _ = find(2, "EFI")
    boot_dir, _ = find(efi_dir, "BOOT")
    cluster, size = find(boot_dir, "BOOTX64.EFI")
    payload = bytearray()
    visited = set()
    while 2 <= cluster < 0x0FFFFFF8 and len(payload) < size:
        if cluster in visited or cluster * 4 + 4 > len(fat):
            raise ValueError("invalid BOOTX64.EFI cluster chain")
        visited.add(cluster)
        payload += cluster_bytes(cluster)
        cluster = struct.unpack_from("<I", fat, cluster * 4)[0] & 0x0FFFFFFF
    payload = bytes(payload[:size])
    if payload[:2] != b"MZ" or (expected_efi is not None and payload != expected_efi):
        raise ValueError("BOOTX64.EFI mismatch")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--efi", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    build(args.efi, args.output, args.receipt)
    print("AIUEOS_HW_PROBE_IMAGE_OK " + args.output)


if __name__ == "__main__":
    main()
