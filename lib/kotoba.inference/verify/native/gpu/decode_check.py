import re,sys,numpy as np
out=open(sys.argv[1]).read()
m=re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
if not m: print("TRAP:", out[:400].replace("\n"," ")); sys.exit(1)
ns,hx,hid,hlog=bytes.fromhex(m.group(1)).decode().split("|")
got=np.frombuffer(bytes.fromhex(hx),dtype=np.float32).astype(np.float64)
tok=int(np.frombuffer(bytes.fromhex(hid),dtype=np.uint32)[0]); mx=float(np.frombuffer(bytes.fromhex(hlog),dtype=np.float32)[0])
ref=np.load("decode_ref.npz"); r=ref["xs"][-1]
rms=np.sqrt(np.mean(r*r)); maxabs=np.max(np.abs(got-r))
print(f"decode {int(ref['layers'][0])} layers + lm_head: command buffer {int(ns)/1e6:.2f} ms ; x rel {maxabs/rms:.2e} ; argmax gpu {tok} (logit {mx:.5f}) ref {int(ref['argmax'][0])} (logit {ref['logits'][ref['argmax'][0]]:.5f}) top5 ref {ref['top5'].tolist()}")
