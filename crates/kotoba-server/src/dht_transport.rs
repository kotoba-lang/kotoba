//! Kubo-backed `PeerTransport` for the DHT durability tier (ADR-2606011330).
//!
//! Wraps a `KuboBlockStore` pointed at a single peer's Kubo HTTP endpoint and
//! exposes it as a `kotoba_dht::PeerTransport`, so `NeighborhoodBlockStore` can
//! replicate blocks to / fetch blocks from that peer using the existing
//! `block/put` + `block/get` RPC (single SHA2-256 CIDv1, IPFS-compatible).
//!
//! This concrete HTTP transport lives in kotoba-server (not kotoba-dht) on
//! purpose: kotoba-dht stays transport-free so it remains WASM-32 buildable
//! (Baien edge invariant).

use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use kotoba_dht::node_id::NodeId;
use kotoba_dht::PeerTransport;

/// A neighbor reachable over Kubo HTTP.
pub struct KuboPeerTransport {
    id: NodeId,
    endpoint: String,
    store: kotoba_store::KuboBlockStore,
}

impl KuboPeerTransport {
    /// Build a transport for a peer at `endpoint` (a Kubo HTTP base URL).
    ///
    /// The DHT `NodeId` is derived deterministically from the endpoint string
    /// until peers advertise DID-keyed node ids. HONEST: this is a routing-key
    /// stand-in, not a verified peer identity — the availability_proof /
    /// warrant layer is what gates trust, not the address derivation.
    pub fn new(endpoint: impl Into<String>) -> Self {
        let endpoint = endpoint.into();
        let id = NodeId::from_pubkey(endpoint.as_bytes());
        let store = kotoba_store::KuboBlockStore::new(endpoint.clone());
        Self { id, endpoint, store }
    }

    /// Build a transport with an explicit DID-derived `NodeId` (R3 #4). Prefer
    /// this once a peer advertises its DID public key: the routing key is then
    /// `blake3(did_pubkey)` (`NodeId::from_pubkey`), a verifiable identity
    /// rather than the endpoint-string stand-in `new()` uses.
    pub fn with_node_id(endpoint: impl Into<String>, id: NodeId) -> Self {
        let endpoint = endpoint.into();
        let store = kotoba_store::KuboBlockStore::new(endpoint.clone());
        Self { id, endpoint, store }
    }

    pub fn endpoint(&self) -> &str {
        &self.endpoint
    }
}

impl PeerTransport for KuboPeerTransport {
    fn node_id(&self) -> &NodeId {
        &self.id
    }

    fn fetch(&self, cid: &KotobaCid) -> Option<Bytes> {
        self.store.get(cid).ok().flatten()
    }

    fn replicate(&self, cid: &KotobaCid, data: &[u8]) -> bool {
        self.store.put(cid, data).is_ok()
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.store.has(cid)
    }
}

/// Live `ProofFetcher` over HTTP (ADR-2606011330 #1, client half). POSTs an
/// `AvailabilityChallenge` to a peer's `availability_challenge` XRPC endpoint
/// and parses the returned `AvailabilityProof`. Uses `reqwest::blocking` so it
/// satisfies the synchronous `ProofFetcher` trait without runtime bridging.
///
/// This is what turns a fleet of `kotoba-server` nodes into a runnable audit:
/// `AuditScheduler::new(auditor, HttpProofFetcher{..}, sink)` over the real
/// network. Peers map `NodeId → base URL`; unknown peers are unreachable.
pub struct HttpProofFetcher {
    client: reqwest::blocking::Client,
    endpoints: std::collections::HashMap<NodeId, String>,
}

impl HttpProofFetcher {
    pub fn new(endpoints: std::collections::HashMap<NodeId, String>) -> Self {
        let client = reqwest::blocking::Client::builder()
            .connect_timeout(std::time::Duration::from_millis(500))
            .timeout(std::time::Duration::from_secs(10))
            .build()
            .unwrap_or_default();
        Self { client, endpoints }
    }

    pub fn peer_count(&self) -> usize {
        self.endpoints.len()
    }
}

impl kotoba_dht::ProofFetcher for HttpProofFetcher {
    fn request_proof(
        &self,
        peer: &NodeId,
        challenge: &kotoba_dht::availability_proof::AvailabilityChallenge,
    ) -> Option<kotoba_dht::availability_proof::AvailabilityProof> {
        let base = self.endpoints.get(peer)?.trim_end_matches('/');
        let url = format!(
            "{base}/xrpc/{}",
            crate::availability_xrpc::NSID_AVAILABILITY_CHALLENGE
        );
        let resp = self.client.post(&url).json(challenge).send().ok()?;
        if !resp.status().is_success() {
            return None;
        }
        resp.json().ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn distinct_endpoints_get_distinct_node_ids() {
        let a = KuboPeerTransport::new("http://peer-a:5001");
        let b = KuboPeerTransport::new("http://peer-b:5001");
        assert_ne!(a.node_id(), b.node_id());
    }

    #[test]
    fn node_id_is_deterministic_for_an_endpoint() {
        let a = KuboPeerTransport::new("http://peer-x:5001");
        let b = KuboPeerTransport::new("http://peer-x:5001");
        assert_eq!(a.node_id(), b.node_id());
        assert_eq!(a.endpoint(), "http://peer-x:5001");
    }

    #[test]
    fn with_node_id_uses_supplied_did_keyed_id_not_endpoint() {
        // A DID pubkey-derived NodeId must override the endpoint-string stand-in.
        let did_id = NodeId::from_pubkey(b"did:web:peer.example#key-1");
        let t = KuboPeerTransport::with_node_id("http://peer:5001", did_id.clone());
        assert_eq!(t.node_id(), &did_id);
        // ...and differs from what new() would have derived from the endpoint.
        assert_ne!(t.node_id(), KuboPeerTransport::new("http://peer:5001").node_id());
    }

    /// Live integration test against a real Kubo daemon (ADR-2606011330 R2 #2).
    /// IGNORED by default — requires a reachable Kubo at $KOTOBA_IPFS_ENDPOINT
    /// (default http://localhost:5001). Run with:
    ///   docker run -d -p 5001:5001 ipfs/kubo:latest
    ///   cargo test -p kotoba-server --lib dht_transport::tests::live_kubo -- --ignored
    /// Exercises the real `replicate` (block/put) → `fetch` (block/get) round
    /// trip and a NeighborhoodBlockStore put_durable over the live transport.
    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    #[ignore = "requires a live Kubo daemon at KOTOBA_IPFS_ENDPOINT"]
    async fn live_kubo_replicate_then_fetch_roundtrip() {
        use kotoba_dht::NeighborhoodBlockStore;
        use std::sync::Arc;

        let endpoint = std::env::var("KOTOBA_IPFS_ENDPOINT")
            .unwrap_or_else(|_| "http://localhost:5001".into());
        let peer = KuboPeerTransport::new(endpoint.clone());

        // Unique payload so reruns don't collide on an already-stored CID.
        let payload = format!("kotoba-dht-live-test-{}", endpoint).into_bytes();
        let cid = KotobaCid::from_bytes(&payload);

        assert!(peer.replicate(&cid, &payload), "live block/put must succeed");
        let got = peer.fetch(&cid).expect("live block/get must return the block");
        assert_eq!(&got[..], &payload[..], "round-tripped bytes must match");
        assert!(peer.has(&cid), "block/stat must report presence");

        // End-to-end durability through the store over the live peer.
        let local = kotoba_store::KuboBlockStore::new(endpoint.clone());
        let local_id = NodeId::from_pubkey(b"live-auditor");
        let store = NeighborhoodBlockStore::new(Arc::new(local), local_id)
            .with_peers(vec![Arc::new(KuboPeerTransport::new(endpoint)) as Arc<dyn PeerTransport>])
            .with_min_replicas(2);
        let p2 = format!("kotoba-dht-live-durable-{}", store.peer_count()).into_bytes();
        let c2 = KotobaCid::from_bytes(&p2);
        store
            .put_durable(&c2, &p2)
            .expect("put_durable must meet 2 replicas against live Kubo");
    }
}
