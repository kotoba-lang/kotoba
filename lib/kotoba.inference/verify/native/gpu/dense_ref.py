# f64 CPU reference (numpy) of a greedy multi-token decode of a DENSE GGUF decoder -- a TEST ORACLE, not tooling.
# Architecture-generic sibling of decode_tokens_ref.py (which hardcodes Nex-N2.5-mini): every shape and hyper-parameter
# is read from the GGUF metadata (general.architecture = qwen2 | llama), every weight from the tensor directory.
#   python3 dense_ref.py <gguf> <prompt-ids,comma-separated> <layers> <steps> [--cache-gb G] [--rope norm|neox]
# Step ti feeds tokens[ti] (forced prompt while it lasts, then the previous argmax) through <layers> blocks, final norm
# and lm_head; prints the argmax per step and saves dense_ref.npz: tokens (prompt + generated), xs (x after the last block
# per step), argmaxes, logits (f64, per step). Generated tokens = steps - (len(prompt) - 1); the argmax of step
# len(prompt)-1 is the first continuation token (same convention as decode_tokens_ref.py).
# Dequant: Q5_K / Q6_K / IQ4_XS follow kdot_ref.py's layouts (vectorised here); Q8_0 / Q4_0 / Q4_1 / Q5_0 / Q5_1 / Q4_K / F16 / F32
# are local (a "Q4_K_M" file of a model whose n_embd is not a multiple of 256, e.g. Qwen2.5-0.5B's 896, is mostly Q5_0).
# RoPE: llama.cpp llama_rope_type -- LLM_ARCH_LLAMA -> LLAMA_ROPE_TYPE_NORM (interleaved pairs 2i,2i+1),
# LLM_ARCH_QWEN2 -> LLAMA_ROPE_TYPE_NEOX (half-split pairs i,i+n_rot/2). rope_freqs.weight (llama3 scaling factors
# precomputed by convert_hf_to_gguf) divides theta per pair when present, as ggml_rope_ext's freq_factors do.
import sys, time, numpy as np, kdot_ref as g
def refuse(msg): print("REFUSE", msg, file=sys.stderr, flush=True); sys.exit(2)   # 2 = could not answer (neither pass nor fail)

path = sys.argv[1]; prompt = [int(t) for t in sys.argv[2].split(",")]; NL = int(sys.argv[3]); NT = int(sys.argv[4])
CACHE_GB = float(sys.argv[sys.argv.index("--cache-gb") + 1]) if "--cache-gb" in sys.argv else 6.0
kv, tensors, ds = g.read_gguf_dir(path)
T = {t[0]: t for t in tensors}
f = open(path, "rb")
ARCH = kv["general.architecture"]
if ARCH not in ("qwen2", "llama"): refuse(f"unsupported general.architecture {ARCH!r} (this oracle knows qwen2, llama)")
def hp(k, default=None):
    v = kv.get(f"{ARCH}.{k}", default)
    if v is None: refuse(f"missing metadata {ARCH}.{k}")
    return v
NBLK = hp("block_count"); NE = hp("embedding_length"); NH = hp("attention.head_count"); NKV = hp("attention.head_count_kv", NH)
NFF = hp("feed_forward_length"); BASE = float(hp("rope.freq_base", 10000.0)); EPS = float(hp("attention.layer_norm_rms_epsilon", 1e-5))
HD = hp("attention.key_length", NE // NH); HDV = hp("attention.value_length", HD); NROT = hp("rope.dimension_count", HD)
ROPE_NEOX = (ARCH == "qwen2")            # llama.cpp llama_rope_type: QWEN2 -> NEOX, LLAMA -> NORM
if "--rope" in sys.argv:                 # negative-control override (norm|neox): the wrong type must break the llama.cpp match
    ROPE_NEOX = {"neox": True, "norm": False}[sys.argv[sys.argv.index("--rope") + 1]]; print("rope type OVERRIDDEN by --rope")
if NL > NBLK: refuse(f"layers {NL} > block_count {NBLK}")
print(f"arch {ARCH} blocks {NBLK} embd {NE} heads {NH} kv_heads {NKV} head_dim {HD} ffn {NFF} rope_base {BASE} n_rot {NROT} "
      f"rope {'neox' if ROPE_NEOX else 'norm'} eps {EPS} vocab {T['token_embd.weight'][3][1]}")

# ---- dequant (vectorised, raw (N, block_bytes) uint8 -> (N, block_values) f64) ----
KVB = g.KV.astype(np.float64)
def _f16(raw, a): return raw[:, a:a + 2].copy().view(np.float16).astype(np.float64)[:, 0]
def deq_f32(raw): return raw.copy().view(np.float32).astype(np.float64)
def deq_f16(raw): return raw.copy().view(np.float16).astype(np.float64)
def deq_q8_0(raw):                   # 34 B: f16 d, 32 x int8
    return _f16(raw, 0)[:, None] * raw[:, 2:34].copy().view(np.int8).astype(np.float64)
def deq_q4_0(raw):                   # 18 B: f16 d, 16 nibble bytes; value d*(q-8), low nibbles first
    d = _f16(raw, 0)[:, None]; q = raw[:, 2:18].astype(np.int64)
    return d * np.concatenate([(q & 0xf) - 8, (q >> 4) - 8], axis=1).astype(np.float64)
def deq_q4_1(raw):                   # 20 B: f16 d, f16 m, 16 nibble bytes; value d*q + m
    d = _f16(raw, 0)[:, None]; m = _f16(raw, 2)[:, None]; q = raw[:, 4:20].astype(np.int64)
    return d * np.concatenate([q & 0xf, q >> 4], axis=1).astype(np.float64) + m
def _q5_nibbles(qh, qs):             # 32 values: low nibbles | bit j of qh, then high nibbles | bit j+16 of qh
    j = np.arange(16)
    lo = (qs & 0xf) | (((qh[:, None] >> j) & 1) << 4); hi = (qs >> 4) | (((qh[:, None] >> (j + 16)) & 1) << 4)
    return np.concatenate([lo, hi], axis=1).astype(np.float64)
def deq_q5_0(raw):                   # 22 B: f16 d, u32 qh, 16 nibble bytes; value d*(q-16)
    d = _f16(raw, 0)[:, None]; qh = raw[:, 2:6].copy().view(np.uint32).astype(np.int64)[:, 0]; qs = raw[:, 6:22].astype(np.int64)
    return d * (_q5_nibbles(qh, qs) - 16)
def deq_q5_1(raw):                   # 24 B: f16 d, f16 m, u32 qh, 16 nibble bytes; value d*q + m
    d = _f16(raw, 0)[:, None]; m = _f16(raw, 2)[:, None]; qh = raw[:, 4:8].copy().view(np.uint32).astype(np.int64)[:, 0]; qs = raw[:, 8:24].astype(np.int64)
    return d * _q5_nibbles(qh, qs) + m
def q4k_scales(sc):
    scales = np.zeros((sc.shape[0], 8), np.int64); mins = np.zeros_like(scales)
    for j in range(8):
        if j < 4: scales[:, j] = sc[:, j] & 63; mins[:, j] = sc[:, j + 4] & 63
        else: scales[:, j] = (sc[:, j + 4] & 0xf) | ((sc[:, j - 4] >> 6) << 4); mins[:, j] = (sc[:, j + 4] >> 4) | ((sc[:, j] >> 6) << 4)
    return scales, mins
def deq_q4_k(raw):                   # 144 B: f16 d, f16 dmin, 12 B scales, 128 B nibbles
    d = _f16(raw, 0); dmin = _f16(raw, 2); scales, mins = q4k_scales(raw[:, 4:16].astype(np.int64)); qs = raw[:, 16:144].astype(np.int64)
    out = np.zeros((raw.shape[0], 256))
    for gi in range(4):
        lo = qs[:, 32 * gi:32 * gi + 32] & 0xf; hi = qs[:, 32 * gi:32 * gi + 32] >> 4; j0, j1 = 2 * gi, 2 * gi + 1
        out[:, 64 * gi:64 * gi + 32] = d[:, None] * scales[:, j0, None] * lo - dmin[:, None] * mins[:, j0, None]
        out[:, 64 * gi + 32:64 * gi + 64] = d[:, None] * scales[:, j1, None] * hi - dmin[:, None] * mins[:, j1, None]
    return out
def deq_q5_k(raw):                   # 176 B (kdot_ref.deq_q5k, vectorised)
    d = _f16(raw, 0); dmin = _f16(raw, 2); scales, mins = q4k_scales(raw[:, 4:16].astype(np.int64))
    qh = raw[:, 16:48].astype(np.int64); qs = raw[:, 48:176].astype(np.int64)
    out = np.zeros((raw.shape[0], 256))
    for gi in range(4):
        lo = qs[:, 32 * gi:32 * gi + 32] & 0xf; hi = qs[:, 32 * gi:32 * gi + 32] >> 4
        b_lo = ((qh >> (2 * gi)) & 1) << 4; b_hi = ((qh >> (2 * gi + 1)) & 1) << 4; j0, j1 = 2 * gi, 2 * gi + 1
        out[:, 64 * gi:64 * gi + 32] = d[:, None] * scales[:, j0, None] * (lo | b_lo) - dmin[:, None] * mins[:, j0, None]
        out[:, 64 * gi + 32:64 * gi + 64] = d[:, None] * scales[:, j1, None] * (hi | b_hi) - dmin[:, None] * mins[:, j1, None]
    return out
def deq_q6_k(raw):                   # 210 B (kdot_ref.deq_q6k, vectorised)
    ql = raw[:, 0:128].astype(np.int64); qh = raw[:, 128:192].astype(np.int64); sc = raw[:, 192:208].copy().view(np.int8).astype(np.int64)
    d = _f16(raw, 208); out = np.zeros((raw.shape[0], 256))
    for gi in range(2):
        qlg = ql[:, 64 * gi:64 * gi + 64]; qhg = qh[:, 32 * gi:32 * gi + 32]; scg = sc[:, 8 * gi:8 * gi + 8]
        for l in range(32):
            q1 = ((qlg[:, l] & 0xf) | (((qhg[:, l] >> 0) & 3) << 4)) - 32; q2 = ((qlg[:, l + 32] & 0xf) | (((qhg[:, l] >> 2) & 3) << 4)) - 32
            q3 = ((qlg[:, l] >> 4) | (((qhg[:, l] >> 4) & 3) << 4)) - 32; q4 = ((qlg[:, l + 32] >> 4) | (((qhg[:, l] >> 6) & 3) << 4)) - 32
            out[:, 128 * gi + l] = d * scg[:, l // 16] * q1; out[:, 128 * gi + 32 + l] = d * scg[:, 2 + l // 16] * q2
            out[:, 128 * gi + 64 + l] = d * scg[:, 4 + l // 16] * q3; out[:, 128 * gi + 96 + l] = d * scg[:, 6 + l // 16] * q4
    return out
def deq_iq4_xs(raw):                 # 136 B (kdot_ref.deq_iq4xs, vectorised)
    d = _f16(raw, 0); sh = raw[:, 2:4].copy().view(np.uint16).astype(np.int64)[:, 0]; sl = raw[:, 4:8].astype(np.int64); qs = raw[:, 8:136].astype(np.int64)
    out = np.zeros((raw.shape[0], 256))
    for ib in range(8):
        ls = ((sl[:, ib // 2] >> (4 * (ib % 2))) & 0xf) | (((sh >> (2 * ib)) & 3) << 4); dl = d * (ls - 32); q = qs[:, 16 * ib:16 * ib + 16]
        out[:, 32 * ib:32 * ib + 16] = dl[:, None] * KVB[q & 0xf]; out[:, 32 * ib + 16:32 * ib + 32] = dl[:, None] * KVB[q >> 4]
    return out
# ggml type id -> (block bytes, block values, dequant)
BLOCK = {0: (4, 1, deq_f32), 1: (2, 1, deq_f16), 2: (18, 32, deq_q4_0), 3: (20, 32, deq_q4_1), 6: (22, 32, deq_q5_0), 7: (24, 32, deq_q5_1),
         8: (34, 32, deq_q8_0), 12: (144, 256, deq_q4_k), 13: (176, 256, deq_q5_k), 14: (210, 256, deq_q6_k), 23: (136, 256, deq_iq4_xs)}
TYPE_NAME = {0: "F32", 1: "F16", 2: "Q4_0", 3: "Q4_1", 6: "Q5_0", 7: "Q5_1", 8: "Q8_0", 12: "Q4_K", 13: "Q5_K", 14: "Q6_K", 23: "IQ4_XS"}
def rows_of(name, r0, n):            # dequant rows r0..r0+n of a 2-D tensor (or the whole 1-D vector)
    _, typ, off, dims = T[name]; cols = dims[0]
    if typ not in BLOCK: refuse(f"tensor {name} has ggml type {typ} (known: {sorted(BLOCK)})")
    bb, bv, deq = BLOCK[typ]; nb = cols // bv; rowbytes = nb * bb
    f.seek(ds + off + r0 * rowbytes); raw = np.frombuffer(f.read(n * rowbytes), dtype=np.uint8).reshape(n * nb, bb)
    return deq(raw).reshape(n, cols)
def nrows(name): dims = T[name][3]; return int(np.prod(dims[1:])) if len(dims) > 1 else 1
def full(name): return rows_of(name, 0, nrows(name))
def V(name): return full(name)[0]

# ---- weight cache: everything in f64 when it fits the budget, else dequant on every use ----
params = sum(int(np.prod(t[3])) for t in tensors)
CACHE = params * 8 <= CACHE_GB * 2 ** 30
print(f"params {params} f64 {params * 8 / 2 ** 30:.2f} GiB -> {'cache all' if CACHE else 'dequant per use'} (budget {CACHE_GB} GiB); "
      f"types {sorted({TYPE_NAME.get(t[1], f'type{t[1]}') for t in tensors})}")
W = {}
def M(name):
    if not CACHE: return full(name)
    if name not in W: W[name] = full(name)
    return W[name]
TIED = "output.weight" not in T
print("lm_head", "tied to token_embd.weight" if TIED else "output.weight")
ROPE_FACTORS = V("rope_freqs.weight") if "rope_freqs.weight" in T else None
if ROPE_FACTORS is not None: print(f"rope_freqs.weight present ({len(ROPE_FACTORS)} factors, min {ROPE_FACTORS.min():.4g} max {ROPE_FACTORS.max():.4g})")

rms = lambda x, w: x / np.sqrt(np.mean(x * x) + EPS) * w
silu = lambda v: v / (1 + np.exp(-v))
INV_FREQ = BASE ** (-2.0 * np.arange(NROT // 2) / NROT)
if ROPE_FACTORS is not None: INV_FREQ = INV_FREQ / ROPE_FACTORS[:NROT // 2]
def rope(v, heads, hd, pos):         # v: heads*hd, rotates the first NROT dims of every head
    o = v.copy(); th = pos * INV_FREQ; c, s = np.cos(th), np.sin(th)
    for hh in range(heads):
        b = hh * hd
        if ROPE_NEOX:
            a1 = v[b:b + NROT // 2]; a2 = v[b + NROT // 2:b + NROT]
            o[b:b + NROT // 2] = a1 * c - a2 * s; o[b + NROT // 2:b + NROT] = a1 * s + a2 * c
        else:
            a1 = v[b:b + NROT:2]; a2 = v[b + 1:b + NROT:2]
            o[b:b + NROT:2] = a1 * c - a2 * s; o[b + 1:b + NROT:2] = a1 * s + a2 * c
    return o
def bias(name): return V(name) if name in T else 0.0

cache = [{"K": [], "V": []} for _ in range(NL)]
tokens = [prompt[0]]; xs = []; argmaxes = []; all_logits = []
t0 = time.time()
for ti in range(NT):
    tok = tokens[-1]
    x = rows_of("token_embd.weight", tok, 1)[0]
    for il in range(NL):
        p = f"blk.{il}."; C = cache[il]
        h = rms(x, V(p + "attn_norm.weight"))
        q = M(p + "attn_q.weight") @ h + bias(p + "attn_q.bias"); k = M(p + "attn_k.weight") @ h + bias(p + "attn_k.bias"); v = M(p + "attn_v.weight") @ h + bias(p + "attn_v.bias")
        q = rope(q, NH, HD, ti); k = rope(k, NKV, HD, ti); C["K"].append(k); C["V"].append(v)
        Ks = np.array(C["K"]).reshape(-1, NKV, HD); Vs = np.array(C["V"]).reshape(-1, NKV, HDV)   # (T, NKV, HD)
        attnO = np.zeros(NH * HDV)
        for hh in range(NH):
            hk = hh // (NH // NKV)
            sc = Ks[:, hk, :] @ q[hh * HD:(hh + 1) * HD] / np.sqrt(HD)
            ex = np.exp(sc - sc.max()); pr = ex / ex.sum()
            attnO[hh * HDV:(hh + 1) * HDV] = pr @ Vs[:, hk, :]
        x = x + M(p + "attn_output.weight") @ attnO
        h2 = rms(x, V(p + "ffn_norm.weight"))
        x = x + M(p + "ffn_down.weight") @ (silu(M(p + "ffn_gate.weight") @ h2) * (M(p + "ffn_up.weight") @ h2))
    xs.append(x.copy())
    logits = M("token_embd.weight" if TIED else "output.weight") @ rms(x, V("output_norm.weight"))
    nxt = int(np.argmax(logits)); argmaxes.append(nxt); all_logits.append(logits)
    tokens.append(prompt[ti + 1] if ti + 1 < len(prompt) else nxt)
    kind = "prompt" if ti + 1 < len(prompt) else "generated"
    print(f"step {ti} token {tok} -> argmax {nxt} (logit {logits[nxt]:.5f}) |x| {np.sqrt(np.mean(x * x)):.4g} next={kind} {time.time() - t0:.1f}s", flush=True)
print(f"prompt {prompt} continuation {tokens[len(prompt):]} wall {time.time() - t0:.2f}s")
np.savez("dense_ref.npz", tokens=np.array(tokens), xs=np.array(xs), argmaxes=np.array(argmaxes), layers=np.array([NL]), logits=np.array(all_logits), prompt=np.array(prompt))
