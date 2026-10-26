#!/usr/bin/env python3
"""Create or inspect a GPT disk with one guarded AIUEOS model A/B partition."""

import argparse
import hashlib
import json
import struct
import uuid
import zlib
from pathlib import Path

BLOCK = 512
GPT_ENTRY_COUNT = 128
GPT_ENTRY_BYTES = 128
GPT_ENTRY_BLOCKS = GPT_ENTRY_COUNT * GPT_ENTRY_BYTES // BLOCK
PARTITION_START = 2048
ALIGN_BLOCKS = 2048
ANCHOR_MAGIC = b"AIUEOS-MODEL-AB1"
RECORD_MAGIC = b"AIUEOS-MODEL-R10"
MODEL_PARTITION_TYPE = uuid.UUID("4bca74df-78a1-4f0a-a06f-bc88fd3b35d9")


def align(value, unit):
    return (value + unit - 1) // unit * unit


def crc_record(block):
    mutable = bytearray(block)
    mutable[-4:] = b"\0\0\0\0"
    return zlib.crc32(mutable) & 0xFFFFFFFF


def anchor_block(partition_blocks, slot_blocks, data_a, data_b):
    block = bytearray(BLOCK)
    struct.pack_into("<16sIIQQQQ", block, 0, ANCHOR_MAGIC, 1, BLOCK,
                     partition_blocks, slot_blocks, data_a, data_b)
    struct.pack_into("<I", block, BLOCK - 4, crc_record(block))
    return block


def protective_mbr(total_blocks):
    mbr = bytearray(BLOCK)
    size = min(total_blocks - 1, 0xFFFFFFFF)
    struct.pack_into("<B3sB3sII", mbr, 446, 0, b"\0\x02\0", 0xEE,
                     b"\xff\xff\xff", 1, size)
    mbr[510:512] = b"\x55\xaa"
    return mbr


def gpt_header(current, backup, first_usable, last_usable, disk_guid,
               entries_lba, entries_crc):
    header = bytearray(BLOCK)
    struct.pack_into("<8sIIIIQQQQ16sQIII", header, 0, b"EFI PART",
                     0x00010000, 92, 0, 0, current, backup, first_usable,
                     last_usable, disk_guid.bytes_le, entries_lba,
                     GPT_ENTRY_COUNT, GPT_ENTRY_BYTES, entries_crc)
    struct.pack_into("<I", header, 16, zlib.crc32(header[:92]) & 0xFFFFFFFF)
    return header


def create(args):
    disk_bytes = args.disk_bytes
    if disk_bytes % BLOCK or disk_bytes < 128 * 1024 * 1024:
        raise SystemExit("disk size must be a 512-byte multiple and at least 128 MiB")
    total_blocks = disk_bytes // BLOCK
    last_block = total_blocks - 1
    first_usable, last_usable = 34, last_block - 33
    partition_blocks = last_usable - PARTITION_START + 1
    slot_blocks = align(args.slot_bytes, BLOCK) // BLOCK
    data_a = ALIGN_BLOCKS
    data_b = align(data_a + slot_blocks, ALIGN_BLOCKS)
    if data_b + slot_blocks > partition_blocks:
        raise SystemExit("disk is too small for two model slots")

    disk_guid = uuid.uuid5(uuid.NAMESPACE_URL,
                           f"aiueos-model-disk:{disk_bytes}:{args.slot_bytes}")
    part_guid = uuid.uuid5(disk_guid, "aiueos-model-partition")
    entries = bytearray(GPT_ENTRY_COUNT * GPT_ENTRY_BYTES)
    name = "AIUEOS MODEL".encode("utf-16le")
    struct.pack_into("<16s16sQQQ72s", entries, 0, MODEL_PARTITION_TYPE.bytes_le,
                     part_guid.bytes_le, PARTITION_START, last_usable, 0,
                     name.ljust(72, b"\0"))
    entries_crc = zlib.crc32(entries) & 0xFFFFFFFF
    primary = gpt_header(1, last_block, first_usable, last_usable, disk_guid,
                         2, entries_crc)
    backup_entries_lba = last_block - GPT_ENTRY_BLOCKS
    backup = gpt_header(last_block, 1, first_usable, last_usable, disk_guid,
                        backup_entries_lba, entries_crc)

    output = Path(args.output)
    with output.open("wb") as stream:
        stream.truncate(disk_bytes)
        stream.seek(0)
        stream.write(protective_mbr(total_blocks))
        stream.seek(BLOCK)
        stream.write(primary)
        stream.seek(2 * BLOCK)
        stream.write(entries)
        stream.seek(backup_entries_lba * BLOCK)
        stream.write(entries)
        stream.seek(last_block * BLOCK)
        stream.write(backup)
        stream.seek(PARTITION_START * BLOCK)
        stream.write(anchor_block(partition_blocks, slot_blocks, data_a, data_b))
    print(json.dumps({"format": "aiueos.model-slot-disk/v1",
                      "output": str(output), "bytes": disk_bytes,
                      "partition_start_lba": PARTITION_START,
                      "partition_blocks": partition_blocks,
                      "slot_blocks": slot_blocks,
                      "slot_capacity_bytes": slot_blocks * BLOCK,
                      "data_lba": [data_a, data_b]}, sort_keys=True))


def parse_record(block, kind):
    magic, version, actual_kind, generation, artifact_bytes, slot, state = \
        struct.unpack_from("<16sIIQQII", block, 0)
    digest = block[48:80]
    valid = (magic == RECORD_MAGIC and version == 1 and actual_kind == kind and
             slot < 2 and state == 1 and generation > 0 and artifact_bytes > 0 and
             struct.unpack_from("<I", block, BLOCK - 4)[0] == crc_record(block))
    return {"valid": valid, "generation": generation, "bytes": artifact_bytes,
            "slot": slot, "sha256": digest.hex()}


def inspect(args):
    image = Path(args.image)
    with image.open("rb") as stream:
        stream.seek(PARTITION_START * BLOCK)
        anchor = stream.read(BLOCK)
        magic, version, block_bytes, partition_blocks, slot_blocks, data_a, data_b = \
            struct.unpack_from("<16sIIQQQQ", anchor, 0)
        anchor_valid = (magic == ANCHOR_MAGIC and version == 1 and block_bytes == BLOCK and
                        struct.unpack_from("<I", anchor, BLOCK - 4)[0] == crc_record(anchor))
        records = []
        for lba, kind in ((1, 2), (2, 2), (3, 1), (4, 1)):
            stream.seek((PARTITION_START + lba) * BLOCK)
            records.append(parse_record(stream.read(BLOCK), kind))
        candidates = []
        for selector in records[:2]:
            if not selector["valid"]:
                continue
            header = records[2 + selector["slot"]]
            if (header["valid"] and all(selector[key] == header[key]
                                         for key in ("generation", "bytes", "slot", "sha256"))):
                candidates.append(selector)
        active = max(candidates, key=lambda item: item["generation"], default=None)
        if active:
            start = data_a if active["slot"] == 0 else data_b
            stream.seek((PARTITION_START + start) * BLOCK)
            digest = hashlib.sha256()
            remaining = active["bytes"]
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                digest.update(chunk)
                remaining -= len(chunk)
            active = dict(active, readback_sha256=digest.hexdigest(),
                          readback_valid=(remaining == 0 and digest.hexdigest() == active["sha256"]))
    result = {"format": "aiueos.model-slot-inspect/v1", "anchor_valid": anchor_valid,
              "partition_blocks": partition_blocks, "slot_blocks": slot_blocks,
              "data_lba": [data_a, data_b], "records": records, "active": active}
    print(json.dumps(result, sort_keys=True))
    if not anchor_valid or not active or not active["readback_valid"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("create")
    make.add_argument("--output", required=True)
    make.add_argument("--disk-bytes", type=int, required=True)
    make.add_argument("--slot-bytes", type=int, required=True)
    show = sub.add_parser("inspect")
    show.add_argument("--image", required=True)
    args = parser.parse_args()
    (create if args.command == "create" else inspect)(args)


if __name__ == "__main__":
    main()
