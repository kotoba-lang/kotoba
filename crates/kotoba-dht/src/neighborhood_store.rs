//! NeighborhoodBlockStore — durability + verifiable-availability block store.
//!
//! Per **ADR-2606011330**, this is the durability *owner* beneath the canonical
//! kotoba Datom log (ADR-2605312345). It composes into kotoba-store's
//! `TieredBlockStore` as the **durability tier**:
//!
//! ```text
//! hot          = BudgetedBlockStore<MemoryBlockStore>   (LRU, µs)
//! durability   = NeighborhoodBlockStore  (THIS)         ← r-replication + availability_proof
//! cold/interop = KuboBlockStore (IPFS CIDv1)            (backstop + interop wire)
//! anchor       = Base L2                                (commit-DAG root)
//! ```
//!
//! Each block is replicated to the `K` DHT nodes nearest (XOR metric) to the
//! block's *content address* (`cid_address`), and `put_durable` only succeeds
//! once `min_replicas` confirmed copies exist. The store answers
//! `AvailabilityChallenge`s from the blocks it holds locally
//! (`respond_to_challenge`), wiring durability ↔ `availability_proof`.
//!
//! ## Placement
//!
//! This lives in **kotoba-dht**, not kotoba-store, to avoid a dependency cycle:
//! `kotoba-store → kotoba-kse → kotoba-store` would loop, and kotoba-dht already
//! owns `NodeId` / `Neighborhood` / `availability_proof`.
//!
//! ## WASM / edge
//!
//! The store and the `PeerTransport` trait carry **no transport dependency**
//! (no HTTP / tokio) so kotoba-dht stays WASM-32 buildable (Baien edge
//! invariant). Concrete transports (Kubo HTTP, libp2p) are supplied by callers
//! — e.g. `kotoba-server` provides a Kubo `PeerTransport`.

use crate::availability_proof::{hash_block, AvailabilityChallenge, AvailabilityProof, ProofEntry};
use crate::neighborhood::K;
use crate::node_id::NodeId;
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::sync::Arc;

/// Map a content address (CID) into the DHT keyspace. The `K` nodes nearest
/// this address (XOR metric) are responsible for storing the block.
pub fn cid_address(cid: &KotobaCid) -> NodeId {
    NodeId::from_pubkey(&cid.0)
}

/// Rebuild a `KotobaCid` from the 36-byte form used in `AvailabilityChallenge`.
fn cid_from_slice(bytes: &[u8]) -> Option<KotobaCid> {
    let arr: [u8; 36] = bytes.try_into().ok()?;
    Some(KotobaCid(arr))
}

/// Build an `AvailabilityProof` for the locally-held subset of a challenge, over
/// **any** `BlockStore` (not just `NeighborhoodBlockStore`). This decoupling lets
/// a node answer availability challenges regardless of how its block store is
/// composed — e.g. a `kotoba-server` XRPC endpoint can prove possession directly
/// over its type-erased `Arc<dyn BlockStore>`. CIDs not held are omitted; the
/// signature is left empty for the gossip/transport layer to sign (ADR-2606011330).
pub fn proof_from_store(
    local: &dyn BlockStore,
    local_id: &NodeId,
    challenge: &AvailabilityChallenge,
) -> AvailabilityProof {
    let mut entries = Vec::new();
    for cid_bytes in &challenge.challenge_cids {
        if let Some(cid) = cid_from_slice(cid_bytes) {
            if let Ok(Some(block)) = local.get(&cid) {
                entries.push(ProofEntry {
                    cid_bytes: cid_bytes.clone(),
                    content_hash: hash_block(&block),
                });
            }
        }
    }
    AvailabilityProof {
        epoch: challenge.epoch,
        prover_peer: local_id.0.to_vec(),
        entries,
        signature: Vec::new(),
    }
}

/// A transport to a single neighbor: fetch a block from it, or replicate one to
/// it. Implementations may be Kubo HTTP, libp2p, or in-memory (tests). Kept free
/// of any concrete transport dependency so kotoba-dht stays WASM-buildable.
pub trait PeerTransport: Send + Sync {
    /// The neighbor's DHT address (XOR routing key).
    fn node_id(&self) -> &NodeId;

    /// Fetch a block from this peer. `None` if the peer does not hold it or the
    /// transport fails.
    fn fetch(&self, cid: &KotobaCid) -> Option<Bytes>;

    /// Push a block to this peer. Returns `true` only on a confirmed write.
    fn replicate(&self, cid: &KotobaCid, data: &[u8]) -> bool;

    /// Cheap presence check. Default delegates to `fetch`.
    fn has(&self, cid: &KotobaCid) -> bool {
        self.fetch(cid).is_some()
    }
}

/// Durability + verifiable-availability block store over a local store and a set
/// of neighbor transports.
pub struct NeighborhoodBlockStore {
    /// Durable local store (the working copy this node is responsible for).
    local: Arc<dyn BlockStore>,
    /// This node's DHT address.
    local_id: NodeId,
    /// Known neighbor transports.
    peers: Vec<Arc<dyn PeerTransport>>,
    /// Replica count required for `put_durable` to succeed (local copy counts
    /// as one). `1` means local-only durability is acceptable (single node).
    min_replicas: usize,
}

impl NeighborhoodBlockStore {
    /// Create a single-node store (no peers, `min_replicas = 1`). Durable on the
    /// local store alone until peers are added.
    pub fn new(local: Arc<dyn BlockStore>, local_id: NodeId) -> Self {
        Self {
            local,
            local_id,
            peers: Vec::new(),
            min_replicas: 1,
        }
    }

    /// Attach neighbor transports.
    pub fn with_peers(mut self, peers: Vec<Arc<dyn PeerTransport>>) -> Self {
        self.peers = peers;
        self
    }

    /// Set the replica count `put_durable` must confirm (clamped to ≥ 1).
    pub fn with_min_replicas(mut self, n: usize) -> Self {
        self.min_replicas = n.max(1);
        self
    }

    pub fn peer_count(&self) -> usize {
        self.peers.len()
    }

    pub fn min_replicas(&self) -> usize {
        self.min_replicas
    }

    pub fn local_id(&self) -> &NodeId {
        &self.local_id
    }

    /// The (up to) `K` peers responsible for a block, nearest-first by XOR
    /// distance to the block's content address.
    fn responsible_peers(&self, cid: &KotobaCid) -> Vec<&Arc<dyn PeerTransport>> {
        let addr = cid_address(cid);
        let mut with_dist: Vec<(&Arc<dyn PeerTransport>, [u8; 32])> = self
            .peers
            .iter()
            .map(|p| (p, addr.xor_distance(p.node_id())))
            .collect();
        with_dist.sort_by_key(|(_, d)| *d);
        with_dist.into_iter().take(K).map(|(p, _)| p).collect()
    }

    /// Owned `Arc` clones of the responsible peers (for spawn / 'static moves).
    fn responsible_owned(&self, cid: &KotobaCid) -> Vec<Arc<dyn PeerTransport>> {
        self.responsible_peers(cid)
            .into_iter()
            .map(Arc::clone)
            .collect()
    }

    /// Best-effort replication for the hot `put` path. Replication is moved OFF
    /// the caller's thread: when a tokio runtime is available each peer write is
    /// offloaded to the blocking pool and detached (fire-and-forget), so a slow
    /// or unreachable peer never stalls a write. Falls back to a synchronous
    /// inline write with no runtime (tests / wasm / bench), preserving
    /// correctness everywhere.
    fn replicate_fire_and_forget(&self, cid: &KotobaCid, data: &[u8]) {
        let targets = self.responsible_owned(cid);
        if targets.is_empty() {
            return;
        }
        #[cfg(not(target_arch = "wasm32"))]
        {
            if let Ok(handle) = tokio::runtime::Handle::try_current() {
                for p in targets {
                    let cid = cid.clone();
                    let buf = data.to_vec();
                    handle.spawn(async move {
                        let _ = tokio::task::spawn_blocking(move || p.replicate(&cid, &buf)).await;
                    });
                }
                return;
            }
        }
        for p in &targets {
            let _ = p.replicate(cid, data);
        }
    }

    /// Replicate to the responsible peers and CONFIRM, returning the number of
    /// peers that acknowledged the write (local copy NOT included). Used by
    /// `put_durable`, where the caller is blocked until the replica target is
    /// met. On native with a multi-thread runtime the peer writes run
    /// **concurrently** (latency = slowest single peer, not the sum); a
    /// sequential fallback covers tests / wasm / current-thread runtimes.
    fn replicate_confirmed(&self, cid: &KotobaCid, data: &[u8]) -> usize {
        let targets = self.responsible_owned(cid);
        if targets.is_empty() {
            return 0;
        }
        #[cfg(not(target_arch = "wasm32"))]
        {
            if let Ok(handle) = tokio::runtime::Handle::try_current() {
                let jobs: Vec<_> = targets
                    .iter()
                    .map(|p| {
                        let p = Arc::clone(p);
                        let cid = cid.clone();
                        let buf = data.to_vec();
                        handle.spawn_blocking(move || p.replicate(&cid, &buf))
                    })
                    .collect();
                return tokio::task::block_in_place(|| {
                    handle.block_on(async {
                        let mut ok = 0usize;
                        for j in jobs {
                            if let Ok(true) = j.await {
                                ok += 1;
                            }
                        }
                        ok
                    })
                });
            }
        }
        targets.iter().filter(|p| p.replicate(cid, data)).count()
    }

    /// Total confirmed replicas of a block right now: `1` (local, if held) plus
    /// every responsible peer that currently holds it. Used to audit durability.
    pub fn replica_count(&self, cid: &KotobaCid) -> usize {
        let local = usize::from(self.local.has(cid));
        let peers = self
            .responsible_peers(cid)
            .iter()
            .filter(|p| p.has(cid))
            .count();
        local + peers
    }

    /// Build an `AvailabilityProof` for the locally-held subset of a challenge.
    /// CIDs the node does not hold are simply omitted (the verifier excludes
    /// them); the signature is left empty for the gossip layer to sign.
    pub fn respond_to_challenge(&self, challenge: &AvailabilityChallenge) -> AvailabilityProof {
        proof_from_store(self.local.as_ref(), &self.local_id, challenge)
    }
}

impl BlockStore for NeighborhoodBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        // Local write must succeed; peer replication is best-effort and moved
        // off the hot path (a slow peer must not stall a write).
        self.local.put(cid, data)?;
        self.replicate_fire_and_forget(cid, data);
        Ok(())
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        if let Some(b) = self.local.get(cid)? {
            return Ok(Some(b));
        }
        // Miss → ask the responsible neighbors, nearest first; promote on hit.
        for peer in self.responsible_peers(cid) {
            if let Some(b) = peer.fetch(cid) {
                let _ = self.local.put(cid, &b);
                tracing::debug!(cid = %cid.to_multibase(), "neighborhood block fetch hit");
                return Ok(Some(b));
            }
        }
        Ok(None)
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.local.has(cid) || self.responsible_peers(cid).iter().any(|p| p.has(cid))
    }

    /// Durable write: confirm `min_replicas` copies (local + peers) before
    /// returning Ok. Surfaces a real error when the network cannot meet the
    /// replication target — used for root commit pointers / vault keys.
    fn put_durable(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.local.put_durable(cid, data)?;
        let replicas = 1 + self.replicate_confirmed(cid, data);
        anyhow::ensure!(
            replicas >= self.min_replicas,
            "durability not met for {}: confirmed {replicas}/{} replicas",
            cid.to_multibase(),
            self.min_replicas,
        );
        Ok(())
    }

    /// Durable batch: write the whole batch to the local tier CONCURRENTLY
    /// (the cold kubo round-trips overlap — the 2026-06-02 commit-path
    /// throughput fix, ADR-2606012200), then meet the replica target per block
    /// exactly as `put_durable` (a no-op extra cost on a single-node deploy
    /// where peer replication finds no peers). Surfaces the first failure.
    fn put_many_durable(&self, blocks: &[(KotobaCid, Vec<u8>)]) -> anyhow::Result<()> {
        self.local.put_many_durable(blocks)?;
        for (cid, data) in blocks {
            let replicas = 1 + self.replicate_confirmed(cid, data);
            anyhow::ensure!(
                replicas >= self.min_replicas,
                "durability not met for {}: confirmed {replicas}/{} replicas",
                cid.to_multibase(),
                self.min_replicas,
            );
        }
        Ok(())
    }

    fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;
    use std::sync::Mutex;

    /// Minimal in-memory `BlockStore` for tests (kotoba-dht does not depend on
    /// kotoba-store, so we cannot use MemoryBlockStore here).
    #[derive(Default)]
    struct MemStore {
        map: Mutex<HashMap<[u8; 36], Bytes>>,
    }
    impl MemStore {
        fn new() -> Arc<Self> {
            Arc::new(Self::default())
        }
    }
    impl BlockStore for MemStore {
        fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
            self.map
                .lock()
                .unwrap()
                .insert(cid.0, Bytes::copy_from_slice(data));
            Ok(())
        }
        fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
            Ok(self.map.lock().unwrap().get(&cid.0).cloned())
        }
        fn has(&self, cid: &KotobaCid) -> bool {
            self.map.lock().unwrap().contains_key(&cid.0)
        }
        fn all_cids(&self) -> Vec<KotobaCid> {
            self.map.lock().unwrap().keys().map(|k| KotobaCid(*k)).collect()
        }
    }

    /// In-memory peer transport wrapping a `MemStore` + a fixed `NodeId`.
    struct MemPeer {
        id: NodeId,
        store: Arc<MemStore>,
        /// When false, `replicate` is rejected (simulates an unavailable peer).
        accept: bool,
    }
    impl MemPeer {
        fn new(tag: &[u8]) -> Arc<Self> {
            Arc::new(Self {
                id: NodeId::from_pubkey(tag),
                store: MemStore::new(),
                accept: true,
            })
        }
        fn rejecting(tag: &[u8]) -> Arc<Self> {
            Arc::new(Self {
                id: NodeId::from_pubkey(tag),
                store: MemStore::new(),
                accept: false,
            })
        }
    }
    impl PeerTransport for MemPeer {
        fn node_id(&self) -> &NodeId {
            &self.id
        }
        fn fetch(&self, cid: &KotobaCid) -> Option<Bytes> {
            self.store.get(cid).ok().flatten()
        }
        fn replicate(&self, cid: &KotobaCid, data: &[u8]) -> bool {
            if !self.accept {
                return false;
            }
            self.store.put(cid, data).is_ok()
        }
    }

    fn local_node(tag: &[u8]) -> (Arc<MemStore>, NodeId) {
        (MemStore::new(), NodeId::from_pubkey(tag))
    }

    #[test]
    fn put_writes_local_and_replicates_to_peers() {
        let (local, id) = local_node(b"local");
        let p1 = MemPeer::new(b"peer-1");
        let p2 = MemPeer::new(b"peer-2");
        let store = NeighborhoodBlockStore::new(local.clone(), id)
            .with_peers(vec![p1.clone(), p2.clone()]);
        let cid = KotobaCid::from_bytes(b"block-A");
        store.put(&cid, b"block-A").unwrap();
        assert!(local.has(&cid), "local must hold the block");
        // Both peers are within K, so both should have received the replica.
        assert!(p1.fetch(&cid).is_some());
        assert!(p2.fetch(&cid).is_some());
    }

    #[test]
    fn get_local_hit() {
        let (local, id) = local_node(b"local");
        let store = NeighborhoodBlockStore::new(local, id);
        let cid = KotobaCid::from_bytes(b"local-block");
        store.put(&cid, b"local-block").unwrap();
        assert_eq!(store.get(&cid).unwrap().as_deref(), Some(b"local-block" as &[u8]));
    }

    #[test]
    fn get_miss_fetches_from_peer_and_promotes() {
        let (local, id) = local_node(b"local");
        let peer = MemPeer::new(b"holder");
        let cid = KotobaCid::from_bytes(b"remote-block");
        // Seed the block ONLY on the peer.
        peer.store.put(&cid, b"remote-block").unwrap();
        let store = NeighborhoodBlockStore::new(local.clone(), id).with_peers(vec![peer]);
        assert!(!local.has(&cid), "precondition: not local yet");
        let got = store.get(&cid).unwrap();
        assert_eq!(got.as_deref(), Some(b"remote-block" as &[u8]));
        // Promotion: a second get is now a local hit.
        assert!(local.has(&cid), "block must be promoted to local after peer fetch");
    }

    #[test]
    fn get_miss_no_peers_returns_none() {
        let (local, id) = local_node(b"local");
        let store = NeighborhoodBlockStore::new(local, id);
        let cid = KotobaCid::from_bytes(b"absent");
        assert!(store.get(&cid).unwrap().is_none());
    }

    #[test]
    fn put_durable_single_node_ok() {
        let (local, id) = local_node(b"local");
        let store = NeighborhoodBlockStore::new(local, id); // min_replicas = 1
        let cid = KotobaCid::from_bytes(b"durable-1");
        store.put_durable(&cid, b"durable-1").unwrap();
    }

    #[test]
    fn put_durable_meets_replica_target() {
        let (local, id) = local_node(b"local");
        let p1 = MemPeer::new(b"peer-1");
        let p2 = MemPeer::new(b"peer-2");
        let store = NeighborhoodBlockStore::new(local, id)
            .with_peers(vec![p1, p2])
            .with_min_replicas(3); // local + 2 peers
        let cid = KotobaCid::from_bytes(b"durable-3");
        store.put_durable(&cid, b"durable-3").unwrap();
    }

    #[test]
    fn put_durable_fails_when_replica_target_unmet() {
        let (local, id) = local_node(b"local");
        // Both peers reject replication → only the local copy exists.
        let p1 = MemPeer::rejecting(b"reject-1");
        let p2 = MemPeer::rejecting(b"reject-2");
        let store = NeighborhoodBlockStore::new(local, id)
            .with_peers(vec![p1, p2])
            .with_min_replicas(2); // need 2, will only get 1 (local)
        let cid = KotobaCid::from_bytes(b"durable-fail");
        let err = store.put_durable(&cid, b"durable-fail").unwrap_err();
        assert!(
            err.to_string().contains("durability not met"),
            "got: {err}"
        );
    }

    #[test]
    fn replica_count_counts_local_plus_holding_peers() {
        let (local, id) = local_node(b"local");
        let p1 = MemPeer::new(b"peer-1");
        let p2 = MemPeer::new(b"peer-2");
        let store = NeighborhoodBlockStore::new(local, id).with_peers(vec![p1, p2]);
        let cid = KotobaCid::from_bytes(b"counted");
        store.put(&cid, b"counted").unwrap();
        assert_eq!(store.replica_count(&cid), 3, "local + 2 peers");
    }

    #[test]
    fn has_checks_local_then_peers() {
        let (local, id) = local_node(b"local");
        let peer = MemPeer::new(b"holder");
        let cid = KotobaCid::from_bytes(b"peer-only");
        peer.store.put(&cid, b"peer-only").unwrap();
        let store = NeighborhoodBlockStore::new(local, id).with_peers(vec![peer]);
        assert!(store.has(&cid), "must see the block on a responsible peer");
    }

    #[test]
    fn respond_to_challenge_only_includes_held_blocks() {
        let (local, id) = local_node(b"local");
        let store = NeighborhoodBlockStore::new(local, id);
        let held = KotobaCid::from_bytes(b"held");
        let missing = KotobaCid::from_bytes(b"missing");
        store.put(&held, b"held").unwrap();

        let challenge = AvailabilityChallenge {
            epoch: 7,
            target_peer: store.local_id().0.to_vec(),
            challenge_cids: vec![held.0.to_vec(), missing.0.to_vec()],
            expires_at: u64::MAX,
        };
        let proof = store.respond_to_challenge(&challenge);
        assert_eq!(proof.epoch, 7);
        assert_eq!(proof.entries.len(), 1, "only the held block is proven");
        assert_eq!(proof.entries[0].cid_bytes, held.0.to_vec());
        assert_eq!(proof.entries[0].content_hash, hash_block(b"held"));
    }

    #[test]
    fn responsible_set_capped_at_k() {
        let (local, id) = local_node(b"local");
        let peers: Vec<Arc<dyn PeerTransport>> = (0..20u8)
            .map(|i| MemPeer::new(&[i, 0xAB]) as Arc<dyn PeerTransport>)
            .collect();
        let store = NeighborhoodBlockStore::new(local, id).with_peers(peers);
        let cid = KotobaCid::from_bytes(b"wide");
        store.put(&cid, b"wide").unwrap();
        // At most K peers should hold a replica.
        assert!(store.replica_count(&cid) <= K + 1, "local + at most K peers");
    }

    #[test]
    fn cid_address_is_deterministic() {
        let cid = KotobaCid::from_bytes(b"addr-test");
        assert_eq!(cid_address(&cid), cid_address(&cid));
    }

    #[test]
    fn proof_from_store_works_over_any_blockstore() {
        // The decoupled builder (used by a server XRPC endpoint over a
        // type-erased Arc<dyn BlockStore>) proves only held blocks.
        let store = MemStore::new();
        let held = KotobaCid::from_bytes(b"held");
        let missing = KotobaCid::from_bytes(b"missing");
        store.put(&held, b"held").unwrap();
        let id = NodeId::from_pubkey(b"prover");
        let challenge = AvailabilityChallenge {
            epoch: 9,
            target_peer: id.0.to_vec(),
            challenge_cids: vec![held.0.to_vec(), missing.0.to_vec()],
            expires_at: u64::MAX,
        };
        let proof = proof_from_store(store.as_ref(), &id, &challenge);
        assert_eq!(proof.epoch, 9);
        assert_eq!(proof.prover_peer, id.0.to_vec());
        assert_eq!(proof.entries.len(), 1);
        assert_eq!(proof.entries[0].content_hash, hash_block(b"held"));
    }

    /// Exercises the native concurrent replication path (`replicate_confirmed`
    /// with a live multi-thread runtime → spawn_blocking + block_in_place),
    /// which the sync unit tests above never reach.
    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn put_durable_concurrent_path_meets_target() {
        let (local, id) = local_node(b"local");
        let p1 = MemPeer::new(b"peer-1");
        let p2 = MemPeer::new(b"peer-2");
        let store = NeighborhoodBlockStore::new(local, id)
            .with_peers(vec![p1.clone(), p2.clone()])
            .with_min_replicas(3); // local + 2 peers, all concurrent
        let cid = KotobaCid::from_bytes(b"concurrent-durable");
        store.put_durable(&cid, b"concurrent-durable").unwrap();
        assert!(p1.fetch(&cid).is_some(), "peer-1 got the replica");
        assert!(p2.fetch(&cid).is_some(), "peer-2 got the replica");
    }

    /// Fire-and-forget `put` under a runtime must still land on peers (the
    /// detached blocking tasks complete); we await a brief yield to let them.
    #[tokio::test(flavor = "multi_thread", worker_threads = 2)]
    async fn put_fire_and_forget_eventually_replicates() {
        let (local, id) = local_node(b"local");
        let p1 = MemPeer::new(b"peer-1");
        let store =
            NeighborhoodBlockStore::new(local.clone(), id).with_peers(vec![p1.clone()]);
        let cid = KotobaCid::from_bytes(b"ff-block");
        store.put(&cid, b"ff-block").unwrap();
        assert!(local.has(&cid), "local write is synchronous");
        // Give the detached spawn_blocking replication a moment to finish.
        for _ in 0..50 {
            if p1.fetch(&cid).is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(2)).await;
        }
        assert!(p1.fetch(&cid).is_some(), "peer received the async replica");
    }
}
