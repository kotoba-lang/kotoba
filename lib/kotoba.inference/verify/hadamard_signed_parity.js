// Exact-source WebGPU parity for Prism's signed block-Hadamard transform.
// deno run --unstable-webgpu --allow-read --allow-write --allow-run verify/hadamard_signed_parity.js

const source = new URL("../resources/kotodama/inference/kernels/native/hadamard_signed.comp", new URL("./", import.meta.url));
const translatedSource = await Deno.makeTempFile({suffix: ".comp"});
const tmp = await Deno.makeTempFile({suffix: ".wgsl"});
// naga's GLSL frontend does not accept memoryBarrierShared.  The immediately
// following barrier() already becomes a WGSL workgroupBarrier, whose memory
// semantics cover workgroup storage.  Remove only the redundant spelling in
// the translation copy; the shipped Vulkan source remains byte-for-byte the
// production kernel.
await Deno.writeTextFile(translatedSource,
  (await Deno.readTextFile(source)).replaceAll("memoryBarrierShared();", ""));
const p = await new Deno.Command("naga", {args: ["--input-kind", "glsl", "--shader-stage", "compute", translatedSource, tmp], stdout: "piped", stderr: "piped"}).output();
if (!p.success) throw new Error(new TextDecoder().decode(p.stderr));
const code = (await Deno.readTextFile(tmp)).replaceAll("subgroupBarrier();", "workgroupBarrier();");
const adapter = await navigator.gpu.requestAdapter();
if (!adapter) throw new Error("WebGPU adapter unavailable");
const device = await adapter.requestDevice();
device.pushErrorScope("validation");
const pipe = device.createComputePipeline({layout: "auto", compute: {module: device.createShaderModule({code}), entryPoint: "main"}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
function buffer(a) { const b = device.createBuffer({size: Math.max(16, a.byteLength), usage: SU}); device.queue.writeBuffer(b, 0, a); return b; }
let seed = 0x12345678;
function rand() { seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0; return ((seed >>> 8) / 0x1000000) * 2 - 1; }
function sourceIndex(dst, hd, nk, rep) {
  if (rep <= 1) return dst;
  const h = dst % hd, q = Math.floor(dst / hd), r = q % rep, k = Math.floor(q / rep);
  return h + hd * (k + nk * r);
}
function fwht(a) { const y = Float64Array.from(a); for (let s = 1; s < 1024; s *= 2) for (let i = 0; i < 1024; i += 2*s) for (let j = 0; j < s; j++) { const u=y[i+j],v=y[i+j+s]; y[i+j]=u+v; y[i+j+s]=u-v; } for (let i=0;i<1024;i++) y[i]/=32; return y; }
function oracle(x, signs, width, rows, hd, nk, rep, signAfter) {
  const o = new Float32Array(width * rows);
  for (let r=0;r<rows;r++) for (let b=0;b<width/1024;b++) {
    const t = new Float64Array(1024);
    for (let i=0;i<1024;i++) { const d=b*1024+i, v=x[r*width+sourceIndex(d,hd,nk,rep)]; t[i]=signAfter?v:v*signs[d]; }
    const h=fwht(t); for(let i=0;i<1024;i++){const d=b*1024+i;o[r*width+d]=signAfter?h[i]*signs[d]:h[i];}
  }
  return o;
}
async function run(x, signs, width, rows, hd, nk, rep, signAfter) {
  const meta=buffer(new Uint32Array([width,rows,1024,hd,nk,rep,signAfter?1:0,0])), xb=buffer(x), sb=buffer(signs), ob=buffer(new Float32Array(width*rows));
  const bg=device.createBindGroup({layout:pipe.getBindGroupLayout(0),entries:[meta,xb,sb,ob].map((b,binding)=>({binding,resource:{buffer:b}}))});
  const e=device.createCommandEncoder(), pass=e.beginComputePass();pass.setPipeline(pipe);pass.setBindGroup(0,bg);pass.dispatchWorkgroups(width/1024,rows,1);pass.end();
  const read=device.createBuffer({size:width*rows*4,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});e.copyBufferToBuffer(ob,0,read,0,width*rows*4);device.queue.submit([e.finish()]);await read.mapAsync(GPUMapMode.READ);return new Float32Array(read.getMappedRange().slice(0));
}
function error(a,b){let maxAbs=0,maxRel=0;for(let i=0;i<a.length;i++){const d=Math.abs(a[i]-b[i]);maxAbs=Math.max(maxAbs,d);maxRel=Math.max(maxRel,d/Math.max(1e-6,Math.abs(a[i])));}return{maxAbs:+maxAbs.toPrecision(4),maxRel:+maxRel.toPrecision(4)};}
const cases=[{name:"forward-5120",width:5120,rows:3,hd:5120,nk:1,rep:1,after:false},{name:"inverse-5120",width:5120,rows:2,hd:5120,nk:1,rep:1,after:true},{name:"gdn-grouped-6144",width:6144,rows:2,hd:128,nk:16,rep:3,after:false},{name:"ffn-17408",width:17408,rows:1,hd:17408,nk:1,rep:1,after:false}];
const report={gpu:adapter.info?.description??"unknown",cases:{}};let failed=false;
for(const c of cases){const x=Float32Array.from({length:c.width*c.rows},rand), signs=Float32Array.from({length:c.width},()=>rand()<0?-1:1), ref=oracle(x,signs,c.width,c.rows,c.hd,c.nk,c.rep,c.after), got=await run(x,signs,c.width,c.rows,c.hd,c.nk,c.rep,c.after), e=error(ref,got);report.cases[c.name]=e;if(e.maxAbs>2e-5)failed=true;}
const validation=await device.popErrorScope();if(validation){report.validation=validation.message;failed=true;}report["kotodama/hadamard-signed-parity"]=failed?"FAIL":"ok";console.log(JSON.stringify(report));await Deno.remove(translatedSource);await Deno.remove(tmp);if(failed)Deno.exit(1);
