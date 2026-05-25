//! Entity attestation with stake enforcement.
//!
//! XRPC endpoints:
//! - POST `ai.gftd.apps.kotoba.attest.claim`      — submit or renew an attestation
//! - POST `ai.gftd.apps.kotoba.attest.challenge`  — challenge an existing attestation
//! - GET  `ai.gftd.apps.kotoba.attest.query`      — query attestation status
//! - GET  `ai.gftd.apps.kotoba.request.log`       — query audit log for requests
//!
//! Stake thresholds (mKOTO):
//! - Self-attested claim:    1,000 KOTO  = 1_000_000_000 mKOTO
//! - Verified-entity claim:  5,000 KOTO  = 5_000_000_000 mKOTO

use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use axum::{
    Json,
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
};
use serde::{Deserialize, Serialize};

use kotoba_core::cid::KotobaCid;
use kotoba_kqe::quad::{Quad, QuadObject};

use crate::server::KotobaState;

// ── NSID constants ────────────────────────────────────────────────────────────

pub const NSID_ATTEST_CLAIM:     &str = "ai.gftd.apps.kotoba.attest.claim";
pub const NSID_ATTEST_CHALLENGE: &str = "ai.gftd.apps.kotoba.attest.challenge";
pub const NSID_ATTEST_QUERY:     &str = "ai.gftd.apps.kotoba.attest.query";
pub const NSID_REQUEST_LOG:      &str = "ai.gftd.apps.kotoba.request.log";

// ── Stake constants (mKOTO) ───────────────────────────────────────────────────

/// Minimum stake for a self-attested claim: 1,000 KOTO in mKOTO.
pub const MIN_STAKE_SELF_ATTESTED: u64 = 1_000 * 1_000_000;

/// Minimum stake for a verified-entity claim: 5,000 KOTO in mKOTO.
pub const MIN_STAKE_VERIFIED_ENTITY: u64 = 5_000 * 1_000_000;

// ── Named graph helpers ───────────────────────────────────────────────────────

fn attest_graph_cid() -> KotobaCid {
    KotobaCid::from_bytes(b"kotoba/attestation/v1")
}

fn audit_graph_cid() -> KotobaCid {
    KotobaCid::from_bytes(b"kotoba/audit/requests/v1")
}

fn now_unix() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
}

// ── Request / Response types ──────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct AttestClaimReq {
    /// DID of the entity being attested.
    pub entity_did: String,
    /// Type of claim: "self" | "verified_entity" | "delegation".
    pub claim_type: String,
    /// Attester DID (who is submitting this claim).
    pub attester_did: String,
    /// Stake locked for this attestation in mKOTO.
    pub stake_mkoto: u64,
    /// Optional human-readable evidence string (URL, CID multibase, etc.).
    pub evidence: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct AttestClaimResp {
    pub status: &'static str,
    /// Multibase CID of the attestation quad (journal entry).
    pub claim_cid: String,
}

#[derive(Debug, Deserialize)]
pub struct AttestChallengeReq {
    /// Multibase CID of the claim being challenged.
    pub claim_cid: String,
    /// DID of the challenger.
    pub challenger_did: String,
    /// Reason for the challenge.
    pub reason: String,
}

#[derive(Debug, Serialize)]
pub struct AttestChallengeResp {
    pub status: &'static str,
    /// Multibase CID of the challenge quad.
    pub challenge_cid: String,
}

#[derive(Debug, Deserialize)]
pub struct AttestQueryParams {
    /// Entity DID to query.
    pub entity_did: Option<String>,
    /// Attester DID to filter by.
    pub attester_did: Option<String>,
    /// Maximum results (default 20, max 100).
    pub limit: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct AttestQueryResp {
    pub claims: Vec<AttestRecord>,
    pub total: usize,
}

#[derive(Debug, Serialize)]
pub struct AttestRecord {
    pub claim_cid: String,
    pub entity_did: String,
    pub claim_type: String,
    pub attester_did: String,
    pub stake_mkoto: u64,
    pub ts_unix: u64,
}

#[derive(Debug, Deserialize)]
pub struct RequestLogQueryParams {
    /// Filter by path prefix.
    pub path_prefix: Option<String>,
    /// Maximum results (default 20, max 100).
    pub limit: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct RequestLogResp {
    pub entries: Vec<RequestLogEntry>,
    pub total: usize,
}

#[derive(Debug, Serialize)]
pub struct RequestLogEntry {
    pub request_cid: String,
    pub method: String,
    pub path: String,
    pub ts_unix: u64,
}

// ── Handlers ─────────────────────────────────────────────────────────────────

/// POST `ai.gftd.apps.kotoba.attest.claim`
///
/// Validates stake thresholds and writes the attestation as Datoms.
pub async fn attest_claim(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<AttestClaimReq>,
) -> impl IntoResponse {
    // Enforce stake threshold based on claim type.
    let min_stake = match req.claim_type.as_str() {
        "verified_entity" | "delegation" => MIN_STAKE_VERIFIED_ENTITY,
        _ => MIN_STAKE_SELF_ATTESTED, // "self" or any unknown type
    };

    if req.stake_mkoto < min_stake {
        return (
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(serde_json::json!({
                "error": "insufficient_stake",
                "required_mkoto": min_stake,
                "provided_mkoto": req.stake_mkoto,
            })),
        )
            .into_response();
    }

    let ts = now_unix();
    let graph = attest_graph_cid();

    // Stable CID for this claim: derived from entity_did + attester_did + ts.
    let claim_seed = format!("attest/{}/{}/{}", req.entity_did, req.attester_did, ts);
    let claim_cid = KotobaCid::from_bytes(claim_seed.as_bytes());

    let entity_cid   = KotobaCid::from_bytes(req.entity_did.as_bytes());
    let attester_cid = KotobaCid::from_bytes(req.attester_did.as_bytes());

    let mut quads = vec![
        Quad {
            graph: graph.clone(),
            subject: claim_cid.clone(),
            predicate: "attest/entity".to_string(),
            object: QuadObject::Cid(entity_cid),
        },
        Quad {
            graph: graph.clone(),
            subject: claim_cid.clone(),
            predicate: "attest/type".to_string(),
            object: QuadObject::Text(req.claim_type.clone()),
        },
        Quad {
            graph: graph.clone(),
            subject: claim_cid.clone(),
            predicate: "attest/attester".to_string(),
            object: QuadObject::Cid(attester_cid),
        },
        Quad {
            graph: graph.clone(),
            subject: claim_cid.clone(),
            predicate: "attest/stake_mkoto".to_string(),
            object: QuadObject::Integer(req.stake_mkoto as i64),
        },
        Quad {
            graph: graph.clone(),
            subject: claim_cid.clone(),
            predicate: "attest/ts_unix".to_string(),
            object: QuadObject::Integer(ts as i64),
        },
    ];

    if let Some(evidence) = req.evidence {
        quads.push(Quad {
            graph: graph.clone(),
            subject: claim_cid.clone(),
            predicate: "attest/evidence".to_string(),
            object: QuadObject::Text(evidence),
        });
    }

    for quad in quads {
        state.quad_store.assert(quad).await;
    }

    let claim_cid_str = claim_cid.to_multibase();
    tracing::info!(
        entity_did = %req.entity_did,
        attester_did = %req.attester_did,
        claim_type = %req.claim_type,
        stake_mkoto = req.stake_mkoto,
        claim_cid = %claim_cid_str,
        "attestation claim recorded"
    );

    (
        StatusCode::CREATED,
        Json(AttestClaimResp {
            status: "attested",
            claim_cid: claim_cid_str,
        }),
    )
        .into_response()
}

/// POST `ai.gftd.apps.kotoba.attest.challenge`
///
/// Records a challenge against an existing attestation claim.
pub async fn attest_challenge(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<AttestChallengeReq>,
) -> impl IntoResponse {
    // Decode the claim CID from multibase (base32lower 'b' prefix).
    let claim_cid = match KotobaCid::from_multibase(&req.claim_cid) {
        Some(c) => c,
        None => {
            // Fallback: treat the string itself as content to hash.
            KotobaCid::from_bytes(req.claim_cid.as_bytes())
        }
    };

    let ts = now_unix();
    let graph = attest_graph_cid();

    // CID for this challenge.
    let challenge_seed = format!("challenge/{}/{}/{}", req.claim_cid, req.challenger_did, ts);
    let challenge_cid = KotobaCid::from_bytes(challenge_seed.as_bytes());

    let challenger_cid = KotobaCid::from_bytes(req.challenger_did.as_bytes());

    let quads = vec![
        Quad {
            graph: graph.clone(),
            subject: challenge_cid.clone(),
            predicate: "challenge/claim".to_string(),
            object: QuadObject::Cid(claim_cid),
        },
        Quad {
            graph: graph.clone(),
            subject: challenge_cid.clone(),
            predicate: "challenge/challenger".to_string(),
            object: QuadObject::Cid(challenger_cid),
        },
        Quad {
            graph: graph.clone(),
            subject: challenge_cid.clone(),
            predicate: "challenge/reason".to_string(),
            object: QuadObject::Text(req.reason.clone()),
        },
        Quad {
            graph: graph.clone(),
            subject: challenge_cid.clone(),
            predicate: "challenge/ts_unix".to_string(),
            object: QuadObject::Integer(ts as i64),
        },
    ];

    for quad in quads {
        state.quad_store.assert(quad).await;
    }

    let challenge_cid_str = challenge_cid.to_multibase();
    tracing::info!(
        claim_cid = %req.claim_cid,
        challenger_did = %req.challenger_did,
        challenge_cid = %challenge_cid_str,
        "attestation challenge recorded"
    );

    (
        StatusCode::CREATED,
        Json(AttestChallengeResp {
            status: "challenged",
            challenge_cid: challenge_cid_str,
        }),
    )
        .into_response()
}

/// GET `ai.gftd.apps.kotoba.attest.query`
///
/// Query attestation records. Currently returns a stub response; full
/// Datalog-backed query is Phase 2 (pending KQE arrangement integration).
pub async fn attest_query(
    State(_state): State<Arc<KotobaState>>,
    Query(params): Query<AttestQueryParams>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(20).min(100);

    tracing::debug!(
        entity_did = ?params.entity_did,
        attester_did = ?params.attester_did,
        limit,
        "attest.query called"
    );

    // Phase 1: return empty result; Phase 2 will scan the Arrangement.
    Json(AttestQueryResp {
        claims: Vec::new(),
        total: 0,
    })
}

/// GET `ai.gftd.apps.kotoba.request.log`
///
/// Query the request audit log stored by the fingerprint middleware.
/// Phase 1: stub response. Phase 2: scan audit graph Arrangement.
pub async fn request_log_query(
    State(_state): State<Arc<KotobaState>>,
    Query(params): Query<RequestLogQueryParams>,
) -> impl IntoResponse {
    let limit = params.limit.unwrap_or(20).min(100);
    let _graph = audit_graph_cid(); // will be used in Phase 2 Arrangement scan

    tracing::debug!(
        path_prefix = ?params.path_prefix,
        limit,
        "request.log query called"
    );

    // Phase 1: empty result.
    Json(RequestLogResp {
        entries: Vec::new(),
        total: 0,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn stake_constants_in_mkoto() {
        // 1,000 KOTO × 1,000,000 mKOTO/KOTO = 1_000_000_000
        assert_eq!(MIN_STAKE_SELF_ATTESTED, 1_000_000_000);
        // 5,000 KOTO × 1,000,000 mKOTO/KOTO = 5_000_000_000
        assert_eq!(MIN_STAKE_VERIFIED_ENTITY, 5_000_000_000);
    }

    #[test]
    fn nsids_have_correct_prefix() {
        for nsid in &[
            NSID_ATTEST_CLAIM,
            NSID_ATTEST_CHALLENGE,
            NSID_ATTEST_QUERY,
            NSID_REQUEST_LOG,
        ] {
            assert!(
                nsid.starts_with("ai.gftd.apps.kotoba."),
                "NSID does not start with ai.gftd.apps.kotoba.: {nsid}"
            );
        }
    }

    #[test]
    fn attest_graph_cid_is_stable() {
        let a = attest_graph_cid();
        let b = attest_graph_cid();
        assert_eq!(a.0, b.0);
    }
}
