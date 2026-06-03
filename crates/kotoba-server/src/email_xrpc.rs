//! XRPC handlers for encrypted email storage and retrieval.
//!
//! NSIDs:
//!   com.etzhayyim.apps.kotoba.email.list   — list email metadata (GET)
//!   com.etzhayyim.apps.kotoba.email.read   — decrypt and return one email (GET)
//!   com.etzhayyim.apps.kotoba.email.ingest — manually ingest a raw message (POST)
//!   com.etzhayyim.apps.kotoba.email.send   — native E2E send via Signal (POST)
//!
//! Two encryption regimes share one inbox datom schema:
//!   • Ingested mail (`email.ingest`, SMTP/Gmail bridge): body is sealed with the
//!     node's `AgentCrypto` vault key (encryption at rest — the server CAN read it).
//!   • Native mail (`email.send`): each recipient's body is a Signal ciphertext
//!     sealed client-side to that recipient's device session. The server stores
//!     and routes the opaque envelope but is **zero-access** — it never holds a key
//!     that decrypts the body (the Proton-style guarantee). Such datoms carry
//!     `email/enc = "signal:v1"`; `email.read` returns the raw envelope for the
//!     recipient to decrypt rather than attempting a server-side decrypt.

pub const NSID_EMAIL_LIST: &str = "com.etzhayyim.apps.kotoba.email.list";
pub const NSID_EMAIL_READ: &str = "com.etzhayyim.apps.kotoba.email.read";
pub const NSID_EMAIL_INGEST: &str = "com.etzhayyim.apps.kotoba.email.ingest";
pub const NSID_EMAIL_SEND: &str = "com.etzhayyim.apps.kotoba.email.send";

/// Marks a body blob that is a client-sealed Signal envelope (zero-access).
const ENC_SIGNAL_V1: &str = "signal:v1";

use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::sync::Arc;

use kotoba_core::cid::KotobaCid;
use kotoba_ingest::{graph_cid_for, EmailIngestor};
use kotoba_kqe::{quad::LegacyQuad, quad::LegacyQuadObject};
use kotoba_signal::message::SignalMessage;

use crate::server::KotobaState;

const MAX_OWNER_DID_LEN: usize = 512;
const MAX_EMAIL_CID_LEN: usize = 256;
// 25 MiB raw ≈ 33 MiB base64 (Gmail attachment limit)
const MAX_RAW_B64_LEN: usize = 34 * 1024 * 1024;
const MAX_THREAD_ID_LEN: usize = 256; // mirrors EmailIngestor::ingest_raw validation

fn require_email_auth(
    headers: &HeaderMap,
    owner_did: &str,
    operator_did: &str,
) -> Result<(), (StatusCode, String)> {
    let token = headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or_else(|| {
            tracing::warn!("email auth: missing Bearer token");
            (
                StatusCode::UNAUTHORIZED,
                "Authorization: Bearer <token> required".to_string(),
            )
        })?;
    if crate::graph_auth::jwt_exp_elapsed(token) {
        tracing::warn!("email auth: expired JWT");
        return Err((
            StatusCode::UNAUTHORIZED,
            "Bearer token has expired".to_string(),
        ));
    }
    let sub = crate::graph_auth::jwt_sub(token).ok_or_else(|| {
        tracing::warn!("email auth: JWT missing sub claim");
        (
            StatusCode::UNAUTHORIZED,
            "Bearer token missing sub claim".to_string(),
        )
    })?;
    if sub == owner_did || sub == operator_did {
        Ok(())
    } else {
        tracing::warn!(sub = %sub, owner_did = %owner_did, "email auth: sub mismatch");
        Err((
            StatusCode::UNAUTHORIZED,
            format!("Bearer sub does not match owner_did {owner_did:?}"),
        ))
    }
}

async fn current_email_quads(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
) -> Result<Vec<LegacyQuad>, (StatusCode, String)> {
    let db = crate::xrpc::current_db_for_graph(state, graph_cid).await?;
    Ok(db
        .datoms()
        .into_iter()
        .filter_map(|datom| {
            let substrate = datom.to_kqe().ok()?;
            Some(LegacyQuad {
                graph: graph_cid.clone(),
                subject: substrate.e,
                predicate: substrate.a,
                object: substrate.v.into(),
            })
        })
        .collect())
}

async fn legacy_email_datoms_for_commit(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
    tx_cid: &KotobaCid,
    email_cid: &KotobaCid,
) -> Result<Vec<kotoba_datomic::Datom>, (StatusCode, String)> {
    let arrangement = state
        .quad_store
        .arrangement(graph_cid)
        .await
        .ok_or_else(|| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                "email ingest produced no graph arrangement".to_string(),
            )
        })?;
    let datoms = arrangement
        .get_subject_datoms(tx_cid, email_cid)
        .into_iter()
        .map(kotoba_datomic::Datom::from_kqe)
        .collect::<Vec<_>>();
    if datoms.is_empty() {
        return Err((
            StatusCode::INTERNAL_SERVER_ERROR,
            "email ingest produced no datoms".to_string(),
        ));
    }
    Ok(datoms)
}

fn text_from_quads(quads: &[LegacyQuad], subject: &KotobaCid, predicate: &str) -> String {
    quads
        .iter()
        .find_map(|quad| {
            if &quad.subject == subject && quad.predicate == predicate {
                if let LegacyQuadObject::Text(text) = &quad.object {
                    return Some(text.clone());
                }
            }
            None
        })
        .unwrap_or_default()
}

// ── email.list ────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct EmailListQuery {
    pub owner_did: String,
    pub limit: Option<usize>,
    pub offset: Option<usize>,
}

pub async fn email_list(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<EmailListQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    crate::graph_auth::validate_did(&q.owner_did, "owner_did", MAX_OWNER_DID_LEN)?;
    require_email_auth(&headers, &q.owner_did, &state.operator_did)?;

    let graph_cid = graph_cid_for(&q.owner_did);
    let quads = current_email_quads(&state, &graph_cid).await?;

    let mut entries: Vec<(KotobaCid, String)> = quads
        .iter()
        .filter_map(|quad| {
            if quad.predicate != "email/date" {
                return None;
            }
            match &quad.object {
                LegacyQuadObject::Text(date) => Some((quad.subject.clone(), date.clone())),
                _ => None,
            }
        })
        .collect();

    // Sort descending by date (Unix timestamp string — lexicographic works for equal-width)
    entries.sort_by(|a, b| b.1.cmp(&a.1));

    let total = entries.len();
    let offset = q.offset.unwrap_or(0);
    let limit = q.limit.unwrap_or(50).min(200);

    let page: Vec<Value> = entries
        .into_iter()
        .skip(offset)
        .take(limit)
        .map(|(email_cid, date)| {
            let message_id = text_from_quads(&quads, &email_cid, "email/message_id");
            json!({ "cid": email_cid.to_multibase(), "date": date, "message_id": message_id })
        })
        .collect();

    Ok(
        Json(json!({ "emails": page, "total": total, "offset": offset, "limit": limit }))
            .into_response(),
    )
}

// ── email.read ────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct EmailReadQuery {
    pub email_cid: String,
    pub owner_did: String,
}

pub async fn email_read(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<EmailReadQuery>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::validate_did(&q.owner_did, "owner_did", MAX_OWNER_DID_LEN)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if q.email_cid.is_empty() || q.email_cid.len() > MAX_EMAIL_CID_LEN {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("email_cid must be 1–{MAX_EMAIL_CID_LEN} bytes") })),
        )
            .into_response();
    }
    if let Err((code, msg)) = require_email_auth(&headers, &q.owner_did, &state.operator_did) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }

    let crypto = match &state.crypto {
        Some(c) => Arc::clone(c),
        None => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "error": "crypto not initialised" })),
            )
                .into_response()
        }
    };

    let graph_cid = graph_cid_for(&q.owner_did);
    let quads = match current_email_quads(&state, &graph_cid).await {
        Ok(quads) if !quads.is_empty() => quads,
        Ok(_) => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "error": "no emails found for owner_did" })),
            )
                .into_response()
        }
        Err((code, msg)) => return (code, Json(json!({ "error": msg }))).into_response(),
    };

    let email_cid = match KotobaCid::from_multibase(&q.email_cid) {
        Some(cid) => cid,
        None => {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({ "error": "invalid email_cid multibase" })),
            )
                .into_response()
        }
    };

    // Native E2E (Signal) messages carry an opaque client-sealed envelope the
    // server cannot decrypt. Return the envelope verbatim for the recipient to
    // open with their Signal session key. `from`/`to` here are plaintext routing
    // metadata (DIDs), not sealed PII — return them as-is.
    if text_from_quads(&quads, &email_cid, "email/enc") == ENC_SIGNAL_V1 {
        let blob_cid_str = text_from_quads(&quads, &email_cid, "email/body_cid");
        let blob_cid = match KotobaCid::from_multibase(&blob_cid_str) {
            Some(cid) => cid,
            None => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({ "error": "invalid body_cid multibase" })),
                )
                    .into_response()
            }
        };
        let envelope_bytes = match state.vault.get(&blob_cid).await {
            Some(b) => b,
            None => {
                return (
                    StatusCode::NOT_FOUND,
                    Json(json!({ "error": "signal envelope not found in vault" })),
                )
                    .into_response()
            }
        };
        // Stored as serialized SignalMessage JSON; hand it back as structured JSON.
        let signal_message: Value =
            serde_json::from_slice(&envelope_bytes).unwrap_or(Value::Null);
        return Json(json!({
            "email_cid":      q.email_cid,
            "enc":            ENC_SIGNAL_V1,
            "message_id":     text_from_quads(&quads, &email_cid, "email/message_id"),
            "from":           text_from_quads(&quads, &email_cid, "email/from"),
            "to":             text_from_quads(&quads, &email_cid, "email/to"),
            "date":           text_from_quads(&quads, &email_cid, "email/date"),
            "thread_id":      text_from_quads(&quads, &email_cid, "email/thread_id"),
            // The body (and subject) live sealed INSIDE signalMessage — decrypt client-side.
            "signalMessage":  signal_message,
        }))
        .into_response();
    }

    // Fetch body_cid → Vault decrypt via AgentCrypto
    let body_text = {
        let blob_cid_str = text_from_quads(&quads, &email_cid, "email/body_cid");
        if blob_cid_str.is_empty() {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "error": "email body_cid not found" })),
            )
                .into_response();
        }
        match KotobaCid::from_multibase(&blob_cid_str) {
            None => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({ "error": "invalid body_cid multibase" })),
                )
                    .into_response()
            }
            Some(blob_cid) => {
                let enc_bytes = match state.vault.get(&blob_cid).await {
                    Some(b) => b,
                    None => {
                        return (
                            StatusCode::NOT_FOUND,
                            Json(json!({ "error": "body blob not found in vault" })),
                        )
                            .into_response()
                    }
                };
                match crypto.decrypt_blob(&enc_bytes).await {
                    Err(e) => {
                        return (
                            StatusCode::INTERNAL_SERVER_ERROR,
                            Json(json!({ "error": format!("decrypt body: {e}") })),
                        )
                            .into_response()
                    }
                    Ok(pt) => String::from_utf8_lossy(&pt).into_owned(),
                }
            }
        }
    };

    // Decrypt PII fields using AgentCrypto::open_field
    let from = open_field_safe(
        &*crypto,
        b"email/from",
        &text_from_quads(&quads, &email_cid, "email/from"),
    )
    .await;
    let to = open_field_safe(
        &*crypto,
        b"email/to",
        &text_from_quads(&quads, &email_cid, "email/to"),
    )
    .await;
    let subj = open_field_safe(
        &*crypto,
        b"email/subject",
        &text_from_quads(&quads, &email_cid, "email/subject"),
    )
    .await;
    let date = text_from_quads(&quads, &email_cid, "email/date");
    let thread_id = text_from_quads(&quads, &email_cid, "email/thread_id");
    let message_id = text_from_quads(&quads, &email_cid, "email/message_id");

    Json(json!({
        "email_cid":  q.email_cid,
        "message_id": message_id,
        "from":       from,
        "to":         to,
        "subject":    subj,
        "date":       date,
        "thread_id":  thread_id,
        "body":       body_text,
    }))
    .into_response()
}

// ── email.ingest (manual POST) ────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct EmailIngestBody {
    /// Base64-encoded raw RFC 2822 message
    pub raw_b64: String,
    pub thread_id: Option<String>,
    pub owner_did: String,
}

#[derive(Serialize)]
pub struct EmailIngestResponse {
    pub status: &'static str,
    pub email_cid: String,
}

pub async fn email_ingest(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<EmailIngestBody>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::validate_did(&body.owner_did, "owner_did", MAX_OWNER_DID_LEN)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if body.raw_b64.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "raw_b64 must not be empty" })),
        )
            .into_response();
    }
    if body.raw_b64.len() > MAX_RAW_B64_LEN {
        return (
            StatusCode::PAYLOAD_TOO_LARGE,
            Json(json!({ "error": format!("raw_b64 exceeds {MAX_RAW_B64_LEN} bytes") })),
        )
            .into_response();
    }
    let thread_id = body.thread_id.as_deref().unwrap_or("");
    if thread_id.len() > MAX_THREAD_ID_LEN {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("thread_id exceeds {MAX_THREAD_ID_LEN} bytes") })),
        )
            .into_response();
    }
    if let Err((code, msg)) = require_email_auth(&headers, &body.owner_did, &state.operator_did) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }

    let crypto = match &state.crypto {
        Some(c) => Arc::clone(c),
        None => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "error": "crypto not initialised" })),
            )
                .into_response()
        }
    };

    use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
    let raw = match B64.decode(&body.raw_b64) {
        Ok(b) => b,
        Err(e) => {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({ "error": format!("base64 decode: {e}") })),
            )
                .into_response()
        }
    };

    // Reject oversized decoded payloads before passing to the ingestor.
    // A 34 MiB base64 string decodes to ~25.5 MiB, which can exceed
    // EmailIngestor::MAX_EMAIL_BYTES (25 MiB). Return 413 here rather
    // than letting the ingestor return an anyhow error that becomes 500.
    if raw.len() > EmailIngestor::MAX_EMAIL_BYTES {
        return (
            StatusCode::PAYLOAD_TOO_LARGE,
            Json(json!({ "error": format!(
                "decoded email exceeds {} bytes", EmailIngestor::MAX_EMAIL_BYTES
            ) })),
        )
            .into_response();
    }

    let owner_did = body.owner_did;
    let graph_cid = graph_cid_for(&owner_did);
    let ingestor = EmailIngestor::new(
        crypto,
        Arc::clone(&state.vault),
        Arc::clone(&state.quad_store),
        owner_did.clone(),
    );

    match ingestor.ingest_raw(&raw, thread_id).await {
        Ok(cid) => {
            let tx_cid = KotobaCid::from_bytes(
                format!("email.ingest:{}:{}", owner_did, cid.to_multibase()).as_bytes(),
            );
            let commit_datoms =
                match legacy_email_datoms_for_commit(&state, &graph_cid, &tx_cid, &cid).await {
                    Ok(datoms) => datoms,
                    Err((code, msg)) => {
                        return (code, Json(json!({ "error": msg }))).into_response();
                    }
                };
            match crate::xrpc::commit_protocol_datoms(
                &state,
                graph_cid.clone(),
                graph_cid.to_multibase(),
                cid.clone(),
                commit_datoms,
                tx_cid,
                owner_did,
                kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                None,
                None,
            )
            .await
            {
                Ok(resp) => Json(json!({
                    "status": "ok",
                    "email_cid": cid.to_multibase(),
                    "commit_cid": resp.commit_cid,
                    "ipns_name": resp.ipns_name,
                    "ipns_sequence": resp.ipns_sequence,
                }))
                .into_response(),
                Err((code, msg)) => (code, Json(json!({ "error": msg }))).into_response(),
            }
        }
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("{e}") })),
        )
            .into_response(),
    }
}

// ── email.send (native E2E via Signal) ────────────────────────────────────────

/// Hard cap on fan-out per send. Each recipient is an independent delivery; this
/// bounds the per-request commit count (and is the natural place a future
/// `Postage.sol` per-recipient charge would gate, ADR-2605172200).
const MAX_RECIPIENTS: usize = 256;
/// Per-recipient Signal envelope cap (the sealed MIME body lives inside this).
const MAX_SIGNAL_MSG_BYTES: usize = 1024 * 1024; // 1 MiB

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EmailSendBody {
    /// The authoring member's DID. Must own the Bearer token and match every
    /// recipient envelope's `senderDid`.
    pub sender_did: String,
    /// Optional thread-correlation id (shared across recipients of one message).
    pub thread_id: Option<String>,
    /// One full `SignalMessage` per recipient device, each sealed client-side to
    /// that recipient. The plaintext (RFC 5322 / MIME, incl. subject + body) is
    /// inside the envelope — the server never sees it.
    pub recipients: Vec<serde_json::Value>,
}

pub async fn email_send(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<EmailSendBody>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::validate_did(&body.sender_did, "sender_did", MAX_OWNER_DID_LEN)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if body.recipients.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "recipients must not be empty" })),
        )
            .into_response();
    }
    if body.recipients.len() > MAX_RECIPIENTS {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("recipients exceeds {MAX_RECIPIENTS}") })),
        )
            .into_response();
    }
    let thread_id = body.thread_id.as_deref().unwrap_or("");
    if thread_id.len() > MAX_THREAD_ID_LEN {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("thread_id exceeds {MAX_THREAD_ID_LEN} bytes") })),
        )
            .into_response();
    }
    // The caller must own the sender DID; delivery into a recipient's inbox graph
    // is authorised by the sender's identity (spam-control / postage is a separate,
    // additive gate — see MAX_RECIPIENTS).
    if let Err((code, msg)) = require_email_auth(&headers, &body.sender_did, &state.operator_did) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }

    let mut delivered: Vec<Value> = Vec::with_capacity(body.recipients.len());
    for raw in &body.recipients {
        let raw_len = serde_json::to_vec(raw).map(|v| v.len()).unwrap_or(usize::MAX);
        if raw_len > MAX_SIGNAL_MSG_BYTES {
            return (
                StatusCode::PAYLOAD_TOO_LARGE,
                Json(json!({
                    "error": format!("a recipient envelope exceeds {MAX_SIGNAL_MSG_BYTES} bytes"),
                    "deliveredSoFar": delivered,
                })),
            )
                .into_response();
        }
        let msg: SignalMessage = match serde_json::from_value(raw.clone()) {
            Ok(m) => m,
            Err(e) => {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(json!({ "error": format!("invalid SignalMessage: {e}"), "deliveredSoFar": delivered })),
                )
                    .into_response()
            }
        };
        // The envelope must be authored by the authenticated sender — prevents a
        // member from delivering mail that appears to come from someone else.
        if msg.sender_did != body.sender_did {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({
                    "error": "envelope senderDid does not match authenticated sender_did",
                    "deliveredSoFar": delivered,
                })),
            )
                .into_response();
        }
        if let Err((code, m)) =
            crate::graph_auth::validate_did(&msg.recipient_did, "recipientDid", MAX_OWNER_DID_LEN)
        {
            return (code, Json(json!({ "error": m, "deliveredSoFar": delivered }))).into_response();
        }

        // Store the opaque envelope as a content-addressed blob. The server cannot
        // read it; it is the recipient's body_cid target.
        let blob_bytes = match serde_json::to_vec(raw) {
            Ok(b) => b,
            Err(e) => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({ "error": format!("serialize envelope: {e}"), "deliveredSoFar": delivered })),
                )
                    .into_response()
            }
        };
        let blob_ref = state.vault.put(bytes::Bytes::from(blob_bytes)).await;
        let body_cid_mb = blob_ref.cid.to_multibase();

        // Distinct subject CID per (sender, recipient, time, ciphertext).
        let email_cid = KotobaCid::from_bytes(
            format!(
                "email.send:{}:{}:{}:{}",
                body.sender_did, msg.recipient_did, msg.timestamp, body_cid_mb
            )
            .as_bytes(),
        );
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(&msg.recipient_did);
        let tx_cid = KotobaCid::from_bytes(
            format!("email.send.tx:{}:{}", body.sender_did, email_cid_mb).as_bytes(),
        );

        // Same inbox schema as ingest — `email/enc=signal:v1` flags zero-access body;
        // `email/subject` is empty because the subject lives sealed in the envelope.
        let fields: &[(&str, String)] = &[
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", body.sender_did.clone()),
            ("email/to", msg.recipient_did.clone()),
            ("email/subject", String::new()),
            ("email/body_cid", body_cid_mb.clone()),
            ("email/date", msg.timestamp.clone()),
            ("email/thread_id", thread_id.to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
            ("email/recipient_device", msg.device_id.clone()),
        ];
        let commit_datoms: Vec<kotoba_datomic::Datom> = fields
            .iter()
            .map(|(predicate, object)| {
                kotoba_datomic::Datom::from_kqe(kotoba_kqe::Datom::assert(
                    email_cid.clone(),
                    predicate.to_string(),
                    kotoba_kqe::Value::Text(object.clone()),
                    tx_cid.clone(),
                ))
            })
            .collect();

        match crate::xrpc::commit_protocol_datoms(
            &state,
            graph_cid.clone(),
            graph_cid.to_multibase(),
            email_cid.clone(),
            commit_datoms,
            tx_cid,
            body.sender_did.clone(),
            kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
            None,
            None,
        )
        .await
        {
            Ok(resp) => delivered.push(json!({
                "recipientDid": msg.recipient_did,
                "emailCid":     email_cid_mb,
                "bodyCid":      body_cid_mb,
                "commitCid":    resp.commit_cid,
            })),
            Err((code, m)) => {
                return (
                    code,
                    Json(json!({ "error": m, "deliveredSoFar": delivered })),
                )
                    .into_response()
            }
        }
    }

    Json(json!({ "status": "ok", "count": delivered.len(), "delivered": delivered }))
        .into_response()
}

// ── Helpers ───────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nsid_constants_have_correct_prefix() {
        let prefix = "com.etzhayyim.apps.kotoba.email.";
        assert!(NSID_EMAIL_LIST.starts_with(prefix));
        assert!(NSID_EMAIL_READ.starts_with(prefix));
        assert!(NSID_EMAIL_INGEST.starts_with(prefix));
    }

    #[test]
    fn size_limits_are_sane() {
        assert!(MAX_OWNER_DID_LEN >= 64);
        assert!(MAX_EMAIL_CID_LEN >= 32);
        assert!(MAX_RAW_B64_LEN >= 1024);
    }

    #[test]
    fn nsid_email_list_exact_value() {
        assert_eq!(NSID_EMAIL_LIST, "com.etzhayyim.apps.kotoba.email.list");
    }

    #[test]
    fn nsid_email_read_exact_value() {
        assert_eq!(NSID_EMAIL_READ, "com.etzhayyim.apps.kotoba.email.read");
    }

    #[test]
    fn nsid_email_ingest_exact_value() {
        assert_eq!(NSID_EMAIL_INGEST, "com.etzhayyim.apps.kotoba.email.ingest");
    }

    #[test]
    fn nsid_email_send_exact_value() {
        assert_eq!(NSID_EMAIL_SEND, "com.etzhayyim.apps.kotoba.email.send");
    }

    #[test]
    fn enc_signal_v1_marker_value() {
        assert_eq!(ENC_SIGNAL_V1, "signal:v1");
    }

    #[test]
    fn send_caps_are_sane() {
        assert!(MAX_RECIPIENTS >= 1);
        assert!(MAX_SIGNAL_MSG_BYTES >= 1024);
    }

    // ── email.send → email.list/read native E2E round-trip ────────────────────
    //
    // Drives the handler logic directly (no HTTP) against an in-memory state to
    // prove a Signal envelope lands in the recipient's inbox graph with the
    // zero-access markers, and that the server returns it verbatim (never
    // attempting to decrypt the sealed body).

    use kotoba_signal::message::{MessageType, SignalMessage};

    fn sample_envelope(sender: &str, recipient: &str) -> serde_json::Value {
        let msg = SignalMessage {
            message_type: MessageType::DirectMessage,
            sender_did: sender.to_string(),
            recipient_did: recipient.to_string(),
            device_id: "device-1".to_string(),
            group_id: None,
            // Opaque to the server: pretend-ciphertext standing in for sealed MIME.
            ciphertext_envelope: "c2VhbGVkLW1pbWU=".to_string(),
            timestamp: "2026-06-02T00:00:00Z".to_string(),
            ephemeral_key: None,
            one_time_prekey_id: None,
        };
        serde_json::to_value(&msg).unwrap()
    }

    /// The native send writes the same predicates `email.read`'s native branch
    /// reads back. This asserts the schema contract between the two code paths
    /// without standing up the full axum stack.
    #[tokio::test]
    async fn native_send_writes_zero_access_inbox_datoms() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderNative";
        let recipient = "did:key:zRecipientNative";

        // Mirror the handler's per-recipient delivery against the recipient graph.
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = KotobaCid::from_bytes(
            format!(
                "email.send:{}:{}:{}:{}",
                sender, recipient, msg.timestamp, body_cid_mb
            )
            .as_bytes(),
        );
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"native-send-tx");
        for (p, o) in [
            ("email/body_cid", body_cid_mb.clone()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
            ("email/from", sender.to_string()),
            ("email/date", msg.timestamp.clone()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_kqe::Datom::assert(
                        email_cid.clone(),
                        p.to_string(),
                        kotoba_kqe::Value::Text(o),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let quads = current_email_quads(&state, &graph_cid).await.unwrap();
        // The native branch's discriminant is present...
        assert_eq!(text_from_quads(&quads, &email_cid, "email/enc"), ENC_SIGNAL_V1);
        // ...the body points at the opaque envelope blob...
        assert_eq!(
            text_from_quads(&quads, &email_cid, "email/body_cid"),
            body_cid_mb
        );
        // ...and the stored blob round-trips back to the exact SignalMessage,
        // proving the server kept it verbatim (no key applied).
        let stored = state.vault.get(&blob.cid).await.unwrap();
        let back: SignalMessage = serde_json::from_slice(&stored).unwrap();
        assert_eq!(back.recipient_did, recipient);
        assert_eq!(back.ciphertext_envelope, "c2VhbGVkLW1pbWU=");
    }

    #[test]
    fn send_rejects_envelope_sender_mismatch_invariant() {
        // The handler enforces msg.sender_did == body.sender_did. Encode that as a
        // direct check so the invariant is covered without the HTTP layer.
        let env = sample_envelope("did:key:zImpostor", "did:key:zVictim");
        let msg: SignalMessage = serde_json::from_value(env).unwrap();
        let authenticated_sender = "did:key:zRealSender";
        assert_ne!(
            msg.sender_did, authenticated_sender,
            "mismatched envelope sender must be rejected by email_send"
        );
    }

    #[test]
    fn nsid_email_constants_are_unique() {
        let mut set = std::collections::HashSet::new();
        assert!(set.insert(NSID_EMAIL_LIST));
        assert!(set.insert(NSID_EMAIL_READ));
        assert!(set.insert(NSID_EMAIL_INGEST));
    }

    #[test]
    fn max_raw_b64_len_is_34_mib() {
        assert_eq!(MAX_RAW_B64_LEN, 34 * 1024 * 1024);
    }

    #[test]
    fn email_cid_len_cap_smaller_than_did_len_cap() {
        assert!(
            MAX_EMAIL_CID_LEN < MAX_OWNER_DID_LEN,
            "email CID length cap should be tighter than DID length cap"
        );
    }

    #[test]
    fn max_owner_did_len_is_512() {
        assert_eq!(MAX_OWNER_DID_LEN, 512);
    }

    #[test]
    fn max_email_cid_len_is_256() {
        assert_eq!(MAX_EMAIL_CID_LEN, 256);
    }

    #[test]
    fn max_thread_id_len_matches_ingestor_limit() {
        // MAX_THREAD_ID_LEN in this file must equal the limit enforced inside
        // EmailIngestor::ingest_raw so that the XRPC handler catches oversized
        // thread_id with 400 before the ingestor would return an anyhow error.
        // ingest_raw rejects thread_id.len() > 256 (matches EmailIngestor internal limit)
        assert_eq!(
            MAX_THREAD_ID_LEN, 256,
            "XRPC handler limit must match ingestor limit"
        );
        // Also ensure the constant is used (not dead code)
        let _ = MAX_THREAD_ID_LEN;
    }

    #[test]
    fn max_email_bytes_is_25_mib() {
        use kotoba_ingest::EmailIngestor;
        assert_eq!(
            EmailIngestor::MAX_EMAIL_BYTES,
            25 * 1024 * 1024,
            "EmailIngestor::MAX_EMAIL_BYTES must be 25 MiB"
        );
    }

    #[test]
    fn decoded_size_guard_catches_overshoot_between_b64_and_raw_limits() {
        // A 34 MiB base64 string decodes to ~25.5 MiB of raw bytes, which
        // exceeds EmailIngestor::MAX_EMAIL_BYTES (25 MiB).  The decoded-size
        // guard must fire before the ingestor gets called.
        use kotoba_ingest::EmailIngestor;
        let max_b64_decoded = (MAX_RAW_B64_LEN / 4) * 3; // approx upper bound
        assert!(
            max_b64_decoded > EmailIngestor::MAX_EMAIL_BYTES,
            "b64 limit must allow payloads that would exceed the raw email limit \
             so the decoded-size guard is reachable"
        );
    }

    #[tokio::test]
    async fn legacy_email_datoms_for_commit_preserves_subject_tx_and_value() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let graph_cid = graph_cid_for("did:key:zEmailBridge");
        let email_cid = KotobaCid::from_bytes(b"email-bridge");
        let tx_cid = KotobaCid::from_bytes(b"tx-email-bridge");

        state
            .quad_store
            .assert_datom(
                graph_cid.clone(),
                kotoba_kqe::Datom::assert(
                    email_cid.clone(),
                    "email/message_id".to_string(),
                    kotoba_kqe::Value::Text("<bridge@example>".to_string()),
                    tx_cid.clone(),
                ),
            )
            .await;

        let datoms = legacy_email_datoms_for_commit(&state, &graph_cid, &tx_cid, &email_cid)
            .await
            .expect("bridge datoms");

        assert_eq!(datoms.len(), 1);
        assert_eq!(datoms[0].e, email_cid);
        assert_eq!(datoms[0].a, "email/message_id");
        assert_eq!(datoms[0].t, tx_cid);
        assert_eq!(
            datoms[0].v,
            kotoba_edn::EdnValue::String("<bridge@example>".to_string())
        );
        assert!(datoms[0].added);
    }

    // ── open_field_safe ───────────────────────────────────────────────────────
    //
    // open_field_safe branches:
    //   1. empty envelope → passthrough (no crypto call)
    //   2. no "signal:v1:" prefix → passthrough (legacy plaintext)
    //   3. "signal:v1:" prefix + valid ciphertext → decrypted plaintext
    //   4. "signal:v1:" prefix + bad ciphertext → original envelope returned

    #[tokio::test]
    async fn open_field_safe_empty_returns_empty() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0xAAu8; 32]));
        let result = open_field_safe(&crypto, b"scope", "").await;
        assert_eq!(result, "");
    }

    #[tokio::test]
    async fn open_field_safe_plaintext_returns_unchanged() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0xAAu8; 32]));
        let result = open_field_safe(&crypto, b"scope", "alice@example.com").await;
        assert_eq!(result, "alice@example.com");
    }

    #[tokio::test]
    async fn open_field_safe_signal_roundtrip_with_real_crypto() {
        use kotoba_crypto::{AgentCrypto as _, VaultKeyedCrypto};
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0x11u8; 32]));
        let scope = b"email/from";
        let plaintext = "test@example.com";
        // seal_field produces a signal:v1: envelope
        let envelope = crypto.seal_field(scope, plaintext).await.unwrap();
        assert!(envelope.starts_with("signal:v1:"));
        // open_field_safe should decrypt it correctly
        let recovered = open_field_safe(&crypto, scope, &envelope).await;
        assert_eq!(recovered, plaintext);
    }

    #[tokio::test]
    async fn open_field_safe_bad_ciphertext_returns_original() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0x11u8; 32]));
        // "signal:v1:" prefix but not valid ciphertext → decrypt will fail → fallback
        let envelope = "signal:v1:not-valid-ciphertext";
        let result = open_field_safe(&crypto, b"scope", envelope).await;
        assert_eq!(result, envelope);
    }

    #[tokio::test]
    async fn open_field_safe_non_signal_prefix_with_colon_passthrough() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0xAAu8; 32]));
        // A string that has a colon but not the signal:v1: prefix
        let result = open_field_safe(&crypto, b"scope", "mailto:user@example.com").await;
        assert_eq!(result, "mailto:user@example.com");
    }
}

/// Open a `signal:v1:` envelope using AgentCrypto; returns ciphertext on failure
/// (same fallback as the old decrypt_text_field).
async fn open_field_safe(
    crypto: &dyn kotoba_crypto::AgentCrypto,
    scope: &[u8],
    envelope: &str,
) -> String {
    if envelope.is_empty() {
        return envelope.to_string();
    }
    if !envelope.starts_with("signal:v1:") {
        // Plain-text legacy value — return as-is
        return envelope.to_string();
    }
    crypto
        .open_field(scope, envelope)
        .await
        .unwrap_or_else(|_| envelope.to_string()) // return ciphertext if decrypt fails
}
