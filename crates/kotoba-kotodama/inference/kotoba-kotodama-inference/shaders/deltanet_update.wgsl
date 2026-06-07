// Gated DeltaNet state update (Qwen3.5 linear_attention)
//
// Delta rule: S[t] = alpha * S[t-1] + beta[t] * (v[t] ⊗ k[t])
// Output:     o[t] = S[t] @ q[t]
//
// alpha = sigmoid(-exp(A_log))  (learnable decay, per-head)
// beta  = sigmoid(beta_proj)    (write gate, per-token)
//
// This shader computes the recurrent update for one head across all timesteps.
// Each workgroup processes one head.
//
// Layout:
//   q:      [seq_len, head_dim]     query vectors
//   k:      [seq_len, head_dim]     key vectors
//   v:      [seq_len, v_head_dim]   value vectors
//   beta:   [seq_len]               write gate (sigmoid-applied)
//   alpha:  scalar                  decay (sigmoid(-exp(A_log)))
//   output: [seq_len, v_head_dim]   output vectors

struct Meta {
    seq_len: u32,
    head_dim: u32,      // key/query head dim
    v_head_dim: u32,    // value head dim
    _pad: u32,
}

@group(0) @binding(0) var<uniform> params: Meta;
@group(0) @binding(1) var<storage, read> q: array<f32>;
@group(0) @binding(2) var<storage, read> k: array<f32>;
@group(0) @binding(3) var<storage, read> v: array<f32>;
@group(0) @binding(4) var<storage, read> beta: array<f32>;
@group(0) @binding(5) var<uniform> alpha: f32;
@group(0) @binding(6) var<storage, read_write> output: array<f32>;

// State matrix S: [head_dim, v_head_dim] — maintained in workgroup shared memory
// For small head_dim (128) × v_head_dim (128), this fits in shared memory (64KB)
var<workgroup> state: array<f32, 16384>;  // 128 * 128 = 16384

@compute @workgroup_size(128)
fn main(
    @builtin(local_invocation_id) lid: vec3<u32>,
    @builtin(workgroup_id) wid: vec3<u32>,
) {
    let hd = params.head_dim;
    let vd = params.v_head_dim;
    let tid = lid.x;  // thread ID within workgroup

    // Initialize state to zero
    let state_size = hd * vd;
    for (var i = tid; i < state_size; i = i + 128u) {
        state[i] = 0.0;
    }
    workgroupBarrier();

    // Sequential scan over timesteps (recurrent — must be sequential)
    for (var t: u32 = 0u; t < params.seq_len; t = t + 1u) {
        let b = beta[t];  // write gate for this timestep

        // Update state: S = alpha * S + beta * (v ⊗ k)
        // Each thread handles a slice of the state matrix
        for (var i = tid; i < state_size; i = i + 128u) {
            let ki_idx = i / vd;  // key dim index
            let vi_idx = i % vd;  // value dim index
            let k_val = k[t * hd + ki_idx];
            let v_val = v[t * vd + vi_idx];
            state[i] = alpha * state[i] + b * k_val * v_val;
        }
        workgroupBarrier();

        // Compute output: o[t] = S^T @ q[t] (for each value dim)
        // Each thread computes one output element
        if tid < vd {
            var acc: f32 = 0.0;
            for (var d: u32 = 0u; d < hd; d = d + 1u) {
                acc += state[d * vd + tid] * q[t * hd + d];
            }
            output[t * vd + tid] = acc;
        }
        workgroupBarrier();
    }
}
