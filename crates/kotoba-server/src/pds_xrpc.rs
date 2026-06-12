//! PDS XRPC surface on kotoba-server (ADR-2606015000 — PDS refactor onto kotoba).
//!
//! First landed endpoint: session PoP verification — the kotoba-server-native
//! replacement for the legacy TS PDS delegating session checks to the auth Worker.
//! Additional AT Protocol PDS endpoints (createSession/refreshSession/repo.*/
//! sync.*) are ported in subsequent increments of the refactor.

pub const NSID_PDS_SESSION_VERIFY: &str = "com.etzhayyim.pds.session.verify";

use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use serde::Deserialize;
use std::sync::Arc;

use crate::pds_session::verify_session_pop;
use crate::server::{HttpDidDocumentFetcher, KotobaState};
use kotoba_auth::resolver::CompositeDidResolver;

const MAX_SESSION_POP_TOKEN_LEN: usize = 8192;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SessionVerifyReq {
    /// Compact EdDSA JWS session PoP signed by the member's session key.
    pub token: String,
}

fn validate_session_pop_token(token: &str) -> Result<(), (StatusCode, String)> {
    if token.trim().is_empty() || token.len() > MAX_SESSION_POP_TOKEN_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("token required (1-{MAX_SESSION_POP_TOKEN_LEN} bytes)"),
        ));
    }
    if token.chars().any(char::is_control) || token.chars().any(char::is_whitespace) {
        return Err((
            StatusCode::BAD_REQUEST,
            "token must not contain whitespace or control characters".to_string(),
        ));
    }
    let mut parts = token.split('.');
    let (Some(header), Some(payload), Some(sig), None) =
        (parts.next(), parts.next(), parts.next(), parts.next())
    else {
        return Ok(());
    };
    for (label, segment) in [("header", header), ("payload", payload), ("signature", sig)] {
        if segment.is_empty() {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("token {label} segment must not be empty"),
            ));
        }
        if !segment
            .bytes()
            .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_'))
        {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("token {label} segment must be base64url without padding"),
            ));
        }
    }
    Ok(())
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
    if let Err((status, reason)) = validate_session_pop_token(&req.token) {
        return (
            status,
            Json(serde_json::json!({ "valid": false, "reason": reason })),
        );
    }
    // did:key resolves trustlessly (no network); did:web/plc fetch the authoritative
    // DID document (the ERC725 / apex-Worker mirror).
    let resolver =
        CompositeDidResolver::with_default_methods(Arc::new(HttpDidDocumentFetcher::new()));
    let v = verify_session_pop(&req.token, &resolver, now_secs());
    let status = if v.valid {
        StatusCode::OK
    } else {
        StatusCode::UNAUTHORIZED
    };
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
        assert!(NSID_PDS_SESSION_VERIFY.starts_with("com.etzhayyim.pds."));
    }

    #[test]
    fn session_pop_token_validation_rejects_empty_control_and_bad_segments() {
        assert!(validate_session_pop_token("aaa.bbb.ccc").is_ok());
        assert!(validate_session_pop_token("not.a.jws").is_ok());
        assert!(validate_session_pop_token("").is_err());
        assert!(validate_session_pop_token("   ").is_err());
        assert!(validate_session_pop_token("aaa.b\nbb.ccc").is_err());
        assert!(validate_session_pop_token("aaa.bbb.ccc=").is_err());
        assert!(validate_session_pop_token("aaa..ccc").is_err());
        assert!(validate_session_pop_token(&"a".repeat(MAX_SESSION_POP_TOKEN_LEN + 1)).is_err());
    }
}
