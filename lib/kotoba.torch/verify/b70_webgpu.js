// JVM-free WebGPU/Vulkan qualification for Intel Arc Pro B70 (PCI 8086:e223).
const requireB70 = Deno.args.includes("--require-b70");
if (!navigator.gpu) throw new Error("WebGPU is unavailable");
const adapter = await navigator.gpu.requestAdapter({ powerPreference: "high-performance" });
if (!adapter) throw new Error("no WebGPU adapter");
const info = adapter.info ?? {};
const identity = JSON.stringify(info).toLowerCase();
let pci = {};
try {
  pci = {
    vendor: (await Deno.readTextFile("/sys/class/drm/renderD128/device/vendor")).trim().toLowerCase(),
    device: (await Deno.readTextFile("/sys/class/drm/renderD128/device/device")).trim().toLowerCase(),
  };
} catch (error) {
  // Non-Linux hosts rely on adapter.info; Linux native builds are allowed only
  // these non-secret sysfs identity files.
  pci = { error: String(error) };
}
const b70 = (pci.vendor === "0x8086" && pci.device === "0xe223") ||
  (identity.includes("intel") &&
   (identity.includes("bmg") || identity.includes("b70") || identity.includes("e223")));
if (requireB70 && !b70) {
  throw new Error(`expected Intel Arc B70, got adapter=${JSON.stringify(info)} pci=${JSON.stringify(pci)}`);
}
if (identity.includes("llvmpipe") || identity.includes("software")) {
  throw new Error(`software adapter rejected: ${JSON.stringify(info)}`);
}

const device = await adapter.requestDevice();
const input = new Float32Array([1, 2, 3, 4]);
const storage = device.createBuffer({
  size: input.byteLength,
  usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_DST | GPUBufferUsage.COPY_SRC,
});
device.queue.writeBuffer(storage, 0, input);
const readback = device.createBuffer({
  size: input.byteLength,
  usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
});
const module = device.createShaderModule({ code: `
@group(0) @binding(0) var<storage, read_write> xs: array<f32>;
@compute @workgroup_size(4) fn main(@builtin(global_invocation_id) id: vec3<u32>) {
  xs[id.x] = xs[id.x] * 2.0 + 1.0;
}` });
const pipeline = device.createComputePipeline({
  layout: "auto", compute: { module, entryPoint: "main" },
});
const bind = device.createBindGroup({
  layout: pipeline.getBindGroupLayout(0), entries: [{ binding: 0, resource: { buffer: storage } }],
});
const encoder = device.createCommandEncoder();
const pass = encoder.beginComputePass();
pass.setPipeline(pipeline); pass.setBindGroup(0, bind); pass.dispatchWorkgroups(1); pass.end();
encoder.copyBufferToBuffer(storage, 0, readback, 0, input.byteLength);
device.queue.submit([encoder.finish()]);
await readback.mapAsync(GPUMapMode.READ);
const output = [...new Float32Array(readback.getMappedRange().slice(0))];
readback.unmap(); storage.destroy(); readback.destroy(); device.destroy();
if (JSON.stringify(output) !== JSON.stringify([3, 5, 7, 9])) {
  throw new Error(`WebGPU compute mismatch: ${JSON.stringify(output)}`);
}
console.log(JSON.stringify({
  ok: true, backend: "webgpu-vulkan", device: "intel-arc-b70",
  adapter: info, pci, output,
}));
