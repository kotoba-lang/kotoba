// f64 CPU reference of Nex layer 0 (a linear-attention + MoE block) on one token, from dequantised
// GGUF weights, compared stage by stage with the GPU dump of verify/nex_decode_step.js
// (NEX_DEBUG_LAYERS=1 NEX_DEBUG_JSON=...). Locates which stage diverges.
//   deno run --allow-read verify/nex_layer0_reference.js <model.gguf> <token id> <gpu dump json>
const [modelPath, tokArg, dumpPath] = Deno.args; const TOK = Number(tokArg);
const gpu = JSON.parse(await Deno.readTextFile(dumpPath));
const file = await Deno.open(modelPath, {read: true});
async function readAt(off, len) { const out = new Uint8Array(len); let got = 0; await file.seek(off, Deno.SeekMode.Start); while (got < len) { const n = await file.read(out.subarray(got)); if (n === null) throw new Error("eof"); got += n; } return out; }
// --- header (same parser as the harness) ---
const head = await readAt(0, 96 * 1024 * 1024); const hv = new DataView(head.buffer); let pos = 0;
const u32 = () => { const v = hv.getUint32(pos, true); pos += 4; return v; }; const u64 = () => { const v = Number(hv.getBigUint64(pos, true)); pos += 8; return v; };
const gstr = () => { const n = u64(); const s = new TextDecoder().decode(head.subarray(pos, pos + n)); pos += n; return s; };
const SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8};
function readValue(t) { if (t === 8) return gstr(); if (t === 9) { const et = u32(), n = u64(); if (n > 4096) { if (et === 8) { for (let i = 0; i < n; i++) { const l = u64(); pos += l; } } else pos += n * SZ[et]; return {skipped: n}; } const arr = []; for (let i = 0; i < n; i++) arr.push(readValue(et)); return arr; } let v; switch (t) { case 0: v = hv.getUint8(pos); break; case 1: v = hv.getInt8(pos); break; case 2: v = hv.getUint16(pos, true); break; case 3: v = hv.getInt16(pos, true); break; case 4: v = hv.getUint32(pos, true); break; case 5: v = hv.getInt32(pos, true); break; case 6: v = hv.getFloat32(pos, true); break; case 7: v = hv.getUint8(pos) !== 0; break; case 10: v = Number(hv.getBigUint64(pos, true)); break; case 11: v = Number(hv.getBigInt64(pos, true)); break; case 12: v = hv.getFloat64(pos, true); break; } pos += SZ[t]; return v; }
pos = 4; u32(); const nT = u64(), nKv = u64(); const kv = {}; for (let i = 0; i < nKv; i++) { const k = gstr(); const t = u32(); kv[k] = readValue(t); }
const tensors = {}; for (let i = 0; i < nT; i++) { const name = gstr(); const nd = u32(); const dims = []; for (let d = 0; d < nd; d++) dims.push(u64()); const type = u32(); const off = u64(); tensors[name] = {dims, type, off}; }
const dataOff = Math.ceil(pos / 32) * 32; const EPS = kv["qwen35moe.attention.layer_norm_rms_epsilon"];
const BB = {12: 144, 13: 176, 14: 210, 23: 136, 0: 4};
// --- dequant ---
const f16 = (u) => { const s = (u >> 15) & 1, e = (u >> 10) & 31, m = u & 1023; if (e === 0) return (s ? -1 : 1) * m * 2 ** -24; if (e === 31) return m ? NaN : (s ? -Infinity : Infinity); return (s ? -1 : 1) * (1 + m / 1024) * 2 ** (e - 15); };
const KV4 = [-127, -104, -83, -65, -49, -35, -22, -10, 1, 13, 25, 38, 53, 69, 89, 113];
function deqRow(raw, o, type, n) {
  const out = new Float64Array(n), dv = new DataView(raw.buffer, raw.byteOffset);
  if (type === 0) { for (let i = 0; i < n; i++) out[i] = dv.getFloat32(o + i * 4, true); return out; }
  const nb = n / 256;
  for (let b = 0; b < nb; b++) {
    const bo = o + b * BB[type];
    if (type === 23) { const d = f16(dv.getUint16(bo, true)), sh = dv.getUint16(bo + 2, true); for (let ib = 0; ib < 8; ib++) { const ls = ((raw[bo + 4 + (ib >> 1)] >> (4 * (ib & 1))) & 0xf) | (((sh >> (2 * ib)) & 3) << 4); const dl = d * (ls - 32); for (let j = 0; j < 16; j++) { const q = raw[bo + 8 + ib * 16 + j]; out[b * 256 + ib * 32 + j] = dl * KV4[q & 0xf]; out[b * 256 + ib * 32 + 16 + j] = dl * KV4[q >> 4]; } } }
    else if (type === 13) { const d = f16(dv.getUint16(bo, true)), dmin = f16(dv.getUint16(bo + 2, true)); const sc = raw.subarray(bo + 4, bo + 16), qh = raw.subarray(bo + 16, bo + 48), qs = raw.subarray(bo + 48, bo + 176);
      let is = 0, u1 = 1, u2 = 2, qo = 0, y = 0; for (let j = 0; j < 256; j += 64) { const [sc1, m1] = smk4(sc, is), [sc2, m2] = smk4(sc, is + 1); is += 2; const d1 = d * sc1, m1v = dmin * m1, d2 = d * sc2, m2v = dmin * m2; for (let l = 0; l < 32; l++) out[b * 256 + y++] = d1 * ((qs[qo + l] & 0xF) + ((qh[l] & u1) ? 16 : 0)) - m1v; for (let l = 0; l < 32; l++) out[b * 256 + y++] = d2 * ((qs[qo + l] >> 4) + ((qh[l] & u2) ? 16 : 0)) - m2v; qo += 32; u1 <<= 2; u2 <<= 2; } }
    else if (type === 14) { const d = f16(dv.getUint16(bo + 208, true)); const ql = raw.subarray(bo, bo + 128), qh = raw.subarray(bo + 128, bo + 192), sc = raw.subarray(bo + 192, bo + 208);
      let y = 0; for (let n2 = 0; n2 < 256; n2 += 128) { const qlo = n2 / 2, qho = n2 / 4, so = n2 / 16; for (let l = 0; l < 32; l++) { const is = l / 16 | 0; const q1 = ((ql[qlo + l] & 0xF) | (((qh[qho + l] >> 0) & 3) << 4)) - 32, q2 = ((ql[qlo + l + 32] & 0xF) | (((qh[qho + l] >> 2) & 3) << 4)) - 32, q3 = ((ql[qlo + l] >> 4) | (((qh[qho + l] >> 4) & 3) << 4)) - 32, q4 = ((ql[qlo + l + 32] >> 4) | (((qh[qho + l] >> 6) & 3) << 4)) - 32; out[b * 256 + n2 + l] = d * (sc[so + is] << 24 >> 24) * q1; out[b * 256 + n2 + l + 32] = d * (sc[so + is + 2] << 24 >> 24) * q2; out[b * 256 + n2 + l + 64] = d * (sc[so + is + 4] << 24 >> 24) * q3; out[b * 256 + n2 + l + 96] = d * (sc[so + is + 6] << 24 >> 24) * q4; } } }
    else throw new Error("type " + type);
  }
  return out;
}
function smk4(q, j) { return j < 4 ? [q[j] & 63, q[j + 4] & 63] : [(q[j + 4] & 0xF) | ((q[j - 4] >> 6) << 4), (q[j + 4] >> 4) | ((q[j] >> 6) << 4)]; }
async function matrix(name) { const t = tensors[name]; const rb = t.type === 0 ? t.dims[0] * 4 : (t.dims[0] / 256) * BB[t.type]; const rows = t.dims.slice(1).reduce((a, b) => a * b, 1); const raw = await readAt(dataOff + t.off, rows * rb); return {rows, cols: t.dims[0], type: t.type, raw, rb, row: (r) => deqRow(raw, r * rb, t.type, t.dims[0]), dims: t.dims}; }
const matvec = (M, x, rowOffset = 0, nrows = M.rows) => { const o = new Float64Array(nrows); for (let r = 0; r < nrows; r++) { const w = M.row(rowOffset + r); let acc = 0; for (let i = 0; i < M.cols; i++) acc += w[i] * x[i]; o[r] = acc; } return o; };
const vec = async (name) => (await matrix(name)).row(0);
const rmsnorm = (x, w, eps) => { let ss = 0; for (const v of x) ss += v * v; const inv = 1 / Math.sqrt(ss / x.length + eps); return x.map((v, i) => v * inv * w[i]); };
const silu = (v) => v / (1 + Math.exp(-v)), sigmoid = (v) => 1 / (1 + Math.exp(-v)), softplus = (v) => v > 20 ? v : Math.log1p(Math.exp(v));
const cmp = (name, ref, got) => { let maxAbs = 0, maxRel = 0, refRms = 0, wi = 0; for (let i = 0; i < ref.length; i++) { const d = Math.abs(ref[i] - got[i]); if (d > maxAbs) { maxAbs = d; wi = i; } refRms += ref[i] * ref[i]; } refRms = Math.sqrt(refRms / ref.length); console.log(name.padEnd(9), `n=${ref.length} maxAbs=${maxAbs.toExponential(2)} refRms=${refRms.toExponential(2)} rel=${(maxAbs / (refRms || 1)).toExponential(2)} at ${wi}: ref=${ref[wi]?.toPrecision(5)} gpu=${got[wi]?.toPrecision(5)}`); };

// --- forward: LAYERS layers over TOKENS tokens, compare the last token's intermediates at layer LAYERS-1 ---
const LAYERS = Number(Deno.env.get("REF_LAYERS") ?? 1); const TOKENS = tokArg.split(",").map(Number);
const nLayer = kv["qwen35moe.block_count"], isRecr = (il) => ((il + 1) % (kv["qwen35moe.full_attention_interval"] ?? 4)) !== 0;
const KD = 16 * 128, VD = 32 * 128, E = 2048, HD = 256, NH = 16, NKV = 2, NROT = kv["qwen35moe.rope.dimension_count"], BASE = kv["qwen35moe.rope.freq_base"];
const l2 = (v, scale = 1) => { let ss = 0; for (const t of v) ss += t * t; const inv = scale / Math.sqrt(ss + EPS); return v.map((t) => t * inv); };
const emb = await matrix("token_embd.weight");
const W = {}; const M = async (n) => (W[n] ??= await matrix(n)); const V = async (n) => (W[n] ??= (await matrix(n)).row(0));
const st = []; // per-layer state
for (let il = 0; il < LAYERS; il++) st.push(isRecr(il) ? {ring: [new Float64Array(8192), new Float64Array(8192), new Float64Array(8192)], S: new Float64Array(32 * 128 * 128)} : {K: [], Vc: []});
let dbg = null;
for (let ti = 0; ti < TOKENS.length; ti++) {
  let x = emb.row(TOKENS[ti]); const last = ti === TOKENS.length - 1;
  for (let il = 0; il < LAYERS; il++) {
    const p = `blk.${il}.`; const d = (last && il === LAYERS - 1) ? {} : null;
    const h = rmsnorm(x, await V(p + "attn_norm.weight"), EPS); if (d) d.h = h;
    let attnOut;
    if (isRecr(il)) {
      const S0 = st[il];
      const qkv = matvec(await M(p + "attn_qkv.weight"), h), z = matvec(await M(p + "attn_gate.weight"), h);
      const alpha = matvec(await M(p + "ssm_alpha.weight"), h), betaL = matvec(await M(p + "ssm_beta.weight"), h);
      const dt = await V(p + "ssm_dt.bias"), ssmA = await V(p + "ssm_a");
      const g = alpha.map((v, i) => softplus(v + dt[i]) * ssmA[i]), beta = betaL.map(sigmoid);
      const convW = await M(p + "ssm_conv1d.weight"); const conv = new Float64Array(8192);
      for (let c = 0; c < 8192; c++) { const taps = convW.row(c); conv[c] = silu(taps[0] * S0.ring[0][c] + taps[1] * S0.ring[1][c] + taps[2] * S0.ring[2][c] + taps[3] * qkv[c]); }
      S0.ring = [S0.ring[1], S0.ring[2], Float64Array.from(qkv)];
      const qn = new Float64Array(KD), kn = new Float64Array(KD); for (let hh = 0; hh < 16; hh++) { qn.set(l2(conv.subarray(hh * 128, hh * 128 + 128), 1 / Math.sqrt(128)), hh * 128); kn.set(l2(conv.subarray(KD + hh * 128, KD + hh * 128 + 128)), hh * 128); }
      const v = conv.subarray(2 * KD, 2 * KD + VD); const dnOut = new Float64Array(VD);
      for (let hh = 0; hh < 32; hh++) { const kh = hh % 16, base = hh * 128 * 128, dec = Math.exp(g[hh]); const kvm = new Float64Array(128);
        for (let i = 0; i < 128; i++) for (let j = 0; j < 128; j++) { S0.S[base + i * 128 + j] *= dec; kvm[j] += S0.S[base + i * 128 + j] * kn[kh * 128 + i]; }
        const delta = new Float64Array(128); for (let j = 0; j < 128; j++) delta[j] = (v[hh * 128 + j] - kvm[j]) * beta[hh];
        for (let i = 0; i < 128; i++) for (let j = 0; j < 128; j++) { S0.S[base + i * 128 + j] += kn[kh * 128 + i] * delta[j]; dnOut[hh * 128 + j] += S0.S[base + i * 128 + j] * qn[kh * 128 + i]; } }
      const ssmNorm = await V(p + "ssm_norm.weight"); const gnorm = new Float64Array(VD); for (let hh = 0; hh < 32; hh++) { const nn = rmsnorm(dnOut.subarray(hh * 128, hh * 128 + 128), ssmNorm, EPS); for (let j = 0; j < 128; j++) gnorm[hh * 128 + j] = nn[j] * silu(z[hh * 128 + j]); }
      attnOut = matvec(await M(p + "ssm_out.weight"), gnorm);
      if (d) Object.assign(d, {qkv, z, alpha, g, beta, conv, qn, kn, dnOut, gnorm});
    } else {
      const C = st[il];
      const qFull = matvec(await M(p + "attn_q.weight"), h), kProj = matvec(await M(p + "attn_k.weight"), h), vProj = matvec(await M(p + "attn_v.weight"), h);
      const qnw = await V(p + "attn_q_norm.weight"), knw = await V(p + "attn_k_norm.weight");
      const qNorm = new Float64Array(NH * HD); for (let hh = 0; hh < NH; hh++) qNorm.set(rmsnorm(qFull.subarray(hh * 2 * HD, hh * 2 * HD + HD), qnw, EPS), hh * HD);
      const kNorm = new Float64Array(NKV * HD); for (let hh = 0; hh < NKV; hh++) kNorm.set(rmsnorm(kProj.subarray(hh * HD, hh * HD + HD), knw, EPS), hh * HD);
      const rope = (v, heads) => { const o = Float64Array.from(v); const half = NROT / 2; for (let hh = 0; hh < heads; hh++) for (let i = 0; i < half; i++) { const th = ti * Math.pow(BASE, -2 * i / NROT), c = Math.cos(th), s_ = Math.sin(th), a = v[hh * HD + i], b = v[hh * HD + i + half]; o[hh * HD + i] = a * c - b * s_; o[hh * HD + i + half] = a * s_ + b * c; } return o; };
      const qRope = rope(qNorm, NH), kRope = rope(kNorm, NKV); C.K.push(kRope); C.Vc.push(Float64Array.from(vProj));
      const attnO = new Float64Array(NH * HD); const T = C.K.length;
      for (let hh = 0; hh < NH; hh++) { const hk = Math.floor(hh / (NH / NKV)); const sc = []; for (let tt = 0; tt < T; tt++) { let dot = 0; for (let i = 0; i < HD; i++) dot += qRope[hh * HD + i] * C.K[tt][hk * HD + i]; sc.push(dot / Math.sqrt(HD)); } const mx = Math.max(...sc); const ex = sc.map((v) => Math.exp(v - mx)); const Z = ex.reduce((a, b) => a + b, 0);
        for (let i = 0; i < HD; i++) { let acc = 0; for (let tt = 0; tt < T; tt++) acc += ex[tt] / Z * C.Vc[tt][hk * HD + i]; attnO[hh * HD + i] = acc * sigmoid(qFull[hh * 2 * HD + HD + i]); } }
      attnOut = matvec(await M(p + "attn_output.weight"), attnO);
      if (d) Object.assign(d, {qFull, kProj, vProj, qNorm, qRope, kRope, attnO});
    }
    const resid = x.map((v2, i) => v2 + attnOut[i]); const h2 = rmsnorm(resid, await V(p + "post_attention_norm.weight"), EPS);
    const router = matvec(await M(p + "ffn_gate_inp.weight"), h2);
    const mx = Math.max(...router); const ex = Array.from(router, (r) => Math.exp(r - mx)); const Z = ex.reduce((a, b) => a + b, 0); const pr = ex.map((e) => e / Z);
    const order = pr.map((pp, i) => [pp, i]).sort((a, b) => b[0] - a[0] || a[1] - b[1]).slice(0, 8); const wsum = order.reduce((a, o) => a + o[0], 0);
    const Wg = await M(p + "ffn_gate_exps.weight"), Wu = await M(p + "ffn_up_exps.weight"), Wd = await M(p + "ffn_down_exps.weight");
    const ffnOut = new Float64Array(E); const downE = new Float64Array(8 * E), actE = new Float64Array(8 * 512), gateE = new Float64Array(8 * 512);
    for (let e = 0; e < 8; e++) { const ex2 = order[e][1]; const gg = matvec(Wg, h2, ex2 * 512, 512), uu = matvec(Wu, h2, ex2 * 512, 512); for (let j = 0; j < 512; j++) { gateE[e * 512 + j] = gg[j]; actE[e * 512 + j] = silu(gg[j]) * uu[j]; } const dd = matvec(Wd, actE.subarray(e * 512, e * 512 + 512), ex2 * 2048, 2048); downE.set(dd, e * E); for (let i = 0; i < E; i++) ffnOut[i] += order[e][0] / wsum * dd[i]; }
    const sg = matvec(await M(p + "ffn_gate_shexp.weight"), h2), su = matvec(await M(p + "ffn_up_shexp.weight"), h2); const sact = sg.map((v2, i) => silu(v2) * su[i]); const shDown = matvec(await M(p + "ffn_down_shexp.weight"), sact);
    const shW = await V(p + "ffn_gate_inp_shexp.weight"); let shLogit = 0; for (let i = 0; i < E; i++) shLogit += shW[i] * h2[i];
    for (let i = 0; i < E; i++) ffnOut[i] += shDown[i] * sigmoid(shLogit);
    x = resid.map((v2, i) => v2 + ffnOut[i]);
    if (d) { Object.assign(d, {attnOut, resid, h2, router, topIds: order.map((o) => o[1]), topW: order.map((o) => o[0] / wsum), gateE, actE, downE, shDown, shLogit: [shLogit], ffnOut, xout: x}); dbg = d; }
  }
}
console.log(`compared: layer ${LAYERS - 1} (${isRecr(LAYERS - 1) ? "linear" : "attention"}), token index ${TOKENS.length - 1}`);
for (const k of Object.keys(dbg)) { if (k === "topIds") { console.log("topIds ", "ref", dbg.topIds, "gpu", gpu.topIds); continue; } if (gpu[k]) cmp(k, dbg[k], gpu[k]); }
