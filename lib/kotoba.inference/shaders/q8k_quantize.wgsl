// ggml Q8_K activation quantisation on the GPU (root ADR-2609182100 D1, M2).
//
// Turns one f32 activation row into ggml's block_q8_K stream -- the exact
// input layout ggml_kdot(_wg).wgsl reads -- so a decode step never brings the
// hidden state back to the host to quantise it. Reference: ggml-quants.c
// quantize_row_q8_K_ref:
//
//   amax = max |x|, max = the x that attains it (signed)
//   if amax == 0: d = 0, qs = 0, bsums = 0
//   iscale = -127 / max ; qs[j] = min(127, nearest_int(iscale * x[j]))
//   bsums[g] = sum of qs[g*16 .. g*16+15] (16 groups) ; d = 1 / iscale
//
// nearest_int in ggml rounds to nearest, ties to even; WGSL `round` is the
// same rule. Block layout (292 bytes): f32 d @0, i8 qs[256] @4, i16 bsums[16]
// @260. Written as u32 words: 292 % 4 == 0 so every block is word aligned.
//
// One 64-thread workgroup per block: thread t owns x[t*4 .. t*4+3], the
// signed-max is found by a shared-memory tree reduction on (|x|, x) pairs,
// each thread packs its four quantised bytes into one word, and threads 0..15
// form the sixteen bsums from the shared qs array. Dispatch:
// (blocks, rows, 1) with rows = number of activation rows (positions).

struct Meta {
  blocks: u32,     // per row, = cols / 256
  rows: u32,       // activation rows (positions)
  _pad0: u32,
  _pad1: u32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read> x: array<f32>;
@group(0) @binding(2) var<storage, read_write> q8: array<u32>;

var<workgroup> amax_sh: array<f32, 64>;
var<workgroup> max_sh: array<f32, 64>;
var<workgroup> qs_sh: array<i32, 256>;
var<workgroup> bsum_sh: array<i32, 16>;

fn clamp127(v: f32) -> i32 {
  return min(127, i32(round(v)));
}

@compute @workgroup_size(64)
fn main(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let block = wg.x;
  let row = wg.y;
  let t = lid.x;
  if block >= params.blocks || row >= params.rows { return; }
  let xbase = (row * params.blocks + block) * 256u + t * 4u;
  let v = vec4<f32>(x[xbase], x[xbase + 1u], x[xbase + 2u], x[xbase + 3u]);

  // signed max by |x| over this thread's four values
  var amax = abs(v.x); var mx = v.x;
  if abs(v.y) > amax { amax = abs(v.y); mx = v.y; }
  if abs(v.z) > amax { amax = abs(v.z); mx = v.z; }
  if abs(v.w) > amax { amax = abs(v.w); mx = v.w; }
  amax_sh[t] = amax; max_sh[t] = mx;
  workgroupBarrier();
  for (var stride = 32u; stride > 0u; stride = stride >> 1u) {
    if t < stride {
      if amax_sh[t + stride] > amax_sh[t] { amax_sh[t] = amax_sh[t + stride]; max_sh[t] = max_sh[t + stride]; }
    }
    workgroupBarrier();
  }
  let block_amax = amax_sh[0];
  let block_max = max_sh[0];
  let out_base = (row * params.blocks + block) * 292u;  // byte offset of this block

  if block_amax == 0.0 {
    // d = 0, qs = 0, bsums = 0: 73 words of zero.
    q8[(out_base >> 2u) + t] = 0u;
    if t < 9u { q8[(out_base >> 2u) + 64u + t] = 0u; }
    return;
  }
  let iscale = -127.0 / block_max;
  let q = vec4<i32>(clamp127(iscale * v.x), clamp127(iscale * v.y), clamp127(iscale * v.z), clamp127(iscale * v.w));
  qs_sh[t * 4u] = q.x; qs_sh[t * 4u + 1u] = q.y; qs_sh[t * 4u + 2u] = q.z; qs_sh[t * 4u + 3u] = q.w;
  // qs bytes @4: thread t writes word (4 + t*4)/4 = 1 + t
  q8[(out_base >> 2u) + 1u + t] = (u32(q.x) & 255u) | ((u32(q.y) & 255u) << 8u) | ((u32(q.z) & 255u) << 16u) | ((u32(q.w) & 255u) << 24u);
  if t == 0u { q8[out_base >> 2u] = bitcast<u32>(1.0 / iscale); }
  workgroupBarrier();
  // bsums @260: sixteen i16, two per word, words 65..72. Thread g (< 16) sums group g;
  // even g writes the word after reading its odd neighbour's sum from shared memory.
  if t < 16u {
    var s = 0;
    for (var i = 0u; i < 16u; i++) { s += qs_sh[t * 16u + i]; }
    bsum_sh[t] = s;
  }
  workgroupBarrier();
  if t < 8u {
    let lo = u32(bsum_sh[t * 2u]) & 65535u;
    let hi = u32(bsum_sh[t * 2u + 1u]) & 65535u;
    q8[(out_base >> 2u) + 65u + t] = lo | (hi << 16u);
  }
}
