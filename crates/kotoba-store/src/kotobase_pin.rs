/// kotobase.gftd.ai XRPC pin client.
///
/// Calls `ai.gftd.apps.kotobase.pin.create` to register a CID for remote
/// IPFS pinning.  kotobase is responsible for B2 persistence and IPFS
/// replication; kotoba is responsible for local block assembly.
///
/// Env vars:
///   KOTOBA_PIN_ENDPOINT  — base URL (default: https://kotobase.gftd.ai)
///   KOTOBA_PIN_TOKEN     — Bearer JWT issued by kotobase (`account.create`)
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Clone)]
pub struct KotobasePinClient {
    client:   reqwest::Client,
    endpoint: String,
    token:    String,
}

#[derive(Debug, Serialize)]
struct PinCreateInput<'a> {
    cid:  &'a str,
    name: Option<&'a str>,
}

#[derive(Debug, Deserialize)]
#[allow(dead_code)]
struct PinCreateOutput {
    cid:    String,
    status: String,
}

#[derive(Debug, Serialize)]
struct PinDeleteInput<'a> {
    cid: &'a str,
}

impl KotobasePinClient {
    pub fn from_env() -> Option<Arc<Self>> {
        let endpoint = std::env::var("KOTOBA_PIN_ENDPOINT")
            .unwrap_or_else(|_| "https://kotobase.gftd.ai".into());
        let token = std::env::var("KOTOBA_PIN_TOKEN").ok()?;
        Some(Arc::new(Self {
            client: reqwest::Client::new(),
            endpoint,
            token,
        }))
    }

    fn xrpc_url(&self, nsid: &str) -> String {
        format!("{}/xrpc/{nsid}", self.endpoint.trim_end_matches('/'))
    }

    /// Fire-and-forget CID pin via `ai.gftd.apps.kotobase.pin.create`.
    /// Errors are logged, not propagated — call via `tokio::spawn`.
    pub async fn pin(&self, cid: &str) {
        let url  = self.xrpc_url("ai.gftd.apps.kotobase.pin.create");
        let body = PinCreateInput { cid, name: Some(cid) };

        match self.client
            .post(&url)
            .bearer_auth(&self.token)
            .json(&body)
            .send()
            .await
        {
            Err(e) => tracing::warn!(cid, err = %e, "kotobase pin.create request failed"),
            Ok(resp) if !resp.status().is_success() => {
                let status = resp.status();
                let text   = resp.text().await.unwrap_or_default();
                tracing::warn!(cid, %status, body = %text, "kotobase pin.create rejected");
            }
            Ok(_) => tracing::debug!(cid, "kotobase pin queued"),
        }
    }

    /// Query pin status via `ai.gftd.apps.kotobase.pin.list`.
    /// Returns `"pinned"`, `"queued"`, `"failed"`, `"not_found"`, or an error description.
    pub async fn status(&self, cid: &str) -> String {
        let url = format!("{}?cid={cid}", self.xrpc_url("ai.gftd.apps.kotobase.pin.list"));

        match self.client
            .get(&url)
            .bearer_auth(&self.token)
            .send()
            .await
        {
            Err(e) => format!("request error: {e}"),
            Ok(r) if !r.status().is_success() => format!("http {}", r.status()),
            Ok(r) => {
                #[derive(Deserialize)]
                struct ListOutput { pins: Vec<PinCreateOutput> }
                match r.json::<ListOutput>().await {
                    Err(e) => format!("parse error: {e}"),
                    Ok(l)  => l.pins.into_iter()
                        .next()
                        .map(|p| p.status)
                        .unwrap_or_else(|| "not_found".into()),
                }
            }
        }
    }

    /// Unpin a CID via `ai.gftd.apps.kotobase.pin.delete`.
    pub async fn unpin(&self, cid: &str) {
        let url  = self.xrpc_url("ai.gftd.apps.kotobase.pin.delete");
        let body = PinDeleteInput { cid };

        match self.client
            .post(&url)
            .bearer_auth(&self.token)
            .json(&body)
            .send()
            .await
        {
            Err(e) => tracing::warn!(cid, err = %e, "kotobase pin.delete request failed"),
            Ok(resp) if !resp.status().is_success() => {
                let status = resp.status();
                let text   = resp.text().await.unwrap_or_default();
                tracing::warn!(cid, %status, body = %text, "kotobase pin.delete rejected");
            }
            Ok(_) => tracing::debug!(cid, "kotobase cid unpinned"),
        }
    }
}
