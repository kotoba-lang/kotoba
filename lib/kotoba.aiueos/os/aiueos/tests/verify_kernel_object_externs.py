#!/usr/bin/env python3
"""The kernel object verifier's declared-extern contract (amu JUN-556 D1, ADR 0380).

fixtures/kernel-object-externs.o is the object a native Amu compiler wrote for
  (defn- extern-sink_a [a b] ..) (defn- extern-sink_b [a] ..)
  (defn f [x] (+ (extern-sink_a x 7) (+ (extern-sink_b x) (extern-sink_a 1 2))))
(amu scripts/seed/check-aiueos-object-externs.py, Mac F2 compiler). The test
checks that it passes with its declared list and that every tamper below is refused.
"""

import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
VERIFY = HERE.parent / "scripts" / "verify-kotoba-kernel-object.py"
SOURCE = (HERE / "fixtures" / "kernel-object-externs.o").read_bytes()


def run(blob, exports="f", externs="sink_a,sink_b"):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "t.o"
        path.write_bytes(blob)
        args = [sys.executable, "-I", str(VERIFY), str(path), "", exports]
        if externs is not None:
            args.append(externs)
        result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def layout(blob):
    shoff, = struct.unpack_from("<Q", blob, 40)
    shnum, shstr = struct.unpack_from("<HH", blob, 60)
    secs = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + 64 * i) for i in range(shnum)]
    table = secs[shstr][4]
    name = lambda o: blob[table + o:blob.index(b"\0", table + o)].decode()
    by = {name(s[0]): s for s in secs}
    return by[".text"][4], by[".rela.text"][4]


def main():
    text, rela = layout(SOURCE)
    rels = [struct.unpack_from("<QQq", SOURCE, rela + 24 * i) for i in range(4)]
    call = rels[1][0]
    code, out = run(SOURCE)
    assert code == 0 and "imports=2 relocations=4" in out, out
    for label, args in (("no list", dict(externs=None)), ("short list", dict(externs="sink_a")),
                        ("extern named like an export", dict(externs="f,sink_a,sink_b"))):
        code, out = run(SOURCE, **args)
        assert code != 0, label
    def tamper(label, edit):
        blob = bytearray(SOURCE)
        edit(blob)
        code, out = run(bytes(blob))
        assert code != 0, f"{label} was accepted"
    tamper("tail byte", lambda b: b.__setitem__(text + call + 4, b[text + call + 4] ^ 1))
    tamper("displacement", lambda b: b.__setitem__(text + call, 1))
    tamper("call opcode", lambda b: b.__setitem__(text + call - 1, 0x90))
    tamper("addend", lambda b: struct.pack_into("<q", b, rela + 24 + 16, 0))
    tamper("type PC32", lambda b: struct.pack_into("<Q", b, rela + 24 + 8, (rels[1][1] & ~0xFFFFFFFF) | 2))
    tamper("names the context", lambda b: struct.pack_into("<Q", b, rela + 24 + 8, (1 << 32) | 4))
    print("PASS_KERNEL_OBJECT_EXTERNS 1 accepted, 9 refused")


if __name__ == "__main__":
    main()


# ---- data cells, exported data symbols and the apic object (amu JUN-556 D3, D3b, D4) --------------------------------
APIC = (HERE / "fixtures" / "kernel-object-apic.o").read_bytes()
GLOBALS = (HERE / "fixtures" / "kernel-object-globals.o").read_bytes()
APIC_ARGS = dict(exports="aiueos_apic_timer_mask,aiueos_apic_timer_unmask,aiueos_apic_timer_initialize")
APIC_EXTERNS = "kotoba_aiueos_msr_read,kotoba_aiueos_msr_write"
APIC_DATA = "aiueos_apic_timer_ticks,aiueos_apic_mmio_base"


def run5(blob, exports, externs, data):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "t.o"
        path.write_bytes(blob)
        args = [sys.executable, "-I", str(VERIFY), str(path), "", exports, externs, data]
        result = subprocess.run(args, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def sections_of(blob):
    shoff, = struct.unpack_from("<Q", blob, 40)
    shnum, shstr = struct.unpack_from("<HH", blob, 60)
    secs = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + 64 * i) for i in range(shnum)]
    table = secs[shstr][4]
    name = lambda o: blob[table + o:blob.index(b"\0", table + o)].decode()
    return {name(s[0]): (shoff + 64 * i, s) for i, s in enumerate(secs)}


def cells_and_symbols():
    code, out = run5(APIC, APIC_ARGS["exports"], APIC_EXTERNS, APIC_DATA)
    assert code == 0 and "imports=2 relocations=7 cells=2 data_symbols=2" in out, out
    code, out = run5(GLOBALS, "f", "sink", "aiueos_apic_timer_ticks,aiueos_apic_mmio_base")
    assert code == 0 and "cells=4 data_symbols=2" in out, out
    # the declarations are the contract: missing or extra ones are refused
    for label, args in (("no data list", (APIC_ARGS["exports"], APIC_EXTERNS, "")),
                        ("short data list", (APIC_ARGS["exports"], APIC_EXTERNS, "aiueos_apic_timer_ticks")),
                        ("data symbol named like an export", (APIC_ARGS["exports"], APIC_EXTERNS, "aiueos_apic_timer_mask,aiueos_apic_mmio_base"))):
        code, _ = run5(APIC, *args)
        assert code != 0, label
    secs = sections_of(APIC)
    text_off = secs[".text"][1][4]
    data_hdr, data = secs[".data"]
    rela_off = secs[".rela.text"][1][4]
    rels = [struct.unpack_from("<QQq", APIC, rela_off + 24 * i) for i in range(7)]
    cell_rel = next(r for r in rels if r[1] & 0xFFFFFFFF == 2 and r[2] != -4)

    def tamper(label, edit):
        blob = bytearray(APIC)
        edit(blob)
        code, _ = run5(bytes(blob), APIC_ARGS["exports"], APIC_EXTERNS, APIC_DATA)
        assert code != 0, f"{label} was accepted"
    tamper("data section grown", lambda b: struct.pack_into("<Q", b, data_hdr + 32, data[5] + 8))
    tamper("cell not zero", lambda b: b.__setitem__(data[4] + 88, 1))
    tamper("cell opcode", lambda b: b.__setitem__(text_off + cell_rel[0] - 3, 0x90))
    tamper("cell displacement", lambda b: b.__setitem__(text_off + cell_rel[0], 1))
    tamper("cell addend off the grid", lambda b: struct.pack_into("<q", b, rela_off + 24 * rels.index(cell_rel) + 16, cell_rel[2] + 1))
    tamper("cell addend beyond 63", lambda b: struct.pack_into("<q", b, rela_off + 24 * rels.index(cell_rel) + 16, 80 + 8 * 64 - 4))
    print("PASS_KERNEL_OBJECT_CELLS 2 accepted, 3 declaration refusals, 6 tampers refused")


cells_and_symbols()
