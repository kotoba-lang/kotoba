//! Rank fusion — combine the lexical (BM25), semantic (IVF/cosine) and
//! authority (PageRank) signals into a single ranking.  This is the piece that
//! makes kotoba search "Google-like": no single signal wins; relevance is the
//! agreement of independent rankers.
//!
//! Two fusers, both keyed on `KotobaCid` (chunk/page identity):
//!
//!   * `reciprocal_rank_fusion` — Reciprocal Rank Fusion (Cormack et al. 2009).
//!     Robust, scale-free: a document's fused score is `Σ_signal w / (k + rank)`.
//!     It only needs the *ordering* each signal produces, not comparable raw
//!     scores — ideal when BM25 (unbounded), cosine (∈[-1,1]) and PageRank
//!     (∈(0,1]) live on wildly different scales.
//!
//!   * `weighted_score_fusion` — min-max-normalise each signal to [0,1], then a
//!     weighted linear blend, optionally multiplied by a per-doc authority
//!     boost.  Use when you trust the raw magnitudes.
//!
//! Pure, deterministic, dependency-free.

use std::collections::HashMap;

use kotoba_core::cid::KotobaCid;

/// One ranker's output: `(doc_cid, score)` pairs.  Order need not be sorted;
/// RRF sorts internally by descending score to derive ranks.
pub type Ranking = Vec<(KotobaCid, f32)>;

/// A named, weighted signal feeding the fusion.
pub struct Signal<'a> {
    pub name: &'a str,
    pub weight: f32,
    pub ranking: &'a Ranking,
}

/// Per-document fused result with a breakdown of contributing signals.
#[derive(Debug, Clone)]
pub struct FusedHit {
    pub cid: KotobaCid,
    pub score: f32,
    /// signal name → that signal's 1-based rank for this doc (if present).
    pub ranks: HashMap<String, usize>,
    /// signal name → that signal's raw score for this doc (if present).
    pub raw: HashMap<String, f32>,
}

/// Default RRF rank-bias constant (Cormack et al. recommend 60).
pub const RRF_K: f32 = 60.0;

/// Reciprocal Rank Fusion.
///
/// For each signal, documents are ranked best-first; a document at 1-based
/// rank `r` contributes `weight / (k + r)` to its fused score.  Returns the
/// top-`top_k` documents, best first.
pub fn reciprocal_rank_fusion(signals: &[Signal<'_>], k: f32, top_k: usize) -> Vec<FusedHit> {
    let mut acc: HashMap<String, FusedHit> = HashMap::new();

    for sig in signals {
        // Sort this signal's ranking best-first (stable by cid on ties).
        let mut ordered: Vec<&(KotobaCid, f32)> = sig.ranking.iter().collect();
        ordered.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.0.to_multibase().cmp(&b.0.to_multibase()))
        });

        for (rank0, (cid, raw)) in ordered.iter().enumerate() {
            let rank = rank0 + 1; // 1-based
            let contrib = sig.weight / (k + rank as f32);
            let mb = cid.to_multibase();
            let hit = acc.entry(mb).or_insert_with(|| FusedHit {
                cid: (*cid).clone(),
                score: 0.0,
                ranks: HashMap::new(),
                raw: HashMap::new(),
            });
            hit.score += contrib;
            hit.ranks.insert(sig.name.to_string(), rank);
            hit.raw.insert(sig.name.to_string(), *raw);
        }
    }

    let mut hits: Vec<FusedHit> = acc.into_values().collect();
    hits.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.cid.to_multibase().cmp(&b.cid.to_multibase()))
    });
    hits.truncate(top_k);
    hits
}

/// Min-max normalise a ranking's scores to `[0, 1]`.
fn min_max(ranking: &Ranking) -> HashMap<String, f32> {
    let mut out = HashMap::new();
    if ranking.is_empty() {
        return out;
    }
    let mut lo = f32::INFINITY;
    let mut hi = f32::NEG_INFINITY;
    for (_, s) in ranking {
        lo = lo.min(*s);
        hi = hi.max(*s);
    }
    let span = (hi - lo).max(1e-9);
    for (cid, s) in ranking {
        out.insert(cid.to_multibase(), (s - lo) / span);
    }
    out
}

/// Weighted linear fusion over min-max-normalised signals, with an optional
/// multiplicative authority boost.
///
/// `authority` maps `doc_cid_multibase → boost ∈ [0,1]` (e.g. PageRank
/// normalised score).  The final score is
/// `(Σ_signal w_s · norm_s(doc)) · (1 + authority_weight · authority(doc))`.
pub fn weighted_score_fusion(
    signals: &[Signal<'_>],
    authority: &HashMap<String, f32>,
    authority_weight: f32,
    top_k: usize,
) -> Vec<FusedHit> {
    let normed: Vec<(&Signal<'_>, HashMap<String, f32>)> =
        signals.iter().map(|s| (s, min_max(s.ranking))).collect();

    // Union of all doc ids across signals.
    let mut all: HashMap<String, KotobaCid> = HashMap::new();
    for sig in signals {
        for (cid, _) in sig.ranking {
            all.entry(cid.to_multibase()).or_insert_with(|| cid.clone());
        }
    }

    let mut hits: Vec<FusedHit> = Vec::with_capacity(all.len());
    for (mb, cid) in all {
        let mut base = 0.0f32;
        let mut raw = HashMap::new();
        for (sig, norm) in &normed {
            if let Some(v) = norm.get(&mb) {
                base += sig.weight * v;
            }
            if let Some((_, r)) = sig.ranking.iter().find(|(c, _)| c.to_multibase() == mb) {
                raw.insert(sig.name.to_string(), *r);
            }
        }
        let boost = 1.0 + authority_weight * authority.get(&mb).copied().unwrap_or(0.0);
        hits.push(FusedHit {
            cid,
            score: base * boost,
            ranks: HashMap::new(),
            raw,
        });
    }

    hits.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.cid.to_multibase().cmp(&b.cid.to_multibase()))
    });
    hits.truncate(top_k);
    hits
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

    #[test]
    fn rrf_agreement_wins() {
        // doc "a" is top in both signals → must rank first after fusion.
        let lex: Ranking = vec![(cid("a"), 9.0), (cid("b"), 5.0), (cid("c"), 1.0)];
        let sem: Ranking = vec![(cid("a"), 0.9), (cid("c"), 0.8), (cid("b"), 0.2)];
        let signals = vec![
            Signal { name: "lex", weight: 1.0, ranking: &lex },
            Signal { name: "sem", weight: 1.0, ranking: &sem },
        ];
        let fused = reciprocal_rank_fusion(&signals, RRF_K, 10);
        assert_eq!(fused[0].cid, cid("a"));
        // "a" recorded a rank from both signals.
        assert_eq!(fused[0].ranks.len(), 2);
    }

    #[test]
    fn rrf_single_signal_preserves_order() {
        let lex: Ranking = vec![(cid("x"), 3.0), (cid("y"), 2.0), (cid("z"), 1.0)];
        let signals = vec![Signal { name: "lex", weight: 1.0, ranking: &lex }];
        let fused = reciprocal_rank_fusion(&signals, RRF_K, 10);
        assert_eq!(fused[0].cid, cid("x"));
        assert_eq!(fused[1].cid, cid("y"));
        assert_eq!(fused[2].cid, cid("z"));
    }

    #[test]
    fn rrf_weight_breaks_ties_toward_heavier_signal() {
        // Two signals disagree on the leader; the heavier signal should win.
        let a_first: Ranking = vec![(cid("a"), 1.0), (cid("b"), 0.5)];
        let b_first: Ranking = vec![(cid("b"), 1.0), (cid("a"), 0.5)];
        let signals = vec![
            Signal { name: "s1", weight: 3.0, ranking: &a_first },
            Signal { name: "s2", weight: 1.0, ranking: &b_first },
        ];
        let fused = reciprocal_rank_fusion(&signals, RRF_K, 10);
        assert_eq!(fused[0].cid, cid("a"), "heavier signal's leader wins");
    }

    #[test]
    fn rrf_top_k_truncates() {
        let r: Ranking = (0..20u8)
            .map(|i| (cid(&format!("d{i}")), (20 - i) as f32))
            .collect();
        let signals = vec![Signal { name: "s", weight: 1.0, ranking: &r }];
        let fused = reciprocal_rank_fusion(&signals, RRF_K, 5);
        assert_eq!(fused.len(), 5);
    }

    #[test]
    fn rrf_empty_signals_empty_result() {
        let fused = reciprocal_rank_fusion(&[], RRF_K, 10);
        assert!(fused.is_empty());
    }

    #[test]
    fn rrf_agreement_beats_single_signal_strength() {
        // THE defining RRF property (sharper than `rrf_agreement_wins`, which uses a
        // doc that is *best* in both signals): a doc at a modest rank in TWO signals
        // must outrank a doc at the very top of only ONE. With k=60:
        //   m: 1/(60+2) + 1/(60+2) = 0.03226   (rank 2 in both)
        //   t: 1/(60+1)            = 0.01639   (rank 1 in one)
        // So agreement, not raw strength, wins.
        let sig1: Ranking = vec![(cid("t"), 9.0), (cid("m"), 5.0)]; // t#1, m#2
        let sig2: Ranking = vec![(cid("u"), 9.0), (cid("m"), 5.0)]; // u#1, m#2
        let signals = vec![
            Signal { name: "s1", weight: 1.0, ranking: &sig1 },
            Signal { name: "s2", weight: 1.0, ranking: &sig2 },
        ];
        let fused = reciprocal_rank_fusion(&signals, RRF_K, 10);
        assert_eq!(fused[0].cid, cid("m"), "doc present in both signals must win");
        assert_eq!(fused[0].ranks.len(), 2, "m contributed from both signals");
        // The single-signal leaders sit below it.
        assert!(fused[1].cid == cid("t") || fused[1].cid == cid("u"));
        assert_eq!(fused[1].ranks.len(), 1);
    }

    #[test]
    fn rrf_score_matches_reciprocal_formula() {
        // Pin the exact contribution w/(k+rank), 1-based — guards against silent
        // drift to 0-based ranks or a k*rank denominator.
        let k = RRF_K;
        let r: Ranking = vec![(cid("first"), 9.0), (cid("second"), 1.0)];
        let signals = vec![Signal { name: "s", weight: 1.0, ranking: &r }];
        let fused = reciprocal_rank_fusion(&signals, k, 10);
        let by = |c: &str| fused.iter().find(|h| h.cid == cid(c)).unwrap().score;
        assert!((by("first") - 1.0 / (k + 1.0)).abs() < 1e-6, "rank-1 score = 1/(k+1)");
        assert!((by("second") - 1.0 / (k + 2.0)).abs() < 1e-6, "rank-2 score = 1/(k+2)");
        // Weight scales the contribution linearly.
        let signals_w = vec![Signal { name: "s", weight: 3.0, ranking: &r }];
        let fused_w = reciprocal_rank_fusion(&signals_w, k, 10);
        let first_w = fused_w.iter().find(|h| h.cid == cid("first")).unwrap().score;
        assert!((first_w - 3.0 / (k + 1.0)).abs() < 1e-6, "weight multiplies the contribution");
    }

    #[test]
    fn weighted_fusion_authority_boost_changes_order() {
        // Without boost, a and b are equally relevant; authority lifts b.
        let lex: Ranking = vec![(cid("a"), 1.0), (cid("b"), 1.0)];
        let signals = vec![Signal { name: "lex", weight: 1.0, ranking: &lex }];
        let mut authority = HashMap::new();
        authority.insert(cid("b").to_multibase(), 1.0);
        authority.insert(cid("a").to_multibase(), 0.0);
        let fused = weighted_score_fusion(&signals, &authority, 2.0, 10);
        assert_eq!(fused[0].cid, cid("b"), "authority boost should lift b");
    }

    #[test]
    fn weighted_fusion_normalizes_scales() {
        // lex on a huge scale, sem on [0,1]; min-max should equalise influence.
        let lex: Ranking = vec![(cid("a"), 1000.0), (cid("b"), 0.0)];
        let sem: Ranking = vec![(cid("b"), 1.0), (cid("a"), 0.0)];
        let signals = vec![
            Signal { name: "lex", weight: 1.0, ranking: &lex },
            Signal { name: "sem", weight: 1.0, ranking: &sem },
        ];
        let fused = weighted_score_fusion(&signals, &HashMap::new(), 0.0, 10);
        // a: lex=1 sem=0 → 1.0 ; b: lex=0 sem=1 → 1.0 ; tie broken by cid.
        assert!((fused[0].score - fused[1].score).abs() < 1e-6);
    }

    #[test]
    fn min_max_handles_constant_scores() {
        let r: Ranking = vec![(cid("a"), 5.0), (cid("b"), 5.0)];
        let m = min_max(&r);
        // No div-by-zero; both map to a finite value.
        assert!(m.values().all(|v| v.is_finite()));
    }
}
