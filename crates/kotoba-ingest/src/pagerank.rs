//! PageRank link-authority index — pure Rust power iteration, no graph DB.
//!
//! This is the *authority* signal of kotoba's hybrid web search: it ranks
//! pages by the recursive importance of the pages that link to them, the same
//! intuition behind Google's original PageRank.  Lexical (BM25) and semantic
//! (IVF) scores say "is this page *about* the query"; PageRank says "is this
//! page *trusted*".  The three are fused at query time (see `fusion.rs`).
//!
//! Data source: the link graph.  Edges are `(src_page_cid, dst_page_cid)`
//! pairs — in Common Crawl terms, the outlinks of a page.  PageRank is run over
//! whatever edges live in the `cc:2026-12:links` named graph; when that graph
//! is unpopulated the hybrid ranker simply falls back to a uniform authority
//! prior (documented honestly — full outlink extraction from the CC parquet
//! schema is a separate ingestion increment).
//!
//! Persistence: `to_quads()` / `from_datoms()`, datom-native.  Scores live as
//! `{ns}/rank/score` Float facts keyed by the page subject CID; the Datom log
//! stays canonical (ADR-2605312345).
//!
//! Predicates:
//!   {ns}/rank/score    — Float(score)   per-page PageRank ∈ (0,1], Σ = 1
//!   {ns}/rank/damping  — Float(d)        damping factor      (meta subject)
//!   {ns}/rank/n        — Integer(N)      node count          (meta subject)

use std::collections::HashMap;

use kotoba_core::cid::KotobaCid;
use kotoba_kqe::datom::{Datom, Value};
use kotoba_kqe::quad::{LegacyQuad as Quad, LegacyQuadObject as QuadObject};

// ---------------------------------------------------------------------------
// Core algorithm (index-based, dependency-free)
// ---------------------------------------------------------------------------

#[derive(Debug, Clone, Copy)]
pub struct PageRankConfig {
    pub damping: f64,
    pub max_iter: usize,
    /// L1 convergence tolerance: stop early when Σ|Δ| < tol.
    pub tol: f64,
}

impl Default for PageRankConfig {
    fn default() -> Self {
        Self {
            damping: 0.85,
            max_iter: 100,
            tol: 1e-8,
        }
    }
}

/// Power-iteration PageRank over a 0-based node id space.
///
/// `edges` are directed `(src, dst)` links.  Dangling nodes (no outlinks) have
/// their rank mass redistributed uniformly, so the result is a proper
/// probability distribution (`Σ = 1`).  Nodes are 0..`num_nodes`.
pub fn pagerank(num_nodes: usize, edges: &[(usize, usize)], cfg: PageRankConfig) -> Vec<f64> {
    if num_nodes == 0 {
        return Vec::new();
    }
    let n = num_nodes;
    let base = 1.0 / n as f64;

    // out-adjacency + out-degree
    let mut out_adj: Vec<Vec<usize>> = vec![Vec::new(); n];
    let mut out_deg: Vec<usize> = vec![0; n];
    for &(s, d) in edges {
        if s < n && d < n {
            out_adj[s].push(d);
            out_deg[s] += 1;
        }
    }

    let mut rank = vec![base; n];
    let d = cfg.damping;

    for _ in 0..cfg.max_iter {
        let mut next = vec![(1.0 - d) / n as f64; n];

        // Dangling mass: rank of nodes with no outlinks, spread uniformly.
        let dangling: f64 = (0..n)
            .filter(|&i| out_deg[i] == 0)
            .map(|i| rank[i])
            .sum();
        let dangling_share = d * dangling / n as f64;
        for v in next.iter_mut() {
            *v += dangling_share;
        }

        // Distribute each node's mass to its out-neighbours.
        for u in 0..n {
            if out_deg[u] == 0 {
                continue;
            }
            let share = d * rank[u] / out_deg[u] as f64;
            for &v in &out_adj[u] {
                next[v] += share;
            }
        }

        // Convergence check (L1).
        let delta: f64 = rank.iter().zip(next.iter()).map(|(a, b)| (a - b).abs()).sum();
        rank = next;
        if delta < cfg.tol {
            break;
        }
    }

    rank
}

// ---------------------------------------------------------------------------
// CID-keyed index
// ---------------------------------------------------------------------------

#[derive(Debug, Clone)]
pub struct PageRankIndex {
    /// page CID multibase → (CID, score)
    scores: HashMap<String, (KotobaCid, f64)>,
    damping: f64,
}

impl PageRankIndex {
    pub fn len(&self) -> usize {
        self.scores.len()
    }
    pub fn is_empty(&self) -> bool {
        self.scores.is_empty()
    }
    pub fn damping(&self) -> f64 {
        self.damping
    }

    /// PageRank score for a page, or `None` if the page is not in the graph.
    pub fn score(&self, cid: &KotobaCid) -> Option<f64> {
        self.scores.get(&cid.to_multibase()).map(|(_, s)| *s)
    }

    /// Score normalised to `[0, 1]` by the index maximum (handy as a fusion
    /// boost factor).  Returns 0.0 for unknown pages.
    pub fn normalized_score(&self, cid: &KotobaCid) -> f64 {
        let max = self
            .scores
            .values()
            .map(|(_, s)| *s)
            .fold(0.0f64, f64::max);
        if max <= 0.0 {
            return 0.0;
        }
        self.score(cid).unwrap_or(0.0) / max
    }

    /// Top-`n` pages by score, best first.
    pub fn top(&self, n: usize) -> Vec<(KotobaCid, f64)> {
        let mut v: Vec<(KotobaCid, f64)> =
            self.scores.values().map(|(c, s)| (c.clone(), *s)).collect();
        v.sort_by(|a, b| {
            b.1.partial_cmp(&a.1)
                .unwrap_or(std::cmp::Ordering::Equal)
                .then(a.0.to_multibase().cmp(&b.0.to_multibase()))
        });
        v.truncate(n);
        v
    }

    /// Compute PageRank from CID-keyed directed edges with default config.
    pub fn compute(edges: &[(KotobaCid, KotobaCid)]) -> Self {
        Self::compute_with(edges, PageRankConfig::default())
    }

    /// Compute with explicit configuration.
    pub fn compute_with(edges: &[(KotobaCid, KotobaCid)], cfg: PageRankConfig) -> Self {
        // Assign dense ids to every node that appears as a src or dst.
        let mut id_of: HashMap<String, usize> = HashMap::new();
        let mut cids: Vec<KotobaCid> = Vec::new();
        let mut idx_edges: Vec<(usize, usize)> = Vec::with_capacity(edges.len());

        let intern = |cid: &KotobaCid,
                          id_of: &mut HashMap<String, usize>,
                          cids: &mut Vec<KotobaCid>|
         -> usize {
            let mb = cid.to_multibase();
            if let Some(&id) = id_of.get(&mb) {
                id
            } else {
                let id = cids.len();
                id_of.insert(mb, id);
                cids.push(cid.clone());
                id
            }
        };

        for (s, d) in edges {
            let si = intern(s, &mut id_of, &mut cids);
            let di = intern(d, &mut id_of, &mut cids);
            idx_edges.push((si, di));
        }

        let ranks = pagerank(cids.len(), &idx_edges, cfg);
        let mut scores = HashMap::with_capacity(cids.len());
        for (i, cid) in cids.into_iter().enumerate() {
            scores.insert(cid.to_multibase(), (cid, ranks[i]));
        }

        Self {
            scores,
            damping: cfg.damping,
        }
    }

    // -----------------------------------------------------------------------
    // Persistence
    // -----------------------------------------------------------------------

    pub fn to_quads(&self, graph_cid: &KotobaCid) -> Vec<Quad> {
        self.to_quads_ns(graph_cid, "cc")
    }

    pub fn to_quads_ns(&self, graph_cid: &KotobaCid, ns: &str) -> Vec<Quad> {
        let mut quads = Vec::with_capacity(self.scores.len() + 2);

        let meta = KotobaCid::from_bytes(b"pagerank-meta");
        quads.push(Quad {
            graph: graph_cid.clone(),
            subject: meta.clone(),
            predicate: format!("{ns}/rank/damping"),
            object: QuadObject::Float(self.damping),
        });
        quads.push(Quad {
            graph: graph_cid.clone(),
            subject: meta,
            predicate: format!("{ns}/rank/n"),
            object: QuadObject::Integer(self.scores.len() as i64),
        });

        for (cid, score) in self.scores.values() {
            quads.push(Quad {
                graph: graph_cid.clone(),
                subject: cid.clone(),
                predicate: format!("{ns}/rank/score"),
                object: QuadObject::Float(*score),
            });
        }
        quads
    }

    /// Restore from Datomic atomic facts.  Namespace-agnostic (`*/rank/*`).
    pub fn from_datoms(datoms: &[Datom]) -> Option<Self> {
        let mut scores: HashMap<String, (KotobaCid, f64)> = HashMap::new();
        let mut damping = 0.85;

        for d in datoms.iter().filter(|d| d.op) {
            match rank_leaf(&d.a) {
                Some("score") => {
                    if let Value::Float(s) = &d.v {
                        scores.insert(d.e.to_multibase(), (d.e.clone(), *s));
                    }
                }
                Some("damping") => {
                    if let Value::Float(v) = &d.v {
                        damping = *v;
                    }
                }
                _ => {}
            }
        }

        if scores.is_empty() {
            return None;
        }
        Some(Self { scores, damping })
    }
}

/// Extract the trailing leaf of a `{ns}/rank/<leaf>` predicate.
fn rank_leaf(pred: &str) -> Option<&str> {
    pred.split("/rank/").nth(1)
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
    fn empty_graph() {
        assert!(pagerank(0, &[], PageRankConfig::default()).is_empty());
    }

    #[test]
    fn ranks_sum_to_one() {
        // 4-node graph with assorted edges.
        let edges = [(0usize, 1usize), (0, 2), (1, 2), (2, 0), (3, 2)];
        let r = pagerank(4, &edges, PageRankConfig::default());
        let sum: f64 = r.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6, "ranks must sum to 1, got {sum}");
    }

    #[test]
    fn hub_outranks_leaves_in_star() {
        // Star: nodes 1,2,3 all link to hub 0; hub links nowhere (dangling).
        let edges = [(1usize, 0usize), (2, 0), (3, 0)];
        let r = pagerank(4, &edges, PageRankConfig::default());
        // Hub (0) should have the highest rank.
        let hub = r[0];
        for leaf in &r[1..] {
            assert!(hub > *leaf, "hub {hub} should outrank leaf {leaf}");
        }
    }

    #[test]
    fn symmetric_cycle_is_uniform() {
        // 3-cycle: every node has in-deg = out-deg = 1 → uniform PageRank.
        let edges = [(0usize, 1usize), (1, 2), (2, 0)];
        let r = pagerank(3, &edges, PageRankConfig::default());
        for w in r.windows(2) {
            assert!((w[0] - w[1]).abs() < 1e-6, "cycle should be uniform");
        }
    }

    #[test]
    fn dangling_node_does_not_lose_mass() {
        // node 0 → 1, node 1 dangling. Mass must stay conserved (Σ=1).
        let edges = [(0usize, 1usize)];
        let r = pagerank(2, &edges, PageRankConfig::default());
        let sum: f64 = r.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6);
    }

    #[test]
    fn no_edges_is_uniform() {
        let r = pagerank(5, &[], PageRankConfig::default());
        let sum: f64 = r.iter().sum();
        assert!((sum - 1.0).abs() < 1e-6);
        for w in r.windows(2) {
            assert!((w[0] - w[1]).abs() < 1e-9, "no edges → uniform");
        }
    }

    #[test]
    fn cid_index_compute_and_score() {
        let edges = vec![
            (cid("b"), cid("a")),
            (cid("c"), cid("a")),
            (cid("d"), cid("a")),
            (cid("a"), cid("b")),
        ];
        let idx = PageRankIndex::compute(&edges);
        assert_eq!(idx.len(), 4);
        // `a` is pointed to by 3 nodes → highest authority.
        let top = idx.top(1);
        assert_eq!(top[0].0, cid("a"));
        assert!(idx.score(&cid("a")).unwrap() > idx.score(&cid("c")).unwrap());
    }

    #[test]
    fn normalized_score_max_is_one() {
        let edges = vec![(cid("x"), cid("y")), (cid("z"), cid("y"))];
        let idx = PageRankIndex::compute(&edges);
        // y has the max score → normalized 1.0.
        assert!((idx.normalized_score(&cid("y")) - 1.0).abs() < 1e-9);
        // unknown page → 0.0
        assert_eq!(idx.normalized_score(&cid("unknown")), 0.0);
    }

    #[test]
    fn quad_roundtrip_via_datoms() {
        let edges = vec![
            (cid("p2"), cid("p1")),
            (cid("p3"), cid("p1")),
            (cid("p1"), cid("p2")),
        ];
        let idx = PageRankIndex::compute(&edges);
        let graph = cid("g");
        let quads = idx.to_quads(&graph);
        let datoms: Vec<Datom> = quads
            .into_iter()
            .map(|q| Datom::from_legacy_quad(q, true))
            .collect();
        let restored = PageRankIndex::from_datoms(&datoms).expect("restore");
        assert_eq!(restored.len(), idx.len());
        for (cid, (_, s)) in &idx.scores {
            let back = restored
                .scores
                .get(cid)
                .expect("missing restored score")
                .1;
            assert!((back - s).abs() < 1e-9);
        }
    }

    #[test]
    fn from_datoms_empty_returns_none() {
        assert!(PageRankIndex::from_datoms(&[]).is_none());
    }

    #[test]
    fn converges_before_max_iter() {
        // tiny tol but converging graph — must not NaN or diverge.
        let edges = [(0usize, 1usize), (1, 0)];
        let cfg = PageRankConfig {
            damping: 0.85,
            max_iter: 1000,
            tol: 1e-12,
        };
        let r = pagerank(2, &edges, cfg);
        assert!(r.iter().all(|x| x.is_finite()));
        assert!((r[0] - r[1]).abs() < 1e-6, "symmetric 2-cycle uniform");
    }
}
