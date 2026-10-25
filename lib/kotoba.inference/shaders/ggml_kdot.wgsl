struct Meta {
  rows: u32,
  cols: u32,
  tensor_type: u32,
  positions: u32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read> weights: array<u32>;
@group(0) @binding(2) var<storage, read> q8: array<u32>;
@group(0) @binding(3) var<storage, read_write> output: array<f32>;

fn weight_byte(offset: u32) -> u32 {
  let word = weights[offset >> 2u];
  return (word >> ((offset & 3u) * 8u)) & 255u;
}

fn q8_byte(offset: u32) -> u32 {
  let word = q8[offset >> 2u];
  return (word >> ((offset & 3u) * 8u)) & 255u;
}

fn signed_weight(offset: u32) -> i32 {
  let x = weight_byte(offset);
  return select(i32(x), i32(x) - 256, x >= 128u);
}

fn signed_q8(offset: u32) -> i32 {
  let x = q8_byte(offset);
  return select(i32(x), i32(x) - 256, x >= 128u);
}

fn signed_i16_q8(offset: u32) -> i32 {
  let x = q8_byte(offset) | (q8_byte(offset + 1u) << 8u);
  return select(i32(x), i32(x) - 65536, x >= 32768u);
}

fn weight_half(offset: u32) -> f32 {
  let pair = unpack2x16float(weights[offset >> 2u]);
  return select(pair.x, pair.y, (offset & 2u) != 0u);
}

fn q8_float(offset: u32) -> f32 {
  return bitcast<f32>(q8[offset >> 2u]);
}

fn q4_scale(base: u32, j: u32) -> i32 {
  if j < 4u { return i32(weight_byte(base + 4u + j) & 63u); }
  return i32((weight_byte(base + 8u + j) & 15u) |
             ((weight_byte(base + j) >> 6u) << 4u));
}

fn q4_min(base: u32, j: u32) -> i32 {
  if j < 4u { return i32(weight_byte(base + 8u + j) & 63u); }
  return i32((weight_byte(base + 8u + j) >> 4u) |
             ((weight_byte(base + 4u + j) >> 6u) << 4u));
}

fn q4_value(base: u32, index: u32) -> i32 {
  let group = index / 64u;
  let within = index & 63u;
  let packed = weight_byte(base + 16u + group * 32u + (within & 31u));
  return i32(select(packed & 15u, packed >> 4u, within >= 32u));
}

fn q6_value(base: u32, index: u32) -> i32 {
  let group = index / 128u;
  let within = index & 127u;
  let lane = within & 31u;
  let ql_base = base + group * 64u;
  let qh = weight_byte(base + 128u + group * 32u + lane);
  if within < 32u {
    return i32((weight_byte(ql_base + lane) & 15u) | ((qh & 3u) << 4u)) - 32;
  }
  if within < 64u {
    return i32((weight_byte(ql_base + 32u + lane) & 15u) | (((qh >> 2u) & 3u) << 4u)) - 32;
  }
  if within < 96u {
    return i32((weight_byte(ql_base + lane) >> 4u) | (((qh >> 4u) & 3u) << 4u)) - 32;
  }
  return i32((weight_byte(ql_base + 32u + lane) >> 4u) | (((qh >> 6u) & 3u) << 4u)) - 32;
}

@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let row = gid.x;
  let position = gid.y;
  if row >= params.rows || position >= params.positions { return; }
  let blocks = params.cols / 256u;
  let row_bytes = blocks * select(210u, 144u, params.tensor_type == 12u);
  var sums: array<f32, 8>;
  for (var lane = 0u; lane < 8u; lane++) { sums[lane] = 0.0; }
  var sumf = 0.0;

  for (var block = 0u; block < blocks; block++) {
    let wb = row * row_bytes + block * select(210u, 144u, params.tensor_type == 12u);
    let yb = (position * blocks + block) * 292u;
    let yd = q8_float(yb);
    var aux: array<i32, 8>;
    for (var lane = 0u; lane < 8u; lane++) { aux[lane] = 0; }
    if params.tensor_type == 12u {
      var sumi = 0;
      for (var j = 0u; j < 16u; j++) { sumi += signed_i16_q8(yb + 260u + j * 2u) * q4_min(wb, j / 2u); }
      for (var j = 0u; j < 8u; j++) {
        let scale = q4_scale(wb, j);
        for (var i = 0u; i < 32u; i++) { let index = j*32u+i; let lane=i&7u; aux[lane] += scale*signed_q8(yb+4u+index)*q4_value(wb,index); }
      }
      let d=weight_half(wb)*yd;for(var lane=0u;lane<8u;lane++){sums[lane]+=d*f32(aux[lane]);}
      sumf-=weight_half(wb+2u)*yd*f32(sumi);
    } else {
      for(var j=0u;j<16u;j++){let scale=signed_weight(wb+192u+j);for(var i=0u;i<16u;i++){let index=j*16u+i;let lane=i&7u;aux[lane]+=scale*signed_q8(yb+4u+index)*q6_value(wb,index);}}
      let d=weight_half(wb+208u)*yd;for(var lane=0u;lane<8u;lane++){sums[lane]+=d*f32(aux[lane]);}
    }
  }
  for(var lane=0u;lane<8u;lane++){sumf+=sums[lane];}
  output[position*params.rows+row]=sumf;
}
