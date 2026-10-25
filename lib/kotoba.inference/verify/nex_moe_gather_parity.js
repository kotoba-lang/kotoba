// Real-Nex MoE expert-gather parity: shaders/ggml_kdot_moe.wgsl on the packed
// blk.0.ffn_gate_exps.weight [2048 x 512 x 256] IQ4_XS cut from the served
// GGUF, eight selected experts read from a GPU buffer, against the JS port of
// ggml_vec_dot_iq4_xs_q8_K_generic on each expert's own slice. Root
// ADR-2609182100 D1 / co-scientist iteration 2 hypothesis N3.
//
//   deno run --unstable-webgpu --allow-read verify/nex_moe_gather_parity.js <ffn_gate_exps.iq4xs.bin>
const here = new URL("./", import.meta.url);
const shader = await Deno.readTextFile(new URL("../shaders/ggml_kdot_moe.wgsl", here));
const [path] = Deno.args; if (!path) { console.error("usage: nex_moe_gather_parity.js <ffn_gate_exps.iq4xs.bin>"); Deno.exit(2); }
const w = await Deno.readFile(path);
const COLS = 2048, ROWS = 512, EXPERTS = 256, BLOCKS = 8, BB = 136;
if (w.byteLength !== EXPERTS * ROWS * BLOCKS * BB) throw new Error(`size ${w.byteLength} != ${EXPERTS * ROWS * BLOCKS * BB}`);

const adapter = await navigator.gpu.requestAdapter(); if (!adapter) throw new Error("no adapter");
const device = await adapter.requestDevice({requiredLimits: {maxStorageBufferBindingSize: Math.min(adapter.limits.maxStorageBufferBindingSize, 1 << 30), maxBufferSize: Math.min(adapter.limits.maxBufferSize, 1 << 30)}});
device.pushErrorScope("validation");
const pipeline = device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code: shader}), entryPoint: "main"}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST, UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const buf = (data, usage) => { const size = Math.max(16, Math.ceil(data.byteLength / 4) * 4); const b = device.createBuffer({size, usage}); const u = new Uint8Array(size); u.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength)); device.queue.writeBuffer(b, 0, u); return b; };

let seed = 11; const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 2 ** 32; };
const nearestEven = (v) => { const r = Math.round(v); return Math.abs(v % 1) === 0.5 ? 2 * Math.round(v / 2) : r; };
function q8k(x) {
  const nb = x.length / 256, out = new Uint8Array(nb * 292), dv = new DataView(out.buffer);
  for (let b = 0; b < nb; b++) {
    let amax = 0, max = 0; for (let j = 0; j < 256; j++) { const ax = Math.abs(x[b * 256 + j]); if (ax > amax) { amax = ax; max = x[b * 256 + j]; } }
    const iscale = Math.fround(-127 / max); const qs = new Int8Array(256);
    for (let j = 0; j < 256; j++) qs[j] = Math.min(127, nearestEven(Math.fround(iscale * x[b * 256 + j])));
    for (let j = 0; j < 256; j++) out[b * 292 + 4 + j] = qs[j] & 255;
    for (let g = 0; g < 16; g++) { let s = 0; for (let l = 0; l < 16; l++) s += qs[g * 16 + l]; dv.setInt16(b * 292 + 260 + g * 2, s, true); }
    dv.setFloat32(b * 292, Math.fround(1 / iscale), true);
  }
  return out;
}
const f16 = (u) => { const s = (u >> 15) & 1, e = (u >> 10) & 31, m = u & 1023; if (e === 0) return (s ? -1 : 1) * m * 2 ** -24; if (e === 31) return m ? NaN : (s ? -Infinity : Infinity); return (s ? -1 : 1) * (1 + m / 1024) * 2 ** (e - 15); };
const KV = [-127, -104, -83, -65, -49, -35, -22, -10, 1, 13, 25, 38, 53, 69, 89, 113];
// reference dot of one packed row against one q8 row (both byte offsets)
function dotIq4xs(wOff, y, yOff) {
  const yv = new DataView(y.buffer, y.byteOffset); let sumf = 0;
  for (let ibl = 0; ibl < BLOCKS; ibl++) {
    const o = wOff + ibl * BB, dv = new DataView(w.buffer, w.byteOffset + o, BB), yo = yOff + ibl * 292;
    const d4d8 = Math.fround(f16(dv.getUint16(0, true)) * yv.getFloat32(yo, true)); let h = dv.getUint16(2, true);
    let qs = 8, q8o = 0;
    const q8 = (j) => (y[yo + 4 + j] << 24) >> 24;
    for (let ib = 0; ib < 8; ib += 2) {
      const sl = w[o + 4 + (ib >> 1)];
      const ls1 = (sl & 0xf) | ((h << 4) & 0x30), ls2 = (sl >> 4) | ((h << 2) & 0x30); h >>= 4;
      const d1 = Math.fround(d4d8 * (ls1 - 32)), d2 = Math.fround(d4d8 * (ls2 - 32));
      let s1 = 0, s2 = 0;
      for (let j = 0; j < 16; j++) { s1 += q8(q8o + j) * KV[w[o + qs + j] & 0xf]; s2 += q8(q8o + 16 + j) * KV[w[o + qs + j] >> 4]; }
      sumf = Math.fround(sumf + Math.fround(d1 * (s1 + s2))); qs += 16; q8o += 32; s1 = 0; s2 = 0;
      for (let j = 0; j < 16; j++) { s1 += q8(q8o + j) * KV[w[o + qs + j] & 0xf]; s2 += q8(q8o + 16 + j) * KV[w[o + qs + j] >> 4]; }
      sumf = Math.fround(sumf + Math.fround(d2 * (s1 + s2))); qs += 16; q8o += 32;
    }
  }
  return sumf;
}

// eight distinct experts, including 0 and 255 (first/last slice) and a middle spread
const experts = new Uint32Array([0, 255, 7, 64, 128, 199, 31, 250]);
const N = experts.length;
// case A: shared input (gate/up shape) ; case B: per-expert input (down shape would be 512 cols -- here we
// exercise the addressing on the same tensor with 8 different 2048-wide inputs)
const xShared = new Float32Array(COLS); for (let i = 0; i < COLS; i++) xShared[i] = Math.fround((rnd() + rnd() + rnd() - 1.5) * 1.7);
const yShared = q8k(xShared);
const yPer = new Uint8Array(N * BLOCKS * 292); for (let e = 0; e < N; e++) { const xe = new Float32Array(COLS); for (let i = 0; i < COLS; i++) xe[i] = Math.fround((rnd() + rnd() + rnd() - 1.5) * 1.3); yPer.set(q8k(xe), e * BLOCKS * 292); }

const wb = buf(w, SU), idb = buf(experts, SU);
async function run(y, perExpert) {
  const meta = buf(new Uint32Array([ROWS, COLS, 23, N, perExpert ? 1 : 0, 0, 0, 0]), UU), ib = buf(y, SU), ob = buf(new Float32Array(N * ROWS), SU);
  const bg = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [meta, wb, ib, ob, idb].map((b, i) => ({binding: i, resource: {buffer: b}}))});
  const enc = async (K, readback) => {
    const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(pipeline); p.setBindGroup(0, bg);
    for (let i = 0; i < K; i++) p.dispatchWorkgroups(ROWS, N, 1); p.end();
    let st; if (readback) { st = device.createBuffer({size: N * ROWS * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ}); e.copyBufferToBuffer(ob, 0, st, 0, N * ROWS * 4); }
    const t0 = performance.now(); device.queue.submit([e.finish()]);
    if (readback) { await st.mapAsync(GPUMapMode.READ); const out = new Float32Array(st.getMappedRange().slice(0)); st.unmap(); return {out}; }
    await device.queue.onSubmittedWorkDone(); return {ms: performance.now() - t0};
  };
  const {out} = await enc(1, true);
  await enc(1, false); const one = Math.min((await enc(1, false)).ms, (await enc(1, false)).ms), many = Math.min((await enc(21, false)).ms, (await enc(21, false)).ms);
  const perDispatch = (many - one) / 20, bytes = N * ROWS * BLOCKS * BB;
  return {out, perDispatchMs: +perDispatch.toFixed(3), "GB/s": +((bytes / 1e9) / (perDispatch / 1000)).toFixed(1), streamedMB: +(bytes / 1e6).toFixed(1)};
}
function compare(out, y, perExpert) {
  let worst = 0, maxAbs = 0, sample = null;
  for (let e = 0; e < N; e++) for (let r = 0; r < ROWS; r++) {
    const ref = dotIq4xs((experts[e] * ROWS + r) * BLOCKS * BB, y, perExpert ? e * BLOCKS * 292 : 0);
    const got = out[e * ROWS + r], d = Math.abs(got - ref), excess = d - 1e-5 * Math.abs(ref);
    if (d > maxAbs) maxAbs = d; if (excess > worst) { worst = excess; sample = {e, expert: experts[e], r, ref, got}; }
  }
  return {maxAbs: +maxAbs.toPrecision(3), excessOverTol: +worst.toPrecision(3), sample, pass: worst <= 1e-4};
}
const report = {gpu: adapter.info?.description ?? "unknown", experts: Array.from(experts)};
{ const r = await run(yShared, false); report["gate/up shape (shared input, 8 experts x 512 rows)"] = {...compare(r.out, yShared, false), perDispatchMs: r.perDispatchMs, "GB/s": r["GB/s"], streamedMB: r.streamedMB}; }
{ const r = await run(yPer, true); report["per-expert input (8 inputs x 8 experts)"] = {...compare(r.out, yPer, true), perDispatchMs: r.perDispatchMs, "GB/s": r["GB/s"]}; }
const validation = await device.popErrorScope(); if (validation) report.validation = validation.message;
const ok = Object.values(report).every((v) => typeof v !== "object" || Array.isArray(v) || v.pass) && !validation;
report["kotodama/nex-moe-gather-parity"] = ok ? "ok" : "FAIL";
console.log(JSON.stringify(report));
if (!ok) Deno.exit(1);
