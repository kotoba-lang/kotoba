//! kotobase XRPC handlers — multi-tenant pinning service (ADR-2605260001)
//!
//! NSIDs: com.etzhayyim.apps.kotobase.*
//!
//! Tenant data lives in kotoba's own QuadStore under namespaced graphs:
//!   kotobase/accounts/{tenant_did}  — tier + metadata
//!   kotobase/pins/{tenant_did}      — per-pin records
//!
//! Quota tiers:
//!   free:    3 pins,  100 MB
//!   starter: 50 pins,   5 GB  ($9/mo — Stripe stub)
//!   pro:    500 pins,  50 GB  ($49/mo — Stripe stub)

pub const NSID_ACCOUNT_CREATE: &str = "com.etzhayyim.apps.kotobase.accountCreate";
pub const NSID_ACCOUNT_STATUS: &str = "com.etzhayyim.apps.kotobase.accountStatus";
pub const NSID_PIN_CREATE: &str = "com.etzhayyim.apps.kotobase.pinCreate";
pub const NSID_PIN_LIST: &str = "com.etzhayyim.apps.kotobase.pinList";
pub const NSID_PIN_DELETE: &str = "com.etzhayyim.apps.kotobase.pinDelete";
pub const NSID_USAGE_GET: &str = "com.etzhayyim.apps.kotobase.usageGet";
/// Revoke a PRE re-key grant + propagate over GossipSub (ADR §23.7 / §28.5).
pub const NSID_PRE_REVOKE: &str = "com.etzhayyim.apps.kotobase.preRevoke";

use crate::server::KotobaState;
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use kotoba_core::cid::KotobaCid;
use kotoba_kqe::quad::{LegacyQuad as Quad, LegacyQuadObject as QuadObject};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

/// Extract Bearer token string from `Authorization: Bearer <token>` header.
fn bearer_token(headers: &HeaderMap) -> Option<&str> {
    let v = headers
        .get(axum::http::header::AUTHORIZATION)?
        .to_str()
        .ok()?;
    v.strip_prefix("Bearer ")
}

/// Read a self-sovereign CACAO from the request, if present.
///
/// Two equivalent carriers are accepted: an `Authorization: CACAO <b64>` scheme
/// (what the edge Worker forwards verbatim) and an explicit `x-kotoba-cacao`
/// header (for clients that hit the pod directly). The value is DAG-CBOR,
/// base64-encoded.
fn cacao_b64_from_headers(headers: &HeaderMap) -> Option<&str> {
    if let Some(auth) = headers.get("authorization").and_then(|v| v.to_str().ok()) {
        if let Some(rest) = auth.strip_prefix("CACAO ").or_else(|| auth.strip_prefix("cacao ")) {
            return Some(rest.trim());
        }
    }
    headers
        .get("x-kotoba-cacao")
        .and_then(|v| v.to_str().ok())
        .map(str::trim)
}

/// Verify that the caller owns `tenant_did` (or is the operator).
///
/// Two authentication modes, tried in order:
///
/// 1. **Self-sovereign CACAO** (no etzhayyim webauth) — when a CACAO is present
///    (`Authorization: CACAO <b64>` or `x-kotoba-cacao`), its signature is
///    *cryptographically verified* (SIWE/EIP-191, Ed25519/did:key, EIP-1271,
///    BIP-322), the `kotobase:pin` capability is required, and the verified
///    issuer must equal `tenant_did` (or `operator_did`). Because the signature
///    is real, this path does NOT require `x-internal-trust` — a client holding
///    its own key can authorize directly.
/// 2. **Edge JWT `sub`** (back-compat) — the token `sub` must match
///    `tenant_did`/`operator_did`. The signature is NOT verified here (the edge
///    BFF is the trust boundary), so when `KOTOBA_INTERNAL_SECRET` is set the
///    request must arrive through the trusted Worker (`x-internal-trust`).
///
/// Returns `Err(401)` when neither mode authorizes the request.
fn require_did_ownership(
    headers: &HeaderMap,
    tenant_did: &str,
    operator_did: &str,
    nonce_store: &crate::nonce_store::NonceStore,
) -> Result<(), (StatusCode, String)> {
    // ── Mode 1: self-sovereign CACAO ─────────────────────────────────────────
    if let Some(cacao_b64) = cacao_b64_from_headers(headers) {
        // Scope the capability to the holder's own DID (graph == tenant_did) so a
        // graph:query / datom:transact CACAO cannot be replayed as pin auth.
        let payload = crate::graph_auth::verify_cacao_graph_operation(
            cacao_b64,
            tenant_did,
            kotoba_auth::CacaoPayload::OP_KOTOBASE_PIN,
            None,
            Some(nonce_store),
        )
        .map_err(|e| {
            tracing::warn!(error = ?e, "kotobase auth: CACAO verification failed");
            (StatusCode::UNAUTHORIZED, format!("CACAO verification failed: {e:?}"))
        })?;
        // The verified issuer is authoritative; it must own the requested tenant.
        if payload.iss == tenant_did || payload.iss == operator_did {
            return Ok(());
        }
        tracing::warn!(iss = %payload.iss, tenant_did = %tenant_did, "kotobase auth: CACAO issuer mismatch");
        return Err((
            StatusCode::UNAUTHORIZED,
            format!("CACAO issuer {:?} does not match tenant_did {tenant_did:?}", payload.iss),
        ));
    }

    // ── Mode 2: edge-issued JWT `sub` (back-compat) ──────────────────────────
    // Defense-in-depth: when KOTOBA_INTERNAL_SECRET is set, only requests through
    // the trusted edge Worker (which forwards x-internal-trust) are accepted, so a
    // directly-reachable pod cannot be impersonated with a forged tenant JWT.
    crate::graph_auth::require_internal_trust(headers)?;
    let token = bearer_token(headers).ok_or_else(|| {
        tracing::warn!("kotobase auth: missing Bearer token");
        (
            StatusCode::UNAUTHORIZED,
            "Authorization: Bearer <token> required".to_string(),
        )
    })?;
    if crate::graph_auth::jwt_exp_elapsed(token) {
        tracing::warn!("kotobase auth: expired JWT");
        return Err((
            StatusCode::UNAUTHORIZED,
            "Bearer token has expired".to_string(),
        ));
    }
    let sub = crate::graph_auth::jwt_sub(token).ok_or_else(|| {
        tracing::warn!("kotobase auth: JWT missing sub claim");
        (
            StatusCode::UNAUTHORIZED,
            "Bearer token missing sub claim".to_string(),
        )
    })?;
    if sub == tenant_did || sub == operator_did {
        Ok(())
    } else {
        tracing::warn!(sub = %sub, tenant_did = %tenant_did, "kotobase auth: sub mismatch");
        Err((
            StatusCode::UNAUTHORIZED,
            format!("Bearer sub {sub:?} does not match tenant_did {tenant_did:?}"),
        ))
    }
}

// ── Input validation ──────────────────────────────────────────────────────

const MAX_DID_LEN: usize = 512;
const MAX_NAME_LEN: usize = 256;
const MAX_TIER_LEN: usize = 32;
const MAX_PIN_ID_LEN: usize = 128;
const MAX_SUBJECT_LEN: usize = 512;
const MAX_PREDICATE_LEN: usize = 256;
const MAX_OBJECT_LEN: usize = 65_536; // 64 KiB per triple value
const MAX_TRIPLES_PER_PIN: usize = 1_024; // prevent DoS via unbounded triple arrays

fn validate_did(did: &str) -> Result<(), (StatusCode, String)> {
    crate::graph_auth::validate_did(did, "tenant_did", MAX_DID_LEN)
}

fn validate_name(name: &str) -> Result<(), (StatusCode, String)> {
    if name.len() > MAX_NAME_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("name exceeds {MAX_NAME_LEN} characters"),
        ));
    }
    Ok(())
}

fn validate_triple(t: &TripleInput) -> Result<(), (StatusCode, String)> {
    if t.subject.is_empty() || t.subject.len() > MAX_SUBJECT_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("triple subject must be 1-{MAX_SUBJECT_LEN} bytes"),
        ));
    }
    if t.predicate.is_empty() || t.predicate.len() > MAX_PREDICATE_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("triple predicate must be 1-{MAX_PREDICATE_LEN} bytes"),
        ));
    }
    if t.object.len() > MAX_OBJECT_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("triple object exceeds {MAX_OBJECT_LEN} bytes"),
        ));
    }
    Ok(())
}

// ── Quota constants ────────────────────────────────────────────────────────

const QUOTA_FREE_PINS: i64 = 3;
const QUOTA_FREE_BYTES: i64 = 100 * 1024 * 1024;
const QUOTA_STARTER_PINS: i64 = 50;
const QUOTA_STARTER_BYTES: i64 = 5 * 1024 * 1024 * 1024;
const QUOTA_PRO_PINS: i64 = 500;
const QUOTA_PRO_BYTES: i64 = 50 * 1024 * 1024 * 1024;

fn quota_for_tier(tier: &str) -> (i64, i64) {
    match tier {
        "starter" => (QUOTA_STARTER_PINS, QUOTA_STARTER_BYTES),
        "pro" => (QUOTA_PRO_PINS, QUOTA_PRO_BYTES),
        _ => (QUOTA_FREE_PINS, QUOTA_FREE_BYTES),
    }
}

// ── CID helpers ────────────────────────────────────────────────────────────

fn cid(s: &str) -> KotobaCid {
    KotobaCid::from_bytes(s.as_bytes())
}

fn text_quad(graph: &str, subject: &str, predicate: &str, value: &str) -> Quad {
    Quad {
        graph: cid(graph),
        subject: cid(subject),
        predicate: predicate.to_string(),
        object: QuadObject::Text(value.to_string()),
    }
}

fn int_quad(graph: &str, subject: &str, predicate: &str, value: i64) -> Quad {
    Quad {
        graph: cid(graph),
        subject: cid(subject),
        predicate: predicate.to_string(),
        object: QuadObject::Integer(value),
    }
}

fn graph_tx_cid(graph: &str, entity: &str) -> KotobaCid {
    KotobaCid::from_bytes(format!("kotobase:{graph}:{entity}:{}", new_pin_id()).as_bytes())
}

async fn commit_quads_as_datoms(
    state: &KotobaState,
    graph: &str,
    entity: &str,
    author: &str,
    quads: Vec<Quad>,
) -> Result<(), (StatusCode, String)> {
    let tx_cid = graph_tx_cid(graph, entity);
    let datoms = quads
        .into_iter()
        .map(|quad| {
            let mut datom = kotoba_kqe::Datom::from_legacy_quad(quad, true);
            datom.tx = tx_cid.clone();
            kotoba_datomic::Datom::from_kqe(datom)
        })
        .collect::<Vec<_>>();
    crate::xrpc::commit_protocol_datoms(
        state,
        cid(graph),
        graph.to_string(),
        cid(entity),
        datoms,
        tx_cid,
        author.to_string(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        None,
        None,
    )
    .await?;
    Ok(())
}

async fn commit_retractions(
    state: &KotobaState,
    graph: &str,
    entity: &str,
    author: &str,
    datoms: Vec<kotoba_datomic::Datom>,
) -> Result<(), (StatusCode, String)> {
    let tx_cid = graph_tx_cid(graph, entity);
    let retractions = datoms
        .into_iter()
        .map(|datom| kotoba_datomic::Datom::retract(datom.e, datom.a, datom.v, tx_cid.clone()))
        .collect::<Vec<_>>();
    crate::xrpc::commit_protocol_datoms(
        state,
        cid(graph),
        graph.to_string(),
        cid(entity),
        retractions,
        tx_cid,
        author.to_string(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        None,
        None,
    )
    .await?;
    Ok(())
}

async fn graph_datoms(
    state: &KotobaState,
    graph: &str,
) -> Result<Vec<kotoba_datomic::Datom>, (StatusCode, String)> {
    Ok(crate::xrpc::current_db_for_graph(state, &cid(graph))
        .await?
        .datoms())
}

fn datom_text(value: &kotoba_edn::EdnValue) -> Option<String> {
    if let kotoba_edn::EdnValue::String(text) = value {
        Some(text.clone())
    } else {
        None
    }
}

fn datom_int(value: &kotoba_edn::EdnValue) -> Option<i64> {
    if let kotoba_edn::EdnValue::Integer(value) = value {
        Some(*value)
    } else {
        None
    }
}

// ── Distributed Datom read helpers ─────────────────────────────────────────

async fn get_text(
    state: &KotobaState,
    graph: &str,
    subject: &str,
    predicate: &str,
) -> Option<String> {
    let subject = cid(subject);
    graph_datoms(state, graph)
        .await
        .ok()?
        .into_iter()
        .find(|datom| datom.e == subject && datom.a == predicate)
        .and_then(|datom| datom_text(&datom.v))
}

#[allow(dead_code)]
async fn get_int(state: &KotobaState, graph: &str, subject: &str, predicate: &str) -> i64 {
    let subject = cid(subject);
    graph_datoms(state, graph)
        .await
        .ok()
        .and_then(|datoms| {
            datoms
                .into_iter()
                .find(|datom| datom.e == subject && datom.a == predicate)
                .and_then(|datom| datom_int(&datom.v))
        })
        .unwrap_or(0)
}

async fn read_tier(state: &KotobaState, tenant_did: &str) -> String {
    let g = format!("kotobase/accounts/{tenant_did}");
    get_text(state, &g, tenant_did, "kotobase/account/tier")
        .await
        .unwrap_or_else(|| "free".to_string())
}

/// Count pins optionally filtered by status; also sums size_bytes.
async fn count_pins(
    state: &KotobaState,
    tenant_did: &str,
    status_filter: Option<&str>,
) -> (i64, i64) {
    let g = format!("kotobase/pins/{tenant_did}");
    let datoms = match graph_datoms(state, &g).await {
        Ok(datoms) => datoms,
        Err(_) => return (0, 0),
    };
    let mut pin_subjects = datoms
        .iter()
        .filter(|datom| datom.a == "kotobase/pin/cid")
        .map(|datom| datom.e.clone())
        .collect::<Vec<_>>();
    pin_subjects.sort_by_key(|cid| cid.to_multibase());
    pin_subjects.dedup();
    let mut count = 0i64;
    let mut bytes = 0i64;
    for subj_cid in pin_subjects {
        if let Some(sf) = status_filter {
            let status = datoms
                .iter()
                .find(|datom| datom.e == subj_cid && datom.a == "kotobase/pin/status")
                .and_then(|datom| datom_text(&datom.v))
                .unwrap_or_default();
            if status != sf {
                continue;
            }
        }
        count += 1;
        let sz: i64 = datoms
            .iter()
            .find(|datom| datom.e == subj_cid && datom.a == "kotobase/pin/size_bytes")
            .and_then(|datom| datom_int(&datom.v))
            .unwrap_or(0);
        bytes += sz;
    }
    (count, bytes)
}



fn now_unix_str() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs().to_string())
        .unwrap_or_else(|_| "0".to_string())
}

fn new_pin_id() -> String {
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::time::{SystemTime, UNIX_EPOCH};
    static SEQ: AtomicU64 = AtomicU64::new(0);
    let seq = SEQ.fetch_add(1, Ordering::Relaxed);
    let ms = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0);
    // Combine timestamp (ms) with a monotonic seq so concurrent calls never collide.
    let combined = ms.wrapping_shl(20) ^ seq;
    format!("pin_{combined:016x}")
}

// ── Request / Response types ───────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct AccountCreateReq {
    pub display_name: Option<String>,
    pub tier: Option<String>,
    pub tenant_did: String,
}

#[derive(Debug, Serialize)]
pub struct AccountCreateResp {
    pub ok: bool,
    pub tenant_did: String,
    pub tier: String,
    pub created_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct AccountStatusReq {
    pub tenant_did: String,
}

#[derive(Debug, Serialize)]
pub struct AccountStatusResp {
    pub ok: bool,
    pub tenant_did: String,
    pub tier: String,
    pub quota_pins: i64,
    pub quota_bytes: i64,
    pub used_pins: i64,
    pub used_bytes: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub created_at: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct TripleInput {
    pub subject: String,
    pub predicate: String,
    pub object: String,
}

#[derive(Debug, Deserialize)]
pub struct QuadsInput {
    pub graph: String,
    pub triples: Option<Vec<TripleInput>>,
}

#[derive(Debug, Deserialize)]
pub struct PinCreateReq {
    pub name: String,
    pub cid: Option<String>,
    pub quads: Option<QuadsInput>,
    pub size_hint_bytes: Option<i64>,
    pub tenant_did: String,
}

#[derive(Debug, Serialize)]
pub struct PinCreateResp {
    pub ok: bool,
    pub pin_id: String,
    pub cid: String,
    pub status: String,
    pub size_bytes: i64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct PinListReq {
    pub tenant_did: String,
    pub status: Option<String>,
    pub limit: Option<usize>,
    pub offset: Option<usize>,
}

#[derive(Debug, Serialize)]
pub struct PinRecord {
    pub pin_id: String,
    pub name: String,
    pub cid: String,
    pub status: String,
    pub size_bytes: i64,
    pub created_at: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub ipfs_status: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct PinListResp {
    pub ok: bool,
    pub pins: Vec<PinRecord>,
    pub total: usize,
    pub offset: usize,
    pub limit: usize,
}

#[derive(Debug, Deserialize)]
pub struct PinDeleteReq {
    pub pin_id: String,
    pub tenant_did: String,
}

#[derive(Debug, Serialize)]
pub struct PinDeleteResp {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Deserialize)]
pub struct UsageGetReq {
    pub tenant_did: String,
}

#[derive(Debug, Serialize)]
pub struct UsageGetResp {
    pub ok: bool,
    pub tenant_did: String,
    pub tier: String,
    pub pin_count: i64,
    pub pinned_count: i64,
    pub pinning_count: i64,
    pub failed_count: i64,
    pub total_bytes: i64,
    pub quota_pins: i64,
    pub quota_bytes: i64,
    pub remaining_pins: i64,
    pub remaining_bytes: i64,
}

#[derive(Debug, Deserialize)]
pub struct PreRevokeReq {
    /// DID that owns the grant being revoked. The caller's JWT `sub` must match
    /// this (or `operator_did`) — only the owner/operator may revoke.
    pub tenant_did: String,
    /// DID whose re-key access is being revoked.
    pub accessor_did: String,
}

#[derive(Debug, Serialize)]
pub struct PreRevokeResp {
    pub ok: bool,
    pub tenant_did: String,
    pub accessor_did: String,
}

// ── Handlers ──────────────────────────────────────────────────────────────

/// POST /xrpc/com.etzhayyim.apps.kotobase.preRevoke
///
/// Revoke a PRE re-key grant (owner → accessor) and propagate the revocation
/// to peers over GossipSub (ADR §23.7 / §28.5 emit path). Owner-authenticated.
pub async fn handle_pre_revoke(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<PreRevokeReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&req.tenant_did)?;
    crate::graph_auth::validate_did(&req.accessor_did, "accessor_did", MAX_DID_LEN)?;
    require_did_ownership(&headers, &req.tenant_did, &state.operator_did, &state.nonce_store)?;

    state
        .revoke_pre_key_grant(&req.tenant_did, &req.accessor_did)
        .await
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, format!("revoke failed: {e}")))?;

    Ok((
        StatusCode::OK,
        Json(PreRevokeResp {
            ok: true,
            tenant_did: req.tenant_did,
            accessor_did: req.accessor_did,
        }),
    ))
}

pub async fn handle_account_create(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<AccountCreateReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&req.tenant_did)?;
    require_did_ownership(&headers, &req.tenant_did, &state.operator_did, &state.nonce_store)?;

    let tier_raw = req.tier.as_deref().unwrap_or("free");
    if tier_raw.len() > MAX_TIER_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("tier exceeds {MAX_TIER_LEN} characters"),
        ));
    }
    let tier = match tier_raw {
        "free" | "starter" | "pro" => tier_raw.to_string(),
        other => return Err((StatusCode::BAD_REQUEST, format!("unknown tier: {other:?}"))),
    };
    let now = now_unix_str();
    let g = format!("kotobase/accounts/{}", req.tenant_did);

    let quads = vec![
        text_quad(&g, &req.tenant_did, "kotobase/account/tier", &tier),
        text_quad(&g, &req.tenant_did, "kotobase/account/created_at", &now),
    ];
    commit_quads_as_datoms(&state, &g, &req.tenant_did, &req.tenant_did, quads).await?;

    Ok((
        StatusCode::OK,
        Json(AccountCreateResp {
            ok: true,
            tenant_did: req.tenant_did,
            tier,
            created_at: now,
            error: None,
        }),
    ))
}

pub async fn handle_account_status(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<AccountStatusReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&req.tenant_did)?;
    require_did_ownership(&headers, &req.tenant_did, &state.operator_did, &state.nonce_store)?;
    let tier = read_tier(&state, &req.tenant_did).await;
    let (quota_pins, quota_bytes) = quota_for_tier(&tier);
    let (used_pins, used_bytes) = count_pins(&state, &req.tenant_did, None).await;

    let g = format!("kotobase/accounts/{}", req.tenant_did);
    let created_at = get_text(&state, &g, &req.tenant_did, "kotobase/account/created_at").await;

    Ok((
        StatusCode::OK,
        Json(AccountStatusResp {
            ok: true,
            tenant_did: req.tenant_did,
            tier,
            quota_pins,
            quota_bytes,
            used_pins,
            used_bytes,
            created_at,
            error: None,
        }),
    ))
}

pub async fn handle_pin_create(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<PinCreateReq>,
) -> impl IntoResponse {
    // Input validation
    if let Err((status, msg)) = validate_did(&req.tenant_did) {
        return (
            status,
            Json(PinCreateResp {
                ok: false,
                pin_id: String::new(),
                cid: String::new(),
                status: "failed".into(),
                size_bytes: 0,
                error: Some(msg),
            }),
        );
    }
    if let Err((status, msg)) =
        require_did_ownership(&headers, &req.tenant_did, &state.operator_did, &state.nonce_store)
    {
        return (
            status,
            Json(PinCreateResp {
                ok: false,
                pin_id: String::new(),
                cid: String::new(),
                status: "failed".into(),
                size_bytes: 0,
                error: Some(msg),
            }),
        );
    }
    if let Err((status, msg)) = validate_name(&req.name) {
        return (
            status,
            Json(PinCreateResp {
                ok: false,
                pin_id: String::new(),
                cid: String::new(),
                status: "failed".into(),
                size_bytes: 0,
                error: Some(msg),
            }),
        );
    }
    if let Some(size_hint) = req.size_hint_bytes {
        if size_hint < 0 {
            return (
                StatusCode::BAD_REQUEST,
                Json(PinCreateResp {
                    ok: false,
                    pin_id: String::new(),
                    cid: String::new(),
                    status: "failed".into(),
                    size_bytes: 0,
                    error: Some("size_hint_bytes must not be negative".into()),
                }),
            );
        }
    }
    if let Some(qi) = &req.quads {
        if qi.graph.is_empty() || qi.graph.len() > MAX_SUBJECT_LEN {
            return (
                StatusCode::BAD_REQUEST,
                Json(PinCreateResp {
                    ok: false,
                    pin_id: String::new(),
                    cid: String::new(),
                    status: "failed".into(),
                    size_bytes: 0,
                    error: Some(format!("quads.graph must be 1-{MAX_SUBJECT_LEN} bytes")),
                }),
            );
        }
        let triples = qi.triples.as_deref().unwrap_or(&[]);
        if triples.len() > MAX_TRIPLES_PER_PIN {
            return (
                StatusCode::BAD_REQUEST,
                Json(PinCreateResp {
                    ok: false,
                    pin_id: String::new(),
                    cid: String::new(),
                    status: "failed".into(),
                    size_bytes: 0,
                    error: Some(format!(
                        "quads.triples exceeds limit of {MAX_TRIPLES_PER_PIN}"
                    )),
                }),
            );
        }
        for t in triples {
            if let Err((status, msg)) = validate_triple(t) {
                return (
                    status,
                    Json(PinCreateResp {
                        ok: false,
                        pin_id: String::new(),
                        cid: String::new(),
                        status: "failed".into(),
                        size_bytes: 0,
                        error: Some(msg),
                    }),
                );
            }
        }
    }

    if req.cid.is_none() == req.quads.is_none() {
        return (
            StatusCode::BAD_REQUEST,
            Json(PinCreateResp {
                ok: false,
                pin_id: String::new(),
                cid: String::new(),
                status: "failed".into(),
                size_bytes: 0,
                error: Some("provide exactly one of: cid, quads".into()),
            }),
        );
    }

    // Quota check
    let tier = read_tier(&state, &req.tenant_did).await;
    let (quota_pins, quota_bytes) = quota_for_tier(&tier);
    let (used_pins, used_bytes) = count_pins(&state, &req.tenant_did, None).await;
    let size = req.size_hint_bytes.unwrap_or(0);

    if quota_pins >= 0 && used_pins >= quota_pins {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(PinCreateResp {
                ok: false,
                pin_id: String::new(),
                cid: String::new(),
                status: "failed".into(),
                size_bytes: 0,
                error: Some(format!(
                    "QuotaExceeded: tier={tier} pins={used_pins}/{quota_pins}"
                )),
            }),
        );
    }
    if quota_bytes >= 0 && size > 0 && used_bytes + size > quota_bytes {
        return (
            StatusCode::TOO_MANY_REQUESTS,
            Json(PinCreateResp {
                ok: false,
                pin_id: String::new(),
                cid: String::new(),
                status: "failed".into(),
                size_bytes: 0,
                error: Some(format!(
                    "QuotaExceeded: tier={tier} bytes={used_bytes}+{size}>{quota_bytes}"
                )),
            }),
        );
    }

    // Resolve CID
    let resolved_cid = if let Some(c) = req.cid.as_deref() {
        c.to_string()
    } else {
        // Invariant: exactly one of cid/quads is Some (enforced by the check above).
        // Use a graceful 500 instead of panic so a refactor cannot silently break this.
        let qi = match req.quads.as_ref() {
            Some(q) => q,
            None => {
                return (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    Json(PinCreateResp {
                        ok: false,
                        pin_id: String::new(),
                        cid: String::new(),
                        status: "failed".into(),
                        size_bytes: 0,
                        error: Some("internal: quads field unexpectedly absent".into()),
                    }),
                )
            }
        };
        let graph = format!("{}/{}", req.tenant_did, qi.graph);
        let mut quads = Vec::new();
        for t in qi.triples.as_deref().unwrap_or(&[]) {
            quads.push(text_quad(&graph, &t.subject, &t.predicate, &t.object));
        }
        let gc = KotobaCid::from_bytes(graph.as_bytes());
        if let Err((status, msg)) =
            commit_quads_as_datoms(&state, &graph, &graph, &req.tenant_did, quads).await
        {
            return (
                status,
                Json(PinCreateResp {
                    ok: false,
                    pin_id: String::new(),
                    cid: String::new(),
                    status: "failed".into(),
                    size_bytes: 0,
                    error: Some(msg),
                }),
            );
        }
        gc.to_multibase()
    };

    let pin_id = new_pin_id();
    let now = now_unix_str();
    let pin_g = format!("kotobase/pins/{}", req.tenant_did);

    let pin_quads = vec![
        // Store the nanoid `pin_id` explicitly so pin.list returns the SAME id
        // that pin.create returns and pin.delete consumes (delete derives the
        // record subject via `cid(pin_id)`). Without this, list returned the
        // subject CID — irreversible — so a pin discovered via list could not be
        // deleted, breaking the IPFS Pinning Service API rm-by-cid flow.
        text_quad(&pin_g, &pin_id, "kotobase/pin/id", &pin_id),
        text_quad(&pin_g, &pin_id, "kotobase/pin/cid", &resolved_cid),
        text_quad(&pin_g, &pin_id, "kotobase/pin/name", &req.name),
        text_quad(&pin_g, &pin_id, "kotobase/pin/status", "pinning"),
        int_quad(&pin_g, &pin_id, "kotobase/pin/size_bytes", size),
        text_quad(&pin_g, &pin_id, "kotobase/pin/created_at", &now),
    ];
    if let Err((status, msg)) =
        commit_quads_as_datoms(&state, &pin_g, &pin_id, &req.tenant_did, pin_quads).await
    {
        return (
            status,
            Json(PinCreateResp {
                ok: false,
                pin_id: String::new(),
                cid: String::new(),
                status: "failed".into(),
                size_bytes: 0,
                error: Some(msg),
            }),
        );
    }

    // Fire-and-forget IPFS pin
    {
        let ipfs_c = Arc::clone(&state.ipfs_pin);
        let cid_c = resolved_cid.clone();
        let state_c = Arc::clone(&state);
        let pin_id_c = pin_id.clone();
        let pin_g_c = pin_g.clone();
        let tenant_did_c = req.tenant_did.clone();
        tokio::spawn(async move {
            ipfs_c.pin(&cid_c).await;
            let done = vec![
                text_quad(&pin_g_c, &pin_id_c, "kotobase/pin/status", "pinned"),
                text_quad(&pin_g_c, &pin_id_c, "kotobase/pin/ipfs_status", "pinned"),
            ];
            if let Err((status, msg)) =
                commit_quads_as_datoms(&state_c, &pin_g_c, &pin_id_c, &tenant_did_c, done).await
            {
                tracing::warn!(%status, error = %msg, "kotobase pin status distributed commit failed");
            }
        });
    }

    (
        StatusCode::OK,
        Json(PinCreateResp {
            ok: true,
            pin_id,
            cid: resolved_cid,
            status: "pinning".into(),
            size_bytes: size,
            error: None,
        }),
    )
}

pub async fn handle_pin_list(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<PinListReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&req.tenant_did)?;
    require_did_ownership(&headers, &req.tenant_did, &state.operator_did, &state.nonce_store)?;
    let limit = req.limit.unwrap_or(20).min(100);
    let offset = req.offset.unwrap_or(0);
    let g = format!("kotobase/pins/{}", req.tenant_did);
    let datoms = graph_datoms(&state, &g).await?;

    let mut pin_subjects = datoms
        .iter()
        .filter(|datom| datom.a == "kotobase/pin/cid")
        .map(|datom| datom.e.clone())
        .collect::<Vec<_>>();
    pin_subjects.sort_by_key(|cid| cid.to_multibase());
    pin_subjects.dedup();
    // Group datoms by subject once (O(datoms)) so per-pin attribute lookups are
    // O(attrs-per-pin) instead of a full O(datoms) linear scan each — turning the
    // overall cost from O(pins × datoms) into O(datoms + pins).
    let mut by_subject: std::collections::HashMap<[u8; 36], Vec<&kotoba_datomic::Datom>> =
        std::collections::HashMap::with_capacity(pin_subjects.len());
    for d in &datoms {
        by_subject.entry(d.e.0).or_default().push(d);
    }
    let empty: Vec<&kotoba_datomic::Datom> = Vec::new();
    let text = |rows: &[&kotoba_datomic::Datom], pred: &str| -> Option<String> {
        rows.iter().find(|d| d.a == pred).and_then(|d| datom_text(&d.v))
    };
    let int = |rows: &[&kotoba_datomic::Datom], pred: &str| -> i64 {
        rows.iter()
            .find(|d| d.a == pred)
            .and_then(|d| datom_int(&d.v))
            .unwrap_or(0)
    };
    let records: Vec<PinRecord> = pin_subjects
        .iter()
        .filter_map(|subj_cid| {
            let rows = by_subject.get(&subj_cid.0).unwrap_or(&empty);
            // Return the stored nanoid (== what create returns / delete consumes);
            // fall back to the subject CID for pins written before this field.
            let pin_id = text(rows, "kotobase/pin/id").unwrap_or_else(|| subj_cid.to_multibase());
            let cid_val = text(rows, "kotobase/pin/cid")?;
            let name = text(rows, "kotobase/pin/name").unwrap_or_default();
            let status = text(rows, "kotobase/pin/status").unwrap_or_else(|| "pinning".into());
            let ipfs_status = text(rows, "kotobase/pin/ipfs_status");
            let size_bytes = int(rows, "kotobase/pin/size_bytes");
            let created_at = text(rows, "kotobase/pin/created_at").unwrap_or_default();

            if let Some(sf) = req.status.as_deref() {
                if status != sf {
                    return None;
                }
            }
            Some(PinRecord {
                pin_id,
                name,
                cid: cid_val,
                status,
                ipfs_status,
                size_bytes,
                created_at,
            })
        })
        .collect();

    let total = records.len();
    let page = records
        .into_iter()
        .skip(offset)
        .take(limit)
        .collect::<Vec<_>>();

    Ok((
        StatusCode::OK,
        Json(PinListResp {
            ok: true,
            pins: page,
            total,
            offset,
            limit,
        }),
    ))
}

pub async fn handle_pin_delete(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<PinDeleteReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&req.tenant_did)?;
    require_did_ownership(&headers, &req.tenant_did, &state.operator_did, &state.nonce_store)?;
    if req.pin_id.is_empty() || req.pin_id.len() > MAX_PIN_ID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("pin_id must be 1–{MAX_PIN_ID_LEN} bytes"),
        ));
    }
    let g = format!("kotobase/pins/{}", req.tenant_did);
    let subj = cid(&req.pin_id);
    let datoms = graph_datoms(&state, &g)
        .await?
        .into_iter()
        .filter(|datom| datom.e == subj)
        .collect::<Vec<_>>();
    if datoms.is_empty() {
        return Ok((
            StatusCode::NOT_FOUND,
            Json(PinDeleteResp {
                ok: false,
                error: Some("NotFound: pin not found".into()),
            }),
        ));
    }

    commit_retractions(&state, &g, &req.pin_id, &req.tenant_did, datoms).await?;

    Ok((
        StatusCode::OK,
        Json(PinDeleteResp {
            ok: true,
            error: None,
        }),
    ))
}

pub async fn handle_usage_get(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<UsageGetReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    validate_did(&req.tenant_did)?;
    require_did_ownership(&headers, &req.tenant_did, &state.operator_did, &state.nonce_store)?;
    let tier = read_tier(&state, &req.tenant_did).await;
    let (quota_pins, quota_bytes) = quota_for_tier(&tier);
    let (pin_count, total_bytes) = count_pins(&state, &req.tenant_did, None).await;
    let (pinned_count, _) = count_pins(&state, &req.tenant_did, Some("pinned")).await;
    let (pinning_count, _) = count_pins(&state, &req.tenant_did, Some("pinning")).await;
    let (failed_count, _) = count_pins(&state, &req.tenant_did, Some("failed")).await;

    let remaining_pins = if quota_pins < 0 {
        -1
    } else {
        (quota_pins - pin_count).max(0)
    };
    let remaining_bytes = if quota_bytes < 0 {
        -1
    } else {
        (quota_bytes - total_bytes).max(0)
    };

    Ok((
        StatusCode::OK,
        Json(UsageGetResp {
            ok: true,
            tenant_did: req.tenant_did,
            tier,
            pin_count,
            pinned_count,
            pinning_count,
            failed_count,
            total_bytes,
            quota_pins,
            quota_bytes,
            remaining_pins,
            remaining_bytes,
        }),
    ))
}

// ── NSID list for test invariant ──────────────────────────────────────────

pub const ALL_NSIDS: &[&str] = &[
    NSID_ACCOUNT_CREATE,
    NSID_ACCOUNT_STATUS,
    NSID_PIN_CREATE,
    NSID_PIN_LIST,
    NSID_PIN_DELETE,
    NSID_USAGE_GET,
    NSID_PRE_REVOKE,
];

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_auth::CacaoPayload;

    // ── preRevoke endpoint (ADR §23.7 / §28.5) ──────────────────────────────────

    #[tokio::test]
    async fn pre_revoke_owner_authenticated_revokes_grant() {
        use base64::{engine::general_purpose::URL_SAFE_NO_PAD, Engine as _};
        std::env::set_var("KOTOBA_IPFS", "off");

        let state = KotobaState::new(None).unwrap();
        let state = Arc::new(state.init_pre_key_registry().await);
        let owner = state.operator_did.clone(); // caller owns the grant
        let accessor = "did:key:zAccessorRevoke".to_string();

        // Seed a grant in the live registry.
        let reg = state.pre_key_registry.clone().expect("registry attached");
        reg.grant(&owner, &accessor, &[3u8; 32], &[7u8; 32])
            .await
            .unwrap();
        assert_eq!(reg.list_accessors(&owner).await, vec![accessor.clone()]);

        let req = || PreRevokeReq {
            tenant_did: owner.clone(),
            accessor_did: accessor.clone(),
        };

        // No Bearer token → 401, grant untouched.
        let unauth = handle_pre_revoke(State(Arc::clone(&state)), HeaderMap::new(), Json(req())).await;
        assert!(unauth.is_err(), "missing auth must be rejected");
        assert_eq!(reg.list_accessors(&owner).await.len(), 1);

        // Owner-authenticated JWT (sub == operator) → revoke succeeds.
        let header = URL_SAFE_NO_PAD.encode(r#"{"alg":"HS256","typ":"JWT"}"#);
        let payload = URL_SAFE_NO_PAD.encode(format!(r#"{{"sub":"{owner}","exp":9999999999}}"#));
        let jwt = format!("{header}.{payload}.sig");
        let mut headers = HeaderMap::new();
        headers.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {jwt}").parse().unwrap(),
        );
        let ok = handle_pre_revoke(State(Arc::clone(&state)), headers, Json(req())).await;
        assert!(ok.is_ok(), "owner-authenticated revoke must succeed");
        assert!(
            reg.list_accessors(&owner).await.is_empty(),
            "grant must be revoked after authenticated preRevoke"
        );
    }

    // ── quota_for_tier ────────────────────────────────────────────────────────

    #[test]
    fn quota_free_tier() {
        let (pins, bytes) = quota_for_tier("free");
        assert_eq!(pins, QUOTA_FREE_PINS);
        assert_eq!(bytes, QUOTA_FREE_BYTES);
    }

    #[test]
    fn quota_starter_tier() {
        let (pins, bytes) = quota_for_tier("starter");
        assert_eq!(pins, QUOTA_STARTER_PINS);
        assert_eq!(bytes, QUOTA_STARTER_BYTES);
    }

    #[test]
    fn quota_pro_tier() {
        let (pins, bytes) = quota_for_tier("pro");
        assert_eq!(pins, QUOTA_PRO_PINS);
        assert_eq!(bytes, QUOTA_PRO_BYTES);
    }

    #[test]
    fn quota_unknown_tier_falls_back_to_free() {
        let (pins, bytes) = quota_for_tier("enterprise");
        assert_eq!(pins, QUOTA_FREE_PINS);
        assert_eq!(bytes, QUOTA_FREE_BYTES);
    }

    // ── validate_name ─────────────────────────────────────────────────────────

    #[test]
    fn validate_name_accepts_empty_string() {
        assert!(validate_name("").is_ok());
    }

    #[test]
    fn validate_name_accepts_max_len() {
        let name = "a".repeat(MAX_NAME_LEN);
        assert!(validate_name(&name).is_ok());
    }

    #[test]
    fn validate_name_rejects_over_max() {
        let name = "a".repeat(MAX_NAME_LEN + 1);
        assert!(validate_name(&name).is_err());
    }

    // ── validate_triple ───────────────────────────────────────────────────────

    fn triple(s: &str, p: &str, o: &str) -> TripleInput {
        TripleInput {
            subject: s.to_string(),
            predicate: p.to_string(),
            object: o.to_string(),
        }
    }

    #[test]
    fn validate_triple_accepts_valid_input() {
        assert!(validate_triple(&triple("subj", "pred/foo", "value")).is_ok());
    }

    #[test]
    fn validate_triple_rejects_empty_subject() {
        assert!(validate_triple(&triple("", "pred", "val")).is_err());
    }

    #[test]
    fn validate_triple_rejects_empty_predicate() {
        assert!(validate_triple(&triple("subj", "", "val")).is_err());
    }

    #[test]
    fn validate_triple_rejects_oversized_subject() {
        let long = "s".repeat(MAX_SUBJECT_LEN + 1);
        assert!(validate_triple(&triple(&long, "pred", "val")).is_err());
    }

    #[test]
    fn validate_triple_rejects_oversized_object() {
        let long = "o".repeat(MAX_OBJECT_LEN + 1);
        assert!(validate_triple(&triple("subj", "pred", &long)).is_err());
    }

    // ── new_pin_id ────────────────────────────────────────────────────────────

    #[test]
    fn new_pin_id_has_pin_prefix() {
        let id = new_pin_id();
        assert!(id.starts_with("pin_"), "expected pin_ prefix, got {id}");
    }

    #[test]
    fn new_pin_id_is_unique() {
        let a = new_pin_id();
        let b = new_pin_id();
        assert_ne!(a, b);
    }

    // ── now_unix_str ──────────────────────────────────────────────────────────

    #[test]
    fn now_unix_str_is_numeric() {
        let s = now_unix_str();
        assert!(
            s.parse::<u64>().is_ok(),
            "expected numeric unix timestamp, got {s}"
        );
    }

    #[test]
    fn now_unix_str_is_reasonable_epoch() {
        let secs: u64 = now_unix_str().parse().unwrap();
        // After 2026-01-01 epoch
        assert!(secs > 1_750_000_000, "unix time looks too old: {secs}");
    }

    // ── ALL_NSIDS ─────────────────────────────────────────────────────────────

    #[test]
    fn all_nsids_have_correct_prefix() {
        for nsid in ALL_NSIDS {
            assert!(
                nsid.starts_with("com.etzhayyim.apps.kotobase."),
                "bad nsid: {nsid}"
            );
        }
    }

    // ── Additional constant / quota tests ─────────────────────────────────────

    #[test]
    fn nsid_account_create_exact_value() {
        assert_eq!(NSID_ACCOUNT_CREATE, "com.etzhayyim.apps.kotobase.accountCreate");
    }

    #[test]
    fn nsid_account_status_exact_value() {
        assert_eq!(NSID_ACCOUNT_STATUS, "com.etzhayyim.apps.kotobase.accountStatus");
    }

    #[test]
    fn nsid_pin_create_exact_value() {
        assert_eq!(NSID_PIN_CREATE, "com.etzhayyim.apps.kotobase.pinCreate");
    }

    #[test]
    fn nsid_pin_list_exact_value() {
        assert_eq!(NSID_PIN_LIST, "com.etzhayyim.apps.kotobase.pinList");
    }

    #[test]
    fn nsid_pin_delete_exact_value() {
        assert_eq!(NSID_PIN_DELETE, "com.etzhayyim.apps.kotobase.pinDelete");
    }

    #[test]
    fn nsid_usage_get_exact_value() {
        assert_eq!(NSID_USAGE_GET, "com.etzhayyim.apps.kotobase.usageGet");
    }

    #[test]
    fn all_nsids_count_is_seven() {
        // Guard against accidental NSID add/remove — bump consciously. Currently:
        // account.create/status, pin.create/list/delete, usage.get, pre.revoke.
        assert_eq!(ALL_NSIDS.len(), 7, "expected 7 NSID constants in ALL_NSIDS");
    }

    #[test]
    fn all_nsids_unique() {
        let mut set = std::collections::HashSet::new();
        for nsid in ALL_NSIDS {
            assert!(set.insert(*nsid), "duplicate NSID: {nsid}");
        }
    }

    #[test]
    fn quota_free_pins_is_three() {
        let (pins, _bytes) = quota_for_tier("free");
        assert_eq!(pins, QUOTA_FREE_PINS);
    }

    #[test]
    fn quota_free_bytes_is_100_mib() {
        let (_pins, bytes) = quota_for_tier("free");
        assert_eq!(bytes, 100 * 1024 * 1024);
    }

    #[test]
    fn quota_starter_pins_and_bytes() {
        let (pins, bytes) = quota_for_tier("starter");
        assert_eq!(pins, QUOTA_STARTER_PINS);
        assert_eq!(bytes, QUOTA_STARTER_BYTES);
    }

    #[test]
    fn quota_pro_pins_and_bytes() {
        let (pins, bytes) = quota_for_tier("pro");
        assert_eq!(pins, QUOTA_PRO_PINS);
        assert_eq!(bytes, QUOTA_PRO_BYTES);
    }

    #[test]
    fn quota_tiers_ordered_ascending() {
        let (free_pins, _) = quota_for_tier("free");
        let (starter_pins, _) = quota_for_tier("starter");
        let (pro_pins, _) = quota_for_tier("pro");
        assert!(
            free_pins < starter_pins,
            "free should have fewer pins than starter"
        );
        assert!(
            starter_pins < pro_pins,
            "starter should have fewer pins than pro"
        );
    }

    #[test]
    fn max_object_len_is_64_kib() {
        assert_eq!(MAX_OBJECT_LEN, 65_536);
    }

    #[test]
    fn max_triples_per_pin_is_1024() {
        assert_eq!(MAX_TRIPLES_PER_PIN, 1_024);
    }

    #[test]
    fn validate_triple_accepts_max_object_len() {
        let long_object = "x".repeat(MAX_OBJECT_LEN);
        let t = triple("did:key:zSub", "pred/path", &long_object);
        assert!(validate_triple(&t).is_ok());
    }

    #[test]
    fn validate_triple_rejects_over_max_object_len() {
        let too_long = "x".repeat(MAX_OBJECT_LEN + 1);
        let t = triple("did:key:zSub", "pred/path", &too_long);
        assert!(validate_triple(&t).is_err());
    }

    // ── Self-sovereign CACAO auth (no etzhayyim webauth) ─────────────────────────────

    /// Build `(issuer_did, base64(DAG-CBOR) CACAO)` signed by `seed`, mirroring
    /// exactly what `kotoba cacao-sign --graph <did> --capability <cap>` emits:
    /// an Ed25519 `did:key` issuer, `kotoba://graph/<graph>` + `kotoba://can/<cap>`
    /// resources, and an EdDSA signature over the SIWE plaintext. When `graph`
    /// is empty the CACAO self-scopes to the issuer's own DID (the pin flow).
    fn cli_cacao(seed: [u8; 32], graph: &str, capability: &str, nonce: &str) -> (String, String) {
        use base64::{
            engine::general_purpose::{STANDARD as B64, URL_SAFE_NO_PAD},
            Engine as _,
        };
        use ed25519_dalek::{Signer as _, SigningKey};
        let sk = SigningKey::from_bytes(&seed);
        let did = kotoba_auth::ed25519_pubkey_to_did_key(&sk.verifying_key().to_bytes());
        let graph_scope = if graph.is_empty() { did.clone() } else { graph.to_string() };
        let mut cacao = kotoba_auth::Cacao {
            h: kotoba_auth::CacaoHeader { t: "caip122".into() },
            p: kotoba_auth::CacaoPayload {
                iss: did.clone(),
                aud: did.clone(),
                issued_at: "2026-05-26T00:00:00Z".into(),
                expiry: Some("2099-01-01T00:00:00Z".into()),
                nonce: nonce.into(),
                domain: "kotoba.cli".into(),
                statement: None,
                version: "1".into(),
                resources: vec![
                    format!("kotoba://graph/{graph_scope}"),
                    format!("kotoba://can/{capability}"),
                ],
            },
            s: kotoba_auth::CacaoSig { t: "EdDSA".into(), s: String::new() },
        };
        let sig = sk.sign(cacao.siwe_message().as_bytes());
        cacao.s.s = URL_SAFE_NO_PAD.encode(sig.to_bytes());
        let mut cbor = Vec::new();
        ciborium::into_writer(&cacao, &mut cbor).expect("cacao cbor");
        (did, B64.encode(cbor))
    }

    fn cacao_headers(cacao_b64: &str) -> HeaderMap {
        let mut h = HeaderMap::new();
        h.insert("x-kotoba-cacao", cacao_b64.parse().unwrap());
        h
    }

    #[test]
    fn cli_cacao_authorizes_own_did_without_jwt() {
        let ns = crate::nonce_store::NonceStore::new();
        // A CACAO straight from `kotoba cacao-sign`, self-scoped, kotobase:pin cap.
        let (did, cacao) = cli_cacao([7u8; 32], "", CacaoPayload::OP_KOTOBASE_PIN, "nonce-pin");
        let res = require_did_ownership(&cacao_headers(&cacao), &did, "did:key:zOp", &ns);
        assert!(res.is_ok(), "self-signed kotobase:pin CACAO must authorize its own DID: {res:?}");
    }

    #[test]
    fn cacao_for_wrong_tenant_is_rejected() {
        let ns = crate::nonce_store::NonceStore::new();
        // Holder signs for their own DID but claims a different tenant_did.
        let (_did, cacao) = cli_cacao([8u8; 32], "", CacaoPayload::OP_KOTOBASE_PIN, "nonce-wrong");
        let res = require_did_ownership(&cacao_headers(&cacao), "did:key:zSomeoneElse", "did:key:zOp", &ns);
        assert!(res.is_err(), "CACAO must not authorize a tenant_did it does not own");
    }

    #[test]
    fn graph_query_cacao_cannot_be_replayed_as_pin_auth() {
        let ns = crate::nonce_store::NonceStore::new();
        // A CACAO minted for graph:query (not kotobase:pin) must NOT pass the pin gate.
        let (did, cacao) = cli_cacao([9u8; 32], "", CacaoPayload::OP_GRAPH_QUERY, "nonce-q");
        let res = require_did_ownership(&cacao_headers(&cacao), &did, "did:key:zOp", &ns);
        assert!(res.is_err(), "a graph:query CACAO must not authorize pin operations");
    }

    #[test]
    fn replayed_cacao_nonce_is_rejected() {
        let ns = crate::nonce_store::NonceStore::new();
        let (did, cacao) = cli_cacao([10u8; 32], "", CacaoPayload::OP_KOTOBASE_PIN, "nonce-replay");
        assert!(require_did_ownership(&cacao_headers(&cacao), &did, "did:key:zOp", &ns).is_ok());
        // Same CACAO (same nonce) a second time → replay rejected.
        assert!(require_did_ownership(&cacao_headers(&cacao), &did, "did:key:zOp", &ns).is_err());
    }
}
