use anyhow::{anyhow, Result};
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use reqwest::Url;
use serde::Deserialize;
/// KuboBlockStore — IPFS cold block store backed by a Kubo HTTP node.
///
/// Uses KotobaCid (sha2-256 CIDv1 dag-cbor) directly as the IPFS block CID.
/// No secondary index or CID translation is needed: the same IPFS CID that
/// kotoba uses internally is stored verbatim in Kubo.  Any node that holds a
/// KotobaCid multibase string can retrieve the block from the IPFS network via
/// Kubo's bitswap/DHT without any additional mapping.
///
/// Kubo HTTP API used:
///   POST /api/v0/block/put?cid-codec=dag-cbor&mhtype=sha2-256 — store raw bytes
///   POST /api/v0/block/get?arg={cid}                          — retrieve raw bytes
///   POST /api/v0/block/rm?arg={cid}&force=true                — delete
///
/// Env vars:
///   KOTOBA_IPFS_ENDPOINT  — base URL (default: http://localhost:5001)
///   KOTOBA_IPFS_TOKEN     — optional Bearer JWT
use std::collections::HashSet;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, RwLock};
use std::time::{Duration, SystemTime, UNIX_EPOCH};

const DEFAULT_KUBO_ENDPOINT: &str = "http://localhost:5001";
const DISABLED_KUBO_ENDPOINT: &str = "http://127.0.0.1:9";
const MAX_KUBO_ENDPOINT_LEN: usize = 256;
const KUBO_CONNECT_TIMEOUT: Duration = Duration::from_secs(5);
const KUBO_REQUEST_TIMEOUT: Duration = Duration::from_secs(30);
const KUBO_POOL_IDLE_TIMEOUT: Duration = Duration::from_secs(30);
const KUBO_POOL_MAX_IDLE_PER_HOST: usize = 8;
/// After a connect failure, wait this long before letting the next op
/// re-probe Kubo. Avoids a permanently-stuck `available=false` state where
/// every block silently drops while Kubo has already recovered.
const KUBO_FAILURE_COOLDOWN_SECS: u64 = 5;
/// Maximum simultaneous in-flight HTTP requests against the local Kubo node.
/// `pool_max_idle_per_host` only caps keep-alive reuse — without an explicit
/// concurrency limit each ProllyTree builder thread can fire hundreds of
/// parallel puts, saturating Kubo's connection handler (observed 256+
/// ESTABLISHED + 318 CLOSE_WAIT on commit bursts).  16 lets a 4-tree commit
/// keep 4 puts per tree in flight while leaving headroom for reads.
const KUBO_MAX_INFLIGHT: usize = 16;

#[derive(Deserialize)]
struct BlockPutResponse {
    #[serde(rename = "Key")]
    key: String,
}

pub struct KuboBlockStore {
    client: reqwest::Client,
    endpoint: String,
    token: Option<String>,
    pinned: Arc<RwLock<HashSet<[u8; 36]>>>,
    /// Unix-seconds timestamp of the most recent connect failure.
    /// `is_available()` returns false only while we're within
    /// `KUBO_FAILURE_COOLDOWN_SECS` of that timestamp.  This lets a stuck
    /// store recover automatically: when Kubo comes back, the next op after
    /// the cooldown probes it and resumes normal operation.  `0` means
    /// "never failed".
    failed_at_unix: Arc<AtomicU64>,
    /// Concurrency cap for in-flight requests to Kubo.  Each put/get acquires
    /// a permit before touching the socket; the rest of the burst queues here
    /// instead of opening fresh connections.
    inflight: Arc<tokio::sync::Semaphore>,
    /// Optional remote pin client (kotobase.gftd.ai).  When set, every
    /// successful local `pin/add` is fanned out asynchronously to the remote
    /// endpoint so commit roots / vault keys / IPNS records replicate beyond
    /// the pod-local PVC.  Mirrors the F-3 "kotoba IPFS only / kotobase pins
    /// for durability" architecture.
    remote_pin: Option<Arc<crate::ipfs_pin::IpfsPinClient>>,
}

impl KuboBlockStore {
    pub fn new(endpoint: impl Into<String>) -> Self {
        let endpoint = normalize_kubo_endpoint(&endpoint.into()).unwrap_or_else(|| {
            tracing::warn!("invalid Kubo endpoint; disabling KuboBlockStore HTTP access");
            DISABLED_KUBO_ENDPOINT.to_string()
        });
        // 5 s connect timeout absorbs sidecar startup race; pool reuse + capped
        // idle keep the Kubo handler from leaking CLOSE_WAIT under burst commits
        // (observed 318 CLOSE_WAIT + 287 FIN_WAIT2 on Kubo 0.34.1 with the prior
        // 500 ms / unbounded pool config).
        let client = kubo_http_client();
        Self {
            client,
            endpoint,
            token: None,
            pinned: Arc::new(RwLock::new(HashSet::new())),
            failed_at_unix: Arc::new(AtomicU64::new(0)),
            inflight: Arc::new(tokio::sync::Semaphore::new(KUBO_MAX_INFLIGHT)),
            remote_pin: None,
        }
    }

    /// Probe the Kubo daemon's `/api/v0/version` endpoint.
    ///
    /// Returns `Ok((version, commit))` on a 200 response so operators can log
    /// the running daemon version at startup.  Falls back to `Err` if the
    /// daemon is unreachable, returns a non-2xx, or the JSON is malformed.
    pub async fn probe_version(&self) -> anyhow::Result<(String, String)> {
        let url = format!("{}/api/v0/version", self.endpoint.trim_end_matches('/'));
        let mut req = self.client.post(&url);
        if let Some(t) = &self.token {
            req = req.bearer_auth(t);
        }
        let resp = req
            .send()
            .await
            .map_err(|e| anyhow::anyhow!("connect: {e}"))?;
        if !resp.status().is_success() {
            anyhow::bail!("HTTP {}", resp.status());
        }
        // Extract just Version/Commit fields from the JSON body without pulling
        // serde_json into the crate's deps — we only need two string lookups.
        let body = resp
            .text()
            .await
            .map_err(|e| anyhow::anyhow!("read: {e}"))?;
        let version = extract_json_string_field(&body, "Version").unwrap_or_default();
        let commit = extract_json_string_field(&body, "Commit").unwrap_or_default();
        Ok((version, commit))
    }

    pub fn from_env() -> Self {
        let endpoint =
            std::env::var("KOTOBA_IPFS_ENDPOINT").unwrap_or_else(|_| DEFAULT_KUBO_ENDPOINT.into());
        let endpoint = normalize_kubo_endpoint(&endpoint).unwrap_or_else(|| {
            tracing::warn!("invalid KOTOBA_IPFS_ENDPOINT; disabling KuboBlockStore HTTP access");
            DISABLED_KUBO_ENDPOINT.to_string()
        });
        let token = std::env::var("KOTOBA_IPFS_TOKEN").ok();
        let client = kubo_http_client();
        Self {
            client,
            endpoint,
            token,
            pinned: Arc::new(RwLock::new(HashSet::new())),
            failed_at_unix: Arc::new(AtomicU64::new(0)),
            inflight: Arc::new(tokio::sync::Semaphore::new(KUBO_MAX_INFLIGHT)),
            remote_pin: None,
        }
    }

    fn api_url(&self, method: &str) -> String {
        format!("{}/api/v0/{method}", self.endpoint.trim_end_matches('/'))
    }

    fn mark_unavailable(&self) {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        self.failed_at_unix.store(now, Ordering::Relaxed);
    }
    fn mark_available(&self) {
        self.failed_at_unix.store(0, Ordering::Relaxed);
    }
    pub fn is_available(&self) -> bool {
        let failed_at = self.failed_at_unix.load(Ordering::Relaxed);
        if failed_at == 0 {
            return true;
        }
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        now.saturating_sub(failed_at) >= KUBO_FAILURE_COOLDOWN_SECS
    }
}

fn kubo_http_client() -> reqwest::Client {
    reqwest::Client::builder()
        .connect_timeout(KUBO_CONNECT_TIMEOUT)
        .timeout(KUBO_REQUEST_TIMEOUT)
        .pool_idle_timeout(KUBO_POOL_IDLE_TIMEOUT)
        .pool_max_idle_per_host(KUBO_POOL_MAX_IDLE_PER_HOST)
        .build()
        .unwrap_or_default()
}

fn normalize_kubo_endpoint(endpoint: &str) -> Option<String> {
    let endpoint = endpoint.trim();
    if endpoint.is_empty()
        || endpoint.len() > MAX_KUBO_ENDPOINT_LEN
        || endpoint.chars().any(|ch| ch.is_control())
    {
        return None;
    }
    let url = Url::parse(endpoint).ok()?;
    if !matches!(url.scheme(), "http" | "https") {
        return None;
    }
    if url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.path() != "/"
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return None;
    }
    Some(url.as_str().trim_end_matches('/').to_string())
}

/// Dedicated multi-thread runtime that drives Kubo HTTP I/O for the synchronous
/// `BlockStore` trait. Keeping I/O off the *caller's* runtime is what prevents
/// the deadlock: the previous `block_in_place(|| Handle::current().block_on(..))`
/// drove the HTTP future on the SAME runtime whose worker the call was blocking,
/// so under concurrency (a commit's background put-storm + concurrent reads) all
/// workers ended up parked inside `block_on`, starving the very runtime that had
/// to make the futures progress → the server wedged (observed at c≈8–16).
fn kubo_runtime() -> &'static tokio::runtime::Runtime {
    static RT: std::sync::OnceLock<tokio::runtime::Runtime> = std::sync::OnceLock::new();
    RT.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .worker_threads(4)
            .enable_all()
            .thread_name("kubo-io")
            .build()
            .expect("build kubo-io runtime")
    })
}

/// Drive a Kubo HTTP future to completion from a synchronous `BlockStore`
/// method without starving the caller's runtime.
///
/// - Inside a Tokio runtime: spawn the future onto the dedicated `kubo-io`
///   runtime (its own threads run the I/O) and block the current worker on a
///   std channel via `block_in_place`, so the caller's runtime spins up a
///   replacement worker and keeps making progress. No nested `block_on`, so no
///   "runtime within a runtime" panic and no pool starvation.
/// - Outside any runtime (e.g. sync unit tests): block directly on the
///   dedicated runtime.
fn kubo_block_on<F>(fut: F) -> F::Output
where
    F: std::future::Future + Send + 'static,
    F::Output: Send + 'static,
{
    let rt = kubo_runtime();
    match tokio::runtime::Handle::try_current() {
        Ok(handle) => {
            let (tx, rx) = std::sync::mpsc::sync_channel(1);
            rt.spawn(async move {
                let _ = tx.send(fut.await);
            });
            if matches!(
                handle.runtime_flavor(),
                tokio::runtime::RuntimeFlavor::MultiThread
            ) {
                tokio::task::block_in_place(|| rx.recv())
                    .expect("kubo-io runtime dropped the in-flight result")
            } else {
                rx.recv()
                    .expect("kubo-io runtime dropped the in-flight result")
            }
        }
        Err(_) => rt.block_on(fut),
    }
}

impl Clone for KuboBlockStore {
    fn clone(&self) -> Self {
        Self {
            client: self.client.clone(),
            endpoint: self.endpoint.clone(),
            token: self.token.clone(),
            pinned: Arc::clone(&self.pinned),
            failed_at_unix: Arc::clone(&self.failed_at_unix),
            inflight: Arc::clone(&self.inflight),
            remote_pin: self.remote_pin.clone(),
        }
    }
}

impl KuboBlockStore {
    /// Attach a remote pin client (kotobase.gftd.ai) so every successful
    /// local `pin/add` is also fanned out to the remote endpoint.
    pub fn with_remote_pin(mut self, remote: Arc<crate::ipfs_pin::IpfsPinClient>) -> Self {
        self.remote_pin = Some(remote);
        self
    }
}

impl BlockStore for KuboBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        ensure_block_matches_cid(cid, data)?;
        if !self.is_available() {
            return Ok(());
        }

        let url = format!(
            "{}?cid-codec=dag-cbor&mhtype=sha2-256",
            self.api_url("block/put")
        );
        let body = data.to_vec();
        let client = self.client.clone();
        let token = self.token.clone();
        let cid_mb = cid.to_multibase();
        let inflight = Arc::clone(&self.inflight);

        let resp_key = kubo_block_on(async move {
            // Wait for an in-flight permit before opening the socket.
            // `acquire_owned` on a never-closed semaphore can only fail if
            // the runtime is shutting down — bubble that up as an error.
            let _permit = inflight
                .acquire_owned()
                .await
                .map_err(|e| anyhow!("kubo block/put permit: {e}"))?;
            let part = reqwest::multipart::Part::bytes(body).file_name("blob");
            let form = reqwest::multipart::Form::new().part("data", part);
            let rb = client.post(&url).multipart(form);
            let rb = match &token {
                Some(t) => rb.bearer_auth(t),
                None => rb,
            };
            let resp = rb
                .send()
                .await
                .map_err(|e| anyhow!("kubo block/put: {e}"))?;
            if !resp.status().is_success() {
                let st = resp.status();
                let tx = resp.text().await.unwrap_or_default();
                return Err(anyhow!("kubo block/put {st}: {tx}"));
            }
            let parsed: BlockPutResponse = resp
                .json()
                .await
                .map_err(|e| anyhow!("kubo block/put parse: {e}"))?;
            Ok::<String, anyhow::Error>(parsed.key)
        });

        match resp_key {
            Err(e) => {
                if e.to_string().contains("connect") {
                    self.mark_unavailable();
                }
                Err(e)
            }
            Ok(key) => {
                self.mark_available();
                tracing::debug!(cid = %cid_mb, kubo_key = %key, "kubo block stored");
                Ok(())
            }
        }
    }

    /// Durably write a batch of blocks CONCURRENTLY (bounded by the inflight
    /// semaphore) in one `kubo_block_on`, so a commit's O(state) blocks overlap
    /// into ~one round-trip instead of N sequential `block/put`s. Throughput fix
    /// for the put_durable commit path (2026-06-02; ADR-2606012200). Fails if any
    /// block fails (surfaces the first error).
    fn put_many_durable(&self, blocks: &[(KotobaCid, Vec<u8>)]) -> Result<()> {
        for (cid, data) in blocks {
            ensure_block_matches_cid(cid, data)?;
        }
        if !self.is_available() || blocks.is_empty() {
            return Ok(());
        }
        let url = format!(
            "{}?cid-codec=dag-cbor&mhtype=sha2-256",
            self.api_url("block/put")
        );
        let client = self.client.clone();
        let token = self.token.clone();
        let inflight = Arc::clone(&self.inflight);
        let bodies: Vec<Vec<u8>> = blocks.iter().map(|(_, d)| d.clone()).collect();
        let result = kubo_block_on(async move {
            let mut set = tokio::task::JoinSet::new();
            for body in bodies {
                let url = url.clone();
                let client = client.clone();
                let token = token.clone();
                let inflight = Arc::clone(&inflight);
                set.spawn(async move {
                    let _permit = inflight
                        .acquire_owned()
                        .await
                        .map_err(|e| anyhow!("kubo block/put permit: {e}"))?;
                    let part = reqwest::multipart::Part::bytes(body).file_name("blob");
                    let form = reqwest::multipart::Form::new().part("data", part);
                    let rb = client.post(&url).multipart(form);
                    let rb = match &token {
                        Some(t) => rb.bearer_auth(t),
                        None => rb,
                    };
                    let resp = rb
                        .send()
                        .await
                        .map_err(|e| anyhow!("kubo block/put: {e}"))?;
                    if !resp.status().is_success() {
                        let st = resp.status();
                        let tx = resp.text().await.unwrap_or_default();
                        return Err(anyhow!("kubo block/put {st}: {tx}"));
                    }
                    let _parsed: BlockPutResponse = resp
                        .json()
                        .await
                        .map_err(|e| anyhow!("kubo block/put parse: {e}"))?;
                    Ok::<(), anyhow::Error>(())
                });
            }
            let mut first_err: Option<anyhow::Error> = None;
            while let Some(joined) = set.join_next().await {
                match joined {
                    Ok(Ok(())) => {}
                    Ok(Err(e)) => {
                        first_err.get_or_insert(e);
                    }
                    Err(e) => {
                        first_err.get_or_insert(anyhow!("kubo block/put join: {e}"));
                    }
                }
            }
            match first_err {
                Some(e) => Err(e),
                None => Ok::<(), anyhow::Error>(()),
            }
        });
        match result {
            Err(e) => {
                if e.to_string().contains("connect") {
                    self.mark_unavailable();
                }
                Err(e)
            }
            Ok(()) => {
                self.mark_available();
                Ok(())
            }
        }
    }

    fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
        if !self.is_available() {
            return Ok(None);
        }

        let url = format!("{}?arg={}", self.api_url("block/get"), cid.to_multibase());
        let client = self.client.clone();
        let token = self.token.clone();
        let inflight = Arc::clone(&self.inflight);

        let result = kubo_block_on(async move {
            let _permit = inflight
                .acquire_owned()
                .await
                .map_err(|e| anyhow!("kubo block/get permit: {e}"))?;
            let rb = client.post(&url);
            let rb = match &token {
                Some(t) => rb.bearer_auth(t),
                None => rb,
            };
            let resp = rb
                .send()
                .await
                .map_err(|e| anyhow!("kubo block/get: {e}"))?;
            let status = resp.status();
            if status == reqwest::StatusCode::NOT_FOUND || status.as_u16() == 500 {
                let text = resp.text().await.unwrap_or_default();
                if text.contains("block not found") || text.contains("not found") {
                    return Ok::<Option<Bytes>, anyhow::Error>(None);
                }
                return Err(anyhow!("kubo block/get error: {text}"));
            }
            if !status.is_success() {
                let text = resp.text().await.unwrap_or_default();
                return Err(anyhow!("kubo block/get {status}: {text}"));
            }
            let bytes = resp
                .bytes()
                .await
                .map_err(|e| anyhow!("kubo block/get body: {e}"))?;
            Ok(Some(bytes))
        });

        match result {
            Err(e) => {
                if e.to_string().contains("connect") {
                    self.mark_unavailable();
                }
                Err(e)
            }
            Ok(bytes) => {
                self.mark_available();
                match bytes {
                    Some(bytes) => {
                        if !block_matches_cid(cid, &bytes) {
                            tracing::warn!(cid = %cid, "kubo block/get failed CID verification");
                            return Ok(None);
                        }
                        Ok(Some(bytes))
                    }
                    None => Ok(None),
                }
            }
        }
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.get(cid).map(|block| block.is_some()).unwrap_or(false)
    }

    fn delete(&self, cid: &KotobaCid) -> Result<()> {
        if !self.is_available() {
            return Ok(());
        }

        let url = format!(
            "{}?arg={}&force=true",
            self.api_url("block/rm"),
            cid.to_multibase()
        );
        let client = self.client.clone();
        let token = self.token.clone();

        kubo_block_on(async move {
            let rb = client.post(&url);
            let rb = match &token {
                Some(t) => rb.bearer_auth(t),
                None => rb,
            };
            let resp = rb.send().await.map_err(|e| anyhow!("kubo block/rm: {e}"))?;
            if !resp.status().is_success() {
                let st = resp.status();
                let text = resp.text().await.unwrap_or_default();
                if !text.contains("not found") {
                    return Err(anyhow!("kubo block/rm {st}: {text}"));
                }
            }
            Ok::<_, anyhow::Error>(())
        })
    }

    /// Add the CID to Kubo's pin set (direct pin, NOT recursive) so the
    /// daemon's GC cannot reclaim it.  Direct pins avoid Kubo's CBOR
    /// traversal — recursive pin/add 500-s on blocks that are not valid
    /// DAG-CBOR (e.g. HPKE-wrapped vault key blocks stored as opaque bytes
    /// under cid-codec=dag-cbor: "pin: unexpected content after end of cbor
    /// object").  Kotoba already calls `put_durable` on every load-bearing
    /// block individually, so recursive traversal is not needed — pinning
    /// each block directly gives the same durability guarantee.
    fn pin(&self, cid: &KotobaCid) {
        self.pinned.write().unwrap().insert(cid.0);
        if !self.is_available() {
            return;
        }
        let url = format!(
            "{}?arg={}&recursive=false",
            self.api_url("pin/add"),
            cid.to_multibase()
        );
        let client = self.client.clone();
        let token = self.token.clone();
        let inflight = Arc::clone(&self.inflight);
        let cid_mb = cid.to_multibase();
        // Skip the HTTP round-trip when called outside a Tokio runtime (e.g.
        // sync unit tests) — the in-memory pin set above is already updated.
        let pin_result = match tokio::runtime::Handle::try_current() {
            Err(_) => Ok::<(), anyhow::Error>(()),
            Ok(_) => kubo_block_on(async move {
                let _permit = inflight.acquire_owned().await.map_err(|e| anyhow!(e))?;
                let rb = client.post(&url);
                let rb = match &token {
                    Some(t) => rb.bearer_auth(t),
                    None => rb,
                };
                let resp = rb.send().await.map_err(|e| anyhow!("kubo pin/add: {e}"))?;
                if !resp.status().is_success() {
                    let st = resp.status();
                    let tx = resp.text().await.unwrap_or_default();
                    return Err(anyhow!("kubo pin/add {st}: {tx}"));
                }
                Ok::<(), anyhow::Error>(())
            }),
        };
        if let Err(e) = pin_result {
            tracing::warn!(cid = %cid_mb, err = %e, "kubo pin/add failed");
            if e.to_string().contains("connect") {
                self.mark_unavailable();
            }
        } else {
            tracing::debug!(cid = %cid_mb, "kubo cid pinned recursively");
            // F-3: fan the pin out to kotobase (or any KOTOBA_IPFS_PIN_ENDPOINT)
            // — fire-and-forget; failures are logged but never block kotoba.
            if let Some(remote) = &self.remote_pin {
                let remote = Arc::clone(remote);
                let cid_for_remote = cid_mb.clone();
                if let Ok(handle) = tokio::runtime::Handle::try_current() {
                    handle.spawn(async move { remote.pin(&cid_for_remote).await });
                }
            }
        }
    }

    /// Remove the CID from Kubo's pin set so it becomes GC-eligible again.
    fn unpin(&self, cid: &KotobaCid) {
        self.pinned.write().unwrap().remove(&cid.0);
        if !self.is_available() {
            return;
        }
        let url = format!("{}?arg={}", self.api_url("pin/rm"), cid.to_multibase());
        let client = self.client.clone();
        let token = self.token.clone();
        let inflight = Arc::clone(&self.inflight);
        let cid_mb = cid.to_multibase();
        let unpin_result = match tokio::runtime::Handle::try_current() {
            Err(_) => Ok::<(), anyhow::Error>(()),
            Ok(_) => kubo_block_on(async move {
                let _permit = inflight.acquire_owned().await.map_err(|e| anyhow!(e))?;
                let rb = client.post(&url);
                let rb = match &token {
                    Some(t) => rb.bearer_auth(t),
                    None => rb,
                };
                let resp = rb.send().await.map_err(|e| anyhow!("kubo pin/rm: {e}"))?;
                let status = resp.status();
                if !status.is_success() {
                    let tx = resp.text().await.unwrap_or_default();
                    // "not pinned" is benign — the local pinned-set may have
                    // tracked a CID Kubo never saw, e.g. across restarts.
                    if tx.contains("not pinned") {
                        return Ok::<(), anyhow::Error>(());
                    }
                    return Err(anyhow!("kubo pin/rm {status}: {tx}"));
                }
                Ok(())
            }),
        };
        if let Err(e) = unpin_result {
            tracing::warn!(cid = %cid_mb, err = %e, "kubo pin/rm failed");
        }
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.pinned.read().unwrap().contains(&cid.0)
    }
}

/// Minimal JSON string-field extractor (avoids a serde_json dep).
/// Looks for `"<key>":"<value>"` and returns the unescaped value.
fn extract_json_string_field(body: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\"");
    let i = body.find(&needle)?;
    let rest = &body[i + needle.len()..];
    let colon = rest.find(':')?;
    let after_colon = rest[colon + 1..].trim_start();
    if !after_colon.starts_with('"') {
        return None;
    }
    let val = &after_colon[1..];
    let end = val.find('"')?;
    Some(val[..end].to_string())
}

fn block_matches_cid(cid: &KotobaCid, data: &[u8]) -> bool {
    KotobaCid::from_bytes(data) == *cid
}

fn ensure_block_matches_cid(cid: &KotobaCid, data: &[u8]) -> Result<()> {
    anyhow::ensure!(
        block_matches_cid(cid, data),
        "cid mismatch: expected {}, got {}",
        cid.to_multibase(),
        KotobaCid::from_bytes(data).to_multibase()
    );
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha2_cid_roundtrip() {
        let data = b"hello kotoba single-cid";
        let cid = KotobaCid::from_bytes(data);
        let mb = cid.to_multibase();
        // CIDv1 dag-cbor sha2-256 multibase starts with 'b' (base32lower)
        assert!(mb.starts_with('b'), "multibase prefix must be 'b'");
        let cid2 = KotobaCid::from_multibase(&mb).expect("round-trip");
        assert_eq!(cid, cid2);
    }

    #[test]
    fn kubo_http_client_uses_bounded_sidecar_timeouts() {
        assert_eq!(KUBO_CONNECT_TIMEOUT, Duration::from_secs(5));
        assert_eq!(KUBO_REQUEST_TIMEOUT, Duration::from_secs(30));
        assert_eq!(KUBO_POOL_IDLE_TIMEOUT, Duration::from_secs(30));
        assert_eq!(KUBO_POOL_MAX_IDLE_PER_HOST, 8);
        assert_eq!(KUBO_FAILURE_COOLDOWN_SECS, 5);
    }

    #[test]
    fn normalize_kubo_endpoint_accepts_http_https_root_urls() {
        assert_eq!(
            normalize_kubo_endpoint(" http://localhost:5001/ ").unwrap(),
            "http://localhost:5001"
        );
        assert_eq!(
            normalize_kubo_endpoint("https://kubo.example.com").unwrap(),
            "https://kubo.example.com"
        );
    }

    #[test]
    fn normalize_kubo_endpoint_rejects_ambiguous_or_header_unsafe_values() {
        for endpoint in [
            "",
            "ftp://localhost:5001",
            "https://user:pass@localhost:5001",
            "http://localhost:5001/api",
            "http://localhost:5001?x=1",
            "http://localhost:5001#frag",
            "http://localhost:5001/\nheader",
            "not a url",
        ] {
            assert!(
                normalize_kubo_endpoint(endpoint).is_none(),
                "endpoint should be rejected: {endpoint:?}"
            );
        }
    }

    #[test]
    fn kubo_store_new_disables_invalid_endpoint() {
        let store = KuboBlockStore::new("http://localhost:5001/api");

        assert_eq!(store.endpoint, DISABLED_KUBO_ENDPOINT);
    }

    #[tokio::test(flavor = "current_thread")]
    async fn kubo_block_on_works_inside_current_thread_runtime() {
        assert_eq!(kubo_block_on(async { 7usize }), 7);
    }

    #[test]
    fn different_data_different_cid() {
        let c1 = KotobaCid::from_bytes(b"block a");
        let c2 = KotobaCid::from_bytes(b"block b");
        assert_ne!(c1.to_multibase(), c2.to_multibase());
    }

    #[test]
    fn block_matches_cid_accepts_matching_bytes() {
        let data = b"kubo verified block";
        let cid = KotobaCid::from_bytes(data);

        assert!(block_matches_cid(&cid, data));
    }

    #[test]
    fn block_matches_cid_rejects_mismatched_bytes() {
        let cid = KotobaCid::from_bytes(b"kubo verified block");

        assert!(!block_matches_cid(&cid, b"different block"));
    }

    #[test]
    fn put_rejects_mismatched_cid_before_availability_check() {
        let store = KuboBlockStore::new("http://localhost:5001");
        store.mark_unavailable();
        let bad_cid = KotobaCid::from_bytes(b"expected");

        let err = store.put(&bad_cid, b"different").unwrap_err();

        assert!(err.to_string().contains("cid mismatch"));
    }

    #[test]
    fn put_many_durable_rejects_mismatched_cid_before_availability_check() {
        let store = KuboBlockStore::new("http://localhost:5001");
        store.mark_unavailable();
        let bad_cid = KotobaCid::from_bytes(b"expected");

        let err = store
            .put_many_durable(&[(bad_cid, b"different".to_vec())])
            .unwrap_err();

        assert!(err.to_string().contains("cid mismatch"));
    }

    #[test]
    fn unavailable_get_returns_none() {
        let store = KuboBlockStore::new("http://localhost:5001");
        store.mark_unavailable();
        let cid = KotobaCid::from_bytes(b"any");
        let rt = tokio::runtime::Runtime::new().unwrap();
        let res = rt.block_on(async {
            tokio::task::spawn_blocking(move || store.get(&cid))
                .await
                .unwrap()
        });
        assert!(res.unwrap().is_none(), "unavailable store must return None");
    }

    #[test]
    fn unavailable_has_returns_false() {
        let store = KuboBlockStore::new("http://localhost:5001");
        store.mark_unavailable();
        let cid = KotobaCid::from_bytes(b"any");
        assert!(!store.has(&cid));
    }

    #[test]
    fn kubo_store_retries_after_failure_cooldown() {
        let store = KuboBlockStore::new("http://localhost:5001");
        store.mark_unavailable();
        assert!(!store.is_available());

        let stale_failure = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
            .saturating_sub(KUBO_FAILURE_COOLDOWN_SECS + 1);
        store.failed_at_unix.store(stale_failure, Ordering::Relaxed);

        assert!(store.is_available());
        store.mark_available();
        assert_eq!(store.failed_at_unix.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn pin_unpin_roundtrip() {
        let store = KuboBlockStore::new("http://localhost:5001");
        let cid = KotobaCid::from_bytes(b"pin-test");
        assert!(!store.is_pinned(&cid));
        store.pin(&cid);
        assert!(store.is_pinned(&cid));
        store.unpin(&cid);
        assert!(!store.is_pinned(&cid));
    }

    #[test]
    fn extract_json_string_field_basic() {
        let body = r#"{"Version":"0.27.0","Commit":"abc123","Other":42}"#;
        assert_eq!(
            extract_json_string_field(body, "Version"),
            Some("0.27.0".into())
        );
        assert_eq!(
            extract_json_string_field(body, "Commit"),
            Some("abc123".into())
        );
        assert_eq!(extract_json_string_field(body, "Missing"), None);
    }
}
