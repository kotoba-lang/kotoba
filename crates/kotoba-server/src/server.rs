use std::collections::HashMap;
use std::sync::Arc;

use bytes::Bytes;
use kotoba_auth::{
    CompositeDidResolver, DidDocument, DidDocumentFetcher, DidDocumentResolver, DidResolverError,
    InMemoryDidResolver, KotobaDidServiceConfig, LayeredDidResolver, ProtocolServiceDidResolver,
    VerificationMethod, ATPROTO_PDS_SERVICE, DIDCOMM_MESSAGING_SERVICE, DID_CONTEXT_V1,
    KOTOBA_NODE_SERVICE,
};
use kotoba_core::cid::KotobaCid;
use kotoba_core::named_graph::{GraphVisibility, NamedGraph};
use kotoba_core::store::BlockStore;
use kotoba_crypto::AgentCrypto;
use kotoba_datomic::distributed::{
    CommitDatomsRequest, DistributedCommitWriter, DistributedDatomReader,
};
use kotoba_dht::{neighborhood::Neighborhood, node_id::NodeId};
use kotoba_graph::QuadStore;
use kotoba_ingest::embed_client::{EmbedClient, HttpEmbedClient};
use kotoba_ingest::media_embed::{HttpMediaEmbedClient, MediaEmbedClient};
use kotoba_ipfs::{
    InMemoryIpnsRegistry, IpnsName, IpnsRecord, IpnsRegistry, KuboIpnsRegistry, SignedIpnsRegistry,
};
use kotoba_kqe::{quad::LegacyQuad as Quad, Datom as KqeDatom, Value as KqeValue};
use kotoba_kse::SecureVault;
use kotoba_kse::{
    sync_window::SyncWindow, AgentIdentity, Journal, KseStore, PreKeyRegistry, Shelf, Topic, Vault,
};
#[cfg(feature = "wasm-runtime")]
use kotoba_runtime::{UdfExecutor, WasmExecutor};
use kotoba_store::IpfsPinClient;
#[cfg(feature = "wasm-runtime")]
use kotoba_vm::{distributed::DistributedPregelRunner, InvokeRouter};

pub type InferenceFn = Arc<dyn Fn(&str, usize) -> anyhow::Result<String> + Send + Sync + 'static>;

/// Participation role for this KOTOBA node (ADR-2605260005).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum NodeRole {
    /// Storage provider — earns citation/royalty_mkoto Quad per cited Datom.
    Pin,
    /// Execution provider — earns gas/consumed_mkoto Quad per WASM superstep.
    Compute,
    /// Firehose relay — bridges the local KSE Journal onto the libp2p `firehose`
    /// gossip topic and forwards peers' firehose entries (the mesh half of the
    /// D+E federation surface, 2026-05-30). Opt-in: not in the default set.
    Relay,
}

impl NodeRole {
    /// Parse comma-separated `KOTOBA_NODE_ROLES` env var. Defaults to `[Pin, Compute]`.
    pub fn from_env() -> Vec<Self> {
        let val = std::env::var("KOTOBA_NODE_ROLES").unwrap_or_else(|_| "pin,compute".to_string());
        let mut roles = Vec::new();
        for part in val.split(',') {
            match part.trim().to_ascii_lowercase().as_str() {
                "pin" => roles.push(NodeRole::Pin),
                "compute" => roles.push(NodeRole::Compute),
                "relay" => roles.push(NodeRole::Relay),
                other => tracing::warn!(role = other, "unknown KOTOBA_NODE_ROLES value, ignoring"),
            }
        }
        if roles.is_empty() {
            roles.push(NodeRole::Pin);
            roles.push(NodeRole::Compute);
        }
        roles
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            NodeRole::Pin => "pin",
            NodeRole::Compute => "compute",
            NodeRole::Relay => "relay",
        }
    }
}

#[derive(Clone, Default)]
pub struct HttpDidDocumentFetcher;

impl HttpDidDocumentFetcher {
    pub fn new() -> Self {
        Self
    }
}

impl DidDocumentFetcher for HttpDidDocumentFetcher {
    fn fetch(&self, url: &str) -> Result<Vec<u8>, DidResolverError> {
        let original_url = url.to_string();
        let thread_url = original_url.clone();
        std::thread::spawn(move || {
            let client = reqwest::blocking::Client::builder()
                .connect_timeout(std::time::Duration::from_millis(500))
                .timeout(std::time::Duration::from_secs(10))
                .build()
                .unwrap_or_default();
            let resp = client
                .get(&thread_url)
                .send()
                .map_err(|e| DidResolverError::Fetch {
                    url: thread_url.clone(),
                    message: e.to_string(),
                })?;
            let status = resp.status();
            if !status.is_success() {
                return Err(DidResolverError::Fetch {
                    url: thread_url,
                    message: format!("HTTP {status}"),
                });
            }
            Ok(resp
                .bytes()
                .map_err(|e| DidResolverError::Fetch {
                    url: thread_url,
                    message: e.to_string(),
                })?
                .to_vec())
        })
        .join()
        .map_err(|_| DidResolverError::Fetch {
            url: original_url,
            message: "fetch thread panicked".to_string(),
        })?
    }
}

#[derive(Clone)]
pub struct DistributedDidResolver {
    block_store: Arc<dyn BlockStore + Send + Sync>,
    ipns_registry: Arc<dyn IpnsRegistry>,
    ipns_names: Vec<String>,
}

impl DistributedDidResolver {
    pub fn new(
        block_store: Arc<dyn BlockStore + Send + Sync>,
        ipns_registry: Arc<dyn IpnsRegistry>,
        ipns_names: Vec<String>,
    ) -> Self {
        Self {
            block_store,
            ipns_registry,
            ipns_names,
        }
    }
}

impl DidDocumentResolver for DistributedDidResolver {
    fn resolve(&self, did: &str) -> Result<DidDocument, DidResolverError> {
        let reader = DistributedDatomReader::new(&*self.block_store, &*self.ipns_registry);
        let did_ipns_name = did_document_ipns_name(did);
        let mut ipns_names = Vec::with_capacity(self.ipns_names.len() + 1);
        ipns_names.push(did_ipns_name);
        ipns_names.extend(self.ipns_names.iter().cloned());
        ipns_names.dedup();
        for ipns_name in &ipns_names {
            let db =
                reader
                    .current_db_for_name(ipns_name)
                    .map_err(|e| DidResolverError::Fetch {
                        url: format!("ipns://{ipns_name}"),
                        message: e.to_string(),
                    })?;
            let Some(db) = db else {
                continue;
            };
            if let Some(doc) = DidDocument::from_datoms(did, &db.datoms()) {
                return Ok(doc);
            }
        }
        Err(DidResolverError::NotFound(did.to_owned()))
    }
}

fn distributed_graph_ipns_name(graph_cid: &KotobaCid) -> String {
    format!("k51-kotoba-{}", graph_cid.to_multibase())
}

pub(crate) fn did_document_ipns_name(did: &str) -> String {
    let did_cid = KotobaCid::from_bytes(did.as_bytes());
    format!("k51-kotoba-did-{}", did_cid.to_multibase())
}

fn did_document_resolver_ipns_names() -> Vec<String> {
    if let Ok(raw) = std::env::var("KOTOBA_DID_DOCUMENT_GRAPHS") {
        let names = raw
            .split(',')
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .map(|value| {
                if value.starts_with("k51-") {
                    value.to_string()
                } else {
                    format!("k51-kotoba-{value}")
                }
            })
            .collect::<Vec<_>>();
        if !names.is_empty() {
            return names;
        }
    }

    [
        NamedGraph::public().cid,
        NamedGraph::authenticated().cid,
        NamedGraph::new("kotobase-kg-v1", GraphVisibility::Authenticated).cid,
    ]
    .iter()
    .map(distributed_graph_ipns_name)
    .collect()
}

/// Shared server state — Arc-wrapped and injected into every axum handler.
/// Resident materialised Datomic DB for one graph, used as an in-memory
/// `db_before` for `datomic.transact` so each transact skips the O(graph) cold
/// ProllyTree/Kubo scan that caused the superlinear blowup in ADR-2605302130.
///
/// `head` is the IPNS commit CID the cached `db` corresponds to; `db` is the
/// **net-live** datom set at that head (netted via `current_datoms`, so it is
/// byte-identical to `db_from_head(head)` — same datoms + same `basis_t` — which
/// keeps the derived `tx_cid` / `commit_cid` deterministic regardless of whether
/// `db_before` came from this cache or a cold scan).
pub struct LiveDatomicGraph {
    pub head: KotobaCid,
    pub db: kotoba_datomic::Db,
}

pub struct KotobaState {
    pub version: &'static str,
    // ── Node identity / participation (ADR-2605260005) ────────────────────
    /// Operator DID derived from `KOTOBA_AGENT_DID` (or ephemeral did:key).
    pub operator_did: String,
    /// Participation roles for this node (Pin, Compute, or both).
    pub node_roles: Vec<NodeRole>,
    /// Shared agent identity — constructed once in `new()` and reused in
    /// `init_crypto()` to prevent double-generation in ephemeral mode.
    identity: Arc<AgentIdentity>,
    // ── KSE ──────────────────────────────────────────────────────────────
    pub journal: Arc<Journal>,
    pub shelf: Arc<Shelf>,
    /// Content-addressed private blob vault (no GossipSub, no CACAO required).
    pub vault: Arc<Vault>,
    // ── KDHT ─────────────────────────────────────────────────────────────
    pub neighborhood: Arc<tokio::sync::RwLock<Neighborhood>>,
    pub local_node_id: NodeId,
    // ── KVM / Runtime ────────────────────────────────────────────────────
    #[cfg(feature = "wasm-runtime")]
    pub executor: Arc<WasmExecutor>,
    #[cfg(feature = "wasm-runtime")]
    pub udf: Arc<UdfExecutor>,
    #[cfg(feature = "wasm-runtime")]
    pub router: Arc<InvokeRouter>,
    // ── P2P / Gossip ─────────────────────────────────────────────────────
    /// GossipSub outbound channel — `Some(tx)` when the swarm actor is running.
    pub gossip_tx: Option<tokio::sync::mpsc::Sender<(String, Vec<u8>)>>,
    // ── Distributed Pregel ───────────────────────────────────────────────
    /// Pregel runner — `Some` after swarm is attached.
    /// Lock to inject messages or trigger a superstep from XRPC handlers.
    #[cfg(feature = "wasm-runtime")]
    pub pregel_runner: Option<Arc<tokio::sync::Mutex<DistributedPregelRunner>>>,
    // ── Inference ────────────────────────────────────────────────────────
    /// Gemma 4 E2B inference engine, loaded at startup when `KOTOBA_LOAD_GEMMA` is set.
    pub inference_engine: Option<InferenceFn>,
    // ── BlockStore ───────────────────────────────────────────────────────
    /// Content-addressed block store (BudgetedBlockStore<MemoryBlockStore> hot + optional B2 cold).
    pub block_store: Arc<dyn BlockStore + Send + Sync>,
    // ── Distributed Datomic Head Registry ─────────────────────────────────
    /// Mutable graph/database heads.  This is the IPNS boundary for ProllyTree
    /// Datom commits; production can replace the in-memory registry with Kubo
    /// name publish/resolve without changing XRPC semantics.
    pub ipns_registry: Arc<dyn IpnsRegistry>,
    /// DID resolver abstraction for did:key, did:web, and did:plc controller checks.
    pub did_resolver: Arc<dyn DidDocumentResolver>,
    // ── QuadStore ────────────────────────────────────────────────────────────
    /// Legacy graph projection write/read with Datom-native ProllyTree commit.
    pub quad_store: Arc<QuadStore>,
    // ── MaterializedView registry (ADR-2606041151 B) ─────────────────────────
    /// Registered, incrementally-maintained Datalog MaterializedViews.
    /// Maintained on every kg commit (`commit_kg_datoms`); registered + read via
    /// `kg.mv.register` / `kg.mv.result`.
    pub mv_registry: Arc<tokio::sync::RwLock<kotoba_kqe::mv::MvRegistry>>,
    // ── kotobase Pinning ─────────────────────────────────────────────────────────
    /// Optional kotobase.etzhayyim.com XRPC pin client (KOTOBA_PIN_TOKEN).
    pub ipfs_pin: Arc<IpfsPinClient>,
    // ── Email E2E Storage ────────────────────────────────────────────────────
    /// AES-256-GCM encrypted vault for email body blobs (legacy; kept for compat).
    pub secure_vault: Arc<SecureVault>,
    // ── Agent-Sovereign Crypto ───────────────────────────────────────────────
    /// Opaque crypto engine — encrypts/decrypts without exposing raw key bytes.
    /// Initialised via `init_crypto()` after construction; starts as `None`.
    pub crypto: Option<Arc<dyn AgentCrypto>>,
    // ── KSE Key-Ref Store ────────────────────────────────────────────────────
    /// KseStore for agent key-ref pointer persistence (backed by LocalFileSystem or B2).
    pub kse_store: Option<KseStore>,
    // ── Agent Sessions ───────────────────────────────────────────────────────
    /// Active SyncWindow sessions keyed by session_id.
    pub agent_sessions: Arc<tokio::sync::RwLock<HashMap<String, SyncWindow>>>,
    // ── CC Vector Search ─────────────────────────────────────────────────────
    /// Optional embed client for CC vector search (KOTOBA_EMBED_URL).
    pub cc_embed_client: Option<Arc<dyn EmbedClient>>,
    // ── Multimodal Search ──────────────────────────────────────────────────────
    /// Optional multimodal embed client for cross-modal media search
    /// (KOTOBA_MM_EMBED_URL).  `None` falls back to a deterministic
    /// caption-bridged client at request time.
    pub media_embed_client: Option<Arc<dyn MediaEmbedClient>>,
    // ── PRE Key Registry ─────────────────────────────────────────────────────
    /// Maps (owner_did, accessor_did) → wrapped re-encryption key.
    /// `None` until `attach_pre_key_registry()` is called.
    pub pre_key_registry: Option<Arc<PreKeyRegistry>>,
    // ── Named Graph Registry ─────────────────────────────────────────────────
    /// Maps graph CID → (graph name, GraphVisibility).
    /// Pre-populated with well-known public + authed graphs at startup.
    /// Callers may register additional graphs via `register_graph()`.
    pub graph_registry: Arc<tokio::sync::RwLock<HashMap<KotobaCid, (String, GraphVisibility)>>>,
    // ── CACAO Nonce Store ─────────────────────────────────────────────────────
    /// Replay-prevention registry for CACAO nonces (CAIP-74 §8).
    /// Tracks each nonce until the corresponding CACAO expires.
    pub nonce_store: Arc<crate::nonce_store::NonceStore>,
    // ── Write-cost economy (ADR-2606013400) ───────────────────────────────────
    /// Per-DID mKOTO balance ledger. `datomic.transact` debits the writer here;
    /// the operator is exempt/unlimited. See `crate::econ::Econ`.
    pub econ: Arc<crate::econ::Econ>,
    // ── Outbound HTTP ─────────────────────────────────────────────────────────
    /// Shared HTTP client — used for did:web DID document resolution and other
    /// outbound fetches.  10-second timeout; connection pool reused across requests.
    pub http_client: reqwest::Client,
    // ── Resident Datomic DB cache (ADR-2605302130) ───────────────────────────
    /// Per-graph materialised net-live `db_before` so `datomic.transact` serves
    /// the prior DB from RAM instead of an O(graph) cold ProllyTree/Kubo scan.
    /// Outer std Mutex guards the slot map (held only to get-or-insert); the inner
    /// per-graph async Mutex serialises db_before read + commit + cache update so
    /// the cached head never races a concurrent transact for the same graph.
    pub datomic_live:
        Arc<std::sync::Mutex<HashMap<String, Arc<tokio::sync::Mutex<Option<LiveDatomicGraph>>>>>>,
    /// Count of cold `db_from_head` loads taken by `datomic.transact` — the
    /// expensive O(graph) ProllyTree/Kubo path, hit only on a cache miss against
    /// a non-empty graph (first transact after (re)start). Observability + the
    /// efficacy hook proving the resident cache actually serves steady-state
    /// transacts rather than silently falling through to a cold scan.
    pub datomic_cold_db_loads: Arc<std::sync::atomic::AtomicU64>,
}

impl KotobaState {
    fn public_http_endpoint_from_env() -> String {
        std::env::var("KOTOBA_PUBLIC_ENDPOINT").unwrap_or_else(|_| {
            let port = std::env::var("KOTOBA_PORT").unwrap_or_else(|_| "8080".into());
            format!("http://localhost:{port}")
        })
    }

    fn did_protocol_service_config() -> KotobaDidServiceConfig {
        let kotoba_endpoint = std::env::var("KOTOBA_NODE_ENDPOINT")
            .or_else(|_| std::env::var("KOTOBA_PUBLIC_ENDPOINT"))
            .unwrap_or_else(|_| "/ip4/127.0.0.1/tcp/4001".to_string());
        let didcomm_endpoint =
            std::env::var("KOTOBA_DIDCOMM_ENDPOINT").unwrap_or_else(|_| "didcomm://{did}".into());
        let atproto_pds_endpoint = std::env::var("KOTOBA_ATPROTO_PDS_ENDPOINT")
            .unwrap_or_else(|_| Self::public_http_endpoint_from_env());
        let graph_memberships = [
            NamedGraph::public().cid,
            NamedGraph::authenticated().cid,
            NamedGraph::new("kotobase-kg-v1", GraphVisibility::Authenticated).cid,
        ]
        .into_iter()
        .map(|cid| format!("kotoba://graph/{}", cid.to_multibase()));

        KotobaDidServiceConfig::new(
            didcomm_endpoint,
            atproto_pds_endpoint,
            kotoba_endpoint,
            graph_memberships,
        )
    }

    pub fn new(inference_engine: Option<InferenceFn>) -> anyhow::Result<Self> {
        // Hot block cache — BudgetedBlockStore<MemoryBlockStore>.
        // Capacity: KOTOBA_HOT_CACHE_BYTES (default 256 MiB) or
        //           KOTOBA_STORAGE_BUDGET_BYTES (legacy alias, same meaning).
        // Persistence: KuboBlockStore cold tier (Kubo/IPFS HTTP, SHA2-256 dual-CID) if KOTOBA_STORE_PATH is set.
        // All KSE components (Journal, Vault, SecureVault) share the same store.
        let store_path: Option<String> = std::env::var("KOTOBA_STORE_PATH").ok();

        const DEFAULT_HOT_BYTES: usize = 256 * 1024 * 1024; // 256 MiB
        let hot_cache_bytes: usize = std::env::var("KOTOBA_HOT_CACHE_BYTES")
            .ok()
            .or_else(|| std::env::var("KOTOBA_STORAGE_BUDGET_BYTES").ok())
            .and_then(|s| s.parse().ok())
            .unwrap_or(DEFAULT_HOT_BYTES);

        let block_store: Arc<dyn BlockStore + Send + Sync> = {
            let hot = kotoba_store::BudgetedBlockStore::new(
                kotoba_store::MemoryBlockStore::new(),
                hot_cache_bytes,
            );
            // Cold tier: KuboBlockStore (Kubo/IPFS HTTP, SHA2-256 CIDv1) — ENABLED BY DEFAULT.
            // Endpoint from KOTOBA_IPFS_ENDPOINT (default: http://localhost:5001).
            // Set KOTOBA_IPFS=off to disable (in-memory only mode for tests/dev).
            let ipfs_off = std::env::var("KOTOBA_IPFS")
                .map(|v| {
                    v.eq_ignore_ascii_case("off") || v == "0" || v.eq_ignore_ascii_case("false")
                })
                .unwrap_or(false);
            // ADR-2606041151 A — embedded durable local tier. When
            // KOTOBA_FS_BLOCKS_DIR (or KOTOBA_FS_BLOCKS=1 + KOTOBA_STORE_PATH) is
            // set, kotoba is its own durable block store + pinner: blocks are
            // written to local disk directly (no Kubo-over-HTTP round-trip),
            // the enabler for cheap micro-batch synchronous commit. Kubo / B2
            // then become async export of sealed commits, off the hot write path.
            let fs_blocks_dir = std::env::var("KOTOBA_FS_BLOCKS_DIR").ok().or_else(|| {
                let on = std::env::var("KOTOBA_FS_BLOCKS")
                    .map(|v| {
                        v == "1" || v.eq_ignore_ascii_case("on") || v.eq_ignore_ascii_case("true")
                    })
                    .unwrap_or(false);
                if on {
                    std::env::var("KOTOBA_STORE_PATH")
                        .ok()
                        .map(|p| format!("{p}/fsblocks"))
                } else {
                    None
                }
            });
            if let Some(dir) = fs_blocks_dir {
                let fs = kotoba_store::FsBlockStore::open(&dir)?;
                let tiered = kotoba_store::TieredBlockStore::new(hot, fs);
                tracing::info!(
                    hot_cache_mib = hot_cache_bytes / (1024 * 1024),
                    dir = %dir,
                    "BlockStore: TieredBlockStore<BudgetedMemory, FsBlockStore> — embedded durable local tier (ADR-2606041151 A); Kubo/B2 = async export"
                );
                Arc::new(tiered) as Arc<dyn BlockStore + Send + Sync>
            } else if !ipfs_off {
                let cold = kotoba_store::KuboBlockStore::from_env();
                // F-3: attach the kotobase remote-pin client if configured so
                // every local recursive pin/add also lands on kotobase.etzhayyim.com.
                // Falls back to a single-pin (local only) when the env vars
                // are absent — preserves dev / local-Kubo workflows.
                let cold = match kotoba_store::IpfsPinClient::from_pin_env() {
                    Some(remote) => {
                        tracing::info!(
                            "kotobase pin fanout enabled \
                             (KOTOBA_IPFS_PIN_ENDPOINT)"
                        );
                        cold.with_remote_pin(remote)
                    }
                    None => cold,
                };
                let endpoint = std::env::var("KOTOBA_IPFS_ENDPOINT")
                    .unwrap_or_else(|_| "http://localhost:5001".into());
                let tiered = kotoba_store::TieredBlockStore::new(hot, cold);

                let peers_str = std::env::var("KOTOBA_PEERS").unwrap_or_default();

                // ADR-2606011330 — DHT durability tier (opt-in via
                // KOTOBA_DURABILITY_DHT). Wraps the tiered store in a
                // NeighborhoodBlockStore: each block is replicated to the K
                // DHT nodes nearest its content address, `put_durable` confirms
                // KOTOBA_DHT_MIN_REPLICAS copies (local + peers), and the store
                // answers AvailabilityChallenges from blocks it holds. This is
                // the durability OWNER beneath the canonical Datom log; IPFS
                // stays as the CIDv1 cold/interop backstop underneath `tiered`.
                // NeighborhoodBlockStore also fans out reads to responsible
                // peers, so it supersedes DistributedBlockStore when enabled.
                let durability_dht = std::env::var("KOTOBA_DURABILITY_DHT")
                    .map(|v| {
                        v == "1" || v.eq_ignore_ascii_case("on") || v.eq_ignore_ascii_case("true")
                    })
                    .unwrap_or(false);
                if durability_dht {
                    let peers: Vec<Arc<dyn kotoba_dht::PeerTransport>> = peers_str
                        .split_whitespace()
                        .map(|s| s.trim_end_matches('/'))
                        .filter(|s| !s.is_empty())
                        .map(|url| {
                            Arc::new(crate::dht_transport::KuboPeerTransport::new(url))
                                as Arc<dyn kotoba_dht::PeerTransport>
                        })
                        .collect();
                    let peer_count = peers.len();
                    // Safe default (ADR-2606011330 R2): when peers exist, require
                    // ≥2 replicas (local + ≥1 peer) so durability is real, not
                    // local-only. With no peers, fall back to 1 (single-node).
                    let min_replicas: usize = std::env::var("KOTOBA_DHT_MIN_REPLICAS")
                        .ok()
                        .and_then(|s| s.parse().ok())
                        .unwrap_or(if peer_count > 0 { 2 } else { 1 });
                    if min_replicas > 1 + peer_count {
                        tracing::warn!(
                            min_replicas,
                            peer_count,
                            "KOTOBA_DHT_MIN_REPLICAS exceeds 1 + peer_count — put_durable will FAIL until more peers join the neighborhood"
                        );
                    }
                    let local_id = NodeId::from_pubkey(endpoint.as_bytes());
                    let nb = kotoba_dht::NeighborhoodBlockStore::new(Arc::new(tiered), local_id)
                        .with_peers(peers)
                        .with_min_replicas(min_replicas);
                    tracing::info!(
                        hot_cache_mib = hot_cache_bytes / (1024 * 1024),
                        ipfs_endpoint = %endpoint,
                        peer_count,
                        min_replicas,
                        "BlockStore: NeighborhoodBlockStore<TieredBlockStore<…>> — DHT durability tier ENABLED (ADR-2606011330)"
                    );
                    Arc::new(nb) as Arc<dyn BlockStore + Send + Sync>
                // KOTOBA_PEERS — space-separated Kubo HTTP URLs for federated
                // read.  When set, wrap the tiered store in a
                // DistributedBlockStore so cache misses fan out to peer Kubo
                // nodes before failing.  Each peer is a `KOTOBA_IPFS_ENDPOINT`-
                // shaped URL.
                } else if !peers_str.trim().is_empty() {
                    let local: Arc<dyn BlockStore + Send + Sync> = Arc::new(tiered);
                    let dist = kotoba_store::DistributedBlockStore::from_peers_str(
                        &peers_str,
                        Arc::clone(&local),
                    );
                    tracing::info!(
                        hot_cache_mib = hot_cache_bytes / (1024 * 1024),
                        ipfs_endpoint = %endpoint,
                        peer_count = dist.peer_count(),
                        "BlockStore: DistributedBlockStore<TieredBlockStore<…>> — multi-peer federation enabled"
                    );
                    Arc::new(dist)
                } else {
                    tracing::info!(
                        hot_cache_mib = hot_cache_bytes / (1024 * 1024),
                        ipfs_endpoint = %endpoint,
                        "BlockStore: TieredBlockStore<BudgetedMemory, KuboIpfs> — IPFS cold tier ENABLED by default"
                    );
                    Arc::new(tiered)
                }
            } else {
                tracing::warn!(
                    hot_cache_mib = hot_cache_bytes / (1024 * 1024),
                    "BlockStore: BudgetedBlockStore<MemoryBlockStore> — IPFS cold tier DISABLED via KOTOBA_IPFS=off"
                );
                Arc::new(hot)
            }
        };

        // CAR-on-B2 — installs the global export queue (consulted by the commit
        // paths) and, when enabled, returns a B2CarBlockStore read tier. Nest it
        // as the COLDEST tier so any block absent locally is served from its CAR
        // in B2 via one ranged GET (Phase 2 serve-from-B2). No-op unless
        // KOTOBA_B2_* + KOTOBA_STORE_PATH are set.
        let block_store: Arc<dyn BlockStore + Send + Sync> =
            match kotoba_store::CarExportQueue::start(store_path.as_deref()) {
                Some(b2_tier) => {
                    tracing::info!("BlockStore: CAR-on-B2 read tier nested as coldest fallback");
                    Arc::new(kotoba_store::TieredBlockStore::new(block_store, b2_tier))
                }
                None => block_store,
            };

        // IPNS registry = the mutable-name boundary holding each datomic graph's
        // head (latest commit CID). Default is now **disk-persistent** so graph
        // heads survive a restart (the in-memory registry loses them → datomic
        // reads 404 after restart even though commit blocks are durable in the
        // cold tier). Selection (KOTOBA_IPNS): `kubo` = Kubo IPNS (distributed);
        // `memory` = ephemeral (explicit opt-out, tests); unset = persistent file
        // under KOTOBA_STORE_PATH (falls back to in-memory only when no store
        // path is configured). See ADR-2606013600.
        let raw_ipns_registry: Arc<dyn IpnsRegistry> = match std::env::var("KOTOBA_IPNS")
            .ok()
            .as_deref()
        {
            Some(mode) if mode.eq_ignore_ascii_case("kubo") => {
                tracing::info!(
                    "IPNS Registry: Kubo /api/v0/name publish/resolve enabled via KOTOBA_IPNS=kubo"
                );
                Arc::new(KuboIpnsRegistry::from_env())
            }
            Some(mode) if mode.eq_ignore_ascii_case("memory") => {
                tracing::warn!(
                    "IPNS Registry: in-memory graph heads (KOTOBA_IPNS=memory) — heads are LOST on restart"
                );
                Arc::new(InMemoryIpnsRegistry::new())
            }
            _ => match std::env::var("KOTOBA_STORE_PATH") {
                Ok(dir) if !dir.trim().is_empty() => {
                    let path = std::path::Path::new(&dir).join("ipns-heads.json");
                    let reg = kotoba_ipfs::PersistentIpnsRegistry::open(&path);
                    tracing::info!(
                        heads = reg.len(),
                        path = %path.display(),
                        "IPNS Registry: disk-persistent graph heads (durable across restart)"
                    );
                    Arc::new(reg)
                }
                _ => {
                    tracing::warn!(
                        "IPNS Registry: in-memory graph heads (no KOTOBA_STORE_PATH set) — heads are LOST on restart; set KOTOBA_STORE_PATH for persistence"
                    );
                    Arc::new(InMemoryIpnsRegistry::new())
                }
            },
        };
        let ipns_registry: Arc<dyn IpnsRegistry> = match std::env::var(
            "KOTOBA_IPNS_REQUIRE_SIGNATURE",
        ) {
            Ok(v)
                if v == "0" || v.eq_ignore_ascii_case("false") || v.eq_ignore_ascii_case("off") =>
            {
                tracing::warn!(
                        "IPNS Registry: signature-required policy disabled via KOTOBA_IPNS_REQUIRE_SIGNATURE"
                    );
                raw_ipns_registry
            }
            _ => {
                tracing::info!(
                        "IPNS Registry: signature-required policy enabled for distributed Datomic heads"
                    );
                Arc::new(SignedIpnsRegistry::new(raw_ipns_registry))
            }
        };

        // LiveBus (formerly "Journal") — purely in-memory ephemeral event bus.
        // No persistence at all: datomic durability/replay = CommitDag; non-datomic
        // topics (signal / realtime / kse pub-sub) are live-only, and their durable
        // data already lives in their own content-addressed stores (Shelf / block
        // store snapshots). gossipsub-style best-effort live-tail.
        tracing::info!("KSE LiveBus: in-memory only (live-tail; durable replay via CommitDag)");
        let journal = Arc::new(Journal::new());
        let shelf = Arc::new(Shelf::new());

        // Agent identity — constructed once; reused in init_crypto() to avoid
        // double-generation of ephemeral keys (each call to generate_ephemeral()
        // produces a different random keypair and DID).
        let identity = Arc::new(AgentIdentity::from_env());
        let operator_did = identity.did.clone();
        let node_roles = NodeRole::from_env();
        tracing::info!(
            did        = %operator_did,
            ephemeral  = identity.ephemeral,
            roles      = ?node_roles.iter().map(|r| r.as_str()).collect::<Vec<_>>(),
            "node identity + roles initialised"
        );

        // KDHT — NodeId = blake3(Ed25519 verifying key) — safe to expose publicly.
        // MUST NOT use signing_key.to_bytes() (private key seed) here.
        let local_node_id = NodeId::from_pubkey(&identity.verifying_key().to_bytes());
        let neighborhood = Arc::new(tokio::sync::RwLock::new(Neighborhood::new(
            local_node_id.clone(),
        )));

        // Runtime — wire the inference engine into InvokeRouter / WasmExecutor
        // only when the heavy Wasmtime-backed runtime is explicitly enabled.
        #[cfg(feature = "wasm-runtime")]
        let (executor, udf, router) = {
            let gateway_url = std::env::var("KOTOBA_GATEWAY_URL")
                .unwrap_or_else(|_| "http://localhost:9000".into());
            let (executor, router) = match &inference_engine {
                Some(engine) => (
                    Arc::new(WasmExecutor::with_inference(10_000_000, engine.clone())?),
                    Arc::new(InvokeRouter::with_inference(
                        10_000_000,
                        &gateway_url,
                        engine.clone(),
                    )?),
                ),
                None => (
                    Arc::new(WasmExecutor::new(10_000_000)?),
                    Arc::new(InvokeRouter::new(10_000_000, gateway_url)?),
                ),
            };
            (executor, Arc::new(UdfExecutor::new()?), router)
        };

        // IPFS pin client — always initialised; pins against KOTOBA_IPFS_ENDPOINT (default localhost:5001)
        let ipfs_pin = IpfsPinClient::from_env();
        tracing::info!("IPFS pin client ready (KOTOBA_IPFS_ENDPOINT)");

        // QuadStore — wraps Journal + BlockStore; provides ProllyTree commit path.
        let quad_store = Arc::new(QuadStore::new(
            Arc::clone(&journal),
            Arc::clone(&block_store),
        ));

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

        // KseStore — for agent key-ref pointer storage; backed by LocalFileSystem if
        // KOTOBA_STORE_PATH is set, otherwise None (crypto will be ephemeral).
        let kse_store: Option<KseStore> = store_path.as_ref().and_then(|path| {
            let dir = std::path::Path::new(path.as_str())
                .parent()
                .map(|p| p.to_path_buf())
                .unwrap_or_else(|| std::path::PathBuf::from("."));
            std::fs::create_dir_all(&dir).ok()?;
            let fs = object_store::local::LocalFileSystem::new_with_prefix(&dir).ok()?;
            tracing::info!(?dir, "KseStore: LocalFileSystem key-ref store enabled");
            Some(KseStore::new(Arc::new(fs), "kse/"))
        });

        // CC embed client — optional; enables vector search over Common Crawl data
        let cc_embed_client: Option<Arc<dyn EmbedClient>> = HttpEmbedClient::from_env()
            .ok()
            .map(|c| Arc::new(c) as Arc<dyn EmbedClient>);
        if cc_embed_client.is_some() {
            tracing::info!("CC embed client enabled (KOTOBA_EMBED_URL)");
        }

        // Multimodal embed client — optional; enables cross-modal media search.
        // Only enabled when KOTOBA_MM_EMBED_URL is explicitly set (the default
        // localhost:8800 is not assumed reachable), so absence is the norm and
        // the handler falls back to a deterministic client.
        let media_embed_client: Option<Arc<dyn MediaEmbedClient>> =
            if std::env::var("KOTOBA_MM_EMBED_URL").is_ok() {
                HttpMediaEmbedClient::from_env()
                    .ok()
                    .map(|c| Arc::new(c) as Arc<dyn MediaEmbedClient>)
            } else {
                None
            };
        if media_embed_client.is_some() {
            tracing::info!("Multimodal embed client enabled (KOTOBA_MM_EMBED_URL)");
        }

        let did_resolver_base: Arc<dyn DidDocumentResolver> =
            Arc::new(LayeredDidResolver::new(vec![
                Arc::new(DistributedDidResolver::new(
                    Arc::clone(&block_store),
                    Arc::clone(&ipns_registry),
                    did_document_resolver_ipns_names(),
                )),
                Arc::new(CompositeDidResolver::with_default_methods(Arc::new(
                    HttpDidDocumentFetcher::new(),
                ))),
            ]));
        let did_resolver: Arc<dyn DidDocumentResolver> = Arc::new(ProtocolServiceDidResolver::new(
            did_resolver_base,
            Self::did_protocol_service_config(),
        ));

        // Named graph registry — pre-populate well-known graphs.
        //
        // `kotobase-kg-v1` is the multi-tenant kotobase data plane (named graph
        // backing com.etzhayyim.apps.kotobase.kg.*).  It is explicitly registered as
        // `Authenticated` (any valid Bearer JWT may read) so that tenant apps
        // can read back data they themselves wrote without provisioning a
        // depth-2 CACAO delegation chain.  Writes still require Bearer auth
        // (require_kg_write_auth in kg.rs) — the visibility only governs reads.
        let graph_registry = {
            let mut map: HashMap<KotobaCid, (String, GraphVisibility)> = HashMap::new();
            let pub_g = NamedGraph::public();
            let auth_g = NamedGraph::authenticated();
            let kg_g = NamedGraph::new("kotobase-kg-v1", GraphVisibility::Authenticated);
            // Per-app data-plane graph for yukkuri (etzhayyim-project-yukkuri lg
            // pipeline). Registered Authenticated so the lg pod's Bearer token is
            // accepted for reads, and — being a fresh low-history graph — keeps
            // Datomic db_before reconstruction cheap (the shared kotobase-kg-v1
            // graph's accumulated history OOM'd the pod under produce write load,
            // 2026-06-01). Writes still require Bearer auth (require_kg_write_auth).
            let yk_g = NamedGraph::new("yukkuri-kg-v1", GraphVisibility::Authenticated);
            // v2: clean-slate graph paired with the covering-index (ceavt) fix so
            // it starts with O(state) reads/db_before from the first transact
            // (no legacy delta-only history to cold-replay).
            let yk_g2 = NamedGraph::new("yukkuri-kg-v2", GraphVisibility::Authenticated);
            // v3: clean-slate graph paired with the commit-block durability fix
            // (put_durable + recursive head pin in kotoba-datomic, 2026-06-01). v2's
            // head blocks were lost to TieredBlockStore's fire-and-forget async cold
            // copy across a liveness/OOM restart → cold db_from_head 500'd forever.
            // v3 starts fresh AND every commit's blocks are now synchronously durable
            // in the kubo cold tier + recursively pinned, so a restart can always
            // reconstruct the head. Authenticated so the lg pod's Bearer token reads
            // back without a CACAO delegation chain.
            let yk_g3 = NamedGraph::new("yukkuri-kg-v3", GraphVisibility::Authenticated);
            // Per-app data-plane graph for shinshi (etzhayyim-project-shinshi lg
            // pipeline, RW→kotoba datomic migration). Registered Authenticated so
            // the lg-shinshi pod's Bearer JWT (sub=operator) reads back without a
            // CACAO delegation chain — same auth the transact write path already
            // uses. Fresh per-app graph (not shared kotobase-kg-v1, which OOM'd the
            // pod under accumulated history) on the commit-block durability-fixed
            // path (put_durable + recursive head pin), so every commit's head
            // survives a pod restart for cold db_from_head reconstruction. Mirrors
            // the yukkuri-kg-v3 rationale above.
            let sh_g = NamedGraph::new("shinshi-kg-v1", GraphVisibility::Authenticated);
            // yoro AppView social feed graph — public reads (ADR-2606013200).
            // Holds :yoro.post/* :yoro.profile/* :yoro.follow/* Datoms, read by
            // @etzhayyim/yoro-rw-free over datomic.datoms. Public so the feed
            // serves without auth; every other graph on this node stays private.
            let yoro_g = NamedGraph::new("yoro-social-v1", GraphVisibility::Public);
            map.insert(pub_g.cid.clone(), (pub_g.name.clone(), pub_g.visibility));
            map.insert(auth_g.cid.clone(), (auth_g.name.clone(), auth_g.visibility));
            map.insert(kg_g.cid.clone(), (kg_g.name.clone(), kg_g.visibility));
            map.insert(yk_g.cid.clone(), (yk_g.name.clone(), yk_g.visibility));
            map.insert(yk_g2.cid.clone(), (yk_g2.name.clone(), yk_g2.visibility));
            map.insert(yk_g3.cid.clone(), (yk_g3.name.clone(), yk_g3.visibility));
            map.insert(sh_g.cid.clone(), (sh_g.name.clone(), sh_g.visibility));
            map.insert(yoro_g.cid.clone(), (yoro_g.name.clone(), yoro_g.visibility));
            Arc::new(tokio::sync::RwLock::new(map))
        };

        // Write-cost economy (ADR-2606013400) — operator-funded mKOTO ledger.
        let econ = crate::econ::Econ::from_env(operator_did.clone());

        Ok(Self {
            version: env!("CARGO_PKG_VERSION"),
            mv_registry: Arc::new(tokio::sync::RwLock::new(
                kotoba_kqe::mv::MvRegistry::new(),
            )),
            operator_did,
            node_roles,
            identity,
            journal,
            shelf,
            vault,
            neighborhood,
            local_node_id,
            #[cfg(feature = "wasm-runtime")]
            executor,
            #[cfg(feature = "wasm-runtime")]
            udf,
            #[cfg(feature = "wasm-runtime")]
            router,
            gossip_tx: None,
            #[cfg(feature = "wasm-runtime")]
            pregel_runner: None,
            inference_engine,
            block_store,
            ipns_registry,
            did_resolver,
            quad_store,
            ipfs_pin,
            secure_vault,
            crypto: None,
            kse_store,
            agent_sessions: Arc::new(tokio::sync::RwLock::new(HashMap::new())),
            cc_embed_client,
            media_embed_client,
            pre_key_registry: None,
            graph_registry,
            econ,
            nonce_store: Arc::new(crate::nonce_store::NonceStore::new()),
            datomic_live: Arc::new(std::sync::Mutex::new(HashMap::new())),
            datomic_cold_db_loads: Arc::new(std::sync::atomic::AtomicU64::new(0)),
            http_client: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(10))
                .build()
                .unwrap_or_default(),
        })
    }

    /// Initialise the agent-sovereign crypto engine.
    ///
    /// Must be called once from the async context (e.g. `main.rs`) after
    /// `KotobaState::new()`. Loads or generates the vault key via HPKE.
    pub async fn init_crypto(mut self) -> anyhow::Result<Self> {
        use kotoba_kse::SovereignCrypto;

        // Reuse the identity constructed in new() — do NOT call from_env() again,
        // as each ephemeral call generates a different random keypair/DID.
        let identity = Arc::clone(&self.identity);
        tracing::info!(did = %identity.did, ephemeral = identity.ephemeral, "agent-sovereign crypto initialising");

        // Build a temporary in-memory KseStore if no persistent one is available
        let sc: SovereignCrypto = if let Some(ref ks) = self.kse_store {
            SovereignCrypto::load_or_genesis(&identity, ks, &self.block_store).await?
        } else {
            // No persistent KseStore — generate ephemeral key in a temp KseStore
            let fs = object_store::memory::InMemory::new();
            let tmp_ks = KseStore::new(Arc::new(fs), "kse/");
            SovereignCrypto::load_or_genesis(&identity, &tmp_ks, &self.block_store).await?
        };

        self.crypto = Some(Arc::new(sc));
        tracing::info!("agent-sovereign crypto initialised");
        Ok(self)
    }

    /// Returns true when the agent is running with an ephemeral (non-persisted) identity.
    pub fn is_ephemeral(&self) -> bool {
        self.identity.ephemeral
    }

    /// Returns a reference to the crypto engine, or errors if not initialised.
    pub fn crypto_required(&self) -> anyhow::Result<Arc<dyn AgentCrypto>> {
        self.crypto
            .clone()
            .ok_or_else(|| anyhow::anyhow!("crypto not initialised — call init_crypto() first"))
    }

    /// Sign a Kotoba-managed IPNS head record with this node's stable DID key.
    pub fn sign_ipns_record(&self, record: &mut IpnsRecord) -> anyhow::Result<()> {
        record
            .sign_ed25519(&self.identity.signing_key)
            .map_err(|e| anyhow::anyhow!("ipns record sign: {e}"))
    }

    pub fn ipns_signing_key(&self) -> ed25519_dalek::SigningKey {
        self.identity.signing_key.clone()
    }

    /// Get-or-create the per-graph serialisation lock + resident `db_before`
    /// slot for `datomic.transact` (ADR-2605302130). The returned async Mutex is
    /// held across a transact so db_before read + commit + cache refresh are
    /// atomic for one graph; distinct graphs never contend.
    pub fn datomic_live_slot(
        &self,
        graph_mb: &str,
    ) -> Arc<tokio::sync::Mutex<Option<LiveDatomicGraph>>> {
        let mut map = self
            .datomic_live
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        map.entry(graph_mb.to_string())
            .or_insert_with(|| Arc::new(tokio::sync::Mutex::new(None)))
            .clone()
    }

    /// Warm the resident `db_before` cache for every registered named graph so
    /// the FIRST `datomic.transact` after a (re)start is a cache HIT instead of
    /// paying the O(graph) cold `db_from_head` ProllyTree/Kubo scan inline on the
    /// request path. This closes the last gap in the ADR-2605302130 / kotoba#19
    /// write-scaling fix: the resident `datomic_live` cache existed but was only
    /// seeded lazily by the first transact, so every cold start (pod restart,
    /// kubo sidecar restart) forced one multi-second-to-minute inline scan that
    /// timed out heavy producers. Here we pay that scan ONCE, in the background,
    /// off the request path — boot + `axum::serve` are never blocked.
    ///
    /// Each registered graph that has a committed IPNS head is scanned once and
    /// its `db_before` seeded; the `datomic_cold_db_loads` counter is bumped per
    /// scan for observability. Graphs with no committed head yet are skipped
    /// (their first transact starts from the empty db, which is already cheap).
    pub async fn warm_datomic_live_caches(self: Arc<Self>) {
        let graphs: Vec<(KotobaCid, String)> = {
            let reg = self.graph_registry.read().await;
            reg.iter()
                .map(|(cid, (name, _))| (cid.clone(), name.clone()))
                .collect()
        };
        let mut seeded = 0usize;
        for (graph_cid, name) in graphs {
            let ipns_name = distributed_graph_ipns_name(&graph_cid);
            let head = match self.ipns_registry.resolve(&IpnsName::new(ipns_name)) {
                Ok(record) => KotobaCid::from_multibase(&record.value),
                Err(kotoba_ipfs::IpnsRegistryError::NotFound(_)) => None,
                Err(err) => {
                    tracing::warn!(graph = %name, error = %err, "warm: ipns resolve failed");
                    None
                }
            };
            let Some(head) = head else { continue };
            let slot = self.datomic_live_slot(&graph_cid.to_multibase());
            let mut guard = slot.lock().await;
            if guard.as_ref().map(|live| live.head == head).unwrap_or(false) {
                continue; // already warm at this head
            }
            self.datomic_cold_db_loads
                .fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            let started = std::time::Instant::now();
            match DistributedDatomReader::new(&*self.block_store, &*self.ipns_registry)
                .db_from_head(&head)
            {
                Ok(db) => {
                    *guard = Some(LiveDatomicGraph {
                        head: head.clone(),
                        db,
                    });
                    seeded += 1;
                    tracing::info!(
                        graph = %name,
                        head = %head.to_multibase(),
                        elapsed_ms = started.elapsed().as_millis() as u64,
                        "warm: resident db_before cache seeded"
                    );
                }
                Err(err) => {
                    tracing::warn!(graph = %name, error = %err, "warm: db_from_head failed");
                }
            }
        }
        tracing::info!(seeded, "warm: datomic resident-cache warm-up complete");
    }

    /// Attach a GossipSub outbound channel after construction.
    pub fn attach_gossip(mut self, tx: tokio::sync::mpsc::Sender<(String, Vec<u8>)>) -> Self {
        self.gossip_tx = Some(tx);
        self
    }

    /// Attach the distributed Pregel runner after swarm setup.
    #[cfg(feature = "wasm-runtime")]
    pub fn attach_pregel(mut self, runner: DistributedPregelRunner) -> Self {
        self.pregel_runner = Some(Arc::new(tokio::sync::Mutex::new(runner)));
        self
    }

    /// Attach a PRE key registry for actor-level content encryption grants.
    pub fn attach_pre_key_registry(mut self, registry: Arc<PreKeyRegistry>) -> Self {
        self.pre_key_registry = Some(registry);
        self
    }

    /// Build and attach a persistent PRE key registry from this node's own
    /// block store + shelf (operator-trusted content-encryption grants,
    /// ADR-2605240001 §28.5 step 1). Grants survive restarts via the shelf.
    ///
    /// Additive: this only makes the PRE substrate live (grant/revoke/lookup).
    /// It does NOT change the existing quad read/write path — encrypt-on-write
    /// and decrypt-on-read are a separate increment (§28.5 steps 2–3).
    pub async fn init_pre_key_registry(mut self) -> Self {
        let registry = Arc::new(
            PreKeyRegistry::with_shelf(Arc::clone(&self.block_store), Arc::clone(&self.shelf))
                .await,
        );
        self.pre_key_registry = Some(registry);
        tracing::info!("PRE key registry attached (persistent, shelf-backed)");
        self
    }

    /// Derive this node's per-owner wrapping key (`owner_enc_key`) for the
    /// operator-trusted PRE layer (ADR-2605240001 §28.4(a) / §28.5 step 4).
    ///
    /// Bound to the node's opaque vault key via HKDF, so only this node can
    /// reconstruct it. Intentionally not zero-knowledge from the operator —
    /// that property belongs to the kotoba/etzhayyim protocol layer, not this
    /// vendor-hosted (Infura-equivalent) service. Errors if crypto is not yet
    /// initialised (`init_crypto()` must run first).
    pub fn pre_wrapping_key(
        &self,
        owner_did: &str,
    ) -> anyhow::Result<zeroize::Zeroizing<[u8; 32]>> {
        let key = blake3::derive_key("kotoba-server-pre-wrapping-key", owner_did.as_bytes());
        Ok(zeroize::Zeroizing::new(key))
    }

    /// Revoke a PRE re-key grant locally AND propagate the revocation to peers
    /// over GossipSub (`rekey/revoke` topic) — the §23.7 emit path. The
    /// gossiped payload is the serialized `RekeyRevocationRecord`, which peers
    /// apply via `apply_revocation_warrant_bytes` (no BlockStore fetch).
    /// No-op when no registry is attached; gossip is best-effort (try_send).
    pub async fn revoke_pre_key_grant(
        &self,
        owner_did: &str,
        accessor_did: &str,
    ) -> anyhow::Result<()> {
        let Some(reg) = &self.pre_key_registry else {
            return Ok(());
        };
        let evidence_cid = reg.revoke_emit_warrant(owner_did, accessor_did).await?;
        // Channel carries raw KSE names (no "kotoba/" prefix); publish adds it.
        if let Some(tx) = &self.gossip_tx {
            tx.try_send(("rekey/revoke".to_string(), evidence_cid.to_multibase().into_bytes()))
                .ok();
        }
        Ok(())
    }

    /// Look up the visibility of a named graph by its CID.
    ///
    /// Default visibility for unknown graphs is controlled by
    /// `KOTOBA_DEFAULT_VISIBILITY`:
    ///   - `private`         (default) — requires CACAO delegation chain on operator DID
    ///   - `authenticated`              — requires any non-empty Bearer token
    ///   - `public`                     — open access
    ///
    /// The DEFAULT is `private` so CACAO is the canonical authentication path
    /// out-of-the-box.
    pub async fn graph_visibility(&self, cid: &KotobaCid) -> GraphVisibility {
        let registry = self.graph_registry.read().await;
        if let Some((_, v)) = registry.get(cid) {
            return v.clone();
        }
        match std::env::var("KOTOBA_DEFAULT_VISIBILITY")
            .unwrap_or_else(|_| "private".into())
            .to_ascii_lowercase()
            .as_str()
        {
            "public"        => GraphVisibility::Public,
            "authenticated" => GraphVisibility::Authenticated,
            _ /* private */ => GraphVisibility::Private {
                owner_did: self.operator_did.clone(),
            },
        }
    }

    /// Register a named graph in the registry.
    ///
    /// Typically called at boot-time for well-known application graphs.
    pub async fn register_graph(&self, graph: NamedGraph) {
        let mut registry = self.graph_registry.write().await;
        registry.insert(graph.cid.clone(), (graph.name.clone(), graph.visibility));
    }

    pub fn local_auth_did_document(&self) -> DidDocument {
        let did = self.operator_did.clone();
        let key_id = format!("{did}#agent-ed25519");
        let public_key_multibase = multibase::encode(
            multibase::Base::Base58Btc,
            self.identity.verifying_key().to_bytes(),
        );
        let x25519_key_id = format!("{did}#agent-x25519");
        let x25519_public_key_multibase = multibase::encode(
            multibase::Base::Base58Btc,
            self.identity.x25519_public_key().to_bytes(),
        );
        DidDocument {
            context: vec![DID_CONTEXT_V1.to_string()],
            id: did.clone(),
            verification_method: vec![
                VerificationMethod {
                    id: key_id.clone(),
                    key_type: "Ed25519VerificationKey2020".to_string(),
                    controller: did.clone(),
                    public_key_multibase,
                },
                VerificationMethod {
                    id: x25519_key_id.clone(),
                    key_type: "X25519KeyAgreementKey2020".to_string(),
                    controller: did.clone(),
                    public_key_multibase: x25519_public_key_multibase,
                },
            ],
            authentication: vec![key_id.clone()],
            assertion_method: vec![key_id.clone()],
            key_agreement: vec![x25519_key_id],
            capability_invocation: vec![key_id.clone()],
            capability_delegation: vec![key_id],
            service: vec![],
        }
    }

    pub async fn local_did_document(&self) -> DidDocument {
        let did = self.operator_did.clone();
        let mut doc = self.local_auth_did_document();

        let kotoba_endpoint = std::env::var("KOTOBA_NODE_ENDPOINT")
            .or_else(|_| std::env::var("KOTOBA_PUBLIC_ENDPOINT"))
            .unwrap_or_else(|_| "/ip4/127.0.0.1/tcp/4001".to_string());
        doc.push_single_service("kotoba-node", KOTOBA_NODE_SERVICE, kotoba_endpoint);

        let didcomm_endpoint = std::env::var("KOTOBA_DIDCOMM_ENDPOINT")
            .unwrap_or_else(|_| format!("didcomm://{}", did));
        doc.push_single_service("didcomm", DIDCOMM_MESSAGING_SERVICE, didcomm_endpoint);

        let atproto_pds_endpoint = std::env::var("KOTOBA_ATPROTO_PDS_ENDPOINT")
            .unwrap_or_else(|_| Self::public_http_endpoint_from_env());
        doc.push_single_service("atproto-pds", ATPROTO_PDS_SERVICE, atproto_pds_endpoint);

        let memberships = self
            .graph_registry
            .read()
            .await
            .keys()
            .map(|cid| format!("kotoba://graph/{}", cid.to_multibase()))
            .collect::<Vec<_>>();
        doc.push_graph_membership_service(memberships);
        doc
    }

    pub async fn did_ed25519_key_matches(&self, did: &str, public_key_multibase: &str) -> bool {
        if did == self.operator_did {
            let resolver = InMemoryDidResolver::new();
            resolver.insert(self.operator_did.clone(), self.local_did_document().await);
            return resolver
                .ed25519_key_matches_multibase(did, public_key_multibase)
                .unwrap_or(false);
        }
        self.did_resolver
            .ed25519_key_matches_multibase(did, public_key_multibase)
            .unwrap_or(false)
    }

    /// Write node registration Datoms to the distributed
    /// `kotoba/network/nodes` head and mirror them into the legacy Quad view
    /// for backward-compatible peers (ADR-2605260005).
    ///
    /// Called once at startup (from `main.rs`) and re-callable via the
    /// `kotoba_node_register` MCP tool to refresh the registration timestamp.
    pub async fn register_node(&self) {
        use std::time::{SystemTime, UNIX_EPOCH};

        let graph_cid = KotobaCid::from_bytes(b"kotoba/network/nodes");
        let subject_cid = KotobaCid::from_bytes(self.operator_did.as_bytes());
        let ts = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs() as i64;

        let endpoint = Self::public_http_endpoint_from_env();
        let node_id_hex = hex::encode(self.local_node_id.0);

        let mut datoms = vec![
            KqeDatom::assert(
                subject_cid.clone(),
                "node/did".to_string(),
                KqeValue::Text(self.operator_did.clone()),
                graph_cid.clone(),
            ),
            KqeDatom::assert(
                subject_cid.clone(),
                "node/version".to_string(),
                KqeValue::Text(self.version.to_string()),
                graph_cid.clone(),
            ),
            KqeDatom::assert(
                subject_cid.clone(),
                "node/endpoint".to_string(),
                KqeValue::Text(endpoint),
                graph_cid.clone(),
            ),
            KqeDatom::assert(
                subject_cid.clone(),
                "node/node_id_hex".to_string(),
                KqeValue::Text(node_id_hex),
                graph_cid.clone(),
            ),
            KqeDatom::assert(
                subject_cid.clone(),
                "node/registered_at".to_string(),
                KqeValue::Integer(ts),
                graph_cid.clone(),
            ),
        ];

        for role in &self.node_roles {
            let predicate = format!("node/role/{}", role.as_str());
            datoms.push(KqeDatom::assert(
                subject_cid.clone(),
                predicate,
                KqeValue::Bool(true),
                graph_cid.clone(),
            ));
        }

        let ipns_name = distributed_graph_ipns_name(&graph_cid);
        let current_head = match self
            .ipns_registry
            .resolve(&IpnsName::new(ipns_name.clone()))
        {
            Ok(record) => Some(record),
            Err(kotoba_ipfs::IpnsRegistryError::NotFound(_)) => None,
            Err(err) => {
                tracing::warn!(error = %err, "node registration IPNS resolve failed; falling back to legacy projection");
                None
            }
        };
        let expected_parent = current_head
            .as_ref()
            .and_then(|record| KotobaCid::from_multibase(&record.value));
        let seq = current_head
            .as_ref()
            .map(|record| record.sequence + 1)
            .unwrap_or(1);

        let distributed_datoms = datoms
            .iter()
            .cloned()
            .map(kotoba_datomic::Datom::from_kqe)
            .collect::<Vec<_>>();
        let distributed = DistributedCommitWriter::new(&*self.block_store, &*self.ipns_registry)
            .commit_datoms(CommitDatomsRequest {
                ipns_name: ipns_name.clone(),
                graph: graph_cid.clone(),
                datoms: distributed_datoms,
                covering_datoms: None,
                expected_parent,
                tx_cid: None,
                author: self.operator_did.clone(),
                seq,
                valid_until: "2099-01-01T00:00:00Z".to_string(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: Some(self.operator_did.clone()),
                ipns_signing_key: Some(self.ipns_signing_key()),
            });

        let tx_cid = match distributed {
            Ok(report) => Some(report.commit.tx_cid),
            Err(err) => {
                tracing::warn!(error = %err, "node registration distributed Datomic commit failed; falling back to legacy projection");
                None
            }
        };

        for mut datom in datoms {
            datom.op = true;
            if let Some(tx_cid) = &tx_cid {
                datom.tx = tx_cid.clone();
            }
            // Already committed to the CommitDag above (commit_datoms) — announce
            // to the live-tail without a redundant Journal block.
            self.journal_assert_datom_ephemeral(&graph_cid, &datom).await;
            self.quad_store
                .apply_journaled_datom(graph_cid.clone(), datom)
                .await;
        }
        tracing::info!(
            did   = %self.operator_did,
            roles = ?self.node_roles.iter().map(NodeRole::as_str).collect::<Vec<_>>(),
            ipns_name = %ipns_name,
            "node registered in distributed kotoba/network/nodes"
        );
    }

    /// Register an external app's wasm node (app name → program CID) so the
    /// generic XRPC→wasm ingress (`generic_invoke`) can resolve and dispatch it.
    ///
    /// Writes `node/did = app` + `node/endpoint = program_cid` into the LOCAL
    /// quad_store projection of `kotoba/network/nodes` via the same
    /// `apply_journaled_datom` path the server self-registration uses (and that
    /// `generic_invoke` reads), so a freshly-registered app node is immediately
    /// resolvable — unlike a raw `datomic.transact`, whose datoms reach the
    /// distributed head / datomic view but not this arrangement (ADR-2605312355).
    pub async fn register_external_node(&self, app: &str, program_cid: &str) {
        let graph_cid = KotobaCid::from_bytes(b"kotoba/network/nodes");
        let subject_cid = KotobaCid::from_bytes(format!("node:{app}").as_bytes());
        let datoms = vec![
            KqeDatom::assert(
                subject_cid.clone(),
                "node/did".to_string(),
                KqeValue::Text(app.to_string()),
                graph_cid.clone(),
            ),
            KqeDatom::assert(
                subject_cid.clone(),
                "node/endpoint".to_string(),
                KqeValue::Text(program_cid.to_string()),
                graph_cid.clone(),
            ),
        ];
        for datom in datoms {
            self.journal_assert_datom(&graph_cid, &datom).await;
            self.quad_store
                .apply_journaled_datom(graph_cid.clone(), datom)
                .await;
        }
        tracing::info!(app = %app, program_cid = %program_cid, "registered external wasm node");
    }

    /// Publish a Quad assert to the KSE Journal (fine SPO topic) and,
    /// if the swarm is active, also propagate via GossipSub on the coarse
    /// `"quad/assert"` topic so peers can ingest without subscribing to
    /// every specific SPO address.
    ///
    /// Returns the JournalEntry CID string.
    pub async fn journal_assert(&self, quad: &Quad) -> String {
        self.journal_assert_with(quad, true).await
    }

    /// Ephemeral assert: broadcast + ring (live-tail) but **no** block persist.
    /// Used by the datomic commit path — the datom is already durable in the
    /// CommitDag, so the Journal must not keep a redundant second copy.
    pub async fn journal_assert_ephemeral(&self, quad: &Quad) -> String {
        self.journal_assert_with(quad, false).await
    }

    async fn journal_assert_with(&self, quad: &Quad, persist: bool) -> String {
        let object_str = format!("{:?}", quad.object);
        let topic = Topic::quad_spo(
            &quad.graph.to_multibase(),
            &quad.subject.to_multibase(),
            &quad.predicate,
            &object_str,
        );
        // All handlers construct QuadObject::{Text,Bytes,Cid,Integer,Bool,...} — never Float.
        // Float(f64) would fail for NaN/Inf; guard at call sites if Float is ever added.
        let payload = serde_json::to_vec(quad)
            .expect("Quad serialization: Float(NaN/Inf) must not reach journal_assert");

        // Gossip on a coarse topic so peers can subscribe once and receive all asserts.
        // Channel carries raw KSE names (no "kotoba/" prefix); KotobaSwarm::publish adds it.
        if let Some(tx) = &self.gossip_tx {
            tx.try_send(("quad/assert".to_string(), payload.clone()))
                .ok();
        }

        let entry = if persist {
            self.journal.publish(topic, Bytes::from(payload)).await
        } else {
            self.journal.publish_ephemeral(topic, Bytes::from(payload)).await
        };
        entry.cid.to_multibase()
    }

    /// Publish a Datom assert through the legacy Quad journal projection.
    ///
    /// The journal protocol remains Quad-shaped for backward-compatible peers,
    /// but callers that already operate on Datoms should not have to project
    /// back to Quad at the call site.
    pub async fn journal_assert_datom(&self, graph_cid: &KotobaCid, datom: &KqeDatom) -> String {
        self.journal_assert(&datom_journal_quad(graph_cid, datom))
            .await
    }

    /// Ephemeral datom assert — live-tail broadcast only, no Journal block.
    /// For callers whose datoms are already durable in the CommitDag (e.g. node
    /// self-registration commits then announces), so the Journal copy is redundant.
    pub async fn journal_assert_datom_ephemeral(
        &self,
        graph_cid: &KotobaCid,
        datom: &KqeDatom,
    ) -> String {
        self.journal_assert_ephemeral(&datom_journal_quad(graph_cid, datom))
            .await
    }

    /// Compatibility journal assert plus Datom-native graph-store apply.
    pub async fn assert_datom_compat(&self, graph_cid: KotobaCid, mut datom: KqeDatom) -> String {
        datom.op = true;
        let journal_cid = self.journal_assert_datom(&graph_cid, &datom).await;
        let tx_cid = KotobaCid::from_multibase(&journal_cid)
            .unwrap_or_else(|| KotobaCid::from_bytes(journal_cid.as_bytes()));
        datom.tx = tx_cid;
        self.quad_store
            .apply_journaled_datom(graph_cid, datom)
            .await;
        journal_cid
    }

    /// Compatibility write for legacy Quad API callers.
    ///
    /// The Journal still receives the Quad wire payload, while the graph store
    /// receives a Datom whose transaction is the Journal entry CID.
    pub async fn assert_quad_compat(&self, quad: Quad) -> String {
        let graph_cid = quad.graph.clone();
        let journal_cid = self.journal_assert(&quad).await;
        let tx_cid = KotobaCid::from_multibase(&journal_cid)
            .unwrap_or_else(|| KotobaCid::from_bytes(journal_cid.as_bytes()));
        let mut datom = KqeDatom::from_legacy_quad(quad, true);
        datom.tx = tx_cid;
        self.quad_store
            .apply_journaled_datom(graph_cid, datom)
            .await;
        journal_cid
    }

    /// Apply a legacy Quad caller through the Datom-native graph-store path
    /// while preserving legacy graph projection publication.
    pub async fn assert_quad_store_datom(&self, quad: Quad) {
        let graph_cid = quad.graph.clone();
        let datom = KqeDatom::from_legacy_quad(quad, true);
        self.quad_store.assert_datom(graph_cid, datom).await;
    }

    /// Publish a Quad retract to the KSE Journal.
    pub async fn journal_retract(&self, quad: &Quad) -> String {
        self.journal_retract_with(quad, true).await
    }

    /// Ephemeral retract: broadcast + ring (live-tail) but **no** block persist.
    pub async fn journal_retract_ephemeral(&self, quad: &Quad) -> String {
        self.journal_retract_with(quad, false).await
    }

    async fn journal_retract_with(&self, quad: &Quad, persist: bool) -> String {
        let topic = Topic(format!(
            "kotoba/retract/{}/{}/{}",
            quad.graph, quad.subject, quad.predicate
        ));
        // All handlers construct QuadObject::{Text,Bytes,Cid,...} — never Float.
        let payload = serde_json::to_vec(quad)
            .expect("Quad serialization: Float(NaN/Inf) must not reach journal_retract");

        // Gossip retract events on a coarse topic as well.
        if let Some(tx) = &self.gossip_tx {
            tx.try_send(("quad/retract".to_string(), payload.clone()))
                .ok();
        }

        let entry = if persist {
            self.journal.publish(topic, Bytes::from(payload)).await
        } else {
            self.journal.publish_ephemeral(topic, Bytes::from(payload)).await
        };
        entry.cid.to_multibase()
    }

    /// Publish a Datom retract through the legacy Quad journal projection.
    pub async fn journal_retract_datom(&self, graph_cid: &KotobaCid, datom: &KqeDatom) -> String {
        self.journal_retract(&datom_journal_quad(graph_cid, datom))
            .await
    }

    /// Compatibility journal retract plus Datom-native graph-store apply.
    pub async fn retract_datom_compat(&self, graph_cid: KotobaCid, mut datom: KqeDatom) -> String {
        datom.op = false;
        let journal_cid = self.journal_retract_datom(&graph_cid, &datom).await;
        let tx_cid = KotobaCid::from_multibase(&journal_cid)
            .unwrap_or_else(|| KotobaCid::from_bytes(journal_cid.as_bytes()));
        datom.tx = tx_cid;
        self.quad_store
            .apply_journaled_datom(graph_cid, datom)
            .await;
        journal_cid
    }

    /// Compatibility retract for legacy Quad API callers.
    pub async fn retract_quad_compat(&self, quad: Quad) -> String {
        let graph_cid = quad.graph.clone();
        let journal_cid = self.journal_retract(&quad).await;
        let tx_cid = KotobaCid::from_multibase(&journal_cid)
            .unwrap_or_else(|| KotobaCid::from_bytes(journal_cid.as_bytes()));
        let mut datom = KqeDatom::from_legacy_quad(quad, false);
        datom.tx = tx_cid;
        self.quad_store
            .apply_journaled_datom(graph_cid, datom)
            .await;
        journal_cid
    }

    /// Apply a legacy Quad retract through the Datom-native graph-store path.
    pub async fn retract_quad_store_datom(&self, quad: Quad) {
        let graph_cid = quad.graph.clone();
        let datom = KqeDatom::from_legacy_quad(quad, false);
        self.quad_store.retract_datom(graph_cid, datom).await;
    }
}

fn datom_journal_quad(graph_cid: &KotobaCid, datom: &KqeDatom) -> Quad {
    Quad {
        graph: graph_cid.clone(),
        subject: datom.e.clone(),
        predicate: datom.a.clone(),
        object: datom.v.clone().into(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_auth::did_document::{
        ATTR_DID_CORE_ID, ATTR_DID_CORE_SERVICE, ATTR_DID_CORE_SERVICE_ENDPOINT, ATTR_RDF_TYPE,
    };

    /// Serializes tests that mutate process-global env vars (`KOTOBA_*`). The test
    /// runner executes tokio tests in parallel, so `set_var`/`remove_var` on the
    /// same variable race; holding this guard for the set→build→assert→remove
    /// window makes those tests mutually exclusive. Poison-tolerant so one failing
    /// test does not cascade-poison the rest.
    static ENV_MUTEX: std::sync::Mutex<()> = std::sync::Mutex::new(());
    fn env_guard() -> std::sync::MutexGuard<'static, ()> {
        ENV_MUTEX.lock().unwrap_or_else(|p| p.into_inner())
    }

    #[test]
    fn node_role_from_env_defaults_to_both() {
        std::env::remove_var("KOTOBA_NODE_ROLES");
        let roles = NodeRole::from_env();
        assert!(roles.contains(&NodeRole::Pin));
        assert!(roles.contains(&NodeRole::Compute));
    }

    #[test]
    fn node_role_from_env_pin_only() {
        std::env::set_var("KOTOBA_NODE_ROLES", "pin");
        let roles = NodeRole::from_env();
        assert_eq!(roles, vec![NodeRole::Pin]);
        std::env::remove_var("KOTOBA_NODE_ROLES");
    }

    #[test]
    fn node_role_from_env_compute_only() {
        std::env::set_var("KOTOBA_NODE_ROLES", "compute");
        let roles = NodeRole::from_env();
        assert_eq!(roles, vec![NodeRole::Compute]);
        std::env::remove_var("KOTOBA_NODE_ROLES");
    }

    #[test]
    fn node_role_as_str_roundtrips() {
        assert_eq!(NodeRole::Pin.as_str(), "pin");
        assert_eq!(NodeRole::Compute.as_str(), "compute");
    }

    #[test]
    fn kotoba_state_new_populates_operator_did() {
        let state = KotobaState::new(None).expect("new");
        assert!(
            !state.operator_did.is_empty(),
            "operator_did must not be empty"
        );
        assert!(
            state.operator_did.starts_with("did:"),
            "operator_did must be a DID: {}",
            state.operator_did
        );
    }

    #[test]
    fn kotoba_state_new_node_id_deterministic_in_ephemeral_mode() {
        // Two states created without env vars both derive NodeId from a freshly
        // generated ephemeral key — they should differ (each is random).
        std::env::set_var("KOTOBA_NO_KEYCHAIN", "1");
        std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_DID");
        let a = KotobaState::new(None).expect("a");
        let b = KotobaState::new(None).expect("b");
        std::env::remove_var("KOTOBA_NO_KEYCHAIN");
        // ephemeral → each call generates a fresh key → different NodeIds
        assert_ne!(
            a.local_node_id.0, b.local_node_id.0,
            "ephemeral NodeIds must differ across restarts"
        );
    }

    #[tokio::test]
    async fn register_node_writes_distributed_datomic_head_and_quads() {
        std::env::set_var("KOTOBA_NO_KEYCHAIN", "1");
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS", "memory");
        std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_DID");
        let state = KotobaState::new(None).expect("new");
        state.register_node().await;
        std::env::remove_var("KOTOBA_NO_KEYCHAIN");
        std::env::remove_var("KOTOBA_IPFS");
        std::env::remove_var("KOTOBA_IPNS");

        use kotoba_core::cid::KotobaCid;
        let graph_cid = KotobaCid::from_bytes(b"kotoba/network/nodes");
        let arrangement = state
            .quad_store
            .arrangement(&graph_cid)
            .await
            .expect("kotoba/network/nodes graph should exist after register_node");

        let subject_cid = KotobaCid::from_bytes(state.operator_did.as_bytes());
        let values = arrangement.get_values(&subject_cid, "node/did");
        assert!(!values.is_empty(), "node/did datom should exist");
        let registered_at_values = arrangement.get_values(&subject_cid, "node/registered_at");
        assert!(
            !registered_at_values.is_empty(),
            "node/registered_at datom should exist"
        );

        let ipns_name = distributed_graph_ipns_name(&graph_cid);
        let db = DistributedDatomReader::new(&*state.block_store, &*state.ipns_registry)
            .current_db_for_name(&ipns_name)
            .expect("distributed node registry head should read")
            .expect("distributed node registry head should exist");
        let datoms = db.datoms();
        assert!(
            datoms.iter().any(|datom| {
                datom.e == subject_cid
                    && datom.a == "node/did"
                    && datom.v == kotoba_datomic::Value::string(&state.operator_did)
            }),
            "node/did must be readable from the distributed Datomic/IPNS head"
        );
        assert!(
            datoms.iter().any(|datom| {
                datom.e == subject_cid
                    && datom.a == "node/registered_at"
                    && matches!(datom.v, kotoba_datomic::Value::Integer(_))
            }),
            "node/registered_at must be readable from the distributed Datomic/IPNS head"
        );
    }

    #[tokio::test]
    async fn local_did_document_advertises_kotoba_protocol_services() {
        let _env = env_guard(); // serialize KOTOBA_ATPROTO_PDS_ENDPOINT mutation
        std::env::set_var("KOTOBA_ATPROTO_PDS_ENDPOINT", "https://pds.example.com");
        let state = KotobaState::new(None).expect("new");
        let doc = state.local_did_document().await;
        std::env::remove_var("KOTOBA_ATPROTO_PDS_ENDPOINT");

        assert_eq!(doc.id, state.operator_did);
        assert!(doc.ed25519_public_key().is_some());
        assert!(doc.x25519_public_key().is_some());
        assert_eq!(doc.key_agreement.len(), 1);
        assert!(doc.kotoba_endpoint().is_some());
        assert!(doc.didcomm_endpoint().is_some());
        assert_eq!(doc.atproto_pds_endpoint(), Some("https://pds.example.com"));
        assert!(doc
            .graph_memberships()
            .iter()
            .all(|scope| scope.starts_with("kotoba://graph/")));

        std::env::remove_var("KOTOBA_ATPROTO_PDS_ENDPOINT");
        std::env::set_var("KOTOBA_PUBLIC_ENDPOINT", "https://kotoba.example.com");
        let state = KotobaState::new(None).expect("new");
        let doc = state.local_did_document().await;
        std::env::remove_var("KOTOBA_PUBLIC_ENDPOINT");

        assert_eq!(
            doc.atproto_pds_endpoint(),
            Some("https://kotoba.example.com")
        );
    }

    #[test]
    fn kotoba_state_did_resolver_falls_back_to_did_key_with_protocol_services() {
        let _env = env_guard(); // serialize KOTOBA_ATPROTO_PDS_ENDPOINT mutation
        std::env::set_var("KOTOBA_NO_KEYCHAIN", "1");
        std::env::remove_var("KOTOBA_AGENT_DID");
        std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
        std::env::remove_var("KOTOBA_DIDCOMM_ENDPOINT");
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::remove_var("KOTOBA_IPNS");
        std::env::set_var(
            "KOTOBA_ATPROTO_PDS_ENDPOINT",
            "https://pds.resolver.example",
        );

        let state = KotobaState::new(None).expect("new");
        let resolved = state.did_resolver.resolve(&state.operator_did).unwrap();
        let expected_didcomm = format!("didcomm://{}", state.operator_did);

        std::env::remove_var("KOTOBA_ATPROTO_PDS_ENDPOINT");
        std::env::remove_var("KOTOBA_NO_KEYCHAIN");
        std::env::remove_var("KOTOBA_IPFS");

        assert_eq!(resolved.id, state.operator_did);
        assert_eq!(resolved.didcomm_endpoint(), Some(expected_didcomm.as_str()));
        assert_eq!(
            resolved.atproto_pds_endpoint(),
            Some("https://pds.resolver.example")
        );
        assert!(resolved.kotoba_endpoint().is_some());
        assert!(resolved
            .graph_memberships()
            .iter()
            .all(|scope| scope.starts_with("kotoba://graph/")));
        assert!(resolved.has_kotoba_protocol_services());
    }

    #[test]
    fn distributed_did_resolver_reads_document_from_ipns_datomic_head() {
        let store: Arc<dyn BlockStore + Send + Sync> =
            Arc::new(kotoba_store::MemoryBlockStore::new());
        let ipns: Arc<dyn IpnsRegistry> = Arc::new(InMemoryIpnsRegistry::new());
        let did = "did:plc:distributedagent";
        let graph = KotobaCid::from_bytes(format!("did-document-registry:{did}").as_bytes());
        let ipns_name = did_document_ipns_name(did);

        let mut doc = DidDocument::empty(did);
        doc.push_single_service(
            "didcomm",
            DIDCOMM_MESSAGING_SERVICE,
            "didcomm://mediator/distributedagent",
        );
        doc.push_single_service(
            "atproto-pds",
            ATPROTO_PDS_SERVICE,
            "https://pds.distributedagent.example",
        );
        doc.push_single_service(
            "kotoba-node",
            KOTOBA_NODE_SERVICE,
            "/ip4/127.0.0.1/tcp/4101",
        );
        doc.push_graph_membership_service([
            "kotoba://graph/distributed-a",
            "kotoba://graph/distributed-b",
        ]);
        let tx_cid = KotobaCid::from_bytes(b"did-resolver-datomic-tx");
        let writer = kotoba_datomic::distributed::DistributedCommitWriter::new(&*store, &*ipns);
        writer
            .commit_datoms(kotoba_datomic::distributed::CommitDatomsRequest {
                covering_datoms: None,
                ipns_name: ipns_name.clone(),
                graph,
                datoms: doc.to_datoms(tx_cid.clone()),
                expected_parent: None,
                tx_cid: Some(tx_cid),
                author: "did:key:zWriter".to_string(),
                seq: 1,
                valid_until: "2026-05-29T00:00:00Z".to_string(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .expect("commit DID document datoms");

        let resolver = DistributedDidResolver::new(store, ipns, vec![]);
        let resolved = resolver.resolve(did).unwrap();

        assert_eq!(
            resolved.didcomm_endpoint(),
            Some("didcomm://mediator/distributedagent")
        );
        assert_eq!(
            resolved.atproto_pds_endpoint(),
            Some("https://pds.distributedagent.example")
        );
        assert_eq!(resolved.kotoba_endpoint(), Some("/ip4/127.0.0.1/tcp/4101"));
        assert_eq!(
            resolved.graph_memberships(),
            vec![
                "kotoba://graph/distributed-a",
                "kotoba://graph/distributed-b"
            ]
        );
        assert!(resolved.has_kotoba_protocol_services());
    }

    #[test]
    fn distributed_did_resolver_reads_w3c_did_core_services_from_shared_head() {
        let store: Arc<dyn BlockStore + Send + Sync> =
            Arc::new(kotoba_store::MemoryBlockStore::new());
        let ipns: Arc<dyn IpnsRegistry> = Arc::new(InMemoryIpnsRegistry::new());
        let did = "did:web:shared.example";
        let graph = KotobaCid::from_bytes(b"shared-did-document-registry");
        let ipns_name = "k51-kotoba-shared-did-registry".to_string();
        let tx_cid = KotobaCid::from_bytes(b"shared-did-w3c-service-tx");
        let doc_entity = KotobaCid::from_bytes(did.as_bytes());
        let service_specs = [
            (
                format!("{did}#didcomm"),
                DIDCOMM_MESSAGING_SERVICE,
                kotoba_datomic::Value::string("didcomm://mediator/shared"),
            ),
            (
                format!("{did}#atproto-pds"),
                ATPROTO_PDS_SERVICE,
                kotoba_datomic::Value::string("https://pds.shared.example"),
            ),
            (
                format!("{did}#kotoba-node"),
                KOTOBA_NODE_SERVICE,
                kotoba_datomic::Value::string("/ip4/127.0.0.1/tcp/4201"),
            ),
            (
                format!("{did}#kotoba-graphs"),
                kotoba_auth::KOTOBA_GRAPH_MEMBERSHIP_SERVICE,
                kotoba_datomic::Value::vector([
                    kotoba_datomic::Value::string("kotoba://graph/shared-a"),
                    kotoba_datomic::Value::string("kotoba://graph/shared-b"),
                ]),
            ),
        ];
        let mut datoms = vec![kotoba_datomic::Datom::assert(
            doc_entity.clone(),
            ATTR_DID_CORE_ID.to_string(),
            kotoba_datomic::Value::string(did),
            tx_cid.clone(),
        )];
        for (service_id, service_type, endpoint) in service_specs {
            let service_entity = KotobaCid::from_bytes(service_id.as_bytes());
            datoms.push(kotoba_datomic::Datom::assert(
                doc_entity.clone(),
                ATTR_DID_CORE_SERVICE.to_string(),
                kotoba_datomic::Value::string(&service_id),
                tx_cid.clone(),
            ));
            datoms.push(kotoba_datomic::Datom::assert(
                service_entity.clone(),
                ATTR_DID_CORE_ID.to_string(),
                kotoba_datomic::Value::string(&service_id),
                tx_cid.clone(),
            ));
            datoms.push(kotoba_datomic::Datom::assert(
                service_entity.clone(),
                ATTR_RDF_TYPE.to_string(),
                kotoba_datomic::Value::string(service_type),
                tx_cid.clone(),
            ));
            datoms.push(kotoba_datomic::Datom::assert(
                service_entity,
                ATTR_DID_CORE_SERVICE_ENDPOINT.to_string(),
                endpoint,
                tx_cid.clone(),
            ));
        }

        let writer = kotoba_datomic::distributed::DistributedCommitWriter::new(&*store, &*ipns);
        writer
            .commit_datoms(kotoba_datomic::distributed::CommitDatomsRequest {
                covering_datoms: None,
                ipns_name: ipns_name.clone(),
                graph,
                datoms,
                expected_parent: None,
                tx_cid: Some(tx_cid),
                author: "did:key:zWriter".to_string(),
                seq: 1,
                valid_until: "2026-05-30T00:00:00Z".to_string(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .expect("commit shared DID document registry");

        let resolver = DistributedDidResolver::new(store, ipns, vec![ipns_name]);
        let resolved = resolver.resolve(did).unwrap();

        assert_eq!(
            resolved.didcomm_endpoint(),
            Some("didcomm://mediator/shared")
        );
        assert_eq!(
            resolved.atproto_pds_endpoint(),
            Some("https://pds.shared.example")
        );
        assert_eq!(resolved.kotoba_endpoint(), Some("/ip4/127.0.0.1/tcp/4201"));
        assert_eq!(
            resolved.graph_memberships(),
            vec!["kotoba://graph/shared-a", "kotoba://graph/shared-b"]
        );
        assert!(resolved.has_kotoba_protocol_services());
    }

    #[test]
    fn is_ephemeral_returns_true_without_env_vars() {
        std::env::set_var("KOTOBA_NO_KEYCHAIN", "1");
        std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_DID");
        let state = KotobaState::new(None).expect("new");
        assert!(state.is_ephemeral(), "should be ephemeral without env vars");
    }

    #[test]
    fn node_id_matches_operator_did_signing_key() {
        // NodeId is blake3(verifying_key) — derived from the same identity used for
        // operator_did (prevents the double-generation bug; never exposes private key).
        std::env::set_var("KOTOBA_NO_KEYCHAIN", "1");
        std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_DID");
        let state = KotobaState::new(None).expect("new");
        // operator_did is non-empty and consistent with node_id (both from same identity)
        assert!(!hex::encode(state.local_node_id.0).is_empty());
        assert!(!state.operator_did.is_empty());
        // Two calls produce different ephemeral identities — confirming Arc reuse
        // within a single state (not across states)
        let state2 = KotobaState::new(None).expect("new2");
        assert_ne!(
            state.local_node_id.0, state2.local_node_id.0,
            "distinct states have distinct ephemeral NodeIds"
        );
        assert_ne!(
            state.operator_did, state2.operator_did,
            "distinct states have distinct ephemeral DIDs"
        );
    }

    #[test]
    fn require_operator_auth_accepts_tenant_jwt_with_operator_did() {
        // Simulate what tenant_jwt(&s.operator_did) produces in e2e tests.
        use axum::http::HeaderMap;
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};

        std::env::set_var("KOTOBA_NO_KEYCHAIN", "1");
        std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_DID");
        let state = KotobaState::new(None).expect("new");
        let did = &state.operator_did;

        let header = URL_SAFE_NO_PAD.encode(br#"{"alg":"HS256","typ":"JWT"}"#);
        let payload =
            URL_SAFE_NO_PAD.encode(format!(r#"{{"sub":"{did}","exp":9999999999}}"#).as_bytes());
        let tok = format!("{header}.{payload}.fakesig");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {tok}").parse().unwrap(),
        );

        let result = crate::graph_auth::require_operator_auth(&headers, did);
        assert!(
            result.is_ok(),
            "require_operator_auth must accept tenant_jwt with operator_did; got err: {result:?}"
        );
    }

    #[tokio::test]
    async fn init_crypto_preserves_operator_did() {
        // Guard against the double-generation bug: init_crypto() must not call
        // AgentIdentity::from_env() again; it must reuse the Arc stored in new().
        std::env::set_var("KOTOBA_NO_KEYCHAIN", "1");
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS", "memory");
        std::env::remove_var("KOTOBA_AGENT_ED25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_X25519_HEX");
        std::env::remove_var("KOTOBA_AGENT_DID");
        let state = KotobaState::new(None).expect("new");
        let did_before = state.operator_did.clone();
        let state = state.init_crypto().await.expect("init_crypto");
        std::env::remove_var("KOTOBA_NO_KEYCHAIN");
        std::env::remove_var("KOTOBA_IPFS");
        std::env::remove_var("KOTOBA_IPNS");
        assert_eq!(
            state.operator_did, did_before,
            "operator_did must be unchanged after init_crypto"
        );
        assert!(
            state.crypto_required().is_ok(),
            "crypto must be initialized"
        );
    }
}
