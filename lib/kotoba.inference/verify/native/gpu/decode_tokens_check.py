import re,sys,numpy as np
out=open(sys.argv[1]).read()
m=re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
if not m: print("TRAP:", out[:400].replace("\n"," ")); sys.exit(1)
ref=np.load("decode_tokens_ref.npz"); toks=ref["tokens"]; xs=ref["xs"]; am=ref["argmaxes"]
ok=True
for i,part in enumerate(bytes.fromhex(m.group(1)).decode().split("#")):
    ns,hx,hid=part.split("|")[:3]   # fn-mode guests append the final logits as a 4th field of the last part
    got=np.frombuffer(bytes.fromhex(hx),dtype=np.float32).astype(np.float64); tok=int(np.frombuffer(bytes.fromhex(hid),dtype=np.uint32)[0])
    r=xs[i]; got=got[:len(r)]   # dense rows (896) sit at the front of the 2048-wide shared buffer (tick 57)
    rel=np.max(np.abs(got-r))/np.sqrt(np.mean(r*r))
    ok = ok and tok==int(am[i])
    print(f"step {i}: in {int(toks[i])} -> argmax gpu {tok} ref {int(am[i])} {'OK' if tok==int(am[i]) else 'MISMATCH'} ; x rel {rel:.2e} ; command buffer {int(ns)/1e6:.2f} ms")
print("greedy chain", "OK" if ok else "FAIL")
