//! # kotoba-rt — Kotoba realtime game sync
//!
//! Deterministic rollback netcode on a **per-room broadcast bus**, the HOT lane
//! of ADR-2606060001. This crate is the core, transport-agnostic engine:
//!
//!   - [`protocol`] — CBOR wire types (input frames, bundles, confirms, snapshot
//!     refs) shared by every transport (T1 WebSocket / T2 WebRTC / T3 QUIC).
//!   - [`sim`]      — the [`sim::SimHost`] seam (Rust mirror of `wit/kge.wit`)
//!     plus a reference deterministic sim for tests.
//!   - [`rollback`] — [`rollback::RollbackEngine`]: predict → rollback → re-sim.
//!   - [`room`]     — [`room::RoomActor`]: the per-room authority + its OWN
//!     `tokio::broadcast` bus. Per-frame traffic NEVER enters the global KSE
//!     LiveBus / firehose / gossip; only the periodic durable snapshot does.
//!
//! What is intentionally NOT here yet (server wiring, P1→P4):
//!   - the axum `sync.connect` WebSocket route (kotoba-server),
//!   - the `kotoba:kge` WASM `SimHost` impl + browser `kotoba-runtime-web`,
//!   - the snapshot→`block_store`+`journal`+pin cold-lane bridge,
//!   - T2/T3 transports.
//!
//! The seams (`SimHost`, `RoomActor::tick_once`'s `cid_of` + `DurableSnapshot`)
//! are shaped so those drop in without touching this engine.

pub mod p2p;
pub mod protocol;
pub mod rollback;
pub mod room;
pub mod sim;
#[cfg(feature = "wasm-component")]
pub mod wasm_component;
#[cfg(feature = "wasm-sim")]
pub mod wasm_sim;

pub use p2p::{input_topic, state_topic, ChannelGossipBus, GossipBus, P2pAuthority, P2pClient};
pub use protocol::{
    ClientMsg, Confirm, Input, InputBundle, InputFrame, PlayerId, Presence, ServerMsg,
    SignalPayload, SnapshotRef, Tick,
};
pub use rollback::{FinalTick, RollbackEngine, RollbackStats, DEFAULT_MAX_ROLLBACK};
pub use room::{DurableSnapshot, RoomActor, RoomConfig};
pub use sim::{CounterSim, SimHost};
#[cfg(feature = "wasm-component")]
pub use wasm_component::{WasmComponentError, WasmComponentSim};
#[cfg(feature = "wasm-sim")]
pub use wasm_sim::{WasmSim, WasmSimError};

#[derive(Debug, thiserror::Error)]
pub enum RtError {
    #[error("codec: {0}")]
    Codec(String),
    #[error("unknown room: {0}")]
    UnknownRoom(String),
    #[error("unknown player: {0:?}")]
    UnknownPlayer(PlayerId),
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Drive a fresh engine with a full, in-order input log → "ground truth".
    fn ground_truth(players: &[PlayerId], log: &[(PlayerId, u64, u32)], ticks: u64) -> [u8; 32] {
        let mut eng = RollbackEngine::new(CounterSim::new(), players.to_vec(), 7, &player_cfg(2));
        for (p, t, b) in log {
            eng.add_input(
                *p,
                Tick(*t),
                Input {
                    buttons: *b,
                    axes: vec![],
                },
            );
        }
        eng.advance_to(Tick(ticks));
        eng.state_hash()
    }

    fn player_cfg(n: u32) -> Vec<u8> {
        n.to_le_bytes().to_vec()
    }

    #[test]
    fn protocol_cbor_roundtrips() {
        let msg = ServerMsg::Confirm(Confirm {
            room: "r1".into(),
            tick: Tick(42),
            state_hash: vec![1, 2, 3, 4],
        });
        let bytes = protocol::encode(&msg).unwrap();
        let back: ServerMsg = protocol::decode(&bytes).unwrap();
        assert_eq!(msg, back);

        let frame = ClientMsg::Input(InputFrame {
            room: "r1".into(),
            player: PlayerId(2),
            tick: Tick(9),
            seq: 100,
            input: Input {
                buttons: 0b1010,
                axes: vec![0.5, -0.25],
            },
        });
        let back2: ClientMsg = protocol::decode(&protocol::encode(&frame).unwrap()).unwrap();
        assert_eq!(frame, back2);
    }

    #[test]
    fn nan_inf_axes_cannot_desync() {
        // A malformed float axis must collapse to 0 at quantization, so two
        // peers — one fed NaN/Inf, one fed 0.0 — reach identical state.
        let players = vec![PlayerId(0)];
        let mk = |axes: Vec<f32>| {
            let mut e = RollbackEngine::new(CounterSim::new(), players.clone(), 3, &player_cfg(1));
            e.add_input(PlayerId(0), Tick(0), Input { buttons: 2, axes });
            e.advance_to(Tick(1));
            e.state_hash()
        };
        let nan = mk(vec![f32::NAN, f32::INFINITY, f32::NEG_INFINITY]);
        let zero = mk(vec![0.0, 0.0, 0.0]);
        assert_eq!(nan, zero, "NaN/Inf axes must quantize to 0 — no desync");
        // And a real axis value is deterministic + clamped.
        assert_eq!(Input::quantize_axis(0.5), 500);
        assert_eq!(Input::quantize_axis(9.0), 1000, "axes clamp to [-1,1]");
    }

    /// A core wasm guest mirroring the `kge` ABI: 8 i64 accumulators at [0,64),
    /// staging at [1024,..). `step` folds `acc[i] += staging[i]*(tick+1)` then
    /// clears staging — the same deterministic rule as `CounterSim`, but running
    /// as a real WASM guest the host drives + rewinds via linear-memory copy.
    #[cfg(feature = "wasm-sim")]
    const KGE_WAT: &str = r#"
(module
  (memory (export "memory") 1)
  (func (export "init") (param $seed i64) (local $i i32)
    (local.set $i (i32.const 0))
    (block $d (loop $l
      (br_if $d (i32.ge_u (local.get $i) (i32.const 8)))
      (i64.store (i32.mul (local.get $i) (i32.const 8)) (local.get $seed))
      (i64.store (i32.add (i32.const 1024) (i32.mul (local.get $i) (i32.const 8))) (i64.const 0))
      (local.set $i (i32.add (local.get $i) (i32.const 1)))
      (br $l))))
  (func (export "set_input") (param $player i64) (param $buttons i64)
    (i64.store
      (i32.add (i32.const 1024) (i32.mul (i32.wrap_i64 (local.get $player)) (i32.const 8)))
      (local.get $buttons)))
  (func (export "step") (param $tick i64) (local $i i32) (local $w i64)
    (local.set $w (i64.add (local.get $tick) (i64.const 1)))
    (local.set $i (i32.const 0))
    (block $d (loop $l
      (br_if $d (i32.ge_u (local.get $i) (i32.const 8)))
      (i64.store (i32.mul (local.get $i) (i32.const 8))
        (i64.add
          (i64.load (i32.mul (local.get $i) (i32.const 8)))
          (i64.mul
            (i64.load (i32.add (i32.const 1024) (i32.mul (local.get $i) (i32.const 8))))
            (local.get $w))))
      (i64.store (i32.add (i32.const 1024) (i32.mul (local.get $i) (i32.const 8))) (i64.const 0))
      (local.set $i (i32.add (local.get $i) (i32.const 1)))
      (br $l))))
  (func (export "state_ptr") (result i32) (i32.const 0))
  (func (export "state_len") (result i32) (i32.const 64)))
"#;

    /// The killer test, now over a REAL WASM guest: out-of-order inputs force
    /// rollbacks (linear-memory restore + re-sim) that reconverge to the
    /// in-order ground-truth state hash. This proves the ADR's core mechanism.
    #[cfg(feature = "wasm-sim")]
    #[test]
    fn wasm_guest_rollback_reconverges() {
        use crate::WasmSim;
        let players = vec![PlayerId(0), PlayerId(1)];
        let mk = || {
            RollbackEngine::new(
                WasmSim::from_bytes(KGE_WAT).expect("compile kge guest"),
                players.clone(),
                7,
                &player_cfg(2),
            )
        };

        let mut truth = mk();
        truth.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        truth.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        truth.advance_to(Tick(10));
        let truth_hash = truth.state_hash();

        let mut eng = mk();
        eng.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        eng.advance_to(Tick(4)); // player 1's tick-1 input missing → mispredict
        let rolled = eng.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        assert!(rolled, "late input must roll back the wasm guest");
        eng.advance_to(Tick(10));

        assert_eq!(
            eng.state_hash(),
            truth_hash,
            "wasm-guest rollback must reconverge to in-order ground truth"
        );
        assert!(eng.stats().rollbacks >= 1);
    }

    /// The REAL Component-Model path: a `kotoba:kge` component (built by
    /// `testdata/kge-counter-guest` with `cargo component`) driven through the
    /// rollback engine. Out-of-order inputs force rollbacks (WIT snapshot/restore)
    /// that reconverge to the in-order ground truth — proving the portable
    /// server+browser component shape works end-to-end.
    #[cfg(feature = "wasm-component")]
    #[test]
    fn wasm_component_rollback_reconverges() {
        use crate::WasmComponentSim;
        const WASM: &[u8] = include_bytes!("../testdata/kge_counter.wasm");
        let players = vec![PlayerId(0), PlayerId(1)];
        let mk = || {
            RollbackEngine::new(
                WasmComponentSim::from_bytes(WASM).expect("instantiate kge component"),
                players.clone(),
                7,
                &player_cfg(2),
            )
        };

        let mut truth = mk();
        truth.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        truth.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        truth.advance_to(Tick(10));
        let truth_hash = truth.state_hash();

        let mut eng = mk();
        eng.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        eng.advance_to(Tick(4));
        let rolled = eng.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        assert!(rolled, "late input must roll back the component guest");
        eng.advance_to(Tick(10));

        assert_eq!(
            eng.state_hash(),
            truth_hash,
            "component rollback reconverges"
        );
        assert!(eng.stats().rollbacks >= 1);
    }

    /// The room-registry swap mechanism: a `RoomActor<Box<dyn SimHost + Send>>`
    /// driving a boxed REAL component runs join/tick/rollback through dynamic
    /// dispatch — exactly what the server registry holds.
    #[cfg(feature = "wasm-component")]
    #[tokio::test]
    async fn boxed_component_sim_drives_a_room() {
        use crate::WasmComponentSim;
        const WASM: &[u8] = include_bytes!("../testdata/kge_counter.wasm");
        let sim: Box<dyn SimHost + Send> =
            Box::new(WasmComponentSim::from_bytes(WASM).expect("instantiate"));

        let mut cfg = RoomConfig::new("box", vec![PlayerId(0)]);
        cfg.capacity = 2;
        cfg.snapshot_interval = 0;
        let mut room: RoomActor<Box<dyn SimHost + Send>> = RoomActor::new(sim, cfg);

        room.submit_input(
            PlayerId(0),
            Tick(0),
            1,
            Input {
                buttons: 4,
                axes: vec![],
            },
        );
        let before = room.state_hash();
        room.tick_once(|_| String::new());
        let after = room.state_hash();
        assert_ne!(
            before, after,
            "boxed component sim must advance state via the room"
        );
        assert_eq!(room.roster(), vec![PlayerId(0)]);
    }

    /// Cross-implementation byte-identity: the SAME `kotoba:kge` component, driven
    /// by wasmtime here, produces the SAME snapshot bytes the browser host
    /// (`kotoba-runtime-web`, jco) asserts in `determinism.test.mjs`. This is what
    /// makes client prediction match server authority. Shared vector:
    ///   init(seed 7, 2 players) → [7,7]; t0(p0:3,p1:5)→[10,12]; t1(p0:1,p1:2)→[12,16]
    #[cfg(feature = "wasm-component")]
    #[test]
    fn wasm_component_matches_cross_impl_snapshot_vector() {
        use crate::{SimHost, WasmComponentSim};
        const WASM: &[u8] = include_bytes!("../testdata/kge_counter.wasm");
        let mut sim = WasmComponentSim::from_bytes(WASM).unwrap();
        sim.init(7, &2u32.to_le_bytes());
        sim.step(
            Tick(0),
            &[
                (
                    PlayerId(0),
                    Input {
                        buttons: 3,
                        axes: vec![],
                    },
                ),
                (
                    PlayerId(1),
                    Input {
                        buttons: 5,
                        axes: vec![],
                    },
                ),
            ],
        );
        sim.step(
            Tick(1),
            &[
                (
                    PlayerId(0),
                    Input {
                        buttons: 1,
                        axes: vec![],
                    },
                ),
                (
                    PlayerId(1),
                    Input {
                        buttons: 2,
                        axes: vec![],
                    },
                ),
            ],
        );
        let hex: String = sim
            .snapshot_durable()
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect();
        assert_eq!(
            hex, "07000000000000000c000000000000001000000000000000",
            "wasmtime snapshot must match the jco/browser cross-impl vector"
        );
    }

    /// Durable snapshot/restore round-trips through the guest's state region.
    #[cfg(feature = "wasm-sim")]
    #[test]
    fn wasm_guest_durable_snapshot_restores() {
        use crate::{SimHost, WasmSim};
        let mut a = WasmSim::from_bytes(KGE_WAT).unwrap();
        a.init(7, &[]);
        a.step(
            Tick(0),
            &[(
                PlayerId(0),
                Input {
                    buttons: 4,
                    axes: vec![],
                },
            )],
        );
        let blob = a.snapshot_durable();
        let h = a.state_hash();

        // A fresh guest restored from the durable blob reaches the same hash.
        let mut b = WasmSim::from_bytes(KGE_WAT).unwrap();
        b.init(0, &[]);
        b.restore_durable(&blob);
        assert_eq!(b.state_hash(), h, "durable restore must reproduce state");
    }

    #[test]
    fn deterministic_same_inputs_same_hash() {
        let players = [PlayerId(0), PlayerId(1)];
        let log = [
            (PlayerId(0), 0, 3),
            (PlayerId(1), 1, 5),
            (PlayerId(0), 4, 2),
        ];
        let a = ground_truth(&players, &log, 10);
        let b = ground_truth(&players, &log, 10);
        assert_eq!(a, b, "same seed + same inputs must yield identical state");
    }

    #[test]
    fn no_rollback_when_inputs_arrive_in_order() {
        let players = vec![PlayerId(0), PlayerId(1)];
        let mut eng = RollbackEngine::new(CounterSim::new(), players, 7, &player_cfg(2));
        for t in 0..5u64 {
            // both inputs known before we simulate the tick
            eng.add_input(
                PlayerId(0),
                Tick(t),
                Input {
                    buttons: t as u32,
                    axes: vec![],
                },
            );
            eng.add_input(
                PlayerId(1),
                Tick(t),
                Input {
                    buttons: 1,
                    axes: vec![],
                },
            );
            eng.advance(1);
        }
        assert_eq!(
            eng.stats().rollbacks,
            0,
            "in-order inputs must not roll back"
        );
        assert_eq!(eng.current_tick(), Tick(5));
    }

    /// The killer test: late, out-of-order inputs that force rollbacks must
    /// reconverge to EXACTLY the in-order ground-truth state.
    #[test]
    fn rollback_reconverges_to_ground_truth() {
        let players = vec![PlayerId(0), PlayerId(1)];
        // Authoritative-style log: player 0 presses buttons at ticks 0 and 4;
        // player 1 at tick 1. (default = no buttons otherwise.)
        let log = [
            (PlayerId(0), 0u64, 3u32),
            (PlayerId(1), 1, 5),
            (PlayerId(0), 4, 2),
        ];
        let truth = ground_truth(&players, &log, 10);

        // Now feed the SAME facts but out of order, advancing in between so the
        // engine mispredicts and must roll back.
        let mut eng = RollbackEngine::new(CounterSim::new(), players, 7, &player_cfg(2));

        // tick 0 input known on time
        eng.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        eng.advance_to(Tick(4)); // simulate 0..4 — player 1's tick-1 input is MISSING (predicted default)

        // player 1's tick-1 input arrives LATE (we are already at tick 4) → rollback
        let rolled = eng.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        assert!(rolled, "late correcting input must trigger a rollback");

        eng.advance_to(Tick(4)); // re-establish to tick 4 (advance_to is forward-only; no-op if already there)
                                 // player 0's tick-4 input arrives on time now
        eng.add_input(
            PlayerId(0),
            Tick(4),
            Input {
                buttons: 2,
                axes: vec![],
            },
        );
        eng.advance_to(Tick(10));

        assert_eq!(
            eng.state_hash(),
            truth,
            "rollback path must reconverge to in-order ground truth"
        );
        assert!(eng.stats().rollbacks >= 1);
        assert!(eng.stats().resimulated_ticks >= 1);
    }

    /// A correction for the SAME value must NOT trigger a needless rollback.
    #[test]
    fn correct_prediction_no_rollback() {
        let players = vec![PlayerId(0)];
        let mut eng = RollbackEngine::new(CounterSim::new(), players, 1, &player_cfg(1));
        eng.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 4,
                axes: vec![],
            },
        );
        eng.advance_to(Tick(3)); // ticks 1,2 predict "buttons:4" (repeat last)
                                 // confirm tick 1 with the SAME predicted value
        let rolled = eng.add_input(
            PlayerId(0),
            Tick(1),
            Input {
                buttons: 4,
                axes: vec![],
            },
        );
        assert!(!rolled, "matching confirmation must not roll back");
        assert_eq!(eng.stats().rollbacks, 0);
    }

    #[test]
    fn dynamic_roster_join_is_deterministic_and_order_independent() {
        // Player 0 from tick 0; player 1 joins (effective) at tick 3.
        let mut a = RollbackEngine::new(CounterSim::new(), vec![PlayerId(0)], 0, &player_cfg(8));
        a.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 1,
                axes: vec![],
            },
        );
        a.add_roster_event(PlayerId(1), Tick(3), true);
        a.add_input(
            PlayerId(1),
            Tick(3),
            Input {
                buttons: 10,
                axes: vec![],
            },
        );
        a.advance_to(Tick(5));

        assert_eq!(a.active_roster(Tick(2)), vec![PlayerId(0)]);
        assert_eq!(a.active_roster(Tick(3)), vec![PlayerId(0), PlayerId(1)]);

        // Same events applied in a DIFFERENT order ⇒ identical state.
        let mut b = RollbackEngine::new(CounterSim::new(), vec![PlayerId(0)], 0, &player_cfg(8));
        b.add_roster_event(PlayerId(1), Tick(3), true);
        b.add_input(
            PlayerId(1),
            Tick(3),
            Input {
                buttons: 10,
                axes: vec![],
            },
        );
        b.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 1,
                axes: vec![],
            },
        );
        b.advance_to(Tick(5));
        assert_eq!(a.state_hash(), b.state_hash());
    }

    #[test]
    fn dynamic_capacity_grows_deterministically_for_high_player_ids() {
        let cfg = player_cfg(1); // sim starts sized to a single slot
                                 // Player 5 (well beyond the initial size) joins at tick 0 and acts.
        let run = |swap: bool| {
            let mut e = RollbackEngine::new(CounterSim::new(), vec![PlayerId(0)], 3, &cfg);
            if swap {
                e.add_input(
                    PlayerId(5),
                    Tick(0),
                    Input {
                        buttons: 9,
                        axes: vec![],
                    },
                );
                e.add_roster_event(PlayerId(5), Tick(0), true);
                e.add_input(
                    PlayerId(0),
                    Tick(0),
                    Input {
                        buttons: 2,
                        axes: vec![],
                    },
                );
            } else {
                e.add_roster_event(PlayerId(5), Tick(0), true);
                e.add_input(
                    PlayerId(0),
                    Tick(0),
                    Input {
                        buttons: 2,
                        axes: vec![],
                    },
                );
                e.add_input(
                    PlayerId(5),
                    Tick(0),
                    Input {
                        buttons: 9,
                        axes: vec![],
                    },
                );
            }
            e.advance_to(Tick(2));
            e.state_hash()
        };
        // Order-independent + deterministic even though the sim had to grow.
        assert_eq!(run(false), run(true));

        // And player 5 actually affected state (vs a run without them).
        let mut base = RollbackEngine::new(CounterSim::new(), vec![PlayerId(0)], 3, &cfg);
        base.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 2,
                axes: vec![],
            },
        );
        base.advance_to(Tick(2));
        assert_ne!(
            run(false),
            base.state_hash(),
            "high-id player must change state"
        );
    }

    #[test]
    fn late_roster_event_rolls_back_and_reconverges() {
        // Ground truth: player 1 active (and inputs) from tick 1.
        let mut truth =
            RollbackEngine::new(CounterSim::new(), vec![PlayerId(0)], 0, &player_cfg(8));
        truth.add_roster_event(PlayerId(1), Tick(1), true);
        truth.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 2,
                axes: vec![],
            },
        );
        truth.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 7,
                axes: vec![],
            },
        );
        truth.advance_to(Tick(6));
        let th = truth.state_hash();

        // Learn of the join AFTER simulating past tick 1 → roster rollback,
        // then the late input → input rollback; must still reconverge.
        let mut eng = RollbackEngine::new(CounterSim::new(), vec![PlayerId(0)], 0, &player_cfg(8));
        eng.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 2,
                axes: vec![],
            },
        );
        eng.advance_to(Tick(4));
        assert!(
            eng.add_roster_event(PlayerId(1), Tick(1), true),
            "past roster change rolls back"
        );
        eng.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 7,
                axes: vec![],
            },
        );
        eng.advance_to(Tick(6));
        assert_eq!(
            eng.state_hash(),
            th,
            "roster + input rollback reconverge to truth"
        );
        assert!(eng.stats().rollbacks >= 2);
    }

    #[tokio::test]
    async fn t2_signaling_is_relayed_with_from_and_to() {
        use crate::SignalPayload;
        let room = RoomActor::new(CounterSim::new(), RoomConfig::new("sig", vec![PlayerId(0)]));
        let mut rx = room.subscribe();
        room.relay_signal(
            PlayerId(1),
            PlayerId(2),
            SignalPayload::Offer("v=0...".into()),
        );

        let got = drain(&mut rx);
        let signal = got.iter().find_map(|m| match m {
            ServerMsg::Signal {
                from, to, payload, ..
            } => Some((*from, *to, payload.clone())),
            _ => None,
        });
        assert_eq!(
            signal,
            Some((
                PlayerId(1),
                PlayerId(2),
                SignalPayload::Offer("v=0...".into())
            )),
            "authority relays the signaling payload with from/to so peers can pair"
        );
    }

    #[tokio::test]
    async fn room_dynamic_join_grows_roster_at_effective_tick() {
        let mut cfg = RoomConfig::new("r", vec![]); // empty initial roster
        cfg.capacity = 8;
        cfg.join_delay = 1;
        cfg.snapshot_interval = 0;
        let mut room = RoomActor::new(CounterSim::new(), cfg);
        assert!(room.roster().is_empty());

        room.join(PlayerId(2)); // effective at current(0)+1 = tick 1
        assert!(
            room.roster().is_empty(),
            "not yet active at the current tick"
        );

        room.tick_once(|_| String::new()); // advance to tick 1
        assert_eq!(
            room.roster(),
            vec![PlayerId(2)],
            "active at the effective tick"
        );

        room.leave(PlayerId(2)); // effective at current(1)+1 = tick 2
        room.tick_once(|_| String::new()); // advance to tick 2
        assert!(room.roster().is_empty(), "left at the effective tick");
    }

    #[tokio::test]
    async fn room_bus_broadcasts_final_confirms_and_snapshots() {
        let mut cfg = RoomConfig::new("battle-1", vec![PlayerId(0), PlayerId(1)]);
        cfg.snapshot_interval = 3;
        cfg.max_rollback = 1; // finality lags by exactly 1 tick
        let mut room = RoomActor::new(CounterSim::new(), cfg);

        let mut rx = room.subscribe();
        room.join(PlayerId(0));

        room.submit_input(
            PlayerId(0),
            Tick(0),
            1,
            Input {
                buttons: 1,
                axes: vec![],
            },
        );

        // Tick three times. With max_rollback=1, ticks 0 and 1 finalize (2
        // confirms); a Snapshot fires at the interval boundary (tick 3).
        let mut snap = None;
        for _ in 0..3 {
            if let Some(s) = room.tick_once(|b| format!("blake3-{}", b.len())) {
                snap = Some(s);
            }
        }
        assert!(
            snap.is_some(),
            "durable snapshot must fire at snapshot_interval"
        );

        let mut confirms = 0;
        let mut snapshots = 0;
        let mut welcomes = 0;
        let mut forwarded_inputs = 0;
        while let Ok(msg) = rx.try_recv() {
            match msg {
                ServerMsg::Confirm(_) => confirms += 1,
                ServerMsg::Snapshot(_) => snapshots += 1,
                ServerMsg::Welcome { .. } => welcomes += 1,
                ServerMsg::Input(_) => forwarded_inputs += 1,
                _ => {}
            }
        }
        assert_eq!(welcomes, 1);
        assert_eq!(
            forwarded_inputs, 1,
            "the submitted input is forwarded immediately"
        );
        assert_eq!(
            confirms, 2,
            "only finalized (past-horizon) ticks are confirmed"
        );
        assert_eq!(snapshots, 1, "one Snapshot at the interval boundary");
    }

    /// The advisor's discriminating test: a Confirm must NEVER be emitted for a
    /// tick that a later rollback revises. We mispredict tick 1, let the engine
    /// run, then correct it — and assert no Confirm for tick 1 was emitted
    /// BEFORE the correction, and that the Confirm eventually emitted carries the
    /// CORRECTED (final) hash.
    #[tokio::test]
    async fn confirm_is_never_emitted_for_a_tick_that_later_rolls_back() {
        let players = vec![PlayerId(0), PlayerId(1)];
        let mut cfg = RoomConfig::new("r", players.clone());
        cfg.seed = 7;
        cfg.capacity = 2; // match the 2-slot ground-truth engine
        cfg.max_rollback = 3; // tick 1 stays revisable while current ≤ 4
        cfg.snapshot_interval = 0; // no snapshots in this test
        let mut room = RoomActor::new(CounterSim::new(), cfg);
        let mut rx = room.subscribe();

        room.submit_input(
            PlayerId(0),
            Tick(0),
            1,
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        // Advance to tick 4 WITHOUT player 1's tick-1 input (mispredicts tick 1).
        for _ in 0..4 {
            room.tick_once(|_| String::new());
        }
        // No Confirm for tick 1 may have been emitted yet (it is still revisable).
        for msg in drain(&mut rx) {
            if let ServerMsg::Confirm(c) = msg {
                assert!(
                    c.tick.0 != 1,
                    "tick 1 confirmed before its inputs were final"
                );
            }
        }

        // Late correction for tick 1 → rollback.
        let rolled = room.submit_input(
            PlayerId(1),
            Tick(1),
            1,
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        assert!(rolled, "late correcting input must roll back");

        // Run far enough that tick 1 finalizes, then capture its Confirm.
        for _ in 0..4 {
            room.tick_once(|_| String::new());
        }
        let tick1_confirm = drain(&mut rx)
            .into_iter()
            .find_map(|m| match m {
                ServerMsg::Confirm(c) if c.tick.0 == 1 => Some(c.state_hash),
                _ => None,
            })
            .expect("tick 1 must eventually be confirmed");

        // Ground truth for tick-1 post-state WITH the correction applied.
        let mut truth = RollbackEngine::new(CounterSim::new(), players, 7, &player_cfg(2));
        truth.add_input(
            PlayerId(0),
            Tick(0),
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        truth.add_input(
            PlayerId(1),
            Tick(1),
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        truth.advance_to(Tick(2)); // state AFTER tick 1
        assert_eq!(
            tick1_confirm,
            truth.state_hash().to_vec(),
            "the emitted Confirm must carry the CORRECTED final hash"
        );
    }

    #[tokio::test]
    async fn room_rollback_via_late_input_on_bus() {
        // End-to-end through the actor: a late input still reconverges.
        let players = vec![PlayerId(0), PlayerId(1)];
        let truth = ground_truth(&players, &[(PlayerId(0), 0, 3), (PlayerId(1), 1, 5)], 6);

        let mut cfg = RoomConfig::new("r", players);
        cfg.seed = 7; // match ground_truth's seed
        cfg.capacity = 2; // match the 2-slot ground-truth engine
        cfg.max_rollback = 4; // keep tick 1 revisable while current ≤ 4
        let mut room = RoomActor::new(CounterSim::new(), cfg);
        room.submit_input(
            PlayerId(0),
            Tick(0),
            1,
            Input {
                buttons: 3,
                axes: vec![],
            },
        );
        for _ in 0..4 {
            room.tick_once(|_| String::new());
        }
        let rolled = room.submit_input(
            PlayerId(1),
            Tick(1),
            1,
            Input {
                buttons: 5,
                axes: vec![],
            },
        );
        assert!(rolled);
        for _ in 0..2 {
            room.tick_once(|_| String::new());
        }
        assert_eq!(room.current_tick(), Tick(6));
        assert_eq!(room.state_hash(), truth);
    }

    fn drain(rx: &mut tokio::sync::broadcast::Receiver<ServerMsg>) -> Vec<ServerMsg> {
        let mut out = Vec::new();
        while let Ok(m) = rx.try_recv() {
            out.push(m);
        }
        out
    }
}
