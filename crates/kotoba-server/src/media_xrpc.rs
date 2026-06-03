//! XRPC handlers for multimodal (cross-modal) search.
//!
//! Where `cc_xrpc` searches *text* chunks, these endpoints search a shared
//! embedding space that spans text, images, audio, video, and documents
//! (books / PDF pages).  A text query retrieves any modality — Google-style
//! cross-modal search — by ranking `media/embed/*` vectors by cosine
//! similarity.
//!
//! NSIDs:
//!   com.etzhayyim.apps.kotoba.media.search  — cross-modal vector search (GET)
//!   com.etzhayyim.apps.kotoba.media.ingest  — ingest base64 assets (POST)
//!   com.etzhayyim.apps.kotoba.media.status  — asset / index status (GET)
//!
//! The query is embedded as TEXT in the shared space, then ranked against the
//! stored media embeddings; results carry the matched asset's modality, blob
//! CID, title, and caption so a client can fetch the raw bytes via the Vault
//! (`com.etzhayyim.apps.kotoba.vault.get`).

pub const NSID_MEDIA_SEARCH: &str = "com.etzhayyim.apps.kotoba.media.search";
pub const NSID_MEDIA_INGEST: &str = "com.etzhayyim.apps.kotoba.media.ingest";
pub const NSID_MEDIA_STATUS: &str = "com.etzhayyim.apps.kotoba.media.status";

use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::sync::Arc;

use kotoba_core::cid::KotobaCid;
use kotoba_ingest::media::{media_assets_graph, rank_by_cosine};
use kotoba_ingest::media_embed::{Blake3MediaEmbedClient, MediaEmbedClient, MediaItem};
use kotoba_kqe::{Datom as KqeDatom, Value as KqeValue};

use crate::server::KotobaState;

// ── limits ──────────────────────────────────────────────────────────────────────

const MAX_QUERY_LEN: usize = 8_192;
const MAX_MODALITY_LEN: usize = 16;
const MAX_TOP_K: usize = 100;
const DEFAULT_EMBED_DIM: usize = 768;
/// 33 MiB base64 asset + JSON framing (matches the email-ingest body limit).
pub const MEDIA_INGEST_BODY_LIMIT: usize = 36 * 1024 * 1024;

fn default_top_k() -> usize {
    10
}

// ── shared helpers ────────────────────────────────────────────────────────────────

/// Resolve the multimodal embed client: the configured HTTP client, or a
/// deterministic caption-bridged fallback so the endpoint is always functional
/// (offline / CI / no encoder deployed).
fn resolve_embed_client(state: &KotobaState) -> Arc<dyn MediaEmbedClient> {
    match state.media_embed_client.as_ref() {
        Some(c) => Arc::clone(c),
        None => Arc::new(Blake3MediaEmbedClient::new(DEFAULT_EMBED_DIM)),
    }
}

async fn current_media_datoms(
    state: &KotobaState,
) -> Result<Vec<KqeDatom>, (StatusCode, String)> {
    Ok(crate::xrpc::current_db_for_graph(state, &media_assets_graph())
        .await?
        .datoms()
        .into_iter()
        .filter_map(|datom| datom.to_kqe().ok())
        .collect())
}

/// Collect (subject, embedding) pairs from the asset graph, de-duplicated by
/// subject (latest embedding wins per the datom iteration order).
fn collect_media_embeddings(datoms: &[KqeDatom]) -> Vec<(KotobaCid, Vec<f32>)> {
    let mut out: Vec<(KotobaCid, Vec<f32>)> = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for datom in datoms {
        if !datom.a.starts_with("media/embed/") {
            continue;
        }
        if !seen.insert(datom.e.to_multibase()) {
            continue;
        }
        if let KqeValue::VectorF32(v) = &datom.v {
            out.push((datom.e.clone(), v.clone()));
        }
    }
    out
}

fn field_text(datoms: &[KqeDatom], subject: &KotobaCid, predicate: &str) -> Option<String> {
    datoms
        .iter()
        .find(|d| d.e == *subject && d.a == predicate)
        .and_then(|d| match &d.v {
            KqeValue::Text(t) => Some(t.clone()),
            _ => None,
        })
}

fn field_cid(datoms: &[KqeDatom], subject: &KotobaCid, predicate: &str) -> Option<KotobaCid> {
    datoms
        .iter()
        .find(|d| d.e == *subject && d.a == predicate)
        .and_then(|d| match &d.v {
            KqeValue::Cid(c) => Some(c.clone()),
            _ => None,
        })
}

// ── media.search ──────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MediaSearchQuery {
    pub q: String,
    #[serde(default = "default_top_k")]
    pub top_k: usize,
    /// Optional modality filter: text|image|audio|video|document.
    pub modality: Option<String>,
}

#[derive(Serialize)]
pub struct MediaSearchResult {
    pub subject: String,
    pub modality: String,
    pub blob_cid: Option<String>,
    pub mime: Option<String>,
    pub title: Option<String>,
    pub caption: Option<String>,
    pub source: Option<String>,
    pub score: f32,
}

pub async fn media_search(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<MediaSearchQuery>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if q.q.is_empty() || q.q.len() > MAX_QUERY_LEN {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("q must be 1–{MAX_QUERY_LEN} bytes") })),
        )
            .into_response();
    }
    if let Some(ref m) = q.modality {
        if m.len() > MAX_MODALITY_LEN {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({ "error": format!("modality exceeds {MAX_MODALITY_LEN} chars") })),
            )
                .into_response();
        }
    }

    let embed_client = resolve_embed_client(&state);

    // Embed the query as TEXT in the shared space.
    let query_item = [MediaItem::text(&q.q)];
    let query_vec = match embed_client.embed_media(&query_item).await {
        Ok(v) if !v.is_empty() => v[0].clone(),
        Ok(_) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": "embedder returned no vector" })),
            )
                .into_response()
        }
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({ "error": format!("embedding failed: {e}") })),
            )
                .into_response()
        }
    };

    let datoms = match current_media_datoms(&state).await {
        Ok(d) => d,
        Err((code, msg)) => return (code, Json(json!({ "error": msg }))).into_response(),
    };
    let embeddings = collect_media_embeddings(&datoms);
    if embeddings.is_empty() {
        return Json(json!({ "results": [], "total": 0, "note": "no media embeddings found" }))
            .into_response();
    }

    let top_k = q.top_k.clamp(1, MAX_TOP_K);
    // Over-fetch before modality filtering so the filter can't starve results.
    let ranked = rank_by_cosine(&query_vec, &embeddings, (top_k * 4).min(embeddings.len()));

    let mut results: Vec<MediaSearchResult> = Vec::new();
    for (score, idx) in ranked {
        let Some((subject, _)) = embeddings.get(idx) else {
            continue;
        };
        let modality = field_text(&datoms, subject, "media/modality").unwrap_or_default();
        if let Some(ref want) = q.modality {
            if &modality != want {
                continue;
            }
        }
        results.push(MediaSearchResult {
            subject: subject.to_multibase(),
            modality,
            blob_cid: field_cid(&datoms, subject, "media/blob").map(|c| c.to_multibase()),
            mime: field_text(&datoms, subject, "media/mime"),
            title: field_text(&datoms, subject, "media/title"),
            caption: field_text(&datoms, subject, "media/caption"),
            source: field_text(&datoms, subject, "media/source"),
            score,
        });
        if results.len() >= top_k {
            break;
        }
    }

    Json(json!({ "results": results, "total": results.len() })).into_response()
}

// ── media.ingest ──────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MediaIngestItem {
    pub mime: String,
    /// Base64-encoded raw bytes.
    pub b64: String,
    pub title: Option<String>,
    pub source: Option<String>,
    #[serde(default)]
    pub page: i64,
    pub caption: Option<String>,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct MediaIngestBody {
    pub items: Vec<MediaIngestItem>,
}

const MAX_INGEST_ITEMS: usize = 256;

pub async fn media_ingest(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<MediaIngestBody>,
) -> impl IntoResponse {
    use base64::Engine as _;
    use bytes::Bytes;
    use kotoba_ingest::media::{MediaIngestor, MediaInput};

    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    if body.items.is_empty() || body.items.len() > MAX_INGEST_ITEMS {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": format!("items must be 1–{MAX_INGEST_ITEMS}") })),
        )
            .into_response();
    }

    let b64 = base64::engine::general_purpose::STANDARD;
    let mut inputs = Vec::with_capacity(body.items.len());
    for (i, item) in body.items.into_iter().enumerate() {
        if item.mime.is_empty() {
            return (
                StatusCode::BAD_REQUEST,
                Json(json!({ "error": format!("item {i}: mime required") })),
            )
                .into_response();
        }
        let bytes = match b64.decode(item.b64.as_bytes()) {
            Ok(b) => b,
            Err(e) => {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(json!({ "error": format!("item {i}: invalid base64: {e}") })),
                )
                    .into_response()
            }
        };
        let mut input = MediaInput::new(item.mime, Bytes::from(bytes)).with_page(item.page);
        if let Some(t) = item.title {
            input = input.with_title(t);
        }
        if let Some(s) = item.source {
            input = input.with_source(s);
        }
        if let Some(c) = item.caption {
            input = input.with_caption(c);
        }
        inputs.push(input);
    }

    let embed_client = resolve_embed_client(&state);
    let ingestor = MediaIngestor::new(
        Arc::clone(&state.quad_store),
        Arc::clone(&state.vault),
        embed_client,
    );

    match ingestor.ingest_items(inputs).await {
        Ok(report) => Json(json!({
            "assets":     report.assets,
            "embeddings": report.embeddings,
            "ivfK":       report.ivf_k,
            "graphCid":   report.graph_cid,
            "modelId":    report.model_id,
        }))
        .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("media ingest failed: {e}") })),
        )
            .into_response(),
    }
}

// ── media.status ──────────────────────────────────────────────────────────────────

pub async fn media_status(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({ "error": msg }))).into_response();
    }
    let graph = media_assets_graph();
    let datoms = match current_media_datoms(&state).await {
        Ok(d) => d,
        Err((code, msg)) => return (code, Json(json!({ "error": msg }))).into_response(),
    };

    let assets = datoms
        .iter()
        .filter(|d| d.a == "media/blob")
        .map(|d| d.e.to_multibase())
        .collect::<std::collections::HashSet<_>>()
        .len();
    let embeddings = datoms
        .iter()
        .filter(|d| d.a.starts_with("media/embed/"))
        .map(|d| d.e.to_multibase())
        .collect::<std::collections::HashSet<_>>()
        .len();
    let ivf_centroids = datoms
        .iter()
        .filter(|d| d.a == "media/ivf/centroid_id")
        .map(|d| d.e.to_multibase())
        .collect::<std::collections::HashSet<_>>()
        .len();

    // Per-modality breakdown.
    let mut by_modality: std::collections::BTreeMap<String, usize> = std::collections::BTreeMap::new();
    for d in &datoms {
        if d.a == "media/modality" {
            if let KqeValue::Text(t) = &d.v {
                *by_modality.entry(t.clone()).or_insert(0) += 1;
            }
        }
    }

    Json(json!({
        "assets":          assets,
        "embeddings":      embeddings,
        "ivfCentroids":    ivf_centroids,
        "byModality":      by_modality,
        "embedConfigured": state.media_embed_client.is_some(),
        "graphCid":        graph.to_multibase(),
    }))
    .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn nsids_have_kotoba_media_prefix() {
        for nsid in [NSID_MEDIA_SEARCH, NSID_MEDIA_INGEST, NSID_MEDIA_STATUS] {
            assert!(nsid.starts_with("com.etzhayyim.apps.kotoba.media."));
            assert!(!nsid.ends_with('.'));
            assert!(nsid.chars().all(|c| c.is_ascii_lowercase() || c == '.'));
        }
    }

    fn datom(e: KotobaCid, a: &str, v: KqeValue) -> KqeDatom {
        KqeDatom::assert(e, a.to_string(), v, KotobaCid::from_bytes(b"media-test-tx"))
    }

    #[test]
    fn collect_media_embeddings_dedupes_by_subject() {
        let s = KotobaCid::from_bytes(b"asset-1");
        let d1 = datom(s.clone(), "media/embed/m", KqeValue::VectorF32(vec![1.0, 0.0]));
        let d2 = datom(s.clone(), "media/embed/m", KqeValue::VectorF32(vec![0.0, 1.0]));
        let out = collect_media_embeddings(&[d1, d2]);
        assert_eq!(out.len(), 1, "same subject must collapse to one embedding");
    }

    #[test]
    fn field_text_and_cid_extract_values() {
        let s = KotobaCid::from_bytes(b"asset-2");
        let blob = KotobaCid::from_bytes(b"blob-2");
        let datoms = vec![
            datom(s.clone(), "media/title", KqeValue::Text("apple".to_string())),
            datom(s.clone(), "media/blob", KqeValue::Cid(blob.clone())),
        ];
        assert_eq!(field_text(&datoms, &s, "media/title").as_deref(), Some("apple"));
        assert_eq!(field_cid(&datoms, &s, "media/blob"), Some(blob));
        assert!(field_text(&datoms, &s, "media/missing").is_none());
    }
}
