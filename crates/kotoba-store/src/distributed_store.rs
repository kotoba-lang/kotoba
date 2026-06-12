#[cfg(test)]
use crate::MemoryBlockStore;
use anyhow::Result;
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use reqwest::Url;
use std::future::Future;
/// DistributedBlockStore — multi-peer block fetch with local-first caching.
///
/// Implements the distributed read path for IPFS-backed ProllyTree queries:
///   1. Check local store (hot cache hit → µs)
///   2. On miss: try each peer's Kubo HTTP `/api/v0/block/get?arg={cid}` in order
///   3. On success: promote block to local store; subsequent reads are cache hits
///
/// Write path: writes go to local store only.  Background replication (bitswap
/// announce to peers) is handled out-of-band by the Kubo daemon or KotobaSwarm.
///
/// # Env-driven peer list
///
/// `KOTOBA_PEERS` — space-separated Kubo HTTP base URLs, e.g.:
/// ```text
/// KOTOBA_PEERS="http://peer1:5001 http://peer2:5001"
/// ```
///
/// # Usage with TieredBlockStore
///
/// Compose a full IPFS-distributed read path:
/// ```text
/// TieredBlockStore
///   hot = BudgetedBlockStore<MemoryBlockStore>   (LRU hot cache)
///   cold = DistributedBlockStore                  (local Kubo + peer fallback)
/// ```
use std::sync::Arc;

const MAX_DISTRIBUTED_PEERS: usize = 32;
const MAX_PEER_URL_LEN: usize = 256;

/// A block store that reads from `local` first, then fans out to `peers` on miss.
///
/// On peer hit the block is promoted to `local` so the next access is a cache hit.
pub struct DistributedBlockStore {
    local: Arc<dyn BlockStore + Send + Sync>,
    peers: Vec<String>, // Kubo HTTP base URLs
    client: reqwest::Client,
}

impl DistributedBlockStore {
    pub fn new(local: Arc<dyn BlockStore + Send + Sync>, peers: Vec<String>) -> Self {
        let client = reqwest::Client::builder()
            .connect_timeout(std::time::Duration::from_millis(500))
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .unwrap_or_default();
        let peers = peers
            .iter()
            .filter_map(|peer| normalize_peer_url(peer))
            .take(MAX_DISTRIBUTED_PEERS)
            .collect();
        Self {
            local,
            peers,
            client,
        }
    }

    /// Create from `KOTOBA_PEERS` env var (space-separated URLs).
    /// Falls back to `local`-only if the var is absent.
    pub fn from_env(local: Arc<dyn BlockStore + Send + Sync>) -> Self {
        let s = std::env::var("KOTOBA_PEERS").unwrap_or_default();
        Self::from_peers_str(&s, local)
    }

    /// Create from a space-separated peer URL string (useful in tests).
    pub fn from_peers_str(peers_str: &str, local: Arc<dyn BlockStore + Send + Sync>) -> Self {
        let peers = peers_str
            .split_whitespace()
            .filter_map(normalize_peer_url)
            .take(MAX_DISTRIBUTED_PEERS)
            .collect();
        Self::new(local, peers)
    }

    pub fn peer_count(&self) -> usize {
        self.peers.len()
    }

    fn kubo_get_url(base: &str, cid_mb: &str) -> String {
        format!("{base}/api/v0/block/get?arg={cid_mb}")
    }

    /// Fetch from a single peer Kubo node.  Returns `None` if not available.
    fn fetch_from_peer(&self, peer: &str, cid_mb: &str) -> Option<Bytes> {
        let url = Self::kubo_get_url(peer, cid_mb);
        let client = self.client.clone();
        distributed_block_on(async move {
            let resp = client.post(&url).send().await.ok()?;
            if !resp.status().is_success() {
                return None;
            }
            let b = resp.bytes().await.ok()?;
            if b.is_empty() {
                None
            } else {
                Some(b)
            }
        })
    }
}

impl BlockStore for DistributedBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        self.local.put(cid, data)
    }

    fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
        // 1. Local hit
        if let Some(b) = self.local.get(cid)? {
            if verified_block(cid, &b) {
                return Ok(Some(b));
            }
            tracing::warn!(cid = %cid, "distributed local block failed CID verification");
            let _ = self.local.delete(cid);
        }
        // 2. Fan out to peers
        let cid_mb = cid.to_multibase();
        for peer in &self.peers {
            if let Some(b) = self.fetch_from_peer(peer, &cid_mb) {
                if !verified_block(cid, &b) {
                    tracing::warn!(
                        peer = %peer,
                        cid = %cid_mb,
                        "distributed peer block failed CID verification"
                    );
                    continue;
                }
                // Promote to local cache (ignore write error — best-effort)
                let _ = self.local.put(cid, &b);
                tracing::debug!(peer = %peer, cid = %cid_mb, "distributed block fetch hit");
                return Ok(Some(b));
            }
        }
        Ok(None)
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.get(cid).map(|block| block.is_some()).unwrap_or(false)
    }

    fn delete(&self, cid: &KotobaCid) -> Result<()> {
        self.local.delete(cid)
    }

    fn pin(&self, cid: &KotobaCid) {
        self.local.pin(cid)
    }
    fn unpin(&self, cid: &KotobaCid) {
        self.local.unpin(cid)
    }
    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.local.is_pinned(cid)
    }

    fn all_cids(&self) -> Vec<KotobaCid> {
        self.local.all_cids()
    }
}

fn verified_block(cid: &KotobaCid, data: &[u8]) -> bool {
    KotobaCid::from_bytes(data) == *cid
}

fn normalize_peer_url(peer: &str) -> Option<String> {
    let peer = peer.trim();
    if peer.is_empty() || peer.len() > MAX_PEER_URL_LEN || peer.chars().any(|ch| ch.is_control()) {
        return None;
    }
    let url = Url::parse(peer).ok()?;
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

fn distributed_runtime() -> &'static tokio::runtime::Runtime {
    static RT: std::sync::OnceLock<tokio::runtime::Runtime> = std::sync::OnceLock::new();
    RT.get_or_init(|| {
        tokio::runtime::Builder::new_multi_thread()
            .worker_threads(2)
            .enable_all()
            .thread_name("distributed-store-io")
            .build()
            .expect("build distributed-store-io runtime")
    })
}

fn distributed_block_on<F>(fut: F) -> F::Output
where
    F: Future + Send + 'static,
    F::Output: Send + 'static,
{
    let rt = distributed_runtime();
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
                    .expect("distributed-store-io runtime dropped the in-flight result")
            } else {
                rx.recv()
                    .expect("distributed-store-io runtime dropped the in-flight result")
            }
        }
        Err(_) => rt.block_on(fut),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_local() -> Arc<dyn BlockStore + Send + Sync> {
        Arc::new(MemoryBlockStore::new())
    }

    #[test]
    fn distributed_store_local_hit_no_peers() {
        let local = make_local();
        let data = b"hello-block";
        let cid = KotobaCid::from_bytes(data);
        local.put(&cid, data).unwrap();
        let dist = DistributedBlockStore::new(local, vec![]);
        let result = dist.get(&cid).unwrap();
        assert_eq!(result.as_deref(), Some(data as &[u8]));
    }

    #[test]
    fn distributed_store_miss_no_peers_returns_none() {
        let local = make_local();
        let cid = KotobaCid::from_bytes(b"dist-test-cid-2");
        let dist = DistributedBlockStore::new(local, vec![]);
        assert!(dist.get(&cid).unwrap().is_none());
    }

    #[test]
    fn distributed_store_has_checks_local() {
        let local = make_local();
        let data = b"data";
        let cid = KotobaCid::from_bytes(data);
        local.put(&cid, data).unwrap();
        let dist = DistributedBlockStore::new(local, vec![]);
        assert!(dist.has(&cid));
    }

    #[test]
    fn distributed_store_has_returns_false_when_absent() {
        let local = make_local();
        let cid = KotobaCid::from_bytes(b"dist-test-cid-4");
        let dist = DistributedBlockStore::new(local, vec![]);
        assert!(!dist.has(&cid));
    }

    #[test]
    fn distributed_store_has_removes_corrupted_local_block() {
        let local_memory = Arc::new(MemoryBlockStore::new());
        let cid = KotobaCid::from_bytes(b"expected distributed has block");
        local_memory.insert_unchecked(&cid, b"corrupted distributed has block");
        let local = Arc::clone(&local_memory) as Arc<dyn BlockStore + Send + Sync>;
        let dist = DistributedBlockStore::new(local, vec![]);

        assert!(!dist.has(&cid));
        assert!(!local_memory.has(&cid));
    }

    #[test]
    fn distributed_store_peer_count() {
        let local = make_local();
        let dist = DistributedBlockStore::new(
            local,
            vec!["http://p1:5001".into(), "http://p2:5001".into()],
        );
        assert_eq!(dist.peer_count(), 2);
    }

    #[test]
    fn distributed_store_put_writes_to_local() {
        let local = make_local();
        let data = b"written";
        let cid = KotobaCid::from_bytes(data);
        let dist = DistributedBlockStore::new(Arc::clone(&local), vec![]);
        dist.put(&cid, data).unwrap();
        // Verify block is in the underlying local store
        let direct = local.get(&cid).unwrap();
        assert_eq!(direct.as_deref(), Some(data as &[u8]));
    }

    #[test]
    fn distributed_store_rejects_corrupted_local_block() {
        let local_memory = Arc::new(MemoryBlockStore::new());
        let data = b"expected distributed block";
        let cid = KotobaCid::from_bytes(data);
        local_memory.insert_unchecked(&cid, b"corrupted local block");
        let local = Arc::clone(&local_memory) as Arc<dyn BlockStore + Send + Sync>;
        let dist = DistributedBlockStore::new(Arc::clone(&local), vec![]);

        let result = dist.get(&cid).unwrap();

        assert!(result.is_none());
        assert!(
            !local.has(&cid),
            "corrupted local block should be removed after verification failure"
        );
    }

    #[test]
    fn distributed_store_all_cids_delegates_to_verified_local_store() {
        let local_memory = Arc::new(MemoryBlockStore::new());
        let good = KotobaCid::from_bytes(b"distributed listed block");
        let corrupt = KotobaCid::from_bytes(b"distributed corrupt listed block");
        local_memory
            .put(&good, b"distributed listed block")
            .unwrap();
        local_memory.insert_unchecked(&corrupt, b"corrupted listed block");
        let local = Arc::clone(&local_memory) as Arc<dyn BlockStore + Send + Sync>;
        let dist = DistributedBlockStore::new(local, vec![]);

        let cids = dist.all_cids();

        assert_eq!(cids, vec![good]);
        assert!(!local_memory.has(&corrupt));
    }

    #[tokio::test]
    async fn distributed_store_get_inside_runtime_handles_peer_miss() {
        let local = make_local();
        let cid = KotobaCid::from_bytes(b"distributed runtime miss");
        let dist = DistributedBlockStore::new(local, vec!["http://127.0.0.1:9".to_string()]);

        assert!(dist.get(&cid).unwrap().is_none());
        assert!(!dist.has(&cid));
    }

    #[test]
    fn distributed_store_from_peers_str_empty() {
        // Test from_peers_str directly (no env var mutation needed)
        let dist = DistributedBlockStore::from_peers_str("", make_local());
        assert_eq!(dist.peer_count(), 0);
    }

    #[test]
    fn distributed_store_from_peers_str_parses_space_separated() {
        let dist = DistributedBlockStore::from_peers_str(
            "http://a:5001/ http://b:5001 http://c:5001/",
            make_local(),
        );
        assert_eq!(dist.peer_count(), 3);
        assert_eq!(
            dist.peers,
            vec!["http://a:5001", "http://b:5001", "http://c:5001"]
        );
    }

    #[test]
    fn distributed_store_rejects_ambiguous_peer_urls() {
        let dist = DistributedBlockStore::from_peers_str(
            "http://ok:5001 https://user:pass@bad:5001 http://bad:5001/api http://bad:5001?x=1 http://bad:5001#frag ftp://bad:21 header",
            make_local(),
        );
        assert_eq!(dist.peers, vec!["http://ok:5001"]);
    }

    #[test]
    fn distributed_store_new_normalizes_and_caps_peers() {
        let peers = (0..(MAX_DISTRIBUTED_PEERS + 5))
            .map(|i| format!("http://p{i}:5001/"))
            .chain([
                "http://bad:5001/api".to_string(),
                "http://bad:5001/\nheader".to_string(),
            ])
            .collect();
        let dist = DistributedBlockStore::new(make_local(), peers);

        assert_eq!(dist.peer_count(), MAX_DISTRIBUTED_PEERS);
        assert_eq!(dist.peers[0], "http://p0:5001");
        assert_eq!(dist.peers[MAX_DISTRIBUTED_PEERS - 1], "http://p31:5001");
    }
}
