//! # Replica-admission membrane (ADR-002 — stake-to-replicate, phase 2)
//!
//! Wires the bond-gated [`eligible_replica`] predicate (kotoba-query, phase 1)
//! into the DHT neighbourhood: a CID's replica candidate set is filtered to
//! **bonded** DIDs *before* XOR k-nearest decides placement. Proximity still
//! chooses *where* a replica lands; the membrane chooses *who is allowed in the
//! pool*. A fresh-keypair Sybil with no observed `Pinned` bond is simply not a
//! candidate.
//!
//! Per the ADR this is **default off** (`KOTOBA_STAKE_TO_REPLICATE`) until the
//! declared-replication integration test (p4) is green. With the membrane off,
//! [`bonded_candidates`] is byte-for-byte the open neighbourhood of today.
//!
//! kotoba stays read+verify: eligibility is a pure function over already-observed
//! `mishmar/pin/*` Datoms — no chain access happens here.

use crate::neighborhood::K;
use crate::node_id::NodeId;
use crate::replication::ReplicationPolicy;
use crate::reputation::prefer_by_reputation;
use kotoba_core::cid::KotobaCid;
use kotoba_query::social::{eligible_replica, PinIndex};

/// A peer offered for replica selection: its DHT node id, the DID whose bond
/// gates its admission, and its current reputation (social capital, higher =
/// preferred). Reputation is preference only — it never admits.
pub type ReplicaCandidate = (NodeId, KotobaCid, u64);

/// End-to-end replica selection for a graph `root` (ADR-002, the single entry
/// point the server calls). Composes the three ledgers in order:
///
/// 1. **admission** — bond-gated: only DIDs that are `eligible_replica` for
///    `root` under `policy.min_bond_mkoto` survive (skipped when the membrane is
///    off, leaving today's open neighbourhood);
/// 2. **placement** — XOR proximity to `cid_address(root)` picks the `K`
///    responsible cells from the admitted pool;
/// 3. **preference** — reputation reorders that `K`-set (highest first), with
///    proximity preserved as the tie-breaker (stable sort).
///
/// Returns the ordered replica set (closest-preferred first). Admission is bond;
/// reputation can only reorder what bond already let in — it never widens the
/// set, which the `reputation_never_admits_a_non_eligible_node` property pins.
pub fn select_replicas(
    root: &KotobaCid,
    address: &NodeId,
    peers: &[ReplicaCandidate],
    policy: &ReplicationPolicy,
    pins: &PinIndex,
    membrane_on: bool,
) -> Vec<NodeId> {
    // 1+2: admission (bond) then XOR-proximity K-set.
    let nd: Vec<(NodeId, KotobaCid)> =
        peers.iter().map(|(n, d, _)| (n.clone(), d.clone())).collect();
    let bonded = bonded_candidates(address, &nd, root, policy.min_bond_mkoto, pins, K, membrane_on);
    // 3: reorder the admitted K-set by reputation (proximity = stable tie-break).
    let rep: std::collections::HashMap<&NodeId, u64> =
        peers.iter().map(|(n, _, r)| (n, *r)).collect();
    let ranked: Vec<(NodeId, u64)> = bonded
        .iter()
        .map(|n| (n.clone(), rep.get(n).copied().unwrap_or(0)))
        .collect();
    prefer_by_reputation(&ranked, bonded.len())
}

/// Env gate for the stake-to-replicate membrane (ADR-002 p2). Default **off**:
/// only `1`/`true`/`on`/`yes` (case-insensitive) enable it. Read this once at the
/// call site and thread the bool into [`bonded_candidates`] so the selection
/// itself stays pure and testable.
pub fn stake_to_replicate_enabled() -> bool {
    std::env::var("KOTOBA_STAKE_TO_REPLICATE")
        .map(|v| matches!(v.trim().to_ascii_lowercase().as_str(), "1" | "true" | "on" | "yes"))
        .unwrap_or(false)
}

/// The replica candidate set for `root`, as `NodeId`s, closest-first by XOR
/// distance to `address` (= `cid_address(root)`), capped at `k`.
///
/// `peers` carries each candidate's `(NodeId, DID)` — the DID is needed to look
/// up its bond in `pins`. When `membrane_on` is false the DID is ignored and the
/// result is exactly `k_nearest` over all peers (today's behaviour). When true,
/// only peers for which `eligible_replica(did, root, min_bond_mkoto, pins)` holds
/// enter the pool before k-nearest.
///
/// `min_bond_mkoto == 0` keeps the neighbourhood open even with the membrane on
/// (every pinner of `root` qualifies); a positive floor excludes unbonded /
/// under-bonded DIDs.
pub fn bonded_candidates(
    address: &NodeId,
    peers: &[(NodeId, KotobaCid)],
    root: &KotobaCid,
    min_bond_mkoto: i64,
    pins: &PinIndex,
    k: usize,
    membrane_on: bool,
) -> Vec<NodeId> {
    let pool: Vec<NodeId> = peers
        .iter()
        .filter(|(_, did)| !membrane_on || eligible_replica(did, root, min_bond_mkoto, pins))
        .map(|(node, _)| node.clone())
        .collect();
    NodeId::k_nearest(address, &pool, k)
        .into_iter()
        .cloned()
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_query::datom::{Datom, Value};
    use kotoba_query::delta::Delta;

    fn did(seed: &str) -> KotobaCid {
        KotobaCid::from_bytes(seed.as_bytes())
    }

    fn nid(tag: &[u8]) -> NodeId {
        NodeId::from_pubkey(tag)
    }

    /// Project one bonded pin (pinner DID on root with bond) into a PinIndex.
    fn bonded_pin(idx: &mut PinIndex, pin: &str, pinner: &KotobaCid, root: &KotobaCid, bond: i64) {
        let p = did(pin);
        let g = did("g");
        idx.apply(&[
            Delta::assert_datom(Datom::assert(
                p.clone(),
                "mishmar/pin/pinner".into(),
                Value::Cid(pinner.clone()),
                g.clone(),
            )),
            Delta::assert_datom(Datom::assert(
                p.clone(),
                "mishmar/pin/root".into(),
                Value::Cid(root.clone()),
                g.clone(),
            )),
            Delta::assert_datom(Datom::assert(
                p,
                "mishmar/pin/bond".into(),
                Value::Integer(bond),
                g,
            )),
        ]);
    }

    #[test]
    fn membrane_off_is_plain_k_nearest() {
        let root = did("rootA");
        let addr = nid(b"rootA-addr");
        let peers: Vec<(NodeId, KotobaCid)> =
            (0..10u8).map(|i| (nid(&[i; 4]), did(&format!("did{i}")))).collect();
        // empty PinIndex + high floor: with the membrane ON nobody qualifies...
        let pins = PinIndex::new();
        assert!(bonded_candidates(&addr, &peers, &root, 5_000, &pins, 7, true).is_empty());
        // ...but OFF, it is exactly k_nearest over all peers.
        let got = bonded_candidates(&addr, &peers, &root, 5_000, &pins, 7, false);
        let want: Vec<NodeId> = {
            let all: Vec<NodeId> = peers.iter().map(|(n, _)| n.clone()).collect();
            NodeId::k_nearest(&addr, &all, 7).into_iter().cloned().collect()
        };
        assert_eq!(got, want);
        assert_eq!(got.len(), 7);
    }

    #[test]
    fn membrane_on_admits_only_bonded_peers() {
        let root = did("rootA");
        let addr = nid(b"rootA-addr");
        let peggy_did = did("did:key:peggy");
        let mallory_did = did("did:key:mallory");
        let peggy_node = nid(b"peggy-node");
        let mallory_node = nid(b"mallory-node");
        let peers = vec![
            (peggy_node.clone(), peggy_did.clone()),
            (mallory_node.clone(), mallory_did.clone()),
        ];
        let mut pins = PinIndex::new();
        bonded_pin(&mut pins, "pinP", &peggy_did, &root, 5_000);
        // peggy is bonded to floor, mallory is not bonded at all.
        let got = bonded_candidates(&addr, &peers, &root, 5_000, &pins, 7, true);
        assert_eq!(got, vec![peggy_node]);
        // raising the floor above peggy's bond empties the pool.
        assert!(bonded_candidates(&addr, &peers, &root, 5_001, &pins, 7, true).is_empty());
    }

    #[test]
    fn membrane_on_zero_floor_is_open() {
        // min_bond == 0 ⇒ any pinner of root qualifies even unbonded.
        let root = did("rootA");
        let addr = nid(b"rootA-addr");
        let did_a = did("did:key:a");
        let node_a = nid(b"node-a");
        let mut pins = PinIndex::new();
        // pinner+root only, no bond Datom.
        let g = did("g");
        let p = did("pinA");
        pins.apply(&[
            Delta::assert_datom(Datom::assert(
                p.clone(),
                "mishmar/pin/pinner".into(),
                Value::Cid(did_a.clone()),
                g.clone(),
            )),
            Delta::assert_datom(Datom::assert(
                p,
                "mishmar/pin/root".into(),
                Value::Cid(root.clone()),
                g,
            )),
        ]);
        let peers = vec![(node_a.clone(), did_a)];
        assert_eq!(
            bonded_candidates(&addr, &peers, &root, 0, &pins, 7, true),
            vec![node_a]
        );
    }

    #[test]
    fn bonded_pool_still_capped_and_sorted_by_distance() {
        // 12 bonded peers, k=4: result is the 4 closest, ascending distance.
        let root = did("rootA");
        let addr = nid(b"rootA-addr");
        let mut pins = PinIndex::new();
        let mut peers = Vec::new();
        for i in 0..12u8 {
            let d = did(&format!("did{i}"));
            bonded_pin(&mut pins, &format!("pin{i}"), &d, &root, 5_000);
            peers.push((nid(&[i; 8]), d));
        }
        let got = bonded_candidates(&addr, &peers, &root, 5_000, &pins, 4, true);
        assert_eq!(got.len(), 4);
        for w in got.windows(2) {
            assert!(
                addr.xor_distance(&w[0]) <= addr.xor_distance(&w[1]),
                "bonded candidates must stay XOR-sorted"
            );
        }
        // SELECTION correctness: no excluded bonded peer is closer than a selected one.
        let max_sel = got.iter().map(|n| addr.xor_distance(n)).max().unwrap();
        for (n, _) in &peers {
            if !got.contains(n) {
                assert!(addr.xor_distance(n) >= max_sel);
            }
        }
    }

    // ── select_replicas — the composed admission → proximity → preference path ─

    #[test]
    fn select_replicas_composes_bond_admission_and_reputation_preference() {
        use crate::replication::ReplicationPolicy;
        let root = did("rootA");
        let addr = crate::neighborhood_store::cid_address(&root);
        let policy = ReplicationPolicy::new(2).with_min_bond(5_000);

        // peggy + quinn are bonded to floor; sybil has a fresh key and no bond.
        let peggy = did("did:key:peggy");
        let quinn = did("did:key:quinn");
        let sybil = did("did:key:sybil");
        let peggy_n = nid(b"peggy-node");
        let quinn_n = nid(b"quinn-node");
        let sybil_n = nid(b"sybil-node");
        let mut pins = PinIndex::new();
        bonded_pin(&mut pins, "pinP", &peggy, &root, 5_000);
        bonded_pin(&mut pins, "pinQ", &quinn, &root, 5_000);

        // reputation: quinn > peggy. sybil's reputation is high but must not save it.
        let peers = vec![
            (peggy_n.clone(), peggy, 10u64),
            (quinn_n.clone(), quinn, 99u64),
            (sybil_n.clone(), sybil, 1_000_000u64),
        ];

        let selected = select_replicas(&root, &addr, &peers, &policy, &pins, true);
        // admission: sybil (no bond) is excluded despite huge reputation.
        assert!(!selected.contains(&sybil_n), "unbonded Sybil must not be admitted");
        // both bonded peers are in; quinn is preferred (higher reputation) first.
        assert_eq!(selected, vec![quinn_n, peggy_n]);
    }

    #[test]
    fn select_replicas_membrane_off_admits_all_and_still_ranks() {
        use crate::replication::ReplicationPolicy;
        let root = did("rootB");
        let addr = crate::neighborhood_store::cid_address(&root);
        // membrane off + open policy → bond ignored, all peers admitted.
        let policy = ReplicationPolicy::default();
        let pins = PinIndex::new();
        let a = nid(b"a-node");
        let b = nid(b"b-node");
        let peers = vec![
            (a.clone(), did("did:a"), 5u64),
            (b.clone(), did("did:b"), 50u64),
        ];
        let selected = select_replicas(&root, &addr, &peers, &policy, &pins, false);
        assert_eq!(selected.len(), 2, "membrane off admits all");
        assert_eq!(selected[0], b, "higher reputation preferred first");
    }

    #[test]
    fn select_replicas_admission_is_bond_only_adversarially() {
        // THE Sybil-resistance property: with the membrane ON, no amount of
        // reputation gets an unbonded / under-bonded DID selected. Sweep peer
        // mixes (bonded/unbonded × varied reputation) × bond floors.
        use crate::neighborhood::K;
        use crate::replication::ReplicationPolicy;
        use std::collections::HashSet;
        let root = did("root");
        let addr = crate::neighborhood_store::cid_address(&root);

        // 8 peers: even indices bonded at 5000, odd indices unbonded; reputation
        // deliberately INVERTED (unbonded peers get the highest reputation).
        let mut pins = PinIndex::new();
        let mut peers = Vec::new();
        for i in 0..8u8 {
            let d = did(&format!("did{i}"));
            let bonded = i % 2 == 0;
            if bonded {
                bonded_pin(&mut pins, &format!("pin{i}"), &d, &root, 5_000);
            }
            let reputation = if bonded { i as u64 } else { 1_000 + i as u64 };
            peers.push((nid(&[i; 6]), d, reputation));
        }
        for floor in [1i64, 5_000, 5_001] {
            // the eligible node set for THIS floor (bond-only admission).
            let eligible: HashSet<NodeId> = peers
                .iter()
                .filter(|(_, d, _)| eligible_replica(d, &root, floor, &pins))
                .map(|(n, _, _)| n.clone())
                .collect();
            let policy = ReplicationPolicy::new(3).with_min_bond(floor);
            let selected = select_replicas(&root, &addr, &peers, &policy, &pins, true);
            assert!(selected.len() <= K, "never exceeds K");
            assert_eq!(
                selected.iter().collect::<HashSet<_>>().len(),
                selected.len(),
                "no duplicates"
            );
            for n in &selected {
                assert!(eligible.contains(n), "selected a non-eligible node (Sybil leak!)");
            }
            if floor > 5_000 {
                assert!(selected.is_empty(), "floor above all bonds admits nobody");
            }
        }
        // membrane OFF: the bond floor is ignored entirely (open neighbourhood).
        let open = select_replicas(
            &root,
            &addr,
            &peers,
            &ReplicationPolicy::new(3).with_min_bond(5_001),
            &pins,
            false,
        );
        assert!(!open.is_empty(), "membrane off ignores the bond floor");
    }
}
