// Parity of shaders/q8k_quantize.wgsl against a JS port of ggml quantize_row_q8_K_ref,
// then the chain x -> GPU q8 -> ggml_kdot_wg vs x -> JS q8 -> ggml_kdot_wg (must be
// identical bytes => identical dot). Root ADR-2609182100 D1 / co-scientist iteration 2.
//   deno run --unstable-webgpu --allow-read verify/q8k_quantize_parity.js [rows] [blocks]
const here = new URL("./", import.meta.url);
const qShader = await Deno.readTextFile(new URL("../shaders/q8k_quantize.wgsl", here));
const kShader = await Deno.readTextFile(new URL("../shaders/ggml_kdot_wg.wgsl", here));
const rows = Number(Deno.args[0] ?? 3), blocks = Number(Deno.args[1] ?? 10), cols = blocks * 256;
const adapter = await navigator.gpu.requestAdapter(); if (!adapter) throw new Error("no adapter");
const device = await adapter.requestDevice(); device.pushErrorScope("validation");
const pipe = (code) => device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code}), entryPoint: "main"}});
const qPipe = pipe(qShader), kPipe = pipe(kShader);
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST, UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const buf = (data, usage) => { const size = Math.max(16, Math.ceil(data.byteLength / 4) * 4); const b = device.createBuffer({size, usage}); const u = new Uint8Array(size); u.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength)); device.queue.writeBuffer(b, 0, u); return b; };
async function read(b, bytes) { const st = device.createBuffer({size: bytes, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ}); const e = device.createCommandEncoder(); e.copyBufferToBuffer(b, 0, st, 0, bytes); device.queue.submit([e.finish()]); await st.mapAsync(GPUMapMode.READ); const out = st.getMappedRange().slice(0); st.unmap(); return new Uint8Array(out); }

// --- JS reference (ggml quantize_row_q8_K_ref, f32 arithmetic via Math.fround) ---
const nearestEven = (v) => { const r = Math.round(v); return Math.abs(v % 1) === 0.5 ? 2 * Math.round(v / 2) : r; };
function q8kRef(x /* Float32Array, length blocks*256 per row */, nrows) {
  const out = new Uint8Array(nrows * blocks * 292), dv = new DataView(out.buffer);
  for (let r = 0; r < nrows; r++) for (let b = 0; b < blocks; b++) {
    const o = (r * blocks + b) * 292, xo = (r * blocks + b) * 256;
    let amax = 0, max = 0;
    for (let j = 0; j < 256; j++) { const ax = Math.abs(x[xo + j]); if (ax > amax) { amax = ax; max = x[xo + j]; } }
    if (amax === 0) continue; // zeros
    const iscale = Math.fround(-127 / max);
    const qs = new Int8Array(256);
    for (let j = 0; j < 256; j++) qs[j] = Math.min(127, nearestEven(Math.fround(iscale * x[xo + j])));
    for (let j = 0; j < 256; j++) out[o + 4 + j] = qs[j] & 255;
    for (let g = 0; g < 16; g++) { let s = 0; for (let l = 0; l < 16; l++) s += qs[g * 16 + l]; dv.setInt16(o + 260 + g * 2, s, true); }
    dv.setFloat32(o, Math.fround(1 / iscale), true);
  }
  return out;
}
// activations: gaussian-ish via LCG, plus one all-zero block and one block with a tie at exactly .5 after scaling
let seed = 42; const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 2 ** 32; };
const x = new Float32Array(rows * cols);
for (let i = 0; i < x.length; i++) x[i] = Math.fround((rnd() + rnd() + rnd() - 1.5) * 2.3);
for (let j = 0; j < 256; j++) x[256 + j] = 0;                 // row 0, block 1: all zeros
const ref = q8kRef(x, rows);

// --- GPU ---
const meta = buf(new Uint32Array([blocks, rows, 0, 0]), UU), xb = buf(x, SU), q8b = buf(new Uint8Array(rows * blocks * 292), SU);
const bg = device.createBindGroup({layout: qPipe.getBindGroupLayout(0), entries: [meta, xb, q8b].map((b, i) => ({binding: i, resource: {buffer: b}}))});
{ const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(qPipe); p.setBindGroup(0, bg); p.dispatchWorkgroups(blocks, rows, 1); p.end(); device.queue.submit([e.finish()]); }
const gpu = await read(q8b, rows * blocks * 292);
let qsMismatch = 0, qsOff1 = 0, dMismatch = 0, bsumMismatch = 0, dUlpMax = 0;
const gv = new DataView(gpu.buffer), rv = new DataView(ref.buffer);
for (let b = 0; b < rows * blocks; b++) {
  const o = b * 292;
  { const a = gv.getFloat32(o, true), c = rv.getFloat32(o, true); if (a !== c) { dMismatch++; const ulp = Math.abs(gv.getUint32(o, true) - rv.getUint32(o, true)); if (ulp > dUlpMax) dUlpMax = ulp; } }
  for (let j = 0; j < 256; j++) { const a = (gpu[o + 4 + j] << 24) >> 24, c = (ref[o + 4 + j] << 24) >> 24; if (a !== c) { qsMismatch++; if (Math.abs(a - c) === 1) qsOff1++; } }
  for (let g = 0; g < 16; g++) if (gv.getInt16(o + 260 + g * 2, true) !== rv.getInt16(o + 260 + g * 2, true)) bsumMismatch++;
}
// --- chain: kdot_wg on GPU-quantised vs JS-quantised input, same Q4_K weights ---
const q4Unit = Uint8Array.from("f516b322fefdfffdfdfefcffeeceefcf4095ea4f94e93e84d92e83d82d73c81d62b71c61b60b51a6fb50a5fa4f95ea3fd82d72c71c62c71c61b60b51a6fb50a5fa4f94e93e94e93e83d82d73c82d72c751a6fb4095ea4f95ea3f84d92e74c92e73c81d62b71c62b70c51a6fb41a6fb40d92e73c82d73c81d62b71c62b70c51a6fb4196eb4095ea3f84d93e84d92e73c8".match(/../g), h => parseInt(h, 16));
const wrows = 512; const w = new Uint8Array(wrows * blocks * 144); for (let i = 0; i < wrows * blocks; i++) { w.set(q4Unit, i * 144); w[i * 144 + 16 + (i % 128)] ^= (i * 37) & 255; }
async function kdot(q8bytes) {
  const m = buf(new Uint32Array([wrows, cols, 12, rows]), UU), wb = buf(w, SU), ib = buf(q8bytes, SU), ob = buf(new Float32Array(wrows * rows), SU);
  const g = device.createBindGroup({layout: kPipe.getBindGroupLayout(0), entries: [m, wb, ib, ob].map((b, i) => ({binding: i, resource: {buffer: b}}))});
  const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(kPipe); p.setBindGroup(0, g); p.dispatchWorkgroups(wrows, rows, 1); p.end(); device.queue.submit([e.finish()]);
  return new Float32Array((await read(ob, wrows * rows * 4)).buffer);
}
const dotGpu = await kdot(gpu), dotRef = await kdot(ref);
let dotMaxAbs = 0; for (let i = 0; i < dotGpu.length; i++) dotMaxAbs = Math.max(dotMaxAbs, Math.abs(dotGpu[i] - dotRef[i]));
// timing: quantise a 10240-wide row (40 blocks) x rows, 21 dispatches in one buffer
const tm = buf(new Uint32Array([40, rows, 0, 0]), UU), tx = buf(new Float32Array(rows * 40 * 256).map(() => rnd()), SU), tq = buf(new Uint8Array(rows * 40 * 292), SU);
const tg = device.createBindGroup({layout: qPipe.getBindGroupLayout(0), entries: [tm, tx, tq].map((b, i) => ({binding: i, resource: {buffer: b}}))});
async function tq8(K) { const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(qPipe); p.setBindGroup(0, tg); for (let i = 0; i < K; i++) p.dispatchWorkgroups(40, rows, 1); p.end(); const t0 = performance.now(); device.queue.submit([e.finish()]); await device.queue.onSubmittedWorkDone(); return performance.now() - t0; }
await tq8(1); const one = Math.min(await tq8(1), await tq8(1), await tq8(1)), many = Math.min(await tq8(201), await tq8(201), await tq8(201));
const validation = await device.popErrorScope();
// d: GPU f32 division is not required to be correctly rounded -- Vulkan permits 2.5 ulp, Metal ~1 --
// so d may differ from C's IEEE 1/iscale by up to 2 ulp (measured: Metal 1, Intel ANV 2, AMD RADV 2).
// qs and bsums must be exact; the chain dot then differs by at most those ulps times the block sums.
let dotWorst = 0; for (let i = 0; i < dotGpu.length; i++) dotWorst = Math.max(dotWorst, Math.abs(dotGpu[i] - dotRef[i]) - 1e-5 * Math.abs(dotRef[i]));
const ok = qsMismatch === 0 && bsumMismatch === 0 && dUlpMax <= 2 && dotWorst <= 1e-4 && !validation;
const report = {gpu: adapter.info?.description, rows, blocks, qsMismatch, qsOff1, dMismatch, bsumMismatch, chainDotMaxAbs: dotMaxAbs, chainDotExcessOverTol: +dotWorst.toPrecision(3), dUlpMax, validation: validation?.message, "kotodama/q8k-quantize-parity": ok ? "ok" : "FAIL"};
report["quantise-10240x" + rows + "-perDispatchMs"] = +((many - one) / 200).toFixed(4);
console.log(JSON.stringify(report));
if (!ok) Deno.exit(1);
