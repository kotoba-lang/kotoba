/// IPFS pin client — Kubo-compatible HTTP RPC API.
///
/// kotoba IS an IPFS node.  This client delegates persistent pinning to
/// a local or remote Kubo-compatible daemon so that pinned CIDs survive GC
/// and are reachable via the IPFS network.  Up to 1 GB of content is pinned
/// for free by kotoba itself; extended durability beyond that is the
/// responsibility of the canonical remote pin service kotobase.net
/// (ADR-2606091500; called separately, not here).
///
/// API surface used:
///   POST /api/v0/pin/add?arg={cid}&recursive=true   — pin a CID
///   POST /api/v0/pin/rm?arg={cid}                   — unpin a CID
///   GET  /api/v0/pin/ls?type=all&arg={cid}           — check pin status
///
/// Env vars:
///   KOTOBA_IPFS_ENDPOINT  — base URL (default: http://localhost:5001)
///   KOTOBA_IPFS_TOKEN     — optional Bearer JWT for authenticated gateways
use serde::Deserialize;
use std::{collections::HashMap, sync::Arc};

/// Canonical remote IPFS pin service (ADR-2606091500). `from_pin_env` defaults
/// to this when `KOTOBA_IPFS_PIN_ENDPOINT` is unset, so the kotobase pin fanout
/// is on by default repo-wide; opt out with `KOTOBA_IPFS_PIN_ENDPOINT=off`.
pub const DEFAULT_REMOTE_PIN_ENDPOINT: &str = "https://kotobase.net";

#[derive(Clone)]
pub struct IpfsPinClient {
    client: reqwest::Client,
    endpoint: String,
    token: Option<String>,
}

#[derive(Debug, Deserialize)]
struct PinAddResponse {
    #[serde(rename = "Pins")]
    pins: Vec<String>,
}

#[derive(Debug, Deserialize)]
struct PinLsResponse {
    #[serde(rename = "Keys")]
    keys: HashMap<String, PinEntry>,
}

#[derive(Debug, Deserialize)]
struct PinEntry {
    #[serde(rename = "Type")]
    pin_type: String,
}

impl IpfsPinClient {
    pub fn from_env() -> Arc<Self> {
        let endpoint = std::env::var("KOTOBA_IPFS_ENDPOINT")
            .unwrap_or_else(|_| "http://localhost:5001".into());
        let token = std::env::var("KOTOBA_IPFS_TOKEN").ok();
        Arc::new(Self {
            client: reqwest::Client::new(),
            endpoint,
            token,
        })
    }

    /// Build the canonical remote pin client (ADR-2606091500).  Defaults to
    /// `kotobase.net` (`DEFAULT_REMOTE_PIN_ENDPOINT`) so the kotobase pin fanout
    /// is **on by default** repo-wide — every recursive pin is dispatched to
    /// kotobase.net in addition to the pod-local sidecar (the F-3 pin chain).
    /// Overridable via `KOTOBA_IPFS_PIN_ENDPOINT`; explicitly opt out (e.g. local
    /// dev / tests) by setting it to `off` / `none` / `disabled`, which returns
    /// `None` so the caller does a local-only pin.  `KOTOBA_IPFS_PIN_JWT` is the
    /// optional Bearer token for the remote service.
    pub fn from_pin_env() -> Option<Arc<Self>> {
        let raw = std::env::var("KOTOBA_IPFS_PIN_ENDPOINT").unwrap_or_default();
        let trimmed = raw.trim();
        if matches!(
            trimmed.to_ascii_lowercase().as_str(),
            "off" | "none" | "disabled" | "0" | "false"
        ) {
            return None;
        }
        let endpoint = if trimmed.is_empty() {
            DEFAULT_REMOTE_PIN_ENDPOINT.to_string()
        } else {
            trimmed.to_string()
        };
        let token = std::env::var("KOTOBA_IPFS_PIN_JWT").ok();
        Some(Arc::new(Self {
            client: reqwest::Client::new(),
            endpoint,
            token,
        }))
    }

    fn api_url(&self, method: &str) -> String {
        format!("{}/api/v0/{method}", self.endpoint.trim_end_matches('/'))
    }

    fn authed(&self, rb: reqwest::RequestBuilder) -> reqwest::RequestBuilder {
        match &self.token {
            Some(t) => rb.bearer_auth(t),
            None => rb,
        }
    }

    /// Pin a CID recursively (fire-and-forget; call via `tokio::spawn`).
    pub async fn pin(&self, cid: &str) {
        let url = format!("{}?arg={cid}&recursive=true", self.api_url("pin/add"));
        let rb = self.authed(self.client.post(&url));

        match rb.send().await {
            Err(e) => tracing::warn!(cid, err = %e, "ipfs pin/add request failed"),
            Ok(resp) if !resp.status().is_success() => {
                let status = resp.status();
                let text = resp.text().await.unwrap_or_default();
                tracing::warn!(cid, %status, body = %text, "ipfs pin/add rejected");
            }
            Ok(resp) => match resp.json::<PinAddResponse>().await {
                Ok(r) => tracing::debug!(cid, pins = ?r.pins, "ipfs cid pinned"),
                Err(e) => tracing::warn!(cid, err = %e, "ipfs pin/add response parse failed"),
            },
        }
    }

    /// Unpin a CID (fire-and-forget; call via `tokio::spawn`).
    pub async fn unpin(&self, cid: &str) {
        let url = format!("{}?arg={cid}", self.api_url("pin/rm"));
        let rb = self.authed(self.client.post(&url));

        match rb.send().await {
            Err(e) => tracing::warn!(cid, err = %e, "ipfs pin/rm request failed"),
            Ok(resp) if !resp.status().is_success() => {
                let status = resp.status();
                let text = resp.text().await.unwrap_or_default();
                // "not pinned" is not an error
                if text.contains("not pinned") {
                    tracing::debug!(cid, "ipfs cid was not pinned, skipping unpin");
                } else {
                    tracing::warn!(cid, %status, body = %text, "ipfs pin/rm rejected");
                }
            }
            Ok(_) => tracing::debug!(cid, "ipfs cid unpinned"),
        }
    }

    /// Query pin status. Returns `"recursive"`, `"direct"`, `"indirect"`,
    /// `"not_found"`, or an error description.
    pub async fn status(&self, cid: &str) -> String {
        let url = format!("{}?type=all&arg={cid}", self.api_url("pin/ls"));
        let rb = self.authed(self.client.get(&url));

        match rb.send().await {
            Err(e) => format!("request error: {e}"),
            Ok(r) if !r.status().is_success() => {
                let text = r.text().await.unwrap_or_default();
                if text.contains("not pinned") {
                    "not_found".into()
                } else {
                    format!("http error: {text}")
                }
            }
            Ok(r) => match r.json::<PinLsResponse>().await {
                Err(e) => format!("parse error: {e}"),
                Ok(ls) => ls
                    .keys
                    .get(cid)
                    .map(|e| e.pin_type.clone())
                    .unwrap_or_else(|| "not_found".into()),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn client(endpoint: &str) -> IpfsPinClient {
        IpfsPinClient {
            client: reqwest::Client::new(),
            endpoint: endpoint.into(),
            token: None,
        }
    }

    #[test]
    fn api_url_normalizes_trailing_slash() {
        // The endpoint may or may not carry a trailing slash (env var, config).
        // `api_url` must produce exactly one separator either way — a double slash
        // (`//api/v0`) is rejected by some Kubo gateways and would break every pin.
        assert_eq!(
            client("http://localhost:5001").api_url("pin/add"),
            "http://localhost:5001/api/v0/pin/add"
        );
        assert_eq!(
            client("http://localhost:5001/").api_url("pin/add"),
            "http://localhost:5001/api/v0/pin/add",
            "trailing slash must be normalized, not doubled"
        );
        assert_eq!(
            client("http://h/").api_url("pin/ls"),
            "http://h/api/v0/pin/ls"
        );
        // Multiple trailing slashes are all trimmed.
        assert_eq!(
            client("http://h///").api_url("pin/rm"),
            "http://h/api/v0/pin/rm"
        );
    }
}
