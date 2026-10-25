// Parity of shaders/nex_ops.wgsl (the small per-token ops of a qwen35moe decode step) against
// f64 JS references of the llama.cpp graph semantics, at Nex-N2.5-mini shapes. Root ADR-2609182100 D1.
//   deno run --unstable-webgpu --allow-read verify/nex_ops_parity.js
const here = new URL("./", import.meta.url);
const code = await Deno.readTextFile(new URL("../shaders/nex_ops.wgsl", here));
const adapter = await navigator.gpu.requestAdapter(); if (!adapter) throw new Error("no adapter");
const device = await adapter.requestDevice(); device.pushErrorScope("validation");
const module = device.createShaderModule({code});
// one explicit layout with all seven bindings, so every entry point takes the same bind group shape
const bgl = device.createBindGroupLayout({entries: [
  {binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: {type: "uniform"}},
  {binding: 1, visibility: GPUShaderStage.COMPUTE, buffer: {type: "read-only-storage"}},
  {binding: 2, visibility: GPUShaderStage.COMPUTE, buffer: {type: "read-only-storage"}},
  {binding: 3, visibility: GPUShaderStage.COMPUTE, buffer: {type: "read-only-storage"}},
  {binding: 4, visibility: GPUShaderStage.COMPUTE, buffer: {type: "storage"}},
  {binding: 5, visibility: GPUShaderStage.COMPUTE, buffer: {type: "storage"}},
  {binding: 6, visibility: GPUShaderStage.COMPUTE, buffer: {type: "storage"}}]});
const layout = device.createPipelineLayout({bindGroupLayouts: [bgl]});
const pipes = {}; for (const e of ["rmsnorm","l2norm","gated_rmsnorm","silu_mul","conv1d_step","softmax_topk","gate_decay","weighted_sum","rope_neox","attn_decode","argmax_partial","argmax_final","add","f32_matvec","add_rmsnorm"]) pipes[e] = device.createComputePipeline({layout, compute: {module, entryPoint: e}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST, UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const fbuf = (arr) => { const b = device.createBuffer({size: Math.max(16, arr.byteLength), usage: SU}); device.queue.writeBuffer(b, 0, arr); return b; };
const meta = (n, rows, aux, aux2, eps, scale) => { const b = device.createBuffer({size: 32, usage: UU}); const u = new ArrayBuffer(32), dv = new DataView(u); dv.setUint32(0, n, true); dv.setUint32(4, rows, true); dv.setUint32(8, aux, true); dv.setUint32(12, aux2, true); dv.setFloat32(16, eps, true); dv.setFloat32(20, scale, true); device.queue.writeBuffer(b, 0, u); return b; };
async function read(b, n, u32 = false) { const st = device.createBuffer({size: n * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ}); const e = device.createCommandEncoder(); e.copyBufferToBuffer(b, 0, st, 0, n * 4); device.queue.submit([e.finish()]); await st.mapAsync(GPUMapMode.READ); const r = st.getMappedRange().slice(0); st.unmap(); return u32 ? new Uint32Array(r) : new Float32Array(r); }
async function run(entry, bufs, groups) {
  const bg = device.createBindGroup({layout: bgl, entries: bufs.map((b, i) => ({binding: i, resource: {buffer: b}}))});
  const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(pipes[entry]); p.setBindGroup(0, bg); p.dispatchWorkgroups(...groups); p.end();
  const t0 = performance.now(); device.queue.submit([e.finish()]); await device.queue.onSubmittedWorkDone(); return performance.now() - t0;
}
let seed = 5; const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 2 ** 32; };
const gauss = (sd = 1) => Math.fround((rnd() + rnd() + rnd() + rnd() - 2) * sd);
const F = (n, f = () => gauss()) => Float32Array.from({length: n}, f);
const cmp = (got, ref, name, tol = {abs: 1e-5, rel: 1e-5}) => { let worst = 0, wi = 0; for (let i = 0; i < ref.length; i++) { const ex = Math.abs(got[i] - ref[i]) - tol.rel * Math.abs(ref[i]); if (ex > worst) { worst = ex; wi = i; } } return {name, excess: +worst.toPrecision(3), pass: worst <= tol.abs, sample: [got[wi], ref[wi]]}; };
const report = {gpu: adapter.info?.description}; const results = [];
// one distinct placeholder per slot: a buffer bound read-only and read-write in the same dispatch is a usage conflict
const dummy = fbuf(new Float32Array(4)), dummy2 = fbuf(new Float32Array(4)), dummy3 = fbuf(new Float32Array(4)), dummyS = fbuf(new Float32Array(4)), dummyU = device.createBuffer({size: 16, usage: SU});
const EPS = 1e-6;

// rmsnorm: 2048 hidden ; per-head norm 16 x 256
{ const x = F(2048), w = F(2048, () => Math.fround(0.5 + rnd())); const ob = fbuf(new Float32Array(2048));
  await run("rmsnorm", [meta(2048, 1, 0, 0, EPS, 0), fbuf(x), fbuf(w), dummy3, ob, dummyS, dummyU], [1, 1, 1]);
  const ss = x.reduce((a, v) => a + v * v, 0) / 2048; const ref = x.map((v, i) => v / Math.sqrt(ss + EPS) * w[i]);
  results.push(cmp(await read(ob, 2048), ref, "rmsnorm 2048")); }
// l2norm: 16 heads x 128
{ const x = F(16 * 128); const ob = fbuf(new Float32Array(16 * 128));
  await run("l2norm", [meta(128, 16, 0, 0, EPS, 0), fbuf(x), dummy2, dummy3, ob, dummyS, dummyU], [16, 1, 1]);
  const ref = new Float64Array(16 * 128); for (let h = 0; h < 16; h++) { let ss = 0; for (let i = 0; i < 128; i++) ss += x[h * 128 + i] ** 2; for (let i = 0; i < 128; i++) ref[h * 128 + i] = x[h * 128 + i] / Math.sqrt(ss + EPS); }
  results.push(cmp(await read(ob, 16 * 128), ref, "l2norm 16x128")); }
// gated rmsnorm: 32 heads x 128, weight [128], z [32x128]
{ const x = F(32 * 128), w = F(128, () => Math.fround(0.5 + rnd())), z = F(32 * 128); const ob = fbuf(new Float32Array(32 * 128));
  await run("gated_rmsnorm", [meta(128, 32, 0, 0, EPS, 0), fbuf(x), fbuf(w), fbuf(z), ob, dummyS, dummyU], [32, 1, 1]);
  const silu = (v) => v / (1 + Math.exp(-v)); const ref = new Float64Array(32 * 128);
  for (let h = 0; h < 32; h++) { let ss = 0; for (let i = 0; i < 128; i++) ss += x[h * 128 + i] ** 2; ss /= 128; for (let i = 0; i < 128; i++) ref[h * 128 + i] = x[h * 128 + i] / Math.sqrt(ss + EPS) * w[i] * silu(z[h * 128 + i]); }
  results.push(cmp(await read(ob, 32 * 128), ref, "gated_rmsnorm 32x128")); }
// silu_mul 512
{ const g = F(512), u = F(512); const ob = fbuf(new Float32Array(512));
  await run("silu_mul", [meta(512, 1, 0, 0, 0, 0), fbuf(g), fbuf(u), dummy3, ob, dummyS, dummyU], [2, 1, 1]);
  results.push(cmp(await read(ob, 512), g.map((v, i) => v / (1 + Math.exp(-v)) * u[i]), "silu_mul 512")); }
// conv1d_step: 8192 channels, kernel 4, ring of 3, two steps
{ const n = 8192; const K = F(4 * n, () => gauss(0.3)); const ring = F(3 * n); const x1 = F(n), x2 = F(n);
  const sb = fbuf(ring), ob = fbuf(new Float32Array(n)); const Kb = fbuf(K);
  await run("conv1d_step", [meta(n, 1, 0, 0, 0, 0), fbuf(x1), Kb, dummy3, ob, sb, dummyU], [Math.ceil(n / 256), 1, 1]);
  const ms = await run("conv1d_step", [meta(n, 1, 0, 0, 0, 0), fbuf(x2), Kb, dummy3, ob, sb, dummyU], [Math.ceil(n / 256), 1, 1]);
  // reference of step 2: inputs = ring[1], ring[2], x1, x2
  const ref = new Float64Array(n); for (let c = 0; c < n; c++) { const y = K[c * 4] * ring[n + c] + K[c * 4 + 1] * ring[2 * n + c] + K[c * 4 + 2] * x1[c] + K[c * 4 + 3] * x2[c]; ref[c] = y / (1 + Math.exp(-y)); }
  results.push({...cmp(await read(ob, n), ref, "conv1d_step 8192 (2nd step, ring shifted)"), ms: +ms.toFixed(3)}); }
// softmax_topk: 256 logits -> top 8 normalised
{ const lg = F(256, () => gauss(2)); const ob = fbuf(new Float32Array(8)), ib = device.createBuffer({size: 32, usage: SU});
  await run("softmax_topk", [meta(256, 1, 8, 0, 0, 1.0), fbuf(lg), dummy2, dummy3, ob, dummyS, ib], [1, 1, 1]);
  const m = Math.max(...lg); const e = Array.from(lg, (v) => Math.exp(v - m)); const Z = e.reduce((a, v) => a + v, 0); const p = e.map((v) => v / Z);
  const order = p.map((v, i) => [v, i]).sort((x, y) => y[0] - x[0] || x[1] - y[1]).slice(0, 8); const wsum = order.reduce((a, v) => a + v[0], 0);
  const gotIds = Array.from(await read(ib, 8, true)), gotW = await read(ob, 8);
  const idsOk = order.every((v, i) => v[1] === gotIds[i]);
  results.push({...cmp(gotW, order.map((v) => v[0] / wsum), "softmax_topk weights"), idsMatch: idsOk, pass: idsOk && cmp(gotW, order.map((v) => v[0] / wsum), "").pass, ids: gotIds}); }
// gate_decay: 32 heads
{ const xa = F(32), dt = F(32), A = F(32, () => -Math.exp(gauss())), xb = F(32); const ob = fbuf(new Float32Array(96)); const ab = fbuf(Float32Array.from([...xa, ...new Float32Array(32), ...xb]));
  await run("gate_decay", [meta(0, 32, 64, 64, 0, 0), ab, fbuf(dt), fbuf(A), ob, dummyS, dummyU], [1, 1, 1]);
  const all = await read(ob, 96); const got = Float32Array.from([...all.slice(0, 32), ...all.slice(64, 96)]); const ref = new Float64Array(64); for (let h = 0; h < 32; h++) { ref[h] = Math.log1p(Math.exp(xa[h] + dt[h])) * A[h]; ref[32 + h] = 1 / (1 + Math.exp(-xb[h])); }
  results.push(cmp(got, ref, "gate_decay 32 (g, beta at aux)")); }
// weighted_sum: 8 experts x 2048 + shared
{ const eo = F(8 * 2048), w = F(8, () => rnd()), sh = F(2048), gl = F(1); const ob = fbuf(new Float32Array(2048));
  await run("weighted_sum", [meta(2048, 1, 8, 0, 0, 0), fbuf(eo), fbuf(w), fbuf(sh), ob, fbuf(gl), dummyU], [8, 1, 1]);
  const ref = new Float64Array(2048); for (let i = 0; i < 2048; i++) { let acc = 0; for (let e = 0; e < 8; e++) acc += w[e] * eo[e * 2048 + i]; ref[i] = acc + sh[i] / (1 + Math.exp(-gl[0])); }
  results.push(cmp(await read(ob, 2048), ref, "weighted_sum 8x2048 + shexp")); }
// rope_neox: 16 heads x 256, n_rot 64, pos 37, base 1e7
{ const x = F(16 * 256); const ob = fbuf(new Float32Array(16 * 256)); const pos = 37, nrot = 64, base = 1e7;
  await run("rope_neox", [meta(256, 16, nrot, pos, 0, base), fbuf(x), dummy2, dummy3, ob, dummyS, dummyU], [16, 1, 1]);
  const ref = new Float64Array(16 * 256); for (let h = 0; h < 16; h++) for (let i = 0; i < 256; i++) { const o = h * 256; if (i >= nrot) { ref[o + i] = x[o + i]; continue; } const half = nrot / 2, pair = i >= half ? i - half : i; const th = pos * Math.pow(base, -2 * pair / nrot); const c = Math.cos(th), s_ = Math.sin(th); const x0 = x[o + pair], x1 = x[o + pair + half]; ref[o + i] = i >= half ? x0 * s_ + x1 * c : x0 * c - x1 * s_; }
  results.push(cmp(await read(ob, 16 * 256), ref, "rope_neox 16x256 nrot64", {abs: 1e-4, rel: 1e-4})); }
// attn_decode: 16 heads, 2 kv heads, d 256, T 40
{ const H = 16, HKV = 2, d = 256, T = 40; const q = F(H * d, () => gauss(0.3)), Kc = F(T * HKV * d, () => gauss(0.3)), Vc = F(T * HKV * d), gate = F(H * d); const ob = fbuf(new Float32Array(H * d));
  const ms = await run("attn_decode", [meta(d, H, T, HKV, 0, 1 / Math.sqrt(d)), fbuf(q), fbuf(Kc), fbuf(Vc), ob, fbuf(gate), dummyU], [H, 1, 1]);
  const ref = new Float64Array(H * d); for (let h = 0; h < H; h++) { const hk = Math.floor(h / (H / HKV)); const sc = []; for (let t = 0; t < T; t++) { let dot = 0; for (let i = 0; i < d; i++) dot += q[h * d + i] * Kc[(t * HKV + hk) * d + i]; sc.push(dot / Math.sqrt(d)); } const m = Math.max(...sc); const e = sc.map((v) => Math.exp(v - m)); const Z = e.reduce((a, v) => a + v, 0); for (let i = 0; i < d; i++) { let acc = 0; for (let t = 0; t < T; t++) acc += e[t] / Z * Vc[(t * HKV + hk) * d + i]; ref[h * d + i] = acc / (1 + Math.exp(-gate[h * d + i])); } }
  results.push({...cmp(await read(ob, H * d), ref, "attn_decode 16h/2kv d256 T40", {abs: 2e-5, rel: 2e-5}), ms: +ms.toFixed(3)}); }
// argmax over 248320 logits (two stages)
{ const n = 248320; const lg = F(n, () => gauss(3)); lg[123457] = 50; const parts = Math.ceil(n / 4096); const sb = fbuf(new Float32Array(parts)), ib = device.createBuffer({size: (parts + 1) * 4, usage: SU}), ob = fbuf(new Float32Array(4)); const lb = fbuf(lg);
  const m1 = await run("argmax_partial", [meta(n, 1, parts, 0, 0, 0), lb, dummy2, dummy3, ob, sb, ib], [parts, 1, 1]);
  const m2 = await run("argmax_final", [meta(n, 1, parts, 0, 0, 0), lb, dummy2, dummy3, ob, sb, ib], [1, 1, 1]);
  const got = (await read(ib, parts + 1, true))[parts]; let ref = 0; for (let i = 1; i < n; i++) if (lg[i] > lg[ref]) ref = i;
  results.push({name: "argmax 248320", got, ref, pass: got === ref, ms: +(m1 + m2).toFixed(3)}); }
// add 2048
{ const x = F(2048), y = F(2048); const ob = fbuf(new Float32Array(2048));
  await run("add", [meta(2048, 1, 0, 0, 0, 0), fbuf(x), fbuf(y), dummy3, ob, dummyS, dummyU], [8, 1, 1]);
  results.push(cmp(await read(ob, 2048), x.map((v, i) => v + y[i]), "add 2048")); }
// f32_matvec: router [256 x 2048]
{ const w = F(256 * 2048, () => gauss(0.05)), x = F(2048); const ob = fbuf(new Float32Array(256));
  await run("f32_matvec", [meta(2048, 256, 0, 0, 0, 0), fbuf(w), fbuf(x), dummy3, ob, dummyS, dummyU], [256, 1, 1]);
  const ref = new Float64Array(256); for (let r = 0; r < 256; r++) { let acc = 0; for (let i = 0; i < 2048; i++) acc += w[r * 2048 + i] * x[i]; ref[r] = acc; }
  results.push(cmp(await read(ob, 256), ref, "f32_matvec 256x2048", {abs: 2e-5, rel: 2e-5})); }
// strided rmsnorm: 16 heads of 256 at stride 512 (q_full layout)
{ const x = F(16 * 512), w = F(256, () => Math.fround(0.5 + rnd())); const ob = fbuf(new Float32Array(16 * 256));
  await run("rmsnorm", [meta(256, 16, 512, 0, EPS, 0), fbuf(x), fbuf(w), dummy3, ob, dummyS, dummyU], [16, 1, 1]);
  const ref = new Float64Array(16 * 256); for (let h = 0; h < 16; h++) { let ss = 0; for (let i = 0; i < 256; i++) ss += x[h * 512 + i] ** 2; ss /= 256; for (let i = 0; i < 256; i++) ref[h * 256 + i] = x[h * 512 + i] / Math.sqrt(ss + EPS) * w[i]; }
  results.push(cmp(await read(ob, 16 * 256), ref, "rmsnorm strided 16x256@512")); }
// add_rmsnorm 2048
{ const x = F(2048), d = F(2048), w = F(2048, () => Math.fround(0.5 + rnd())); const ob = fbuf(new Float32Array(2048)), sb = fbuf(new Float32Array(2048));
  await run("add_rmsnorm", [meta(2048, 1, 0, 0, EPS, 0), fbuf(x), fbuf(d), fbuf(w), ob, sb, dummyU], [1, 1, 1]);
  const sum = x.map((v, i) => v + d[i]); const ss = sum.reduce((a, v) => a + v * v, 0) / 2048; const ref = sum.map((v, i) => v / Math.sqrt(ss + EPS) * w[i]);
  results.push(cmp(await read(ob, 2048), sum, "add_rmsnorm sum")); results.push(cmp(await read(sb, 2048), ref, "add_rmsnorm norm")); }
const validation = await device.popErrorScope(); if (validation) report.validation = validation.message;
report.results = results; report["kotodama/nex-ops-parity"] = results.every((r) => r.pass) && !validation ? "ok" : "FAIL";
console.log(JSON.stringify(report));
if (report["kotodama/nex-ops-parity"] !== "ok") Deno.exit(1);
