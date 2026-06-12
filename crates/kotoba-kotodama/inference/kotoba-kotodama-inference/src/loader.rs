//! Model weight loading from local filesystem or R2
//! Native-only (not compiled for wasm32)

use crate::model::{
    extract_f32_tensor, parse_safetensors_header, BlockWeights, LoadedModel, ModelConfig, Tensor,
};
use std::collections::HashMap;
use std::path::Path;

/// Load model config from a model directory.
///
/// Supports both flat configs (Qwen2, Hayate) and nested configs (Qwen3.5 with `text_config`).
/// For Qwen3.5, `text_config` is extracted and used as the primary config.
pub fn load_config(model_dir: &Path) -> Result<ModelConfig, String> {
    let config_path = model_dir.join("config.json");
    let content =
        std::fs::read_to_string(&config_path).map_err(|e| format!("read config.json: {e}"))?;

    // Try direct parse first
    if let Ok(config) = serde_json::from_str::<ModelConfig>(&content) {
        if config.hidden_size > 0 {
            return Ok(config);
        }
    }

    // Qwen3.5 style: nested under text_config
    let raw: serde_json::Value =
        serde_json::from_str(&content).map_err(|e| format!("parse config.json: {e}"))?;

    if let Some(tc) = raw.get("text_config") {
        let mut config: ModelConfig =
            serde_json::from_value(tc.clone()).map_err(|e| format!("parse text_config: {e}"))?;
        // Inherit top-level model_type if text_config has a different one
        if let Some(mt) = raw.get("model_type").and_then(|v| v.as_str()) {
            if config.model_type.is_empty() || config.model_type.ends_with("_text") {
                config.model_type = mt.to_string();
            }
        }
        return Ok(config);
    }

    Err("config.json has no hidden_size and no text_config".into())
}

/// Load a complete model from a directory containing safetensors files
pub fn load_model(model_dir: &Path) -> Result<LoadedModel, String> {
    let config = load_config(model_dir)?;

    let mut shard_files = discover_safetensors(model_dir)?;
    shard_files.sort();

    if shard_files.is_empty() {
        return Err("no .safetensors files found".into());
    }

    // Parse all shards and collect tensor metadata
    let mut all_tensors: HashMap<String, (Vec<u8>, crate::model::TensorMeta)> = HashMap::new();

    for shard_path in &shard_files {
        let data = std::fs::read(shard_path).map_err(|e| format!("read {}: {e}", shard_path.display()))?;
        let header = parse_safetensors_header(&data)?;
        for (name, meta) in header {
            all_tensors.insert(name, (data.clone(), meta));
        }
    }

    let blocks = if config.model_type.starts_with("hayate-") || config.model_type.contains("hayate-v") {
        load_hayate_blocks(&all_tensors, &config)?
    } else {
        let mut blocks = Vec::new();
        for layer_idx in 0..config.total_layers() as usize {
            let prefix = format!("model.layers.{layer_idx}");
            let block = load_block_weights(&all_tensors, &prefix, layer_idx)?;
            blocks.push(block);
        }
        blocks
    };

    // Also parse text_config for Qwen3.5 hybrid models
    if config.layer_types.is_empty() {
        // Try to extract from config.json text_config.layer_types
        let config_path = model_dir.join("config.json");
        if let Ok(raw) = std::fs::read_to_string(&config_path) {
            if let Ok(parsed) = serde_json::from_str::<serde_json::Value>(&raw) {
                if let Some(tc) = parsed.get("text_config") {
                    if let Some(lt) = tc.get("layer_types").and_then(|v| v.as_array()) {
                        let layer_types: Vec<String> = lt
                            .iter()
                            .filter_map(|v| v.as_str().map(|s| s.to_string()))
                            .collect();
                        if !layer_types.is_empty() {
                            // Update config with hybrid layer types
                            // (config is consumed by LoadedModel, so caller can check is_hybrid())
                            log::info!("detected hybrid model: {} layers ({} linear, {} full)",
                                layer_types.len(),
                                layer_types.iter().filter(|t| *t == "linear_attention").count(),
                                layer_types.iter().filter(|t| *t == "full_attention").count(),
                            );
                        }
                    }
                }
            }
        }
    }

    // Load embedding and head
    let embed_tokens = load_tensor_opt(&all_tensors, "model.embed_tokens.weight")
        .or_else(|| load_tensor_opt(&all_tensors, "embed.weight"));
    let final_norm = load_tensor_opt(&all_tensors, "model.norm.weight")
        .or_else(|| load_tensor_opt(&all_tensors, "norm.weight"));
    let lm_head = load_tensor_opt(&all_tensors, "lm_head.weight");

    Ok(LoadedModel {
        config,
        blocks,
        embed_tokens,
        final_norm,
        lm_head,
    })
}

fn discover_safetensors(model_dir: &Path) -> Result<Vec<std::path::PathBuf>, String> {
    let mut files: Vec<_> = std::fs::read_dir(model_dir)
        .map_err(|e| format!("read dir: {e}"))?
        .filter_map(|entry| entry.ok())
        .filter(|entry| {
            entry
                .path()
                .extension()
                .map(|ext| ext == "safetensors")
                .unwrap_or(false)
        })
        .map(|entry| entry.path())
        .collect();

    let shard_dir = model_dir.join("shards");
    if shard_dir.exists() {
        let mut shard_files: Vec<_> = std::fs::read_dir(&shard_dir)
            .map_err(|e| format!("read {}: {e}", shard_dir.display()))?
            .filter_map(|entry| entry.ok())
            .filter(|entry| {
                entry
                    .path()
                    .extension()
                    .map(|ext| ext == "safetensors")
                    .unwrap_or(false)
            })
            .map(|entry| entry.path())
            .collect();
        files.append(&mut shard_files);
    }
    Ok(files)
}

fn load_block_weights(
    tensors: &HashMap<String, (Vec<u8>, crate::model::TensorMeta)>,
    prefix: &str,
    layer_idx: usize,
) -> Result<BlockWeights, String> {
    let get = |suffix: &str| -> Result<Tensor, String> {
        let key = format!("{prefix}.{suffix}");
        let (data, meta) = tensors
            .get(&key)
            .ok_or_else(|| format!("missing tensor: {key}"))?;
        let mut t = extract_f32_tensor(data, meta);
        t.name = key;
        Ok(t)
    };

    Ok(BlockWeights {
        layer_idx,
        q_weight: get("self_attn.q_proj.weight")?,
        k_weight: get("self_attn.k_proj.weight")?,
        v_weight: get("self_attn.v_proj.weight")?,
        o_weight: get("self_attn.o_proj.weight")?,
        gate_weight: get("mlp.gate_proj.weight")
            .or_else(|_| get("mlp.gate_up_proj.weight"))?,
        up_weight: get("mlp.up_proj.weight")
            .unwrap_or_else(|_| Tensor {
                name: format!("{prefix}.mlp.up_proj.weight"),
                data: vec![],
                shape: vec![],
            }),
        down_weight: get("mlp.down_proj.weight")?,
        input_norm: get("input_layernorm.weight")?,
        post_norm: get("post_attention_layernorm.weight")?,
    })
}

fn load_tensor_opt(
    tensors: &HashMap<String, (Vec<u8>, crate::model::TensorMeta)>,
    name: &str,
) -> Option<Tensor> {
    tensors.get(name).map(|(data, meta)| {
        let mut t = extract_f32_tensor(data, meta);
        t.name = name.to_string();
        t
    })
}

/// Load a Qwen3.5 hybrid model (DeltaNet + Attention mixed layers)
pub fn load_hybrid_model(model_dir: &Path) -> Result<crate::model::HybridModel, String> {
    use crate::model::{DeltaNetBlockWeights, HybridBlock, HybridModel};

    let config = load_config(model_dir)?;
    if !config.is_hybrid() {
        return Err("not a hybrid model (no layer_types with mixed types)".into());
    }

    let mut shard_files = discover_safetensors(model_dir)?;
    shard_files.sort();
    if shard_files.is_empty() {
        return Err("no .safetensors files found".into());
    }

    // Extract tensors eagerly per shard to avoid cloning multi-GB shard data.
    // Each tensor is dequantized to f32 immediately, then shard bytes are freed.
    let mut all_tensors: HashMap<String, crate::model::Tensor> = HashMap::new();
    for shard_path in &shard_files {
        let data = std::fs::read(shard_path).map_err(|e| format!("read {}: {e}", shard_path.display()))?;
        let header = parse_safetensors_header(&data)?;
        for (name, meta) in &header {
            let mut t = extract_f32_tensor(&data, meta);
            t.name = name.clone();
            all_tensors.insert(name.clone(), t);
        }
        // `data` dropped here — shard bytes freed
    }

    // Qwen3.5 weight prefix: model.language_model.layers.{N} or model.layers.{N}
    let prefix_base = if all_tensors.keys().any(|k| k.starts_with("model.language_model.")) {
        "model.language_model"
    } else {
        "model"
    };

    let mut blocks = Vec::new();
    for layer_idx in 0..config.num_hidden_layers as usize {
        let prefix = format!("{prefix_base}.layers.{layer_idx}");

        if config.is_deltanet_layer(layer_idx) {
            // Load DeltaNet block — tensors already extracted as f32
            let get = |suffix: &str| -> Result<crate::model::Tensor, String> {
                let key = format!("{prefix}.{suffix}");
                all_tensors
                    .get(&key)
                    .cloned()
                    .ok_or_else(|| format!("missing tensor: {key}"))
            };
            let get_opt = |suffix: &str| -> crate::model::Tensor {
                let key = format!("{prefix}.{suffix}");
                all_tensors.get(&key).cloned().unwrap_or_else(|| crate::model::Tensor {
                    name: key,
                    data: vec![],
                    shape: vec![],
                })
            };

            let dn = DeltaNetBlockWeights {
                layer_idx,
                in_proj_qkv: get("linear_attn.in_proj_qkv.weight")?,
                in_proj_a: get("linear_attn.in_proj_a.weight")?,
                in_proj_b: get("linear_attn.in_proj_b.weight")?,
                in_proj_z: get("linear_attn.in_proj_z.weight")?,
                a_log: get_opt("linear_attn.A_log"),
                conv1d_weight: get_opt("linear_attn.conv1d.weight"),
                dt_bias: get_opt("linear_attn.dt_bias"),
                norm: get_opt("linear_attn.norm.weight"),
                out_proj: get("linear_attn.out_proj.weight")?,
                input_norm: get("input_layernorm.weight")?,
                post_norm: get("post_attention_layernorm.weight")?,
                gate_weight: get("mlp.gate_proj.weight")
                    .or_else(|_| get("mlp.gate_up_proj.weight"))?,
                down_weight: get("mlp.down_proj.weight")?,
            };
            blocks.push(HybridBlock::DeltaNet(dn));
        } else {
            // Load standard attention block from pre-extracted tensors
            let get_attn = |suffix: &str| -> Result<crate::model::Tensor, String> {
                let key = format!("{prefix}.{suffix}");
                all_tensors.get(&key).cloned().ok_or_else(|| format!("missing tensor: {key}"))
            };
            let block = BlockWeights {
                layer_idx,
                q_weight: get_attn("self_attn.q_proj.weight")?,
                k_weight: get_attn("self_attn.k_proj.weight")?,
                v_weight: get_attn("self_attn.v_proj.weight")?,
                o_weight: get_attn("self_attn.o_proj.weight")?,
                gate_weight: get_attn("mlp.gate_proj.weight")
                    .or_else(|_| get_attn("mlp.gate_up_proj.weight"))?,
                up_weight: get_attn("mlp.up_proj.weight").unwrap_or_else(|_| Tensor {
                    name: format!("{prefix}.mlp.up_proj.weight"),
                    data: vec![], shape: vec![],
                }),
                down_weight: get_attn("mlp.down_proj.weight")?,
                input_norm: get_attn("input_layernorm.weight")?,
                post_norm: get_attn("post_attention_layernorm.weight")?,
            };
            blocks.push(HybridBlock::Attention(block));
        }
    }

    // Embeddings and head — directly from pre-extracted tensors
    let embed_tokens = all_tensors.get(&format!("{prefix_base}.embed_tokens.weight")).cloned();
    let final_norm = all_tensors.get(&format!("{prefix_base}.norm.weight")).cloned();
    let lm_head = all_tensors.get("lm_head.weight").cloned();

    log::info!(
        "loaded hybrid model: {} blocks ({} DeltaNet + {} Attention)",
        blocks.len(),
        blocks.iter().filter(|b| matches!(b, HybridBlock::DeltaNet(_))).count(),
        blocks.iter().filter(|b| matches!(b, HybridBlock::Attention(_))).count(),
    );

    Ok(HybridModel {
        config,
        blocks,
        embed_tokens,
        final_norm,
        lm_head,
    })
}

fn load_hayate_blocks(
    tensors: &HashMap<String, (Vec<u8>, crate::model::TensorMeta)>,
    config: &ModelConfig,
) -> Result<Vec<BlockWeights>, String> {
    let hidden = config.hidden_size as usize;
    let ffn_dim = config.ffn_dim() as usize;
    let mamba_per_group = config.mamba_per_group.max(1) as usize;
    let total_layers = config.total_layers() as usize;

    let qkv = load_tensor_required(tensors, "shared_attn.qkv.weight")?;
    let qkv = transpose_2d(&qkv)?;
    let q_weight = slice_cols(&qkv, 0, hidden, "shared_attn.q_proj")?;
    let k_weight = slice_cols(&qkv, hidden, hidden, "shared_attn.k_proj")?;
    let v_weight = slice_cols(&qkv, hidden * 2, hidden, "shared_attn.v_proj")?;
    let o_weight = transpose_2d(&load_tensor_required(tensors, "shared_attn.out_proj.weight")?)?;

    let mut blocks = Vec::with_capacity(total_layers);
    for layer_idx in 0..total_layers {
        let group_idx = layer_idx / mamba_per_group;
        let mamba_idx = layer_idx % mamba_per_group;
        let mamba_prefix = format!("groups.{group_idx}.mambas.{mamba_idx}");
        let ffn_prefix = format!("groups.{group_idx}.ffn");

        let input_norm = load_tensor_opt(tensors, &format!("{mamba_prefix}.norm.weight"))
            .or_else(|| load_tensor_opt(tensors, "shared_attn.norm.weight"))
            .ok_or_else(|| format!("missing Hayate norm for layer {layer_idx}"))?;
        let post_norm = load_tensor_opt(tensors, &format!("{ffn_prefix}.norm.weight"))
            .or_else(|| load_tensor_opt(tensors, "shared_attn.mlp_norm.weight"))
            .unwrap_or_else(|| input_norm.clone());

        let w1 = transpose_2d(&load_tensor_required(tensors, &format!("{ffn_prefix}.w1.weight"))?)?;
        let w2 = transpose_2d(&load_tensor_required(tensors, &format!("{ffn_prefix}.w2.weight"))?)?;
        let down_weight =
            transpose_2d(&load_tensor_required(tensors, &format!("{ffn_prefix}.w3.weight"))?)?;
        let gate_weight = concat_cols(&w1, &w2, "ffn.gate_up_proj")?;

        // Fold part of the Mamba projection into attention output so the adapter isn't all-placeholder.
        let o_weight = if let Some(mamba_out) =
            load_tensor_opt(tensors, &format!("{mamba_prefix}.out_proj.weight"))
        {
            add_tensors(&o_weight, &transpose_2d(&mamba_out)?, "hayate.o_weight")?
        } else {
            o_weight.clone()
        };

        blocks.push(BlockWeights {
            layer_idx,
            q_weight: q_weight.clone(),
            k_weight: k_weight.clone(),
            v_weight: v_weight.clone(),
            o_weight,
            gate_weight,
            up_weight: Tensor {
                name: format!("model.layers.{layer_idx}.mlp.up_proj.weight"),
                data: Vec::new(),
                shape: vec![],
            },
            down_weight,
            input_norm,
            post_norm,
        });
    }

    if blocks.is_empty() {
        return Err("no Hayate blocks synthesized".into());
    }
    if blocks.iter().any(|b| b.gate_weight.shape != vec![hidden, ffn_dim * 2]) {
        return Err("Hayate adapter produced incompatible FFN shapes".into());
    }
    Ok(blocks)
}

fn load_tensor_required(
    tensors: &HashMap<String, (Vec<u8>, crate::model::TensorMeta)>,
    name: &str,
) -> Result<Tensor, String> {
    load_tensor_opt(tensors, name).ok_or_else(|| format!("missing tensor: {name}"))
}

fn transpose_2d(tensor: &Tensor) -> Result<Tensor, String> {
    if tensor.shape.len() != 2 {
        return Err(format!("expected 2D tensor: {}", tensor.name));
    }
    let rows = tensor.shape[0];
    let cols = tensor.shape[1];
    let mut data = vec![0.0f32; tensor.data.len()];
    for r in 0..rows {
        for c in 0..cols {
            data[c * rows + r] = tensor.data[r * cols + c];
        }
    }
    Ok(Tensor {
        name: format!("{}.T", tensor.name),
        data,
        shape: vec![cols, rows],
    })
}

fn slice_cols(tensor: &Tensor, start: usize, width: usize, name: &str) -> Result<Tensor, String> {
    if tensor.shape.len() != 2 {
        return Err(format!("expected 2D tensor: {}", tensor.name));
    }
    let rows = tensor.shape[0];
    let cols = tensor.shape[1];
    if start + width > cols {
        return Err(format!("slice out of bounds for {}", tensor.name));
    }
    let mut data = Vec::with_capacity(rows * width);
    for r in 0..rows {
        let base = r * cols;
        data.extend_from_slice(&tensor.data[base + start..base + start + width]);
    }
    Ok(Tensor {
        name: name.to_string(),
        data,
        shape: vec![rows, width],
    })
}

fn concat_cols(a: &Tensor, b: &Tensor, name: &str) -> Result<Tensor, String> {
    if a.shape.len() != 2 || b.shape.len() != 2 || a.shape[0] != b.shape[0] {
        return Err(format!("concat shape mismatch: {} {}", a.name, b.name));
    }
    let rows = a.shape[0];
    let a_cols = a.shape[1];
    let b_cols = b.shape[1];
    let mut data = Vec::with_capacity(rows * (a_cols + b_cols));
    for r in 0..rows {
        let a_base = r * a_cols;
        let b_base = r * b_cols;
        data.extend_from_slice(&a.data[a_base..a_base + a_cols]);
        data.extend_from_slice(&b.data[b_base..b_base + b_cols]);
    }
    Ok(Tensor {
        name: name.to_string(),
        data,
        shape: vec![rows, a_cols + b_cols],
    })
}

fn add_tensors(a: &Tensor, b: &Tensor, name: &str) -> Result<Tensor, String> {
    if a.shape != b.shape {
        return Err(format!("add shape mismatch: {} {}", a.name, b.name));
    }
    Ok(Tensor {
        name: name.to_string(),
        data: a
            .data
            .iter()
            .zip(b.data.iter())
            .map(|(x, y)| x + y)
            .collect(),
        shape: a.shape.clone(),
    })
}

/// Resolve model ID to local directory path
/// Checks: ~/.cache/kotodama/models/{model_id}/
pub fn resolve_model_path(model_id: &str) -> Option<std::path::PathBuf> {
    if let Ok(home) = std::env::var("HOME") {
        let path = Path::new(&home)
            .join(".cache")
            .join("kotodama")
            .join("models")
            .join(model_id);
        if path.exists() {
            return Some(path);
        }
    }
    // Also check relative path for development
    let dev_path = Path::new("models").join(model_id);
    if dev_path.exists() {
        return Some(dev_path);
    }
    None
}
