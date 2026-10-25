import re,sys,numpy as np
name=sys.argv[1]; out=open(sys.argv[2]).read()
m=re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
if not m: print(name, "TRAP:", out[:300].replace("\n"," ")); sys.exit(1)
txt=bytes.fromhex(m.group(1)).decode(); one,ten,hexo=txt.split("|")
got=np.frombuffer(bytes.fromhex(hexo),dtype=np.float32)
# name: one of the four Nex shorthands, or any GGUF tensor name (dots or underscores) whose kdot_ref.py output
# sits in the cwd; argv[3] = the tensor's bytes on the box (gen_kdot_guest prints it) for the GB/s column.
shorthand={'attn_qkv':'blk_0_attn_qkv_weight','attn_gate':'blk_0_attn_gate_weight','ffn_gate_exp0':'blk_0_ffn_gate_exps_weight','output':'output_weight'}
xname=shorthand.get(name, name.replace('.','_'))
ref=np.load(xname+'.ref.npy')
rel=np.max(np.abs(got-ref)/np.maximum(np.abs(ref),1e-2))
nbytes={'attn_qkv':11534336,'attn_gate':4456448,'ffn_gate_exp0':557056,'output':417177600}.get(name, int(sys.argv[3]) if len(sys.argv)>3 else 0)
gbs=f"{10*nbytes/int(ten):.1f} GB/s" if nbytes else "GB/s unmeasured (no byte count)"
import os
# int8 kernels (i8r8 / i8x8r4): also the error against the activation-quantized oracle (.refq.npy, kdot_ref.py) --
# a kernel that is exact on the quantized activation shows ~1e-5 here while `rel` shows the quantization (~1e-1)
q=f" ; vs quant_q8-activation oracle {np.max(np.abs(got-np.load(xname+'.refq.npy'))/np.maximum(np.abs(np.load(xname+'.refq.npy')),1e-2)):.2e}" if os.path.exists(xname+'.refq.npy') else ""
print(f"{name}: one dispatch {int(one)/1e6:.3f} ms, 10-in-one-buffer {int(ten)/1e6:.2f} ms -> {gbs} ; max rel err vs CPU dequant {rel:.2e}{q} ; got {got[:2]} ref {ref[:2]}")
# 8-question rule 4: a NaN row printed as "nan" is not a measurement -- exit red (tick 55; found by the Q5_0-vs-old-shader
# control). The threshold applies to the quantized-activation oracle when one exists (int8 kernels), else to `rel`.
relq=np.max(np.abs(got-np.load(xname+'.refq.npy'))/np.maximum(np.abs(np.load(xname+'.refq.npy')),1e-2)) if os.path.exists(xname+'.refq.npy') else rel
if not np.all(np.isfinite(got)): print(f"{name}: RED non-finite rows {int(np.sum(~np.isfinite(got)))} of {got.size}"); sys.exit(1)
if relq > 1e-3: print(f"{name}: RED max rel err {relq:.2e} > 1e-3"); sys.exit(1)
