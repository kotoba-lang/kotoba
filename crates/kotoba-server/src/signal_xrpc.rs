//! Signal Protocol XRPC endpoints.
//! NSIDs: com.etzhayyim.signal.{register.prekeys, get.prekey.bundle, send.message, send.group.message}
//!
//! These endpoints make kotoba-server the SSoT for Signal Protocol E2E,
//! superseding `@gftd/signal` (`10-protocol/signal/`).

pub const NSID_SIGNAL_REGISTER_PREKEYS: &str = "com.etzhayyim.signal.register.prekeys";
pub const NSID_SIGNAL_GET_PREKEY_BUNDLE: &str = "com.etzhayyim.signal.get.prekey.bundle";
pub const NSID_SIGNAL_SEND_MESSAGE: &str = "com.etzhayyim.signal.send.message";
pub const NSID_SIGNAL_SEND_GROUP_MESSAGE: &str = "com.etzhayyim.signal.send.group.message";
pub const NSID_SIGNAL_DISTRIBUTE_SENDER_KEY: &str = "com.etzhayyim.signal.distribute.sender.key";
pub const NSID_SIGNAL_PUBLISH_IDENTITY: &str = "com.etzhayyim.signal.publish.identity";
pub const NSID_SIGNAL_RESOLVE_IDENTITY: &str = "com.etzhayyim.signal.resolve.identity";
pub const SIGNAL_MESSAGE_BODY_LIMIT: usize = 512 * 1024;
pub const SIGNAL_REGISTER_PREKEYS_BODY_LIMIT: usize = 256 * 1024;
pub const SIGNAL_PUBLISH_IDENTITY_BODY_LIMIT: usize = 16 * 1024;

pub const ALL_SIGNAL_NSIDS: &[&str] = &[
    NSID_SIGNAL_REGISTER_PREKEYS,
    NSID_SIGNAL_GET_PREKEY_BUNDLE,
    NSID_SIGNAL_SEND_MESSAGE,
    NSID_SIGNAL_SEND_GROUP_MESSAGE,
    NSID_SIGNAL_DISTRIBUTE_SENDER_KEY,
    NSID_SIGNAL_PUBLISH_IDENTITY,
    NSID_SIGNAL_RESOLVE_IDENTITY,
];

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
use kotoba_signal::group::SenderKeyMessage;
use kotoba_signal::identity::IdentityKey;
use kotoba_signal::message::{MessageType, SignalMessage};
use kotoba_signal::prekey::PreKeyBundle;
use kotoba_signal::SignalBinding;

// Soft caps — prevent shelf key exhaustion and oversized payloads.
const MAX_DID_LEN: usize = 512;
const MAX_DEVICE_ID_LEN: usize = 128;
const MAX_GROUP_ID_LEN: usize = 128;
const MAX_PAYLOAD_BYTES: usize = 256 * 1024; // 256 KiB per encrypted message
const MAX_BUNDLE_BYTES: usize = 64 * 1024; // 64 KiB per prekey bundle / identity key
const MAX_TIMESTAMP_LEN: usize = 64;
const MAX_EPHEMERAL_KEY_LEN: usize = 512;
const SIGNAL_PUBLIC_KEY_BYTES: usize = 32;
const SIGNAL_SIGNATURE_BYTES: usize = 64;
const SIGNAL_REGISTRATION_ID_MAX: u32 = 0x3fff;
const SIGNAL_AEAD_MIN_BYTES: usize = kotoba_crypto::aead::NONCE_LEN + kotoba_crypto::aead::TAG_LEN;

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

fn validate_visible_ascii_field(
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
    if !value.bytes().all(|b| (0x21..=0x7e).contains(&b)) {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must contain only visible ASCII characters"),
        ));
    }
    Ok(())
}

fn validate_signal_message_fields(msg: &SignalMessage) -> Result<(), (StatusCode, String)> {
    validate_signal_did(&msg.sender_did, "sender_did")?;
    validate_signal_did(&msg.recipient_did, "recipient_did")?;
    validate_path_component(&msg.device_id, "device_id", MAX_DEVICE_ID_LEN)?;
    if matches!(msg.message_type, MessageType::GroupMessage) && msg.group_id.is_none() {
        return Err((
            StatusCode::BAD_REQUEST,
            "groupMessage requires groupId".to_string(),
        ));
    }
    if !matches!(msg.message_type, MessageType::GroupMessage) && msg.group_id.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "groupId is only allowed for groupMessage".to_string(),
        ));
    }
    if let Some(group_id) = &msg.group_id {
        validate_path_component(group_id, "group_id", MAX_GROUP_ID_LEN)?;
    }
    validate_visible_ascii_field(&msg.timestamp, "timestamp", MAX_TIMESTAMP_LEN)?;
    validate_visible_ascii_field(
        &msg.ciphertext_envelope,
        "ciphertext_envelope",
        MAX_PAYLOAD_BYTES,
    )?;
    if let Some(ephemeral_key) = &msg.ephemeral_key {
        validate_visible_ascii_field(ephemeral_key, "ephemeral_key", MAX_EPHEMERAL_KEY_LEN)?;
    }
    Ok(())
}

fn validate_sender_key_message_fields(msg: &SenderKeyMessage) -> Result<(), (StatusCode, String)> {
    validate_path_component(&msg.group_id, "group_id", MAX_GROUP_ID_LEN)?;
    validate_signal_did(&msg.sender_did, "sender_did")?;
    if msg.ciphertext.len() < SIGNAL_AEAD_MIN_BYTES || msg.ciphertext.len() > MAX_PAYLOAD_BYTES {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("ciphertext must be {SIGNAL_AEAD_MIN_BYTES}–{MAX_PAYLOAD_BYTES} bytes"),
        ));
    }
    if msg.signature.len() != SIGNAL_SIGNATURE_BYTES {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("signature must be {SIGNAL_SIGNATURE_BYTES} bytes"),
        ));
    }
    Ok(())
}

fn validate_identity_key_bytes(key: &IdentityKey, field: &str) -> Result<(), (StatusCode, String)> {
    if key.signing.len() != SIGNAL_PUBLIC_KEY_BYTES {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field}.signing must be {SIGNAL_PUBLIC_KEY_BYTES} bytes"),
        ));
    }
    if key.dh.len() != SIGNAL_PUBLIC_KEY_BYTES {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field}.dh must be {SIGNAL_PUBLIC_KEY_BYTES} bytes"),
        ));
    }
    Ok(())
}

fn validate_prekey_bundle_bytes(bundle: &PreKeyBundle) -> Result<(), (StatusCode, String)> {
    validate_identity_key_bytes(&bundle.identity_key, "prekey_bundle.identity_key")?;
    if bundle.signed_prekey.len() != SIGNAL_PUBLIC_KEY_BYTES {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("prekey_bundle.signed_prekey must be {SIGNAL_PUBLIC_KEY_BYTES} bytes"),
        ));
    }
    if bundle.signed_prekey_sig.len() != SIGNAL_SIGNATURE_BYTES {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("prekey_bundle.signed_prekey_sig must be {SIGNAL_SIGNATURE_BYTES} bytes"),
        ));
    }
    if !bundle
        .identity_key
        .verify(&bundle.signed_prekey, &bundle.signed_prekey_sig)
    {
        return Err((
            StatusCode::BAD_REQUEST,
            "prekey_bundle.signed_prekey_sig must verify signed_prekey with identity_key.signing"
                .to_string(),
        ));
    }
    if let Some(one_time_prekey) = &bundle.one_time_prekey {
        if one_time_prekey.len() != SIGNAL_PUBLIC_KEY_BYTES {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("prekey_bundle.one_time_prekey must be {SIGNAL_PUBLIC_KEY_BYTES} bytes"),
            ));
        }
    }
    if bundle.one_time_prekey.is_some() != bundle.one_time_prekey_id.is_some() {
        return Err((
            StatusCode::BAD_REQUEST,
            "prekey_bundle one_time_prekey and one_time_prekey_id must be provided together"
                .to_string(),
        ));
    }
    Ok(())
}

fn validate_prekey_bundle_binding(
    did: &str,
    device_id: &str,
    identity_key: &IdentityKey,
    prekey_bundle: &PreKeyBundle,
) -> Result<(), (StatusCode, String)> {
    validate_identity_key_bytes(identity_key, "identity_key")?;
    validate_prekey_bundle_bytes(prekey_bundle)?;
    if prekey_bundle.did != did {
        return Err((
            StatusCode::BAD_REQUEST,
            "prekey_bundle did does not match did".to_string(),
        ));
    }
    if prekey_bundle.device_id != device_id {
        return Err((
            StatusCode::BAD_REQUEST,
            "prekey_bundle device_id does not match device_id".to_string(),
        ));
    }
    if prekey_bundle.identity_key != *identity_key {
        return Err((
            StatusCode::BAD_REQUEST,
            "prekey_bundle identity_key does not match identity_key".to_string(),
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

    let identity_key: IdentityKey = serde_json::from_value(req.identity_key).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("identity_key is malformed: {e}"),
        )
    })?;
    let prekey_bundle: PreKeyBundle = serde_json::from_value(req.prekey_bundle).map_err(|e| {
        (
            StatusCode::BAD_REQUEST,
            format!("prekey_bundle is malformed: {e}"),
        )
    })?;
    validate_prekey_bundle_binding(&req.did, &req.device_id, &identity_key, &prekey_bundle)?;

    let bundle_bytes = serde_json::to_vec(&prekey_bundle).map_err(|e| {
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
    let ik_bytes = serde_json::to_vec(&identity_key).map_err(|e| {
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
            let bundle: PreKeyBundle = serde_json::from_slice(&b).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("stored prekey bundle is malformed: {e}"),
                )
            })?;
            let identity_key: IdentityKey = serde_json::from_slice(&ik).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("stored identity key is malformed: {e}"),
                )
            })?;
            validate_prekey_bundle_binding(&q.did, device_id, &identity_key, &bundle).map_err(
                |(_, msg)| {
                    (
                        StatusCode::INTERNAL_SERVER_ERROR,
                        format!("stored prekey bundle failed validation: {msg}"),
                    )
                },
            )?;
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
    if let Err((code, msg)) = validate_signal_message_fields(&msg) {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }

    // Require the caller to prove ownership of signal_message.sender_did.
    if let Err((code, err_msg)) =
        require_signal_auth(&headers, &msg.sender_did, &state.operator_did)
    {
        return (code, Json(serde_json::json!({ "error": err_msg }))).into_response();
    }

    let topic_name = format!("signal/inbox/{}/{}", msg.recipient_did, msg.device_id);
    let topic = kotoba_kse::topic::Topic(format!("kotoba/{topic_name}"));
    let payload_vec = match serde_json::to_vec(&msg) {
        Ok(v) => v,
        Err(e) => return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(
                serde_json::json!({ "error": format!("canonical signal_message serialize: {e}") }),
            ),
        )
            .into_response(),
    };
    let entry = state
        .journal
        .publish_checked(topic, bytes::Bytes::from(payload_vec))
        .await
        .map_err(|e| {
            (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({ "error": e })),
            )
        });
    let entry = match entry {
        Ok(entry) => entry,
        Err(resp) => return resp.into_response(),
    };

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
    let msg: SenderKeyMessage = match serde_json::from_value(req.sender_key_message.clone()) {
        Ok(m) => m,
        Err(e) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({ "error": e.to_string() })),
            )
                .into_response()
        }
    };
    if let Err((code, msg)) = validate_sender_key_message_fields(&msg) {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    if msg.group_id != req.group_id {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "error": "sender_key_message group_id does not match group_id"
            })),
        )
            .into_response();
    }
    if msg.sender_did != req.sender_did {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "error": "sender_key_message sender_did does not match sender_did"
            })),
        )
            .into_response();
    }

    let topic = kotoba_kse::topic::Topic(format!("kotoba/signal/group/{}", req.group_id));
    let payload_vec = match serde_json::to_vec(&msg) {
        Ok(v) => v,
        Err(e) => return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(
                serde_json::json!({ "error": format!("canonical sender_key_message serialize: {e}") }),
            ),
        )
            .into_response(),
    };
    let entry = state
        .journal
        .publish_checked(topic, bytes::Bytes::from(payload_vec))
        .await
        .map_err(|e| {
            (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({ "error": e })),
            )
        });
    let entry = match entry {
        Ok(entry) => entry,
        Err(resp) => return resp.into_response(),
    };

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
    if let Err((code, msg)) = validate_signal_message_fields(&msg) {
        return (code, Json(serde_json::json!({ "error": msg }))).into_response();
    }
    if msg.message_type != MessageType::DirectMessage {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "error": "signal_message messageType must be directMessage for sender key distribution"
            })),
        )
            .into_response();
    }
    if msg.recipient_did != req.recipient_did {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "error": "signal_message recipientDid does not match recipient_did"
            })),
        )
            .into_response();
    }
    if msg.device_id != req.recipient_device {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "error": "signal_message deviceId does not match recipient_device"
            })),
        )
            .into_response();
    }
    if let Err((code, err_msg)) =
        require_signal_auth(&headers, &msg.sender_did, &state.operator_did)
    {
        return (code, Json(serde_json::json!({ "error": err_msg }))).into_response();
    }

    let topic = kotoba_kse::topic::Topic(format!(
        "kotoba/signal/inbox/{}/{}",
        req.recipient_did, req.recipient_device
    ));
    let payload_vec = match serde_json::to_vec(&msg) {
        Ok(v) => v,
        Err(e) => return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(
                serde_json::json!({ "error": format!("canonical signal_message serialize: {e}") }),
            ),
        )
            .into_response(),
    };
    let entry = state
        .journal
        .publish_checked(topic, bytes::Bytes::from(payload_vec))
        .await
        .map_err(|e| {
            (
                StatusCode::BAD_REQUEST,
                Json(serde_json::json!({ "error": e })),
            )
        });
    let entry = match entry {
        Ok(entry) => entry,
        Err(resp) => return resp.into_response(),
    };

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

fn require_exact_bytes(
    bytes: &[u8],
    field: &str,
    expected: usize,
) -> Result<(), (StatusCode, String)> {
    if bytes.len() != expected {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must decode to {expected} bytes"),
        ));
    }
    Ok(())
}

fn is_leap_year(year: u32) -> bool {
    year.is_multiple_of(4) && (!year.is_multiple_of(100) || year.is_multiple_of(400))
}

fn days_in_month(year: u32, month: u32) -> Option<u32> {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => Some(31),
        4 | 6 | 9 | 11 => Some(30),
        2 if is_leap_year(year) => Some(29),
        2 => Some(28),
        _ => None,
    }
}

fn validate_utc_rfc3339_seconds(value: &str, field: &str) -> Result<(), (StatusCode, String)> {
    validate_visible_ascii_field(value, field, MAX_TIMESTAMP_LEN)?;
    let bytes = value.as_bytes();
    let is_digits = |range: std::ops::Range<usize>| bytes[range].iter().all(u8::is_ascii_digit);
    let valid_shape = bytes.len() == 20
        && is_digits(0..4)
        && bytes[4] == b'-'
        && is_digits(5..7)
        && bytes[7] == b'-'
        && is_digits(8..10)
        && bytes[10] == b'T'
        && is_digits(11..13)
        && bytes[13] == b':'
        && is_digits(14..16)
        && bytes[16] == b':'
        && is_digits(17..19)
        && bytes[19] == b'Z';
    if !valid_shape {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must use UTC RFC3339 seconds format YYYY-MM-DDTHH:MM:SSZ"),
        ));
    }

    let parse = |range: std::ops::Range<usize>| -> u32 {
        std::str::from_utf8(&bytes[range])
            .expect("digits are utf8")
            .parse()
            .expect("digits parse")
    };
    let year = parse(0..4);
    let month = parse(5..7);
    let day = parse(8..10);
    let hour = parse(11..13);
    let minute = parse(14..16);
    let second = parse(17..19);
    let Some(max_day) = days_in_month(year, month) else {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must contain valid UTC RFC3339 date/time fields"),
        ));
    };
    if !(1..=max_day).contains(&day) || hour > 23 || minute > 59 || second > 59 {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must contain valid UTC RFC3339 date/time fields"),
        ));
    }
    Ok(())
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
    validate_signal_did(did, "did")?;
    validate_utc_rfc3339_seconds(created_at, "createdAt")?;
    if signal_registration_id > SIGNAL_REGISTRATION_ID_MAX {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("signalRegistrationId must be at most {SIGNAL_REGISTRATION_ID_MAX}"),
        ));
    }
    let sig = decode_b64_field(signature, "signature")?;
    require_exact_bytes(&sig, "signature", SIGNAL_SIGNATURE_BYTES)?;
    let signal_identity_key = decode_b64_field(signal_identity_key, "signalIdentityKey")?;
    require_exact_bytes(
        &signal_identity_key,
        "signalIdentityKey",
        SIGNAL_PUBLIC_KEY_BYTES,
    )?;
    let signal_dh_key = decode_b64_field(signal_dh_key, "signalDhKey")?;
    require_exact_bytes(&signal_dh_key, "signalDhKey", SIGNAL_PUBLIC_KEY_BYTES)?;
    let binding = SignalBinding {
        did: did.to_string(),
        signal_identity_key,
        signal_dh_key,
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
    if record.did != q.did {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            "stored binding did does not match requested did".to_string(),
        ));
    }
    let (binding, sig) = binding_from_fields(
        &record.did,
        &record.signal_identity_key,
        &record.signal_dh_key,
        record.signal_registration_id,
        &record.created_at,
        &record.signature,
    )
    .map_err(|(_, msg)| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("stored binding failed validation: {msg}"),
        )
    })?;
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

    #[test]
    fn all_signal_nsids_have_correct_prefix() {
        for nsid in ALL_SIGNAL_NSIDS {
            assert!(
                nsid.starts_with("com.etzhayyim.signal."),
                "Signal NSID must start with com.etzhayyim.signal.: {nsid}"
            );
        }
    }

    #[test]
    fn all_signal_nsids_alphanumeric_dotted() {
        for nsid in ALL_SIGNAL_NSIDS {
            assert!(
                nsid.chars().all(|c| c.is_ascii_alphanumeric() || c == '.'),
                "NSID must be alphanumeric+dots: {nsid}"
            );
        }
    }

    #[test]
    fn all_signal_nsids_unique() {
        let mut seen = std::collections::HashSet::new();
        for nsid in ALL_SIGNAL_NSIDS {
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

    fn sample_signal_message() -> SignalMessage {
        SignalMessage {
            message_type: kotoba_signal::message::MessageType::DirectMessage,
            sender_did: "did:key:zSender".to_string(),
            recipient_did: "did:key:zRecipient".to_string(),
            device_id: "device-1".to_string(),
            group_id: None,
            ciphertext_envelope: "AAAA".to_string(),
            timestamp: "2026-06-12T00:00:00Z".to_string(),
            ephemeral_key: None,
            one_time_prekey_id: None,
        }
    }

    fn bearer_jwt_for_sub(did: &str) -> String {
        let payload = serde_json::json!({
            "sub": did,
            "exp": 4_102_444_800u64
        });
        format!("x.{}.x", B64U.encode(serde_json::to_vec(&payload).unwrap()))
    }

    fn sample_prekey_bundle(did: &str, device_id: &str) -> PreKeyBundle {
        let identity = kotoba_signal::identity::IdentityKeyPair::generate();
        let signed_prekey = kotoba_signal::prekey::SignedPreKey::generate(1, &identity);
        PreKeyBundle {
            did: did.to_string(),
            device_id: device_id.to_string(),
            identity_key: identity.public_key(),
            signed_prekey: signed_prekey.public_bytes().to_vec(),
            signed_prekey_id: signed_prekey.id,
            signed_prekey_sig: signed_prekey.signature.clone(),
            one_time_prekey: Some(vec![3; 32]),
            one_time_prekey_id: Some(2),
        }
    }

    async fn register_prekeys_err(
        state: Arc<KotobaState>,
        did: &str,
        device_id: &str,
        identity_key: IdentityKey,
        bundle: PreKeyBundle,
    ) -> (StatusCode, String) {
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(did))
                .parse()
                .unwrap(),
        );
        match register_prekeys(
            State(state),
            headers,
            Json(RegisterPrekeysReq {
                did: did.to_string(),
                device_id: device_id.to_string(),
                identity_key: serde_json::to_value(&identity_key).unwrap(),
                prekey_bundle: serde_json::to_value(&bundle).unwrap(),
            }),
        )
        .await
        {
            Ok(_) => panic!("register_prekeys must reject invalid request"),
            Err(err) => err,
        }
    }

    #[tokio::test]
    async fn register_prekeys_stores_canonical_identity_and_bundle_without_unknown_fields() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let bundle = sample_prekey_bundle(did, device_id);
        let identity_key = bundle.identity_key.clone();
        let mut raw_identity = serde_json::to_value(&identity_key).unwrap();
        raw_identity["untrustedVisibleMetadata"] = serde_json::json!("must-not-be-stored");
        let mut raw_bundle = serde_json::to_value(&bundle).unwrap();
        raw_bundle["untrustedVisibleMetadata"] = serde_json::json!("must-not-be-stored");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(did))
                .parse()
                .unwrap(),
        );
        let response = register_prekeys(
            State(state.clone()),
            headers,
            Json(RegisterPrekeysReq {
                did: did.to_string(),
                device_id: device_id.to_string(),
                identity_key: raw_identity,
                prekey_bundle: raw_bundle,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);

        let stored_identity = state
            .shelf
            .get(
                "KOTOBA_SIGNAL",
                &format!("signal/identity/{did}/{device_id}"),
            )
            .await
            .expect("stored identity");
        let stored_bundle = state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .expect("stored bundle");
        let stored_identity: serde_json::Value = serde_json::from_slice(&stored_identity).unwrap();
        let stored_bundle: serde_json::Value = serde_json::from_slice(&stored_bundle).unwrap();

        assert!(
            stored_identity.get("untrustedVisibleMetadata").is_none(),
            "{stored_identity}"
        );
        assert!(
            stored_bundle.get("untrustedVisibleMetadata").is_none(),
            "{stored_bundle}"
        );
        assert_eq!(
            stored_identity,
            serde_json::to_value(&identity_key).unwrap()
        );
        assert_eq!(stored_bundle, serde_json::to_value(&bundle).unwrap());
    }

    #[tokio::test]
    async fn get_prekey_bundle_returns_canonical_stored_bundle_without_unknown_fields() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let bundle = sample_prekey_bundle(did, device_id);
        let identity_key = bundle.identity_key.clone();
        let mut raw_identity = serde_json::to_value(&identity_key).unwrap();
        raw_identity["untrustedVisibleMetadata"] = serde_json::json!("must-not-be-returned");
        let mut raw_bundle = serde_json::to_value(&bundle).unwrap();
        raw_bundle["untrustedVisibleMetadata"] = serde_json::json!("must-not-be-returned");
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                format!("signal/identity/{did}/{device_id}"),
                bytes::Bytes::from(serde_json::to_vec(&raw_identity).unwrap()),
            )
            .await;
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                format!("signal/bundle/{did}/{device_id}"),
                bytes::Bytes::from(serde_json::to_vec(&raw_bundle).unwrap()),
            )
            .await;

        let response = get_prekey_bundle(
            State(state),
            Query(GetPreKeyBundleQuery {
                did: did.to_string(),
                device_id: Some(device_id.to_string()),
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(
            value["identityKey"],
            serde_json::to_value(&identity_key).unwrap()
        );
        assert_eq!(value["bundle"], serde_json::to_value(&bundle).unwrap());
        assert!(
            value["identityKey"]
                .get("untrustedVisibleMetadata")
                .is_none(),
            "{value}"
        );
        assert!(
            value["bundle"].get("untrustedVisibleMetadata").is_none(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn get_prekey_bundle_rejects_stored_bundle_did_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let mut bundle = sample_prekey_bundle(did, device_id);
        let identity_key = bundle.identity_key.clone();
        bundle.did = "did:key:zOtherPrekeyOwner".to_string();
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                format!("signal/identity/{did}/{device_id}"),
                bytes::Bytes::from(serde_json::to_vec(&identity_key).unwrap()),
            )
            .await;
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                format!("signal/bundle/{did}/{device_id}"),
                bytes::Bytes::from(serde_json::to_vec(&bundle).unwrap()),
            )
            .await;

        let err = match get_prekey_bundle(
            State(state),
            Query(GetPreKeyBundleQuery {
                did: did.to_string(),
                device_id: Some(device_id.to_string()),
            }),
        )
        .await
        {
            Ok(_) => panic!("get_prekey_bundle must reject stale mismatched stored bundle"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::INTERNAL_SERVER_ERROR);
        assert!(err.1.contains("failed validation"), "{err:?}");
        assert!(err.1.contains("did"), "{err:?}");
    }

    #[tokio::test]
    async fn get_prekey_bundle_rejects_stored_invalid_signed_prekey_signature() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let mut bundle = sample_prekey_bundle(did, device_id);
        let identity_key = bundle.identity_key.clone();
        bundle.signed_prekey_sig[0] ^= 0x01;
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                format!("signal/identity/{did}/{device_id}"),
                bytes::Bytes::from(serde_json::to_vec(&identity_key).unwrap()),
            )
            .await;
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                format!("signal/bundle/{did}/{device_id}"),
                bytes::Bytes::from(serde_json::to_vec(&bundle).unwrap()),
            )
            .await;

        let err = match get_prekey_bundle(
            State(state),
            Query(GetPreKeyBundleQuery {
                did: did.to_string(),
                device_id: Some(device_id.to_string()),
            }),
        )
        .await
        {
            Ok(_) => panic!("get_prekey_bundle must reject forged stored signed_prekey_sig"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::INTERNAL_SERVER_ERROR);
        assert!(err.1.contains("failed validation"), "{err:?}");
        assert!(err.1.contains("signed_prekey_sig"), "{err:?}");
    }

    #[tokio::test]
    async fn register_prekeys_rejects_invalid_identity_key_lengths() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let bundle = sample_prekey_bundle(did, device_id);
        let mut identity_key = bundle.identity_key.clone();
        identity_key.signing = vec![1; SIGNAL_PUBLIC_KEY_BYTES - 1];

        let err = register_prekeys_err(state.clone(), did, device_id, identity_key, bundle).await;
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("identity_key.signing"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn register_prekeys_rejects_invalid_prekey_bundle_lengths() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let mut bundle = sample_prekey_bundle(did, device_id);
        let identity_key = bundle.identity_key.clone();
        bundle.signed_prekey_sig = vec![2; SIGNAL_SIGNATURE_BYTES - 1];

        let err = register_prekeys_err(state.clone(), did, device_id, identity_key, bundle).await;
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("prekey_bundle.signed_prekey_sig"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn register_prekeys_rejects_invalid_signed_prekey_signature() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let mut bundle = sample_prekey_bundle(did, device_id);
        let identity_key = bundle.identity_key.clone();
        bundle.signed_prekey_sig[0] ^= 0x01;

        let err = register_prekeys_err(state.clone(), did, device_id, identity_key, bundle).await;
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("signed_prekey_sig"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn register_prekeys_rejects_one_time_prekey_without_matching_id() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let mut bundle = sample_prekey_bundle(did, device_id);
        let identity_key = bundle.identity_key.clone();
        bundle.one_time_prekey_id = None;

        let err =
            register_prekeys_err(state.clone(), did, device_id, identity_key.clone(), bundle).await;
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("one_time_prekey_id"), "{err:?}");

        let mut bundle = sample_prekey_bundle(did, device_id);
        bundle.one_time_prekey = None;
        let err = register_prekeys_err(state.clone(), did, device_id, identity_key, bundle).await;
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("one_time_prekey"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn register_prekeys_rejects_bundle_did_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let mut bundle = sample_prekey_bundle(did, device_id);
        bundle.did = "did:key:zOtherPrekeyOwner".to_string();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(did))
                .parse()
                .unwrap(),
        );
        let err = match register_prekeys(
            State(state.clone()),
            headers,
            Json(RegisterPrekeysReq {
                did: did.to_string(),
                device_id: device_id.to_string(),
                identity_key: serde_json::to_value(&bundle.identity_key).unwrap(),
                prekey_bundle: serde_json::to_value(&bundle).unwrap(),
            }),
        )
        .await
        {
            Ok(_) => panic!("register_prekeys must reject mismatched bundle DID"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("did"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn register_prekeys_rejects_bundle_device_id_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let mut bundle = sample_prekey_bundle(did, device_id);
        bundle.device_id = "device-2".to_string();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(did))
                .parse()
                .unwrap(),
        );
        let err = match register_prekeys(
            State(state.clone()),
            headers,
            Json(RegisterPrekeysReq {
                did: did.to_string(),
                device_id: device_id.to_string(),
                identity_key: serde_json::to_value(&bundle.identity_key).unwrap(),
                prekey_bundle: serde_json::to_value(&bundle).unwrap(),
            }),
        )
        .await
        {
            Ok(_) => panic!("register_prekeys must reject mismatched bundle device_id"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("device_id"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn register_prekeys_rejects_bundle_identity_key_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let did = "did:key:zPrekeyOwner";
        let device_id = "device-1";
        let bundle = sample_prekey_bundle(did, device_id);
        let other_identity = kotoba_signal::identity::IdentityKeyPair::generate().public_key();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(did))
                .parse()
                .unwrap(),
        );
        let err = match register_prekeys(
            State(state.clone()),
            headers,
            Json(RegisterPrekeysReq {
                did: did.to_string(),
                device_id: device_id.to_string(),
                identity_key: serde_json::to_value(&other_identity).unwrap(),
                prekey_bundle: serde_json::to_value(&bundle).unwrap(),
            }),
        )
        .await
        {
            Ok(_) => panic!("register_prekeys must reject mismatched bundle identity_key"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("identity_key"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &format!("signal/bundle/{did}/{device_id}"))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn send_message_publishes_canonical_signal_message_without_unknown_fields() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let msg = sample_signal_message();
        let mut raw = serde_json::to_value(&msg).unwrap();
        raw["untrustedVisibleMetadata"] = serde_json::json!("must-not-be-published");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = send_message(
            State(state.clone()),
            headers,
            Json(SendMessageReq {
                signal_message: raw,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);

        let entries = state.journal.read_since(1).await;
        assert_eq!(entries.len(), 1);
        let stored: serde_json::Value = serde_json::from_slice(&entries[0].payload).unwrap();
        assert!(stored.get("untrustedVisibleMetadata").is_none(), "{stored}");
        assert_eq!(stored, serde_json::to_value(&msg).unwrap());
    }

    #[tokio::test]
    async fn send_message_rejects_group_message_without_group_id() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let mut msg = sample_signal_message();
        msg.message_type = MessageType::GroupMessage;
        msg.group_id = None;

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = send_message(
            State(state.clone()),
            headers,
            Json(SendMessageReq {
                signal_message: serde_json::to_value(&msg).unwrap(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("groupId")),
            "{value}"
        );
        assert!(state.journal.read_since(1).await.is_empty());
    }

    #[tokio::test]
    async fn send_message_rejects_direct_message_with_group_id() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let mut msg = sample_signal_message();
        msg.message_type = MessageType::DirectMessage;
        msg.group_id = Some("group-1".to_string());

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = send_message(
            State(state.clone()),
            headers,
            Json(SendMessageReq {
                signal_message: serde_json::to_value(&msg).unwrap(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("groupMessage")),
            "{value}"
        );
        assert!(state.journal.read_since(1).await.is_empty());
    }

    #[tokio::test]
    async fn distribute_sender_key_publishes_canonical_signal_message_without_unknown_fields() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let msg = sample_signal_message();
        let mut raw = serde_json::to_value(&msg).unwrap();
        raw["untrustedVisibleMetadata"] = serde_json::json!("must-not-be-published");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = distribute_sender_key(
            State(state.clone()),
            headers,
            Json(DistributeSenderKeyReq {
                recipient_did: msg.recipient_did.clone(),
                recipient_device: msg.device_id.clone(),
                signal_message: raw,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);

        let entries = state.journal.read_since(1).await;
        assert_eq!(entries.len(), 1);
        let stored: serde_json::Value = serde_json::from_slice(&entries[0].payload).unwrap();
        assert!(stored.get("untrustedVisibleMetadata").is_none(), "{stored}");
        assert_eq!(stored, serde_json::to_value(&msg).unwrap());
    }

    #[tokio::test]
    async fn distribute_sender_key_rejects_signal_message_recipient_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let msg = sample_signal_message();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = distribute_sender_key(
            State(state.clone()),
            headers,
            Json(DistributeSenderKeyReq {
                recipient_did: "did:key:zDifferentRecipient".to_string(),
                recipient_device: msg.device_id.clone(),
                signal_message: serde_json::to_value(&msg).unwrap(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("recipientDid")),
            "{value}"
        );
        assert!(state.journal.read_since(1).await.is_empty());
    }

    #[tokio::test]
    async fn distribute_sender_key_rejects_non_direct_signal_message() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let mut msg = sample_signal_message();
        msg.message_type = MessageType::GroupMessage;
        msg.group_id = Some("group-1".to_string());

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = distribute_sender_key(
            State(state.clone()),
            headers,
            Json(DistributeSenderKeyReq {
                recipient_did: msg.recipient_did.clone(),
                recipient_device: msg.device_id.clone(),
                signal_message: serde_json::to_value(&msg).unwrap(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("directMessage")),
            "{value}"
        );
        assert!(state.journal.read_since(1).await.is_empty());
    }

    #[tokio::test]
    async fn distribute_sender_key_rejects_signal_message_device_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let msg = sample_signal_message();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = distribute_sender_key(
            State(state.clone()),
            headers,
            Json(DistributeSenderKeyReq {
                recipient_did: msg.recipient_did.clone(),
                recipient_device: "different-device".to_string(),
                signal_message: serde_json::to_value(&msg).unwrap(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("deviceId")),
            "{value}"
        );
        assert!(state.journal.read_since(1).await.is_empty());
    }

    #[tokio::test]
    async fn send_group_message_publishes_canonical_sender_key_message_without_unknown_fields() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let mut sender = kotoba_signal::group::SenderKeyState::generate(
            "group-canonical",
            "did:key:zGroupSender",
        );
        let msg = sender.encrypt(b"sealed group payload").unwrap();
        let mut raw = serde_json::to_value(&msg).unwrap();
        raw["untrustedVisibleMetadata"] = serde_json::json!("must-not-be-published");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = send_group_message(
            State(state.clone()),
            headers,
            Json(SendGroupMessageReq {
                group_id: msg.group_id.clone(),
                sender_did: msg.sender_did.clone(),
                sender_key_message: raw,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);

        let entries = state.journal.read_since(1).await;
        assert_eq!(entries.len(), 1);
        let stored: serde_json::Value = serde_json::from_slice(&entries[0].payload).unwrap();
        assert!(stored.get("untrustedVisibleMetadata").is_none(), "{stored}");
        assert_eq!(stored, serde_json::to_value(&msg).unwrap());
    }

    #[tokio::test]
    async fn send_group_message_rejects_sender_key_group_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let mut sender =
            kotoba_signal::group::SenderKeyState::generate("group-message", "did:key:zGroupSender");
        let msg = sender.encrypt(b"sealed group payload").unwrap();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&msg.sender_did))
                .parse()
                .unwrap(),
        );
        let response = send_group_message(
            State(state.clone()),
            headers,
            Json(SendGroupMessageReq {
                group_id: "group-route".to_string(),
                sender_did: msg.sender_did.clone(),
                sender_key_message: serde_json::to_value(&msg).unwrap(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("group_id")),
            "{value}"
        );
        assert!(state.journal.read_since(1).await.is_empty());
    }

    #[tokio::test]
    async fn send_group_message_rejects_sender_key_sender_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let mut sender = kotoba_signal::group::SenderKeyState::generate(
            "group-sender-mismatch",
            "did:key:zGroupSender",
        );
        let msg = sender.encrypt(b"sealed group payload").unwrap();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub("did:key:zRouteSender"))
                .parse()
                .unwrap(),
        );
        let response = send_group_message(
            State(state.clone()),
            headers,
            Json(SendGroupMessageReq {
                group_id: msg.group_id.clone(),
                sender_did: "did:key:zRouteSender".to_string(),
                sender_key_message: serde_json::to_value(&msg).unwrap(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::BAD_REQUEST);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("sender_did")),
            "{value}"
        );
        assert!(state.journal.read_since(1).await.is_empty());
    }

    #[test]
    fn sender_key_message_fields_reject_empty_ciphertext_and_signature() {
        let mut sender = kotoba_signal::group::SenderKeyState::generate(
            "group-validator",
            "did:key:zGroupSender",
        );
        let mut msg = sender.encrypt(b"sealed group payload").unwrap();

        msg.ciphertext = vec![0; SIGNAL_AEAD_MIN_BYTES - 1];
        let (code, err) = validate_sender_key_message_fields(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("ciphertext"));

        msg = sender.encrypt(b"sealed group payload").unwrap();
        msg.signature = vec![0; SIGNAL_SIGNATURE_BYTES - 1];
        let (code, err) = validate_sender_key_message_fields(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("signature"));

        msg = sender.encrypt(b"sealed group payload").unwrap();
        msg.signature = vec![0; SIGNAL_SIGNATURE_BYTES + 1];
        let (code, err) = validate_sender_key_message_fields(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("signature"));
    }

    #[test]
    fn signal_message_fields_accept_sample_message() {
        validate_signal_message_fields(&sample_signal_message()).unwrap();
    }

    #[test]
    fn signal_message_fields_reject_invalid_dids_and_device() {
        let mut msg = sample_signal_message();
        msg.sender_did = "not-a-did".to_string();
        let (code, err) = validate_signal_message_fields(&msg).unwrap_err();
        assert_eq!(code, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.contains("sender_did"));

        msg = sample_signal_message();
        msg.device_id = "device/1".to_string();
        let (code, err) = validate_signal_message_fields(&msg).unwrap_err();
        assert_eq!(code, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.contains("device_id"));
    }

    #[test]
    fn signal_message_fields_reject_empty_or_control_payload_fields() {
        let mut msg = sample_signal_message();
        msg.ciphertext_envelope.clear();
        let (code, err) = validate_signal_message_fields(&msg).unwrap_err();
        assert_eq!(code, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.contains("ciphertext_envelope"));

        msg = sample_signal_message();
        msg.timestamp = "2026-06-12\n00:00:00Z".to_string();
        let (code, err) = validate_signal_message_fields(&msg).unwrap_err();
        assert_eq!(code, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.contains("visible ASCII"));
    }

    #[test]
    fn signal_message_fields_reject_group_message_without_group_id() {
        let mut msg = sample_signal_message();
        msg.message_type = MessageType::GroupMessage;
        msg.group_id = None;
        let (code, err) = validate_signal_message_fields(&msg).unwrap_err();
        assert_eq!(code, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.contains("groupId"));

        msg.group_id = Some("group-1".to_string());
        validate_signal_message_fields(&msg).unwrap();
    }

    #[test]
    fn signal_message_fields_reject_non_group_message_with_group_id() {
        let mut msg = sample_signal_message();
        msg.message_type = MessageType::DirectMessage;
        msg.group_id = Some("group-1".to_string());
        let (code, err) = validate_signal_message_fields(&msg).unwrap_err();
        assert_eq!(code, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.contains("groupMessage"));

        msg.message_type = MessageType::Receipt;
        let (code, err) = validate_signal_message_fields(&msg).unwrap_err();
        assert_eq!(code, axum::http::StatusCode::BAD_REQUEST);
        assert!(err.contains("groupMessage"));
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
    fn public_signal_lexicons_match_xrpc_nsids() {
        let lexicons = [
            (
                NSID_SIGNAL_REGISTER_PREKEYS,
                "register.prekeys.json",
                include_str!("../../../lexicons/com/etzhayyim/signal/register.prekeys.json"),
                "procedure",
            ),
            (
                NSID_SIGNAL_GET_PREKEY_BUNDLE,
                "get.prekey.bundle.json",
                include_str!("../../../lexicons/com/etzhayyim/signal/get.prekey.bundle.json"),
                "query",
            ),
            (
                NSID_SIGNAL_SEND_MESSAGE,
                "send.message.json",
                include_str!("../../../lexicons/com/etzhayyim/signal/send.message.json"),
                "procedure",
            ),
            (
                NSID_SIGNAL_SEND_GROUP_MESSAGE,
                "send.group.message.json",
                include_str!("../../../lexicons/com/etzhayyim/signal/send.group.message.json"),
                "procedure",
            ),
            (
                NSID_SIGNAL_DISTRIBUTE_SENDER_KEY,
                "distribute.sender.key.json",
                include_str!("../../../lexicons/com/etzhayyim/signal/distribute.sender.key.json"),
                "procedure",
            ),
            (
                NSID_SIGNAL_PUBLISH_IDENTITY,
                "publish.identity.json",
                include_str!("../../../lexicons/com/etzhayyim/signal/publish.identity.json"),
                "procedure",
            ),
            (
                NSID_SIGNAL_RESOLVE_IDENTITY,
                "resolve.identity.json",
                include_str!("../../../lexicons/com/etzhayyim/signal/resolve.identity.json"),
                "query",
            ),
        ];

        let expected_nsids: std::collections::BTreeSet<&str> =
            ALL_SIGNAL_NSIDS.iter().copied().collect();
        let lexicon_nsids: std::collections::BTreeSet<&str> =
            lexicons.iter().map(|(nsid, _, _, _)| *nsid).collect();
        assert_eq!(
            lexicon_nsids, expected_nsids,
            "Signal lexicons must enumerate every public Signal NSID"
        );
        let expected_files: std::collections::BTreeSet<_> = lexicons
            .iter()
            .map(|(_, file_name, _, _)| file_name.to_string())
            .collect();
        let lexicon_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../lexicons/com/etzhayyim/signal");
        let actual_files: std::collections::BTreeSet<_> = std::fs::read_dir(&lexicon_dir)
            .expect("read signal lexicon dir")
            .map(|entry| {
                entry
                    .expect("dir entry")
                    .file_name()
                    .to_string_lossy()
                    .into_owned()
            })
            .collect();
        assert_eq!(
            actual_files, expected_files,
            "Signal XRPC surface must enumerate every public Signal lexicon"
        );

        for (expected_id, _, src, expected_type) in lexicons {
            let value: serde_json::Value = serde_json::from_str(src).expect("signal lexicon JSON");
            assert_eq!(value["lexicon"], 1);
            assert_eq!(value["id"], expected_id);
            assert_eq!(value["defs"]["main"]["type"], expected_type);
        }
    }

    #[test]
    fn signal_lexicons_expose_crypto_material_limits() {
        let register: serde_json::Value = serde_json::from_str(include_str!(
            "../../../lexicons/com/etzhayyim/signal/register.prekeys.json"
        ))
        .expect("register.prekeys lexicon JSON");
        assert_eq!(
            register["defs"]["identityKey"]["properties"]["signing"]["length"],
            SIGNAL_PUBLIC_KEY_BYTES
        );
        assert_eq!(
            register["defs"]["identityKey"]["properties"]["dh"]["length"],
            SIGNAL_PUBLIC_KEY_BYTES
        );
        assert_eq!(
            register["defs"]["prekeyBundle"]["properties"]["signed_prekey_sig"]["length"],
            SIGNAL_SIGNATURE_BYTES
        );

        let group_message: serde_json::Value = serde_json::from_str(include_str!(
            "../../../lexicons/com/etzhayyim/signal/send.group.message.json"
        ))
        .expect("send.group.message lexicon JSON");
        let sender_key_props = &group_message["defs"]["senderKeyMessage"]["properties"];
        assert_eq!(
            sender_key_props["ciphertext"]["minLength"],
            SIGNAL_AEAD_MIN_BYTES
        );
        assert_eq!(
            sender_key_props["ciphertext"]["maxLength"],
            MAX_PAYLOAD_BYTES
        );
        assert_eq!(
            sender_key_props["signature"]["length"],
            SIGNAL_SIGNATURE_BYTES
        );

        let send_message: serde_json::Value = serde_json::from_str(include_str!(
            "../../../lexicons/com/etzhayyim/signal/send.message.json"
        ))
        .expect("send.message lexicon JSON");
        assert_eq!(
            send_message["defs"]["main"]["output"]["schema"]["properties"]["messageId"]
                ["minLength"],
            1
        );
        assert_eq!(
            send_message["defs"]["main"]["output"]["schema"]["properties"]["messageId"]
                ["maxLength"],
            256
        );
        assert_eq!(
            send_message["defs"]["main"]["output"]["schema"]["properties"]["messageId"]["pattern"]
                .as_str(),
            Some("^[!-~]+$")
        );
        let signal_props = &send_message["defs"]["signalMessage"]["properties"];
        for field in ["messageType", "groupId"] {
            let description = signal_props[field]["description"]
                .as_str()
                .unwrap_or_else(|| panic!("{field} description"));
            assert!(description.contains("groupMessage"), "{description}");
            assert!(description.contains("groupId"), "{description}");
            assert!(description.contains("absent"), "{description}");
        }

        let publish: serde_json::Value = serde_json::from_str(include_str!(
            "../../../lexicons/com/etzhayyim/signal/publish.identity.json"
        ))
        .expect("publish.identity lexicon JSON");
        let props = &publish["defs"]["main"]["input"]["schema"]["properties"];
        assert_eq!(
            props["signalRegistrationId"]["maximum"],
            SIGNAL_REGISTRATION_ID_MAX
        );
        assert_eq!(props["createdAt"]["minLength"], 20);
        assert_eq!(props["createdAt"]["maxLength"], 20);
        assert!(
            props["createdAt"]["pattern"]
                .as_str()
                .is_some_and(|pattern| pattern.contains("T") && pattern.ends_with("Z$")),
            "{}",
            props["createdAt"]["pattern"]
        );
        assert_eq!(props["signalIdentityKey"]["minLength"], 43);
        assert_eq!(props["signalIdentityKey"]["maxLength"], 43);
        assert_eq!(
            props["signalIdentityKey"]["pattern"].as_str(),
            Some("^[A-Za-z0-9_-]+$")
        );
        assert_eq!(props["signalDhKey"]["minLength"], 43);
        assert_eq!(props["signalDhKey"]["maxLength"], 43);
        assert_eq!(
            props["signalDhKey"]["pattern"].as_str(),
            Some("^[A-Za-z0-9_-]+$")
        );
        assert_eq!(props["signature"]["minLength"], 86);
        assert_eq!(props["signature"]["maxLength"], 86);
        assert_eq!(
            props["signature"]["pattern"].as_str(),
            Some("^[A-Za-z0-9_-]+$")
        );

        let resolve: serde_json::Value = serde_json::from_str(include_str!(
            "../../../lexicons/com/etzhayyim/signal/resolve.identity.json"
        ))
        .expect("resolve.identity lexicon JSON");
        let resolve_props = &resolve["defs"]["main"]["output"]["schema"]["properties"];
        for field in ["signalIdentityKey", "signalDhKey", "signature"] {
            assert_eq!(
                resolve_props[field]["pattern"].as_str(),
                Some("^[A-Za-z0-9_-]+$"),
                "resolve.identity {field} must publish the base64url-no-pad contract"
            );
        }

        let distribute: serde_json::Value = serde_json::from_str(include_str!(
            "../../../lexicons/com/etzhayyim/signal/distribute.sender.key.json"
        ))
        .expect("distribute.sender.key lexicon JSON");
        for (name, value) in [
            ("send.group.message", &group_message),
            ("distribute.sender.key", &distribute),
        ] {
            let message_id = &value["defs"]["main"]["output"]["schema"]["properties"]["messageId"];
            assert_eq!(message_id["minLength"], 1, "{name} messageId minLength");
            assert_eq!(message_id["maxLength"], 256, "{name} messageId maxLength");
            assert_eq!(
                message_id["pattern"].as_str(),
                Some("^[!-~]+$"),
                "{name} messageId must publish the visible-ASCII CID contract"
            );
        }
        let description = distribute["defs"]["main"]["input"]["schema"]["properties"]
            ["signalMessage"]["description"]
            .as_str()
            .expect("signalMessage description");
        assert!(
            description.contains("messageType=directMessage"),
            "{description}"
        );
    }

    #[test]
    fn signal_lexicons_publish_did_field_contracts() {
        let lexicons = [
            (
                "register.prekeys",
                serde_json::from_str::<serde_json::Value>(include_str!(
                    "../../../lexicons/com/etzhayyim/signal/register.prekeys.json"
                ))
                .expect("register.prekeys lexicon JSON"),
                vec![
                    "/defs/main/input/schema/properties/did",
                    "/defs/main/output/schema/properties/did",
                    "/defs/prekeyBundle/properties/did",
                ],
            ),
            (
                "get.prekey.bundle",
                serde_json::from_str::<serde_json::Value>(include_str!(
                    "../../../lexicons/com/etzhayyim/signal/get.prekey.bundle.json"
                ))
                .expect("get.prekey.bundle lexicon JSON"),
                vec![
                    "/defs/main/parameters/properties/did",
                    "/defs/main/output/schema/properties/did",
                ],
            ),
            (
                "send.message",
                serde_json::from_str::<serde_json::Value>(include_str!(
                    "../../../lexicons/com/etzhayyim/signal/send.message.json"
                ))
                .expect("send.message lexicon JSON"),
                vec![
                    "/defs/signalMessage/properties/senderDid",
                    "/defs/signalMessage/properties/recipientDid",
                ],
            ),
            (
                "send.group.message",
                serde_json::from_str::<serde_json::Value>(include_str!(
                    "../../../lexicons/com/etzhayyim/signal/send.group.message.json"
                ))
                .expect("send.group.message lexicon JSON"),
                vec![
                    "/defs/main/input/schema/properties/senderDid",
                    "/defs/senderKeyMessage/properties/sender_did",
                ],
            ),
            (
                "distribute.sender.key",
                serde_json::from_str::<serde_json::Value>(include_str!(
                    "../../../lexicons/com/etzhayyim/signal/distribute.sender.key.json"
                ))
                .expect("distribute.sender.key lexicon JSON"),
                vec!["/defs/main/input/schema/properties/recipientDid"],
            ),
            (
                "publish.identity",
                serde_json::from_str::<serde_json::Value>(include_str!(
                    "../../../lexicons/com/etzhayyim/signal/publish.identity.json"
                ))
                .expect("publish.identity lexicon JSON"),
                vec![
                    "/defs/main/input/schema/properties/did",
                    "/defs/main/output/schema/properties/did",
                ],
            ),
            (
                "resolve.identity",
                serde_json::from_str::<serde_json::Value>(include_str!(
                    "../../../lexicons/com/etzhayyim/signal/resolve.identity.json"
                ))
                .expect("resolve.identity lexicon JSON"),
                vec![
                    "/defs/main/parameters/properties/did",
                    "/defs/main/output/schema/properties/did",
                ],
            ),
        ];

        for (name, lexicon, paths) in lexicons {
            for path in paths {
                let schema = lexicon
                    .pointer(path)
                    .unwrap_or_else(|| panic!("{name} missing {path}"));
                assert_eq!(schema["minLength"], 1, "{name} {path} minLength");
                assert_eq!(schema["maxLength"], MAX_DID_LEN, "{name} {path} maxLength");
                assert_eq!(
                    schema["pattern"].as_str(),
                    Some("^did:[!-~]+$"),
                    "{name} {path} must publish the DID prefix and visible-ASCII contract"
                );
            }
        }
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

    #[test]
    fn binding_from_fields_rejects_invalid_key_and_signature_lengths() {
        let (_did, req) = signed_didkey_binding();
        let err = binding_from_fields(
            &req.did,
            &B64U.encode(vec![1; SIGNAL_PUBLIC_KEY_BYTES - 1]),
            &req.signal_dh_key,
            req.signal_registration_id,
            &req.created_at,
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("signalIdentityKey"), "{err:?}");

        let err = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            &req.created_at,
            &B64U.encode(vec![1; SIGNAL_SIGNATURE_BYTES - 1]),
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("signature"), "{err:?}");
    }

    #[test]
    fn binding_from_fields_rejects_non_base64url_identity_fields() {
        let (_did, req) = signed_didkey_binding();
        for (field, signal_identity_key, signal_dh_key, signature) in [
            (
                "signalIdentityKey",
                "not+base64url/value",
                req.signal_dh_key.as_str(),
                req.signature.as_str(),
            ),
            (
                "signalDhKey",
                req.signal_identity_key.as_str(),
                "not+base64url/value",
                req.signature.as_str(),
            ),
            (
                "signature",
                req.signal_identity_key.as_str(),
                req.signal_dh_key.as_str(),
                "not+base64url/value",
            ),
        ] {
            let err = binding_from_fields(
                &req.did,
                signal_identity_key,
                signal_dh_key,
                req.signal_registration_id,
                &req.created_at,
                signature,
            )
            .unwrap_err();
            assert_eq!(err.0, StatusCode::BAD_REQUEST);
            assert!(err.1.contains(field), "{field}: {err:?}");
            assert!(err.1.contains("base64url"), "{field}: {err:?}");
        }
    }

    #[test]
    fn binding_from_fields_rejects_invalid_metadata_fields() {
        let (_did, req) = signed_didkey_binding();
        let err = binding_from_fields(
            "not-a-did",
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            &req.created_at,
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("did"), "{err:?}");

        let err = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            "2026-06-01\n00:00:00Z",
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("createdAt"), "{err:?}");

        let err = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            "2026-02-29T00:00:00Z",
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("createdAt"), "{err:?}");

        let err = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            "2026-04-31T00:00:00Z",
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("createdAt"), "{err:?}");

        let (binding, _) = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            "2028-02-29T00:00:00Z",
            &req.signature,
        )
        .unwrap();
        assert_eq!(binding.created_at, "2028-02-29T00:00:00Z");

        let err = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            "2026-13-01T00:00:00Z",
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("createdAt"), "{err:?}");

        let err = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            req.signal_registration_id,
            "2026-06-01T00:00:00+09:00",
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("createdAt"), "{err:?}");

        let err = binding_from_fields(
            &req.did,
            &req.signal_identity_key,
            &req.signal_dh_key,
            SIGNAL_REGISTRATION_ID_MAX + 1,
            &req.created_at,
            &req.signature,
        )
        .unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("signalRegistrationId"), "{err:?}");
    }

    #[tokio::test]
    async fn publish_signal_identity_rejects_invalid_signature_length() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let (did, mut req) = signed_didkey_binding();
        req.signature = B64U.encode(vec![1; SIGNAL_SIGNATURE_BYTES - 1]);
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&did))
                .parse()
                .unwrap(),
        );

        let err = match publish_signal_identity(State(state.clone()), headers, Json(req)).await {
            Ok(_) => panic!("publish_signal_identity must reject short signatures"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("signature"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &shelf_binding_key(&did))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn publish_signal_identity_rejects_invalid_created_at() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let (did, mut req) = signed_didkey_binding();
        req.created_at = "2026-06-01\n00:00:00Z".to_string();
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&did))
                .parse()
                .unwrap(),
        );

        let err = match publish_signal_identity(State(state.clone()), headers, Json(req)).await {
            Ok(_) => panic!("publish_signal_identity must reject invalid createdAt"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("createdAt"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &shelf_binding_key(&did))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn publish_signal_identity_rejects_registration_id_out_of_range() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let (did, mut req) = signed_didkey_binding();
        req.signal_registration_id = SIGNAL_REGISTRATION_ID_MAX + 1;
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(&did))
                .parse()
                .unwrap(),
        );

        let err = match publish_signal_identity(State(state.clone()), headers, Json(req)).await {
            Ok(_) => panic!("publish_signal_identity must reject out-of-range registration id"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("signalRegistrationId"), "{err:?}");
        assert!(state
            .shelf
            .get("KOTOBA_SIGNAL", &shelf_binding_key(&did))
            .await
            .is_none());
    }

    #[tokio::test]
    async fn resolve_signal_identity_rejects_stored_did_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let (did, req) = signed_didkey_binding();
        let record = StoredBinding {
            did: "did:key:zDifferentStoredDid".to_string(),
            signal_identity_key: req.signal_identity_key,
            signal_dh_key: req.signal_dh_key,
            signal_registration_id: req.signal_registration_id,
            created_at: req.created_at,
            signature: req.signature,
        };
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                shelf_binding_key(&did),
                bytes::Bytes::from(serde_json::to_vec(&record).unwrap()),
            )
            .await;

        let err = match resolve_signal_identity(
            State(state),
            Query(ResolveSignalIdentityQuery { did: did.clone() }),
        )
        .await
        {
            Ok(_) => panic!("resolve_signal_identity must reject mismatched stored DID"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::INTERNAL_SERVER_ERROR);
        assert!(err.1.contains("did"), "{err:?}");
    }

    #[tokio::test]
    async fn resolve_signal_identity_rejects_stored_invalid_created_at_as_server_error() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let (did, req) = signed_didkey_binding();
        let record = StoredBinding {
            did: did.clone(),
            signal_identity_key: req.signal_identity_key,
            signal_dh_key: req.signal_dh_key,
            signal_registration_id: req.signal_registration_id,
            created_at: "2026-02-29T00:00:00Z".to_string(),
            signature: req.signature,
        };
        state
            .shelf
            .put(
                "KOTOBA_SIGNAL",
                shelf_binding_key(&did),
                bytes::Bytes::from(serde_json::to_vec(&record).unwrap()),
            )
            .await;

        let err = match resolve_signal_identity(
            State(state),
            Query(ResolveSignalIdentityQuery { did: did.clone() }),
        )
        .await
        {
            Ok(_) => panic!("resolve_signal_identity must reject invalid stored createdAt"),
            Err(err) => err,
        };
        assert_eq!(err.0, StatusCode::INTERNAL_SERVER_ERROR);
        assert!(
            err.1.contains("stored binding failed validation"),
            "{err:?}"
        );
        assert!(err.1.contains("createdAt"), "{err:?}");
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
