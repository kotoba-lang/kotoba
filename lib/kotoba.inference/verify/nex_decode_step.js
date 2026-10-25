// A full Nex-N2.5-mini (qwen35moe) decode, weights from the served GGUF, every op on the GPU,
// ONE command buffer per token, the only readback being the argmax token id. Greedy tokens are
// compared with llama.cpp (the control host) on the same GGUF and prompt ids.
// Root ADR-2609182100 D1 / co-scientist iteration 2 -- the composed step. Deno WebGPU is the
// bench/oracle HARNESS here, not the runtime (the finished path is Kotoba + amu native).
//
//   deno run --unstable-webgpu --allow-read verify/nex_decode_step.js <model.gguf> <prompt ids csv> <n_predict> [expected ids csv]
//
// Memory: the whole 17.4 GB of weights is uploaded to the GPU; run on a device with >= 24 GB
// free (a 64 GB Apple Silicon Mac, or the B70 with its llama-server stopped).
const here = new URL("./", import.meta.url);
const [modelPath, promptCsv, nPredictArg, expectedCsv] = Deno.args;
if (!modelPath || !promptCsv) { console.error("usage: nex_decode_step.js <model.gguf> <prompt ids csv> <n_predict> [expected ids csv]"); Deno.exit(2); }
const promptIds = promptCsv.split(",").map(Number), nPredict = Number(nPredictArg ?? 8);
const expected = expectedCsv ? expectedCsv.split(",").map(Number) : null;
const T0 = performance.now();
const log = (...a) => console.error(`[${((performance.now() - T0) / 1000).toFixed(1)}s]`, ...a);

// ---------------- GGUF header ----------------
const file = await Deno.open(modelPath, {read: true});
const fstat = await file.stat();
async function readAt(off, len) { const out = new Uint8Array(len); let got = 0; await file.seek(off, Deno.SeekMode.Start); while (got < len) { const n = await file.read(out.subarray(got)); if (n === null) throw new Error("eof"); got += n; } return out; }
const head = await readAt(0, Math.min(fstat.size, 96 * 1024 * 1024));
const hv = new DataView(head.buffer); let pos = 0;
const u32 = () => { const v = hv.getUint32(pos, true); pos += 4; return v; };
const u64 = () => { const v = Number(hv.getBigUint64(pos, true)); pos += 8; return v; };
const gstr = () => { const n = u64(); const s = new TextDecoder().decode(head.subarray(pos, pos + n)); pos += n; return s; };
const SZ = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8, 11: 8, 12: 8};
function readValue(t) {
  if (t === 8) return gstr();
  if (t === 9) { const et = u32(), n = u64(); if (n > 4096) { if (et === 8) { for (let i = 0; i < n; i++) { const l = u64(); pos += l; } } else pos += n * SZ[et]; return {skipped: n}; } const arr = []; for (let i = 0; i < n; i++) arr.push(readValue(et)); return arr; }
  let v; switch (t) { case 0: v = hv.getUint8(pos); break; case 1: v = hv.getInt8(pos); break; case 2: v = hv.getUint16(pos, true); break; case 3: v = hv.getInt16(pos, true); break; case 4: v = hv.getUint32(pos, true); break; case 5: v = hv.getInt32(pos, true); break; case 6: v = hv.getFloat32(pos, true); break; case 7: v = hv.getUint8(pos) !== 0; break; case 10: v = Number(hv.getBigUint64(pos, true)); break; case 11: v = Number(hv.getBigInt64(pos, true)); break; case 12: v = hv.getFloat64(pos, true); break; default: throw new Error("gguf type " + t); }
  pos += SZ[t]; return v;
}
if (new TextDecoder().decode(head.subarray(0, 4)) !== "GGUF") throw new Error("not gguf");
pos = 4; const version = u32(), nTensors = u64(), nKv = u64();
const kv = {}; for (let i = 0; i < nKv; i++) { const k = gstr(); const t = u32(); kv[k] = readValue(t); }
const tensors = {}; for (let i = 0; i < nTensors; i++) { const name = gstr(); const nd = u32(); const dims = []; for (let d = 0; d < nd; d++) dims.push(u64()); const type = u32(); const off = u64(); tensors[name] = {dims, type, off}; }
const alignment = kv["general.alignment"] ?? 32; const dataOff = Math.ceil(pos / alignment) * alignment;
const arch = kv["general.architecture"]; if (arch !== "qwen35moe") throw new Error("expected qwen35moe, got " + arch);
const H = {
  nLayer: kv["qwen35moe.block_count"], nEmbd: kv["qwen35moe.embedding_length"], nHead: kv["qwen35moe.attention.head_count"], nHeadKv: kv["qwen35moe.attention.head_count_kv"],
  headDim: kv["qwen35moe.attention.key_length"], nRot: kv["qwen35moe.rope.dimension_count"], ropeBase: kv["qwen35moe.rope.freq_base"], eps: kv["qwen35moe.attention.layer_norm_rms_epsilon"],
  nExpert: kv["qwen35moe.expert_count"], nExpertUsed: kv["qwen35moe.expert_used_count"], nFfExp: kv["qwen35moe.expert_feed_forward_length"], nFfShexp: kv["qwen35moe.expert_shared_feed_forward_length"],
  convK: kv["qwen35moe.ssm.conv_kernel"], dInner: kv["qwen35moe.ssm.inner_size"], dState: kv["qwen35moe.ssm.state_size"], nKHeads: kv["qwen35moe.ssm.group_count"], nVHeads: kv["qwen35moe.ssm.time_step_rank"],
  fullInterval: kv["qwen35moe.full_attention_interval"] ?? 4, vocab: tensors["output.weight"].dims[1],
};
const isRecr = (il) => ((il + 1) % H.fullInterval) !== 0;
const BLOCK_BYTES = {12: 144, 13: 176, 14: 210, 23: 136, 0: 4};
const rowBytes = (t) => t.type === 0 ? t.dims[0] * 4 : (t.dims[0] / 256) * BLOCK_BYTES[t.type];
const tensorBytes = (t) => t.dims.slice(1).reduce((a, b) => a * b, 1) * rowBytes(t);
log("gguf", {version, nTensors, arch, dataOff}, H);

// ---------------- GPU ----------------
const adapter = await navigator.gpu.requestAdapter(); if (!adapter) throw new Error("no adapter");
const device = await adapter.requestDevice({requiredLimits: {maxStorageBufferBindingSize: Math.min(adapter.limits.maxStorageBufferBindingSize, 1 << 30), maxBufferSize: Math.min(adapter.limits.maxBufferSize, 1 << 30), maxStorageBuffersPerShaderStage: Math.max(8, adapter.limits.maxStorageBuffersPerShaderStage >= 8 ? 8 : adapter.limits.maxStorageBuffersPerShaderStage)}});
device.pushErrorScope("validation"); device.pushErrorScope("out-of-memory");
const src = async (f) => await Deno.readTextFile(new URL("../shaders/" + f, here));
const mod = async (f) => device.createShaderModule({code: await src(f)});
// f32-activation K-quant dot, four layouts (co-scientist iteration 3): r1 = thread per 4 values, row
// per workgroup; r8 = 8 rows per workgroup, x loaded once; v3 = sub-block per thread, x staged in
// workgroup memory; v3b = v3 + codebook staged in workgroup memory. Which one is fastest depends on
// the backend AND the tensor type (verify/kdot_f32_bench.js, 2026-09-18, GB/s on real Nex tensors):
//   Intel B70 : Q5_K v3 162 / r8 108 / r1 22 ; IQ4_XS v3b 30-54 / v3 24-37 / r1 13-29
//   AMD 8060S : Q5_K r8 151 / r1 92 ; IQ4_XS r1 51-81 / v3b 53-60
//   M1 Max    : Q5_K v3b 29 / r8 26 ; IQ4_XS v3b 40 / v3 34 / r1 13-19
// so the host picks per (backend, type). Owner 2026-09-18: every backend properly, none is the reference.
const KDOT = {}; for (const [n, f] of [["r1", "ggml_kdot_f32.wgsl"], ["r8", "ggml_kdot_f32_r8.wgsl"], ["v3", "ggml_kdot_f32_v3.wgsl"], ["v3b", "ggml_kdot_f32_v3b.wgsl"], ["v3c", "ggml_kdot_f32_v3c.wgsl"]]) KDOT[n] = device.createComputePipeline({layout: "auto", compute: {module: await mod(f), entryPoint: "main"}});
const gpuName = (adapter.info?.description ?? "").toLowerCase();
const backend = gpuName.includes("intel") ? "intel" : gpuName.includes("radeon") || gpuName.includes("amd") ? "amd" : gpuName.includes("apple") ? "metal" : gpuName.includes("nvidia") || gpuName.includes("tegra") ? "nvidia" : "unknown";
// re-measured with 40 dispatches per command buffer (iteration 4): Intel Q5_K v3 224 GB/s, IQ4_XS v3c 54-72;
// AMD Q5_K r8 136, IQ4_XS r8 65-117; Metal IQ4_XS v3b 38-40, Q5_K v3 23.
const KDOT_TABLE = {intel: {13: "v3", 23: "v3c", 14: "v3", 12: "v3"}, amd: {13: "r8", 23: "r8", 14: "r8", 12: "r8"}, metal: {13: "v3", 23: "v3b", 14: "v3b", 12: "v3b"}, nvidia: {13: "v3", 23: "v3c", 14: "v3", 12: "v3"}, unknown: {13: "r1", 23: "r1", 14: "r1", 12: "r1"}};
const kdotFor = (type) => { const n = (Deno.env.get("NEX_KDOT") ?? KDOT_TABLE[backend][type]) || "r1"; return {name: n, pipe: KDOT[n], groups: (rows) => n === "r1" ? rows : Math.ceil(rows / 8)}; };
const kdotPipe = KDOT.r1; const moePipe = KDOT.r1; // identities used by the profiler's class detection
log("backend", backend, "kdot table", KDOT_TABLE[backend], Deno.env.get("NEX_KDOT") ? `(forced ${Deno.env.get("NEX_KDOT")})` : "");
const dnPipe = device.createComputePipeline({layout: "auto", compute: {module: await mod("deltanet_step.wgsl"), entryPoint: "main"}});
const opsMod = await mod("nex_ops.wgsl");
const bgl = device.createBindGroupLayout({entries: [
  {binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: {type: "uniform"}},
  {binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: {type: "read-only-storage"}},
  {binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: {type: "read-only-storage"}},
  {binding: 3, visibility: GPUShaderStage.COMPUTE, buffer: {type: "read-only-storage"}},
  {binding: 4, visibility: GPUShaderStage.COMPUTE, buffer: {type: "storage"}},
  {binding: 5, visibility: GPUShaderStage.COMPUTE, buffer: {type: "storage"}},
  {binding: 6, visibility: GPUShaderStage.COMPUTE, buffer: {type: "storage"}}]});
const opsLayout = device.createPipelineLayout({bindGroupLayouts: [bgl]});
const OPS = {}; for (const e of ["rmsnorm", "l2norm", "gated_rmsnorm", "silu_mul", "conv1d_step", "softmax_topk", "gate_decay", "weighted_sum", "rope_neox", "attn_decode", "argmax_partial", "argmax_final", "add", "f32_matvec", "add_rmsnorm"]) OPS[e] = device.createComputePipeline({layout: opsLayout, compute: {module: opsMod, entryPoint: e}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST, UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const gbuf = (bytes, usage = SU) => device.createBuffer({size: Math.max(16, Math.ceil(bytes / 4) * 4), usage});
const f32buf = (n) => gbuf(n * 4);
const uni = (arr) => { const b = gbuf(Math.max(32, arr.byteLength), UU); device.queue.writeBuffer(b, 0, arr); return b; };
const meta4 = (a, b, c, d) => uni(new Uint32Array([a, b, c, d]));
const meta8 = (a, b, c, d, e, f, g, h) => uni(new Uint32Array([a, b, c, d, e, f, g, h]));
const opsMeta = (n, rows, aux, aux2, eps, scale) => { const u = new ArrayBuffer(32), dv = new DataView(u); dv.setUint32(0, n, true); dv.setUint32(4, rows, true); dv.setUint32(8, aux, true); dv.setUint32(12, aux2, true); dv.setFloat32(16, eps, true); dv.setFloat32(20, scale, true); return uni(new Uint8Array(u)); };
const setOpsMeta = (buf, n, rows, aux, aux2, eps, scale) => { const u = new ArrayBuffer(32), dv = new DataView(u); dv.setUint32(0, n, true); dv.setUint32(4, rows, true); dv.setUint32(8, aux, true); dv.setUint32(12, aux2, true); dv.setFloat32(16, eps, true); dv.setFloat32(20, scale, true); device.queue.writeBuffer(buf, 0, u); };
const dummies = [0, 1, 2, 3, 4].map(() => f32buf(4));
const ent = (bufs) => bufs.map((b, i) => ({binding: i, resource: Array.isArray(b) ? {buffer: b[0], offset: b[1], size: b[2]} : {buffer: b}}));

// upload a tensor's raw bytes to a GPU buffer (chunked reads)
let uploaded = 0;
async function upload(name) {
  const t = tensors[name]; if (!t) throw new Error("missing tensor " + name);
  const bytes = tensorBytes(t); const b = gbuf(bytes);
  const CH = 64 << 20; for (let o = 0; o < bytes; o += CH) { const n = Math.min(CH, bytes - o); const chunk = await readAt(dataOff + t.off + o, n); device.queue.writeBuffer(b, o, chunk, 0, n); }
  // Flush: wgpu stages queue.writeBuffer data until the next submit; 18 GB of pending staging
  // silently lost the small tensors (measured: layer norm weights read back as zeros while the
  // last-uploaded output_norm was intact). An empty submit per tensor bounds the staging.
  device.queue.submit([]);
  uploaded += bytes; return {buf: b, t};
}
// several same-type, same-width tensors uploaded back to back into ONE buffer (rows concatenated), so one
// dispatch computes them all: fewer dispatches, same bytes. Returns {buf, t: {type, dims: [cols, rows]}}.
async function uploadConcat(names) {
  const ts = names.map((n) => tensors[n]); const type = ts[0].type, cols = ts[0].dims[0];
  for (const t of ts) if (t.type !== type || t.dims[0] !== cols) throw new Error("uploadConcat: mixed type/width " + names);
  const sizes = ts.map(tensorBytes); const total = sizes.reduce((a, b) => a + b, 0); const b = gbuf(total); let off = 0;
  for (let k = 0; k < ts.length; k++) { const CH = 64 << 20; for (let o = 0; o < sizes[k]; o += CH) { const n = Math.min(CH, sizes[k] - o); const chunk = await readAt(dataOff + ts[k].off + o, n); device.queue.writeBuffer(b, off + o, chunk, 0, n); } off += sizes[k]; device.queue.submit([]); }
  uploaded += total; const rows = ts.reduce((a, t) => a + t.dims.slice(1).reduce((x, y) => x * y, 1), 0);
  return {buf: b, t: {type, dims: [cols, rows], off: -1}};
}
// f32 tensor to a JS array (small ones)
async function f32Tensor(name) { const t = tensors[name]; const bytes = tensorBytes(t); const raw = await readAt(dataOff + t.off, bytes); return new Float32Array(raw.buffer, raw.byteOffset, bytes / 4); }
// IQ4_XS row dequant (token embedding)
const KV4 = [-127, -104, -83, -65, -49, -35, -22, -10, 1, 13, 25, 38, 53, 69, 89, 113];
const f16 = (u) => { const s = (u >> 15) & 1, e = (u >> 10) & 31, m = u & 1023; if (e === 0) return (s ? -1 : 1) * m * 2 ** -24; if (e === 31) return m ? NaN : (s ? -Infinity : Infinity); return (s ? -1 : 1) * (1 + m / 1024) * 2 ** (e - 15); };
async function embedRow(id) {
  const t = tensors["token_embd.weight"]; if (t.type !== 23) throw new Error("token_embd type " + t.type + " not handled (IQ4_XS only)");
  const rb = rowBytes(t); const raw = await readAt(dataOff + t.off + id * rb, rb); const dv = new DataView(raw.buffer, raw.byteOffset);
  const out = new Float32Array(t.dims[0]); const nb = t.dims[0] / 256;
  for (let b = 0; b < nb; b++) { const o = b * 136; const d = f16(dv.getUint16(o, true)); const sh = dv.getUint16(o + 2, true);
    for (let ib = 0; ib < 8; ib++) { const ls = ((raw[o + 4 + (ib >> 1)] >> (4 * (ib & 1))) & 0xf) | (((sh >> (2 * ib)) & 3) << 4); const dl = d * (ls - 32);
      for (let j = 0; j < 16; j++) { const q = raw[o + 8 + ib * 16 + j]; out[b * 256 + ib * 32 + j] = dl * KV4[q & 0xf]; out[b * 256 + ib * 32 + 16 + j] = dl * KV4[q >> 4]; } } }
  return out;
}

// ---------------- activation buffers ----------------
const E = H.nEmbd, QKV = 2 * H.nKHeads * H.dState + H.nVHeads * H.dState, VD = H.nVHeads * H.dState, KD = H.nKHeads * H.dState;
const A = {
  x: f32buf(E), h: f32buf(E), q8x: gbuf((E / 256) * 292), resid: f32buf(E), h2: f32buf(E), q8h2: gbuf((E / 256) * 292), ffnOut: f32buf(E), hn: f32buf(E), q8hn: gbuf((E / 256) * 292),
  qkv: f32buf(QKV), zab: f32buf(VD + 3 * H.nVHeads), g: f32buf(64 + H.nVHeads), /* g at 0, beta at element 64 (byte 256) */ conv: f32buf(QKV), qn: f32buf(KD), kn: f32buf(KD), dnOut: f32buf(VD), gnorm: f32buf(VD), q8vd: gbuf((VD / 256) * 292), attnOut: f32buf(E),
  routerSh: f32buf(H.nExpert + 1), topIds: gbuf(H.nExpertUsed * 4), topW: f32buf(H.nExpertUsed), gateE: f32buf(H.nExpertUsed * H.nFfExp), upE: f32buf(H.nExpertUsed * H.nFfExp), actE: f32buf(H.nExpertUsed * H.nFfExp), q8e: gbuf(H.nExpertUsed * (H.nFfExp / 256) * 292), downE: f32buf(H.nExpertUsed * E),
  shGU: f32buf(2 * H.nFfShexp), shAct: f32buf(H.nFfShexp), shDown: f32buf(E),
  qFull: f32buf(H.nHead * H.headDim * 2), kProj: f32buf(H.nHeadKv * H.headDim), vProj: f32buf(H.nHeadKv * H.headDim), qNorm: f32buf(H.nHead * H.headDim), kNorm: f32buf(H.nHeadKv * H.headDim), qRope: f32buf(H.nHead * H.headDim), kRope: f32buf(H.nHeadKv * H.headDim), attnO: f32buf(H.nHead * H.headDim), q8attn: gbuf(((H.nHead * H.headDim) / 256) * 292),
  logits: f32buf(H.vocab), amaxPart: f32buf(Math.ceil(H.vocab / 4096)), amaxIds: gbuf((Math.ceil(H.vocab / 4096) + 1) * 4), amaxVal: f32buf(4),
};
const T_MAX = 512;
const zero = (b, n) => device.queue.writeBuffer(b, 0, new Float32Array(n));

// ---------------- per-layer resources ----------------
const layers = [];
for (let il = 0; il < H.nLayer; il++) {
  const L = {il, recr: isRecr(il)};
  const w = async (suffix) => await upload(`blk.${il}.${suffix}`);
  L.attnNorm = await w("attn_norm.weight"); L.postNorm = await w("post_attention_norm.weight");
  if (L.recr) {
    L.qkv = await w("attn_qkv.weight");
    // z (4096 rows) | alpha (32) | alpha again (32 rows of padding so beta lands 256-byte aligned) | beta (32)
    L.zab = await uploadConcat([`blk.${il}.attn_gate.weight`, `blk.${il}.ssm_alpha.weight`, `blk.${il}.ssm_alpha.weight`, `blk.${il}.ssm_beta.weight`]);
    L.conv1d = await w("ssm_conv1d.weight"); L.dt = await w("ssm_dt.bias"); L.ssmA = await w("ssm_a"); L.ssmNorm = await w("ssm_norm.weight"); L.out = await w("ssm_out.weight");
    L.convRing = f32buf(3 * QKV); zero(L.convRing, 3 * QKV); L.state = f32buf(H.nVHeads * H.dState * H.dState); zero(L.state, H.nVHeads * H.dState * H.dState);
  } else {
    L.q = await w("attn_q.weight"); L.k = await w("attn_k.weight"); L.v = await w("attn_v.weight"); L.o = await w("attn_output.weight"); L.qNormW = await w("attn_q_norm.weight"); L.kNormW = await w("attn_k_norm.weight");
    L.kCache = f32buf(T_MAX * H.nHeadKv * H.headDim); L.vCache = f32buf(T_MAX * H.nHeadKv * H.headDim);
  }
  L.routerSh = await uploadConcat([`blk.${il}.ffn_gate_inp.weight`, `blk.${il}.ffn_gate_inp_shexp.weight`]); // f32 [256 + 1] x 2048
  L.gateExps = await w("ffn_gate_exps.weight"); L.upExps = await w("ffn_up_exps.weight"); L.downExps = await w("ffn_down_exps.weight");
  L.gateUpSh = await uploadConcat([`blk.${il}.ffn_gate_shexp.weight`, `blk.${il}.ffn_up_shexp.weight`]); L.downSh = await w("ffn_down_shexp.weight");
  layers.push(L);
  if (il % 5 === 4) { await device.queue.onSubmittedWorkDone(); log(`layer ${il} uploaded, ${(uploaded / 1e9).toFixed(2)} GB so far`); }
}
const outNorm = await upload("output_norm.weight"); const outW = await upload("output.weight");
await device.queue.onSubmittedWorkDone();
log(`weights uploaded: ${(uploaded / 1e9).toFixed(2)} GB`);

// ---------------- bind groups (static) ----------------
const zeroIds = gbuf(16); device.queue.writeBuffer(zeroIds, 0, new Uint32Array([0, 0, 0, 0]));
// plain matvec: expert 0 of a 1-expert tensor = the tensor itself; xin is an f32 buffer (or [buf, off, size])
const kdotBG = (W, xin, out, rows, cols, outOffsetBytes = 0, weightOffsetBytes = 0, weightBytes = null) => {
  const k = kdotFor(W.t.type); const m = meta8(rows, cols, W.t.type, 1, 0, 0, 0, 0);
  const wres = weightBytes ? [W.buf, weightOffsetBytes, weightBytes] : W.buf;
  const ores = outOffsetBytes ? [out, outOffsetBytes, rows * 4] : out;
  return {bg: device.createBindGroup({layout: k.pipe.getBindGroupLayout(0), entries: ent([m, wres, xin, ores, zeroIds])}), rows, pipe: k.pipe, gx: k.groups(rows)};
};
const moeBG = (W, xin, out, rowsPerExpert, cols, perExpertInput) => { const k = kdotFor(W.t.type); return {bg: device.createBindGroup({layout: k.pipe.getBindGroupLayout(0), entries: ent([meta8(rowsPerExpert, cols, W.t.type, H.nExpertUsed, perExpertInput ? 1 : 0, 0, 0, 0), W.buf, xin, out, A.topIds])}), rows: rowsPerExpert, pipe: k.pipe, gx: k.groups(rowsPerExpert)}; };
const opBG = (metaBuf, a, b, c, o, s, ids) => device.createBindGroup({layout: bgl, entries: ent([metaBuf, a, b ?? dummies[0], c ?? dummies[1], o, s ?? dummies[2], ids ?? dummies[3]])});
const kdotOutBytes = 0;
for (const L of layers) {
  L.bg = {};
  L.bg.attnNorm = opBG(opsMeta(E, 1, 0, 0, H.eps, 0), A.x, L.attnNorm.buf, null, A.h);
    if (L.recr) {
    L.bg.qkv = kdotBG(L.qkv, A.h, A.qkv, QKV, E); L.bg.zab = kdotBG(L.zab, A.h, A.zab, VD + 3 * H.nVHeads, E);
    const abSlice = [A.zab, VD * 4, 3 * H.nVHeads * 4]; // alpha | alpha(pad) | beta
    L.bg.gateDecay = opBG(opsMeta(0, H.nVHeads, 64, 2 * H.nVHeads, 0, 0), abSlice, L.dt.buf, L.ssmA.buf, A.g);
    L.bg.conv = opBG(opsMeta(QKV, 1, 0, 0, 0, 0), A.qkv, L.conv1d.buf, null, A.conv, L.convRing);
    L.bg.qn = opBG(opsMeta(H.dState, H.nKHeads, 0, 0, H.eps, 1 / Math.sqrt(H.dState)), [A.conv, 0, KD * 4], null, null, A.qn); // q * 1/sqrt(S_k) as in delta-net-base.cpp
    L.bg.kn = opBG(opsMeta(H.dState, H.nKHeads, 0, 0, H.eps, 0), [A.conv, KD * 4, KD * 4], null, null, A.kn);
    L.bg.dn = device.createBindGroup({layout: dnPipe.getBindGroupLayout(0), entries: ent([meta4(H.nVHeads, H.dState, H.dState, H.nKHeads), A.qn, A.kn, [A.conv, 2 * KD * 4, VD * 4], [A.g, 0, H.nVHeads * 4], [A.g, 256, H.nVHeads * 4], L.state, A.dnOut])});
    L.bg.gnorm = opBG(opsMeta(H.dState, H.nVHeads, 0, 0, H.eps, 0), A.dnOut, L.ssmNorm.buf, [A.zab, 0, VD * 4], A.gnorm);
    L.bg.out = kdotBG(L.out, A.gnorm, A.attnOut, E, VD);
  } else {
    L.bg.q = kdotBG(L.q, A.h, A.qFull, H.nHead * H.headDim * 2, E); L.bg.k = kdotBG(L.k, A.h, A.kProj, H.nHeadKv * H.headDim, E); L.bg.v = kdotBG(L.v, A.h, A.vProj, H.nHeadKv * H.headDim, E);
    L.bg.qNorm = opBG(opsMeta(H.headDim, H.nHead, 2 * H.headDim, 0, H.eps, 0), A.qFull, L.qNormW.buf, null, A.qNorm);
    L.bg.kNorm = opBG(opsMeta(H.headDim, H.nHeadKv, 0, 0, H.eps, 0), A.kProj, L.kNormW.buf, null, A.kNorm);
    L.ropeQMeta = opsMeta(H.headDim, H.nHead, H.nRot, 0, 0, H.ropeBase); L.ropeKMeta = opsMeta(H.headDim, H.nHeadKv, H.nRot, 0, 0, H.ropeBase);
    L.bg.ropeQ = opBG(L.ropeQMeta, A.qNorm, null, null, A.qRope); L.bg.ropeK = opBG(L.ropeKMeta, A.kNorm, null, null, A.kRope);
    L.attnMeta = opsMeta(H.headDim, H.nHead, 1, H.nHeadKv, -1.0, 1 / Math.sqrt(H.headDim));
    L.bg.attn = opBG(L.attnMeta, A.qRope, L.kCache, L.vCache, A.attnO, A.qFull);
    L.bg.o = kdotBG(L.o, A.attnO, A.attnOut, E, H.nHead * H.headDim);
  }
  L.bg.residPost = opBG(opsMeta(E, 1, 0, 0, H.eps, 0), A.x, A.attnOut, L.postNorm.buf, A.resid, A.h2); // add_rmsnorm
  L.bg.routerSh = opBG(opsMeta(E, H.nExpert + 1, 0, 0, 0, 0), L.routerSh.buf, A.h2, null, A.routerSh);
  L.bg.topk = opBG(opsMeta(H.nExpert, 1, H.nExpertUsed, 0, 0, 1.0), [A.routerSh, 0, H.nExpert * 4], null, null, A.topW, null, A.topIds);
  L.bg.gateE = moeBG(L.gateExps, A.h2, A.gateE, H.nFfExp, E, false); L.bg.upE = moeBG(L.upExps, A.h2, A.upE, H.nFfExp, E, false);
  L.bg.actE = opBG(opsMeta(H.nExpertUsed * H.nFfExp, 1, 0, 0, 0, 0), A.gateE, A.upE, null, A.actE);
  L.bg.downE = moeBG(L.downExps, A.actE, A.downE, E, H.nFfExp, true);
  L.bg.shGU = kdotBG(L.gateUpSh, A.h2, A.shGU, 2 * H.nFfShexp, E);
  L.bg.shAct = opBG(opsMeta(H.nFfShexp, 1, 0, 0, 0, 0), [A.shGU, 0, H.nFfShexp * 4], [A.shGU, H.nFfShexp * 4, H.nFfShexp * 4], null, A.shAct);
  L.bg.shDown = kdotBG(L.downSh, A.shAct, A.shDown, E, H.nFfShexp);
  L.bg.wsum = opBG(opsMeta(E, 1, H.nExpertUsed, 0, 0, 0), A.downE, A.topW, A.shDown, A.ffnOut, [A.routerSh, H.nExpert * 4, 4]);
  // x = resid + ffnOut, and the NEXT layer's attn_norm (or the final output_norm) in the same dispatch
  L.bg.resid2 = null; // built after all layers exist (needs layer il+1's norm weight)
}
for (let il = 0; il < H.nLayer; il++) { const L = layers[il]; const nw = il + 1 < H.nLayer ? layers[il + 1].attnNorm.buf : outNorm.buf; const dst = il + 1 < H.nLayer ? A.h : A.hn; L.bg.resid2 = opBG(opsMeta(E, 1, 0, 0, H.eps, 0), A.resid, A.ffnOut, nw, A.x, dst); }
const finalBG = {
  lmChunks: [], parts: Math.ceil(H.vocab / 4096),
};
{ const CH = 62080; const rb = rowBytes(outW.t); for (let r0 = 0; r0 < H.vocab; r0 += CH) { const rows = Math.min(CH, H.vocab - r0); finalBG.lmChunks.push(kdotBG(outW, A.hn, A.logits, rows, E, r0 * 4, r0 * rb, rows * rb)); } }
finalBG.amaxP = opBG(opsMeta(H.vocab, 1, finalBG.parts, 0, 0, 0), A.logits, null, null, A.amaxVal, A.amaxPart, A.amaxIds);
finalBG.amaxF = opBG(opsMeta(H.vocab, 1, finalBG.parts, 0, 0, 0), A.logits, null, null, A.amaxVal, A.amaxPart, A.amaxIds);
const idStaging = device.createBuffer({size: (finalBG.parts + 1) * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
log("bind groups ready");

// ---------------- one token = one command buffer ----------------
const wgN = (n) => Math.ceil(n / 256);
// The attention layers need this position's k/v in the cache before attn_decode reads them, and
// the copy is a transfer command, so a token is: [pass A: everything up to and including rope for
// every layer]? No -- layers are sequential, so the copy must sit between rope and attn of the same
// layer. WebGPU allows copyBufferToBuffer between compute passes in one command buffer, so the step
// is one command buffer with 10 short pass breaks (one per attention layer), still one submit.
const DEBUG_LAYERS = Number(Deno.env.get("NEX_DEBUG_LAYERS") ?? 0);
// Profiling: PROFILE_ONLY selects which dispatch classes are recorded so a token's time can be
// split by ablation (everything else is skipped; results are then garbage, only timing matters).
let PROFILE_ONLY = null; // null = all; "kdot" = plain K-quant matvecs; "moe" = expert gathers; "lmhead"; "ops" = nex_ops + deltanet; "none" = no dispatch (submit/readback floor)
let dispatchCount = 0;
function encodeToken(enc, position) {
  let rawPass = enc.beginComputePass();
  const wrap = (pass) => { let cls = "ops"; return {
    setPipeline(pl) { cls = Object.values(KDOT).includes(pl) ? "kdot" : "ops"; pass.setPipeline(pl); },
    setBindGroup(i, bg) { pass.setBindGroup(i, bg); },
    dispatchWorkgroups(x, y = 1, z = 1) { let c = cls; if (c === "kdot" && y > 1) c = "moe"; if (c === "kdot" && currentLm) c = "lmhead"; dispatchCount++; if (PROFILE_ONLY === null || PROFILE_ONLY === c) pass.dispatchWorkgroups(x, y, z); },
    end() { pass.end(); } }; };
  let currentLm = false;
  let p = wrap(rawPass);
  for (const L of (DEBUG_LAYERS ? layers.slice(0, DEBUG_LAYERS) : layers)) {
    if (L.il === 0) { p.setPipeline(OPS.rmsnorm); p.setBindGroup(0, L.bg.attnNorm); p.dispatchWorkgroups(1); } // later layers get h from the previous add_rmsnorm
    if (L.recr) {
      for (const k of [L.bg.qkv, L.bg.zab]) { p.setPipeline(k.pipe); p.setBindGroup(0, k.bg); p.dispatchWorkgroups(k.gx, 1, 1); }
      p.setPipeline(OPS.gate_decay); p.setBindGroup(0, L.bg.gateDecay); p.dispatchWorkgroups(1);
      p.setPipeline(OPS.conv1d_step); p.setBindGroup(0, L.bg.conv); p.dispatchWorkgroups(wgN(QKV));
      p.setPipeline(OPS.l2norm); p.setBindGroup(0, L.bg.qn); p.dispatchWorkgroups(H.nKHeads); p.setBindGroup(0, L.bg.kn); p.dispatchWorkgroups(H.nKHeads);
      p.setPipeline(dnPipe); p.setBindGroup(0, L.bg.dn); p.dispatchWorkgroups(H.nVHeads);
      p.setPipeline(OPS.gated_rmsnorm); p.setBindGroup(0, L.bg.gnorm); p.dispatchWorkgroups(H.nVHeads);
      p.setPipeline(L.bg.out.pipe); p.setBindGroup(0, L.bg.out.bg); p.dispatchWorkgroups(L.bg.out.gx, 1, 1);
    } else {
      for (const k of [L.bg.q, L.bg.k, L.bg.v]) { p.setPipeline(k.pipe); p.setBindGroup(0, k.bg); p.dispatchWorkgroups(k.gx, 1, 1); }
      p.setPipeline(OPS.rmsnorm); p.setBindGroup(0, L.bg.qNorm); p.dispatchWorkgroups(H.nHead); p.setBindGroup(0, L.bg.kNorm); p.dispatchWorkgroups(H.nHeadKv);
      p.setPipeline(OPS.rope_neox); p.setBindGroup(0, L.bg.ropeQ); p.dispatchWorkgroups(H.nHead); p.setBindGroup(0, L.bg.ropeK); p.dispatchWorkgroups(H.nHeadKv);
      p.end();
      const kvBytes = H.nHeadKv * H.headDim * 4;
      enc.copyBufferToBuffer(A.kRope, 0, L.kCache, position * kvBytes, kvBytes);
      enc.copyBufferToBuffer(A.vProj, 0, L.vCache, position * kvBytes, kvBytes);
      p = wrap(enc.beginComputePass());
      p.setPipeline(OPS.attn_decode); p.setBindGroup(0, L.bg.attn); p.dispatchWorkgroups(H.nHead);
      p.setPipeline(L.bg.o.pipe); p.setBindGroup(0, L.bg.o.bg); p.dispatchWorkgroups(L.bg.o.gx, 1, 1);
    }
    p.setPipeline(OPS.add_rmsnorm); p.setBindGroup(0, L.bg.residPost); p.dispatchWorkgroups(1);
    p.setPipeline(OPS.f32_matvec); p.setBindGroup(0, L.bg.routerSh); p.dispatchWorkgroups(H.nExpert + 1);
    p.setPipeline(OPS.softmax_topk); p.setBindGroup(0, L.bg.topk); p.dispatchWorkgroups(1);
    p.setPipeline(L.bg.gateE.pipe); p.setBindGroup(0, L.bg.gateE.bg); p.dispatchWorkgroups(L.bg.gateE.gx, H.nExpertUsed); p.setPipeline(L.bg.upE.pipe); p.setBindGroup(0, L.bg.upE.bg); p.dispatchWorkgroups(L.bg.upE.gx, H.nExpertUsed);
    p.setPipeline(OPS.silu_mul); p.setBindGroup(0, L.bg.actE); p.dispatchWorkgroups(wgN(H.nExpertUsed * H.nFfExp));
    p.setPipeline(L.bg.downE.pipe); p.setBindGroup(0, L.bg.downE.bg); p.dispatchWorkgroups(L.bg.downE.gx, H.nExpertUsed);
    p.setPipeline(L.bg.shGU.pipe); p.setBindGroup(0, L.bg.shGU.bg); p.dispatchWorkgroups(L.bg.shGU.gx, 1, 1);
    p.setPipeline(OPS.silu_mul); p.setBindGroup(0, L.bg.shAct); p.dispatchWorkgroups(wgN(H.nFfShexp));
    p.setPipeline(L.bg.shDown.pipe); p.setBindGroup(0, L.bg.shDown.bg); p.dispatchWorkgroups(L.bg.shDown.gx, 1, 1);
    p.setPipeline(OPS.weighted_sum); p.setBindGroup(0, L.bg.wsum); p.dispatchWorkgroups(wgN(E));
    p.setPipeline(OPS.add_rmsnorm); p.setBindGroup(0, L.bg.resid2); p.dispatchWorkgroups(1);   // x += ffnOut ; h (next layer) or hn (final)
  }
  currentLm = true; for (const c of finalBG.lmChunks) { p.setPipeline(c.pipe); p.setBindGroup(0, c.bg); p.dispatchWorkgroups(c.gx, 1, 1); } currentLm = false;
  p.setPipeline(OPS.argmax_partial); p.setBindGroup(0, finalBG.amaxP); p.dispatchWorkgroups(finalBG.parts);
  p.setPipeline(OPS.argmax_final); p.setBindGroup(0, finalBG.amaxF); p.dispatchWorkgroups(1);
  p.end();
  enc.copyBufferToBuffer(A.amaxIds, 0, idStaging, 0, (finalBG.parts + 1) * 4);
}
async function stats(name, buf, n, u32 = false) {
  const st = device.createBuffer({size: n * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
  const e = device.createCommandEncoder(); e.copyBufferToBuffer(buf, 0, st, 0, n * 4); device.queue.submit([e.finish()]);
  await st.mapAsync(GPUMapMode.READ); const raw = st.getMappedRange().slice(0); st.unmap();
  if (u32) { console.error(name, Array.from(new Uint32Array(raw)).slice(0, 16)); return; }
  const a = new Float32Array(raw); let nan = 0, sum = 0, sq = 0, mx = -Infinity, mn = Infinity;
  for (const v of a) { if (Number.isNaN(v) || !Number.isFinite(v)) { nan++; continue; } sum += v; sq += v * v; if (v > mx) mx = v; if (v < mn) mn = v; }
  const m = sum / a.length; console.error(name.padEnd(12), `n=${a.length} nan/inf=${nan} mean=${m.toExponential(3)} rms=${Math.sqrt(sq / a.length).toExponential(3)} min=${mn.toExponential(2)} max=${mx.toExponential(2)} head=[${Array.from(a.slice(0, 4)).map((v) => v.toPrecision(4)).join(", ")}]`);
}
async function dumpF32(buf, n) { const st = device.createBuffer({size: n * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ}); const e = device.createCommandEncoder(); e.copyBufferToBuffer(buf, 0, st, 0, n * 4); device.queue.submit([e.finish()]); await st.mapAsync(GPUMapMode.READ); const a = Array.from(new Float32Array(st.getMappedRange().slice(0))); st.unmap(); return a; }
async function dumpU32(buf, n) { const st = device.createBuffer({size: n * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ}); const e = device.createCommandEncoder(); e.copyBufferToBuffer(buf, 0, st, 0, n * 4); device.queue.submit([e.finish()]); await st.mapAsync(GPUMapMode.READ); const a = Array.from(new Uint32Array(st.getMappedRange().slice(0))); st.unmap(); return a; }
async function debugDump() {
  const L = layers[DEBUG_LAYERS - 1];
  if (Deno.env.get("NEX_DEBUG_JSON")) {
    const d = {xout: await dumpF32(A.x, E), h: await dumpF32(A.h, E), qFull: await dumpF32(A.qFull, H.nHead * H.headDim * 2), kProj: await dumpF32(A.kProj, H.nHeadKv * H.headDim), vProj: await dumpF32(A.vProj, H.nHeadKv * H.headDim), qNorm: await dumpF32(A.qNorm, H.nHead * H.headDim), qRope: await dumpF32(A.qRope, H.nHead * H.headDim), kRope: await dumpF32(A.kRope, H.nHeadKv * H.headDim), attnO: await dumpF32(A.attnO, H.nHead * H.headDim), qkv: await dumpF32(A.qkv, QKV), z: (await dumpF32(A.zab, VD + 3 * H.nVHeads)).slice(0, VD), alpha: (await dumpF32(A.zab, VD + 3 * H.nVHeads)).slice(VD, VD + H.nVHeads), g: await dumpF32(A.g, H.nVHeads), beta: (await dumpF32(A.g, 64 + H.nVHeads)).slice(64), conv: await dumpF32(A.conv, QKV), qn: await dumpF32(A.qn, KD), kn: await dumpF32(A.kn, KD), dnOut: await dumpF32(A.dnOut, VD), gnorm: await dumpF32(A.gnorm, VD), attnOut: await dumpF32(A.attnOut, E), resid: await dumpF32(A.resid, E), h2: await dumpF32(A.h2, E), router: (await dumpF32(A.routerSh, H.nExpert + 1)).slice(0, H.nExpert), topIds: await dumpU32(A.topIds, H.nExpertUsed), topW: await dumpF32(A.topW, H.nExpertUsed), gateE: await dumpF32(A.gateE, H.nExpertUsed * H.nFfExp), actE: await dumpF32(A.actE, H.nExpertUsed * H.nFfExp), downE: await dumpF32(A.downE, H.nExpertUsed * E), shDown: await dumpF32(A.shDown, E), shLogit: (await dumpF32(A.routerSh, H.nExpert + 1)).slice(H.nExpert), ffnOut: await dumpF32(A.ffnOut, E)};
    // NOTE: A.x has been overwritten by the layer output at this point; the layer input is resid - attnOut
    if (DEBUG_LAYERS >= H.nLayer) { const lg = await dumpF32(A.logits, H.vocab); const top = Array.from(lg.keys()).sort((a, b) => lg[b] - lg[a]).slice(0, 8).map((i) => [i, +lg[i].toFixed(3)]); d.top8 = top; console.error("GPU top-8 logits", JSON.stringify(top)); }
    await Deno.writeTextFile(Deno.env.get("NEX_DEBUG_JSON"), JSON.stringify(d)); console.error("wrote", Deno.env.get("NEX_DEBUG_JSON"));
  }
  console.error("attn_norm tensor", L.attnNorm.t, "bytes", tensorBytes(L.attnNorm.t));
  await stats("attnNormW", L.attnNorm.buf, E); await stats("postNormW", L.postNorm.buf, E); await stats("outNormW", outNorm.buf, E);
  await stats("x(in)", A.x, E); await stats("h(norm)", A.h, E);
  if (L.recr) { await stats("qkv", A.qkv, QKV); await stats("zab", A.zab, VD + 3 * H.nVHeads); await stats("g", A.g, H.nVHeads); await stats("conv", A.conv, QKV); await stats("qn", A.qn, KD); await stats("kn", A.kn, KD); await stats("dnOut", A.dnOut, VD); await stats("gnorm", A.gnorm, VD); }
  else { await stats("qFull", A.qFull, H.nHead * H.headDim * 2); await stats("qRope", A.qRope, H.nHead * H.headDim); await stats("kRope", A.kRope, H.nHeadKv * H.headDim); await stats("attnO", A.attnO, H.nHead * H.headDim); }
  await stats("attnOut", A.attnOut, E); await stats("resid", A.resid, E); await stats("h2", A.h2, E); await stats("routerSh", A.routerSh, H.nExpert + 1); await stats("topIds", A.topIds, H.nExpertUsed, true); await stats("topW", A.topW, H.nExpertUsed);
  await stats("gateE", A.gateE, H.nExpertUsed * H.nFfExp); await stats("actE", A.actE, H.nExpertUsed * H.nFfExp); await stats("downE", A.downE, H.nExpertUsed * E); await stats("shDown", A.shDown, E); await stats("ffnOut", A.ffnOut, E); await stats("x(out)", A.x, E);
  await stats("hn", A.hn, E); await stats("logits", A.logits, H.vocab);
}
async function step(tokenId, position) {
  device.queue.writeBuffer(A.x, 0, await embedRow(tokenId));
  for (const L of layers) if (!L.recr) { setOpsMeta(L.ropeQMeta, H.headDim, H.nHead, H.nRot, position, 0, H.ropeBase); setOpsMeta(L.ropeKMeta, H.headDim, H.nHeadKv, H.nRot, position, 0, H.ropeBase); setOpsMeta(L.attnMeta, H.headDim, H.nHead, position + 1, H.nHeadKv, -1.0, 1 / Math.sqrt(H.headDim)); }
  const enc = device.createCommandEncoder(); encodeToken(enc, position);
  const t0 = performance.now(); device.queue.submit([enc.finish()]);
  await idStaging.mapAsync(GPUMapMode.READ); const ids = new Uint32Array(idStaging.getMappedRange().slice(0)); idStaging.unmap();
  if (DEBUG_LAYERS && position === promptIds.length - 1) { await debugDump(); const oom = await device.popErrorScope(); const val = await device.popErrorScope(); console.error("scopes", oom?.message, val?.message); Deno.exit(0); }
  return {next: ids[finalBG.parts], ms: performance.now() - t0};
}

// ---------------- profile mode ----------------
if (Deno.env.get("NEX_PROFILE")) {
  const variants = [null, "kdot", "moe", "lmhead", "ops", "none"]; const out = {gpu: adapter.info?.description};
  for (const v of variants) { PROFILE_ONLY = v; dispatchCount = 0; await step(760, 0); const ms = []; for (let i = 0; i < 5; i++) { dispatchCount = 0; ms.push((await step(760, i + 1)).ms); } ms.sort((a, b) => a - b); out[v ?? "all"] = {medianMs: +ms[2].toFixed(1), minMs: +ms[0].toFixed(1), dispatches: dispatchCount}; }
  console.log(JSON.stringify(out)); Deno.exit(0);
}
// ---------------- GPU-only time: N prompt tokens in ONE command buffer ----------------
// The single-token step pays a host submit -> mapAsync round trip (~14 ms on Deno/wgpu). Prompt
// tokens are known in advance, so they can be recorded back to back in one command buffer with each
// token's embedding copied in from a staging buffer; the per-token GPU time is then (total)/N.
if (Deno.env.get("NEX_GPU_TIME")) {
  const N = promptIds.length; const embStage = f32buf(N * E);
  for (let i = 0; i < N; i++) device.queue.writeBuffer(embStage, i * E * 4, await embedRow(promptIds[i]));
  for (const L of layers) if (!L.recr) { setOpsMeta(L.attnMeta, H.headDim, H.nHead, N, H.nHeadKv, -1.0, 1 / Math.sqrt(H.headDim)); } // attention over the full prompt (approximation for timing only)
  const runN = async () => {
    const enc = device.createCommandEncoder();
    for (let i = 0; i < N; i++) { enc.copyBufferToBuffer(embStage, i * E * 4, A.x, 0, E * 4); encodeToken(enc, i); }
    const t0 = performance.now(); device.queue.submit([enc.finish()]); await idStaging.mapAsync(GPUMapMode.READ); idStaging.unmap(); return performance.now() - t0;
  };
  await runN(); const ms = []; for (let i = 0; i < 5; i++) ms.push(await runN()); ms.sort((a, b) => a - b);
  const one = []; for (let i = 0; i < 3; i++) one.push((await step(promptIds[0], 0)).ms); one.sort((a, b) => a - b);
  console.log(JSON.stringify({gpu: adapter.info?.description, backend, tokensPerCommandBuffer: N, msPerCommandBuffer: +ms[2].toFixed(1), gpuMsPerToken: +(ms[2] / N).toFixed(1), singleTokenMs: +one[1].toFixed(1), hostFloorMsEstimate: +(one[1] - ms[2] / N).toFixed(1), "gpu-tok/s": +(1000 / (ms[2] / N)).toFixed(1)}));
  Deno.exit(0);
}
// ---------------- run ----------------
const generated = []; const times = [];
let position = 0; let next = null;
for (const id of promptIds) { const r = await step(id, position++); next = r.next; times.push(r.ms); }
log(`prompt ${promptIds.length} tokens processed, first prediction ${next}`);
for (let i = 0; i < nPredict; i++) { generated.push(next); const r = await step(next, position++); next = r.next; times.push(r.ms); }
const oom = await device.popErrorScope(); const validation = await device.popErrorScope();
if (oom) console.error("OUT OF MEMORY:", oom.message);
const sorted = [...times].sort((a, b) => a - b);
const report = {gpu: adapter.info?.description, model: modelPath.split("/").pop(), weightsGB: +(uploaded / 1e9).toFixed(2), promptIds, generated, expected, match: expected ? generated.slice(0, expected.length).filter((v, i) => v === expected[i]).length + "/" + Math.min(expected.length, generated.length) : "no expected given", msPerToken: {median: +sorted[Math.floor(sorted.length / 2)].toFixed(1), min: +sorted[0].toFixed(1)}, "tok/s@median": +(1000 / sorted[Math.floor(sorted.length / 2)]).toFixed(2), validation: validation?.message, submitsPerToken: 1};
console.log(JSON.stringify(report));
if (validation) Deno.exit(1);
