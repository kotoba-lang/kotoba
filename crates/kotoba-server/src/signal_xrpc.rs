//! Signal Protocol XRPC endpoints.
//! NSIDs: com.etzhayyim.signal.{register.prekeys, get.prekey.bundle, send.message, send.group.message}
//!
//! These endpoints make kotoba-server the SSoT for Signal Protocol E2E,
//! superseding `@etzhayyim/signal` (`10-protocol/signal/`).

pub const NSID_SIGNAL_REGISTER_PREKEYS: &str = "com.etzhayyim.signal.register.prekeys";
pub const NSID_SIGNAL_GET_PREKEY_BUNDLE: &str = "com.etzhayyim.signal.get.prekey.bundle";
pub const NSID_SIGNAL_SEND_MESSAGE: &str = "com.etzhayyim.signal.send.message";
pub const NSID_SIGNAL_SEND_GROUP_MESSAGE: &str = "com.etzhayyim.signal.send.group.message";
pub const NSID_SIGNAL_DISTRIBUTE_SENDER_KEY: &str = "com.etzhayyim.signal.distribute.sender.key";
pub const NSID_SIGNAL_PUBLISH_IDENTITY: &str = "com.etzhayyim.signal.publish.identity";
pub const NSID_SIGNAL_RESOLVE_IDENTITY: &str = "com.etzhayyim.signal.resolve.identity";

use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use base64::{engine::general_purpose::URL_SAFE_NO_PAD as B64U, Engine as _};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

use crate::server::{HttpDidDocumentFetcher, KotobaState};
use kotoba_auth::resolver::{CompositeDidResolver, DidDocumentResolver, DidKeyResolver};
use kotoba_signal::message::SignalMessage;
use kotoba_signal::SignalBinding;

// Soft caps — prevent shelf key exhaustion and oversized payloads.
const MAX_DID_LEN: usize = 512;
const MAX_DEVICE_ID_LEN: usize = 128;
const MAX_GROUP_ID_LEN: usize = 128;
const MAX_PAYLOAD_BYTES: usize = 256 * 1024; // 256 KiB per encrypted message
const MAX_BUNDLE_BYTES: usize = 64 * 1024; // 64 KiB per prekey bundle / identity key

/// Thin wrapper — delegates to the shared validator in `graph_auth`.
fn validate_signal_did(did: &str, field: &str) -> Result<(), (StatusCode, String)> {
    crate::graph_auth::validate_did(did, field, MAX_DID_LEN)
}

/// Validates a value used as a path component in storage keys or topic names.
/// Allows only `[A-Za-z0-9._-]` to prevent path-traversal / key-namespace pollution.
fn validate_path_component(
    value: &str,
    field: &str,
    max_len: usize,
) -> Result<(), (StatusCode, String)> {
    if value.is_empty() || value.len() > max_len {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must be 1–{max_len} bytes"),
        ));
    }
    if !value
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-'))
    {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must contain only [A-Za-z0-9._-]"),
        ));
    }
    Ok(())
}

/// Verify caller owns `did` via Bearer JWT `sub` claim.
fn require_signal_auth(
    headers: &HeaderMap,
    did: &str,
    operator_did: &str,
) -> Result<(), (StatusCode, String)> {
    let token = headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or_else(|| {
            tracing::warn!("signal auth: missing Bearer token");
            (
                StatusCode::UNAUTHORIZED,
                "Authorization: Bearer <token> required".to_string(),
            )
        })?;
    if crate::graph_auth::jwt_exp_elapsed(token) {
        tracing::warn!("signal auth: expired JWT");
        return Err((
            StatusCode::UNAUTHORIZED,
            "Bearer token has expired".to_string(),
        ));
    }
    let sub = crate::graph_auth::jwt_sub(token).ok_or_else(|| {
        tracing::warn!("signal auth: JWT missing sub claim");
        (
            StatusCode::UNAUTHORIZED,
            "Bearer token missing sub claim".to_string(),
        )
    })?;
    if sub == did || sub == operator_did {
        Ok(())
    } else {
        tracing::warn!(sub = %sub, did = %did, "signal auth: sub mismatch");
        Err((
            StatusCode::UNAUTHORIZED,
            format!("Bearer sub does not match did {did:?}"),
        ))
    }
}

// ── registerPrekeys ───────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterPrekeysReq {
    pub did: String,
    pub device_id: String,
    /// Serialised `IdentityKey` (JSON).
    pub identity_key: serde_json::Value,
    /// Serialised `PreKeyBundle` (JSON) — signed_prekey + one_time_prekeys.
    pub prekey_bundle: serde_json::Value,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterPrekeysResp {
    pub status: &'static str,
    pub did: String,
}

pub async fn register_prekeys(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<RegisterPrekeysReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_signal_did(&req.did, "did")?;
    validate_path_component(&req.device_id, "device_id", MAX_DEVICE_ID_LEN)?;
    require_signal_auth(&headers, &req.did, &state.operator_did)?;

    let bundle_bytes = serde_json::to_vec(&req.prekey_bundle).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("prekey_bundle serialize: {e}"),
        )
    })?;
    if bundle_bytes.len() > MAX_BUNDLE_BYTES {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!("prekey_bundle exceeds {MAX_BUNDLE_BYTES} bytes"),
        ));
    }
    let ik_bytes = serde_json::to_vec(&req.identity_key).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("identity_key serialize: {e}"),
        )
    })?;
    if ik_bytes.len() > MAX_BUNDLE_BYTES {
        return Err((
            StatusCode::PAYLOAD_TOO_LARGE,
            format!("identity_key exceeds {MAX_BUNDLE_BYTES} bytes"),
        ));
    }

    let key = format!("signal/bundle/{}/{}", req.did, req.device_id);
    state
        .shelf
        .put("KOTOBA_SIGNAL", key, bytes::Bytes::from(bundle_bytes))
        .await;
    let ik_key = format!("signal/identity/{}/{}", req.did, req.device_id);
    state
        .shelf
        .put("KOTOBA_SIGNAL", ik_key, bytes::Bytes::from(ik_bytes))
        .await;
    Ok(Json(RegisterPrekeysResp {
        status: "ok",
        did: req.did,
    }))
}

// ── getPrekeyBundle ───────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetPreKeyBundleQuery {
    pub did: String,
    pub device_id: Option<String>,
}

pub async fn get_prekey_bundle(
    State(state): State<Arc<KotobaState>>,
    Query(q): Query<GetPreKeyBundleQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_signal_did(&q.did, "did")?;
    let device_id = q.device_id.as_deref().unwrap_or("default");
    validate_path_component(device_id, "device_id", MAX_DEVICE_ID_LEN)?;
    let bundle_key = format!("signal/bundle/{}/{}", q.did, device_id);
    let ik_key = format!("signal/identity/{}/{}", q.did, device_id);

    let bundle_bytes = state.shelf.get("KOTOBA_SIGNAL", &bundle_key).await;
    let ik_bytes = state.shelf.get("KOTOBA_SIGNAL", &ik_key).await;

    Ok(match (bundle_bytes, ik_bytes) {
        (Some(b), Some(ik)) => {
            let bundle: serde_json::Value = serde_json::from_slice(&b).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("stored prekey bundle is malformed: {e}"),
                )
            })?;
            let identity_key: serde_json::Value = serde_json::from_slice(&ik).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("stored identity key is malformed: {e}"),
                )
            })?;
            Json(serde_json::json!({
                "did": q.did,
                "deviceId": device_id,
                "identityKey": identity_key,
                "bundle": bundle,
            }))
            .into_response()
        }
        _ => (
            StatusCode::NOT_FOUND,
            Json(serde_json::json!({
                "error": "prekey bundle not found",
                "did": q.did,
            })),
        )
            .into_response(),
    })
}

// ── sendMessage ───────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SendMessageReq {
    pub signal_message: serde_json::Value,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct SendMessageResp {
    pub status: &'static str,
    pub message_id: String,
}

pub async fn send_message(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<SendMessageReq>,
) -> impl IntoResponse {
    let raw_len = serde_json::to_vec(&req.signal_message)
        .map(|v| v.len())
        .unwrap_or(usize::MAX);
    if raw_len > MAX_PAYLOAD_BYTES {
        return (StatusCode::PAYLOAD_TOO_LARGE,
            Json(serde_json::json!({ "error": format!("signal_message exceeds {MAX_PAYLOAD_BYTES} bytes") })),
        ).into_response();
    }

    let msg: SignalMessage = match serde_json::from_value(req.signal_message.clone()) {
        Ok(m) => m,
        Err(e) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({ "error": e.to_string() })),
            )
                .into_response()
        }
    };

    // Require the caller to prove ownership of signal_message.sender_did.
    if let Err((code, err_msg)) =
        require_signal_auth(&headers, &msg.sender_did, &state.operator_did)
    {
        return (code, Json(serde_json::json!({ "error": err_msg }))).into_response();
    }

    let topic_name = format!("signal/inbox/{}/{}", msg.recipient_did, msg.device_id);
    let topic = kotoba_vault::topic::Topic(format!("kotoba/{topic_name}"));
    let payload_vec = match serde_json::to_vec(&req.signal_message) {
        Ok(v) => v,
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": format!("signal_message serialize: {e}") })),
            )
                .into_response()
        }
    };
    let entry = state
        .journal
        .publish(topic, bytes::Bytes::from(payload_vec))
        .await;

    Json(SendMessageResp {
        status: "ok",
        message_id: entry.cid.to_multibase(),
    })
    .into_response()
}

// ── sendGroupMessage ──────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SendGroupMessageReq {
    pub group_id: String,
    pub sender_did: String,
    pub sender_key_message: serde_json::Value,
}

pub async fn send_group_message(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<SendGroupMessageReq>,
) -> impl IntoResponse {
    if let Err((code, msg)) = validate_path_component(&req.group_id, "group_id", MAX_GROUP_ID_LEN) {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    if let Err((code, msg)) = validate_signal_did(&req.sender_did, "sender_did") {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    if let Err((code, err_msg)) =
        require_signal_auth(&headers, &req.sender_did, &state.operator_did)
    {
        return (code, Json(serde_json::json!({ "error": err_msg }))).into_response();
    }
    let raw_len = serde_json::to_vec(&req.sender_key_message)
        .map(|v| v.len())
        .unwrap_or(usize::MAX);
    if raw_len > MAX_PAYLOAD_BYTES {
        return (StatusCode::PAYLOAD_TOO_LARGE,
            Json(serde_json::json!({ "error": format!("sender_key_message exceeds {MAX_PAYLOAD_BYTES} bytes") })),
        ).into_response();
    }

    let topic = kotoba_vault::topic::Topic(format!("kotoba/signal/group/{}", req.group_id));
    let payload_vec =
        match serde_json::to_vec(&req.sender_key_message) {
            Ok(v) => v,
            Err(e) => return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": format!("sender_key_message serialize: {e}") })),
            )
                .into_response(),
        };
    let entry = state
        .journal
        .publish(topic, bytes::Bytes::from(payload_vec))
        .await;

    Json(serde_json::json!({
        "status": "ok",
        "messageId": entry.cid.to_multibase(),
        "groupId": req.group_id,
    }))
    .into_response()
}

// ── distributeSenderKey ───────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DistributeSenderKeyReq {
    /// Recipient DID — receives the distribution via their 1:1 inbox.
    pub recipient_did: String,
    pub recipient_device: String,
    /// SenderKeyDistribution serialised as a SignalMessage ciphertext.
    pub signal_message: serde_json::Value,
}

pub async fn distribute_sender_key(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<DistributeSenderKeyReq>,
) -> impl IntoResponse {
    if let Err((code, msg)) = validate_signal_did(&req.recipient_did, "recipient_did") {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    if let Err((code, msg)) =
        validate_path_component(&req.recipient_device, "recipient_device", MAX_DEVICE_ID_LEN)
    {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    let raw_len = serde_json::to_vec(&req.signal_message)
        .map(|v| v.len())
        .unwrap_or(usize::MAX);
    if raw_len > MAX_PAYLOAD_BYTES {
        return (StatusCode::PAYLOAD_TOO_LARGE,
            Json(serde_json::json!({ "error": format!("signal_message exceeds {MAX_PAYLOAD_BYTES} bytes") })),
        ).into_response();
    }
    // Require any authenticated caller (the sender distributing their key).
    // We verify: Bearer present + non-expired + has sub claim.
    if let Err((code, err_msg)) =
        crate::graph_auth::require_any_bearer_auth(&headers, "distribute_sender_key")
    {
        return (code, Json(serde_json::json!({ "error": err_msg }))).into_response();
    }

    let topic = kotoba_vault::topic::Topic(format!(
        "kotoba/signal/inbox/{}/{}",
        req.recipient_did, req.recipient_device
    ));
    let payload_vec = match serde_json::to_vec(&req.signal_message) {
        Ok(v) => v,
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({ "error": format!("signal_message serialize: {e}") })),
            )
                .into_response()
        }
    };
    let entry = state
        .journal
        .publish(topic, bytes::Bytes::from(payload_vec))
        .await;

    Json(serde_json::json!({
        "status": "ok",
        "messageId": entry.cid.to_multibase(),
    }))
    .into_response()
}

// ── publishSignalIdentity / resolveSignalIdentity (ADR-2606014000 D4) ─────────
//
// The DID↔Signal binding: an actor publishes, signed by their DID key, which
// Signal identity is canonical for their DID. A peer MUST resolve+verify this
// binding before X3DH, else a malicious server could substitute a Signal
// identity (the gap the prekey endpoints above do NOT close on their own).
//
// Verification trust:
//   • did:key:z6Mk…  — the verifying key is THE DID itself → fully trustless,
//     no external lookup, server cannot forge.
//   • did:web / did:plc — needs the DID document's key from an authoritative
//     resolver (apex Worker / on-chain ERC725 mirror). Not wired yet, so resolve
//     returns `verified=false` with a reason rather than vouching (honest TOFU).

const MAX_B64_FIELD: usize = 512;

fn shelf_binding_key(did: &str) -> String {
    format!("signal/identity-binding/{did}")
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PublishSignalIdentityReq {
    pub did: String,
    /// Ed25519 signing public component, base64url-no-pad (32 bytes).
    pub signal_identity_key: String,
    /// X25519 DH public component, base64url-no-pad (32 bytes).
    pub signal_dh_key: String,
    pub signal_registration_id: u32,
    pub created_at: String,
    /// Ed25519 signature over the binding payload by the DID key, base64url-no-pad.
    pub signature: String,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct StoredBinding {
    did: String,
    signal_identity_key: String,
    signal_dh_key: String,
    signal_registration_id: u32,
    created_at: String,
    signature: String,
}

fn decode_b64_field(s: &str, field: &str) -> Result<Vec<u8>, (StatusCode, String)> {
    if s.len() > MAX_B64_FIELD {
        return Err((StatusCode::BAD_REQUEST, format!("{field} too long")));
    }
    B64U.decode(s)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("{field} base64url: {e}")))
}

/// Reconstruct a `SignalBinding` + raw signature from a stored/published record.
fn binding_from_fields(
    did: &str,
    signal_identity_key: &str,
    signal_dh_key: &str,
    signal_registration_id: u32,
    created_at: &str,
    signature: &str,
) -> Result<(SignalBinding, Vec<u8>), (StatusCode, String)> {
    let sig = decode_b64_field(signature, "signature")?;
    let binding = SignalBinding {
        did: did.to_string(),
        signal_identity_key: decode_b64_field(signal_identity_key, "signalIdentityKey")?,
        signal_dh_key: decode_b64_field(signal_dh_key, "signalDhKey")?,
        signal_registration_id,
        created_at: created_at.to_string(),
    };
    Ok((binding, sig))
}

/// Resolver for did:key only — purely local (no network). Used at publish time,
/// where we eagerly verify did:key bindings but defer did:web/plc to resolve time.
fn local_didkey_resolver() -> CompositeDidResolver {
    CompositeDidResolver::new().with_method(DidKeyResolver)
}

/// Full resolver: did:key (trustless, local) + did:web + did:plc (HTTP-fetched
/// DID documents). The did:web/plc key is the authoritative DID-document
/// `verificationMethod` — the ERC725 / apex-Worker mirror (ADR-2606013800),
/// which is what closes the residual MITM trust on key distribution.
fn full_did_resolver() -> CompositeDidResolver {
    CompositeDidResolver::with_default_methods(Arc::new(HttpDidDocumentFetcher::new()))
}

/// Verify a binding by resolving the issuer DID to its Ed25519 key and checking
/// the signature. Returns `(verified, reason)`.
///
/// Trust per method falls out of the resolver:
///   • did:key — the resolver derives the key from the DID itself (trustless).
///   • did:web / did:plc — the resolver fetches the authoritative DID document;
///     verification is only as strong as that document's key anchor.
/// A DID that does not resolve, or whose document has no Ed25519 verification
/// method, is reported unverified — **never falsely vouched**.
fn verify_binding_against_did(
    binding: &SignalBinding,
    sig: &[u8],
    resolver: &dyn DidDocumentResolver,
) -> (bool, String) {
    let method = if binding.did.starts_with("did:key:") {
        "did:key (trustless)"
    } else {
        "DID document (resolved)"
    };
    match resolver.resolve(&binding.did) {
        Ok(doc) => match doc.ed25519_public_key() {
            Some(pubkey) => {
                if binding.verify(sig, &pubkey) {
                    (true, method.to_string())
                } else {
                    (false, format!("signature does not verify against {method}"))
                }
            }
            None => (
                false,
                "DID document has no Ed25519 verification method".to_string(),
            ),
        },
        Err(e) => (false, format!("DID resolution failed: {e}")),
    }
}

pub async fn publish_signal_identity(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<PublishSignalIdentityReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_signal_did(&req.did, "did")?;
    require_signal_auth(&headers, &req.did, &state.operator_did)?;

    let (binding, sig) = binding_from_fields(
        &req.did,
        &req.signal_identity_key,
        &req.signal_dh_key,
        req.signal_registration_id,
        &req.created_at,
        &req.signature,
    )?;

    // did:key issuers verify locally (no network) — reject a bad signature now so
    // the store never holds an invalid binding. did:web/plc verification needs the
    // authoritative DID document and is deferred to resolve time.
    let verified = if binding.did.starts_with("did:key:") {
        let (ok, reason) = verify_binding_against_did(&binding, &sig, &local_didkey_resolver());
        if !ok {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("binding signature invalid: {reason}"),
            ));
        }
        true
    } else {
        false
    };

    let record = StoredBinding {
        did: req.did.clone(),
        signal_identity_key: req.signal_identity_key,
        signal_dh_key: req.signal_dh_key,
        signal_registration_id: req.signal_registration_id,
        created_at: req.created_at,
        signature: req.signature,
    };
    let bytes = serde_json::to_vec(&record)
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("serialize: {e}")))?;
    state
        .shelf
        .put(
            "KOTOBA_SIGNAL",
            shelf_binding_key(&req.did),
            bytes::Bytes::from(bytes),
        )
        .await;

    Ok(Json(serde_json::json!({
        "status": "ok",
        "did": req.did,
        "verifiedOnPublish": verified,
    })))
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ResolveSignalIdentityQuery {
    pub did: String,
}

pub async fn resolve_signal_identity(
    State(state): State<Arc<KotobaState>>,
    Query(q): Query<ResolveSignalIdentityQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_signal_did(&q.did, "did")?;
    let Some(raw) = state
        .shelf
        .get("KOTOBA_SIGNAL", &shelf_binding_key(&q.did))
        .await
    else {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(
                serde_json::json!({ "error": "no signal identity binding for did", "did": q.did }),
            ),
        )
            .into_response());
    };
    let record: StoredBinding = serde_json::from_slice(&raw).map_err(|e| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("stored binding malformed: {e}"),
        )
    })?;
    let (binding, sig) = binding_from_fields(
        &record.did,
        &record.signal_identity_key,
        &record.signal_dh_key,
        record.signal_registration_id,
        &record.created_at,
        &record.signature,
    )?;
    let (verified, reason) = verify_binding_against_did(&binding, &sig, &full_did_resolver());

    Ok(Json(serde_json::json!({
        "did": record.did,
        "signalIdentityKey": record.signal_identity_key,
        "signalDhKey": record.signal_dh_key,
        "signalRegistrationId": record.signal_registration_id,
        "createdAt": record.created_at,
        "signature": record.signature,
        // The peer MUST treat `verified=false` as untrusted and refuse X3DH.
        "verified": verified,
        "verificationMethod": reason,
    }))
    .into_response())
}

// ── NSID invariant tests ──────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    const SIGNAL_NSIDS: &[&str] = &[
        NSID_SIGNAL_REGISTER_PREKEYS,
        NSID_SIGNAL_GET_PREKEY_BUNDLE,
        NSID_SIGNAL_SEND_MESSAGE,
        NSID_SIGNAL_SEND_GROUP_MESSAGE,
        NSID_SIGNAL_DISTRIBUTE_SENDER_KEY,
    ];

    #[test]
    fn all_signal_nsids_have_correct_prefix() {
        for nsid in SIGNAL_NSIDS {
            assert!(
                nsid.starts_with("com.etzhayyim.signal."),
                "Signal NSID must start with com.etzhayyim.signal.: {nsid}"
            );
        }
    }

    #[test]
    fn all_signal_nsids_alphanumeric_dotted() {
        for nsid in SIGNAL_NSIDS {
            assert!(
                nsid.chars().all(|c| c.is_ascii_alphanumeric() || c == '.'),
                "NSID must be alphanumeric+dots: {nsid}"
            );
        }
    }

    #[test]
    fn all_signal_nsids_unique() {
        let mut seen = std::collections::HashSet::new();
        for nsid in SIGNAL_NSIDS {
            assert!(seen.insert(*nsid), "duplicate NSID: {nsid}");
        }
    }

    // ── validate_path_component ───────────────────────────────────────────────

    #[test]
    fn path_component_accepts_valid_ids() {
        assert!(validate_path_component("device-1", "device_id", 128).is_ok());
        assert!(validate_path_component("abc.def_GHI-123", "device_id", 128).is_ok());
        assert!(validate_path_component("default", "device_id", 128).is_ok());
        assert!(validate_path_component("group-ABC_01.v2", "group_id", 128).is_ok());
    }

    #[test]
    fn path_component_rejects_empty() {
        let err = validate_path_component("", "device_id", 128).unwrap_err();
        assert_eq!(err.0, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.1.contains("1–128"));
    }

    #[test]
    fn path_component_rejects_too_long() {
        let long = "a".repeat(129);
        let err = validate_path_component(&long, "device_id", 128).unwrap_err();
        assert_eq!(err.0, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.1.contains("1–128"));
    }

    #[test]
    fn path_component_rejects_slash() {
        let err = validate_path_component("foo/bar", "device_id", 128).unwrap_err();
        assert_eq!(err.0, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.1.contains("[A-Za-z0-9._-]"));
    }

    #[test]
    fn path_component_rejects_dotdot_traversal() {
        // `..` contains only dots and would pass a naive charset check; verify combined path
        // injection like `../../other` is caught at the slash.
        let err = validate_path_component("../../etc/passwd", "device_id", 128).unwrap_err();
        assert_eq!(err.0, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.1.contains("[A-Za-z0-9._-]"));
    }

    #[test]
    fn path_component_rejects_space_and_special_chars() {
        for bad in &["hello world", "id@host", "id#1", "id\x00null"] {
            let err = validate_path_component(bad, "device_id", 128).unwrap_err();
            assert_eq!(err.0, axum::http::StatusCode::BAD_REQUEST);
        }
    }

    #[test]
    fn bundle_bytes_cap_constant_is_smaller_than_payload_cap() {
        assert!(
            MAX_BUNDLE_BYTES < MAX_PAYLOAD_BYTES,
            "bundle cap should be tighter than general payload cap"
        );
    }

    // ── additional constant / boundary tests ─────────────────────────────────

    #[test]
    fn nsid_register_prekeys_exact_value() {
        assert_eq!(
            NSID_SIGNAL_REGISTER_PREKEYS,
            "com.etzhayyim.signal.register.prekeys"
        );
    }

    #[test]
    fn nsid_get_prekey_bundle_exact_value() {
        assert_eq!(
            NSID_SIGNAL_GET_PREKEY_BUNDLE,
            "com.etzhayyim.signal.get.prekey.bundle"
        );
    }

    #[test]
    fn nsid_send_message_exact_value() {
        assert_eq!(
            NSID_SIGNAL_SEND_MESSAGE,
            "com.etzhayyim.signal.send.message"
        );
    }

    #[test]
    fn nsid_send_group_message_exact_value() {
        assert_eq!(
            NSID_SIGNAL_SEND_GROUP_MESSAGE,
            "com.etzhayyim.signal.send.group.message"
        );
    }

    #[test]
    fn nsid_distribute_sender_key_exact_value() {
        assert_eq!(
            NSID_SIGNAL_DISTRIBUTE_SENDER_KEY,
            "com.etzhayyim.signal.distribute.sender.key"
        );
    }

    #[test]
    fn max_did_len_is_512() {
        assert_eq!(MAX_DID_LEN, 512);
    }

    #[test]
    fn max_device_id_len_is_128() {
        assert_eq!(MAX_DEVICE_ID_LEN, 128);
    }

    #[test]
    fn max_group_id_len_is_128() {
        assert_eq!(MAX_GROUP_ID_LEN, 128);
    }

    #[test]
    fn max_payload_bytes_is_256_kib() {
        assert_eq!(MAX_PAYLOAD_BYTES, 256 * 1024);
    }

    #[test]
    fn max_bundle_bytes_is_64_kib() {
        assert_eq!(MAX_BUNDLE_BYTES, 64 * 1024);
    }

    #[test]
    fn path_component_accepts_exactly_max_len() {
        let exactly_max = "a".repeat(MAX_DEVICE_ID_LEN);
        assert!(validate_path_component(&exactly_max, "device_id", MAX_DEVICE_ID_LEN).is_ok());
    }

    #[test]
    fn path_component_accepts_single_char() {
        assert!(validate_path_component("x", "device_id", MAX_DEVICE_ID_LEN).is_ok());
    }

    #[test]
    fn path_component_rejects_tilde() {
        let err = validate_path_component("foo~bar", "device_id", MAX_DEVICE_ID_LEN).unwrap_err();
        assert_eq!(err.0, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.1.contains("[A-Za-z0-9._-]"));
    }

    // ── DID↔Signal binding verification (ADR-2606014000 D4) ───────────────────

    use ed25519_dalek::SigningKey;
    use kotoba_signal::identity::IdentityKeyPair;

    /// Build a published-record's fields for a did:key issuer with a real signature.
    fn signed_didkey_binding() -> (String, PublishSignalIdentityReq) {
        // The DID key IS the issuer for did:key — the binding is signed by it.
        let did_sk = SigningKey::from_bytes(&[5u8; 32]);
        let did =
            kotoba_auth::did_key::ed25519_pubkey_to_did_key(&did_sk.verifying_key().to_bytes());
        let signal = IdentityKeyPair::generate().public_key();
        let binding = SignalBinding::from_identity(&did, &signal, 99, "2026-06-01T00:00:00Z");
        let sig = binding.sign(&did_sk);
        let req = PublishSignalIdentityReq {
            did: did.clone(),
            signal_identity_key: B64U.encode(&binding.signal_identity_key),
            signal_dh_key: B64U.encode(&binding.signal_dh_key),
            signal_registration_id: 99,
            created_at: "2026-06-01T00:00:00Z".to_string(),
            signature: B64U.encode(&sig),
        };
        (did, req)
    }

    #[test]
    fn didkey_binding_verifies_trustlessly() {
        let (_did, req) = signed_didkey_binding();
        let (binding, sig) = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            &req.created_at,
            &req.signature,
        )
        .unwrap();
        // Local did:key resolver — no network.
        let (verified, reason) =
            verify_binding_against_did(&binding, &sig, &local_didkey_resolver());
        assert!(
            verified,
            "did:key binding must verify trustlessly: {reason}"
        );
    }

    #[test]
    fn didkey_binding_rejects_tampered_signal_key() {
        let (_did, req) = signed_didkey_binding();
        // Swap the bound Signal key — signature no longer matches the DID key.
        let other = IdentityKeyPair::generate().public_key();
        let (binding, sig) = binding_from_fields(
            &req.did,
            &B64U.encode(&other.signing),
            &B64U.encode(&other.dh),
            req.signal_registration_id,
            &req.created_at,
            &req.signature,
        )
        .unwrap();
        let (verified, _) = verify_binding_against_did(&binding, &sig, &local_didkey_resolver());
        assert!(!verified, "tampered Signal key must fail verification");
    }

    /// Build an InMemory resolver mapping `did` → a DID document whose Ed25519
    /// verification key is `did_pubkey` (simulates the ERC725/apex-Worker mirror).
    fn resolver_with_doc(
        did: &str,
        did_pubkey: &[u8; 32],
    ) -> kotoba_auth::resolver::InMemoryDidResolver {
        use kotoba_auth::did_document::{DidDocument, VerificationMethod, ED25519_KEY_TYPE_2020};
        let mut doc = DidDocument::empty(did);
        doc.verification_method.push(VerificationMethod {
            id: format!("{did}#key-1"),
            key_type: ED25519_KEY_TYPE_2020.to_string(),
            controller: did.to_string(),
            public_key_multibase: multibase::encode(multibase::Base::Base58Btc, did_pubkey),
        });
        let resolver = kotoba_auth::resolver::InMemoryDidResolver::new();
        resolver.insert(did, doc);
        resolver
    }

    #[test]
    fn didweb_binding_verifies_against_resolved_doc() {
        // The non-trustless path: a did:web binding signed by the DID key, where
        // the DID document (resolved via the mirror) carries that key, verifies.
        let did = "did:web:etzhayyim.com:actor:alice";
        let did_sk = SigningKey::from_bytes(&[11u8; 32]);
        let signal = IdentityKeyPair::generate().public_key();
        let binding = SignalBinding::from_identity(did, &signal, 1, "2026-06-01T00:00:00Z");
        let sig = binding.sign(&did_sk);

        let resolver = resolver_with_doc(did, &did_sk.verifying_key().to_bytes());
        let (verified, reason) = verify_binding_against_did(&binding, &sig, &resolver);
        assert!(
            verified,
            "did:web binding must verify against its resolved doc: {reason}"
        );

        // A document carrying the WRONG key must reject (substitution attempt).
        let wrong = resolver_with_doc(
            did,
            &SigningKey::from_bytes(&[12u8; 32])
                .verifying_key()
                .to_bytes(),
        );
        let (bad, _) = verify_binding_against_did(&binding, &sig, &wrong);
        assert!(!bad, "wrong DID-document key must fail");
    }

    #[test]
    fn didweb_binding_not_vouched_when_unresolvable() {
        // No resolver method for did:web → resolution fails → never vouched.
        let signal = IdentityKeyPair::generate().public_key();
        let binding =
            SignalBinding::from_identity("did:web:etzhayyim.com:actor:bob", &signal, 1, "t");
        let empty = CompositeDidResolver::new();
        let (verified, reason) = verify_binding_against_did(&binding, &[0u8; 64], &empty);
        assert!(!verified);
        assert!(reason.contains("resolution failed"), "reason={reason}");
    }

    #[test]
    fn new_identity_nsids_have_correct_prefix() {
        for nsid in [NSID_SIGNAL_PUBLISH_IDENTITY, NSID_SIGNAL_RESOLVE_IDENTITY] {
            assert!(nsid.starts_with("com.etzhayyim.signal."), "{nsid}");
        }
    }
}
