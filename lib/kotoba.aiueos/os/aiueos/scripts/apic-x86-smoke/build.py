#!/usr/bin/env python3
"""Link an apic object (Kotoba apic.o, or clang-built kernel/apic.c) into a flat bare-metal image with
harness.S and print the image path. usage: build.py OBJECT OUTDIR"""
import struct, subprocess, sys
from pathlib import Path
here = Path(__file__).parent.resolve()
obj = Path(sys.argv[1]).read_bytes()
out = Path(sys.argv[2]).resolve(); out.mkdir(parents=True, exist_ok=True)
NAMES = ("aiueos_apic_timer_mask", "aiueos_apic_timer_unmask", "aiueos_apic_timer_initialize",
         "aiueos_apic_timer_ticks", "aiueos_apic_mmio_base")

def elf(blob):
    shoff, = struct.unpack_from("<Q", blob, 40); shnum, shstrndx = struct.unpack_from("<HH", blob, 60)
    secs = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + 64 * i) for i in range(shnum)]
    shstr = blob[secs[shstrndx][4]:secs[shstrndx][4] + secs[shstrndx][5]]
    nm = lambda t, o: t[o:t.index(b"\0", o)].decode()
    names = [nm(shstr, s[0]) for s in secs]
    sec = lambda n: secs[names.index(n)] if n in names else None
    body = lambda n: blob[sec(n)[4]:sec(n)[4] + sec(n)[5]] if sec(n) and sec(n)[1] != 8 else b""
    strtab = body(".strtab"); sd = body(".symtab")
    syms = [(nm(strtab, n), info, shndx, val) for off in range(0, len(sd), 24)
            for n, info, o, shndx, val, size in [struct.unpack_from("<IBBHQQ", sd, off)]]
    rd = body(".rela.text")
    relas = [struct.unpack_from("<QQq", rd, o) for o in range(0, len(rd), 24)]
    return names, secs, body(".text"), syms, relas

names, secs, text, syms, relas = elf(obj)
data_name = ".data" if ".data" in names else ".bss"
dsec = secs[names.index(data_name)]
data = bytes(dsec[5]) if data_name == ".bss" else obj[dsec[4]:dsec[4] + dsec[5]]
data_idx, text_idx = names.index(data_name), names.index(".text")
sym = {n: (shndx, v) for n, i, shndx, v in syms if n in NAMES}
assert set(sym) == set(NAMES), sym
(out / "apic.text").write_bytes(text); (out / "apic.data").write_bytes(data)
DEF = dict(zip(NAMES, ("OBJ_MASK", "OBJ_UNMASK", "OBJ_INIT", "TICKS", "MMIO_BASE")))
defs = [f"-D{DEF[n]}={sym[n][1]}" for n in NAMES]
subprocess.run(["clang", "-target", "x86_64-unknown-linux-gnu", "-c", str(here / "harness.S"), "-I", str(out), *defs,
                "-o", str(out / "h.o")], check=True, cwd=out)
_, _, h_text, h_syms, h_relas = elf((out / "h.o").read_bytes())
assert not h_relas, f"harness has unresolved relocations: {h_relas}"
hs = {n: v for n, i, s, v in h_syms}
img = bytearray(h_text)
obj_text, obj_data = hs["obj_text"], hs["obj_data"]
img[obj_data:obj_data + len(data)] = data
ext = {"kotoba_aiueos_msr_read": hs["msr_read"], "kotoba_aiueos_msr_write": hs["msr_write"]}
for off, info, add in relas:
    typ, si = info & 0xFFFFFFFF, info >> 32
    name, _, shndx, value = syms[si]
    assert typ in (2, 4), f"relocation type {typ} for {name}"
    if shndx == 0: S = ext[name]
    elif shndx == data_idx: S = obj_data + value
    elif shndx == text_idx: S = obj_text + value
    else: raise SystemExit(f"{name}: section {names[shndx]}")
    struct.pack_into("<i", img, obj_text + off, S + add - (obj_text + off))
(out / "image.bin").write_bytes(bytes(img))
print("image", len(img), "relocs", len(relas), "text", len(text), "data", len(data))
