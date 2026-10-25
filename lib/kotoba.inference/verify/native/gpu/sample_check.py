# Oracle for sample_test.kotoba (iteration 18): the same top-p set and the same hash in numpy/f64.
# usage: python3 sample_check.py <loader output> <logits_last.f32> [T=0.8] [top_p=0.95] [seed=0x01234567]
import re, sys, numpy as np
out = open(sys.argv[1]).read()
m = re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
if not m: print("TRAP:", out[:400].replace("\n", " ")); sys.exit(1)
ns, hx = bytes.fromhex(m.group(1)).decode().split("|")
got = np.frombuffer(bytes.fromhex(hx), dtype=np.uint32)
lg = np.fromfile(sys.argv[2], dtype=np.float32).astype(np.float64)
T = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8; topp = float(sys.argv[4]) if len(sys.argv) > 4 else 0.95
seed = int(sys.argv[5], 0) if len(sys.argv) > 5 else 0x01234567
z = lg / T; z -= z.max(); p = np.exp(z); p /= p.sum()
order = np.argsort(-p); cum = np.cumsum(p[order]); k = int(np.searchsorted(cum, topp)) + 1   # smallest set with mass >= top_p
tau = p[order[k - 1]]; inset = p >= tau; mass = p[inset].sum()
def mix32(x):
    x &= 0xFFFFFFFF; x ^= x >> 16; x = (x * 0x7FEB352D) & 0xFFFFFFFF; x ^= x >> 15; x = (x * 0x846CA68B) & 0xFFFFFFFF; x ^= x >> 16; return x
idx = np.nonzero(inset)[0]; cp = np.cumsum(p[idx])
exact = []
for pos in range(len(got)):
    u = (mix32(seed ^ ((pos * 0x9E3779B9) & 0xFFFFFFFF)) >> 8) / 16777216.0
    j = int(np.searchsorted(cp, u * mass, side="right")); j = min(j, len(idx) - 1); exact.append(int(idx[j]))
exact = np.array(exact)
agree = int((got == exact).sum()); inside = int(inset[got].sum())
print(f"top-p set: {k} tokens, mass {mass:.4f}, tau {tau:.3e}; draws {len(got)}: exact-match {agree}/{len(got)}, inside the set {inside}/{len(got)}; last draw command buffer {int(ns)/1e6:.2f} ms")
# empirical vs exact over the set (total variation on the top tokens)
counts = np.bincount(got, minlength=len(p))[idx] / len(got); q = p[idx] / mass
print(f"empirical vs exact over the set: TV {0.5*np.abs(counts-q).sum():.3f} (256 draws; expected ~{0.5*np.sqrt(len(idx)/len(got))/2:.2f}), top-5 exact {[(int(idx[i]), round(float(q[i]),3)) for i in np.argsort(-q)[:5]]} empirical {[(int(idx[i]), round(float(counts[i]),3)) for i in np.argsort(-q)[:5]]}")
if agree < len(got) - 3 or inside < len(got): sys.exit(1)
