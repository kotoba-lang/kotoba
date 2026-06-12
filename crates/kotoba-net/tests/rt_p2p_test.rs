//! T3 integration: kotoba-rt peer-hosted rooms over a REAL libp2p QUIC mesh.
//!
//! Two swarms on ephemeral local QUIC ports. A peer node publishes an
//! `InputFrame` on `rt/<room>/input`; the authority node ingests it through a
//! `P2pAuthority` (driven by a `ChannelGossipBus` bridged to the swarm), advances
//! its `RoomActor`, and republishes the authoritative stream on `rt/<room>/state`
//! — which the peer receives back. This exercises the entire T3 path end-to-end
//! over real gossip (not a mock): framing, topic scheme, relay, authority.
//!
//! TIMING: GossipSub mesh formation takes 100–500 ms; the test uses an 8 s
//! deadline and drives both swarms in the loop.

use kotoba_net::{KotobaNetEvent, KotobaSwarm, Multiaddr};
use kotoba_rt::{
    input_topic, state_topic, ChannelGossipBus, CounterSim, Input, InputFrame, P2pAuthority,
    P2pClient, PlayerId, RoomActor, RoomConfig, ServerMsg, Tick,
};
use std::time::Duration;
use tokio::sync::mpsc;
use tokio::time::{sleep, timeout, Instant};

async fn get_listen_addr(swarm: &mut KotobaSwarm) -> Option<Multiaddr> {
    timeout(Duration::from_secs(5), async {
        loop {
            match swarm.next_event().await? {
                KotobaNetEvent::ListenAddr(a) => return Some(a),
                _ => {}
            }
        }
    })
    .await
    .ok()
    .flatten()
}

/// Strip the swarm's `kotoba/` gossip prefix so it matches `rt/<room>/...`.
fn unprefix(topic: &str) -> String {
    topic.strip_prefix("kotoba/").unwrap_or(topic).to_string()
}

#[tokio::test]
async fn t3_peer_input_round_trips_through_authority_over_libp2p() {
    let addr1: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
    let addr2: Multiaddr = "/ip4/127.0.0.1/udp/0/quic-v1".parse().unwrap();
    let mut sa = KotobaSwarm::new(addr1).await.expect("authority swarm");
    let mut sb = KotobaSwarm::new(addr2).await.expect("peer swarm");

    let room = "arena";
    for s in [&mut sa, &mut sb] {
        s.subscribe(&input_topic(room)).expect("subscribe input");
        s.subscribe(&state_topic(room)).expect("subscribe state");
    }

    // Connect peer → authority.
    let la = get_listen_addr(&mut sa)
        .await
        .expect("authority listen addr");
    sb.add_peer(sa.local_peer_id, la);
    let connected = timeout(Duration::from_secs(5), async {
        loop {
            tokio::select! {
                e = sa.next_event() => if let Some(KotobaNetEvent::PeerConnected(_)) = e { return true; },
                e = sb.next_event() => if let Some(KotobaNetEvent::PeerConnected(_)) = e { return true; },
            }
        }
    })
    .await;
    assert!(connected.is_ok(), "swarms must connect (check QUIC/libp2p)");
    sleep(Duration::from_millis(300)).await; // let SUBSCRIBE/GRAFT propagate

    // Authority: RoomActor + ChannelGossipBus bridged to channels we pump to/from sa.
    let (a_out_tx, mut a_out_rx) = mpsc::channel::<(String, Vec<u8>)>(256);
    let (a_in_tx, a_in_rx) = mpsc::channel::<(String, Vec<u8>)>(256);
    let mut cfg = RoomConfig::new(room, vec![PlayerId(0), PlayerId(1)]);
    cfg.capacity = 2;
    cfg.snapshot_interval = 0;
    let mut authority = P2pAuthority::new(
        RoomActor::new(CounterSim::new(), cfg),
        ChannelGossipBus::new(a_out_tx, a_in_rx),
    );

    // Peer client bridged to sb.
    let (b_out_tx, mut b_out_rx) = mpsc::channel::<(String, Vec<u8>)>(256);
    let (b_in_tx, b_in_rx) = mpsc::channel::<(String, Vec<u8>)>(256);
    let mut client = P2pClient::new(room, ChannelGossipBus::new(b_out_tx, b_in_rx));

    // Peer publishes one input over the mesh.
    client.send_input(InputFrame {
        room: room.into(),
        player: PlayerId(1),
        tick: Tick(0),
        seq: 1,
        input: Input {
            buttons: 5,
            axes: vec![],
        },
    });

    let mut pend_a: Vec<(String, Vec<u8>)> = Vec::new();
    let mut pend_b: Vec<(String, Vec<u8>)> = Vec::new();
    let start = Instant::now();
    let mut got_input_back = false;
    let mut got_confirm = false;

    while start.elapsed() < Duration::from_secs(8) && !(got_input_back && got_confirm) {
        // Collect outbound from both buses.
        while let Ok(m) = a_out_rx.try_recv() {
            pend_a.push(m);
        }
        while let Ok(m) = b_out_rx.try_recv() {
            pend_b.push(m);
        }
        // Publish, retaining anything that fails (InsufficientPeers during ramp-up).
        pend_a.retain(|(t, d)| sa.publish(t, d.clone()).is_err());
        pend_b.retain(|(t, d)| sb.publish(t, d.clone()).is_err());

        // Drive both swarms; route inbound rt/* gossip into the right bus inbox.
        tokio::select! {
            e = sa.next_event() => if let Some(KotobaNetEvent::GossipMessage { topic, data, .. }) = e {
                let _ = a_in_tx.try_send((unprefix(&topic), data));
            },
            e = sb.next_event() => if let Some(KotobaNetEvent::GossipMessage { topic, data, .. }) = e {
                let _ = b_in_tx.try_send((unprefix(&topic), data));
            },
            _ = sleep(Duration::from_millis(40)) => {}
        }

        // Authority: ingest peer inputs → advance → publish authoritative stream.
        authority.pump(|_| String::new());

        // Peer: consume the authoritative stream.
        for m in client.recv() {
            match m {
                ServerMsg::Input(f) if f.player == PlayerId(1) && f.input.buttons == 5 => {
                    got_input_back = true;
                }
                ServerMsg::Confirm(_) => got_confirm = true,
                _ => {}
            }
        }
    }

    assert!(
        got_input_back,
        "peer's InputFrame must traverse real gossip → authority ingest → forward → back to peer"
    );
    assert!(
        got_confirm,
        "peer must receive an authoritative Confirm over real gossip"
    );
}
