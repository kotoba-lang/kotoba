#!/usr/bin/env python3
# usage: compare.py OLD-TRACE NEW-TRACE OLD-SERIAL NEW-SERIAL -- the port-I/O differentials' check (JUN-552): both QEMU
# runs log every device-register access (memory_region_ops_write / _read), the driver's debugcon output among them.
# Dropping the per-run CPU and MemoryRegion pointer fields and the firmware's accesses before the driver's first
# debugcon byte (timers and the CMOS clock, which vary from run to run), the two sequences must be equal entry for
# entry. Prints the driver's CASES line with DIFFS (differing trace entries, plus differing debugcon lines) and the
# device access counts.
import sys, re, collections
def norm(p):
    out = []
    for line in open(p, errors="replace"):
        m = re.search(r"memory_region_ops_(read|write) .*?addr (0x[0-9a-f]+) value (0x[0-9a-f]+) size (\d+) name '([^']*)'", line)
        if m: out.append(m.groups())
    i = next(i for i, x in enumerate(out) if x[4] == "isa-debugcon")
    return out[i:]
a, b = norm(sys.argv[1]), norm(sys.argv[2])
sa, sb = open(sys.argv[3], errors="replace").read().splitlines(), open(sys.argv[4], errors="replace").read().splitlines()
c = collections.Counter(x[4] for x in a if x[4] != "isa-debugcon")
d = sum(1 for i in range(min(len(a), len(b))) if a[i] != b[i]) + abs(len(a) - len(b))
d += sum(1 for i in range(min(len(sa), len(sb))) if sa[i] != sb[i]) + abs(len(sa) - len(sb))
cases = next(l for l in sa if l.startswith("CASES")).split()
print("CASES %s NONZERO %s DIFFS %04x ACCESSES %s" % (cases[1], cases[3], min(d, 0xffff),
      " ".join("%s=%d" % kv for kv in sorted(c.items()) if kv[0] != "isa-debug-exit")))
sys.exit(1 if d else 0)
