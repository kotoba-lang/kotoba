#!/usr/bin/env python3
"""Link several x86_64-aiueos-kernel-v1 objects (and clang-built C objects) into one flat bare-metal image with
harness2.S, which feeds the vectors of a contract to FUNC and prints the return value and the 40-byte poll struct.
usage: build2.py OUTDIR FUNC CONTRACT.edn OBJECT [OBJECT ...]"""
import re, struct, subprocess, sys
from pathlib import Path
here = Path(__file__).parent.resolve()
out = Path(sys.argv[1]).resolve(); out.mkdir(parents=True, exist_ok=True)
func, contract = sys.argv[2], (Path(sys.argv[3]).read_text() if Path(sys.argv[3]).suffix != ".hex" else "")
objs = [Path(p) for p in sys.argv[4:]]

def elf(blob):
    shoff, = struct.unpack_from("<Q", blob, 40); shnum, shstrndx = struct.unpack_from("<HH", blob, 60)
    secs = [struct.unpack_from("<IIQQQQIIQQ", blob, shoff + 64 * i) for i in range(shnum)]
    shstr = blob[secs[shstrndx][4]:secs[shstrndx][4] + secs[shstrndx][5]]
    nm = lambda t, o: t[o:t.index(b"\0", o)].decode()
    names = [nm(shstr, s[0]) for s in secs]
    body = lambda n: (blob[secs[names.index(n)][4]:secs[names.index(n)][4] + secs[names.index(n)][5]]
                      if n in names and secs[names.index(n)][1] != 8 else b"")
    strtab = body(".strtab"); sd = body(".symtab")
    syms = [(nm(strtab, n), info, shndx, val) for off in range(0, len(sd), 24)
            for n, info, o, shndx, val, size in [struct.unpack_from("<IBBHQQ", sd, off)]]
    rd = body(".rela.text")
    relas = [struct.unpack_from("<QQq", rd, o) for o in range(0, len(rd), 24)]
    dname = ".data" if ".data" in names else (".bss" if ".bss" in names else None)
    dsize = secs[names.index(dname)][5] if dname else 0
    data = body(".data") if dname == ".data" else bytes(dsize)
    return names, body(".text"), data, syms, relas, names.index(".text"), (names.index(dname) if dname else -1)

L = []; text = b""; data = b""
for o in objs:
    names, t, d, syms, relas, ti, di = elf(o.read_bytes())
    text += b"\0" * (-len(text) % 16); data += b"\0" * (-len(data) % 16)
    L.append(dict(path=o, t=len(text), d=len(data), tbytes=t, syms=syms, relas=relas, ti=ti, di=di)); text += t; data += d
(out / "objs.text").write_bytes(text); (out / "objs.data").write_bytes(data)
exports = {}
for o in L:
    for n, info, shndx, val in o["syms"]:
        if shndx == o["ti"] and (info >> 4) == 1: exports[n] = o["t"] + val
assert func in exports, (func, sorted(exports))
# vectors from the contract: the first seed (offset 0) is the HTTP response
vecs = []
if Path(sys.argv[3]).suffix == ".hex":
    vecs = [bytes.fromhex(l.strip()) for l in Path(sys.argv[3]).read_text().split() if l.strip()]
for blk in ([] if vecs else re.split(r"\{:name :", contract)[1:]):
    m = re.search(r':seed \[\{:offset 0 :hex "([0-9a-f]*)"\}', blk); a = re.search(r":args \[:http (\d+) :out\]", blk)
    if m and a:
        b = bytes.fromhex(m.group(1)); n = int(a.group(1)); vecs.append(b[:n].ljust(n, b"\0"))
blob = struct.pack("<Q", len(vecs))
for b in vecs: blob += struct.pack("<Q", len(b)) + b + b"\0" * (-len(b) % 8)
(out / "vectors.bin").write_bytes(blob)
subprocess.run(["clang", "-target", "x86_64-unknown-linux-gnu", "-c", str(here / "harness2.S"), "-I", str(out), f"-DFUNC_OFF={exports[func]}",
                "-o", str(out / "h.o")], check=True, cwd=out)
_, htext, _, hsyms, hrelas, _, _ = elf((out / "h.o").read_bytes())
assert not hrelas, hrelas
hs = {n: v for n, i, s, v in hsyms}
img = bytearray(htext); ot, od = hs["obj_text"], hs["obj_data"]
img[od:od + len(data)] = data
img[ot:ot + len(text)] = text
glob = {n: ot + v for n, v in exports.items()}; glob["memset"] = hs["memset"]
for o in L:
    for off, info, add in o["relas"]:
        typ, si = info & 0xFFFFFFFF, info >> 32
        name, sinfo, shndx, val = o["syms"][si]
        assert typ in (2, 4, 1, 11), f"relocation type {typ} for {name}"
        if shndx == 0: S = glob[name]
        elif shndx == o["di"]: S = od + o["d"] + val
        elif shndx == o["ti"]: S = ot + o["t"] + val
        else: raise SystemExit(f"{name}: section {shndx}")
        site = ot + o["t"] + off
        if typ in (2, 4): struct.pack_into("<i", img, site, S + add - site)
        else: raise SystemExit(f"absolute relocation {typ} for {name} is not supported by this linker")
(out / "image.bin").write_bytes(bytes(img))
print("image", len(img), "vectors", len(vecs), "objects", len(objs))
