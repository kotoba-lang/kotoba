# Prefill oracle check (iteration 37): the prefill guest answers "<ns>|<x of all P rows>|<argmax of the last row>";
# decode_tokens_ref.py run with the same P forced tokens and NT = P gives xs[p] (the hidden state of token p
# after all layers) and argmaxes[P-1] -- the same math, so every row must match.
import re, sys, numpy as np
out = open(sys.argv[1]).read(); ref = np.load(sys.argv[2])
m = re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
if not m: print("TRAP:", out[:400].replace("\n", " ")); sys.exit(1)
ns, hx, hid = bytes.fromhex(m.group(1)).decode().split("|")[:3]
got = np.frombuffer(bytes.fromhex(hx), dtype=np.float32).astype(np.float64).reshape(-1, 2048)
tok = int(np.frombuffer(bytes.fromhex(hid), dtype=np.uint32)[0])
xs = ref["xs"]; am = ref["argmaxes"]; P = got.shape[0]
ok = True
for p in range(P):
    rel = np.max(np.abs(got[p] - xs[p])) / np.sqrt(np.mean(xs[p] ** 2)); ok = ok and rel < 1e-3
    print(f"row {p}: x rel {rel:.2e}")
print(f"argmax of the last row: gpu {tok} ref {int(am[P-1])} {'OK' if tok == int(am[P-1]) else 'MISMATCH'} ; prefill command buffer {int(ns)/1e6:.2f} ms for {P} tokens")
sys.exit(0 if ok and tok == int(am[P-1]) else 1)
