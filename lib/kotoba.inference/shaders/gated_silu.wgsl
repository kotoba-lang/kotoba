struct Meta {
  n: u32,
  ffn_dim: u32,
  _p0: u32,
  _p1: u32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read> input: array<f32>;
@group(0) @binding(2) var<storage, read_write> output: array<f32>;

fn silu(x: f32) -> f32 {
  return x / (1.0 + exp(-x));
}

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let idx = gid.x;
  let total = params.n * params.ffn_dim;
  if (idx >= total) { return; }

  let row = idx / params.ffn_dim;
  let col = idx % params.ffn_dim;
  let in_offset = row * params.ffn_dim * 2u;

  let gate_val = input[in_offset + col];
  let up_val = input[in_offset + params.ffn_dim + col];
  output[idx] = silu(gate_val) * up_val;
}
