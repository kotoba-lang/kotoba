//! End-to-end demo of the KOTOBA Mesh control loop (ADR M1 brain):
//!
//!   EDN manifest  →  desired state
//!   heartbeats    →  observed state
//!   reconcile     →  need actions (scale up/down)
//!   auction       →  leader-less placement (bid + deterministic award)
//!
//! Run:  cargo run -p kotoba-lattice --example mesh_reconcile
//!
//! No network, no wasmtime — this is the pure deterministic decision core that
//! kotoba-net/kotoba-server will wire to gossipsub + the WASM host.

use std::collections::BTreeMap;

use kotoba_lattice::protocol::{auction_id, Auction, Bid, Constraints, NodeRole};
use kotoba_lattice::{
    award_winners, need_actions, observed_counts, score_bid, AppManifest, Heartbeat,
};

// The real sample manifest — kept in sync with examples/kotoba-mesh-app/.
const MANIFEST: &str = include_str!("../../../examples/kotoba-mesh-app/kotoba.app.edn");

fn node(did: &str, zone: &str, caps: &[&str], free_gas: u64, hosted: &[&str]) -> Heartbeat {
    Heartbeat {
        node_did: did.into(),
        roles: vec![NodeRole::Compute, NodeRole::Pin],
        labels: BTreeMap::from([("zone".into(), zone.into()), ("tier".into(), "edge".into())]),
        caps: caps.iter().map(|s| s.to_string()).collect(),
        free_gas,
        hosted: hosted.iter().map(|s| s.to_string()).collect(),
        lat_ms: 0,
    }
}

fn main() {
    let app = AppManifest::from_edn(MANIFEST).expect("parse manifest");

    println!("== app: {} v{} ==", app.name, app.version.as_deref().unwrap_or("?"));
    for c in &app.components {
        println!(
            "  component {:8} lang={:?} scale={} requires={:?}",
            c.name, c.lang, c.scale, c.requires
        );
    }
    println!("  placement spread={:?} require={:?}\n", app.placement.spread, app.placement.require);

    // ── observed state from a 3-node fleet (nothing hosted yet) ──
    let mut fleet = vec![
        node("did:key:zTokyo", "jp", &["cap/kqe", "cap/egress", "cap/llm"], 9_000_000, &[]),
        node("did:key:zOsaka", "jp", &["cap/kqe", "cap/egress"], 8_000_000, &[]),
        node("did:key:zNara", "jp", &["cap/kqe", "cap/egress", "cap/llm"], 5_000_000, &[]),
    ];

    let desired = app.desired_by_cid();
    let observed = observed_counts(&fleet);
    let actions = need_actions(&desired, &observed);

    println!("== reconcile: desired={:?} observed={:?} ==", desired, observed);
    for a in &actions {
        println!("  need {:+} of {}", a.delta, a.cid);
    }
    println!();

    // ── run an auction per scale-up action and place via deterministic award ──
    for a in actions.iter().filter(|a| a.delta > 0) {
        // constraints = component's required caps + app placement labels
        let comp = app
            .components
            .iter()
            .find(|c| a.cid == format!("clj:{}", c.name) || Some(&a.cid) == c.cid.as_ref())
            .unwrap();
        let constraints = Constraints {
            require_labels: app.placement.require.clone(),
            requires_caps: comp.requires.clone(),
        };
        let have = observed.get(&a.cid).copied().unwrap_or(0);
        let auction = Auction {
            id: auction_id(&a.cid, comp.scale, have),
            cid: a.cid.clone(),
            n: a.delta as u32,
            constraints: constraints.clone(),
        };

        // every eligible node bids its score; ineligible nodes stay silent
        let bids: Vec<Bid> = fleet
            .iter()
            .filter_map(|hb| {
                score_bid(hb, &constraints).map(|score| Bid {
                    auction_id: auction.id.clone(),
                    node_did: hb.node_did.clone(),
                    score,
                })
            })
            .collect();

        let winners = award_winners(&auction, &bids);
        println!(
            "  auction {} for {} (n={}) → bids={} winners={:?}",
            auction.id,
            comp.name,
            auction.n,
            bids.len(),
            winners
        );

        // reflect the placement back into observed state (next heartbeat)
        for w in &winners {
            if let Some(hb) = fleet.iter_mut().find(|h| &h.node_did == w) {
                hb.hosted.push(a.cid.clone());
            }
        }
    }

    // ── verify convergence: re-reconcile should now be empty ──
    let observed2 = observed_counts(&fleet);
    let remaining = need_actions(&desired, &observed2);
    println!("\n== post-placement: observed={:?} ==", observed2);
    if remaining.is_empty() {
        println!("  ✓ converged — desired == observed, no further actions");
    } else {
        println!("  … still need: {:?}", remaining);
    }
}
