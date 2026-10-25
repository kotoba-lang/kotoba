// Gated delta-net recurrence, ONE decode token, all heads (Qwen3.5 linear
// attention as Nex-N2.5-mini uses it on 30 of 40 layers). Root ADR-2609182100
// D1 / co-scientist iteration 2 hypothesis N4.
//
// Per head h with state S_h [K x V] (row-major S[i*V + j]), decay g_h (log
// space, already -exp(A_log) * softplus(a + dt_bias)), write gate beta_h
// (already sigmoid), query q_h [K] (already L2-normalised and scaled), key
// k_h [K] (L2-normalised), value v_h [V]  -- the FLA recurrent_gated_delta_rule:
//
//   S      = S * exp(g)
//   kv_mem = k^T S                 (kv_mem[j] = sum_i S[i][j] k[i])
//   delta  = (v - kv_mem) * beta
//   S      = S + k (x) delta       (S[i][j] += k[i] delta[j])
//   o      = q^T S                 (o[j] = sum_i S[i][j] q[i])
//
// Layout for the GPU: one workgroup per head, one thread per value column j.
// Thread j owns column j of S for the whole step (decay, dot with k, update,
// dot with q), so every access S[i*V + j] across the workgroup is one
// contiguous row segment -- coalesced -- and no shared memory is needed. K and
// V are 128 in Nex (linear_key_head_dim = linear_value_head_dim = 128), so the
// workgroup is 128 threads and each thread walks 128 rows four times.
//
// Key heads are fewer than value heads in Nex (16 vs 32). llama.cpp maps value
// head h to key/query head h % k_heads (ggml_compute_forward_gated_delta_net:
// iq1 = iv1 % neq1; the unfused path's ggml_repeat_4d tiles the same way) --
// NOT h / group. Measured 2026-09-18: with h / group, value head 1 read key
// head 0 and layer-0 output diverged from llama.cpp at head 1 while head 0
// matched. params.k_heads carries the key-head count.
//
// Dispatch: (heads, 1, 1) workgroups. State is updated in place.

struct Meta {
  heads: u32,       // value heads (32 in Nex)
  k_dim: u32,       // 128
  v_dim: u32,       // 128, must equal the workgroup size
  k_heads: u32,     // key/query heads (16 in Nex); value head h uses key head h % k_heads
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read> q: array<f32>;       // [k_heads * k_dim]
@group(0) @binding(2) var<storage, read> k: array<f32>;       // [k_heads * k_dim]
@group(0) @binding(3) var<storage, read> v: array<f32>;       // [heads * v_dim]
@group(0) @binding(4) var<storage, read> g: array<f32>;       // [heads] log decay
@group(0) @binding(5) var<storage, read> beta: array<f32>;    // [heads]
@group(0) @binding(6) var<storage, read_write> state: array<f32>; // [heads * k_dim * v_dim]
@group(0) @binding(7) var<storage, read_write> out: array<f32>;   // [heads * v_dim]

@compute @workgroup_size(128)
fn main(@builtin(workgroup_id) wg: vec3<u32>, @builtin(local_invocation_id) lid: vec3<u32>) {
  let h = wg.x;
  let j = lid.x;
  if h >= params.heads || j >= params.v_dim { return; }
  let K = params.k_dim;
  let V = params.v_dim;
  let kh = h % params.k_heads;
  let sbase = h * K * V;
  let decay = exp(g[h]);
  let b = beta[h];

  // decay + kv_mem in one pass over the column
  var kv_mem = 0.0;
  for (var i = 0u; i < K; i++) {
    let s = state[sbase + i * V + j] * decay;
    state[sbase + i * V + j] = s;
    kv_mem += s * k[kh * K + i];
  }
  let delta = (v[h * V + j] - kv_mem) * b;
  // rank-1 update + output dot in one pass
  var o = 0.0;
  for (var i = 0u; i < K; i++) {
    let s = state[sbase + i * V + j] + k[kh * K + i] * delta;
    state[sbase + i * V + j] = s;
    o += s * q[kh * K + i];
  }
  out[h * V + j] = o;
}
