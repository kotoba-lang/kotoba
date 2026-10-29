#!/usr/bin/env python3
"""Fail-closed validation for the x86_64-aiueos-kernel-v1 object ABI.

usage: verify-kotoba-kernel-object.py OBJECT [SHA256] [EXPORT[,EXPORT...]] [EXTERN[,EXTERN...]]

One export is the original contract. A comma-separated list (at most 8) names
the exports of a multi-export object (amu JUN-556): every name is exactly one
GLOBAL FUNC in .text, and there is one .rela.text entry per export, each an
R_X86_64_PC32 with addend -4 against the same local .data context symbol and
inside .text. Anything else is refused as before.

An optional fourth argument names declared extern functions (amu JUN-556 D1, ADR 0380,
at most 16). Each is exactly one undefined GLOBAL NOTYPE symbol, distinct from the
exports. Every .rela.text entry after the per-export context relocations must be an
R_X86_64_PLT32 with addend -4 against a declared extern, placed on the displacement of a
`call rel32` (0xE8, zero displacement) that is followed by `mov r9,[rbp-8]`
(4c 8b 4d f8). Any other undefined symbol is still refused, and without the
fourth argument the contract is exactly the previous one.
"""

import struct
import sys
import hashlib
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"error: invalid Kotoba kernel object: {message}")


blob = Path(sys.argv[1]).read_bytes()
expected_symbols = (sys.argv[3] if len(sys.argv) > 3 else "kotoba_aiueos_probe").split(",")
if not 1 <= len(expected_symbols) <= 8 or len(set(expected_symbols)) != len(expected_symbols) or "" in expected_symbols:
    fail("export list must be one to eight distinct names")
extern_symbols = [name for name in (sys.argv[4] if len(sys.argv) > 4 else "").split(",") if name]
if len(extern_symbols) > 16 or len(set(extern_symbols)) != len(extern_symbols) or set(extern_symbols) & set(expected_symbols):
    fail("extern list must be at most sixteen distinct names that are not exports")
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
for expected_symbol in expected_symbols:
    probes = [item for item in symbols if item[0] == expected_symbol]
    if len(probes) != 1:
        fail(f"requires exactly one {expected_symbol} symbol")
    _, info, other, shndx, _, size = probes[0]
    if info != 0x12 or other != 0 or shndx != by_name[".text"] or size == 0:
        fail("export must be a default-visibility GLOBAL FUNC defined in .text")
for extern_symbol in extern_symbols:
    declared = [item for item in symbols if item[0] == extern_symbol]
    if len(declared) != 1 or declared[0][1:] != (0x10, 0, 0, 0, 0):
        fail(f"extern {extern_symbol} must be exactly one undefined GLOBAL NOTYPE symbol")
if any(item[3] == 0 and item[0] and item[0] not in extern_symbols for item in symbols):
    fail("undefined/imported symbols are forbidden")
rela = sections[by_name[".rela.text"]]
count = len(expected_symbols)
call_sites = rela[5] // 24 - count
if (rela[1] != 4 or rela[9] != 24 or rela[6] != sym_index or rela[7] != by_name[".text"] or rela[5] % 24
        or call_sites < 0 or (call_sites and not extern_symbols)):
    fail("requires exactly one .rela.text entry" if count == 1 else f"requires exactly {count} .rela.text entries")
text = section_bytes(by_name[".text"])
text_size = len(text)
data_symbols = set()
for entry in range(count):
    rel_offset, rel_info, addend = struct.unpack_from("<QQq", section_bytes(by_name[".rela.text"]), entry * 24)
    symbol_index, relocation_type = rel_info >> 32, rel_info & 0xFFFFFFFF
    if symbol_index >= len(symbols) or relocation_type != 2 or addend != -4:
        fail("relocation must be R_X86_64_PC32 with addend -4")
    if symbols[symbol_index][3] != by_name[".data"]:
        fail("relocation target must be defined in .data")
    if rel_offset + 4 > text_size:
        fail("relocation offset exceeds .text")
    data_symbols.add(symbol_index)
if len(data_symbols) != 1:
    fail("every relocation must name the same context symbol")
for entry in range(count, count + call_sites):
    rel_offset, rel_info, addend = struct.unpack_from("<QQq", section_bytes(by_name[".rela.text"]), entry * 24)
    symbol_index, relocation_type = rel_info >> 32, rel_info & 0xFFFFFFFF
    if symbol_index >= len(symbols) or symbols[symbol_index][0] not in extern_symbols or symbols[symbol_index][3] != 0:
        fail("a call relocation must name a declared extern")
    if relocation_type != 4 or addend != -4:
        fail("call relocation must be R_X86_64_PLT32 with addend -4")
    if rel_offset < 1 or rel_offset + 8 > text_size or text[rel_offset - 1] != 0xE8 or text[rel_offset:rel_offset + 4] != b"\0\0\0\0":
        fail("call relocation must sit on the displacement of a call rel32")
    if text[rel_offset + 4:rel_offset + 8] != bytes.fromhex("4c8b4df8"):
        fail("an extern call must be followed by mov r9,[rbp-8]")
print(f"AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export={','.join(expected_symbols)} imports={len(extern_symbols)} relocations={count + call_sites}")
