// The small per-token ops of a Nex-N2.5-mini (qwen35moe) decode step, one WGSL
// module with one @compute entry point each, so the whole step can be recorded
// into a single command buffer (root ADR-2609182100 D1). Semantics follow
// llama.cpp src/models/qwen35moe.cpp (the control host serving the same GGUF):
//
//   rmsnorm        build_norm(LLM_NORM_RMS): y = x * rsqrt(mean(x^2) + eps) * w      (rows x n)
//   l2norm         build_gdn_l2_norm: y = x / sqrt(sum(x^2) + eps)                    (rows x n)
//   gated_rmsnorm  build_norm_gated: rmsnorm(x, w) * silu(z)                          (rows x n)
//   silu_mul       LLM_FFN_SILU / LLM_FFN_PAR: y = silu(gate) * up                    (n)
//   conv1d_step    ggml_ssm_conv for ONE token: y[c] = sum_{t<4} K[c][t] * x[t][c],
//                  x[3] = current token, x[0..2] = the three previous (ring on GPU),
//                  then silu (conv_output_silu). Also shifts the ring.
//   softmax_topk   build_moe_ffn SOFTMAX + norm_w: p = softmax(logits) over 256,
//                  top-8 ids + weights normalised to sum 1 (times expert_weights_scale)
//   gate_decay     beta = sigmoid(x_beta); g = softplus(x_alpha + dt_bias) * ssm_a
//   weighted_sum   moe_out = sum_e w[e] * expert_out[e]; ffn_out = moe_out +
//                  shexp_out * sigmoid(shared_gate)
//   rope_neox      ggml_rope_multi for text (all position components equal ->
//                  NEOX pairs (i, i + n_rot/2) on the first n_rot dims of each head)
//   attn_decode    build_attn for one query token over T cached positions, GQA,
//                  scale 1/sqrt(head_dim), then * sigmoid(gate) (qwen35 attn gate)
//   argmax         greedy token over n logits (two-stage: per-workgroup then final)
//   add            residual: o = a + b                                                (n)
//   add_rmsnorm    fused residual + norm: o = a + b ; s = rmsnorm(o) * c              (n, one workgroup)
//   f32_matvec     o[r] = sum_i w[r*n + i] * x[i] for f32 weights (router ffn_gate_inp
//                  [256 x 2048], shared-expert gate [1 x 2048]); one workgroup per row

struct Meta {
  n: u32,          // row length / element count
  rows: u32,       // rows (heads)
  aux: u32,        // op-specific: T for attn_decode, n_rot for rope, k for topk, kv_group for attn
  aux2: u32,       // op-specific: position for rope, heads_kv for attn
  eps: f32,
  scale: f32,      // rope theta base as f32 (1e7 fits), or expert_weights_scale, or kq scale
  _p0: f32,
  _p1: f32,
}

@group(0) @binding(0) var<uniform> P: Meta;
@group(0) @binding(1) var<storage, read> a: array<f32>;
@group(0) @binding(2) var<storage, read> b: array<f32>;
@group(0) @binding(3) var<storage, read> c: array<f32>;
@group(0) @binding(4) var<storage, read_write> o: array<f32>;
@group(0) @binding(5) var<storage, read_write> s: array<f32>;   // state / scratch
@group(0) @binding(6) var<storage, read_write> ids: array<u32>;

var<workgroup> red: array<f32, 256>;
var<workgroup> redi: array<u32, 256>;

fn silu(x: f32) -> f32 { return x / (1.0 + exp(-x)); }
fn sigmoid(x: f32) -> f32 { return 1.0 / (1.0 + exp(-x)); }
fn softplus(x: f32) -> f32 { return select(log(1.0 + exp(x)), x, x > 20.0); }

fn wg_sum(t: u32, v: f32) -> f32 {
  red[t] = v;
  workgroupBarrier();
  for (var st = 128u; st > 0u; st = st >> 1u) { if t < st { red[t] += red[t + st]; } workgroupBarrier(); }
  let r = red[0];
  workgroupBarrier();
  return r;
}

// a = x [rows x n], b = w [n] -> o [rows x n]. aux = input row stride in elements (0 -> n):
// the qwen35 attention q projection interleaves [q_h(256) gate_h(256)] per head, so the per-head
// q norm reads rows of 256 at stride 512 and writes them contiguous.
@compute @workgroup_size(256)
fn rmsnorm(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let r = wg.x; let t = lid.x; let n = P.n; let stride = select(P.aux, n, P.aux == 0u);
  let ibase = r * stride; let obase = r * n;
  var ss = 0.0;
  for (var i = t; i < n; i += 256u) { let x = a[ibase + i]; ss += x * x; }
  let tot = wg_sum(t, ss);
  let inv = inverseSqrt(tot / f32(n) + P.eps);
  for (var i = t; i < n; i += 256u) { o[obase + i] = a[ibase + i] * inv * b[i]; }
}

// a = x [rows x n] -> o = x / sqrt(sum x^2 + eps) * scale (scale 0 -> 1). llama.cpp's
// build_gdn_l2_norm is rms_norm(x, eps/n) / sqrt(n), i.e. exactly this; the delta-net q is then
// scaled by 1/sqrt(S_k) (delta-net-base.cpp), which the harness folds into `scale`.
@compute @workgroup_size(256)
fn l2norm(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let r = wg.x; let t = lid.x; let n = P.n; let base = r * n;
  var ss = 0.0;
  for (var i = t; i < n; i += 256u) { let x = a[base + i]; ss += x * x; }
  let tot = wg_sum(t, ss);
  let inv = inverseSqrt(tot + P.eps) * select(P.scale, 1.0, P.scale == 0.0);
  for (var i = t; i < n; i += 256u) { o[base + i] = a[base + i] * inv; }
}

// a = x [rows x n], b = w [n], c = z [rows x n] -> o = rmsnorm(x) * silu(z)
@compute @workgroup_size(256)
fn gated_rmsnorm(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let r = wg.x; let t = lid.x; let n = P.n; let base = r * n;
  var ss = 0.0;
  for (var i = t; i < n; i += 256u) { let x = a[base + i]; ss += x * x; }
  let tot = wg_sum(t, ss);
  let inv = inverseSqrt(tot / f32(n) + P.eps);
  for (var i = t; i < n; i += 256u) { o[base + i] = a[base + i] * inv * b[i] * silu(c[base + i]); }
}

// a = gate [n], b = up [n] -> o
@compute @workgroup_size(256)
fn silu_mul(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x; if i >= P.n { return; }
  o[i] = silu(a[i]) * b[i];
}

// a = x_t [n] (current qkv_mixed), b = ssm_conv1d as stored in the GGUF: dims [4, n], ne0 = 4, i.e.
// CHANNEL-major, the four taps of channel c contiguous at b[c*4 .. c*4+3] with tap 0 on the oldest
// input (ggml_ssm_conv); s = ring [3 x n] of the previous three inputs (s[0] oldest) -> o = silu(conv),
// ring shifted
@compute @workgroup_size(256)
fn conv1d_step(@builtin(global_invocation_id) gid: vec3<u32>) {
  let ch = gid.x; if ch >= P.n { return; }
  let n = P.n;
  let x0 = s[ch]; let x1 = s[n + ch]; let x2 = s[2u * n + ch]; let x3 = a[ch];
  let y = b[ch * 4u] * x0 + b[ch * 4u + 1u] * x1 + b[ch * 4u + 2u] * x2 + b[ch * 4u + 3u] * x3;
  o[ch] = silu(y);
  s[ch] = x1; s[n + ch] = x2; s[2u * n + ch] = x3;
}

// a = logits [256] -> ids[0..k) expert ids, o[0..k) normalised weights * scale. One workgroup.
@compute @workgroup_size(256)
fn softmax_topk(@builtin(local_invocation_id) lid: vec3<u32>) {
  let t = lid.x; let n = P.n; let k = P.aux;
  let x = select(-1e30, a[t], t < n);
  // max
  red[t] = x; workgroupBarrier();
  for (var st = 128u; st > 0u; st = st >> 1u) { if t < st { red[t] = max(red[t], red[t + st]); } workgroupBarrier(); }
  let m = red[0]; workgroupBarrier();
  let e = select(0.0, exp(x - m), t < n);
  let denom = wg_sum(t, e);
  var p = e / denom;
  // k rounds of argmax over the remaining probabilities
  var wsum = 0.0;
  for (var round = 0u; round < k; round++) {
    red[t] = p; redi[t] = t; workgroupBarrier();
    for (var st = 128u; st > 0u; st = st >> 1u) {
      if t < st {
        let other = red[t + st];
        // ties: lower index wins (matches a sequential scan)
        if other > red[t] || (other == red[t] && redi[t + st] < redi[t]) { red[t] = other; redi[t] = redi[t + st]; }
      }
      workgroupBarrier();
    }
    let best = redi[0]; let bp = red[0];
    workgroupBarrier();
    if t == 0u { ids[round] = best; o[round] = bp; }
    if t == best { p = -1.0; }
    wsum += bp;
    workgroupBarrier();
  }
  storageBarrier();
  if t < k { o[t] = o[t] / wsum * P.scale; }
}

// a = [x_alpha (rows) ... x_beta (rows) at element aux2] (one read-only slice of the concatenated
// z|alpha|alpha|beta projection output), b = dt_bias [rows], c = ssm_a [rows] ->
// o[h] = g = softplus(x_alpha + dt) * ssm_a (log decay), o[aux + h] = beta = sigmoid(x_beta).
// aux = 64 in the harness so beta starts 256 bytes in and can be bound as its own range. Everything
// read comes through read-only bindings: WebGPU rejects one buffer bound read-only and read-write
// in the same dispatch, which is what a beta-in-place variant did (measured 2026-09-18).
@compute @workgroup_size(256)
fn gate_decay(@builtin(global_invocation_id) gid: vec3<u32>) {
  let h = gid.x; if h >= P.rows { return; }
  o[h] = softplus(a[h] + b[h]) * c[h];
  o[P.aux + h] = sigmoid(a[P.aux2 + h]);
}

// a = expert_out [k x n], b = weights [k], c = shexp_out [n], s[0] = shared gate logit -> o [n]
@compute @workgroup_size(256)
fn weighted_sum(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x; if i >= P.n { return; }
  var acc = 0.0;
  for (var e = 0u; e < P.aux; e++) { acc += b[e] * a[e * P.n + i]; }
  o[i] = acc + c[i] * sigmoid(s[0]);
}

// a = x [rows(heads) x n(head_dim)] -> o, NEOX pairs (i, i + n_rot/2) on the first n_rot dims,
// theta_i = pos * base^(-2i/n_rot). aux = n_rot, aux2 = pos, scale = base.
@compute @workgroup_size(256)
fn rope_neox(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let h = wg.x; let t = lid.x; let n = P.n; let nrot = P.aux; let half = nrot / 2u; let base = h * n;
  for (var i = t; i < n; i += 256u) {
    if i >= nrot { o[base + i] = a[base + i]; continue; }
    let pair = select(i, i - half, i >= half);
    let theta = f32(P.aux2) * pow(P.scale, -2.0 * f32(pair) / f32(nrot));
    let cs = cos(theta); let sn = sin(theta);
    let x0 = a[base + pair]; let x1 = a[base + pair + half];
    o[base + i] = select(x0 * cs - x1 * sn, x0 * sn + x1 * cs, i >= half);
  }
}

// a = q [heads x d], b = Kcache [T x heads_kv x d], c = Vcache [T x heads_kv x d], s = gate [heads x d]
// -> o [heads x d] = softmax(q.K^T * scale) V * sigmoid(gate). aux = T, aux2 = heads_kv. One workgroup per head,
// T <= 256 per pass (a decode step at longer context tiles over T; this is the reference form).
@compute @workgroup_size(256)
fn attn_decode(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let h = wg.x; let t = lid.x; let d = P.n; let T = P.aux; let hkv = h / (P.rows / P.aux2);
  // score for position t
  var sc = -1e30;
  if t < T {
    var dot = 0.0;
    for (var i = 0u; i < d; i++) { dot += a[h * d + i] * b[(t * P.aux2 + hkv) * d + i]; }
    sc = dot * P.scale;
  }
  red[t] = sc; workgroupBarrier();
  for (var st = 128u; st > 0u; st = st >> 1u) { if t < st { red[t] = max(red[t], red[t + st]); } workgroupBarrier(); }
  let m = red[0]; workgroupBarrier();
  let e = select(0.0, exp(sc - m), t < T);
  let denom = wg_sum(t, e);
  let p = e / denom;
  red[t] = p; workgroupBarrier();           // probabilities visible to all threads
  for (var i = t; i < d; i += 256u) {
    var acc = 0.0;
    for (var tt = 0u; tt < T; tt++) { acc += red[tt] * c[(tt * P.aux2 + hkv) * d + i]; }
    // gate: contiguous [heads x d] when eps == 0, or interleaved q_full layout [h][q(d) gate(d)] when eps < 0
    let gi = select(h * d + i, (h * 2u + 1u) * d + i, P.eps < 0.0);
    o[h * d + i] = acc * sigmoid(s[gi]);
  }
}

// a = logits [n] -> per-workgroup (max, idx) into s / ids; then argmax_final reduces them. aux = number of partials.
@compute @workgroup_size(256)
fn argmax_partial(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let t = lid.x; let n = P.n; let start = wg.x * 4096u;
  var bv = -1e30; var bi = 0u;
  for (var i = start + t; i < min(start + 4096u, n); i += 256u) { let v = a[i]; if v > bv || (v == bv && i < bi) { bv = v; bi = i; } }
  red[t] = bv; redi[t] = bi; workgroupBarrier();
  for (var st = 128u; st > 0u; st = st >> 1u) {
    if t < st { let ov = red[t + st]; let oi = redi[t + st]; if ov > red[t] || (ov == red[t] && oi < redi[t]) { red[t] = ov; redi[t] = oi; } }
    workgroupBarrier();
  }
  if t == 0u { s[wg.x] = red[0]; ids[wg.x] = redi[0]; }
}
@compute @workgroup_size(256)
fn argmax_final(@builtin(local_invocation_id) lid: vec3<u32>) {
  let t = lid.x; let parts = P.aux;
  var bv = -1e30; var bi = 0u;
  for (var i = t; i < parts; i += 256u) { let v = s[i]; let ix = ids[i]; if v > bv || (v == bv && ix < bi) { bv = v; bi = ix; } }
  red[t] = bv; redi[t] = bi; workgroupBarrier();
  for (var st = 128u; st > 0u; st = st >> 1u) {
    if t < st { let ov = red[t + st]; let oi = redi[t + st]; if ov > red[t] || (ov == red[t] && oi < redi[t]) { red[t] = ov; redi[t] = oi; } }
    workgroupBarrier();
  }
  if t == 0u { ids[parts] = redi[0]; o[0] = red[0]; }
}

// a = x [n], b = y [n] -> o = x + y
@compute @workgroup_size(256)
fn add(@builtin(global_invocation_id) gid: vec3<u32>) {
  let i = gid.x; if i >= P.n { return; }
  o[i] = a[i] + b[i];
}

// a = w [rows x n] f32, b = x [n] -> o [rows]; one workgroup per row
@compute @workgroup_size(256)
fn f32_matvec(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let r = wg.x; let t = lid.x; let n = P.n; let base = r * n;
  var acc = 0.0;
  for (var i = t; i < n; i += 256u) { acc += a[base + i] * b[i]; }
  let tot = wg_sum(t, acc);
  if t == 0u { o[r] = tot; }
}

// a = x [n], b = delta [n], c = w [n] -> o = x + delta (the new residual stream), s = rmsnorm(o) * w.
// One workgroup: the sum of squares needs the whole row. Replaces add + rmsnorm (2 dispatches -> 1).
@compute @workgroup_size(256)
fn add_rmsnorm(@builtin(local_invocation_id) lid: vec3<u32>) {
  let t = lid.x; let n = P.n;
  var ss = 0.0;
  for (var i = t; i < n; i += 256u) { let v = a[i] + b[i]; o[i] = v; ss += v * v; }
  let tot = wg_sum(t, ss);
  let inv = inverseSqrt(tot / f32(n) + P.eps);
  for (var i = t; i < n; i += 256u) { s[i] = o[i] * inv * c[i]; }
}
