#!/usr/bin/env python3
import hashlib
import struct
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected = sys.argv[2]
blob = path.read_bytes()
if hashlib.sha256(blob).hexdigest() != expected:
    raise SystemExit("error: Kotoba user ELF digest mismatch")
if len(blob) < 64 or blob[:6] != b"\x7fELF\x02\x01":
    raise SystemExit("error: invalid Kotoba user ELF identity")
etype, machine, version = struct.unpack_from("<HHI", blob, 16)
entry, phoff = struct.unpack_from("<QQ", blob, 24)
ehsize, phentsize, phnum = struct.unpack_from("<HHH", blob, 52)
if (etype, machine, version, entry, ehsize, phentsize, phnum) != (
        2, 0x3E, 1, 0x1E1000, 64, 56, 2):
    raise SystemExit("error: unsupported Kotoba user ELF contract")
segments = []
data_segment = None
for index in range(phnum):
    offset = phoff + index * phentsize
    if offset + phentsize > len(blob):
        raise SystemExit("error: truncated Kotoba user program headers")
    ptype, flags, file_offset, va, _, filesz, memsz, align = struct.unpack_from(
        "<IIQQQQQQ", blob, offset)
    if ptype != 1 or filesz > memsz or memsz > 4096 or file_offset + filesz > len(blob):
        raise SystemExit("error: invalid Kotoba user segment range")
    segments.append((flags, va, align))
    if va == 0x1E2000:
        data_segment = (file_offset, filesz)
if segments != [(5, 0x1E1000, 4096), (6, 0x1E2000, 4096)]:
    raise SystemExit("error: Kotoba user segments are not canonical RX/RW")
if data_segment is None or data_segment[1] != 88:
    raise SystemExit("error: unsupported Kotoba user runtime context size")
context = blob[data_segment[0]:data_segment[0] + data_segment[1]]
if (struct.unpack_from("<Q", context, 8)[0] != 256 or context[16] != 60 or
        any(context[17:48]) or struct.unpack_from("<Q", context, 48)[0] != 0x1E1020 or
        any(context[56:80]) or struct.unpack_from("<Q", context, 80)[0] != 0):
    raise SystemExit("error: invalid Kotoba aiueos runtime-v2 context")
if blob[0x1020:0x102c] != bytes([0xB8,5,0,0,0,0x48,0x8B,0x7F,0x50,0x0F,5,0xC3]):
    raise SystemExit("error: invalid Kotoba aiueos runtime syscall trampoline")
print("AIUEOS_KOTOBA_USER_ELF_OK entry=1e1000 segments=rx,rw runtime=v2 caps=2,3,4,5")
