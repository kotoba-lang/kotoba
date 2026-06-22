//! Integration test: KOTOBA Mesh lattice control-plane messages flow between
//! two real libp2p swarms over QUIC gossipsub.
//!
//! This is the end-to-end async-swarm coverage for the lattice binding: it
//! exercises `subscribe_lattice` + `impl Transport for KotobaSwarm` (CBOR encode
//! → gossipsub publish over a real QUIC connection) + `decode_lattice` on the
//! receiving peer. Mirrors the timing approach of `swarm_gossip_test.rs`.

use std::collections::BTreeMap;
use std::time::Duration;

use kotoba_lattice::protocol::{topic, Heartbeat, Link, NodeRole};
use kotoba_lattice::{LatticeMessage, Transport};
use kotoba_net::lattice::{decode_lattice, subscribe_lattice};
use kotoba_net::{KotobaNetEvent, KotobaSwarm, Multiaddr};
use tokio::time::{sleep, timeout, Instant};

async fn get_listen_addr(swarm: &mut KotobaSwarm) -> Option<Multiaddr> {
    timeout(Duration::from_secs(5), async {
        loop {
            if let KotobaNetEvent::ListenAddr(a) = swarm.next_event().await? {
                return Some(a);
            }
        }
    })
    .await
    .ok()
    .flatten()
}

/// Drive both swarms until a decodable lattice message arrives on `rx`.
async fn drive_until_lattice(
    drive: &mut KotobaSwarm,
    rx: &mut KotobaSwarm,
    deadline: Duration,
) -> Option<LatticeMessage> {
    let start = Instant::now();
    loop {
        if start.elapsed() > deadline {
            return None;
        }
        tokio::select! {
            ev = drive.next_event() => { ev.as_ref()?; }
            ev = rx.next_event() => match ev {
                None => return None,
                Some(KotobaNetEvent::GossipMessage { topic, data, .. }) => {
                    if let Some(m) = decode_lattice(&topic, &data) {
                        return Some(m);
                    }
                }
                _ => {}
            }
        }
    }
}

/// Connect `s2 → s1` and wait until both report the connection.
async fn connect(s1: &mut KotobaSwarm, s2: &mut KotobaSwarm) {
    let listen = get_listen_addr(s1).await.expect("swarm1 ListenAddr timeout");
    s2.add_peer(s1.local_peer_id, listen);
    let connected = timeout(Duration::from_secs(5), async {
        loop {
            tokio::select! {
                ev1 = s1.next_event() => if let Some(KotobaNetEvent::PeerConnected(_)) = ev1 { return true; },
                ev2 = s2.next_event() => if let Some(KotobaNetEvent::PeerConnected(_)) = ev2 { return true; },
            }
        }
    })
    .await;
    assert!(connected.is_ok(), "swarms failed to connect within 5s");
    // let gossipsub SUBSCRIBE/GRAFT propagate before the first publish
    sleep(Duration::from_millis(200)).await;
}

/// Publish a lattice message via the `Transport` impl, retrying through mesh ramp-up.
async fn publish_lattice(
    s1: &mut KotobaSwarm,
    s2: &mut KotobaSwarm,
    t: &str,
    msg: &LatticeMessage,
) -> bool {
    for _ in 0..10 {
        if <KotobaSwarm as Transport>::publish(s1, t, msg).is_ok() {
            return true;
        }
        tokio::select! {
            _ = s1.next_event() => {}
            _ = s2.next_event() => {}
            _ = sleep(Duration::from_millis(100)) => {}
        }
    }
    false
}

#[tokio::test]
async fn lattice_heartbeat_round_trips_over_quic_gossipsub() {
    let mut s1 = KotobaSwarm::new("/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap())
        .await
        .expect("swarm1");
    let mut s2 = KotobaSwarm::new("/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap())
        .await
        .expect("swarm2");

    subscribe_lattice(&mut s1).expect("s1 subscribe_lattice");
    subscribe_lattice(&mut s2).expect("s2 subscribe_lattice");
    connect(&mut s1, &mut s2).await;

    let hb = LatticeMessage::Heartbeat(Heartbeat {
        node_did: "did:key:zSender".into(),
        roles: vec![NodeRole::Compute, NodeRole::Pin],
        labels: BTreeMap::from([("zone".into(), "jp".into())]),
        caps: vec!["cap/kqe".into(), "cap/llm".into()],
        free_gas: 9_000_000,
        hosted: vec!["bafyComponent".into()],
        lat_ms: 7,
    });

    assert!(
        publish_lattice(&mut s1, &mut s2, topic::HEARTBEAT, &hb).await,
        "could not publish heartbeat to the lattice topic"
    );

    let got = drive_until_lattice(&mut s1, &mut s2, Duration::from_secs(5)).await;
    assert_eq!(got, Some(hb), "peer must decode the exact heartbeat sent over QUIC");
}

#[tokio::test]
async fn lattice_putlink_propagates_over_the_mesh() {
    // mesh policy (links) must propagate node-to-node — net_actor relies on this.
    let mut s1 = KotobaSwarm::new("/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap())
        .await
        .expect("swarm1");
    let mut s2 = KotobaSwarm::new("/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap())
        .await
        .expect("swarm2");

    subscribe_lattice(&mut s1).expect("s1 subscribe_lattice");
    subscribe_lattice(&mut s2).expect("s2 subscribe_lattice");
    connect(&mut s1, &mut s2).await;

    let put = LatticeMessage::PutLink(Link {
        id: "lnk-1".into(),
        source: "did:key:zComponent".into(),
        target: "cap/llm".into(),
        config: Some("bafyCfg".into()),
        cacao: "bafyGrant".into(),
        ability: "infer".into(),
    });

    assert!(
        publish_lattice(&mut s1, &mut s2, topic::LINK, &put).await,
        "could not publish PutLink to the lattice topic"
    );

    match drive_until_lattice(&mut s1, &mut s2, Duration::from_secs(5)).await {
        Some(LatticeMessage::PutLink(l)) => {
            assert_eq!(l.id, "lnk-1");
            assert_eq!(l.target, "cap/llm");
            assert_eq!(l.ability, "infer");
        }
        other => panic!("expected PutLink over the wire, got {other:?}"),
    }
}
