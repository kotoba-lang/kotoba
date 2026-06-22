//! Leader-less reconcile + auction logic (ADR §6.1 / §7).
//!
//! These are **pure deterministic functions**. Any number of reconcilers
//! observing the same desired state (manifest datoms) and the same observed
//! state (heartbeats) compute the same actions and pick the same auction
//! winners — so the lattice converges with no leader election.

use std::collections::BTreeMap;

use crate::protocol::{Auction, Bid, Constraints, Heartbeat};

/// A single placement adjustment for one component artifact.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NeedAction {
    pub cid: String,
    /// `> 0` → start that many; `< 0` → stop |delta|. Never `0`.
    pub delta: i64,
}

/// Count observed instances per component CID from the latest heartbeats.
/// `hosted` entries on each heartbeat are tallied across the fleet.
pub fn observed_counts(heartbeats: &[Heartbeat]) -> BTreeMap<String, u32> {
    let mut counts: BTreeMap<String, u32> = BTreeMap::new();
    for hb in heartbeats {
        for cid in &hb.hosted {
            *counts.entry(cid.clone()).or_insert(0) += 1;
        }
    }
    counts
}

/// Compute the reconcile delta: desired (cid → want) vs observed (cid → have).
/// Returns one [`NeedAction`] per component whose count is off, sorted by CID
/// for deterministic ordering across reconcilers.
pub fn need_actions(
    desired: &BTreeMap<String, u32>,
    observed: &BTreeMap<String, u32>,
) -> Vec<NeedAction> {
    let mut out = Vec::new();
    // scale-up / scale-down for desired components
    for (cid, want) in desired {
        let have = observed.get(cid).copied().unwrap_or(0);
        let delta = *want as i64 - have as i64;
        if delta != 0 {
            out.push(NeedAction {
                cid: cid.clone(),
                delta,
            });
        }
    }
    // components running but no longer desired → scale to zero
    for (cid, have) in observed {
        if !desired.contains_key(cid) && *have > 0 {
            out.push(NeedAction {
                cid: cid.clone(),
                delta: -(*have as i64),
            });
        }
    }
    out.sort_by(|a, b| a.cid.cmp(&b.cid));
    out
}

/// Score a node's eligibility+fitness to host a component under `constraints`.
/// Returns `None` if the node cannot host it (label or capability mismatch).
/// Otherwise returns the bid score (higher = better): free capacity, lightly
/// penalised by current load and latency. Deterministic given the heartbeat.
pub fn score_bid(hb: &Heartbeat, constraints: &Constraints) -> Option<u64> {
    // must supply every required capability
    for cap in &constraints.requires_caps {
        if !hb.caps.iter().any(|c| c == cap) {
            return None;
        }
    }
    // must match every required label exactly
    for (k, v) in &constraints.require_labels {
        match hb.labels.get(k) {
            Some(got) if got == v => {}
            _ => return None,
        }
    }
    // score: free_gas dominates; spread by penalising existing load; small
    // latency penalty. Saturating so it never panics.
    let load_penalty = (hb.hosted.len() as u64).saturating_mul(50_000);
    let lat_penalty = hb.lat_ms as u64;
    Some(
        hb.free_gas
            .saturating_sub(load_penalty)
            .saturating_sub(lat_penalty),
    )
}

/// Pick the winning node DIDs for an auction from the collected bids.
/// Sort by score descending, then `node_did` ascending (deterministic
/// tie-break), and take the top `auction.n`. Every reconciler that sees the
/// same bid set returns the same winners — no leader needed.
pub fn award_winners(auction: &Auction, bids: &[Bid]) -> Vec<String> {
    let mut eligible: Vec<&Bid> = bids
        .iter()
        .filter(|b| b.auction_id == auction.id)
        .collect();
    eligible.sort_by(|a, b| {
        b.score
            .cmp(&a.score)
            .then_with(|| a.node_did.cmp(&b.node_did))
    });
    eligible
        .into_iter()
        .take(auction.n as usize)
        .map(|b| b.node_did.clone())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::NodeRole;

    fn hb(did: &str, caps: &[&str], free_gas: u64, hosted: &[&str]) -> Heartbeat {
        Heartbeat {
            node_did: did.into(),
            roles: vec![NodeRole::Compute],
            labels: BTreeMap::new(),
            caps: caps.iter().map(|s| s.to_string()).collect(),
            free_gas,
            hosted: hosted.iter().map(|s| s.to_string()).collect(),
            lat_ms: 0,
        }
    }

    #[test]
    fn observed_counts_tallies_fleet() {
        let fleet = vec![
            hb("n1", &[], 0, &["A", "B"]),
            hb("n2", &[], 0, &["A"]),
        ];
        let c = observed_counts(&fleet);
        assert_eq!(c.get("A"), Some(&2));
        assert_eq!(c.get("B"), Some(&1));
    }

    #[test]
    fn need_actions_scale_up_down_and_undeploy() {
        let desired = BTreeMap::from([("A".to_string(), 3u32), ("B".to_string(), 1)]);
        let observed = BTreeMap::from([("A".to_string(), 1u32), ("C".to_string(), 2)]);
        let acts = need_actions(&desired, &observed);
        // A: +2, B: +1, C: -2  (sorted by cid)
        assert_eq!(
            acts,
            vec![
                NeedAction { cid: "A".into(), delta: 2 },
                NeedAction { cid: "B".into(), delta: 1 },
                NeedAction { cid: "C".into(), delta: -2 },
            ]
        );
    }

    #[test]
    fn need_actions_empty_when_converged() {
        let desired = BTreeMap::from([("A".to_string(), 2u32)]);
        let observed = BTreeMap::from([("A".to_string(), 2u32)]);
        assert!(need_actions(&desired, &observed).is_empty());
    }

    #[test]
    fn score_bid_rejects_missing_cap() {
        let c = Constraints {
            require_labels: BTreeMap::new(),
            requires_caps: vec!["cap/llm".into()],
        };
        assert!(score_bid(&hb("n1", &["cap/kqe"], 100, &[]), &c).is_none());
        assert!(score_bid(&hb("n1", &["cap/kqe", "cap/llm"], 100, &[]), &c).is_some());
    }

    #[test]
    fn score_bid_rejects_label_mismatch() {
        let mut h = hb("n1", &["cap/kqe"], 100, &[]);
        h.labels.insert("zone".into(), "us".into());
        let c = Constraints {
            require_labels: BTreeMap::from([("zone".into(), "jp".into())]),
            requires_caps: vec![],
        };
        assert!(score_bid(&h, &c).is_none());
        h.labels.insert("zone".into(), "jp".into());
        assert!(score_bid(&h, &c).is_some());
    }

    #[test]
    fn score_bid_prefers_free_capacity_and_low_load() {
        let c = Constraints::default();
        let busy = score_bid(&hb("n1", &[], 1_000_000, &["X", "Y"]), &c).unwrap();
        let idle = score_bid(&hb("n2", &[], 1_000_000, &[]), &c).unwrap();
        assert!(idle > busy, "idle node should outscore busy node");
    }

    #[test]
    fn award_is_deterministic_with_tiebreak() {
        let auction = Auction {
            id: "auc-1".into(),
            cid: "A".into(),
            n: 2,
            constraints: Constraints::default(),
        };
        let bids = vec![
            Bid { auction_id: "auc-1".into(), node_did: "nB".into(), score: 100 },
            Bid { auction_id: "auc-1".into(), node_did: "nA".into(), score: 100 },
            Bid { auction_id: "auc-1".into(), node_did: "nC".into(), score: 50 },
            // wrong auction — must be ignored
            Bid { auction_id: "auc-2".into(), node_did: "nZ".into(), score: 999 },
        ];
        // tie at 100 → nA before nB; take top 2
        assert_eq!(award_winners(&auction, &bids), vec!["nA", "nB"]);
        // recompute → identical (leader-less convergence)
        assert_eq!(award_winners(&auction, &bids), award_winners(&auction, &bids));
    }
}
