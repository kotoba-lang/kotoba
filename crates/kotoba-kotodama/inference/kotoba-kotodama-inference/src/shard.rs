//! Distributed shard management — split models across browser/native workers

use crate::model::{ModelConfig, ShardAssignment};
use serde::{Deserialize, Serialize};

/// Plan for distributing model layers across workers
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShardPlan {
    pub model_id: String,
    pub total_layers: usize,
    pub assignments: Vec<ShardAssignment>,
}

/// Worker capability for shard assignment decisions
#[derive(Debug, Clone)]
pub struct WorkerSlot {
    pub worker_id: String,
    pub gpu_tier: String,
    pub vram_mb: u64,
    pub runtime_class: String,
}

/// Result from one shard's forward pass
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ShardOutput {
    pub shard_id: String,
    pub hidden_states_b64: String,
    pub gpu_time_ms: u64,
    pub checksum: u32,
}

impl ShardPlan {
    /// Create a shard plan that distributes layers across workers based on VRAM capacity
    pub fn create(
        model_id: &str,
        config: &ModelConfig,
        workers: &[WorkerSlot],
    ) -> Self {
        let total_layers = config.num_hidden_layers as usize;

        if workers.is_empty() {
            return Self {
                model_id: model_id.into(),
                total_layers,
                assignments: vec![ShardAssignment {
                    shard_id: format!("{model_id}-shard-0"),
                    start_layer: 0,
                    end_layer: total_layers,
                    model_id: model_id.into(),
                }],
            };
        }

        // Weight VRAM to determine layer allocation
        let total_vram: u64 = workers.iter().map(|w| w.vram_mb.max(256)).sum();
        let mut assignments = Vec::new();
        let mut layer_cursor = 0usize;

        for (i, worker) in workers.iter().enumerate() {
            let worker_vram = worker.vram_mb.max(256);
            let share = (worker_vram as f64) / (total_vram as f64);
            let layer_count = if i == workers.len() - 1 {
                total_layers - layer_cursor
            } else {
                ((total_layers as f64 * share).round() as usize).max(1)
            };

            let end = (layer_cursor + layer_count).min(total_layers);
            assignments.push(ShardAssignment {
                shard_id: format!("{model_id}-shard-{i}"),
                start_layer: layer_cursor,
                end_layer: end,
                model_id: model_id.into(),
            });

            layer_cursor = end;
            if layer_cursor >= total_layers {
                break;
            }
        }

        Self {
            model_id: model_id.into(),
            total_layers,
            assignments,
        }
    }

    /// Simple equal split (for homogeneous workers)
    pub fn equal_split(model_id: &str, total_layers: usize, num_shards: usize) -> Self {
        let per_shard = total_layers / num_shards.max(1);
        let mut assignments = Vec::new();
        let mut cursor = 0;

        for i in 0..num_shards {
            let end = if i == num_shards - 1 {
                total_layers
            } else {
                cursor + per_shard
            };
            assignments.push(ShardAssignment {
                shard_id: format!("{model_id}-shard-{i}"),
                start_layer: cursor,
                end_layer: end,
                model_id: model_id.into(),
            });
            cursor = end;
        }

        Self {
            model_id: model_id.into(),
            total_layers,
            assignments,
        }
    }
}

/// Merge partial shard outputs into a complete hidden state
pub fn merge_shard_outputs(outputs: &[ShardOutput]) -> Result<Vec<f32>, String> {
    // Shards are sequential pipeline stages — last shard's output is the final hidden state
    let last = outputs.last().ok_or("no shard outputs")?;
    decode_hidden_states(&last.hidden_states_b64)
}

pub fn encode_hidden_states(data: &[f32]) -> String {
    use base64::Engine;
    let bytes: &[u8] = bytemuck::cast_slice(data);
    base64::engine::general_purpose::STANDARD.encode(bytes)
}

pub fn decode_hidden_states(b64: &str) -> Result<Vec<f32>, String> {
    use base64::Engine;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(b64)
        .map_err(|e| format!("base64 decode: {e}"))?;
    if bytes.len() % 4 != 0 {
        return Err("invalid float data length".into());
    }
    Ok(bytemuck::cast_slice(&bytes).to_vec())
}

/// Compute a simple checksum of hidden states for verification
pub fn checksum(data: &[f32]) -> u32 {
    let bytes: &[u8] = bytemuck::cast_slice(data);
    let hash = blake3::hash(bytes);
    let h = hash.as_bytes();
    u32::from_le_bytes([h[0], h[1], h[2], h[3]])
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_equal_split() {
        let plan = ShardPlan::equal_split("test-model", 32, 4);
        assert_eq!(plan.assignments.len(), 4);
        assert_eq!(plan.assignments[0].start_layer, 0);
        assert_eq!(plan.assignments[0].end_layer, 8);
        assert_eq!(plan.assignments[3].start_layer, 24);
        assert_eq!(plan.assignments[3].end_layer, 32);
    }

    #[test]
    fn test_vram_weighted_split() {
        let config = ModelConfig {
            model_type: "qwen2".into(),
            hidden_size: 3072,
            intermediate_size: 14336,
            num_attention_heads: 24,
            num_hidden_layers: 32,
            head_dim: 128,
            vocab_size: 151936,
            max_position_embeddings: 32768,
            rms_norm_eps: 1e-6,
            num_key_value_heads: 24,
            quantization: "int4".into(),
            ..Default::default()
        };
        let workers = vec![
            WorkerSlot { worker_id: "a".into(), gpu_tier: "g4".into(), vram_mb: 8000, runtime_class: "native".into() },
            WorkerSlot { worker_id: "b".into(), gpu_tier: "g2".into(), vram_mb: 2000, runtime_class: "browser".into() },
        ];
        let plan = ShardPlan::create("test", &config, &workers);
        assert_eq!(plan.assignments.len(), 2);
        // Worker A (8GB) should get ~80% of layers
        assert!(plan.assignments[0].end_layer > 20);
    }

    #[test]
    fn test_hidden_state_roundtrip() {
        let data = vec![1.0f32, 2.0, 3.0, -4.5];
        let encoded = encode_hidden_states(&data);
        let decoded = decode_hidden_states(&encoded).unwrap();
        assert_eq!(data, decoded);
    }

    #[test]
    fn test_checksum_deterministic() {
        let data = vec![1.0f32, 2.0, 3.0];
        assert_eq!(checksum(&data), checksum(&data));
    }
}
