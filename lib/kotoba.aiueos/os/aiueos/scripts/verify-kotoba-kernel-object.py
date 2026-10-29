#!/usr/bin/env python3
"""Fail-closed validation for the x86_64-aiueos-kernel-v1 object ABI.

usage: verify-kotoba-kernel-object.py OBJECT [SHA256] [EXPORT[,EXPORT...]] [EXTERN[,EXTERN...]] [DATA[,DATA...]]

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

Data cells (amu JUN-556 D3, D3b): .data may hold, after the 80-byte context, 8-byte cells at 80 + 8k (k < 64).
Every further R_X86_64_PC32 relocation must name the context symbol with addend 80 + 8k - 4 and sit on the zero
displacement of `mov rax,[rip+disp]` (48 8b 05) or `mov [rip+disp],rax` (48 89 05). The optional fifth argument
names data symbols (at most 16): each is exactly one GLOBAL OBJECT of size 8 in .data at 80 + 8j, distinct from
every other name. .data is exactly 80 + 8 * (highest cell used or named + 1) bytes and the cells are zero.
Fixed-address MMIO (D4) is an immediate in .text and adds no relocation, symbol or data to check here.
Every symbol must be null, the context, an export, a declared extern or a declared data symbol; anything else is refused.
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
data_symbol_names = [name for name in (sys.argv[5] if len(sys.argv) > 5 else "").split(",") if name]
if (len(data_symbol_names) > 16 or len(set(data_symbol_names)) != len(data_symbol_names)
        or set(data_symbol_names) & (set(expected_symbols) | set(extern_symbols) | {"context"})):
    fail("data symbol list must be at most sixteen distinct names that are not exports, externs or context")
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
data_index = by_name[".data"]
data_section = sections[data_index]
declared_names = set(expected_symbols) | set(extern_symbols) | set(data_symbol_names)
for item in symbols:
    if item[0] and item[0] != "context" and item[0] not in declared_names:
        fail(f"unexpected symbol {item[0]}")
cells_named = 0
for name in data_symbol_names:
    found = [item for item in symbols if item[0] == name]
    if len(found) != 1:
        fail(f"requires exactly one {name} symbol")
    _, info, other, shndx, value, size = found[0]
    if info != 0x11 or other != 0 or shndx != data_index or size != 8 or value < 80 or (value - 80) % 8 or (value - 80) // 8 >= 64:
        fail(f"data symbol {name} must be a GLOBAL OBJECT of size 8 in .data at 80 + 8k, k < 64")
    cells_named = max(cells_named, (value - 80) // 8 + 1)
rela = sections[by_name[".rela.text"]]
count = len(expected_symbols)
extras = rela[5] // 24 - count
if rela[1] != 4 or rela[9] != 24 or rela[6] != sym_index or rela[7] != by_name[".text"] or rela[5] % 24 or extras < 0:
    fail("requires exactly one .rela.text entry" if count == 1 else f"requires exactly {count} .rela.text entries")
text = section_bytes(by_name[".text"])
text_size = len(text)
rela_bytes = section_bytes(by_name[".rela.text"])
context_symbols = set()
for entry in range(count):
    rel_offset, rel_info, addend = struct.unpack_from("<QQq", rela_bytes, entry * 24)
    symbol_index, relocation_type = rel_info >> 32, rel_info & 0xFFFFFFFF
    if symbol_index >= len(symbols) or relocation_type != 2 or addend != -4:
        fail("relocation must be R_X86_64_PC32 with addend -4")
    if symbols[symbol_index][3] != data_index:
        fail("relocation target must be defined in .data")
    if rel_offset + 4 > text_size:
        fail("relocation offset exceeds .text")
    context_symbols.add(symbol_index)
if len(context_symbols) != 1:
    fail("every relocation must name the same context symbol")
context_index = next(iter(context_symbols))
if symbols[context_index][0] != "context":
    fail("the shim relocations must name the context symbol")
calls = 0
cells_used = 0
for entry in range(count, count + extras):
    rel_offset, rel_info, addend = struct.unpack_from("<QQq", rela_bytes, entry * 24)
    symbol_index, relocation_type = rel_info >> 32, rel_info & 0xFFFFFFFF
    if symbol_index >= len(symbols):
        fail("relocation names a missing symbol")
    if relocation_type == 4:
        if symbols[symbol_index][0] not in extern_symbols or symbols[symbol_index][3] != 0:
            fail("a call relocation must name a declared extern")
        if addend != -4:
            fail("call relocation must be R_X86_64_PLT32 with addend -4")
        if rel_offset < 1 or rel_offset + 8 > text_size or text[rel_offset - 1] != 0xE8 or text[rel_offset:rel_offset + 4] != b"\0\0\0\0":
            fail("call relocation must sit on the displacement of a call rel32")
        if text[rel_offset + 4:rel_offset + 8] != bytes.fromhex("4c8b4df8"):
            fail("an extern call must be followed by mov r9,[rbp-8]")
        calls += 1
    elif relocation_type == 2:
        k, rest = divmod(addend + 4 - 80, 8)
        if symbol_index != context_index or rest != 0 or not 0 <= k < 64:
            fail("a cell access must be R_X86_64_PC32 against the context with addend 80 + 8k - 4, k < 64")
        if rel_offset < 3 or rel_offset + 4 > text_size or text[rel_offset - 3:rel_offset] not in (bytes.fromhex("488b05"), bytes.fromhex("488905")):
            fail("a cell access must be mov rax,[rip+disp] or mov [rip+disp],rax")
        if text[rel_offset:rel_offset + 4] != b"\0\0\0\0":
            fail("a cell access displacement must be zero for the linker")
        cells_used = max(cells_used, k + 1)
    else:
        fail("unsupported relocation type")
if calls and not extern_symbols:
    fail("a call relocation needs a declared extern")
cells = max(cells_used, cells_named)
if data_section[5] != 80 + 8 * cells:
    fail(f".data must be exactly {80 + 8 * cells} bytes for {cells} cell(s), got {data_section[5]}")
if any(section_bytes(data_index)[80:]):
    fail("data cells must be zero")
extra = f" cells={cells} data_symbols={len(data_symbol_names)}" if cells or data_symbol_names else ""
print(f"AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export={','.join(expected_symbols)} imports={len(extern_symbols)} relocations={count + extras}{extra}")
