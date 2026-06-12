// Element-wise SiLU activation: y[i] = x[i] * sigmoid(x[i])

struct Meta {
    total: u32,
    _p0: u32,
    _p1: u32,
    _p2: u32,
}

@group(0) @binding(0) var<uniform> uniforms: Meta;
@group(0) @binding(1) var<storage, read> input: array<f32>;
@group(0) @binding(2) var<storage, read_write> output: array<f32>;

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let idx = gid.x;
    if idx >= uniforms.total { return; }
    let x = input[idx];
    output[idx] = x / (1.0 + exp(-x));
}
