//! Mamba2 SSM forward pass — Hayate V5 architecture
//!
//! Block = [Mamba2 ×N] → [SharedAttn] → [SwiGLU FFN]
//! Mamba2: in_proj → split(x_in, z=silu) → dt=softplus(dt_proj(x_in))
//!         → B_proj → C_proj → SSM output → out_proj(y * z) + residual

use crate::engine::InferenceEngine;
use crate::model::{
    HayateV5GroupWeights, HayateV5Model, Mamba2BlockWeights, ModelConfig, UltraMemV2Weights,
};
use std::collections::HashMap;

pub struct Mamba2Output {
    pub hidden_states: Vec<f32>,
    pub gpu_time_ms: u64,
}

/// Run a single Mamba2 block forward pass
pub async fn forward_mamba2_block(
    engine: &InferenceEngine,
    block: &Mamba2BlockWeights,
    config: &ModelConfig,
    hidden: &[f32],
) -> Result<Mamba2Output, String> {
    let start = instant_now();
    let dim = config.hidden_size;
    let inner = config.ssm_inner();
    let state_dim = config.ssm_state();
    let seq_len = hidden.len() as u32 / dim;

    // 1. LayerNorm
    let mut normed = hidden.to_vec();
    engine
        .rmsnorm(&mut normed, &block.norm.data, seq_len, dim, config.rms_norm_eps)
        .await
        .map_err(|e| e.to_string())?;

    // 2. in_proj: [seq_len, dim] @ [dim, inner*2] → [seq_len, inner*2]
    let xz = engine
        .matmul(&normed, &block.in_proj.data, seq_len, dim, inner * 2, None)
        .await
        .map_err(|e| e.to_string())?;

    // 3. Split into x_in [seq_len, inner] and z [seq_len, inner]
    let mut x_in = Vec::with_capacity((seq_len * inner) as usize);
    let mut z_raw = Vec::with_capacity((seq_len * inner) as usize);
    for t in 0..seq_len as usize {
        let row_start = t * (inner * 2) as usize;
        x_in.extend_from_slice(&xz[row_start..row_start + inner as usize]);
        z_raw.extend_from_slice(&xz[row_start + inner as usize..row_start + (inner * 2) as usize]);
    }

    // 4. z = silu(z_raw) — gating
    let z = engine.silu(&z_raw).await.map_err(|e| e.to_string())?;

    // 5. dt = softplus(dt_proj(x_in))
    let dt_raw = engine
        .matmul(&x_in, &block.dt_proj.data, seq_len, inner, inner, None)
        .await
        .map_err(|e| e.to_string())?;
    let dt = engine.softplus(&dt_raw).await.map_err(|e| e.to_string())?;

    // 6. B = B_proj(x_in): [seq_len, inner] @ [inner, inner*state_dim] → [seq_len, inner*state_dim]
    let b_val = engine
        .matmul(
            &x_in,
            &block.b_proj.data,
            seq_len,
            inner,
            inner * state_dim,
            None,
        )
        .await
        .map_err(|e| e.to_string())?;

    // 7. C = C_proj(x_in): same shape as B
    let c_val = engine
        .matmul(
            &x_in,
            &block.c_proj.data,
            seq_len,
            inner,
            inner * state_dim,
            None,
        )
        .await
        .map_err(|e| e.to_string())?;

    // 8. SSM output: y[t,i] = sum_s(C*dt*B) + D*x_in
    let y = engine
        .ssm_output(&x_in, &dt, &b_val, &c_val, &block.d.data, seq_len, inner, state_dim)
        .await
        .map_err(|e| e.to_string())?;

    // 9. y * z (element-wise gating)
    let yz = engine
        .elementwise_mul(&y, &z)
        .await
        .map_err(|e| e.to_string())?;

    // 10. out_proj: [seq_len, inner] @ [inner, dim] → [seq_len, dim]
    let projected = engine
        .matmul(&yz, &block.out_proj.data, seq_len, inner, dim, None)
        .await
        .map_err(|e| e.to_string())?;

    // 11. Residual connection
    let mut output = hidden.to_vec();
    engine
        .residual_add(&mut output, &projected)
        .await
        .map_err(|e| e.to_string())?;

    let gpu_time_ms = (instant_now() - start) as u64;
    Ok(Mamba2Output {
        hidden_states: output,
        gpu_time_ms,
    })
}

/// Run SwiGLU FFN: x + w3(silu(w1(norm(x))) * w2(norm(x)))
pub async fn forward_swiglu_ffn(
    engine: &InferenceEngine,
    group: &HayateV5GroupWeights,
    config: &ModelConfig,
    hidden: &[f32],
) -> Result<Vec<f32>, String> {
    let dim = config.hidden_size;
    let seq_len = hidden.len() as u32 / dim;
    let ffn_hidden = group.ffn_w1.shape[1] as u32;

    // Norm
    let mut normed = hidden.to_vec();
    engine
        .rmsnorm(&mut normed, &group.ffn_norm.data, seq_len, dim, config.rms_norm_eps)
        .await
        .map_err(|e| e.to_string())?;

    // w1 and w2 projections
    let w1_out = engine
        .matmul(&normed, &group.ffn_w1.data, seq_len, dim, ffn_hidden, None)
        .await
        .map_err(|e| e.to_string())?;
    let w2_out = engine
        .matmul(&normed, &group.ffn_w2.data, seq_len, dim, ffn_hidden, None)
        .await
        .map_err(|e| e.to_string())?;

    // silu(w1) * w2
    let gate = engine.silu(&w1_out).await.map_err(|e| e.to_string())?;
    let mid = engine
        .elementwise_mul(&gate, &w2_out)
        .await
        .map_err(|e| e.to_string())?;

    // w3 down projection
    let ffn_out = engine
        .matmul(&mid, &group.ffn_w3.data, seq_len, ffn_hidden, dim, None)
        .await
        .map_err(|e| e.to_string())?;

    // Residual
    let mut output = hidden.to_vec();
    engine
        .residual_add(&mut output, &ffn_out)
        .await
        .map_err(|e| e.to_string())?;

    Ok(output)
}

/// Sparse co-activation graph for Sql-learned routing (inference side).
/// Tracks which expert slots co-activate and uses this to boost routing scores.
pub struct CoActivationGraph {
    /// (slot_a, slot_b) → weight. a < b always.
    edges: HashMap<(usize, usize), f32>,
    /// Per-slot activation count
    act_count: Vec<f32>,
    /// Per-slot reward accumulator
    reward: Vec<f32>,
    /// Number of forward passes processed
    forward_count: u64,
    /// Blend weight: (1-w)*pkm + w*graph
    boost_weight: f32,
}

impl CoActivationGraph {
    pub fn new(total_slots: usize) -> Self {
        Self {
            edges: HashMap::new(),
            act_count: vec![0.0; total_slots],
            reward: vec![0.0; total_slots],
            forward_count: 0,
            boost_weight: 0.1,
        }
    }

    /// Record co-activation from one token's top-M selection
    pub fn record(&mut self, slot_ids: &[usize], weights: &[f32]) {
        self.forward_count += 1;
        for (i, &sid) in slot_ids.iter().enumerate() {
            if sid < self.act_count.len() {
                self.act_count[sid] += 1.0;
                self.reward[sid] += weights.get(i).copied().unwrap_or(0.0);
            }
        }
        let top_k = slot_ids.len().min(4);
        for i in 0..top_k {
            for j in (i + 1)..top_k {
                let a = slot_ids[i].min(slot_ids[j]);
                let b = slot_ids[i].max(slot_ids[j]);
                let w = weights.get(i).copied().unwrap_or(0.0)
                    * weights.get(j).copied().unwrap_or(0.0);
                *self.edges.entry((a, b)).or_insert(0.0) += w;
            }
        }
    }

    /// Boost PKM scores with co-activation graph knowledge
    pub fn boost_scores(&self, candidates: &[(f32, usize)]) -> Vec<(f32, usize)> {
        if self.forward_count < 100 || self.edges.is_empty() {
            return candidates.to_vec();
        }
        // Anchor = top-4 by PKM score
        let mut anchors: Vec<usize> = candidates.iter()
            .take(4)
            .map(|(_, s)| *s)
            .collect();
        anchors.sort();

        let pkm_max = candidates.iter().map(|(s, _)| s.abs()).fold(0.0f32, f32::max);
        if pkm_max == 0.0 {
            return candidates.to_vec();
        }

        let mut result: Vec<(f32, usize)> = candidates.iter().map(|&(pkm_score, slot)| {
            let mut graph_score = 0.0f32;
            for &anchor in &anchors {
                let a = slot.min(anchor);
                let b = slot.max(anchor);
                graph_score += self.edges.get(&(a, b)).copied().unwrap_or(0.0);
            }
            graph_score += 0.01 * self.reward.get(slot).copied().unwrap_or(0.0);
            let blended = (1.0 - self.boost_weight) * pkm_score + self.boost_weight * graph_score;
            (blended, slot)
        }).collect();

        result.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        result
    }
}

/// UltraMemV2 forward: Product Key routing + Sql graph boost → top-M experts → MLP W2(GELU(W1 x))
/// CPU-side implementation (expert selection + dequant), GPU for matmul
pub async fn forward_ultramem_v2(
    _engine: &InferenceEngine,
    um: &UltraMemV2Weights,
    config: &ModelConfig,
    hidden: &[f32],
) -> Result<Vec<f32>, String> {
    let dim = config.hidden_size as usize;
    let seq_len = hidden.len() / dim;
    let eh = um.expert_hidden;
    let top_m = um.top_m.min(um.total_slots);
    let half_dim = dim / 2;

    // Skip if no experts loaded
    if um.total_slots == 0 || um.w1.data.is_empty() {
        return Ok(hidden.to_vec());
    }

    // Product Key routing (CPU — O(√N) per token)
    let sub_size = (um.total_slots as f64).sqrt().ceil() as usize;
    let k_sub = ((top_m as f64).sqrt().ceil() as usize + 1).min(sub_size);

    let mut output = hidden.to_vec();

    for t in 0..seq_len {
        let h = &hidden[t * dim..(t + 1) * dim];

        // Simple dot-product routing against keys (CPU)
        // Row scores: h[0..half_dim] · keys_row[i]
        let mut row_scores: Vec<(f32, usize)> = Vec::with_capacity(sub_size);
        for i in 0..sub_size.min(um.keys_row.data.len() / half_dim) {
            let mut score = 0.0f32;
            for d in 0..half_dim {
                score += h[d] * um.keys_row.data[i * half_dim + d];
            }
            row_scores.push((score, i));
        }
        row_scores.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        row_scores.truncate(k_sub);

        // Col scores: h[half_dim..dim] · keys_col[j]
        let mut col_scores: Vec<(f32, usize)> = Vec::with_capacity(sub_size);
        for j in 0..sub_size.min(um.keys_col.data.len() / half_dim) {
            let mut score = 0.0f32;
            for d in 0..half_dim {
                score += h[half_dim + d] * um.keys_col.data[j * half_dim + d];
            }
            col_scores.push((score, j));
        }
        col_scores.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        col_scores.truncate(k_sub);

        // Cartesian product → candidates
        let mut candidates: Vec<(f32, usize)> = Vec::with_capacity(k_sub * k_sub);
        for &(rs, ri) in &row_scores {
            for &(cs, ci) in &col_scores {
                let slot = (ri * sub_size + ci).min(um.total_slots - 1);
                candidates.push((rs + cs, slot));
            }
        }
        candidates.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        // Sql graph routing boost (if graph has enough history)
        // TODO: pass CoActivationGraph via model state when available
        // For now, pure PKM routing (graph boost applied when CoActivationGraph is provided)

        candidates.truncate(top_m);

        // Softmax weights
        let max_score = candidates.first().map(|c| c.0).unwrap_or(0.0);
        let mut weights: Vec<f32> = candidates.iter().map(|c| (c.0 - max_score).exp()).collect();
        let sum: f32 = weights.iter().sum();
        if sum > 0.0 {
            for w in weights.iter_mut() {
                *w /= sum;
            }
        }

        // MLP expert compute: W2(GELU(W1 @ h)) for each selected expert
        let mut expert_sum = vec![0.0f32; dim];
        for (idx, &(_, slot)) in candidates.iter().enumerate() {
            let w = weights[idx];
            if w < 1e-8 {
                continue;
            }

            // W1 @ h → hidden (dim*eh elements for this slot)
            let w1_offset = slot * dim * eh;
            let w2_offset = slot * eh * dim;
            if w1_offset + dim * eh > um.w1.data.len() || w2_offset + eh * dim > um.w2.data.len() {
                continue;
            }

            // GELU(W1 @ h): [eh]
            let mut mid = vec![0.0f32; eh];
            for j in 0..eh {
                let mut val = 0.0f32;
                for d in 0..dim {
                    val += um.w1.data[w1_offset + j * dim + d] * h[d];
                }
                // GELU approximation: x * 0.5 * (1 + tanh(sqrt(2/pi) * (x + 0.044715 * x^3)))
                let x = val;
                mid[j] = x * 0.5 * (1.0 + (0.7978845608 * (x + 0.044715 * x * x * x)).tanh());
            }

            // W2 @ mid: [dim]
            for d in 0..dim {
                let mut val = 0.0f32;
                for j in 0..eh {
                    val += um.w2.data[w2_offset + d * eh + j] * mid[j];
                }
                expert_sum[d] += w * val;
            }
        }

        // Residual + gated output (simplified: alpha=0.5)
        for d in 0..dim {
            output[t * dim + d] = hidden[t * dim + d] * 0.5 + expert_sum[d] * 0.5;
        }
    }

    Ok(output)
}

/// UltraMemV2 forward with Sql graph routing boost.
/// Same as forward_ultramem_v2 but uses co-activation graph to rerank candidates.
pub async fn forward_ultramem_v2_with_graph(
    _engine: &InferenceEngine,
    um: &UltraMemV2Weights,
    graph: &mut CoActivationGraph,
    config: &ModelConfig,
    hidden: &[f32],
) -> Result<Vec<f32>, String> {
    let dim = config.hidden_size as usize;
    let seq_len = hidden.len() / dim;
    let eh = um.expert_hidden;
    let top_m = um.top_m.min(um.total_slots);
    let half_dim = dim / 2;

    if um.total_slots == 0 || um.w1.data.is_empty() {
        return Ok(hidden.to_vec());
    }

    let sub_size = (um.total_slots as f64).sqrt().ceil() as usize;
    let k_sub = ((top_m as f64).sqrt().ceil() as usize + 1).min(sub_size);
    let mut output = hidden.to_vec();

    for t in 0..seq_len {
        let h = &hidden[t * dim..(t + 1) * dim];

        // Row scores
        let mut row_scores: Vec<(f32, usize)> = Vec::with_capacity(sub_size);
        for i in 0..sub_size.min(um.keys_row.data.len() / half_dim) {
            let mut score = 0.0f32;
            for d in 0..half_dim {
                score += h[d] * um.keys_row.data[i * half_dim + d];
            }
            row_scores.push((score, i));
        }
        row_scores.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        row_scores.truncate(k_sub);

        // Col scores
        let mut col_scores: Vec<(f32, usize)> = Vec::with_capacity(sub_size);
        for j in 0..sub_size.min(um.keys_col.data.len() / half_dim) {
            let mut score = 0.0f32;
            for d in 0..half_dim {
                score += h[half_dim + d] * um.keys_col.data[j * half_dim + d];
            }
            col_scores.push((score, j));
        }
        col_scores.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
        col_scores.truncate(k_sub);

        // Cartesian product
        let mut candidates: Vec<(f32, usize)> = Vec::with_capacity(k_sub * k_sub);
        for &(rs, ri) in &row_scores {
            for &(cs, ci) in &col_scores {
                let slot = (ri * sub_size + ci).min(um.total_slots - 1);
                candidates.push((rs + cs, slot));
            }
        }
        candidates.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

        // Sql graph routing boost — rerank using co-activation history
        candidates = graph.boost_scores(&candidates);
        candidates.truncate(top_m);

        // Softmax weights
        let max_score = candidates.first().map(|c| c.0).unwrap_or(0.0);
        let mut weights: Vec<f32> = candidates.iter().map(|c| (c.0 - max_score).exp()).collect();
        let sum: f32 = weights.iter().sum();
        if sum > 0.0 {
            for w in weights.iter_mut() {
                *w /= sum;
            }
        }

        // Record co-activation for online graph learning
        let slot_ids: Vec<usize> = candidates.iter().map(|(_, s)| *s).collect();
        graph.record(&slot_ids, &weights);

        // MLP expert compute: W2(GELU(W1 @ h))
        let mut expert_sum = vec![0.0f32; dim];
        for (idx, &(_, slot)) in candidates.iter().enumerate() {
            let w = weights[idx];
            if w < 1e-8 { continue; }
            let w1_offset = slot * dim * eh;
            let w2_offset = slot * eh * dim;
            if w1_offset + dim * eh > um.w1.data.len() || w2_offset + eh * dim > um.w2.data.len() {
                continue;
            }
            let mut mid = vec![0.0f32; eh];
            for j in 0..eh {
                let mut val = 0.0f32;
                for d in 0..dim {
                    val += um.w1.data[w1_offset + j * dim + d] * h[d];
                }
                let x = val;
                mid[j] = x * 0.5 * (1.0 + (0.7978845608 * (x + 0.044715 * x * x * x)).tanh());
            }
            for d in 0..dim {
                let mut val = 0.0f32;
                for j in 0..eh {
                    val += um.w2.data[w2_offset + d * eh + j] * mid[j];
                }
                expert_sum[d] += w * val;
            }
        }

        for d in 0..dim {
            output[t * dim + d] = hidden[t * dim + d] * 0.5 + expert_sum[d] * 0.5;
        }
    }

    Ok(output)
}

/// Run a full Hayate V5 group: Mamba2 ×N → SwiGLU FFN
pub async fn forward_hayate_v5_group(
    engine: &InferenceEngine,
    group: &HayateV5GroupWeights,
    config: &ModelConfig,
    input: &[f32],
) -> Result<Mamba2Output, String> {
    let mut hidden = input.to_vec();
    let mut total_gpu_ms = 0u64;

    // Mamba2 blocks
    for mamba in &group.mambas {
        let result = forward_mamba2_block(engine, mamba, config, &hidden).await?;
        total_gpu_ms += result.gpu_time_ms;
        hidden = result.hidden_states;
    }

    // SwiGLU FFN
    hidden = forward_swiglu_ffn(engine, group, config, &hidden).await?;

    Ok(Mamba2Output {
        hidden_states: hidden,
        gpu_time_ms: total_gpu_ms,
    })
}

/// Full Hayate V5/V6 forward: embed → groups × [Mamba2×N + UltraMemV2 + FFN] → norm → lm_head
pub async fn forward_hayate_v5(
    engine: &InferenceEngine,
    model: &HayateV5Model,
    input_ids: &[u32],
) -> Result<Vec<f32>, String> {
    let seq_len = input_ids.len();
    let dim = model.config.hidden_size as usize;

    // Token embedding (RoPE handles position — no pos_embed addition for V6)
    let mut hidden = vec![0.0f32; seq_len * dim];
    let has_pos_embed = !model.pos_embed.data.is_empty() && model.pos_embed.data.iter().any(|&v| v != 0.0);
    for (t, &token_id) in input_ids.iter().enumerate() {
        let tok_offset = token_id as usize * dim;
        for d in 0..dim {
            hidden[t * dim + d] = model.embed_tokens.data.get(tok_offset + d).copied().unwrap_or(0.0);
            if has_pos_embed {
                let pos_offset = t * dim;
                hidden[t * dim + d] += model.pos_embed.data.get(pos_offset + d).copied().unwrap_or(0.0);
            }
        }
    }

    // Process through groups: Mamba2×N → UltraMemV2 → FFN
    for group in &model.groups {
        let result =
            forward_hayate_v5_group(engine, group, &model.config, &hidden).await?;
        hidden = result.hidden_states;

        // UltraMemV2 expert layer (after each group, shared across groups)
        if let Some(ref um) = model.ultramem {
            hidden = forward_ultramem_v2(engine, um, &model.config, &hidden).await?;
        }
    }

    // Final norm
    engine
        .rmsnorm(
            &mut hidden,
            &model.final_norm.data,
            seq_len as u32,
            model.config.hidden_size,
            model.config.rms_norm_eps,
        )
        .await
        .map_err(|e| e.to_string())?;

    // lm_head: [seq_len, dim] @ [dim, vocab] → logits [seq_len, vocab]
    let logits = engine
        .matmul(
            &hidden,
            &model.lm_head.data,
            seq_len as u32,
            model.config.hidden_size,
            model.config.vocab_size,
            None,
        )
        .await
        .map_err(|e| e.to_string())?;

    Ok(logits)
}

fn instant_now() -> f64 {
    #[cfg(target_arch = "wasm32")]
    {
        js_sys::Date::now()
    }
    #[cfg(not(target_arch = "wasm32"))]
    {
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs_f64()
            * 1000.0
    }
}
