//! Model weight loading — safetensors and shard management

use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// Model configuration loaded from model.json alongside weight files
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ModelConfig {
    pub model_type: String,
    pub hidden_size: u32,
    pub intermediate_size: u32,
    pub num_attention_heads: u32,
    pub num_hidden_layers: u32,
    pub head_dim: u32,
    pub vocab_size: u32,
    pub max_position_embeddings: u32,
    pub rms_norm_eps: f32,
    #[serde(default)]
    pub num_key_value_heads: u32,
    #[serde(default)]
    pub quantization: String,
    #[serde(default)]
    pub ssm_state_dim: u32,
    #[serde(default)]
    pub ssm_expand: u32,
    #[serde(default)]
    pub num_groups: u32,
    #[serde(default)]
    pub mamba_per_group: u32,
    /// Per-layer type for hybrid models (Qwen3.5): "linear_attention" or "full_attention"
    #[serde(default)]
    pub layer_types: Vec<String>,
    /// DeltaNet linear attention key head dim (Qwen3.5: 128)
    #[serde(default)]
    pub linear_key_head_dim: u32,
    /// DeltaNet linear attention value head dim (Qwen3.5: 128)
    #[serde(default)]
    pub linear_value_head_dim: u32,
    /// Number of Q/K heads for linear attention (Qwen3.5: 16)
    #[serde(default)]
    pub linear_num_key_heads: u32,
    /// Number of V heads for linear attention (Qwen3.5: 32)
    #[serde(default)]
    pub linear_num_value_heads: u32,
    /// Conv1d kernel size for DeltaNet (Qwen3.5: 4)
    #[serde(default)]
    pub linear_conv_kernel_dim: u32,
}

impl ModelConfig {
    pub fn head_dim(&self) -> u32 {
        if self.head_dim > 0 {
            self.head_dim
        } else {
            self.hidden_size / self.num_attention_heads
        }
    }

    pub fn ffn_dim(&self) -> u32 {
        self.intermediate_size
    }

    /// Total transformer/SSM layers (groups × mamba_per_group, or num_hidden_layers).
    pub fn total_layers(&self) -> u32 {
        let from_groups = self.num_groups.saturating_mul(self.mamba_per_group.max(1));
        if from_groups > 0 { from_groups } else { self.num_hidden_layers }
    }

    pub fn kv_heads(&self) -> u32 {
        if self.num_key_value_heads > 0 {
            self.num_key_value_heads
        } else {
            self.num_attention_heads
        }
    }

    pub fn ssm_inner(&self) -> u32 {
        let expand = if self.ssm_expand > 0 { self.ssm_expand } else { 2 };
        self.hidden_size * expand
    }

    pub fn ssm_state(&self) -> u32 {
        if self.ssm_state_dim > 0 { self.ssm_state_dim } else { 16 }
    }
}

/// A tensor loaded from safetensors format
#[derive(Debug, Clone)]
pub struct Tensor {
    pub name: String,
    pub data: Vec<f32>,
    pub shape: Vec<usize>,
}

impl Tensor {
    pub fn numel(&self) -> usize {
        self.shape.iter().product()
    }
}

/// Transformer block weights (Q, K, V, O projections + FFN + norms)
#[derive(Debug, Clone)]
pub struct BlockWeights {
    pub layer_idx: usize,
    pub q_weight: Tensor,
    pub k_weight: Tensor,
    pub v_weight: Tensor,
    pub o_weight: Tensor,
    pub gate_weight: Tensor,
    pub up_weight: Tensor,
    pub down_weight: Tensor,
    pub input_norm: Tensor,
    pub post_norm: Tensor,
}

/// A shard is a subset of transformer blocks assigned to one worker
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShardAssignment {
    pub shard_id: String,
    pub start_layer: usize,
    pub end_layer: usize,
    pub model_id: String,
}

/// Loaded model ready for inference
pub struct LoadedModel {
    pub config: ModelConfig,
    pub blocks: Vec<BlockWeights>,
    pub embed_tokens: Option<Tensor>,
    pub final_norm: Option<Tensor>,
    pub lm_head: Option<Tensor>,
}

impl LoadedModel {
    /// Get a subset of blocks for a shard assignment
    pub fn shard_blocks(&self, assignment: &ShardAssignment) -> Vec<&BlockWeights> {
        self.blocks[assignment.start_layer..assignment.end_layer]
            .iter()
            .collect()
    }
}

/// Gated DeltaNet block weights (Qwen3.5 linear_attention layers)
///
/// DeltaNet uses a gated linear attention mechanism with:
///   - Short convolution (conv1d) for local context
///   - Delta rule state update (write/erase gates via A_log)
///   - Separate QKV projections with different head counts
///   - Output gating (z gate)
#[derive(Debug, Clone)]
pub struct DeltaNetBlockWeights {
    pub layer_idx: usize,
    /// Input projection for QKV: [dim, qk_dim + qk_dim + v_dim]
    pub in_proj_qkv: Tensor,
    /// Input projection A (erase/write gate): [dim, v_dim]
    pub in_proj_a: Tensor,
    /// Input projection B (beta gate): [dim, v_dim]
    pub in_proj_b: Tensor,
    /// Input projection Z (output gate): [dim, v_dim]
    pub in_proj_z: Tensor,
    /// A_log: learnable decay parameter [num_v_heads]
    pub a_log: Tensor,
    /// Short convolution: [v_dim, 1, conv_kernel]
    pub conv1d_weight: Tensor,
    /// DeltaNet dt_bias (optional): [v_dim]
    pub dt_bias: Tensor,
    /// RMSNorm within DeltaNet block: [v_dim]
    pub norm: Tensor,
    /// Output projection: [v_dim, dim]
    pub out_proj: Tensor,
    /// Input layernorm: [dim]
    pub input_norm: Tensor,
    /// Post-attention layernorm: [dim]
    pub post_norm: Tensor,
    /// FFN gate_proj (gate+up fused): [dim, ffn_dim*2]
    pub gate_weight: Tensor,
    /// FFN down_proj: [ffn_dim, dim]
    pub down_weight: Tensor,
}

/// Hybrid block: either a standard attention block or a DeltaNet block
#[derive(Debug, Clone)]
pub enum HybridBlock {
    /// Standard softmax attention (Qwen3.5 full_attention layers)
    Attention(BlockWeights),
    /// Gated DeltaNet linear attention (Qwen3.5 linear_attention layers)
    DeltaNet(DeltaNetBlockWeights),
}

/// Hybrid model with mixed attention types (Qwen3.5)
pub struct HybridModel {
    pub config: ModelConfig,
    pub blocks: Vec<HybridBlock>,
    pub embed_tokens: Option<Tensor>,
    pub final_norm: Option<Tensor>,
    pub lm_head: Option<Tensor>,
}

impl ModelConfig {
    /// Check if layer at given index is a DeltaNet (linear_attention) layer.
    pub fn is_deltanet_layer(&self, layer_idx: usize) -> bool {
        if layer_idx < self.layer_types.len() {
            self.layer_types[layer_idx] == "linear_attention"
        } else {
            false
        }
    }

    /// Check if this is a hybrid model (has layer_types with mixed types).
    pub fn is_hybrid(&self) -> bool {
        !self.layer_types.is_empty()
            && self.layer_types.iter().any(|t| t == "linear_attention")
            && self.layer_types.iter().any(|t| t == "full_attention")
    }

    /// DeltaNet value dimension = linear_num_value_heads * linear_value_head_dim
    pub fn deltanet_v_dim(&self) -> u32 {
        self.linear_num_value_heads.max(1) * self.linear_value_head_dim.max(128)
    }

    /// DeltaNet QK dimension = linear_num_key_heads * linear_key_head_dim
    pub fn deltanet_qk_dim(&self) -> u32 {
        self.linear_num_key_heads.max(1) * self.linear_key_head_dim.max(128)
    }
}

/// Mamba2 block weights (SSM projections + norm)
#[derive(Debug, Clone)]
pub struct Mamba2BlockWeights {
    pub layer_idx: usize,
    pub in_proj: Tensor,   // [dim, inner*2] (x_in + gate z)
    pub dt_proj: Tensor,   // [inner, inner]
    pub b_proj: Tensor,    // [inner, inner*state_dim]
    pub c_proj: Tensor,    // [inner, inner*state_dim]
    pub d: Tensor,         // [inner] skip connection scalar
    pub out_proj: Tensor,  // [inner, dim]
    pub norm: Tensor,      // [dim] LayerNorm weight
}

/// Hayate V5 group: N Mamba2 blocks + SwiGLU FFN
#[derive(Debug, Clone)]
pub struct HayateV5GroupWeights {
    pub mambas: Vec<Mamba2BlockWeights>,
    pub ffn_w1: Tensor,    // [dim, ffn_hidden]
    pub ffn_w2: Tensor,    // [dim, ffn_hidden]
    pub ffn_w3: Tensor,    // [ffn_hidden, dim]
    pub ffn_norm: Tensor,  // [dim]
}

/// UltraMemV2 expert weights (MLP per slot, int8 quantized for inference)
#[derive(Debug, Clone)]
pub struct UltraMemV2Weights {
    /// Expert MLP layer 1 weights, dequantized to f32 [total_slots, dim * expert_hidden]
    pub w1: Tensor,
    /// Expert MLP layer 2 weights, dequantized to f32 [total_slots, expert_hidden * dim]
    pub w2: Tensor,
    /// Product Key routing: row keys [sub_size, dim/2]
    pub keys_row: Tensor,
    /// Product Key routing: col keys [sub_size, dim/2]
    pub keys_col: Tensor,
    /// Query projection row [dim, dim/2]
    pub query_row: Option<Tensor>,
    /// Query projection col [dim, dim/2]
    pub query_col: Option<Tensor>,
    /// Output projection [dim, dim]
    pub out_proj: Option<Tensor>,
    /// Gate [dim, dim]
    pub gate: Option<Tensor>,
    /// Norm [dim]
    pub norm: Option<Tensor>,
    /// Total expert slots
    pub total_slots: usize,
    /// Expert hidden dim (eh = max(64, dim/8))
    pub expert_hidden: usize,
    /// Top-M active experts per token
    pub top_m: usize,
}

/// Per-label expert weights loaded from safetensors (int8 dequantized)
#[derive(Debug, Clone)]
pub struct LabelExpertWeights {
    pub label: String,
    pub w1: Vec<f32>,       // [slots, dim * eh] dequantized
    pub w2: Vec<f32>,       // [slots, eh * dim] dequantized
    pub slots: usize,
    pub offset: usize,      // offset in flat expert pool
}

/// Hayate V5/V6 full model weights
pub struct HayateV5Model {
    pub config: ModelConfig,
    pub embed_tokens: Tensor,       // [vocab, dim]
    pub pos_embed: Tensor,          // [max_seq, dim]
    pub groups: Vec<HayateV5GroupWeights>,
    pub shared_attn: BlockWeights,  // reuse transformer BlockWeights for shared attention
    pub final_norm: Tensor,         // [dim]
    pub lm_head: Tensor,            // [vocab, dim]
    /// V6 UltraMemV2 expert weights (None = no experts, backbone-only)
    pub ultramem: Option<UltraMemV2Weights>,
    /// Per-label expert metadata (for multi-label assembled models)
    pub expert_labels: Vec<LabelExpertWeights>,
}

/// Build Mamba2 block weights from a tensor map (safetensors-parsed)
pub fn build_mamba2_block(
    tensors: &HashMap<String, Tensor>,
    prefix: &str,
    layer_idx: usize,
) -> Option<Mamba2BlockWeights> {
    let get = |suffix: &str| -> Option<Tensor> {
        tensors.get(&format!("{prefix}.{suffix}")).cloned()
    };
    Some(Mamba2BlockWeights {
        layer_idx,
        in_proj: get("in_proj.weight")?,
        dt_proj: get("dt_proj.weight")?,
        b_proj: get("B_proj.weight")?,
        c_proj: get("C_proj.weight")?,
        d: get("D")?,
        out_proj: get("out_proj.weight")?,
        norm: get("norm.weight")?,
    })
}

/// Build Hayate V5 model from raw safetensors bytes (supports int8 expert weights)
pub fn load_hayate_v5_from_bytes(data: &[u8]) -> Result<HayateV5Model, String> {
    let header = parse_safetensors_header(data)?;
    let mut tensors = HashMap::new();

    for (name, meta) in &header {
        // Skip scale tensors — they're consumed alongside their parent int8 tensor
        if name.ends_with("_scale") {
            continue;
        }
        let mut t = if meta.dtype == "I8" {
            // Int8 tensor: look up corresponding _scale tensor for dequantization
            let scale_name = format!("{name}_scale");
            let scale = if let Some(scale_meta) = header.get(&scale_name) {
                extract_scale(data, scale_meta)
            } else {
                1.0 // fallback: no scale → treat as raw signed bytes
            };
            extract_f32_tensor_int8(data, meta, scale)
        } else {
            extract_f32_tensor(data, meta)
        };
        t.name = name.clone();
        tensors.insert(name.clone(), t);
    }

    let get = |name: &str| -> Result<Tensor, String> {
        tensors
            .get(name)
            .cloned()
            .ok_or_else(|| format!("missing tensor: {name}"))
    };

    // Probe config from tensor shapes
    let embed = get("embed.weight")?;
    let vocab = embed.shape[0] as u32;
    let dim = embed.shape[1] as u32;

    // Count groups and mambas by scanning tensor names
    let mut num_groups = 0u32;
    let mut mamba_per_group = 0u32;
    for name in tensors.keys() {
        if let Some(rest) = name.strip_prefix("groups.") {
            if let Some(g) = rest.split('.').next().and_then(|s| s.parse::<u32>().ok()) {
                num_groups = num_groups.max(g + 1);
            }
            if rest.contains("mambas.") {
                if let Some(m) = rest
                    .strip_prefix(&format!("{}.", rest.split('.').next().unwrap_or("")))
                    .and_then(|r| r.strip_prefix("mambas."))
                    .and_then(|r| r.split('.').next())
                    .and_then(|s| s.parse::<u32>().ok())
                {
                    mamba_per_group = mamba_per_group.max(m + 1);
                }
            }
        }
    }

    // Infer SSM dimensions from in_proj shape: [dim, inner*2]
    let inner = if let Some(t) = tensors.get("groups.0.mambas.0.in_proj.weight") {
        (t.shape[1] / 2) as u32
    } else {
        dim * 2
    };
    let state_dim = if let Some(t) = tensors.get("groups.0.mambas.0.B_proj.weight") {
        (t.shape[1] / inner as usize) as u32
    } else {
        16
    };

    let config = ModelConfig {
        model_type: "hayate_v5".into(),
        hidden_size: dim,
        intermediate_size: inner,
        num_attention_heads: 8,
        num_hidden_layers: num_groups * mamba_per_group,
        head_dim: dim / 8,
        vocab_size: vocab,
        max_position_embeddings: 512,
        rms_norm_eps: 1e-5,
        num_key_value_heads: 8,
        quantization: String::new(),
        ssm_state_dim: state_dim,
        ssm_expand: inner / dim,
        num_groups,
        mamba_per_group,
        ..Default::default()
    };

    let mut groups = Vec::new();
    for g in 0..num_groups as usize {
        let mut mambas = Vec::new();
        for m in 0..mamba_per_group as usize {
            let prefix = format!("groups.{g}.mambas.{m}");
            let block = build_mamba2_block(&tensors, &prefix, m)
                .ok_or_else(|| format!("missing mamba block {g}.{m}"))?;
            mambas.push(block);
        }
        groups.push(HayateV5GroupWeights {
            mambas,
            ffn_w1: get(&format!("groups.{g}.ffn.w1.weight"))?,
            ffn_w2: get(&format!("groups.{g}.ffn.w2.weight"))?,
            ffn_w3: get(&format!("groups.{g}.ffn.w3.weight"))?,
            ffn_norm: get(&format!("groups.{g}.ffn.norm.weight"))?,
        });
    }

    // Shared attention block (reuse BlockWeights)
    let shared_attn = BlockWeights {
        layer_idx: 0,
        q_weight: get("shared_attn.qkv.weight").unwrap_or_else(|_| Tensor {
            name: String::new(),
            data: vec![],
            shape: vec![],
        }),
        k_weight: Tensor { name: String::new(), data: vec![], shape: vec![] },
        v_weight: Tensor { name: String::new(), data: vec![], shape: vec![] },
        o_weight: get("shared_attn.out_proj.weight").unwrap_or_else(|_| Tensor {
            name: String::new(),
            data: vec![],
            shape: vec![],
        }),
        gate_weight: Tensor { name: String::new(), data: vec![], shape: vec![] },
        up_weight: Tensor { name: String::new(), data: vec![], shape: vec![] },
        down_weight: Tensor { name: String::new(), data: vec![], shape: vec![] },
        input_norm: get("shared_attn.norm.weight").unwrap_or_else(|_| Tensor {
            name: String::new(),
            data: vec![],
            shape: vec![],
        }),
        post_norm: Tensor { name: String::new(), data: vec![], shape: vec![] },
    };

    // Load UltraMemV2 expert weights (if present)
    // Experts can be under "ultramem.w1"/"ultramem.w2" (assembled) or "experts.{label}.w1" (per-label)
    let mut ultramem = None;
    let mut expert_labels = Vec::new();

    if let (Some(w1), Some(w2)) = (tensors.get("ultramem.w1"), tensors.get("ultramem.w2")) {
        // Assembled flat pool: single w1/w2 for all experts
        let total_slots = w1.shape[0];
        let w1_cols = if w1.shape.len() > 1 { w1.shape[1] } else { w1.data.len() / total_slots };
        let expert_hidden = w1_cols / dim as usize;

        ultramem = Some(UltraMemV2Weights {
            w1: w1.clone(),
            w2: w2.clone(),
            keys_row: tensors.get("ultramem.keys_row").cloned().unwrap_or_else(|| Tensor { name: String::new(), data: vec![], shape: vec![] }),
            keys_col: tensors.get("ultramem.keys_col").cloned().unwrap_or_else(|| Tensor { name: String::new(), data: vec![], shape: vec![] }),
            query_row: tensors.get("ultramem.query_row.weight").cloned(),
            query_col: tensors.get("ultramem.query_col.weight").cloned(),
            out_proj: tensors.get("ultramem.out_proj.weight").cloned(),
            gate: tensors.get("ultramem.gate.weight").cloned(),
            norm: tensors.get("ultramem.norm.weight").cloned(),
            total_slots,
            expert_hidden,
            top_m: 128,
        });
    }

    // Per-label experts: "experts.{label}.w1", "experts.{label}.w2"
    let mut label_names: Vec<String> = Vec::new();
    for name in tensors.keys() {
        if let Some(rest) = name.strip_prefix("experts.") {
            if let Some(label) = rest.strip_suffix(".w1") {
                if !label.contains('.') {
                    label_names.push(label.to_string());
                }
            }
        }
    }
    label_names.sort();
    label_names.dedup();

    if !label_names.is_empty() {
        let mut all_w1 = Vec::new();
        let mut all_w2 = Vec::new();
        let mut offset = 0;

        for label in &label_names {
            if let (Some(w1), Some(w2)) = (
                tensors.get(&format!("experts.{label}.w1")),
                tensors.get(&format!("experts.{label}.w2")),
            ) {
                let slots = w1.shape[0];
                expert_labels.push(LabelExpertWeights {
                    label: label.clone(),
                    w1: w1.data.clone(),
                    w2: w2.data.clone(),
                    slots,
                    offset,
                });
                all_w1.extend_from_slice(&w1.data);
                all_w2.extend_from_slice(&w2.data);
                offset += slots;
            }
        }

        if offset > 0 && ultramem.is_none() {
            let total_slots = offset;
            let w1_cols = all_w1.len() / total_slots;
            let expert_hidden = w1_cols / dim as usize;

            ultramem = Some(UltraMemV2Weights {
                w1: Tensor { name: "experts.w1".into(), data: all_w1, shape: vec![total_slots, w1_cols] },
                w2: Tensor { name: "experts.w2".into(), data: all_w2, shape: vec![total_slots, w1_cols] },
                keys_row: Tensor { name: String::new(), data: vec![], shape: vec![] },
                keys_col: Tensor { name: String::new(), data: vec![], shape: vec![] },
                query_row: None,
                query_col: None,
                out_proj: None,
                gate: None,
                norm: None,
                total_slots,
                expert_hidden,
                top_m: 128,
            });
        }
    }

    Ok(HayateV5Model {
        config,
        embed_tokens: embed,
        pos_embed: get("pos_embed.weight").unwrap_or_else(|_| Tensor { name: String::new(), data: vec![0.0; dim as usize * 512], shape: vec![512, dim as usize] }),
        groups,
        shared_attn,
        final_norm: get("norm.weight")?,
        lm_head: get("head.weight")?,
        ultramem,
        expert_labels,
    })
}

/// Parse safetensors header to get tensor metadata
/// Format: 8-byte LE header size, then JSON header, then raw data
pub fn parse_safetensors_header(data: &[u8]) -> Result<HashMap<String, TensorMeta>, String> {
    if data.len() < 8 {
        return Err("file too small".into());
    }
    let header_size = u64::from_le_bytes(data[..8].try_into().unwrap()) as usize;
    if data.len() < 8 + header_size {
        return Err("truncated header".into());
    }
    let header_json = std::str::from_utf8(&data[8..8 + header_size])
        .map_err(|e| format!("invalid UTF-8: {e}"))?;

    let header: HashMap<String, serde_json::Value> =
        serde_json::from_str(header_json).map_err(|e| format!("invalid JSON: {e}"))?;

    let mut result = HashMap::new();
    for (name, info) in &header {
        if name == "__metadata__" {
            continue;
        }
        if let Some(obj) = info.as_object() {
            let dtype = obj
                .get("dtype")
                .and_then(|v| v.as_str())
                .unwrap_or("F32")
                .to_string();
            let shape: Vec<usize> = obj
                .get("shape")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_u64().map(|n| n as usize)).collect())
                .unwrap_or_default();
            let offsets: Vec<usize> = obj
                .get("data_offsets")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_u64().map(|n| n as usize)).collect())
                .unwrap_or_default();

            let (start, end) = if offsets.len() == 2 {
                (offsets[0], offsets[1])
            } else {
                (0, 0)
            };

            result.insert(
                name.clone(),
                TensorMeta {
                    dtype,
                    shape,
                    data_start: 8 + header_size + start,
                    data_end: 8 + header_size + end,
                },
            );
        }
    }
    Ok(result)
}

#[derive(Debug, Clone)]
pub struct TensorMeta {
    pub dtype: String,
    pub shape: Vec<usize>,
    pub data_start: usize,
    pub data_end: usize,
}

/// Extract f32 tensor data from safetensors binary
pub fn extract_f32_tensor(data: &[u8], meta: &TensorMeta) -> Tensor {
    let raw = &data[meta.data_start..meta.data_end];
    let floats: Vec<f32> = match meta.dtype.as_str() {
        "F32" => bytemuck::cast_slice(raw).to_vec(),
        "F16" => {
            // Convert f16 → f32
            raw.chunks_exact(2)
                .map(|chunk| {
                    let bits = u16::from_le_bytes([chunk[0], chunk[1]]);
                    f16_to_f32(bits)
                })
                .collect()
        }
        "BF16" => {
            raw.chunks_exact(2)
                .map(|chunk| {
                    let bits = u16::from_le_bytes([chunk[0], chunk[1]]);
                    bf16_to_f32(bits)
                })
                .collect()
        }
        "I8" => {
            // int8 quantized — dequantize to f32 using per-tensor scale
            // Scale must be provided via extract_f32_tensor_int8() or set to 1.0
            raw.iter()
                .map(|&b| (b as i8) as f32)
                .collect()
        }
        _ => vec![0.0; meta.shape.iter().product()],
    };

    Tensor {
        name: String::new(),
        data: floats,
        shape: meta.shape.clone(),
    }
}

/// Extract int8 tensor and dequantize using a scale factor tensor.
/// Looks up "{name}_scale" in the header for the per-tensor scale.
pub fn extract_f32_tensor_int8(
    data: &[u8],
    meta: &TensorMeta,
    scale: f32,
) -> Tensor {
    let raw = &data[meta.data_start..meta.data_end];
    let floats: Vec<f32> = raw
        .iter()
        .map(|&b| (b as i8) as f32 * scale)
        .collect();
    Tensor {
        name: String::new(),
        data: floats,
        shape: meta.shape.clone(),
    }
}

/// Load a single f32 scalar from a scale tensor
pub fn extract_scale(data: &[u8], meta: &TensorMeta) -> f32 {
    let raw = &data[meta.data_start..meta.data_end];
    if raw.len() >= 4 {
        f32::from_le_bytes([raw[0], raw[1], raw[2], raw[3]])
    } else {
        1.0
    }
}

fn f16_to_f32(bits: u16) -> f32 {
    let sign = ((bits >> 15) & 1) as u32;
    let exp = ((bits >> 10) & 0x1f) as u32;
    let mant = (bits & 0x3ff) as u32;

    if exp == 0 {
        if mant == 0 {
            return f32::from_bits(sign << 31);
        }
        // Subnormal
        let mut e = 1u32;
        let mut m = mant;
        while (m & 0x400) == 0 {
            m <<= 1;
            e += 1;
        }
        let f32_exp = 127 - 15 - e + 1;
        let f32_mant = (m & 0x3ff) << 13;
        f32::from_bits((sign << 31) | (f32_exp << 23) | f32_mant)
    } else if exp == 31 {
        let f32_mant = mant << 13;
        f32::from_bits((sign << 31) | (0xff << 23) | f32_mant)
    } else {
        let f32_exp = exp + 127 - 15;
        let f32_mant = mant << 13;
        f32::from_bits((sign << 31) | (f32_exp << 23) | f32_mant)
    }
}

fn bf16_to_f32(bits: u16) -> f32 {
    f32::from_bits((bits as u32) << 16)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_f16_conversion() {
        assert_eq!(f16_to_f32(0x0000), 0.0);
        assert_eq!(f16_to_f32(0x3c00), 1.0);
        assert!((f16_to_f32(0x4000) - 2.0).abs() < 1e-6);
    }

    #[test]
    fn test_bf16_conversion() {
        assert_eq!(bf16_to_f32(0x0000), 0.0);
        assert_eq!(bf16_to_f32(0x3f80), 1.0);
    }

    #[test]
    fn test_model_config() {
        let cfg = ModelConfig {
            model_type: "qwen2".into(),
            hidden_size: 3072,
            intermediate_size: 14336,
            num_attention_heads: 24,
            num_hidden_layers: 32,
            head_dim: 0,
            vocab_size: 151936,
            max_position_embeddings: 32768,
            rms_norm_eps: 1e-6,
            num_key_value_heads: 24,
            quantization: "int4".into(),
            ..Default::default()
        };
        assert_eq!(cfg.head_dim(), 128); // 3072 / 24
        assert_eq!(cfg.ffn_dim(), 14336);
    }
}

#[cfg(test)]
mod int8_tests {
    use super::*;

    #[test]
    #[ignore = "requires /tmp/hayate_v6_test_int8.safetensors fixture"]
    fn test_load_v6_int8_safetensors() {
        let data = std::fs::read("/tmp/hayate_v6_test_int8.safetensors")
            .expect("test safetensors file not found");
        let model = load_hayate_v5_from_bytes(&data).expect("failed to load model");

        assert_eq!(model.config.hidden_size, 64);
        assert_eq!(model.config.vocab_size, 100);
        assert_eq!(model.groups.len(), 1);
        assert_eq!(model.groups[0].mambas.len(), 1);

        // Check expert weights loaded correctly (int8 dequantized)
        let um = model.ultramem.as_ref().expect("ultramem should be loaded");
        assert_eq!(um.total_slots, 16);
        assert_eq!(um.expert_hidden, 8); // dim=64, eh = 512/64 = 8
        assert!(!um.w1.data.is_empty(), "w1 should have data");
        assert!(!um.w2.data.is_empty(), "w2 should have data");
        // w1 should NOT be all zeros (int8 dequant must have worked)
        let w1_nonzero = um.w1.data.iter().any(|&v| v != 0.0);
        assert!(w1_nonzero, "w1 should have non-zero values after int8 dequant");

        // Check keys
        assert!(!um.keys_row.data.is_empty(), "keys_row should be loaded");
        assert!(!um.keys_col.data.is_empty(), "keys_col should be loaded");

        println!("V6 int8 model loaded OK:");
        println!("  dim={}, vocab={}, groups={}", model.config.hidden_size, model.config.vocab_size, model.groups.len());
        println!("  experts: {} slots, eh={}", um.total_slots, um.expert_hidden);
        println!("  w1: {} elements, w2: {} elements", um.w1.data.len(), um.w2.data.len());
        println!("  w1 range: [{:.4}, {:.4}]", um.w1.data.iter().cloned().fold(f32::INFINITY, f32::min), um.w1.data.iter().cloned().fold(f32::NEG_INFINITY, f32::max));
    }
}
