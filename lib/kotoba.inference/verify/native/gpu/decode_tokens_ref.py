# f64 CPU reference (numpy) of a greedy multi-token decode -- a TEST ORACLE, not tooling.
# f64 CPU reference (numpy) of a GREEDY decode over T tokens through the first N
# layers of Nex-N2.5-mini, state carried (conv ring, delta-net S, KV cache) --
# a TEST ORACLE, not tooling. python3 decode_tokens_ref.py <gguf> <prompt-token> <layers> <tokens>
# -> decode_tokens_ref.npz: tokens (prompt + generated), x after the last layer per step, logits argmax per step
import sys, numpy as np, kdot_ref as g
import layer0_ref as L  # module-level code runs layer 0 once for argv; we only reuse its helpers
from decode_ref import deq_q6k_blocks, matq
path, NL, NT = sys.argv[1], int(sys.argv[3]), int(sys.argv[4])
prompt = [int(t) for t in sys.argv[2].split(",")]; tok0 = prompt[0]   # forced prompt tokens, then greedy (iteration 13)
# --sample T top_p seed: past the prompt draw with the device's rule (nex_sample_topp, iteration 18) instead of argmax
SAMPLE = None
if "--sample" in sys.argv:
    i = sys.argv.index("--sample"); SAMPLE = (float(sys.argv[i + 1]), float(sys.argv[i + 2]), int(sys.argv[i + 3], 0))
def mix32(x):
    x &= 0xFFFFFFFF; x ^= x >> 16; x = (x * 0x7FEB352D) & 0xFFFFFFFF; x ^= x >> 15; x = (x * 0x846CA68B) & 0xFFFFFFFF; x ^= x >> 16; return x
def sample_topp(logits, pos, T, topp, seed):
    z = logits / T; z = z - z.max(); p = np.exp(z); p /= p.sum()
    order = np.argsort(-p); cum = np.cumsum(p[order]); k = int(np.searchsorted(cum, topp)) + 1
    tau = p[order[k - 1]]; idx = np.nonzero(p >= tau)[0]; cp = np.cumsum(p[idx])
    u = (mix32(seed ^ ((pos * 0x9E3779B9) & 0xFFFFFFFF)) >> 8) / 16777216.0
    j = min(int(np.searchsorted(cp, u * cp[-1], side="right")), len(idx) - 1); return int(idx[j])
kv, T, mat, rows_of, rms, silu, sigmoid, softplus, l2 = L.kv, L.T, L.mat, L.rows_of, L.rms, L.silu, L.sigmoid, L.softplus, L.l2
NROT = kv["qwen35moe.rope.dimension_count"]; BASE = kv["qwen35moe.rope.freq_base"]; NH, NKV, HD = 16, 2, 256
interval = kv.get("qwen35moe.full_attention_interval", 4)
recurrent = [0 if (il + 1) % interval == 0 else 1 for il in range(64)]
W = {}
def M(n):
    if n not in W: W[n] = matq(n)
    return W[n]
def V(n): return mat(n)[0]
st = [({"ring": np.zeros((3, 8192)), "S": np.zeros((32, 128, 128))} if recurrent[il] else {"K": [], "V": []}) for il in range(NL)]
lm = None
def rope(v, heads, pos):
    o = v.copy(); half = NROT // 2
    for hh in range(heads):
        for i in range(half):
            th = pos * BASE ** (-2.0 * i / NROT); c, s_ = np.cos(th), np.sin(th)
            a, b = v[hh * HD + i], v[hh * HD + i + half]
            o[hh * HD + i] = a * c - b * s_; o[hh * HD + i + half] = a * s_ + b * c
    return o
tokens = [tok0]; xs = []; argmaxes = []; all_logits = []
for ti in range(NT):
    tok = tokens[-1]
    x = rows_of("token_embd.weight", tok, 1)[0]
    for il in range(NL):
        p = f"blk.{il}."
        h = rms(x, V(p + "attn_norm.weight"))
        if recurrent[il]:
            S0 = st[il]
            qkv = M(p + "attn_qkv.weight") @ h; z = M(p + "attn_gate.weight") @ h
            gg = softplus(M(p + "ssm_alpha.weight") @ h + V(p + "ssm_dt.bias")) * V(p + "ssm_a"); beta = sigmoid(M(p + "ssm_beta.weight") @ h)
            convW = M(p + "ssm_conv1d.weight")
            conv = silu(convW[:, 0] * S0["ring"][0] + convW[:, 1] * S0["ring"][1] + convW[:, 2] * S0["ring"][2] + convW[:, 3] * qkv)
            S0["ring"] = np.stack([S0["ring"][1], S0["ring"][2], qkv])
            qn = np.concatenate([l2(conv[hh * 128:(hh + 1) * 128], 1 / np.sqrt(128)) for hh in range(16)])
            kn = np.concatenate([l2(conv[2048 + hh * 128:2048 + (hh + 1) * 128]) for hh in range(16)])
            v = conv[4096:8192]; dn = np.zeros(4096)
            for hh in range(32):
                kh = hh % 16; S = S0["S"][hh]; S *= np.exp(gg[hh])
                delta = (v[hh * 128:(hh + 1) * 128] - kn[kh * 128:(kh + 1) * 128] @ S) * beta[hh]
                S += np.outer(kn[kh * 128:(kh + 1) * 128], delta); dn[hh * 128:(hh + 1) * 128] = qn[kh * 128:(kh + 1) * 128] @ S
            ssmNorm = V(p + "ssm_norm.weight")
            gnorm = np.concatenate([rms(dn[hh * 128:(hh + 1) * 128], ssmNorm) * silu(z[hh * 128:(hh + 1) * 128]) for hh in range(32)])
            attnOut = M(p + "ssm_out.weight") @ gnorm
        else:
            C = st[il]
            qFull = M(p + "attn_q.weight") @ h; kProj = M(p + "attn_k.weight") @ h; vProj = M(p + "attn_v.weight") @ h
            qnw = V(p + "attn_q_norm.weight"); knw = V(p + "attn_k_norm.weight")
            qNorm = np.concatenate([rms(qFull[hh * 2 * HD:hh * 2 * HD + HD], qnw) for hh in range(NH)])
            kNorm = np.concatenate([rms(kProj[hh * HD:(hh + 1) * HD], knw) for hh in range(NKV)])
            qR = rope(qNorm, NH, ti); kR = rope(kNorm, NKV, ti); C["K"].append(kR); C["V"].append(vProj.copy())
            attnO = np.zeros(NH * HD); Tn = len(C["K"])
            for hh in range(NH):
                hk = hh // (NH // NKV)
                sc = np.array([qR[hh * HD:(hh + 1) * HD] @ C["K"][tt][hk * HD:(hk + 1) * HD] / np.sqrt(HD) for tt in range(Tn)])
                ex = np.exp(sc - sc.max()); pr = ex / ex.sum()
                acc = sum(pr[tt] * C["V"][tt][hk * HD:(hk + 1) * HD] for tt in range(Tn))
                attnO[hh * HD:(hh + 1) * HD] = acc * sigmoid(qFull[hh * 2 * HD + HD:hh * 2 * HD + 2 * HD])
            attnOut = M(p + "attn_output.weight") @ attnO
        resid = x + attnOut; h2 = rms(resid, V(p + "post_attention_norm.weight"))
        router = M(p + "ffn_gate_inp.weight") @ h2
        pr = np.exp(router - router.max()); pr /= pr.sum()
        order = sorted(range(256), key=lambda i: (-pr[i], i))[:8]; wsum = sum(pr[i] for i in order)
        ffn = np.zeros(2048)
        for ex in order:
            Wg = rows_of(p + "ffn_gate_exps.weight", ex * 512, 512); Wu = rows_of(p + "ffn_up_exps.weight", ex * 512, 512); Wd = rows_of(p + "ffn_down_exps.weight", ex * 2048, 2048)
            ffn += (pr[ex] / wsum) * (Wd @ (silu(Wg @ h2) * (Wu @ h2)))
        sact = silu(M(p + "ffn_gate_shexp.weight") @ h2) * (M(p + "ffn_up_shexp.weight") @ h2)
        ffn += (M(p + "ffn_down_shexp.weight") @ sact) * sigmoid(float(V(p + "ffn_gate_inp_shexp.weight") @ h2))
        x = resid + ffn
    xs.append(x.copy())
    if lm is None: lm = matq("output.weight")
    logits = lm @ rms(x, V("output_norm.weight"))
    nxt = sample_topp(logits, ti, *SAMPLE) if SAMPLE else int(np.argmax(logits)); argmaxes.append(nxt); tokens.append(prompt[ti + 1] if ti + 1 < len(prompt) else nxt); all_logits.append(logits.astype(np.float32))
    print(f"step {ti} token {tok} -> argmax {nxt} (logit {logits[nxt]:.5f}) |x| {np.sqrt(np.mean(x*x)):.4g}")
np.savez("decode_tokens_ref.npz", tokens=np.array(tokens), xs=np.array(xs), argmaxes=np.array(argmaxes), layers=np.array([NL]), logits=np.array(all_logits))  # logits: for distribution parity (iteration 13)
