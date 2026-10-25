// Parity + timing of shaders/deltanet_step.wgsl against an f64 JS reference of
// the FLA recurrent gated delta rule, over a run of tokens (state carried on the
// GPU), at Nex's shape: 32 value heads, 16 key heads, K = V = 128.
// Root ADR-2609182100 / co-scientist iteration 2 hypothesis N4.
//
//   deno run --unstable-webgpu --allow-read verify/deltanet_step_parity.js [tokens] [layers-for-timing]
const here = new URL("./", import.meta.url);
const shader = await Deno.readTextFile(new URL("../shaders/deltanet_step.wgsl", here));
const TOKENS = Number(Deno.args[0] ?? 16), LAYERS = Number(Deno.args[1] ?? 30);
const HEADS = 32, KHEADS = 16, K = 128, V = 128, GROUP = HEADS / KHEADS;
const adapter = await navigator.gpu.requestAdapter(); if (!adapter) throw new Error("no adapter");
const device = await adapter.requestDevice(); device.pushErrorScope("validation");
const pipeline = device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code: shader}), entryPoint: "main"}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST, UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const mk = (bytes, usage = SU) => device.createBuffer({size: Math.max(16, bytes), usage});
const write = (b, data) => device.queue.writeBuffer(b, 0, data);

let seed = 3; const rnd = () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 2 ** 32; };
const gauss = () => Math.fround((rnd() + rnd() + rnd() + rnd() - 2) * 1.2);
function l2norm(x, heads, dim, scale = 1) { for (let h = 0; h < heads; h++) { let s = 0; for (let i = 0; i < dim; i++) s += x[h * dim + i] ** 2; const n = Math.sqrt(s) + 1e-6; for (let i = 0; i < dim; i++) x[h * dim + i] = Math.fround(x[h * dim + i] / n * scale); } return x; }
// per-token inputs (as the projections + conv + norms would produce them)
function tokenInputs() {
  const q = l2norm(Float32Array.from({length: KHEADS * K}, gauss), KHEADS, K, 1 / Math.sqrt(K));
  const k = l2norm(Float32Array.from({length: KHEADS * K}, gauss), KHEADS, K);
  const v = Float32Array.from({length: HEADS * V}, gauss);
  const g = Float32Array.from({length: HEADS}, () => Math.fround(-Math.exp(rnd() * 2 - 1) * Math.log1p(Math.exp(gauss()))));   // -exp(A_log) * softplus(a + dt)
  const beta = Float32Array.from({length: HEADS}, () => Math.fround(1 / (1 + Math.exp(-gauss()))));
  return {q, k, v, g, beta};
}
// f64 reference
const S = new Float64Array(HEADS * K * V);
function refStep({q, k, v, g, beta}) {
  const o = new Float64Array(HEADS * V);
  for (let h = 0; h < HEADS; h++) {
    const kh = h % KHEADS, dec = Math.exp(g[h]), base = h * K * V;
    const kvm = new Float64Array(V);
    for (let i = 0; i < K; i++) for (let j = 0; j < V; j++) { S[base + i * V + j] *= dec; kvm[j] += S[base + i * V + j] * k[kh * K + i]; }
    const delta = new Float64Array(V); for (let j = 0; j < V; j++) delta[j] = (v[h * V + j] - kvm[j]) * beta[h];
    for (let i = 0; i < K; i++) for (let j = 0; j < V; j++) { S[base + i * V + j] += k[kh * K + i] * delta[j]; o[h * V + j] += S[base + i * V + j] * q[kh * K + i]; }
  }
  return o;
}
// GPU
const meta = mk(16, UU); write(meta, new Uint32Array([HEADS, K, V, KHEADS]));
const bq = mk(KHEADS * K * 4), bk = mk(KHEADS * K * 4), bv = mk(HEADS * V * 4), bg = mk(HEADS * 4), bb = mk(HEADS * 4);
const bstate = mk(HEADS * K * V * 4); write(bstate, new Float32Array(HEADS * K * V));
const bout = mk(HEADS * V * 4);
const staging = device.createBuffer({size: HEADS * V * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
const bind = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [meta, bq, bk, bv, bg, bb, bstate, bout].map((b, i) => ({binding: i, resource: {buffer: b}}))});
async function gpuStep(inp) {
  write(bq, inp.q); write(bk, inp.k); write(bv, inp.v); write(bg, inp.g); write(bb, inp.beta);
  const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(pipeline); p.setBindGroup(0, bind); p.dispatchWorkgroups(HEADS, 1, 1); p.end();
  e.copyBufferToBuffer(bout, 0, staging, 0, HEADS * V * 4); device.queue.submit([e.finish()]);
  await staging.mapAsync(GPUMapMode.READ); const out = new Float32Array(staging.getMappedRange().slice(0)); staging.unmap(); return out;
}
let worstRel = 0, worstAbs = 0, lastRel = 0;
for (let t = 0; t < TOKENS; t++) {
  const inp = tokenInputs(); const ref = refStep(inp); const got = await gpuStep(inp);
  let rel = 0, abs = 0, norm = 0; for (let i = 0; i < ref.length; i++) { abs = Math.max(abs, Math.abs(got[i] - ref[i])); norm = Math.max(norm, Math.abs(ref[i])); }
  rel = abs / Math.max(norm, 1e-6); worstRel = Math.max(worstRel, rel); worstAbs = Math.max(worstAbs, abs); lastRel = rel;
}
// timing: LAYERS independent states, one step each, in one command buffer (a decode step's worth)
const bigState = mk(LAYERS * HEADS * K * V * 4); write(bigState, new Float32Array(LAYERS * HEADS * K * V));
const binds = []; for (let l = 0; l < LAYERS; l++) { const st = device.createBuffer({size: HEADS * K * V * 4, usage: SU}); binds.push(device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [meta, bq, bk, bv, bg, bb, st, bout].map((b, i) => ({binding: i, resource: {buffer: b}}))})); }
async function timeStep(reps) { const e = device.createCommandEncoder(); const p = e.beginComputePass(); p.setPipeline(pipeline); for (let r = 0; r < reps; r++) for (const b of binds) { p.setBindGroup(0, b); p.dispatchWorkgroups(HEADS, 1, 1); } p.end(); const t0 = performance.now(); device.queue.submit([e.finish()]); await device.queue.onSubmittedWorkDone(); return performance.now() - t0; }
await timeStep(1); const one = Math.min(await timeStep(1), await timeStep(1)), many = Math.min(await timeStep(11), await timeStep(11));
const perStepAllLayers = (many - one) / 10;
const validation = await device.popErrorScope();
const ok = worstRel <= 2e-5 && !validation;
console.log(JSON.stringify({gpu: adapter.info?.description, heads: HEADS, kHeads: KHEADS, K, V, tokens: TOKENS, worstRel: +worstRel.toPrecision(3), worstAbs: +worstAbs.toPrecision(3), lastTokenRel: +lastRel.toPrecision(3), layersTimed: LAYERS, [`ms-per-token-${LAYERS}-layers`]: +perStepAllLayers.toFixed(3), stateMBperLayer: +(HEADS * K * V * 4 / 1e6).toFixed(2), validation: validation?.message, "kotodama/deltanet-step-parity": ok ? "ok" : "FAIL"}));
if (!ok) Deno.exit(1);
