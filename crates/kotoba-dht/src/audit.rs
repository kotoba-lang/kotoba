//! Availability audit — the epoch challenge → proof → verdict loop.
//!
//! Per **ADR-2606011330**, this is the "validating" half of the validating DHT:
//! it ties the prover side (`NeighborhoodBlockStore::respond_to_challenge`) to
//! the verifier side (`availability_proof::verify_proof`) into one runnable
//! epoch, producing a reward / slash / none verdict per peer.
//!
//! The auditor is itself a holder of (some of) the challenged blocks — it
//! re-computes the expected blake3 hashes from its **own** local copy and
//! compares them to each peer's answer. Peers that prove possession score high
//! (reward); peers that cannot score low (slash); blocks the auditor does not
//! hold are excluded from scoring (it cannot verify what it lacks).
//!
//! ## Scope (honest)
//!
//! This is the **deterministic core** of the loop, transport-free and fully
//! unit-tested in-memory. The network transport (`ProofFetcher` over libp2p
//! GossipSub) and the on-chain reward/slash settlement (USDC on Base L2) are
//! separate increments — `AuditAction` is the hand-off boundary to them.

use crate::availability_proof::{
    verify_proof, AvailabilityChallenge, AvailabilityProof, VerificationResult,
};
use crate::node_id::NodeId;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::sync::Arc;

/// Supplies a peer's `AvailabilityProof` for a challenge. In production this is
/// a network round-trip (request over GossipSub / libp2p, await the signed
/// proof); in tests it is an in-memory call into the peer's store. Returns
/// `None` when the peer is unreachable or declines to answer.
pub trait ProofFetcher: Send + Sync {
    fn request_proof(
        &self,
        peer: &NodeId,
        challenge: &AvailabilityChallenge,
    ) -> Option<AvailabilityProof>;
}

/// What the auditor decides to do about a peer this epoch. This is the boundary
/// handed to the (separate) incentive layer — `Reward`/`Slash` map to USDC-on-
/// Base settlement once that contract lands (Council-ratify-gated).
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum AuditAction {
    /// score ≥ 0.80 — peer reliably holds its share.
    Reward,
    /// score < 0.50 — peer failed to prove possession.
    Slash,
    /// 0.50 ≤ score < 0.80, or nothing checkable — no action.
    None,
    /// Peer did not return a usable proof (offline / declined / epoch mismatch).
    Unreachable,
}

/// Per-peer outcome of one audit epoch.
#[derive(Debug, Clone)]
pub struct PeerAudit {
    pub peer: NodeId,
    /// `None` when the peer was unreachable or the proof failed sanity checks.
    pub result: Option<VerificationResult>,
    pub action: AuditAction,
}

/// Runs availability-audit epochs against a set of peers, scoring each from the
/// auditor's own copy of the challenged blocks.
pub struct AvailabilityAuditor {
    /// The auditor's local store (source of the expected hashes).
    local: Arc<dyn BlockStore>,
}

impl AvailabilityAuditor {
    pub fn new(local: Arc<dyn BlockStore>) -> Self {
        Self { local }
    }

    /// Build the per-peer challenge for an epoch.
    fn challenge_for(&self, epoch: u64, peer: &NodeId, cids: &[KotobaCid]) -> AvailabilityChallenge {
        AvailabilityChallenge {
            epoch,
            target_peer: peer.0.to_vec(),
            challenge_cids: cids.iter().map(|c| c.0.to_vec()).collect(),
            expires_at: u64::MAX,
        }
    }

    /// Expected blake3 hashes for the challenged CIDs, computed from the
    /// auditor's own store. `None` for blocks the auditor does not hold (those
    /// are excluded from a peer's score — we cannot verify what we lack).
    fn expected_hashes(&self, cids: &[KotobaCid]) -> Vec<Option<Vec<u8>>> {
        cids.iter()
            .map(|cid| {
                self.local
                    .get(cid)
                    .ok()
                    .flatten()
                    .map(|b| crate::availability_proof::hash_block(&b))
            })
            .collect()
    }

    /// Run one audit epoch: challenge every peer for `cids`, fetch and verify
    /// their proofs, and return a verdict per peer.
    pub fn run_epoch<F: ProofFetcher>(
        &self,
        epoch: u64,
        cids: &[KotobaCid],
        peers: &[NodeId],
        fetcher: &F,
    ) -> Vec<PeerAudit> {
        let expected = self.expected_hashes(cids);
        peers
            .iter()
            .map(|peer| {
                let challenge = self.challenge_for(epoch, peer, cids);
                match fetcher.request_proof(peer, &challenge) {
                    None => PeerAudit {
                        peer: peer.clone(),
                        result: None,
                        action: AuditAction::Unreachable,
                    },
                    Some(proof) => match verify_proof(&challenge, &proof, &expected) {
                        None => PeerAudit {
                            peer: peer.clone(),
                            result: None,
                            action: AuditAction::Unreachable,
                        },
                        Some(result) => {
                            let action = if result.eligible_for_reward() {
                                AuditAction::Reward
                            } else if result.trigger_slash() {
                                AuditAction::Slash
                            } else {
                                AuditAction::None
                            };
                            PeerAudit {
                                peer: peer.clone(),
                                result: Some(result),
                                action,
                            }
                        }
                    },
                }
            })
            .collect()
    }
}

/// Running reputation for a peer accumulated across audit epochs. This is what
/// makes a single reward/slash verdict *mean* something: a peer's standing is
/// its history, not one epoch.
#[derive(Debug, Clone, Default)]
pub struct PeerReputation {
    pub rewards: u64,
    pub slashes: u64,
    pub unreachable: u64,
    pub epochs: u64,
    /// Consecutive slash-or-unreachable epochs (reset by Reward / None).
    pub consecutive_failures: u64,
    pub last_score: Option<f64>,
}

impl PeerReputation {
    fn apply(&mut self, audit: &PeerAudit) {
        self.epochs += 1;
        if let Some(r) = &audit.result {
            self.last_score = Some(r.score);
        }
        match audit.action {
            AuditAction::Reward => {
                self.rewards += 1;
                self.consecutive_failures = 0;
            }
            AuditAction::Slash => {
                self.slashes += 1;
                self.consecutive_failures += 1;
            }
            AuditAction::Unreachable => {
                self.unreachable += 1;
                self.consecutive_failures += 1;
            }
            AuditAction::None => {
                self.consecutive_failures = 0;
            }
        }
    }

    /// A peer is distrusted once it racks up `threshold` consecutive failures —
    /// the signal to stop counting it toward a block's replica target and to
    /// re-replicate its share elsewhere.
    pub fn is_distrusted(&self, threshold: u64) -> bool {
        self.consecutive_failures >= threshold
    }
}

/// Receives each epoch verdict — the hand-off boundary to the incentive layer.
/// `Reward` / `Slash` map to USDC-on-Base-L2 settlement once that contract
/// lands (ADR-2605172100; Council-ratify-gated). `InMemoryVerdictSink` is the
/// reference impl and test double.
pub trait VerdictSink: Send + Sync {
    fn record(&self, epoch: u64, audit: &PeerAudit);
}

/// In-memory verdict log — reference `VerdictSink` and test double. The on-chain
/// sink will implement the same trait and settle Reward/Slash on Base L2.
#[derive(Default)]
pub struct InMemoryVerdictSink {
    pub records: std::sync::Mutex<Vec<(u64, NodeId, AuditAction)>>,
}

impl VerdictSink for InMemoryVerdictSink {
    fn record(&self, epoch: u64, audit: &PeerAudit) {
        self.records
            .lock()
            .unwrap()
            .push((epoch, audit.peer.clone(), audit.action.clone()));
    }
}

/// Lets a sink be shared (e.g. inspected by the caller while the scheduler owns
/// a clone) without giving up ownership.
impl<T: VerdictSink> VerdictSink for std::sync::Arc<T> {
    fn record(&self, epoch: u64, audit: &PeerAudit) {
        (**self).record(epoch, audit);
    }
}

/// Whether a settlement rewards or slashes a peer.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SettlementKind {
    Reward,
    Slash,
}

/// A pending settlement produced from an audit verdict — the concrete artifact
/// the (Council-ratify-gated) on-chain executor consumes to settle on Base L2
/// (ADR-2605172100). `units` are policy-determined points resolved to USDC by
/// that executor under the reward/slash schedule; they are NOT fiat amounts.
///
/// **Recording an intent moves NO funds.** This substrate holds no signing key
/// (no-server-key posture, ADR-2605231525); actual settlement is a separate,
/// gated, member/Council-signed action. There is deliberately no `transfer()`
/// here — this is the propose-only boundary.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SettlementIntent {
    pub epoch: u64,
    pub peer: NodeId,
    pub kind: SettlementKind,
    pub units: u64,
}

/// `VerdictSink` that turns `Reward` / `Slash` verdicts into pending
/// `SettlementIntent`s. `None` / `Unreachable` produce no intent. The on-chain
/// executor later drains and settles these; nothing here touches funds.
#[derive(Default)]
pub struct SettlementIntentSink {
    reward_units: u64,
    slash_units: u64,
    pending: std::sync::Mutex<Vec<SettlementIntent>>,
}

impl SettlementIntentSink {
    pub fn new(reward_units: u64, slash_units: u64) -> Self {
        Self {
            reward_units,
            slash_units,
            pending: std::sync::Mutex::new(Vec::new()),
        }
    }

    /// Number of pending (unsettled) intents.
    pub fn pending_len(&self) -> usize {
        self.pending.lock().unwrap().len()
    }

    /// Take all pending intents (hand-off to the gated on-chain executor).
    pub fn drain(&self) -> Vec<SettlementIntent> {
        std::mem::take(&mut *self.pending.lock().unwrap())
    }
}

impl VerdictSink for SettlementIntentSink {
    fn record(&self, epoch: u64, audit: &PeerAudit) {
        let intent = match audit.action {
            AuditAction::Reward => Some(SettlementIntent {
                epoch,
                peer: audit.peer.clone(),
                kind: SettlementKind::Reward,
                units: self.reward_units,
            }),
            AuditAction::Slash => Some(SettlementIntent {
                epoch,
                peer: audit.peer.clone(),
                kind: SettlementKind::Slash,
                units: self.slash_units,
            }),
            AuditAction::None | AuditAction::Unreachable => None,
        };
        if let Some(i) = intent {
            self.pending.lock().unwrap().push(i);
        }
    }
}

/// Runs audit epochs over a peer set, accumulates per-peer reputation, and emits
/// every verdict to a `VerdictSink`. This is the runnable validating loop: only
/// the `ProofFetcher` (live libp2p transport) and the on-chain `VerdictSink`
/// remain as swap-ins for R3 — both are exercised here via in-memory doubles.
pub struct AuditScheduler<F: ProofFetcher, S: VerdictSink> {
    auditor: AvailabilityAuditor,
    fetcher: F,
    sink: S,
    reputations: std::sync::Mutex<std::collections::HashMap<NodeId, PeerReputation>>,
    distrust_threshold: u64,
}

impl<F: ProofFetcher, S: VerdictSink> AuditScheduler<F, S> {
    pub fn new(auditor: AvailabilityAuditor, fetcher: F, sink: S) -> Self {
        Self {
            auditor,
            fetcher,
            sink,
            reputations: std::sync::Mutex::new(std::collections::HashMap::new()),
            distrust_threshold: 3,
        }
    }

    /// Consecutive-failure count at which a peer becomes distrusted (default 3).
    pub fn with_distrust_threshold(mut self, n: u64) -> Self {
        self.distrust_threshold = n.max(1);
        self
    }

    /// Run one audit epoch: score every peer for `cids`, update reputations,
    /// emit verdicts to the sink, and return them.
    pub fn run_epoch(&self, epoch: u64, cids: &[KotobaCid], peers: &[NodeId]) -> Vec<PeerAudit> {
        let verdicts = self.auditor.run_epoch(epoch, cids, peers, &self.fetcher);
        let mut reps = self.reputations.lock().unwrap();
        for a in &verdicts {
            reps.entry(a.peer.clone()).or_default().apply(a);
            self.sink.record(epoch, a);
        }
        verdicts
    }

    pub fn reputation(&self, peer: &NodeId) -> Option<PeerReputation> {
        self.reputations.lock().unwrap().get(peer).cloned()
    }

    /// Peers that have hit the distrust threshold — their replica share should
    /// be re-replicated elsewhere and they should not count toward durability.
    pub fn distrusted_peers(&self) -> Vec<NodeId> {
        let t = self.distrust_threshold;
        self.reputations
            .lock()
            .unwrap()
            .iter()
            .filter(|(_, r)| r.is_distrusted(t))
            .map(|(id, _)| id.clone())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::neighborhood_store::NeighborhoodBlockStore;
    use bytes::Bytes;
    use std::collections::HashMap;
    use std::sync::Mutex;

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
    }

    /// A fetcher backed by per-peer NeighborhoodBlockStores: routes the
    /// challenge to the store whose `local_id` matches the target peer and
    /// returns its real `respond_to_challenge` proof. Peers not in the map are
    /// treated as unreachable.
    struct LocalFetcher {
        stores: HashMap<NodeId, Arc<NeighborhoodBlockStore>>,
    }
    impl ProofFetcher for LocalFetcher {
        fn request_proof(
            &self,
            peer: &NodeId,
            challenge: &AvailabilityChallenge,
        ) -> Option<AvailabilityProof> {
            self.stores.get(peer).map(|s| s.respond_to_challenge(challenge))
        }
    }

    fn peer_store(tag: &[u8]) -> (NodeId, Arc<NeighborhoodBlockStore>, Arc<MemStore>) {
        let id = NodeId::from_pubkey(tag);
        let backing = MemStore::new();
        let store = Arc::new(NeighborhoodBlockStore::new(backing.clone(), id.clone()));
        (id, store, backing)
    }

    fn cids(seeds: &[&[u8]]) -> Vec<KotobaCid> {
        seeds.iter().map(|s| KotobaCid::from_bytes(s)).collect()
    }

    #[test]
    fn peer_holding_all_blocks_is_rewarded() {
        let blocks = cids(&[b"a", b"b", b"c"]);
        // Auditor holds all blocks (so it can verify).
        let auditor_store = MemStore::new();
        for (i, c) in blocks.iter().enumerate() {
            auditor_store.put(c, [b"a", b"b", b"c"][i]).unwrap();
        }
        let auditor = AvailabilityAuditor::new(auditor_store);

        // Peer also holds all blocks.
        let (pid, pstore, _pbk) = peer_store(b"good-peer");
        for (i, c) in blocks.iter().enumerate() {
            pstore.put(c, [b"a", b"b", b"c"][i]).unwrap();
        }
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore)]),
        };

        let verdicts = auditor.run_epoch(1, &blocks, &[pid], &fetcher);
        assert_eq!(verdicts.len(), 1);
        assert_eq!(verdicts[0].action, AuditAction::Reward);
        assert_eq!(verdicts[0].result.as_ref().unwrap().score, 1.0);
    }

    #[test]
    fn peer_holding_nothing_is_slashed() {
        let blocks = cids(&[b"a", b"b", b"c"]);
        let auditor_store = MemStore::new();
        for (i, c) in blocks.iter().enumerate() {
            auditor_store.put(c, [b"a", b"b", b"c"][i]).unwrap();
        }
        let auditor = AvailabilityAuditor::new(auditor_store);

        // Peer holds NONE of the blocks → empty proof → score 0 → slash.
        let (pid, pstore, _pbk) = peer_store(b"bad-peer");
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore)]),
        };

        let verdicts = auditor.run_epoch(1, &blocks, &[pid], &fetcher);
        assert_eq!(verdicts[0].action, AuditAction::Slash);
        assert_eq!(verdicts[0].result.as_ref().unwrap().score, 0.0);
    }

    #[test]
    fn unreachable_peer_is_flagged() {
        let blocks = cids(&[b"a"]);
        let auditor_store = MemStore::new();
        auditor_store.put(&blocks[0], b"a").unwrap();
        let auditor = AvailabilityAuditor::new(auditor_store);

        let absent = NodeId::from_pubkey(b"never-registered");
        let fetcher = LocalFetcher {
            stores: HashMap::new(),
        };
        let verdicts = auditor.run_epoch(1, &blocks, &[absent], &fetcher);
        assert_eq!(verdicts[0].action, AuditAction::Unreachable);
        assert!(verdicts[0].result.is_none());
    }

    #[test]
    fn partial_holder_gets_no_action() {
        // 2 of 3 held → score ≈ 0.67 → no reward, no slash.
        let blocks = cids(&[b"a", b"b", b"c"]);
        let payloads: [&[u8]; 3] = [b"a", b"b", b"c"];
        let auditor_store = MemStore::new();
        for (i, c) in blocks.iter().enumerate() {
            auditor_store.put(c, payloads[i]).unwrap();
        }
        let auditor = AvailabilityAuditor::new(auditor_store);

        let (pid, pstore, _pbk) = peer_store(b"partial-peer");
        pstore.put(&blocks[0], payloads[0]).unwrap();
        pstore.put(&blocks[1], payloads[1]).unwrap();
        // third block missing
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore)]),
        };

        let verdicts = auditor.run_epoch(1, &blocks, &[pid], &fetcher);
        assert_eq!(verdicts[0].action, AuditAction::None);
        let score = verdicts[0].result.as_ref().unwrap().score;
        assert!((score - 2.0 / 3.0).abs() < 1e-9, "score was {score}");
    }

    #[test]
    fn mixed_fleet_one_reward_one_slash_one_unreachable() {
        let blocks = cids(&[b"x", b"y"]);
        let payloads: [&[u8]; 2] = [b"x", b"y"];
        let auditor_store = MemStore::new();
        for (i, c) in blocks.iter().enumerate() {
            auditor_store.put(c, payloads[i]).unwrap();
        }
        let auditor = AvailabilityAuditor::new(auditor_store);

        let (good, good_store, _g) = peer_store(b"good");
        for (i, c) in blocks.iter().enumerate() {
            good_store.put(c, payloads[i]).unwrap();
        }
        let (bad, bad_store, _b) = peer_store(b"bad"); // holds nothing
        let gone = NodeId::from_pubkey(b"gone");

        let fetcher = LocalFetcher {
            stores: HashMap::from([(good.clone(), good_store), (bad.clone(), bad_store)]),
        };
        let verdicts = auditor.run_epoch(7, &blocks, &[good, bad, gone], &fetcher);
        assert_eq!(verdicts[0].action, AuditAction::Reward);
        assert_eq!(verdicts[1].action, AuditAction::Slash);
        assert_eq!(verdicts[2].action, AuditAction::Unreachable);
    }

    // ---- Scheduler: multi-epoch reputation + verdict sink (R3 #1/#2 cores) ----

    fn auditor_holding(blocks: &[KotobaCid], payloads: &[&[u8]]) -> AvailabilityAuditor {
        let store = MemStore::new();
        for (c, p) in blocks.iter().zip(payloads) {
            store.put(c, p).unwrap();
        }
        AvailabilityAuditor::new(store)
    }

    #[test]
    fn scheduler_accrues_reward_reputation_over_epochs() {
        let blocks = cids(&[b"a", b"b"]);
        let payloads: [&[u8]; 2] = [b"a", b"b"];
        let auditor = auditor_holding(&blocks, &payloads);

        let (pid, pstore, _bk) = peer_store(b"reliable");
        for (c, p) in blocks.iter().zip(payloads.iter()) {
            pstore.put(c, p).unwrap();
        }
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore)]),
        };
        let sched = AuditScheduler::new(auditor, fetcher, InMemoryVerdictSink::default());

        for epoch in 0..3 {
            sched.run_epoch(epoch, &blocks, &[pid.clone()]);
        }
        let rep = sched.reputation(&pid).unwrap();
        assert_eq!(rep.epochs, 3);
        assert_eq!(rep.rewards, 3);
        assert_eq!(rep.slashes, 0);
        assert_eq!(rep.consecutive_failures, 0);
        assert!(sched.distrusted_peers().is_empty());
    }

    #[test]
    fn scheduler_distrusts_peer_after_consecutive_failures() {
        let blocks = cids(&[b"a", b"b"]);
        let payloads: [&[u8]; 2] = [b"a", b"b"];
        let auditor = auditor_holding(&blocks, &payloads);

        // Peer holds nothing → slashed every epoch.
        let (pid, pstore, _bk) = peer_store(b"flaky");
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore)]),
        };
        let sched = AuditScheduler::new(auditor, fetcher, InMemoryVerdictSink::default())
            .with_distrust_threshold(3);

        for epoch in 0..2 {
            sched.run_epoch(epoch, &blocks, &[pid.clone()]);
        }
        assert!(
            sched.distrusted_peers().is_empty(),
            "2 slashes < threshold 3"
        );
        sched.run_epoch(2, &blocks, &[pid.clone()]); // 3rd consecutive slash
        let rep = sched.reputation(&pid).unwrap();
        assert_eq!(rep.slashes, 3);
        assert_eq!(rep.consecutive_failures, 3);
        assert_eq!(sched.distrusted_peers(), vec![pid]);
    }

    #[test]
    fn scheduler_reward_resets_consecutive_failures() {
        let blocks = cids(&[b"a"]);
        let payloads: [&[u8]; 1] = [b"a"];
        let auditor = auditor_holding(&blocks, &payloads);

        // Peer starts empty (slash), then gains the block (reward).
        let (pid, pstore, _bk) = peer_store(b"recovering");
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore.clone())]),
        };
        let sched = AuditScheduler::new(auditor, fetcher, InMemoryVerdictSink::default())
            .with_distrust_threshold(3);

        sched.run_epoch(0, &blocks, &[pid.clone()]); // slash
        sched.run_epoch(1, &blocks, &[pid.clone()]); // slash
        pstore.put(&blocks[0], payloads[0]).unwrap(); // peer recovers the block
        sched.run_epoch(2, &blocks, &[pid.clone()]); // reward → reset
        let rep = sched.reputation(&pid).unwrap();
        assert_eq!(rep.slashes, 2);
        assert_eq!(rep.rewards, 1);
        assert_eq!(rep.consecutive_failures, 0, "reward must reset the streak");
        assert!(sched.distrusted_peers().is_empty());
    }

    #[test]
    fn scheduler_emits_every_verdict_to_sink() {
        let blocks = cids(&[b"a"]);
        let payloads: [&[u8]; 1] = [b"a"];
        let auditor = auditor_holding(&blocks, &payloads);
        let (pid, pstore, _bk) = peer_store(b"sink-peer");
        pstore.put(&blocks[0], payloads[0]).unwrap();
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore)]),
        };
        let sink = std::sync::Arc::new(InMemoryVerdictSink::default());
        let sched = AuditScheduler::new(auditor, fetcher, sink.clone());
        sched.run_epoch(0, &blocks, &[pid.clone()]);
        sched.run_epoch(1, &blocks, &[pid.clone()]);
        let recs = sink.records.lock().unwrap();
        assert_eq!(recs.len(), 2, "every epoch's verdict reaches the sink");
        assert!(recs.iter().all(|(_, _, a)| *a == AuditAction::Reward));
        assert_eq!(recs[0].0, 0);
        assert_eq!(recs[1].0, 1);
    }

    // ---- Settlement-intent sink (R3/#2 Base L2 hand-off boundary) ----

    fn audit_with(action: AuditAction) -> PeerAudit {
        PeerAudit {
            peer: NodeId::from_pubkey(b"p"),
            result: None,
            action,
        }
    }

    #[test]
    fn settlement_sink_emits_reward_and_slash_intents_only() {
        let sink = SettlementIntentSink::new(100, 50);
        sink.record(1, &audit_with(AuditAction::Reward));
        sink.record(2, &audit_with(AuditAction::Slash));
        sink.record(3, &audit_with(AuditAction::None));
        sink.record(4, &audit_with(AuditAction::Unreachable));
        assert_eq!(sink.pending_len(), 2, "only Reward + Slash settle");

        let intents = sink.drain();
        assert_eq!(intents.len(), 2);
        assert_eq!(intents[0].kind, SettlementKind::Reward);
        assert_eq!(intents[0].units, 100);
        assert_eq!(intents[0].epoch, 1);
        assert_eq!(intents[1].kind, SettlementKind::Slash);
        assert_eq!(intents[1].units, 50);
        assert_eq!(sink.pending_len(), 0, "drain empties the queue");
    }

    #[test]
    fn scheduler_feeds_settlement_intents() {
        // End-to-end: a reliable peer over 2 epochs → 2 reward intents queued.
        let blocks = cids(&[b"a"]);
        let payloads: [&[u8]; 1] = [b"a"];
        let auditor = auditor_holding(&blocks, &payloads);
        let (pid, pstore, _bk) = peer_store(b"settle-peer");
        pstore.put(&blocks[0], payloads[0]).unwrap();
        let fetcher = LocalFetcher {
            stores: HashMap::from([(pid.clone(), pstore)]),
        };
        let sink = std::sync::Arc::new(SettlementIntentSink::new(10, 7));
        let sched = AuditScheduler::new(auditor, fetcher, sink.clone());
        sched.run_epoch(0, &blocks, &[pid.clone()]);
        sched.run_epoch(1, &blocks, &[pid]);
        let intents = sink.drain();
        assert_eq!(intents.len(), 2);
        assert!(intents.iter().all(|i| i.kind == SettlementKind::Reward && i.units == 10));
    }
}
