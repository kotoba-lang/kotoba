//! KOTOBA Mesh M4 (wadm) — desired state as control datoms, propagated and
//! reconciled end-to-end:
//!
//!   manifest → app_to_quads (control datoms) → desired_from_quads
//!           → PutApp (lattice) → reconcile → auction → award → StartComponent
//!           → node marks it hosted → converged
//!
//! Run:  cargo run -p kotoba-lattice --example mesh_wadm

use std::collections::{BTreeMap, BTreeSet};

use kotoba_lattice::protocol::{Auction, LatticeMessage, NodeRole};
use kotoba_lattice::{app_to_quads, desired_from_quads, AppManifest, Heartbeat, LatticeController};

const APP: &str = r#"{:kotoba.app/name "wadm-demo"
    :kotoba.app/components
    [{:name "reply" :cid "bafyReply" :scale 2 :requires [:cap/kqe]}]
    :kotoba.app/placement {:require {:tier "edge"}}}"#;

fn hb(did: &str, hosted: &BTreeSet<String>) -> Heartbeat {
    Heartbeat {
        node_did: did.into(),
        roles: vec![NodeRole::Compute],
        labels: BTreeMap::from([("tier".into(), "edge".into())]),
        caps: vec!["cap/kqe".into()],
        free_gas: 1_000_000,
        hosted: hosted.iter().cloned().collect(),
        lat_ms: 0,
    }
}

fn main() {
    // 1. operator deploys: manifest → control datoms (the durable SSOT)
    let app = AppManifest::from_edn(APP).unwrap();
    let quads = app_to_quads(&app, &BTreeMap::new());
    println!("control datoms ({}):", quads.len());
    for q in &quads {
        println!("  ({}  {}  {})", q.subject, q.predicate, q.object);
    }

    // 2. a node reads them back → desired + constraints, announced via PutApp
    let (desired, constraints) = desired_from_quads(&quads);
    println!("\ndesired = {desired:?}");

    let mut c = LatticeController::new(1000, 100);
    c.on_message(
        LatticeMessage::PutApp {
            app: app.name.clone(),
            desired,
            constraints,
        },
        0,
    );

    // 3. two edge nodes online, nothing placed yet
    let mut hosted_a = BTreeSet::new();
    let mut hosted_b = BTreeSet::new();
    c.on_heartbeat(hb("nA", &hosted_a), 0);
    c.on_heartbeat(hb("nB", &hosted_b), 0);

    // 4. reconcile → auction; both eligible nodes bid
    let opened = c.tick(0);
    let auction: Auction = opened
        .iter()
        .find_map(|(_, m)| match m {
            LatticeMessage::Auction(a) => Some(a.clone()),
            _ => None,
        })
        .expect("auction opened");
    println!(
        "\nauction {} for {} (n={})",
        auction.id, auction.cid, auction.n
    );
    c.on_bid(LatticeController::bid_for(&auction, &hb("nA", &hosted_a)).unwrap());
    c.on_bid(LatticeController::bid_for(&auction, &hb("nB", &hosted_b)).unwrap());

    // 5. close → award + StartComponent; each winning node marks it hosted
    //    (in the server this is: fetch wasm by CID → WasmExecutor::execute)
    for (_, m) in c.close_due(120) {
        if let LatticeMessage::StartComponent { node_did, cid, .. } = m {
            println!("  start {cid} on {node_did}");
            match node_did.as_str() {
                "nA" => {
                    hosted_a.insert(cid);
                }
                "nB" => {
                    hosted_b.insert(cid);
                }
                _ => {}
            }
        }
    }

    // 6. nodes re-advertise with the component now hosted → converged
    c.on_heartbeat(hb("nA", &hosted_a), 130);
    c.on_heartbeat(hb("nB", &hosted_b), 130);
    println!("\nobserved = {:?}", c.observed(140));
    if c.tick(140).is_empty() {
        println!("✓ converged — desired == observed (wadm reconcile complete)");
    } else {
        println!("… not yet converged");
    }
}
