struct Meta {
  rows: u32,
  cols: u32,
  _p0: u32,
  _p1: u32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read_write> data: array<f32>;

@compute @workgroup_size(256)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let row = gid.x;
  if (row >= params.rows) { return; }

  let offset = row * params.cols;
  let cols = params.cols;

  var m: f32 = -1e30;
  for (var i: u32 = 0u; i < cols; i++) {
    m = max(m, data[offset + i]);
  }

  var s: f32 = 0.0;
  for (var i: u32 = 0u; i < cols; i++) {
    let e = exp(data[offset + i] - m);
    data[offset + i] = e;
    s += e;
  }

  let inv_s = 1.0 / s;
  for (var i: u32 = 0u; i < cols; i++) {
    data[offset + i] *= inv_s;
  }
}
