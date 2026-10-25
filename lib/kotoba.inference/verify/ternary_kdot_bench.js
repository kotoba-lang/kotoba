// Measure the exact Murakumo PTQ1_0 production shaders on a real GGUF tensor.
// Reports resident-weight decode (r1: weights reread per row) and aggregate
// positions form (p: weights decoded once for B independent activation rows).
//
// deno run --unstable-webgpu --allow-read --allow-write --allow-run \
//   verify/ternary_kdot_bench.js model.gguf [tensor] [1,2,4,8] [row-limit]

const gguf = Deno.args[0];
if (!gguf) throw new Error("usage: model.gguf [tensor] [batches] [row-limit]");
const tensorName = Deno.args[1] ?? "blk.0.ffn_gate.weight";
const batches = (Deno.args[2] ?? "1,2,4,8").split(",").map(Number);
const rowLimit = Number(Deno.args[3] ?? 0);
if (batches.some((b) => !Number.isInteger(b) || b < 1 || b > 16)) throw new Error("batch must be 1..16");

const here = new URL("./", import.meta.url);
const gpuDir = new URL("../resources/kotodama/inference/kernels/native/", here);
const tmp = await Deno.makeTempDir({prefix: "murakumo-ptq-bench-"});
async function translate(source, output, defines = []) {
  const args = ["--input-kind", "glsl", "--shader-stage", "compute"];
  for (const d of defines) args.push("-D", d);
  args.push(new URL(source, gpuDir).pathname, `${tmp}/${output}`);
  const p = await new Deno.Command("naga", {args, stdout: "piped", stderr: "piped"}).output();
  if (!p.success) throw new Error(new TextDecoder().decode(p.stderr));
  return (await Deno.readTextFile(`${tmp}/${output}`)).replaceAll("subgroupBarrier();", "workgroupBarrier();");
}

async function readTensor(path, name) {
  const f = await Deno.open(path, {read: true});
  const head = new Uint8Array(64 * 1024 * 1024); let hn = 0;
  while (hn < head.length) { const n = await f.read(head.subarray(hn)); if (n === null) break; hn += n; }
  const d = new DataView(head.buffer, 0, hn); let p = 4;
  const u8=()=>d.getUint8(p++), u32=()=>{const v=d.getUint32(p,true);p+=4;return v;};
  const u64=()=>{const v=Number(d.getBigUint64(p,true));p+=8;return v;};
  const str=()=>{const n=u64(),s=new TextDecoder().decode(head.subarray(p,p+n));p+=n;return s;};
  function skip(t) { if(t===0||t===1||t===7){p++;return;} if(t===2||t===3){p+=2;return;} if(t===4||t===5||t===6){p+=4;return;} if(t===8){str();return;} if(t===9){const et=u32(),n=u64();for(let i=0;i<n;i++)skip(et);return;} if(t===10||t===11||t===12){p+=8;return;} throw new Error(`metadata type ${t}`); }
  const version=u32(), nt=u64(), nkv=u64(); if(version!==3) throw new Error(`GGUF version ${version}`);
  for(let i=0;i<nkv;i++){str();skip(u32());}
  let target;
  for(let i=0;i<nt;i++){const n=str(),nd=u32(),dims=Array.from({length:nd},u64),type=u32(),offset=u64();if(n===name)target={dims,type,offset};}
  const dataStart=Math.ceil(p/32)*32;
  if(!target) throw new Error(`${name} missing`);
  if(target.type!==143) throw new Error(`${name} type ${target.type}, expected PTQ1_0 (143)`);
  const [cols, fullRows] = target.dims, rows = rowLimit ? Math.min(rowLimit, fullRows) : fullRows;
  if(cols % 128) throw new Error(`cols ${cols} is not group-128 aligned`);
  const bytes=rows*(cols/128)*28, raw=new Uint8Array(bytes);
  await f.seek(dataStart+target.offset,Deno.SeekMode.Start); let got=0;
  while(got<bytes){const n=await f.read(raw.subarray(got));if(n===null)break;got+=n;} f.close();
  if(got!==bytes) throw new Error(`short tensor read ${got}/${bytes}`);
  return {raw, rows, fullRows, cols};
}

const {raw: weights, rows, fullRows, cols} = await readTensor(gguf, tensorName);
const adapter = await navigator.gpu.requestAdapter();
if (!adapter) throw new Error("WebGPU adapter unavailable");
if (rows > adapter.limits.maxComputeWorkgroupsPerDimension) {
  throw new Error(
    `rows ${rows} exceeds WebGPU maxComputeWorkgroupsPerDimension ` +
    `${adapter.limits.maxComputeWorkgroupsPerDimension}; pass a row-limit and report any full-tensor scaling as an estimate`,
  );
}
const device = await adapter.requestDevice({requiredLimits: {
  maxBufferSize: adapter.limits.maxBufferSize,
  maxStorageBufferBindingSize: adapter.limits.maxStorageBufferBindingSize,
}});
const r1Code = await translate("kdot_f32_r1.comp", "r1.wgsl");
const r1 = device.createComputePipeline({layout:"auto",compute:{module:device.createShaderModule({code:r1Code}),entryPoint:"main"}});
const pPipes = new Map();
for (const b of batches) {
  const code = await translate("kdot_f32_p.comp", `p${b}.wgsl`, [`PFIX=${b}`]);
  pPipes.set(b, device.createComputePipeline({layout:"auto",compute:{module:device.createShaderModule({code}),entryPoint:"main"}}));
}
const SU=GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC|GPUBufferUsage.COPY_DST;
const UU=GPUBufferUsage.STORAGE|GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST;
function buffer(data,usage=SU){const n=Math.max(16,Math.ceil(data.byteLength/4)*4),b=device.createBuffer({size:n,usage});device.queue.writeBuffer(b,0,data.buffer,data.byteOffset,data.byteLength);return b;}
const wb=buffer(weights);
function makeCase(pipe,b,positionsForm){
  const meta=buffer(new Uint32Array([rows,cols,143,b,1,0,0,0]),UU);
  const x=buffer(Float32Array.from({length:b*cols},(_,i)=>((i*1664525+1013904223)>>>8)/0x1000000-0.5));
  const out=buffer(new Float32Array(b*rows));
  const ids=buffer(new Uint32Array(b));
  const bufs=positionsForm?[meta,wb,x,out]:[meta,wb,x,out,ids];
  const bg=device.createBindGroup({layout:pipe.getBindGroupLayout(0),entries:bufs.map((buffer,binding)=>({binding,resource:{buffer}}))});
  return {pipe,bg,dispatch:positionsForm?[rows,1,1]:[rows,b,1]};
}
async function measure(c, loops) {
  const submit=()=>{const enc=device.createCommandEncoder(),pass=enc.beginComputePass();pass.setPipeline(c.pipe);pass.setBindGroup(0,c.bg);for(let i=0;i<loops;i++)pass.dispatchWorkgroups(...c.dispatch);pass.end();device.queue.submit([enc.finish()]);};
  submit(); await device.queue.onSubmittedWorkDone();
  const samples=[];
  for(let r=0;r<5;r++){const t=performance.now();submit();await device.queue.onSubmittedWorkDone();samples.push((performance.now()-t)/loops);}
  samples.sort((a,b)=>a-b); return {median_ms:+samples[2].toFixed(4),samples_ms:samples.map(x=>+x.toFixed(4))};
}
const loops=weights.byteLength>200_000_000?3:10, results=[];
for(const b of batches){
  for(const [form,c] of [["r1",makeCase(r1,b,false)],["positions",makeCase(pPipes.get(b),b,true)]]){
    const m=await measure(c,loops), aggregate=b/(m.median_ms/1000);
    results.push({batch:b,form,...m,aggregate_row_matmuls_s:+aggregate.toFixed(2),resident_weight_GB_s:+((weights.byteLength/1e9)/(m.median_ms/1000)).toFixed(2)});
  }
}
console.log(JSON.stringify({gpu:adapter.info?.description??"unknown",tensor:tensorName,rows,full_rows:fullRows,cols,weight_bytes:weights.byteLength,loops,results},null,2));
await Deno.remove(tmp,{recursive:true});
