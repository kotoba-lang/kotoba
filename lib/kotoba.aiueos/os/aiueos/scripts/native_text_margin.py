"""Kernel text margin against the compiler's code cap (JUN-811).

The compiler refuses a project whose cumulative per-module code extent exceeds `kp-text-cap` (amu seed/85
kp-emit-module, E7104) and prints nothing about the extent when it fits, so a feature that adds a few KiB first shows up as
a compile refusal. This reads the executable PT_LOAD of KERNEL.ELF and estimates the margin.

The ELF text segment is larger than the compiler's extent by a fixed amount (entry shims and import stubs after the last
module, plus 16-byte alignment). That amount is measured per compiler image and kept in native/layout-table.json; it is
used only for the exact compiler image it was measured with. For any other compiler the margin is reported UNCALIBRATED
and not enforced, never guessed.
"""
import struct


def text_segment_bytes(elf_bytes):
    """File size of the single executable PT_LOAD of an ELF64 little-endian image."""
    if elf_bytes[:7] != b"\x7fELF\x02\x01\x01":
        raise ValueError("not an ELF64 little-endian image")
    phoff, = struct.unpack_from("<Q", elf_bytes, 32)
    phentsize, phnum = struct.unpack_from("<HH", elf_bytes, 54)
    if phentsize != 56:
        raise ValueError("unexpected program header size")
    sizes = []
    for index in range(phnum):
        kind, flags, _off, _va, _pa, filesz, _memsz, _align = struct.unpack_from("<IIQQQQQQ", elf_bytes, phoff + index * phentsize)
        if kind == 1 and flags & 1:
            sizes.append(filesz)
    if len(sizes) != 1:
        raise ValueError("expected exactly one executable PT_LOAD, found %d" % len(sizes))
    return sizes[0]


def text_margin(elf_bytes, cap_bytes, compiler_sha256, table_row):
    """Return the margin record for the receipt. `table_row` is the layout-table rung of the kernel target."""
    text = text_segment_bytes(elf_bytes)
    spec = table_row.get("textMargin")
    record = {"textSegmentBytes": text, "compilerCapBytes": cap_bytes}
    if not spec:
        return {**record, "state": "UNCONFIGURED"}
    calibration = next((c for c in spec["calibrations"] if c["compilerSha256"] == compiler_sha256), None)
    if calibration is None:
        return {**record, "state": "UNCALIBRATED", "compilerSha256": compiler_sha256}
    overhead = calibration["textSegmentOverheadBytes"]
    margin = cap_bytes - (text - overhead)
    state = "FAIL" if margin < spec["failBelowBytes"] else "WARN" if margin < spec["warnBelowBytes"] else "OK"
    return {**record, "state": state, "estimatedMarginBytes": margin, "textSegmentOverheadBytes": overhead,
            "warnBelowBytes": spec["warnBelowBytes"], "failBelowBytes": spec["failBelowBytes"],
            "compilerSha256": compiler_sha256}
