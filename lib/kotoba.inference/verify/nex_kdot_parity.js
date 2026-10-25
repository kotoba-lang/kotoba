// Real-Nex kernel parity: shaders/ggml_kdot_wg.wgsl on tensors cut from the
// orcarouter Nex-N2.5-mini-Uncensored IQ4_XS GGUF (the file 6600hs-1 serves),
// against JS ports of ggml-cpu/quants.c ggml_vec_dot_{iq4_xs,q5_K}_q8_K_generic.
// Root ADR-2609182100, co-scientist iteration 2 hypothesis N2.
//
//   deno run --unstable-webgpu --allow-read verify/nex_kdot_parity.js <attn_gate.iq4xs.bin> <attn_qkv.q5k.bin>
//
// attn_gate.iq4xs.bin  = blk.0.attn_gate.weight  [2048 x 4096] IQ4_XS  (4096 rows x 8 blocks x 136 B)
// attn_qkv.q5k.bin     = blk.0.attn_qkv.weight   [2048 x 8192] Q5_K    (8192 rows x 8 blocks x 176 B)
// Cut with dd from data-offset + tensor offset as printed by verify/gguf_inventory.cljk.
const here = new URL("./", import.meta.url);
const shader = await Deno.readTextFile(new URL("../shaders/ggml_kdot_wg.wgsl", here));
const [gatePath, qkvPath] = Deno.args;
if (!gatePath || !qkvPath) { console.error("usage: nex_kdot_parity.js <attn_gate.iq4xs.bin> <attn_qkv.q5k.bin>"); Deno.exit(2); }
const gate = await Deno.readFile(gatePath), qkv = await Deno.readFile(qkvPath);
const COLS = 2048, BLOCKS = 8;
if (gate.byteLength !== 4096 * BLOCKS * 136) throw new Error(`attn_gate size ${gate.byteLength} != ${4096 * BLOCKS * 136}`);
if (qkv.byteLength !== 8192 * BLOCKS * 176) throw new Error(`attn_qkv size ${qkv.byteLength} != ${8192 * BLOCKS * 176}`);

const adapter = await navigator.gpu.requestAdapter(); if (!adapter) throw new Error("no adapter");
const device = await adapter.requestDevice(); device.pushErrorScope("validation");
const pipeline = device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code: shader}), entryPoint: "main"}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST, UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const buf = (data, usage) => { const size = Math.max(16, Math.ceil(data.byteLength / 4) * 4); const b = device.createBuffer({size, usage}); const u = new Uint8Array(size); u.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength)); device.queue.writeBuffer(b, 0, u); return b; };

// --- Q8_K input (ggml quantize_row_q8_K_ref) from a pseudo-random activation ---
let seed = 7; const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 2 ** 32; };
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
const x = new Float32Array(COLS); for (let i = 0; i < COLS; i++) x[i] = Math.fround((rnd() + rnd() + rnd() - 1.5) * 1.7);
const y = q8k(x); const yv = new DataView(y.buffer);
const q8 = (b, j) => (y[b * 292 + 4 + j] << 24) >> 24, bsum = (b, g) => yv.getInt16(b * 292 + 260 + g * 2, true), yd = (b) => yv.getFloat32(b * 292, true);
const f16 = (u) => { const s = (u >> 15) & 1, e = (u >> 10) & 31, m = u & 1023; if (e === 0) return (s ? -1 : 1) * m * 2 ** -24; if (e === 31) return m ? NaN : (s ? -Infinity : Infinity); return (s ? -1 : 1) * (1 + m / 1024) * 2 ** (e - 15); };

// --- JS reference dots (generic C, f32 accumulation via fround where C uses float) ---
const KV = [-127, -104, -83, -65, -49, -35, -22, -10, 1, 13, 25, 38, 53, 69, 89, 113];
function dotIq4xs(w, row) {
  let sumf = 0;
  for (let ibl = 0; ibl < BLOCKS; ibl++) {
    const o = (row * BLOCKS + ibl) * 136; const dv = new DataView(w.buffer, w.byteOffset + o, 136);
    const d4d8 = Math.fround(f16(dv.getUint16(0, true)) * yd(ibl)); let h = dv.getUint16(2, true);
    let qs = 8, q8o = 0;
    for (let ib = 0; ib < 8; ib += 2) {
      const sl = w[o + 4 + (ib >> 1)];
      const ls1 = (sl & 0xf) | ((h << 4) & 0x30), ls2 = (sl >> 4) | ((h << 2) & 0x30); h >>= 4;
      const d1 = Math.fround(d4d8 * (ls1 - 32)), d2 = Math.fround(d4d8 * (ls2 - 32));
      let s1 = 0, s2 = 0;
      for (let j = 0; j < 16; j++) { s1 += q8(ibl, q8o + j) * KV[w[o + qs + j] & 0xf]; s2 += q8(ibl, q8o + 16 + j) * KV[w[o + qs + j] >> 4]; }
      sumf = Math.fround(sumf + Math.fround(d1 * (s1 + s2))); qs += 16; q8o += 32; s1 = 0; s2 = 0;
      for (let j = 0; j < 16; j++) { s1 += q8(ibl, q8o + j) * KV[w[o + qs + j] & 0xf]; s2 += q8(ibl, q8o + 16 + j) * KV[w[o + qs + j] >> 4]; }
      sumf = Math.fround(sumf + Math.fround(d2 * (s1 + s2))); qs += 16; q8o += 32;
    }
  }
  return sumf;
}
function scaleMinK4(sc, j) { return j < 4 ? [sc[j] & 63, sc[j + 4] & 63] : [(sc[j + 4] & 0xF) | ((sc[j - 4] >> 6) << 4), (sc[j + 4] >> 4) | ((sc[j] >> 6) << 4)]; }
function dotQ5k(w, row) {
  const sums = new Float32Array(8); let sumf = 0;
  for (let i = 0; i < BLOCKS; i++) {
    const o = (row * BLOCKS + i) * 176; const dv = new DataView(w.buffer, w.byteOffset + o, 176);
    const d = Math.fround(f16(dv.getUint16(0, true)) * yd(i)), dmin = Math.fround(f16(dv.getUint16(2, true)) * yd(i));
    const sc = w.subarray(o + 4, o + 16), hm = w.subarray(o + 16, o + 48), q4 = w.subarray(o + 48, o + 176);
    const a = new Int8Array(256); let m = 1, ai = 0;
    for (let j = 0; j < 4; j++) { for (let l = 0; l < 32; l++) a[ai + l] = (q4[j * 32 + l] & 0xF) + ((hm[l] & m) ? 16 : 0); ai += 32; m <<= 1; for (let l = 0; l < 32; l++) a[ai + l] = (q4[j * 32 + l] >> 4) + ((hm[l] & m) ? 16 : 0); ai += 32; m <<= 1; }
    let sumi = 0; for (let j = 0; j < 16; j++) sumi += bsum(i, j) * scaleMinK4(sc, j >> 1)[1];
    const aux32 = new Int32Array(8);
    for (let j = 0; j < 8; j++) { const scale = scaleMinK4(sc, j)[0]; for (let l = 0; l < 32; l++) aux32[l & 7] += scale * q8(i, j * 32 + l) * a[j * 32 + l]; }
    for (let l = 0; l < 8; l++) sums[l] = Math.fround(sums[l] + Math.fround(d * aux32[l]));
    sumf = Math.fround(sumf - Math.fround(dmin * sumi));
  }
  for (let l = 0; l < 8; l++) sumf = Math.fround(sumf + sums[l]);
  return sumf;
}

// --- GPU ---
async function gpuDot(w, rows, type) {
  const meta = buf(new Uint32Array([rows, COLS, type, 1]), UU), wb = buf(w, SU), ib = buf(y, SU), ob = buf(new Float32Array(rows), SU);
  const bg = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [meta, wb, ib, ob].map((b, i) => ({binding: i, resource: {buffer: b}}))});
  const run = async (K, readback) => {
    const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(pipeline); p.setBindGroup(0, bg);
    for (let i = 0; i < K; i++) p.dispatchWorkgroups(rows, 1, 1); p.end();
    let st; if (readback) { st = device.createBuffer({size: rows * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ}); e.copyBufferToBuffer(ob, 0, st, 0, rows * 4); }
    const t0 = performance.now(); device.queue.submit([e.finish()]);
    if (readback) { await st.mapAsync(GPUMapMode.READ); const out = new Float32Array(st.getMappedRange().slice(0)); st.unmap(); return {out, ms: performance.now() - t0}; }
    await device.queue.onSubmittedWorkDone(); return {ms: performance.now() - t0};
  };
  const {out} = await run(1, true);
  await run(1, false); const one = Math.min((await run(1, false)).ms, (await run(1, false)).ms), many = Math.min((await run(21, false)).ms, (await run(21, false)).ms);
  const perDispatch = (many - one) / 20;
  return {out, perDispatchMs: +perDispatch.toFixed(3), gbps: +((w.byteLength / 1e9) / (perDispatch / 1000)).toFixed(1)};
}
function compare(out, ref, rows) {
  let worst = 0, worstI = 0, maxAbs = 0;
  for (let r = 0; r < rows; r++) { const d = Math.abs(out[r] - ref[r]); const excess = d - 1e-5 * Math.abs(ref[r]); if (d > maxAbs) maxAbs = d; if (excess > worst) { worst = excess; worstI = r; } }
  return {maxAbs: +maxAbs.toPrecision(3), excessOverTol: +worst.toPrecision(3), sampleRef: ref[worstI], sampleGpu: out[worstI], pass: worst <= 1e-4};
}
const report = {gpu: adapter.info?.description ?? "unknown"};
{ const rows = 4096, g = await gpuDot(gate, rows, 23); const ref = new Float32Array(rows); for (let r = 0; r < rows; r++) ref[r] = dotIq4xs(gate, r);
  report["blk.0.attn_gate.weight IQ4_XS 4096x2048"] = {...compare(g.out, ref, rows), perDispatchMs: g.perDispatchMs, "GB/s": g.gbps}; }
{ const rows = 8192, g = await gpuDot(qkv, rows, 13); const ref = new Float32Array(rows); for (let r = 0; r < rows; r++) ref[r] = dotQ5k(qkv, r);
  report["blk.0.attn_qkv.weight Q5_K 8192x2048"] = {...compare(g.out, ref, rows), perDispatchMs: g.perDispatchMs, "GB/s": g.gbps}; }
const validation = await device.popErrorScope(); if (validation) report.validation = validation.message;
const ok = Object.values(report).every((v) => typeof v !== "object" || v.pass) && !validation;
report["kotodama/nex-kdot-parity"] = ok ? "ok" : "FAIL";
console.log(JSON.stringify(report));
if (!ok) Deno.exit(1);
