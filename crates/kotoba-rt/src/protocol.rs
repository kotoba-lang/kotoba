//! Realtime wire protocol (ADR-2606060001).
//!
//! CBOR-framed, room-scoped, tick-ordered. These types travel on the HOT lane
//! only — the per-room broadcast bus and the T1 WebSocket / T2 DataChannel /
//! T3 QUIC transports. They NEVER enter the global KSE Journal, firehose, or
//! gossip mesh; only the low-rate `SnapshotRef` references a cold-lane blob.

use serde::{Deserialize, Serialize};
use std::io::Cursor;

/// Maximum encoded realtime frame size accepted at the transport boundary.
/// Realtime gossip/WebSocket frames should stay small; snapshots live on the
/// cold lane and are referenced by CID instead of embedded here.
pub const MAX_RT_FRAME_BYTES: usize = 256 * 1024;
pub const MAX_ROOM_BYTES: usize = 128;
pub const MAX_AXES: usize = 16;
pub const MAX_BUNDLE_INPUTS: usize = 1024;
pub const MAX_STATE_HASH_BYTES: usize = 64;
pub const MAX_SNAPSHOT_CID_BYTES: usize = 256;
pub const MAX_SIGNAL_PAYLOAD_BYTES: usize = 64 * 1024;

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

pub trait WireMessage: Sized {
    fn validate_wire(&self) -> Result<(), crate::RtError>;
}

fn codec_error(message: impl Into<String>) -> crate::RtError {
    crate::RtError::Codec(message.into())
}

fn validate_room(room: &str) -> Result<(), crate::RtError> {
    if room.is_empty() {
        return Err(codec_error("room must not be empty"));
    }
    if room.len() > MAX_ROOM_BYTES {
        return Err(codec_error(format!(
            "room exceeds {MAX_ROOM_BYTES} byte limit"
        )));
    }
    if room.bytes().any(|b| b.is_ascii_control()) {
        return Err(codec_error("room contains control byte"));
    }
    Ok(())
}

fn validate_input(input: &Input) -> Result<(), crate::RtError> {
    if input.axes.len() > MAX_AXES {
        return Err(codec_error(format!(
            "input axes exceeds {MAX_AXES} entry limit"
        )));
    }
    Ok(())
}

fn validate_input_frame(frame: &InputFrame) -> Result<(), crate::RtError> {
    validate_room(&frame.room)?;
    validate_input(&frame.input)
}

fn validate_signal_payload(payload: &SignalPayload) -> Result<(), crate::RtError> {
    let bytes = match payload {
        SignalPayload::Offer(s) | SignalPayload::Answer(s) | SignalPayload::Ice(s) => s.len(),
    };
    if bytes > MAX_SIGNAL_PAYLOAD_BYTES {
        return Err(codec_error(format!(
            "signal payload exceeds {MAX_SIGNAL_PAYLOAD_BYTES} byte limit"
        )));
    }
    Ok(())
}

impl WireMessage for ClientMsg {
    fn validate_wire(&self) -> Result<(), crate::RtError> {
        match self {
            ClientMsg::Join { room, .. } | ClientMsg::Leave { room, .. } => validate_room(room),
            ClientMsg::Input(frame) => validate_input_frame(frame),
            ClientMsg::Signal { room, payload, .. } => {
                validate_room(room)?;
                validate_signal_payload(payload)
            }
        }
    }
}

impl WireMessage for ServerMsg {
    fn validate_wire(&self) -> Result<(), crate::RtError> {
        match self {
            ServerMsg::Welcome { room, .. } => validate_room(room),
            ServerMsg::Input(frame) => validate_input_frame(frame),
            ServerMsg::Bundle(bundle) => bundle.validate_wire(),
            ServerMsg::Confirm(confirm) => confirm.validate_wire(),
            ServerMsg::Snapshot(snapshot) => snapshot.validate_wire(),
            ServerMsg::Presence(presence) => presence.validate_wire(),
            ServerMsg::Signal { room, payload, .. } => {
                validate_room(room)?;
                validate_signal_payload(payload)
            }
        }
    }
}

impl WireMessage for InputBundle {
    fn validate_wire(&self) -> Result<(), crate::RtError> {
        validate_room(&self.room)?;
        if self.inputs.len() > MAX_BUNDLE_INPUTS {
            return Err(codec_error(format!(
                "input bundle exceeds {MAX_BUNDLE_INPUTS} entry limit"
            )));
        }
        for (_, input) in &self.inputs {
            validate_input(input)?;
        }
        Ok(())
    }
}

impl WireMessage for Confirm {
    fn validate_wire(&self) -> Result<(), crate::RtError> {
        validate_room(&self.room)?;
        if self.state_hash.is_empty() || self.state_hash.len() > MAX_STATE_HASH_BYTES {
            return Err(codec_error(format!(
                "state hash must be 1..={MAX_STATE_HASH_BYTES} bytes"
            )));
        }
        Ok(())
    }
}

impl WireMessage for SnapshotRef {
    fn validate_wire(&self) -> Result<(), crate::RtError> {
        validate_room(&self.room)?;
        if self.snapshot_cid.is_empty() || self.snapshot_cid.len() > MAX_SNAPSHOT_CID_BYTES {
            return Err(codec_error(format!(
                "snapshot CID must be 1..={MAX_SNAPSHOT_CID_BYTES} bytes"
            )));
        }
        Ok(())
    }
}

impl WireMessage for Presence {
    fn validate_wire(&self) -> Result<(), crate::RtError> {
        validate_room(&self.room)
    }
}

/// CBOR encode any protocol value. Stable framing for all transports.
pub fn encode<T: Serialize + WireMessage>(v: &T) -> Result<Vec<u8>, crate::RtError> {
    v.validate_wire()?;
    let mut buf = Vec::new();
    ciborium::ser::into_writer(v, &mut buf).map_err(|e| crate::RtError::Codec(e.to_string()))?;
    if buf.len() > MAX_RT_FRAME_BYTES {
        return Err(codec_error(format!(
            "realtime frame exceeds {MAX_RT_FRAME_BYTES} byte limit"
        )));
    }
    Ok(buf)
}

/// CBOR decode any protocol value.
pub fn decode<T: for<'de> Deserialize<'de> + WireMessage>(
    bytes: &[u8],
) -> Result<T, crate::RtError> {
    if bytes.len() > MAX_RT_FRAME_BYTES {
        return Err(codec_error(format!(
            "realtime frame exceeds {MAX_RT_FRAME_BYTES} byte limit"
        )));
    }
    let mut cursor = Cursor::new(bytes);
    let value: T =
        ciborium::de::from_reader(&mut cursor).map_err(|e| crate::RtError::Codec(e.to_string()))?;
    if cursor.position() != bytes.len() as u64 {
        return Err(codec_error("trailing bytes after realtime frame"));
    }
    value.validate_wire()?;
    Ok(value)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn raw_cbor<T: Serialize>(value: &T) -> Vec<u8> {
        let mut bytes = Vec::new();
        ciborium::ser::into_writer(value, &mut bytes).unwrap();
        bytes
    }

    #[test]
    fn decode_rejects_oversized_frame_before_cbor() {
        let bytes = vec![0u8; MAX_RT_FRAME_BYTES + 1];
        let err = decode::<ClientMsg>(&bytes).unwrap_err();
        assert!(
            err.to_string().contains("frame exceeds"),
            "error should mention frame cap: {err}"
        );
    }

    #[test]
    fn decode_rejects_trailing_bytes_after_cbor_item() {
        let msg = ClientMsg::Join {
            room: "arena".into(),
            player: PlayerId(1),
        };
        let mut bytes = encode(&msg).unwrap();
        bytes.push(0);

        let err = decode::<ClientMsg>(&bytes).unwrap_err();
        assert!(
            err.to_string().contains("trailing bytes"),
            "error should mention trailing bytes: {err}"
        );
    }

    #[test]
    fn decode_rejects_too_many_axes() {
        let msg = ClientMsg::Input(InputFrame {
            room: "arena".into(),
            player: PlayerId(1),
            tick: Tick(0),
            seq: 1,
            input: Input {
                buttons: 0,
                axes: vec![0.0; MAX_AXES + 1],
            },
        });

        let err = decode::<ClientMsg>(&raw_cbor(&msg)).unwrap_err();
        assert!(
            err.to_string().contains("axes exceeds"),
            "error should mention axes cap: {err}"
        );
    }

    #[test]
    fn encode_rejects_oversized_signal_payload() {
        let msg = ClientMsg::Signal {
            room: "arena".into(),
            to: PlayerId(2),
            payload: SignalPayload::Offer("x".repeat(MAX_SIGNAL_PAYLOAD_BYTES + 1)),
        };

        let err = encode(&msg).unwrap_err();
        assert!(
            err.to_string().contains("signal payload exceeds"),
            "error should mention signal cap: {err}"
        );
    }

    #[test]
    fn decode_rejects_empty_room() {
        let msg = ServerMsg::Presence(Presence {
            room: String::new(),
            player: PlayerId(1),
            joined: true,
        });

        let err = decode::<ServerMsg>(&raw_cbor(&msg)).unwrap_err();
        assert!(
            err.to_string().contains("room must not be empty"),
            "error should mention room validation: {err}"
        );
    }
}
