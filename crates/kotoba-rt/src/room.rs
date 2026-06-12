//! Per-room actor + broadcast bus (ADR-2606060001).
//!
//! THE load-bearing isolation: each room owns its OWN `tokio::broadcast` bus.
//! Per-frame input/bundles/confirms live only here. They never touch the global
//! KSE LiveBus, firehose, or gossip mesh. Only the low-rate durable snapshot
//! crosses into the cold/federated lane (the `take_durable_snapshot` hook the
//! server wires to `block_store` + `journal` + pin).

use tokio::sync::broadcast;

use crate::protocol::{
    Confirm, Input, InputBundle, InputFrame, PlayerId, Presence, ServerMsg, SignalPayload,
    SnapshotRef, Tick,
};
use crate::rollback::RollbackEngine;
use crate::sim::SimHost;

#[derive(Clone, Debug)]
pub struct RoomConfig {
    pub room_id: String,
    /// Players present from tick 0 (recorded as join events at tick 0). May be
    /// empty — players then join dynamically via [`RoomActor::join`].
    pub players: Vec<PlayerId>,
    /// Max concurrent players = number of simulation slots the `SimHost` is sized
    /// to. Dynamic joins are accepted for `PlayerId` `< capacity`.
    pub capacity: u32,
    /// Ticks between a `join`/`leave` call and its deterministic effect, so all
    /// peers agree on the tick the roster changed (no rollback on the hot path).
    pub join_delay: u64,
    pub seed: u64,
    /// Take a durable snapshot every N ticks (cold-lane bridge cadence).
    pub snapshot_interval: u64,
    /// Bound on retained rollback saves.
    pub max_rollback: u64,
    /// Capacity of the per-room broadcast bus.
    pub bus_capacity: usize,
}

impl RoomConfig {
    pub fn new(room_id: impl Into<String>, players: Vec<PlayerId>) -> Self {
        // Default sim capacity covers the initial roster (min 8 slots).
        let capacity = players.iter().map(|p| p.0 + 1).max().unwrap_or(0).max(8);
        Self {
            room_id: room_id.into(),
            players,
            capacity,
            join_delay: 2,
            seed: 0,
            snapshot_interval: 60,
            max_rollback: crate::rollback::DEFAULT_MAX_ROLLBACK,
            bus_capacity: 1024,
        }
    }
}

/// A durable snapshot the server should persist to the cold lane.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct DurableSnapshot {
    pub tick: Tick,
    pub blob: Vec<u8>,
}

/// The authoritative room runtime. One per active room, owned by a server task.
pub struct RoomActor<S: SimHost> {
    cfg: RoomConfig,
    engine: RollbackEngine<S>,
    bus: broadcast::Sender<ServerMsg>,
    members: Vec<PlayerId>,
}

impl<S: SimHost> RoomActor<S> {
    pub fn new(sim: S, cfg: RoomConfig) -> Self {
        // Size the sim to CAPACITY (LE u32) so dynamic joiners up to `capacity`
        // have a state slot — the engine's ACTIVE roster is what varies per tick.
        let config = cfg.capacity.to_le_bytes();
        let engine = RollbackEngine::new(sim, cfg.players.clone(), cfg.seed, &config)
            .with_max_rollback(cfg.max_rollback);
        let (bus, _) = broadcast::channel(cfg.bus_capacity);
        Self {
            cfg,
            engine,
            bus,
            members: Vec::new(),
        }
    }

    pub fn room_id(&self) -> &str {
        &self.cfg.room_id
    }

    pub fn current_tick(&self) -> Tick {
        self.engine.current_tick()
    }

    pub fn state_hash(&mut self) -> [u8; 32] {
        self.engine.state_hash()
    }

    /// Subscribe to the room's hot bus (a new spectator/player receiver).
    pub fn subscribe(&self) -> broadcast::Receiver<ServerMsg> {
        self.bus.subscribe()
    }

    /// Live receiver count on the hot bus — lets a server reap idle rooms.
    pub fn subscriber_count(&self) -> usize {
        self.bus.receiver_count()
    }

    /// A player joins. The membership change takes effect deterministically at
    /// `current + join_delay` (a tick-stamped roster event through the engine),
    /// so every peer agrees on when the roster grew. Broadcasts a Welcome (with
    /// the effective tick) + Presence. Rejected if `player >= capacity`.
    pub fn join(&mut self, player: PlayerId) {
        if player.0 >= self.cfg.capacity {
            tracing::warn!(
                player = player.0,
                capacity = self.cfg.capacity,
                "kotoba-rt: join over capacity"
            );
            return;
        }
        let effective = Tick(self.engine.current_tick().0 + self.cfg.join_delay);
        self.engine.add_roster_event(player, effective, true);
        if !self.members.contains(&player) {
            self.members.push(player);
            self.members.sort();
        }
        let _ = self.bus.send(ServerMsg::Welcome {
            room: self.cfg.room_id.clone(),
            player,
            tick: effective,
        });
        let _ = self.bus.send(ServerMsg::Presence(Presence {
            room: self.cfg.room_id.clone(),
            player,
            joined: true,
        }));
    }

    pub fn leave(&mut self, player: PlayerId) {
        let effective = Tick(self.engine.current_tick().0 + self.cfg.join_delay);
        self.engine.add_roster_event(player, effective, false);
        self.members.retain(|p| *p != player);
        let _ = self.bus.send(ServerMsg::Presence(Presence {
            room: self.cfg.room_id.clone(),
            player,
            joined: false,
        }));
    }

    /// The active roster at the current tick (authoritative membership).
    pub fn roster(&self) -> Vec<PlayerId> {
        self.engine.active_roster(self.engine.current_tick())
    }

    /// T2: relay a WebRTC signaling payload from `from` to peer `to` on the bus.
    /// The authority does not parse it — peers use it to establish a DataChannel,
    /// after which input frames flow over that loss-tolerant channel.
    pub fn relay_signal(&self, from: PlayerId, to: PlayerId, payload: SignalPayload) {
        let _ = self.bus.send(ServerMsg::Signal {
            room: self.cfg.room_id.clone(),
            from,
            to,
            payload,
        });
    }

    /// Ingest one player's input for a tick (from any transport). The input is
    /// immediately forwarded to all members (PROVISIONAL — for low-latency
    /// client prediction), then applied to the authoritative engine, which rolls
    /// back if it corrects an already-simulated tick. Returns true on rollback.
    pub fn submit_input(&mut self, player: PlayerId, tick: Tick, seq: u64, input: Input) -> bool {
        // Forward first so peers see the input even if it is a late correction
        // the authority will only confirm later.
        let _ = self.bus.send(ServerMsg::Input(InputFrame {
            room: self.cfg.room_id.clone(),
            player,
            tick,
            seq,
            input: input.clone(),
        }));
        self.engine.add_input(player, tick, input)
    }

    /// Advance the authoritative simulation by one tick, then broadcast a FINAL
    /// `Bundle` + `Confirm` for every tick that has just fallen past the rollback
    /// horizon (and is therefore immutable — the GGPO "confirmed frame"). This is
    /// the load-bearing fix per ADR-2606060001: a `Confirm` is only ever emitted
    /// once its tick can no longer be revised by a late input, so the desync
    /// detector never passes on a state that later changes.
    ///
    /// Every `snapshot_interval` ticks it also returns a `DurableSnapshot` for
    /// the server to commit to the cold lane and announces a `SnapshotRef` CID.
    /// `cid_of` content-addresses the durable blob with kotoba's own CID function
    /// (blake3 / KotobaCid) without this crate depending on kotoba-core.
    pub fn tick_once(&mut self, cid_of: impl FnOnce(&[u8]) -> String) -> Option<DurableSnapshot> {
        self.engine.advance(1);

        // Broadcast FINAL confirms for ticks that just crossed the horizon.
        for f in self.engine.drain_finalized() {
            let _ = self.bus.send(ServerMsg::Bundle(InputBundle {
                room: self.cfg.room_id.clone(),
                tick: f.tick,
                inputs: f.inputs,
            }));
            let _ = self.bus.send(ServerMsg::Confirm(Confirm {
                room: self.cfg.room_id.clone(),
                tick: f.tick,
                state_hash: f.state_hash.to_vec(),
            }));
        }

        // Cold-lane bridge: only the periodic snapshot leaves the hot lane.
        let now = self.engine.current_tick().0;
        if self.cfg.snapshot_interval > 0 && now.is_multiple_of(self.cfg.snapshot_interval) {
            let blob = self.engine.durable_snapshot();
            let cid = cid_of(&blob);
            let _ = self.bus.send(ServerMsg::Snapshot(SnapshotRef {
                room: self.cfg.room_id.clone(),
                tick: self.engine.current_tick(),
                snapshot_cid: cid,
            }));
            return Some(DurableSnapshot {
                tick: self.engine.current_tick(),
                blob,
            });
        }
        None
    }
}
