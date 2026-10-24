// num-clj S1: run the FULL IBackend contract on Apple Metal (wgpu via Deno WebGPU)
// and assert every op ≡ the CPU reference values from num.contract.
const adapter = await navigator.gpu.requestAdapter();
const dev = await adapter.requestDevice();
console.log("GPU:", adapter.info?.description, "(wgpu→Metal)\n");

const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
const UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const fbuf = (a) => { const b = dev.createBuffer({size: Math.max(a.byteLength,4), usage: SU}); dev.queue.writeBuffer(b,0,a); return b; };
const ubuf = (a) => { const b = dev.createBuffer({size: Math.max(a.byteLength,16), usage: UU}); dev.queue.writeBuffer(b,0,a); return b; };
async function readf(b, n) {
  const stg = dev.createBuffer({size: n*4, usage: GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  const e = dev.createCommandEncoder(); e.copyBufferToBuffer(b,0,stg,0,n*4); dev.queue.submit([e.finish()]);
  await stg.mapAsync(GPUMapMode.READ); const r = Array.from(new Float32Array(stg.getMappedRange().slice(0))); stg.unmap(); return r;
}
const pipes = {};
function dispatch(src, bufs, wg) {
  if (!pipes[src]) { const m = dev.createShaderModule({code: src}); pipes[src] = dev.createComputePipeline({layout:"auto", compute:{module:m, entryPoint:"main"}}); }
  const p = pipes[src];
  const bg = dev.createBindGroup({layout:p.getBindGroupLayout(0), entries: bufs.map((b,i)=>({binding:i,resource:{buffer:b}}))});
  const e = dev.createCommandEncoder(); const pass = e.beginComputePass();
  pass.setPipeline(p); pass.setBindGroup(0,bg); pass.dispatchWorkgroups(...wg); pass.end(); dev.queue.submit([e.finish()]);
}
const ceil = (a,b)=>Math.ceil(a/b);

// --- shaders (the num.wgsl kernel set) -------------------------------------
const S = {
axpy:`@group(0)@binding(0)var<storage,read>x:array<f32>;@group(0)@binding(1)var<storage,read_write>y:array<f32>;@group(0)@binding(2)var<uniform>a:f32;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&y)){return;}y[i]=a*x[i]+y[i];}`,
scal:`@group(0)@binding(0)var<storage,read_write>x:array<f32>;@group(0)@binding(1)var<uniform>a:f32;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&x)){return;}x[i]=a*x[i];}`,
ewise:`@group(0)@binding(0)var<storage,read>x:array<f32>;@group(0)@binding(1)var<storage,read>y:array<f32>;@group(0)@binding(2)var<storage,read_write>z:array<f32>;@group(0)@binding(3)var<uniform>op:u32;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&z)){return;}let a=x[i];let b=y[i];var r=0.0;switch op{case 0u{r=a+b;}case 1u{r=a-b;}case 2u{r=a*b;}case 3u{r=a/b;}default{r=0.0;}}z[i]=r;}`,
reduce:`@group(0)@binding(0)var<storage,read>x:array<f32>;@group(0)@binding(1)var<storage,read_write>p:array<f32>;@group(0)@binding(2)var<uniform>op:u32;
var<workgroup> s:array<f32,256>;
fn cmb(a:f32,b:f32,op:u32)->f32{if(op==1u){return max(a,b);}if(op==2u){return min(a,b);}return a+b;}
@compute @workgroup_size(256) fn main(@builtin(global_invocation_id)g:vec3<u32>,@builtin(local_invocation_id)l:vec3<u32>,@builtin(workgroup_id)w:vec3<u32>){
let ident=select(select(3.4e38,-3.4e38,op==1u),0.0,op==0u);
s[l.x]=select(ident,x[g.x],g.x<arrayLength(&x));workgroupBarrier();
var d:u32=128u;loop{if(d==0u){break;}if(l.x<d){s[l.x]=cmb(s[l.x],s[l.x+d],op);}workgroupBarrier();d=d/2u;}
if(l.x==0u){p[w.x]=s[0];}}`,
gemv:`@group(0)@binding(0)var<storage,read>A:array<f32>;@group(0)@binding(1)var<storage,read>x:array<f32>;@group(0)@binding(2)var<storage,read_write>y:array<f32>;@group(0)@binding(3)var<uniform>d:vec2<u32>;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;let m=d.x;let n=d.y;if(i>=m){return;}var s=0.0;for(var j:u32=0u;j<n;j=j+1u){s=s+A[i*n+j]*x[j];}y[i]=s 
;}`,
gemm:`const T:u32=16u;@group(0)@binding(0)var<storage,read>A:array<f32>;@group(0)@binding(1)var<storage,read>B:array<f32>;@group(0)@binding(2)var<storage,read_write>C:array<f32>;@group(0)@binding(3)var<uniform>d:vec3<u32>;
var<workgroup> As:array<array<f32,16>,16>;var<workgroup> Bs:array<array<f32,16>,16>;
@compute @workgroup_size(16,16) fn main(@builtin(local_invocation_id)l:vec3<u32>,@builtin(workgroup_id)w:vec3<u32>){
let m=d.x;let k=d.y;let n=d.z;let row=w.y*T+l.y;let col=w.x*T+l.x;var acc=0.0;let nt=(k+T-1u)/T;
for(var t:u32=0u;t<nt;t=t+1u){let ac=t*T+l.x;let br=t*T+l.y;
As[l.y][l.x]=select(0.0,A[row*k+ac],row<m&&ac<k);Bs[l.y][l.x]=select(0.0,B[br*n+col],br<k&&col<n);workgroupBarrier();
for(var i:u32=0u;i<T;i=i+1u){acc=acc+As[l.y][i]*Bs[i][l.x];}workgroupBarrier();}
if(row<m&&col<n){C[row*n+col]=acc;}}`,
spmv:`@group(0)@binding(0)var<storage,read>rp:array<u32>;@group(0)@binding(1)var<storage,read>ci:array<u32>;@group(0)@binding(2)var<storage,read>v:array<f32>;@group(0)@binding(3)var<storage,read>x:array<f32>;@group(0)@binding(4)var<storage,read_write>y:array<f32>;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&y)){return;}var s=0.0;let a=rp[i];let b=rp[i+1u];for(var p:u32=a;p<b;p=p+1u){s=s+v[p]*x[ci[p]];}y[i]=s;}`,
};

// --- ops (mirror num.core via dispatch) ------------------------------------
async function reduce(xb, n, op){ const p=fbuf(new Float32Array(1)); dispatch(S.reduce,[xb,p,ubuf(new Uint32Array([op]))],[ceil(n,256),1,1]); return (await readf(p,1))[0]; }
async function dotOp(xv,yv){ const n=xv.length; const z=fbuf(new Float32Array(n)); dispatch(S.ewise,[fbuf(new Float32Array(xv)),fbuf(new Float32Array(yv)),z,ubuf(new Uint32Array([2]))],[ceil(n,64),1,1]); return reduce(z,n,0); }

let pass=0, fail=0;
const approx=(a,b)=>Math.abs(a-b)<1e-4;
const av=(u,v)=>u.length===v.length&&u.every((x,i)=>approx(x,v[i]));
const ck=(ok,l)=>{ok?pass++:fail++; console.log(`${ok?"✓":"✗"} ${l}`);};

// level-1
{ const x=fbuf(new Float32Array([1,2,3,4])), y=fbuf(new Float32Array([10,20,30,40]));
  dispatch(S.axpy,[x,y,ubuf(new Float32Array([2]))],[1,1,1]); ck(av(await readf(y,4),[12,24,36,48]),"axpy"); }
{ const x=fbuf(new Float32Array([1,2,3,4])); dispatch(S.scal,[x,ubuf(new Float32Array([2]))],[1,1,1]); ck(av(await readf(x,4),[2,4,6,8]),"scal"); }
ck(approx(await dotOp([1,2,3,4],[10,20,30,40]),300),"dot");
ck(approx(Math.sqrt(await dotOp([3,4],[3,4])),5),"nrm2");
// ewise + reductions
for (const [op,name,want] of [[0,"add",[5,5,5,5]],[1,"sub",[-3,-1,1,3]],[2,"mul",[4,6,6,4]]]) {
  const z=fbuf(new Float32Array(4)); dispatch(S.ewise,[fbuf(new Float32Array([1,2,3,4])),fbuf(new Float32Array([4,3,2,1])),z,ubuf(new Uint32Array([op]))],[1,1,1]);
  ck(av(await readf(z,4),want),name);
}
ck(approx(await reduce(fbuf(new Float32Array([1,2,3,4])),4,0),10),"sum");
ck(approx(await reduce(fbuf(new Float32Array([1,2,3,4])),4,1),4),"amax");
ck(approx(await reduce(fbuf(new Float32Array([1,2,3,4])),4,2),1),"amin");
// level-2/3
{ const y=fbuf(new Float32Array([0,0])); dispatch(S.gemv,[fbuf(new Float32Array([1,2,3,4])),fbuf(new Float32Array([1,1])),y,ubuf(new Uint32Array([2,2]))],[1,1,1]); ck(av(await readf(y,2),[3,7]),"gemv"); }
{ const C=fbuf(new Float32Array([0,0,0,0])); dispatch(S.gemm,[fbuf(new Float32Array([1,2,3,4])),fbuf(new Float32Array([5,6,7,8])),C,ubuf(new Uint32Array([2,2,2,0]))],[1,1,1]); ck(av(await readf(C,4),[19,22,43,50]),"gemm"); }
{ const y=fbuf(new Float32Array([0,0])); dispatch(S.spmv,[fbuf(new Uint32Array([0,2,3])),fbuf(new Uint32Array([0,2,1])),fbuf(new Float32Array([1,2,3])),fbuf(new Float32Array([1,1,1])),y],[1,1,1]); ck(av(await readf(y,2),[3,3]),"spmv"); }

console.log(`\nMetal full-contract: ${pass} passed, ${fail} failed`);
Deno.exit(fail?1:0);
