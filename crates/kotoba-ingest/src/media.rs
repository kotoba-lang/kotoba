//! Multimodal asset ingestor.
//!
//! Stores images, video, audio, and documents (books / PDF pages) as
//! content-addressed blobs in the KSE [`Vault`], embeds each asset into the
//! shared vector space via a [`MediaEmbedClient`], and projects the result as
//! Datoms (+ an IVF index) into the `media:2026:assets` named graph.
//!
//! This is the multimodal sibling of [`crate::cc::CcChunkIngestor`].  Because
//! text, image, video, and book embeddings all live in ONE space, a text query
//! can retrieve any modality (Google-style cross-modal search) by ranking the
//! `media/embed/*` vectors by cosine similarity.
//!
//! Predicate namespace `media/*`:
//!   media/mime            Text     — original MIME type
//!   media/modality        Text     — text|image|audio|video|document
//!   media/blob            Cid      — Vault blob CID (the raw bytes)
//!   media/size            Integer  — byte length
//!   media/title           Text     — optional display title
//!   media/source          Text     — optional path / URL provenance
//!   media/page            Integer  — page index (books / PDFs); 0 otherwise
//!   media/caption         Text     — optional caption / OCR / page text
//!   media/embed/{model}   VectorF32 (dim ≤ 1024) | TensorCid (larger)
//!   media/embed_norm      Float    — pre-computed L2 norm
//!   media/ivf/cluster     Integer  — assigned IVF centroid
//!   media/ivf/*           centroid table (see IvfIndex::to_quads_ns)

use std::path::{Path, PathBuf};
use std::sync::Arc;

use anyhow::{Context, Result};
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_graph::quad_store::QuadStore;
use kotoba_query::datom::{Datom, TensorDtype, Value};
use kotoba_query::quad::{LegacyQuad as Quad, LegacyQuadObject as QuadObject};
use kotoba_vault::Vault;
use tracing::{debug, info};

use crate::ivf::IvfIndex;
use crate::media_embed::{MediaEmbedClient, MediaItem, Modality};

/// Predicate namespace for multimodal asset datoms.
pub const MEDIA_NS: &str = "media";

/// Named graph holding multimodal assets.
pub fn media_assets_graph() -> KotobaCid {
    KotobaCid::from_bytes(b"media:2026:assets")
}

// ── Subject derivation ─────────────────────────────────────────────────────────

/// Deterministic, content-derived subject CID for an asset.
///
/// Keyed on (blob CID, page, source) so re-ingesting identical bytes is
/// idempotent, while the same image used as distinct pages / sources stays
/// distinct.
fn subject_for(blob_cid: &KotobaCid, page: i64, source: &str) -> KotobaCid {
    KotobaCid::from_bytes(format!("media:{}:{}:{}", blob_cid.to_multibase(), page, source).as_bytes())
}

// ── Inputs / outputs ────────────────────────────────────────────────────────────

/// One asset to ingest.
#[derive(Debug, Clone)]
pub struct MediaInput {
    pub mime: String,
    pub bytes: Bytes,
    pub title: Option<String>,
    pub source: Option<String>,
    /// Page index for paginated documents (books / PDFs).  Use `0` otherwise.
    pub page: i64,
    /// Caption / OCR text / page text — the strongest cross-modal bridge.
    pub caption: Option<String>,
}

impl MediaInput {
    pub fn new(mime: impl Into<String>, bytes: Bytes) -> Self {
        Self {
            mime: mime.into(),
            bytes,
            title: None,
            source: None,
            page: 0,
            caption: None,
        }
    }
    pub fn with_title(mut self, t: impl Into<String>) -> Self {
        self.title = Some(t.into());
        self
    }
    pub fn with_source(mut self, s: impl Into<String>) -> Self {
        self.source = Some(s.into());
        self
    }
    pub fn with_page(mut self, p: i64) -> Self {
        self.page = p;
        self
    }
    pub fn with_caption(mut self, c: impl Into<String>) -> Self {
        self.caption = Some(c.into());
        self
    }
}

/// Summary of an ingest run.
#[derive(Debug, Default, Clone, serde::Serialize)]
pub struct MediaIngestReport {
    pub assets: u64,
    pub embeddings: u64,
    pub ivf_k: usize,
    pub graph_cid: String,
    pub model_id: String,
}

// ── Cosine ranking (shared with the search path) ─────────────────────────────────

/// Cosine similarity, zero-safe.
pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    let dot: f32 = a.iter().zip(b.iter()).map(|(x, y)| x * y).sum();
    let na: f32 = a.iter().map(|x| x * x).sum::<f32>().sqrt();
    let nb: f32 = b.iter().map(|x| x * x).sum::<f32>().sqrt();
    if na == 0.0 || nb == 0.0 {
        0.0
    } else {
        dot / (na * nb)
    }
}

/// Brute-force cosine ranking → up to `top_k` `(score, index)` pairs, best first.
pub fn rank_by_cosine(
    query: &[f32],
    embeddings: &[(KotobaCid, Vec<f32>)],
    top_k: usize,
) -> Vec<(f32, usize)> {
    let mut scored: Vec<(f32, usize)> = embeddings
        .iter()
        .enumerate()
        .map(|(i, (_, v))| (cosine_similarity(query, v), i))
        .collect();
    scored.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));
    scored.truncate(top_k);
    scored
}

// ── Quad helpers ─────────────────────────────────────────────────────────────────

fn text_quad(g: &KotobaCid, s: &KotobaCid, p: &str, v: &str) -> Quad {
    Quad {
        graph: g.clone(),
        subject: s.clone(),
        predicate: p.to_string(),
        object: QuadObject::Text(v.to_string()),
    }
}
fn int_quad(g: &KotobaCid, s: &KotobaCid, p: &str, v: i64) -> Quad {
    Quad {
        graph: g.clone(),
        subject: s.clone(),
        predicate: p.to_string(),
        object: QuadObject::Integer(v),
    }
}
fn cid_quad(g: &KotobaCid, s: &KotobaCid, p: &str, v: &KotobaCid) -> Quad {
    Quad {
        graph: g.clone(),
        subject: s.clone(),
        predicate: p.to_string(),
        object: QuadObject::Cid(v.clone()),
    }
}
fn quads_to_datoms(quads: Vec<Quad>) -> Vec<Datom> {
    quads
        .into_iter()
        .map(|q| Datom::from_legacy_quad(q, true))
        .collect()
}

// ═══════════════════════════════════════════════════════════════════════════════
// MediaIngestor
// ═══════════════════════════════════════════════════════════════════════════════

pub struct MediaIngestor {
    pub quad_store: Arc<QuadStore>,
    pub vault: Arc<Vault>,
    pub embed_client: Arc<dyn MediaEmbedClient>,
    pub graph_cid: KotobaCid,
    pub k_centroids: usize,
    pub ivf_max_iter: usize,
    /// Items per embedding request.
    pub embed_batch: usize,
}

impl MediaIngestor {
    pub fn new(
        quad_store: Arc<QuadStore>,
        vault: Arc<Vault>,
        embed_client: Arc<dyn MediaEmbedClient>,
    ) -> Self {
        Self {
            quad_store,
            vault,
            embed_client,
            graph_cid: media_assets_graph(),
            k_centroids: 64,
            ivf_max_iter: 20,
            embed_batch: 16,
        }
    }

    pub fn with_k(mut self, k: usize) -> Self {
        self.k_centroids = k;
        self
    }
    pub fn with_embed_batch(mut self, n: usize) -> Self {
        self.embed_batch = n.max(1);
        self
    }

    /// Ingest assets and commit them to the QuadStore.  Returns a run summary.
    pub async fn ingest_items(&self, inputs: Vec<MediaInput>) -> Result<MediaIngestReport> {
        let (mut report, datoms) = self.ingest_items_datoms(inputs).await?;
        if datoms.is_empty() {
            return Ok(report);
        }
        let graph = &self.graph_cid;
        self.quad_store
            .assert_datom_batch_silent(graph.clone(), datoms)
            .await;
        let commit_seq = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs();
        self.quad_store
            .commit("did:web:kotoba.etzhayyim.com", graph.clone(), commit_seq)
            .await?;
        self.quad_store.reset_arrangement(graph).await;

        report.graph_cid = graph.to_multibase();
        info!(
            assets = report.assets,
            embeddings = report.embeddings,
            ivf_k = report.ivf_k,
            "MediaIngestor: committed"
        );
        Ok(report)
    }

    /// Build Datoms for `inputs` **without** committing quads.  Blobs are still
    /// written to the Vault (content-addressed + idempotent), so the distributed
    /// commit path can publish the same data.
    pub async fn ingest_items_datoms(
        &self,
        inputs: Vec<MediaInput>,
    ) -> Result<(MediaIngestReport, Vec<Datom>)> {
        let model_id = self.embed_client.model_id().to_string();
        let mut report = MediaIngestReport {
            model_id: model_id.clone(),
            graph_cid: self.graph_cid.to_multibase(),
            ..Default::default()
        };
        if inputs.is_empty() {
            return Ok((report, vec![]));
        }
        let graph = &self.graph_cid;

        // ── Pass 1: store blobs + metadata quads, derive subjects ─────────────
        let mut subjects: Vec<KotobaCid> = Vec::with_capacity(inputs.len());
        let mut quads: Vec<Quad> = Vec::with_capacity(inputs.len() * 8);
        for input in &inputs {
            let blob = self
                .vault
                .put_typed(input.bytes.clone(), input.mime.clone())
                .await;
            let source = input.source.as_deref().unwrap_or("");
            let subj = subject_for(&blob.cid, input.page, source);
            let modality = Modality::from_mime(&input.mime);

            quads.push(text_quad(graph, &subj, "media/mime", &input.mime));
            quads.push(text_quad(graph, &subj, "media/modality", modality.as_str()));
            quads.push(cid_quad(graph, &subj, "media/blob", &blob.cid));
            quads.push(int_quad(graph, &subj, "media/size", input.bytes.len() as i64));
            quads.push(int_quad(graph, &subj, "media/page", input.page));
            if let Some(t) = &input.title {
                if !t.is_empty() {
                    quads.push(text_quad(graph, &subj, "media/title", t));
                }
            }
            if !source.is_empty() {
                quads.push(text_quad(graph, &subj, "media/source", source));
            }
            if let Some(c) = &input.caption {
                if !c.is_empty() {
                    quads.push(text_quad(graph, &subj, "media/caption", c));
                }
            }
            subjects.push(subj);
        }
        let mut datoms = quads_to_datoms(quads);
        report.assets = inputs.len() as u64;

        // ── Pass 2: embed into the shared space ───────────────────────────────
        let items: Vec<MediaItem> = inputs
            .iter()
            .map(|input| MediaItem {
                modality: Modality::from_mime(&input.mime),
                mime: &input.mime,
                bytes: &input.bytes,
                caption: input.caption.as_deref(),
            })
            .collect();

        let embed_pred = format!("media/embed/{model_id}");
        let mut all_embeddings: Vec<(KotobaCid, Vec<f32>)> = Vec::with_capacity(inputs.len());
        let mut base = 0usize;
        for chunk in items.chunks(self.embed_batch) {
            let vecs = self
                .embed_client
                .embed_media(chunk)
                .await
                .context("multimodal embed_media failed")?;
            for (i, vec) in vecs.into_iter().enumerate() {
                let subj = subjects[base + i].clone();
                let norm = vec.iter().map(|x| x * x).sum::<f32>().sqrt();

                let value = if vec.len() <= 1024 {
                    Value::VectorF32(vec.clone())
                } else {
                    let raw: Vec<u8> = vec.iter().flat_map(|f| f.to_le_bytes()).collect();
                    let tcid = KotobaCid::from_bytes(&raw);
                    Value::TensorCid {
                        cid: tcid,
                        shape: vec![vec.len() as u32],
                        dtype: TensorDtype::F32,
                    }
                };
                datoms.push(Datom::assert(
                    subj.clone(),
                    embed_pred.clone(),
                    value,
                    graph.clone(),
                ));
                datoms.push(Datom::assert(
                    subj.clone(),
                    "media/embed_norm".to_string(),
                    Value::Float(norm as f64),
                    graph.clone(),
                ));
                all_embeddings.push((subj, vec));
            }
            base += chunk.len();
        }
        report.embeddings = all_embeddings.len() as u64;

        // ── Pass 3: build IVF index over the shared-space vectors ─────────────
        let k = self.k_centroids.min(all_embeddings.len());
        if k > 0 {
            let t0 = std::time::Instant::now();
            let ivf = IvfIndex::build(&all_embeddings, k, &model_id, self.ivf_max_iter);
            debug!(k, n = all_embeddings.len(), elapsed_ms = t0.elapsed().as_millis(), "media IVF built");

            let mut member_counts = vec![0usize; k];
            let mut assign_quads: Vec<Quad> = Vec::with_capacity(all_embeddings.len());
            for (subj, vec) in &all_embeddings {
                let (centroid_id, _) = ivf.assign(vec);
                member_counts[centroid_id] += 1;
                assign_quads.push(int_quad(graph, subj, "media/ivf/cluster", centroid_id as i64));
            }
            datoms.extend(quads_to_datoms(assign_quads));
            datoms.extend(quads_to_datoms(
                ivf.to_quads_ns(graph, &member_counts, MEDIA_NS),
            ));
            report.ivf_k = k;
        }

        Ok((report, datoms))
    }

    /// Ingest whole files from disk, inferring MIME from the extension.
    ///
    /// Each file is ingested as a single asset (page 0, no caption).  Paginated
    /// documents whose pages carry text should be ingested via
    /// [`MediaIngestor::ingest_items`] with one [`MediaInput`] per page.
    pub async fn ingest_paths(&self, paths: &[PathBuf]) -> Result<MediaIngestReport> {
        let mut inputs = Vec::with_capacity(paths.len());
        for path in paths {
            let bytes = std::fs::read(path)
                .with_context(|| format!("read {}", path.display()))?;
            let mime = mime_for_path(path);
            let title = path
                .file_name()
                .and_then(|n| n.to_str())
                .map(|s| s.to_string());
            let mut input = MediaInput::new(mime, Bytes::from(bytes))
                .with_source(path.display().to_string());
            if let Some(t) = title {
                input = input.with_title(t);
            }
            inputs.push(input);
        }
        self.ingest_items(inputs).await
    }
}

/// Map a file extension to a MIME type (best-effort; falls back to octet-stream).
fn mime_for_path(path: &Path) -> String {
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_ascii_lowercase();
    match ext.as_str() {
        "png" => "image/png",
        "jpg" | "jpeg" => "image/jpeg",
        "gif" => "image/gif",
        "webp" => "image/webp",
        "bmp" => "image/bmp",
        "tif" | "tiff" => "image/tiff",
        "svg" => "image/svg+xml",
        "mp4" | "m4v" => "video/mp4",
        "webm" => "video/webm",
        "mov" => "video/quicktime",
        "mkv" => "video/x-matroska",
        "avi" => "video/x-msvideo",
        "mp3" => "audio/mpeg",
        "wav" => "audio/wav",
        "flac" => "audio/flac",
        "ogg" | "oga" => "audio/ogg",
        "m4a" => "audio/mp4",
        "pdf" => "application/pdf",
        "epub" => "application/epub+zip",
        "doc" => "application/msword",
        "docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt" | "md" => "text/plain",
        _ => "application/octet-stream",
    }
    .to_string()
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests (no network, no ML — Blake3MediaEmbedClient + in-memory Vault)
// ═══════════════════════════════════════════════════════════════════════════════

#[cfg(test)]
mod tests {
    use super::*;
    use crate::media_embed::Blake3MediaEmbedClient;
    use kotoba_vault::LiveBus;
    use kotoba_store::MemoryBlockStore;

    fn make_store() -> Arc<QuadStore> {
        let journal = Arc::new(LiveBus::new());
        let block_store = Arc::new(MemoryBlockStore::new())
            as Arc<dyn kotoba_core::store::BlockStore + Send + Sync>;
        Arc::new(QuadStore::new(journal, block_store))
    }

    fn make_ingestor(dim: usize) -> MediaIngestor {
        let qs = make_store();
        let vault = Arc::new(Vault::new());
        let embed = Arc::new(Blake3MediaEmbedClient::new(dim));
        MediaIngestor::new(qs, vault, embed).with_k(4)
    }

    #[test]
    fn assets_graph_is_stable_and_distinct() {
        assert_eq!(media_assets_graph(), media_assets_graph());
        assert_ne!(media_assets_graph(), KotobaCid::from_bytes(b"cc:2026-12:chunks"));
    }

    #[test]
    fn subject_is_content_derived_and_idempotent() {
        let blob = KotobaCid::from_bytes(b"blob-1");
        let a = subject_for(&blob, 0, "src");
        let b = subject_for(&blob, 0, "src");
        let c = subject_for(&blob, 1, "src");
        assert_eq!(a, b, "same (blob,page,source) → same subject");
        assert_ne!(a, c, "different page → different subject");
    }

    #[tokio::test]
    async fn ingest_writes_blob_and_embedding_datoms() {
        let ing = make_ingestor(64);
        let inputs = vec![
            MediaInput::new("image/png", Bytes::from_static(&[1, 2, 3, 4]))
                .with_caption("a red apple")
                .with_title("apple.png"),
            MediaInput::new("video/mp4", Bytes::from_static(&[9, 8, 7, 6, 5]))
                .with_caption("a running dog"),
        ];
        let (report, datoms) = ing.ingest_items_datoms(inputs).await.unwrap();
        assert_eq!(report.assets, 2);
        assert_eq!(report.embeddings, 2);

        // Blob was actually stored in the Vault.
        let blob_cids: Vec<_> = datoms
            .iter()
            .filter(|d| d.a == "media/blob")
            .filter_map(|d| match &d.v {
                Value::Cid(c) => Some(c.clone()),
                _ => None,
            })
            .collect();
        assert_eq!(blob_cids.len(), 2);
        for c in &blob_cids {
            assert!(ing.vault.contains(c).await, "blob {c:?} must be in vault");
        }

        // Embedding + modality datoms exist.
        assert!(datoms.iter().any(|d| d.a.starts_with("media/embed/")));
        assert!(datoms
            .iter()
            .any(|d| d.a == "media/modality" && matches!(&d.v, Value::Text(t) if t == "image")));
        assert!(datoms
            .iter()
            .any(|d| d.a == "media/modality" && matches!(&d.v, Value::Text(t) if t == "video")));
    }

    #[tokio::test]
    async fn cross_modal_text_query_retrieves_matching_image() {
        // The whole point: a TEXT query ranks an IMAGE asset top because they
        // share one embedding space (bridged here by the caption).
        let ing = make_ingestor(128);
        let inputs = vec![
            MediaInput::new("image/jpeg", Bytes::from_static(b"\xff\xd8apple-pixels"))
                .with_caption("red apple")
                .with_title("apple"),
            MediaInput::new("image/jpeg", Bytes::from_static(b"\xff\xd8car-pixels"))
                .with_caption("blue sports car")
                .with_title("car"),
            MediaInput::new("video/mp4", Bytes::from_static(b"\x00\x00ocean"))
                .with_caption("waves on a beach")
                .with_title("beach"),
        ];
        let (_r, datoms) = ing.ingest_items_datoms(inputs).await.unwrap();

        // Collect (subject, embedding) the way the search path would.
        let embeddings: Vec<(KotobaCid, Vec<f32>)> = datoms
            .iter()
            .filter(|d| d.a.starts_with("media/embed/"))
            .filter_map(|d| match &d.v {
                Value::VectorF32(v) => Some((d.e.clone(), v.clone())),
                _ => None,
            })
            .collect();
        assert_eq!(embeddings.len(), 3);

        // Embed the text query in the SAME space.
        let q_item = [MediaItem::text("red apple")];
        let q_vec = ing.embed_client.embed_media(&q_item).await.unwrap()[0].clone();

        let ranked = rank_by_cosine(&q_vec, &embeddings, 3);
        let top_subject = &embeddings[ranked[0].1].0;

        // The top hit must be the apple image's subject — find its title.
        let title = datoms
            .iter()
            .find(|d| d.e == *top_subject && d.a == "media/title")
            .and_then(|d| match &d.v {
                Value::Text(t) => Some(t.clone()),
                _ => None,
            });
        assert_eq!(title.as_deref(), Some("apple"), "text query must retrieve the apple image");
        assert!(ranked[0].0 > 0.999, "caption-bridged match should be ~1.0");
    }

    #[tokio::test]
    async fn ivf_centroids_persist_under_media_namespace_and_restore() {
        let ing = make_ingestor(32);
        let inputs: Vec<MediaInput> = (0..12)
            .map(|i| {
                MediaInput::new("image/png", Bytes::from(vec![i as u8; 8]))
                    .with_caption(format!("concept-{}", i % 3))
            })
            .collect();
        let (report, datoms) = ing.ingest_items_datoms(inputs).await.unwrap();
        assert!(report.ivf_k > 0);

        // Centroid datoms use the media/ivf/* namespace, not cc/ivf/*.
        assert!(datoms.iter().any(|d| d.a == "media/ivf/centroid_id"));
        assert!(datoms.iter().any(|d| d.a == "media/ivf/cluster"));
        assert!(!datoms.iter().any(|d| d.a.starts_with("cc/ivf/")));

        // The namespace-agnostic restore path reconstructs the index.
        let kqe_datoms: Vec<_> = datoms
            .iter()
            .filter(|d| d.a.contains("/ivf/"))
            .cloned()
            .collect();
        let restored = IvfIndex::from_datoms(&kqe_datoms).expect("restore media IVF");
        assert_eq!(restored.dim(), 32);
        assert_eq!(restored.k(), report.ivf_k);
    }

    #[tokio::test]
    async fn empty_input_is_noop() {
        let ing = make_ingestor(16);
        let (report, datoms) = ing.ingest_items_datoms(vec![]).await.unwrap();
        assert_eq!(report.assets, 0);
        assert!(datoms.is_empty());
    }

    #[tokio::test]
    async fn ingest_items_commits_to_store() {
        let ing = make_ingestor(16);
        let report = ing
            .ingest_items(vec![MediaInput::new(
                "image/png",
                Bytes::from_static(&[1, 2, 3]),
            )
            .with_caption("dot")])
            .await
            .unwrap();
        assert_eq!(report.assets, 1);
        assert_eq!(report.embeddings, 1);
        assert_eq!(report.graph_cid, media_assets_graph().to_multibase());
    }

    #[test]
    fn mime_for_path_covers_modalities() {
        assert_eq!(mime_for_path(Path::new("a.png")), "image/png");
        assert_eq!(mime_for_path(Path::new("a.mp4")), "video/mp4");
        assert_eq!(mime_for_path(Path::new("a.mp3")), "audio/mpeg");
        assert_eq!(mime_for_path(Path::new("a.pdf")), "application/pdf");
        assert_eq!(mime_for_path(Path::new("a.epub")), "application/epub+zip");
        assert_eq!(mime_for_path(Path::new("a.unknownext")), "application/octet-stream");
    }

    #[test]
    fn cosine_similarity_basics() {
        assert!((cosine_similarity(&[1.0, 0.0], &[1.0, 0.0]) - 1.0).abs() < 1e-6);
        assert!(cosine_similarity(&[1.0, 0.0], &[0.0, 1.0]).abs() < 1e-6);
        assert_eq!(cosine_similarity(&[0.0, 0.0], &[1.0, 1.0]), 0.0);
    }
}
