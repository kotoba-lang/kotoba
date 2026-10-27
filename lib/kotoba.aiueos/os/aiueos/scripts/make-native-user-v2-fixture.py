#!/usr/bin/env python3
"""Stage the pinned user-v2 ELF in a diagnostic boot slot, not a release app."""

import argparse
import hashlib
import os
from pathlib import Path
import struct


ELF_SHA256 = "d1cd47b63ec90df52f6763f63c9410d2a032266412be3dd49238db8ecdf61248"
SLOT_BYTES = 524288
MAGIC = 0x0031444c50554941


def make(elf, output):
    if elf.is_symlink() or not elf.is_file() or output.exists():
        raise ValueError("ELF must be a regular file and output must be new")
    raw = elf.read_bytes()
    if len(raw) != 8280 or hashlib.sha256(raw).hexdigest() != ELF_SHA256:
        raise ValueError("user-v2 ELF pin mismatch")
    if struct.unpack_from("<Q", raw, 24)[0] != 0x220000:
        raise ValueError("user-v2 entry address mismatch")
    slot = bytearray(SLOT_BYTES)
    struct.pack_into("<QQQ", slot, 0, MAGIC, 2, len(raw))
    slot[64:64 + len(raw)] = raw
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(slot)
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    print(hashlib.sha256(slot).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    make(args.elf, args.output)
