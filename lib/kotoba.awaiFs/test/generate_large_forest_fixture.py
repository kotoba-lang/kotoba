#!/usr/bin/env python3
"""Recreate the pinned test fixture; this is staging, not a runtime codec."""
import hashlib
import struct
import sys
from pathlib import Path

root = Path(__file__).parent / 'fixtures'
source = (root / 'forest-part0.car.zst').read_bytes()
if hashlib.sha256(source).hexdigest() != '87a1d2773c099ef49af8fc7b9b00b43123a4e83ab1bc3f1f2b3fca0278fb62df':
    raise ValueError('source fixture mismatch')
data = bytearray(source)
shift = 1153432
index = struct.unpack_from('<Q', data, len(data) - 8)[0] - 8
footer = len(data) - 16
for offset in range(index + 40, footer, 16):
    key, position = struct.unpack_from('<QQ', data, offset)
    if key != (1 << 64) - 1:
        struct.pack_into('<Q', data, offset + 8, position + shift)
struct.pack_into('<Q', data, len(data) - 8, index + 8 + shift)
result = struct.pack('<II', 0x184d2a50, shift - 8) + bytes(shift - 8) + data
if hashlib.sha256(result).hexdigest() != 'eea07036e8a76dd891f675a198a3da90afa4181f31794c910f376fe27b7bd39f':
    raise ValueError('generated fixture mismatch')
if len(sys.argv) != 2:
    raise ValueError('supply a new task-owned output path')
# Never overwrite a retained artifact.
with Path(sys.argv[1]).open('xb') as out:
    out.write(result)
