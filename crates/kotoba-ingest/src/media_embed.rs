//! MediaEmbedClient — multimodal embedding backend trait + implementations.
//!
//! Where [`crate::embed_client`] embeds *text* only, this module embeds text,
//! images, audio, video, and documents (book / PDF pages) into **one shared
//! vector space**.  That shared space is what makes Google-style cross-modal
//! retrieval possible: a text query embedding can rank image / video / book
//! embeddings by cosine similarity (CLIP- / ImageBind-style joint embeddings).
//!
//! Two concrete clients:
//!   HttpMediaEmbedClient   — POSTs base64 bytes + modality to an external
//!                            multimodal encoder (CLIP / SigLIP / ImageBind
//!                            served over HTTP).  Heavy ML stays out-of-process,
//!                            exactly like the text [`crate::embed_client`] path
//!                            delegates to Ollama / OpenAI-compat endpoints.
//!   Blake3MediaEmbedClient — deterministic pseudo-vectors for tests / CI, no
//!                            HTTP required.  Hashes the item's caption (when
//!                            present) so the *same concept* across modalities
//!                            lands on the *same vector* — letting offline tests
//!                            exercise the cross-modal retrieval path.
//!
//! Environment variables (for `HttpMediaEmbedClient::from_env`):
//!   KOTOBA_MM_EMBED_URL    — base URL, e.g. "http://localhost:8800"
//!   KOTOBA_MM_EMBED_MODEL  — model id, e.g. "siglip-so400m"
//!   KOTOBA_MM_EMBED_DIM    — output dimension (default: 768)
//!   KOTOBA_MM_EMBED_BATCH  — items per HTTP request (default: 16)

use std::future::Future;
use std::pin::Pin;

use anyhow::Result;
use base64::Engine as _;
use reqwest::Url;
use serde_json::json;

type EmbedFuture<'a> = Pin<Box<dyn Future<Output = Result<Vec<Vec<f32>>>> + Send + 'a>>;

const DEFAULT_MM_EMBED_URL: &str = "http://localhost:8800";
const DISABLED_MM_EMBED_URL: &str = "http://127.0.0.1:9";
const MAX_MM_EMBED_URL_LEN: usize = 256;

// ---------------------------------------------------------------------------
// Modality
// ---------------------------------------------------------------------------

/// The kind of content an asset carries.  All modalities share one embedding
/// space, so the variant only steers the encoder, not the vector geometry.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Modality {
    Text,
    Image,
    Audio,
    Video,
    /// Books, PDFs, e-pub, office documents — typically ingested page-by-page.
    Document,
}

impl Modality {
    /// Best-effort classification from a MIME type.
    pub fn from_mime(mime: &str) -> Modality {
        let m = mime.trim().to_ascii_lowercase();
        if m.starts_with("image/") {
            Modality::Image
        } else if m.starts_with("video/") {
            Modality::Video
        } else if m.starts_with("audio/") {
            Modality::Audio
        } else if m == "application/pdf"
            || m == "application/epub+zip"
            || m == "application/msword"
            || m.starts_with("application/vnd.openxmlformats-officedocument")
            || m.starts_with("application/vnd.oasis.opendocument")
        {
            Modality::Document
        } else if m.starts_with("text/") {
            Modality::Text
        } else {
            // Unknown binary: treat as an opaque document so it is still
            // stored + indexed rather than silently dropped.
            Modality::Document
        }
    }

    /// Stable lowercase tag persisted as the `media/modality` datom value.
    pub fn as_str(&self) -> &'static str {
        match self {
            Modality::Text => "text",
            Modality::Image => "image",
            Modality::Audio => "audio",
            Modality::Video => "video",
            Modality::Document => "document",
        }
    }
}

// ---------------------------------------------------------------------------
// MediaItem
// ---------------------------------------------------------------------------

/// One unit to embed.  Borrows its bytes / caption so callers can batch without
/// cloning large blobs.
pub struct MediaItem<'a> {
    pub modality: Modality,
    pub mime: &'a str,
    pub bytes: &'a [u8],
    /// Optional human-readable caption / OCR / page text.  When present it is
    /// the strongest cross-modal bridge to text queries.
    pub caption: Option<&'a str>,
}

impl<'a> MediaItem<'a> {
    /// Convenience constructor for a text query in the shared space.
    pub fn text(query: &'a str) -> MediaItem<'a> {
        MediaItem {
            modality: Modality::Text,
            mime: "text/plain",
            bytes: query.as_bytes(),
            caption: Some(query),
        }
    }
}

// ---------------------------------------------------------------------------
// Trait
// ---------------------------------------------------------------------------

/// Object-safe async multimodal embedding client.
pub trait MediaEmbedClient: Send + Sync {
    /// Embed a batch of media items into the shared vector space.
    fn embed_media<'a>(&'a self, items: &'a [MediaItem<'a>]) -> EmbedFuture<'a>;

    fn dim(&self) -> usize;
    fn model_id(&self) -> &str;
}

// ---------------------------------------------------------------------------
// HttpMediaEmbedClient
// ---------------------------------------------------------------------------

/// HTTP-backed multimodal encoder.
///
/// Wire format (request):
/// ```json
/// { "model": "...", "input": [
///     { "modality": "image", "mime": "image/png", "b64": "...", "text": null },
///     { "modality": "text",  "mime": "text/plain", "b64": "",   "text": "a cat" }
/// ]}
/// ```
/// Response: `{ "data": [ { "embedding": [f32, ...] }, ... ] }` (OpenAI-shaped).
#[derive(Debug, Clone)]
pub struct HttpMediaEmbedClient {
    base_url: String,
    model: String,
    dim: usize,
    batch_size: usize,
    http: reqwest::Client,
}

impl HttpMediaEmbedClient {
    pub fn new(
        base_url: impl Into<String>,
        model: impl Into<String>,
        dim: usize,
        batch_size: usize,
    ) -> Self {
        let base_url = normalize_mm_embed_url(&base_url.into()).unwrap_or_else(|| {
            tracing::warn!(
                "invalid multimodal embed base URL; disabling HttpMediaEmbedClient HTTP access"
            );
            DISABLED_MM_EMBED_URL.to_string()
        });
        Self {
            base_url,
            model: model.into(),
            dim,
            batch_size: batch_size.max(1),
            http: reqwest::Client::new(),
        }
    }

    pub fn from_env() -> Result<Self> {
        let base_url = std::env::var("KOTOBA_MM_EMBED_URL")
            .unwrap_or_else(|_| DEFAULT_MM_EMBED_URL.to_string());
        anyhow::ensure!(
            normalize_mm_embed_url(&base_url).is_some(),
            "invalid KOTOBA_MM_EMBED_URL"
        );
        let model =
            std::env::var("KOTOBA_MM_EMBED_MODEL").unwrap_or_else(|_| "clip-shared".to_string());
        let dim: usize = std::env::var("KOTOBA_MM_EMBED_DIM")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(768);
        let batch_size: usize = std::env::var("KOTOBA_MM_EMBED_BATCH")
            .ok()
            .and_then(|s| s.parse().ok())
            .unwrap_or(16);
        Ok(Self::new(base_url, model, dim, batch_size))
    }

    async fn embed_chunk(&self, items: &[MediaItem<'_>]) -> Result<Vec<Vec<f32>>> {
        let b64 = base64::engine::general_purpose::STANDARD;
        let input: Vec<serde_json::Value> = items
            .iter()
            .map(|it| {
                json!({
                    "modality": it.modality.as_str(),
                    "mime": it.mime,
                    // Text items send an empty payload; the encoder uses `text`.
                    "b64": if matches!(it.modality, Modality::Text) {
                        String::new()
                    } else {
                        b64.encode(it.bytes)
                    },
                    "text": it.caption,
                })
            })
            .collect();

        let url = format!(
            "{}/v1/embeddings/multimodal",
            self.base_url.trim_end_matches('/')
        );
        let body = json!({ "model": self.model, "input": input });
        let resp = self.http.post(&url).json(&body).send().await?;
        if !resp.status().is_success() {
            anyhow::bail!("multimodal embed endpoint returned {}", resp.status());
        }
        let v: serde_json::Value = resp.json().await?;
        let data = v
            .get("data")
            .and_then(|d| d.as_array())
            .ok_or_else(|| anyhow::anyhow!("response missing 'data' array"))?;
        let vecs: Vec<Vec<f32>> = data
            .iter()
            .filter_map(|item| {
                let emb = item.get("embedding")?.as_array()?;
                emb.iter().map(|x| x.as_f64().map(|f| f as f32)).collect()
            })
            .collect();
        if vecs.len() != items.len() {
            anyhow::bail!(
                "encoder returned {} vectors for {} items",
                vecs.len(),
                items.len()
            );
        }
        Ok(vecs)
    }
}

fn normalize_mm_embed_url(base_url: &str) -> Option<String> {
    let base_url = base_url.trim();
    if base_url.is_empty()
        || base_url.len() > MAX_MM_EMBED_URL_LEN
        || base_url.chars().any(|ch| ch.is_control())
    {
        return None;
    }
    let url = Url::parse(base_url).ok()?;
    if !matches!(url.scheme(), "http" | "https") {
        return None;
    }
    if url.host_str().is_none()
        || !url.username().is_empty()
        || url.password().is_some()
        || url.path() != "/"
        || url.query().is_some()
        || url.fragment().is_some()
    {
        return None;
    }
    Some(url.as_str().trim_end_matches('/').to_string())
}

impl MediaEmbedClient for HttpMediaEmbedClient {
    fn embed_media<'a>(&'a self, items: &'a [MediaItem<'a>]) -> EmbedFuture<'a> {
        Box::pin(async move {
            let mut all: Vec<Vec<f32>> = Vec::with_capacity(items.len());
            for chunk in items.chunks(self.batch_size) {
                all.extend(self.embed_chunk(chunk).await?);
            }
            Ok(all)
        })
    }

    fn dim(&self) -> usize {
        self.dim
    }
    fn model_id(&self) -> &str {
        &self.model
    }
}

// ---------------------------------------------------------------------------
// Blake3MediaEmbedClient
// ---------------------------------------------------------------------------

/// Deterministic pseudo-vector for `seed` bytes.
///
/// Identical to [`crate::embed_client::Blake3EmbedClient`]'s text formula, so a
/// text query and a media caption carrying the *same* string produce the *same*
/// vector — the property the offline cross-modal test relies on.
pub fn blake3_pseudo_vector(seed: &[u8], dim: usize) -> Vec<f32> {
    let hash = blake3::hash(seed);
    let bytes = hash.as_bytes();
    (0..dim)
        .map(|i| (bytes[i % 32] as f32 / 127.5) - 1.0)
        .collect()
}

/// Deterministic multimodal client for testing / CI.  No HTTP, no ML.
///
/// Embedding seed precedence: caption (if any) → raw bytes.  This means an
/// image tagged `caption = "red apple"` and the text query `"red apple"` map to
/// the same point in the shared space, so cross-modal retrieval is exercisable
/// without a real encoder.
#[derive(Debug, Clone)]
pub struct Blake3MediaEmbedClient {
    dim: usize,
}

impl Blake3MediaEmbedClient {
    pub fn new(dim: usize) -> Self {
        Self { dim }
    }

    fn vector_for(&self, item: &MediaItem<'_>) -> Vec<f32> {
        match item.caption {
            Some(c) => blake3_pseudo_vector(c.as_bytes(), self.dim),
            None => blake3_pseudo_vector(item.bytes, self.dim),
        }
    }
}

impl MediaEmbedClient for Blake3MediaEmbedClient {
    fn embed_media<'a>(&'a self, items: &'a [MediaItem<'a>]) -> EmbedFuture<'a> {
        Box::pin(async move { Ok(items.iter().map(|it| self.vector_for(it)).collect()) })
    }

    fn dim(&self) -> usize {
        self.dim
    }
    fn model_id(&self) -> &str {
        "blake3-mm-pseudo"
    }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modality_from_mime_classifies() {
        assert_eq!(Modality::from_mime("image/png"), Modality::Image);
        assert_eq!(Modality::from_mime("video/mp4"), Modality::Video);
        assert_eq!(Modality::from_mime("audio/mpeg"), Modality::Audio);
        assert_eq!(Modality::from_mime("application/pdf"), Modality::Document);
        assert_eq!(
            Modality::from_mime("application/epub+zip"),
            Modality::Document
        );
        assert_eq!(Modality::from_mime("text/plain"), Modality::Text);
        // Unknown binary falls back to Document, never dropped.
        assert_eq!(
            Modality::from_mime("application/octet-stream"),
            Modality::Document
        );
    }

    #[tokio::test]
    async fn blake3_media_dim_and_count() {
        let c = Blake3MediaEmbedClient::new(64);
        let items = [
            MediaItem {
                modality: Modality::Image,
                mime: "image/png",
                bytes: &[1, 2, 3],
                caption: Some("a cat"),
            },
            MediaItem::text("a dog"),
        ];
        let v = c.embed_media(&items).await.unwrap();
        assert_eq!(v.len(), 2);
        assert_eq!(v[0].len(), 64);
        assert_eq!(c.dim(), 64);
        assert_eq!(c.model_id(), "blake3-mm-pseudo");
    }

    #[tokio::test]
    async fn caption_drives_cross_modal_alignment() {
        // An image captioned "red apple" and the text query "red apple" must
        // produce identical vectors in the shared space.
        let c = Blake3MediaEmbedClient::new(128);
        let img = [MediaItem {
            modality: Modality::Image,
            mime: "image/jpeg",
            bytes: &[9, 9, 9, 9], // bytes differ from the query string
            caption: Some("red apple"),
        }];
        let txt = [MediaItem::text("red apple")];
        let iv = c.embed_media(&img).await.unwrap();
        let tv = c.embed_media(&txt).await.unwrap();
        assert_eq!(iv[0], tv[0], "caption must bridge image and text");
    }

    #[tokio::test]
    async fn captionless_media_falls_back_to_bytes() {
        let c = Blake3MediaEmbedClient::new(32);
        let a = [MediaItem {
            modality: Modality::Image,
            mime: "image/png",
            bytes: b"AAAA",
            caption: None,
        }];
        let b = [MediaItem {
            modality: Modality::Image,
            mime: "image/png",
            bytes: b"BBBB",
            caption: None,
        }];
        let av = c.embed_media(&a).await.unwrap();
        let bv = c.embed_media(&b).await.unwrap();
        assert_ne!(av[0], bv[0], "different bytes → different vectors");
    }

    #[test]
    fn blake3_pseudo_vector_matches_text_client_formula() {
        // Guard: keep this in lock-step with embed_client::Blake3EmbedClient so
        // the shared space stays shared.
        let v = blake3_pseudo_vector(b"same text", 64);
        let hash = blake3::hash(b"same text");
        let bytes = hash.as_bytes();
        for (i, x) in v.iter().enumerate() {
            assert!((*x - ((bytes[i % 32] as f32 / 127.5) - 1.0)).abs() < 1e-9);
        }
    }

    #[test]
    fn normalize_mm_embed_url_accepts_http_https_root_urls() {
        assert_eq!(
            normalize_mm_embed_url(" http://localhost:8800/ ").unwrap(),
            "http://localhost:8800"
        );
        assert_eq!(
            normalize_mm_embed_url("https://mm-embed.example.com").unwrap(),
            "https://mm-embed.example.com"
        );
    }

    #[test]
    fn normalize_mm_embed_url_rejects_ambiguous_or_header_unsafe_values() {
        for endpoint in [
            "",
            "ftp://localhost:8800",
            "https://user:pass@localhost:8800",
            "http://localhost:8800/api",
            "http://localhost:8800?x=1",
            "http://localhost:8800#frag",
            "http://localhost:8800/\nheader",
            "not a url",
        ] {
            assert!(
                normalize_mm_embed_url(endpoint).is_none(),
                "endpoint should be rejected: {endpoint:?}"
            );
        }
    }

    #[test]
    fn http_media_embed_client_normalizes_endpoint_and_batch_size() {
        let client = HttpMediaEmbedClient::new(" http://localhost:8800/ ", "model", 128, 0);
        assert_eq!(client.base_url, "http://localhost:8800");
        assert_eq!(client.batch_size, 1);
    }

    #[test]
    fn http_media_embed_client_new_disables_invalid_endpoint() {
        let client = HttpMediaEmbedClient::new("http://localhost:8800/api", "model", 128, 1);
        assert_eq!(client.base_url, DISABLED_MM_EMBED_URL);
    }
}
