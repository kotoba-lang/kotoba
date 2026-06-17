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

use crate::node_id::NodeId;
use kotoba_core::cid::KotobaCid;
use kotoba_query::social::{eligible_replica, PinIndex};

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
}
