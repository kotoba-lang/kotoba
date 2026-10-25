// Persistent binary-protocol WebGPU worker for JVM Gemma4 projection calls.
// stdout is protocol-only; diagnostics go to stderr.
const shader = await Deno.readTextFile(new URL("../shaders/ggml_kdot.wgsl", import.meta.url));
const adapter = await navigator.gpu.requestAdapter();
if (!adapter) throw new Error("WebGPU adapter unavailable");
const device = await adapter.requestDevice({requiredLimits:{
  maxBufferSize: adapter.limits.maxBufferSize,
  maxStorageBufferBindingSize: adapter.limits.maxStorageBufferBindingSize,
}});
const module = device.createShaderModule({code:shader});
const pipeline = device.createComputePipeline({layout:"auto", compute:{module,entryPoint:"main"}});
const SU = GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC|GPUBufferUsage.COPY_DST;
const UU = GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST;
const decoder = new TextDecoder();
const cache = new Map();

async function readExact(n) {
  const out = new Uint8Array(n); let off = 0;
  while (off < n) { const got = await Deno.stdin.read(out.subarray(off)); if (got === null) return off === 0 ? null : (()=>{throw new Error("truncated request")})(); off += got; }
  return out;
}
async function writeAll(data) { let off=0; while(off<data.length) off += await Deno.stdout.write(data.subarray(off)); }
const f32Scratch = new Float32Array(1), u32Scratch = new Uint32Array(f32Scratch.buffer);
function nearestInt(x) { f32Scratch[0] = Math.fround(Math.fround(x)+Math.fround(12582912)); return (u32Scratch[0]&0x007fffff)-0x00400000; }
function quantizeQ8(input, positions, cols) {
  const blocks = cols/256, out = new Uint8Array(positions*blocks*292), view = new DataView(out.buffer);
  for(let p=0;p<positions;p++) for(let b=0;b<blocks;b++) {
    const ib=p*cols+b*256, ob=(p*blocks+b)*292; let max=0,amax=0;
    for(let j=0;j<256;j++){const x=Math.fround(input[ib+j]), ax=Math.fround(Math.abs(x));if(ax>amax){amax=ax;max=x;}}
    if(amax===0) continue;
    const iscale=Math.fround(Math.fround(-127)/max); view.setFloat32(ob,Math.fround(1/iscale),true);
    for(let j=0;j<256;j++){const v=Math.min(127,nearestInt(Math.fround(iscale*Math.fround(input[ib+j]))));out[ob+4+j]=v&255;}
    for(let j=0;j<16;j++){let sum=0;for(let k=0;k<16;k++){const q=out[ob+4+j*16+k];sum+=q>=128?q-256:q;}view.setInt16(ob+260+j*2,sum,true);}
  }
  return out;
}
function gpuBuffer(data, usage) {
  const size=Math.max(16,Math.ceil(data.byteLength/4)*4), padded=new Uint8Array(size);padded.set(data);
  const b=device.createBuffer({size,usage});device.queue.writeBuffer(b,0,padded);return b;
}
async function weightBuffer(path,offset,n,key){
  if(cache.has(key))return cache.get(key);
  const file=await Deno.open(path,{read:true});try{await file.seek(offset,Deno.SeekMode.Start);const data=new Uint8Array(n);let off=0;while(off<n){const got=await file.read(data.subarray(off));if(got===null)throw new Error("truncated GGUF tensor");off+=got;}const b=gpuBuffer(data,SU);cache.set(key,b);return b;}finally{file.close();}
}
async function project(req,input) {
  return await projectMany([req],input);
}
async function projectMany(reqs,input) {
  const first=reqs[0],positions=first.positions,cols=first.cols;
  const q8=gpuBuffer(quantizeQ8(input,positions,cols),SU);
  const runs=[];let totalFloats=0;
  for(const req of reqs){
    if(req.cols!==cols||req.positions!==positions)throw new Error("batched projection input shape mismatch");
    const weights=await weightBuffer(req.path,req.offset,req.tensorBytes,req.key);
    const output=device.createBuffer({size:req.rows*positions*4,usage:SU});
    const params=gpuBuffer(new Uint8Array(new Uint32Array([req.rows,cols,req.type,positions]).buffer),UU);
    const bg=device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries:[params,weights,q8,output].map((b,i)=>({binding:i,resource:{buffer:b}}))});
    runs.push({req,output,params,bg,offset:totalFloats*4});totalFloats+=req.rows*positions;
  }
  const staging=device.createBuffer({size:totalFloats*4,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  const enc=device.createCommandEncoder();
  for(const run of runs){const pass=enc.beginComputePass();pass.setPipeline(pipeline);pass.setBindGroup(0,run.bg);pass.dispatchWorkgroups(Math.ceil(run.req.rows/64),positions,1);pass.end();enc.copyBufferToBuffer(run.output,0,staging,run.offset,run.req.rows*positions*4);}
  device.queue.submit([enc.finish()]);await staging.mapAsync(GPUMapMode.READ);const result=new Float32Array(staging.getMappedRange().slice(0));staging.unmap();
  for(const run of runs){run.params.destroy();run.output.destroy();}q8.destroy();staging.destroy();return result;
}
async function respond(status,payload){
  const body=status===0?new Uint8Array(payload.buffer,payload.byteOffset,payload.byteLength):new TextEncoder().encode(String(payload));
  const out=new Uint8Array(8+body.length),v=new DataView(out.buffer);v.setInt32(0,status,false);v.setInt32(4,status===0?payload.length:body.length,false);
  if(status===0){for(let i=0;i<payload.length;i++)v.setFloat32(8+i*4,payload[i],false);}else out.set(body,8);await writeAll(out);
}
for(;;){
  const magicBytes=await readExact(4);if(magicBytes===null)break;
  try{
    const magic=new DataView(magicBytes.buffer).getUint32(0,false);
    if(magic===0x4b444f54){
      const h=await readExact(48),v=new DataView(h.buffer);const req={type:v.getInt32(0,false),rows:Number(v.getBigInt64(4,false)),cols:Number(v.getBigInt64(12,false)),positions:v.getInt32(20,false),offset:Number(v.getBigInt64(24,false)),tensorBytes:Number(v.getBigInt64(32,false)),pathLen:v.getInt32(40,false),keyLen:v.getInt32(44,false)};req.path=decoder.decode(await readExact(req.pathLen));req.key=decoder.decode(await readExact(req.keyLen));const raw=await readExact(req.positions*req.cols*4),rv=new DataView(raw.buffer),input=new Float32Array(req.positions*req.cols);for(let i=0;i<input.length;i++)input[i]=rv.getFloat32(i*4,false);await respond(0,await project(req,input));
    }else if(magic===0x4b444d54){
      const h=await readExact(20),v=new DataView(h.buffer),cols=Number(v.getBigInt64(0,false)),positions=v.getInt32(8,false),tensorCount=v.getInt32(12,false),pathLen=v.getInt32(16,false),reqs=[];
      for(let i=0;i<tensorCount;i++){const d=await readExact(32),dv=new DataView(d.buffer);reqs.push({type:dv.getInt32(0,false),rows:Number(dv.getBigInt64(4,false)),offset:Number(dv.getBigInt64(12,false)),tensorBytes:Number(dv.getBigInt64(20,false)),keyLen:dv.getInt32(28,false),cols,positions});}
      const path=decoder.decode(await readExact(pathLen));for(const req of reqs){req.path=path;req.key=decoder.decode(await readExact(req.keyLen));}
      const raw=await readExact(positions*cols*4),rv=new DataView(raw.buffer),input=new Float32Array(positions*cols);for(let i=0;i<input.length;i++)input[i]=rv.getFloat32(i*4,false);await respond(0,await projectMany(reqs,input));
    }else throw new Error("bad protocol magic");
  }catch(e){await respond(-1,e?.stack??e);}
}
