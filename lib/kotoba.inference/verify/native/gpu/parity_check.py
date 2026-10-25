# Distribution parity of the native :gpu/compute decode against the f64 oracle and llama-server (iteration 14).
# usage: python3 parity_check.py <loader output> <decode_tokens_ref.npz> [llama /completion json with n_probs]
# (tick 58: the llama-server json is optional -- without it the check is oracle-only, e.g. the h2 dense layout on Xavier)
# The guest (stream mode) answers its LAST token as "ns|x hex|argmax hex|logits hex"; the oracle's logits[-1]
# and llama-server's top_logprobs are the two references. Prints KL(ref||gpu) over the reference's support,
# top-1 / top-10 agreement and the argmax chain; exit 1 on a trap or a broken answer.
import re, sys, json, math, numpy as np
out = open(sys.argv[1]).read()
m = re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
if not m: print("TRAP:", out[:400].replace("\n", " ")); sys.exit(1)
parts = bytes.fromhex(m.group(1)).decode().split("#")
ref = np.load(sys.argv[2]); toks = ref["tokens"]; am = ref["argmaxes"]; xs = ref["xs"]
for i, part in enumerate(parts):
    f = part.split("|"); ns, hx, hid = f[0], f[1], f[2]
    got = np.frombuffer(bytes.fromhex(hx), dtype=np.float32).astype(np.float64); tok = int(np.frombuffer(bytes.fromhex(hid), dtype=np.uint32)[0])
    r = xs[i]; got = got[:len(r)]; rel = np.max(np.abs(got - r)) / np.sqrt(np.mean(r * r))   # dense rows sit at the front of the 2048-wide buffer
    print(f"step {i}: in {int(toks[i])} -> argmax gpu {tok} ref {int(am[i])} {'OK' if tok == int(am[i]) else 'MISMATCH'} ; x rel {rel:.2e} ; lm_head command buffer {int(ns)/1e6:.2f} ms")
last = parts[-1].split("|")
if len(last) < 4: print("no logits in the last answer (not a stream guest?)"); sys.exit(1)
lg = np.frombuffer(bytes.fromhex(last[3]), dtype=np.float32).astype(np.float64)
def softmax(v): z = v - v.max(); e = np.exp(z); return e / e.sum()
pg = softmax(lg); po = softmax(ref["logits"][-1].astype(np.float64))
print(f"logits: gpu vs oracle max|diff| {np.max(np.abs(lg - ref['logits'][-1])):.3e}, KL(oracle||gpu) {float(np.sum(po * (np.log(po + 1e-30) - np.log(pg + 1e-30)))):.3e} nats, top-1 gpu {int(pg.argmax())} oracle {int(po.argmax())}")
if len(sys.argv) < 4: sys.exit(0 if int(pg.argmax()) == int(po.argmax()) else 1)   # oracle-only: red when the top-1 differs
d = json.load(open(sys.argv[3])); cp = d["completion_probabilities"][0]
lp = {p["id"]: p["logprob"] for p in cp["top_logprobs"]}
ids = sorted(lp, key=lambda i: -lp[i])
kl = sum(math.exp(lp[i]) * (lp[i] - math.log(pg[i] + 1e-30)) for i in ids)
top10_g = [int(i) for i in np.argsort(-pg)[:10]]
print(f"llama.cpp top-1 {ids[0]} p {math.exp(lp[ids[0]]):.3f} | gpu top-1 {top10_g[0]} p {pg[top10_g[0]]:.3f} | KL(llama||gpu) over llama's top-{len(ids)} {kl:.4f} nats | llama mass on its top-{len(ids)} {sum(math.exp(v) for v in lp.values()):.3f}, gpu mass on those {float(sum(pg[i] for i in ids)):.3f} | gpu top-10 in llama top-{len(ids)}: {sum(i in lp for i in top10_g)}/10")
print("llama top-10:", [(i, round(math.exp(lp[i]), 4)) for i in ids[:10]])
print("gpu   top-10:", [(i, round(float(pg[i]), 4)) for i in top10_g])
