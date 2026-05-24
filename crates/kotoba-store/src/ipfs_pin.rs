/// IPFS Pinning Service API v1 client (https://ipfs.github.io/pinning-services-api-spec/)
///
/// No Kubo/daemon dependency — pure HTTP to Pinata / web3.storage / Filebase / etc.
///
/// Env vars (read at construction):
///   KOTOBA_IPFS_PIN_ENDPOINT  — e.g. https://api.pinata.cloud/psa
///   KOTOBA_IPFS_PIN_JWT       — Bearer token
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Clone)]
pub struct IpfsPinClient {
    client:   reqwest::Client,
    endpoint: String,
    jwt:      String,
}

#[derive(Debug, Serialize)]
struct PinRequest<'a> {
    cid:  &'a str,
    name: Option<&'a str>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct PinResponse {
    requestid: String,
    status:    String,
    cid:       Option<String>,
}

impl IpfsPinClient {
    /// Build from env vars. Returns `None` if vars are absent.
    pub fn from_env() -> Option<Arc<Self>> {
        let endpoint = std::env::var("KOTOBA_IPFS_PIN_ENDPOINT").ok()?;
        let jwt      = std::env::var("KOTOBA_IPFS_PIN_JWT").ok()?;
        let client   = reqwest::Client::new();
        Some(Arc::new(Self { client, endpoint, jwt }))
    }

    /// Fire-and-forget CID pin. Errors are logged, not propagated.
    /// Call with `tokio::spawn` to avoid blocking the caller.
    pub async fn pin(&self, cid: &str) {
        let url  = format!("{}/pins", self.endpoint.trim_end_matches('/'));
        let body = PinRequest { cid, name: Some(cid) };

        match self.client
            .post(&url)
            .bearer_auth(&self.jwt)
            .json(&body)
            .send()
            .await
        {
            Err(e) => tracing::warn!(cid, err = %e, "IPFS pin request failed"),
            Ok(resp) if !resp.status().is_success() => {
                let status = resp.status();
                let text   = resp.text().await.unwrap_or_default();
                tracing::warn!(cid, %status, body = %text, "IPFS pin rejected");
            }
            Ok(_) => tracing::debug!(cid, "IPFS pin queued"),
        }
    }

    /// Check pin status. Returns `"pinned"`, `"queued"`, `"failed"`, or error text.
    pub async fn status(&self, cid: &str) -> String {
        let url = format!(
            "{}/pins?cid={cid}",
            self.endpoint.trim_end_matches('/')
        );
        match self.client
            .get(&url)
            .bearer_auth(&self.jwt)
            .send()
            .await
        {
            Err(e) => format!("request error: {e}"),
            Ok(r) if !r.status().is_success() => format!("http {}", r.status()),
            Ok(r) => {
                #[derive(Deserialize)] struct List { results: Vec<PinResponse> }
                match r.json::<List>().await {
                    Err(e) => format!("parse error: {e}"),
                    Ok(l) => l.results
                        .into_iter()
                        .next()
                        .map(|p| p.status)
                        .unwrap_or_else(|| "not_found".into()),
                }
            }
        }
    }
}
