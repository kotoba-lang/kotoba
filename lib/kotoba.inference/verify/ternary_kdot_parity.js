// Exact-source parity for the native Murakumo PTQ1_0/PQ2_0 kernels.
// naga translates the production GLSL to WGSL; WebGPU then executes it on the
// local adapter. This avoids a second test-only implementation of the GPU dot.
//
// deno run --unstable-webgpu --allow-read --allow-write --allow-run \
//   verify/ternary_kdot_parity.js [rows] [cols]

const here = new URL("./", import.meta.url);
const gpuDir = new URL("../resources/kotodama/inference/kernels/native/", here);
const rows = Number(Deno.args[0] ?? 37);
const cols = Number(Deno.args[1] ?? 1024);
const gguf = Deno.args[2];
if (cols % 256) throw new Error("cols must be a multiple of 256");

const tmp = await Deno.makeTempDir({prefix: "kotodama-ternary-kdot-"});
async function translate(source, output, defines = []) {
  const args = ["--input-kind", "glsl", "--shader-stage", "compute"];
  for (const d of defines) args.push("-D", d);
  args.push(new URL(source, gpuDir).pathname, `${tmp}/${output}`);
  const p = await new Deno.Command("naga", {args, stdout: "piped", stderr: "piped"}).output();
  if (!p.success) throw new Error(new TextDecoder().decode(p.stderr));
  // naga currently prints GLSL `barrier()` as WGSL subgroupBarrier(), although
  // the source barrier synchronises the whole 64-thread workgroup. Preserve the
  // production operation while using the WebGPU spelling accepted by wgpu.
  return (await Deno.readTextFile(`${tmp}/${output}`)).replaceAll("subgroupBarrier();", "workgroupBarrier();");
}

const [r1Code, p4Code, embedCode] = await Promise.all([
  translate("kdot_f32_r1.comp", "r1.wgsl"),
  translate("kdot_f32_p.comp", "p4.wgsl", ["PFIX=4"]),
  translate("embed_iq4xs.comp", "embed.wgsl", ["PTQ1"]),
]);
const adapter = await navigator.gpu.requestAdapter();
if (!adapter) throw new Error("WebGPU adapter unavailable");
const device = await adapter.requestDevice();
device.pushErrorScope("validation");
const pipelines = {
  r1: device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code: r1Code}), entryPoint: "main"}}),
  p4: device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code: p4Code}), entryPoint: "main"}}),
  embed: device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code: embedCode}), entryPoint: "main"}}),
};
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
// GLSL std430 binding 0 translates to a read-only storage buffer; include
// UNIFORM too so this harness remains valid if the source declaration changes.
const UU = GPUBufferUsage.STORAGE | GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
function gpuBuffer(data, usage = SU) {
  const n = Math.max(16, Math.ceil(data.byteLength / 4) * 4);
  const b = device.createBuffer({size: n, usage});
  const upload = new Uint8Array(n); upload.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength));
  device.queue.writeBuffer(b, 0, upload); return b;
}
let seed = 0x5eed1234;
function random() { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return seed; }

function weights(type) {
  const blockBytes = type === 142 ? 34 : 28;
  const blocks = rows * cols / 128;
  const out = new Uint8Array(blocks * blockBytes);
  for (let b = 0; b < blocks; b++) {
    const o = b * blockBytes;
    for (let i = 0; i < blockBytes; i++) out[o + i] = random() >>> 24;
    if (type === 142) { // valid ternary codes only: 0,1,2; code 3 is unused
      out[o] = 0; out[o + 1] = 0x3c; // fp16 scale 1.0 is first
      for (let i = 0; i < 32; i++) {
        let q = 0; for (let k = 0; k < 4; k++) q |= (random() % 3) << (2 * k);
        out[o + 2 + i] = q;
      }
    } else {
      out[o + 26] = 0; out[o + 27] = 0x3c; // scale follows qs[24], qh[2]
    }
  }
  return out;
}
function codeAt(w, type, row, e) {
  const blockBytes = type === 142 ? 34 : 28;
  const rowBytes = cols / 128 * blockBytes;
  const base = row * rowBytes + Math.floor(e / 128) * blockBytes;
  const x = e & 127;
  if (type === 142) return ((w[base + 2 + (x >> 2)] >> (2 * (x & 3))) & 3) - 1;
  let byte, n;
  if (x < 80) { byte = w[base + (x & 15)]; n = x >> 4; }
  else if (x < 120) { const q = x - 80; byte = w[base + 16 + (q & 7)]; n = q >> 3; }
  else { const q = x - 120; byte = w[base + 24 + (q & 1)]; n = q >> 1; }
  for (let i = 0; i < n; i++) byte = (byte * 3) & 255;
  return ((byte * 3) >> 8) - 1;
}
function halfAt(w, off) {
  const h = w[off] | (w[off + 1] << 8), s = (h & 0x8000) ? -1 : 1, e = (h >> 10) & 31, f = h & 1023;
  return e === 0 ? s * 2 ** -14 * (f / 1024) : e === 31 ? (f ? NaN : s * Infinity) : s * 2 ** (e - 15) * (1 + f / 1024);
}
function scaleAt(w, type, row, e) {
  const blockBytes = type === 142 ? 34 : 28, rowBytes = cols / 128 * blockBytes;
  const base = row * rowBytes + Math.floor(e / 128) * blockBytes;
  return halfAt(w, base + (type === 142 ? 0 : 26));
}
function oracle(w, x, type, positions) {
  const out = new Float32Array(rows * positions);
  for (let p = 0; p < positions; p++) for (let r = 0; r < rows; r++) {
    let s = 0; for (let k = 0; k < cols; k++) s += scaleAt(w, type, r, k) * codeAt(w, type, r, k) * x[p * cols + k];
    out[p * rows + r] = s;
  }
  return out;
}

async function actualTensor(path, name = "blk.0.attn_gate.weight", startRow = 0, rowCount = rows) {
  const f = await Deno.open(path, {read: true});
  const head = new Uint8Array(64 * 1024 * 1024); let hn = 0;
  while (hn < head.length) { const n = await f.read(head.subarray(hn)); if (n === null) break; hn += n; }
  const d = new DataView(head.buffer, 0, hn); let p = 4;
  const u8=()=>d.getUint8(p++), u16=()=>{const v=d.getUint16(p,true);p+=2;return v;}, u32=()=>{const v=d.getUint32(p,true);p+=4;return v;}, u64=()=>{const v=Number(d.getBigUint64(p,true));p+=8;return v;};
  const str=()=>{const n=u64(),s=new TextDecoder().decode(head.subarray(p,p+n));p+=n;return s;};
  function skip(t){if(t===0||t===1||t===7){p++;return;}if(t===2||t===3){p+=2;return;}if(t===4||t===5||t===6){p+=4;return;}if(t===8){str();return;}if(t===9){const et=u32(),n=u64();for(let i=0;i<n;i++)skip(et);return;}if(t===10||t===11||t===12){p+=8;return;}throw new Error(`unknown GGUF metadata type ${t}`);}
  const version=u32(), nt=u64(), nkv=u64(); if(version!==3) throw new Error(`GGUF version ${version}`);
  for(let i=0;i<nkv;i++){str();skip(u32());}
  let target;
  for(let i=0;i<nt;i++){const n=str(),nd=u32(),dims=Array.from({length:nd},u64),type=u32(),offset=u64();if(n===name)target={dims,type,offset};}
  const dataStart=Math.ceil(p/32)*32;
  if(!target)throw new Error(`${name} missing`);if(target.type!==143||target.dims[0]!==cols)throw new Error(`${name} expected PTQ1_0 cols=${cols}, got ${JSON.stringify(target)}`);
  const rowBytes=cols/128*28, raw=new Uint8Array(rowCount*rowBytes);await f.seek(dataStart+target.offset+startRow*rowBytes,Deno.SeekMode.Start);let nread=0;while(nread<raw.length){const n=await f.read(raw.subarray(nread));if(n===null)break;nread+=n;}f.close();if(nread!==raw.length)throw new Error(`short tensor read ${nread}/${raw.length}`);return raw;
}
async function run(pipe, w, x, type, positions, dispatch, usesExpertIds = true) {
  const meta = gpuBuffer(new Uint32Array([rows, cols, type, positions, 1, 0, 0, 0]), UU);
  const wb = gpuBuffer(w), xb = gpuBuffer(x), ob = gpuBuffer(new Float32Array(rows * positions));
  const ids = gpuBuffer(new Uint32Array(positions));
  const bindings = usesExpertIds ? [meta, wb, xb, ob, ids] : [meta, wb, xb, ob];
  const bg = device.createBindGroup({layout: pipe.getBindGroupLayout(0), entries: bindings.map((buffer, binding) => ({binding, resource: {buffer}}))});
  const enc = device.createCommandEncoder(); const pass = enc.beginComputePass();
  pass.setPipeline(pipe); pass.setBindGroup(0, bg); pass.dispatchWorkgroups(...dispatch); pass.end();
  const staging = device.createBuffer({size: rows * positions * 4, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
  enc.copyBufferToBuffer(ob, 0, staging, 0, rows * positions * 4); device.queue.submit([enc.finish()]);
  await staging.mapAsync(GPUMapMode.READ); const out = new Float32Array(staging.getMappedRange().slice(0)); staging.unmap(); return out;
}
async function runEmbed(w) {
  const meta=gpuBuffer(new Uint32Array([cols,0,0,0]),UU), wb=gpuBuffer(w), ids=gpuBuffer(new Uint32Array([0])), ob=gpuBuffer(new Float32Array(cols)), pos=gpuBuffer(new Uint32Array([0]));
  const bg=device.createBindGroup({layout:pipelines.embed.getBindGroupLayout(0),entries:[meta,wb,ids,ob,pos].map((buffer,binding)=>({binding,resource:{buffer}}))});
  const enc=device.createCommandEncoder(),pass=enc.beginComputePass();pass.setPipeline(pipelines.embed);pass.setBindGroup(0,bg);pass.dispatchWorkgroups(1,1,1);pass.end();
  const staging=device.createBuffer({size:cols*4,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});enc.copyBufferToBuffer(ob,0,staging,0,cols*4);device.queue.submit([enc.finish()]);await staging.mapAsync(GPUMapMode.READ);return new Float32Array(staging.getMappedRange().slice(0));
}
function error(a, b) {
  let maxAbs = 0, maxRel = 0;
  for (let i = 0; i < a.length; i++) { const d = Math.abs(a[i] - b[i]); maxAbs = Math.max(maxAbs, d); maxRel = Math.max(maxRel, d / Math.max(1e-6, Math.abs(a[i]))); }
  return {maxAbs: +maxAbs.toPrecision(4), maxRel: +maxRel.toPrecision(4)};
}

const report = {gpu: adapter.info?.description ?? "unknown", rows, cols, cases: {}};
let failed = false;
for (const type of [142, 143]) {
  const w = weights(type), x = Float32Array.from({length: 4 * cols}, () => ((random() >>> 8) / 0x1000000) * 2 - 1);
  const ref1 = oracle(w, x, type, 1), ref4 = oracle(w, x, type, 4);
  const got1 = await run(pipelines.r1, w, x, type, 1, [rows, 1, 1]);
  const got4r = await run(pipelines.r1, w, x, type, 4, [rows, 4, 1]);
  const got4p = await run(pipelines.p4, w, x, type, 4, [rows, 1, 1], false);
  const e1 = error(ref1, got1), e4r = error(ref4, got4r), e4p = error(ref4, got4p), cross = error(got4r, got4p);
  report.cases[type === 142 ? "pq2_0" : "ptq1_0"] = {r1: e1, r1Batch4: e4r, positionsBatch4: e4p, cross};
  if ([e1, e4r, e4p].some(e => e.maxAbs > 2e-4 + e.maxRel * 1e-4)) failed = true;
}
{
  const w = new Uint8Array(rows * cols * 2), dv = new DataView(w.buffer), decoded = new Float32Array(rows * cols);
  for (let i = 0; i < decoded.length; i++) {
    const f = ((random() >>> 8) / 0x1000000) * 2 - 1, bits = new Uint32Array(new Float32Array([f]).buffer)[0] & 0xffff0000;
    dv.setUint16(i * 2, bits >>> 16, true); decoded[i] = new Float32Array(new Uint32Array([bits]).buffer)[0];
  }
  const x = Float32Array.from({length: cols}, () => ((random() >>> 8) / 0x1000000) * 2 - 1), ref = new Float32Array(rows);
  for (let r = 0; r < rows; r++) { let s = 0; for (let k = 0; k < cols; k++) s += decoded[r * cols + k] * x[k]; ref[r] = s; }
  const got = await run(pipelines.r1, w, x, 30, 1, [rows, 1, 1]), e = error(ref, got);
  report.cases.bf16 = {r1: e}; if (e.maxAbs > 2e-4) failed = true;
}
if (gguf) {
  const w = await actualTensor(gguf), x = Float32Array.from({length: cols}, () => ((random() >>> 8) / 0x1000000) * 2 - 1);
  const ref = oracle(w, x, 143, 1), got = await run(pipelines.r1, w, x, 143, 1, [rows, 1, 1]);
  const e = error(ref, got); report.realTensor = {file: gguf, tensor: "blk.0.attn_gate.weight", rows, cols, r1: e}; if (e.maxAbs > 2e-3) failed = true;
  const token=9707, ew=await actualTensor(gguf,"token_embd.weight",token,1), eref=new Float32Array(cols);
  for(let k=0;k<cols;k++)eref[k]=scaleAt(ew,143,0,k)*codeAt(ew,143,0,k);
  const egot=await runEmbed(ew),ee=error(eref,egot);report.realEmbedding={tensor:"token_embd.weight",token,ptq1Lookup:ee};if(ee.maxAbs>1e-6)failed=true;
}
const validation = await device.popErrorScope(); if (validation) { report.validation = validation.message; failed = true; }
report["kotodama/ternary-kdot-parity"] = failed ? "FAIL" : "ok";
console.log(JSON.stringify(report));
await Deno.remove(tmp, {recursive: true});
if (failed) Deno.exit(1);
