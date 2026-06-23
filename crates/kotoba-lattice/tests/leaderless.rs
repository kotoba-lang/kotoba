//! Integration tests for the no-central-master invariant (ADR §2/§6.1):
//! any number of leader-less reconcilers that observe the same desired state
//! and the same fleet/bids MUST make byte-identical decisions, so the lattice
//! converges without electing a leader. These exercise the crate through its
//! public API only (as a downstream consumer would).

use std::collections::BTreeMap;

use kotoba_lattice::protocol::{Auction, Bid, Constraints, Heartbeat, NodeRole};
use kotoba_lattice::{LatticeController, LatticeMessage};

fn hb(did: &str, caps: &[&str], free_gas: u64, hosted: &[&str]) -> Heartbeat {
    Heartbeat {
        node_did: did.into(),
        roles: vec![NodeRole::Compute],
        labels: BTreeMap::from([("tier".into(), "edge".into())]),
        caps: caps.iter().map(|s| s.to_string()).collect(),
        free_gas,
        hosted: hosted.iter().map(|s| s.to_string()).collect(),
        lat_ms: 0,
    }
}

fn put_app(desired: &[(&str, u32)], cap: &str) -> LatticeMessage {
    let desired: BTreeMap<String, u32> = desired.iter().map(|(c, n)| (c.to_string(), *n)).collect();
    let constraints = desired
        .keys()
        .cloned()
        .map(|k| {
            (
                k,
                Constraints {
                    require_labels: BTreeMap::from([("tier".into(), "edge".into())]),
                    requires_caps: vec![cap.to_string()],
                },
            )
        })
        .collect();
    LatticeMessage::PutApp {
        app: "app".into(),
        desired,
        constraints,
    }
}

/// Build a fresh controller fed an identical message stream.
fn controller_seeded(fleet: &[Heartbeat], app: &LatticeMessage) -> LatticeController {
    let mut c = LatticeController::new(15_000, 3_000);
    c.on_message(app.clone(), 0);
    for h in fleet {
        c.on_heartbeat(h.clone(), 0);
    }
    c
}

#[test]
fn two_reconcilers_emit_identical_auctions_and_awards() {
    let fleet = vec![
        hb("nA", &["cap/kqe"], 300, &[]),
        hb("nB", &["cap/kqe"], 200, &[]),
        hb("nC", &["cap/other"], 999, &[]), // ineligible
    ];
    let app = put_app(&[("bafyX", 2)], "cap/kqe");

    let mut a = controller_seeded(&fleet, &app);
    let mut b = controller_seeded(&fleet, &app);

    // identical auctions (same id from deterministic auction_id, same constraints)
    let ta = a.tick(100);
    let tb = b.tick(100);
    assert_eq!(ta, tb, "auctions must be identical across reconcilers");
    assert!(ta
        .iter()
        .any(|(_, m)| matches!(m, LatticeMessage::Auction(_))));

    // identical bid stream → identical awards + StartComponents
    let auction: Auction = ta
        .iter()
        .find_map(|(_, m)| match m {
            LatticeMessage::Auction(x) => Some(x.clone()),
            _ => None,
        })
        .unwrap();
    for h in &fleet {
        if let Some(bid) = LatticeController::bid_for(&auction, h) {
            a.on_bid(bid.clone());
            b.on_bid(bid);
        }
    }
    let ca = a.close_due(4_000);
    let cb = b.close_due(4_000);
    assert_eq!(ca, cb, "awards must be identical across reconcilers");
    // exactly the 2 eligible, richest nodes win (nA, nB), not nC
    let winners: Vec<String> = ca
        .iter()
        .filter_map(|(_, m)| match m {
            LatticeMessage::StartComponent { node_did, .. } => Some(node_did.clone()),
            _ => None,
        })
        .collect();
    assert_eq!(winners, vec!["nA".to_string(), "nB".to_string()]);
}

#[test]
fn bid_order_does_not_change_the_award() {
    // award must depend only on (score, did) — not on bid arrival order.
    let auction = {
        let fleet = vec![
            hb("nA", &["cap/kqe"], 300, &[]),
            hb("nB", &["cap/kqe"], 200, &[]),
        ];
        let app = put_app(&[("bafyX", 1)], "cap/kqe");
        let mut c = controller_seeded(&fleet, &app);
        match c.tick(100).into_iter().find_map(|(_, m)| match m {
            LatticeMessage::Auction(a) => Some(a),
            _ => None,
        }) {
            Some(a) => a,
            None => panic!("no auction"),
        }
    };

    let bids = [
        Bid {
            auction_id: auction.id.clone(),
            node_did: "nA".into(),
            score: 300,
        },
        Bid {
            auction_id: auction.id.clone(),
            node_did: "nB".into(),
            score: 200,
        },
    ];

    // auction is opened lazily on tick, so seed identically first, then feed
    // the same two bids in opposite orders and compare the awards.
    let forward = {
        let mut c = LatticeController::new(15_000, 3_000);
        c.on_message(put_app(&[("bafyX", 1)], "cap/kqe"), 0);
        c.on_heartbeat(hb("nA", &["cap/kqe"], 300, &[]), 0);
        let _ = c.tick(100);
        c.on_bid(bids[0].clone());
        c.on_bid(bids[1].clone());
        c.close_due(4_000)
    };
    let reverse = {
        let mut c = LatticeController::new(15_000, 3_000);
        c.on_message(put_app(&[("bafyX", 1)], "cap/kqe"), 0);
        c.on_heartbeat(hb("nA", &["cap/kqe"], 300, &[]), 0);
        let _ = c.tick(100);
        c.on_bid(bids[1].clone());
        c.on_bid(bids[0].clone());
        c.close_due(4_000)
    };
    assert_eq!(
        forward, reverse,
        "award must be independent of bid arrival order"
    );
}

#[test]
fn reannouncing_same_app_does_not_double_auction() {
    let fleet = vec![hb("nA", &["cap/kqe"], 300, &[])];
    let app = put_app(&[("bafyX", 2)], "cap/kqe");
    let mut c = controller_seeded(&fleet, &app);

    let first = c.tick(100);
    assert!(first
        .iter()
        .any(|(_, m)| matches!(m, LatticeMessage::Auction(_))));

    // a duplicate PutApp (same desired) must not reopen an in-flight auction
    c.on_message(app.clone(), 110);
    let second = c.tick(120);
    assert!(
        !second
            .iter()
            .any(|(_, m)| matches!(m, LatticeMessage::Auction(_))),
        "an auction is already in flight — must not duplicate"
    );
}

#[test]
fn fleet_converges_and_self_heals_identically_on_two_reconcilers() {
    let app = put_app(&[("bafyX", 2)], "cap/kqe");
    let fleet0 = vec![
        hb("nA", &["cap/kqe"], 300, &[]),
        hb("nB", &["cap/kqe"], 200, &[]),
    ];

    let mut a = controller_seeded(&fleet0, &app);
    let mut b = controller_seeded(&fleet0, &app);

    // round 1: auction + award identical
    let auction: Auction = a
        .tick(100)
        .into_iter()
        .find_map(|(_, m)| match m {
            LatticeMessage::Auction(x) => Some(x),
            _ => None,
        })
        .unwrap();
    let _ = b.tick(100);
    for h in &fleet0 {
        if let Some(bid) = LatticeController::bid_for(&auction, h) {
            a.on_bid(bid.clone());
            b.on_bid(bid);
        }
    }
    assert_eq!(a.close_due(4_000), b.close_due(4_000));

    // both observe the winners now hosting → both converge (no more auctions)
    let hosted = [
        hb("nA", &["cap/kqe"], 280, &["bafyX"]),
        hb("nB", &["cap/kqe"], 180, &["bafyX"]),
    ];
    for h in &hosted {
        a.on_heartbeat(h.clone(), 5_000);
        b.on_heartbeat(h.clone(), 5_000);
    }
    assert_eq!(a.observed(5_100), b.observed(5_100));
    assert!(a.tick(5_100).is_empty() && b.tick(5_100).is_empty());

    // nB lost on both → both re-auction identically (self-heal determinism)
    a.on_heartbeat(hb("nA", &["cap/kqe"], 280, &["bafyX"]), 30_000);
    b.on_heartbeat(hb("nA", &["cap/kqe"], 280, &["bafyX"]), 30_000);
    let ha = a.tick(30_000);
    let hb_ = b.tick(30_000);
    assert_eq!(
        ha, hb_,
        "self-heal re-auction must be identical across reconcilers"
    );
    assert!(ha
        .iter()
        .any(|(_, m)| matches!(m, LatticeMessage::Auction(_))));
}
