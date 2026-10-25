// Mamba2 SSM output computation:
//   y[t, i] = sum_s(C[t, i, s] * dt[t, i] * B[t, i, s]) + D[i] * x[t, i]
//
// Layout (row-major):
//   x_in:  [seq_len * inner]           x_in[t * inner + i]
//   dt:    [seq_len * inner]           dt[t * inner + i]
//   B:     [seq_len * inner * state_dim]  B[(t * inner + i) * state_dim + s]
//   C:     [seq_len * inner * state_dim]  C[(t * inner + i) * state_dim + s]
//   D:     [inner]                     D[i]
//   output:[seq_len * inner]           output[t * inner + i]

struct Meta {
    seq_len: u32,
    inner: u32,
    state_dim: u32,
    _pad: u32,
}

@group(0) @binding(0) var<uniform> uniforms: Meta;
@group(0) @binding(1) var<storage, read> x_in: array<f32>;
@group(0) @binding(2) var<storage, read> dt: array<f32>;
@group(0) @binding(3) var<storage, read> B: array<f32>;
@group(0) @binding(4) var<storage, read> C: array<f32>;
@group(0) @binding(5) var<storage, read> D: array<f32>;
@group(0) @binding(6) var<storage, read_write> output: array<f32>;

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
    let idx = gid.x;
    let total = uniforms.seq_len * uniforms.inner;
    if idx >= total { return; }

    let t = idx / uniforms.inner;
    let i = idx % uniforms.inner;

    let dt_val = dt[idx];
    let base = idx * uniforms.state_dim;

    var acc: f32 = 0.0;
    for (var s: u32 = 0u; s < uniforms.state_dim; s = s + 1u) {
        acc += C[base + s] * dt_val * B[base + s];
    }

    output[idx] = acc + D[i] * x_in[idx];
}
