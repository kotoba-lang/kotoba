# Turn a FLAT token-loop guest (gen_decode_tokens_guest.cljk ... <backend> flat, one token) into a
# profiling guest: every dispatch runs alone in its own command buffer and its SUBMIT time is
# collected, so a layer's cost can be ranked per op (iteration 22). Each timing carries the
# single-submit floor (~0.07 ms on Xavier, measured with the embed dispatch), so ranks are
# meaningful and sums are not -- the in-buffer layer is ~40% cheaper than the sum.
# usage: python3 profile_guest.py <flat.kotoba> <out.kotoba> <out.labels>
#        ... compile / run as usual, then: python3 profile_guest.py --report <loader output> <labels> <layers>
import re, sys, numpy as np
REC = ['rmsnorm','qkv 8192x2048 Q5_K','gate 4096x2048 IQ4_XS','alpha 32','beta 32','gate_decay2','gate_decay2 (beta)','conv1d','l2norm q','l2norm k','deltanet','gated_rmsnorm','ssm_out 2048x4096','add_rmsnorm','router f32','gate_sh 512','up_sh 512','shlogit','softmax_topk','silu_sh','gate_exps 512x8','up_exps 512x8','down_sh 2048','silu8','down_exps 2048x8','weighted_sum','add']
REC_FUSED = ['rmsnorm','qkv 8192x2048 Q5_K','gate 4096x2048 IQ4_XS','alpha 32','beta 32','deltanet_fused','ssm_out 2048x4096','add_rmsnorm','router f32','gate_sh 512','up_sh 512','shlogit','softmax_topk','silu_sh','gate_exps 512x8','up_exps 512x8','down_sh 2048','silu8','down_exps 2048x8','weighted_sum','add']
ATT = ['rmsnorm','q 8192x2048','k 512','v 512','rmsnorm q','rmsnorm k','rope q','rope k','copy v','copy k','attn_decode','attn_out 2048x4096','add_rmsnorm','router f32','gate_sh 512','up_sh 512','shlogit','softmax_topk','silu_sh','gate_exps 512x8','up_exps 512x8','down_sh 2048','silu8','down_exps 2048x8','weighted_sum','add']
if sys.argv[1] == '--report':
    out = open(sys.argv[2]).read(); labels = open(sys.argv[3]).read().split('\n'); layers = int(sys.argv[4])
    m = re.search(r':result-utf8-hex "([0-9a-f]+)"', out)
    if not m: print('TRAP:', out[:300]); sys.exit(1)
    t = np.array([int(x) / 1e6 for x in bytes.fromhex(m.group(1)).decode().split('|')[1:]])
    print(f'embed {t[0]:.3f} ms (the single-submit floor is about this)'); pos = 1
    for il in range(layers):
        rec = (il + 1) % 4 != 0; names = (REC_FUSED if 'deltanet_fused' in labels else REC) if rec else ATT; n = len(names)
        seg = t[pos:pos + n]; pos += n
        print(f'layer {il} ({"recurrent" if rec else "attention"}) sum {seg.sum():.2f} ms alone-in-submit')
        for nm, v in sorted(zip(names, seg), key=lambda x: -x[1])[:10]: print(f'   {nm:<24s} {v:.3f}')
    print('tail:', ' '.join(f'{l} {v:.2f}' for l, v in zip(labels[pos:], t[pos:])))
    sys.exit(0)
src = open(sys.argv[1]).read()
pipes = re.findall(r'PIPELINE /root/kgpu/([a-z0-9_]+)\.spv', src); names = {str(i + 1): n for i, n in enumerate(pipes)}
head, body = src.split('(gpu "BEGIN")', 1)
reqs, labels = [], []
for ln in body.split('\n'):
    m = re.match(r'\s*\(gpu "(DISPATCHC?) (\d+) ([^"]*)"\)', ln)
    if m: reqs.append(f'DISPATCH {m.group(2)} {m.group(3)}'); labels.append(names[m.group(2)])
G = 16   # nesting depth the desugarer accepts comfortably (112 nested lets exhausted its stack)
fns = '(defn timed [req :string acc :string] :string\n  (do (gpu "BEGIN") (gpu req) (string-concat acc (string-concat "|" (gpu "SUBMIT")))))\n'
groups = [reqs[i:i + G] for i in range(0, len(reqs), G)]
for gi, g in enumerate(groups):
    expr = 'acc'
    for r in g: expr = f'(timed "{r}" {expr})'
    fns += f'(defn g{gi} [acc :string] :string\n  {expr})\n'
call = '""'
for gi in range(len(groups)): call = f'(g{gi} {call})'
mi = head.index('(defn main [] :string')
open(sys.argv[2], 'w').write(head[:mi] + fns + head[mi:].rstrip() + '\n      ' + call + '))\n')
open(sys.argv[3], 'w').write('\n'.join(labels))
print(len(reqs), 'dispatches in', len(groups), 'groups')
