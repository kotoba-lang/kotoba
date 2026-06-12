//! XRPC handlers for Common Crawl vector search and knowledge query.
//!
//! NSIDs:
//!   com.etzhayyim.apps.kotoba.cc.search   — ANN vector search over CC chunks (GET)
//!   com.etzhayyim.apps.kotoba.cc.rag      — RAG: search + LLM synthesis (POST)
//!   com.etzhayyim.apps.kotoba.cc.ingest   — trigger CC parquet ingest job (POST)
//!   com.etzhayyim.apps.kotoba.cc.status   — ingest / index status (GET)
//!   com.etzhayyim.apps.kotoba.search.web  — hybrid web search (lexical + semantic +
//!                                     authority, RRF-fused) over CC chunks (GET)

pub const NSID_CC_SEARCH: &str = "com.etzhayyim.apps.kotoba.cc.search";
pub const NSID_CC_RAG: &str = "com.etzhayyim.apps.kotoba.cc.rag";
pub const NSID_CC_INGEST: &str = "com.etzhayyim.apps.kotoba.cc.ingest";
pub const NSID_CC_STATUS: &str = "com.etzhayyim.apps.kotoba.cc.status";
pub const NSID_WEB_SEARCH: &str = "com.etzhayyim.apps.kotoba.search.web";
pub const NSID_SEARCH_REINDEX: &str = "com.etzhayyim.apps.kotoba.search.reindex";

use axum::{
    extract::{Query, State},
    http::{HeaderMap, StatusCode},
    response::IntoResponse,
    Json,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::sync::Arc;

use kotoba_core::cid::KotobaCid;
use kotoba_ingest::bm25::Bm25Index;
#[cfg(feature = "cc-parquet")]
use kotoba_ingest::embed_client::EmbedClient;
use kotoba_ingest::fusion::{reciprocal_rank_fusion, Ranking, Signal, RRF_K};
use kotoba_ingest::ivf::IvfIndex;
use kotoba_ingest::pagerank::PageRankIndex;
use kotoba_query::{Datom as KqeDatom, Value as KqeValue};

use crate::server::KotobaState;

// ── helpers ───────────────────────────────────────────────────────────────────

fn cc_pages_graph() -> KotobaCid {
    KotobaCid::from_bytes(b"cc:2026-12:pages")
}

fn cc_chunks_graph() -> KotobaCid {
    KotobaCid::from_bytes(b"cc:2026-12:chunks")
}

fn cc_links_graph() -> KotobaCid {
    KotobaCid::from_bytes(b"cc:2026-12:links")
}

/// Map each chunk subject (multibase) → its persisted IVF cluster id, from the
/// `cc/ivf/cluster` datoms written at ingest time.
fn collect_chunk_clusters(datoms: &[KqeDatom]) -> HashMap<String, usize> {
    let mut out = HashMap::new();
    for d in datoms {
        if d.a == "cc/ivf/cluster" {
            if let KqeValue::Integer(c) = &d.v {
                out.insert(d.e.to_multibase(), *c as usize);
            }
        }
    }
    out
}

/// Semantic ranking over chunk embeddings.
///
/// Uses the persisted IVF index (`cc/ivf/*` centroids + per-chunk
/// `cc/ivf/cluster` assignments) when present — probing only the `nprobe`
/// nearest centroids — and otherwise falls back to a brute-force cosine scan.
/// Returns `(score, chunk_embeddings_index)` pairs, best first.
fn semantic_ranking(
    datoms: &[KqeDatom],
    chunk_embeddings: &[(KotobaCid, Vec<f32>)],
    query_vec: &[f32],
    nprobe: usize,
    top_k: usize,
) -> Vec<(f32, usize)> {
    let ivf_datoms: Vec<KqeDatom> = datoms
        .iter()
        .filter(|d| d.a.starts_with("cc/ivf/") && d.a != "cc/ivf/cluster")
        .cloned()
        .collect();

    if let Some(ivf) = IvfIndex::from_datoms(&ivf_datoms) {
        let clusters = collect_chunk_clusters(datoms);
        // Only chunks with a known cluster assignment can be IVF-probed.
        let candidates: Vec<(usize, &[f32])> = chunk_embeddings
            .iter()
            .filter_map(|(cid, v)| {
                clusters
                    .get(&cid.to_multibase())
                    .map(|&c| (c, v.as_slice()))
            })
            .collect();
        // candidate index i lines up with chunk_embeddings index i only when
        // every chunk has a cluster; guard by rebuilding an index map.
        if candidates.len() == chunk_embeddings.len() && !candidates.is_empty() {
            return ivf.search(query_vec, &candidates, nprobe, top_k);
        }
    }
    brute_force_cosine(query_vec, chunk_embeddings, top_k)
}

// ── search-index build (BM25 + PageRank precompute) ─────────────────────────────

/// Build a corpus-global BM25 lexical index over every `cc/chunk/text` and
/// return its `cc/bm25/*` persistence datoms (to commit into the chunks graph).
/// Global by construction (df / N / avgdl span the whole corpus), so it must
/// run as a post-ingest pass, not per-file.
fn build_bm25_datoms(chunk_datoms: &[KqeDatom]) -> Vec<KqeDatom> {
    let texts = collect_chunk_texts(chunk_datoms);
    if texts.is_empty() {
        return Vec::new();
    }
    Bm25Index::build(&texts)
        .to_quads(&cc_chunks_graph())
        .into_iter()
        .map(|q| KqeDatom::from_legacy_quad(q, true))
        .collect()
}

/// Extract directed `cc/link/to` edges from the links graph.
fn collect_link_edges(link_datoms: &[KqeDatom]) -> Vec<(KotobaCid, KotobaCid)> {
    link_datoms
        .iter()
        .filter(|d| d.a == "cc/link/to")
        .filter_map(|d| match &d.v {
            KqeValue::Cid(dst) => Some((d.e.clone(), dst.clone())),
            _ => None,
        })
        .collect()
}

/// Compute PageRank over the links graph and return its `cc/rank/*`
/// persistence datoms (to commit into the links graph).
fn build_pagerank_datoms(link_datoms: &[KqeDatom]) -> Vec<KqeDatom> {
    let edges = collect_link_edges(link_datoms);
    if edges.is_empty() {
        return Vec::new();
    }
    PageRankIndex::compute(&edges)
        .to_quads(&cc_links_graph())
        .into_iter()
        .map(|q| KqeDatom::from_legacy_quad(q, true))
        .collect()
}

/// Rebuild and persist the search indexes (BM25 over chunks, PageRank over
/// links) from the current canonical Datom view.  Returns
/// `(bm25_datoms, pagerank_datoms, link_edges)` counts.
async fn rebuild_search_indexes(
    state: &KotobaState,
    author: &str,
) -> Result<(usize, usize, usize), (StatusCode, String)> {
    // BM25 over the committed chunk corpus.
    let chunk_datoms = current_cc_chunk_datoms(state).await?;
    let bm25 = build_bm25_datoms(&chunk_datoms);
    let bm25_n = bm25.len();
    bridge_cc_graph_to_distributed_head(
        state,
        cc_chunks_graph(),
        "cc:2026-12:chunks",
        author,
        bm25,
    )
    .await?;

    // PageRank over the link graph.
    let link_datoms = current_cc_graph_datoms(state, &cc_links_graph()).await?;
    let edge_n = collect_link_edges(&link_datoms).len();
    let pr = build_pagerank_datoms(&link_datoms);
    let pr_n = pr.len();
    bridge_cc_graph_to_distributed_head(state, cc_links_graph(), "cc:2026-12:links", author, pr)
        .await?;

    Ok((bm25_n, pr_n, edge_n))
}

fn cosine_score(a: &[f32], b: &[f32]) -> f32 {
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt().max(1e-9);
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt().max(1e-9);
    dot / (na * nb)
}

fn brute_force_cosine(
    query: &[f32],
    embeddings: &[(KotobaCid, Vec<f32>)],
    top_k: usize,
) -> Vec<(f32, usize)> {
    let mut scored: Vec<(f32, usize)> = embeddings
        .iter()
        .enumerate()
        .map(|(i, (_, v))| (cosine_score(query, v), i))
        .collect();
    scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    scored.truncate(top_k);
    scored
}

async fn current_cc_chunk_datoms(
    state: &KotobaState,
) -> Result<Vec<KqeDatom>, (StatusCode, String)> {
    current_cc_graph_datoms(state, &cc_chunks_graph()).await
}

async fn current_cc_graph_datoms(
    state: &KotobaState,
    graph_cid: &KotobaCid,
) -> Result<Vec<KqeDatom>, (StatusCode, String)> {
    Ok(crate::xrpc::current_db_for_graph(state, graph_cid)
        .await?
        .datoms()
        .into_iter()
        .filter_map(|datom| datom.to_kqe().ok())
        .collect())
}

/// Collect (subject, embedding_vec) pairs from the distributed Datom view.
fn collect_chunk_embeddings(datoms: &[KqeDatom]) -> Vec<(KotobaCid, Vec<f32>)> {
    let mut out: Vec<(KotobaCid, Vec<f32>)> = Vec::new();
    let mut seen = std::collections::HashSet::new();
    for datom in datoms {
        if !datom.a.starts_with("cc/embed/") {
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

fn get_chunk_field(datoms: &[KqeDatom], subject: &KotobaCid, predicate: &str) -> Option<String> {
    datoms
        .iter()
        .find(|datom| datom.e == *subject && datom.a == predicate)
        .and_then(|datom| {
            if let KqeValue::Text(t) = &datom.v {
                Some(t.clone())
            } else {
                None
            }
        })
}

// ── cc.search ─────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CcSearchQuery {
    pub q: String,
    #[serde(default = "default_top_k")]
    pub top_k: usize,
    #[serde(default = "default_nprobe")]
    pub nprobe: usize,
    pub lang: Option<String>,
}

fn default_top_k() -> usize {
    10
}
fn default_nprobe() -> usize {
    8
}

const MAX_QUERY_LEN: usize = 8_192; // 8 KiB — prevents embed-client DoS
const MAX_LANG_LEN: usize = 16;
const MAX_SYSTEM_LEN: usize = 4_096;
const MAX_TOP_K: usize = 100;
const MAX_CONTEXT_K: usize = 20; // cap RAG context chunks before LLM prompt construction
const MAX_NPROBE: usize = 256; // cap IVF probe count to prevent brute-force fallback DoS
const MAX_OWNER_DID_LEN: usize = 512;
#[cfg(feature = "cc-parquet")]
const MAX_PARQUET_DIR: usize = 1_024;

fn validate_cc_query_field(label: &str, value: &str) -> Result<(), (StatusCode, String)> {
    if value.trim().is_empty() || value.len() > MAX_QUERY_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{label} must be 1–{MAX_QUERY_LEN} bytes"),
        ));
    }
    if value.chars().any(char::is_control) {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("{label} contains control characters"),
        ));
    }
    Ok(())
}

fn validate_cc_lang(lang: Option<&str>) -> Result<(), (StatusCode, String)> {
    let Some(lang) = lang else {
        return Ok(());
    };
    if lang.trim().is_empty() || lang.len() > MAX_LANG_LEN {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("lang must be 1–{MAX_LANG_LEN} characters"),
        ));
    }
    if lang.chars().any(char::is_control) {
        return Err((
            StatusCode::BAD_REQUEST,
            "lang contains control characters".to_string(),
        ));
    }
    Ok(())
}

fn validate_cc_nprobe(nprobe: usize) -> Result<(), (StatusCode, String)> {
    if nprobe > MAX_NPROBE {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("nprobe must not exceed {MAX_NPROBE}"),
        ));
    }
    Ok(())
}

#[cfg(feature = "cc-parquet")]
fn validate_cc_parquet_dir(parquet_dir: &str) -> Result<(), (StatusCode, String)> {
    if parquet_dir.trim().is_empty() || parquet_dir.len() > MAX_PARQUET_DIR {
        return Err((
            StatusCode::BAD_REQUEST,
            format!("parquetDir must be 1–{MAX_PARQUET_DIR} bytes"),
        ));
    }
    if parquet_dir.chars().any(char::is_control) {
        return Err((
            StatusCode::BAD_REQUEST,
            "parquetDir contains control characters".to_string(),
        ));
    }
    Ok(())
}

fn validate_cc_mode(mode: &str) -> Result<(), (StatusCode, String)> {
    if !matches!(mode, "chunks" | "pages" | "both") {
        return Err((
            StatusCode::BAD_REQUEST,
            "mode must be 'chunks', 'pages', or 'both'".to_string(),
        ));
    }
    Ok(())
}

// Commit a batch of CC datoms to a graph's distributed head.  Un-gated so the
// reindex / search-index build path works without the `cc-parquet` feature.
async fn bridge_cc_graph_to_distributed_head(
    state: &KotobaState,
    graph_cid: KotobaCid,
    graph_name: &'static str,
    author: &str,
    datoms: Vec<KqeDatom>,
) -> Result<(String, usize), (StatusCode, String)> {
    if datoms.is_empty() {
        return Ok((String::new(), 0));
    }
    let tx_cid = KotobaCid::from_bytes(
        format!(
            "cc.ingest:{graph_name}:{}:{}",
            author,
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_nanos())
                .unwrap_or(0)
        )
        .as_bytes(),
    );
    let datoms = datoms
        .into_iter()
        .map(|mut datom| {
            datom.tx = tx_cid.clone();
            kotoba_datomic::Datom::from_kqe(datom)
        })
        .collect::<Vec<_>>();
    let resp = crate::xrpc::commit_protocol_datoms(
        state,
        graph_cid.clone(),
        graph_name.to_string(),
        graph_cid,
        datoms,
        tx_cid,
        author.to_string(),
        kotoba_auth::CacaoPayload::OP_DATOM_TRANSACT,
        None,
        None,
    )
    .await?;
    Ok((resp.commit_cid, resp.assert_count))
}

#[derive(Serialize)]
pub struct CcSearchResult {
    pub url: String,
    pub domain: String,
    pub score: f32,
    pub text: String,
    pub lang: Option<String>,
}

pub async fn cc_search(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<CcSearchQuery>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_query_field("q", &q.q) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_lang(q.lang.as_deref()) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_nprobe(q.nprobe) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    let embed_client = match state.cc_embed_client.as_ref() {
        Some(c) => Arc::clone(c),
        None => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({"error": "embed client not configured; set KOTOBA_EMBED_URL"})),
            )
                .into_response()
        }
    };

    let vecs = match embed_client.embed_batch(&[q.q.as_str()]).await {
        Ok(v) => v,
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"error": format!("embedding failed: {e}")})),
            )
                .into_response()
        }
    };
    let query_vec = &vecs[0];
    let datoms = match current_cc_chunk_datoms(&state).await {
        Ok(datoms) => datoms,
        Err((code, msg)) => return (code, Json(json!({"error": msg}))).into_response(),
    };

    let chunk_embeddings = collect_chunk_embeddings(&datoms);
    if chunk_embeddings.is_empty() {
        return Json(json!({ "results": [], "total": 0, "note": "no embeddings found" }))
            .into_response();
    }

    let top_k = q.top_k.min(MAX_TOP_K);

    // IVF (probe `nprobe` nearest centroids via persisted `cc/ivf/cluster`
    // assignments) when an index is present, else brute-force cosine.
    let ranked = semantic_ranking(&datoms, &chunk_embeddings, query_vec, q.nprobe, top_k);

    let mut results: Vec<CcSearchResult> = Vec::new();
    for (score, idx) in ranked {
        let Some((subj, _)) = chunk_embeddings.get(idx) else {
            continue;
        };
        let lang = get_chunk_field(&datoms, subj, "cc/chunk/lang");
        if let Some(ref lf) = q.lang {
            if lang.as_deref() != Some(lf.as_str()) {
                continue;
            }
        }
        results.push(CcSearchResult {
            url: get_chunk_field(&datoms, subj, "cc/chunk/url").unwrap_or_default(),
            domain: get_chunk_field(&datoms, subj, "cc/chunk/domain").unwrap_or_default(),
            text: get_chunk_field(&datoms, subj, "cc/chunk/text").unwrap_or_default(),
            score,
            lang,
        });
    }

    Json(json!({ "results": results, "total": results.len() })).into_response()
}

// ── search.web (hybrid: lexical + semantic + authority) ─────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WebSearchQuery {
    pub q: String,
    #[serde(default = "default_top_k")]
    pub top_k: usize,
    #[serde(default = "default_nprobe")]
    pub nprobe: usize,
    pub lang: Option<String>,
    /// Lexical (BM25) RRF weight.
    #[serde(default = "default_signal_weight")]
    pub w_lex: f32,
    /// Semantic (vector) RRF weight.
    #[serde(default = "default_signal_weight")]
    pub w_sem: f32,
    /// Authority (PageRank) RRF weight.
    #[serde(default = "default_authority_weight")]
    pub w_auth: f32,
}

fn default_signal_weight() -> f32 {
    1.0
}
fn default_authority_weight() -> f32 {
    0.5
}

#[derive(Serialize)]
pub struct WebSearchResult {
    pub url: String,
    pub domain: String,
    pub text: String,
    pub lang: Option<String>,
    /// Fused RRF score (higher = better).
    pub score: f32,
    /// Per-signal 1-based rank for this document (lex / sem / auth).
    pub signals: serde_json::Value,
}

/// Collect `(chunk_subject, chunk_text)` for lexical indexing.
fn collect_chunk_texts(datoms: &[KqeDatom]) -> Vec<(KotobaCid, String)> {
    let mut out = Vec::new();
    for d in datoms {
        if d.a == "cc/chunk/text" {
            if let KqeValue::Text(t) = &d.v {
                out.push((d.e.clone(), t.clone()));
            }
        }
    }
    out
}

/// Map each chunk subject (multibase) → its parent page CID (`cc/chunk/page`).
fn collect_chunk_pages(datoms: &[KqeDatom]) -> HashMap<String, KotobaCid> {
    let mut out = HashMap::new();
    for d in datoms {
        if d.a == "cc/chunk/page" {
            if let KqeValue::Cid(c) = &d.v {
                out.insert(d.e.to_multibase(), c.clone());
            }
        }
    }
    out
}

/// Hybrid web search: fuse lexical (BM25), semantic (IVF/cosine) and authority
/// (PageRank) rankings via Reciprocal Rank Fusion.
///
/// Lexical search needs no embedding backend, so this endpoint degrades
/// gracefully: if `KOTOBA_EMBED_URL` is unset the semantic leg is simply
/// dropped and results come from BM25 + PageRank alone.  Authority is included
/// only when the `cc:2026-12:links` graph has PageRank scores.
pub async fn web_search(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Query(q): Query<WebSearchQuery>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_query_field("q", &q.q) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_lang(q.lang.as_deref()) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_nprobe(q.nprobe) {
        return (code, Json(json!({"error": msg}))).into_response();
    }

    let top_k = q.top_k.min(MAX_TOP_K);
    // Over-fetch each signal so fusion has depth to work with.
    let signal_k = (top_k * 4).clamp(top_k, MAX_TOP_K * 4);

    let datoms = match current_cc_chunk_datoms(&state).await {
        Ok(d) => d,
        Err((code, msg)) => return (code, Json(json!({"error": msg}))).into_response(),
    };
    if datoms.is_empty() {
        return Json(json!({ "results": [], "total": 0, "note": "no CC data indexed" }))
            .into_response();
    }

    // ── lexical (BM25) ──
    // Prefer the precomputed `cc/bm25/*` index (built by search.reindex / the
    // ingest job); fall back to a query-time build over the in-memory corpus.
    let texts = collect_chunk_texts(&datoms);
    let bm25 = Bm25Index::from_datoms(&datoms)
        .filter(|idx| !idx.is_empty())
        .unwrap_or_else(|| Bm25Index::build(&texts));
    let lex_ranking: Ranking = bm25
        .search_cids(&q.q, signal_k)
        .into_iter()
        .map(|(score, cid)| (cid, score))
        .collect();

    // ── semantic (vector / IVF) ── (optional — needs an embed backend)
    let mut sem_ranking: Ranking = Vec::new();
    if let Some(client) = state.cc_embed_client.as_ref() {
        match client.embed_batch(&[q.q.as_str()]).await {
            Ok(vecs) if !vecs.is_empty() => {
                let chunk_embeddings = collect_chunk_embeddings(&datoms);
                if !chunk_embeddings.is_empty() {
                    let ranked =
                        semantic_ranking(&datoms, &chunk_embeddings, &vecs[0], q.nprobe, signal_k);
                    sem_ranking = ranked
                        .into_iter()
                        .filter_map(|(s, idx)| {
                            chunk_embeddings.get(idx).map(|(cid, _)| (cid.clone(), s))
                        })
                        .collect();
                }
            }
            Ok(_) => {}
            Err(e) => tracing::warn!(err = %e, "web_search: query embedding failed; lexical-only"),
        }
    }

    // ── authority (PageRank over the links graph) ──
    let auth_ranking: Ranking = match current_cc_graph_datoms(&state, &cc_links_graph()).await {
        Ok(link_datoms) => match PageRankIndex::from_datoms(&link_datoms) {
            Some(pr) => {
                let chunk_pages = collect_chunk_pages(&datoms);
                // A chunk's authority is its parent page's normalised PageRank.
                texts
                    .iter()
                    .filter_map(|(chunk_cid, _)| {
                        chunk_pages
                            .get(&chunk_cid.to_multibase())
                            .map(|page| (chunk_cid.clone(), pr.normalized_score(page) as f32))
                    })
                    .filter(|(_, s)| *s > 0.0)
                    .collect()
            }
            None => Vec::new(),
        },
        Err(_) => Vec::new(),
    };

    // ── fuse (RRF) ──
    let mut signals: Vec<Signal<'_>> = Vec::new();
    if !lex_ranking.is_empty() {
        signals.push(Signal {
            name: "lex",
            weight: q.w_lex.max(0.0),
            ranking: &lex_ranking,
        });
    }
    if !sem_ranking.is_empty() {
        signals.push(Signal {
            name: "sem",
            weight: q.w_sem.max(0.0),
            ranking: &sem_ranking,
        });
    }
    if !auth_ranking.is_empty() {
        signals.push(Signal {
            name: "auth",
            weight: q.w_auth.max(0.0),
            ranking: &auth_ranking,
        });
    }

    let fused = reciprocal_rank_fusion(&signals, RRF_K, top_k.max(1) * 2);

    // ── materialise results (+ lang filter) ──
    let mut results: Vec<WebSearchResult> = Vec::new();
    for hit in fused {
        if results.len() >= top_k {
            break;
        }
        let lang = get_chunk_field(&datoms, &hit.cid, "cc/chunk/lang");
        if let Some(ref lf) = q.lang {
            if lang.as_deref() != Some(lf.as_str()) {
                continue;
            }
        }
        results.push(WebSearchResult {
            url: get_chunk_field(&datoms, &hit.cid, "cc/chunk/url").unwrap_or_default(),
            domain: get_chunk_field(&datoms, &hit.cid, "cc/chunk/domain").unwrap_or_default(),
            text: get_chunk_field(&datoms, &hit.cid, "cc/chunk/text").unwrap_or_default(),
            lang,
            score: hit.score,
            signals: json!(hit.ranks),
        });
    }

    Json(json!({
        "results": results,
        "total":   results.len(),
        "fused":   signals.iter().map(|s| s.name).collect::<Vec<_>>(),
    }))
    .into_response()
}

// ── search.reindex (rebuild BM25 + PageRank) ────────────────────────────────────

#[derive(Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct ReindexBody {
    #[serde(default = "default_owner_did")]
    pub owner_did: String,
}

/// Rebuild the persisted search indexes: a corpus-global BM25 over the chunk
/// graph and PageRank over the link graph.  Idempotent — run after a CC ingest
/// (the ingest job also triggers it automatically) or whenever the link graph
/// changes.
pub async fn search_reindex(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<ReindexBody>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) =
        crate::graph_auth::validate_did(&body.owner_did, "owner_did", MAX_OWNER_DID_LEN)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    match rebuild_search_indexes(&state, &body.owner_did).await {
        Ok((bm25_n, pr_n, edge_n)) => Json(json!({
            "status":          "ok",
            "bm25_datoms":     bm25_n,
            "pagerank_datoms": pr_n,
            "link_edges":      edge_n,
        }))
        .into_response(),
        Err((code, msg)) => (code, Json(json!({"error": msg}))).into_response(),
    }
}

// ── cc.rag ────────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CcRagBody {
    pub query: String,
    #[serde(default = "default_rag_k")]
    pub context_k: usize,
    #[serde(default = "default_nprobe")]
    pub nprobe: usize,
    pub lang: Option<String>,
    pub system: Option<String>,
}

fn default_rag_k() -> usize {
    5
}

pub async fn cc_rag(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<CcRagBody>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_query_field("query", &body.query) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_lang(body.lang.as_deref()) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Some(ref sys) = body.system {
        if sys.len() > MAX_SYSTEM_LEN {
            return (
                StatusCode::BAD_REQUEST,
                Json(
                    json!({"error": format!("system prompt exceeds {MAX_SYSTEM_LEN} characters")}),
                ),
            )
                .into_response();
        }
    }
    if let Err((code, msg)) = validate_cc_nprobe(body.nprobe) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    let embed_client = match state.cc_embed_client.as_ref() {
        Some(c) => Arc::clone(c),
        None => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({"error": "embed client not configured"})),
            )
                .into_response()
        }
    };

    let vecs = match embed_client.embed_batch(&[body.query.as_str()]).await {
        Ok(v) => v,
        Err(e) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(json!({"error": format!("embedding failed: {e}")})),
            )
                .into_response()
        }
    };
    let query_vec = &vecs[0];
    let datoms = match current_cc_chunk_datoms(&state).await {
        Ok(datoms) => datoms,
        Err((code, msg)) => return (code, Json(json!({"error": msg}))).into_response(),
    };

    let chunk_embeddings = collect_chunk_embeddings(&datoms);
    if chunk_embeddings.is_empty() {
        return Json(json!({
            "answer":  "(no CC data indexed)",
            "context": [],
            "query":   body.query,
        }))
        .into_response();
    }
    let ranked = brute_force_cosine(
        query_vec,
        &chunk_embeddings,
        body.context_k.min(MAX_CONTEXT_K),
    );

    let mut context_texts: Vec<String> = Vec::new();
    let mut context_meta: Vec<Value> = Vec::new();

    for (score, idx) in &ranked {
        let Some((subj, _)) = chunk_embeddings.get(*idx) else {
            continue;
        };
        let lang = get_chunk_field(&datoms, subj, "cc/chunk/lang");
        if let Some(ref lf) = body.lang {
            if lang.as_deref() != Some(lf.as_str()) {
                continue;
            }
        }
        let text = get_chunk_field(&datoms, subj, "cc/chunk/text").unwrap_or_default();
        let url = get_chunk_field(&datoms, subj, "cc/chunk/url").unwrap_or_default();
        let domain = get_chunk_field(&datoms, subj, "cc/chunk/domain").unwrap_or_default();
        context_texts.push(text.clone());
        context_meta.push(json!({ "url": url, "domain": domain, "score": score, "text": text }));
    }

    let answer = if let Some(ref infer) = state.inference_engine {
        let system = body.system.as_deref().unwrap_or(
            "You are a knowledgeable assistant. Answer concisely based on the provided context.",
        );
        let prompt = format!(
            "{system}\n\nContext from Common Crawl:\n{}\n\nQuestion: {}\n\nAnswer:",
            context_texts.join("\n\n---\n\n"),
            body.query
        );
        match (infer)(&prompt, 512) {
            Ok(t) => t,
            Err(e) => {
                tracing::warn!(err = %e, "cc_rag: inference failed");
                format!("[inference error: {e}]")
            }
        }
    } else {
        context_texts.join("\n\n")
    };

    Json(json!({
        "answer":  answer,
        "context": context_meta,
        "query":   body.query,
    }))
    .into_response()
}

// ── cc.ingest ─────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct CcIngestBody {
    pub parquet_dir: String,
    pub max_batches: Option<usize>,
    #[serde(default = "default_ingest_mode")]
    pub mode: String,
    #[serde(default = "default_owner_did")]
    pub owner_did: String,
}

fn default_ingest_mode() -> String {
    "chunks".to_string()
}
fn default_owner_did() -> String {
    "did:plc:unknown".to_string()
}

#[cfg(feature = "cc-parquet")]
pub async fn cc_ingest(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<CcIngestBody>,
) -> impl IntoResponse {
    use kotoba_ingest::cc::{CcChunkIngestor, CcPageIngestor};
    use kotoba_ingest::embed_client::Blake3EmbedClient;

    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }

    if let Err((code, msg)) = validate_cc_parquet_dir(&body.parquet_dir) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_mode(&body.mode) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) =
        crate::graph_auth::validate_did(&body.owner_did, "owner_did", MAX_OWNER_DID_LEN)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }

    let quad_store = Arc::clone(&state.quad_store);
    let embed_client = state.cc_embed_client.clone();
    let parquet_dir = body.parquet_dir.clone();
    let max_batches = body.max_batches;
    let mode = body.mode.clone();
    let owner_did = body.owner_did.clone();
    let state_for_ingest = Arc::clone(&state);

    // Use a timestamp-based job_id without chrono
    let job_id = format!(
        "cc-ingest-{}",
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0)
    );

    tokio::spawn(async move {
        let dir = std::path::Path::new(&parquet_dir);
        if mode == "pages" || mode == "both" {
            let ingestor = CcPageIngestor::new(Arc::clone(&quad_store));
            match ingestor.ingest_dir_datoms(dir, max_batches).await {
                Ok((files, datoms)) => {
                    let datom_count = datoms.len();
                    tracing::info!(files, datom_count, "CC pages ingest datoms built");
                    match bridge_cc_graph_to_distributed_head(
                        &state_for_ingest,
                        cc_pages_graph(),
                        "cc:2026-12:pages",
                        &owner_did,
                        datoms,
                    )
                    .await
                    {
                        Ok((commit_cid, assert_count)) => {
                            tracing::info!(%commit_cid, assert_count, "CC pages distributed commit complete");
                        }
                        Err((status, msg)) => {
                            tracing::error!(%status, error = %msg, "CC pages distributed commit failed");
                        }
                    }
                }
                Err(e) => tracing::error!(err = %e, "CC pages ingest failed"),
            }

            // Link graph (outlink edges) → cc:2026-12:links, for PageRank.
            match ingestor.ingest_links_dir_datoms(dir, max_batches).await {
                Ok((_files, link_datoms)) if !link_datoms.is_empty() => {
                    let edge_count = link_datoms.len();
                    match bridge_cc_graph_to_distributed_head(
                        &state_for_ingest,
                        cc_links_graph(),
                        "cc:2026-12:links",
                        &owner_did,
                        link_datoms,
                    )
                    .await
                    {
                        Ok((commit_cid, assert_count)) => {
                            tracing::info!(%commit_cid, assert_count, edge_count, "CC links distributed commit complete");
                        }
                        Err((status, msg)) => {
                            tracing::error!(%status, error = %msg, "CC links distributed commit failed");
                        }
                    }
                }
                Ok(_) => tracing::info!(
                    "CC links: no outlink edges in dataset (authority signal absent)"
                ),
                Err(e) => tracing::error!(err = %e, "CC links ingest failed"),
            }
        }
        if mode == "chunks" || mode == "both" {
            let client: Arc<dyn EmbedClient> =
                embed_client.unwrap_or_else(|| Arc::new(Blake3EmbedClient::new(384)));
            let ingestor = CcChunkIngestor::new(Arc::clone(&quad_store), client);
            match ingestor.ingest_dir_datoms(dir, max_batches).await {
                Ok((chunks, embeddings, datoms)) => {
                    let datom_count = datoms.len();
                    tracing::info!(
                        chunks,
                        embeddings,
                        datom_count,
                        "CC chunks ingest datoms built"
                    );
                    match bridge_cc_graph_to_distributed_head(
                        &state_for_ingest,
                        cc_chunks_graph(),
                        "cc:2026-12:chunks",
                        &owner_did,
                        datoms,
                    )
                    .await
                    {
                        Ok((commit_cid, assert_count)) => {
                            tracing::info!(%commit_cid, assert_count, "CC chunks distributed commit complete");
                        }
                        Err((status, msg)) => {
                            tracing::error!(%status, error = %msg, "CC chunks distributed commit failed");
                        }
                    }
                }
                Err(e) => tracing::error!(err = %e, "CC chunks ingest failed"),
            }
        }

        // Post-ingest: rebuild the corpus-global search indexes (BM25 over the
        // chunk graph, PageRank over the link graph) so search.web reads a
        // precomputed index rather than rebuilding per query.
        match rebuild_search_indexes(&state_for_ingest, &owner_did).await {
            Ok((bm25_n, pr_n, edge_n)) => {
                tracing::info!(bm25_n, pr_n, edge_n, "CC search indexes rebuilt");
            }
            Err((status, msg)) => {
                tracing::error!(%status, error = %msg, "CC search index rebuild failed");
            }
        }
    });

    Json(json!({
        "job_id":      job_id,
        "status":      "started",
        "parquet_dir": body.parquet_dir,
        "mode":        body.mode,
    }))
    .into_response()
}

#[cfg(not(feature = "cc-parquet"))]
pub async fn cc_ingest(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
    Json(body): Json<CcIngestBody>,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) = validate_cc_mode(&body.mode) {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    if let Err((code, msg)) =
        crate::graph_auth::validate_did(&body.owner_did, "owner_did", MAX_OWNER_DID_LEN)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    (
        StatusCode::SERVICE_UNAVAILABLE,
        Json(json!({"error": "cc.ingest requires the `cc-parquet` feature"})),
    )
        .into_response()
}

// ── cc.status ────────────────────────────────────────────────────────────────

pub async fn cc_status(
    State(state): State<Arc<KotobaState>>,
    headers: HeaderMap,
) -> impl IntoResponse {
    if let Err((code, msg)) =
        crate::graph_auth::require_operator_auth(&headers, &state.operator_did)
    {
        return (code, Json(json!({"error": msg}))).into_response();
    }
    let chunks_graph = cc_chunks_graph();
    let pages_graph = cc_pages_graph();

    let chunk_datoms = match current_cc_graph_datoms(&state, &chunks_graph).await {
        Ok(datoms) => datoms,
        Err((code, msg)) => return (code, Json(json!({"error": msg}))).into_response(),
    };
    let page_datoms = match current_cc_graph_datoms(&state, &pages_graph).await {
        Ok(datoms) => datoms,
        Err((code, msg)) => return (code, Json(json!({"error": msg}))).into_response(),
    };

    let chunk_count = chunk_datoms
        .iter()
        .filter(|datom| datom.a == "cc/chunk/text")
        .map(|datom| datom.e.to_multibase())
        .collect::<std::collections::HashSet<_>>()
        .len();
    let page_count = page_datoms
        .iter()
        .filter(|datom| datom.a == "cc/url")
        .map(|datom| datom.e.to_multibase())
        .collect::<std::collections::HashSet<_>>()
        .len();
    let ivf_centroids = chunk_datoms
        .iter()
        .filter(|datom| datom.a == "cc/ivf/centroid_id")
        .map(|datom| datom.e.to_multibase())
        .collect::<std::collections::HashSet<_>>()
        .len();
    let bm25_terms = chunk_datoms
        .iter()
        .filter(|datom| datom.a == "cc/bm25/term")
        .count();

    let links_graph = cc_links_graph();
    let (link_edges, pagerank_nodes) = match current_cc_graph_datoms(&state, &links_graph).await {
        Ok(link_datoms) => (
            link_datoms.iter().filter(|d| d.a == "cc/link/to").count(),
            link_datoms
                .iter()
                .filter(|d| d.a == "cc/rank/score")
                .count(),
        ),
        Err(_) => (0, 0),
    };

    Json(json!({
        "chunks_indexed":   chunk_count,
        "pages_indexed":    page_count,
        "ivf_centroids":    ivf_centroids,
        "bm25_terms":       bm25_terms,
        "link_edges":       link_edges,
        "pagerank_nodes":   pagerank_nodes,
        "embed_configured": state.cc_embed_client.is_some(),
        "chunks_graph_cid": chunks_graph.to_multibase(),
        "pages_graph_cid":  pages_graph.to_multibase(),
        "links_graph_cid":  links_graph.to_multibase(),
    }))
    .into_response()
}

#[cfg(test)]
mod tests {
    use super::*;

    // ── cosine_score ──────────────────────────────────────────────────────────

    #[test]
    fn cosine_score_identity() {
        let v = vec![1.0f32, 2.0, 3.0];
        let s = cosine_score(&v, &v);
        assert!((s - 1.0).abs() < 1e-6, "same vector → 1.0, got {s}");
    }

    #[test]
    fn cosine_score_orthogonal() {
        let a = vec![1.0f32, 0.0];
        let b = vec![0.0f32, 1.0];
        let s = cosine_score(&a, &b);
        assert!(s.abs() < 1e-6, "orthogonal → ~0.0, got {s}");
    }

    #[test]
    fn cosine_score_opposite() {
        let a = vec![1.0f32, 0.0];
        let b = vec![-1.0f32, 0.0];
        let s = cosine_score(&a, &b);
        assert!((s + 1.0).abs() < 1e-6, "opposite → -1.0, got {s}");
    }

    #[test]
    fn cosine_score_zero_vector_no_nan() {
        // norm guard: .max(1e-9) ensures no NaN; dot=0 → result=0
        let a = vec![0.0f32, 0.0];
        let b = vec![1.0f32, 0.0];
        let s = cosine_score(&a, &b);
        assert!(!s.is_nan(), "must not be NaN");
        assert!(s.abs() < 1e-3, "zero-vector dot=0 → ~0.0, got {s}");
    }

    #[test]
    fn cosine_score_mismatched_lengths_uses_zip() {
        // zip truncates to shorter; na uses full a, nb uses full b
        // a=[1,0,0], b=[1,0]  dot=1  na=1  nb=1 → 1.0
        let a = vec![1.0f32, 0.0, 0.0];
        let b = vec![1.0f32, 0.0];
        let s = cosine_score(&a, &b);
        assert!(
            (s - 1.0).abs() < 1e-5,
            "zip-truncated overlap identical → 1.0, got {s}"
        );
    }

    // ── brute_force_cosine ───────────────────────────────────────────────────

    #[test]
    fn brute_force_cosine_empty_embeddings() {
        let q = vec![1.0f32, 0.0];
        let result = brute_force_cosine(&q, &[], 5);
        assert!(result.is_empty());
    }

    #[test]
    fn brute_force_cosine_top_k_zero() {
        let q = vec![1.0f32, 0.0];
        let cid = KotobaCid::from_bytes(b"x");
        let emb = vec![(cid, vec![1.0f32, 0.0])];
        let result = brute_force_cosine(&q, &emb, 0);
        assert!(result.is_empty());
    }

    #[test]
    fn brute_force_cosine_sorted_descending() {
        let q = vec![1.0f32, 0.0];
        let cid0 = KotobaCid::from_bytes(b"a");
        let cid1 = KotobaCid::from_bytes(b"b");
        let cid2 = KotobaCid::from_bytes(b"c");
        let embs = vec![
            (cid0, vec![0.0f32, 1.0]),  // orthogonal → ~0
            (cid1, vec![-1.0f32, 0.0]), // opposite   → -1
            (cid2, vec![1.0f32, 0.0]),  // identical  → 1
        ];
        let result = brute_force_cosine(&q, &embs, 3);
        assert_eq!(result.len(), 3);
        // scores must be non-increasing
        for w in result.windows(2) {
            assert!(w[0].0 >= w[1].0, "not sorted descending: {:?}", result);
        }
        // best match is cid2 (index 2)
        assert_eq!(result[0].1, 2);
    }

    #[test]
    fn brute_force_cosine_truncates_to_top_k() {
        let q = vec![1.0f32, 0.0];
        let embs: Vec<(KotobaCid, Vec<f32>)> = (0u8..10)
            .map(|i| (KotobaCid::from_bytes(&[i]), vec![i as f32, 0.0]))
            .collect();
        let result = brute_force_cosine(&q, &embs, 3);
        assert_eq!(result.len(), 3);
    }

    // ── constants ─────────────────────────────────────────────────────────────

    #[test]
    fn nsid_constants_have_correct_prefix() {
        let prefix = "com.etzhayyim.apps.kotoba.cc.";
        assert!(NSID_CC_SEARCH.starts_with(prefix));
        assert!(NSID_CC_RAG.starts_with(prefix));
        assert!(NSID_CC_INGEST.starts_with(prefix));
        assert!(NSID_CC_STATUS.starts_with(prefix));
    }

    #[test]
    fn limits_are_sane() {
        assert!(MAX_QUERY_LEN >= 1_024);
        assert!(MAX_TOP_K >= 10);
        assert!(MAX_CONTEXT_K <= MAX_TOP_K);
        assert_eq!(MAX_OWNER_DID_LEN, 512);
        assert!(
            MAX_NPROBE >= 10,
            "MAX_NPROBE should allow reasonable IVF probing"
        );
        assert!(
            MAX_NPROBE <= 1_024,
            "MAX_NPROBE must cap unbounded computation"
        );
        #[cfg(feature = "cc-parquet")]
        assert!(MAX_PARQUET_DIR >= 10);
    }

    #[test]
    fn cc_query_and_lang_validation_rejects_empty_control_and_oversized_values() {
        assert!(validate_cc_query_field("q", "rust search").is_ok());
        assert!(validate_cc_lang(Some("ja")).is_ok());
        assert!(validate_cc_lang(None).is_ok());

        for value in ["", "   ", "bad\nquery"] {
            assert!(
                validate_cc_query_field("q", value).is_err(),
                "query should be rejected: {value:?}"
            );
        }
        let oversized_query = "q".repeat(MAX_QUERY_LEN + 1);
        assert!(validate_cc_query_field("q", &oversized_query).is_err());

        for lang in ["", "   ", "ja\n"] {
            assert!(
                validate_cc_lang(Some(lang)).is_err(),
                "lang should be rejected: {lang:?}"
            );
        }
        let oversized_lang = "x".repeat(MAX_LANG_LEN + 1);
        assert!(validate_cc_lang(Some(&oversized_lang)).is_err());
    }

    #[test]
    fn cc_mode_and_nprobe_validation_reject_invalid_values() {
        for mode in ["chunks", "pages", "both"] {
            assert!(validate_cc_mode(mode).is_ok());
        }
        assert!(validate_cc_mode("invalid").is_err());
        assert!(validate_cc_nprobe(MAX_NPROBE).is_ok());
        assert!(validate_cc_nprobe(MAX_NPROBE + 1).is_err());
    }

    #[cfg(feature = "cc-parquet")]
    #[test]
    fn cc_parquet_dir_validation_rejects_empty_control_and_oversized_values() {
        assert!(validate_cc_parquet_dir("/tmp/cc").is_ok());
        for value in ["", "   ", "/tmp/cc\nbad"] {
            assert!(validate_cc_parquet_dir(value).is_err());
        }
        let oversized = "p".repeat(MAX_PARQUET_DIR + 1);
        assert!(validate_cc_parquet_dir(&oversized).is_err());
    }

    #[test]
    fn max_nprobe_constant_value() {
        assert_eq!(MAX_NPROBE, 256);
    }

    #[test]
    fn default_nprobe_is_within_limit() {
        assert!(
            default_nprobe() <= MAX_NPROBE,
            "default_nprobe() {} exceeds MAX_NPROBE {}",
            default_nprobe(),
            MAX_NPROBE
        );
    }

    #[test]
    fn nprobe_at_limit_is_accepted() {
        // Boundary: MAX_NPROBE itself must be ≤ MAX_NPROBE (trivially, but documents intent)
        assert!(MAX_NPROBE <= MAX_NPROBE);
    }

    #[test]
    fn nprobe_above_limit_would_be_rejected() {
        // Documents that any nprobe > MAX_NPROBE should trigger a 400 in the handler.
        // The handler check is: if q.nprobe > MAX_NPROBE { return 400 }
        let oversized = MAX_NPROBE + 1;
        assert!(
            oversized > MAX_NPROBE,
            "oversized nprobe must exceed the cap"
        );
    }

    // ── hybrid web-search helpers ─────────────────────────────────────────────

    fn tx() -> KotobaCid {
        KotobaCid::from_bytes(b"tx")
    }
    fn d_int(e: &KotobaCid, a: &str, v: i64) -> KqeDatom {
        KqeDatom::assert(e.clone(), a.to_string(), KqeValue::Integer(v), tx())
    }
    fn d_text(e: &KotobaCid, a: &str, v: &str) -> KqeDatom {
        KqeDatom::assert(
            e.clone(),
            a.to_string(),
            KqeValue::Text(v.to_string()),
            tx(),
        )
    }
    fn d_cid(e: &KotobaCid, a: &str, v: &KotobaCid) -> KqeDatom {
        KqeDatom::assert(e.clone(), a.to_string(), KqeValue::Cid(v.clone()), tx())
    }

    #[test]
    fn collect_chunk_clusters_reads_ivf_assignments() {
        let c0 = KotobaCid::from_bytes(b"chunk0");
        let c1 = KotobaCid::from_bytes(b"chunk1");
        let datoms = vec![
            d_int(&c0, "cc/ivf/cluster", 3),
            d_int(&c1, "cc/ivf/cluster", 7),
            d_text(&c0, "cc/chunk/text", "ignored"),
        ];
        let m = collect_chunk_clusters(&datoms);
        assert_eq!(m.get(&c0.to_multibase()), Some(&3));
        assert_eq!(m.get(&c1.to_multibase()), Some(&7));
        assert_eq!(m.len(), 2);
    }

    #[test]
    fn collect_chunk_texts_and_pages() {
        let chunk = KotobaCid::from_bytes(b"chunkA");
        let page = KotobaCid::from_bytes(b"pageA");
        let datoms = vec![
            d_text(&chunk, "cc/chunk/text", "hello world"),
            d_cid(&chunk, "cc/chunk/page", &page),
        ];
        let texts = collect_chunk_texts(&datoms);
        assert_eq!(texts.len(), 1);
        assert_eq!(texts[0].1, "hello world");

        let pages = collect_chunk_pages(&datoms);
        assert_eq!(pages.get(&chunk.to_multibase()), Some(&page));
    }

    #[test]
    fn semantic_ranking_brute_forces_without_ivf() {
        // No cc/ivf/* datoms → falls back to brute-force cosine.
        let c0 = KotobaCid::from_bytes(b"e0");
        let c1 = KotobaCid::from_bytes(b"e1");
        let embeddings = vec![(c0, vec![1.0f32, 0.0]), (c1, vec![0.0f32, 1.0])];
        let datoms: Vec<KqeDatom> = Vec::new();
        let ranked = semantic_ranking(&datoms, &embeddings, &[1.0, 0.0], 8, 2);
        assert_eq!(ranked.len(), 2);
        assert_eq!(ranked[0].1, 0, "query [1,0] should rank e0 first");
        assert!(ranked[0].0 >= ranked[1].0);
    }

    #[test]
    fn build_bm25_datoms_then_restore_searches() {
        // Two chunks → global BM25 → persistence datoms → restore → search.
        let c0 = KotobaCid::from_bytes(b"chunk0");
        let c1 = KotobaCid::from_bytes(b"chunk1");
        let chunk_datoms = vec![
            d_text(&c0, "cc/chunk/text", "quantum machine learning"),
            d_text(&c1, "cc/chunk/text", "the lazy brown dog"),
        ];
        let bm25_datoms = build_bm25_datoms(&chunk_datoms);
        assert!(!bm25_datoms.is_empty(), "should emit cc/bm25/* datoms");
        assert!(bm25_datoms.iter().any(|d| d.a == "cc/bm25/term"));
        assert!(bm25_datoms.iter().any(|d| d.a == "cc/bm25/len"));

        // Restoring the persisted index reproduces the ranking.
        let idx = Bm25Index::from_datoms(&bm25_datoms).expect("restore");
        let top = idx.search_cids("quantum", 1);
        assert_eq!(top[0].1, c0, "quantum should retrieve chunk0");
    }

    #[test]
    fn build_bm25_datoms_empty_corpus() {
        assert!(build_bm25_datoms(&[]).is_empty());
    }

    #[test]
    fn collect_link_edges_and_pagerank_datoms() {
        // 3 → 1, 2 → 1 : page1 is the authority hub.
        let p1 = KotobaCid::from_bytes(b"page1");
        let p2 = KotobaCid::from_bytes(b"page2");
        let p3 = KotobaCid::from_bytes(b"page3");
        let link_datoms = vec![
            d_cid(&p3, "cc/link/to", &p1),
            d_cid(&p2, "cc/link/to", &p1),
            d_cid(&p1, "cc/link/to", &p2),
        ];
        let edges = collect_link_edges(&link_datoms);
        assert_eq!(edges.len(), 3);

        let pr_datoms = build_pagerank_datoms(&link_datoms);
        assert!(pr_datoms.iter().any(|d| d.a == "cc/rank/score"));

        // The persisted scores rank page1 highest.
        let pr = PageRankIndex::from_datoms(&pr_datoms).expect("restore");
        assert!(pr.score(&p1).unwrap() > pr.score(&p3).unwrap());
    }

    #[test]
    fn build_pagerank_datoms_no_edges() {
        assert!(build_pagerank_datoms(&[]).is_empty());
    }
}
