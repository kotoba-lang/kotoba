//! PDS XRPC surface on kotoba-server (ADR-2606015000 — PDS refactor onto kotoba).
//!
//! First landed endpoint: session PoP verification — the kotoba-server-native
//! replacement for the legacy TS PDS delegating session checks to the auth Worker.
//! Additional AT Protocol PDS endpoints (createSession/refreshSession/repo.*/
//! sync.*) are ported in subsequent increments of the refactor.

pub const NSID_PDS_SESSION_VERIFY: &str = "ai.gftd.pds.session.verify";

use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use serde::Deserialize;
use std::sync::Arc;

use crate::pds_session::verify_session_pop;
use crate::server::{HttpDidDocumentFetcher, KotobaState};
use kotoba_auth::resolver::CompositeDidResolver;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionVerifyReq {
    /// Compact EdDSA JWS session PoP signed by the member's session key.
    pub token: String,
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

pub async fn session_verify(
    State(_state): State<Arc<KotobaState>>,
    Json(req): Json<SessionVerifyReq>,
) -> impl IntoResponse {
    if req.token.is_empty() || req.token.len() > 8192 {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({ "valid": false, "reason": "token required (1–8192 bytes)" })),
        );
    }
    // did:key resolves trustlessly (no network); did:web/plc fetch the authoritative
    // DID document (the ERC725 / apex-Worker mirror).
    let resolver = CompositeDidResolver::with_default_methods(Arc::new(HttpDidDocumentFetcher::new()));
    let v = verify_session_pop(&req.token, &resolver, now_secs());
    let status = if v.valid { StatusCode::OK } else { StatusCode::UNAUTHORIZED };
    (
        status,
        Json(serde_json::json!({
            "valid": v.valid,
            "did": v.did,
            "reason": v.reason,
            "claims": v.claims,
        })),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nsid_has_correct_prefix() {
        assert!(NSID_PDS_SESSION_VERIFY.starts_with("ai.gftd.pds."));
    }
}
