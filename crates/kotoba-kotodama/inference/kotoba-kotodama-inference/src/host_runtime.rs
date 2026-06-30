//! Host-owned handle registry for copy-minimal train/inference orchestration.
//!
//! Large tensors stay in the host registry. Callers exchange small string handles.

use crate::engine::InferenceEngine;
use crate::loader;
use crate::model::LoadedModel;
use crate::tokenizer::SimpleTokenizer;
use crate::transformer;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone)]
pub struct HostTensor {
    pub data: Vec<f32>,
    pub shape: Vec<usize>,
    pub dtype: String,
    pub device: String,
}

#[derive(Debug, Clone)]
struct SessionEntry {
    model_handle: String,
    model_id: String,
    prompt_token_ids: Vec<u32>,
    generated_token_ids: Vec<u32>,
}

#[derive(Debug, Clone)]
struct ObjectRef {
    model_id: String,
    storage_key: String,
    format: String,
    locality: String,
    digest_blake3: Option<String>,
    files: Vec<CatalogFile>,
}

struct RegistryState {
    objects: HashMap<String, ObjectRef>,
    models: HashMap<String, Arc<LoadedModel>>,
    tensors: HashMap<String, Arc<HostTensor>>,
    sessions: HashMap<String, SessionEntry>,
    model_paths: HashMap<String, PathBuf>,
    tokenizers: HashMap<String, SimpleTokenizer>,
}

impl RegistryState {
    fn new() -> Self {
        Self {
            objects: HashMap::new(),
            models: HashMap::new(),
            tensors: HashMap::new(),
            sessions: HashMap::new(),
            model_paths: HashMap::new(),
            tokenizers: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone, Deserialize)]
struct CatalogEntry {
    #[serde(default)]
    key: Option<String>,
    #[serde(default)]
    path: Option<String>,
    #[serde(default)]
    storage_key: Option<String>,
    #[serde(default)]
    format: Option<String>,
    #[serde(default)]
    locality: Option<String>,
    #[serde(default)]
    digest_blake3: Option<String>,
    #[serde(default)]
    files: Vec<CatalogFile>,
    #[serde(default)]
    artifact_files: Vec<CatalogFile>,
}

#[derive(Debug, Clone, Deserialize)]
struct CatalogFile {
    #[serde(default)]
    path: Option<String>,
    #[serde(default)]
    key: Option<String>,
    #[serde(default)]
    url: Option<String>,
    #[serde(default)]
    storage_key: Option<String>,
    #[serde(default)]
    digest_blake3: Option<String>,
}

#[derive(Serialize)]
pub struct RuntimeProbe {
    pub backend: String,
    pub zero_copy_tiers: Vec<&'static str>,
}

#[derive(Serialize)]
pub struct LoadModelSessionResult {
    pub session_handle: String,
    pub model_handle: String,
    pub model_id: String,
    pub backend: String,
    pub num_layers: usize,
    pub hidden_size: u32,
}

#[derive(Serialize)]
pub struct ResolveObjectResult {
    pub object_handle: String,
    pub model_id: String,
    pub storage_key: String,
    pub format: String,
    pub locality: String,
}

#[derive(Serialize)]
pub struct EnsureLocalResult {
    pub status: &'static str,
    pub cache_hit: bool,
    pub locality: String,
    pub residency_handle: String,
}

#[derive(Serialize)]
pub struct TensorHandleResult {
    pub tensor_handle: String,
    pub owner: &'static str,
    pub shape: Vec<usize>,
    pub dtype: String,
    pub device: String,
}

#[derive(Serialize)]
pub struct PrefillResult {
    pub hidden_handle: String,
    pub kv_handle: Option<String>,
    pub prefill_stats: PrefillStats,
}

#[derive(Serialize)]
pub struct PrefillStats {
    pub gpu_time_ms: u64,
    pub output_len: usize,
}

#[derive(Serialize)]
pub struct DecodeStepResult {
    pub token_ids: Vec<u32>,
    pub decoded_text: String,
    pub logits_handle: Option<String>,
    pub kv_handle: Option<String>,
    pub decode_stats: DecodeStats,
}

#[derive(Serialize)]
pub struct DecodeStats {
    pub steps: u32,
    pub source_handle: String,
    pub used_lm_head: bool,
}

#[derive(Serialize)]
pub struct GenerateTextResult {
    pub text: String,
    pub token_ids: Vec<u32>,
    pub backend: String,
    pub session_handle: String,
    pub model_handle: String,
    pub prefill_stats: PrefillStats,
    pub decode_stats: DecodeStats,
}

#[derive(Serialize)]
pub struct ReduceResult {
    pub reduced_handle: String,
    pub reduce_stats: ReduceStats,
}

#[derive(Serialize)]
pub struct ReduceStats {
    pub partial_count: usize,
    pub reduced_len: usize,
}

pub struct HostRuntime {
    engine: InferenceEngine,
    state: Mutex<RegistryState>,
    next_id: AtomicU64,
}

impl HostRuntime {
    pub async fn new() -> Result<Self, String> {
        let engine = InferenceEngine::new()
            .await
            .map_err(|e| e.to_string())?;
        Ok(Self {
            engine,
            state: Mutex::new(RegistryState::new()),
            next_id: AtomicU64::new(1),
        })
    }

    pub fn probe_runtime(&self) -> RuntimeProbe {
        RuntimeProbe {
            backend: self.engine.backend_name().to_string(),
            zero_copy_tiers: vec![
                "intra-container-mmap",
                "intra-node-host-owned",
                "guest-handle-based",
            ],
        }
    }

    pub fn load_model_session(&self, model_id: &str) -> Result<LoadModelSessionResult, String> {
        let model_dir = self.resolve_model_storage_path(model_id).ok_or_else(|| {
            format!(
                "model not found: {}. Expected at ~/.cache/kotodama/models/{}",
                model_id, model_id
            )
        })?;
        let loaded_model = Arc::new(loader::load_model(&model_dir)?);
        let tokenizer = SimpleTokenizer::load_from_dir(&model_dir);

        let model_handle = self.new_handle("model");
        let session_handle = self.new_handle("session");

        let mut state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        state.models.insert(model_handle.clone(), loaded_model.clone());
        state.sessions.insert(
            session_handle.clone(),
            SessionEntry {
                model_handle: model_handle.clone(),
                model_id: model_id.to_string(),
                prompt_token_ids: Vec::new(),
                generated_token_ids: Vec::new(),
            },
        );
        state
            .model_paths
            .insert(model_id.to_string(), model_dir.clone());
        state.tokenizers.insert(model_id.to_string(), tokenizer);

        Ok(LoadModelSessionResult {
            session_handle,
            model_handle,
            model_id: model_id.to_string(),
            backend: self.engine.backend_name().to_string(),
            num_layers: loaded_model.blocks.len(),
            hidden_size: loaded_model.config.hidden_size,
        })
    }

    pub fn resolve_object(
        &self,
        model_id: &str,
        _version: Option<&str>,
        _shard_id: Option<&str>,
    ) -> Result<ResolveObjectResult, String> {
        let (storage_key, format, locality, digest_blake3, files) =
            self.resolve_model_object_ref(model_id)?;
        let object_handle = self.new_handle("object");
        let object = ObjectRef {
            model_id: model_id.to_string(),
            storage_key: storage_key.clone(),
            format,
            locality,
            digest_blake3,
            files,
        };
        let mut state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        state.objects.insert(object_handle.clone(), object.clone());
        if let Ok(path) = self.materialize_storage_key(&storage_key) {
            state.model_paths.insert(model_id.to_string(), path);
        }
        Ok(ResolveObjectResult {
            object_handle,
            model_id: object.model_id,
            storage_key: object.storage_key,
            format: object.format,
            locality: object.locality,
        })
    }

    pub fn ensure_local(&self, object_handle: &str) -> Result<EnsureLocalResult, String> {
        let object = {
            let state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
            state
            .objects
            .get(object_handle)
            .cloned()
            .ok_or_else(|| format!("object not found: {object_handle}"))?
        };
        let local_path = self.materialize_object(&object)?;
        let locality = if local_path.exists() { "local" } else { &object.locality };
        let mut state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        state
            .model_paths
            .insert(object.model_id.clone(), local_path.clone());
        Ok(EnsureLocalResult {
            status: "ready",
            cache_hit: true,
            locality: locality.to_string(),
            residency_handle: format!("resident:{object_handle}"),
        })
    }

    pub fn register_prompt_tensor(
        &self,
        session_handle: &str,
        prompt: &str,
    ) -> Result<TensorHandleResult, String> {
        let model = self.get_session_model(session_handle)?;
        let tokenizer = self.get_session_tokenizer(session_handle)?;
        let dim = model.config.hidden_size as usize;
        let token_ids = tokenizer.encode(prompt);
        let hidden = self.embed_prompt_tokens(&model, &token_ids);
        let seq_len = token_ids.len().max(1).min(128);
        {
            let mut state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
            let session = state
                .sessions
                .get_mut(session_handle)
                .ok_or_else(|| format!("session not found: {session_handle}"))?;
            session.prompt_token_ids = token_ids;
            session.generated_token_ids.clear();
        }
        self.register_tensor(hidden, vec![seq_len, dim], "f32", self.engine.backend_name())
    }

    pub fn open_tensor(
        &self,
        object_handle: &str,
        offset: Option<usize>,
        length: Option<usize>,
    ) -> Result<TensorHandleResult, String> {
        let state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        let storage_key = state
            .objects
            .get(object_handle)
            .map(|o| o.storage_key.clone())
            .ok_or_else(|| format!("object not found: {object_handle}"))?;
        drop(state);
        let model_dir = self.materialize_storage_key(&storage_key)?;
        let loaded_model = loader::load_model(&model_dir)?;
        let lm_head = loaded_model
            .lm_head
            .ok_or_else(|| format!("object has no tensor viewable payload: {object_handle}"))?;
        let start = offset.unwrap_or(0).min(lm_head.data.len());
        let end = length
            .map(|len| start.saturating_add(len))
            .unwrap_or(lm_head.data.len())
            .min(lm_head.data.len());
        self.register_tensor(
            lm_head.data[start..end].to_vec(),
            vec![end - start],
            "f32",
            self.engine.backend_name(),
        )
    }

    pub fn map_tensor_view(
        &self,
        tensor_handle: &str,
        offset: Option<usize>,
        length: Option<usize>,
    ) -> Result<TensorHandleResult, String> {
        let tensor = self.get_tensor(tensor_handle)?;
        let start = offset.unwrap_or(0).min(tensor.data.len());
        let end = length
            .map(|len| start.saturating_add(len))
            .unwrap_or(tensor.data.len())
            .min(tensor.data.len());
        self.register_tensor(
            tensor.data[start..end].to_vec(),
            vec![end - start],
            &tensor.dtype,
            &tensor.device,
        )
    }

    pub async fn prefill(
        &self,
        session_handle: &str,
        token_handle: &str,
    ) -> Result<PrefillResult, String> {
        let model = self.get_session_model(session_handle)?;
        let input = self.get_tensor(token_handle)?;
        let block_refs: Vec<_> = model.blocks.iter().collect();
        let result = transformer::forward_shard(
            &self.engine,
            &block_refs,
            &model.config,
            &input.data,
        )
        .await?;

        let hidden = self.register_tensor(
            result.hidden_states.clone(),
            vec![input.shape.first().copied().unwrap_or(1), model.config.hidden_size as usize],
            "f32",
            self.engine.backend_name(),
        )?;

        Ok(PrefillResult {
            hidden_handle: hidden.tensor_handle,
            kv_handle: None,
            prefill_stats: PrefillStats {
                gpu_time_ms: result.gpu_time_ms,
                output_len: result.hidden_states.len(),
            },
        })
    }

    pub fn decode_step(
        &self,
        session_handle: &str,
        hidden_handle: &str,
        steps: u32,
    ) -> Result<DecodeStepResult, String> {
        let hidden = self.get_tensor(hidden_handle)?;
        let model = self.get_session_model(session_handle)?;
        let tokenizer = self.get_session_tokenizer(session_handle)?;
        let take = steps.max(1) as usize;
        let mut token_ids = Vec::with_capacity(take);
        let mut decoded_text = String::new();
        let mut logits_handle = None;
        let mut used_lm_head = false;

        if let Some(lm_head) = &model.lm_head {
            if let Some(last_hidden) = self.last_token_slice(&hidden.data, model.config.hidden_size as usize) {
                let logits = self.compute_logits(last_hidden, lm_head, model.config.vocab_size as usize);
                let best = logits
                    .iter()
                    .enumerate()
                    .max_by(|a, b| a.1.partial_cmp(b.1).unwrap_or(std::cmp::Ordering::Equal))
                    .map(|(idx, _)| idx as u32)
                    .unwrap_or(0);
                token_ids.resize(take, best);
                logits_handle = Some(
                    self.register_tensor(
                        logits,
                        vec![model.config.vocab_size as usize],
                        "f32",
                        self.engine.backend_name(),
                    )?
                    .tensor_handle,
                );
                used_lm_head = true;
            }
        }

        if token_ids.is_empty() {
            token_ids = hidden
                .data
                .iter()
                .take(take)
                .map(|v| ((v.abs() * 10_000.0) as u32) % 32_000)
                .collect();
        }
        {
            let mut state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
            if let Some(session) = state.sessions.get_mut(session_handle) {
                session.generated_token_ids.extend(token_ids.iter().copied());
                decoded_text = tokenizer.decode(&token_ids);
            }
        }
        Ok(DecodeStepResult {
            token_ids,
            decoded_text,
            logits_handle,
            kv_handle: None,
            decode_stats: DecodeStats {
                steps: steps.max(1),
                source_handle: hidden_handle.to_string(),
                used_lm_head,
            },
        })
    }

    pub fn reduce_partials(&self, partial_handles: &[String]) -> Result<ReduceResult, String> {
        if partial_handles.is_empty() {
            return Err("no partial handles".to_string());
        }
        let partials: Result<Vec<_>, _> = partial_handles
            .iter()
            .map(|h| self.get_tensor(h))
            .collect();
        let partials = partials?;
        let first_len = partials[0].data.len();
        let same_shape = partials.iter().all(|p| p.data.len() == first_len);
        let reduced = if same_shape {
            let mut out = vec![0.0f32; first_len];
            for part in &partials {
                for (dst, src) in out.iter_mut().zip(part.data.iter()) {
                    *dst += *src;
                }
            }
            let denom = partials.len() as f32;
            for v in &mut out {
                *v /= denom;
            }
            out
        } else {
            partials
                .last()
                .map(|p| p.data.clone())
                .ok_or_else(|| "no partial handles".to_string())?
        };
        let shape = if same_shape {
            partials[0].shape.clone()
        } else {
            vec![reduced.len()]
        };
        let handle = self.register_tensor(reduced.clone(), shape, "f32", self.engine.backend_name())?;
        Ok(ReduceResult {
            reduced_handle: handle.tensor_handle,
            reduce_stats: ReduceStats {
                partial_count: partial_handles.len(),
                reduced_len: reduced.len(),
            },
        })
    }

    pub fn release_handle(&self, handle: &str) -> Result<(), String> {
        let mut state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        if state.objects.remove(handle).is_some() {
            return Ok(());
        }
        if state.tensors.remove(handle).is_some() {
            return Ok(());
        }
        if state.sessions.remove(handle).is_some() {
            return Ok(());
        }
        if state.models.remove(handle).is_some() {
            return Ok(());
        }
        Err(format!("handle not found: {handle}"))
    }

    /// End-to-end local generation path: load a model, tokenize prompt, run
    /// prefill, decode one or more tokens, then release temporary handles.
    ///
    /// This is intentionally conservative and deterministic. It is enough to
    /// wire a real locally materialized safetensors model into a kototama
    /// `llm.infer` host binding while the sampler/KV-cache path matures.
    pub async fn generate_text(
        &self,
        model_id: &str,
        prompt: &str,
        max_new_tokens: usize,
    ) -> Result<GenerateTextResult, String> {
        let loaded = self.load_model_session(model_id)?;
        let token = self.register_prompt_tensor(&loaded.session_handle, prompt)?;
        let prefill = self.prefill(&loaded.session_handle, &token.tensor_handle).await?;
        let decode = self.decode_step(
            &loaded.session_handle,
            &prefill.hidden_handle,
            max_new_tokens.max(1).min(64) as u32,
        )?;

        let _ = self.release_handle(&token.tensor_handle);
        let _ = self.release_handle(&prefill.hidden_handle);

        Ok(GenerateTextResult {
            text: decode.decoded_text.clone(),
            token_ids: decode.token_ids.clone(),
            backend: loaded.backend.clone(),
            session_handle: loaded.session_handle,
            model_handle: loaded.model_handle,
            prefill_stats: prefill.prefill_stats,
            decode_stats: decode.decode_stats,
        })
    }

    /// Build a synchronous function suitable for `kototama::LocalInferFn`.
    ///
    /// It owns a Tokio runtime internally because kototama's current core-wasm
    /// host import ABI is synchronous. Browser/WebGPU hosts should use the
    /// async worker path instead.
    pub fn local_infer_fn(self: Arc<Self>) -> Arc<dyn Fn(&str, usize) -> Result<String, String> + Send + Sync> {
        Arc::new(move |prompt: &str, max_new_tokens: usize| {
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .map_err(|e| format!("create kotodama inference runtime: {e}"))?;
            let model_id = std::env::var("KOTODAMA_MODEL_ID")
                .or_else(|_| std::env::var("KOTODAMA_INFERENCE_MODEL"))
                .unwrap_or_else(|_| "default".to_string());
            rt.block_on(self.generate_text(&model_id, prompt, max_new_tokens))
                .map(|result| result.text)
        })
    }

    /// Build a function suitable for `kototama::LocalInferFn`, preserving the
    /// model id supplied by the guest's `(llm-infer model prompt)` call.
    pub fn kototama_local_infer_fn(
        self: Arc<Self>,
    ) -> Arc<dyn Fn(&str, &str, usize) -> Result<String, String> + Send + Sync> {
        Arc::new(move |model_id: &str, prompt: &str, max_new_tokens: usize| {
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .map_err(|e| format!("create kotodama inference runtime: {e}"))?;
            rt.block_on(self.generate_text(model_id, prompt, max_new_tokens))
                .map(|result| result.text)
        })
    }

    fn register_tensor(
        &self,
        data: Vec<f32>,
        shape: Vec<usize>,
        dtype: &str,
        device: &str,
    ) -> Result<TensorHandleResult, String> {
        let handle = self.new_handle("tensor");
        let tensor = Arc::new(HostTensor {
            data,
            shape: shape.clone(),
            dtype: dtype.to_string(),
            device: device.to_string(),
        });
        let mut state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        state.tensors.insert(handle.clone(), tensor);
        Ok(TensorHandleResult {
            tensor_handle: handle,
            owner: "host",
            shape,
            dtype: dtype.to_string(),
            device: device.to_string(),
        })
    }

    fn get_session_model(&self, session_handle: &str) -> Result<Arc<LoadedModel>, String> {
        let state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        let session = state
            .sessions
            .get(session_handle)
            .ok_or_else(|| format!("session not found: {session_handle}"))?;
        let _ = &session.model_id;
        state
            .models
            .get(&session.model_handle)
            .cloned()
            .ok_or_else(|| format!("model handle missing for session: {session_handle}"))
    }

    fn get_tensor(&self, tensor_handle: &str) -> Result<Arc<HostTensor>, String> {
        let state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        state
            .tensors
            .get(tensor_handle)
            .cloned()
            .ok_or_else(|| format!("tensor not found: {tensor_handle}"))
    }

    fn get_session_tokenizer(&self, session_handle: &str) -> Result<SimpleTokenizer, String> {
        let state = self.state.lock().map_err(|_| "registry poisoned".to_string())?;
        let session = state
            .sessions
            .get(session_handle)
            .ok_or_else(|| format!("session not found: {session_handle}"))?;
        state
            .tokenizers
            .get(&session.model_id)
            .cloned()
            .ok_or_else(|| format!("tokenizer missing for model: {}", session.model_id))
    }

    fn new_handle(&self, kind: &str) -> String {
        let id = self.next_id.fetch_add(1, Ordering::Relaxed);
        format!("{kind}:h:{id:016x}")
    }

    fn last_token_slice<'a>(&self, hidden: &'a [f32], hidden_size: usize) -> Option<&'a [f32]> {
        if hidden_size == 0 || hidden.len() < hidden_size {
            return None;
        }
        let start = hidden.len().saturating_sub(hidden_size);
        Some(&hidden[start..])
    }

    fn compute_logits(
        &self,
        last_hidden: &[f32],
        lm_head: &crate::model::Tensor,
        vocab_size: usize,
    ) -> Vec<f32> {
        let hidden_size = last_hidden.len();
        if vocab_size == 0 || hidden_size == 0 || lm_head.data.is_empty() {
            return vec![];
        }

        let shape = &lm_head.shape;
        if shape.len() >= 2 && shape[0] == vocab_size && shape[1] == hidden_size {
            let mut logits = vec![0.0f32; vocab_size];
            for (tok, logit) in logits.iter_mut().enumerate() {
                let row = &lm_head.data[tok * hidden_size..(tok + 1) * hidden_size];
                *logit = row
                    .iter()
                    .zip(last_hidden.iter())
                    .map(|(w, h)| w * h)
                    .sum();
            }
            logits
        } else if shape.len() >= 2 && shape[0] == hidden_size && shape[1] == vocab_size {
            let mut logits = vec![0.0f32; vocab_size];
            for (i, h) in last_hidden.iter().enumerate() {
                let row = &lm_head.data[i * vocab_size..(i + 1) * vocab_size];
                for (tok, logit) in logits.iter_mut().enumerate() {
                    *logit += row[tok] * h;
                }
            }
            logits
        } else {
            vec![]
        }
    }

    fn resolve_model_storage_path(&self, model_id: &str) -> Option<PathBuf> {
        if let Ok(state) = self.state.lock() {
            if let Some(path) = state.model_paths.get(model_id) {
                return Some(path.clone());
            }
        }
        loader::resolve_model_path(model_id)
    }

    fn resolve_model_object_ref(
        &self,
        model_id: &str,
    ) -> Result<(String, String, String, Option<String>, Vec<CatalogFile>), String> {
        if let Some(path) = loader::resolve_model_path(model_id) {
            return Ok((
                path.display().to_string(),
                "safetensors-dir".to_string(),
                "local".to_string(),
                None,
                Vec::new(),
            ));
        }

        if let Some(storage_key) = self.resolve_model_storage_override(model_id) {
            return Ok((
                storage_key,
                "safetensors-dir".to_string(),
                "remote".to_string(),
                None,
                Vec::new(),
            ));
        }

        let catalog = self.load_yata_catalog()?;
        let entry = catalog
            .get(model_id)
            .ok_or_else(|| format!("model not found in YATA catalog: {model_id}"))?;
        let storage_key = entry
            .storage_key
            .clone()
            .or_else(|| entry.path.clone())
            .or_else(|| entry.key.clone())
            .ok_or_else(|| format!("catalog entry missing key/path/storage_key for {model_id}"))?;
        Ok((
            storage_key,
            entry
                .format
                .clone()
                .unwrap_or_else(|| "safetensors-dir".to_string()),
            entry
                .locality
                .clone()
                .unwrap_or_else(|| "catalog".to_string()),
            entry.digest_blake3.clone(),
            if entry.files.is_empty() {
                entry.artifact_files.clone()
            } else {
                entry.files.clone()
            },
        ))
    }

    fn resolve_model_storage_override(&self, model_id: &str) -> Option<String> {
        let slug = self.model_slug(model_id);
        let exact_key = format!("KOTODAMA_MODEL_STORAGE_URL_{}", slug.to_ascii_uppercase());
        if let Ok(url) = std::env::var(&exact_key) {
            if !url.trim().is_empty() {
                return Some(url);
            }
        }
        if let Ok(template) = std::env::var("KOTODAMA_MODEL_STORAGE_URL_TEMPLATE") {
            if !template.trim().is_empty() {
                return Some(
                    template
                        .replace("{model_id}", model_id)
                        .replace("{model_slug}", &slug),
                );
            }
        }
        None
    }

    fn model_slug(&self, model_id: &str) -> String {
        model_id
            .chars()
            .map(|ch| match ch {
                '/' | '\\' | ':' | '.' => '-',
                _ => ch,
            })
            .collect()
    }

    fn load_yata_catalog(&self) -> Result<HashMap<String, CatalogEntry>, String> {
        if let Ok(path) = std::env::var("KOTODAMA_YATA_CATALOG_PATH") {
            let body = std::fs::read_to_string(&path)
                .map_err(|e| format!("read KOTODAMA_YATA_CATALOG_PATH {path}: {e}"))?;
            return self.parse_yata_catalog(&body);
        }

        let url = std::env::var("KOTODAMA_YATA_CATALOG_URL")
            .unwrap_or_else(|_| "https://atproto.etzhayyim.com/xrpc/com.etzhayyim.kagami.catalog".to_string());
        let response = ureq::get(&url)
            .call()
            .map_err(|e| format!("fetch YATA catalog {url}: {e}"))?;
        let body = response
            .into_string()
            .map_err(|e| format!("read YATA catalog response: {e}"))?;
        self.parse_yata_catalog(&body)
    }

    fn parse_yata_catalog(&self, body: &str) -> Result<HashMap<String, CatalogEntry>, String> {
        let value: serde_json::Value =
            serde_json::from_str(body).map_err(|e| format!("parse YATA catalog json: {e}"))?;
        let mut out = HashMap::new();
        let object = if let Some(models) = value.get("models").and_then(|v| v.as_object()) {
            models
        } else {
            value
                .as_object()
                .ok_or_else(|| "YATA catalog must be a JSON object".to_string())?
        };
        for (model_id, entry_value) in object {
            if let Ok(entry) = serde_json::from_value::<CatalogEntry>(entry_value.clone()) {
                out.insert(model_id.clone(), entry);
            }
        }
        if out.is_empty() {
            return Err("YATA catalog contained no usable model entries".to_string());
        }
        Ok(out)
    }

    fn materialize_storage_key(&self, storage_key: &str) -> Result<PathBuf, String> {
        if let Some(path) = storage_key.strip_prefix("file://") {
            return Ok(PathBuf::from(path));
        }
        let path = PathBuf::from(storage_key);
        if path.exists() {
            return Ok(path);
        }
        if let Ok(root) = std::env::var("KOTODAMA_YATA_OBJECT_ROOT") {
            let joined = Path::new(&root).join(storage_key);
            if joined.exists() {
                return Ok(joined);
            }
        }
        Err(format!(
            "storage key is not locally materialized: {storage_key}. Set KOTODAMA_YATA_OBJECT_ROOT or KOTODAMA_YATA_CATALOG_PATH"
        ))
    }

    fn materialize_object(&self, object: &ObjectRef) -> Result<PathBuf, String> {
        if let Ok(path) = self.materialize_storage_key(&object.storage_key) {
            return Ok(path);
        }

        let cache_root = self.object_cache_root()?;
        let target_dir = cache_root.join(self.sanitize_path_component(&object.model_id));
        std::fs::create_dir_all(&target_dir)
            .map_err(|e| format!("create object cache dir {}: {e}", target_dir.display()))?;

        let files = if object.files.is_empty() {
            self.discover_remote_files(object)?
        } else {
            object.files.clone()
        };

        for file in &files {
            let rel = file
                .path
                .clone()
                .or_else(|| file.key.clone())
                .or_else(|| file.storage_key.clone())
                .ok_or_else(|| {
                    format!(
                        "catalog file entry missing path/key/storage_key for {}",
                        object.model_id
                    )
                })?;
            let dest = target_dir.join(&rel);
            if dest.exists() {
                if let Some(expected) = &file.digest_blake3 {
                    self.verify_blake3(&dest, expected)?;
                }
                continue;
            }
            if let Some(parent) = dest.parent() {
                std::fs::create_dir_all(parent)
                    .map_err(|e| format!("create parent dir {}: {e}", parent.display()))?;
            }
            let url = self.resolve_file_url(&object.storage_key, file)?;
            self.download_file(&url, &dest)?;
            if let Some(expected) = &file.digest_blake3 {
                self.verify_blake3(&dest, expected)?;
            }
        }

        if let Some(expected) = &object.digest_blake3 {
            let marker = target_dir.join(".object.digest");
            std::fs::write(&marker, expected)
                .map_err(|e| format!("write digest marker {}: {e}", marker.display()))?;
        }
        Ok(target_dir)
    }

    fn discover_remote_files(&self, object: &ObjectRef) -> Result<Vec<CatalogFile>, String> {
        if let Ok(manifest) = self.fetch_known_json(&object.storage_key, "manifest.json") {
            let files = self.parse_manifest_files(&manifest);
            if !files.is_empty() {
                return Ok(files);
            }
        }

        let mut files = Vec::new();
        for required in ["config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"] {
            if self.remote_file_exists(&object.storage_key, required) {
                files.push(CatalogFile {
                    path: Some(required.to_string()),
                    key: None,
                    url: None,
                    storage_key: None,
                    digest_blake3: None,
                });
            }
        }

        if let Ok(index) = self.fetch_known_json(&object.storage_key, "model.safetensors.index.json") {
            if !files.iter().any(|f| f.path.as_deref() == Some("model.safetensors.index.json")) {
                files.push(CatalogFile {
                    path: Some("model.safetensors.index.json".to_string()),
                    key: None,
                    url: None,
                    storage_key: None,
                    digest_blake3: None,
                });
            }
            files.extend(self.parse_index_weight_map(&index));
        } else if self.remote_file_exists(&object.storage_key, "model.safetensors") {
            files.push(CatalogFile {
                path: Some("model.safetensors".to_string()),
                key: None,
                url: None,
                storage_key: None,
                digest_blake3: None,
            });
        }

        if !files.is_empty() {
            return Ok(files);
        }

        Err(format!(
            "remote object {} has no files[] and no discoverable manifest/index",
            object.model_id
        ))
    }

    fn object_cache_root(&self) -> Result<PathBuf, String> {
        if let Ok(root) = std::env::var("KOTODAMA_YATA_OBJECT_CACHE") {
            return Ok(PathBuf::from(root));
        }
        let home = std::env::var("HOME").map_err(|e| format!("HOME not set: {e}"))?;
        Ok(Path::new(&home)
            .join(".cache")
            .join("kotodama")
            .join("objects"))
    }

    fn sanitize_path_component(&self, value: &str) -> String {
        value
            .chars()
            .map(|ch| match ch {
                '/' | '\\' | ':' | '?' | '&' | '=' => '_',
                _ => ch,
            })
            .collect()
    }

    fn resolve_file_url(&self, storage_key: &str, file: &CatalogFile) -> Result<String, String> {
        if let Some(url) = &file.url {
            return Ok(url.clone());
        }
        let rel = file
            .path
            .as_deref()
            .or(file.key.as_deref())
            .or(file.storage_key.as_deref())
            .ok_or_else(|| "catalog file entry missing relative path".to_string())?;
        if storage_key.starts_with("http://") || storage_key.starts_with("https://") {
            let base = storage_key.trim_end_matches('/');
            return Ok(format!("{base}/{rel}"));
        }
        let base_url = std::env::var("KOTODAMA_YATA_OBJECT_BASE_URL").map_err(|_| {
            format!(
                "cannot resolve remote file URL for storage_key {} without KOTODAMA_YATA_OBJECT_BASE_URL",
                storage_key
            )
        })?;
        let base = base_url.trim_end_matches('/');
        let key = storage_key.trim_start_matches('/');
        Ok(format!("{base}/{key}/{rel}"))
    }

    fn fetch_known_json(&self, storage_key: &str, rel: &str) -> Result<serde_json::Value, String> {
        let url = self.resolve_file_url(
            storage_key,
            &CatalogFile {
                path: Some(rel.to_string()),
                key: None,
                url: None,
                storage_key: None,
                digest_blake3: None,
            },
        )?;
        let response = ureq::get(&url)
            .call()
            .map_err(|e| format!("download {url}: {e}"))?;
        let body = response
            .into_string()
            .map_err(|e| format!("read {url}: {e}"))?;
        serde_json::from_str(&body).map_err(|e| format!("parse {url}: {e}"))
    }

    fn remote_file_exists(&self, storage_key: &str, rel: &str) -> bool {
        let Ok(url) = self.resolve_file_url(
            storage_key,
            &CatalogFile {
                path: Some(rel.to_string()),
                key: None,
                url: None,
                storage_key: None,
                digest_blake3: None,
            },
        ) else {
            return false;
        };
        ureq::head(&url).call().is_ok()
    }

    fn parse_manifest_files(&self, manifest: &serde_json::Value) -> Vec<CatalogFile> {
        let mut out = Vec::new();
        if let Some(files) = manifest.get("files").and_then(|v| v.as_array()) {
            for file in files {
                if let Some(path) = file.as_str() {
                    out.push(CatalogFile {
                        path: Some(path.to_string()),
                        key: None,
                        url: None,
                        storage_key: None,
                        digest_blake3: None,
                    });
                    continue;
                }
                if let Ok(file) = serde_json::from_value::<CatalogFile>(file.clone()) {
                    out.push(file);
                }
            }
        }
        out
    }

    fn parse_index_weight_map(&self, index: &serde_json::Value) -> Vec<CatalogFile> {
        let mut seen = std::collections::BTreeSet::new();
        let mut out = Vec::new();
        if let Some(weight_map) = index.get("weight_map").and_then(|v| v.as_object()) {
            for shard in weight_map.values().filter_map(|v| v.as_str()) {
                if seen.insert(shard.to_string()) {
                    out.push(CatalogFile {
                        path: Some(shard.to_string()),
                        key: None,
                        url: None,
                        storage_key: None,
                        digest_blake3: None,
                    });
                }
            }
        }
        out
    }

    fn download_file(&self, url: &str, dest: &Path) -> Result<(), String> {
        let response = ureq::get(url)
            .call()
            .map_err(|e| format!("download {url}: {e}"))?;
        let mut reader = response.into_reader();
        let mut file =
            std::fs::File::create(dest).map_err(|e| format!("create {}: {e}", dest.display()))?;
        std::io::copy(&mut reader, &mut file)
            .map_err(|e| format!("write {} from {url}: {e}", dest.display()))?;
        Ok(())
    }

    fn verify_blake3(&self, path: &Path, expected: &str) -> Result<(), String> {
        let bytes = std::fs::read(path).map_err(|e| format!("read {}: {e}", path.display()))?;
        let actual = blake3::hash(&bytes).to_hex().to_string();
        if actual != expected {
            return Err(format!(
                "blake3 mismatch for {}: expected {}, got {}",
                path.display(),
                expected,
                actual
            ));
        }
        Ok(())
    }

    fn embed_prompt_tokens(&self, model: &LoadedModel, token_ids: &[u32]) -> Vec<f32> {
        let dim = model.config.hidden_size as usize;
        let seq_len = token_ids.len().max(1).min(128);
        let mut hidden = vec![0.0f32; seq_len * dim];
        if let Some(embed) = &model.embed_tokens {
            if embed.shape.len() >= 2 && embed.shape[1] == dim {
                let vocab_rows = embed.shape[0].max(1);
                for (row_idx, token_id) in token_ids.iter().take(seq_len).enumerate() {
                    let src_row = (*token_id as usize) % vocab_rows;
                    let src_start = src_row * dim;
                    let dst_start = row_idx * dim;
                    let src_end = src_start.saturating_add(dim).min(embed.data.len());
                    let copy_len = src_end.saturating_sub(src_start).min(dim);
                    hidden[dst_start..dst_start + copy_len]
                        .copy_from_slice(&embed.data[src_start..src_start + copy_len]);
                }
                return hidden;
            }
        }
        for (idx, value) in hidden.iter_mut().enumerate() {
            let token = token_ids[(idx / dim.max(1)) % token_ids.len().max(1)] as f32;
            *value = (token - 128.0) / 256.0;
        }
        hidden
    }
}
