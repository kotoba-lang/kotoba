//! KOTOBA Mesh M2 — the stateful controller running over time, with node churn.
//!
//!   tick → auction → bids → close/award → place → converge → lose a node → self-heal
//!
//! Run:  cargo run -p kotoba-lattice --example mesh_node
//!
//! Pure + deterministic (time is injected). The same loop runs against gossipsub
//! in kotoba-server via `impl Transport for KotobaSwarm` (kotoba-net::lattice).

use std::collections::BTreeMap;

use kotoba_lattice::protocol::{Auction, LatticeMessage, NodeRole};
use kotoba_lattice::{AppManifest, Heartbeat, LatticeController, RecordingTransport};

const APP: &str = r#"{:kotoba.app/name "demo"
    :kotoba.app/components
    [{:name "reply" :cid "bafyReply" :scale 2 :requires [:cap/kqe]}]}"#;

fn hb(did: &str, free_gas: u64, hosted: &[&str]) -> Heartbeat {
    Heartbeat {
        node_did: did.into(),
        roles: vec![NodeRole::Compute],
        labels: BTreeMap::new(),
        caps: vec!["cap/kqe".into()],
        free_gas,
        hosted: hosted.iter().map(|s| s.to_string()).collect(),
        lat_ms: 0,
    }
}

fn collect_bids(
    c: &mut LatticeController,
    msgs: &[(String, LatticeMessage)],
    nodes: &[(&str, u64)],
) {
    for (_, m) in msgs {
        if let LatticeMessage::Auction(a) = m {
            let a: &Auction = a;
            for (did, gas) in nodes {
                if let Some(b) = LatticeController::bid_for(a, &hb(did, *gas, &[])) {
                    c.on_bid(b);
                }
            }
        }
    }
}

fn main() {
    let app = AppManifest::from_edn(APP).unwrap();
    let mut c = LatticeController::new(/*ttl*/ 1000, /*bid_window*/ 100);
    c.set_app(&app);
    let mut tx = RecordingTransport::default();

    println!("desired: reply x2 (requires cap/kqe)\n");

    // t=0: two nodes online, nothing placed
    c.on_heartbeat(hb("nTokyo", 200, &[]), 0);
    c.on_heartbeat(hb("nOsaka", 100, &[]), 0);
    let opened = c.tick(0);
    println!(
        "t=0   tick     → {} msg (auction opened, observed=0/2)",
        opened.len()
    );
    collect_bids(&mut c, &opened, &[("nTokyo", 200), ("nOsaka", 100)]);

    // t=120: bid window elapsed → award + place
    let placed = c.close_due(120);
    for (_, m) in &placed {
        if let LatticeMessage::StartComponent { node_did, cid, .. } = m {
            println!("t=120 place    → start {} on {}", cid, node_did);
        }
    }

    // winners report the component hosted → converged
    c.on_heartbeat(hb("nTokyo", 150, &["bafyReply"]), 130);
    c.on_heartbeat(hb("nOsaka", 80, &["bafyReply"]), 130);
    let conv = c.step(140, &mut tx).unwrap();
    println!(
        "t=140 reconcile→ {} msg, observed={:?} (✓ converged)",
        conv,
        c.observed(140)
    );

    // t=2000: nOsaka goes silent → pruned → observed drops → self-heal
    c.on_heartbeat(hb("nTokyo", 150, &["bafyReply"]), 2000); // nTokyo still alive
    c.on_heartbeat(hb("nKyoto", 90, &[]), 2000); // a fresh node joins to take over
    let pruned = c.prune(2000);
    println!(
        "\nt=2000 lost {:?}; observed now {:?}",
        pruned,
        c.observed(2000)
    );
    let heal = c.tick(2000);
    println!(
        "t=2000 tick     → {} msg (re-auction the lost instance)",
        heal.len()
    );
    // bids reflect real load: nTokyo already hosts one (load-penalised), nKyoto is idle
    for (_, m) in &heal {
        if let LatticeMessage::Auction(a) = m {
            if let Some(b) = LatticeController::bid_for(a, &hb("nTokyo", 150, &["bafyReply"])) {
                c.on_bid(b);
            }
            if let Some(b) = LatticeController::bid_for(a, &hb("nKyoto", 90, &[])) {
                c.on_bid(b);
            }
        }
    }
    let replaced = c.close_due(2200);
    for (_, m) in &replaced {
        if let LatticeMessage::StartComponent { node_did, cid, .. } = m {
            println!(
                "t=2200 replace  → start {} on {} (self-healed)",
                cid, node_did
            );
        }
    }
}
