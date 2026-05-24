/// Gemma local inference runner via candle-transformers.
///
/// Uses `candle_transformers::models::gemma2` — the Gemma 2 module which covers
/// the same GQA + RoPE + SwiGLU architecture family as Gemma 3/4.
/// `gemma3` is not present in candle-transformers 0.8; the next available family
/// member is `gemma2`.
///
/// Only compiled when the `local-inference` feature is enabled:
///   cargo build -p kotoba-llm --features local-inference
#[cfg(feature = "local-inference")]
mod inner {
    use anyhow::Result;
    use candle_core::{DType, Device, Tensor};
    use candle_nn::VarBuilder;
    use candle_transformers::generation::LogitsProcessor;
    use candle_transformers::models::gemma2::{Config as GemmaConfig, Model as GemmaModel};
    use hf_hub::api::tokio::Api;
    use hf_hub::{Repo, RepoType};
    use std::collections::HashSet;
    use std::path::PathBuf;
    use tokenizers::Tokenizer;

    /// HuggingFace repo for the target model.
    /// NOTE: `google/gemma-4-E2B` may not yet be published; the load() call will
    /// return an hf-hub error at runtime if the repo does not exist.  The error is
    /// propagated as `anyhow::Error` — callers should handle it gracefully.
    pub const GEMMA_E2B_REPO: &str = "google/gemma-4-E2B";


    /// A loaded Gemma model + tokenizer, ready for synchronous generate() calls.
    ///
    /// Wrap in `Arc<std::sync::Mutex<GemmaRunner>>` when sharing across threads:
    ///   `Arc<std::sync::Mutex<GemmaRunner>>`
    pub struct GemmaRunner {
        pub model: GemmaModel,
        pub tokenizer: Tokenizer,
        pub device: Device,
    }

    impl GemmaRunner {
        /// Download (or load from cache) the model from HuggingFace and initialise.
        /// CPU-only; no GPU required.
        pub async fn load() -> Result<Self> {
            let device = Device::Cpu;

            let api = Api::new()?;
            let repo = api.repo(Repo::new(GEMMA_E2B_REPO.to_string(), RepoType::Model));

            // Download config + tokenizer
            let config_path = repo.get("config.json").await?;
            let tokenizer_path = repo.get("tokenizer.json").await?;

            // Try a single-shard safetensors file first; fall back to index-based shards.
            let model_paths: Vec<PathBuf> =
                if let Ok(p) = repo.get("model.safetensors").await {
                    vec![p]
                } else {
                    let index_path = repo.get("model.safetensors.index.json").await?;
                    let index_text = std::fs::read_to_string(&index_path)?;
                    let index: serde_json::Value = serde_json::from_str(&index_text)?;
                    let mut files: HashSet<String> = HashSet::new();
                    if let Some(weight_map) =
                        index.get("weight_map").and_then(|v| v.as_object())
                    {
                        for v in weight_map.values() {
                            if let Some(s) = v.as_str() {
                                files.insert(s.to_string());
                            }
                        }
                    }
                    let mut paths = Vec::new();
                    for f in files {
                        paths.push(repo.get(&f).await?);
                    }
                    paths.sort(); // deterministic order
                    paths
                };

            let config: GemmaConfig =
                serde_json::from_str(&std::fs::read_to_string(&config_path)?)?;
            let tokenizer = Tokenizer::from_file(&tokenizer_path)
                .map_err(|e| anyhow::anyhow!("tokenizer load error: {e}"))?;

            // Safety: mmap is read-only; all data is already on disk before this call.
            let vb = unsafe {
                VarBuilder::from_mmaped_safetensors(&model_paths, DType::F32, &device)?
            };

            let model = GemmaModel::new(/* use_flash_attn */ false, &config, vb)?;

            Ok(Self { model, tokenizer, device })
        }

        /// Run text generation synchronously.
        ///
        /// `prompt`          — UTF-8 input text
        /// `max_new_tokens`  — maximum tokens to generate (capped, never 0)
        ///
        /// Returns the generated text (not including the prompt).
        pub fn generate(&mut self, prompt: &str, max_new_tokens: usize) -> Result<String> {
            let max_new_tokens = max_new_tokens.max(1);

            // Encode the prompt
            let encoding = self
                .tokenizer
                .encode(prompt, true)
                .map_err(|e| anyhow::anyhow!("tokenizer encode error: {e}"))?;
            let prompt_ids: Vec<u32> = encoding.get_ids().to_vec();
            let _prompt_len = prompt_ids.len();

            let mut tokens = prompt_ids;

            // Identify EOS token id
            let eos_token = self
                .tokenizer
                .token_to_id("<eos>")
                .or_else(|| self.tokenizer.token_to_id("</s>"))
                .or_else(|| self.tokenizer.token_to_id("<end_of_turn>"))
                .unwrap_or(1);

            // temperature=0.7, top_p=0.9
            let mut logits_processor = LogitsProcessor::new(42, Some(0.7), Some(0.9));

            let mut generated: Vec<u32> = Vec::new();

            // Clear any leftover KV cache from a previous call
            self.model.clear_kv_cache();

            for idx in 0..max_new_tokens {
                // For the first step feed the full prompt; afterwards feed one token.
                let (input_slice, seqlen_offset) = if idx == 0 {
                    (tokens.as_slice(), 0usize)
                } else {
                    let last = &tokens[tokens.len() - 1..];
                    (last, tokens.len() - 1)
                };

                let input =
                    Tensor::new(input_slice, &self.device)?.unsqueeze(0)?;
                let logits = self.model.forward(&input, seqlen_offset)?;

                // logits shape: [1, seq_len, vocab] — take the last position
                let logits = logits.squeeze(0)?; // [seq_len, vocab]
                let seq_len = logits.dim(0)?;
                let last_logits = logits.get(seq_len - 1)?; // [vocab]

                let next_token = logits_processor.sample(&last_logits)?;

                if next_token == eos_token {
                    break;
                }

                tokens.push(next_token);
                generated.push(next_token);
            }

            let text = self
                .tokenizer
                .decode(&generated, /* skip_special_tokens */ true)
                .map_err(|e| anyhow::anyhow!("tokenizer decode error: {e}"))?;
            Ok(text)
        }
    }
}

#[cfg(feature = "local-inference")]
pub use inner::{GemmaRunner, GEMMA_E2B_REPO};
