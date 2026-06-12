//! XRPC read surface for the social-capital ledger (ADR-2606082100 §5).
//!
//! `GET /xrpc/com.etzhayyim.apps.kotoba.social.capital?graph=<cid>&did=<cid>&epoch=<n>`
//! → the decayed social capital of a DID at `epoch`. Read-only: it cold-scans the
//! entity's `social/mint|burn` Datoms from the canonical log and folds them through
//! [`SocialCapitalView`] (non-social Datoms are ignored by the reducer). `did` is
//! the DID's entity CID (multibase); `graph` is the social graph CID.

use std::sync::Arc;

use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use serde_json::json;

use kotoba_core::cid::KotobaCid;
use kotoba_query::datom::Datom;
use kotoba_query::delta::Delta;
use kotoba_query::social::{SocialCapitalView, SCALE};

use crate::server::KotobaState;

pub const NSID_SOCIAL_CAPITAL: &str = "com.etzhayyim.apps.kotoba.social.capital";

#[derive(Deserialize)]
pub struct SocialCapitalQuery {
    /// social graph CID (multibase).
    pub graph: String,
    /// the DID's entity CID (multibase).
    pub did: String,
    /// epoch to read the decayed balance at (default 0).
    #[serde(default)]
    pub epoch: u64,
}

pub async fn social_capital(
    State(state): State<Arc<KotobaState>>,
    Query(q): Query<SocialCapitalQuery>,
) -> impl IntoResponse {
    let Some(graph) = KotobaCid::from_multibase(&q.graph) else {
        return (StatusCode::BAD_REQUEST, Json(json!({"error": "invalid graph cid"}))).into_response();
    };
    let Some(did) = KotobaCid::from_multibase(&q.did) else {
        return (StatusCode::BAD_REQUEST, Json(json!({"error": "invalid did cid"}))).into_response();
    };

    let quads = match state.quad_store.get_entity_quads_cold(&graph, &did).await {
        Ok(qs) => qs,
        Err(e) => {
            return (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({"error": e.to_string()})))
                .into_response();
        }
    };

    // Fold the entity's Datoms through the reducer; it keeps only social/mint|burn.
    let deltas: Vec<Delta> = quads
        .into_iter()
        .map(|qd| Delta::assert_datom(Datom::from_legacy_quad(qd, true)))
        .collect();
    let mut view = SocialCapitalView::new();
    view.apply(&deltas);
    let smic = view.capital(&did, q.epoch);

    (
        StatusCode::OK,
        Json(json!({
            "did": q.did,
            "graph": q.graph,
            "epoch": q.epoch,
            "capital_smic": smic,
            "capital_points": smic as f64 / SCALE as f64,
        })),
    )
        .into_response()
}
