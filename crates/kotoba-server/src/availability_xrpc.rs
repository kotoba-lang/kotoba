//! Availability-challenge XRPC endpoint (ADR-2606011330 #1).
//!
//! The server-side half of the live `ProofFetcher`: a peer POSTs an
//! `AvailabilityChallenge` and this node answers with an `AvailabilityProof`
//! built from its own block store via `kotoba_dht::proof_from_store` over the
//! type-erased `Arc<dyn BlockStore>`. The client half is
//! `crate::dht_transport::HttpProofFetcher`, which turns this endpoint into a
//! `ProofFetcher` usable by `AuditScheduler` over a real network.
//!
//! Auth: intentionally **open** — an availability proof reveals only possession
//! of CIDs the challenger already names, which is the entire point of the audit
//! protocol. Peer-authentication of challengers is a follow-up (not a
//! confidentiality gate). The signature on the returned proof is left empty
//! here; the transport/gossip layer signs (ADR-2606011330).

use crate::server::KotobaState;
use axum::{extract::State, response::IntoResponse, Json};
use kotoba_dht::availability_proof::AvailabilityChallenge;
use std::sync::Arc;

pub const NSID_AVAILABILITY_CHALLENGE: &str = "ai.gftd.apps.kotoba.dht.availability_challenge";

/// Answer an availability challenge from this node's block store.
pub async fn availability_challenge(
    State(state): State<Arc<KotobaState>>,
    Json(challenge): Json<AvailabilityChallenge>,
) -> impl IntoResponse {
    let proof = kotoba_dht::proof_from_store(
        state.block_store.as_ref(),
        &state.local_node_id,
        &challenge,
    );
    Json(proof)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::build_router;
    use axum::http::Request;
    use kotoba_core::cid::KotobaCid;
    use kotoba_core::store::BlockStore as _;
    use kotoba_dht::availability_proof::AvailabilityProof;
    use tower::ServiceExt;

    #[tokio::test]
    async fn challenge_endpoint_proves_only_held_blocks() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = Arc::new(KotobaState::new(None).expect("state"));

        // Hold one block; the other is absent.
        let held = KotobaCid::from_bytes(b"avail-xrpc-held");
        state.block_store.put(&held, b"avail-xrpc-held").unwrap();
        let missing = KotobaCid::from_bytes(b"avail-xrpc-missing");

        let challenge = AvailabilityChallenge {
            epoch: 3,
            target_peer: state.local_node_id.0.to_vec(),
            challenge_cids: vec![held.0.to_vec(), missing.0.to_vec()],
            expires_at: u64::MAX,
        };

        let app = build_router(state.clone());
        let body = serde_json::to_vec(&challenge).unwrap();
        let req = Request::builder()
            .method("POST")
            .uri(format!("/xrpc/{NSID_AVAILABILITY_CHALLENGE}"))
            .header("content-type", "application/json")
            .body(axum::body::Body::from(body))
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::OK);

        let bytes = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        let proof: AvailabilityProof = serde_json::from_slice(&bytes).unwrap();
        assert_eq!(proof.epoch, 3);
        assert_eq!(proof.entries.len(), 1, "only the held block is proven");
        assert_eq!(proof.entries[0].cid_bytes, held.0.to_vec());
    }

    /// End-to-end LIVE audit loop over real HTTP (ADR-2606011330 #1, full close):
    /// AuditScheduler → HttpProofFetcher → TCP → availability endpoint →
    /// proof_from_store → verify_proof → Reward → reputation. Binds a real axum
    /// server on an ephemeral port; the blocking fetcher runs off-runtime via
    /// spawn_blocking.
    #[tokio::test]
    async fn live_http_audit_loop_rewards_holding_server() {
        use crate::dht_transport::HttpProofFetcher;
        use kotoba_dht::{
            AuditAction, AuditScheduler, AvailabilityAuditor, InMemoryVerdictSink, NodeId,
        };
        use std::collections::HashMap;

        std::env::set_var("KOTOBA_IPFS", "off");
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let block = KotobaCid::from_bytes(b"live-audit-block");
        state.block_store.put(&block, b"live-audit-block").unwrap();
        let server_node: NodeId = state.local_node_id.clone();

        // Serve the router on an ephemeral port.
        let app = build_router(state.clone());
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();
        tokio::spawn(async move {
            axum::serve(listener, app).await.unwrap();
        });
        tokio::time::sleep(std::time::Duration::from_millis(50)).await;

        // Auditor holds its own copy (so it can verify); fetcher targets the
        // live server as the peer. reqwest::blocking → run off the runtime.
        let action = tokio::task::spawn_blocking(move || {
            let local = Arc::new(kotoba_store::MemoryBlockStore::new());
            local.put(&block, b"live-audit-block").unwrap();
            let auditor = AvailabilityAuditor::new(local);
            let endpoints = HashMap::from([(server_node.clone(), format!("http://{addr}"))]);
            let fetcher = HttpProofFetcher::new(endpoints);
            let sched = AuditScheduler::new(auditor, fetcher, InMemoryVerdictSink::default());
            let verdicts = sched.run_epoch(1, &[block.clone()], &[server_node.clone()]);
            verdicts[0].action.clone()
        })
        .await
        .unwrap();

        assert_eq!(
            action,
            AuditAction::Reward,
            "a server proving possession over live HTTP must be rewarded"
        );
    }
}
