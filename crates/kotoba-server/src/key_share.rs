//! `key.requestShare` / `key.depositShare` — the server-side wiring of the
//! R3b custodian protocol (ADR-sealed-cold-tier).
//!
//! This node acts as ONE custodian: it holds HPKE-wrapped Shamir shares of
//! other graphs' block keys (deposited via `key.depositShare`, operator-gated)
//! and releases its share for a graph ONLY after verifying the requester's
//! CACAO `datom:read` capability + purpose policy and writing an access
//! receipt — exactly the `authorize`-then-release invariant the custody
//! protocol core enforces. A client collects `threshold` such grants from
//! distinct custodians and recombines the key locally (`combine_granted`);
//! no single node ever reconstructs the key, and no release happens without a
//! receipt.

use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use axum::extract::State;
use axum::http::{HeaderMap, StatusCode};
use axum::Json;
use kotoba_core::cid::KotobaCid;
use kotoba_core::named_graph::GraphVisibility;
use kotoba_custody::{handle_key_share_request, CustodianShare, KeyShareRequest, KeyShareResponse};
use serde::{Deserialize, Serialize};

use crate::access_receipt::{pin_cacao_evidence, record_receipt, AccessReceipt};
use crate::server::KotobaState;

pub const NSID_KEY_REQUEST_SHARE: &str = "com.etzhayyim.apps.kotoba.key.requestShare";
pub const NSID_KEY_DEPOSIT_SHARE: &str = "com.etzhayyim.apps.kotoba.key.depositShare";
pub const NSID_KEY_CUSTODIAN_INFO: &str = "com.etzhayyim.apps.kotoba.key.custodianInfo";

#[derive(Debug, Deserialize)]
pub struct RequestShareReq {
    /// Graph whose block-key share is requested (multibase CID).
    pub graph: String,
    /// CACAO delegation chain (base64), required for Private graphs.
    pub cacao_b64: Option<String>,
    /// Declared purpose (recorded; required for Private when KOTOBA_REQUIRE_PURPOSE).
    pub purpose: Option<String>,
    /// Anti-replay nonce.
    pub nonce: String,
    /// Requester's ephemeral X25519 pubkey (hex) to re-wrap the share to.
    pub requester_x25519_pk_hex: String,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RequestShareResp {
    pub ok: bool,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub custodian_did: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub index: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub threshold: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub epoch: Option<u64>,
    /// HPKE envelope (hex) of the share, sealed to the requester's pubkey.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sealed_share_hex: Option<String>,
    /// The full custodian-SIGNED grant (R3d evidence). The requester keeps this;
    /// presenting it to `key.reportUnreceiptedRelease` proves the release.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub grant: Option<kotoba_custody::GrantedShare>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.key.requestShare
pub async fn key_request_share(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<RequestShareReq>,
) -> Result<Json<RequestShareResp>, (StatusCode, String)> {
    let _ = &headers; // identity travels in the CACAO, not the Bearer, here.
    let graph_cid = KotobaCid::from_multibase(&req.graph)
        .ok_or((StatusCode::BAD_REQUEST, "invalid graph CID".to_string()))?;

    // This node must actually be a custodian for the graph.
    let my_share: CustodianShare = {
        let shares = state.custody_shares.read().await;
        shares.get(&req.graph).cloned().ok_or((
            StatusCode::NOT_FOUND,
            "this node holds no custodian share for that graph".to_string(),
        ))?
    };

    let requester_pk = hex::decode(req.requester_x25519_pk_hex.trim())
        .ok()
        .filter(|b| b.len() == 32)
        .ok_or((
            StatusCode::BAD_REQUEST,
            "requester_x25519_pk_hex must be 32 bytes hex".to_string(),
        ))?;

    let proto_req = KeyShareRequest {
        graph_cid_mb: req.graph.clone(),
        cacao_b64: req.cacao_b64.clone(),
        purpose: req.purpose.clone(),
        nonce: req.nonce.clone(),
        requester_x25519_pk: requester_pk,
    };

    // The authorize closure: CACAO datom:read + purpose policy + nonce, then an
    // access receipt — share release is gated on this returning Ok (custody
    // protocol invariant). Capturing &state by ref is fine; the closure runs
    // synchronously inside handle_key_share_request.
    let visibility = state.graph_visibility(&graph_cid).await;
    let authorize = |r: &KeyShareRequest| -> Result<(), String> {
        authorize_share_release(&state, &graph_cid, &visibility, r)
    };

    let my_sk = state.custodian_x25519_secret();
    match handle_key_share_request(&proto_req, &my_share, &my_sk, &authorize) {
        KeyShareResponse::Granted(mut g) => {
            // R3d: sign the grant with the operator (custodian) Ed25519 key so
            // it is non-repudiable evidence of THIS release (same seam as R2b
            // commit signing — kotoba-custody is X25519-only).
            use ed25519_dalek::Signer as _;
            let sig = state
                .operator_signing_key()
                .sign(&g.grant_signing_payload());
            g.grant_sig = Some(sig.to_bytes().to_vec());
            Ok(Json(RequestShareResp {
                ok: true,
                custodian_did: Some(g.custodian_did.clone()),
                index: Some(g.index),
                threshold: Some(g.threshold),
                epoch: Some(g.epoch),
                sealed_share_hex: Some(hex::encode(&g.sealed_for_requester)),
                grant: Some(g),
                error: None,
            }))
        }
        KeyShareResponse::Denied { reason } => Ok(Json(RequestShareResp {
            ok: false,
            custodian_did: None,
            index: None,
            threshold: None,
            epoch: None,
            sealed_share_hex: None,
            grant: None,
            error: Some(reason),
        })),
    }
}

/// CACAO + purpose verification AND receipt write for one share release.
/// Returns `Err(reason)` (→ Denied) without releasing on any failure.
fn authorize_share_release(
    state: &KotobaState,
    graph_cid: &KotobaCid,
    visibility: &GraphVisibility,
    req: &KeyShareRequest,
) -> Result<(), String> {
    let graph_scope = graph_cid.to_multibase();
    let accessor_did: Option<String> = match visibility {
        GraphVisibility::Public => None,
        GraphVisibility::Authenticated => {
            // A share for an Authenticated graph still needs a presented CACAO
            // to attribute the read; without one we cannot name the accessor.
            req.cacao_b64.as_deref().and_then(|b64| {
                crate::access_receipt::accessor_from_request(
                    &HeaderMap::new(),
                    Some(b64),
                    visibility,
                )
            })
        }
        GraphVisibility::Private { .. } => {
            let cacao_b64 = req
                .cacao_b64
                .as_deref()
                .ok_or_else(|| "private graph requires cacao_b64".to_string())?;
            // datom:read capability for this graph, replay-checked.
            let payload = crate::graph_auth::verify_cacao_graph_operation(
                cacao_b64,
                &graph_scope,
                kotoba_auth::CacaoPayload::OP_DATOM_READ,
                Some(state.operator_did.as_str()),
                Some(&state.nonce_store),
            )
            .map_err(|e| format!("cacao: {:?}", e.into_response().1))?;
            Some(payload.iss)
        }
    };

    // Purpose policy (observe-first; required for Private under the env flag).
    let purpose = req
        .purpose
        .as_deref()
        .map(|p| {
            p.trim()
                .chars()
                .filter(|c| !c.is_control())
                .take(256)
                .collect::<String>()
        })
        .filter(|p| !p.is_empty());
    if matches!(visibility, GraphVisibility::Private { .. })
        && purpose.is_none()
        && std::env::var("KOTOBA_REQUIRE_PURPOSE")
            .map(|v| v == "1" || v.eq_ignore_ascii_case("true") || v.eq_ignore_ascii_case("on"))
            .unwrap_or(false)
    {
        return Err("purpose required for private-graph key release".to_string());
    }

    // Receipt — same shape as a read receipt, operation = key:requestShare.
    let cacao_cid = pin_cacao_evidence(state, req.cacao_b64.as_deref());
    record_receipt(
        state,
        AccessReceipt {
            graph_mb: graph_scope,
            accessor_did,
            operation: "key:requestShare".to_string(),
            purpose,
            ts_unix: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            cacao_cid,
            // Custody-protocol seam, not a plain HTTP read: no edge-forwarded
            // network metadata (ADR-2606131600 P0).
            ..Default::default()
        },
    );
    Ok(())
}

#[derive(Debug, Deserialize)]
pub struct DepositShareReq {
    /// Graph this share belongs to (multibase CID).
    pub graph: String,
    /// The custodian share, as produced by `kotoba_custody::split_key` for
    /// THIS node's DID, JSON-encoded.
    pub share: CustodianShare,
}

#[derive(Debug, Serialize)]
pub struct DepositShareResp {
    pub ok: bool,
    pub graph: String,
    pub epoch: u64,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.key.depositShare (operator-gated)
pub async fn key_deposit_share(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(req): Json<DepositShareReq>,
) -> Result<Json<DepositShareResp>, (StatusCode, String)> {
    crate::graph_auth::require_operator_auth(&headers, &state.operator_did)?;
    KotobaCid::from_multibase(&req.graph)
        .ok_or((StatusCode::BAD_REQUEST, "invalid graph CID".to_string()))?;
    let mut shares = state.custody_shares.write().await;
    // Rotation monotonicity: a deposit may only install a share whose epoch is
    // >= the one already held, so a stale (revoked) dealing can't be replayed
    // back in over a newer one.
    if let Some(existing) = shares.get(&req.graph) {
        if req.share.epoch < existing.epoch {
            return Err((
                StatusCode::CONFLICT,
                format!(
                    "stale share epoch {} < held epoch {} for that graph",
                    req.share.epoch, existing.epoch
                ),
            ));
        }
    }
    let epoch = req.share.epoch;
    shares.insert(req.graph.clone(), req.share);
    Ok(Json(DepositShareResp {
        ok: true,
        graph: req.graph,
        epoch,
    }))
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct CustodianInfoResp {
    pub did: String,
    /// X25519 public key (hex) to wrap this node's key shares to.
    pub x25519_pubkey_hex: String,
}

/// GET /xrpc/com.etzhayyim.apps.kotoba.key.custodianInfo
///
/// Public: returns this node's custodian identity (DID + X25519 pubkey) so an
/// operator dealing key shares can wrap this node's share to it.
pub async fn key_custodian_info(State(state): State<Arc<KotobaState>>) -> Json<CustodianInfoResp> {
    Json(CustodianInfoResp {
        did: state.operator_did.clone(),
        x25519_pubkey_hex: state.custodian_x25519_pubkey_hex(),
    })
}

// ── key.reportUnreceiptedRelease (R3d enforcement) ───────────────────────────

pub const NSID_KEY_REPORT_RELEASE: &str = "com.etzhayyim.apps.kotoba.key.reportUnreceiptedRelease";

#[derive(Debug, Deserialize)]
pub struct ReportReleaseReq {
    /// A custodian-signed grant (as returned by `key.requestShare`).
    pub grant: kotoba_custody::GrantedShare,
    /// How far apart (secs) a covering receipt may be from the grant ts.
    /// Default 120 (clock skew + receipt batch-flush). Capped at 3600.
    pub window_secs: Option<u64>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReportReleaseResp {
    /// True only when the grant is signature-valid AND unreceipted (a warrant
    /// was emitted). False = signature invalid OR a covering receipt exists.
    pub warranted: bool,
    pub verdict: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub accused_did: Option<String>,
    /// CID of the persisted grant-evidence block, if a warrant was emitted.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub evidence_cid: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

/// POST /xrpc/com.etzhayyim.apps.kotoba.key.reportUnreceiptedRelease
///
/// Cross-audit (R3d): a requester (or watchdog) presents a custodian-signed
/// grant. This node verifies the signature against the custodian DID, then
/// checks the audit receipt log for a matching `key:requestShare` receipt
/// within the window. No match ⇒ the custodian released a share without
/// logging it — a `CustodyUnreceiptedRelease` warrant is emitted (the grant
/// is pinned as evidence; an off-chain relayer feeds it to MishmarBondEscrow
/// for slashing, the same build-here / submit-elsewhere boundary as the R2a
/// anchor).
pub async fn key_report_unreceipted_release(
    State(state): State<Arc<KotobaState>>,
    Json(req): Json<ReportReleaseReq>,
) -> Result<Json<ReportReleaseResp>, (StatusCode, String)> {
    let grant = req.grant;

    // 1. Verify the custodian's signature — only a non-repudiable grant is
    //    evidence. A grant we can't attribute is rejected outright.
    let sig_bytes = grant
        .grant_sig
        .as_ref()
        .ok_or((StatusCode::BAD_REQUEST, "grant is unsigned".to_string()))?;
    let pk = kotoba_auth::parse_ed25519_did_key(&grant.custodian_did)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("custodian DID: {e}")))?;
    let vk = ed25519_dalek::VerifyingKey::from_bytes(&pk)
        .map_err(|e| (StatusCode::BAD_REQUEST, format!("custodian pubkey: {e}")))?;
    let sig_arr: [u8; 64] = sig_bytes
        .as_slice()
        .try_into()
        .map_err(|_| (StatusCode::BAD_REQUEST, "grant_sig length".to_string()))?;
    let sig = ed25519_dalek::Signature::from_bytes(&sig_arr);
    {
        use ed25519_dalek::Verifier as _;
        if vk.verify(&grant.grant_signing_payload(), &sig).is_err() {
            return Ok(Json(ReportReleaseResp {
                warranted: false,
                verdict: "grant signature invalid".to_string(),
                accused_did: None,
                evidence_cid: None,
                error: Some("signature does not verify against custodian DID".to_string()),
            }));
        }
    }

    // 2. Cross-audit against the receipt log (hot arrangement of the audit graph).
    let window = req.window_secs.unwrap_or(120).min(3600);
    let receipts_graph = crate::access_receipt::receipts_graph_cid();
    let quads = state
        .quad_store
        .quads_by_predicate_prefix(Some(&receipts_graph), "access/")
        .await;
    let receipts = receipt_records_from_quads(&quads);
    let verdict = kotoba_custody::audit_grant(&grant, &receipts, window);

    match verdict {
        kotoba_custody::AuditVerdict::Receipted => Ok(Json(ReportReleaseResp {
            warranted: false,
            verdict: "receipted".to_string(),
            accused_did: None,
            evidence_cid: None,
            error: None,
        })),
        kotoba_custody::AuditVerdict::UnreceiptedRelease => {
            // Pin the signed grant as warrant evidence.
            let mut ev = Vec::new();
            ciborium::into_writer(&grant, &mut ev).map_err(|e| {
                (
                    StatusCode::INTERNAL_SERVER_ERROR,
                    format!("encode grant: {e}"),
                )
            })?;
            let evidence_cid = KotobaCid::from_bytes(&ev);
            if let Err(e) = state.block_store.put(&evidence_cid, &ev) {
                tracing::warn!(err = %e, "warrant evidence block put failed");
            }
            let warrant = kotoba_dht::warrant::Warrant {
                accused: grant.custodian_did.clone().into_bytes(),
                evidence: evidence_cid.clone(),
                rule_id: kotoba_dht::warrant::ValidationRule::CustodyUnreceiptedRelease as u8,
                validator: state.local_node_id.0.to_vec(),
                ts: SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|d| d.as_millis() as u64)
                    .unwrap_or(0),
                sig: {
                    use ed25519_dalek::Signer as _;
                    state
                        .operator_signing_key()
                        .sign(&evidence_cid.0)
                        .to_bytes()
                        .to_vec()
                },
            };
            tracing::warn!(
                accused = %grant.custodian_did,
                evidence = %evidence_cid.to_multibase(),
                "R3d warrant: unreceipted key-share release"
            );
            let _ = &warrant; // gossip propagation is the libp2p shell (deferred)
            Ok(Json(ReportReleaseResp {
                warranted: true,
                verdict: "unreceipted-release".to_string(),
                accused_did: Some(grant.custodian_did),
                evidence_cid: Some(evidence_cid.to_multibase()),
                error: None,
            }))
        }
    }
}

/// Project audit-graph quads into the flat ReceiptRecords the cross-audit needs.
fn receipt_records_from_quads(
    quads: &[kotoba_query::quad::LegacyQuad],
) -> Vec<kotoba_custody::ReceiptRecord> {
    use kotoba_query::quad::LegacyQuadObject;
    use std::collections::HashMap;
    type ReceiptFields = (Option<String>, Option<String>, Option<u64>);
    let mut by_subject: HashMap<[u8; 36], ReceiptFields> = HashMap::new();
    for q in quads {
        let e = by_subject.entry(q.subject.0).or_default();
        match (q.predicate.as_str(), &q.object) {
            ("access/graph", LegacyQuadObject::Text(s)) => e.0 = Some(s.clone()),
            ("access/operation", LegacyQuadObject::Text(s)) => e.1 = Some(s.clone()),
            ("access/ts-unix", LegacyQuadObject::Integer(i)) => e.2 = Some(*i as u64),
            _ => {}
        }
    }
    by_subject
        .into_values()
        .filter_map(|(g, op, ts)| {
            Some(kotoba_custody::ReceiptRecord {
                graph_mb: g?,
                operation: op?,
                ts_unix: ts?,
            })
        })
        .collect()
}
