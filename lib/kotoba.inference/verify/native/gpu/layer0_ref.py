# f64 CPU reference (numpy) -- a TEST ORACLE, not tooling (AGENTS.md kbb-first is for tooling); imports kdot_ref for the GGUF directory and codebook.
# f64 CPU reference of ONE recurrent (gated delta-net) layer of Nex-N2.5-mini for
# one token at position 0 -- the numpy port of verify/nex_layer0_reference.js
# (Deno, retired). Writes x.f32 (the token's embedding row, MAPped by the guest)
# and layer0_ref.npz with every intermediate. Usage: python3 layer0_ref.py <gguf> <token-id> <layer>
import sys, struct, numpy as np, kdot_ref as g
path, tok, il = sys.argv[1], int(sys.argv[2].split(",")[0]), int(sys.argv[3])   # importers may pass a comma list of prompt tokens
kv, tensors, ds = g.read_gguf_dir(path)
T = {t[0]: t for t in tensors}
f = open(path, 'rb')
KV = g.KV
def read(name):
    _, typ, off, dims = T[name]; cols = dims[0]; rows = int(np.prod(dims[1:])) if len(dims) > 1 else 1
    if typ == 0:
        f.seek(ds + off); return np.frombuffer(f.read(rows * cols * 4), dtype=np.float32).reshape(rows, cols).astype(np.float64), typ
    bb = g.BLOCK[typ][0]; nb = cols // 256
    f.seek(ds + off); raw = np.frombuffer(f.read(rows * nb * bb), dtype=np.uint8).reshape(rows * nb, bb)
    return raw, typ
def deq_iq4xs_blocks(raw):           # raw (N,136) -> (N,256) f64, vectorised
    d = raw[:, 0:2].copy().view(np.float16).astype(np.float64)[:, 0]
    sh = raw[:, 2:4].copy().view(np.uint16).astype(np.int64)[:, 0]
    sl = raw[:, 4:8].astype(np.int64); qs = raw[:, 8:136].astype(np.int64)
    out = np.zeros((raw.shape[0], 256))
    for ib in range(8):
        ls = ((sl[:, ib // 2] >> (4 * (ib % 2))) & 0xf) | (((sh >> (2 * ib)) & 3) << 4)
        dl = d * (ls - 32)
        q = qs[:, 16 * ib:16 * ib + 16]
        out[:, 32 * ib:32 * ib + 16] = dl[:, None] * KV[q & 0xf]; out[:, 32 * ib + 16:32 * ib + 32] = dl[:, None] * KV[q >> 4]
    return out
def deq_q5k_blocks(raw):             # raw (N,176)
    d = raw[:, 0:2].copy().view(np.float16).astype(np.float64)[:, 0]; dmin = raw[:, 2:4].copy().view(np.float16).astype(np.float64)[:, 0]
    sc = raw[:, 4:16].astype(np.int64); qh = raw[:, 16:48].astype(np.int64); qs = raw[:, 48:176].astype(np.int64)
    scales = np.zeros((raw.shape[0], 8), np.int64); mins = np.zeros_like(scales)
    for j in range(8):
        if j < 4: scales[:, j] = sc[:, j] & 63; mins[:, j] = sc[:, j + 4] & 63
        else: scales[:, j] = (sc[:, j + 4] & 0xf) | ((sc[:, j - 4] >> 6) << 4); mins[:, j] = (sc[:, j + 4] >> 4) | ((sc[:, j] >> 6) << 4)
    out = np.zeros((raw.shape[0], 256))
    for gi in range(4):
        lo = qs[:, 32 * gi:32 * gi + 32] & 0xf; hi = qs[:, 32 * gi:32 * gi + 32] >> 4
        b_lo = ((qh >> (2 * gi)) & 1) << 4; b_hi = ((qh >> (2 * gi + 1)) & 1) << 4
        j0, j1 = 2 * gi, 2 * gi + 1
        out[:, 64 * gi:64 * gi + 32] = d[:, None] * scales[:, j0, None] * (lo | b_lo) - dmin[:, None] * mins[:, j0, None]
        out[:, 64 * gi + 32:64 * gi + 64] = d[:, None] * scales[:, j1, None] * (hi | b_hi) - dmin[:, None] * mins[:, j1, None]
    return out
def mat(name):
    raw, typ = read(name)
    if typ == 0: return raw
    _, _, _, dims = T[name]; cols = dims[0]; rows = int(np.prod(dims[1:]))
    blocks = {23: deq_iq4xs_blocks, 13: deq_q5k_blocks}[typ](raw)
    return blocks.reshape(rows, cols)
def rows_of(name, r0, n):            # dequant only rows r0..r0+n of a quantized matrix
    _, typ, off, dims = T[name]; cols = dims[0]; bb = g.BLOCK[typ][0]; nb = cols // 256
    f.seek(ds + off + r0 * nb * bb); raw = np.frombuffer(f.read(n * nb * bb), dtype=np.uint8).reshape(n * nb, bb)
    return {23: deq_iq4xs_blocks, 13: deq_q5k_blocks}[typ](raw).reshape(n, cols)
EPS = kv["qwen35moe.attention.layer_norm_rms_epsilon"]
rms = lambda x, w: x / np.sqrt(np.mean(x * x) + EPS) * w
silu = lambda v: v / (1 + np.exp(-v)); sigmoid = lambda v: 1 / (1 + np.exp(-v)); softplus = lambda v: np.where(v > 20, v, np.log1p(np.exp(v)))
l2 = lambda v, scale=1.0: v * (scale / np.sqrt(np.sum(v * v) + EPS))
# the one-layer run below is the script; importers (decode_ref, decode_tokens_ref) want only the helpers above
if __name__ != "__main__": il = 0
p = f"blk.{il}."
x = rows_of("token_embd.weight", tok, 1)[0]
x.astype(np.float32).tofile("x.f32")
h = rms(x, mat(p + "attn_norm.weight")[0])
qkv = mat(p + "attn_qkv.weight") @ h; z = mat(p + "attn_gate.weight") @ h
alpha = mat(p + "ssm_alpha.weight") @ h; betaL = mat(p + "ssm_beta.weight") @ h
dt = mat(p + "ssm_dt.bias")[0]; ssmA = mat(p + "ssm_a")[0]
gg = softplus(alpha + dt) * ssmA; beta = sigmoid(betaL)
convW = mat(p + "ssm_conv1d.weight")        # (8192, 4) channel-major
ring = np.zeros((3, 8192))
conv = silu(convW[:, 0] * ring[0] + convW[:, 1] * ring[1] + convW[:, 2] * ring[2] + convW[:, 3] * qkv)
KD, VD = 2048, 4096
qn = np.concatenate([l2(conv[hh * 128:(hh + 1) * 128], 1 / np.sqrt(128)) for hh in range(16)])
kn = np.concatenate([l2(conv[KD + hh * 128:KD + (hh + 1) * 128]) for hh in range(16)])
v = conv[2 * KD:2 * KD + VD]
S = np.zeros((32, 128, 128)); dn = np.zeros(VD)
for hh in range(32):
    kh = hh % 16; S[hh] *= np.exp(gg[hh]); kvm = kn[kh * 128:(kh + 1) * 128] @ S[hh]
    delta = (v[hh * 128:(hh + 1) * 128] - kvm) * beta[hh]
    S[hh] += np.outer(kn[kh * 128:(kh + 1) * 128], delta); dn[hh * 128:(hh + 1) * 128] = qn[kh * 128:(kh + 1) * 128] @ S[hh]
ssmNorm = mat(p + "ssm_norm.weight")[0]
gnorm = np.concatenate([rms(dn[hh * 128:(hh + 1) * 128], ssmNorm) * silu(z[hh * 128:(hh + 1) * 128]) for hh in range(32)])
attnOut = mat(p + "ssm_out.weight") @ gnorm
resid = x + attnOut; h2 = rms(resid, mat(p + "post_attention_norm.weight")[0])
router = mat(p + "ffn_gate_inp.weight") @ h2
pr = np.exp(router - router.max()); pr /= pr.sum()
order = sorted(range(256), key=lambda i: (-pr[i], i))[:8]; wsum = sum(pr[i] for i in order)
topW = np.array([pr[i] / wsum for i in order])
ffn = np.zeros(2048); gateE = np.zeros((8, 512)); actE = np.zeros((8, 512)); downE = np.zeros((8, 2048))
for e, ex in enumerate(order):
    Wg = rows_of(p + "ffn_gate_exps.weight", ex * 512, 512); Wu = rows_of(p + "ffn_up_exps.weight", ex * 512, 512); Wd = rows_of(p + "ffn_down_exps.weight", ex * 2048, 2048)
    gateE[e] = Wg @ h2; actE[e] = silu(gateE[e]) * (Wu @ h2); downE[e] = Wd @ actE[e]; ffn += topW[e] * downE[e]
sg = mat(p + "ffn_gate_shexp.weight") @ h2; su = mat(p + "ffn_up_shexp.weight") @ h2; sact = silu(sg) * su
shDown = mat(p + "ffn_down_shexp.weight") @ sact
shLogit = float(mat(p + "ffn_gate_inp_shexp.weight")[0] @ h2)
ffn += shDown * sigmoid(shLogit)
xout = resid + ffn
np.savez("layer0_ref.npz", x=x, h=h, qkv=qkv, z=z, alpha=alpha, betaL=betaL, g=gg, beta=beta, conv=conv, qn=qn, kn=kn, dn=dn, gnorm=gnorm, attnOut=attnOut, resid=resid, h2=h2, router=router, topIds=np.array(order), topW=topW, gateE=gateE, actE=actE, downE=downE, sact=sact, shDown=shDown, shLogit=np.array([shLogit]), ffn=ffn, xout=xout)
print("token", tok, "layer", il, "topIds", order, "xout[:4]", xout[:4], "|xout|", np.sqrt(np.mean(xout ** 2)))
