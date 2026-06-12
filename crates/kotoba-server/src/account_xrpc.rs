//! Account key-custody XRPC — the opaque wrapped-ARK store (ADR-2606014000 L1).
//!
//! The server persists each device's `wrapArk` ciphertext (ARK wrapped under that
//! passkey's WebAuthn PRF output, AAD = account DID) but **cannot read it**: the
//! wrapping key is the PRF output, which never leaves the device. This is the
//! piece that lets a returning device recover its ARK — `S_prf` (from the
//! passkey) unwraps the blob fetched here — without the server ever holding a key
//! (ADR-2605231525 no-server-key invariant).
//!
//! One wrap per (account DID, passkey credential id) → multi-device falls out.

pub const NSID_ACCOUNT_PUT_WRAPPED_ARK: &str = "com.etzhayyim.account.put.wrapped.ark";
pub const NSID_ACCOUNT_GET_WRAPPED_ARK: &str = "com.etzhayyim.account.get.wrapped.ark";

use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
use serde::Deserialize;
use std::sync::Arc;

use crate::server::KotobaState;

const MAX_DID_LEN: usize = 512;
const MAX_CRED_ID_LEN: usize = 256;
// A 32-byte ARK wraps to iv(12)+ct(32)+tag(16)=60 bytes → ~80 base64url chars.
// Cap generously to also allow larger future payloads without unbounded growth.
const MAX_WRAP_B64_LEN: usize = 1024;

fn validate_did(did: &str) -> Result<(), (StatusCode, String)> {
    crate::graph_auth::validate_did(did, "did", MAX_DID_LEN)
}

fn validate_credential_id(id: &str) -> Result<(), (StatusCode, String)> {
    if id.is_empty() || id.len() > MAX_CRED_ID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("credentialId must be 1–{MAX_CRED_ID_LEN} bytes"),
        ));
    }
    if !id
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
    {
        return Err((
            StatusCode::BAD_REQUEST,
            "credentialId must contain only [A-Za-z0-9._-]".to_string(),
        ));
    }
    Ok(())
}

fn validate_wrapped_ark(value: &str) -> Result<(), (StatusCode, String)> {
    if value.is_empty() || value.len() > MAX_WRAP_B64_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("wrappedArk must be 1–{MAX_WRAP_B64_LEN} base64url chars"),
        ));
    }
    if value.contains('=') {
        return Err((
            StatusCode::BAD_REQUEST,
            "wrappedArk must use unpadded base64url".to_string(),
        ));
    }
    if !value
        .bytes()
        .all(|b| b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_'))
    {
        return Err((
            StatusCode::BAD_REQUEST,
            "wrappedArk must contain only base64url characters [A-Za-z0-9_-]".to_string(),
        ));
    }
    B64U.decode(value).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("wrappedArk base64url decode: {e}"),
        )
    })?;
    Ok(())
}

/// Bearer JWT `sub` must be the account DID itself (or the operator). The wrap is
/// opaque, but write/read is still gated to the owning member.
fn require_owner_auth(
    headers: &HeaderMap,
    did: &str,
    operator_did: &str,
) -> Result<(), (StatusCode, String)> {
    let token = headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or_else(|| {
            (
                StatusCode::UNAUTHORIZED,
                "Authorization: Bearer <token> required".to_string(),
            )
        })?;
    if crate::graph_auth::jwt_exp_elapsed(token) {
        return Err((
            StatusCode::UNAUTHORIZED,
            "Bearer token has expired".to_string(),
        ));
    }
    let sub = crate::graph_auth::jwt_sub(token).ok_or_else(|| {
        (
            StatusCode::UNAUTHORIZED,
            "Bearer token missing sub claim".to_string(),
        )
    })?;
    if sub == did || sub == operator_did {
        Ok(())
    } else {
        Err((
            StatusCode::UNAUTHORIZED,
            format!("Bearer sub does not match did {did:?}"),
        ))
    }
}

fn wrap_key(did: &str, credential_id: &str) -> String {
    format!("account/ark-wrap/{did}/{credential_id}")
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PutWrappedArkReq {
    pub did: String,
    /// WebAuthn credential id (base64url) of the passkey whose PRF wrapped the ARK.
    pub credential_id: String,
    /// Opaque `wrapArk` blob, base64url. The server treats this as bytes — it has
    /// no key to decrypt it.
    pub wrapped_ark: String,
}

pub async fn put_wrapped_ark(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<PutWrappedArkReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&req.did)?;
    validate_credential_id(&req.credential_id)?;
    require_owner_auth(&headers, &req.did, &state.operator_did)?;
    validate_wrapped_ark(&req.wrapped_ark)?;

    state
        .shelf
        .put(
            "KOTOBA_ACCOUNT",
            wrap_key(&req.did, &req.credential_id),
            bytes::Bytes::from(req.wrapped_ark.into_bytes()),
        )
        .await;
    Ok(Json(serde_json::json!({
        "status": "ok",
        "did": req.did,
        "credentialId": req.credential_id,
    })))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetWrappedArkQuery {
    pub did: String,
    pub credential_id: String,
}

pub async fn get_wrapped_ark(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<GetWrappedArkQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&q.did)?;
    validate_credential_id(&q.credential_id)?;
    require_owner_auth(&headers, &q.did, &state.operator_did)?;

    match state
        .shelf
        .get("KOTOBA_ACCOUNT", &wrap_key(&q.did, &q.credential_id))
        .await
    {
        Some(bytes) => {
            let wrapped = String::from_utf8(bytes.to_vec()).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("stored wrap malformed: {e}"),
                )
            })?;
            validate_wrapped_ark(&wrapped).map_err(|(_, msg)| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("stored wrap malformed: {msg}"),
                )
            })?;
            Ok(Json(serde_json::json!({
                "did": q.did,
                "credentialId": q.credential_id,
                "wrappedArk": wrapped,
            }))
            .into_response())
        }
        None => Ok((
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({
                "error": "no wrapped ARK for (did, credentialId)",
                "did": q.did,
            })),
        )
            .into_response()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nsids_have_correct_prefix() {
        for n in [NSID_ACCOUNT_PUT_WRAPPED_ARK, NSID_ACCOUNT_GET_WRAPPED_ARK] {
            assert!(n.starts_with("com.etzhayyim.account."), "{n}");
        }
    }

    #[test]
    fn wrap_key_is_namespaced_per_did_and_credential() {
        let k = wrap_key("did:key:zAlice", "cred-1");
        assert_eq!(k, "account/ark-wrap/did:key:zAlice/cred-1");
    }

    #[test]
    fn credential_id_validation() {
        assert!(validate_credential_id("AbC_0-9.x").is_ok());
        assert!(validate_credential_id("").is_err());
        assert!(validate_credential_id("has/slash").is_err());
        assert!(validate_credential_id(&"a".repeat(MAX_CRED_ID_LEN + 1)).is_err());
    }

    #[test]
    fn max_wrap_b64_len_holds_a_60_byte_blob() {
        // 60 raw bytes ≈ 80 base64url chars — comfortably under the cap.
        assert!(MAX_WRAP_B64_LEN > 80);
    }

    #[test]
    fn wrapped_ark_validation_accepts_base64url_no_pad() {
        assert!(validate_wrapped_ark("AAAA").is_ok());
        assert!(validate_wrapped_ark("YWJjZGVmZw").is_ok());
        assert!(validate_wrapped_ark("AA-_").is_ok());
    }

    #[test]
    fn wrapped_ark_validation_rejects_padding_and_non_urlsafe_chars() {
        for bad in ["AAAA=", "AA+/", "AA AA", "AA\nAA"] {
            assert!(
                validate_wrapped_ark(bad).is_err(),
                "{bad:?} should be rejected"
            );
        }
    }

    #[test]
    fn wrapped_ark_validation_rejects_empty_and_oversized() {
        assert!(validate_wrapped_ark("").is_err());
        assert!(validate_wrapped_ark(&"A".repeat(MAX_WRAP_B64_LEN + 1)).is_err());
    }

    #[test]
    fn credential_id_accepts_exactly_max_len() {
        assert!(validate_credential_id(&"a".repeat(MAX_CRED_ID_LEN)).is_ok());
    }

    #[test]
    fn credential_id_rejects_special_chars() {
        for bad in ["a b", "a/b", "a@b", "a#b", "a\u{0}b"] {
            assert!(
                validate_credential_id(bad).is_err(),
                "{bad:?} should be rejected"
            );
        }
    }

    #[test]
    fn wrap_key_distinct_per_credential() {
        let did = "did:web:etzhayyim.com:actor:alice";
        assert_ne!(wrap_key(did, "cred-1"), wrap_key(did, "cred-2"));
        assert_ne!(wrap_key("did:a", "c"), wrap_key("did:b", "c"));
    }
}
