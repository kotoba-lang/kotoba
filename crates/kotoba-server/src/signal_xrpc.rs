/// Signal Protocol XRPC endpoints.
/// NSIDs: ai.gftd.signal.{register.prekeys, get.prekey.bundle, send.message, send.group.message}
///
/// These endpoints make kotoba-server the SSoT for Signal Protocol E2E,
/// superseding `@gftd/signal` (`10-protocol/signal/`).

pub const NSID_SIGNAL_REGISTER_PREKEYS:      &str = "ai.gftd.signal.register.prekeys";
pub const NSID_SIGNAL_GET_PREKEY_BUNDLE:     &str = "ai.gftd.signal.get.prekey.bundle";
pub const NSID_SIGNAL_SEND_MESSAGE:          &str = "ai.gftd.signal.send.message";
pub const NSID_SIGNAL_SEND_GROUP_MESSAGE:    &str = "ai.gftd.signal.send.group.message";
pub const NSID_SIGNAL_DISTRIBUTE_SENDER_KEY: &str = "ai.gftd.signal.distribute.sender.key";

use std::sync::Arc;
use axum::{
    Json,
    extract::{State, Query},
    http::StatusCode,
    response::IntoResponse,
};
use serde::{Deserialize, Serialize};

use kotoba_signal::message::SignalMessage;
use crate::server::KotobaState;

// ── registerPrekeys ───────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterPrekeysReq {
    pub did:              String,
    pub device_id:        String,
    /// Serialised `IdentityKey` (JSON).
    pub identity_key:     serde_json::Value,
    /// Serialised `PreKeyBundle` (JSON) — signed_prekey + one_time_prekeys.
    pub prekey_bundle:    serde_json::Value,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RegisterPrekeysResp {
    pub status: &'static str,
    pub did:    String,
}

pub async fn register_prekeys(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<RegisterPrekeysReq>,
) -> impl IntoResponse {
    let key = format!("signal/bundle/{}/{}", req.did, req.device_id);
    state.shelf.put(
        "KOTOBA_SIGNAL",
        key,
        bytes::Bytes::from(serde_json::to_vec(&req.prekey_bundle).unwrap_or_default()),
    ).await;
    // Store identity key separately for lookup
    let ik_key = format!("signal/identity/{}/{}", req.did, req.device_id);
    state.shelf.put(
        "KOTOBA_SIGNAL",
        ik_key,
        bytes::Bytes::from(serde_json::to_vec(&req.identity_key).unwrap_or_default()),
    ).await;
    Json(RegisterPrekeysResp { status: "ok", did: req.did })
}

// ── getPrekeyBundle ───────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct GetPreKeyBundleQuery {
    pub did:       String,
    pub device_id: Option<String>,
}

pub async fn get_prekey_bundle(
    State(state): State<Arc<KotobaState>>,
    Query(q): Query<GetPreKeyBundleQuery>,
) -> impl IntoResponse {
    let device_id = q.device_id.as_deref().unwrap_or("default");
    let bundle_key = format!("signal/bundle/{}/{}", q.did, device_id);
    let ik_key     = format!("signal/identity/{}/{}", q.did, device_id);

    let bundle_bytes = state.shelf.get("KOTOBA_SIGNAL", &bundle_key).await;
    let ik_bytes     = state.shelf.get("KOTOBA_SIGNAL", &ik_key).await;

    match (bundle_bytes, ik_bytes) {
        (Some(b), Some(ik)) => {
            let bundle: serde_json::Value = serde_json::from_slice(&b).unwrap_or_default();
            let identity_key: serde_json::Value = serde_json::from_slice(&ik).unwrap_or_default();
            Json(serde_json::json!({
                "did": q.did,
                "deviceId": device_id,
                "identityKey": identity_key,
                "bundle": bundle,
            })).into_response()
        }
        _ => (StatusCode::NOT_FOUND, Json(serde_json::json!({
            "error": "prekey bundle not found",
            "did": q.did,
        }))).into_response(),
    }
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
    pub status:     &'static str,
    pub message_id: String,
}

pub async fn send_message(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<SendMessageReq>,
) -> impl IntoResponse {
    // Route the encrypted message envelope to the recipient's inbox on the KSE Journal.
    let msg: SignalMessage = match serde_json::from_value(req.signal_message.clone()) {
        Ok(m) => m,
        Err(e) => return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({ "error": e.to_string() })),
        ).into_response(),
    };

    let topic_name = format!("signal/inbox/{}/{}", msg.recipient_did, msg.device_id);
    let topic = kotoba_kse::topic::Topic(format!("kotoba/{topic_name}"));
    let payload = bytes::Bytes::from(serde_json::to_vec(&req.signal_message).unwrap_or_default());
    let entry = state.journal.publish(topic, payload).await;

    Json(SendMessageResp {
        status: "ok",
        message_id: entry.cid.to_multibase(),
    }).into_response()
}

// ── sendGroupMessage ──────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SendGroupMessageReq {
    pub group_id:     String,
    pub sender_did:   String,
    pub sender_key_message: serde_json::Value,
}

pub async fn send_group_message(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<SendGroupMessageReq>,
) -> impl IntoResponse {
    let topic = kotoba_kse::topic::Topic(
        format!("kotoba/signal/group/{}", req.group_id),
    );
    let payload = bytes::Bytes::from(
        serde_json::to_vec(&req.sender_key_message).unwrap_or_default(),
    );
    let entry = state.journal.publish(topic, payload).await;

    Json(serde_json::json!({
        "status": "ok",
        "messageId": entry.cid.to_multibase(),
        "groupId": req.group_id,
    })).into_response()
}

// ── distributeSenderKey ───────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct DistributeSenderKeyReq {
    /// Recipient DID — receives the distribution via their 1:1 inbox.
    pub recipient_did:  String,
    pub recipient_device: String,
    /// SenderKeyDistribution serialised as a SignalMessage ciphertext.
    pub signal_message: serde_json::Value,
}

pub async fn distribute_sender_key(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<DistributeSenderKeyReq>,
) -> impl IntoResponse {
    let topic = kotoba_kse::topic::Topic(
        format!("kotoba/signal/inbox/{}/{}", req.recipient_did, req.recipient_device),
    );
    let payload = bytes::Bytes::from(
        serde_json::to_vec(&req.signal_message).unwrap_or_default(),
    );
    let entry = state.journal.publish(topic, payload).await;

    Json(serde_json::json!({
        "status": "ok",
        "messageId": entry.cid.to_multibase(),
    })).into_response()
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
                nsid.starts_with("ai.gftd.signal."),
                "Signal NSID must start with ai.gftd.signal.: {nsid}"
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
}
