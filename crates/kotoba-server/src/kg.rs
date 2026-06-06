//! yatabase KG entity lookup endpoint backed by kotoba Datom projection indexes.
//!
//! NSID: com.etzhayyim.apps.kotobase.kg.entity
//! All KG quads live in the named graph `kotobase-kg-v1`.
//!
//! Predicate conventions (written by seed_kotoba.py):
//!   kg/id           — nanoid primary key
//!   kg/qid          — Wikidata QID (e.g. "Q42")
//!   kg/type         — entity type string
//!   kg/label/ja     — Japanese label
//!   kg/label/en     — English label
//!   kg/confidence   — float string
//!   kg/license      — license SPDX
//!   kg/extractor    — extractor identifier
//!   kg/valid_from   — ISO-8601 date
//!   kg/valid_to     — ISO-8601 date
//!   kg/ingested_at  — ISO-8601 datetime
//!   kg/source_id    — source nanoid
//!   kg/claim/<pred> — property claim (Text / Float / Bool)
//!   kg/relation/<pred> — edge to another entity (Cid object = subject CID of dst)

use crate::graph_auth::{check_read_access, AccessDenied};
use crate::server::KotobaState;
use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use kotoba_core::cid::KotobaCid;
use kotoba_crypto::AgentCrypto;
use kotoba_datomic::distributed::{
    CommitDatomsRequest, DistributedCommitError, DistributedCommitWriter,
};
use kotoba_graph::quad_store::QuadStore;
use kotoba_ipfs::{IpnsName, IpnsRegistryError};
use kotoba_kqe::{
    datom::{Datom as KqeDatom, Value as KqeValue},
    delta::Delta,
    quad::LegacyQuad,
    quad::LegacyQuadObject as QuadObject,
};
use kotoba_kse::journal::Journal;
use kotoba_store::MemoryBlockStore;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

/// Require a valid, non-expired Bearer JWT to authorise KG write operations.
/// Any authenticated principal with a `sub` claim and a valid `exp` is accepted.
fn require_kg_write_auth(headers: &HeaderMap) -> Result<(), (StatusCode, String)> {
    let token = headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .ok_or_else(|| {
            tracing::warn!("kg write auth: missing Bearer token");
            (
                StatusCode::UNAUTHORIZED,
                "Authorization: Bearer <token> required for KG write operations".to_string(),
            )
        })?;
    if crate::graph_auth::jwt_exp_elapsed(token) {
        tracing::warn!("kg write auth: expired JWT");
        return Err((
            StatusCode::UNAUTHORIZED,
            "Bearer token has expired".to_string(),
        ));
    }
    crate::graph_auth::jwt_sub(token).ok_or_else(|| {
        tracing::warn!("kg write auth: JWT missing sub claim");
        (
            StatusCode::UNAUTHORIZED,
            "Bearer token missing sub claim".to_string(),
        )
    })?;
    Ok(())
}

pub const NSID_KG_ENTITY: &str = "com.etzhayyim.apps.kotobase.kg.entity";
pub const NSID_KG_CATALOG: &str = "com.etzhayyim.apps.kotobase.kg.catalog";
pub const NSID_KG_EMBED: &str = "com.etzhayyim.apps.kotobase.kg.embed";
pub const NSID_KG_SEARCH: &str = "com.etzhayyim.apps.kotobase.kg.search";
pub const NSID_KG_QUERY: &str = "com.etzhayyim.apps.kotobase.kg.query";
pub const NSID_KG_SPARQL: &str = "com.etzhayyim.apps.kotoba.graph.sparql";
const QUERY_ENGINE_DATOMIC: &str = "datomic";
const STORAGE_MODEL_IPLD_DAG_CBOR_PROLLY_TREE: &str = "ipld-dag-cbor-prolly-tree";
pub const NSID_KG_INGEST: &str = "com.etzhayyim.apps.kotobase.kg.ingest";
pub const NSID_KG_INGEST_BATCH: &str = "com.etzhayyim.apps.kotobase.kg.ingest_batch";
pub const NSID_KG_DELETE: &str = "com.etzhayyim.apps.kotobase.kg.delete";
pub const NSID_KG_COMMIT: &str = "com.etzhayyim.apps.kotobase.kg.commit";
pub const NSID_KG_MV_REGISTER: &str = "com.etzhayyim.apps.kotobase.kg.mv.register";
pub const NSID_KG_MV_RESULT: &str = "com.etzhayyim.apps.kotobase.kg.mv.result";

/// All yatabase KG quads are written into this named graph.
pub fn kg_graph_cid() -> KotobaCid {
    KotobaCid::from_bytes(b"kotobase-kg-v1")
}

fn kg_tx_cid(label: &str, parts: &[&str]) -> KotobaCid {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_nanos())
        .unwrap_or_default();
    KotobaCid::from_bytes(format!("kg:{label}:{nanos}:{}", parts.join(":")).as_bytes())
}

// ── Operator-trusted Pattern B content encryption (ADR-2605240001 §29.6) ──────
//
// Sensitive claim values are sealed at rest with the node's opaque vault key
// (`signal:v1:` envelope, stored as opaque Text — no AVET / SPARQL FILTER on the
// ciphertext: the documented §29.3 trade-off) and decrypted for CACAO-authorized
// readers. Operator-trusted (the node holds the key), NOT zero-knowledge.
//
// Opt-in via `KOTOBA_ENCRYPT_CLAIM_PREDS` = comma-separated FULL predicate names
// (e.g. "kg/claim/settlementAmount,kg/claim/ssn"). Unset/empty → no encryption,
// byte-identical to prior behaviour (zero regression for existing deploys).

/// `signal:v1:` envelope prefix (matches `kotoba_crypto::envelope::SIGNAL_VAL_PREFIX`).
const SIGNAL_ENVELOPE_PREFIX: &str = "signal:v1:";

/// Parse the sensitive-claim-predicate allowlist from the environment.
fn sensitive_claim_preds() -> std::collections::HashSet<String> {
    std::env::var("KOTOBA_ENCRYPT_CLAIM_PREDS")
        .ok()
        .map(|s| {
            s.split(',')
                .map(|p| p.trim().to_string())
                .filter(|p| !p.is_empty())
                .collect()
        })
        .unwrap_or_default()
}

/// Encrypt-on-write for a sensitive claim value. Scope = the full predicate
/// (domain separation). Falls back to plaintext when the predicate is not in
/// the allowlist, crypto is absent, or sealing fails — never silently drops data.
async fn maybe_seal_claim_value(
    crypto: Option<&Arc<dyn AgentCrypto>>,
    sensitive: &std::collections::HashSet<String>,
    full_pred: &str,
    value: &str,
) -> String {
    if !sensitive.contains(full_pred) {
        return value.to_string();
    }
    match crypto {
        Some(c) => c
            .seal_field(full_pred.as_bytes(), value)
            .await
            .unwrap_or_else(|_| value.to_string()),
        None => value.to_string(),
    }
}

/// Decrypt-on-read counterpart. Returns plaintext for a `signal:v1:` Text claim
/// object (scope = full predicate); otherwise delegates to `obj_to_json`.
/// Callers MUST have passed `check_read_access` first (operator-trusted: the
/// node decrypts for any CACAO-authorized reader).
async fn decrypt_claim_obj(
    crypto: Option<&Arc<dyn AgentCrypto>>,
    full_pred: &str,
    obj: &QuadObject,
) -> serde_json::Value {
    if let QuadObject::Text(s) = obj {
        if s.starts_with(SIGNAL_ENVELOPE_PREFIX) {
            if let Some(c) = crypto {
                if let Ok(pt) = c.open_field(full_pred.as_bytes(), s).await {
                    return serde_json::Value::String(pt);
                }
            }
        }
    }
    obj_to_json(obj)
}

fn kg_datom(subject: &KotobaCid, predicate: impl Into<String>, value: KqeValue) -> KqeDatom {
    KqeDatom::assert(
        subject.clone(),
        predicate.into(),
        value,
        KotobaCid::from_bytes(b"kotoba-kg-pending-tx"),
    )
}

async fn commit_kg_datoms(
    state: &Arc<KotobaState>,
    entity: KotobaCid,
    tx_cid: KotobaCid,
    mut datoms: Vec<KqeDatom>,
    author: String,
    auth_proof_cid: Option<KotobaCid>,
    auth_capability: Option<crate::xrpc::AuthCapabilityProjection>,
) -> Result<crate::xrpc::ProtocolDatomWriteResp, (StatusCode, String)> {
    let graph = kg_graph_cid();
    for datom in &mut datoms {
        datom.tx = tx_cid.clone();
    }
    // ADR-2606041151 B — capture this commit's datoms as assert-deltas so the
    // MaterializedView registry can be incrementally maintained after a
    // successful commit (kg ingest is assert-only; no-op when no views exist).
    let mv_deltas: Vec<kotoba_kqe::delta::Delta> = datoms
        .iter()
        .cloned()
        .map(kotoba_kqe::delta::Delta::assert_datom)
        .collect();
    let resp = crate::xrpc::commit_protocol_datoms(
        state,
        graph.clone(),
        graph.to_multibase(),
        entity,
        datoms
            .into_iter()
            .map(kotoba_datomic::Datom::from_kqe)
            .collect(),
        tx_cid,
        author,
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        auth_proof_cid,
        auth_capability,
    )
    .await;
    if resp.is_ok() {
        state.mv_registry.write().await.maintain(&mv_deltas);
    }
    resp
}

fn kg_legacy_write_auth(
    headers: &HeaderMap,
    fallback: &str,
) -> Result<crate::xrpc::ProtocolWriteAuth, (StatusCode, String)> {
    require_kg_write_auth(headers)?;
    Ok(crate::xrpc::ProtocolWriteAuth {
        author: kg_write_author(headers, fallback),
        auth_proof_cid: None,
        auth_capability: None,
    })
}

fn authorize_kg_write(
    state: &KotobaState,
    headers: &HeaderMap,
    cacao_b64: Option<&str>,
    presentation: Option<&kotoba_vc::VerifiablePresentation>,
    tx_cid: &KotobaCid,
) -> Result<crate::xrpc::ProtocolWriteAuth, (StatusCode, String)> {
    if cacao_b64.is_some() || presentation.is_some() {
        return crate::xrpc::authorize_protocol_datom_write(
            state,
            headers,
            &kg_graph_cid().to_multibase(),
            cacao_b64,
            presentation,
            &[kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT],
            Some(tx_cid),
        );
    }
    kg_legacy_write_auth(headers, &state.operator_did)
}

fn kg_write_author(headers: &HeaderMap, fallback: &str) -> String {
    headers
        .get(axum::http::header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .and_then(crate::graph_auth::jwt_sub)
        .unwrap_or_else(|| fallback.to_string())
}

async fn current_graph_quads(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
) -> Result<Vec<LegacyQuad>, (StatusCode, String)> {
    let db = crate::xrpc::current_db_for_graph(state, graph_cid).await?;
    Ok(db
        .datoms()
        .into_iter()
        .map(|datom| {
            let substrate = datom.to_kqe().unwrap_or_else(|_| KqeDatom {
                e: datom.e,
                a: datom.a,
                v: KqeValue::Text(kotoba_edn::to_string(&datom.v)),
                tx: datom.t,
                op: datom.added,
            });
            LegacyQuad {
                graph: graph_cid.clone(),
                subject: substrate.e,
                predicate: substrate.a,
                object: substrate.v.into(),
            }
        })
        .collect())
}

async fn current_graph_deltas(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
) -> Result<Vec<Delta>, (StatusCode, String)> {
    let db = crate::xrpc::current_db_for_graph(state, graph_cid).await?;
    Ok(db
        .datoms()
        .into_iter()
        .map(|datom| {
            datom.to_kqe().unwrap_or_else(|_| KqeDatom {
                e: datom.e,
                a: datom.a,
                v: KqeValue::Text(kotoba_edn::to_string(&datom.v)),
                tx: datom.t,
                op: datom.added,
            })
        })
        .map(Delta::from_datom)
        .collect())
}

/// Build an EAV `SchemaMap` from the predicates present in `deltas`.
///
/// Each distinct predicate `P` becomes a binary table `P(s, o)` whose value
/// column `o` maps straight to predicate `P` (entity column `s` = subject), so
/// enterprise SQL can address KG predicates directly: `SELECT t.s, t.o FROM "P" t`.
/// Without this, the compiler's binary fallback would read predicate `P/o`, which
/// no KG datom uses — the endpoint would be reachable but always return 0 rows.
fn schema_from_predicates(deltas: &[Delta]) -> kotoba_kqe::SchemaMap {
    use kotoba_kqe::{AttrDef, SchemaMap, TableSchema};
    let mut schema = SchemaMap::new();
    let mut seen = std::collections::HashSet::new();
    for d in deltas {
        let p = d.attribute();
        if seen.insert(p.to_string()) {
            schema.add(
                p,
                TableSchema::new("s").with_attr(AttrDef::scalar("o", p).with_predicate(p)),
            );
        }
    }
    schema
}

/// Readable string form of a datom object value, for resolving enterprise-SQL
/// result objects back from their content-hash CID. Matches the variants that
/// `kotoba_kqe::object_value_cid` indexes (Text/Integer/Bool/Cid).
fn readable_value(v: &KqeValue) -> String {
    match v {
        KqeValue::Text(s) => s.clone(),
        KqeValue::Integer(n) => n.to_string(),
        KqeValue::Bool(b) => b.to_string(),
        KqeValue::Cid(c) => c.to_multibase(),
        other => format!("{other:?}"),
    }
}

async fn distributed_query_store(
    state: &Arc<KotobaState>,
    graph_cid: &KotobaCid,
    as_of: Option<&str>,
    since: Option<&str>,
    remote_peer: Option<&str>,
    remote_ipns_name: Option<&str>,
) -> Result<(Arc<QuadStore>, Option<String>), (StatusCode, String)> {
    // Time-travel (as_of / since) and remote/distributed reads need a
    // point-in-time snapshot reconstructed from the datomic history → build an
    // ephemeral query store from that snapshot.
    if remote_peer.is_some() || remote_ipns_name.is_some() || as_of.is_some() || since.is_some() {
        let db = crate::xrpc::require_distributed_datomic_db(
            state,
            graph_cid,
            as_of,
            since,
            remote_peer,
            remote_ipns_name,
        )?;
        let basis_t = db.basis_t.as_ref().map(KotobaCid::to_multibase);
        let quads = datomic_db_quads(graph_cid, db);
        let query_store =
            QuadStore::new(Arc::new(Journal::new()), Arc::new(MemoryBlockStore::new()));
        query_store.assert_batch_silent(quads).await;
        return Ok((Arc::new(query_store), basis_t));
    }

    // Local current-state read: serve directly from the resident QuadStore.
    // Its hot 4-index Arrangement already reflects all committed datoms (applied
    // via `apply_journaled_datom` on every commit + WAL replay on startup), so
    // the SPARQL hot-path returns in O(result) — no O(graph) cold ProllyTree/Kubo
    // reconstruction and no per-query throwaway rebuild. (Previously every query
    // re-materialised the whole graph from cold storage: 71ms@1K → ~3s@10K, and
    // the concurrent cold reads wedged the Kubo sync-bridge pool at c≈16.)
    Ok((Arc::clone(&state.quad_store), None))
}

fn datomic_db_quads(graph_cid: &KotobaCid, db: kotoba_datomic::Db) -> Vec<LegacyQuad> {
    db.datoms()
        .into_iter()
        .map(|datom| {
            let substrate = datom.to_kqe().unwrap_or_else(|_| KqeDatom {
                e: datom.e,
                a: datom.a,
                v: KqeValue::Text(kotoba_edn::to_string(&datom.v)),
                tx: datom.t,
                op: datom.added,
            });
            LegacyQuad {
                graph: graph_cid.clone(),
                subject: substrate.e,
                predicate: substrate.a,
                object: substrate.v.into(),
            }
        })
        .collect()
}

fn kg_subject_by_predicate_value(
    quads: &[LegacyQuad],
    predicate: &str,
    value: &str,
) -> Option<KotobaCid> {
    quads
        .iter()
        .find(|quad| {
            quad.predicate == predicate
                && matches!(&quad.object, QuadObject::Text(text) if text == value)
        })
        .map(|quad| quad.subject.clone())
}

fn kg_entity_quads<'a>(
    quads: &'a [LegacyQuad],
    subject: &'a KotobaCid,
) -> impl Iterator<Item = &'a LegacyQuad> {
    quads.iter().filter(move |quad| &quad.subject == subject)
}

const MAX_KG_ID_LEN: usize = 256;
const MAX_KG_TEXT_LEN: usize = 8_192; // max embed text — prevents inference-engine DoS
const MAX_KG_QUERY_LEN: usize = 2_048;
const MAX_KG_LIMIT: usize = 1_000;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgEntityQuery {
    pub id: Option<String>,
    pub qid: Option<String>,
    #[serde(default = "default_true")]
    pub include_claims: bool,
    #[serde(default = "default_true")]
    pub include_relations: bool,
    #[serde(default = "default_max_relations")]
    pub max_relations: usize,
    /// CACAO delegation chain for private graphs (DAG-CBOR, base64-standard encoded).
    pub cacao_b64: Option<String>,
}

fn default_true() -> bool {
    true
}
fn default_max_relations() -> usize {
    50
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KgEntityResp {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub entity: Option<serde_json::Value>,
    pub elapsed_ms: u128,
}

/// GET /xrpc/com.etzhayyim.apps.kotobase.kg.entity?id=<nanoid>
/// GET /xrpc/com.etzhayyim.apps.kotobase.kg.entity?qid=Q42
pub async fn kg_entity(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<KgEntityQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use std::time::Instant;
    let t0 = Instant::now();
    let graph_cid = kg_graph_cid();

    // ── Read-access gate ─────────────────────────────────────────────────────
    let visibility = state.graph_visibility(&graph_cid).await;
    check_read_access(
        &visibility,
        &headers,
        q.cacao_b64.as_deref(),
        Some(&state.operator_did),
        Some(&state.nonce_store),
    )
    .map_err(AccessDenied::into_response)?;

    let (lookup_pred, lookup_val) = match (&q.id, &q.qid) {
        (Some(id), _) => {
            if id.len() > MAX_KG_ID_LEN {
                return Err((
                    StatusCode::BAD_REQUEST,
                    format!("id must be ≤{MAX_KG_ID_LEN} bytes"),
                ));
            }
            ("kg/id", id.as_str())
        }
        (_, Some(qid)) => {
            if qid.len() > MAX_KG_ID_LEN {
                return Err((
                    StatusCode::BAD_REQUEST,
                    format!("qid must be ≤{MAX_KG_ID_LEN} bytes"),
                ));
            }
            ("kg/qid", qid.as_str())
        }
        _ => {
            return Err((
                StatusCode::BAD_REQUEST,
                "missing `id` or `qid` query param".into(),
            ))
        }
    };

    let quads = current_graph_quads(&state, &graph_cid).await?;
    let subject_cid = match kg_subject_by_predicate_value(&quads, lookup_pred, lookup_val) {
        Some(s) => s,
        None => {
            return Ok(Json(KgEntityResp {
                ok: false,
                error: Some(format!("entity not found: {lookup_val}")),
                entity: None,
                elapsed_ms: t0.elapsed().as_millis(),
            }));
        }
    };

    let mut meta: serde_json::Map<String, serde_json::Value> = serde_json::Map::new();
    let mut claims: Vec<serde_json::Value> = Vec::new();
    let mut relations: Vec<serde_json::Value> = Vec::new();

    for quad in kg_entity_quads(&quads, &subject_cid) {
        let pred = quad.predicate.as_str();
        match pred {
            "kg/id" => {
                meta.insert("id".into(), obj_to_json(&quad.object));
            }
            "kg/qid" => {
                meta.insert("qid".into(), obj_to_json(&quad.object));
            }
            "kg/type" => {
                meta.insert("type".into(), obj_to_json(&quad.object));
            }
            "kg/label/ja" => {
                meta.insert("labelJa".into(), obj_to_json(&quad.object));
            }
            "kg/label/en" => {
                meta.insert("labelEn".into(), obj_to_json(&quad.object));
            }
            "kg/confidence" => {
                meta.insert("confidence".into(), obj_to_json(&quad.object));
            }
            "kg/license" => {
                meta.insert("license".into(), obj_to_json(&quad.object));
            }
            "kg/extractor" => {
                meta.insert("extractor".into(), obj_to_json(&quad.object));
            }
            "kg/valid_from" => {
                meta.insert("validFrom".into(), obj_to_json(&quad.object));
            }
            "kg/valid_to" => {
                meta.insert("validTo".into(), obj_to_json(&quad.object));
            }
            "kg/ingested_at" => {
                meta.insert("ingestedAt".into(), obj_to_json(&quad.object));
            }
            "kg/source_id" => {
                meta.insert("sourceId".into(), obj_to_json(&quad.object));
            }
            _ if pred.starts_with("kg/claim/") && q.include_claims => {
                let claim_pred = &pred["kg/claim/".len()..];
                // Decrypt operator-trusted Pattern B sealed claims for this
                // CACAO-authorized reader (no-op for plaintext claims).
                let value = decrypt_claim_obj(state.crypto.as_ref(), pred, &quad.object).await;
                claims.push(serde_json::json!({
                    "predicate": claim_pred,
                    "value":     value,
                }));
            }
            _ if pred.starts_with("kg/relation/")
                && q.include_relations
                && relations.len() < q.max_relations.min(MAX_KG_LIMIT) =>
            {
                let rel_pred = &pred["kg/relation/".len()..];
                relations.push(serde_json::json!({
                    "predicate": rel_pred,
                    "dstCid":    match &quad.object {
                        QuadObject::Cid(c) => c.to_multibase(),
                        other              => format!("{other:?}"),
                    },
                }));
            }
            _ => {}
        }
    }

    if q.include_claims {
        meta.insert("claims".into(), serde_json::Value::Array(claims));
    }
    if q.include_relations {
        meta.insert("relations".into(), serde_json::Value::Array(relations));
    }

    Ok(Json(KgEntityResp {
        ok: true,
        error: None,
        entity: Some(serde_json::Value::Object(meta)),
        elapsed_ms: t0.elapsed().as_millis(),
    }))
}

fn obj_to_json(obj: &QuadObject) -> serde_json::Value {
    match obj {
        QuadObject::Text(s) => serde_json::Value::String(s.clone()),
        QuadObject::Integer(n) => serde_json::json!(n),
        QuadObject::Float(f) => serde_json::json!(f),
        QuadObject::Bool(b) => serde_json::json!(b),
        QuadObject::Cid(c) => serde_json::Value::String(c.to_multibase()),
        _ => serde_json::Value::Null,
    }
}

// ── kg.catalog ────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgCatalogQuery {
    /// CACAO delegation chain for private graphs (DAG-CBOR, base64-standard encoded).
    pub cacao_b64: Option<String>,
}

/// GET /xrpc/com.etzhayyim.apps.kotobase.kg.catalog
/// Returns aggregate stats and source breakdown from the distributed Datomic DB.
pub async fn kg_catalog(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<KgCatalogQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use std::time::Instant;
    let t0 = Instant::now();
    let graph_cid = kg_graph_cid();

    // ── Read-access gate ─────────────────────────────────────────────────────
    let visibility = state.graph_visibility(&graph_cid).await;
    check_read_access(
        &visibility,
        &headers,
        q.cacao_b64.as_deref(),
        Some(&state.operator_did),
        Some(&state.nonce_store),
    )
    .map_err(AccessDenied::into_response)?;

    let quads = current_graph_quads(&state, &graph_cid).await?;
    let entity_count = quads
        .iter()
        .filter(|quad| quad.predicate == "kg/id")
        .count();
    let claim_count = quads
        .iter()
        .filter(|quad| quad.predicate.starts_with("kg/claim/"))
        .count();
    let relation_count = quads
        .iter()
        .filter(|quad| quad.predicate.starts_with("kg/relation/"))
        .count();

    // Gather source_ids from kg/source_id datoms.
    let mut source_counts: std::collections::HashMap<String, usize> =
        std::collections::HashMap::new();
    for quad in quads.iter().filter(|quad| quad.predicate == "kg/source_id") {
        let src = match &quad.object {
            QuadObject::Text(s) => s.clone(),
            other => format!("{other:?}"),
        };
        *source_counts.entry(src).or_insert(0) += 1;
    }
    let sources: Vec<serde_json::Value> = source_counts
        .into_iter()
        .map(|(id, count)| serde_json::json!({ "id": id, "entityCount": count }))
        .collect();

    Ok(Json(serde_json::json!({
        "ok": true,
        "stats": {
            "totalEntities":  entity_count,
            "totalClaims":    claim_count,
            "totalRelations": relation_count,
        },
        "sources":    sources,
        "elapsedMs":  t0.elapsed().as_millis(),
    })))
}

// ── kg.embed ──────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgEmbedReq {
    /// Nanoid entity ID — used to resolve the subject CID.
    pub entity_id: String,
    /// Text to embed (typically labelEn or labelJa).
    pub text: String,
    /// CACAO delegation chain for distributed Datom writes.
    pub cacao_b64: Option<String>,
    /// W3C Verifiable Presentation carrying a datom:transact capability.
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KgEmbedResp {
    pub ok: bool,
    pub dims: usize,
}

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.embed
/// Compute a blake3 pseudo-vector for `text` and store it as a `kg/label_vec`
/// VectorF32 quad for the entity.  Uses the inference engine when available.
pub async fn kg_embed(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<KgEmbedReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    if req.entity_id.is_empty() || req.entity_id.len() > MAX_KG_ID_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("entityId must be 1–{MAX_KG_ID_LEN} bytes"),
        ));
    }
    if req.text.is_empty() || req.text.len() > MAX_KG_TEXT_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("text must be 1–{MAX_KG_TEXT_LEN} bytes"),
        ));
    }
    let graph_cid = kg_graph_cid();
    let tx_cid = kg_tx_cid("embed", &[&req.entity_id]);
    let auth = authorize_kg_write(
        &state,
        &headers,
        req.cacao_b64.as_deref(),
        req.auth_presentation.as_ref(),
        &tx_cid,
    )?;

    let quads = current_graph_quads(&state, &graph_cid).await?;
    let subject =
        kg_subject_by_predicate_value(&quads, "kg/id", &req.entity_id).ok_or_else(|| {
            (
                StatusCode::NOT_FOUND,
                format!("entity not found: {}", req.entity_id),
            )
        })?;

    let vector: Vec<f32> = if let Some(engine) = &state.inference_engine {
        let engine = engine.clone();
        let text = format!("embed: {}", req.text);
        let result = tokio::task::spawn_blocking(move || engine(&text, 256))
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
        let parsed: Vec<f32> = result
            .split_whitespace()
            .filter_map(|s| s.parse::<f32>().ok())
            .collect();
        if parsed.is_empty() {
            blake3_pseudo_vector(&req.text, 128)
        } else {
            parsed
        }
    } else {
        blake3_pseudo_vector(&req.text, 128)
    };

    let dims = vector.len();
    let datom = kg_datom(&subject, "kg/label_vec", KqeValue::VectorF32(vector));
    commit_kg_datoms(
        &state,
        subject,
        tx_cid,
        vec![datom],
        auth.author,
        auth.auth_proof_cid,
        auth.auth_capability,
    )
    .await?;

    Ok(Json(KgEmbedResp { ok: true, dims }))
}

fn blake3_pseudo_vector(text: &str, dims: usize) -> Vec<f32> {
    let hash = blake3::hash(text.as_bytes());
    let hash_bytes = hash.as_bytes();
    (0..dims)
        .map(|i| {
            let b = hash_bytes[i % 32] as f32;
            (b / 127.5) - 1.0
        })
        .collect()
}

// ── kg.search ─────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgSearchQuery {
    /// Free-text query string
    pub q: String,
    #[serde(default = "default_limit")]
    pub limit: usize,
    /// CACAO delegation chain for private graphs (DAG-CBOR, base64-standard encoded).
    pub cacao_b64: Option<String>,
}
fn default_limit() -> usize {
    10
}

/// GET /xrpc/com.etzhayyim.apps.kotobase.kg.search?q=<text>&limit=10
/// Cosine similarity search over `kg/label_vec` VectorF32 quads.
pub async fn kg_search(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<KgSearchQuery>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use std::time::Instant;
    if q.q.is_empty() || q.q.len() > MAX_KG_QUERY_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("q must be 1–{MAX_KG_QUERY_LEN} bytes"),
        ));
    }
    let t0 = Instant::now();
    let graph_cid = kg_graph_cid();
    let limit = q.limit.min(MAX_KG_LIMIT);

    // ── Read-access gate ─────────────────────────────────────────────────────
    let visibility = state.graph_visibility(&graph_cid).await;
    check_read_access(
        &visibility,
        &headers,
        q.cacao_b64.as_deref(),
        Some(&state.operator_did),
        Some(&state.nonce_store),
    )
    .map_err(AccessDenied::into_response)?;

    // Use inference engine for query embedding when available, matching kg_embed semantics.
    // Falls back to blake3 pseudo-vector so search works without an LLM.
    let query_vec: Vec<f32> = if let Some(engine) = &state.inference_engine {
        let engine = engine.clone();
        let text = format!("embed: {}", q.q);
        let result = tokio::task::spawn_blocking(move || engine(&text, 256))
            .await
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
            .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
        let parsed: Vec<f32> = result
            .split_whitespace()
            .filter_map(|s| s.parse::<f32>().ok())
            .collect();
        if parsed.is_empty() {
            blake3_pseudo_vector(&q.q, 128)
        } else {
            parsed
        }
    } else {
        blake3_pseudo_vector(&q.q, 128)
    };

    let quads = current_graph_quads(&state, &graph_cid).await?;

    // Score each entity
    let mut scored: Vec<(f32, KotobaCid)> = quads
        .iter()
        .filter(|quad| quad.predicate == "kg/label_vec")
        .filter_map(|quad| {
            if let QuadObject::VectorF32(v) = &quad.object {
                Some((cosine(&query_vec, v), quad.subject.clone()))
            } else {
                None
            }
        })
        .collect();

    scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    scored.truncate(limit);

    // Fetch entity metadata for top-k subjects
    let mut results: Vec<serde_json::Value> = Vec::with_capacity(scored.len());
    for (score, subject) in &scored {
        let mut meta: serde_json::Map<String, serde_json::Value> = serde_json::Map::new();
        meta.insert("score".into(), serde_json::json!(score));
        for quad in kg_entity_quads(&quads, subject) {
            match quad.predicate.as_str() {
                "kg/id" => {
                    meta.insert("id".into(), obj_to_json(&quad.object));
                }
                "kg/qid" => {
                    meta.insert("qid".into(), obj_to_json(&quad.object));
                }
                "kg/label/ja" => {
                    meta.insert("labelJa".into(), obj_to_json(&quad.object));
                }
                "kg/label/en" => {
                    meta.insert("labelEn".into(), obj_to_json(&quad.object));
                }
                "kg/type" => {
                    meta.insert("type".into(), obj_to_json(&quad.object));
                }
                _ => {}
            }
        }
        results.push(serde_json::Value::Object(meta));
    }

    Ok(Json(serde_json::json!({
        "ok":        true,
        "count":     results.len(),
        "results":   results,
        "elapsedMs": t0.elapsed().as_millis(),
    })))
}

// ── kg.ingest ─────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgClaim {
    pub pred: String,
    pub value: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgRelation {
    pub pred: String,
    pub dst_id: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgIngestReq {
    pub id: String,
    pub qid: Option<String>,
    #[serde(rename = "type")]
    pub kind: Option<String>,
    pub label_ja: Option<String>,
    pub label_en: Option<String>,
    pub confidence: Option<String>,
    pub license: Option<String>,
    pub extractor: Option<String>,
    pub valid_from: Option<String>,
    pub valid_to: Option<String>,
    pub ingested_at: Option<String>,
    pub source_id: Option<String>,
    /// Pre-computed embedding vector (e.g. from yatabase vLLM).
    /// When present, stored as `kg/label_vec` VectorF32 quad so that
    /// `kg_search` can do real cosine similarity without a local inference engine.
    #[serde(default)]
    pub label_vec: Vec<f32>,
    #[serde(default)]
    pub claims: Vec<KgClaim>,
    #[serde(default)]
    pub relations: Vec<KgRelation>,
    /// CACAO delegation chain for distributed Datom writes.
    pub cacao_b64: Option<String>,
    /// W3C Verifiable Presentation carrying a datom:transact capability.
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KgIngestResp {
    pub ok: bool,
    pub subject_cid: String,
    pub quad_count: usize,
}

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.ingest
///
/// Write a KG entity into the `kotobase-kg-v1` named graph. Each field becomes
/// a quad with predicate conventions matching `kg_entity` lookups.
const MAX_KG_CLAIMS: usize = 1_024;
const MAX_KG_RELATIONS: usize = 1_024;
const MAX_KG_VEC_DIMS: usize = 4_096;
const MAX_KG_FIELD_LEN: usize = 4_096;

pub async fn kg_ingest(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<KgIngestReq>,
) -> impl IntoResponse {
    use axum::Json as AxumJson;
    if req.id.is_empty() || req.id.len() > MAX_KG_ID_LEN {
        return (
            StatusCode::BAD_REQUEST,
            AxumJson(serde_json::json!({"ok": false, "error":
                format!("id must be 1–{MAX_KG_ID_LEN} bytes")})),
        )
            .into_response();
    }
    if req.claims.len() > MAX_KG_CLAIMS {
        return (
            StatusCode::BAD_REQUEST,
            AxumJson(serde_json::json!({"ok": false, "error":
                format!("claims array exceeds {MAX_KG_CLAIMS} entries")})),
        )
            .into_response();
    }
    if req.relations.len() > MAX_KG_RELATIONS {
        return (
            StatusCode::BAD_REQUEST,
            AxumJson(serde_json::json!({"ok": false, "error":
                format!("relations array exceeds {MAX_KG_RELATIONS} entries")})),
        )
            .into_response();
    }
    if req.label_vec.len() > MAX_KG_VEC_DIMS {
        return (
            StatusCode::BAD_REQUEST,
            AxumJson(serde_json::json!({"ok": false, "error":
                format!("labelVec exceeds {MAX_KG_VEC_DIMS} dimensions")})),
        )
            .into_response();
    }
    if req.label_vec.iter().any(|f| !f.is_finite()) {
        return (
            StatusCode::BAD_REQUEST,
            AxumJson(serde_json::json!({"ok": false, "error":
                "labelVec contains non-finite values (NaN/Inf)"})),
        )
            .into_response();
    }
    // Validate per-field lengths to prevent oversized individual quads
    for v in [
        &req.qid,
        &req.kind,
        &req.label_ja,
        &req.label_en,
        &req.license,
        &req.extractor,
        &req.valid_from,
        &req.valid_to,
        &req.ingested_at,
        &req.source_id,
    ]
    .into_iter()
    .flatten()
    {
        if v.len() > MAX_KG_FIELD_LEN {
            return (
                StatusCode::BAD_REQUEST,
                AxumJson(serde_json::json!({"ok": false, "error":
                              format!("field value exceeds {MAX_KG_FIELD_LEN} bytes")})),
            )
                .into_response();
        }
    }
    // Validate per-item predicate/value lengths within claims and relations
    for claim in &req.claims {
        if claim.pred.is_empty() || claim.pred.len() > MAX_KG_ID_LEN {
            return (
                StatusCode::BAD_REQUEST,
                AxumJson(serde_json::json!({"ok": false, "error":
                    format!("claim.pred must be 1–{MAX_KG_ID_LEN} bytes")})),
            )
                .into_response();
        }
        if claim.value.len() > MAX_KG_FIELD_LEN {
            return (
                StatusCode::BAD_REQUEST,
                AxumJson(serde_json::json!({"ok": false, "error":
                    format!("claim.value must be ≤{MAX_KG_FIELD_LEN} bytes")})),
            )
                .into_response();
        }
    }
    for rel in &req.relations {
        if rel.pred.is_empty() || rel.pred.len() > MAX_KG_ID_LEN {
            return (
                StatusCode::BAD_REQUEST,
                AxumJson(serde_json::json!({"ok": false, "error":
                    format!("relation.pred must be 1–{MAX_KG_ID_LEN} bytes")})),
            )
                .into_response();
        }
        if rel.dst_id.is_empty() || rel.dst_id.len() > MAX_KG_ID_LEN {
            return (
                StatusCode::BAD_REQUEST,
                AxumJson(serde_json::json!({"ok": false, "error":
                    format!("relation.dstId must be 1–{MAX_KG_ID_LEN} bytes")})),
            )
                .into_response();
        }
    }
    let subject = KotobaCid::from_bytes(req.id.as_bytes());

    let mut count = 0usize;
    let mut datoms = Vec::new();

    macro_rules! assert_text {
        ($pred:expr, $val:expr) => {{
            datoms.push(kg_datom(&subject, $pred, KqeValue::Text($val.to_string())));
            count += 1;
        }};
    }

    // Always write kg/id so lookup_subject_by_po works
    assert_text!("kg/id", &req.id);

    if let Some(v) = &req.qid {
        assert_text!("kg/qid", v);
    }
    if let Some(v) = &req.kind {
        assert_text!("kg/type", v);
    }
    if let Some(v) = &req.label_ja {
        assert_text!("kg/label/ja", v);
    }
    if let Some(v) = &req.label_en {
        assert_text!("kg/label/en", v);
    }
    if let Some(v) = &req.confidence {
        assert_text!("kg/confidence", v);
    }
    if let Some(v) = &req.license {
        assert_text!("kg/license", v);
    }
    if let Some(v) = &req.extractor {
        assert_text!("kg/extractor", v);
    }
    if let Some(v) = &req.valid_from {
        assert_text!("kg/valid_from", v);
    }
    if let Some(v) = &req.valid_to {
        assert_text!("kg/valid_to", v);
    }
    if let Some(v) = &req.ingested_at {
        assert_text!("kg/ingested_at", v);
    }
    if let Some(v) = &req.source_id {
        assert_text!("kg/source_id", v);
    }

    let sensitive = sensitive_claim_preds();
    for claim in &req.claims {
        let pred = format!("kg/claim/{}", claim.pred);
        let value =
            maybe_seal_claim_value(state.crypto.as_ref(), &sensitive, &pred, &claim.value).await;
        datoms.push(kg_datom(&subject, pred, KqeValue::Text(value)));
        count += 1;
    }

    for rel in &req.relations {
        let dst_cid = KotobaCid::from_bytes(rel.dst_id.as_bytes());
        datoms.push(kg_datom(
            &subject,
            format!("kg/relation/{}", rel.pred),
            KqeValue::Cid(dst_cid),
        ));
        count += 1;
    }

    if !req.label_vec.is_empty() {
        datoms.push(kg_datom(
            &subject,
            "kg/label_vec",
            KqeValue::VectorF32(req.label_vec.clone()),
        ));
        count += 1;
    }

    let tx_cid = kg_tx_cid("ingest", &[&req.id]);
    let auth = match authorize_kg_write(
        &state,
        &headers,
        req.cacao_b64.as_deref(),
        req.auth_presentation.as_ref(),
        &tx_cid,
    ) {
        Ok(auth) => auth,
        Err((code, msg)) => {
            return (
                code,
                AxumJson(serde_json::json!({"ok": false, "error": msg})),
            )
                .into_response();
        }
    };
    if let Err((code, msg)) = commit_kg_datoms(
        &state,
        subject.clone(),
        tx_cid,
        datoms,
        auth.author,
        auth.auth_proof_cid,
        auth.auth_capability,
    )
    .await
    {
        return (
            code,
            AxumJson(serde_json::json!({"ok": false, "error": msg})),
        )
            .into_response();
    }

    Json(KgIngestResp {
        ok: true,
        subject_cid: subject.to_multibase(),
        quad_count: count,
    })
    .into_response()
}

// ── kg.ingest_batch ───────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgIngestBatchReq {
    /// Up to MAX_KG_BATCH_SIZE entities to ingest in a single HTTP request.
    pub entities: Vec<KgIngestReq>,
    /// CACAO delegation chain for distributed Datom writes.
    pub cacao_b64: Option<String>,
    /// W3C Verifiable Presentation carrying a datom:transact capability.
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KgIngestBatchResp {
    pub ok: bool,
    /// CIDs of subjects ingested, in input order.
    pub subject_cids: Vec<String>,
    /// Total quads written across all entities.
    pub quad_count: usize,
    /// Number of entities ingested.
    pub entity_count: usize,
}

/// Maximum number of entities accepted in a single batch request.
/// Bounds per-request memory + amortises HTTP overhead.
const MAX_KG_BATCH_SIZE: usize = 1_000;

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.ingest_batch
///
/// Ingest up to `MAX_KG_BATCH_SIZE` entities in a single HTTP request.
/// Validation is run once before any writes; if any entity fails the entire
/// batch is rejected (all-or-nothing semantics).  Inserts are then performed
/// serially through the same Datom projection path as single-ingest, amortising the
/// HTTP + JSON + auth-gate cost across the whole batch.
pub async fn kg_ingest_batch(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<KgIngestBatchReq>,
) -> impl IntoResponse {
    use axum::Json as AxumJson;
    if req.entities.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            AxumJson(serde_json::json!({"ok": false,
                "error": "entities[] is empty"})),
        )
            .into_response();
    }
    if req.entities.len() > MAX_KG_BATCH_SIZE {
        return (
            StatusCode::BAD_REQUEST,
            AxumJson(serde_json::json!({"ok": false,
                "error": format!("batch size {} exceeds limit {MAX_KG_BATCH_SIZE}",
                    req.entities.len())})),
        )
            .into_response();
    }

    // Validate ALL entities up front so we never partially-write a batch.
    for (i, e) in req.entities.iter().enumerate() {
        if let Err(msg) = validate_ingest_req(e) {
            return (
                StatusCode::BAD_REQUEST,
                AxumJson(serde_json::json!({"ok": false,
                    "error": format!("entity[{i}]: {msg}")})),
            )
                .into_response();
        }
    }

    let mut subject_cids = Vec::with_capacity(req.entities.len());
    let mut total_quads = 0usize;
    let mut all_datoms = Vec::new();
    let first_subject = KotobaCid::from_bytes(req.entities[0].id.as_bytes());
    let sensitive = sensitive_claim_preds();

    for e in &req.entities {
        let subject = KotobaCid::from_bytes(e.id.as_bytes());
        subject_cids.push(subject.to_multibase());
        let mut count = 0usize;

        macro_rules! assert_text {
            ($pred:expr, $val:expr) => {{
                all_datoms.push(kg_datom(&subject, $pred, KqeValue::Text($val.to_string())));
                count += 1;
            }};
        }

        assert_text!("kg/id", &e.id);
        if let Some(v) = &e.qid {
            assert_text!("kg/qid", v);
        }
        if let Some(v) = &e.kind {
            assert_text!("kg/type", v);
        }
        if let Some(v) = &e.label_ja {
            assert_text!("kg/label/ja", v);
        }
        if let Some(v) = &e.label_en {
            assert_text!("kg/label/en", v);
        }
        if let Some(v) = &e.confidence {
            assert_text!("kg/confidence", v);
        }
        if let Some(v) = &e.license {
            assert_text!("kg/license", v);
        }
        if let Some(v) = &e.extractor {
            assert_text!("kg/extractor", v);
        }
        if let Some(v) = &e.valid_from {
            assert_text!("kg/valid_from", v);
        }
        if let Some(v) = &e.valid_to {
            assert_text!("kg/valid_to", v);
        }
        if let Some(v) = &e.ingested_at {
            assert_text!("kg/ingested_at", v);
        }
        if let Some(v) = &e.source_id {
            assert_text!("kg/source_id", v);
        }

        for claim in &e.claims {
            let pred = format!("kg/claim/{}", claim.pred);
            let value =
                maybe_seal_claim_value(state.crypto.as_ref(), &sensitive, &pred, &claim.value)
                    .await;
            all_datoms.push(kg_datom(&subject, pred, KqeValue::Text(value)));
            count += 1;
        }
        for rel in &e.relations {
            let dst_cid = KotobaCid::from_bytes(rel.dst_id.as_bytes());
            all_datoms.push(kg_datom(
                &subject,
                format!("kg/relation/{}", rel.pred),
                KqeValue::Cid(dst_cid),
            ));
            count += 1;
        }
        if !e.label_vec.is_empty() {
            all_datoms.push(kg_datom(
                &subject,
                "kg/label_vec",
                KqeValue::VectorF32(e.label_vec.clone()),
            ));
            count += 1;
        }
        total_quads += count;
    }

    let tx_cid = kg_tx_cid("ingest_batch", &[&req.entities.len().to_string()]);
    let auth = match authorize_kg_write(
        &state,
        &headers,
        req.cacao_b64.as_deref(),
        req.auth_presentation.as_ref(),
        &tx_cid,
    ) {
        Ok(auth) => auth,
        Err((code, msg)) => {
            return (
                code,
                AxumJson(serde_json::json!({"ok": false, "error": msg})),
            )
                .into_response();
        }
    };
    if let Err((code, msg)) = commit_kg_datoms(
        &state,
        first_subject,
        tx_cid,
        all_datoms,
        auth.author,
        auth.auth_proof_cid,
        auth.auth_capability,
    )
    .await
    {
        return (
            code,
            AxumJson(serde_json::json!({"ok": false, "error": msg})),
        )
            .into_response();
    }

    AxumJson(KgIngestBatchResp {
        ok: true,
        subject_cids,
        quad_count: total_quads,
        entity_count: req.entities.len(),
    })
    .into_response()
}

/// Validate a single ingest entity; returns `Err(human-message)` on any failure.
fn validate_ingest_req(e: &KgIngestReq) -> Result<(), String> {
    if e.id.is_empty() || e.id.len() > MAX_KG_ID_LEN {
        return Err(format!("id must be 1–{MAX_KG_ID_LEN} bytes"));
    }
    if e.claims.len() > MAX_KG_CLAIMS {
        return Err(format!("claims array exceeds {MAX_KG_CLAIMS} entries"));
    }
    if e.relations.len() > MAX_KG_RELATIONS {
        return Err(format!(
            "relations array exceeds {MAX_KG_RELATIONS} entries"
        ));
    }
    if e.label_vec.len() > MAX_KG_VEC_DIMS {
        return Err(format!("labelVec exceeds {MAX_KG_VEC_DIMS} dimensions"));
    }
    if e.label_vec.iter().any(|f| !f.is_finite()) {
        return Err("labelVec contains non-finite values (NaN/Inf)".into());
    }
    for v in [
        &e.qid,
        &e.kind,
        &e.label_ja,
        &e.label_en,
        &e.license,
        &e.extractor,
        &e.valid_from,
        &e.valid_to,
        &e.ingested_at,
        &e.source_id,
    ]
    .into_iter()
    .flatten()
    {
        if v.len() > MAX_KG_FIELD_LEN {
            return Err(format!("field value exceeds {MAX_KG_FIELD_LEN} bytes"));
        }
    }
    for c in &e.claims {
        if c.pred.is_empty() || c.pred.len() > MAX_KG_ID_LEN {
            return Err(format!("claim.pred must be 1–{MAX_KG_ID_LEN} bytes"));
        }
        if c.value.len() > MAX_KG_FIELD_LEN {
            return Err(format!("claim.value must be ≤{MAX_KG_FIELD_LEN} bytes"));
        }
    }
    for r in &e.relations {
        if r.pred.is_empty() || r.pred.len() > MAX_KG_ID_LEN {
            return Err(format!("relation.pred must be 1–{MAX_KG_ID_LEN} bytes"));
        }
        if r.dst_id.is_empty() || r.dst_id.len() > MAX_KG_ID_LEN {
            return Err(format!("relation.dstId must be 1–{MAX_KG_ID_LEN} bytes"));
        }
    }
    Ok(())
}

// ── kg.delete ─────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgDeleteReq {
    /// Entity nanoid — same as the `id` field used in kg.ingest.
    pub id: String,
    /// CACAO delegation chain for distributed Datom writes.
    pub cacao_b64: Option<String>,
    /// W3C Verifiable Presentation carrying a datom:transact capability.
    pub auth_presentation: Option<kotoba_vc::VerifiablePresentation>,
}

// ── kg.commit ─────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgCommitReq {
    /// Optional author DID for the commit metadata.  Defaults to the
    /// operator DID.
    pub author: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct KgCommitResp {
    pub ok: bool,
    pub commit_cid: String,
    pub ipns_name: String,
    pub ipns_sequence: u64,
    pub elapsed_ms: u128,
}

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.commit
///
/// Return the distributed Datomic/IPLD head for the KG graph.  New KG writes
/// publish their own DAG-CBOR/ProllyTree commits through IPNS; this endpoint is
/// now a compatibility checkpoint.  If no distributed KG head exists yet, it
/// snapshots the current KG DB view as the first distributed commit.
///
/// Restricted to operator DID — only the node operator may seal a commit.
pub async fn kg_commit(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<KgCommitReq>,
) -> impl IntoResponse {
    use std::time::Instant;
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(serde_json::json!({"ok": false, "error": msg}))).into_response();
    }
    let t0 = Instant::now();
    let graph = kg_graph_cid();
    let author = req
        .author
        .clone()
        .unwrap_or_else(|| state.operator_did.clone());
    let seq = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let ipns_name = crate::xrpc::distributed_graph_ipns_name(&graph);
    match state
        .ipns_registry
        .resolve(&IpnsName::new(ipns_name.clone()))
    {
        Ok(record) => {
            return Json(KgCommitResp {
                ok: true,
                commit_cid: record.value,
                ipns_name,
                ipns_sequence: record.sequence,
                elapsed_ms: t0.elapsed().as_millis(),
            })
            .into_response();
        }
        Err(IpnsRegistryError::NotFound(_)) => {}
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(serde_json::json!({
                    "ok": false, "error": format!("ipns resolve: {e}"),
                })),
            )
                .into_response();
        }
    }

    let db = match crate::xrpc::current_db_for_graph(&state, &graph).await {
        Ok(db) => db,
        Err((code, msg)) => {
            return (code, Json(serde_json::json!({"ok": false, "error": msg}))).into_response();
        }
    };
    let writer = DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry);
    match writer.commit_datoms(CommitDatomsRequest {
        ipns_name: ipns_name.clone(),
        graph: graph.clone(),
        datoms: db.datoms(),
        covering_datoms: None,
        expected_parent: None,
        tx_cid: Some(KotobaCid::from_bytes(
            format!("kg.commit:{}:{author}:{seq}", graph.to_multibase()).as_bytes(),
        )),
        author,
        seq: 1,
        valid_until: "2099-01-01T00:00:00Z".to_string(),
        ttl_secs: Some(60),
        cacao_proof_cid: None,
        ipns_controller_did: Some(state.operator_did.clone()),
        ipns_signing_key: Some(state.ipns_signing_key()),
    }) {
        Ok(report) => Json(KgCommitResp {
            ok: true,
            commit_cid: report.commit.cid.to_multibase(),
            ipns_name,
            ipns_sequence: report.ipns_record.sequence,
            elapsed_ms: t0.elapsed().as_millis(),
        })
        .into_response(),
        Err(e) => {
            let code = match e {
                DistributedCommitError::StaleParent { .. } => StatusCode::CONFLICT,
                _ => StatusCode::INTERNAL_SERVER_ERROR,
            };
            (
                code,
                Json(serde_json::json!({
                    "ok": false, "error": format!("distributed commit: {e}"),
                })),
            )
                .into_response()
        }
    }
}

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.delete
///
/// Retract all quads for the given entity from the `kotobase-kg-v1` graph.
/// Publishes a retract event to the Journal for each quad (WAL + GossipSub).
pub async fn kg_delete(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<KgDeleteReq>,
) -> impl IntoResponse {
    if req.id.is_empty() || req.id.len() > MAX_KG_ID_LEN {
        return (
            StatusCode::BAD_REQUEST,
            Json(serde_json::json!({
                "ok": false, "error": format!("id must be 1–{MAX_KG_ID_LEN} bytes"),
            })),
        )
            .into_response();
    }
    let graph = kg_graph_cid();
    let subject = KotobaCid::from_bytes(req.id.as_bytes());
    let tx_cid = KotobaCid::from_bytes(format!("kg.delete:{}", req.id).as_bytes());
    let auth = match if req.cacao_b64.is_some() || req.auth_presentation.is_some() {
        crate::xrpc::authorize_protocol_datom_write(
            &state,
            &headers,
            &graph.to_multibase(),
            req.cacao_b64.as_deref(),
            req.auth_presentation.as_ref(),
            &[kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT],
            Some(&tx_cid),
        )
    } else {
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did).map(|_| {
            crate::xrpc::ProtocolWriteAuth {
                author: state.operator_did.clone(),
                auth_proof_cid: None,
                auth_capability: None,
            }
        })
    } {
        Ok(auth) => auth,
        Err((code, msg)) => {
            return (code, Json(serde_json::json!({"ok": false, "error": msg}))).into_response();
        }
    };

    let db = match crate::xrpc::current_db_for_graph(&state, &graph).await {
        Ok(db) => db,
        Err((code, msg)) => {
            return (code, Json(serde_json::json!({"ok": false, "error": msg}))).into_response()
        }
    };
    let current_datoms: Vec<_> = db
        .datoms()
        .into_iter()
        .filter(|datom| datom.e == subject)
        .collect();

    let retracted = current_datoms.len();

    if retracted > 0 {
        let retract_datoms: Vec<_> = current_datoms
            .into_iter()
            .map(|datom| kotoba_datomic::Datom::retract(datom.e, datom.a, datom.v, tx_cid.clone()))
            .collect();
        if let Err((code, msg)) = crate::xrpc::commit_protocol_datoms(
            &state,
            graph.clone(),
            graph.to_multibase(),
            subject.clone(),
            retract_datoms,
            tx_cid,
            auth.author,
            kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
            auth.auth_proof_cid,
            auth.auth_capability,
        )
        .await
        {
            return (code, Json(serde_json::json!({"ok": false, "error": msg}))).into_response();
        }
    }

    (
        StatusCode::OK,
        Json(serde_json::json!({
            "ok":            true,
            "id":            req.id,
            "retractedCount": retracted,
        })),
    )
        .into_response()
}

fn cosine(a: &[f32], b: &[f32]) -> f32 {
    let len = a.len().min(b.len());
    let dot: f32 = a[..len]
        .iter()
        .zip(b[..len].iter())
        .map(|(x, y)| x * y)
        .sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if na == 0.0 || nb == 0.0 {
        0.0
    } else {
        dot / (na * nb)
    }
}

// ── kg.query ──────────────────────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct KgQueryReq {
    /// Query language: "sparql", "cypher", or an enterprise SQL dialect
    /// (oracle/tsql/hana/db2/teradata/snowflake/bigquery/presto/mdx/hiveql/mysql/postgresql).
    pub lang: String,
    /// Query string
    pub query: String,
    /// CACAO delegation chain for private graphs (DAG-CBOR, base64-standard encoded).
    pub cacao_b64: Option<String>,
    /// Maximum results to return (1–10000; default 1000).
    pub limit: Option<usize>,
    /// ADR-2606041151 B — when set to a `kg.mv.register`'d view name, serve the
    /// incrementally-maintained result instead of evaluating `query` from
    /// scratch. `lang`/`query` are still validated but not re-evaluated.
    #[serde(default)]
    pub mv_name: Option<String>,
    /// Emit a content-addressed provenance envelope (querySpecCid / queryJobCid /
    /// resultCid) over canonical DAG-CBOR. resultCid hashes the canonically-sorted
    /// results, so it is stable despite kg.query's unordered CID-pair output.
    /// Applies to both the from-scratch and materialized-view paths. Absent when
    /// false. Default false.
    #[serde(default)]
    pub emit_cid: bool,
}

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.query
/// Execute a SPARQL SELECT, Cypher MATCH/RETURN, or enterprise SQL SELECT
/// against the Datom projection. All compilers lower to a `DatalogProgram`.
///
/// All compilers enforce binary-relation arity (exactly 2 projected columns).
/// Results are returned as `[{ "a": "<cid>", "b": "<cid>" }]` pairs where
/// the variable names come from the compiled output_relation. For enterprise
/// SQL dialects, `LIMIT`/`OFFSET` are honoured (`ORDER BY` is not — output is
/// opaque content-addressed CID pairs).
const MAX_KG_QUERY_PROG_LEN: usize = 65_536; // 64 KiB — SPARQL/Cypher compile DoS guard

// ── kg.mv — MaterializedView registry (ADR-2606041151 B) ─────────────────────

#[derive(serde::Deserialize)]
pub struct MvRegisterReq {
    /// View name — also the output relation of the compiled program.
    pub name: String,
    /// "sparql" | "cypher".
    pub lang: String,
    /// The query whose maintained result becomes the view.
    pub query: String,
}

#[derive(serde::Serialize)]
pub struct MvRegisterResp {
    pub name: String,
    pub newly_registered: bool,
}

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.mv.register
///
/// Register (or replace) a Datalog MaterializedView compiled from a SPARQL or
/// Cypher query (ADR-2606041151 B). Once registered, the view is incrementally
/// maintained on every kg commit (`commit_kg_datoms` → `MvRegistry::maintain`)
/// and read via `kg.mv.result` — Datomic-Datalog served first-tier, without the
/// per-request from-scratch re-evaluation `kg.query` does today.
pub async fn kg_mv_register(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<MvRegisterReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_graph::sparql::SparqlCompiler;
    use kotoba_kqe::cypher::CypherCompiler;
    require_kg_write_auth(&headers)?;
    if req.name.is_empty() || req.name.len() > 128 {
        return Err((StatusCode::BAD_REQUEST, "name must be 1–128 bytes".into()));
    }
    if req.query.len() > MAX_KG_QUERY_PROG_LEN {
        return Err((StatusCode::BAD_REQUEST, "query too large".into()));
    }
    let program = match req.lang.as_str() {
        "sparql" => SparqlCompiler::compile(&req.query, &req.name)
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("SPARQL compile: {e}")))?
            .program,
        "cypher" => CypherCompiler::compile(&req.query, &req.name)
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("Cypher compile: {e}")))?
            .program,
        other => {
            return Err((
                StatusCode::BAD_REQUEST,
                format!("lang must be 'sparql' or 'cypher' (got '{other}')"),
            ))
        }
    };
    let newly_registered = state
        .mv_registry
        .write()
        .await
        .register(req.name.clone(), program);
    Ok(Json(MvRegisterResp {
        name: req.name,
        newly_registered,
    }))
}

#[derive(serde::Deserialize)]
pub struct MvResultReq {
    pub name: String,
}

#[derive(serde::Serialize)]
pub struct MvResultRow {
    pub s: String,
    pub a: String,
    pub v: String,
}

#[derive(serde::Serialize)]
pub struct MvResultResp {
    pub name: String,
    pub count: usize,
    pub rows: Vec<MvResultRow>,
}

/// POST /xrpc/com.etzhayyim.apps.kotobase.kg.mv.result
///
/// Read the maintained derived facts of a registered MaterializedView — the
/// accumulated, incrementally-maintained result (not a from-scratch eval).
pub async fn kg_mv_result(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<MvResultReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    require_kg_write_auth(&headers)?;
    let reg = state.mv_registry.read().await;
    let arr = reg
        .result(&req.name)
        .ok_or_else(|| (StatusCode::NOT_FOUND, format!("no view '{}'", req.name)))?;
    let rows: Vec<MvResultRow> = arr
        .current_datoms()
        .into_iter()
        .map(|d| MvResultRow {
            s: d.e.to_multibase(),
            a: d.a.clone(),
            v: readable_value(&d.v),
        })
        .collect();
    Ok(Json(MvResultResp {
        name: req.name,
        count: rows.len(),
        rows,
    }))
}

pub async fn kg_query(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<KgQueryReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use kotoba_graph::sparql::SparqlCompiler;
    use kotoba_kqe::cypher::CypherCompiler;
    use std::time::Instant;

    const MAX_KG_LANG_LEN: usize = 16;
    const MAX_KG_QUERY_RESULT_LIMIT: usize = 10_000;
    if req.lang.len() > MAX_KG_LANG_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "lang field too long ({} bytes, limit {MAX_KG_LANG_LEN})",
                req.lang.len()
            ),
        ));
    }
    if req.query.is_empty() || req.query.len() > MAX_KG_QUERY_PROG_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("query must be 1–{MAX_KG_QUERY_PROG_LEN} bytes"),
        ));
    }
    let is_enterprise_sql = kotoba_kqe::enterprise::dialect_by_name(&req.lang).is_some();
    if !matches!(req.lang.as_str(), "sparql" | "cypher") && !is_enterprise_sql {
        return Err((
            StatusCode::BAD_REQUEST,
            "lang must be 'sparql', 'cypher', or an enterprise SQL dialect \
             (oracle/tsql/hana/db2/teradata/snowflake/bigquery/presto/mdx/hiveql/mysql/postgresql)"
                .to_string(),
        ));
    }
    let result_limit = req
        .limit
        .unwrap_or(MAX_KG_LIMIT)
        .min(MAX_KG_QUERY_RESULT_LIMIT);

    let t0 = Instant::now();
    let graph_cid = kg_graph_cid();

    // ── Read-access gate ─────────────────────────────────────────────────────
    let visibility = state.graph_visibility(&graph_cid).await;
    check_read_access(
        &visibility,
        &headers,
        req.cacao_b64.as_deref(),
        Some(&state.operator_did),
        Some(&state.nonce_store),
    )
    .map_err(AccessDenied::into_response)?;

    // ADR-2606041151 B — route through a maintained MaterializedView when the
    // caller names one. Serves the incrementally-maintained result (read from the
    // registry, maintained on every commit) instead of the per-request
    // from-scratch evaluation below — first-tier Datomic-Datalog.
    if let Some(mv_name) = req.mv_name.as_deref() {
        let reg = state.mv_registry.read().await;
        let arr = reg
            .result(mv_name)
            .ok_or_else(|| (StatusCode::NOT_FOUND, format!("no maintained view '{mv_name}'")))?;
        let rows: Vec<serde_json::Value> = arr
            .current_datoms()
            .into_iter()
            .take(result_limit)
            .map(|d| serde_json::json!({ "a": d.e.to_multibase(), "b": readable_value(&d.v) }))
            .collect();
        let mut response = serde_json::json!({
            "lang":      req.lang,
            "count":     rows.len(),
            "results":   rows,
            "source":    "mv",
            "view":      mv_name,
            "elapsedMs": t0.elapsed().as_millis(),
        });
        if req.emit_cid {
            let canonical = query_canonical_result(&response);
            let lang = response
                .get("lang")
                .and_then(|v| v.as_str())
                .unwrap_or("")
                .to_string();
            let (spec, job, result_cid) =
                query_emit_cids(&state, &lang, &req.query, None, None, None, &canonical);
            if let Some(obj) = response.as_object_mut() {
                obj.insert("querySpecCid".to_string(), serde_json::Value::String(spec));
                obj.insert("queryJobCid".to_string(), serde_json::Value::String(job));
                obj.insert("resultCid".to_string(), serde_json::Value::String(result_cid));
            }
        }
        return Ok(Json(response));
    }

    // Load the current graph projection first — enterprise SQL builds its EAV
    // schema from the live predicate set.
    let input_deltas = current_graph_deltas(&state, &graph_cid).await?;

    // Compile query to DatalogProgram (+ PostProcess for SQL LIMIT/OFFSET).
    let (program, output_relation, post_process) = match req.lang.as_str() {
        "sparql" => {
            let compiled = SparqlCompiler::compile(&req.query, "kg_query_result")
                .map_err(|e| (StatusCode::BAD_REQUEST, format!("SPARQL compile: {e}")))?;
            (
                compiled.program,
                compiled.output_relation,
                kotoba_kqe::PostProcess::default(),
            )
        }
        "cypher" => {
            let compiled = CypherCompiler::compile(&req.query, "kg_query_result")
                .map_err(|e| (StatusCode::BAD_REQUEST, format!("Cypher compile: {e}")))?;
            (
                compiled.program,
                compiled.output_relation,
                kotoba_kqe::PostProcess::default(),
            )
        }
        sql_lang => {
            // Enterprise SQL dialect → DatalogProgram + PostProcess. Each live KG
            // predicate `P` is registered as a binary table `P(s, o)`, so
            // `SELECT t.s, t.o FROM "<predicate>" t` projects that predicate's
            // (subject, object) pairs.
            //
            // WHERE: equality (`col = 'literal'`, ANDed) filters correctly — the
            // engine normalises stored text and the literal through the same
            // cid_of_str hash. Non-equality operators (`<>`, `>`, `<`, `LIKE`, `OR`)
            // are now REJECTED fail-loud by apply_where (they cannot be evaluated
            // in CID space and previously returned an unfiltered superset).
            // ORDER BY is not applied. Object values in the response are resolved
            // back to their source scalar text via `value_index` (see below).
            let dialect = kotoba_kqe::enterprise::dialect_by_name(sql_lang)
                .ok_or_else(|| (StatusCode::BAD_REQUEST, format!("unknown lang: {sql_lang}")))?;
            let schema = schema_from_predicates(&input_deltas);
            let compiled = dialect
                .compile(&req.query, &schema, "kg_query_result")
                .map_err(|e| (StatusCode::BAD_REQUEST, format!("{sql_lang} compile: {e}")))?;
            (
                compiled.program,
                compiled.output_relation,
                compiled.post_process,
            )
        }
    };
    // For enterprise SQL, build a reverse index (object CID → source scalar) so
    // the response carries readable values instead of opaque content hashes. The
    // datalog engine stores only the hashed object CID in derived facts; we
    // recover the original from the input deltas. SPARQL/Cypher keep their
    // existing CID-multibase output shape (empty index → fallback).
    let value_index: std::collections::HashMap<String, String> = if is_enterprise_sql {
        input_deltas
            .iter()
            .filter_map(|d| {
                kotoba_kqe::object_value_cid(d.value())
                    .map(|cid| (cid.to_multibase(), readable_value(d.value())))
            })
            .collect()
    } else {
        std::collections::HashMap::new()
    };

    let derived = tokio::task::spawn_blocking(move || program.evaluate_delta(&input_deltas))
        .await
        .map_err(|e| {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("datalog eval join: {e}"),
            )
        })?;

    // Collect derived facts for the output_relation. SQL OFFSET skips leading
    // rows; the effective cap is the tighter of SQL LIMIT and the request limit.
    let sql_offset = post_process.offset.unwrap_or(0);
    let effective_limit = post_process
        .limit
        .map(|l| l.min(result_limit))
        .unwrap_or(result_limit);
    let results: Vec<serde_json::Value> = derived
        .iter()
        .filter(|d| d.attribute() == output_relation && d.is_assert())
        .skip(sql_offset)
        .take(effective_limit)
        .map(|d| {
            let b = match d.value() {
                kotoba_kqe::Value::Cid(c) => {
                    let mb = c.to_multibase();
                    // SQL path: resolve content-hash CID back to its source scalar.
                    value_index.get(&mb).cloned().unwrap_or(mb)
                }
                other => format!("{other:?}"),
            };
            serde_json::json!({ "a": d.entity().to_multibase(), "b": b })
        })
        .collect();

    let mut response = serde_json::json!({
        "ok":        true,
        "lang":      req.lang,
        "count":     results.len(),
        "results":   results,
        "elapsedMs": t0.elapsed().as_millis(),
    });
    // Optional content-addressed provenance over the canonically-SORTED results
    // (kg.query output is unordered CID pairs), so resultCid is stable. The
    // materialized-view fast path above emits the same envelopes.
    if req.emit_cid {
        let canonical = query_canonical_result(&response);
        let lang = response
            .get("lang")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let (spec, job, result_cid) =
            query_emit_cids(&state, &lang, &req.query, None, None, None, &canonical);
        if let Some(obj) = response.as_object_mut() {
            obj.insert("querySpecCid".to_string(), serde_json::Value::String(spec));
            obj.insert("queryJobCid".to_string(), serde_json::Value::String(job));
            obj.insert("resultCid".to_string(), serde_json::Value::String(result_cid));
        }
    }
    Ok(Json(response))
}

// ── Direct SPARQL form endpoint (SELECT / DESCRIBE / CONSTRUCT / ASK) ─────────

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct SparqlReq {
    /// SPARQL query string (max 64 KiB).  Auto-detects SELECT / DESCRIBE /
    /// CONSTRUCT / ASK from the leading keyword.
    pub query: String,
    /// Optional named graph CID (multibase).  Defaults to the kg-graph CID.
    pub graph: Option<String>,
    /// Optional `host:port` or `/ip4/<addr>/tcp/<port>` kotoba-ipfs peer used
    /// to resolve a remote graph head and DAG-CBOR/Prolly blocks.
    pub remote_peer: Option<String>,
    /// Optional IPNS name override for SPARQL reads. Defaults to the graph's
    /// canonical `k51-kotoba-{graphCid}` head.
    pub remote_ipns_name: Option<String>,
    /// Optional Datomic `as-of` transaction CID for SPARQL reads.
    pub as_of: Option<String>,
    /// Optional Datomic `since` transaction CID for SPARQL reads.
    pub since: Option<String>,
    /// CACAO delegation chain (DAG-CBOR + base64) for private graphs.
    pub cacao_b64: Option<String>,
    /// W3C Verifiable Presentation carrying operator-issued graph capabilities.
    #[serde(default)]
    pub presentation: Option<kotoba_vc::VerifiablePresentation>,
    /// Maximum results to materialise (defaults to 10000).
    pub limit: Option<usize>,
    /// For DESCRIBE only: number of hops to traverse along `QuadObject::Cid`
    /// edges starting from the matched seed subjects.  When > 0 dispatches to
    /// `sparql_describe_n_hop` instead of the single-level `sparql_describe`,
    /// returning the entire reachable subgraph deduplicated by entity.
    /// Useful for "multi-pop" social-graph / citation-chain expansion.
    #[serde(default)]
    pub max_hops: usize,
    /// Emit a content-addressed provenance envelope (querySpecCid / queryJobCid /
    /// resultCid) over canonical DAG-CBOR. The result envelope hashes the
    /// **canonically-sorted** quads, so resultCid is stable despite SPARQL's
    /// unordered bag semantics. Fields absent when false. Default false.
    #[serde(default)]
    pub emit_cid: bool,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.graph.sparql
///
/// Execute a SPARQL query directly against the distributed Datomic DB view.
/// Supports all four query forms; result shape varies:
///
///   - SELECT    →  `{ "form": "select",    "quads": [{...}] }`
///   - DESCRIBE  →  `{ "form": "describe",  "quads": [{...}] }`
///   - CONSTRUCT →  `{ "form": "construct", "quads": [{...}] }`
///   - ASK       →  `{ "form": "ask",       "result": true }`
///
/// Loads the current graph basis from IPNS/IPLD ProllyTree indexes, materialises
/// a local query-only projection, and honours CACAO gating per visibility policy.
pub async fn kg_sparql(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<SparqlReq>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    use std::time::Instant;

    const MAX_SPARQL_RESULT_LIMIT: usize = 100_000;
    if req.query.is_empty() || req.query.len() > MAX_KG_QUERY_PROG_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("query must be 1–{MAX_KG_QUERY_PROG_LEN} bytes"),
        ));
    }
    let limit = req.limit.unwrap_or(10_000).min(MAX_SPARQL_RESULT_LIMIT);

    // Resolve target graph CID.
    let graph_cid = match req.graph.as_deref() {
        None => kg_graph_cid(),
        Some(s) => kotoba_core::cid::KotobaCid::from_multibase(s)
            .ok_or((StatusCode::BAD_REQUEST, format!("invalid graph CID: {s}")))?,
    };

    crate::xrpc::require_datomic_read(
        &state,
        &headers,
        &graph_cid,
        req.cacao_b64.as_deref(),
        req.presentation.as_ref(),
        kotoba_auth::CacaoPayload::OP_GRAPH_QUERY,
        req.as_of.as_deref(),
        req.since.as_deref(),
    )
    .await?;

    // Detect the SPARQL query form from the leading keyword.
    let t0 = Instant::now();
    let head = req.query.trim_start();
    let upper: String = head
        .chars()
        .take(10)
        .collect::<String>()
        .to_ascii_uppercase();
    let (qs, basis_t) = distributed_query_store(
        &state,
        &graph_cid,
        req.as_of.as_deref(),
        req.since.as_deref(),
        req.remote_peer.as_deref(),
        req.remote_ipns_name.as_deref(),
    )
    .await?;

    let mut response = if upper.starts_with("ASK") {
        let result = qs
            .sparql_ask(&graph_cid, &req.query)
            .await
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("ASK eval: {e}")))?;
        serde_json::json!({
            "ok":        true,
            "form":      "ask",
            "queryEngine": QUERY_ENGINE_DATOMIC,
            "primaryQuery": crate::xrpc::NSID_DATOMIC_Q,
            "auxiliaryQuery": NSID_KG_SPARQL,
            "storageModel": STORAGE_MODEL_IPLD_DAG_CBOR_PROLLY_TREE,
            "basisT":    basis_t,
            "result":    result,
            "elapsedMs": t0.elapsed().as_millis(),
        })
    } else if upper.starts_with("DESCRIBE") {
        // Bound max_hops to a sane ceiling — N-hop is fully parallel per layer
        // but each hop fans out, so the per-request memory cost is O(reach).
        const MAX_HOPS_HARD_CAP: usize = 16;
        let max_hops = req.max_hops.min(MAX_HOPS_HARD_CAP);
        let quads = if max_hops == 0 {
            qs.sparql_describe(&graph_cid, &req.query).await
        } else {
            qs.sparql_describe_n_hop(&graph_cid, &req.query, max_hops)
                .await
        }
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("DESCRIBE eval: {e}")))?;
        let materialised: Vec<_> = quads.into_iter().take(limit).map(quad_to_json).collect();
        serde_json::json!({
            "ok":        true,
            "form":      "describe",
            "queryEngine": QUERY_ENGINE_DATOMIC,
            "primaryQuery": crate::xrpc::NSID_DATOMIC_Q,
            "auxiliaryQuery": NSID_KG_SPARQL,
            "storageModel": STORAGE_MODEL_IPLD_DAG_CBOR_PROLLY_TREE,
            "basisT":    basis_t,
            "maxHops":   max_hops,
            "count":     materialised.len(),
            "quads":     materialised,
            "elapsedMs": t0.elapsed().as_millis(),
        })
    } else if upper.starts_with("CONSTRUCT") {
        let quads = qs
            .sparql_construct(&graph_cid, &req.query)
            .await
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("CONSTRUCT eval: {e}")))?;
        let materialised: Vec<_> = quads.into_iter().take(limit).map(quad_to_json).collect();
        serde_json::json!({
            "ok":        true,
            "form":      "construct",
            "queryEngine": QUERY_ENGINE_DATOMIC,
            "primaryQuery": crate::xrpc::NSID_DATOMIC_Q,
            "auxiliaryQuery": NSID_KG_SPARQL,
            "storageModel": STORAGE_MODEL_IPLD_DAG_CBOR_PROLLY_TREE,
            "basisT":    basis_t,
            "count":     materialised.len(),
            "quads":     materialised,
            "elapsedMs": t0.elapsed().as_millis(),
        })
    } else if upper.starts_with("SELECT") {
        let quads = qs
            .cold_query_sparql_bgp(&graph_cid, &req.query)
            .await
            .map_err(|e| (StatusCode::BAD_REQUEST, format!("SELECT eval: {e}")))?;
        let materialised: Vec<_> = quads.into_iter().take(limit).map(quad_to_json).collect();
        serde_json::json!({
            "ok":        true,
            "form":      "select",
            "queryEngine": QUERY_ENGINE_DATOMIC,
            "primaryQuery": crate::xrpc::NSID_DATOMIC_Q,
            "auxiliaryQuery": NSID_KG_SPARQL,
            "storageModel": STORAGE_MODEL_IPLD_DAG_CBOR_PROLLY_TREE,
            "basisT":    basis_t,
            "count":     materialised.len(),
            "quads":     materialised,
            "elapsedMs": t0.elapsed().as_millis(),
        })
    } else {
        return Err((
            StatusCode::BAD_REQUEST,
            "query must start with SELECT, DESCRIBE, CONSTRUCT, or ASK".to_string(),
        ));
    };

    // Optional content-addressed provenance. resultCid hashes the canonically
    // SORTED result (SPARQL is an unordered bag), so it is stable across runs.
    if req.emit_cid {
        let canonical = query_canonical_result(&response);
        let basis = response
            .get("basisT")
            .and_then(|v| v.as_str())
            .map(str::to_string);
        let (spec, job, result_cid) = query_emit_cids(
            &state,
            "sparql",
            &req.query,
            basis.as_deref(),
            req.as_of.as_deref(),
            req.since.as_deref(),
            &canonical,
        );
        if let Some(obj) = response.as_object_mut() {
            obj.insert("querySpecCid".to_string(), serde_json::Value::String(spec));
            obj.insert("queryJobCid".to_string(), serde_json::Value::String(job));
            obj.insert("resultCid".to_string(), serde_json::Value::String(result_cid));
        }
    }
    Ok(Json(response))
}

#[derive(Serialize)]
struct SparqlQuerySpecEnvelope<'a> {
    #[serde(rename = "type")]
    kind: &'a str,
    lang: &'a str,
    query: String,
}

#[derive(Serialize)]
struct SparqlQueryJobEnvelope<'a> {
    #[serde(rename = "type")]
    kind: &'a str,
    query_spec: String,
    basis_t: Option<String>,
    as_of: Option<String>,
    since: Option<String>,
    engine: &'a str,
}

#[derive(Serialize)]
struct SparqlResultEnvelope<'a> {
    #[serde(rename = "type")]
    kind: &'a str,
    query_job: String,
    basis_t: Option<String>,
    engine: &'a str,
    result: &'a [String],
}

/// Canonical, deterministic representation of a query response for content-
/// addressing: the ASK boolean, or the materialised `quads`/`results` **sorted**
/// by their serialized form. SPARQL SELECT/DESCRIBE/CONSTRUCT and kg.query are
/// unordered bags (no `ORDER BY`), so the sort is what makes `resultCid` stable
/// across runs.
fn query_canonical_result(response: &serde_json::Value) -> Vec<String> {
    if let Some(b) = response.get("result") {
        return vec![format!("ask:{b}")];
    }
    for field in ["quads", "results"] {
        if let Some(arr) = response.get(field).and_then(|q| q.as_array()) {
            let mut rows: Vec<String> = arr.iter().map(|q| q.to_string()).collect();
            rows.sort();
            return rows;
        }
    }
    Vec::new()
}

/// Build the provenance envelopes for a graph/kg query → `(querySpecCid,
/// queryJobCid, resultCid)`. `resultCid` is content-derived over the
/// canonically-sorted result, so it is stable and tamper-evident. Blocks are PUT
/// best-effort (size-capped, un-pinned) via the shared `put_envelope`.
/// Canonicalization (R0): the query string is whitespace-normalized — weaker
/// than the datomic EDN-AST path; full algebra normalization is deferred.
fn query_emit_cids(
    state: &KotobaState,
    lang: &str,
    query: &str,
    basis_t: Option<&str>,
    as_of: Option<&str>,
    since: Option<&str>,
    canonical_result: &[String],
) -> (String, String, String) {
    const ENGINE: &str = concat!("kotoba-server/", env!("CARGO_PKG_VERSION"));
    let normalized = query.split_whitespace().collect::<Vec<_>>().join(" ");

    let spec = SparqlQuerySpecEnvelope {
        kind: "kotoba.queryspec.v1",
        lang,
        query: normalized,
    };
    let query_spec = crate::xrpc::put_envelope(state, &spec);

    let job = SparqlQueryJobEnvelope {
        kind: "kotoba.queryjob.v1",
        query_spec: query_spec.clone(),
        basis_t: basis_t.map(str::to_string),
        as_of: as_of.map(str::to_string),
        since: since.map(str::to_string),
        engine: ENGINE,
    };
    let query_job = crate::xrpc::put_envelope(state, &job);

    let result = SparqlResultEnvelope {
        kind: "kotoba.result.v1",
        query_job: query_job.clone(),
        basis_t: basis_t.map(str::to_string),
        engine: ENGINE,
        result: canonical_result,
    };
    let result_cid = crate::xrpc::put_envelope(state, &result);

    (query_spec, query_job, result_cid)
}

fn quad_to_json(q: kotoba_kqe::quad::LegacyQuad) -> serde_json::Value {
    serde_json::json!({
        "graph":     q.graph.to_multibase(),
        "subject":   q.subject.to_multibase(),
        "predicate": q.predicate,
        "object":    match q.object {
            QuadObject::Cid(c)      => serde_json::json!({"cid": c.to_multibase()}),
            QuadObject::Text(t)     => serde_json::json!({"text": t}),
            QuadObject::Integer(i)  => serde_json::json!({"int": i}),
            QuadObject::Float(f)    => serde_json::json!({"float": f}),
            QuadObject::Bool(b)     => serde_json::json!({"bool": b}),
            other                   => serde_json::json!({"raw": format!("{other:?}")}),
        },
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use axum::response::IntoResponse;
    use ed25519_dalek::Signer as _;
    use kotoba_core::cid::KotobaCid;
    use kotoba_core::named_graph::GraphVisibility;
    use kotoba_datomic::distributed::CommitDatomsRequest;
    use kotoba_datomic::Datom;
    use kotoba_edn::EdnValue;

    // ── kg_graph_cid ──────────────────────────────────────────────────────────

    #[test]
    fn kg_graph_cid_is_stable() {
        let a = kg_graph_cid();
        let b = kg_graph_cid();
        assert_eq!(a, b);
    }

    #[tokio::test]
    async fn kg_sparql_reads_named_distributed_ipns_head() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"kg-sparql-named-ipns-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            ("kg-sparql-named-ipns-graph".into(), GraphVisibility::Public),
        );

        let ipns_name = "k51-kotoba-kg-sparql-named-head".to_string();
        let tx = KotobaCid::from_bytes(b"kg-sparql-named-ipns-tx");
        let second_tx = KotobaCid::from_bytes(b"kg-sparql-named-ipns-second-tx");
        let alice = KotobaCid::from_bytes(b"kg-sparql-alice");
        let bob = KotobaCid::from_bytes(b"kg-sparql-bob");
        let writer = DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry);
        let first = writer
            .commit_datoms(CommitDatomsRequest {
                covering_datoms: None,
                ipns_name: ipns_name.clone(),
                graph: graph.clone(),
                datoms: vec![
                    Datom::assert(
                        alice.clone(),
                        "role".into(),
                        EdnValue::string("admin"),
                        tx.clone(),
                    ),
                    Datom::assert(alice, "name".into(), EdnValue::string("Alice"), tx.clone()),
                ],
                expected_parent: None,
                tx_cid: Some(tx.clone()),
                author: "did:key:zSparqlAuthor".into(),
                seq: 1,
                valid_until: "2030-01-01T00:00:00Z".into(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .unwrap();
        writer
            .commit_datoms(CommitDatomsRequest {
                covering_datoms: None,
                ipns_name: ipns_name.clone(),
                graph: graph.clone(),
                datoms: vec![
                    Datom::assert(
                        bob.clone(),
                        "role".into(),
                        EdnValue::string("editor"),
                        second_tx.clone(),
                    ),
                    Datom::assert(
                        bob,
                        "name".into(),
                        EdnValue::string("Bob"),
                        second_tx.clone(),
                    ),
                ],
                expected_parent: Some(first.commit.cid.clone()),
                tx_cid: Some(second_tx.clone()),
                author: "did:key:zSparqlAuthor".into(),
                seq: 2,
                valid_until: "2030-01-01T00:00:00Z".into(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .unwrap();

        let response = kg_sparql(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(SparqlReq {
                query: r#"SELECT ?s WHERE { ?s <role> "admin" }"#.into(),
                graph: Some(graph_mb.clone()),
                remote_peer: None,
                remote_ipns_name: Some(ipns_name.clone()),
                as_of: None,
                since: None,
                cacao_b64: None,
                presentation: None,
                limit: None,
                max_hops: 0,
                emit_cid: false,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(body["form"], "select");
        assert_eq!(body["queryEngine"], QUERY_ENGINE_DATOMIC);
        assert_eq!(body["primaryQuery"], crate::xrpc::NSID_DATOMIC_Q);
        assert_eq!(body["auxiliaryQuery"], NSID_KG_SPARQL);
        assert_eq!(
            body["storageModel"],
            STORAGE_MODEL_IPLD_DAG_CBOR_PROLLY_TREE
        );
        assert_eq!(body["count"], 1);
        assert_eq!(body["quads"][0]["predicate"], "role");
        assert_eq!(body["quads"][0]["object"]["text"], "admin");

        let as_of = kg_sparql(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(SparqlReq {
                query: r#"SELECT ?s WHERE { ?s <role> "editor" }"#.into(),
                graph: Some(graph_mb.clone()),
                remote_peer: None,
                remote_ipns_name: Some(ipns_name.clone()),
                as_of: Some(tx.to_multibase()),
                since: None,
                cacao_b64: None,
                presentation: None,
                limit: None,
                max_hops: 0,
                emit_cid: false,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(as_of.status(), StatusCode::OK);
        let as_of_body = axum::body::to_bytes(as_of.into_body(), usize::MAX)
            .await
            .unwrap();
        let as_of_body: serde_json::Value = serde_json::from_slice(&as_of_body).unwrap();
        assert_eq!(as_of_body["basisT"], tx.to_multibase());
        assert_eq!(as_of_body["count"], 0);

        let since = kg_sparql(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(SparqlReq {
                query: r#"SELECT ?s WHERE { ?s <role> "editor" }"#.into(),
                graph: Some(graph_mb),
                remote_peer: None,
                remote_ipns_name: Some(ipns_name),
                as_of: None,
                since: Some(tx.to_multibase()),
                cacao_b64: None,
                presentation: None,
                limit: None,
                max_hops: 0,
                emit_cid: false,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(since.status(), StatusCode::OK);
        let since_body = axum::body::to_bytes(since.into_body(), usize::MAX)
            .await
            .unwrap();
        let since_body: serde_json::Value = serde_json::from_slice(&since_body).unwrap();
        assert_eq!(since_body["basisT"], second_tx.to_multibase());
        assert_eq!(since_body["count"], 1);
        assert_eq!(since_body["quads"][0]["object"]["text"], "editor");
    }

    #[tokio::test]
    async fn kg_sparql_accepts_vp_graph_query_capability_for_private_graph() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = KotobaCid::from_bytes(b"kg-sparql-vp-private-graph");
        let graph_mb = graph.to_multibase();
        state.graph_registry.write().await.insert(
            graph.clone(),
            (
                "kg-sparql-vp-private-graph".into(),
                GraphVisibility::Private {
                    owner_did: state.operator_did.clone(),
                },
            ),
        );

        let ipns_name = "k51-kotoba-kg-sparql-vp-private-head".to_string();
        let tx = KotobaCid::from_bytes(b"kg-sparql-vp-private-tx");
        let alice = KotobaCid::from_bytes(b"kg-sparql-vp-private-alice");
        DistributedCommitWriter::new(&*state.block_store, &*state.ipns_registry)
            .commit_datoms(CommitDatomsRequest {
                covering_datoms: None,
                ipns_name: ipns_name.clone(),
                graph: graph.clone(),
                datoms: vec![Datom::assert(
                    alice,
                    "role".into(),
                    EdnValue::string("admin"),
                    tx.clone(),
                )],
                expected_parent: None,
                tx_cid: Some(tx),
                author: state.operator_did.clone(),
                seq: 1,
                valid_until: "2030-01-01T00:00:00Z".into(),
                ttl_secs: Some(60),
                cacao_proof_cid: None,
                ipns_controller_did: None,
                ipns_signing_key: None,
            })
            .unwrap();

        let denied = kg_sparql(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(SparqlReq {
                query: r#"SELECT ?s WHERE { ?s <role> "admin" }"#.into(),
                graph: Some(graph_mb.clone()),
                remote_peer: None,
                remote_ipns_name: Some(ipns_name.clone()),
                as_of: None,
                since: None,
                cacao_b64: None,
                presentation: None,
                limit: None,
                max_hops: 0,
                emit_cid: false,
            }),
        )
        .await;
        assert!(
            denied.is_err(),
            "private graph must reject unauthenticated SPARQL"
        );

        let response = kg_sparql(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(SparqlReq {
                query: r#"SELECT ?s WHERE { ?s <role> "admin" }"#.into(),
                graph: Some(graph_mb),
                remote_peer: None,
                remote_ipns_name: Some(ipns_name),
                as_of: None,
                since: None,
                cacao_b64: None,
                presentation: Some(signed_capability_presentation(
                    &state,
                    &graph,
                    kotoba_auth::CacaoPayload::OP_GRAPH_QUERY,
                    "graph.sparql",
                )),
                limit: None,
                max_hops: 0,
                emit_cid: false,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);
        let body = axum::body::to_bytes(response.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(body["form"], "select");
        assert_eq!(body["count"], 1);
        assert_eq!(body["quads"][0]["object"]["text"], "admin");
    }

    #[tokio::test]
    async fn kg_ingest_accepts_vp_datom_transact_capability() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        let state = Arc::new(KotobaState::new(None).unwrap());
        let graph = kg_graph_cid();

        let response = kg_ingest(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(KgIngestReq {
                id: "kg-vp-ingest-1".into(),
                qid: None,
                kind: Some("test".into()),
                label_ja: None,
                label_en: Some("VP Ingest".into()),
                confidence: None,
                license: None,
                extractor: None,
                valid_from: None,
                valid_to: None,
                ingested_at: None,
                source_id: None,
                label_vec: vec![],
                claims: vec![],
                relations: vec![],
                cacao_b64: None,
                auth_presentation: Some(signed_capability_presentation(
                    &state,
                    &graph,
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                    "kg.ingest",
                )),
            }),
        )
        .await
        .into_response();
        assert_eq!(response.status(), StatusCode::OK);

        let db = crate::xrpc::current_db_for_graph(&state, &graph)
            .await
            .unwrap();
        assert!(db.datoms().iter().any(|datom| {
            datom.a == ":capability/operation"
                && datom.v == EdnValue::string(kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT)
        }));
        assert!(db.datoms().iter().any(|datom| {
            datom.a == ":capability/proofFormat"
                && datom.v == EdnValue::string("W3C VerifiablePresentation")
        }));
    }

    /// 実動作検証 (real e2e, ADR §21.8): operator-trusted Pattern B through the
    /// live `kg_ingest` → QuadStore → `kg_entity` handlers. Proves (1) a sensitive
    /// claim is SEALED at rest in the real store, (2) a non-sensitive claim stays
    /// plaintext, (3) an authorized read DECRYPTS the sealed claim back.
    #[tokio::test]
    async fn pattern_b_end_to_end_through_kg_handlers() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_IPNS_REQUIRE_SIGNATURE", "false");
        // Unique predicate so this process-global env never seals another test's claims.
        std::env::set_var("KOTOBA_ENCRYPT_CLAIM_PREDS", "kg/claim/secretAmount");

        let state = KotobaState::new(None).unwrap();
        let state = Arc::new(state.init_crypto().await.unwrap());
        let graph = kg_graph_cid();
        // Public so the kg_entity read gate passes without a CACAO.
        state
            .graph_registry
            .write()
            .await
            .insert(graph.clone(), ("kg-default".into(), GraphVisibility::Public));

        // ── Ingest one sensitive + one non-sensitive claim via the real handler ──
        let resp = kg_ingest(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(KgIngestReq {
                id: "verify-ent-1".into(),
                qid: None,
                kind: Some("test".into()),
                label_ja: None,
                label_en: Some("PublicLabel".into()),
                confidence: None,
                license: None,
                extractor: None,
                valid_from: None,
                valid_to: None,
                ingested_at: None,
                source_id: None,
                label_vec: vec![],
                claims: vec![
                    KgClaim {
                        pred: "secretAmount".into(),
                        value: "JPY 12,300,000".into(),
                    },
                    KgClaim {
                        pred: "publicNote".into(),
                        value: "not-secret".into(),
                    },
                ],
                relations: vec![],
                cacao_b64: None,
                auth_presentation: Some(signed_capability_presentation(
                    &state,
                    &graph,
                    kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
                    "kg.ingest",
                )),
            }),
        )
        .await
        .into_response();
        assert_eq!(resp.status(), StatusCode::OK, "ingest must succeed");

        // ── At rest: sensitive claim sealed, plaintext absent, public claim plain ──
        let db = crate::xrpc::current_db_for_graph(&state, &graph)
            .await
            .unwrap();
        let values: Vec<String> = db
            .datoms()
            .iter()
            .map(|d| kotoba_edn::to_string(&d.v))
            .collect();
        assert!(
            values.iter().any(|v| v.contains("signal:v1:")),
            "sensitive claim must be SEALED at rest; datom values = {values:?}"
        );
        assert!(
            !values.iter().any(|v| v.contains("JPY 12,300,000")),
            "plaintext of the sealed claim must NOT appear at rest"
        );
        assert!(
            values.iter().any(|v| v.contains("not-secret")),
            "non-sensitive claim must remain plaintext at rest"
        );

        // ── Authorized read decrypts the sealed claim back to plaintext ──
        let resp = kg_entity(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Query(KgEntityQuery {
                id: Some("verify-ent-1".into()),
                qid: None,
                include_claims: true,
                include_relations: false,
                max_relations: 50,
                cacao_b64: None,
            }),
        )
        .await
        .unwrap()
        .into_response();
        assert_eq!(resp.status(), StatusCode::OK);
        let body = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        let claims = body["entity"]["claims"]
            .as_array()
            .expect("entity.claims array");
        let secret = claims
            .iter()
            .find(|c| c["predicate"] == "secretAmount")
            .expect("secretAmount claim present");
        assert_eq!(
            secret["value"], "JPY 12,300,000",
            "authorized read must DECRYPT the sealed claim"
        );
        let public = claims
            .iter()
            .find(|c| c["predicate"] == "publicNote")
            .expect("publicNote claim present");
        assert_eq!(public["value"], "not-secret");

        std::env::remove_var("KOTOBA_ENCRYPT_CLAIM_PREDS");
    }

    fn signed_capability_presentation(
        state: &KotobaState,
        graph: &KotobaCid,
        operation: &str,
        challenge: &str,
    ) -> kotoba_vc::VerifiablePresentation {
        let holder = state.operator_did.clone();
        let mut credential = kotoba_vc::VerifiableCredential::new(
            format!("urn:uuid:{challenge}-vp-capability"),
            state.operator_did.clone(),
            serde_json::json!({
                "id": holder,
                "graph": graph.to_multibase(),
                "operation": operation,
                "scope": format!("kotoba://graph/{}", graph.to_multibase()),
            }),
        );
        credential
            .types
            .push("KotobaGraphCapabilityCredential".into());
        let credential_signature = state
            .ipns_signing_key()
            .sign(&credential.proof_bytes().unwrap());
        credential.proof = Some(kotoba_vc::DataIntegrityProof {
            proof_type: "DataIntegrityProof".into(),
            cryptosuite: Some("eddsa-2022".into()),
            proof_purpose: "assertionMethod".into(),
            verification_method: format!("{}#agent-ed25519", state.operator_did),
            created: Some("2026-05-30T00:00:00Z".into()),
            proof_value: multibase::encode(
                multibase::Base::Base58Btc,
                credential_signature.to_bytes(),
            ),
            challenge: Some(challenge.into()),
            domain: Some("kotoba.protocol.write".into()),
        });

        let mut presentation = kotoba_vc::VerifiablePresentation {
            context: vec![kotoba_vc::VC_CONTEXT_V2.into()],
            id: format!("urn:uuid:{challenge}-vp"),
            types: vec!["VerifiablePresentation".into()],
            holder: Some(state.operator_did.clone()),
            verifiable_credentials: vec![credential],
            proof: None,
        };
        let presentation_signature = state
            .ipns_signing_key()
            .sign(&presentation.proof_bytes().unwrap());
        presentation.proof = Some(kotoba_vc::DataIntegrityProof {
            proof_type: "DataIntegrityProof".into(),
            cryptosuite: Some("eddsa-2022".into()),
            proof_purpose: "authentication".into(),
            verification_method: format!("{}#agent-ed25519", state.operator_did),
            created: Some("2026-05-30T00:00:00Z".into()),
            proof_value: multibase::encode(
                multibase::Base::Base58Btc,
                presentation_signature.to_bytes(),
            ),
            challenge: Some(challenge.into()),
            domain: Some("kotoba.protocol.write".into()),
        });
        presentation
    }

    // ── Pattern B operator-trusted claim encryption (ADR §29.6 / §28.5 inc.2) ──

    #[tokio::test]
    async fn pattern_b_claim_seal_open_roundtrip() {
        use kotoba_crypto::VaultKeyedCrypto;
        use zeroize::Zeroizing;

        let crypto: Arc<dyn AgentCrypto> =
            Arc::new(VaultKeyedCrypto::new(Zeroizing::new([7u8; 32])));
        let mut sensitive = std::collections::HashSet::new();
        sensitive.insert("kg/claim/settlementAmount".to_string());

        // Sensitive claim → sealed `signal:v1:` envelope at rest.
        let sealed = maybe_seal_claim_value(
            Some(&crypto),
            &sensitive,
            "kg/claim/settlementAmount",
            "JPY 12,300,000",
        )
        .await;
        assert!(
            sealed.starts_with(SIGNAL_ENVELOPE_PREFIX),
            "sensitive claim must be sealed at rest, got {sealed}"
        );

        // Authorized read decrypts back to plaintext.
        let opened = decrypt_claim_obj(
            Some(&crypto),
            "kg/claim/settlementAmount",
            &QuadObject::Text(sealed.clone()),
        )
        .await;
        assert_eq!(opened, serde_json::json!("JPY 12,300,000"));

        // Non-sensitive predicate → plaintext passthrough (queryable).
        assert_eq!(
            maybe_seal_claim_value(Some(&crypto), &sensitive, "kg/claim/labelEn", "Acme").await,
            "Acme"
        );

        // Empty allowlist (default) → zero-regression passthrough.
        assert_eq!(
            maybe_seal_claim_value(
                Some(&crypto),
                &std::collections::HashSet::new(),
                "kg/claim/settlementAmount",
                "x",
            )
            .await,
            "x"
        );

        // Wrong scope (predicate) must NOT decrypt — domain separation; the
        // envelope is returned unchanged rather than leaking plaintext.
        assert_eq!(
            decrypt_claim_obj(
                Some(&crypto),
                "kg/claim/other",
                &QuadObject::Text(sealed.clone()),
            )
            .await,
            serde_json::Value::String(sealed)
        );
    }

    // ── obj_to_json ───────────────────────────────────────────────────────────

    #[test]
    fn obj_to_json_text() {
        let v = obj_to_json(&QuadObject::Text("hello".to_string()));
        assert_eq!(v, serde_json::json!("hello"));
    }

    #[test]
    fn obj_to_json_integer() {
        let v = obj_to_json(&QuadObject::Integer(42));
        assert_eq!(v, serde_json::json!(42));
    }

    #[test]
    fn obj_to_json_float() {
        let v = obj_to_json(&QuadObject::Float(3.14));
        assert!((v.as_f64().unwrap() - 3.14).abs() < 1e-10);
    }

    #[test]
    fn obj_to_json_bool() {
        assert_eq!(
            obj_to_json(&QuadObject::Bool(true)),
            serde_json::json!(true)
        );
        assert_eq!(
            obj_to_json(&QuadObject::Bool(false)),
            serde_json::json!(false)
        );
    }

    #[test]
    fn obj_to_json_cid_is_multibase_string() {
        let cid = KotobaCid::from_bytes(b"test-cid");
        let v = obj_to_json(&QuadObject::Cid(cid.clone()));
        assert_eq!(v.as_str().unwrap(), cid.to_multibase());
    }

    #[test]
    fn obj_to_json_bytes_is_null() {
        let v = obj_to_json(&QuadObject::Bytes(b"raw".to_vec()));
        assert_eq!(v, serde_json::Value::Null);
    }

    // ── blake3_pseudo_vector ──────────────────────────────────────────────────

    #[test]
    fn blake3_pseudo_vector_has_correct_dims() {
        let v = blake3_pseudo_vector("hello world", 64);
        assert_eq!(v.len(), 64);
    }

    #[test]
    fn blake3_pseudo_vector_values_in_minus1_plus1() {
        let v = blake3_pseudo_vector("test", 128);
        for x in &v {
            assert!(*x >= -1.0 && *x <= 1.0, "value out of range: {x}");
        }
    }

    #[test]
    fn blake3_pseudo_vector_is_deterministic() {
        let a = blake3_pseudo_vector("kotoba", 32);
        let b = blake3_pseudo_vector("kotoba", 32);
        assert_eq!(a, b);
    }

    #[test]
    fn blake3_pseudo_vector_differs_for_different_inputs() {
        let a = blake3_pseudo_vector("foo", 32);
        let b = blake3_pseudo_vector("bar", 32);
        assert_ne!(a, b);
    }

    // ── cosine ────────────────────────────────────────────────────────────────

    #[test]
    fn cosine_identical_vectors_is_one() {
        let v = vec![1.0f32, 2.0, 3.0];
        let s = cosine(&v, &v);
        assert!(
            (s - 1.0).abs() < 1e-6,
            "cosine of identical vectors must be 1.0, got {s}"
        );
    }

    #[test]
    fn cosine_orthogonal_vectors_is_zero() {
        let a = vec![1.0f32, 0.0];
        let b = vec![0.0f32, 1.0];
        let s = cosine(&a, &b);
        assert!(
            s.abs() < 1e-6,
            "cosine of orthogonal vectors must be 0.0, got {s}"
        );
    }

    #[test]
    fn cosine_zero_vector_returns_zero() {
        let a = vec![0.0f32, 0.0];
        let b = vec![1.0f32, 0.0];
        assert_eq!(cosine(&a, &b), 0.0);
    }

    #[test]
    fn cosine_opposite_vectors_is_minus_one() {
        let a = vec![1.0f32, 0.0];
        let b = vec![-1.0f32, 0.0];
        let s = cosine(&a, &b);
        assert!(
            (s + 1.0).abs() < 1e-6,
            "cosine of opposite vectors must be -1.0, got {s}"
        );
    }

    #[test]
    fn cosine_mismatched_lengths_clips_dot_product() {
        // dot = a[..2]·b[..2] = 1*1 + 0*0 = 1
        // na  = ||a||_full = sqrt(1 + 0 + 99²) ≈ 99.005
        // nb  = ||b||_full = 1.0
        // cosine ≈ 1 / (99.005 * 1) ≈ 0.0101 (clearly not 1.0)
        let a = vec![1.0f32, 0.0, 99.0];
        let b = vec![1.0f32, 0.0];
        let s = cosine(&a, &b);
        // The norms use the full vectors; dot uses only the shorter prefix.
        let expected = 1.0 / (f32::sqrt(1.0 + 0.0 + 99.0_f32 * 99.0) * 1.0);
        assert!((s - expected).abs() < 1e-5, "got {s}, expected {expected}");
    }

    // ── kg_query input-guard constants ────────────────────────────────────────

    #[test]
    fn kg_query_lang_length_constant_is_sane() {
        // MAX_KG_LANG_LEN must accept "sparql" and "cypher" (6 and 6 chars) with margin.
        assert!("sparql".len() <= 16, "MAX_KG_LANG_LEN must fit 'sparql'");
        assert!("cypher".len() <= 16, "MAX_KG_LANG_LEN must fit 'cypher'");
        // The constant must be small enough to prevent oversized error messages.
        assert!(16 <= 64, "MAX_KG_LANG_LEN should be modest");
    }

    #[test]
    fn kg_query_result_limit_constant_is_sane() {
        // MAX_KG_QUERY_RESULT_LIMIT (10000) is ≥ MAX_KG_LIMIT (1000) and ≤ MAX_DERIVED_FACTS.
        assert!(
            10_000 >= MAX_KG_LIMIT,
            "result limit must be ≥ default kg limit"
        );
        // A response of 10k rows should remain reasonable in size.
        assert!(
            10_000 <= 100_000,
            "result limit should be bounded for response safety"
        );
    }

    #[test]
    fn kg_query_limit_field_default_and_cap() {
        // Default: None → MAX_KG_LIMIT (1000).
        let default_limit = None::<usize>.unwrap_or(MAX_KG_LIMIT).min(10_000);
        assert_eq!(default_limit, MAX_KG_LIMIT);

        // Caller-supplied value is capped at MAX_KG_QUERY_RESULT_LIMIT.
        let caller_huge = Some(999_999usize).unwrap_or(MAX_KG_LIMIT).min(10_000);
        assert_eq!(
            caller_huge, 10_000,
            "oversized limit must be capped at 10_000"
        );

        // Caller-supplied small value passes through unchanged.
        let caller_small = Some(42usize).unwrap_or(MAX_KG_LIMIT).min(10_000);
        assert_eq!(caller_small, 42);
    }

    // ── kg.query enterprise SQL dialect wiring ────────────────────────────────

    #[tokio::test]
    async fn kg_query_rejects_unknown_lang_naming_dialects() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = Arc::new(KotobaState::new(None).unwrap());

        // lang validation runs before the read-access gate, so no graph/auth setup.
        let result = kg_query(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(KgQueryReq {
                lang: "sqlite".into(),
                query: "SELECT t.s, t.o FROM role t".into(),
                cacao_b64: None,
                limit: None,
                mv_name: None,
                emit_cid: false,
            }),
        )
        .await;
        match result {
            Ok(_) => panic!("unknown lang must be rejected"),
            Err((status, msg)) => {
                assert_eq!(status, StatusCode::BAD_REQUEST);
                assert!(
                    msg.contains("mysql") && msg.contains("postgresql"),
                    "error should name the enterprise dialects, got: {msg}"
                );
            }
        }
    }

    /// End-to-end reachability of the enterprise SQL path: validation → public
    /// read-access → dialect resolve → SQL compile → datalog eval → JSON.
    /// Data-bearing correctness of each dialect is covered by kotoba-kqe tests;
    /// here the empty kg graph yields count=0 but proves the pipeline runs.
    async fn assert_dialect_reachable(lang: &str) {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = Arc::new(KotobaState::new(None).unwrap());
        // Register the fixed kg graph as Public in this test's own state so the
        // read-access gate passes without CACAO (no global env mutation).
        state.graph_registry.write().await.insert(
            kg_graph_cid(),
            ("kg".into(), GraphVisibility::Public),
        );

        let resp = kg_query(
            State(Arc::clone(&state)),
            HeaderMap::new(),
            Json(KgQueryReq {
                lang: lang.into(),
                // Binary EAV fallback: table `role` → predicate `role/o`, cols s/o.
                query: "SELECT t.s, t.o FROM role t".into(),
                cacao_b64: None,
                limit: None,
                mv_name: None,
                emit_cid: false,
            }),
        )
        .await
        .unwrap_or_else(|e| panic!("{lang} query should succeed: {e:?}"))
        .into_response();
        assert_eq!(resp.status(), StatusCode::OK, "{lang} → 200");
        let body = axum::body::to_bytes(resp.into_body(), usize::MAX)
            .await
            .unwrap();
        let body: serde_json::Value = serde_json::from_slice(&body).unwrap();
        assert_eq!(body["ok"], true);
        assert_eq!(body["lang"], lang);
        assert_eq!(body["count"], 0, "empty kg graph → 0 rows");
    }

    #[tokio::test]
    async fn kg_query_accepts_postgresql_dialect_end_to_end() {
        assert_dialect_reachable("postgresql").await;
    }

    #[tokio::test]
    async fn kg_query_accepts_mysql_dialect_end_to_end() {
        assert_dialect_reachable("mysql").await;
    }

    /// Decisive data round-trip: schema_from_predicates maps a real KG predicate
    /// so `SELECT t.s, t.o FROM "<predicate>" t` actually projects its rows
    /// (proving the path is not inert). Uses the kqe compiler directly with the
    /// exact SchemaMap the handler builds.
    #[test]
    fn schema_from_predicates_projects_real_kg_predicate_rows() {
        use kotoba_core::cid::KotobaCid;
        use kotoba_kqe::datom::{Datom, Value};

        let g = KotobaCid::from_bytes(b"g");
        let cid = |s: &str| KotobaCid::from_bytes(s.as_bytes());
        let deltas = vec![
            Delta::assert_datom(Datom::assert(
                cid("alice"),
                "kg/claim/role".into(),
                Value::Text("admin".into()),
                g.clone(),
            )),
            Delta::assert_datom(Datom::assert(
                cid("bob"),
                "kg/claim/role".into(),
                Value::Text("user".into()),
                g.clone(),
            )),
            Delta::assert_datom(Datom::assert(
                cid("alice"),
                "kg/name".into(),
                Value::Text("Alice".into()),
                g,
            )),
        ];

        let schema = schema_from_predicates(&deltas);
        for lang in ["postgresql", "mysql"] {
            let dialect = kotoba_kqe::enterprise::dialect_by_name(lang).unwrap();
            let compiled = dialect
                .compile(
                    r#"SELECT t.s, t.o FROM "kg/claim/role" t"#,
                    &schema,
                    "kg_query_result",
                )
                .unwrap_or_else(|e| panic!("{lang} compile failed: {e}"));
            let derived = compiled.program.evaluate_delta(&deltas);
            let rows = derived
                .iter()
                .filter(|d| d.attribute() == "kg_query_result" && d.is_assert())
                .count();
            // Both role rows project; the kg/name predicate is excluded.
            assert_eq!(rows, 2, "{lang}: expected 2 role rows, got {rows}");
        }
    }

    /// Precise WHERE semantics over KG scalar (text) objects. The datalog engine
    /// normalises both stored `Value::Text` and the WHERE literal through
    /// `cid_of_str` into the same CID space, so **equality filters correctly**.
    /// Non-equality operators (`<>`, `>`, `LIKE`) cannot be evaluated in CID space
    /// and are now REJECTED fail-loud by `apply_where` (previously silently dropped
    /// → unfiltered superset). This test pins that contract.
    #[test]
    fn sql_where_equality_works_and_inequality_is_rejected() {
        use kotoba_core::cid::KotobaCid;
        use kotoba_kqe::datom::{Datom, Value};

        let g = KotobaCid::from_bytes(b"g");
        let cid = |s: &str| KotobaCid::from_bytes(s.as_bytes());
        let deltas = vec![
            Delta::assert_datom(Datom::assert(
                cid("alice"),
                "kg/claim/role".into(),
                Value::Text("admin".into()),
                g.clone(),
            )),
            Delta::assert_datom(Datom::assert(
                cid("bob"),
                "kg/claim/role".into(),
                Value::Text("user".into()),
                g,
            )),
        ];
        let schema = schema_from_predicates(&deltas);
        let pg = kotoba_kqe::enterprise::dialect_by_name("postgresql").unwrap();

        // Equality compiles and filters to the matching row.
        let eq = pg
            .compile(
                r#"SELECT t.s, t.o FROM "kg/claim/role" t WHERE t.o = 'admin'"#,
                &schema,
                "out",
            )
            .unwrap();
        let n = eq
            .program
            .evaluate_delta(&deltas)
            .iter()
            .filter(|d| d.attribute() == "out" && d.is_assert())
            .count();
        assert_eq!(n, 1, "equality on scalar text must filter to the matching row");

        // Non-equality operators are rejected at compile (fail-loud).
        for sql in [
            r#"SELECT t.s, t.o FROM "kg/claim/role" t WHERE t.o <> 'user'"#,
            r#"SELECT t.s, t.o FROM "kg/claim/role" t WHERE t.o LIKE 'adm%'"#,
            r#"SELECT t.s, t.o FROM "kg/claim/role" t WHERE t.o > 'm'"#,
        ] {
            match pg.compile(sql, &schema, "out") {
                Ok(_) => panic!("non-equality WHERE must be rejected: {sql}"),
                Err(e) => assert!(
                    e.to_string().contains("unsupported WHERE"),
                    "unexpected error for {sql}: {e}"
                ),
            }
        }
    }

    /// (a) Object value resolution: the handler reverse-indexes object CIDs back
    /// to source scalar text via `object_value_cid` + `readable_value` (the exact
    /// two lines kg_query uses), so `SELECT t.s, t.o` returns "admin", not a hash.
    #[test]
    fn sql_object_values_resolve_to_readable_text() {
        use kotoba_core::cid::KotobaCid;
        use kotoba_kqe::datom::{Datom, Value};

        let g = KotobaCid::from_bytes(b"g");
        let cid = |s: &str| KotobaCid::from_bytes(s.as_bytes());
        let deltas = vec![
            Delta::assert_datom(Datom::assert(
                cid("alice"),
                "kg/claim/role".into(),
                Value::Text("admin".into()),
                g.clone(),
            )),
            Delta::assert_datom(Datom::assert(
                cid("bob"),
                "kg/claim/age".into(),
                Value::Integer(42),
                g,
            )),
        ];
        let index: std::collections::HashMap<String, String> = deltas
            .iter()
            .filter_map(|d| {
                kotoba_kqe::object_value_cid(d.value())
                    .map(|c| (c.to_multibase(), readable_value(d.value())))
            })
            .collect();

        // A derived fact carries the object as Value::Cid(object_value_cid(value)).
        let admin_cid =
            kotoba_kqe::object_value_cid(&Value::Text("admin".into())).unwrap();
        assert_eq!(
            index.get(&admin_cid.to_multibase()).map(String::as_str),
            Some("admin"),
            "text object CID must resolve back to readable text"
        );
        let age_cid = kotoba_kqe::object_value_cid(&Value::Integer(42)).unwrap();
        assert_eq!(
            index.get(&age_cid.to_multibase()).map(String::as_str),
            Some("42"),
            "integer object CID must resolve back to its decimal string"
        );
    }

    // SPARQL resultCid must be order-independent (the canonical sort handles the
    // unordered-bag semantics): the same quads in different order → the same
    // resultCid; a changed quad → different; whitespace-only query edits don't
    // move querySpecCid; and every envelope is persisted (verify-by-CID).
    #[tokio::test]
    async fn sparql_emit_cid_result_is_order_independent_and_tamper_evident() {
        use kotoba_core::store::BlockStore as _;
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = KotobaState::new(None).unwrap();

        let q1 = serde_json::json!({"subject": "a", "predicate": "p", "object": {"text": "1"}});
        let q2 = serde_json::json!({"subject": "b", "predicate": "p", "object": {"text": "2"}});
        let resp_ab = serde_json::json!({"form": "select", "basisT": "tx1", "quads": [q1.clone(), q2.clone()]});
        let resp_ba = serde_json::json!({"form": "select", "basisT": "tx1", "quads": [q2.clone(), q1.clone()]});

        // Canonical result is identical regardless of quad order.
        assert_eq!(query_canonical_result(&resp_ab), query_canonical_result(&resp_ba));

        let sparql = "SELECT ?s WHERE { ?s ?p ?o }";
        let emit = |resp: &serde_json::Value| {
            query_emit_cids(&state, "sparql", sparql, Some("tx1"), None, None, &query_canonical_result(resp))
        };
        let (spec_ab, job_ab, result_ab) = emit(&resp_ab);
        let (_, _, result_ba) = emit(&resp_ba);
        // 1. Order-independence: a reordered bag yields the SAME resultCid.
        assert_eq!(result_ab, result_ba, "reordered SPARQL bag must yield the same resultCid");

        // 2. Tamper-evidence: a changed object moves resultCid.
        let q2b = serde_json::json!({"subject": "b", "predicate": "p", "object": {"text": "999"}});
        let resp_t = serde_json::json!({"form": "select", "basisT": "tx1", "quads": [q1, q2b]});
        assert_ne!(result_ab, emit(&resp_t).2, "changed quad must move resultCid");

        // 3. Canonicalization: whitespace-only query edits don't move querySpecCid.
        let (spec_spaced, _, _) = query_emit_cids(
            &state,
            "sparql",
            "SELECT   ?s\n  WHERE { ?s ?p ?o }",
            Some("tx1"),
            None,
            None,
            &query_canonical_result(&resp_ab),
        );
        assert_eq!(spec_ab, spec_spaced, "whitespace must not move querySpecCid");

        // 4. Verify-by-CID: every envelope was persisted.
        for cid in [&spec_ab, &job_ab, &result_ab] {
            let kcid = kotoba_core::cid::KotobaCid::from_multibase(cid).unwrap();
            assert!(state.block_store.get(&kcid).unwrap().is_some(), "envelope persisted: {cid}");
        }
    }

    // kg.query shares the generic emit path: the `results` field is canonicalized
    // (order-independent) and `lang` is part of querySpecCid (cypher ≠ sql).
    #[tokio::test]
    async fn kg_query_emit_cid_uses_results_field_and_lang() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = KotobaState::new(None).unwrap();

        let r1 = serde_json::json!({"a": "x", "b": "1"});
        let r2 = serde_json::json!({"a": "y", "b": "2"});
        let resp_ab = serde_json::json!({"ok": true, "results": [r1.clone(), r2.clone()]});
        let resp_ba = serde_json::json!({"ok": true, "results": [r2, r1]});
        // The "results" field is read and canonicalized order-independently.
        let canon = query_canonical_result(&resp_ab);
        assert_eq!(canon.len(), 2, "results field is read");
        assert_eq!(canon, query_canonical_result(&resp_ba), "results order must not matter");

        // lang is part of querySpec → same query text, different dialect → different CID.
        let q = "SELECT a, b FROM t";
        let (spec_sql, _, _) = query_emit_cids(&state, "sql", q, None, None, None, &canon);
        let (spec_cypher, _, _) = query_emit_cids(&state, "cypher", q, None, None, None, &canon);
        assert_ne!(spec_sql, spec_cypher, "lang must be part of querySpecCid");
    }
}
