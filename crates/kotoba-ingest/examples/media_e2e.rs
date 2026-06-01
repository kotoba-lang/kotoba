//! End-to-end cross-modal search demo.
//!
//! Run:
//!   cargo run --release --example media_e2e -p kotoba-ingest
//!
//! Demonstrates the multimodal pipeline with NO external encoder and NO server:
//!   1. Ingest a mixed corpus (images, a video, an audio clip, book pages)
//!      into a content-addressed Vault + the `media:2026:assets` Datom graph.
//!   2. Embed everything into ONE shared vector space.
//!   3. Run TEXT queries that retrieve the matching asset *regardless of its
//!      modality* — the core property of Google-style multimodal search.
//!
//! The deterministic `Blake3MediaEmbedClient` bridges a query string to any
//! asset carrying the same caption, so the demo is reproducible offline.  In
//! production you point `KOTOBA_MM_EMBED_URL` at a CLIP / SigLIP / ImageBind
//! encoder and the exact same code path performs real semantic retrieval.

use std::sync::Arc;

use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_graph::quad_store::QuadStore;
use kotoba_ingest::media::{rank_by_cosine, MediaIngestor, MediaInput};
use kotoba_ingest::media_embed::{Blake3MediaEmbedClient, MediaEmbedClient, MediaItem};
use kotoba_kqe::datom::Value;
use kotoba_kse::Journal;
use kotoba_kse::Vault;
use kotoba_store::MemoryBlockStore;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let dim = 256;

    // ── Wiring: in-memory store + Vault + deterministic shared-space encoder ──
    let journal = Arc::new(Journal::new());
    let block_store =
        Arc::new(MemoryBlockStore::new()) as Arc<dyn kotoba_core::store::BlockStore + Send + Sync>;
    let quad_store = Arc::new(QuadStore::new(journal, block_store));
    let vault = Arc::new(Vault::new());
    let embed: Arc<dyn MediaEmbedClient> = Arc::new(Blake3MediaEmbedClient::new(dim));

    let ingestor =
        MediaIngestor::new(quad_store, vault, Arc::clone(&embed)).with_k(6);

    // ── A small mixed-modality corpus ────────────────────────────────────────
    // Bytes are placeholder payloads; captions stand in for what a real encoder
    // would extract (image labels / ASR transcripts / OCR'd book pages).
    let corpus = vec![
        MediaInput::new("image/jpeg", Bytes::from_static(b"\xff\xd8...apple-pixels"))
            .with_title("apple.jpg")
            .with_caption("a red apple on a wooden table"),
        MediaInput::new("image/png", Bytes::from_static(b"\x89PNG...car-pixels"))
            .with_title("car.png")
            .with_caption("a blue sports car on a mountain road"),
        MediaInput::new("video/mp4", Bytes::from_static(b"\x00\x00...ocean-frames"))
            .with_title("beach.mp4")
            .with_caption("waves crashing on a sandy beach at sunset"),
        MediaInput::new("audio/mpeg", Bytes::from_static(b"ID3...piano-samples"))
            .with_title("sonata.mp3")
            .with_caption("a solo piano playing a slow classical sonata"),
        MediaInput::new("application/pdf", Bytes::from_static(b"%PDF...page-3"))
            .with_title("cookbook.pdf")
            .with_page(3)
            .with_caption("recipe for an apple pie with cinnamon"),
        MediaInput::new("application/epub+zip", Bytes::from_static(b"PK...chapter-1"))
            .with_title("novel.epub")
            .with_page(1)
            .with_caption("the sailor returned home from the sea"),
    ];

    // `ingest_items_datoms` stores each blob in the Vault and returns the
    // projected `media/*` Datoms (the same set `ingest_items` would commit).
    // We rank directly over them, which is exactly what the `media.search`
    // XRPC handler does after reading the graph back server-side.
    let (report, datoms) = ingestor.ingest_items_datoms(corpus).await?;
    println!("== ingest ==");
    println!(
        "  assets={}  embeddings={}  ivf_k={}  graph={}",
        report.assets, report.embeddings, report.ivf_k, report.graph_cid
    );
    println!("  model={}\n", report.model_id);

    let embeddings: Vec<(KotobaCid, Vec<f32>)> = datoms
        .iter()
        .filter(|d| d.op && d.a.starts_with("media/embed/"))
        .filter_map(|d| match &d.v {
            Value::VectorF32(v) => Some((d.e.clone(), v.clone())),
            _ => None,
        })
        .collect();
    println!("== index == {} asset vectors in the shared space\n", embeddings.len());

    let title_of = |subject: &KotobaCid| -> String {
        datoms
            .iter()
            .find(|d| d.e == *subject && d.a == "media/title")
            .and_then(|d| match &d.v {
                Value::Text(t) => Some(t.clone()),
                _ => None,
            })
            .unwrap_or_else(|| subject.to_multibase())
    };
    let modality_of = |subject: &KotobaCid| -> String {
        datoms
            .iter()
            .find(|d| d.e == *subject && d.a == "media/modality")
            .and_then(|d| match &d.v {
                Value::Text(t) => Some(t.clone()),
                _ => None,
            })
            .unwrap_or_default()
    };

    // ── Cross-modal text → any-modality retrieval ────────────────────────────
    let queries = [
        "a red apple on a wooden table",                // → image
        "waves crashing on a sandy beach at sunset",    // → video
        "a solo piano playing a slow classical sonata", // → audio
        "recipe for an apple pie with cinnamon",        // → document (PDF page)
    ];

    for q in queries {
        let qv = embed.embed_media(&[MediaItem::text(q)]).await?;
        let ranked = rank_by_cosine(&qv[0], &embeddings, 3);
        println!("query: {q:?}");
        for (rank, (score, idx)) in ranked.iter().enumerate() {
            let subj = &embeddings[*idx].0;
            println!(
                "  {}. [{:>8}] {:<14} score={:.4}",
                rank + 1,
                modality_of(subj),
                title_of(subj),
                score
            );
        }
        println!();
    }

    println!("Done. A text query retrieved image / video / audio / document assets");
    println!("from a single shared embedding space — no per-modality silos.");
    Ok(())
}
