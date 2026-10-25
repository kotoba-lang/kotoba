// Parity + throughput of shaders/ggml_kdot_wg.wgsl (workgroup-per-row) against
// shaders/ggml_kdot.wgsl (thread-per-row reference) on whatever WebGPU adapter
// Deno finds (wgpu -> Metal on Apple, Vulkan on Linux). Root ADR-2609181800 M1.
//
//   deno run --unstable-webgpu --allow-read verify/kdot_wg_parity.js [rows] [blocks]
//
// Prints one JSON line. Exit 1 on any mismatch (oracle or reference parity),
// so a green run means both kernels agree on the ggml oracle AND on
// pseudo-random full-size matrices, and the timing row is the same matrix
// through both kernels, warm, min-of-5 and median-of-5.
const here = new URL("./", import.meta.url);
const refShader = await Deno.readTextFile(new URL("../shaders/ggml_kdot.wgsl", here));
const wgShader = await Deno.readTextFile(new URL("../shaders/ggml_kdot_wg.wgsl", here));
const q4 = "f516b322fefdfffdfdfefcffeeceefcf4095ea4f94e93e84d92e83d82d73c81d62b71c61b60b51a6fb50a5fa4f95ea3fd82d72c71c62c71c61b60b51a6fb50a5fa4f94e93e94e93e83d82d73c82d72c751a6fb4095ea4f95ea3f84d92e74c92e73c81d62b71c62b70c51a6fb41a6fb40d92e73c82d73c81d62b71c62b70c51a6fb4196eb4095ea3f84d93e84d92e73c8";
const q6 = "3085aa0f6387dc3055ba1e3287eb00655702ce7925f0ac5713ce7a45f1ac68133189c1146ca4e63f87c9115aace43c7f0a2ea3385cd1658a0e83a73cb0d569ee9c1743ce4a65f17c9813aeca45c1fc78ec3186ca1f54a7ec3175ca0f5297ec208bb6015e89e3306bb6033e98e5106bb802ce7925f0ac5713ce7a45f1ac6813ceec3542ef35429f35429f38429fe8429f17ca6017ca6117cabd17cabd14cabd20db06b1db0671dc0671ec0671ac0b71ac28825f28855f28f55f28f55228f58228837f6d81887c806e7f847b7f6d81857cb08a";
const q8 = "c8e3f13b8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bc08fc79038ffcfa0217fd7b029efdfc0126fe7d01adfefe0035ff7f00bcff0000";
const bytes = (hex) => Uint8Array.from(hex.match(/../g), x => parseInt(x, 16));
const Q4_EXPECT = -3.695021629333496, Q6_EXPECT = -3.70485520362854;

const rows = Number(Deno.args[0] ?? 10240), blocks = Number(Deno.args[1] ?? 10);
const adapter = await navigator.gpu.requestAdapter();
if (!adapter) throw new Error("WebGPU adapter unavailable");
const device = await adapter.requestDevice();
device.pushErrorScope("validation");
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
const UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const pipe = (code) => device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code}), entryPoint: "main"}});
const kernels = {
  reference: {pipeline: pipe(refShader), dispatch: (r, p) => [Math.ceil(r / 64), p, 1]},
  workgroup: {pipeline: pipe(wgShader), dispatch: (r, p) => [r, p, 1]},
};
const buffer = (data, usage) => {
  const size = Math.max(16, Math.ceil(data.byteLength / 4) * 4);
  const b = device.createBuffer({size, usage});
  const upload = data.byteLength === size ? data : (() => { const p = new Uint8Array(size); p.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength)); return p; })();
  device.queue.writeBuffer(b, 0, upload);
  return b;
};

// One weight matrix + one q8 input, resident on the GPU; run either kernel on it.
function problem(type, weightData, inputData, r, cols, positions = 1) {
  const meta = buffer(new Uint32Array([r, cols, type, positions]), UU);
  const weights = buffer(weightData, SU), input = buffer(inputData, SU);
  const output = buffer(new Float32Array(r * positions), SU);
  const staging = device.createBuffer({size: r * positions * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
  const groups = {};
  for (const [name, k] of Object.entries(kernels)) {
    groups[name] = device.createBindGroup({layout: k.pipeline.getBindGroupLayout(0), entries: [meta, weights, input, output].map((b, i) => ({binding: i, resource: {buffer: b}}))});
  }
  return {
    async run(name, readback = true, repeats = 1) {
      const k = kernels[name];
      const enc = device.createCommandEncoder();
      const pass = enc.beginComputePass();
      pass.setPipeline(k.pipeline); pass.setBindGroup(0, groups[name]);
      for (let i = 0; i < repeats; i++) pass.dispatchWorkgroups(...k.dispatch(r, positions));
      pass.end();
      if (readback) enc.copyBufferToBuffer(output, 0, staging, 0, r * positions * 4);
      const t0 = performance.now();
      device.queue.submit([enc.finish()]);
      if (readback) {
        await staging.mapAsync(GPUMapMode.READ);
        const out = new Float32Array(staging.getMappedRange().slice(0));
        staging.unmap();
        return {out, ms: performance.now() - t0};
      }
      await device.queue.onSubmittedWorkDone();
      return {out: null, ms: performance.now() - t0};
    },
  };
}

// Pseudo-random K-quant bytes: LCG over the whole payload, then pin the f16
// scale words to the oracle's (d, dmin) so no block carries a NaN/Inf scale.
function lcgBytes(n, seed) {
  const out = new Uint8Array(n); let s = seed >>> 0;
  for (let i = 0; i < n; i++) { s = (s * 1664525 + 1013904223) >>> 0; out[i] = s >>> 24; }
  return out;
}
function randomMatrix(type, r, nblocks, seed) {
  const bb = type === 12 ? 144 : 210, unit = bytes(type === 12 ? q4 : q6);
  const m = lcgBytes(r * nblocks * bb, seed);
  for (let b = 0; b < r * nblocks; b++) {
    const o = b * bb;
    if (type === 12) { m.set(unit.subarray(0, 4), o); }          // d, dmin
    else { m.set(unit.subarray(208, 210), o + 208); }            // d
  }
  return m;
}
function randomQ8(nblocks, seed) {
  const unit = bytes(q8), m = lcgBytes(nblocks * 292, seed);
  for (let b = 0; b < nblocks; b++) {
    const o = b * 292;
    m.set(unit.subarray(0, 4), o);                               // d (f32)
    // bsums must equal the sums of each 16-value group, as ggml's quantizer writes them.
    for (let g = 0; g < 16; g++) {
      let s = 0; for (let i = 0; i < 16; i++) { const v = m[o + 4 + g * 16 + i]; s += v >= 128 ? v - 256 : v; }
      m[o + 260 + g * 2] = s & 255; m[o + 261 + g * 2] = (s >> 8) & 255;
    }
  }
  return m;
}

const report = {gpu: adapter.info?.description ?? "unknown", rows, blocks, cols: blocks * 256};
const close = (a, b, tol) => Math.abs(a - b) <= tol;
let failed = false;

// 1. ggml oracle, both kernels.
for (const [type, hex, expect, key] of [[12, q4, Q4_EXPECT, "q4"], [14, q6, Q6_EXPECT, "q6"]]) {
  const p = problem(type, bytes(hex), bytes(q8), 1, 256);
  for (const name of Object.keys(kernels)) {
    const {out} = await p.run(name);
    report[`oracle-${key}-${name}`] = out[0];
    if (!close(out[0], expect, 2e-5)) { failed = true; report[`FAIL-oracle-${key}-${name}`] = `${out[0]} != ${expect}`; }
  }
}

// 2. Reference parity on pseudo-random full-size matrices (both types, positions 1 and 3).
for (const [type, key] of [[12, "q4"], [14, "q6"]]) {
  for (const positions of [1, 3]) {
    const w = randomMatrix(type, rows, blocks, 0x1234 + type);
    const y = new Uint8Array(positions * blocks * 292);
    for (let pos = 0; pos < positions; pos++) y.set(randomQ8(blocks, 0xabcd + pos), pos * blocks * 292);
    const p = problem(type, w, y, rows, blocks * 256, positions);
    const a = (await p.run("reference")).out, b = (await p.run("workgroup")).out;
    let maxAbs = 0, maxRel = 0, worst = -1;
    for (let i = 0; i < a.length; i++) {
      const d = Math.abs(a[i] - b[i]); const rel = d / Math.max(1e-6, Math.abs(a[i]));
      if (d > maxAbs) { maxAbs = d; worst = i; }
      if (rel > maxRel) maxRel = rel;
    }
    report[`parity-${key}-p${positions}`] = {maxAbs: +maxAbs.toPrecision(3), maxRel: +maxRel.toPrecision(3), sampleRef: a[worst < 0 ? 0 : worst], sampleWg: b[worst < 0 ? 0 : worst]};
    // Block-wise integer math is exact in both; only f32 summation order differs.
    if (maxAbs > 1e-4 + 1e-5 * Math.abs(a[worst < 0 ? 0 : worst])) { failed = true; report[`FAIL-parity-${key}-p${positions}`] = true; }
  }
}

// 3. Timing: Q4_K, both kernels, warm, without readback (queue.onSubmittedWorkDone),
//    at several sizes -- a time that does not move with size is launch/sync
//    latency, not bandwidth, and must not be reported as GB/s.
report.timing = {};
for (const r of [rows / 8, rows, rows * 4]) {
  const w = randomMatrix(12, r, blocks, 99), y = randomQ8(blocks, 7);
  const p = problem(12, w, y, r, blocks * 256);
  const gb = (r * blocks * 144) / 1e9;
  const row = {weightsMB: +(gb * 1000).toFixed(1)};
  for (const name of Object.keys(kernels)) {
    await p.run(name, false); // warm-up (pipeline / first dispatch)
    const ms = [];
    for (let i = 0; i < 5; i++) ms.push((await p.run(name, false)).ms);
    ms.sort((a, b) => a - b);
    row[name] = {min: +ms[0].toFixed(3), median: +ms[2].toFixed(3), "GB/s@median": +(gb / (ms[2] / 1000)).toFixed(1)};
  }
  row.speedup_median = +(row.reference.median / row.workgroup.median).toFixed(1);
  // Single submits sit on a fixed submit->done latency (measured 13-18 ms on
  // B70/wgpu regardless of size), so the kernel's own time is taken from K
  // dispatches in ONE command buffer: (t_K - t_1) / (K - 1).
  const K = 21;
  for (const name of Object.keys(kernels)) {
    const one = [], many = [];
    for (let i = 0; i < 3; i++) { one.push((await p.run(name, false, 1)).ms); many.push((await p.run(name, false, K)).ms); }
    one.sort((a, b) => a - b); many.sort((a, b) => a - b);
    const perDispatch = (many[1] - one[1]) / (K - 1);
    row[name].perDispatchMs = +perDispatch.toFixed(3);
    row[name]["GB/s@kernel"] = +(gb / (perDispatch / 1000)).toFixed(1);
  }
  row.kernel_speedup = +(row.reference.perDispatchMs / row.workgroup.perDispatchMs).toFixed(1);
  report.timing[`rows${r}`] = row;
}
const validation = await device.popErrorScope();
if (validation) { failed = true; report.validation = validation.message; }
report["kotodama/kdot-wg-parity"] = failed ? "FAIL" : "ok";
console.log(JSON.stringify(report));
if (failed) Deno.exit(1);
