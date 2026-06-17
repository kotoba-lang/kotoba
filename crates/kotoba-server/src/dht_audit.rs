//! Availability-audit runner (ADR-2606011330 #3 / ADR-002 p4) — the orchestration
//! that turns a fleet of nodes into a *running* audit.
//!
//! The pieces all exist: [`AvailabilityAuditor`] scores peers from this node's own
//! block copies, [`crate::dht_transport::HttpProofFetcher`] fetches their proofs
//! over real HTTP (answered by [`crate::availability_xrpc`]), and
//! [`AuditScheduler`] accumulates reputation + emits each verdict to a sink. This
//! module ties one epoch of that together and feeds a [`SettlementIntentSink`] so
//! the owed retainer / slashes are observable (`node.status`, ADR-002 p3).
//!
//! `audit_epoch` is synchronous (the HTTP fetcher uses `reqwest::blocking`) — run
//! it from `tokio::task::spawn_blocking` in a periodic loop.

use crate::dht_transport::HttpProofFetcher;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use kotoba_dht::{
    AuditAction, AuditScheduler, AvailabilityAuditor, NodeId, SettlementIntentSink,
};
use std::collections::HashMap;
use std::sync::Arc;

/// Per-action tally of one audit epoch (ADR-002 p4 observability).
#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct AuditEpochSummary {
    pub rewarded: usize,
    pub slashed: usize,
    pub unreachable: usize,
    pub none: usize,
}

impl AuditEpochSummary {
    /// Total peers audited this epoch.
    pub fn audited(&self) -> usize {
        self.rewarded + self.slashed + self.unreachable + self.none
    }
}

/// Run ONE availability-audit epoch over `endpoints` (peer `NodeId` → base URL):
/// challenge each peer for `cids`, score from `local`'s own copies, emit every
/// verdict into `sink` (reward/slash → pending `SettlementIntent`), and return
/// the tally. Peers with no reachable endpoint score `Unreachable`.
///
/// Synchronous — `HttpProofFetcher` is blocking; call via `spawn_blocking`.
pub fn audit_epoch<B>(
    local: Arc<B>,
    endpoints: HashMap<NodeId, String>,
    epoch: u64,
    cids: &[KotobaCid],
    sink: Arc<SettlementIntentSink>,
) -> AuditEpochSummary
where
    B: BlockStore + Send + Sync + 'static,
{
    let peers: Vec<NodeId> = endpoints.keys().cloned().collect();
    let auditor = AvailabilityAuditor::new(local);
    let fetcher = HttpProofFetcher::new(endpoints);
    let scheduler = AuditScheduler::new(auditor, fetcher, sink);
    let verdicts = scheduler.run_epoch(epoch, cids, &peers);

    let mut summary = AuditEpochSummary::default();
    for v in &verdicts {
        match v.action {
            AuditAction::Reward => summary.rewarded += 1,
            AuditAction::Slash => summary.slashed += 1,
            AuditAction::Unreachable => summary.unreachable += 1,
            AuditAction::None => summary.none += 1,
        }
    }
    summary
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::build_router;
    use crate::server::KotobaState;
    use kotoba_dht::{RetainerOwed, SettlementSchedule};

    /// Live HTTP audit epoch end-to-end: spin up a real server holding a block,
    /// audit it over TCP, and confirm the Reward verdict flows into the state's
    /// SettlementIntentSink and surfaces as owed retainer.
    #[tokio::test]
    async fn audit_epoch_over_http_feeds_settlement_sink() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let block = KotobaCid::from_bytes(b"audit-runner-block");
        state.block_store.put(&block, b"audit-runner-block").unwrap();
        let server_node: NodeId = state.local_node_id.clone();

        let app = build_router(state.clone());
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;

        let summary = tokio::task::spawn_blocking(move || {
            // Auditor holds its own copy so it can verify the peer's proof.
            let local = Arc::new(kotoba_store::MemoryBlockStore::new());
            local.put(&block, b"audit-runner-block").unwrap();
            let endpoints =
                HashMap::from([(server_node.clone(), format!("http://{addr}"))]);
            let sink = Arc::new(SettlementIntentSink::new(10, 5));
            let summary = audit_epoch(local, endpoints, 1, std::slice::from_ref(&block), sink.clone());

            // the reward verdict became a pending settlement intent...
            let pending = sink.snapshot();
            assert_eq!(pending.len(), 1);
            // ...and the owed-retainer view sees it.
            let owed = RetainerOwed::from_intents(&pending, SettlementSchedule::new(1));
            assert_eq!(owed.total_micros, 10, "10 reward units × 1 micro/unit");
            summary
        })
        .await
        .unwrap();

        assert_eq!(summary.rewarded, 1, "server proving possession is rewarded");
        assert_eq!(summary.slashed, 0);
        assert_eq!(summary.audited(), 1);
    }

    /// An unreachable peer (no live endpoint) is tallied Unreachable and emits no
    /// settlement intent.
    #[tokio::test]
    async fn audit_epoch_unreachable_peer_emits_no_intent() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let summary = tokio::task::spawn_blocking(|| {
            let local = Arc::new(kotoba_store::MemoryBlockStore::new());
            let block = KotobaCid::from_bytes(b"x");
            local.put(&block, b"x").unwrap();
            let dead = NodeId::from_pubkey(b"dead-peer");
            // endpoint points nowhere listening.
            let endpoints = HashMap::from([(dead, "http://127.0.0.1:1".to_string())]);
            let sink = Arc::new(SettlementIntentSink::new(10, 5));
            let summary =
                audit_epoch(local, endpoints, 1, std::slice::from_ref(&block), sink.clone());
            assert_eq!(sink.snapshot().len(), 0, "unreachable → no intent");
            summary
        })
        .await
        .unwrap();
        assert_eq!(summary.unreachable, 1);
        assert_eq!(summary.audited(), 1);
    }
}
