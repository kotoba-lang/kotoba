# f64 CPU reference (numpy) of the decode step through N layers -- a TEST ORACLE, not tooling.
# f64 CPU reference of the Nex-N2.5-mini decode step for ONE token at position 0
# through the first N layers, then output norm, lm_head and argmax -- the numpy
# port (extended) of the retired Deno reference. A TEST ORACLE, not tooling.
# Usage: python3 decode_ref.py <gguf> <token-id> <layers>   -> x.f32, decode_ref.npz
import sys, numpy as np, kdot_ref as g
from layer0_ref import *  # noqa: reuses read/mat/rows_of/deq and the constants (runs layer 0 of token argv[2]; we redo below)
path, tok, NL = sys.argv[1], int(sys.argv[2].split(",")[0]), int(sys.argv[3])   # importers may pass a comma list of prompt tokens
NROT = kv["qwen35moe.rope.dimension_count"]; BASE = kv["qwen35moe.rope.freq_base"]; NH, NKV, HD = 16, 2, 256
def deq_q6k_blocks(raw):             # raw (N,210) for the lm_head
    ql = raw[:, 0:128].astype(np.int64); qh = raw[:, 128:192].astype(np.int64); sc = raw[:, 192:208].astype(np.int8).astype(np.int64)
    d = raw[:, 208:210].copy().view(np.float16).astype(np.float64)[:, 0]
    out = np.zeros((raw.shape[0], 256))
    for gi in range(2):
        qlg = ql[:, 64 * gi:64 * gi + 64]; qhg = qh[:, 32 * gi:32 * gi + 32]; scg = sc[:, 8 * gi:8 * gi + 8]
        for l in range(32):
            q1 = ((qlg[:, l] & 0xf) | (((qhg[:, l] >> 0) & 3) << 4)) - 32
            q2 = ((qlg[:, l + 32] & 0xf) | (((qhg[:, l] >> 2) & 3) << 4)) - 32
            q3 = ((qlg[:, l] >> 4) | (((qhg[:, l] >> 4) & 3) << 4)) - 32
            q4 = ((qlg[:, l + 32] >> 4) | (((qhg[:, l] >> 6) & 3) << 4)) - 32
            out[:, 128 * gi + l] = d * scg[:, l // 16] * q1; out[:, 128 * gi + 32 + l] = d * scg[:, 2 + l // 16] * q2
            out[:, 128 * gi + 64 + l] = d * scg[:, 4 + l // 16] * q3; out[:, 128 * gi + 96 + l] = d * scg[:, 6 + l // 16] * q4
    return out
def matq(name):
    raw, typ = read(name)
    if typ == 0: return raw
    _, _, _, dims = T[name]; cols = dims[0]; rows = int(np.prod(dims[1:]))
    return {23: deq_iq4xs_blocks, 13: deq_q5k_blocks, 14: deq_q6k_blocks}[typ](raw).reshape(rows, cols)
recurrent = kv["qwen35moe.attention.recurrent_layers"]
x = rows_of("token_embd.weight", tok, 1)[0]; x.astype(np.float32).tofile("x.f32")
xs = []
for il in range(NL):
    p = f"blk.{il}."
    h = rms(x, mat(p + "attn_norm.weight")[0])
    if recurrent[il]:
        qkv = matq(p + "attn_qkv.weight") @ h; z = matq(p + "attn_gate.weight") @ h
        alpha = matq(p + "ssm_alpha.weight") @ h; betaL = matq(p + "ssm_beta.weight") @ h
        gg = softplus(alpha + mat(p + "ssm_dt.bias")[0]) * mat(p + "ssm_a")[0]; beta = sigmoid(betaL)
        convW = mat(p + "ssm_conv1d.weight"); conv = silu(convW[:, 3] * qkv)   # ring is zero at position 0
        qn = np.concatenate([l2(conv[hh * 128:(hh + 1) * 128], 1 / np.sqrt(128)) for hh in range(16)])
        kn = np.concatenate([l2(conv[2048 + hh * 128:2048 + (hh + 1) * 128]) for hh in range(16)])
        v = conv[4096:8192]; dn = np.zeros(4096)
        for hh in range(32):
            kh = hh % 16; S = np.zeros((128, 128))           # fresh state at position 0
            delta = (v[hh * 128:(hh + 1) * 128] - kn[kh * 128:(kh + 1) * 128] @ S) * beta[hh]
            S += np.outer(kn[kh * 128:(kh + 1) * 128], delta); dn[hh * 128:(hh + 1) * 128] = qn[kh * 128:(kh + 1) * 128] @ S
        ssmNorm = mat(p + "ssm_norm.weight")[0]
        gnorm = np.concatenate([rms(dn[hh * 128:(hh + 1) * 128], ssmNorm) * silu(z[hh * 128:(hh + 1) * 128]) for hh in range(32)])
        attnOut = matq(p + "ssm_out.weight") @ gnorm
    else:
        qFull = matq(p + "attn_q.weight") @ h; kProj = matq(p + "attn_k.weight") @ h; vProj = matq(p + "attn_v.weight") @ h
        qnw = mat(p + "attn_q_norm.weight")[0]; knw = mat(p + "attn_k_norm.weight")[0]
        qNorm = np.concatenate([rms(qFull[hh * 2 * HD:hh * 2 * HD + HD], qnw) for hh in range(NH)])
        kNorm = np.concatenate([rms(kProj[hh * HD:(hh + 1) * HD], knw) for hh in range(NKV)])
        # position 0: rope is the identity (theta = 0)
        attnO = np.zeros(NH * HD)
        for hh in range(NH):
            hk = hh // (NH // NKV)   # T = 1: softmax over one position is 1
            attnO[hh * HD:(hh + 1) * HD] = vProj[hk * HD:(hk + 1) * HD] * sigmoid(qFull[hh * 2 * HD + HD:hh * 2 * HD + 2 * HD])
        attnOut = matq(p + "attn_output.weight") @ attnO
    resid = x + attnOut; h2 = rms(resid, mat(p + "post_attention_norm.weight")[0])
    router = mat(p + "ffn_gate_inp.weight") @ h2
    pr = np.exp(router - router.max()); pr /= pr.sum()
    order = sorted(range(256), key=lambda i: (-pr[i], i))[:8]; wsum = sum(pr[i] for i in order)
    ffn = np.zeros(2048)
    for e, ex in enumerate(order):
        Wg = rows_of(p + "ffn_gate_exps.weight", ex * 512, 512); Wu = rows_of(p + "ffn_up_exps.weight", ex * 512, 512); Wd = rows_of(p + "ffn_down_exps.weight", ex * 2048, 2048)
        act = silu(Wg @ h2) * (Wu @ h2); ffn += (pr[ex] / wsum) * (Wd @ act)
    sact = silu(matq(p + "ffn_gate_shexp.weight") @ h2) * (matq(p + "ffn_up_shexp.weight") @ h2)
    ffn += (matq(p + "ffn_down_shexp.weight") @ sact) * sigmoid(float(mat(p + "ffn_gate_inp_shexp.weight")[0] @ h2))
    x = resid + ffn; xs.append(x.copy())
    print(f"layer {il} {'recurrent' if recurrent[il] else 'attention'} top8 {order} |x| {np.sqrt(np.mean(x*x)):.5g}")
hN = rms(x, mat("output_norm.weight")[0])
logits = matq("output.weight") @ hN
top = np.argsort(-logits)[:5]
np.savez("decode_ref.npz", xs=np.array(xs), hN=hN, logits=logits, argmax=np.array([int(top[0])]), top5=top, layers=np.array([NL]))
print("argmax", int(top[0]), "top5", top.tolist(), "logit", logits[top[0]])
