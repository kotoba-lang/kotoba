//! Browser Web Worker — wasm-bindgen exports
//! Loaded inside a Web Worker via: `import init, { BrowserInferenceWorker } from 'kotodama-inference'`

use wasm_bindgen::prelude::*;

use crate::engine::InferenceEngine;
use crate::mamba2;
use crate::model::{self, HayateV5Model};
use crate::protocol::{BrowserCapability, Envelope, GpuCap, RegisterMsg, TaskResultMsg};
use crate::shard;

#[wasm_bindgen]
pub struct BrowserInferenceWorker {
    engine: InferenceEngine,
    session_id: String,
    model: Option<HayateV5Model>,
}

#[wasm_bindgen]
impl BrowserInferenceWorker {
    /// Initialize the inference engine (requests WebGPU adapter).
    /// Call via `BrowserInferenceWorker.create()` from JS.
    #[wasm_bindgen(js_name = create)]
    pub async fn create() -> Result<BrowserInferenceWorker, JsValue> {
        let engine = InferenceEngine::new()
            .await
            .map_err(|e| JsValue::from_str(&e.to_string()))?;

        Ok(Self {
            engine,
            session_id: String::new(),
            model: None,
        })
    }

    /// Set session ID after WebSocket registration
    #[wasm_bindgen(js_name = setSessionId)]
    pub fn set_session_id(&mut self, id: &str) {
        self.session_id = id.to_string();
    }

    /// Load Hayate V5 model weights from raw safetensors bytes.
    /// Call from JS: `await engine.loadWeights(new Uint8Array(arrayBuffer))`
    #[wasm_bindgen(js_name = loadWeights)]
    pub fn load_weights(&mut self, data: &[u8]) -> Result<String, JsValue> {
        let m = model::load_hayate_v5_from_bytes(data)
            .map_err(|e| JsValue::from_str(&e))?;
        let info = format!(
            "loaded hayate_v5: dim={}, groups={}, mamba/group={}, vocab={}, params={}",
            m.config.hidden_size,
            m.config.num_groups,
            m.config.mamba_per_group,
            m.config.vocab_size,
            count_params(&m),
        );
        self.model = Some(m);
        Ok(info)
    }

    /// Check if model weights are loaded
    #[wasm_bindgen(js_name = hasModel)]
    pub fn has_model(&self) -> bool {
        self.model.is_some()
    }

    /// Run full Hayate V5 inference on token IDs, return logits as Float32Array.
    /// `input_ids` is a Uint32Array of token IDs.
    #[wasm_bindgen(js_name = inferenceForward)]
    pub async fn inference_forward(&self, input_ids: Vec<u32>) -> Result<Vec<f32>, JsValue> {
        let model = self
            .model
            .as_ref()
            .ok_or_else(|| JsValue::from_str("no model loaded — call loadWeights first"))?;

        mamba2::forward_hayate_v5(&self.engine, model, &input_ids)
            .await
            .map_err(|e| JsValue::from_str(&e))
    }

    /// Build a registration envelope with probed GPU capabilities
    #[wasm_bindgen(js_name = buildRegisterEnvelope)]
    pub fn build_register_envelope(&self) -> Result<String, JsValue> {
        let cap = self.probe_capability();
        let env = Envelope::register(RegisterMsg {
            capability: cap,
            warm_shards: vec![],
        });
        serde_json::to_string(&env).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Execute a shard inference task (called when MSG_TASK_PUSH is received).
    /// If model is loaded, runs real Mamba2 block forward pass.
    /// Otherwise falls back to identity pass-through.
    #[wasm_bindgen(js_name = executeShard)]
    pub async fn execute_shard(
        &self,
        task_id: String,
        lease_id: String,
        hidden_states_b64: String,
        shard_params: String,
    ) -> Result<String, JsValue> {
        let start = js_sys::Date::now();

        let hidden = shard::decode_hidden_states(&hidden_states_b64)
            .map_err(|e| JsValue::from_str(&e))?;

        let output = if let Some(model) = &self.model {
            // Parse shard params to determine which group/layers to run
            let params: ShardParams = serde_json::from_str(&shard_params)
                .unwrap_or(ShardParams { group_idx: 0 });

            let group_idx = params.group_idx.min(model.groups.len().saturating_sub(1));
            let group = &model.groups[group_idx];

            let result =
                mamba2::forward_hayate_v5_group(&self.engine, group, &model.config, &hidden)
                    .await
                    .map_err(|e| JsValue::from_str(&e))?;
            result.hidden_states
        } else {
            // Fallback: identity pass-through (GPU pipeline test)
            let dim = hidden.len();
            if dim > 0 {
                let seq_len = 1u32;
                let d = dim as u32;
                let identity: Vec<f32> = (0..d)
                    .flat_map(|i| (0..d).map(move |j| if i == j { 1.0f32 } else { 0.0 }))
                    .collect();
                self.engine
                    .matmul(&hidden, &identity, seq_len, d, d, None)
                    .await
                    .map_err(|e| JsValue::from_str(&e.to_string()))?
            } else {
                hidden.clone()
            }
        };

        let gpu_time_ms = (js_sys::Date::now() - start) as u64;
        let cs = shard::checksum(&output);
        let output_b64 = shard::encode_hidden_states(&output);

        let env = Envelope::task_result(TaskResultMsg {
            lease_id,
            task_id,
            output: output_b64,
            gpu_time_ms,
            checksum: Some(format!("{cs:08x}")),
        });

        serde_json::to_string(&env).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Execute a GPU matmul (for testing/benchmarking)
    #[wasm_bindgen(js_name = matmul)]
    pub async fn matmul(
        &self,
        a: Vec<f32>,
        b: Vec<f32>,
        m: u32,
        k: u32,
        n: u32,
    ) -> Result<Vec<f32>, JsValue> {
        self.engine
            .matmul(&a, &b, m, k, n, None)
            .await
            .map_err(|e| JsValue::from_str(&e.to_string()))
    }

    /// Probe GPU capabilities
    #[wasm_bindgen(js_name = probeCapabilities)]
    pub fn probe_capabilities_js(&self) -> Result<String, JsValue> {
        let cap = self.probe_capability();
        serde_json::to_string(&cap).map_err(|e| JsValue::from_str(&e.to_string()))
    }

    fn probe_capability(&self) -> BrowserCapability {
        BrowserCapability {
            wasm_simd: true,
            wasm_threads: js_sys::Reflect::get(
                &js_sys::global(),
                &JsValue::from_str("SharedArrayBuffer"),
            )
            .map(|v| !v.is_undefined())
            .unwrap_or(false),
            gpu: GpuCap {
                available: true,
                adapter: "wgpu-wasm".into(),
                features: vec![],
                max_storage_buffer_binding_size: 0,
                max_compute_workgroup_storage_size: 0,
            },
            mem_class: "mid".into(),
            net_class: "good".into(),
            power_class: "desktop".into(),
            gpu_tier: "g1".into(),
            cores: 1,
            user_agent: format!("kotodama-inference-wasm/{}", env!("CARGO_PKG_VERSION")),
            runtime_class: "browser_wgpu".into(),
            accelerator_class: "webgpu".into(),
            moq_available: false,
        }
    }
}

#[derive(serde::Deserialize)]
struct ShardParams {
    #[serde(default)]
    group_idx: usize,
}

fn count_params(model: &HayateV5Model) -> usize {
    let mut total = model.embed_tokens.numel()
        + model.pos_embed.numel()
        + model.final_norm.numel()
        + model.lm_head.numel();
    for g in &model.groups {
        for m in &g.mambas {
            total += m.in_proj.numel()
                + m.dt_proj.numel()
                + m.b_proj.numel()
                + m.c_proj.numel()
                + m.d.numel()
                + m.out_proj.numel()
                + m.norm.numel();
        }
        total += g.ffn_w1.numel() + g.ffn_w2.numel() + g.ffn_w3.numel() + g.ffn_norm.numel();
    }
    total
}
