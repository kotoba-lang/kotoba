// ggml K-quant dot, f32 activations, SUB-BLOCK-PER-THREAD layout (M2b kaizen, iteration 3, v3).
//
// A workgroup owns 8 rows. Per 256-value block: the 64 threads first stage the block's 256
// activation values into workgroup memory (4 each), then thread t = (row r = t/8, sub-block
// j = t%8) dequantises its own 32 weights (4 u32 words) with ONE scale/min computation and
// accumulates 32 MACs against the shared x. Row partials (8 threads per row) are reduced at
// the end. Compared with ggml_kdot_f32 (thread = 4 values, 64 threads per row, x re-read per
// row): 8x fewer scale/min decodes, x read once per workgroup per block, 4x more independent
// work per thread. Same bindings, same Meta, same dequant helpers.
// Dispatch: (ceil(rows_per_expert / 8), n_selected, 1).
const ROWS_PER_WG: u32 = 8u;

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
@group(0) @binding(2) var<storage, read> x: array<f32>;      // [n_inputs * cols] f32 activations
@group(0) @binding(3) var<storage, read_write> output: array<f32>;
@group(0) @binding(4) var<storage, read> expert_ids: array<u32>;

fn weight_byte(offset: u32) -> u32 {
  let word = weights[offset >> 2u];
  return (word >> ((offset & 3u) * 8u)) & 255u;
}



fn weight_half(offset: u32) -> f32 {
  let pair = unpack2x16float(weights[offset >> 2u]);
  return select(pair.x, pair.y, (offset & 2u) != 0u);
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
  var out: vec4<i32>;
  for (var b = 0u; b < 4u; b++) {
    let lo = (ql >> (b * 8u + ql_shift)) & 15u;
    let hi = ((qh >> (b * 8u + qh_shift)) & 3u) << 4u;
    out[b] = i32(lo | hi) - 32;
  }
  return out;
}

// IQ4_XS non-linear codebook (ggml-common.h kvalues_iq4nl).
var<private> kvalues_iq4nl: array<i32, 16> = array<i32, 16>(-127, -104, -83, -65, -49, -35, -22, -10, 1, 13, 25, 38, 53, 69, 89, 113);

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
  var out: vec4<i32>;
  for (var b = 0u; b < 4u; b++) {
    let nib = (qs >> (b * 8u + shift)) & 15u;
    let h = ((qh >> (b * 8u + bit)) & 1u) << 4u;
    out[b] = i32(nib | h);
  }
  return out;
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
    kvalues_iq4nl[(w >> shift) & 15u],
    kvalues_iq4nl[(w >> (8u + shift)) & 15u],
    kvalues_iq4nl[(w >> (16u + shift)) & 15u],
    kvalues_iq4nl[(w >> (24u + shift)) & 15u]);
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

// IQ4_XS codebook as four packed u32 constants (see ggml_kdot_wg.wgsl).
fn kv_lookup(n: u32) -> i32 {
  let w = select(select(0xBFAD9881u, 0xF6EADDCFu, n >= 4u), select(0x26190D01u, 0x71594535u, n >= 12u), n >= 8u);
  return (i32(w << ((3u - (n & 3u)) * 8u))) >> 24u;
}
var<workgroup> xs: array<f32, 256>;
var<workgroup> partial: array<f32, 64>;

// 32 dequantised values of sub-block j (values j*32 .. j*32+31) dotted with xs[j*32 ..]
fn subblock_dot(tt: u32, wb: u32, j: u32) -> f32 {
  var acc = 0.0;
  if tt == 23u {
    let ls = f32(iq4xs_scale(wb, j) - 32);
    // qs[j*16 .. j*16+15] @8: low nibbles = values 0..15, high nibbles = 16..31
    for (var w = 0u; w < 4u; w++) {
      let word = weights[(wb + 8u + j * 16u + w * 4u) >> 2u];
      let base = j * 32u + w * 4u;
      for (var b = 0u; b < 4u; b++) {
        let byte = (word >> (b * 8u)) & 255u;
        acc += f32(kv_lookup(byte & 15u)) * xs[base + b] + f32(kv_lookup(byte >> 4u)) * xs[base + 16u + b];
      }
    }
    return weight_half(wb) * ls * acc;
  } else if tt == 12u || tt == 13u {
    let scale = f32(q4_scale(wb, j)); let mn = f32(q4_min(wb, j));
    var xsum = 0.0;
    // sub-block j: group = j/2 (64 values), half = j%2 (low/high nibble), bytes qs[group*32 .. +32]
    let group = j / 2u; let hi = (j & 1u) == 1u; let shift = select(0u, 4u, hi);
    let qs_off = select(16u, 48u, tt == 13u) + group * 32u;
    for (var w = 0u; w < 8u; w++) {
      let word = weights[(wb + qs_off + w * 4u) >> 2u];
      var hword = 0u; if tt == 13u { hword = weights[(wb + 16u + w * 4u) >> 2u]; }
      let bit = 2u * group + select(0u, 1u, hi);
      for (var b = 0u; b < 4u; b++) {
        let i = w * 4u + b;
        var q = (word >> (b * 8u + shift)) & 15u;
        if tt == 13u { q |= ((hword >> (b * 8u + bit)) & 1u) << 4u; }
        let xv = xs[j * 32u + i];
        acc += f32(q) * xv; xsum += xv;
      }
    }
    return weight_half(wb) * scale * acc - weight_half(wb + 2u) * mn * xsum;
  } else {
    // Q6_K: two 16-value scale groups per 32 values; reuse the per-value helper
    var out = 0.0;
    for (var half = 0u; half < 2u; half++) {
      let jj = j * 2u + half;
      let sb = weight_byte(wb + 192u + jj);
      let scale = f32(select(i32(sb), i32(sb) - 256, sb >= 128u));
      var a = 0.0;
      for (var i = 0u; i < 16u; i += 4u) {
        let q = q6_word_values(wb, jj * 16u + i);
        let base = jj * 16u + i;
        a += f32(q.x) * xs[base] + f32(q.y) * xs[base + 1u] + f32(q.z) * xs[base + 2u] + f32(q.w) * xs[base + 3u];
      }
      out += scale * a;
    }
    return weight_half(wb + 208u) * out;
  }
}

@compute @workgroup_size(64)
fn main(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let row0 = wg.x * ROWS_PER_WG;
  let position = wg.y;
  let t = lid.x;
  let r = t / 8u; let j = t % 8u;
  let expert = expert_ids[position];
  let in_row = select(0u, position, params.input_per_expert == 1u);
  let blocks = params.cols / 256u;
  let tt = params.tensor_type;
  let block_bytes = block_bytes_of(tt);
  let row_bytes = blocks * block_bytes;
  let row = row0 + r;
  let live = row < params.rows && position < params.positions;
  var acc = 0.0;
  for (var block = 0u; block < blocks; block++) {
    // stage x for this block
    let xb = in_row * params.cols + block * 256u + t * 4u;
    xs[t * 4u] = x[xb]; xs[t * 4u + 1u] = x[xb + 1u]; xs[t * 4u + 2u] = x[xb + 2u]; xs[t * 4u + 3u] = x[xb + 3u];
    workgroupBarrier();
    if live {
      let wb = (expert * params.rows + row) * row_bytes + block * block_bytes;
      acc += subblock_dot(tt, wb, j);
    }
    workgroupBarrier();
  }
  partial[t] = acc;
  workgroupBarrier();
  // 8 threads per row: t = r*8 + j
  if j < 4u { partial[t] += partial[t + 4u]; } workgroupBarrier();
  if j < 2u { partial[t] += partial[t + 2u]; } workgroupBarrier();
  if j == 0u && live { output[position * params.rows + row] = partial[t] + partial[t + 1u]; }
}
