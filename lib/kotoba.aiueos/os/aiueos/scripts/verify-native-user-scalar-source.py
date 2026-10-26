#!/usr/bin/env python3
"""Check the diagnostic Kotoba byte staging against one pinned Amu user ELF.

This is a host-side source/artifact comparator, not guest ELF admission.
"""

import argparse
import hashlib
import re
import struct
from pathlib import Path


EXPECTED_ELF_SHA256 = "7f5a8c0a31b5bdf191410f007973413d16e497a20ae7fe86c734b9fea85808b1"
WORD_PATTERN = re.compile(r"\b([cr])(\d+) \(checked-word (code|request) (\d+) ([0-9-]+)\)")


def verify(source: Path, elf: Path):
    raw = elf.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_ELF_SHA256
    assert len(raw) == 8280
    assert raw[:16] == b"\x7fELF\x02\x01\x01" + bytes(9)
    rx, rw = (struct.unpack_from("<IIQQQQQQ", raw, 64 + 56 * i) for i in range(2))
    assert rx == (1, 5, 4096, 0x1E1000, 0x1E1000, 109, 109, 4096)
    assert rw == (1, 6, 8192, 0x1E2000, 0x1E2000, 88, 88, 4096)
    text = source.read_text()
    assert "(ns aiueos.native.user-elf-entry" in text
    words = {"c": {}, "r": {}}
    for kind, number, page, offset, literal in WORD_PATTERN.findall(text):
        assert (kind, page) in (("c", "code"), ("r", "request"))
        index = int(number)
        assert index not in words[kind] and int(offset) == index * 8
        value = int(literal)
        assert -(1 << 63) <= value < (1 << 63)
        words[kind][index] = value & ((1 << 64) - 1)
    assert set(words["c"]) == set(range(14))
    assert set(words["r"]) == set(range(11))
    code = b"".join(words["c"][i].to_bytes(8, "little") for i in range(14))
    data = b"".join(words["r"][i].to_bytes(8, "little") for i in range(11))
    assert code[:109] == raw[4096:4205] and code[109:] == bytes(3)
    assert data == raw[8192:8280]
    return raw[4096:4205]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--elf", type=Path, required=True)
    args = parser.parse_args()
    verify(args.source, args.elf)
    print("PASS_NATIVE_USER_SCALAR_SOURCE_ARTIFACT_PARITY")
