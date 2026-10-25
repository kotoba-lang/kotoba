// Decode-step submit-shape bench (root ADR-2609181800 M2, co-scientist iteration 1).
//
// Hypothesis H1: kotodama's 8.4 s/token on Gemma4 e4b is submit count, not
// kernel speed. This runs ONE decode step's weight stream -- all 42 layers x 7
// projections of Gemma4 e4b at their real shapes and ggml types, plus the tied
// 262144 x 2560 Q6_K lm_head -- through shaders/ggml_kdot_wg.wgsl with weights
// resident on the GPU, in three submit shapes:
//   A  one submit + readback per projection      (today's host: 295 round trips)
//   B  one submit per layer, readback at the end (42 round trips)
//   C  one command buffer per token, logits only (1 round trip)
// and prints ms/token for each, plus the weight bytes streamed and GB/s.
// Norms / attention / activation quantisation are NOT included: this is the
// weight-stream floor of a decode step, and the number to compare against
// 8.4 s/token is the shape A vs C difference, not an absolute tok/s claim.
//
//   deno run --unstable-webgpu --allow-read verify/decode_step_bench.js [layers]
// Memory: 42 layers allocate ~3.0 GB of GPU weights plus transient host copies.
// Do NOT run the full size on a node that is serving with < 8 GB free: on
// xavier (31 GiB unified, 21 GiB resident model) this OOM-killed a stray
// llama-server and thrashed the box for ~3 min on 2026-09-18. Use [layers] = 6
// there, or stop the server first with the owner`s approval.
const here = new URL("./", import.meta.url);
const shader = await Deno.readTextFile(new URL("../shaders/ggml_kdot_wg.wgsl", here));
const layers = Number(Deno.args[0] ?? 42);
const adapter = await navigator.gpu.requestAdapter();
if (!adapter) throw new Error("WebGPU adapter unavailable");
const want = {
  maxStorageBufferBindingSize: Math.min(adapter.limits.maxStorageBufferBindingSize, 1 << 30),
  maxBufferSize: Math.min(adapter.limits.maxBufferSize, 1 << 30),
};
const device = await adapter.requestDevice({requiredLimits: want});
device.pushErrorScope("validation");
const pipeline = device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code: shader}), entryPoint: "main"}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
const UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const Q4 = 12, Q6 = 14, BYTES = {12: 144, 14: 210};

// Gemma4 e4b (verify/maturity.edn :gemma4-e4b-gguf): 42 blocks, embedding 2560,
// ffn 10240, 8 q heads x 256, 2 kv heads x 256, vocab 262144 tied Q6_K.
const LAYER = [
  ["attn_q", 2048, 2560, Q4], ["attn_k", 512, 2560, Q4], ["attn_v", 512, 2560, Q6],
  ["attn_output", 2560, 2048, Q4], ["ffn_gate", 10240, 2560, Q4], ["ffn_up", 10240, 2560, Q4],
  ["ffn_down", 2560, 10240, Q6],
];
const LM_HEAD = ["output", 262144, 2560, Q6];
const CHUNK_ROWS = 32768; // 32768 x 2560 Q6_K = 68.9 MB per chunk, under every default binding limit

function lcg(n, seed) { const o = new Uint8Array(n); let s = seed >>> 0; for (let i = 0; i < n; i++) { s = (s * 1664525 + 1013904223) >>> 0; o[i] = s >>> 24; } return o; }
// f16 1.0 = 0x3c00 (little-endian 00 3c); keep every block scale finite.
function weightBytes(type, rows, cols, seed) {
  const bb = BYTES[type], nb = cols / 256, m = lcg(rows * nb * bb, seed);
  for (let b = 0; b < rows * nb; b++) { const o = b * bb; if (type === Q4) { m[o] = 0; m[o + 1] = 0x3c; m[o + 2] = 0; m[o + 3] = 0x3c; } else { m[o + 208] = 0; m[o + 209] = 0x3c; } }
  return m;
}
function q8Bytes(cols, seed) {
  const nb = cols / 256, m = lcg(nb * 292, seed);
  for (let b = 0; b < nb; b++) { const o = b * 292; new DataView(m.buffer).setFloat32(o, 1.0, true); for (let g = 0; g < 16; g++) { let s = 0; for (let i = 0; i < 16; i++) { const v = m[o + 4 + g * 16 + i]; s += v >= 128 ? v - 256 : v; } m[o + 260 + g * 2] = s & 255; m[o + 261 + g * 2] = (s >> 8) & 255; } }
  return m;
}
const gpuBuf = (data, usage) => { const size = Math.max(16, Math.ceil(data.byteLength / 4) * 4); const b = device.createBuffer({size, usage}); device.queue.writeBuffer(b, 0, data.byteLength === size ? data : (() => { const p = new Uint8Array(size); p.set(data); return p; })()); return b; };

// Build the resident model: one bind group per projection (or lm_head chunk).
const inputs = {}; // cols -> q8 buffer (shared by every projection with that input width)
for (const cols of [2560, 2048, 10240]) inputs[cols] = gpuBuf(q8Bytes(cols, cols), SU);
const outputs = {}; // rows -> output buffer
for (const rows of [2048, 512, 2560, 10240, CHUNK_ROWS]) outputs[rows] = gpuBuf(new Float32Array(rows), SU);
const steps = []; // [{name, rows, bindGroup}]
let weightBytesTotal = 0;
const t0 = performance.now();
let seed = 1;
function addProjection(name, rows, cols, type) {
  const w = weightBytes(type, rows, cols, seed++);
  weightBytesTotal += w.byteLength;
  const meta = gpuBuf(new Uint32Array([rows, cols, type, 1]), UU);
  const wb = gpuBuf(w, SU);
  const bg = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [meta, wb, inputs[cols], outputs[rows]].map((b, i) => ({binding: i, resource: {buffer: b}}))});
  steps.push({name, rows, bg});
}
for (let l = 0; l < layers; l++) for (const [name, rows, cols, type] of LAYER) addProjection(`blk.${l}.${name}`, rows, cols, type);
for (let c = 0; c < LM_HEAD[1] / CHUNK_ROWS; c++) addProjection(`output.chunk${c}`, CHUNK_ROWS, LM_HEAD[2], LM_HEAD[3]);
await device.queue.onSubmittedWorkDone();
const buildMs = performance.now() - t0;
const logitsStaging = device.createBuffer({size: CHUNK_ROWS * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
const smallStaging = device.createBuffer({size: 10240 * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});

async function readback(src, staging, bytes) {
  const enc = device.createCommandEncoder(); enc.copyBufferToBuffer(src, 0, staging, 0, bytes); device.queue.submit([enc.finish()]);
  await staging.mapAsync(GPUMapMode.READ); const v = new Float32Array(staging.getMappedRange().slice(0, 4))[0]; staging.unmap(); return v;
}
function dispatchInto(enc, list) {
  const pass = enc.beginComputePass(); pass.setPipeline(pipeline);
  for (const s of list) { pass.setBindGroup(0, s.bg); pass.dispatchWorkgroups(s.rows, 1, 1); }
  pass.end();
}
async function shapeA() { // per projection: submit + readback
  const t = performance.now();
  for (const s of steps) { const enc = device.createCommandEncoder(); dispatchInto(enc, [s]); device.queue.submit([enc.finish()]); await readback(outputs[s.rows], s.rows === CHUNK_ROWS ? logitsStaging : smallStaging, 4); }
  return performance.now() - t;
}
async function shapeB() { // per layer submit, readback once
  const t = performance.now();
  for (let i = 0; i < steps.length; i += 7) { const enc = device.createCommandEncoder(); dispatchInto(enc, steps.slice(i, i + 7)); device.queue.submit([enc.finish()]); }
  await readback(outputs[CHUNK_ROWS], logitsStaging, 4);
  return performance.now() - t;
}
async function shapeC() { // one command buffer per token, logits only
  const t = performance.now();
  const enc = device.createCommandEncoder(); dispatchInto(enc, steps); enc.copyBufferToBuffer(outputs[CHUNK_ROWS], 0, logitsStaging, 0, 4); device.queue.submit([enc.finish()]);
  await logitsStaging.mapAsync(GPUMapMode.READ); logitsStaging.unmap();
  return performance.now() - t;
}
const median3 = async (f) => { const v = []; for (let i = 0; i < 3; i++) v.push(await f()); v.sort((a, b) => a - b); return {ms: +v[1].toFixed(1), min: +v[0].toFixed(1)}; };
await shapeC(); // warm-up
const report = {gpu: adapter.info?.description ?? "unknown", layers, projections: steps.length, weightsGB: +(weightBytesTotal / 1e9).toFixed(3), buildMs: +buildMs.toFixed(0)};
report.C_one_submit_per_token = await median3(shapeC);
report.B_one_submit_per_layer = await median3(shapeB);
report.A_submit_and_readback_per_projection = await median3(shapeA);
for (const k of ["A_submit_and_readback_per_projection", "B_one_submit_per_layer", "C_one_submit_per_token"]) {
  report[k]["tok/s@median"] = +(1000 / report[k].ms).toFixed(2);
  report[k]["GB/s@median"] = +(weightBytesTotal / 1e9 / (report[k].ms / 1000)).toFixed(1);
}
report.A_over_C = +(report.A_submit_and_readback_per_projection.ms / report.C_one_submit_per_token.ms).toFixed(1);
const validation = await device.popErrorScope();
if (validation) report.validation = validation.message;
console.log(JSON.stringify(report));
