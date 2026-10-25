// num-clj S3 demo: a Jacobi-preconditioned CONJUGATE GRADIENT solve run entirely
// with num-clj's GPU kernels (SpMV/AXPY/dot/ewise) on Apple Metal — the same Krylov
// loop nagare-clj's linsolve runs. Solves a 2-D Poisson system A x = b and checks
// x ≈ x_true. Data stays resident on the GPU; only the scalars (α,β,‖r‖) read back.
const adapter = await navigator.gpu.requestAdapter();
const dev = await adapter.requestDevice();
console.log("GPU:", adapter.info?.description, "(wgpu→Metal)\n");

const SU = GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_SRC|GPUBufferUsage.COPY_DST;
const UU = GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST;
const fbuf=a=>{const b=dev.createBuffer({size:Math.max(a.byteLength,4),usage:SU});dev.queue.writeBuffer(b,0,a);return b;};
const ubuf=a=>{const b=dev.createBuffer({size:Math.max(a.byteLength,16),usage:UU});dev.queue.writeBuffer(b,0,a);return b;};
async function readf(b,n){const s=dev.createBuffer({size:n*4,usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  const e=dev.createCommandEncoder();e.copyBufferToBuffer(b,0,s,0,n*4);dev.queue.submit([e.finish()]);
  await s.mapAsync(GPUMapMode.READ);const r=Array.from(new Float32Array(s.getMappedRange().slice(0)));s.unmap();return r;}
const pipes={};
function disp(src,bufs,wg){if(!pipes[src]){const m=dev.createShaderModule({code:src});pipes[src]=dev.createComputePipeline({layout:"auto",compute:{module:m,entryPoint:"main"}});}
  const p=pipes[src];const bg=dev.createBindGroup({layout:p.getBindGroupLayout(0),entries:bufs.map((b,i)=>({binding:i,resource:{buffer:b}}))});
  const e=dev.createCommandEncoder();const pa=e.beginComputePass();pa.setPipeline(p);pa.setBindGroup(0,bg);pa.dispatchWorkgroups(...wg);pa.end();dev.queue.submit([e.finish()]);}
const ceil=(a,b)=>Math.ceil(a/b);

const SPMV=`@group(0)@binding(0)var<storage,read>rp:array<u32>;@group(0)@binding(1)var<storage,read>ci:array<u32>;@group(0)@binding(2)var<storage,read>v:array<f32>;@group(0)@binding(3)var<storage,read>x:array<f32>;@group(0)@binding(4)var<storage,read_write>y:array<f32>;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&y)){return;}var s=0.0;let a=rp[i];let b=rp[i+1u];for(var p:u32=a;p<b;p=p+1u){s=s+v[p]*x[ci[p]];}y[i]=s;}`;
const AXPY=`@group(0)@binding(0)var<storage,read>x:array<f32>;@group(0)@binding(1)var<storage,read_write>y:array<f32>;@group(0)@binding(2)var<uniform>a:f32;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&y)){return;}y[i]=a*x[i]+y[i];}`;
const SCAL=`@group(0)@binding(0)var<storage,read_write>x:array<f32>;@group(0)@binding(1)var<uniform>a:f32;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&x)){return;}x[i]=a*x[i];}`;
const MUL=`@group(0)@binding(0)var<storage,read>x:array<f32>;@group(0)@binding(1)var<storage,read>y:array<f32>;@group(0)@binding(2)var<storage,read_write>z:array<f32>;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&z)){return;}z[i]=x[i]*y[i];}`;
const DIV=`@group(0)@binding(0)var<storage,read>x:array<f32>;@group(0)@binding(1)var<storage,read>y:array<f32>;@group(0)@binding(2)var<storage,read_write>z:array<f32>;
@compute @workgroup_size(64) fn main(@builtin(global_invocation_id)g:vec3<u32>){let i=g.x;if(i>=arrayLength(&z)){return;}z[i]=x[i]/y[i];}`;
const RED=`@group(0)@binding(0)var<storage,read>x:array<f32>;@group(0)@binding(1)var<storage,read_write>p:array<f32>;
var<workgroup> s:array<f32,256>;
@compute @workgroup_size(256) fn main(@builtin(global_invocation_id)g:vec3<u32>,@builtin(local_invocation_id)l:vec3<u32>,@builtin(workgroup_id)w:vec3<u32>){
s[l.x]=select(0.0,x[g.x],g.x<arrayLength(&x));workgroupBarrier();var d:u32=128u;loop{if(d==0u){break;}if(l.x<d){s[l.x]=s[l.x]+s[l.x+d];}workgroupBarrier();d=d/2u;}if(l.x==0u){p[w.x]=s[0];}}`;

const N1=(n)=>ceil(n,64), NW=(n)=>ceil(n,256);
function axpy(a,x,y,n){disp(AXPY,[x,y,ubuf(new Float32Array([a]))],[N1(n),1,1]);}
function scal(a,x,n){disp(SCAL,[x,ubuf(new Float32Array([a]))],[N1(n),1,1]);}
function spmv(M,x,y,n){disp(SPMV,[M.rp,M.ci,M.v,x,y],[N1(n),1,1]);}
async function dot(x,y,n){const z=fbuf(new Float32Array(n));disp(MUL,[x,y,z],[N1(n),1,1]);
  const nw=NW(n);const p=fbuf(new Float32Array(nw));disp(RED,[z,p],[nw,1,1]);
  return (await readf(p,nw)).reduce((a,b)=>a+b,0);}

// --- build a 2-D Poisson system (5-point, Dirichlet), N = n*n -------------------
const n=32, N=n*n;
const rp=[0], ci=[], vv=[], diag=new Float32Array(N);
for(let j=0;j<n;j++)for(let i=0;i<n;i++){const c=j*n+i;const nb=[];
  if(i>0)nb.push([c-1,-1]); if(i<n-1)nb.push([c+1,-1]); if(j>0)nb.push([c-n,-1]); if(j<n-1)nb.push([c+n,-1]);
  ci.push(c);vv.push(4);diag[c]=4;                       // diagonal
  for(const[k,val]of nb){ci.push(k);vv.push(val);}
  rp.push(ci.length);}
const M={rp:fbuf(new Uint32Array(rp)),ci:fbuf(new Uint32Array(ci)),v:fbuf(new Float32Array(vv))};
const Dinv=new Float32Array(N); for(let k=0;k<N;k++)Dinv[k]=1/diag[k];
const dinv=fbuf(Dinv);
// x_true smooth, b = A x_true
const xt=new Float32Array(N); for(let k=0;k<N;k++){const h=Math.sin(k*12.9898+1.0)*43758.5453; xt[k]=h-Math.floor(h);} // deterministic pseudo-random (non-eigenvector)
const xtb=fbuf(xt), bb=fbuf(new Float32Array(N)); spmv(M,xtb,bb,N);

// --- Jacobi-preconditioned CG (all ops on GPU) ---------------------------------
const x=fbuf(new Float32Array(N));                       // x0 = 0
const r=fbuf(new Float32Array(await readf(bb,N)));        // r = b - A·0 = b
const z=fbuf(new Float32Array(N)); disp(MUL,[r,dinv,z],[N1(N),1,1]);  // z = M^-1 r = r .* Dinv
const p=fbuf(new Float32Array(await readf(z,N)));         // p = z
const Ap=fbuf(new Float32Array(N));
let rz=await dot(r,z,N); const b0=Math.sqrt(await dot(bb,bb,N));
let it=0, rn=0;
for(;it<500;it++){
  spmv(M,p,Ap,N);
  const pAp=await dot(p,Ap,N);
  const alpha=rz/pAp;
  axpy(alpha,p,x,N);                 // x += α p
  axpy(-alpha,Ap,r,N);               // r -= α Ap
  rn=Math.sqrt(await dot(r,r,N));
  if(rn/b0<1e-5){it++;break;}
  disp(MUL,[r,dinv,z],[N1(N),1,1]);  // z = M^-1 r
  const rzNew=await dot(r,z,N);
  const beta=rzNew/rz;
  scal(beta,p,N); axpy(1.0,z,p,N);   // p = z + β p
  rz=rzNew;
}
const xg=await readf(x,N);
let emax=0; for(let k=0;k<N;k++)emax=Math.max(emax,Math.abs(xg[k]-xt[k]));
console.log(`2-D Poisson ${n}x${n} (N=${N}), Jacobi-PCG on Metal:`);
console.log(`  iterations: ${it}`);
console.log(`  relative residual ‖r‖/‖b‖: ${(rn/b0).toExponential(2)}`);
console.log(`  max |x_gpu - x_true|: ${emax.toExponential(3)}`);
const ok = (rn/b0<1e-5) && emax<1e-3;
console.log(`\n${ok?"✓ GPU PCG converged to the analytic solution":"✗ did not converge"}`);
Deno.exit(ok?0:1);
