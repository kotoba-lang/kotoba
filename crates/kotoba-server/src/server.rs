use std::sync::Arc;
use std::collections::HashMap;

use bytes::Bytes;
use kotoba_dht::{
    neighborhood::Neighborhood,
    node_id::NodeId,
};
use kotoba_kse::{sync_window::SyncWindow, Journal, Shelf, Topic, Vault};
use kotoba_kqe::quad::Quad;
use kotoba_graph::QuadStore;
use kotoba_kse::SecureVault;
use kotoba_store::{BudgetedBlockStore, IpfsPinClient, LayeredBlockStore};
use kotoba_runtime::{host::InferenceFn, UdfExecutor, WasmExecutor};
use kotoba_ingest::embed_client::{EmbedClient, HttpEmbedClient};
use kotoba_vm::{distributed::DistributedPregelRunner, InvokeRouter};
use kotoba_core::store::BlockStore;

/// Shared server state — Arc-wrapped and injected into every axum handler.
pub struct KotobaState {
    pub version:       &'static str,
    // ── KSE ──────────────────────────────────────────────────────────────
    pub journal:       Arc<Journal>,
    pub shelf:         Arc<Shelf>,
    /// Content-addressed private blob vault (no GossipSub, no CACAO required).
    pub vault:         Arc<Vault>,
    // ── KDHT ─────────────────────────────────────────────────────────────
    pub neighborhood:  Arc<tokio::sync::RwLock<Neighborhood>>,
    pub local_node_id: NodeId,
    // ── KVM / Runtime ────────────────────────────────────────────────────
    pub executor:      Arc<WasmExecutor>,
    pub udf:           Arc<UdfExecutor>,
    pub router:        Arc<InvokeRouter>,
    // ── P2P / Gossip ─────────────────────────────────────────────────────
    /// GossipSub outbound channel — `Some(tx)` when the swarm actor is running.
    pub gossip_tx:        Option<tokio::sync::mpsc::Sender<(String, Vec<u8>)>>,
    // ── Distributed Pregel ───────────────────────────────────────────────
    /// Pregel runner — `Some` after swarm is attached.
    /// Lock to inject messages or trigger a superstep from XRPC handlers.
    pub pregel_runner:    Option<Arc<tokio::sync::Mutex<DistributedPregelRunner>>>,
    // ── Inference ────────────────────────────────────────────────────────
    /// Gemma 4 E2B inference engine, loaded at startup when `KOTOBA_LOAD_GEMMA` is set.
    pub inference_engine: Option<InferenceFn>,
    // ── BlockStore ───────────────────────────────────────────────────────
    /// Content-addressed block store (sled-backed or ephemeral).
    pub block_store: Arc<dyn BlockStore + Send + Sync>,
    // ── QuadStore ────────────────────────────────────────────────────────────
    /// Quad write/read with ProllyTree commit + 3-index Journal publish.
    pub quad_store:  Arc<QuadStore>,
    // ── IPFS Pinning ─────────────────────────────────────────────────────────
    /// Optional IPFS Pinning Service client (Pinata/web3.storage/Filebase).
    pub ipfs_pin: Option<Arc<IpfsPinClient>>,
    // ── Email E2E Storage ────────────────────────────────────────────────────
    /// AES-256-GCM encrypted vault for email body blobs.
    pub secure_vault: Arc<SecureVault>,
    /// 32-byte vault key from KOTOBA_VAULT_KEY (hex).  None = email features disabled.
    pub vault_key: Option<[u8; 32]>,
    // ── Agent Sessions ───────────────────────────────────────────────────────
    /// Active SyncWindow sessions keyed by session_id.
    pub agent_sessions: Arc<tokio::sync::RwLock<HashMap<String, SyncWindow>>>,
    // ── CC Vector Search ─────────────────────────────────────────────────────
    /// Optional embed client for CC vector search (KOTOBA_EMBED_URL).
    pub cc_embed_client: Option<Arc<dyn EmbedClient>>,
}

impl KotobaState {
    pub fn new(inference_engine: Option<InferenceFn>) -> anyhow::Result<Self> {
        // BlockStore — sled-backed when KOTOBA_STORE_PATH is set, ephemeral otherwise.
        // All KSE components (Journal, Vault, SecureVault) share the same store.
        let store_path: Option<String> = std::env::var("KOTOBA_STORE_PATH").ok();
        let sled_db: Option<sled::Db> = store_path.as_ref().map(|path| {
            sled::open(path)
                .map_err(|e| anyhow::anyhow!("sled open failed: {e}"))
                .expect("sled open")
        });

        let budget_bytes: Option<usize> = std::env::var("KOTOBA_STORAGE_BUDGET_BYTES")
            .ok()
            .and_then(|s| s.parse().ok());

        let block_store: Arc<dyn BlockStore + Send + Sync> = match &sled_db {
            Some(db) => {
                tracing::info!("BlockStore: sled-backed persistence");
                let inner = kotoba_store::SledBlockStore::from_db(db)
                    .map_err(|e| anyhow::anyhow!("sled blocks tree: {e}"))?;
                maybe_wrap(inner, budget_bytes)
            }
            None => {
                tracing::warn!("BlockStore: ephemeral (set KOTOBA_STORE_PATH for persistence)");
                let inner = kotoba_store::SledBlockStore::temporary()
                    .map_err(|e| anyhow::anyhow!("sled temporary failed: {e}"))?;
                maybe_wrap(inner, budget_bytes)
            }
        };

        // Journal — Merkle WAL backed by block_store; head pointer in a sibling JSON file.
        let journal = Arc::new(match &store_path {
            Some(path) => {
                let head_path = format!("{path}.journal-head.json");
                tracing::info!("KSE Journal: block-store persistence enabled");
                Journal::with_block_store(Arc::clone(&block_store), head_path)
            }
            None => {
                tracing::info!("KSE Journal: in-memory only (set KOTOBA_STORE_PATH for persistence)");
                Journal::new()
            }
        });
        let shelf = Arc::new(Shelf::new());

        // KDHT — generate ephemeral NodeId (dev mode; prod uses persisted Ed25519 key)
        let local_node_id = {
            let seed: [u8; 32] = rand_seed();
            NodeId(seed)
        };
        let neighborhood = Arc::new(tokio::sync::RwLock::new(
            Neighborhood::new(local_node_id.clone()),
        ));

        // Runtime — wire the inference engine into InvokeRouter / WasmExecutor
        let gateway_url = std::env::var("KOTOBA_GATEWAY_URL")
            .unwrap_or_else(|_| "http://localhost:9000".into());

        let (executor, router) = match &inference_engine {
            Some(engine) => (
                Arc::new(WasmExecutor::with_inference(10_000_000, engine.clone())?),
                Arc::new(InvokeRouter::with_inference(10_000_000, &gateway_url, engine.clone())?),
            ),
            None => (
                Arc::new(WasmExecutor::new(10_000_000)?),
                Arc::new(InvokeRouter::new(10_000_000, gateway_url)?),
            ),
        };
        let udf = Arc::new(UdfExecutor::new()?);

        // IPFS Pinning Service client (E) — optional, no daemon required
        let ipfs_pin = IpfsPinClient::from_env();
        if ipfs_pin.is_some() {
            tracing::info!("IPFS pinning enabled (KOTOBA_IPFS_PIN_ENDPOINT)");
        }

        // QuadStore — wraps Journal + BlockStore; provides ProllyTree commit path
        let quad_store = Arc::new(QuadStore::new(Arc::clone(&journal), Arc::clone(&block_store)));

        // Vault — content-addressed private blob store; backed by block_store.
        let vault = Arc::new(if store_path.is_some() {
            tracing::info!("Vault: block-store persistence enabled");
            Vault::with_block_store(Arc::clone(&block_store))
        } else {
            tracing::info!("Vault: in-memory only");
            Vault::new()
        });

        // SecureVault — E2E encrypted blob store for email bodies; shares block_store.
        let secure_vault = Arc::new(if store_path.is_some() {
            tracing::info!("SecureVault: block-store persistence enabled");
            SecureVault::with_vault(Vault::with_block_store(Arc::clone(&block_store)))
        } else {
            SecureVault::new()
        });

        // Vault key — 32 bytes from KOTOBA_VAULT_KEY (64 hex chars)
        let vault_key: Option<[u8; 32]> = std::env::var("KOTOBA_VAULT_KEY").ok().and_then(|s| {
            let b = hex::decode(s.trim()).ok()?;
            if b.len() != 32 {
                tracing::warn!("KOTOBA_VAULT_KEY must be 64 hex chars (32 bytes); email features disabled");
                return None;
            }
            let mut k = [0u8; 32];
            k.copy_from_slice(&b);
            tracing::info!("KOTOBA_VAULT_KEY loaded — email E2E encryption enabled");
            Some(k)
        });
        if vault_key.is_none() {
            tracing::info!("KOTOBA_VAULT_KEY not set — email features disabled");
        }

        // CC embed client — optional; enables vector search over Common Crawl data
        let cc_embed_client: Option<Arc<dyn EmbedClient>> =
            HttpEmbedClient::from_env().ok().map(|c| Arc::new(c) as Arc<dyn EmbedClient>);
        if cc_embed_client.is_some() {
            tracing::info!("CC embed client enabled (KOTOBA_EMBED_URL)");
        }

        Ok(Self {
            version: env!("CARGO_PKG_VERSION"),
            journal,
            shelf,
            vault,
            neighborhood,
            local_node_id,
            executor,
            udf,
            router,
            gossip_tx:      None,
            pregel_runner:  None,
            inference_engine,
            block_store,
            quad_store,
            ipfs_pin,
            secure_vault,
            vault_key,
            agent_sessions:  Arc::new(tokio::sync::RwLock::new(HashMap::new())),
            cc_embed_client,
        })
    }

    /// Replay Journal WAL into the in-memory QuadStore Arrangement.
    ///
    /// Must be called once after `KotobaState::new()` and before serving
    /// requests.  When the Journal is backed by B2 this recovers all quads
    /// written in previous runs; with in-memory-only Journal it is a no-op.
    pub async fn replay_wal(&self) {
        self.quad_store.replay_from_journal().await;
    }

    /// Attach a GossipSub outbound channel after construction.
    pub fn attach_gossip(mut self, tx: tokio::sync::mpsc::Sender<(String, Vec<u8>)>) -> Self {
        self.gossip_tx = Some(tx);
        self
    }

    /// Attach the distributed Pregel runner after swarm setup.
    pub fn attach_pregel(mut self, runner: DistributedPregelRunner) -> Self {
        self.pregel_runner = Some(Arc::new(tokio::sync::Mutex::new(runner)));
        self
    }

    /// Publish a Quad assert to the KSE Journal (fine SPO topic) and,
    /// if the swarm is active, also propagate via GossipSub on the coarse
    /// `"quad/assert"` topic so peers can ingest without subscribing to
    /// every specific SPO address.
    ///
    /// Returns the JournalEntry CID string.
    pub async fn journal_assert(&self, quad: &Quad) -> String {
        let object_str = format!("{:?}", quad.object);
        let topic = Topic::quad_spo(
            &quad.graph.to_multibase(),
            &quad.subject.to_multibase(),
            &quad.predicate,
            &object_str,
        );
        let payload = serde_json::to_vec(quad).unwrap_or_default();

        // Gossip on a coarse topic so peers can subscribe once and receive all asserts.
        // Channel carries raw KSE names (no "kotoba/" prefix); KotobaSwarm::publish adds it.
        if let Some(tx) = &self.gossip_tx {
            tx.try_send(("quad/assert".to_string(), payload.clone())).ok();
        }

        let entry = self.journal.publish(topic, Bytes::from(payload)).await;
        entry.cid.to_multibase()
    }

    /// Publish a Quad retract to the KSE Journal.
    pub async fn journal_retract(&self, quad: &Quad) -> String {
        let topic   = Topic(format!("kotoba/retract/{}/{}/{}", quad.graph, quad.subject, quad.predicate));
        let payload = serde_json::to_vec(quad).unwrap_or_default();

        // Gossip retract events on a coarse topic as well.
        if let Some(tx) = &self.gossip_tx {
            tx.try_send(("quad/retract".to_string(), payload.clone())).ok();
        }

        let entry = self.journal.publish(topic, Bytes::from(payload)).await;
        entry.cid.to_multibase()
    }
}

/// Optionally wrap a concrete `BlockStore` in a `BudgetedBlockStore`, then box it.
///
/// Accepts the concrete value (not `Arc<S>`) because `BudgetedBlockStore<S>`
/// requires `S: BlockStore + Sized` — it cannot wrap a `dyn` or `Arc<dyn>`.
fn maybe_wrap<S: BlockStore + Send + Sync + 'static>(
    inner:  S,
    budget: Option<usize>,
) -> Arc<dyn BlockStore + Send + Sync> {
    match budget {
        Some(b) if b > 0 => {
            tracing::info!(budget_bytes = b, "BlockStore: BudgetedBlockStore LRU eviction enabled");
            Arc::new(BudgetedBlockStore::new(inner, b))
        }
        _ => Arc::new(inner),
    }
}

/// Generate a deterministic-ish seed for the ephemeral dev NodeId.
/// Production: load from persisted Ed25519 key in Shelf/Keychain.
fn rand_seed() -> [u8; 32] {
    use std::time::{SystemTime, UNIX_EPOCH};
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    let hash = blake3::hash(&ts.to_le_bytes());
    *hash.as_bytes()
}
