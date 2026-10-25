const shader = await Deno.readTextFile(new URL("../shaders/ggml_kdot.wgsl", import.meta.url));
const q4 = "f516b322fefdfffdfdfefcffeeceefcf4095ea4f94e93e84d92e83d82d73c81d62b71c61b60b51a6fb50a5fa4f95ea3fd82d72c71c62c71c61b60b51a6fb50a5fa4f94e93e94e93e83d82d73c82d72c751a6fb4095ea4f95ea3f84d92e74c92e73c81d62b71c62b70c51a6fb41a6fb40d92e73c82d73c81d62b71c62b70c51a6fb4196eb4095ea3f84d93e84d92e73c8";
const q6 = "3085aa0f6387dc3055ba1e3287eb00655702ce7925f0ac5713ce7a45f1ac68133189c1146ca4e63f87c9115aace43c7f0a2ea3385cd1658a0e83a73cb0d569ee9c1743ce4a65f17c9813aeca45c1fc78ec3186ca1f54a7ec3175ca0f5297ec208bb6015e89e3306bb6033e98e5106bb802ce7925f0ac5713ce7a45f1ac6813ceec3542ef35429f35429f38429fe8429f17ca6017ca6117cabd17cabd14cabd20db06b1db0671dc0671ec0671ac0b71ac28825f28855f28f55f28f55228f58228837f6d81887c806e7f847b7f6d81857cb08a";
const q8 = "c8e3f13b8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bcc5cdd6dee7eff800081119222a333b444c555d666e777f8189929aa3abb4bc08fc79038ffcfa0217fd7b029efdfc0126fe7d01adfefe0035ff7f00bcff0000";

const bytes = (hex) => Uint8Array.from(hex.match(/../g), x => parseInt(x, 16));
const adapter = await navigator.gpu.requestAdapter();
if (!adapter) throw new Error("WebGPU adapter unavailable");
const device = await adapter.requestDevice();
device.pushErrorScope("validation");
const module = device.createShaderModule({code: shader});
const pipeline = device.createComputePipeline({layout: "auto", compute: {module, entryPoint: "main"}});
const SU = GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST;
const UU = GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST;
const buffer = (data, usage) => {
  const size = Math.max(16, Math.ceil(data.byteLength / 4) * 4);
  const b = device.createBuffer({size, usage});
  const upload = data.byteLength === size ? data : (() => { const p = new Uint8Array(size); p.set(new Uint8Array(data.buffer, data.byteOffset, data.byteLength)); return p; })();
  device.queue.writeBuffer(b, 0, upload);
  return b;
};

async function run(type, weightData, inputData=bytes(q8), rows=1, cols=256) {
  const meta = buffer(new Uint32Array([rows, cols, type, 1]), UU);
  const weights = buffer(typeof weightData === "string" ? bytes(weightData) : weightData, SU);
  const input = buffer(inputData, SU);
  const output = buffer(new Float32Array(rows), SU);
  const bg = device.createBindGroup({layout: pipeline.getBindGroupLayout(0), entries: [meta, weights, input, output].map((b, i) => ({binding:i, resource:{buffer:b}}))});
  const encoder = device.createCommandEncoder();
  const pass = encoder.beginComputePass();
  pass.setPipeline(pipeline); pass.setBindGroup(0, bg); pass.dispatchWorkgroups(Math.ceil(rows/64),1,1); pass.end();
  const staging = device.createBuffer({size:rows*4, usage:GPUBufferUsage.COPY_DST|GPUBufferUsage.MAP_READ});
  encoder.copyBufferToBuffer(output, 0, staging, 0, rows*4);
  const started = performance.now();
  device.queue.submit([encoder.finish()]);
  await staging.mapAsync(GPUMapMode.READ);
  return {value:new Float32Array(staging.getMappedRange().slice(0))[0], milliseconds:performance.now()-started};
}

const q4Result = await run(12, q4), q4Actual=q4Result.value;
const q6Result = await run(14, q6), q6Actual=q6Result.value;
const validation = await device.popErrorScope();
if (validation) throw validation;
const close = (a,b) => Math.abs(a-b) <= 2e-5;
if (!close(q4Actual, -3.695021629333496)) throw new Error(`Q4 Metal mismatch: ${q4Actual}`);
if (!close(q6Actual, -3.70485520362854)) throw new Error(`Q6 Metal mismatch: ${q6Actual}`);
const repeat = (unit, n) => { const out=new Uint8Array(unit.length*n);for(let i=0;i<n;i++)out.set(unit,i*unit.length);return out; };
const blocks=10, rows=10240, q4Row=repeat(bytes(q4),blocks), q4Matrix=repeat(q4Row,rows), q8Input=repeat(bytes(q8),blocks);
const bench=await run(12,q4Matrix,q8Input,rows,blocks*256);
console.log(JSON.stringify({"kotodama/metal-kdot":"ok",gpu:adapter.info?.description,q4:q4Actual,q6:q6Actual,"q4-10240x2560-ms":bench.milliseconds}));
