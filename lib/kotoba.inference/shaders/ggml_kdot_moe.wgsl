// ggml K-quant dot over a PACKED expert tensor with an in-kernel expert gather
// (Nex-N2.5-mini MoE: ffn_{gate,up,down}_exps are [cols, rows_per_expert, 256]
// with each expert's rows contiguous). Root ADR-2609182100 D1 / co-scientist
// iteration 2 hypothesis N3: the router's top-k ids stay on the GPU -- this
// kernel reads them from a storage buffer, so a decode step never returns to
// the host to pick bind groups for the chosen experts.
//
// Same dequant arithmetic and helpers as ggml_kdot_wg.wgsl (Q4_K 12, Q5_K 13,
// Q6_K 14, IQ4_XS 23). Differences:
//   Meta.rows            = rows per expert (512 for gate/up, 2048 for down)
//   Meta.positions       = n_selected experts (8)
//   Meta.input_per_expert: 0 -> every expert reads q8 row 0 (gate/up share the
//                          block input); 1 -> expert slot e reads q8 row e (down
//                          reads each expert's own activation)
//   binding 4 expert_ids : u32[n_selected], produced by the top-k kernel
//   output[e * rows + row], e = selection slot (not expert id)
// Dispatch: (rows, n_selected, 1) workgroups.

struct Meta {
  rows: u32,
  cols: u32,
  tensor_type: u32,
  positions: u32,
  input_per_expert: u32,
  _pad0: u32,
  _pad1: u32,
  _pad2: u32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read> weights: array<u32>;
@group(0) @binding(2) var<storage, read> q8: array<u32>;
@group(0) @binding(3) var<storage, read_write> output: array<f32>;
@group(0) @binding(4) var<storage, read> expert_ids: array<u32>;
var<workgroup> partial: array<f32, 64>;

fn weight_byte(offset: u32) -> u32 {
  let word = weights[offset >> 2u];
  return (word >> ((offset & 3u) * 8u)) & 255u;
}

fn q8_byte(offset: u32) -> u32 {
  let word = q8[offset >> 2u];
  return (word >> ((offset & 3u) * 8u)) & 255u;
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

// Four signed q8 values packed in one word (byte offset must be 4-aligned).
fn q8_word_i8(offset: u32) -> vec4<i32> {
  let w = q8[offset >> 2u];
  return vec4<i32>(
    i32(w << 24u) >> 24u,
    i32(w << 16u) >> 24u,
    i32(w << 8u) >> 24u,
    i32(w) >> 24u);
}

// Four consecutive Q4_K values for `index .. index+3` of one block: they sit in
// four consecutive bytes of one 32-byte group, all low or all high nibbles.
fn q4_word_values(base: u32, index: u32) -> vec4<i32> {
  let group = index / 64u;
  let within = index & 63u;
  let w = weights[(base + 16u + group * 32u + (within & 31u)) >> 2u];
  let shift = select(0u, 4u, within >= 32u);
  return vec4<i32>(
    i32((w >> shift) & 15u),
    i32((w >> (8u + shift)) & 15u),
    i32((w >> (16u + shift)) & 15u),
    i32((w >> (24u + shift)) & 15u));
}

// A u32 at an arbitrary byte offset. Q4_K blocks are 144 bytes and Q8_K rows
// 292, both multiples of 4, so their words are aligned; Q6_K blocks are 210
// bytes, so from the second block on every word straddles two stored words.
fn weight_u32_at(offset: u32) -> u32 {
  let w0 = weights[offset >> 2u];
  let shift = (offset & 3u) * 8u;
  if shift == 0u { return w0; }
  let w1 = weights[(offset >> 2u) + 1u];
  return (w0 >> shift) | (w1 << (32u - shift));
}

// Four consecutive Q6_K values for `index .. index+3`: same ql word, same qh
// word, same nibble half and same qh bit pair.
fn q6_word_values(base: u32, index: u32) -> vec4<i32> {
  let group = index / 128u;
  let within = index & 127u;
  let lane = within & 31u;
  let ql_base = base + group * 64u;
  let qh = weight_u32_at(base + 128u + group * 32u + lane);
  let quarter = within / 32u;                  // 0..3
  let ql = weight_u32_at(ql_base + select(0u, 32u, (quarter & 1u) == 1u) + lane);
  let ql_shift = select(0u, 4u, quarter >= 2u); // quarters 2,3 read the high nibble
  let qh_shift = quarter * 2u;                  // bit pair per quarter
  return vec4<i32>(
    i32(((ql >> ql_shift) & 15u) | (((qh >> qh_shift) & 3u) << 4u)) - 32,
    i32(((ql >> (8u + ql_shift)) & 15u) | (((qh >> (8u + qh_shift)) & 3u) << 4u)) - 32,
    i32(((ql >> (16u + ql_shift)) & 15u) | (((qh >> (16u + qh_shift)) & 3u) << 4u)) - 32,
    i32(((ql >> (24u + ql_shift)) & 15u) | (((qh >> (24u + qh_shift)) & 3u) << 4u)) - 32);
}

// IQ4_XS non-linear codebook (ggml-common.h kvalues_iq4nl).
// codebook packed as 16 signed bytes in four u32 words; lookup = shift + sign-extend (no memory).
fn kv_lookup(n: u32) -> i32 {
  let w = select(select(0xBFAD9881u, 0xF6EADDCFu, n >= 4u), select(0x26190D01u, 0x71594535u, n >= 12u), n >= 8u);
  return (i32(w << ((3u - (n & 3u)) * 8u))) >> 24u;
}

// Four consecutive Q5_K values for `index .. index+3`: Q4_K nibbles (qs @48,
// 32 bytes per 64-group) plus the fifth bit from qh (@16, one byte per lane,
// bit 2*group for the low-nibble half and 2*group+1 for the high half).
fn q5_word_values(base: u32, index: u32) -> vec4<i32> {
  let group = index / 64u;
  let within = index & 63u;
  let lane = within & 31u;
  let hi_half = within >= 32u;
  let qs = weights[(base + 48u + group * 32u + lane) >> 2u];
  let qh = weights[(base + 16u + lane) >> 2u];
  let shift = select(0u, 4u, hi_half);
  let bit = 2u * group + select(0u, 1u, hi_half);
  return vec4<i32>(
    i32(((qs >> shift) & 15u) | (((qh >> bit) & 1u) << 4u)),
    i32(((qs >> (8u + shift)) & 15u) | (((qh >> (8u + bit)) & 1u) << 4u)),
    i32(((qs >> (16u + shift)) & 15u) | (((qh >> (16u + bit)) & 1u) << 4u)),
    i32(((qs >> (24u + shift)) & 15u) | (((qh >> (24u + bit)) & 1u) << 4u)));
}

// Four consecutive IQ4_XS codebook values for `index .. index+3`: sub-block
// ib = index/32 owns qs[ib*16 .. ib*16+15] (@8); values 0..15 of the sub-block
// are the low nibbles, 16..31 the high nibbles of the same 16 bytes.
fn iq4xs_word_values(base: u32, index: u32) -> vec4<i32> {
  let ib = index / 32u;
  let within = index & 31u;
  let hi = within >= 16u;
  let w = weights[(base + 8u + ib * 16u + select(within, within - 16u, hi)) >> 2u];
  let shift = select(0u, 4u, hi);
  return vec4<i32>(
    kv_lookup((w >> shift) & 15u),
    kv_lookup((w >> (8u + shift)) & 15u),
    kv_lookup((w >> (16u + shift)) & 15u),
    kv_lookup((w >> (24u + shift)) & 15u));
}

// IQ4_XS 6-bit sub-block scale, before the -32.
fn iq4xs_scale(base: u32, ib: u32) -> i32 {
  let scales_h = weights[base >> 2u] >> 16u;               // u16 @2 (d is @0 in the same word)
  let scales_l = weight_byte(base + 4u + ib / 2u);
  return i32(((scales_l >> (4u * (ib & 1u))) & 15u) | (((scales_h >> (2u * ib)) & 3u) << 4u));
}

fn block_bytes_of(t: u32) -> u32 {
  switch t {
    case 12u: { return 144u; }
    case 13u: { return 176u; }
    case 14u: { return 210u; }
    case 23u: { return 136u; }
    default: { return 0u; }
  }
}

@compute @workgroup_size(64)
fn main(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let row = wg.x;
  let position = wg.y;            // selection slot e
  let t = lid.x;
  let expert = expert_ids[position];
  let in_row = select(0u, position, params.input_per_expert == 1u);
  let blocks = params.cols / 256u;
  let tt = params.tensor_type;
  let block_bytes = block_bytes_of(tt);
  let row_bytes = blocks * block_bytes;
  let index = t * 4u;                 // this thread's four values inside every block
  var acc = 0.0;                      // sum over blocks of d*yd*aux (thread's share)
  var mins = 0.0;                     // sum over blocks of dmin*yd*sumi (threads 0..15 only, Q4_K)

  if row < params.rows && position < params.positions {
    for (var block = 0u; block < blocks; block++) {
      let wb = (expert * params.rows + row) * row_bytes + block * block_bytes;
      let yb = (in_row * blocks + block) * 292u;
      let yd = q8_float(yb);
      let y = q8_word_i8(yb + 4u + index);
      if tt == 12u || tt == 13u {
        // Q4_K and Q5_K share d/dmin/scales; Q5_K adds the fifth bit.
        let j = index / 32u;
        let scale = q4_scale(wb, j);
        var q: vec4<i32>;
        if tt == 12u { q = q4_word_values(wb, index); } else { q = q5_word_values(wb, index); }
        let aux = scale * (y.x * q.x + y.y * q.y + y.z * q.z + y.w * q.w);
        acc += weight_half(wb) * yd * f32(aux);
        if t < 16u {
          // ggml: sumi = sum_j bsums[j] * mins[j/2]; sixteen terms, one per thread.
          mins += weight_half(wb + 2u) * yd * f32(signed_i16_q8(yb + 260u + t * 2u) * q4_min(wb, t / 2u));
        }
      } else if tt == 23u {
        let ib = index / 32u;
        let ls = iq4xs_scale(wb, ib) - 32;
        let q = iq4xs_word_values(wb, index);
        let sumi = y.x * q.x + y.y * q.y + y.z * q.z + y.w * q.w;
        acc += weight_half(wb) * yd * f32(ls) * f32(sumi);
      } else {
        let j = index / 16u;
        let sb = weight_byte(wb + 192u + j);
        let scale = select(i32(sb), i32(sb) - 256, sb >= 128u);
        let q = q6_word_values(wb, index);
        let aux = scale * (y.x * q.x + y.y * q.y + y.z * q.z + y.w * q.w);
        acc += weight_half(wb + 208u) * yd * f32(aux);
      }
    }
  }
  partial[t] = acc - mins;
  workgroupBarrier();
  for (var stride = 32u; stride > 0u; stride = stride >> 1u) {
    if t < stride { partial[t] += partial[t + stride]; }
    workgroupBarrier();
  }
  if t == 0u && row < params.rows && position < params.positions {
    output[position * params.rows + row] = partial[0];
  }
}
