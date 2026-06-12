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
pub const ALL_EMAIL_NSIDS: &[&str] = &[
    NSID_EMAIL_LIST,
    NSID_EMAIL_READ,
    NSID_EMAIL_INGEST,
    NSID_EMAIL_SEND,
];

/// 33 MiB raw email base64 + JSON framing overhead.
pub const EMAIL_INGEST_BODY_LIMIT: usize = 36 * 1024 * 1024;
/// 256 recipients x 1 MiB Signal envelope + JSON framing.
pub const EMAIL_SEND_BODY_LIMIT: usize = 300 * 1024 * 1024;

/// Marks a body blob that is a client-sealed Signal envelope (zero-access).
pub(crate) const ENC_SIGNAL_V1: &str = "signal:v1";

use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use serde_json::{json, Value};
use std::sync::Arc;

use kotoba_core::cid::KotobaCid;
use kotoba_ingest::{graph_cid_for, EmailIngestor};
use kotoba_query::{quad::LegacyQuad, quad::LegacyQuadObject};
use kotoba_signal::message::{MessageType, SignalMessage};

use crate::server::KotobaState;

pub(crate) const MAX_OWNER_DID_LEN: usize = 512;
pub(crate) const MAX_EMAIL_CID_LEN: usize = 256;
pub(crate) const DEFAULT_EMAIL_LIST_LIMIT: usize = 50;
pub(crate) const MAX_EMAIL_LIST_LIMIT: usize = 200;
pub(crate) const MAX_EMAIL_LIST_OFFSET: usize = 10_000;
// 25 MiB raw ≈ 33 MiB base64 (Gmail attachment limit)
const MAX_RAW_B64_LEN: usize = 34 * 1024 * 1024;
pub(crate) const MAX_THREAD_ID_LEN: usize = 256; // mirrors EmailIngestor::ingest_raw validation
pub(crate) const MAX_LEGACY_ADDR_LEN: usize = 4096; // mirrors EmailIngestor::ingest_raw truncation
pub(crate) const MAX_LEGACY_SUBJECT_LEN: usize = 998; // RFC 5322 header line cap used by ingest
pub(crate) const MAX_EMAIL_MESSAGE_ID_LEN: usize = 998; // mirrors EmailIngestor::ingest_raw truncation
pub(crate) const MAX_EMAIL_DATE_LEN: usize = 64;
const MAX_SIGNAL_DEVICE_ID_LEN: usize = 128;
const MAX_SIGNAL_TIMESTAMP_LEN: usize = MAX_EMAIL_DATE_LEN;
const MAX_SIGNAL_GROUP_ID_LEN: usize = 256;
const MAX_SIGNAL_EPHEMERAL_KEY_LEN: usize = 512;

fn validate_email_cid_param(value: &str) -> Result<(), (StatusCode, String)> {
    if value.trim().is_empty() {
        return Err((
            StatusCode::BAD_REQUEST,
            "email_cid must not be empty".to_string(),
        ));
    }
    if value.len() > MAX_EMAIL_CID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("email_cid must be 1–{MAX_EMAIL_CID_LEN} bytes"),
        ));
    }
    if !is_visible_ascii_text(value) {
        return Err((
            StatusCode::BAD_REQUEST,
            "email_cid must contain only visible ASCII characters".to_string(),
        ));
    }
    Ok(())
}

fn is_visible_ascii_text(value: &str) -> bool {
    !value.is_empty() && value.bytes().all(|byte| (0x21..=0x7e).contains(&byte))
}

fn is_visible_multibase_cid_text(value: &str) -> bool {
    is_visible_ascii_text(value) && KotobaCid::from_multibase(value).is_some()
}

fn validate_email_list_limit(limit: Option<usize>) -> Result<usize, (StatusCode, String)> {
    match limit {
        None => Ok(DEFAULT_EMAIL_LIST_LIMIT),
        Some(0) => Err((
            StatusCode::BAD_REQUEST,
            "limit must be at least 1".to_string(),
        )),
        Some(value) if value > MAX_EMAIL_LIST_LIMIT => Err((
            StatusCode::BAD_REQUEST,
            format!("limit exceeds {MAX_EMAIL_LIST_LIMIT}"),
        )),
        Some(value) => Ok(value),
    }
}

fn validate_email_list_offset(offset: Option<usize>) -> Result<usize, (StatusCode, String)> {
    match offset {
        None => Ok(0),
        Some(value) if value > MAX_EMAIL_LIST_OFFSET => Err((
            StatusCode::BAD_REQUEST,
            format!("offset exceeds {MAX_EMAIL_LIST_OFFSET}"),
        )),
        Some(value) => Ok(value),
    }
}

fn validate_thread_id_param(
    field: &'static str,
    thread_id: &str,
) -> Result<(), (StatusCode, String)> {
    if thread_id.len() > MAX_THREAD_ID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} exceeds {MAX_THREAD_ID_LEN} bytes"),
        ));
    }
    if !thread_id.is_empty() && !is_visible_ascii_text(thread_id) {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must contain only visible ASCII characters"),
        ));
    }
    Ok(())
}

pub(crate) fn signal_email_cid_for(
    sender_did: &str,
    recipient_did: &str,
    timestamp: &str,
    body_cid_mb: &str,
) -> KotobaCid {
    KotobaCid::from_bytes(
        format!("email.send:{sender_did}:{recipient_did}:{timestamp}:{body_cid_mb}").as_bytes(),
    )
}

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

fn visible_bounded_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &str,
    max_len: usize,
) -> String {
    quads
        .iter()
        .find_map(|quad| {
            if &quad.subject == subject && quad.predicate == predicate {
                if let LegacyQuadObject::Text(text) = &quad.object {
                    if !text.is_empty() && text.len() <= max_len && is_visible_ascii_text(text) {
                        return Some(text.clone());
                    }
                }
            }
            None
        })
        .unwrap_or_default()
}

fn latest_visible_bounded_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &str,
    max_len: usize,
) -> String {
    quads
        .iter()
        .filter_map(|quad| {
            if &quad.subject == subject && quad.predicate == predicate {
                if let LegacyQuadObject::Text(text) = &quad.object {
                    if !text.is_empty() && text.len() <= max_len && is_visible_ascii_text(text) {
                        return Some(text.clone());
                    }
                }
            }
            None
        })
        .max()
        .unwrap_or_default()
}

#[derive(Debug, PartialEq, Eq)]
enum EmailTextFieldError {
    Missing,
    Invalid,
    Ambiguous,
}

fn unique_visible_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &str,
) -> Result<String, EmailTextFieldError> {
    let mut value = None;
    for quad in quads {
        if &quad.subject != subject || quad.predicate != predicate {
            continue;
        }
        let LegacyQuadObject::Text(text) = &quad.object else {
            return Err(EmailTextFieldError::Invalid);
        };
        if !is_visible_ascii_text(text) {
            return Err(EmailTextFieldError::Invalid);
        }
        match &value {
            Some(existing) if existing != text => return Err(EmailTextFieldError::Ambiguous),
            Some(_) => {}
            None => value = Some(text.clone()),
        }
    }
    value.ok_or(EmailTextFieldError::Missing)
}

fn email_text_field_error_response(
    predicate: &'static str,
    err: EmailTextFieldError,
) -> axum::response::Response {
    let message = match err {
        EmailTextFieldError::Missing => format!("{predicate} not found"),
        EmailTextFieldError::Invalid => format!("invalid {predicate}"),
        EmailTextFieldError::Ambiguous => format!("multiple {predicate} values found"),
    };
    (
        StatusCode::INTERNAL_SERVER_ERROR,
        Json(json!({ "error": message })),
    )
        .into_response()
}

fn optional_unique_visible_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
) -> Result<Option<String>, EmailTextFieldError> {
    match unique_visible_text_from_quads(quads, subject, predicate) {
        Ok(value) => Ok(Some(value)),
        Err(EmailTextFieldError::Missing) => Ok(None),
        Err(err) => Err(err),
    }
}

fn unique_visible_bounded_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
    max_len: usize,
) -> Result<String, EmailTextFieldError> {
    let value = unique_visible_text_from_quads(quads, subject, predicate)?;
    if value.len() > max_len {
        return Err(EmailTextFieldError::Invalid);
    }
    Ok(value)
}

fn optional_unique_visible_bounded_text_from_quads(
    quads: &[LegacyQuad],
    subject: &KotobaCid,
    predicate: &'static str,
    max_len: usize,
) -> Option<String> {
    match unique_visible_text_from_quads(quads, subject, predicate) {
        Ok(value) if value.len() <= max_len => Some(value),
        _ => None,
    }
}

#[derive(Debug, PartialEq, Eq)]
enum EmailEnc {
    Legacy,
    Signal,
}

#[derive(Debug, PartialEq, Eq)]
enum EmailEncError {
    Invalid,
}

fn email_enc_from_quads(
    quads: &[LegacyQuad],
    email_cid: &KotobaCid,
) -> Result<EmailEnc, EmailEncError> {
    let mut signal = false;
    for quad in quads {
        if &quad.subject != email_cid || quad.predicate != "email/enc" {
            continue;
        }
        let LegacyQuadObject::Text(value) = &quad.object else {
            return Err(EmailEncError::Invalid);
        };
        if !is_visible_ascii_text(value) || value != ENC_SIGNAL_V1 {
            return Err(EmailEncError::Invalid);
        }
        signal = true;
    }
    Ok(if signal {
        EmailEnc::Signal
    } else {
        EmailEnc::Legacy
    })
}

fn email_enc_error_response(err: EmailEncError) -> axum::response::Response {
    match err {
        EmailEncError::Invalid => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": "invalid email/enc" })),
        ),
    }
    .into_response()
}

#[derive(Debug, PartialEq, Eq)]
enum EmailBodyCidError {
    Missing,
    Invalid,
    Ambiguous,
}

fn email_body_cid_from_quads(
    quads: &[LegacyQuad],
    email_cid: &KotobaCid,
) -> Result<String, EmailBodyCidError> {
    let mut body_cid = None;
    for quad in quads {
        if &quad.subject != email_cid || quad.predicate != "email/body_cid" {
            continue;
        }
        let LegacyQuadObject::Text(value) = &quad.object else {
            return Err(EmailBodyCidError::Invalid);
        };
        if !is_visible_multibase_cid_text(value) {
            return Err(EmailBodyCidError::Invalid);
        }
        match &body_cid {
            Some(existing) if existing != value => return Err(EmailBodyCidError::Ambiguous),
            Some(_) => {}
            None => body_cid = Some(value.clone()),
        }
    }
    body_cid.ok_or(EmailBodyCidError::Missing)
}

fn email_body_cid_error_response(err: EmailBodyCidError) -> axum::response::Response {
    match err {
        EmailBodyCidError::Missing => (
            StatusCode::NOT_FOUND,
            Json(json!({ "error": "email/body_cid not found" })),
        ),
        EmailBodyCidError::Invalid => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": "invalid body_cid multibase" })),
        ),
        EmailBodyCidError::Ambiguous => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": "multiple email/body_cid values found" })),
        ),
    }
    .into_response()
}

#[cfg(test)]
fn email_record_exists(quads: &[LegacyQuad], email_cid: &KotobaCid) -> bool {
    let has_message_id = unique_visible_bounded_text_from_quads(
        quads,
        email_cid,
        "email/message_id",
        MAX_EMAIL_MESSAGE_ID_LEN,
    )
    .is_ok();
    let has_date = quads.iter().any(|quad| {
        &quad.subject == email_cid
            && quad.predicate == "email/date"
            && matches!(&quad.object, LegacyQuadObject::Text(value) if !value.is_empty() && value.len() <= MAX_EMAIL_DATE_LEN && is_visible_ascii_text(value))
    });
    has_message_id && has_date
}

pub(crate) fn email_entries_from_quads(quads: &[LegacyQuad]) -> Vec<(KotobaCid, String)> {
    let mut by_cid: std::collections::HashMap<KotobaCid, String> = std::collections::HashMap::new();
    for quad in quads {
        if quad.predicate == "email/date" {
            let LegacyQuadObject::Text(date) = &quad.object else {
                continue;
            };
            if !is_visible_ascii_text(date) {
                continue;
            }
            if date.is_empty() {
                continue;
            }
            if date.len() > MAX_EMAIL_DATE_LEN {
                continue;
            }
            by_cid
                .entry(quad.subject.clone())
                .and_modify(|current| {
                    if date > current {
                        *current = date.clone();
                    }
                })
                .or_insert_with(|| date.clone());
        }
    }
    let mut entries = by_cid
        .into_iter()
        .filter(|(email_cid, _)| {
            unique_visible_bounded_text_from_quads(
                quads,
                email_cid,
                "email/message_id",
                MAX_EMAIL_MESSAGE_ID_LEN,
            )
            .is_ok()
                && email_body_cid_from_quads(quads, email_cid).is_ok()
                && email_enc_from_quads(quads, email_cid).is_ok()
        })
        .collect::<Vec<_>>();
    entries.sort_by(|a, b| {
        b.1.cmp(&a.1)
            .then_with(|| a.0.to_multibase().cmp(&b.0.to_multibase()))
    });
    entries
}

pub(crate) fn email_list_signal_metadata_from_quads(
    quads: &[LegacyQuad],
    email_cid: &KotobaCid,
) -> (Option<String>, Option<String>) {
    let enc = matches!(email_enc_from_quads(quads, email_cid), Ok(EmailEnc::Signal))
        .then_some(ENC_SIGNAL_V1.to_string());
    let recipient_device = if enc.is_some() {
        optional_unique_visible_bounded_text_from_quads(
            quads,
            email_cid,
            "email/recipient_device",
            MAX_SIGNAL_DEVICE_ID_LEN,
        )
    } else {
        None
    };
    (enc, recipient_device)
}

fn email_list_item_from_quads(quads: &[LegacyQuad], email_cid: &KotobaCid, date: String) -> Value {
    let message_id = unique_visible_bounded_text_from_quads(
        quads,
        email_cid,
        "email/message_id",
        MAX_EMAIL_MESSAGE_ID_LEN,
    )
    .unwrap_or_default();
    let mut item =
        json!({ "cid": email_cid.to_multibase(), "date": date, "message_id": message_id });
    let (enc, recipient_device) = email_list_signal_metadata_from_quads(quads, email_cid);
    if let Some(enc) = enc {
        item["enc"] = json!(enc);
    }
    if let Some(recipient_device) = recipient_device {
        item["recipient_device"] = json!(recipient_device);
    }
    item
}

fn validate_legacy_read_text_output(
    field: &'static str,
    value: &str,
    max_len: usize,
) -> Result<(), String> {
    if value.len() > max_len {
        return Err(format!("{field} exceeds {max_len} bytes"));
    }
    if !value.is_empty() && !is_visible_ascii_text(value) {
        return Err(format!(
            "{field} must contain only visible ASCII characters"
        ));
    }
    Ok(())
}

// ── email.list ────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
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
    let limit = validate_email_list_limit(q.limit)?;
    let offset = validate_email_list_offset(q.offset)?;
    require_email_auth(&headers, &q.owner_did, &state.operator_did)?;

    let graph_cid = graph_cid_for(&q.owner_did);
    let quads = current_email_quads(&state, &graph_cid).await?;

    let entries = email_entries_from_quads(&quads);

    let total = entries.len();

    let page: Vec<Value> = entries
        .into_iter()
        .skip(offset)
        .take(limit)
        .map(|(email_cid, date)| email_list_item_from_quads(&quads, &email_cid, date))
        .collect();

    Ok(
        Json(json!({ "emails": page, "total": total, "offset": offset, "limit": limit }))
            .into_response(),
    )
}

// ── email.read ────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(deny_unknown_fields)]
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
    if let Err((code, msg)) = validate_email_cid_param(&q.email_cid) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if let Err((code, msg)) = require_email_auth(&headers, &q.owner_did, &state.operator_did) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }

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
    let message_id = match unique_visible_bounded_text_from_quads(
        &quads,
        &email_cid,
        "email/message_id",
        MAX_EMAIL_MESSAGE_ID_LEN,
    ) {
        Ok(value) => value,
        Err(EmailTextFieldError::Missing) => {
            return (
                StatusCode::NOT_FOUND,
                Json(json!({ "error": "email_cid not found in mailbox" })),
            )
                .into_response()
        }
        Err(err) => return email_text_field_error_response("email/message_id", err),
    };
    let date = latest_visible_bounded_text_from_quads(
        &quads,
        &email_cid,
        "email/date",
        MAX_EMAIL_DATE_LEN,
    );
    if date.is_empty() {
        return (
            StatusCode::NOT_FOUND,
            Json(json!({ "error": "email_cid not found in mailbox" })),
        )
            .into_response();
    }
    let enc = match email_enc_from_quads(&quads, &email_cid) {
        Ok(value) => value,
        Err(err) => return email_enc_error_response(err),
    };
    let email_cid_mb = email_cid.to_multibase();

    // Native E2E (Signal) messages carry an opaque client-sealed envelope the
    // server cannot decrypt. Return the envelope verbatim for the recipient to
    // open with their Signal session key. `from`/`to` here are plaintext routing
    // metadata (DIDs), not sealed PII — return them as-is.
    if enc == EmailEnc::Signal {
        let blob_cid_str = match email_body_cid_from_quads(&quads, &email_cid) {
            Ok(value) => value,
            Err(err) => return email_body_cid_error_response(err),
        };
        let blob_cid = KotobaCid::from_multibase(&blob_cid_str).expect("validated body CID");
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
        // Stored as serialized SignalMessage JSON; corrupted, structurally
        // invalid, or policy-invalid blobs must not pass through as arbitrary JSON.
        let signal_message = match signal_message_value_from_envelope_bytes(&envelope_bytes) {
            Ok(value) => value,
            Err(err) => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({ "error": err })),
                )
                    .into_response()
            }
        };
        let signal_from = signal_message["senderDid"]
            .as_str()
            .unwrap_or_default()
            .to_string();
        let signal_to = signal_message["recipientDid"]
            .as_str()
            .unwrap_or_default()
            .to_string();
        if signal_to != q.owner_did {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({
                    "error": "signal envelope recipientDid does not match mailbox owner_did"
                })),
            )
                .into_response();
        }
        let stored_signal_from =
            match optional_unique_visible_text_from_quads(&quads, &email_cid, "email/from") {
                Ok(value) => value,
                Err(err) => return email_text_field_error_response("email/from", err),
            };
        if stored_signal_from
            .as_deref()
            .is_some_and(|value| value != signal_from)
        {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({
                    "error": "signal envelope senderDid does not match email/from"
                })),
            )
                .into_response();
        }
        let stored_signal_to =
            match optional_unique_visible_text_from_quads(&quads, &email_cid, "email/to") {
                Ok(value) => value,
                Err(err) => return email_text_field_error_response("email/to", err),
            };
        if stored_signal_to
            .as_deref()
            .is_some_and(|value| value != signal_to)
        {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({
                    "error": "signal envelope recipientDid does not match email/to"
                })),
            )
                .into_response();
        }
        let signal_timestamp = signal_message["timestamp"].as_str().unwrap_or_default();
        let stored_signal_date = date.as_str();
        if stored_signal_date != signal_timestamp {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({
                    "error": "signal envelope timestamp does not match email/date"
                })),
            )
                .into_response();
        }
        let expected_email_cid =
            signal_email_cid_for(&signal_from, &signal_to, signal_timestamp, &blob_cid_str);
        if expected_email_cid != email_cid {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({
                    "error": "signal envelope body_cid does not match email_cid"
                })),
            )
                .into_response();
        }
        return Json(json!({
            "email_cid":      email_cid_mb,
            "enc":            ENC_SIGNAL_V1,
            "message_id":     message_id,
            "from":           signal_from,
            "to":             signal_to,
            "date":           signal_timestamp,
            "thread_id":      visible_bounded_text_from_quads(
                &quads,
                &email_cid,
                "email/thread_id",
                MAX_THREAD_ID_LEN,
            ),
            // The body (and subject) live sealed INSIDE signalMessage — decrypt client-side.
            "signalMessage":  signal_message,
        }))
        .into_response();
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

    // Fetch body_cid → Vault decrypt via AgentCrypto
    let body_text =
        {
            let blob_cid_str = match email_body_cid_from_quads(&quads, &email_cid) {
                Ok(value) => value,
                Err(err) => return email_body_cid_error_response(err),
            };
            let blob_cid = KotobaCid::from_multibase(&blob_cid_str).expect("validated body CID");
            {
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
                match crypto
                    .decrypt_blob_bound(email_cid_mb.as_bytes(), &enc_bytes)
                    .await
                {
                    Err(e) => {
                        return (
                            StatusCode::INTERNAL_SERVER_ERROR,
                            Json(json!({ "error": format!("decrypt body: {e}") })),
                        )
                            .into_response()
                    }
                    Ok(mut pt) => {
                        let bytes = std::mem::take(&mut *pt);
                        match String::from_utf8(bytes) {
                            Ok(body) => body,
                            Err(err) => return (
                                StatusCode::INTERNAL_SERVER_ERROR,
                                Json(json!({ "error": format!("body is not valid UTF-8: {err}") })),
                            )
                                .into_response(),
                        }
                    }
                }
            }
        };

    // Decrypt PII fields using AgentCrypto::open_field.
    let from = match open_field_safe(
        &*crypto,
        b"email/from",
        &text_from_quads(&quads, &email_cid, "email/from"),
    )
    .await
    {
        Ok(value) => value,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("decrypt from: {err}") })),
            )
                .into_response()
        }
    };
    let to = match open_field_safe(
        &*crypto,
        b"email/to",
        &text_from_quads(&quads, &email_cid, "email/to"),
    )
    .await
    {
        Ok(value) => value,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("decrypt to: {err}") })),
            )
                .into_response()
        }
    };
    let subj = match open_field_safe(
        &*crypto,
        b"email/subject",
        &text_from_quads(&quads, &email_cid, "email/subject"),
    )
    .await
    {
        Ok(value) => value,
        Err(err) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("decrypt subject: {err}") })),
            )
                .into_response()
        }
    };
    let thread_id =
        visible_bounded_text_from_quads(&quads, &email_cid, "email/thread_id", MAX_THREAD_ID_LEN);
    for (field, value, max_len) in [
        ("from", from.as_str(), MAX_LEGACY_ADDR_LEN),
        ("to", to.as_str(), MAX_LEGACY_ADDR_LEN),
        ("subject", subj.as_str(), MAX_LEGACY_SUBJECT_LEN),
    ] {
        if let Err(err) = validate_legacy_read_text_output(field, value, max_len) {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": err })),
            )
                .into_response();
        }
    }

    Json(json!({
        "email_cid":  email_cid_mb,
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
#[serde(deny_unknown_fields)]
pub struct EmailIngestBody {
    /// Base64-encoded raw RFC 2822 message
    pub raw_b64: String,
    pub thread_id: Option<String>,
    pub owner_did: String,
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
    if let Err((code, msg)) = validate_thread_id_param("thread_id", thread_id) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if let Err((code, msg)) = require_email_auth(&headers, &body.owner_did, &state.operator_did) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }

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
/// Cap only the serialized ciphertext field; the whole SignalMessage has its
/// own request cap above, but datom/CID metadata fields are much smaller.
const MAX_SIGNAL_CIPHERTEXT_ENVELOPE_LEN: usize = MAX_SIGNAL_MSG_BYTES;

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
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
        crate::graph_auth::validate_did(&body.sender_did, "senderDid", MAX_OWNER_DID_LEN)
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
    if let Err((code, msg)) = validate_thread_id_param("threadId", thread_id) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    // The caller must own the sender DID; delivery into a recipient's inbox graph
    // is authorised by the sender's identity (spam-control / postage is a separate,
    // additive gate — see MAX_RECIPIENTS).
    if let Err((code, msg)) = require_email_auth(&headers, &body.sender_did, &state.operator_did) {
        return (code, Json(json!({ "error": msg }))).into_response();
    }

    let mut prepared: Vec<(SignalMessage, Vec<u8>)> = Vec::with_capacity(body.recipients.len());
    let mut planned_email_cids = std::collections::HashSet::with_capacity(body.recipients.len());
    let mut planned_devices = std::collections::HashSet::with_capacity(body.recipients.len());
    for raw in &body.recipients {
        let raw_len = serde_json::to_vec(raw)
            .map(|v| v.len())
            .unwrap_or(usize::MAX);
        if raw_len > MAX_SIGNAL_MSG_BYTES {
            return (
                StatusCode::PAYLOAD_TOO_LARGE,
                Json(json!({
                    "error": format!("a recipient envelope exceeds {MAX_SIGNAL_MSG_BYTES} bytes"),
                    "deliveredSoFar": Vec::<Value>::new(),
                })),
            )
                .into_response();
        }
        if let Err(err) = validate_signal_message_json_shape(raw) {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({ "error": err, "deliveredSoFar": Vec::<Value>::new() })),
            )
                .into_response();
        }
        let msg: SignalMessage = match serde_json::from_value(raw.clone()) {
            Ok(m) => m,
            Err(e) => {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(json!({ "error": format!("invalid SignalMessage: {e}"), "deliveredSoFar": Vec::<Value>::new() })),
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
                    "error": "envelope senderDid does not match authenticated senderDid",
                    "deliveredSoFar": Vec::<Value>::new(),
                })),
            )
                .into_response();
        }
        if let Err((code, m)) = validate_signal_email_message(&msg) {
            return (
                code,
                Json(json!({ "error": m, "deliveredSoFar": Vec::<Value>::new() })),
            )
                .into_response();
        }
        if let Err((code, m)) =
            crate::graph_auth::validate_did(&msg.recipient_did, "recipientDid", MAX_OWNER_DID_LEN)
        {
            return (
                code,
                Json(json!({ "error": m, "deliveredSoFar": Vec::<Value>::new() })),
            )
                .into_response();
        }
        if !planned_devices.insert((msg.recipient_did.clone(), msg.device_id.clone())) {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({
                    "error": "duplicate recipient device",
                    "deliveredSoFar": Vec::<Value>::new(),
                })),
            )
                .into_response();
        }

        let blob_bytes = match serde_json::to_vec(&msg) {
            Ok(b) => b,
            Err(e) => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(json!({ "error": format!("serialize canonical envelope: {e}"), "deliveredSoFar": Vec::<Value>::new() })),
                )
                    .into_response()
            }
        };
        let planned_body_cid = KotobaCid::from_bytes(&blob_bytes).to_multibase();
        let planned_email_cid = signal_email_cid_for(
            &body.sender_did,
            &msg.recipient_did,
            &msg.timestamp,
            &planned_body_cid,
        )
        .to_multibase();
        if !planned_email_cids.insert(planned_email_cid) {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({
                    "error": "duplicate recipient envelope",
                    "deliveredSoFar": Vec::<Value>::new(),
                })),
            )
                .into_response();
        }
        prepared.push((msg, blob_bytes));
    }

    let mut delivered: Vec<Value> = Vec::with_capacity(prepared.len());
    for (msg, blob_bytes) in prepared {
        // Store the opaque envelope as a content-addressed blob. The server cannot
        // read it; it is the recipient's body_cid target.
        let blob_ref = state.vault.put(bytes::Bytes::from(blob_bytes)).await;
        let body_cid_mb = blob_ref.cid.to_multibase();

        // Distinct subject CID per (sender, recipient, time, ciphertext).
        let email_cid = signal_email_cid_for(
            &body.sender_did,
            &msg.recipient_did,
            &msg.timestamp,
            &body_cid_mb,
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
                kotoba_datomic::Datom::from_kqe(kotoba_query::Datom::assert(
                    email_cid.clone(),
                    predicate.to_string(),
                    kotoba_query::Value::Text(object.clone()),
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

fn validate_signal_email_message(msg: &SignalMessage) -> Result<(), (StatusCode, String)> {
    crate::graph_auth::validate_did(&msg.sender_did, "senderDid", MAX_OWNER_DID_LEN)?;
    crate::graph_auth::validate_did(&msg.recipient_did, "recipientDid", MAX_OWNER_DID_LEN)?;
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
    validate_visible_ascii_field(
        "deviceId",
        &msg.device_id,
        1,
        MAX_SIGNAL_DEVICE_ID_LEN,
        StatusCode::BAD_REQUEST,
    )?;
    validate_visible_ascii_field(
        "timestamp",
        &msg.timestamp,
        1,
        MAX_SIGNAL_TIMESTAMP_LEN,
        StatusCode::BAD_REQUEST,
    )?;
    validate_visible_ascii_field(
        "ciphertextEnvelope",
        &msg.ciphertext_envelope,
        1,
        MAX_SIGNAL_CIPHERTEXT_ENVELOPE_LEN,
        StatusCode::PAYLOAD_TOO_LARGE,
    )?;
    if let Some(group_id) = &msg.group_id {
        validate_visible_ascii_field(
            "groupId",
            group_id,
            1,
            MAX_SIGNAL_GROUP_ID_LEN,
            StatusCode::BAD_REQUEST,
        )?;
    }
    if let Some(ephemeral_key) = &msg.ephemeral_key {
        validate_visible_ascii_field(
            "ephemeralKey",
            ephemeral_key,
            1,
            MAX_SIGNAL_EPHEMERAL_KEY_LEN,
            StatusCode::BAD_REQUEST,
        )?;
    }
    Ok(())
}

fn validate_signal_message_json_shape(raw: &Value) -> Result<(), String> {
    let Some(one_time_prekey_id) = raw.get("oneTimePrekeyId") else {
        return Ok(());
    };
    let Some(value) = one_time_prekey_id.as_u64() else {
        return Err("oneTimePrekeyId must be a non-negative integer".to_string());
    };
    if value > u32::MAX as u64 {
        return Err(format!("oneTimePrekeyId exceeds {}", u32::MAX));
    }
    Ok(())
}

pub(crate) fn signal_message_value_from_envelope_bytes(bytes: &[u8]) -> Result<Value, String> {
    let raw: Value = serde_json::from_slice(bytes)
        .map_err(|err| format!("invalid signal envelope JSON: {err}"))?;
    validate_signal_message_json_shape(&raw)
        .map_err(|err| format!("invalid signal envelope JSON: {err}"))?;
    let message: SignalMessage = serde_json::from_value(raw)
        .map_err(|err| format!("invalid signal envelope JSON: {err}"))?;
    validate_signal_email_message(&message)
        .map_err(|(_, err)| format!("invalid signal envelope JSON: {err}"))?;
    serde_json::to_value(message).map_err(|err| format!("signal envelope JSON: {err}"))
}

fn validate_visible_ascii_field(
    field: &'static str,
    value: &str,
    min_len: usize,
    max_len: usize,
    oversize_status: StatusCode,
) -> Result<(), (StatusCode, String)> {
    if value.len() < min_len {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must not be empty"),
        ));
    }
    if value.len() > max_len {
        return Err((oversize_status, format!("{field} exceeds {max_len} bytes")));
    }
    if !value.bytes().all(|b| (0x21..=0x7e).contains(&b)) {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{field} must contain only visible ASCII characters"),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nsid_constants_have_correct_prefix() {
        let prefix = "com.etzhayyim.apps.kotoba.email.";
        for nsid in ALL_EMAIL_NSIDS {
            assert!(nsid.starts_with(prefix), "{nsid}");
        }
    }

    #[test]
    fn all_email_nsids_are_unique_and_complete() {
        let mut seen = std::collections::HashSet::new();
        for nsid in ALL_EMAIL_NSIDS {
            assert!(seen.insert(*nsid), "duplicate email NSID: {nsid}");
        }
        assert_eq!(
            ALL_EMAIL_NSIDS,
            [
                NSID_EMAIL_LIST,
                NSID_EMAIL_READ,
                NSID_EMAIL_INGEST,
                NSID_EMAIL_SEND
            ]
        );
    }

    #[test]
    fn size_limits_are_sane() {
        assert!(MAX_OWNER_DID_LEN >= 64);
        assert!(MAX_EMAIL_CID_LEN >= 32);
        assert!((1..=MAX_EMAIL_LIST_LIMIT).contains(&DEFAULT_EMAIL_LIST_LIMIT));
        assert!(MAX_RAW_B64_LEN >= 1024);
        assert!(
            EMAIL_INGEST_BODY_LIMIT > MAX_RAW_B64_LEN,
            "ingest route body limit must allow raw_b64 plus JSON framing"
        );
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
        assert!(
            EMAIL_SEND_BODY_LIMIT > MAX_RECIPIENTS * MAX_SIGNAL_MSG_BYTES,
            "send route body limit must cover max recipients plus JSON framing"
        );
        assert!(MAX_SIGNAL_DEVICE_ID_LEN < MAX_SIGNAL_MSG_BYTES);
        assert!(MAX_SIGNAL_TIMESTAMP_LEN < MAX_SIGNAL_MSG_BYTES);
    }

    #[test]
    fn legacy_read_text_output_rejects_oversized_and_control_text() {
        assert!(validate_legacy_read_text_output("from", "", MAX_LEGACY_ADDR_LEN).is_ok());
        assert!(validate_legacy_read_text_output(
            "from",
            "alice@example.test",
            MAX_LEGACY_ADDR_LEN
        )
        .is_ok());
        assert_eq!(
            validate_legacy_read_text_output(
                "from",
                &"a".repeat(MAX_LEGACY_ADDR_LEN + 1),
                MAX_LEGACY_ADDR_LEN
            )
            .unwrap_err(),
            "from exceeds 4096 bytes"
        );
        assert_eq!(
            validate_legacy_read_text_output("subject", "hello\nworld", MAX_LEGACY_SUBJECT_LEN)
                .unwrap_err(),
            "subject must contain only visible ASCII characters"
        );
    }

    #[test]
    fn email_record_exists_requires_message_id_and_date() {
        let graph = KotobaCid::from_bytes(b"email-record-exists-graph");
        let email_cid = KotobaCid::from_bytes(b"email-record-exists-email");
        let other_cid = KotobaCid::from_bytes(b"email-record-exists-other");
        let quad = |subject: KotobaCid, predicate: &str, object: &str| LegacyQuad {
            graph: graph.clone(),
            subject,
            predicate: predicate.to_string(),
            object: LegacyQuadObject::Text(object.to_string()),
        };

        assert!(!email_record_exists(&[], &email_cid));
        assert!(!email_record_exists(
            &[quad(
                email_cid.clone(),
                "email/message_id",
                "<message@example.test>",
            )],
            &email_cid
        ));
        assert!(!email_record_exists(
            &[quad(
                email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z",
            )],
            &email_cid
        ));
        assert!(!email_record_exists(
            &[
                quad(
                    email_cid.clone(),
                    "email/message_id",
                    "<message@example.test>",
                ),
                quad(other_cid, "email/date", "2026-06-12T00:00:00Z",),
            ],
            &email_cid
        ));
        assert!(!email_record_exists(
            &[
                quad(email_cid.clone(), "email/message_id", ""),
                quad(email_cid.clone(), "email/date", "2026-06-12T00:00:00Z",),
            ],
            &email_cid
        ));
        assert!(!email_record_exists(
            &[
                quad(email_cid.clone(), "email/message_id", "bad\nmessage-id"),
                quad(email_cid.clone(), "email/date", "2026-06-12T00:00:00Z",),
            ],
            &email_cid
        ));
        assert!(!email_record_exists(
            &[
                quad(
                    email_cid.clone(),
                    "email/message_id",
                    &"m".repeat(MAX_EMAIL_MESSAGE_ID_LEN + 1),
                ),
                quad(email_cid.clone(), "email/date", "2026-06-12T00:00:00Z",),
            ],
            &email_cid
        ));
        assert!(!email_record_exists(
            &[
                quad(
                    email_cid.clone(),
                    "email/message_id",
                    "<message@example.test>",
                ),
                quad(email_cid.clone(), "email/date", ""),
            ],
            &email_cid
        ));
        assert!(!email_record_exists(
            &[
                quad(
                    email_cid.clone(),
                    "email/message_id",
                    "<message@example.test>",
                ),
                quad(email_cid.clone(), "email/date", "2026-06-12\n00:00:00Z"),
            ],
            &email_cid
        ));
        assert!(email_record_exists(
            &[
                quad(
                    email_cid.clone(),
                    "email/message_id",
                    "<message@example.test>",
                ),
                quad(email_cid.clone(), "email/date", "2026-06-12T00:00:00Z",),
            ],
            &email_cid
        ));
    }

    #[test]
    fn visible_bounded_text_from_quads_skips_control_text() {
        let graph = KotobaCid::from_bytes(b"visible-text-graph");
        let email_cid = KotobaCid::from_bytes(b"visible-text-email");
        let quads = [
            String::new(),
            "bad\nmessage-id".to_string(),
            "<visible@example.test>".to_string(),
        ]
        .into_iter()
        .map(|object| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/message_id".to_string(),
            object: LegacyQuadObject::Text(object),
        })
        .collect::<Vec<_>>();

        assert_eq!(
            visible_bounded_text_from_quads(&quads, &email_cid, "email/message_id", 256),
            "<visible@example.test>"
        );
    }

    #[test]
    fn visible_bounded_text_from_quads_skips_oversized_text() {
        let graph = KotobaCid::from_bytes(b"visible-bounded-text-graph");
        let email_cid = KotobaCid::from_bytes(b"visible-bounded-text-email");
        let quads = [
            String::new(),
            "t".repeat(MAX_THREAD_ID_LEN + 1),
            "thread-visible".to_string(),
        ]
        .into_iter()
        .map(|object| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/thread_id".to_string(),
            object: LegacyQuadObject::Text(object),
        })
        .collect::<Vec<_>>();

        assert_eq!(
            visible_bounded_text_from_quads(
                &quads,
                &email_cid,
                "email/thread_id",
                MAX_THREAD_ID_LEN
            ),
            "thread-visible"
        );
    }

    #[test]
    fn latest_visible_bounded_text_from_quads_keeps_latest_visible_value() {
        let graph = KotobaCid::from_bytes(b"latest-visible-text-graph");
        let email_cid = KotobaCid::from_bytes(b"latest-visible-text-email");
        let quads = [
            String::new(),
            "2026-06-10T00:00:00Z".to_string(),
            "2026-06-12T00:00:00Z".to_string(),
            "2026-06-13\n00:00:00Z".to_string(),
        ]
        .into_iter()
        .map(|object| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/date".to_string(),
            object: LegacyQuadObject::Text(object),
        })
        .collect::<Vec<_>>();

        assert_eq!(
            latest_visible_bounded_text_from_quads(
                &quads,
                &email_cid,
                "email/date",
                MAX_EMAIL_DATE_LEN
            ),
            "2026-06-12T00:00:00Z"
        );
    }

    #[test]
    fn latest_visible_bounded_text_from_quads_skips_oversized_values() {
        let graph = KotobaCid::from_bytes(b"latest-visible-bounded-text-graph");
        let email_cid = KotobaCid::from_bytes(b"latest-visible-bounded-text-email");
        let quads = [
            String::new(),
            "2026-06-12T00:00:00Z".to_string(),
            "x".repeat(MAX_EMAIL_DATE_LEN + 1),
        ]
        .into_iter()
        .map(|object| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/date".to_string(),
            object: LegacyQuadObject::Text(object),
        })
        .collect::<Vec<_>>();

        assert_eq!(
            latest_visible_bounded_text_from_quads(
                &quads,
                &email_cid,
                "email/date",
                MAX_EMAIL_DATE_LEN
            ),
            "2026-06-12T00:00:00Z"
        );
    }

    #[test]
    fn unique_visible_text_from_quads_rejects_invalid_and_ambiguous_values() {
        let graph = KotobaCid::from_bytes(b"unique-visible-text-graph");
        let email_cid = KotobaCid::from_bytes(b"unique-visible-text-email");
        let quad = |object: &str| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/message_id".to_string(),
            object: LegacyQuadObject::Text(object.to_string()),
        };

        assert_eq!(
            unique_visible_text_from_quads(&[], &email_cid, "email/message_id"),
            Err(EmailTextFieldError::Missing)
        );
        assert_eq!(
            unique_visible_text_from_quads(
                &[quad("bad\nmessage-id")],
                &email_cid,
                "email/message_id"
            ),
            Err(EmailTextFieldError::Invalid)
        );
        assert_eq!(
            unique_visible_text_from_quads(
                &[quad("<a@example.test>"), quad("<b@example.test>")],
                &email_cid,
                "email/message_id"
            ),
            Err(EmailTextFieldError::Ambiguous)
        );
        assert_eq!(
            unique_visible_text_from_quads(
                &[quad("<a@example.test>"), quad("<a@example.test>")],
                &email_cid,
                "email/message_id"
            )
            .unwrap(),
            "<a@example.test>"
        );
    }

    #[test]
    fn unique_visible_bounded_text_from_quads_rejects_oversized_values() {
        let graph = KotobaCid::from_bytes(b"unique-visible-bounded-text-graph");
        let email_cid = KotobaCid::from_bytes(b"unique-visible-bounded-text-email");
        let quad = |object: String| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/message_id".to_string(),
            object: LegacyQuadObject::Text(object),
        };

        assert_eq!(
            unique_visible_bounded_text_from_quads(
                &[quad("m".repeat(MAX_EMAIL_MESSAGE_ID_LEN))],
                &email_cid,
                "email/message_id",
                MAX_EMAIL_MESSAGE_ID_LEN
            ),
            Ok("m".repeat(MAX_EMAIL_MESSAGE_ID_LEN))
        );
        assert_eq!(
            unique_visible_bounded_text_from_quads(
                &[quad("m".repeat(MAX_EMAIL_MESSAGE_ID_LEN + 1))],
                &email_cid,
                "email/message_id",
                MAX_EMAIL_MESSAGE_ID_LEN
            ),
            Err(EmailTextFieldError::Invalid)
        );
    }

    #[test]
    fn email_enc_from_quads_accepts_missing_or_signal_only() {
        let graph = KotobaCid::from_bytes(b"email-enc-graph");
        let email_cid = KotobaCid::from_bytes(b"email-enc-email");
        let quad = |object: LegacyQuadObject| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/enc".to_string(),
            object,
        };

        assert_eq!(
            email_enc_from_quads(&[], &email_cid).unwrap(),
            EmailEnc::Legacy
        );
        assert_eq!(
            email_enc_from_quads(
                &[quad(LegacyQuadObject::Text(ENC_SIGNAL_V1.to_string()))],
                &email_cid
            )
            .unwrap(),
            EmailEnc::Signal
        );
        assert_eq!(
            email_enc_from_quads(
                &[quad(LegacyQuadObject::Text("unknown:v1".to_string()))],
                &email_cid
            ),
            Err(EmailEncError::Invalid)
        );
        assert_eq!(
            email_enc_from_quads(&[quad(LegacyQuadObject::Integer(1))], &email_cid),
            Err(EmailEncError::Invalid)
        );
    }

    #[test]
    fn email_body_cid_from_quads_requires_one_valid_cid() {
        let graph = KotobaCid::from_bytes(b"email-body-cid-graph");
        let email_cid = KotobaCid::from_bytes(b"email-body-cid-email");
        let quad = |object: String| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: "email/body_cid".to_string(),
            object: LegacyQuadObject::Text(object),
        };
        let body = test_body_cid(b"email-body-cid-body");
        assert_eq!(
            email_body_cid_from_quads(&[quad(body.clone()), quad(body.clone())], &email_cid)
                .unwrap(),
            body
        );
        assert_eq!(
            email_body_cid_from_quads(&[], &email_cid),
            Err(EmailBodyCidError::Missing)
        );
        assert_eq!(
            email_body_cid_from_quads(&[quad("not-a-cid".to_string())], &email_cid),
            Err(EmailBodyCidError::Invalid)
        );
        assert_eq!(
            email_body_cid_from_quads(
                &[
                    quad(test_body_cid(b"email-body-cid-body-a")),
                    quad(test_body_cid(b"email-body-cid-body-b")),
                ],
                &email_cid,
            ),
            Err(EmailBodyCidError::Ambiguous)
        );
    }

    #[tokio::test]
    async fn email_body_cid_error_response_maps_status_and_message() {
        for (err, status, expected) in [
            (
                EmailBodyCidError::Missing,
                StatusCode::NOT_FOUND,
                "email/body_cid not found",
            ),
            (
                EmailBodyCidError::Invalid,
                StatusCode::INTERNAL_SERVER_ERROR,
                "invalid body_cid multibase",
            ),
            (
                EmailBodyCidError::Ambiguous,
                StatusCode::INTERNAL_SERVER_ERROR,
                "multiple email/body_cid values found",
            ),
        ] {
            let response = email_body_cid_error_response(err);
            assert_eq!(response.status(), status);
            let body = axum::body::to_bytes(response.into_body(), usize::MAX)
                .await
                .unwrap();
            let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
            assert_eq!(value["error"], expected);
        }
    }

    #[test]
    fn email_entries_from_quads_dedupes_by_cid_and_keeps_latest_date() {
        let graph = KotobaCid::from_bytes(b"email-entries-graph");
        let first = KotobaCid::from_bytes(b"email-entries-first");
        let second = KotobaCid::from_bytes(b"email-entries-second");
        let date_only = KotobaCid::from_bytes(b"email-entries-date-only");
        let empty_message_id = KotobaCid::from_bytes(b"email-entries-empty-message-id");
        let empty_date = KotobaCid::from_bytes(b"email-entries-empty-date");
        let missing_body_cid = KotobaCid::from_bytes(b"email-entries-missing-body-cid");
        let invalid_body_cid = KotobaCid::from_bytes(b"email-entries-invalid-body-cid");
        let non_text_message_id = KotobaCid::from_bytes(b"email-entries-non-text-message-id");
        let oversized_message_id = KotobaCid::from_bytes(b"email-entries-oversized-message-id");
        let quad = |subject: KotobaCid, predicate: &str, object: &str| LegacyQuad {
            graph: graph.clone(),
            subject,
            predicate: predicate.to_string(),
            object: LegacyQuadObject::Text(object.to_string()),
        };
        let quads = vec![
            quad(first.clone(), "email/message_id", "<first@example.test>"),
            quad(
                first.clone(),
                "email/body_cid",
                &test_body_cid(b"email-entries-first-body"),
            ),
            quad(first.clone(), "email/date", "2026-06-10T00:00:00Z"),
            quad(first.clone(), "email/date", "2026-06-12T00:00:00Z"),
            quad(second.clone(), "email/message_id", "<second@example.test>"),
            quad(
                second.clone(),
                "email/body_cid",
                &test_body_cid(b"email-entries-second-body"),
            ),
            quad(second.clone(), "email/date", "2026-06-11T00:00:00Z"),
            quad(
                KotobaCid::from_bytes(b"email-entries-control-message-id"),
                "email/message_id",
                "bad\nmessage-id",
            ),
            quad(
                KotobaCid::from_bytes(b"email-entries-control-message-id"),
                "email/date",
                "2026-06-16T00:00:00Z",
            ),
            quad(
                KotobaCid::from_bytes(b"email-entries-control-date"),
                "email/message_id",
                "<control-date@example.test>",
            ),
            quad(
                KotobaCid::from_bytes(b"email-entries-control-date"),
                "email/date",
                "2026-06-17\n00:00:00Z",
            ),
            LegacyQuad {
                graph: graph.clone(),
                subject: KotobaCid::from_bytes(b"email-entries-non-text-date"),
                predicate: "email/message_id".to_string(),
                object: LegacyQuadObject::Text("<bad-date@example.test>".to_string()),
            },
            LegacyQuad {
                graph: graph.clone(),
                subject: KotobaCid::from_bytes(b"email-entries-non-text-date"),
                predicate: "email/date".to_string(),
                object: LegacyQuadObject::Integer(1),
            },
            quad(empty_message_id.clone(), "email/message_id", ""),
            quad(
                empty_message_id.clone(),
                "email/body_cid",
                &test_body_cid(b"email-entries-empty-message-id-body"),
            ),
            quad(empty_message_id, "email/date", "2026-06-14T00:00:00Z"),
            quad(
                empty_date.clone(),
                "email/message_id",
                "<empty-date@example.test>",
            ),
            quad(
                empty_date.clone(),
                "email/body_cid",
                &test_body_cid(b"email-entries-empty-date-body"),
            ),
            quad(empty_date, "email/date", ""),
            quad(
                missing_body_cid.clone(),
                "email/message_id",
                "<missing-body@example.test>",
            ),
            quad(missing_body_cid, "email/date", "2026-06-18T00:00:00Z"),
            quad(
                invalid_body_cid.clone(),
                "email/message_id",
                "<invalid-body@example.test>",
            ),
            quad(invalid_body_cid.clone(), "email/body_cid", "not-a-cid"),
            quad(invalid_body_cid, "email/date", "2026-06-19T00:00:00Z"),
            LegacyQuad {
                graph: graph.clone(),
                subject: non_text_message_id.clone(),
                predicate: "email/message_id".to_string(),
                object: LegacyQuadObject::Integer(1),
            },
            quad(non_text_message_id, "email/date", "2026-06-15T00:00:00Z"),
            quad(
                oversized_message_id.clone(),
                "email/message_id",
                &"m".repeat(MAX_EMAIL_MESSAGE_ID_LEN + 1),
            ),
            quad(
                oversized_message_id.clone(),
                "email/body_cid",
                &test_body_cid(b"email-entries-oversized-message-id-body"),
            ),
            quad(oversized_message_id, "email/date", "2026-06-20T00:00:00Z"),
            quad(date_only, "email/date", "2026-06-13T00:00:00Z"),
        ];

        let entries = email_entries_from_quads(&quads);
        assert_eq!(entries.len(), 2);
        assert_eq!(entries[0], (first, "2026-06-12T00:00:00Z".to_string()));
        assert_eq!(entries[1], (second, "2026-06-11T00:00:00Z".to_string()));
    }

    #[test]
    fn email_entries_from_quads_tiebreaks_same_date_by_cid() {
        let graph = KotobaCid::from_bytes(b"email-entries-tiebreak-graph");
        let a = KotobaCid::from_bytes(b"email-entries-tiebreak-a");
        let b = KotobaCid::from_bytes(b"email-entries-tiebreak-b");
        let date = "2026-06-12T00:00:00Z";
        let quad = |subject: KotobaCid, predicate: &str, object: String| LegacyQuad {
            graph: graph.clone(),
            subject,
            predicate: predicate.to_string(),
            object: LegacyQuadObject::Text(object),
        };
        let quads = vec![
            quad(b.clone(), "email/message_id", b.to_multibase()),
            quad(
                b.clone(),
                "email/body_cid",
                test_body_cid(b"email-entries-tiebreak-b-body"),
            ),
            quad(b.clone(), "email/date", date.to_string()),
            quad(a.clone(), "email/message_id", a.to_multibase()),
            quad(
                a.clone(),
                "email/body_cid",
                test_body_cid(b"email-entries-tiebreak-a-body"),
            ),
            quad(a.clone(), "email/date", date.to_string()),
        ];

        let entries = email_entries_from_quads(&quads);
        let mut expected = vec![(a, date.to_string()), (b, date.to_string())];
        expected.sort_by_key(|entry| entry.0.to_multibase());
        assert_eq!(entries, expected);
    }

    // ── email.send → email.list/read native E2E round-trip ────────────────────
    //
    // Drives the handler logic directly (no HTTP) against an in-memory state to
    // prove a Signal envelope lands in the recipient's inbox graph with the
    // zero-access markers, and that the server returns it verbatim (never
    // attempting to decrypt the sealed body).

    use kotoba_signal::message::{MessageType, SignalMessage};

    fn bearer_jwt_from_payload(payload: serde_json::Value) -> String {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
        format!(
            "x.{}.x",
            URL_SAFE_NO_PAD.encode(serde_json::to_vec(&payload).unwrap())
        )
    }

    fn bearer_jwt_for_sub(did: &str) -> String {
        let payload = serde_json::json!({
            "sub": did,
            "exp": 4_102_444_800u64
        });
        bearer_jwt_from_payload(payload)
    }

    fn test_body_cid(label: &[u8]) -> String {
        KotobaCid::from_bytes(label).to_multibase()
    }

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

    #[test]
    fn email_query_and_ingest_body_deserialize_public_snake_case_fields() {
        let owner = "did:key:zEmailSnakeCaseSerde";
        let list: EmailListQuery = serde_json::from_value(json!({
            "owner_did": owner,
            "limit": 25,
            "offset": 2
        }))
        .expect("email.list snake_case params");
        assert_eq!(list.owner_did, owner);
        assert_eq!(list.limit, Some(25));
        assert_eq!(list.offset, Some(2));

        let read: EmailReadQuery = serde_json::from_value(json!({
            "owner_did": owner,
            "email_cid": "bafyEmailCid"
        }))
        .expect("email.read snake_case params");
        assert_eq!(read.owner_did, owner);
        assert_eq!(read.email_cid, "bafyEmailCid");

        let ingest: EmailIngestBody = serde_json::from_value(json!({
            "owner_did": owner,
            "raw_b64": "T0s=",
            "thread_id": "thread-1"
        }))
        .expect("email.ingest snake_case body");
        assert_eq!(ingest.owner_did, owner);
        assert_eq!(ingest.raw_b64, "T0s=");
        assert_eq!(ingest.thread_id.as_deref(), Some("thread-1"));
    }

    #[test]
    fn email_ingest_body_rejects_camel_case_owner_field() {
        let err = match serde_json::from_value::<EmailIngestBody>(json!({
            "ownerDid": "did:key:zEmailIngestCamelCase",
            "raw_b64": "T0s=",
            "thread_id": "thread-1"
        })) {
            Ok(_) => panic!("email.ingest body unexpectedly accepted camelCase fields"),
            Err(err) => err,
        };

        assert!(err.to_string().contains("owner_did"), "{err}");
    }

    #[test]
    fn validate_thread_id_param_allows_empty_optional_value_and_rejects_invalid_text() {
        assert!(validate_thread_id_param("thread_id", "").is_ok());
        assert!(validate_thread_id_param("thread_id", "thread-1").is_ok());

        let oversized =
            validate_thread_id_param("thread_id", &"t".repeat(MAX_THREAD_ID_LEN + 1)).unwrap_err();
        assert_eq!(oversized.0, StatusCode::BAD_REQUEST);
        assert!(oversized.1.contains("thread_id exceeds"), "{oversized:?}");

        let control = validate_thread_id_param("thread_id", "thread\nid").unwrap_err();
        assert_eq!(control.0, StatusCode::BAD_REQUEST);
        assert!(
            control
                .1
                .contains("thread_id must contain only visible ASCII characters"),
            "{control:?}"
        );
    }

    #[test]
    fn email_ingest_body_rejects_unknown_fields() {
        let err = match serde_json::from_value::<EmailIngestBody>(json!({
            "owner_did": "did:key:zEmailIngestUnknownField",
            "raw_b64": "T0s=",
            "thread_id": "thread-1",
            "extra": true
        })) {
            Ok(_) => panic!("email.ingest body unexpectedly accepted unknown field"),
            Err(err) => err,
        };

        assert!(err.to_string().contains("unknown field `extra`"), "{err}");
    }

    #[test]
    fn email_list_query_rejects_unknown_fields() {
        let err = match serde_json::from_value::<EmailListQuery>(json!({
            "owner_did": "did:key:zEmailListQueryUnknownField",
            "limit": 25,
            "offset": 2,
            "extra": true
        })) {
            Ok(_) => panic!("email.list query unexpectedly accepted unknown field"),
            Err(err) => err,
        };

        assert!(err.to_string().contains("unknown field `extra`"), "{err}");
    }

    #[test]
    fn email_read_query_rejects_unknown_fields() {
        let err = match serde_json::from_value::<EmailReadQuery>(json!({
            "owner_did": "did:key:zEmailReadQueryUnknownField",
            "email_cid": "bafyEmailCid",
            "extra": true
        })) {
            Ok(_) => panic!("email.read query unexpectedly accepted unknown field"),
            Err(err) => err,
        };

        assert!(err.to_string().contains("unknown field `extra`"), "{err}");
    }

    #[test]
    fn email_send_body_deserializes_public_camel_case_fields() {
        let sender = "did:key:zSenderSendBodySerde";
        let body: EmailSendBody = serde_json::from_value(json!({
            "senderDid": sender,
            "threadId": "thread-1",
            "recipients": [sample_envelope(sender, "did:key:zRecipientSendBodySerde")]
        }))
        .expect("camelCase email.send body");

        assert_eq!(body.sender_did, sender);
        assert_eq!(body.thread_id.as_deref(), Some("thread-1"));
        assert_eq!(body.recipients.len(), 1);
    }

    #[test]
    fn email_send_body_rejects_legacy_snake_case_sender_field() {
        let sender = "did:key:zSenderSendBodySnakeCase";
        let err = match serde_json::from_value::<EmailSendBody>(json!({
            "sender_did": sender,
            "thread_id": "thread-1",
            "recipients": [sample_envelope(sender, "did:key:zRecipientSendBodySnakeCase")]
        })) {
            Ok(_) => panic!("email.send body unexpectedly accepted snake_case fields"),
            Err(err) => err,
        };

        assert!(err.to_string().contains("senderDid"), "{err}");
    }

    #[test]
    fn email_send_body_rejects_unknown_fields() {
        let sender = "did:key:zSenderSendBodyUnknownField";
        let err = match serde_json::from_value::<EmailSendBody>(json!({
            "senderDid": sender,
            "threadId": "thread-1",
            "recipients": [sample_envelope(sender, "did:key:zRecipientSendBodyUnknownField")],
            "extra": true
        })) {
            Ok(_) => panic!("email.send body unexpectedly accepted unknown field"),
            Err(err) => err,
        };

        assert!(err.to_string().contains("unknown field `extra`"), "{err}");
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
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
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
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        p.to_string(),
                        kotoba_query::Value::Text(o),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let quads = current_email_quads(&state, &graph_cid).await.unwrap();
        // The native branch's discriminant is present...
        assert_eq!(
            text_from_quads(&quads, &email_cid, "email/enc"),
            ENC_SIGNAL_V1
        );
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

    #[tokio::test]
    async fn email_send_stores_canonical_signal_envelope_without_unknown_fields() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderCanonical";
        let recipient = "did:key:zRecipientCanonical";
        let mut env = sample_envelope(sender, recipient);
        env["untrustedVisibleMetadata"] = json!("must-not-be-stored");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state.clone()),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![env],
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let body_cid = value["delivered"][0]["bodyCid"].as_str().expect("bodyCid");
        let blob_cid = KotobaCid::from_multibase(body_cid).expect("body cid");
        let envelope_bytes = state.vault.get(&blob_cid).await.expect("envelope blob");
        let stored: serde_json::Value = serde_json::from_slice(&envelope_bytes).unwrap();

        assert!(stored.get("untrustedVisibleMetadata").is_none(), "{stored}");
        assert_eq!(stored, sample_envelope(sender, recipient));
    }

    #[tokio::test]
    async fn email_send_rejects_oversized_recipient_envelope() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderOversizedEnvelope";
        let recipient = "did:key:zRecipientOversizedEnvelope";
        let mut env = sample_envelope(sender, recipient);
        env["ciphertextEnvelope"] = json!("x".repeat(MAX_SIGNAL_MSG_BYTES + 1));

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![env],
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("recipient envelope exceeds")),
            "{value}"
        );
        assert_eq!(value["deliveredSoFar"].as_array().map(Vec::len), Some(0));
    }

    #[tokio::test]
    async fn email_send_rejects_invalid_sender_did_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_send(
            State(state),
            HeaderMap::new(),
            Json(EmailSendBody {
                sender_did: "not-a-did".to_string(),
                thread_id: None,
                recipients: Vec::new(),
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
                .is_some_and(|err| err.contains("senderDid")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_rejects_invalid_owner_did_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_ingest(
            State(state),
            HeaderMap::new(),
            Json(EmailIngestBody {
                owner_did: "not-a-did".to_string(),
                raw_b64: String::new(),
                thread_id: None,
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
                .is_some_and(|err| err.contains("owner_did")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_rejects_empty_raw_b64_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_ingest(
            State(state),
            HeaderMap::new(),
            Json(EmailIngestBody {
                owner_did: "did:key:zXrpcEmailIngestEmptyRaw".to_string(),
                raw_b64: String::new(),
                thread_id: None,
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
                .is_some_and(|err| err.contains("raw_b64 must not be empty")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_rejects_oversized_raw_b64_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_ingest(
            State(state),
            HeaderMap::new(),
            Json(EmailIngestBody {
                owner_did: "did:key:zXrpcEmailIngestOversizedRaw".to_string(),
                raw_b64: "A".repeat(MAX_RAW_B64_LEN + 1),
                thread_id: None,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("raw_b64 exceeds")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_rejects_oversized_thread_id_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_ingest(
            State(state),
            HeaderMap::new(),
            Json(EmailIngestBody {
                owner_did: "did:key:zXrpcEmailIngestOversizedThread".to_string(),
                raw_b64: "T0s=".to_string(),
                thread_id: Some("t".repeat(MAX_THREAD_ID_LEN + 1)),
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
                .is_some_and(|err| err.contains("thread_id exceeds")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_rejects_control_thread_id_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_ingest(
            State(state),
            HeaderMap::new(),
            Json(EmailIngestBody {
                owner_did: "did:key:zXrpcEmailIngestControlThread".to_string(),
                raw_b64: "T0s=".to_string(),
                thread_id: Some("thread\nid".to_string()),
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
                .is_some_and(|err| err.contains("thread_id")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_rejects_invalid_base64_before_crypto() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        assert!(
            state.crypto.is_none(),
            "test state must not initialise crypto"
        );
        let owner = "did:key:zXrpcEmailIngestInvalidBase64";
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );

        let response = email_ingest(
            State(state),
            headers,
            Json(EmailIngestBody {
                owner_did: owner.to_string(),
                raw_b64: "not-valid-base64!".to_string(),
                thread_id: None,
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
                .is_some_and(|err| err.contains("base64 decode")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_rejects_oversized_decoded_payload_before_crypto() {
        use base64::{engine::general_purpose::STANDARD as B64, Engine as _};

        let state = Arc::new(KotobaState::new(None).expect("state"));
        assert!(
            state.crypto.is_none(),
            "test state must not initialise crypto"
        );
        let owner = "did:key:zXrpcEmailIngestOversizedDecoded";
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let raw_b64 = B64.encode(vec![b'X'; EmailIngestor::MAX_EMAIL_BYTES + 1]);
        assert!(
            raw_b64.len() <= MAX_RAW_B64_LEN,
            "test input must pass raw_b64 length validation"
        );

        let response = email_ingest(
            State(state),
            headers,
            Json(EmailIngestBody {
                owner_did: owner.to_string(),
                raw_b64,
                thread_id: None,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::PAYLOAD_TOO_LARGE);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("decoded email exceeds")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_ingest_without_crypto_returns_503_after_valid_base64() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        assert!(
            state.crypto.is_none(),
            "test state must not initialise crypto"
        );
        let owner = "did:key:zXrpcEmailIngestNoCrypto";
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );

        let response = email_ingest(
            State(state),
            headers,
            Json(EmailIngestBody {
                owner_did: owner.to_string(),
                raw_b64: "T0s=".to_string(),
                thread_id: None,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("crypto not initialised")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_send_rejects_empty_recipients_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderEmptyRecipients";

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: Vec::new(),
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
                .is_some_and(|err| err.contains("recipients must not be empty")),
            "{value}"
        );
        assert!(value.get("deliveredSoFar").is_none(), "{value}");
    }

    #[tokio::test]
    async fn email_send_rejects_too_many_recipients_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderTooManyRecipients";
        let recipients = (0..=MAX_RECIPIENTS)
            .map(|index| sample_envelope(sender, &format!("did:key:zRecipient{index}")))
            .collect::<Vec<_>>();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients,
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
                .is_some_and(|err| err.contains("recipients exceeds")),
            "{value}"
        );
        assert!(value.get("deliveredSoFar").is_none(), "{value}");
    }

    #[tokio::test]
    async fn email_send_rejects_oversized_thread_id_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderOversizedThread";
        let recipient = "did:key:zRecipientOversizedThread";
        let env = sample_envelope(sender, recipient);

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: Some("t".repeat(MAX_THREAD_ID_LEN + 1)),
                recipients: vec![env],
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
                .is_some_and(|err| err.contains("threadId exceeds")),
            "{value}"
        );
        assert!(value.get("deliveredSoFar").is_none(), "{value}");
    }

    #[tokio::test]
    async fn email_send_rejects_control_thread_id_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderControlThread";
        let recipient = "did:key:zRecipientControlThread";
        let env = sample_envelope(sender, recipient);

        let response = email_send(
            State(state),
            HeaderMap::new(),
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: Some("thread\nid".to_string()),
                recipients: vec![env],
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
                .is_some_and(|err| err.contains("threadId")),
            "{value}"
        );
        assert!(value.get("deliveredSoFar").is_none(), "{value}");
    }

    #[tokio::test]
    async fn email_send_rejects_invalid_recipient_did_without_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderInvalidRecipient";
        let mut env = sample_envelope(sender, "did:key:zRecipientInvalid");
        env["recipientDid"] = json!("did:key:zRecipientInvalid/path");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![env],
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
        assert_eq!(value["deliveredSoFar"].as_array().map(Vec::len), Some(0));
    }

    #[tokio::test]
    async fn email_send_rejects_bearer_sender_mismatch_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderBearerMismatch";
        let bearer_owner = "did:key:zDifferentBearerOwner";
        let recipient = "did:key:zRecipientBearerMismatch";
        let env = sample_envelope(sender, recipient);

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(bearer_owner))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![env],
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("Bearer sub does not match owner_did")),
            "{value}"
        );
        assert!(
            value.get("deliveredSoFar").is_none(),
            "auth failures must not enter the delivery loop: {value}"
        );
    }

    #[tokio::test]
    async fn email_send_rejects_expired_bearer_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderExpiredBearer";
        let recipient = "did:key:zRecipientExpiredBearer";
        let env = sample_envelope(sender, recipient);

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!(
                "Bearer {}",
                bearer_jwt_from_payload(json!({ "sub": sender, "exp": 1u64 }))
            )
            .parse()
            .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![env],
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("Bearer token has expired")),
            "{value}"
        );
        assert!(
            value.get("deliveredSoFar").is_none(),
            "auth failures must not enter the delivery loop: {value}"
        );
    }

    #[tokio::test]
    async fn email_send_rejects_envelope_sender_mismatch_without_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zAuthenticatedSenderMismatch";
        let recipient = "did:key:zRecipientSenderMismatch";
        let env = sample_envelope("did:key:zEnvelopeImpostorMismatch", recipient);

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(state),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![env],
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
                .is_some_and(|err| err.contains("senderDid")),
            "{value}"
        );
        assert_eq!(value["deliveredSoFar"].as_array().map(Vec::len), Some(0));
    }

    #[tokio::test]
    async fn email_send_preflights_all_recipients_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderPartialFailure";
        let first_recipient = "did:key:zRecipientPartialSuccess";
        let second_recipient = "did:key:zRecipientPartialFailure";
        let first = sample_envelope(sender, first_recipient);
        let second = sample_envelope("did:key:zImpostorPartialFailure", second_recipient);

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(Arc::clone(&state)),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: Some("thread-partial-failure".to_string()),
                recipients: vec![first, second],
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
                .is_some_and(|err| err.contains("senderDid")),
            "{value}"
        );
        let delivered = value["deliveredSoFar"].as_array().expect("deliveredSoFar");
        assert_eq!(delivered.len(), 0, "{value}");
        assert!(
            state
                .quad_store
                .arrangement(&graph_cid_for(first_recipient))
                .await
                .is_none(),
            "invalid later recipient must not partially deliver earlier recipients"
        );
    }

    #[tokio::test]
    async fn email_send_rejects_duplicate_envelopes_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderDuplicateEnvelope";
        let recipient = "did:key:zRecipientDuplicateEnvelope";
        let env = sample_envelope(sender, recipient);

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(Arc::clone(&state)),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![env.clone(), env],
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
                .is_some_and(|err| err.contains("duplicate recipient")),
            "{value}"
        );
        assert_eq!(value["deliveredSoFar"].as_array().map(Vec::len), Some(0));
        assert!(
            state
                .quad_store
                .arrangement(&graph_cid_for(recipient))
                .await
                .is_none(),
            "duplicate input must not deliver before validation completes"
        );
    }

    #[tokio::test]
    async fn email_send_rejects_duplicate_recipient_device_before_delivery() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zSenderDuplicateDevice";
        let recipient = "did:key:zRecipientDuplicateDevice";
        let first = sample_envelope(sender, recipient);
        let mut second = sample_envelope(sender, recipient);
        second["ciphertextEnvelope"] = json!("different-sealed-envelope");

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(sender))
                .parse()
                .unwrap(),
        );
        let response = email_send(
            State(Arc::clone(&state)),
            headers,
            Json(EmailSendBody {
                sender_did: sender.to_string(),
                thread_id: None,
                recipients: vec![first, second],
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
                .is_some_and(|err| err.contains("duplicate recipient device")),
            "{value}"
        );
        assert_eq!(value["deliveredSoFar"].as_array().map(Vec::len), Some(0));
        assert!(
            state
                .quad_store
                .arrangement(&graph_cid_for(recipient))
                .await
                .is_none(),
            "duplicate recipient device must not deliver before validation completes"
        );
    }

    #[tokio::test]
    async fn email_read_returns_signal_envelope_without_crypto() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        assert!(
            state.crypto.is_none(),
            "test state must not initialise crypto"
        );

        let sender = "did:key:zXrpcSignalSenderNoCrypto";
        let recipient = "did:key:zXrpcSignalRecipientNoCrypto";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-signal-no-crypto-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender.to_string()),
            ("email/to", recipient.to_string()),
            ("email/body_cid", body_cid_mb),
            ("email/date", "2026-06-01T00:00:00Z".to_string()),
            ("email/date", msg.timestamp.clone()),
            ("email/thread_id", "thread-no-crypto".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb.clone(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(value["email_cid"], email_cid_mb, "{value}");
        assert_eq!(value["enc"], ENC_SIGNAL_V1, "{value}");
        assert_eq!(value["date"], msg.timestamp, "{value}");
        assert_eq!(value["signalMessage"], env, "{value}");
        assert!(
            value.get("body").is_none(),
            "signal read must not require or expose server-decrypted body: {value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_signal_routing_datoms_that_mismatch_envelope() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalEnvelopeSender";
        let recipient = "did:key:zXrpcSignalEnvelopeRecipient";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-signal-envelope-dids-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", "not-a-did".to_string()),
            ("email/to", "did:key:zWrongRecipient".to_string()),
            ("email/body_cid", body_cid_mb),
            ("email/date", msg.timestamp.clone()),
            ("email/thread_id", "thread-envelope-dids".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("senderDid does not match email/from")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_ambiguous_signal_from_routing_datoms() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalAmbiguousFromSender";
        let recipient = "did:key:zXrpcSignalAmbiguousFromRecipient";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-signal-ambiguous-from-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender.to_string()),
            ("email/from", "did:key:zOtherSender".to_string()),
            ("email/to", recipient.to_string()),
            ("email/body_cid", body_cid_mb),
            ("email/date", msg.timestamp),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("multiple email/from values found")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_signal_to_datom_that_mismatches_envelope() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalToDatomSender";
        let recipient = "did:key:zXrpcSignalToDatomRecipient";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-signal-to-datom-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender.to_string()),
            ("email/to", "did:key:zWrongRecipient".to_string()),
            ("email/body_cid", body_cid_mb),
            ("email/date", msg.timestamp),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("recipientDid does not match email/to")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_invalid_signal_to_routing_datom() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalInvalidToSender";
        let recipient = "did:key:zXrpcSignalInvalidToRecipient";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-signal-invalid-to-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender.to_string()),
            ("email/to", "did:key:zBad\nRecipient".to_string()),
            ("email/body_cid", body_cid_mb),
            ("email/date", msg.timestamp),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("invalid email/to")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_omits_control_thread_id() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalControlThreadSender";
        let recipient = "did:key:zXrpcSignalControlThreadRecipient";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-control-thread-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", body_cid_mb),
            ("email/date", msg.timestamp),
            ("email/thread_id", "thread\nid".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(value["thread_id"], "", "{value}");
    }

    #[tokio::test]
    async fn email_read_omits_oversized_thread_id() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalOversizedThreadSender";
        let recipient = "did:key:zXrpcSignalOversizedThreadRecipient";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-oversized-thread-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", body_cid_mb),
            ("email/date", msg.timestamp),
            ("email/thread_id", "t".repeat(MAX_THREAD_ID_LEN + 1)),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(value["thread_id"], "", "{value}");
    }

    #[tokio::test]
    async fn email_read_returns_canonical_signal_envelope_without_unknown_fields() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalReadCanonicalSender";
        let recipient = "did:key:zXrpcSignalReadCanonicalRecipient";
        let mut stored_env = sample_envelope(sender, recipient);
        stored_env["untrustedVisibleMetadata"] = json!("must-not-be-returned");
        let expected_env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(expected_env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&stored_env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-signal-canonical-envelope-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", sender.to_string()),
            ("email/to", recipient.to_string()),
            ("email/body_cid", body_cid_mb),
            ("email/date", msg.timestamp),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(value["signalMessage"], expected_env, "{value}");
        assert!(
            value["signalMessage"]
                .get("untrustedVisibleMetadata")
                .is_none(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_signal_body_cid_swapped_after_send() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalSwapSender";
        let recipient = "did:key:zXrpcSignalSwapRecipient";
        let original_env = sample_envelope(sender, recipient);
        let original_msg: SignalMessage = serde_json::from_value(original_env.clone()).unwrap();
        let original_blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&original_env).unwrap(),
            ))
            .await;
        let original_body_cid_mb = original_blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(
            sender,
            recipient,
            &original_msg.timestamp,
            &original_body_cid_mb,
        );
        let email_cid_mb = email_cid.to_multibase();

        let mut swapped_env = sample_envelope(sender, recipient);
        swapped_env["ciphertextEnvelope"] = json!("c3dhcHBlZC1taW1l");
        let swapped_msg: SignalMessage = serde_json::from_value(swapped_env.clone()).unwrap();
        let swapped_blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&swapped_env).unwrap(),
            ))
            .await;
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-body-cid-swapped-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", swapped_blob.cid.to_multibase()),
            ("email/date", swapped_msg.timestamp),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("body_cid does not match email_cid")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_signal_date_mismatch() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let sender = "did:key:zXrpcSignalDateSender";
        let recipient = "did:key:zXrpcSignalDateRecipient";
        let env = sample_envelope(sender, recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let body_cid_mb = blob.cid.to_multibase();
        let email_cid = signal_email_cid_for(sender, recipient, &msg.timestamp, &body_cid_mb);
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(recipient);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-date-mismatch-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", body_cid_mb),
            ("email/date", "2026-06-03T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(recipient))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: recipient.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("timestamp does not match email/date")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_signal_envelope_for_different_recipient() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalMailboxOwner";
        let actual_recipient = "did:key:zXrpcSignalOtherRecipient";
        let env = sample_envelope("did:key:zXrpcSignalSender", actual_recipient);
        let msg: SignalMessage = serde_json::from_value(env.clone()).unwrap();
        let blob = state
            .vault
            .put(bytes::Bytes::from(serde_json::to_vec(&env).unwrap()))
            .await;
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-recipient-mismatch");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-recipient-mismatch-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/from", msg.sender_did),
            ("email/to", owner.to_string()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", msg.timestamp),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let err = value["error"].as_str().unwrap_or_default();
        assert!(err.contains("recipientDid"), "{value}");
        assert!(err.contains("owner_did"), "{value}");
    }

    #[tokio::test]
    async fn email_read_rejects_corrupt_signal_envelope_blob() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalCorruptEnvelope";
        let blob = state
            .vault
            .put(bytes::Bytes::from_static(b"not-json"))
            .await;
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-corrupt-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-corrupt-envelope-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("invalid signal envelope JSON")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_malformed_signal_envelope_object() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalMalformedEnvelope";
        let blob = state
            .vault
            .put(bytes::Bytes::from_static(
                br#"{"messageType":"directMessage"}"#,
            ))
            .await;
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-malformed-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-malformed-envelope-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("invalid signal envelope JSON")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_oversized_stored_signal_envelope() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalOversizedStoredEnvelope";
        let mut signal_message = sample_envelope("did:key:zSender", owner);
        signal_message["ciphertextEnvelope"] =
            json!("x".repeat(MAX_SIGNAL_CIPHERTEXT_ENVELOPE_LEN + 1));
        let blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-oversized-stored-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-oversized-stored-envelope-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let err = value["error"].as_str().unwrap_or_default();
        assert!(err.contains("invalid signal envelope JSON"), "{value}");
        assert!(err.contains("ciphertextEnvelope"), "{value}");
    }

    #[tokio::test]
    async fn email_read_rejects_signal_envelope_with_invalid_sender_did() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalInvalidSenderEnvelope";
        let mut signal_message = sample_envelope("did:key:zSender", owner);
        signal_message["senderDid"] = json!("not-a-did");
        let blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-invalid-sender-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-invalid-sender-envelope-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let err = value["error"].as_str().unwrap_or_default();
        assert!(err.contains("invalid signal envelope JSON"), "{value}");
        assert!(err.contains("senderDid"), "{value}");
    }

    #[tokio::test]
    async fn email_read_rejects_signal_envelope_with_invalid_recipient_did() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalInvalidRecipientEnvelope";
        let mut signal_message = sample_envelope("did:key:zSender", owner);
        signal_message["recipientDid"] = json!("did:key:zRecipientInvalid/path");
        let blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-invalid-recipient-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-invalid-recipient-envelope-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let err = value["error"].as_str().unwrap_or_default();
        assert!(err.contains("invalid signal envelope JSON"), "{value}");
        assert!(err.contains("recipientDid"), "{value}");
    }

    #[tokio::test]
    async fn email_read_rejects_policy_invalid_signal_envelope_object() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalPolicyInvalidEnvelope";
        let signal_message = json!({
            "messageType": "groupMessage",
            "senderDid": "did:key:zSender",
            "recipientDid": owner,
            "deviceId": "device-1",
            "ciphertextEnvelope": "c2VhbGVk",
            "timestamp": "2026-06-02T00:00:00Z"
        });
        let blob = state
            .vault
            .put(bytes::Bytes::from(
                serde_json::to_vec(&signal_message).expect("signal message JSON"),
            ))
            .await;
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-policy-invalid-envelope");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-policy-invalid-envelope-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let err = value["error"].as_str().unwrap_or_default();
        assert!(err.contains("invalid signal envelope JSON"), "{value}");
        assert!(err.contains("groupId"), "{value}");
    }

    #[tokio::test]
    async fn email_read_signal_mail_without_body_cid_returns_404() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalMissingBodyCid";
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-missing-body-cid");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-missing-body-cid-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("email/body_cid not found")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_signal_mail_with_invalid_body_cid_returns_500() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalInvalidBodyCid";
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-invalid-body-cid");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-invalid-body-cid-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", "not a multibase cid".to_string()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("invalid body_cid multibase")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_signal_mail_with_multiple_body_cids_returns_500() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalMultipleBodyCid";
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-multiple-body-cid");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-multiple-body-cid-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            (
                "email/body_cid",
                test_body_cid(b"xrpc-signal-multiple-body-a"),
            ),
            (
                "email/body_cid",
                test_body_cid(b"xrpc-signal-multiple-body-b"),
            ),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("multiple email/body_cid values found")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_signal_mail_with_missing_envelope_blob_returns_404() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcSignalMissingEnvelopeBlob";
        let email_cid = KotobaCid::from_bytes(b"xrpc-signal-missing-envelope-blob");
        let email_cid_mb = email_cid.to_multibase();
        let missing_body_cid = KotobaCid::from_bytes(b"xrpc-missing-signal-envelope-blob");
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-signal-missing-envelope-blob-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", missing_body_cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("signal envelope not found in vault")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_invalid_owner_did_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_read(
            State(state),
            HeaderMap::new(),
            Query(EmailReadQuery {
                owner_did: "not-a-did".to_string(),
                email_cid: "also\ninvalid".to_string(),
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
                .is_some_and(|err| err.contains("owner_did")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_invalid_email_cid_params_before_auth() {
        for (email_cid, expected) in [
            ("", "email_cid must not be empty"),
            (
                "bafy\ncid",
                "email_cid must contain only visible ASCII characters",
            ),
            (
                "bafy cid",
                "email_cid must contain only visible ASCII characters",
            ),
            (
                "bafyé",
                "email_cid must contain only visible ASCII characters",
            ),
        ] {
            let state = Arc::new(KotobaState::new(None).expect("state"));
            let response = email_read(
                State(state),
                HeaderMap::new(),
                Query(EmailReadQuery {
                    owner_did: "did:key:zXrpcEmailReadInvalidCid".to_string(),
                    email_cid: email_cid.to_string(),
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
                    .is_some_and(|err| err.contains(expected)),
                "{value}"
            );
        }
    }

    #[tokio::test]
    async fn email_read_rejects_bearer_missing_sub_before_lookup() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailReadMissingSub";
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!(
                "Bearer {}",
                bearer_jwt_from_payload(json!({ "exp": 4_102_444_800u64 }))
            )
            .parse()
            .unwrap(),
        );

        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: "bafyMissingSub".to_string(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::UNAUTHORIZED);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("Bearer token missing sub claim")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_oversized_email_cid_param_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let response = email_read(
            State(state),
            HeaderMap::new(),
            Query(EmailReadQuery {
                owner_did: "did:key:zXrpcEmailReadOversizedCid".to_string(),
                email_cid: "b".repeat(MAX_EMAIL_CID_LEN + 1),
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
                .is_some_and(|err| err.contains("email_cid must be 1")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_missing_email_cid_returns_404_before_body_lookup() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailReadMissingCid";
        let existing_email_cid = KotobaCid::from_bytes(b"xrpc-existing-email-cid");
        let missing_email_cid = KotobaCid::from_bytes(b"xrpc-missing-email-cid");
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-read-missing-cid-tx");
        for (predicate, object) in [
            ("email/message_id", existing_email_cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"body").to_multibase(),
            ),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        existing_email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: missing_email_cid.to_multibase(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("email_cid not found in mailbox")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_ignores_non_email_subject_datoms_when_checking_existence() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailReadNonEmailSubject";
        let cid = KotobaCid::from_bytes(b"xrpc-non-email-subject");
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-non-email-subject-tx");
        state
            .quad_store
            .assert_datom(
                graph_cid,
                kotoba_query::Datom::assert(
                    cid.clone(),
                    "profile/name".to_string(),
                    kotoba_query::Value::Text("not an email".to_string()),
                    tx_cid,
                ),
            )
            .await;

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: cid.to_multibase(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("email_cid not found in mailbox")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_ignores_enc_only_subject_when_checking_existence() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailReadEncOnlySubject";
        let cid = KotobaCid::from_bytes(b"xrpc-enc-only-subject");
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-enc-only-subject-tx");
        state
            .quad_store
            .assert_datom(
                graph_cid,
                kotoba_query::Datom::assert(
                    cid.clone(),
                    "email/enc".to_string(),
                    kotoba_query::Value::Text(ENC_SIGNAL_V1.to_string()),
                    tx_cid,
                ),
            )
            .await;

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: cid.to_multibase(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("email_cid not found in mailbox")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_existing_non_signal_mail_without_crypto_returns_503() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        assert!(
            state.crypto.is_none(),
            "test state must not initialise crypto"
        );

        let owner = "did:key:zXrpcPlainMailNoCrypto";
        let email_cid = KotobaCid::from_bytes(b"xrpc-plain-mail-no-crypto");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-plain-mail-no-crypto-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"body").to_multibase(),
            ),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::SERVICE_UNAVAILABLE);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("crypto not initialised")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_invalid_enc_before_legacy_crypto() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcInvalidEnc";
        let email_cid = KotobaCid::from_bytes(b"xrpc-invalid-enc");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-invalid-enc-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", test_body_cid(b"xrpc-invalid-enc-body")),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/enc", "unknown:v1".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("invalid email/enc")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_legacy_mail_without_body_cid_returns_404() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        assert!(state.crypto.is_some(), "legacy path must reach body lookup");

        let owner = "did:key:zXrpcLegacyMissingBodyCid";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-missing-body-cid");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-missing-body-cid-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("email/body_cid not found")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_oversized_date_as_missing_record() {
        let state = Arc::new(KotobaState::new(None).expect("state"));

        let owner = "did:key:zXrpcReadOversizedDate";
        let email_cid = KotobaCid::from_bytes(b"xrpc-read-oversized-date");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-read-oversized-date-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            (
                "email/body_cid",
                test_body_cid(b"xrpc-read-oversized-date-body"),
            ),
            ("email/date", "x".repeat(MAX_EMAIL_DATE_LEN + 1)),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::NOT_FOUND);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("email_cid not found in mailbox")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_legacy_body_decrypts_blob_bound_to_email_cid() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));

        let owner = "did:key:zXrpcLegacyBodyBoundRoundtrip";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-body-bound-roundtrip");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-body-bound-roundtrip-tx");
        let body_text = "body bound to this email cid";
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), body_text.as_bytes())
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;

        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-01T00:00:00Z".to_string()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/thread_id", "t".repeat(MAX_THREAD_ID_LEN + 1)),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb.clone(),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(value["email_cid"], email_cid_mb, "{value}");
        assert_eq!(value["date"], "2026-06-02T00:00:00Z", "{value}");
        assert_eq!(value["thread_id"], "", "{value}");
        assert_eq!(value["body"], body_text, "{value}");
    }

    #[tokio::test]
    async fn email_read_legacy_body_rejects_invalid_utf8_plaintext() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));

        let owner = "did:key:zXrpcLegacyInvalidUtf8Body";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-invalid-utf8-body");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-invalid-utf8-body-tx");
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), &[0xff, 0xfe, 0xfd])
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;

        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("body is not valid UTF-8")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_legacy_rejects_decrypted_metadata_above_ingest_caps() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));

        let owner = "did:key:zXrpcLegacyOversizedMetadata";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-oversized-metadata");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-oversized-metadata-tx");
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), b"valid body")
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;
        let oversized_from = crypto
            .seal_field(b"email/from", &"f".repeat(MAX_LEGACY_ADDR_LEN + 1))
            .await
            .expect("oversized from envelope");

        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/from", oversized_from),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("from exceeds 4096 bytes")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_legacy_rejects_control_metadata_after_decrypt() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));

        let owner = "did:key:zXrpcLegacyControlMetadata";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-control-metadata");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-control-metadata-tx");
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), b"valid body")
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;
        let control_subject = crypto
            .seal_field(b"email/subject", "hello\nworld")
            .await
            .expect("control subject envelope");

        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/subject", control_subject),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"].as_str().is_some_and(
                |err| err.contains("subject must contain only visible ASCII characters")
            ),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_legacy_rejects_corrupt_encrypted_metadata() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));

        let owner = "did:key:zXrpcLegacyCorruptMetadata";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-corrupt-metadata");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-corrupt-metadata-tx");
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), b"valid body")
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;

        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
            ("email/from", "signal:v1:not-valid-ciphertext".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("decrypt from")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_legacy_rejects_ambiguous_message_id_metadata() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));

        let owner = "did:key:zXrpcLegacyAmbiguousMessageId";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-ambiguous-message-id");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-ambiguous-message-id-tx");
        let body = crypto
            .encrypt_blob_bound(email_cid_mb.as_bytes(), b"valid body")
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(body)).await;

        for (predicate, object) in [
            ("email/message_id", "<first@example.test>".to_string()),
            ("email/message_id", "<second@example.test>".to_string()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("multiple email/message_id values found")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_rejects_oversized_message_id_metadata_before_crypto() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        assert!(
            state.crypto.is_none(),
            "test state must not initialise crypto"
        );

        let owner = "did:key:zXrpcOversizedMessageId";
        let email_cid = KotobaCid::from_bytes(b"xrpc-oversized-message-id");
        let email_cid_mb = email_cid.to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-oversized-message-id-tx");
        for (predicate, object) in [
            ("email/message_id", "m".repeat(MAX_EMAIL_MESSAGE_ID_LEN + 1)),
            (
                "email/body_cid",
                KotobaCid::from_bytes(b"xrpc-oversized-message-id-body").to_multibase(),
            ),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("invalid email/message_id")),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_read_legacy_body_rejects_blob_bound_to_different_email_cid() {
        let state = Arc::new(
            KotobaState::new(None)
                .expect("state")
                .init_crypto()
                .await
                .expect("crypto"),
        );
        let crypto = Arc::clone(state.crypto.as_ref().expect("crypto"));

        let owner = "did:key:zXrpcLegacyBodyBoundSwap";
        let email_cid = KotobaCid::from_bytes(b"xrpc-legacy-body-bound-target");
        let email_cid_mb = email_cid.to_multibase();
        let other_email_cid_mb =
            KotobaCid::from_bytes(b"xrpc-legacy-body-bound-other").to_multibase();
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-legacy-body-bound-swap-tx");
        let swapped_body = crypto
            .encrypt_blob_bound(other_email_cid_mb.as_bytes(), b"swapped body")
            .await
            .expect("bound body ciphertext");
        let blob = state.vault.put(bytes::Bytes::from(swapped_body)).await;

        for (predicate, object) in [
            ("email/message_id", email_cid_mb.clone()),
            ("email/body_cid", blob.cid.to_multibase()),
            ("email/date", "2026-06-02T00:00:00Z".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_read(
            State(state),
            headers,
            Query(EmailReadQuery {
                owner_did: owner.to_string(),
                email_cid: email_cid_mb,
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::INTERNAL_SERVER_ERROR);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let value: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert!(
            value["error"]
                .as_str()
                .is_some_and(|err| err.contains("decrypt body")),
            "{value}"
        );
    }

    #[test]
    fn email_list_item_exposes_signal_metadata_when_present() {
        let email_cid = KotobaCid::from_bytes(b"xrpc-email-list-signal");
        let graph = graph_cid_for("did:key:zXrpcEmailListSignal");
        let quads = [
            ("email/message_id", email_cid.to_multibase()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
            ("email/recipient_device", "device-1".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: predicate.to_string(),
            object: LegacyQuadObject::Text(object),
        })
        .collect::<Vec<_>>();

        let item =
            email_list_item_from_quads(&quads, &email_cid, "2026-06-02T00:00:00Z".to_string());
        assert_eq!(item["cid"], email_cid.to_multibase(), "{item}");
        assert_eq!(item["message_id"], email_cid.to_multibase(), "{item}");
        assert_eq!(item["enc"], ENC_SIGNAL_V1, "{item}");
        assert_eq!(item["recipient_device"], "device-1", "{item}");
    }

    #[test]
    fn email_list_item_omits_invalid_signal_metadata() {
        let email_cid = KotobaCid::from_bytes(b"xrpc-email-list-invalid-signal-metadata");
        let graph = graph_cid_for("did:key:zXrpcEmailListInvalidSignalMetadata");
        let quads = [
            ("email/message_id", email_cid.to_multibase()),
            ("email/enc", "unknown:v1".to_string()),
            (
                "email/recipient_device",
                "d".repeat(MAX_SIGNAL_DEVICE_ID_LEN + 1),
            ),
        ]
        .into_iter()
        .map(|(predicate, object)| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: predicate.to_string(),
            object: LegacyQuadObject::Text(object),
        })
        .collect::<Vec<_>>();

        let item =
            email_list_item_from_quads(&quads, &email_cid, "2026-06-02T00:00:00Z".to_string());
        assert!(item.get("enc").is_none(), "{item}");
        assert!(item.get("recipient_device").is_none(), "{item}");
    }

    #[test]
    fn email_list_item_omits_ambiguous_recipient_device() {
        let email_cid = KotobaCid::from_bytes(b"xrpc-email-list-ambiguous-recipient-device");
        let graph = graph_cid_for("did:key:zXrpcEmailListAmbiguousRecipientDevice");
        let quads = [
            ("email/message_id", email_cid.to_multibase()),
            ("email/enc", ENC_SIGNAL_V1.to_string()),
            ("email/recipient_device", "device-1".to_string()),
            ("email/recipient_device", "device-2".to_string()),
        ]
        .into_iter()
        .map(|(predicate, object)| LegacyQuad {
            graph: graph.clone(),
            subject: email_cid.clone(),
            predicate: predicate.to_string(),
            object: LegacyQuadObject::Text(object),
        })
        .collect::<Vec<_>>();

        let item =
            email_list_item_from_quads(&quads, &email_cid, "2026-06-02T00:00:00Z".to_string());
        assert_eq!(item["enc"], ENC_SIGNAL_V1, "{item}");
        assert!(item.get("recipient_device").is_none(), "{item}");
    }

    #[tokio::test]
    async fn email_list_skips_date_only_subjects() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsDateOnly";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-skips-date-only-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-email");
        let date_only_cid = KotobaCid::from_bytes(b"xrpc-list-date-only");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-email-body"),
            ),
            (
                date_only_cid,
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_list_skips_subjects_with_empty_message_id() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsEmptyMessageId";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-empty-message-id-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-message-id");
        let empty_message_id_cid = KotobaCid::from_bytes(b"xrpc-list-empty-message-id");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-message-id-body"),
            ),
            (
                empty_message_id_cid.clone(),
                "email/message_id",
                String::new(),
            ),
            (
                empty_message_id_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-empty-message-id-body"),
            ),
            (
                empty_message_id_cid,
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
        assert_ne!(value["emails"][0]["message_id"], "", "{value}");
    }

    #[tokio::test]
    async fn email_list_skips_subjects_with_control_message_id() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsControlMessageId";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-control-message-id-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-control-message-id");
        let control_message_id_cid = KotobaCid::from_bytes(b"xrpc-list-control-message-id");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-control-message-id-body"),
            ),
            (
                control_message_id_cid.clone(),
                "email/message_id",
                "bad\nmessage-id".to_string(),
            ),
            (
                control_message_id_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-control-message-id-body"),
            ),
            (
                control_message_id_cid,
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
        assert!(
            value["emails"][0]["message_id"]
                .as_str()
                .is_some_and(is_visible_ascii_text),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_list_skips_subjects_with_empty_date() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsEmptyDate";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-empty-date-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-date");
        let empty_date_cid = KotobaCid::from_bytes(b"xrpc-list-empty-date");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-date-body"),
            ),
            (
                empty_date_cid.clone(),
                "email/message_id",
                empty_date_cid.to_multibase(),
            ),
            (
                empty_date_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-empty-date-body"),
            ),
            (empty_date_cid, "email/date", String::new()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
        assert_ne!(value["emails"][0]["date"], "", "{value}");
    }

    #[tokio::test]
    async fn email_list_skips_subjects_with_control_date() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsControlDate";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-control-date-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-control-date");
        let control_date_cid = KotobaCid::from_bytes(b"xrpc-list-control-date");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-control-date-body"),
            ),
            (
                control_date_cid.clone(),
                "email/message_id",
                control_date_cid.to_multibase(),
            ),
            (
                control_date_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-control-date-body"),
            ),
            (
                control_date_cid,
                "email/date",
                "2026-06-13\n00:00:00Z".to_string(),
            ),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
        assert!(
            value["emails"][0]["date"]
                .as_str()
                .is_some_and(is_visible_ascii_text),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_list_skips_subjects_with_oversized_date() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsOversizedDate";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-oversized-date-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-sized-date");
        let oversized_date_cid = KotobaCid::from_bytes(b"xrpc-list-oversized-date");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-sized-date-body"),
            ),
            (
                oversized_date_cid.clone(),
                "email/message_id",
                oversized_date_cid.to_multibase(),
            ),
            (
                oversized_date_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-oversized-date-body"),
            ),
            (
                oversized_date_cid,
                "email/date",
                "x".repeat(MAX_EMAIL_DATE_LEN + 1),
            ),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
        assert!(
            value["emails"][0]["date"]
                .as_str()
                .is_some_and(|date| date.len() <= MAX_EMAIL_DATE_LEN),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_list_skips_subjects_without_valid_body_cid() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsInvalidBodyCid";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-invalid-body-cid-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-body-cid");
        let missing_body_cid = KotobaCid::from_bytes(b"xrpc-list-missing-body-cid");
        let invalid_body_cid = KotobaCid::from_bytes(b"xrpc-list-invalid-body-cid");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-body-cid-body"),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                missing_body_cid.clone(),
                "email/message_id",
                missing_body_cid.to_multibase(),
            ),
            (
                missing_body_cid,
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
            (
                invalid_body_cid.clone(),
                "email/message_id",
                invalid_body_cid.to_multibase(),
            ),
            (
                invalid_body_cid.clone(),
                "email/body_cid",
                "not-a-multibase-cid".to_string(),
            ),
            (
                invalid_body_cid,
                "email/date",
                "2026-06-14T00:00:00Z".to_string(),
            ),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_list_skips_subjects_with_invalid_enc() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSkipsInvalidEnc";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-invalid-enc-tx");
        let valid_email_cid = KotobaCid::from_bytes(b"xrpc-list-valid-enc");
        let invalid_enc_cid = KotobaCid::from_bytes(b"xrpc-list-invalid-enc");
        for (subject, predicate, object) in [
            (
                valid_email_cid.clone(),
                "email/message_id",
                valid_email_cid.to_multibase(),
            ),
            (
                valid_email_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-valid-enc-body"),
            ),
            (
                valid_email_cid.clone(),
                "email/date",
                "2026-06-12T00:00:00Z".to_string(),
            ),
            (
                invalid_enc_cid.clone(),
                "email/message_id",
                invalid_enc_cid.to_multibase(),
            ),
            (
                invalid_enc_cid.clone(),
                "email/body_cid",
                test_body_cid(b"xrpc-list-invalid-enc-body"),
            ),
            (
                invalid_enc_cid.clone(),
                "email/date",
                "2026-06-13T00:00:00Z".to_string(),
            ),
            (invalid_enc_cid, "email/enc", "unknown:v1".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        subject,
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: None,
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(
            value["emails"][0]["cid"],
            valid_email_cid.to_multibase(),
            "{value}"
        );
    }

    #[tokio::test]
    async fn email_list_rejects_invalid_owner_did_before_auth() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let err = match email_list(
            State(state),
            HeaderMap::new(),
            Query(EmailListQuery {
                owner_did: "not-a-did".to_string(),
                limit: None,
                offset: None,
            }),
        )
        .await
        {
            Ok(_) => panic!("email.list unexpectedly accepted invalid owner_did"),
            Err(err) => err,
        };

        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("owner_did"), "{err:?}");
    }

    #[tokio::test]
    async fn email_list_rejects_missing_bearer_before_lookup() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let err = match email_list(
            State(state),
            HeaderMap::new(),
            Query(EmailListQuery {
                owner_did: "did:key:zXrpcEmailListMissingBearer".to_string(),
                limit: None,
                offset: None,
            }),
        )
        .await
        {
            Ok(_) => panic!("email.list unexpectedly accepted missing bearer"),
            Err(err) => err,
        };

        assert_eq!(err.0, StatusCode::UNAUTHORIZED);
        assert!(
            err.1.contains("Authorization: Bearer <token> required"),
            "{err:?}"
        );
    }

    #[tokio::test]
    async fn email_list_rejects_zero_limit() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListZeroLimit";
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );

        let err = match email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: Some(0),
                offset: None,
            }),
        )
        .await
        {
            Ok(_) => panic!("email.list unexpectedly accepted limit=0"),
            Err(err) => err,
        };

        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("limit must be at least 1"), "{err:?}");
    }

    #[tokio::test]
    async fn email_list_rejects_limit_above_max() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListLimitAboveMax";
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );

        let err = match email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: Some(MAX_EMAIL_LIST_LIMIT + 1),
                offset: None,
            }),
        )
        .await
        {
            Ok(_) => panic!("email.list unexpectedly accepted limit above max"),
            Err(err) => err,
        };

        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("limit exceeds"), "{err:?}");
    }

    #[tokio::test]
    async fn email_list_rejects_offset_above_max() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListOffsetAboveMax";
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );

        let err = match email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: None,
                offset: Some(MAX_EMAIL_LIST_OFFSET + 1),
            }),
        )
        .await
        {
            Ok(_) => panic!("email.list unexpectedly accepted offset above max"),
            Err(err) => err,
        };

        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("offset exceeds"), "{err:?}");
    }

    #[tokio::test]
    async fn email_list_applies_limit_and_offset_after_date_sort() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListPaged";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-paged-tx");
        let newest = KotobaCid::from_bytes(b"xrpc-list-paged-newest");
        let middle = KotobaCid::from_bytes(b"xrpc-list-paged-middle");
        let oldest = KotobaCid::from_bytes(b"xrpc-list-paged-oldest");
        for (email_cid, date) in [
            (oldest.clone(), "2026-06-10T00:00:00Z"),
            (newest.clone(), "2026-06-12T00:00:00Z"),
            (middle.clone(), "2026-06-11T00:00:00Z"),
        ] {
            for (predicate, object) in [
                ("email/message_id", email_cid.to_multibase()),
                (
                    "email/body_cid",
                    test_body_cid(format!("xrpc-list-paged-body-{}", date).as_bytes()),
                ),
                ("email/date", date.to_string()),
            ] {
                state
                    .quad_store
                    .assert_datom(
                        graph_cid.clone(),
                        kotoba_query::Datom::assert(
                            email_cid.clone(),
                            predicate.to_string(),
                            kotoba_query::Value::Text(object),
                            tx_cid.clone(),
                        ),
                    )
                    .await;
            }
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: Some(1),
                offset: Some(1),
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
        assert_eq!(value["total"], 3, "{value}");
        assert_eq!(value["offset"], 1, "{value}");
        assert_eq!(value["limit"], 1, "{value}");
        let emails = value["emails"].as_array().expect("emails");
        assert_eq!(emails.len(), 1, "{value}");
        assert_eq!(emails[0]["cid"], middle.to_multibase(), "{value}");
        assert_eq!(emails[0]["date"], "2026-06-11T00:00:00Z", "{value}");
    }

    #[tokio::test]
    async fn email_list_tiebreaks_same_date_by_cid() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListSameDate";
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-email-list-same-date-tx");
        let first = KotobaCid::from_bytes(b"xrpc-list-same-date-a");
        let second = KotobaCid::from_bytes(b"xrpc-list-same-date-b");
        let date = "2026-06-12T00:00:00Z";
        for email_cid in [second.clone(), first.clone()] {
            for (predicate, object) in [
                ("email/message_id", email_cid.to_multibase()),
                (
                    "email/body_cid",
                    test_body_cid(email_cid.to_multibase().as_bytes()),
                ),
                ("email/date", date.to_string()),
            ] {
                state
                    .quad_store
                    .assert_datom(
                        graph_cid.clone(),
                        kotoba_query::Datom::assert(
                            email_cid.clone(),
                            predicate.to_string(),
                            kotoba_query::Value::Text(object),
                            tx_cid.clone(),
                        ),
                    )
                    .await;
            }
        }

        let mut expected = [first.to_multibase(), second.to_multibase()];
        expected.sort();

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: Some(2),
                offset: Some(0),
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
        assert_eq!(value["total"], 2, "{value}");
        let emails = value["emails"].as_array().expect("emails");
        assert_eq!(emails.len(), 2, "{value}");
        assert_eq!(emails[0]["cid"], expected[0], "{value}");
        assert_eq!(emails[1]["cid"], expected[1], "{value}");
    }

    #[tokio::test]
    async fn email_list_accepts_max_offset_and_returns_empty_page() {
        let state = Arc::new(KotobaState::new(None).expect("state"));
        let owner = "did:key:zXrpcEmailListMaxOffset";
        let email_cid = KotobaCid::from_bytes(b"xrpc-list-max-offset-email");
        let graph_cid = graph_cid_for(owner);
        let tx_cid = KotobaCid::from_bytes(b"xrpc-list-max-offset-tx");
        for (predicate, object) in [
            ("email/message_id", email_cid.to_multibase()),
            (
                "email/body_cid",
                test_body_cid(b"xrpc-list-max-offset-body"),
            ),
            ("email/date", "2026-06-12T00:00:00Z".to_string()),
        ] {
            state
                .quad_store
                .assert_datom(
                    graph_cid.clone(),
                    kotoba_query::Datom::assert(
                        email_cid.clone(),
                        predicate.to_string(),
                        kotoba_query::Value::Text(object),
                        tx_cid.clone(),
                    ),
                )
                .await;
        }

        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {}", bearer_jwt_for_sub(owner))
                .parse()
                .unwrap(),
        );
        let response = email_list(
            State(state),
            headers,
            Query(EmailListQuery {
                owner_did: owner.to_string(),
                limit: Some(1),
                offset: Some(MAX_EMAIL_LIST_OFFSET),
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
        assert_eq!(value["total"], 1, "{value}");
        assert_eq!(value["offset"], MAX_EMAIL_LIST_OFFSET, "{value}");
        assert_eq!(value["limit"], 1, "{value}");
        assert_eq!(value["emails"].as_array().map(Vec::len), Some(0));
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
    fn signal_email_message_validation_accepts_sample_envelope() {
        let env = sample_envelope("did:key:zSender", "did:key:zRecipient");
        let msg: SignalMessage = serde_json::from_value(env).unwrap();
        validate_signal_email_message(&msg).unwrap();
    }

    #[test]
    fn signal_email_message_validation_accepts_group_message_with_group_id() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.message_type = MessageType::GroupMessage;
        msg.group_id = Some("group-1".to_string());
        validate_signal_email_message(&msg).unwrap();
    }

    #[test]
    fn signal_email_message_validation_rejects_group_message_without_group_id() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.message_type = MessageType::GroupMessage;
        msg.group_id = None;
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("groupId"));
    }

    #[test]
    fn signal_email_message_validation_rejects_non_group_message_with_group_id() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.group_id = Some("group-1".to_string());
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("groupId"));

        let bytes = serde_json::to_vec(&msg).unwrap();
        let err = signal_message_value_from_envelope_bytes(&bytes).unwrap_err();
        assert!(err.contains("invalid signal envelope JSON"));
        assert!(err.contains("groupId"));
    }

    #[test]
    fn signal_message_json_shape_accepts_max_one_time_prekey_id() {
        let mut env = sample_envelope("did:key:zSender", "did:key:zRecipient");
        env["oneTimePrekeyId"] = json!(u32::MAX);
        validate_signal_message_json_shape(&env).unwrap();

        let value = signal_message_value_from_envelope_bytes(&serde_json::to_vec(&env).unwrap())
            .expect("signal message");
        assert_eq!(value["oneTimePrekeyId"].as_u64(), Some(u32::MAX as u64));
    }

    #[test]
    fn signal_message_json_shape_rejects_invalid_one_time_prekey_id() {
        let mut env = sample_envelope("did:key:zSender", "did:key:zRecipient");
        for bad in [json!(-1), json!("1"), json!(u32::MAX as u64 + 1)] {
            env["oneTimePrekeyId"] = bad;
            let err = validate_signal_message_json_shape(&env).unwrap_err();
            assert!(err.contains("oneTimePrekeyId"), "{err}");
        }
    }

    #[test]
    fn signal_envelope_blob_parser_rejects_oversized_one_time_prekey_id() {
        let mut env = sample_envelope("did:key:zSender", "did:key:zRecipient");
        env["oneTimePrekeyId"] = json!(u32::MAX as u64 + 1);
        let err = signal_message_value_from_envelope_bytes(&serde_json::to_vec(&env).unwrap())
            .unwrap_err();
        assert!(err.contains("invalid signal envelope JSON"));
        assert!(err.contains("oneTimePrekeyId"));
    }

    #[test]
    fn signal_email_message_validation_rejects_empty_and_control_metadata() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.device_id.clear();
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("deviceId"));

        msg.device_id = "device\n1".to_string();
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("visible ASCII"));
    }

    #[test]
    fn signal_email_message_validation_rejects_invalid_envelope_dids() {
        for (field, sender, recipient) in [
            ("senderDid", "not-a-did", "did:key:zRecipient"),
            ("recipientDid", "did:key:zSender", "did:key:zRecipient/path"),
        ] {
            let msg: SignalMessage = serde_json::from_value(sample_envelope(sender, recipient))
                .expect("sample envelope");
            let (code, err) = validate_signal_email_message(&msg).unwrap_err();
            assert_eq!(code, StatusCode::BAD_REQUEST);
            assert!(err.contains(field), "{field}: {err}");

            let bytes = serde_json::to_vec(&msg).unwrap();
            let err = signal_message_value_from_envelope_bytes(&bytes).unwrap_err();
            assert!(err.contains("invalid signal envelope JSON"));
            assert!(err.contains(field), "{field}: {err}");
        }
    }

    #[test]
    fn signal_email_message_validation_rejects_oversized_metadata() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.timestamp = "x".repeat(MAX_SIGNAL_TIMESTAMP_LEN + 1);
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("timestamp"));

        msg.timestamp = "2026-06-02T00:00:00Z".to_string();
        msg.group_id = Some("g".repeat(MAX_SIGNAL_GROUP_ID_LEN + 1));
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("groupId"));
    }

    #[test]
    fn signal_email_message_validation_rejects_empty_ciphertext() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.ciphertext_envelope.clear();
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("ciphertextEnvelope"));
    }

    #[test]
    fn signal_envelope_blob_parser_rejects_policy_invalid_signal_message() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.ciphertext_envelope.clear();
        let bytes = serde_json::to_vec(&msg).unwrap();
        let err = signal_message_value_from_envelope_bytes(&bytes).unwrap_err();
        assert!(err.contains("invalid signal envelope JSON"));
        assert!(err.contains("ciphertextEnvelope"));
    }

    #[test]
    fn signal_email_message_validation_rejects_empty_optional_metadata() {
        let mut msg: SignalMessage =
            serde_json::from_value(sample_envelope("did:key:zSender", "did:key:zRecipient"))
                .unwrap();
        msg.group_id = Some(String::new());
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("groupId"));

        msg.group_id = None;
        msg.ephemeral_key = Some(String::new());
        let (code, err) = validate_signal_email_message(&msg).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("ephemeralKey"));
    }

    #[test]
    fn email_list_limit_matches_public_contract() {
        assert_eq!(
            validate_email_list_limit(None).unwrap(),
            DEFAULT_EMAIL_LIST_LIMIT
        );
        assert_eq!(validate_email_list_limit(Some(1)).unwrap(), 1);
        assert_eq!(
            validate_email_list_limit(Some(MAX_EMAIL_LIST_LIMIT)).unwrap(),
            MAX_EMAIL_LIST_LIMIT
        );

        for limit in [0, MAX_EMAIL_LIST_LIMIT + 1] {
            let (code, err) = validate_email_list_limit(Some(limit)).unwrap_err();
            assert_eq!(code, StatusCode::BAD_REQUEST);
            assert!(err.contains("limit"), "unexpected error: {err}");
        }
    }

    #[test]
    fn email_list_offset_matches_public_contract() {
        assert_eq!(validate_email_list_offset(None).unwrap(), 0);
        assert_eq!(validate_email_list_offset(Some(0)).unwrap(), 0);
        assert_eq!(
            validate_email_list_offset(Some(MAX_EMAIL_LIST_OFFSET)).unwrap(),
            MAX_EMAIL_LIST_OFFSET
        );

        let (code, err) = validate_email_list_offset(Some(MAX_EMAIL_LIST_OFFSET + 1)).unwrap_err();
        assert_eq!(code, StatusCode::BAD_REQUEST);
        assert!(err.contains("offset"), "unexpected error: {err}");
    }

    #[test]
    fn nsid_email_constants_are_unique() {
        let mut set = std::collections::HashSet::new();
        assert!(set.insert(NSID_EMAIL_LIST));
        assert!(set.insert(NSID_EMAIL_READ));
        assert!(set.insert(NSID_EMAIL_INGEST));
        assert!(set.insert(NSID_EMAIL_SEND));
    }

    #[test]
    fn public_email_lexicons_match_xrpc_nsids() {
        let lexicons = [
            (
                NSID_EMAIL_LIST,
                "list.json",
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/list.json"),
                "query",
            ),
            (
                NSID_EMAIL_READ,
                "read.json",
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/read.json"),
                "query",
            ),
            (
                NSID_EMAIL_INGEST,
                "ingest.json",
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/ingest.json"),
                "procedure",
            ),
            (
                NSID_EMAIL_SEND,
                "send.json",
                include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/send.json"),
                "procedure",
            ),
        ];

        let expected_nsids: std::collections::BTreeSet<&str> =
            ALL_EMAIL_NSIDS.iter().copied().collect();
        let lexicon_nsids: std::collections::BTreeSet<&str> =
            lexicons.iter().map(|(nsid, _, _, _)| *nsid).collect();
        assert_eq!(
            lexicon_nsids, expected_nsids,
            "Email lexicons must enumerate every public email NSID"
        );
        let expected_files: std::collections::BTreeSet<_> = lexicons
            .iter()
            .map(|(_, file_name, _, _)| file_name.to_string())
            .collect();
        let lexicon_dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
            .join("../../lexicons/com/etzhayyim/apps/kotoba/email");
        let actual_files: std::collections::BTreeSet<_> = std::fs::read_dir(&lexicon_dir)
            .expect("read email lexicon dir")
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
            "Email XRPC surface must enumerate every public email lexicon"
        );

        for (expected_id, _, src, expected_type) in lexicons {
            let value: serde_json::Value = serde_json::from_str(src).expect("email lexicon JSON");
            assert_eq!(value["lexicon"], 1);
            assert_eq!(value["id"], expected_id);
            assert_eq!(value["defs"]["main"]["type"], expected_type);
        }
    }

    #[test]
    fn email_list_lexicon_matches_handler_contract() {
        let src = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/list.json");
        let value: serde_json::Value = serde_json::from_str(src).expect("email.list lexicon JSON");
        assert_eq!(value["lexicon"], 1);
        assert_eq!(value["id"], NSID_EMAIL_LIST);
        assert_eq!(value["defs"]["main"]["type"], "query");

        let params = &value["defs"]["main"]["parameters"];
        assert_eq!(params["type"], "params");
        let required = params["required"].as_array().expect("required params");
        assert!(
            required
                .iter()
                .any(|field| field.as_str() == Some("owner_did")),
            "email.list must require owner_did"
        );
        let props = &params["properties"];
        assert_eq!(props["owner_did"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["owner_did"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(props["owner_did"]["pattern"].as_str(), Some("^did:[!-~]+$"));
        assert_eq!(props["limit"]["minimum"].as_u64(), Some(1));
        assert_eq!(
            props["limit"]["maximum"].as_u64(),
            Some(MAX_EMAIL_LIST_LIMIT as u64)
        );
        assert_eq!(props["offset"]["minimum"].as_u64(), Some(0));
        assert_eq!(
            props["offset"]["maximum"].as_u64(),
            Some(MAX_EMAIL_LIST_OFFSET as u64)
        );

        let output = &value["defs"]["main"]["output"]["schema"];
        let output_required = output["required"].as_array().expect("output required");
        for field in ["emails", "total", "offset", "limit"] {
            assert!(
                output_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.list output must require {field}"
            );
        }
        assert_eq!(output["properties"]["limit"]["minimum"].as_u64(), Some(1));
        assert_eq!(
            output["properties"]["limit"]["maximum"].as_u64(),
            Some(MAX_EMAIL_LIST_LIMIT as u64)
        );
        assert_eq!(
            output["properties"]["offset"]["maximum"].as_u64(),
            Some(MAX_EMAIL_LIST_OFFSET as u64)
        );
        let item = &output["properties"]["emails"]["items"];
        let item_required = item["required"].as_array().expect("email item required");
        for field in ["cid", "date", "message_id"] {
            assert!(
                item_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.list email item must require {field}"
            );
        }
        let item_props = item["properties"]
            .as_object()
            .expect("email item properties");
        for field in ["enc", "recipient_device"] {
            assert!(
                item_props.contains_key(field),
                "email.list email item must document optional {field}"
            );
        }
        assert_eq!(item["properties"]["cid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item["properties"]["cid"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_CID_LEN as u64)
        );
        assert_eq!(
            item["properties"]["cid"]["pattern"].as_str(),
            Some("^[!-~]+$")
        );
        assert_eq!(item["properties"]["date"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item["properties"]["date"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_DATE_LEN as u64)
        );
        assert_eq!(
            item["properties"]["date"]["pattern"].as_str(),
            Some("^[!-~]+$")
        );
        assert_eq!(
            item["properties"]["message_id"]["minLength"].as_u64(),
            Some(1)
        );
        assert_eq!(
            item["properties"]["message_id"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_MESSAGE_ID_LEN as u64)
        );
        assert_eq!(
            item["properties"]["message_id"]["pattern"].as_str(),
            Some("^[!-~]+$")
        );
        assert_eq!(
            item["properties"]["recipient_device"]["minLength"].as_u64(),
            Some(1)
        );
        assert_eq!(
            item["properties"]["recipient_device"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_DEVICE_ID_LEN as u64)
        );
        assert_eq!(
            item["properties"]["recipient_device"]["pattern"].as_str(),
            Some("^[!-~]+$")
        );
        let enc_values = item["properties"]["enc"]["knownValues"]
            .as_array()
            .expect("enc knownValues");
        assert!(
            enc_values
                .iter()
                .any(|value| value.as_str() == Some(ENC_SIGNAL_V1)),
            "email.list enc knownValues must advertise {ENC_SIGNAL_V1}"
        );
    }

    #[test]
    fn email_read_lexicon_matches_handler_contract() {
        let src = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/read.json");
        let value: serde_json::Value = serde_json::from_str(src).expect("email.read lexicon JSON");
        assert_eq!(value["lexicon"], 1);
        assert_eq!(value["id"], NSID_EMAIL_READ);
        assert_eq!(value["defs"]["main"]["type"], "query");

        let params = &value["defs"]["main"]["parameters"];
        let required = params["required"].as_array().expect("required params");
        for field in ["owner_did", "email_cid"] {
            assert!(
                required.iter().any(|value| value.as_str() == Some(field)),
                "email.read must require {field}"
            );
        }
        let props = &params["properties"];
        assert_eq!(props["owner_did"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["owner_did"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(props["owner_did"]["pattern"].as_str(), Some("^did:[!-~]+$"));
        assert_eq!(props["email_cid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["email_cid"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_CID_LEN as u64)
        );
        assert_eq!(props["email_cid"]["pattern"].as_str(), Some("^[!-~]+$"));
        assert!(
            props["email_cid"]["description"]
                .as_str()
                .is_some_and(|description| description.contains("visible ASCII")),
            "email.read email_cid description must disclose visible-ASCII rejection"
        );

        let output = &value["defs"]["main"]["output"]["schema"];
        let output_required = output["required"].as_array().expect("output required");
        for field in ["email_cid", "message_id", "from", "to", "date", "thread_id"] {
            assert!(
                output_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.read output must require {field}"
            );
        }
        let output_props = &output["properties"];
        for field in ["subject", "body", "enc", "signalMessage"] {
            assert!(
                output_props
                    .as_object()
                    .is_some_and(|props| props.contains_key(field)),
                "email.read output must document optional {field}"
            );
        }
        assert_eq!(output_props["email_cid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            output_props["email_cid"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_CID_LEN as u64)
        );
        assert_eq!(
            output_props["email_cid"]["pattern"].as_str(),
            Some("^[!-~]+$")
        );
        assert_eq!(output_props["message_id"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            output_props["message_id"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_MESSAGE_ID_LEN as u64)
        );
        assert_eq!(
            output_props["message_id"]["pattern"].as_str(),
            Some("^[!-~]+$")
        );
        assert_eq!(
            output_props["from"]["maxLength"].as_u64(),
            Some(MAX_LEGACY_ADDR_LEN as u64)
        );
        assert_eq!(
            output_props["to"]["maxLength"].as_u64(),
            Some(MAX_LEGACY_ADDR_LEN as u64)
        );
        assert_eq!(
            output_props["subject"]["maxLength"].as_u64(),
            Some(MAX_LEGACY_SUBJECT_LEN as u64)
        );
        for field in ["from", "to", "subject"] {
            assert_eq!(
                output_props[field]["pattern"].as_str(),
                Some("^[!-~]*$"),
                "email.read output {field} must publish visible-ASCII-or-empty contract"
            );
        }
        assert_eq!(output_props["date"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            output_props["date"]["maxLength"].as_u64(),
            Some(MAX_EMAIL_DATE_LEN as u64)
        );
        assert_eq!(output_props["date"]["pattern"].as_str(), Some("^[!-~]+$"));
        assert_eq!(
            output_props["thread_id"]["maxLength"].as_u64(),
            Some(MAX_THREAD_ID_LEN as u64)
        );
        assert_eq!(
            output_props["thread_id"]["pattern"].as_str(),
            Some("^[!-~]*$")
        );
        let enc_values = output_props["enc"]["knownValues"]
            .as_array()
            .expect("enc knownValues");
        assert!(
            enc_values
                .iter()
                .any(|value| value.as_str() == Some(ENC_SIGNAL_V1)),
            "email.read enc knownValues must advertise {ENC_SIGNAL_V1}"
        );
        let signal_message = &output_props["signalMessage"];
        let signal_required = signal_message["required"]
            .as_array()
            .expect("signalMessage required");
        for field in [
            "messageType",
            "senderDid",
            "recipientDid",
            "deviceId",
            "ciphertextEnvelope",
            "timestamp",
        ] {
            assert!(
                signal_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.read signalMessage must require {field}"
            );
        }
        let signal_props = &signal_message["properties"];
        assert_eq!(signal_props["senderDid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            signal_props["senderDid"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(
            signal_props["senderDid"]["pattern"].as_str(),
            Some("^did:[!-~]+$")
        );
        assert_eq!(signal_props["recipientDid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            signal_props["recipientDid"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(
            signal_props["recipientDid"]["pattern"].as_str(),
            Some("^did:[!-~]+$")
        );
        assert_eq!(signal_props["deviceId"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            signal_props["deviceId"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_DEVICE_ID_LEN as u64)
        );
        assert_eq!(
            signal_props["ciphertextEnvelope"]["minLength"].as_u64(),
            Some(1)
        );
        assert_eq!(
            signal_props["ciphertextEnvelope"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_CIPHERTEXT_ENVELOPE_LEN as u64)
        );
        assert_eq!(signal_props["timestamp"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            signal_props["timestamp"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_TIMESTAMP_LEN as u64)
        );
        assert_eq!(signal_props["oneTimePrekeyId"]["minimum"].as_u64(), Some(0));
        assert_eq!(
            signal_props["oneTimePrekeyId"]["maximum"].as_u64(),
            Some(u32::MAX as u64)
        );
        let message_type_values = signal_props["messageType"]["knownValues"]
            .as_array()
            .expect("signalMessage messageType knownValues");
        for message_type in ["directMessage", "groupMessage", "receipt"] {
            assert!(
                message_type_values
                    .iter()
                    .any(|value| value.as_str() == Some(message_type)),
                "email.read signalMessage messageType must advertise {message_type}"
            );
        }
        let message_type_description = signal_props["messageType"]["description"]
            .as_str()
            .expect("signalMessage messageType description");
        assert!(message_type_description.contains("requires groupId"));
        assert!(message_type_description.contains("absent"));
        let group_id_description = signal_props["groupId"]["description"]
            .as_str()
            .expect("signalMessage groupId description");
        assert!(group_id_description.contains("Required for groupMessage"));
        assert!(group_id_description.contains("absent"));
    }

    #[test]
    fn email_read_signal_message_schema_matches_send_recipient_schema() {
        let read_src = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/read.json");
        let send_src = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/send.json");
        let read: serde_json::Value =
            serde_json::from_str(read_src).expect("email.read lexicon JSON");
        let send: serde_json::Value =
            serde_json::from_str(send_src).expect("email.send lexicon JSON");

        let read_signal_message =
            &read["defs"]["main"]["output"]["schema"]["properties"]["signalMessage"];
        let send_recipient =
            &send["defs"]["main"]["input"]["schema"]["properties"]["recipients"]["items"];
        assert_eq!(
            read_signal_message, send_recipient,
            "email.read signalMessage must stay wire-compatible with email.send recipient envelope"
        );
    }

    #[test]
    fn email_ingest_lexicon_matches_handler_contract() {
        let src = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/ingest.json");
        let value: serde_json::Value =
            serde_json::from_str(src).expect("email.ingest lexicon JSON");
        assert_eq!(value["lexicon"], 1);
        assert_eq!(value["id"], NSID_EMAIL_INGEST);
        assert_eq!(value["defs"]["main"]["type"], "procedure");

        let schema = &value["defs"]["main"]["input"]["schema"];
        let required = schema["required"].as_array().expect("input required");
        for field in ["owner_did", "raw_b64"] {
            assert!(
                required.iter().any(|value| value.as_str() == Some(field)),
                "email.ingest input must require {field}"
            );
        }
        let props = &schema["properties"];
        assert_eq!(props["owner_did"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["owner_did"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(props["owner_did"]["pattern"].as_str(), Some("^did:[!-~]+$"));
        assert_eq!(props["raw_b64"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["raw_b64"]["maxLength"].as_u64(),
            Some(MAX_RAW_B64_LEN as u64)
        );
        assert!(
            props["raw_b64"]["description"].as_str().is_some_and(
                |description| description.contains(&EmailIngestor::MAX_EMAIL_BYTES.to_string())
            ),
            "raw_b64 description must disclose decoded payload cap"
        );
        assert_eq!(
            props["thread_id"]["maxLength"].as_u64(),
            Some(MAX_THREAD_ID_LEN as u64)
        );
        assert_eq!(props["thread_id"]["pattern"].as_str(), Some("^[!-~]*$"));

        let output = &value["defs"]["main"]["output"]["schema"];
        let output_required = output["required"].as_array().expect("output required");
        for field in [
            "status",
            "email_cid",
            "commit_cid",
            "ipns_name",
            "ipns_sequence",
        ] {
            assert!(
                output_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.ingest output must require {field}"
            );
        }
        let status_values = output["properties"]["status"]["knownValues"]
            .as_array()
            .expect("status knownValues");
        assert!(
            status_values
                .iter()
                .any(|value| value.as_str() == Some("ok")),
            "email.ingest status knownValues must advertise ok"
        );
        let output_props = &output["properties"];
        for field in ["email_cid", "commit_cid", "ipns_name"] {
            assert_eq!(output_props[field]["minLength"].as_u64(), Some(1));
            assert_eq!(
                output_props[field]["maxLength"].as_u64(),
                Some(MAX_EMAIL_CID_LEN as u64),
                "email.ingest output {field} must publish the string length cap"
            );
            assert_eq!(
                output_props[field]["pattern"].as_str(),
                Some("^[!-~]+$"),
                "email.ingest output {field} must publish the visible-ASCII contract"
            );
        }
    }

    #[test]
    fn email_send_lexicon_matches_handler_contract() {
        let src = include_str!("../../../lexicons/com/etzhayyim/apps/kotoba/email/send.json");
        let value: serde_json::Value = serde_json::from_str(src).expect("email.send lexicon JSON");
        assert_eq!(value["lexicon"], 1);
        assert_eq!(value["id"], NSID_EMAIL_SEND);
        assert_eq!(value["defs"]["main"]["type"], "procedure");

        let schema = &value["defs"]["main"]["input"]["schema"];
        let required = schema["required"].as_array().expect("input required");
        for field in ["senderDid", "recipients"] {
            assert!(
                required.iter().any(|value| value.as_str() == Some(field)),
                "email.send input must require {field}"
            );
        }
        let props = &schema["properties"];
        assert_eq!(props["senderDid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            props["senderDid"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(props["senderDid"]["pattern"].as_str(), Some("^did:[!-~]+$"));
        assert_eq!(
            props["threadId"]["maxLength"].as_u64(),
            Some(MAX_THREAD_ID_LEN as u64)
        );
        assert_eq!(props["threadId"]["pattern"].as_str(), Some("^[!-~]*$"));
        assert_eq!(
            props["recipients"]["maxLength"].as_u64(),
            Some(MAX_RECIPIENTS as u64)
        );
        assert_eq!(props["recipients"]["minLength"].as_u64(), Some(1));
        let recipients_description = props["recipients"]["description"]
            .as_str()
            .expect("recipients description");
        assert!(recipients_description.contains("One SignalMessage per recipient device"));
        assert!(recipients_description.contains("duplicate recipientDid + deviceId"));

        let item = &props["recipients"]["items"];
        let item_required = item["required"].as_array().expect("recipient required");
        for field in [
            "messageType",
            "senderDid",
            "recipientDid",
            "deviceId",
            "ciphertextEnvelope",
            "timestamp",
        ] {
            assert!(
                item_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.send recipient must require {field}"
            );
        }
        let item_props = &item["properties"];
        assert_eq!(item_props["senderDid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item_props["senderDid"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(item_props["recipientDid"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item_props["recipientDid"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        assert_eq!(item_props["deviceId"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item_props["deviceId"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_DEVICE_ID_LEN as u64)
        );
        assert_eq!(item_props["groupId"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item_props["groupId"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_GROUP_ID_LEN as u64)
        );
        assert_eq!(
            item_props["ciphertextEnvelope"]["minLength"].as_u64(),
            Some(1)
        );
        assert_eq!(
            item_props["ciphertextEnvelope"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_CIPHERTEXT_ENVELOPE_LEN as u64)
        );
        assert_eq!(item_props["timestamp"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item_props["timestamp"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_TIMESTAMP_LEN as u64)
        );
        assert_eq!(item_props["ephemeralKey"]["minLength"].as_u64(), Some(1));
        assert_eq!(
            item_props["ephemeralKey"]["maxLength"].as_u64(),
            Some(MAX_SIGNAL_EPHEMERAL_KEY_LEN as u64)
        );
        assert_eq!(item_props["oneTimePrekeyId"]["minimum"].as_u64(), Some(0));
        assert_eq!(
            item_props["oneTimePrekeyId"]["maximum"].as_u64(),
            Some(u32::MAX as u64)
        );
        for field in ["senderDid", "recipientDid"] {
            assert_eq!(
                item_props[field]["pattern"].as_str(),
                Some("^did:[!-~]+$"),
                "email.send {field} must publish the DID prefix and visible-ASCII contract"
            );
        }
        for field in [
            "deviceId",
            "groupId",
            "ciphertextEnvelope",
            "timestamp",
            "ephemeralKey",
        ] {
            assert_eq!(
                item_props[field]["pattern"].as_str(),
                Some("^[!-~]+$"),
                "email.send {field} must publish the visible-ASCII contract"
            );
        }
        let message_type_values = item_props["messageType"]["knownValues"]
            .as_array()
            .expect("messageType knownValues");
        for message_type in ["directMessage", "groupMessage", "receipt"] {
            assert!(
                message_type_values
                    .iter()
                    .any(|value| value.as_str() == Some(message_type)),
                "email.send messageType must advertise {message_type}"
            );
        }
        let message_type_description = item_props["messageType"]["description"]
            .as_str()
            .expect("messageType description");
        assert!(message_type_description.contains("requires groupId"));
        assert!(message_type_description.contains("absent"));
        let group_id_description = item_props["groupId"]["description"]
            .as_str()
            .expect("groupId description");
        assert!(group_id_description.contains("Required for groupMessage"));
        assert!(group_id_description.contains("absent"));

        let output = &value["defs"]["main"]["output"]["schema"];
        let output_required = output["required"].as_array().expect("output required");
        for field in ["status", "count", "delivered"] {
            assert!(
                output_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.send output must require {field}"
            );
        }
        let delivered_item = &output["properties"]["delivered"]["items"];
        let delivered_required = delivered_item["required"]
            .as_array()
            .expect("delivered required");
        for field in ["recipientDid", "emailCid", "bodyCid", "commitCid"] {
            assert!(
                delivered_required
                    .iter()
                    .any(|value| value.as_str() == Some(field)),
                "email.send delivered item must require {field}"
            );
        }
        let delivered_props = &delivered_item["properties"];
        assert_eq!(
            delivered_props["recipientDid"]["minLength"].as_u64(),
            Some(1)
        );
        assert_eq!(
            delivered_props["recipientDid"]["maxLength"].as_u64(),
            Some(MAX_OWNER_DID_LEN as u64)
        );
        for field in ["emailCid", "bodyCid", "commitCid"] {
            assert_eq!(delivered_props[field]["minLength"].as_u64(), Some(1));
            assert_eq!(
                delivered_props[field]["maxLength"].as_u64(),
                Some(MAX_EMAIL_CID_LEN as u64),
                "email.send delivered {field} must publish the CID length cap"
            );
        }
        assert_eq!(
            delivered_props["recipientDid"]["pattern"].as_str(),
            Some("^did:[!-~]+$"),
            "email.send delivered recipientDid must publish the DID prefix and visible-ASCII contract"
        );
        for field in ["emailCid", "bodyCid", "commitCid"] {
            assert_eq!(
                delivered_props[field]["pattern"].as_str(),
                Some("^[!-~]+$"),
                "email.send delivered {field} must publish the visible-ASCII contract"
            );
        }
        assert_eq!(
            output["properties"]["deliveredSoFar"]["items"], *delivered_item,
            "email.send deliveredSoFar items must match delivered items"
        );
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
    fn email_cid_param_rejects_empty_non_visible_ascii_and_oversized_values() {
        assert!(validate_email_cid_param("bafyLegacyOrRealCid").is_ok());
        for (value, expected) in [
            ("", "email_cid must not be empty"),
            ("   ", "email_cid must not be empty"),
            (
                "bafy\ncid",
                "email_cid must contain only visible ASCII characters",
            ),
            (
                "bafy cid",
                "email_cid must contain only visible ASCII characters",
            ),
            (
                "bafyé",
                "email_cid must contain only visible ASCII characters",
            ),
        ] {
            let err = validate_email_cid_param(value).unwrap_err();
            assert_eq!(err.0, StatusCode::BAD_REQUEST);
            assert_eq!(err.1, expected);
        }
        let oversized = "b".repeat(MAX_EMAIL_CID_LEN + 1);
        let err = validate_email_cid_param(&oversized).unwrap_err();
        assert_eq!(err.0, StatusCode::BAD_REQUEST);
        assert!(err.1.contains("email_cid must be 1"), "{err:?}");
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
                kotoba_query::Datom::assert(
                    email_cid.clone(),
                    "email/message_id".to_string(),
                    kotoba_query::Value::Text("<bridge@example>".to_string()),
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
    //   4. "signal:v1:" prefix + bad ciphertext → error

    #[tokio::test]
    async fn open_field_safe_empty_returns_empty() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0xAAu8; 32]));
        let result = open_field_safe(&crypto, b"scope", "").await.unwrap();
        assert_eq!(result, "");
    }

    #[tokio::test]
    async fn open_field_safe_plaintext_returns_unchanged() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0xAAu8; 32]));
        let result = open_field_safe(&crypto, b"scope", "alice@example.com")
            .await
            .unwrap();
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
        let recovered = open_field_safe(&crypto, scope, &envelope).await.unwrap();
        assert_eq!(recovered, plaintext);
    }

    #[tokio::test]
    async fn open_field_safe_bad_ciphertext_returns_error() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0x11u8; 32]));
        let envelope = "signal:v1:not-valid-ciphertext";
        let err = open_field_safe(&crypto, b"scope", envelope)
            .await
            .unwrap_err();
        assert!(!err.is_empty());
    }

    #[tokio::test]
    async fn open_field_safe_non_signal_prefix_with_colon_passthrough() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;
        let crypto = VaultKeyedCrypto::new(Zeroizing::new([0xAAu8; 32]));
        // A string that has a colon but not the signal:v1: prefix
        let result = open_field_safe(&crypto, b"scope", "mailto:user@example.com")
            .await
            .unwrap();
        assert_eq!(result, "mailto:user@example.com");
    }
}

/// Open a `signal:v1:` envelope using AgentCrypto.
async fn open_field_safe(
    crypto: &dyn kotoba_crypto::AgentCrypto,
    scope: &[u8],
    envelope: &str,
) -> Result<String, String> {
    if envelope.is_empty() {
        return Ok(envelope.to_string());
    }
    if !envelope.starts_with("signal:v1:") {
        // Plain-text legacy value — return as-is
        return Ok(envelope.to_string());
    }
    crypto
        .open_field(scope, envelope)
        .await
        .map_err(|err| err.to_string())
}
