//! Robustness / edge-case + property tests for the lattice control plane.
//! Public-API only. These guard the boundaries the happy-path tests skip:
//! empty fleets, ineligible-only fleets, under-supplied auctions, large-fleet
//! award determinism, and the control-datom round-trip invariant.

use std::collections::BTreeMap;

use kotoba_lattice::protocol::{Auction, Bid, Constraints, Heartbeat, NodeRole};
use kotoba_lattice::{
    app_to_quads, award_winners, desired_from_quads, AppManifest, LatticeController, LatticeMessage,
};

fn hb(did: &str, caps: &[&str], free_gas: u64) -> Heartbeat {
    Heartbeat {
        node_did: did.into(),
        roles: vec![NodeRole::Compute],
        labels: BTreeMap::new(),
        caps: caps.iter().map(|s| s.to_string()).collect(),
        free_gas,
        hosted: vec![],
        lat_ms: 0,
    }
}

fn put_app(cid: &str, n: u32, cap: &str) -> LatticeMessage {
    LatticeMessage::PutApp {
        app: "app".into(),
        desired: BTreeMap::from([(cid.to_string(), n)]),
        constraints: BTreeMap::from([(
            cid.to_string(),
            Constraints {
                require_labels: BTreeMap::new(),
                requires_caps: vec![cap.to_string()],
            },
        )]),
    }
}

#[test]
fn auction_with_no_bids_awards_nothing() {
    // desired, but no node ever bids → close_due must yield no StartComponent
    // and must not panic / loop.
    let mut c = LatticeController::new(15_000, 3_000);
    c.on_message(put_app("bafyX", 2, "cap/kqe"), 0);
    let opened = c.tick(100);
    assert!(opened
        .iter()
        .any(|(_, m)| matches!(m, LatticeMessage::Auction(_))));
    let closed = c.close_due(4_000);
    assert!(
        !closed
            .iter()
            .any(|(_, m)| matches!(m, LatticeMessage::StartComponent { .. })),
        "no bids → no placement"
    );
    // still short → a later round re-auctions
    let again = c.tick(8_000);
    assert!(again
        .iter()
        .any(|(_, m)| matches!(m, LatticeMessage::Auction(_))));
}

#[test]
fn ineligible_nodes_never_bid() {
    // a node lacking the required cap, or failing a label, must produce no bid.
    let auction = Auction {
        id: "a1".into(),
        cid: "bafyX".into(),
        n: 1,
        constraints: Constraints {
            require_labels: BTreeMap::from([("tier".into(), "edge".into())]),
            requires_caps: vec!["cap/llm".into()],
        },
    };
    // missing cap
    assert!(LatticeController::bid_for(&auction, &hb("n1", &["cap/kqe"], 100)).is_none());
    // has cap but missing label
    assert!(LatticeController::bid_for(&auction, &hb("n2", &["cap/llm"], 100)).is_none());
    // has cap + label → bids
    let mut ok = hb("n3", &["cap/llm"], 100);
    ok.labels.insert("tier".into(), "edge".into());
    assert!(LatticeController::bid_for(&auction, &ok).is_some());
}

#[test]
fn award_is_capped_at_available_bids() {
    // desired 5 but only 2 eligible bidders → exactly 2 placements this round.
    let mut c = LatticeController::new(15_000, 3_000);
    c.on_message(put_app("bafyX", 5, "cap/kqe"), 0);
    let auction: Auction = c
        .tick(100)
        .into_iter()
        .find_map(|(_, m)| match m {
            LatticeMessage::Auction(a) => Some(a),
            _ => None,
        })
        .unwrap();
    for did in ["nA", "nB"] {
        c.on_bid(LatticeController::bid_for(&auction, &hb(did, &["cap/kqe"], 100)).unwrap());
    }
    let starts = c
        .close_due(4_000)
        .into_iter()
        .filter(|(_, m)| matches!(m, LatticeMessage::StartComponent { .. }))
        .count();
    assert_eq!(
        starts, 2,
        "cannot place more instances than there are bidders"
    );
}

#[test]
fn award_winners_is_deterministic_and_sorted_on_a_large_fleet() {
    let auction = Auction {
        id: "big".into(),
        cid: "bafyX".into(),
        n: 5,
        constraints: Constraints::default(),
    };
    // 50 bidders; scores collide deliberately to exercise the did tie-break.
    let mut bids = Vec::new();
    for i in 0..50u32 {
        bids.push(Bid {
            auction_id: "big".into(),
            node_did: format!("did:n{i:02}"),
            score: (i % 5) as u64 * 100, // many ties
        });
    }
    let w1 = award_winners(&auction, &bids);
    // reversing input order must not change the result
    let mut rev = bids.clone();
    rev.reverse();
    let w2 = award_winners(&auction, &rev);
    assert_eq!(w1, w2, "award must be order-independent");
    assert_eq!(w1.len(), 5);
    // winners must be the top score band (400), tie-broken by ascending did
    assert_eq!(
        w1,
        vec!["did:n04", "did:n09", "did:n14", "did:n19", "did:n24"]
    );
}

#[test]
fn award_winners_ignores_foreign_auction_bids() {
    let auction = Auction {
        id: "mine".into(),
        cid: "x".into(),
        n: 3,
        constraints: Constraints::default(),
    };
    let bids = vec![
        Bid {
            auction_id: "mine".into(),
            node_did: "a".into(),
            score: 10,
        },
        Bid {
            auction_id: "other".into(),
            node_did: "b".into(),
            score: 999,
        },
    ];
    assert_eq!(award_winners(&auction, &bids), vec!["a".to_string()]);
}

#[test]
fn control_roundtrip_is_order_independent_and_multi_component() {
    let src = r#"{:kotoba.app/name "multi"
        :kotoba.app/components
        [{:name "a" :cid "bafyA" :scale 3 :requires [:cap/kqe]}
         {:name "b" :cid "bafyB" :scale 1 :requires [:cap/llm :cap/kqe]}]
        :kotoba.app/placement {:require {:tier "edge"}}}"#;
    let app = AppManifest::from_edn(src).unwrap();
    let quads = app_to_quads(&app, &BTreeMap::new());

    let (d1, c1) = desired_from_quads(&quads);
    // shuffle the datom order → must recover the same desired + constraints
    let mut shuffled = quads.clone();
    shuffled.reverse();
    let (d2, c2) = desired_from_quads(&shuffled);

    assert_eq!(d1, d2);
    assert_eq!(c1, c2);
    assert_eq!(d1.get("bafyA"), Some(&3));
    assert_eq!(d1.get("bafyB"), Some(&1));
    assert!(c1["bafyB"].requires_caps.contains(&"cap/llm".to_string()));
    assert_eq!(
        c1["bafyA"].require_labels.get("tier").map(|s| s.as_str()),
        Some("edge")
    );
}

#[test]
fn undesired_running_component_is_scaled_to_zero() {
    // a component that's running (observed) but not desired → ScaleTo 0.
    let mut c = LatticeController::new(15_000, 3_000);
    // desired is empty (no PutApp); a node reports hosting something
    let mut h = hb("nA", &["cap/kqe"], 100);
    h.hosted.push("bafyOrphan".into());
    c.on_heartbeat(h, 0);
    let msgs = c.tick(100);
    let scale = msgs.iter().find_map(|(_, m)| match m {
        LatticeMessage::ScaleTo { cid, n } => Some((cid.clone(), *n)),
        _ => None,
    });
    assert_eq!(scale, Some(("bafyOrphan".to_string(), 0)));
}
