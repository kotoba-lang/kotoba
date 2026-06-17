//! # Declared replication — the pin contract (ADR-001 phase 4 / GROWTH p4)
//!
//! Availability becomes a *declared responsibility*: each graph carries a
//! [`ReplicationPolicy`] ("how many replicas, which pinners, what bond floor")
//! that the DHT tier enforces, instead of single-holder-by-default. This is the
//! integration anchor the ADR-002 stake-to-replicate membrane plugs into —
//! `min_bond_mkoto` lives here and feeds `eligible_replica`.
//!
//! [`audit_replication`] is the pure status surface (the `node.status`
//! availability block, ADR-001 p4 / ADR-002 p3): given an observation of how
//! many replicas exist and who holds the block, it reports whether the contract
//! is met and what is missing.

use crate::node_id::NodeId;
use kotoba_core::cid::KotobaCid;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

fn one() -> usize {
    1
}

/// Per-graph declared replication policy — the pin contract.
///
/// Defaults are today's open, single-node behaviour (`min_replicas = 1`, no
/// declared pinners, `min_bond_mkoto = 0`), and every field is `#[serde(default)]`
/// so policies written before a field existed still decode.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationPolicy {
    /// Minimum confirmed replicas before a durable write is satisfied (the local
    /// copy counts as one). `1` = local-only durability acceptable.
    #[serde(default = "one")]
    pub min_replicas: usize,
    /// Nodes explicitly contracted to pin this graph, beyond XOR proximity. A
    /// pin_peer absent from the holder set makes the contract unsatisfied even
    /// when `min_replicas` is otherwise met.
    #[serde(default)]
    pub pin_peers: Vec<NodeId>,
    /// ADR-002 stake-to-replicate: the minimum bond (mKOTO) a replica must post
    /// to be admitted to this graph's neighbourhood. `0` = open (default).
    #[serde(default)]
    pub min_bond_mkoto: i64,
}

impl Default for ReplicationPolicy {
    fn default() -> Self {
        Self {
            min_replicas: 1,
            pin_peers: Vec::new(),
            min_bond_mkoto: 0,
        }
    }
}

impl ReplicationPolicy {
    /// A policy with a replica floor (clamped to ≥ 1), open bond, no pinners.
    pub fn new(min_replicas: usize) -> Self {
        Self {
            min_replicas: min_replicas.max(1),
            ..Default::default()
        }
    }

    pub fn with_pin_peers(mut self, peers: Vec<NodeId>) -> Self {
        self.pin_peers = peers;
        self
    }

    pub fn with_min_bond(mut self, mkoto: i64) -> Self {
        self.min_bond_mkoto = mkoto;
        self
    }
}

/// Audit of a graph's replication against its pin contract — the `node.status`
/// availability surface. Produced by [`audit_replication`].
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ReplicationStatus {
    pub min_replicas: usize,
    pub observed_replicas: usize,
    /// Declared `pin_peers` not currently among the holders.
    pub missing_pin_peers: Vec<NodeId>,
    /// `min_replicas - observed_replicas`, floored at 0 (0 = replica floor met).
    pub under_replicated_by: usize,
    /// `true` iff the floor is met **and** every declared pin_peer holds it.
    pub satisfied: bool,
}

/// Pure contract audit: compare an observation (replica count + the set of
/// `holders` currently confirmed to hold the block) against `policy`. The bond
/// floor is not checked here — admission is enforced upstream by the membrane;
/// this surface reports *delivered availability*.
pub fn audit_replication(
    policy: &ReplicationPolicy,
    observed_replicas: usize,
    holders: &[NodeId],
) -> ReplicationStatus {
    let held: std::collections::HashSet<&NodeId> = holders.iter().collect();
    let missing_pin_peers: Vec<NodeId> = policy
        .pin_peers
        .iter()
        .filter(|p| !held.contains(p))
        .cloned()
        .collect();
    let under_replicated_by = policy.min_replicas.saturating_sub(observed_replicas);
    let satisfied = under_replicated_by == 0 && missing_pin_peers.is_empty();
    ReplicationStatus {
        min_replicas: policy.min_replicas,
        observed_replicas,
        missing_pin_peers,
        under_replicated_by,
        satisfied,
    }
}

/// Enforcement decision (ADR-001 p4): given an audit `status`, the current
/// `holders`, and admission-ordered `candidates` (e.g. from
/// [`crate::membrane::select_replicas`] — already bond-gated and
/// reputation-ranked), return the prioritised set of peers to **push the block
/// to** so the pin contract is met. Priority:
///
/// 1. every missing declared `pin_peer` (contractual — must hold it), then
/// 2. enough additional fresh candidates (in their given order) to close the
///    remaining replica shortfall.
///
/// Targets are deduped and never include a current holder. Empty when the
/// contract is already satisfied. Pure: the actual push is the caller's
/// `NeighborhoodBlockStore::replicate`.
pub fn replication_plan(
    status: &ReplicationStatus,
    holders: &[NodeId],
    candidates: &[NodeId],
) -> Vec<NodeId> {
    if status.satisfied {
        return Vec::new();
    }
    let held: std::collections::HashSet<&NodeId> = holders.iter().collect();
    let mut targets: Vec<NodeId> = Vec::new();
    let mut chosen: std::collections::HashSet<NodeId> = std::collections::HashSet::new();

    // 1. contracted pin_peers that are missing — always pushed.
    for p in &status.missing_pin_peers {
        if !held.contains(p) && chosen.insert(p.clone()) {
            targets.push(p.clone());
        }
    }

    // 2. close the remaining replica shortfall with fresh candidates. Each pin
    //    peer added above also becomes a replica, so it counts toward the floor.
    let mut still_needed = status.under_replicated_by.saturating_sub(targets.len());
    for c in candidates {
        if still_needed == 0 {
            break;
        }
        if held.contains(c) || chosen.contains(c) {
            continue;
        }
        chosen.insert(c.clone());
        targets.push(c.clone());
        still_needed -= 1;
    }
    targets
}

/// Per-graph replication policies with a node-wide default fallback (GROWTH p4
/// "per-graph policy store"). A graph that has not declared its own pin contract
/// inherits the node default, so callers can always resolve a policy with
/// [`policy_for`](Self::policy_for) without special-casing absence.
#[derive(Debug, Clone, Default)]
pub struct ReplicationPolicyStore {
    default: ReplicationPolicy,
    per_graph: HashMap<KotobaCid, ReplicationPolicy>,
}

impl ReplicationPolicyStore {
    /// A store whose unset graphs resolve to `default`.
    pub fn new(default: ReplicationPolicy) -> Self {
        Self {
            default,
            per_graph: HashMap::new(),
        }
    }

    /// The node-wide default contract.
    pub fn default_policy(&self) -> &ReplicationPolicy {
        &self.default
    }

    /// Declare (or replace) a graph's own pin contract.
    pub fn set(&mut self, graph: KotobaCid, policy: ReplicationPolicy) {
        self.per_graph.insert(graph, policy);
    }

    /// Drop a graph's override; it reverts to the default. Returns the removed
    /// policy if one was set.
    pub fn remove(&mut self, graph: &KotobaCid) -> Option<ReplicationPolicy> {
        self.per_graph.remove(graph)
    }

    /// `true` if `graph` has its own declared contract (not just the default).
    pub fn has_override(&self, graph: &KotobaCid) -> bool {
        self.per_graph.contains_key(graph)
    }

    /// The effective policy for `graph`: its own override if declared, else the
    /// node default. Always resolves.
    pub fn policy_for(&self, graph: &KotobaCid) -> &ReplicationPolicy {
        self.per_graph.get(graph).unwrap_or(&self.default)
    }

    /// Number of graphs with an explicit override.
    pub fn override_count(&self) -> usize {
        self.per_graph.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn nid(tag: &[u8]) -> NodeId {
        NodeId::from_pubkey(tag)
    }

    #[test]
    fn default_is_open_single_node() {
        let p = ReplicationPolicy::default();
        assert_eq!(p.min_replicas, 1);
        assert!(p.pin_peers.is_empty());
        assert_eq!(p.min_bond_mkoto, 0);
    }

    #[test]
    fn new_clamps_min_replicas_to_one() {
        assert_eq!(ReplicationPolicy::new(0).min_replicas, 1);
        assert_eq!(ReplicationPolicy::new(3).min_replicas, 3);
    }

    #[test]
    fn policy_serde_roundtrip_and_backward_compat() {
        let p = ReplicationPolicy::new(3)
            .with_pin_peers(vec![nid(b"pinner")])
            .with_min_bond(5_000);
        let json = serde_json::to_string(&p).unwrap();
        assert_eq!(serde_json::from_str::<ReplicationPolicy>(&json).unwrap(), p);
        // a legacy policy serialized before any field existed still decodes.
        let legacy: ReplicationPolicy = serde_json::from_str("{}").unwrap();
        assert_eq!(legacy, ReplicationPolicy::default());
        // a policy with only min_replicas decodes with field defaults.
        let partial: ReplicationPolicy = serde_json::from_str(r#"{"min_replicas":2}"#).unwrap();
        assert_eq!(partial, ReplicationPolicy::new(2));
    }

    #[test]
    fn audit_satisfied_when_floor_met_and_no_pinners() {
        let policy = ReplicationPolicy::new(2);
        let holders = vec![nid(b"a"), nid(b"b")];
        let st = audit_replication(&policy, 2, &holders);
        assert!(st.satisfied);
        assert_eq!(st.under_replicated_by, 0);
        assert!(st.missing_pin_peers.is_empty());
    }

    #[test]
    fn audit_under_replicated_reports_shortfall() {
        let policy = ReplicationPolicy::new(3);
        let st = audit_replication(&policy, 1, &[nid(b"a")]);
        assert!(!st.satisfied);
        assert_eq!(st.under_replicated_by, 2);
    }

    #[test]
    fn audit_unsatisfied_when_declared_pinner_missing() {
        // floor met, but a contracted pin_peer is not holding it → unsatisfied.
        let pinner = nid(b"contracted");
        let policy = ReplicationPolicy::new(2).with_pin_peers(vec![pinner.clone()]);
        let holders = vec![nid(b"a"), nid(b"b")]; // pinner absent
        let st = audit_replication(&policy, 2, &holders);
        assert_eq!(st.under_replicated_by, 0, "floor is met");
        assert!(!st.satisfied, "but a declared pinner is missing");
        assert_eq!(st.missing_pin_peers, vec![pinner]);
    }

    #[test]
    fn audit_satisfied_when_pinner_present() {
        let pinner = nid(b"contracted");
        let policy = ReplicationPolicy::new(2).with_pin_peers(vec![pinner.clone()]);
        let holders = vec![nid(b"a"), pinner];
        let st = audit_replication(&policy, 2, &holders);
        assert!(st.satisfied);
        assert!(st.missing_pin_peers.is_empty());
    }

    // ── replication_plan — the enforcement decision (ADR-001 p4) ───────────

    #[test]
    fn plan_is_empty_when_contract_satisfied() {
        let policy = ReplicationPolicy::new(2);
        let holders = vec![nid(b"a"), nid(b"b")];
        let st = audit_replication(&policy, 2, &holders);
        assert!(replication_plan(&st, &holders, &[nid(b"c"), nid(b"d")]).is_empty());
    }

    #[test]
    fn plan_fills_shortfall_from_candidates_skipping_holders() {
        // need 3, have 1 (a). candidates b,c,d (a is a holder, must be skipped).
        let policy = ReplicationPolicy::new(3);
        let holders = vec![nid(b"a")];
        let st = audit_replication(&policy, 1, &holders);
        assert_eq!(st.under_replicated_by, 2);
        let plan = replication_plan(&st, &holders, &[nid(b"a"), nid(b"b"), nid(b"c"), nid(b"d")]);
        assert_eq!(plan, vec![nid(b"b"), nid(b"c")], "two fresh candidates, in order");
    }

    #[test]
    fn plan_pushes_missing_pinners_first_then_counts_them_toward_floor() {
        // need 3, have 1 (a). a contracted pin_peer P is missing.
        // P must be pushed (contractual) AND it counts toward the floor, so only
        // 1 more candidate is needed after P → [P, b].
        let pinner = nid(b"P");
        let policy = ReplicationPolicy::new(3).with_pin_peers(vec![pinner.clone()]);
        let holders = vec![nid(b"a")];
        let st = audit_replication(&policy, 1, &holders);
        assert_eq!(st.under_replicated_by, 2);
        assert_eq!(st.missing_pin_peers, vec![pinner.clone()]);
        let plan = replication_plan(&st, &holders, &[nid(b"b"), nid(b"c")]);
        assert_eq!(plan, vec![pinner, nid(b"b")]);
    }

    #[test]
    fn plan_pushes_pinner_even_when_floor_otherwise_met() {
        // floor met (2/2) but contracted pinner missing → push just the pinner.
        let pinner = nid(b"P");
        let policy = ReplicationPolicy::new(2).with_pin_peers(vec![pinner.clone()]);
        let holders = vec![nid(b"a"), nid(b"b")];
        let st = audit_replication(&policy, 2, &holders);
        assert!(!st.satisfied);
        let plan = replication_plan(&st, &holders, &[nid(b"c")]);
        assert_eq!(plan, vec![pinner], "only the missing pinner; no extra replicas");
    }

    #[test]
    fn plan_stops_when_candidates_exhausted() {
        // need 3, have 0, only one candidate available → plan is best-effort.
        let policy = ReplicationPolicy::new(3);
        let st = audit_replication(&policy, 0, &[]);
        let plan = replication_plan(&st, &[], &[nid(b"only")]);
        assert_eq!(plan, vec![nid(b"only")]);
    }

    // ── ReplicationPolicyStore — per-graph policies + default (GROWTH p4) ───

    fn gcid(seed: &str) -> KotobaCid {
        KotobaCid::from_bytes(seed.as_bytes())
    }

    #[test]
    fn store_falls_back_to_default_for_unknown_graph() {
        let store = ReplicationPolicyStore::new(ReplicationPolicy::new(2));
        // an undeclared graph resolves to the default — always resolvable.
        assert_eq!(store.policy_for(&gcid("graphX")).min_replicas, 2);
        assert!(!store.has_override(&gcid("graphX")));
        assert_eq!(store.override_count(), 0);
    }

    #[test]
    fn store_override_takes_precedence_over_default() {
        let mut store = ReplicationPolicyStore::new(ReplicationPolicy::new(1));
        let g = gcid("hot-graph");
        store.set(g.clone(), ReplicationPolicy::new(5).with_min_bond(9_000));
        let p = store.policy_for(&g);
        assert_eq!(p.min_replicas, 5);
        assert_eq!(p.min_bond_mkoto, 9_000);
        assert!(store.has_override(&g));
        assert_eq!(store.override_count(), 1);
        // a different graph still gets the default.
        assert_eq!(store.policy_for(&gcid("cold-graph")).min_replicas, 1);
    }

    #[test]
    fn store_remove_reverts_to_default() {
        let mut store = ReplicationPolicyStore::new(ReplicationPolicy::new(1));
        let g = gcid("g");
        store.set(g.clone(), ReplicationPolicy::new(4));
        assert_eq!(store.policy_for(&g).min_replicas, 4);
        let removed = store.remove(&g).expect("override existed");
        assert_eq!(removed.min_replicas, 4);
        assert_eq!(store.policy_for(&g).min_replicas, 1, "reverts to default");
        assert!(store.remove(&g).is_none(), "second remove is a no-op");
    }
}
