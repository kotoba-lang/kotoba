import re,sys,numpy as np
out=open(sys.argv[1]).read()
m=re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
if not m: print("TRAP:", out[:400].replace("\n"," ")); sys.exit(1)
ref=np.load("layer0_ref.npz")
def ref_dbg(nm):
  k={"h":"h","qkv":"qkv","gb":"g","conv":"conv","dn":"dn","resid":"resid","router":"router","topw":"topW"}[nm]; return ref[k].ravel()[:4]
parts=bytes.fromhex(m.group(1)).decode().split("|"); ns,hx,hids=parts[:3]
for nm,hh in zip(["h","qkv","gb","conv","dn","resid","router","topw"], parts[3:]): print("  dbg", nm, np.frombuffer(bytes.fromhex(hh),dtype=np.float32), "ref", ref_dbg(nm))
got=np.frombuffer(bytes.fromhex(hx),dtype=np.float32).astype(np.float64)
ids=np.frombuffer(bytes.fromhex(hids),dtype=np.uint32)
ref=np.load("layer0_ref.npz")
def ref_dbg(nm):
  k={"h":"h","qkv":"qkv","gb":"g","conv":"conv","dn":"dn","resid":"resid","router":"router","topw":"topW"}[nm]; return ref[k].ravel()[:4]
r=ref["xout"]
rms=np.sqrt(np.mean(r*r)); maxabs=np.max(np.abs(got-r)); wi=int(np.argmax(np.abs(got-r)))
print(f"layer0: command buffer {int(ns)/1e6:.2f} ms ; topIds gpu {ids.tolist()} ref {ref['topIds'].tolist()} ; xout maxAbs {maxabs:.3e} refRms {rms:.3e} rel {maxabs/rms:.2e} at {wi}: ref {r[wi]:.6g} gpu {got[wi]:.6g}")
