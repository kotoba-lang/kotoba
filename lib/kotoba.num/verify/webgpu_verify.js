// Run num-clj's WGSL kernels on Metal (via Deno WebGPU/wgpu) and check ≡ CPU reference.
const adapter = await navigator.gpu.requestAdapter();
const dev = await adapter.requestDevice();
console.log("GPU:", adapter.info?.description, "(wgpu→Metal)\n");

const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
function buf(data, usage) {
  const b = dev.createBuffer({size: data.byteLength, usage});
  dev.queue.writeBuffer(b, 0, data);
  return b;
}
async function read(b, nbytes) {
  const stg = dev.createBuffer({size: nbytes, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
  const enc = dev.createCommandEncoder();
  enc.copyBufferToBuffer(b, 0, stg, 0, nbytes);
  dev.queue.submit([enc.finish()]);
  await stg.mapAsync(GPUMapMode.READ);
  const out = new Float32Array(stg.getMappedRange().slice(0));
  stg.unmap();
  return Array.from(out);
}
function run(shader, entry, bindings, wg) {
  const mod = dev.createShaderModule({code: shader});
  const pipe = dev.createComputePipeline({layout: "auto", compute: {module: mod, entryPoint: entry}});
  const bg = dev.createBindGroup({layout: pipe.getBindGroupLayout(0),
    entries: bindings.map((b, i) => ({binding: i, resource: {buffer: b}}))});
  const enc = dev.createCommandEncoder();
  const pass = enc.beginComputePass();
  pass.setPipeline(pipe); pass.setBindGroup(0, bg);
  pass.dispatchWorkgroups(...wg); pass.end();
  dev.queue.submit([enc.finish()]);
}
const approx = (a, b) => a.length === b.length && a.every((v, i) => Math.abs(v - b[i]) < 1e-4);
let pass = 0, fail = 0;
const check = (ok, label, got, want) => { ok ? pass++ : fail++;
  console.log(`${ok ? "✓" : "✗"} ${label}  got=[${got.map(x=>x.toFixed(2))}]  want=[${want.map(x=>x.toFixed(2))}]`); };

// --- AXPY: y = 2x + y -------------------------------------------------------
const axpy = `
@group(0) @binding(0) var<storage, read> x: array<f32>;
@group(0) @binding(1) var<storage, read_write> y: array<f32>;
@group(0) @binding(2) var<uniform> alpha: f32;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x; if (i >= arrayLength(&y)) { return; }
  y[i] = alpha * x[i] + y[i];
}`;
{
  const x = buf(new Float32Array([1,2,3,4]), SU);
  const y = buf(new Float32Array([10,20,30,40]), SU);
  const a = buf(new Float32Array([2,0,0,0]), GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST);
  run(axpy, "main", [x, y, a], [Math.ceil(4/64),1,1]);
  const got = await read(y, 16), want = [12,24,36,48];
  check(approx(got, want), "AXPY  y←2x+y", got, want);
}

// --- tiled GEMM: C = A·B ----------------------------------------------------
const gemm = `
const TILE: u32 = 16u;
@group(0) @binding(0) var<storage, read> A: array<f32>;
@group(0) @binding(1) var<storage, read> B: array<f32>;
@group(0) @binding(2) var<storage, read_write> C: array<f32>;
@group(0) @binding(3) var<uniform> dims: vec3<u32>;
var<workgroup> As: array<array<f32, 16>, 16>;
var<workgroup> Bs: array<array<f32, 16>, 16>;
@compute @workgroup_size(16, 16)
fn main(@builtin(local_invocation_id) lid: vec3<u32>, @builtin(workgroup_id) wid: vec3<u32>) {
  let m = dims.x; let k = dims.y; let n = dims.z;
  let row = wid.y * TILE + lid.y; let col = wid.x * TILE + lid.x;
  var acc: f32 = 0.0;
  let ntiles = (k + TILE - 1u) / TILE;
  for (var t: u32 = 0u; t < ntiles; t = t + 1u) {
    let aCol = t*TILE + lid.x; let bRow = t*TILE + lid.y;
    As[lid.y][lid.x] = select(0.0, A[row*k + aCol], row < m && aCol < k);
    Bs[lid.y][lid.x] = select(0.0, B[bRow*n + col], bRow < k && col < n);
    workgroupBarrier();
    for (var i: u32 = 0u; i < TILE; i = i + 1u) { acc = acc + As[lid.y][i] * Bs[i][lid.x]; }
    workgroupBarrier();
  }
  if (row < m && col < n) { C[row*n + col] = acc; }
}`;
{
  const m=2,k=2,n=2;
  const A = buf(new Float32Array([1,2,3,4]), SU);
  const B = buf(new Float32Array([5,6,7,8]), SU);
  const C = buf(new Float32Array([0,0,0,0]), SU);
  const d = buf(new Uint32Array([m,k,n,0]), GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST);
  run(gemm, "main", [A,B,C,d], [Math.ceil(n/16), Math.ceil(m/16), 1]);
  const got = await read(C, 16), want = [19,22,43,50];
  check(approx(got, want), "GEMM  C←A·B (tiled)", got, want);
}

// --- CSR SpMV: y = A·x ------------------------------------------------------
const spmv = `
@group(0) @binding(0) var<storage, read> row_ptr: array<u32>;
@group(0) @binding(1) var<storage, read> col_idx: array<u32>;
@group(0) @binding(2) var<storage, read> vals: array<f32>;
@group(0) @binding(3) var<storage, read> x: array<f32>;
@group(0) @binding(4) var<storage, read_write> y: array<f32>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x; if (i >= arrayLength(&y)) { return; }
  var s: f32 = 0.0; let a = row_ptr[i]; let b = row_ptr[i+1u];
  for (var p: u32 = a; p < b; p = p + 1u) { s = s + vals[p] * x[col_idx[p]]; }
  y[i] = s;
}`;
{
  // [[1 0 2],[0 3 0]] · [1,1,1] = [3,3]
  const rp = buf(new Uint32Array([0,2,3]), SU);
  const ci = buf(new Uint32Array([0,2,1]), SU);
  const v  = buf(new Float32Array([1,2,3]), SU);
  const x  = buf(new Float32Array([1,1,1]), SU);
  const y  = buf(new Float32Array([0,0]), SU);
  run(spmv, "main", [rp,ci,v,x,y], [Math.ceil(2/64),1,1]);
  const got = await read(y, 8), want = [3,3];
  check(approx(got, want), "SpMV  y←A·x (CSR)", got, want);
}

console.log(`\nMetal verification: ${pass} passed, ${fail} failed`);
Deno.exit(fail ? 1 : 0);
