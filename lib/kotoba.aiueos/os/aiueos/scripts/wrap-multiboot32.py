#!/usr/bin/env python3
"""Wrap a linked x86_64 kernel image in a 32-bit ELF container.

QEMU's built-in Multiboot loader requires an ELFCLASS32 / EM_386 image because
it enters the kernel in 32-bit protected mode. The kernel's machine code is
still the x86_64 code produced by the linker (the trampoline switches to long
mode); only the ELF container metadata — class, machine, program headers, and
entry — is rebuilt here. Load bytes are copied verbatim from the input's
PT_LOAD segments, so the multiboot header and all code are byte-identical.
"""

import struct
import sys
from pathlib import Path

PT_LOAD = 1


def main():
    source, output = sys.argv[1], sys.argv[2]
    data = Path(source).read_bytes()
    if data[:4] != b"\x7fELF" or data[4] != 2:
        raise SystemExit("input is not a 64-bit ELF")
    entry = struct.unpack_from("<Q", data, 24)[0]
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phentsize = struct.unpack_from("<H", data, 54)[0]
    phnum = struct.unpack_from("<H", data, 56)[0]

    segments = []
    for i in range(phnum):
        base = phoff + i * phentsize
        p_type = struct.unpack_from("<I", data, base)[0]
        if p_type != PT_LOAD:
            continue
        p_offset = struct.unpack_from("<Q", data, base + 8)[0]
        p_paddr = struct.unpack_from("<Q", data, base + 24)[0]
        p_filesz = struct.unpack_from("<Q", data, base + 32)[0]
        p_memsz = struct.unpack_from("<Q", data, base + 40)[0]
        segments.append((p_paddr, p_offset, p_filesz, p_memsz))
    if not segments:
        raise SystemExit("no PT_LOAD segments")
    if entry > 0xFFFFFFFF:
        raise SystemExit("entry does not fit a 32-bit container")

    load_base = min(s[0] for s in segments)
    load_end = max(s[0] + s[3] for s in segments)
    if load_base > 0xFFFFFFFF or load_end > 0xFFFFFFFF:
        raise SystemExit("load image does not fit below 4 GiB")
    image = bytearray(load_end - load_base)
    for p_paddr, p_offset, p_filesz, _ in segments:
        image[p_paddr - load_base:p_paddr - load_base + p_filesz] = \
            data[p_offset:p_offset + p_filesz]

    ehsize, phentsize32 = 52, 32
    # Round the load data up to an 8-byte file offset so the embedded Multiboot
    # and Multiboot2 headers keep their 8-byte alignment in the file (GRUB
    # searches for the MB2 header at 8-byte-aligned file offsets).
    data_offset = (ehsize + phentsize32 + 7) & ~7
    pad = data_offset - (ehsize + phentsize32)
    header = bytearray(ehsize)
    header[0:4] = b"\x7fELF"
    header[4], header[5], header[6] = 1, 1, 1  # ELFCLASS32, ELFDATA2LSB, version
    struct.pack_into("<HHIIIIIHHHHHH", header, 16,
                     2, 3, 1, entry, ehsize, 0, 0,
                     ehsize, phentsize32, 1, 0, 0, 0)
    phdr = struct.pack("<IIIIIIII", PT_LOAD, data_offset, load_base, load_base,
                       len(image), len(image), 7, 0x1000)
    Path(output).write_bytes(bytes(header) + phdr + bytes(pad) + bytes(image))
    print("wrapped 32-bit multiboot ELF: entry=0x%x load=0x%x-0x%x" %
          (entry, load_base, load_end))


if __name__ == "__main__":
    main()
