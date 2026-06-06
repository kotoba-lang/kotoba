//! T3 — peer-hosted (serverless) rooms over a gossip mesh (ADR-2606060001).
//!
//! Reuses the same protocol + `RoomActor`; the only new thing is the bridge
//! between a gossip transport and the authoritative room. The actual transport
//! is kotoba-net's `KotobaSwarm` (libp2p QUIC + GossipSub + dcutr hole-punch) —
//! it implements [`GossipBus`]. This module is pure (no libp2p dep) so the relay
//! logic is unit-testable with a mock mesh; the swarm slots in unchanged.
//!
//! Roles: exactly one peer holds the authority token and runs a [`P2pAuthority`]
//! (the authoritative `RoomActor`); the others are [`P2pClient`]s that publish
//! inputs and consume the authoritative state stream. Per-frame gossip stays on
//! the room-scoped topics below and never touches the global firehose.

use tokio::sync::broadcast;

use crate::protocol::{self, ClientMsg, InputFrame, ServerMsg};
use crate::room::RoomActor;
use crate::sim::SimHost;

/// Peers publish their `InputFrame`s here.
pub fn input_topic(room: &str) -> String {
    format!("rt/{room}/input")
}
/// The authority publishes the confirmed state stream (bundles/confirms/snapshots) here.
pub fn state_topic(room: &str) -> String {
    format!("rt/{room}/state")
}

/// A gossip transport. `drain` returns messages received from OTHER peers since
/// the last call. kotoba-net's `KotobaSwarm` (publish + subscribe) implements this.
pub trait GossipBus {
    fn publish(&mut self, topic: &str, data: Vec<u8>);
    fn drain(&mut self) -> Vec<(String, Vec<u8>)>;
}

/// The concrete `GossipBus` over kotoba-net's actor swarm: `out` feeds the
/// swarm's `publish_rx` (→ `KotobaSwarm::publish` on the gossip topic), and
/// `inbox` is fed by the swarm's inbound `gossipsub::Message` events for the
/// room topics (the small wiring `net_actor` adds). The adapter itself is pure
/// channels, so it's testable without libp2p; the swarm just drives the ends.
pub struct ChannelGossipBus {
    out: tokio::sync::mpsc::Sender<(String, Vec<u8>)>,
    inbox: tokio::sync::mpsc::Receiver<(String, Vec<u8>)>,
}

impl ChannelGossipBus {
    pub fn new(
        out: tokio::sync::mpsc::Sender<(String, Vec<u8>)>,
        inbox: tokio::sync::mpsc::Receiver<(String, Vec<u8>)>,
    ) -> Self {
        Self { out, inbox }
    }
}

impl GossipBus for ChannelGossipBus {
    fn publish(&mut self, topic: &str, data: Vec<u8>) {
        // Drop on backpressure: realtime gossip is loss-tolerant (rollback covers gaps).
        let _ = self.out.try_send((topic.to_string(), data));
    }
    fn drain(&mut self) -> Vec<(String, Vec<u8>)> {
        let mut out = Vec::new();
        while let Ok(m) = self.inbox.try_recv() {
            out.push(m);
        }
        out
    }
}

/// The peer holding the authority token: ingests peer inputs from the input
/// topic, advances the authoritative room, and republishes its bus (input
/// forwards, confirms, bundles, snapshots) to the state topic.
pub struct P2pAuthority<S: SimHost, B: GossipBus> {
    room_id: String,
    room: RoomActor<S>,
    rx: broadcast::Receiver<ServerMsg>,
    bus: B,
}

impl<S: SimHost, B: GossipBus> P2pAuthority<S, B> {
    pub fn new(room: RoomActor<S>, bus: B) -> Self {
        let room_id = room.room_id().to_string();
        let rx = room.subscribe();
        Self { room_id, room, rx, bus }
    }

    /// One pump cycle: ingest peer inputs → advance one tick → publish outputs.
    pub fn pump(&mut self, cid_of: impl FnOnce(&[u8]) -> String) {
        let it = input_topic(&self.room_id);
        for (topic, data) in self.bus.drain() {
            if topic == it {
                if let Ok(ClientMsg::Input(f)) = protocol::decode::<ClientMsg>(&data) {
                    self.room.submit_input(f.player, f.tick, f.seq, f.input);
                }
            }
        }
        self.room.tick_once(cid_of);
        let st = state_topic(&self.room_id);
        while let Ok(msg) = self.rx.try_recv() {
            if let Ok(bytes) = protocol::encode(&msg) {
                self.bus.publish(&st, bytes);
            }
        }
    }

    pub fn room(&self) -> &RoomActor<S> {
        &self.room
    }
    pub fn room_mut(&mut self) -> &mut RoomActor<S> {
        &mut self.room
    }
}

/// A non-authority peer: publishes local inputs, consumes authoritative state.
pub struct P2pClient<B: GossipBus> {
    room_id: String,
    bus: B,
}

impl<B: GossipBus> P2pClient<B> {
    pub fn new(room_id: impl Into<String>, bus: B) -> Self {
        Self { room_id: room_id.into(), bus }
    }

    pub fn send_input(&mut self, frame: InputFrame) {
        if let Ok(bytes) = protocol::encode(&ClientMsg::Input(frame)) {
            self.bus.publish(&input_topic(&self.room_id), bytes);
        }
    }

    /// Drain the authoritative state stream addressed to this room.
    pub fn recv(&mut self) -> Vec<ServerMsg> {
        let st = state_topic(&self.room_id);
        self.bus
            .drain()
            .into_iter()
            .filter(|(t, _)| *t == st)
            .filter_map(|(_, d)| protocol::decode::<ServerMsg>(&d).ok())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::protocol::{Input, PlayerId, Tick};
    use crate::room::RoomConfig;
    use crate::sim::CounterSim;
    use std::cell::RefCell;
    use std::rc::Rc;

    /// In-memory gossip mesh: publish appends to a shared log; drain returns
    /// other peers' messages since the node's cursor (gossip = see others, not self).
    type Log = Rc<RefCell<Vec<(usize, String, Vec<u8>)>>>;
    struct Node {
        id: usize,
        log: Log,
        cursor: usize,
    }
    impl GossipBus for Node {
        fn publish(&mut self, topic: &str, data: Vec<u8>) {
            self.log.borrow_mut().push((self.id, topic.to_string(), data));
        }
        fn drain(&mut self) -> Vec<(String, Vec<u8>)> {
            let out: Vec<_> = self.log.borrow()[self.cursor..]
                .iter()
                .filter(|(from, _, _)| *from != self.id)
                .map(|(_, t, d)| (t.clone(), d.clone()))
                .collect();
            self.cursor = self.log.borrow().len();
            out
        }
    }

    #[test]
    fn topics_are_room_scoped() {
        assert_eq!(input_topic("arena"), "rt/arena/input");
        assert_eq!(state_topic("arena"), "rt/arena/state");
    }

    #[tokio::test]
    async fn channel_gossip_bus_publishes_outbound_and_drains_inbound() {
        let (out_tx, mut out_rx) = tokio::sync::mpsc::channel(16);
        let (in_tx, in_rx) = tokio::sync::mpsc::channel(16);
        let mut bus = ChannelGossipBus::new(out_tx, in_rx);

        // publish → reaches the swarm side (publish_rx).
        bus.publish("rt/r/input", vec![1, 2, 3]);
        assert_eq!(out_rx.recv().await.unwrap(), ("rt/r/input".to_string(), vec![1, 2, 3]));

        // inbound swarm events → drain.
        in_tx.send(("rt/r/state".to_string(), vec![9])).await.unwrap();
        in_tx.send(("rt/r/state".to_string(), vec![8])).await.unwrap();
        assert_eq!(
            bus.drain(),
            vec![("rt/r/state".to_string(), vec![9]), ("rt/r/state".to_string(), vec![8])]
        );
        assert!(bus.drain().is_empty(), "drain consumes the inbox");
    }

    #[test]
    fn p2p_authority_relays_peer_input_and_confirms_over_gossip() {
        let log: Log = Rc::new(RefCell::new(Vec::new()));
        let auth_node = Node { id: 0, log: log.clone(), cursor: 0 };
        let client_node = Node { id: 1, log: log.clone(), cursor: 0 };

        let mut cfg = RoomConfig::new("p2p", vec![PlayerId(0), PlayerId(1)]);
        cfg.capacity = 2;
        cfg.snapshot_interval = 0;
        cfg.max_rollback = 1; // finalize quickly
        let room = RoomActor::new(CounterSim::new(), cfg);
        let mut authority = P2pAuthority::new(room, auth_node);
        let mut client = P2pClient::new("p2p", client_node);

        // Peer publishes an input over the mesh.
        client.send_input(InputFrame {
            room: "p2p".into(),
            player: PlayerId(1),
            tick: Tick(0),
            seq: 1,
            input: Input { buttons: 5, axes: vec![] },
        });

        // Authority pumps: ingest → tick → publish. Twice so tick 0 finalizes.
        authority.pump(|_| String::new());
        authority.pump(|_| String::new());

        let msgs = client.recv();
        assert!(
            msgs.iter().any(|m| matches!(m, ServerMsg::Input(f) if f.player == PlayerId(1))),
            "peer input must be forwarded on the gossip state stream"
        );
        assert!(
            msgs.iter().any(|m| matches!(m, ServerMsg::Confirm(_))),
            "client must receive a finalized Confirm over gossip"
        );
    }
}
