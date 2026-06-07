struct Meta {
  n: u32,
  dim: u32,
  eps: f32,
  _pad: f32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read_write> x: array<f32>;
@group(0) @binding(2) var<storage, read> weight: array<f32>;

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let row = gid.x;
  if (row >= params.n) { return; }

  let d = params.dim;
  let offset = row * d;

  var sum_sq: f32 = 0.0;
  for (var i: u32 = 0u; i < d; i++) {
    let v = x[offset + i];
    sum_sq += v * v;
  }
  let rms = 1.0 / sqrt(sum_sq / f32(d) + params.eps);

  for (var i: u32 = 0u; i < d; i++) {
    x[offset + i] = x[offset + i] * rms * weight[i];
  }
}
