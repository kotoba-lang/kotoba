//! Cross-crate end-to-end (ADR-002): the SAME observed `mishmar/pin/*` bond in
//! the social `PinIndex` drives BOTH membrane admission (kotoba-dht
//! `select_replicas`) AND the slash magnitude (`SlashSchedule` over the bond).
//! Proves the social ledger ↔ DHT membrane composition holds through the real
//! data flow, not just within each crate's unit tests.

use kotoba_core::cid::KotobaCid;
use kotoba_dht::availability_proof::VerificationResult;
use kotoba_dht::neighborhood_store::cid_address;
use kotoba_dht::{
    availability_slash_warrant, select_replicas, AuditAction, PeerAudit, ReplicationPolicy,
    SlashSchedule, ValidationRule,
};
use kotoba_query::datom::{Datom, Value};
use kotoba_query::delta::Delta;
use kotoba_query::social::PinIndex;

fn did(seed: &str) -> KotobaCid {
    KotobaCid::from_bytes(seed.as_bytes())
}

/// Project one observed `Pinned` event (pinner DID on root with bond) into a
/// PinIndex — the shape `mishmar_observe::decode_pinned_logs` produces.
fn observe_pin(idx: &mut PinIndex, pin: &str, pinner: &KotobaCid, root: &KotobaCid, bond: i64) {
    let p = did(pin);
    let g = did("graph");
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
fn observed_bond_drives_both_admission_and_slash() {
    let root = did("root:hot-graph");
    let addr = cid_address(&root);

    // Two would-be replicas: peggy posted a 6000 bond; sybil has a fresh key and
    // no bond at all (but a huge reputation, which must not save her).
    let peggy_did = did("did:key:peggy");
    let sybil_did = did("did:key:sybil");
    let peggy_node = kotoba_dht::NodeId::from_pubkey(b"peggy-node");
    let sybil_node = kotoba_dht::NodeId::from_pubkey(b"sybil-node");

    let mut pins = PinIndex::new();
    observe_pin(&mut pins, "pinP", &peggy_did, &root, 6_000);

    // ── admission: select_replicas under a 5000 bond floor ──────────────────
    let policy = ReplicationPolicy::new(2).with_min_bond(5_000);
    let peers = vec![
        (peggy_node.clone(), peggy_did.clone(), 1u64),
        (sybil_node.clone(), sybil_did, 1_000_000u64),
    ];
    let selected = select_replicas(&root, &addr, &peers, &policy, &pins, true);
    assert!(
        selected.contains(&peggy_node),
        "bonded peer is admitted from the observed pin"
    );
    assert!(
        !selected.contains(&sybil_node),
        "unbonded Sybil is excluded despite huge reputation"
    );

    // ── slash: peggy later fails an availability proof ──────────────────────
    let validator = kotoba_dht::NodeId::from_pubkey(b"auditor");
    let failed = PeerAudit {
        peer: peggy_node.clone(),
        result: Some(VerificationResult {
            epoch: 1,
            prover_peer: peggy_node.0.to_vec(),
            score: 0.10, // < 0.5 → slash
            challenged: 10,
            proven: 1,
        }),
        action: AuditAction::Slash,
    };
    let (warrant, evidence) =
        availability_slash_warrant(&failed, &validator, 42, |m| m.to_vec()).expect("slash warrant");
    assert_eq!(
        warrant.rule_id,
        ValidationRule::AvailabilityProofFailed as u8
    );
    assert_eq!(warrant.evidence, evidence.cid(), "evidence is content-addressed");

    // The slash is sized from the SAME observed bond that admitted peggy.
    let schedule = SlashSchedule::new(2_500, 10_000); // 25% per consecutive miss
    let bond = pins.max_bond_for(&peggy_did, &root);
    assert_eq!(bond, 6_000, "slash reads the very bond that gated admission");
    assert_eq!(schedule.slash_amount(bond, 1), 1_500, "first miss → 25% of 6000");
    assert_eq!(schedule.slash_amount(bond, 4), 6_000, "sustained failure → full bond");
}

#[test]
fn membrane_off_admits_unbonded_and_slash_reads_zero_bond() {
    // With the membrane off (open neighbourhood), an unbonded peer IS admitted —
    // and a slash against it reads bond 0, i.e. there is nothing to lose. This is
    // exactly why stake-to-replicate must be on for slashing to bite.
    let root = did("root:open");
    let addr = cid_address(&root);
    let did_a = did("did:a");
    let node_a = kotoba_dht::NodeId::from_pubkey(b"a-node");
    let pins = PinIndex::new(); // no observed pins at all
    let policy = ReplicationPolicy::default();
    let peers = vec![(node_a.clone(), did_a.clone(), 0u64)];

    let selected = select_replicas(&root, &addr, &peers, &policy, &pins, false);
    assert_eq!(selected, vec![node_a], "membrane off admits the unbonded peer");

    let schedule = SlashSchedule::new(2_500, 10_000);
    assert_eq!(
        schedule.slash_amount(pins.max_bond_for(&did_a, &root), 4),
        0,
        "no bond ⇒ nothing to slash — open membrane has no teeth"
    );
}
