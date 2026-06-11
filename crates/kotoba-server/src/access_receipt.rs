//! Access receipts — purpose-bound read accountability (ADR-sealed-cold-tier R1).
//!
//! Estonia/X-Road translation for kotoba: data may replicate freely (sealed,
//! R0), but a meaningful read of a non-public graph leaves a receipt — WHO
//! (DID), WHICH graph, WHAT operation, WHY (declared purpose), WHEN. Receipts
//! are datoms in the `kotoba/audit/access-receipts/v1` named graph, so they
//! are immutable, time-travel queryable, and ride the same distributed commit
//! / anchoring path as every other datom (R2 anchors their roots on Base).
//!
//! Quads emitted per receipt (subject = unique receipt CID):
//! - `(audit, r, "access/graph",        Text(target graph multibase))`
//! - `(audit, r, "access/accessor-did", Text(DID))` — CACAO leaf `iss`, else JWT `sub`
//! - `(audit, r, "access/operation",    Text(op))` — e.g. `datom:q`, `kg:entity`
//! - `(audit, r, "access/purpose",      Text(purpose))` — from `x-kotoba-purpose`
//! - `(audit, r, "access/ts-unix",      Integer(secs))`
//!
//! Write path: handlers enqueue on an unbounded channel; ONE background writer
//! batches receipts (`KOTOBA_RECEIPT_FLUSH_MS`, default 1000ms / 256 receipts)
//! into a single `commit_protocol_datoms` per batch. This keeps the read hot
//! path at ~a channel send, serialises audit-graph commits (no IPNS head
//! races), and amortises the distributed-commit cost — the lesson from the
//! request-fingerprint middleware's per-request commit pileup.
//!
//! Enforcement rollout: receipts are ALWAYS recorded for Authenticated/Private
//! reads at the instrumented seams. The `x-kotoba-purpose` header becomes
//! REQUIRED for Private-graph reads only when `KOTOBA_REQUIRE_PURPOSE` is
//! truthy — observe first, enforce when clients have migrated.

use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use axum::extract::{Query, State};
use axum::http::{HeaderMap, StatusCode};
use axum::Json;
use base64::{engine::general_purpose::STANDARD as B64, Engine as _};
use kotoba_core::cid::KotobaCid;
use kotoba_core::named_graph::GraphVisibility;
use serde::Deserialize;

use crate::server::KotobaState;

pub const NSID_AUDIT_LIST: &str = "com.etzhayyim.apps.kotoba.audit.listReceipts";

/// Header carrying the caller's declared purpose for a read.
pub const PURPOSE_HEADER: &str = "x-kotoba-purpose";
/// Longest stored purpose string (bytes, post-trim).
const MAX_PURPOSE_LEN: usize = 256;
/// A flush commits at most this many receipts (one tx).
const MAX_BATCH: usize = 256;

/// Named audit graph for access receipts. Fixed seed → stable across restarts
/// (same pattern as `fingerprint::audit_graph_cid`).
pub fn receipts_graph_cid() -> KotobaCid {
    KotobaCid::from_bytes(b"kotoba/audit/access-receipts/v1")
}

#[derive(Debug, Clone)]
pub struct AccessReceipt {
    pub graph_mb: String,
    pub accessor_did: Option<String>,
    pub operation: String,
    pub purpose: Option<String>,
    pub ts_unix: u64,
    /// CID of the presented CACAO's CBOR bytes (pinned to the block store) —
    /// the requester-signed half of the two-party evidence (R2b): the receipt
    /// commit is operator-signed (author_sig), the CACAO is requester-signed.
    pub cacao_cid: Option<String>,
}

/// Extract + sanitise the declared purpose from `x-kotoba-purpose`.
pub(crate) fn purpose_from_headers(headers: &HeaderMap) -> Option<String> {
    let raw = headers.get(PURPOSE_HEADER)?.to_str().ok()?.trim();
    if raw.is_empty() {
        return None;
    }
    let cleaned: String = raw
        .chars()
        .filter(|c| !c.is_control())
        .take(MAX_PURPOSE_LEN)
        .collect();
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned)
    }
}

/// Who is reading. Attribution follows the credential the gate actually
/// verified for this visibility tier: Private → the CACAO's leaf `iss` (its
/// signature chain was verified), falling back to the Bearer `sub`;
/// Authenticated → the Bearer `sub` FIRST, so a decorative (unverified) CACAO
/// attached to a Bearer-authed request cannot blame a third-party DID.
/// `None` only when the caller is anonymous.
pub(crate) fn accessor_from_request(
    headers: &HeaderMap,
    cacao_b64: Option<&str>,
    visibility: &GraphVisibility,
) -> Option<String> {
    let cacao_iss = || {
        let cbor = B64.decode(cacao_b64?).ok()?;
        kotoba_auth::Cacao::from_cbor(&cbor).ok().map(|c| c.p.iss)
    };
    let bearer_sub = || {
        headers
            .get(axum::http::header::AUTHORIZATION)
            .and_then(|v| v.to_str().ok())
            .and_then(|v| v.strip_prefix("Bearer "))
            .and_then(crate::graph_auth::jwt_sub)
    };
    match visibility {
        GraphVisibility::Private { .. } => cacao_iss().or_else(bearer_sub),
        _ => bearer_sub().or_else(cacao_iss),
    }
}

fn require_purpose_enabled() -> bool {
    std::env::var("KOTOBA_REQUIRE_PURPOSE")
        .map(|v| v == "1" || v.eq_ignore_ascii_case("true") || v.eq_ignore_ascii_case("on"))
        .unwrap_or(false)
}

/// Pure policy: is this (visibility, purpose) pair a violation under `enforce`?
fn purpose_violation(visibility: &GraphVisibility, purpose: Option<&str>, enforce: bool) -> bool {
    enforce && matches!(visibility, GraphVisibility::Private { .. }) && purpose.is_none()
}

/// Post-auth hook for instrumented read seams: enforce the purpose policy and
/// enqueue a receipt. Public reads pass through unrecorded (no identity, no
/// personal-data accountability obligation — Estonia's tracker covers personal
/// data, not open data).
pub(crate) fn enforce_and_record(
    state: &KotobaState,
    headers: &HeaderMap,
    cacao_b64: Option<&str>,
    graph: &KotobaCid,
    visibility: &GraphVisibility,
    operation: &str,
) -> Result<(), (StatusCode, String)> {
    if matches!(visibility, GraphVisibility::Public) {
        return Ok(());
    }
    let purpose = purpose_from_headers(headers);
    if purpose_violation(visibility, purpose.as_deref(), require_purpose_enabled()) {
        return Err((
            StatusCode::BAD_REQUEST,
            format!(
                "{PURPOSE_HEADER} header required: private-graph reads must declare a purpose \
                 (KOTOBA_REQUIRE_PURPOSE is on; ADR-sealed-cold-tier R1)"
            ),
        ));
    }
    // Pin the presented CACAO bytes as requester-signed evidence (only when
    // they actually parse — garbage would not have passed a Private gate).
    let cacao_cid = cacao_b64
        .and_then(|b64| B64.decode(b64).ok())
        .filter(|cbor| kotoba_auth::Cacao::from_cbor(cbor).is_ok())
        .map(|cbor| {
            let cid = KotobaCid::from_bytes(&cbor);
            if let Err(e) = state.block_store.put(&cid, &cbor) {
                tracing::warn!(err = %e, "cacao evidence block put failed");
            }
            cid.to_multibase()
        });
    let receipt = AccessReceipt {
        graph_mb: graph.to_multibase(),
        accessor_did: accessor_from_request(headers, cacao_b64, visibility),
        operation: operation.to_string(),
        purpose,
        ts_unix: SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
        cacao_cid,
    };
    if state.receipt_tx.send(receipt).is_err() {
        // Writer task gone (shutdown or never spawned outside a runtime):
        // best-effort in R1 — the read proceeds, loudly.
        tracing::warn!(graph = %graph.to_multibase(), operation, "access receipt DROPPED — writer unavailable");
    }
    Ok(())
}

/// Unique receipt subject CID: content fields + a process-monotonic counter so
/// two reads in the same second never collide.
fn receipt_cid(r: &AccessReceipt, seq: u64) -> KotobaCid {
    let mut buf = Vec::with_capacity(r.graph_mb.len() + 64);
    buf.extend_from_slice(r.graph_mb.as_bytes());
    buf.push(b'|');
    buf.extend_from_slice(r.accessor_did.as_deref().unwrap_or("").as_bytes());
    buf.push(b'|');
    buf.extend_from_slice(r.operation.as_bytes());
    buf.push(b'|');
    buf.extend_from_slice(&r.ts_unix.to_le_bytes());
    buf.push(b'|');
    buf.extend_from_slice(&seq.to_le_bytes());
    KotobaCid::from_bytes(&buf)
}

pub(crate) fn build_receipt_datoms(
    r: &AccessReceipt,
    subject: &KotobaCid,
    tx_cid: &KotobaCid,
) -> Vec<kotoba_datomic::Datom> {
    let mut datoms = vec![
        kotoba_datomic::Datom::assert(
            subject.clone(),
            "access/graph".to_string(),
            kotoba_edn::EdnValue::string(&r.graph_mb),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            subject.clone(),
            "access/operation".to_string(),
            kotoba_edn::EdnValue::string(&r.operation),
            tx_cid.clone(),
        ),
        kotoba_datomic::Datom::assert(
            subject.clone(),
            "access/ts-unix".to_string(),
            kotoba_edn::EdnValue::Integer(r.ts_unix as i64),
            tx_cid.clone(),
        ),
    ];
    if let Some(did) = &r.accessor_did {
        datoms.push(kotoba_datomic::Datom::assert(
            subject.clone(),
            "access/accessor-did".to_string(),
            kotoba_edn::EdnValue::string(did),
            tx_cid.clone(),
        ));
    }
    if let Some(purpose) = &r.purpose {
        datoms.push(kotoba_datomic::Datom::assert(
            subject.clone(),
            "access/purpose".to_string(),
            kotoba_edn::EdnValue::string(purpose),
            tx_cid.clone(),
        ));
    }
    if let Some(cacao_cid) = &r.cacao_cid {
        datoms.push(kotoba_datomic::Datom::assert(
            subject.clone(),
            "access/cacao-cid".to_string(),
            kotoba_edn::EdnValue::string(cacao_cid),
            tx_cid.clone(),
        ));
    }
    datoms
}

static RECEIPT_SEQ: AtomicU64 = AtomicU64::new(0);

/// Commit one batch of receipts as a single audit-graph tx.
pub(crate) async fn write_receipt_batch(state: &KotobaState, batch: Vec<AccessReceipt>) {
    if batch.is_empty() {
        return;
    }
    let graph = receipts_graph_cid();
    let first_seq = RECEIPT_SEQ.fetch_add(batch.len() as u64, Ordering::Relaxed);
    let tx_cid = KotobaCid::from_bytes(
        format!(
            "access.receipt.tx:{}:{}:{}",
            batch[0].ts_unix,
            first_seq,
            batch.len()
        )
        .as_bytes(),
    );
    let mut datoms = Vec::with_capacity(batch.len() * 5);
    let mut first_subject: Option<KotobaCid> = None;
    for (i, r) in batch.iter().enumerate() {
        let subject = receipt_cid(r, first_seq + i as u64);
        if first_subject.is_none() {
            first_subject = Some(subject.clone());
        }
        datoms.extend(build_receipt_datoms(r, &subject, &tx_cid));
    }
    let entity = first_subject.expect("non-empty batch");
    if let Err((status, message)) = crate::xrpc::commit_protocol_datoms(
        state,
        graph.clone(),
        graph.to_multibase(),
        entity,
        datoms,
        tx_cid,
        state.operator_did.clone(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        None,
        None,
    )
    .await
    {
        // Best-effort in R1 (same stance as request fingerprints): the
        // underlying read already happened; receipts harden to fail-closed
        // with the R2 signed-journal path.
        tracing::warn!(status = %status, error = %message, "access receipt batch commit failed");
    }
}

/// Start the single background receipt writer. Idempotent (the receiver can be
/// taken once); a no-op outside a tokio runtime (sync test contexts).
pub fn spawn_receipt_writer(state: Arc<KotobaState>) {
    if tokio::runtime::Handle::try_current().is_err() {
        tracing::warn!("access-receipt writer not started: no tokio runtime");
        return;
    }
    let Some(mut rx) = state.receipt_rx.lock().unwrap().take() else {
        return; // already running
    };
    let flush_ms: u64 = std::env::var("KOTOBA_RECEIPT_FLUSH_MS")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(1000);
    tokio::spawn(async move {
        loop {
            // Block until the first receipt of a batch arrives…
            let Some(first) = rx.recv().await else { break };
            let mut batch = vec![first];
            // …drain whatever is already queued (no waiting) so a backlog from
            // a slow commit clears at full speed instead of MAX_BATCH/window…
            while batch.len() < MAX_BATCH {
                match rx.try_recv() {
                    Ok(r) => batch.push(r),
                    Err(_) => break,
                }
            }
            // …then, if there is room, collect stragglers for one flush window.
            if batch.len() < MAX_BATCH {
                let deadline = tokio::time::sleep(std::time::Duration::from_millis(flush_ms));
                tokio::pin!(deadline);
                loop {
                    tokio::select! {
                        _ = &mut deadline => break,
                        more = rx.recv() => match more {
                            Some(r) => {
                                batch.push(r);
                                if batch.len() >= MAX_BATCH {
                                    break;
                                }
                            }
                            None => break,
                        },
                    }
                }
            }
            write_receipt_batch(&state, batch).await;
        }
        tracing::info!("access-receipt writer stopped (channel closed)");
    });
}

// ── audit.listReceipts XRPC ──────────────────────────────────────────────────

#[derive(Debug, Deserialize)]
pub struct AuditListQuery {
    /// Filter: target graph multibase CID.
    pub graph: Option<String>,
    /// Filter: accessor DID.
    pub accessor: Option<String>,
    /// Max receipts returned (default 100, cap 1000).
    pub limit: Option<usize>,
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.audit.listReceipts
///
/// Operator-gated in R1 (the owner-facing CACAO gate — Estonia's citizen Data
/// Tracker analog — lands with per-graph keys, where owner != operator becomes
/// the common case).
pub async fn audit_list_receipts(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<AuditListQuery>,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;

    let limit = q.limit.unwrap_or(100).min(1000);
    let graph = receipts_graph_cid();
    let quads = state
        .quad_store
        .quads_by_predicate_prefix(Some(&graph), "access/")
        .await;

    use std::collections::HashMap;
    let mut by_subject: HashMap<String, serde_json::Map<String, serde_json::Value>> =
        HashMap::new();
    for quad in quads {
        let entry = by_subject.entry(quad.subject.to_multibase()).or_default();
        let value: serde_json::Value = match &quad.object {
            kotoba_kqe::quad::LegacyQuadObject::Text(s) => s.clone().into(),
            kotoba_kqe::quad::LegacyQuadObject::Integer(i) => (*i).into(),
            other => format!("{other:?}").into(),
        };
        let key = match quad.predicate.as_str() {
            "access/graph" => "graph",
            "access/accessor-did" => "accessorDid",
            "access/operation" => "operation",
            "access/purpose" => "purpose",
            "access/cacao-cid" => "cacaoCid",
            "access/ts-unix" => "tsUnix",
            _ => continue,
        };
        entry.insert(key.to_string(), value);
    }

    let mut receipts: Vec<serde_json::Value> = by_subject
        .into_iter()
        .filter(|(_, fields)| {
            if let Some(g) = &q.graph {
                if fields.get("graph").and_then(|v| v.as_str()) != Some(g.as_str()) {
                    return false;
                }
            }
            if let Some(a) = &q.accessor {
                if fields.get("accessorDid").and_then(|v| v.as_str()) != Some(a.as_str()) {
                    return false;
                }
            }
            true
        })
        .map(|(cid, mut fields)| {
            fields.insert("receiptCid".to_string(), cid.into());
            serde_json::Value::Object(fields)
        })
        .collect();
    receipts.sort_by_key(|r| std::cmp::Reverse(r.get("tsUnix").and_then(|v| v.as_i64()).unwrap_or(0)));
    receipts.truncate(limit);

    Ok(Json(serde_json::json!({
        "ok": true,
        "count": receipts.len(),
        "receipts": receipts,
    })))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn receipt() -> AccessReceipt {
        AccessReceipt {
            graph_mb: "btestgraph".into(),
            accessor_did: Some("did:key:zReader".into()),
            operation: "datom:q".into(),
            purpose: Some("billing-dispute #42".into()),
            ts_unix: 1_780_000_000,
            cacao_cid: None,
        }
    }

    #[test]
    fn receipts_graph_cid_is_stable() {
        assert_eq!(receipts_graph_cid().0, receipts_graph_cid().0);
        assert_ne!(
            receipts_graph_cid().0,
            KotobaCid::from_bytes(b"kotoba/audit/requests/v1").0,
            "must not collide with the request-fingerprint graph"
        );
    }

    #[test]
    fn purpose_header_trimmed_capped_and_control_stripped() {
        let mut h = HeaderMap::new();
        // \t is a control char that HeaderValue accepts — the filter strips it.
        h.insert(PURPOSE_HEADER, "  billing\taudit  ".parse().unwrap());
        assert_eq!(purpose_from_headers(&h).as_deref(), Some("billingaudit"));

        let mut h = HeaderMap::new();
        h.insert(PURPOSE_HEADER, "   ".parse().unwrap());
        assert_eq!(purpose_from_headers(&h), None, "whitespace-only → None");

        let long = "p".repeat(MAX_PURPOSE_LEN + 50);
        let mut h = HeaderMap::new();
        h.insert(PURPOSE_HEADER, long.parse().unwrap());
        assert_eq!(purpose_from_headers(&h).unwrap().len(), MAX_PURPOSE_LEN);

        assert_eq!(purpose_from_headers(&HeaderMap::new()), None);
    }

    #[test]
    fn accessor_falls_back_to_jwt_sub() {
        use base64::engine::general_purpose::URL_SAFE_NO_PAD;
        let payload = URL_SAFE_NO_PAD.encode(br#"{"sub":"did:key:zJwtCaller","exp":9999999999}"#);
        let token = format!("eyJhbGciOiJub25lIn0.{payload}.sig");
        let mut h = HeaderMap::new();
        h.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer {token}").parse().unwrap(),
        );
        let auth_tier = GraphVisibility::Authenticated;
        assert_eq!(
            accessor_from_request(&h, None, &auth_tier).as_deref(),
            Some("did:key:zJwtCaller")
        );
        assert_eq!(accessor_from_request(&HeaderMap::new(), None, &auth_tier), None);
    }

    #[test]
    fn purpose_policy_only_bites_private_under_enforcement() {
        let private = GraphVisibility::Private {
            owner_did: "did:key:zOwner".into(),
        };
        assert!(purpose_violation(&private, None, true));
        assert!(!purpose_violation(&private, Some("ops"), true));
        assert!(!purpose_violation(&private, None, false), "observe-only default");
        assert!(!purpose_violation(&GraphVisibility::Authenticated, None, true));
        assert!(!purpose_violation(&GraphVisibility::Public, None, true));
    }

    #[test]
    fn receipt_datoms_carry_all_fields() {
        let mut r = receipt();
        r.cacao_cid = Some("bcacaoevidence".into());
        let subject = receipt_cid(&r, 1);
        let tx = KotobaCid::from_bytes(b"tx");
        let datoms = build_receipt_datoms(&r, &subject, &tx);
        let attrs: Vec<&str> = datoms.iter().map(|d| d.a.as_str()).collect();
        assert_eq!(
            attrs,
            vec![
                "access/graph",
                "access/operation",
                "access/ts-unix",
                "access/accessor-did",
                "access/purpose",
                "access/cacao-cid"
            ]
        );
        assert!(datoms.iter().all(|d| d.t == tx && d.added));
    }

    #[test]
    fn anonymous_no_purpose_receipt_has_three_datoms() {
        let r = AccessReceipt {
            accessor_did: None,
            purpose: None,
            ..receipt()
        };
        let subject = receipt_cid(&r, 2);
        let datoms = build_receipt_datoms(&r, &subject, &KotobaCid::from_bytes(b"tx"));
        assert_eq!(datoms.len(), 3);
    }

    #[test]
    fn receipt_cids_unique_per_seq_and_deterministic() {
        let r = receipt();
        assert_ne!(receipt_cid(&r, 1).0, receipt_cid(&r, 2).0);
        assert_eq!(receipt_cid(&r, 7).0, receipt_cid(&r, 7).0);
    }
}

#[cfg(test)]
mod write_path_tests {
    use super::*;

    #[tokio::test(flavor = "multi_thread")]
    async fn write_receipt_batch_lands_in_hot_arrangement() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = crate::server::KotobaState::new(None).expect("state");
        let r = AccessReceipt {
            graph_mb: "btarget".into(),
            accessor_did: Some("did:key:zU".into()),
            operation: "datom:q".into(),
            purpose: Some("unit".into()),
            ts_unix: 1_780_000_123,
            cacao_cid: None,
        };
        write_receipt_batch(&state, vec![r]).await;
        let quads = state
            .quad_store
            .quads_by_predicate_prefix(Some(&receipts_graph_cid()), "access/")
            .await;
        eprintln!("quads with access/ prefix: {}", quads.len());
        let all = state
            .quad_store
            .quads_by_predicate_prefix(Some(&receipts_graph_cid()), "")
            .await;
        for q in all.iter().take(12) {
            eprintln!("  attr={} obj={:?}", q.predicate, q.object);
        }
        assert!(
            quads.iter().any(|q| q.predicate == "access/purpose"),
            "receipt datoms must be queryable in the hot arrangement"
        );
    }
}

#[cfg(test)]
mod writer_task_tests {
    use super::*;

    // current_thread flavor on purpose: reproduces the e2e harness runtime.
    #[tokio::test]
    async fn channel_writer_flushes_on_current_thread_runtime() {
        std::env::set_var("KOTOBA_IPFS", "off");
        std::env::set_var("KOTOBA_RECEIPT_FLUSH_MS", "20");
        let state = Arc::new(crate::server::KotobaState::new(None).expect("state"));
        spawn_receipt_writer(Arc::clone(&state));
        state
            .receipt_tx
            .send(AccessReceipt {
                graph_mb: "btarget".into(),
                accessor_did: Some("did:key:zCt".into()),
                operation: "kg:catalog".into(),
                purpose: Some("ct".into()),
                ts_unix: 1_780_000_456,
                cacao_cid: None,
            })
            .expect("send");
        for _ in 0..50 {
            tokio::time::sleep(std::time::Duration::from_millis(50)).await;
            let quads = state
                .quad_store
                .quads_by_predicate_prefix(Some(&receipts_graph_cid()), "access/operation")
                .await;
            if !quads.is_empty() {
                return;
            }
        }
        panic!("receipt never flushed on current_thread runtime");
    }
}

#[cfg(test)]
mod attribution_tests {
    use super::*;

    fn bearer(did: &str) -> HeaderMap {
        use base64::engine::general_purpose::URL_SAFE_NO_PAD;
        let payload =
            URL_SAFE_NO_PAD.encode(format!(r#"{{"sub":"{did}","exp":9999999999}}"#).as_bytes());
        let mut h = HeaderMap::new();
        h.insert(
            axum::http::header::AUTHORIZATION,
            format!("Bearer eyJhbGciOiJub25lIn0.{payload}.sig")
                .parse()
                .unwrap(),
        );
        h
    }

    #[test]
    fn authenticated_tier_prefers_bearer_over_decorative_cacao() {
        // An unverified CACAO attached to a Bearer-authed read must not be able
        // to attribute the access to a third-party DID.
        let h = bearer("did:key:zRealCaller");
        let bogus_cacao = base64::engine::general_purpose::STANDARD.encode(b"not-a-real-cacao");
        let got = accessor_from_request(&h, Some(&bogus_cacao), &GraphVisibility::Authenticated);
        assert_eq!(got.as_deref(), Some("did:key:zRealCaller"));
    }

    #[test]
    fn private_tier_falls_back_to_bearer_when_cacao_unparseable() {
        let h = bearer("did:key:zFallback");
        let got = accessor_from_request(
            &h,
            Some("%%%not-base64%%%"),
            &GraphVisibility::Private {
                owner_did: "did:key:zOwner".into(),
            },
        );
        assert_eq!(got.as_deref(), Some("did:key:zFallback"));
    }
}

// ── audit.anchorPayload XRPC (R2a — receipt-root anchoring) ──────────────────

pub const NSID_AUDIT_ANCHOR: &str = "com.etzhayyim.apps.kotoba.audit.anchorPayload";

/// GET /xrpc/com.etzhayyim.apps.kotoba.audit.anchorPayload
///
/// The Estonia-KSI analog: returns the `AnchorBridge.commitRoot(bytes32,bytes,
/// uint64)` calldata committing the audit graph's CURRENT head commit CID to
/// Base. kotoba builds the payload; the relayer signs + submits (the same
/// read+verify boundary as kotoba-EVM R3, ADR-2606091500 / PR #96). Once the
/// root is on-chain, not even the node operator can silently rewrite or drop
/// receipts committed before the anchor.
///
/// `rootHash` = low 32 bytes of the head commit CID; `ipfsCid` = the head CID
/// multibase (anyone can fetch + replay the audit DAG from IPFS and check it
/// hashes to the anchored root); `batchSize` = the IPNS sequence (monotonic
/// commit count for the audit graph).
pub async fn audit_anchor_payload(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;

    let graph = receipts_graph_cid();
    let ipns_name = crate::xrpc::distributed_graph_ipns_name(&graph);
    let record = state
        .ipns_registry
        .resolve(&kotoba_ipfs::IpnsName::new(ipns_name))
        .map_err(|e| match e {
            kotoba_ipfs::IpnsRegistryError::NotFound(_) => (
                StatusCode::NOT_FOUND,
                "no receipts committed yet — nothing to anchor".to_string(),
            ),
            other => (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("ipns resolve: {other}"),
            ),
        })?;
    let head = KotobaCid::from_multibase(&record.value).ok_or((
        StatusCode::INTERNAL_SERVER_ERROR,
        format!("audit head is not a CID: {}", record.value),
    ))?;
    let calldata = kotoba_evm::anchor::anchor_block_calldata(&head, &head, record.sequence);

    Ok(Json(serde_json::json!({
        "ok": true,
        "graph": graph.to_multibase(),
        "headCid": head.to_multibase(),
        "seq": record.sequence,
        "function": "commitRoot(bytes32,bytes,uint64)",
        "calldataHex": hex::encode(&calldata),
    })))
}

#[cfg(test)]
mod anchor_tests {
    use super::*;

    #[tokio::test(flavor = "multi_thread")]
    async fn anchor_payload_encodes_committed_audit_head() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = crate::server::KotobaState::new(None).expect("state");

        // Before any receipt: head missing.
        let ipns = crate::xrpc::distributed_graph_ipns_name(&receipts_graph_cid());
        assert!(state
            .ipns_registry
            .resolve(&kotoba_ipfs::IpnsName::new(ipns.clone()))
            .is_err());

        // Commit one receipt batch → audit head exists.
        write_receipt_batch(
            &state,
            vec![AccessReceipt {
                graph_mb: "btarget".into(),
                accessor_did: Some("did:key:zA".into()),
                operation: "datom:q".into(),
                purpose: Some("anchor-test".into()),
                ts_unix: 1_780_000_789,
                cacao_cid: None,
            }],
        )
        .await;
        let record = state
            .ipns_registry
            .resolve(&kotoba_ipfs::IpnsName::new(ipns))
            .expect("audit head after first batch");
        let head = KotobaCid::from_multibase(&record.value).expect("head CID");

        // The calldata layout matches kotoba-evm's pinned ABI: selector, then
        // rootHash = low 32 bytes of the head CID.
        let calldata =
            kotoba_evm::anchor::anchor_block_calldata(&head, &head, record.sequence);
        assert_eq!(&calldata[..4], &kotoba_evm::anchor::commit_root_selector());
        assert_eq!(&calldata[4..36], &head.0[4..36]);
        // dynamic tail carries the multibase CID string.
        let mb = head.to_multibase();
        assert!(calldata
            .windows(mb.len())
            .any(|w| w == mb.as_bytes()));
    }
}

#[cfg(test)]
mod signed_commit_tests {
    use super::*;

    /// R2b: the audit-graph head commit is author-signed by the operator and
    /// verifiable from the author DID alone (did:key → pubkey → verify).
    #[tokio::test(flavor = "multi_thread")]
    async fn receipt_commit_is_author_signed_and_did_verifiable() {
        std::env::set_var("KOTOBA_IPFS", "off");
        let state = crate::server::KotobaState::new(None).expect("state");
        write_receipt_batch(
            &state,
            vec![AccessReceipt {
                graph_mb: "btarget".into(),
                accessor_did: Some("did:key:zR2b".into()),
                operation: "datom:q".into(),
                purpose: Some("sig-test".into()),
                ts_unix: 1_780_001_000,
                cacao_cid: None,
            }],
        )
        .await;
        let ipns = crate::xrpc::distributed_graph_ipns_name(&receipts_graph_cid());
        let record = state
            .ipns_registry
            .resolve(&kotoba_ipfs::IpnsName::new(ipns))
            .expect("audit head");
        let head = KotobaCid::from_multibase(&record.value).expect("head CID");
        let commit = kotoba_datomic::distributed::DistributedDatomCommit::load(
            &head,
            &*state.block_store,
        )
        .expect("load")
        .expect("commit block");
        assert_eq!(commit.author, state.operator_did);
        assert!(commit.author_sig.is_some(), "audit commit must be signed");
        // Verify with the node key…
        let vk = state.operator_signing_key().verifying_key();
        assert!(commit.verify_author_sig(&vk).unwrap());
        // …and via the author DID alone (what a third-party verifier does).
        if commit.author.starts_with("did:key:") {
            let pk = kotoba_auth::parse_ed25519_did_key(&commit.author).expect("did:key");
            let vk2 = ed25519_dalek::VerifyingKey::from_bytes(&pk).expect("pubkey");
            assert!(commit.verify_author_sig(&vk2).unwrap());
        }
    }
}
