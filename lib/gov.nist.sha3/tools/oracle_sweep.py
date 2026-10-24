#!/usr/bin/env python3
"""Compare tools/sweep.cljk output with Python's hashlib. Standard library only."""
import hashlib
import sys

def msg(n):
    return bytes((i * 7 + 3) % 256 for i in range(n))

checked = bad = 0
for line in sys.stdin:
    fn, n, out, hexd = line.split()
    n, out = int(n), int(out)
    m = msg(n)
    if fn.startswith("sha3-"):
        want = getattr(hashlib, fn.replace("-", "_"))(m).hexdigest()
    elif fn == "shake128":
        want = hashlib.shake_128(m).hexdigest(out)
    else:
        want = hashlib.shake_256(m).hexdigest(out)
    checked += 1
    if want != hexd:
        bad += 1
        print("MISMATCH", fn, n, out)
print(f"{checked} lines compared, {bad} mismatches")
sys.exit(1 if bad else 0)
