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
use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use kotoba_dht::availability_proof::AvailabilityChallenge;
use std::sync::Arc;

pub const NSID_AVAILABILITY_CHALLENGE: &str =
    "com.etzhayyim.apps.kotoba.dht.availability_challenge";

const MAX_CHALLENGE_CIDS: usize = 1024;
const KOTOBA_CID_BYTES: usize = 36;
const NODE_ID_BYTES: usize = 32;

fn validate_challenge(
    local_node_id: &[u8],
    challenge: &AvailabilityChallenge,
) -> Result<(), (StatusCode, String)> {
    if challenge.target_peer.len() != NODE_ID_BYTES {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("target_peer must be {NODE_ID_BYTES} bytes"),
        ));
    }
    if challenge.target_peer.as_slice() != local_node_id {
        return Err((
            StatusCode::BAD_REQUEST,
            "target_peer does not match this node".to_string(),
        ));
    }
    if challenge.challenge_cids.len() > MAX_CHALLENGE_CIDS {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("challenge_cids exceeds {MAX_CHALLENGE_CIDS} entries"),
        ));
    }
    for (idx, cid) in challenge.challenge_cids.iter().enumerate() {
        if cid.len() != KOTOBA_CID_BYTES {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("challenge_cids[{idx}] must be {KOTOBA_CID_BYTES} bytes"),
            ));
        }
    }
    Ok(())
}

/// Answer an availability challenge from this node's block store.
pub async fn availability_challenge(
    State(state): State<Arc<KotobaState>>,
    Json(challenge): Json<AvailabilityChallenge>,
) -> impl IntoResponse {
    if let Err((status, msg)) = validate_challenge(&state.local_node_id.0, &challenge) {
        return (status, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    let proof =
        kotoba_dht::proof_from_store(state.block_store.as_ref(), &state.local_node_id, &challenge);
    Json(proof).into_response()
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

    fn challenge_for(state: &KotobaState, cids: Vec<Vec<u8>>) -> AvailabilityChallenge {
        AvailabilityChallenge {
            epoch: 3,
            target_peer: state.local_node_id.0.to_vec(),
            challenge_cids: cids,
            expires_at: u64::MAX,
        }
    }

    #[test]
    fn availability_challenge_validation_rejects_wrong_peer_and_malformed_cids() {
        let state = KotobaState::new(None).expect("state");
        let cid = KotobaCid::from_bytes(b"availability-validation-cid");

        let valid = challenge_for(&state, vec![cid.0.to_vec()]);
        assert!(validate_challenge(&state.local_node_id.0, &valid).is_ok());

        let mut wrong_peer = valid.clone();
        wrong_peer.target_peer = vec![0u8; NODE_ID_BYTES];
        assert!(validate_challenge(&state.local_node_id.0, &wrong_peer).is_err());

        let mut short_peer = valid.clone();
        short_peer.target_peer = vec![0u8; NODE_ID_BYTES - 1];
        assert!(validate_challenge(&state.local_node_id.0, &short_peer).is_err());

        let malformed_cid = challenge_for(&state, vec![vec![1u8; KOTOBA_CID_BYTES - 1]]);
        assert!(validate_challenge(&state.local_node_id.0, &malformed_cid).is_err());

        let oversized = challenge_for(&state, vec![cid.0.to_vec(); MAX_CHALLENGE_CIDS + 1]);
        assert!(validate_challenge(&state.local_node_id.0, &oversized).is_err());
    }

    #[tokio::test]
    async fn challenge_endpoint_proves_only_held_blocks() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = Arc::new(KotobaState::new(None).expect("state"));

        // Hold one block; the other is absent.
        let held = KotobaCid::from_bytes(b"avail-xrpc-held");
        state.block_store.put(&held, b"avail-xrpc-held").unwrap();
        let missing = KotobaCid::from_bytes(b"avail-xrpc-missing");

        let challenge = challenge_for(&state, vec![held.0.to_vec(), missing.0.to_vec()]);

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

    #[tokio::test]
    async fn challenge_endpoint_rejects_malformed_cid_bytes() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let challenge = challenge_for(&state, vec![vec![9u8; KOTOBA_CID_BYTES - 1]]);

        let app = build_router(state.clone());
        let body = serde_json::to_vec(&challenge).unwrap();
        let req = Request::builder()
            .method("POST")
            .uri(format!("/xrpc/{NSID_AVAILABILITY_CHALLENGE}"))
            .header("content-type", "application/json")
            .body(axum::body::Body::from(body))
            .unwrap();

        let resp = app.oneshot(req).await.unwrap();
        assert_eq!(resp.status(), axum::http::StatusCode::BAD_REQUEST);
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
            let verdicts = sched.run_epoch(
                1,
                std::slice::from_ref(&block),
                std::slice::from_ref(&server_node),
            );
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
