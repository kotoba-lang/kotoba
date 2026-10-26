#!/usr/bin/env python3
"""Fail-closed validation for the x86_64-aiueos-kernel-v1 object ABI."""

import struct
import sys
import hashlib
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"error: invalid Kotoba kernel object: {message}")


blob = Path(sys.argv[1]).read_bytes()
expected_symbol = sys.argv[3] if len(sys.argv) > 3 else "kotoba_aiueos_probe"
if len(sys.argv) > 2 and sys.argv[2] and hashlib.sha256(blob).hexdigest() != sys.argv[2]:
    fail("fixture digest does not match the pinned compiler output")
if len(blob) < 64 or blob[:16] != b"\x7fELF\x02\x01\x01\x00" + b"\0" * 8:
    fail("not canonical ELF64 little-endian System V")
header = struct.unpack_from("<HHIQQQIHHHHHH", blob, 16)
etype, machine, version, entry, phoff, shoff, flags, ehsize, phentsize, phnum, shentsize, shnum, shstrndx = header
if (etype, machine, version, entry, phoff, phnum, flags, ehsize, shentsize) != (1, 62, 1, 0, 0, 0, 0, 64, 64):
    fail("header is not ET_REL/EM_X86_64 without program headers")
if not shnum or shnum > 16 or shstrndx >= shnum or shoff + shnum * 64 > len(blob):
    fail("invalid section table bounds")
sections = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + i * 64) for i in range(shnum)]


def section_bytes(index: int) -> bytes:
    _, stype, _, _, offset, size, _, _, _, _ = sections[index]
    if stype == 8:  # SHT_NOBITS
        return b""
    if offset + size > len(blob):
        fail("section exceeds file")
    return blob[offset : offset + size]


strings = section_bytes(shstrndx)


def string_at(table: bytes, offset: int) -> str:
    if offset >= len(table):
        fail("string offset exceeds table")
    end = table.find(b"\0", offset)
    if end < 0:
        fail("unterminated string")
    try:
        return table[offset:end].decode("ascii")
    except UnicodeDecodeError:
        fail("non-ASCII name")


names = [string_at(strings, section[0]) for section in sections]
allowed = {"", ".text", ".data", ".rela.text", ".symtab", ".strtab", ".shstrtab"}
if set(names) != allowed or len(names) != len(allowed):
    fail(f"section set must be exactly {sorted(allowed)!r}, got {names!r}")
by_name = {name: index for index, name in enumerate(names)}
if sections[by_name[".text"]][1] != 1 or not sections[by_name[".text"]][2] & 0x4:
    fail(".text must be executable PROGBITS")
if sections[by_name[".data"]][1] != 1 or sections[by_name[".data"]][2] & 0x4:
    fail(".data must be non-executable PROGBITS")
sym_index = by_name[".symtab"]
sym = sections[sym_index]
if sym[1] != 2 or sym[9] != 24 or sym[6] != by_name[".strtab"] or sym[5] % 24:
    fail("invalid symbol table")
symbol_strings = section_bytes(by_name[".strtab"])
symbols = []
for offset in range(0, len(section_bytes(sym_index)), 24):
    name, info, other, shndx, value, size = struct.unpack_from("<IBBHQQ", section_bytes(sym_index), offset)
    symbols.append((string_at(symbol_strings, name), info, other, shndx, value, size))
probes = [item for item in symbols if item[0] == expected_symbol]
if len(probes) != 1:
    fail(f"requires exactly one {expected_symbol} symbol")
_, info, other, shndx, _, size = probes[0]
if info != 0x12 or other != 0 or shndx != by_name[".text"] or size == 0:
    fail("export must be a default-visibility GLOBAL FUNC defined in .text")
if any(item[3] == 0 and item[0] for item in symbols):
    fail("undefined/imported symbols are forbidden")
rela = sections[by_name[".rela.text"]]
if rela[1] != 4 or rela[9] != 24 or rela[6] != sym_index or rela[7] != by_name[".text"] or rela[5] != 24:
    fail("requires exactly one .rela.text entry")
rel_offset, rel_info, addend = struct.unpack("<QQq", section_bytes(by_name[".rela.text"]))
symbol_index, relocation_type = rel_info >> 32, rel_info & 0xFFFFFFFF
if symbol_index >= len(symbols) or relocation_type != 2 or addend != -4:
    fail("relocation must be R_X86_64_PC32 with addend -4")
if symbols[symbol_index][3] != by_name[".data"]:
    fail("relocation target must be defined in .data")
if rel_offset + 4 > len(section_bytes(by_name[".text"])):
    fail("relocation offset exceeds .text")
print(f"AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export={expected_symbol} imports=0 relocations=1")
