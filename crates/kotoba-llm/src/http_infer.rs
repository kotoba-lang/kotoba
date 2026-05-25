/// OpenAI-compatible HTTP inference engine.
///
/// Works with any OpenAI-compatible endpoint: Ollama, vLLM, Vultr A16.
///
/// Environment variables:
///   KOTOBA_INFERENCE_URL   — base URL (e.g. http://localhost:11434 for Ollama)
///   KOTOBA_INFERENCE_MODEL — model name (default: gemma2:2b)
///
/// Wire format: POST /v1/chat/completions (OpenAI chat completions API).
///
/// Only compiled when the `http-inference` feature is enabled.
#[cfg(feature = "http-inference")]
mod inner {
    use anyhow::{anyhow, Result};

    /// Synchronous HTTP inference engine backed by reqwest + tokio block_in_place.
    #[derive(Clone)]
    pub struct HttpInferEngine {
        base_url: String,
        model: String,
        client: reqwest::Client,
    }

    impl HttpInferEngine {
        /// Construct from environment variables.
        ///
        /// Requires `KOTOBA_INFERENCE_URL`.
        /// `KOTOBA_INFERENCE_MODEL` defaults to `"gemma4:e4b"`.
        pub fn from_env() -> Result<Self> {
            let base_url = std::env::var("KOTOBA_INFERENCE_URL")
                .map_err(|_| anyhow!("KOTOBA_INFERENCE_URL not set"))?;
            let model = std::env::var("KOTOBA_INFERENCE_MODEL")
                .unwrap_or_else(|_| "gemma4:e4b".to_string());
            let client = reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(120))
                .build()?;
            Ok(Self {
                base_url: base_url.trim_end_matches('/').to_string(),
                model,
                client,
            })
        }

        /// Synchronous generate — blocks the current tokio worker thread.
        ///
        /// Safe to call from `Arc<dyn Fn>` InferenceFn closures that run inside
        /// a `tokio::task::spawn_blocking` or a multi-threaded runtime.
        pub fn generate(&self, prompt: &str, max_tokens: usize) -> Result<String> {
            let engine = self.clone();
            let prompt = prompt.to_string();
            tokio::task::block_in_place(|| {
                tokio::runtime::Handle::current()
                    .block_on(engine.generate_async(&prompt, max_tokens))
            })
        }

        async fn generate_async(&self, prompt: &str, max_tokens: usize) -> Result<String> {
            let url = format!("{}/v1/chat/completions", self.base_url);
            let body = serde_json::json!({
                "model": self.model,
                "messages": [{ "role": "user", "content": prompt }],
                "max_tokens": max_tokens,
                "stream": false,
            });
            let resp = self
                .client
                .post(&url)
                .header("Content-Type", "application/json")
                .json(&body)
                .send()
                .await?
                .error_for_status()?;

            let json: serde_json::Value = resp.json().await?;
            let text = json["choices"][0]["message"]["content"]
                .as_str()
                .ok_or_else(|| anyhow!("missing choices[0].message.content in response"))?
                .to_string();
            Ok(text)
        }
    }
}

#[cfg(feature = "http-inference")]
pub use inner::HttpInferEngine;
