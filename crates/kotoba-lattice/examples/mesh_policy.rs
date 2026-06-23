//! KOTOBA Mesh M5 — capability links (mesh policy) + out-of-proc routing.
//!
//!   PutLink (CACAO-rooted grant) → authorize gate → wRPC route to a provider
//!
//! Run:  cargo run -p kotoba-lattice --example mesh_policy

use std::collections::BTreeMap;

use kotoba_lattice::protocol::{Heartbeat, Link, NodeRole};
use kotoba_lattice::{route_capability, LatticeController, LatticeMessage, ProviderRoute};

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

fn main() {
    let mut c = LatticeController::new(1000, 100);

    // component reply (did:reply) wants to call cap/llm.infer
    let (source, target, ability) = ("did:reply", "cap/llm", "infer");

    println!("== mesh policy gate ==");
    let d = c.authorize(source, target, ability);
    println!("before link: allowed={} ({})", d.allowed, d.reason);

    // operator grants a CACAO-rooted link → propagated as PutLink
    c.on_message(
        LatticeMessage::PutLink(Link {
            id: "lnk-1".into(),
            source: source.into(),
            target: target.into(),
            config: Some("bafyGemmaCfg".into()),
            cacao: "bafyDepth2Grant".into(), // CACAO chain = Holochain cap grant
            ability: ability.into(),
        }),
        0,
    );
    let d = c.authorize(source, target, ability);
    println!("after  link: allowed={} (link={:?})", d.allowed, d.link_id);

    // escalation attempt: same link does NOT grant a different ability
    let esc = c.authorize(source, target, "train");
    println!(
        "escalation (infer→train): allowed={} ({})",
        esc.allowed, esc.reason
    );

    // revoke
    c.on_message(LatticeMessage::DelLink { id: "lnk-1".into() }, 0);
    println!(
        "after revoke: allowed={}",
        c.authorize(source, target, ability).allowed
    );

    // == out-of-proc provider routing (wRPC) ==
    println!("\n== wRPC routing ==");
    let local = hb("did:self", &["cap/kqe"], 100); // local has kqe, not llm
    let fleet = vec![
        hb("did:self", &["cap/kqe"], 100),
        hb("did:gpu-a", &["cap/llm"], 400),
        hb("did:gpu-b", &["cap/llm"], 900),
    ];
    println!(
        "cap/kqe → {:?}",
        route_capability("cap/kqe", &local, &fleet)
    ); // Local
    println!(
        "cap/llm → {:?}",
        route_capability("cap/llm", &local, &fleet)
    ); // Remote(gpu-b, richest)
    println!(
        "cap/evm → {:?}",
        route_capability("cap/evm", &local, &fleet)
    ); // Unavailable

    assert_eq!(
        route_capability("cap/kqe", &local, &fleet),
        ProviderRoute::Local
    );
    assert_eq!(
        route_capability("cap/llm", &local, &fleet),
        ProviderRoute::Remote("did:gpu-b".into())
    );
}
