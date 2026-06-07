//! Transformer forward pass — combines engine ops into full DiT block execution
//!
//! Supports:
//!   - Standard attention blocks (BlockWeights)
//!   - Gated DeltaNet blocks (DeltaNetBlockWeights) for Qwen3.5 hybrid models
//!   - Hybrid forward_shard that dispatches per layer_type

use crate::engine::InferenceEngine;
use crate::model::{BlockWeights, DeltaNetBlockWeights, HybridBlock, ModelConfig};

/// Result of a single transformer block forward pass
pub struct BlockOutput {
    pub hidden_states: Vec<f32>,
    pub gpu_time_ms: u64,
}

/// Run a single transformer block: attention + FFN with residual connections
pub async fn forward_block(
    engine: &InferenceEngine,
    block: &BlockWeights,
    config: &ModelConfig,
    hidden: &[f32],
) -> Result<BlockOutput, String> {
    let start = instant_now();
    let seq_len = hidden.len() / config.hidden_size as usize;
    let dim = config.hidden_size;
    let head_dim = config.head_dim();
    let num_heads = config.num_attention_heads;
    let kv_heads = config.kv_heads();
    let ffn_dim = config.ffn_dim();

    // 1. Input LayerNorm (RMSNorm)
    let mut normed = hidden.to_vec();
    engine
        .rmsnorm(
            &mut normed,
            &block.input_norm.data,
            seq_len as u32,
            dim,
            config.rms_norm_eps,
        )
        .await
        .map_err(|e| e.to_string())?;

    // 2. QKV projections
    //    Qwen3.5 gated attention: Q proj is [dim, q_dim*2] (Q + gate fused)
    //    Detect by comparing weight shape vs expected q_dim
    let expected_q_dim = num_heads * head_dim;
    let actual_q_out = (block.q_weight.data.len() / dim as usize) as u32;
    let is_gated_q = actual_q_out > expected_q_dim;
    let q_proj_dim = if is_gated_q { actual_q_out } else { expected_q_dim };

    let q_raw = engine
        .matmul(&normed, &block.q_weight.data, seq_len as u32, dim, q_proj_dim, None)
        .await
        .map_err(|e| e.to_string())?;

    // Split Q and gate if gated attention
    let (q, q_gate) = if is_gated_q {
        let half = (q_proj_dim / 2) as usize;
        let mut q_vec = Vec::with_capacity(seq_len * half);
        let mut gate_vec = Vec::with_capacity(seq_len * half);
        for s in 0..seq_len {
            let base = s * q_proj_dim as usize;
            q_vec.extend_from_slice(&q_raw[base..base + half]);
            gate_vec.extend_from_slice(&q_raw[base + half..base + q_proj_dim as usize]);
        }
        (q_vec, Some(gate_vec))
    } else {
        (q_raw, None)
    };

    let kv_dim = kv_heads * head_dim;
    let k = engine
        .matmul(&normed, &block.k_weight.data, seq_len as u32, dim, kv_dim, None)
        .await
        .map_err(|e| e.to_string())?;

    let v = engine
        .matmul(&normed, &block.v_weight.data, seq_len as u32, dim, kv_dim, None)
        .await
        .map_err(|e| e.to_string())?;

    // 3. Attention scores: Q @ K^T / sqrt(head_dim), per head
    //    For GQA: replicate K/V heads to match Q heads
    //    Note: Qwen3.5 has num_heads*head_dim (4096) > dim (2560)
    let scale = 1.0 / (head_dim as f32).sqrt();
    let q_total_dim = num_heads * head_dim; // may differ from dim
    let mut attn_output = vec![0.0f32; seq_len * q_total_dim as usize];

    for h in 0..num_heads as usize {
        let kv_h = h * kv_heads as usize / num_heads as usize;

        // Extract Q slice for this head: [seq_len, head_dim]
        let q_head: Vec<f32> = (0..seq_len)
            .flat_map(|s| {
                let offset = s * (num_heads * head_dim) as usize + h * head_dim as usize;
                q[offset..offset + head_dim as usize].iter().copied()
            })
            .collect();

        // Extract K slice: [seq_len, head_dim]
        let k_head: Vec<f32> = (0..seq_len)
            .flat_map(|s| {
                let offset = s * kv_dim as usize + kv_h * head_dim as usize;
                k[offset..offset + head_dim as usize].iter().copied()
            })
            .collect();

        // Extract V slice: [seq_len, head_dim]
        let v_head: Vec<f32> = (0..seq_len)
            .flat_map(|s| {
                let offset = s * kv_dim as usize + kv_h * head_dim as usize;
                v[offset..offset + head_dim as usize].iter().copied()
            })
            .collect();

        // K^T: transpose [seq_len, head_dim] → [head_dim, seq_len]
        let mut k_t = vec![0.0f32; seq_len * head_dim as usize];
        for s in 0..seq_len {
            for d in 0..head_dim as usize {
                k_t[d * seq_len + s] = k_head[s * head_dim as usize + d];
            }
        }

        // scores = Q @ K^T: [seq_len, seq_len]
        let mut scores = engine
            .matmul(
                &q_head,
                &k_t,
                seq_len as u32,
                head_dim,
                seq_len as u32,
                None,
            )
            .await
            .map_err(|e| e.to_string())?;

        // Scale
        for s in scores.iter_mut() {
            *s *= scale;
        }

        // Softmax
        engine
            .softmax(&mut scores, seq_len as u32, seq_len as u32)
            .await
            .map_err(|e| e.to_string())?;

        // attn_out = scores @ V: [seq_len, head_dim]
        let head_out = engine
            .matmul(
                &scores,
                &v_head,
                seq_len as u32,
                seq_len as u32,
                head_dim,
                None,
            )
            .await
            .map_err(|e| e.to_string())?;

        // Write back to concatenated output
        for s in 0..seq_len {
            let dst_offset = s * q_total_dim as usize + h * head_dim as usize;
            let src_offset = s * head_dim as usize;
            attn_output[dst_offset..dst_offset + head_dim as usize]
                .copy_from_slice(&head_out[src_offset..src_offset + head_dim as usize]);
        }
    }

    // 4. Output projection
    //    Qwen3.5: o_weight shape may be [dim, q_dim] where q_dim = num_heads * head_dim
    let o_out_dim = (block.o_weight.data.len() / q_total_dim as usize) as u32;
    let projected = engine
        .matmul(
            &attn_output,
            &block.o_weight.data,
            seq_len as u32,
            q_total_dim,
            o_out_dim,
            None,
        )
        .await
        .map_err(|e| e.to_string())?;

    // Apply output gate if gated attention (Qwen3.5 attn_output_gate=true)
    let projected = if let Some(gate) = &q_gate {
        // gate is sigmoid-applied, then elementwise mul with projection
        let gate_sigmoid: Vec<f32> = gate.iter().map(|&x| 1.0 / (1.0 + (-x).exp())).collect();
        engine.elementwise_mul(&projected, &gate_sigmoid).await.map_err(|e| e.to_string())?
    } else {
        projected
    };

    // 5. Residual add
    let mut residual_out = hidden.to_vec();
    engine
        .residual_add(&mut residual_out, &projected)
        .await
        .map_err(|e| e.to_string())?;

    // 6. Post-attention norm
    let mut post_normed = residual_out.clone();
    engine
        .rmsnorm(
            &mut post_normed,
            &block.post_norm.data,
            seq_len as u32,
            dim,
            config.rms_norm_eps,
        )
        .await
        .map_err(|e| e.to_string())?;

    // 7. FFN: gate_proj + up_proj → gated_silu → down_proj
    //    Qwen3.5: gate_proj and up_proj are separate (not fused)
    //    Detect by checking gate_weight shape
    let gate_out_dim = (block.gate_weight.data.len() / dim as usize) as u32;
    let has_separate_up = !block.up_weight.data.is_empty();

    let (ffn_mid, actual_ffn_dim) = if has_separate_up {
        // Separate gate + up projections
        let gate = engine
            .matmul(&post_normed, &block.gate_weight.data, seq_len as u32, dim, gate_out_dim, None)
            .await.map_err(|e| e.to_string())?;
        let up = engine
            .matmul(&post_normed, &block.up_weight.data, seq_len as u32, dim, gate_out_dim, None)
            .await.map_err(|e| e.to_string())?;
        // gate_silu: silu(gate) * up
        let gate_activated = engine.silu(&gate).await.map_err(|e| e.to_string())?;
        let mid = engine.elementwise_mul(&gate_activated, &up).await.map_err(|e| e.to_string())?;
        (mid, gate_out_dim)
    } else {
        // Fused gate_up projection
        let gate_up = engine
            .matmul(&post_normed, &block.gate_weight.data, seq_len as u32, dim, ffn_dim * 2, None)
            .await.map_err(|e| e.to_string())?;
        let mid = engine.gated_silu(&gate_up, seq_len as u32, ffn_dim).await.map_err(|e| e.to_string())?;
        (mid, ffn_dim)
    };

    let down_out_dim = (block.down_weight.data.len() / actual_ffn_dim as usize) as u32;
    let ffn_out = engine
        .matmul(&ffn_mid, &block.down_weight.data, seq_len as u32, actual_ffn_dim, down_out_dim, None)
        .await.map_err(|e| e.to_string())?;

    // 8. Final residual
    let mut output = residual_out;
    engine
        .residual_add(&mut output, &ffn_out)
        .await
        .map_err(|e| e.to_string())?;

    let gpu_time_ms = (instant_now() - start) as u64;

    Ok(BlockOutput {
        hidden_states: output,
        gpu_time_ms,
    })
}

/// Run a Gated DeltaNet block: conv1d → delta rule recurrence → output gate → FFN
///
/// Qwen3.5 linear_attention layer:
///   1. Input norm
///   2. Project to Q, K, V, A (erase gate), B (write gate), Z (output gate)
///   3. Short conv1d on concatenated projections
///   4. Delta rule recurrence: S[t] = alpha*S[t-1] + beta*v⊗k, o = S^T @ q
///   5. Output gate: o = o * silu(z)
///   6. Output projection + residual
///   7. Post-norm → FFN → residual
pub async fn forward_deltanet_block(
    engine: &InferenceEngine,
    block: &DeltaNetBlockWeights,
    config: &ModelConfig,
    hidden: &[f32],
) -> Result<BlockOutput, String> {
    let start = instant_now();
    let seq_len = hidden.len() / config.hidden_size as usize;
    let dim = config.hidden_size;
    let qk_dim = config.deltanet_qk_dim();
    let v_dim = config.deltanet_v_dim();
    let ffn_dim = config.ffn_dim();

    // 1. Input LayerNorm
    let mut normed = hidden.to_vec();
    engine
        .rmsnorm(&mut normed, &block.input_norm.data, seq_len as u32, dim, config.rms_norm_eps)
        .await
        .map_err(|e| e.to_string())?;

    // 2. QKV projections
    let qkv = engine
        .matmul(&normed, &block.in_proj_qkv.data, seq_len as u32, dim, qk_dim + qk_dim + v_dim, None)
        .await
        .map_err(|e| e.to_string())?;

    // Split QKV
    let _qk_size = (qk_dim as usize) * seq_len;
    let _v_size = (v_dim as usize) * seq_len;
    let q: Vec<f32> = (0..seq_len)
        .flat_map(|s| {
            let base = s * (qk_dim + qk_dim + v_dim) as usize;
            qkv[base..base + qk_dim as usize].iter().copied()
        })
        .collect();
    let k: Vec<f32> = (0..seq_len)
        .flat_map(|s| {
            let base = s * (qk_dim + qk_dim + v_dim) as usize + qk_dim as usize;
            qkv[base..base + qk_dim as usize].iter().copied()
        })
        .collect();
    let v: Vec<f32> = (0..seq_len)
        .flat_map(|s| {
            let base = s * (qk_dim + qk_dim + v_dim) as usize + (qk_dim * 2) as usize;
            qkv[base..base + v_dim as usize].iter().copied()
        })
        .collect();

    // Project beta (write gate) and z (output gate)
    let beta_raw = engine
        .matmul(&normed, &block.in_proj_b.data, seq_len as u32, dim, v_dim, None)
        .await
        .map_err(|e| e.to_string())?;
    let z_raw = engine
        .matmul(&normed, &block.in_proj_z.data, seq_len as u32, dim, v_dim, None)
        .await
        .map_err(|e| e.to_string())?;

    // 3. Compute alpha from A_log: alpha = sigmoid(-exp(A_log))
    //    For simplicity, use mean A_log across heads as scalar alpha
    let a_log_mean = if block.a_log.data.is_empty() {
        -1.0_f32 // default decay
    } else {
        block.a_log.data.iter().sum::<f32>() / block.a_log.data.len() as f32
    };
    let alpha = 1.0 / (1.0 + (-a_log_mean).exp().exp()); // sigmoid(-exp(A_log))

    // Apply sigmoid to beta (write gate)
    let beta: Vec<f32> = beta_raw.iter().map(|&x| 1.0 / (1.0 + (-x).exp())).collect();

    // 4. Delta rule recurrence (CPU fallback — sequential by nature)
    //    S[t] = alpha * S[t-1] + beta[t] * (v[t] ⊗ k[t])
    //    o[t] = S[t]^T @ q[t]
    let hd = qk_dim as usize;
    let vd = v_dim as usize;
    let num_v_heads = config.linear_num_value_heads.max(1) as usize;
    let v_head_dim = vd / num_v_heads;
    let num_qk_heads = config.linear_num_key_heads.max(1) as usize;
    let qk_head_dim = hd / num_qk_heads;

    let mut deltanet_output = vec![0.0f32; seq_len * vd];

    // Per-head recurrence
    for head in 0..num_v_heads {
        let mut state = vec![0.0f32; qk_head_dim * v_head_dim]; // S: [qk_head_dim, v_head_dim]

        // Map heads: if num_qk_heads != num_v_heads, distribute
        let qk_head = head * num_qk_heads / num_v_heads;

        for t in 0..seq_len {
            let b_t = beta[t * vd + head * v_head_dim]; // per-head beta (first element)

            // Update state: S = alpha * S + beta * (k ⊗ v)
            for ki in 0..qk_head_dim {
                let k_val = k[t * hd + qk_head * qk_head_dim + ki];
                for vi in 0..v_head_dim {
                    let v_val = v[t * vd + head * v_head_dim + vi];
                    let idx = ki * v_head_dim + vi;
                    state[idx] = alpha * state[idx] + b_t * k_val * v_val;
                }
            }

            // Output: o[t] = S^T @ q[t]
            for vi in 0..v_head_dim {
                let mut acc = 0.0f32;
                for ki in 0..qk_head_dim {
                    let q_val = q[t * hd + qk_head * qk_head_dim + ki];
                    acc += state[ki * v_head_dim + vi] * q_val;
                }
                deltanet_output[t * vd + head * v_head_dim + vi] = acc;
            }
        }
    }

    // 5. Output gate: o = norm(o) * silu(z)
    let mut normed_out = deltanet_output;
    engine
        .rmsnorm(&mut normed_out, &block.norm.data, seq_len as u32, v_dim, config.rms_norm_eps)
        .await
        .map_err(|e| e.to_string())?;

    let z_silu = engine.silu(&z_raw).await.map_err(|e| e.to_string())?;
    let gated = engine
        .elementwise_mul(&normed_out, &z_silu)
        .await
        .map_err(|e| e.to_string())?;

    // 6. Output projection: [seq_len, v_dim] @ [v_dim, dim] → [seq_len, dim]
    let projected = engine
        .matmul(&gated, &block.out_proj.data, seq_len as u32, v_dim, dim, None)
        .await
        .map_err(|e| e.to_string())?;

    // Residual
    let mut residual_out = hidden.to_vec();
    engine
        .residual_add(&mut residual_out, &projected)
        .await
        .map_err(|e| e.to_string())?;

    // 7. Post-norm → FFN → residual
    let mut post_normed = residual_out.clone();
    engine
        .rmsnorm(&mut post_normed, &block.post_norm.data, seq_len as u32, dim, config.rms_norm_eps)
        .await
        .map_err(|e| e.to_string())?;

    let gate_up = engine
        .matmul(&post_normed, &block.gate_weight.data, seq_len as u32, dim, ffn_dim * 2, None)
        .await
        .map_err(|e| e.to_string())?;

    let ffn_mid = engine
        .gated_silu(&gate_up, seq_len as u32, ffn_dim)
        .await
        .map_err(|e| e.to_string())?;

    let ffn_out = engine
        .matmul(&ffn_mid, &block.down_weight.data, seq_len as u32, ffn_dim, dim, None)
        .await
        .map_err(|e| e.to_string())?;

    let mut output = residual_out;
    engine
        .residual_add(&mut output, &ffn_out)
        .await
        .map_err(|e| e.to_string())?;

    let gpu_time_ms = (instant_now() - start) as u64;
    Ok(BlockOutput {
        hidden_states: output,
        gpu_time_ms,
    })
}

/// Run a hybrid shard (Qwen3.5: mixed DeltaNet + Attention blocks)
pub async fn forward_hybrid_shard(
    engine: &InferenceEngine,
    blocks: &[&HybridBlock],
    config: &ModelConfig,
    input_hidden: &[f32],
) -> Result<BlockOutput, String> {
    let mut hidden = input_hidden.to_vec();
    let mut total_gpu_ms = 0u64;

    for block in blocks {
        let result = match block {
            HybridBlock::Attention(attn) => forward_block(engine, attn, config, &hidden).await?,
            HybridBlock::DeltaNet(dn) => forward_deltanet_block(engine, dn, config, &hidden).await?,
        };
        total_gpu_ms += result.gpu_time_ms;
        hidden = result.hidden_states;
    }

    Ok(BlockOutput {
        hidden_states: hidden,
        gpu_time_ms: total_gpu_ms,
    })
}

/// Run a sequence of transformer blocks (for shard execution)
pub async fn forward_shard(
    engine: &InferenceEngine,
    blocks: &[&BlockWeights],
    config: &ModelConfig,
    input_hidden: &[f32],
) -> Result<BlockOutput, String> {
    let mut hidden = input_hidden.to_vec();
    let mut total_gpu_ms = 0u64;

    for block in blocks {
        let result = forward_block(engine, block, config, &hidden).await?;
        total_gpu_ms += result.gpu_time_ms;
        hidden = result.hidden_states;
    }

    Ok(BlockOutput {
        hidden_states: hidden,
        gpu_time_ms: total_gpu_ms,
    })
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
