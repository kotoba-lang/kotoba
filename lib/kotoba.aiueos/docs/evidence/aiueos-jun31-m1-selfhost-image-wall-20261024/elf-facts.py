#!/usr/bin/env python3
"""M1 window facts: parse one KERNEL.ELF's program headers against the loader's
fixture literals (loader-probe.kotoba:20-31). Python orchestrates and hashes
only; no build logic here."""
import struct, hashlib, sys

p = sys.argv[1]
b = open(p, "rb").read()
print("file bytes:", len(b), "sha256:", hashlib.sha256(b).hexdigest())
eh = struct.unpack_from("<HHIQQQIHHHHHH", b, 16)
etype, machine, version, entry, phoff, shoff, flags, ehsize, phentsize, phnum, shentsize, shnum, shstrndx = eh
print(f"e_type={etype} e_machine={machine} e_entry=0x{entry:x} "
      f"e_phoff={phoff} e_phnum={phnum} e_shoff={shoff} e_shnum={shnum}")
phs = []
for i in range(phnum):
    off = phoff + i * phentsize
    t, fl, poff, vaddr, paddr, filesz, memsz, align = struct.unpack_from("<IIQQQQQQ", b, off)
    phs.append((t, fl, poff, vaddr, paddr, filesz, memsz, align))
    print(f"ph[{i}] type={t} flags={fl} poff={poff} vaddr=0x{vaddr:x} paddr=0x{paddr:x} "
          f"filesz={filesz} memsz={memsz} align={align}")

loads = [x for x in phs if x[0] == 1]
print("--- window clauses (fixture literals, loader-probe.kotoba:20-31) ---")
if len(loads) >= 2:
    (t0, fl0, o0, v0, p0, fs0, ms0, a0), (t1, fl1, o1, v1, p1, fs1, ms1, a1) = loads[0], loads[1]
    checks = [
        ("phnum==2", phnum == 2, phnum),
        ("s0off==4096", o0 == 4096, o0),
        ("s1off==32768", o1 == 32768, o1),
        ("kentry==s0addr", entry == p0, hex(entry)),
        ("s0 filesz==memsz", fs0 == ms0, (fs0, ms0)),
        ("s1 filesz==memsz", fs1 == ms1, (fs1, ms1)),
        ("s0mem<=4096", ms0 <= 4096, ms0),
        ("s1mem<=77824", ms1 <= 77824, ms1),
        ("klen<=114688", len(b) <= 114688, len(b)),
    ]
    for name, ok, val in checks:
        print(f"{'pass' if ok else 'FAIL'} {name}  (measured {val})")
print("bytes after seg1 file end:", len(b) - (o1 + fs1))
