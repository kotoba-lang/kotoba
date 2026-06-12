//! Realtime wire protocol (ADR-2606060001).
//!
//! CBOR-framed, room-scoped, tick-ordered. These types travel on the HOT lane
//! only — the per-room broadcast bus and the T1 WebSocket / T2 DataChannel /
//! T3 QUIC transports. They NEVER enter the global KSE Journal, firehose, or
//! gossip mesh; only the low-rate `SnapshotRef` references a cold-lane blob.

use serde::{Deserialize, Serialize};

/// Stable per-room player id (assigned by the control plane on join).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct PlayerId(pub u32);

/// Simulation tick (monotonic from 0 at `init`).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash, Serialize, Deserialize)]
pub struct Tick(pub u64);

impl Tick {
    pub fn next(self) -> Tick {
        Tick(self.0 + 1)
    }
}

/// One player's input for one tick. Mirrors `kotoba:kge` `record input`.
#[derive(Clone, Debug, PartialEq, Default, Serialize, Deserialize)]
pub struct Input {
    pub buttons: u32,
    pub axes: Vec<f32>,
}

/// Fixed-point scale for axis quantization (1/1000 units). The simulation must
/// never read raw `f32` axes — float nondeterminism across engines is exactly
/// what rollback cannot tolerate (ADR-2606060001). Ingress quantizes once.
pub const AXIS_SCALE: i32 = 1000;

impl Input {
    /// Quantize a raw axis to deterministic fixed-point. NaN/Inf collapse to 0,
    /// so a malformed float can never reach simulation state.
    pub fn quantize_axis(v: f32) -> i32 {
        if !v.is_finite() {
            return 0;
        }
        (v.clamp(-1.0, 1.0) * AXIS_SCALE as f32).round() as i32
    }

    /// Deterministic fixed-point view of the axes — the ONLY form a `SimHost`
    /// may consume. Call at the transport ingress boundary.
    pub fn quantized_axes(&self) -> Vec<i32> {
        self.axes.iter().copied().map(Self::quantize_axis).collect()
    }
}

/// Client → authority: a single input frame.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct InputFrame {
    pub room: String,
    pub player: PlayerId,
    pub tick: Tick,
    /// Per-player monotonic sequence — lets the authority drop dup/stale frames.
    pub seq: u64,
    pub input: Input,
}

/// Authority → members: the merged input set for a tick.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct InputBundle {
    pub room: String,
    pub tick: Tick,
    pub inputs: Vec<(PlayerId, Input)>,
}

/// Authority → members: a confirmed tick + canonical state hash (desync detector).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Confirm {
    pub room: String,
    pub tick: Tick,
    #[serde(with = "serde_bytes")]
    pub state_hash: Vec<u8>,
}

/// Authority → members: handle to a cold-lane durable snapshot (for resync).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct SnapshotRef {
    pub room: String,
    pub tick: Tick,
    /// CID (multibase string) of the durable snapshot block in the cold lane.
    pub snapshot_cid: String,
}

/// Membership / presence change.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Presence {
    pub room: String,
    pub player: PlayerId,
    pub joined: bool,
}

/// WebRTC signaling payload (T2). SDP/ICE are opaque strings the authority just
/// relays between two peers over the reliable T1 channel; once the DataChannel is
/// up, it carries the SAME `ClientMsg::Input` / `ServerMsg` frames (UDP-like,
/// loss-tolerant — rollback predicts over gaps). The authority never parses these.
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum SignalPayload {
    Offer(String),
    Answer(String),
    Ice(String),
}

/// Messages a client sends to the authority (T1/T2/T3 ingress).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum ClientMsg {
    Join {
        room: String,
        player: PlayerId,
    },
    Leave {
        room: String,
        player: PlayerId,
    },
    Input(InputFrame),
    /// T2: ask the authority to relay a signaling payload to peer `to`.
    Signal {
        room: String,
        to: PlayerId,
        payload: SignalPayload,
    },
}

/// Messages the authority broadcasts to room members (egress).
#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub enum ServerMsg {
    Welcome {
        room: String,
        player: PlayerId,
        tick: Tick,
    },
    /// Immediate, PROVISIONAL forward of a player's input to all members, so
    /// clients can predict at low latency. Not final — may be superseded.
    Input(InputFrame),
    /// FINAL merged inputs for a confirmed (past-horizon) tick — for replay.
    Bundle(InputBundle),
    /// FINAL state hash for a confirmed tick — the desync detector.
    Confirm(Confirm),
    Snapshot(SnapshotRef),
    Presence(Presence),
    /// T2: a signaling payload relayed from peer `from` to peer `to`. Members
    /// process only those addressed to them.
    Signal {
        room: String,
        from: PlayerId,
        to: PlayerId,
        payload: SignalPayload,
    },
}

/// CBOR encode any protocol value. Stable framing for all transports.
pub fn encode<T: Serialize>(v: &T) -> Result<Vec<u8>, crate::RtError> {
    let mut buf = Vec::new();
    ciborium::ser::into_writer(v, &mut buf).map_err(|e| crate::RtError::Codec(e.to_string()))?;
    Ok(buf)
}

/// CBOR decode any protocol value.
pub fn decode<T: for<'de> Deserialize<'de>>(bytes: &[u8]) -> Result<T, crate::RtError> {
    ciborium::de::from_reader(bytes).map_err(|e| crate::RtError::Codec(e.to_string()))
}
