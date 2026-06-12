//! BM25 lexical (keyword) inverted index — pure Rust, no external search engine.
//!
//! This is the *lexical* half of kotoba's hybrid web search: the missing
//! keyword/full-text leg that complements the existing IVF vector (semantic)
//! search.  The two are fused at query time (see `fusion.rs`).
//!
//! Scoring: Okapi BM25 (`k1`, `b` tunable).  IDF uses the standard
//! `ln(1 + (N - df + 0.5)/(df + 0.5))` form, which is always non-negative.
//!
//! Tokenizer: CJK-aware.  ASCII alphanumeric runs become lowercased word
//! tokens; runs of CJK ideographs/kana are emitted as overlapping bigrams
//! (single-char runs as unigrams).  This gives reasonable recall for both
//! English and Japanese Common Crawl text without any external segmenter.
//!
//! Persistence: `to_quads()` / `from_datoms()`, datom-native, living in the
//! same `cc:2026-12:chunks` named graph as the chunk text and IVF centroids.
//! Predicate namespace `{ns}/bm25/*` (default `cc`).  The Datom log remains the
//! canonical state (ADR-2605312345); the index merely materializes it.
//!
//! Predicates:
//!   {ns}/bm25/n         — Integer(N)    document count        (meta subject)
//!   {ns}/bm25/avgdl     — Float(avgdl)  mean document length  (meta subject)
//!   {ns}/bm25/k1        — Float(k1)                            (meta subject)
//!   {ns}/bm25/b         — Float(b)                             (meta subject)
//!   {ns}/bm25/len       — Integer(len)  per-document length    (doc subject)
//!   {ns}/bm25/term      — Text(term)    term string            (term subject)
//!   {ns}/bm25/df        — Integer(df)   document frequency     (term subject)
//!   {ns}/bm25/postings  — Bytes(blob)   packed postings list   (term subject)

use std::collections::HashMap;

use kotoba_core::cid::KotobaCid;
use kotoba_query::datom::{Datom, Value};
use kotoba_query::quad::{LegacyQuad as Quad, LegacyQuadObject as QuadObject};

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------

/// Is `c` a CJK ideograph or Japanese kana that should be bigram-tokenized?
fn is_cjk(c: char) -> bool {
    matches!(c as u32,
        0x3040..=0x309F |   // Hiragana
        0x30A0..=0x30FF |   // Katakana
        0x3400..=0x4DBF |   // CJK Ext A
        0x4E00..=0x9FFF |   // CJK Unified Ideographs
        0xF900..=0xFAFF |   // CJK Compatibility Ideographs
        0x20000..=0x2A6DF) // CJK Ext B
}

/// CJK-aware tokenizer.
///
/// * ASCII alphanumeric runs → one lowercased word token.
/// * CJK runs → overlapping bigrams (a single CJK char → one unigram).
/// * All other characters are separators.
pub fn tokenize(text: &str) -> Vec<String> {
    let mut tokens = Vec::new();
    let mut word = String::new();
    let mut cjk_run: Vec<char> = Vec::new();

    // Flush a pending CJK run into overlapping bigrams (or a unigram).
    macro_rules! flush_cjk {
        () => {
            if !cjk_run.is_empty() {
                if cjk_run.len() == 1 {
                    tokens.push(cjk_run[0].to_string());
                } else {
                    for w in cjk_run.windows(2) {
                        tokens.push(format!("{}{}", w[0], w[1]));
                    }
                }
                cjk_run.clear();
            }
        };
    }
    macro_rules! flush_word {
        () => {
            if !word.is_empty() {
                tokens.push(std::mem::take(&mut word));
            }
        };
    }

    for c in text.chars() {
        if is_cjk(c) {
            flush_word!();
            cjk_run.push(c);
        } else if c.is_ascii_alphanumeric() {
            flush_cjk!();
            word.push(c.to_ascii_lowercase());
        } else {
            // separator
            flush_word!();
            flush_cjk!();
        }
    }
    flush_word!();
    flush_cjk!();

    tokens
}

// ---------------------------------------------------------------------------
// Bm25Index
// ---------------------------------------------------------------------------

const DEFAULT_K1: f64 = 1.2;
const DEFAULT_B: f64 = 0.75;

#[derive(Debug, Clone)]
pub struct Bm25Index {
    /// Document identities, indexed by internal doc id.
    doc_ids: Vec<KotobaCid>,
    /// Token count per document, parallel to `doc_ids`.
    doc_lens: Vec<u32>,
    /// term → postings: list of (doc_id, term_frequency).
    postings: HashMap<String, Vec<(usize, u32)>>,
    avgdl: f64,
    k1: f64,
    b: f64,
}

impl Bm25Index {
    pub fn len(&self) -> usize {
        self.doc_ids.len()
    }
    pub fn is_empty(&self) -> bool {
        self.doc_ids.is_empty()
    }
    pub fn num_terms(&self) -> usize {
        self.postings.len()
    }
    pub fn avgdl(&self) -> f64 {
        self.avgdl
    }

    /// Build a BM25 index from `(subject, text)` documents with default `k1`/`b`.
    pub fn build(docs: &[(KotobaCid, String)]) -> Self {
        Self::build_with(docs, DEFAULT_K1, DEFAULT_B)
    }

    /// Build with explicit BM25 parameters.
    pub fn build_with(docs: &[(KotobaCid, String)], k1: f64, b: f64) -> Self {
        let mut doc_ids = Vec::with_capacity(docs.len());
        let mut doc_lens = Vec::with_capacity(docs.len());
        let mut postings: HashMap<String, Vec<(usize, u32)>> = HashMap::new();
        let mut total_len: u64 = 0;

        for (doc_id, text) in docs {
            let id = doc_ids.len();
            doc_ids.push(doc_id.clone());

            let toks = tokenize(text);
            doc_lens.push(toks.len() as u32);
            total_len += toks.len() as u64;

            // term frequency within this document
            let mut tf: HashMap<&str, u32> = HashMap::new();
            for t in &toks {
                *tf.entry(t.as_str()).or_insert(0) += 1;
            }
            for (term, count) in tf {
                postings
                    .entry(term.to_string())
                    .or_default()
                    .push((id, count));
            }
        }

        let n = doc_ids.len();
        let avgdl = if n == 0 {
            0.0
        } else {
            total_len as f64 / n as f64
        };

        Self {
            doc_ids,
            doc_lens,
            postings,
            avgdl,
            k1,
            b,
        }
    }

    /// IDF for a term given its document frequency.  Always ≥ 0.
    fn idf(&self, df: usize) -> f64 {
        let n = self.doc_ids.len() as f64;
        (1.0 + (n - df as f64 + 0.5) / (df as f64 + 0.5)).ln()
    }

    /// BM25 search.  Returns up to `top_k` `(score, doc_id_index)` pairs, best
    /// first.  Documents with a zero score (no query term present) are omitted.
    pub fn search(&self, query: &str, top_k: usize) -> Vec<(f32, usize)> {
        if self.doc_ids.is_empty() || top_k == 0 {
            return Vec::new();
        }
        let mut q_terms = tokenize(query);
        q_terms.sort();
        q_terms.dedup();

        let mut scores: HashMap<usize, f64> = HashMap::new();
        for term in &q_terms {
            let Some(plist) = self.postings.get(term) else {
                continue;
            };
            let idf = self.idf(plist.len());
            if idf <= 0.0 {
                continue;
            }
            for &(doc_id, tf) in plist {
                let dl = self.doc_lens[doc_id] as f64;
                let denom =
                    tf as f64 + self.k1 * (1.0 - self.b + self.b * dl / self.avgdl.max(1e-9));
                let contrib = idf * (tf as f64 * (self.k1 + 1.0)) / denom.max(1e-9);
                *scores.entry(doc_id).or_insert(0.0) += contrib;
            }
        }

        let mut ranked: Vec<(f32, usize)> =
            scores.into_iter().map(|(d, s)| (s as f32, d)).collect();
        ranked.sort_by(|a, b| {
            b.0.partial_cmp(&a.0)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.1.cmp(&b.1)) // stable tie-break by doc id
        });
        ranked.truncate(top_k);
        ranked
    }

    /// Convenience: search returning `(score, doc CID)` pairs.
    pub fn search_cids(&self, query: &str, top_k: usize) -> Vec<(f32, KotobaCid)> {
        self.search(query, top_k)
            .into_iter()
            .filter_map(|(s, idx)| self.doc_ids.get(idx).map(|c| (s, c.clone())))
            .collect()
    }

    // -----------------------------------------------------------------------
    // Persistence
    // -----------------------------------------------------------------------

    pub fn to_quads(&self, graph_cid: &KotobaCid) -> Vec<Quad> {
        self.to_quads_ns(graph_cid, "cc")
    }

    /// Serialise into quads under the `{ns}/bm25/*` predicate namespace.
    pub fn to_quads_ns(&self, graph_cid: &KotobaCid, ns: &str) -> Vec<Quad> {
        let mut quads = Vec::new();

        // ── meta ──
        let meta = KotobaCid::from_bytes(b"bm25-meta");
        quads.push(Quad {
            graph: graph_cid.clone(),
            subject: meta.clone(),
            predicate: format!("{ns}/bm25/n"),
            object: QuadObject::Integer(self.doc_ids.len() as i64),
        });
        quads.push(Quad {
            graph: graph_cid.clone(),
            subject: meta.clone(),
            predicate: format!("{ns}/bm25/avgdl"),
            object: QuadObject::Float(self.avgdl),
        });
        quads.push(Quad {
            graph: graph_cid.clone(),
            subject: meta.clone(),
            predicate: format!("{ns}/bm25/k1"),
            object: QuadObject::Float(self.k1),
        });
        quads.push(Quad {
            graph: graph_cid.clone(),
            subject: meta.clone(),
            predicate: format!("{ns}/bm25/b"),
            object: QuadObject::Float(self.b),
        });

        // ── per-document lengths ──
        for (id, doc) in self.doc_ids.iter().enumerate() {
            quads.push(Quad {
                graph: graph_cid.clone(),
                subject: doc.clone(),
                predicate: format!("{ns}/bm25/len"),
                object: QuadObject::Integer(self.doc_lens[id] as i64),
            });
        }

        // ── per-term df + packed postings ──
        for (term, plist) in &self.postings {
            let subject = term_subject(term);
            quads.push(Quad {
                graph: graph_cid.clone(),
                subject: subject.clone(),
                predicate: format!("{ns}/bm25/term"),
                object: QuadObject::Text(term.clone()),
            });
            quads.push(Quad {
                graph: graph_cid.clone(),
                subject: subject.clone(),
                predicate: format!("{ns}/bm25/df"),
                object: QuadObject::Integer(plist.len() as i64),
            });
            // Postings reference docs by CID multibase (order-independent restore).
            let blob = pack_postings(plist, &self.doc_ids);
            quads.push(Quad {
                graph: graph_cid.clone(),
                subject,
                predicate: format!("{ns}/bm25/postings"),
                object: QuadObject::Bytes(blob),
            });
        }

        quads
    }

    /// Restore from Datomic atomic facts.  Namespace-agnostic (`*/bm25/*`).
    pub fn from_datoms(datoms: &[Datom]) -> Option<Self> {
        // doc CID multibase → internal id, plus length lookup.
        let mut doc_len_by_cid: HashMap<String, (KotobaCid, u32)> = HashMap::new();
        let mut term_postings: HashMap<String, Vec<(String, u32)>> = HashMap::new();
        let mut avgdl = 0.0f64;
        let mut k1 = DEFAULT_K1;
        let mut b = DEFAULT_B;
        let mut n_meta: Option<usize> = None;

        for d in datoms.iter().filter(|d| d.op) {
            match bm25_leaf(&d.a) {
                Some("n") => {
                    if let Value::Integer(v) = &d.v {
                        n_meta = Some(*v as usize);
                    }
                }
                Some("avgdl") => {
                    if let Value::Float(v) = &d.v {
                        avgdl = *v;
                    }
                }
                Some("k1") => {
                    if let Value::Float(v) = &d.v {
                        k1 = *v;
                    }
                }
                Some("b") => {
                    if let Value::Float(v) = &d.v {
                        b = *v;
                    }
                }
                Some("len") => {
                    if let Value::Integer(v) = &d.v {
                        doc_len_by_cid.insert(d.e.to_multibase(), (d.e.clone(), *v as u32));
                    }
                }
                Some("postings") => {
                    if let Value::Bytes(blob) = &d.v {
                        // term resolved later from the matching `term` datom on
                        // the same subject; key the raw blob by subject for now.
                        term_postings.insert(format!("@subj:{}", d.e.to_multibase()), {
                            // Decode immediately; term name attached below.
                            unpack_postings(blob)
                        });
                    }
                }
                _ => {}
            }
        }

        // Second pass: map term-subject → term string, attach postings.
        let mut subj_to_term: HashMap<String, String> = HashMap::new();
        for d in datoms.iter().filter(|d| d.op) {
            if bm25_leaf(&d.a) == Some("term") {
                if let Value::Text(t) = &d.v {
                    subj_to_term.insert(d.e.to_multibase(), t.clone());
                }
            }
        }

        if doc_len_by_cid.is_empty() {
            return None;
        }

        // Assign stable internal ids to docs (sorted by multibase for determinism).
        let mut docs: Vec<(String, KotobaCid, u32)> = doc_len_by_cid
            .into_iter()
            .map(|(mb, (cid, len))| (mb, cid, len))
            .collect();
        docs.sort_by(|a, b| a.0.cmp(&b.0));
        let mut id_of: HashMap<String, usize> = HashMap::new();
        let mut doc_ids = Vec::with_capacity(docs.len());
        let mut doc_lens = Vec::with_capacity(docs.len());
        for (mb, cid, len) in &docs {
            id_of.insert(mb.clone(), doc_ids.len());
            doc_ids.push(cid.clone());
            doc_lens.push(*len);
        }

        // Build postings keyed by real term name.
        let mut postings: HashMap<String, Vec<(usize, u32)>> = HashMap::new();
        for (subj_key, decoded) in term_postings {
            let subj_mb = subj_key.trim_start_matches("@subj:");
            let Some(term) = subj_to_term.get(subj_mb) else {
                continue;
            };
            let plist: Vec<(usize, u32)> = decoded
                .into_iter()
                .filter_map(|(doc_mb, tf)| id_of.get(&doc_mb).map(|&id| (id, tf)))
                .collect();
            if !plist.is_empty() {
                postings.insert(term.clone(), plist);
            }
        }

        if avgdl <= 0.0 {
            let total: u64 = doc_lens.iter().map(|&l| l as u64).sum();
            avgdl = if doc_ids.is_empty() {
                0.0
            } else {
                total as f64 / doc_ids.len() as f64
            };
        }
        let _ = n_meta; // informational; doc count derives from len datoms

        Some(Self {
            doc_ids,
            doc_lens,
            postings,
            avgdl,
            k1,
            b,
        })
    }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Stable synthetic subject CID for a term's posting cluster.
fn term_subject(term: &str) -> KotobaCid {
    KotobaCid::from_bytes(format!("bm25-term:{term}").as_bytes())
}

/// Extract the trailing leaf of a `{ns}/bm25/<leaf>` predicate.
fn bm25_leaf(pred: &str) -> Option<&str> {
    pred.split("/bm25/").nth(1)
}

/// Pack a posting list into bytes: `u32 count` then repeated
/// `[u16 cid_len][cid_multibase bytes][u32 tf]` (little-endian).
fn pack_postings(plist: &[(usize, u32)], doc_ids: &[KotobaCid]) -> Vec<u8> {
    let mut out = Vec::with_capacity(plist.len() * 24 + 4);
    out.extend_from_slice(&(plist.len() as u32).to_le_bytes());
    for &(doc_id, tf) in plist {
        let mb = doc_ids[doc_id].to_multibase();
        let bytes = mb.as_bytes();
        out.extend_from_slice(&(bytes.len() as u16).to_le_bytes());
        out.extend_from_slice(bytes);
        out.extend_from_slice(&tf.to_le_bytes());
    }
    out
}

/// Inverse of [`pack_postings`].  Returns `(doc_multibase, tf)` entries.
fn unpack_postings(blob: &[u8]) -> Vec<(String, u32)> {
    let mut out = Vec::new();
    if blob.len() < 4 {
        return out;
    }
    let count = u32::from_le_bytes([blob[0], blob[1], blob[2], blob[3]]) as usize;
    let mut off = 4;
    for _ in 0..count {
        if off + 2 > blob.len() {
            break;
        }
        let len = u16::from_le_bytes([blob[off], blob[off + 1]]) as usize;
        off += 2;
        if off + len + 4 > blob.len() {
            break;
        }
        let mb = String::from_utf8_lossy(&blob[off..off + len]).into_owned();
        off += len;
        let tf = u32::from_le_bytes([blob[off], blob[off + 1], blob[off + 2], blob[off + 3]]);
        off += 4;
        out.push((mb, tf));
    }
    out
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    fn cid(s: &str) -> KotobaCid {
        KotobaCid::from_bytes(s.as_bytes())
    }

    fn corpus() -> Vec<(KotobaCid, String)> {
        vec![
            (
                cid("d0"),
                "the quick brown fox jumps over the lazy dog".into(),
            ),
            (cid("d1"), "a fast brown fox leaps".into()),
            (cid("d2"), "lazy dogs sleep all day in the sun".into()),
            (cid("d3"), "quantum computing and machine learning".into()),
        ]
    }

    #[test]
    fn tokenize_latin_lowercases_and_splits() {
        let t = tokenize("Hello, World! foo-bar  baz123");
        assert_eq!(t, vec!["hello", "world", "foo", "bar", "baz123"]);
    }

    #[test]
    fn tokenize_cjk_bigrams() {
        // 4 ideographs → 3 overlapping bigrams.
        let t = tokenize("東京都庁");
        assert_eq!(t, vec!["東京", "京都", "都庁"]);
    }

    #[test]
    fn tokenize_single_cjk_unigram() {
        assert_eq!(tokenize("猫"), vec!["猫"]);
    }

    #[test]
    fn tokenize_mixed_latin_cjk() {
        let t = tokenize("Rust製のkotoba");
        // "rust" word, then 製 (unigram, isolated by 'の'? no — 製の are adjacent CJK)
        // 製の → bigram "製の"; then "kotoba"
        assert_eq!(t, vec!["rust", "製の", "kotoba"]);
    }

    #[test]
    fn build_basic_stats() {
        let idx = Bm25Index::build(&corpus());
        assert_eq!(idx.len(), 4);
        assert!(idx.avgdl() > 0.0);
        assert!(idx.num_terms() > 0);
    }

    #[test]
    fn search_relevant_doc_ranks_first() {
        let idx = Bm25Index::build(&corpus());
        let r = idx.search("quantum machine learning", 5);
        assert!(!r.is_empty());
        // d3 is the only doc with these terms.
        assert_eq!(r[0].1, 3);
    }

    #[test]
    fn search_fox_matches_two_docs() {
        let idx = Bm25Index::build(&corpus());
        let r = idx.search("brown fox", 10);
        let hit_docs: std::collections::HashSet<usize> = r.iter().map(|(_, d)| *d).collect();
        assert!(hit_docs.contains(&0));
        assert!(hit_docs.contains(&1));
        assert!(!hit_docs.contains(&3), "d3 has no fox");
    }

    #[test]
    fn search_descending_and_top_k() {
        let idx = Bm25Index::build(&corpus());
        let r = idx.search("the lazy dog", 2);
        assert!(r.len() <= 2);
        for w in r.windows(2) {
            assert!(w[0].0 >= w[1].0, "scores must be non-increasing");
        }
    }

    #[test]
    fn search_no_match_empty() {
        let idx = Bm25Index::build(&corpus());
        assert!(idx.search("zzz_nonexistent_term", 5).is_empty());
    }

    #[test]
    fn search_empty_index() {
        let idx = Bm25Index::build(&[]);
        assert!(idx.search("anything", 5).is_empty());
    }

    #[test]
    fn search_cids_returns_correct_cid() {
        let idx = Bm25Index::build(&corpus());
        let r = idx.search_cids("quantum", 1);
        assert_eq!(r.len(), 1);
        assert_eq!(r[0].1, cid("d3"));
    }

    #[test]
    fn rare_term_outscores_common_term() {
        // "quantum" (df=1) should give a higher idf-weighted score than "the" (df=many).
        let idx = Bm25Index::build(&corpus());
        let rare = idx.search("quantum", 1)[0].0;
        let common = idx.search("the", 1)[0].0;
        assert!(
            rare > common,
            "rare term {rare} should outscore common {common}"
        );
    }

    #[test]
    fn quad_roundtrip_via_datoms() {
        let idx = Bm25Index::build(&corpus());
        let graph = cid("g");
        let quads = idx.to_quads(&graph);
        let datoms: Vec<Datom> = quads
            .into_iter()
            .map(|q| Datom::from_legacy_quad(q, true))
            .collect();
        let restored = Bm25Index::from_datoms(&datoms).expect("restore");

        assert_eq!(restored.len(), idx.len());
        assert_eq!(restored.num_terms(), idx.num_terms());
        assert!((restored.avgdl() - idx.avgdl()).abs() < 1e-9);

        // Same query → same top doc CID after round-trip.
        let a = idx.search_cids("quantum machine learning", 1);
        let b = restored.search_cids("quantum machine learning", 1);
        assert_eq!(a[0].1, b[0].1);
    }

    #[test]
    fn pack_unpack_postings_roundtrip() {
        let docs = vec![cid("alpha"), cid("beta"), cid("gamma")];
        let plist = vec![(0usize, 3u32), (2, 1)];
        let blob = pack_postings(&plist, &docs);
        let back = unpack_postings(&blob);
        assert_eq!(back.len(), 2);
        assert_eq!(back[0], (docs[0].to_multibase(), 3));
        assert_eq!(back[1], (docs[2].to_multibase(), 1));
    }

    #[test]
    fn unpack_truncated_blob_is_safe() {
        // Claims 5 postings but provides none — must not panic.
        let mut blob = 5u32.to_le_bytes().to_vec();
        blob.truncate(4);
        let back = unpack_postings(&blob);
        assert!(back.is_empty());
    }

    #[test]
    fn from_datoms_empty_returns_none() {
        assert!(Bm25Index::from_datoms(&[]).is_none());
    }

    #[test]
    fn idf_is_non_negative() {
        let idx = Bm25Index::build(&corpus());
        // Even a term in every doc must have idf >= 0.
        assert!(idx.idf(idx.len()) >= 0.0);
        assert!(idx.idf(1) > idx.idf(idx.len()));
    }

    #[test]
    fn bm25_term_frequency_saturates() {
        // THE property distinguishing BM25 from linear TF-IDF: term-frequency
        // contribution saturates via k1. Two equal-length docs, same term, one with
        // 10 occurrences and one with 1 — the 10× doc ranks higher but by FAR less
        // than 10× (with defaults the ratio is ≈1.96). A linear-TF bug would yield ~10×.
        let docs = vec![
            (cid("many"), "x x x x x x x x x x".into()), // tf=10, len 10
            (cid("one"), "x a b c d e f g h i".into()),  // tf=1,  len 10 (same length)
        ];
        let idx = Bm25Index::build(&docs);
        let r = idx.search("x", 10);
        let s_many = r.iter().find(|(_, d)| *d == 0).unwrap().0;
        let s_one = r.iter().find(|(_, d)| *d == 1).unwrap().0;
        assert!(s_many > s_one, "more occurrences must rank higher");
        assert!(
            s_many < 2.5 * s_one,
            "TF must saturate: 10× frequency gave {}×, expected strongly sublinear",
            s_many / s_one
        );
    }

    #[test]
    fn bm25_length_normalization_penalizes_longer_docs() {
        // The `b` parameter: with identical term frequency (1), a SHORT document
        // outranks a LONG one — a single match means more in a terse doc. A bug that
        // dropped length normalization (b=0 behaviour) would tie them.
        let docs = vec![
            (cid("short"), "x a".into()),                // tf=1, len 2
            (cid("long"), "x a b c d e f g h i".into()), // tf=1, len 10
        ];
        let idx = Bm25Index::build(&docs);
        let r = idx.search("x", 10);
        let s_short = r.iter().find(|(_, d)| *d == 0).unwrap().0;
        let s_long = r.iter().find(|(_, d)| *d == 1).unwrap().0;
        assert!(
            s_short > s_long,
            "same TF, shorter doc must score higher (length normalization): short={s_short}, long={s_long}"
        );
    }
}
