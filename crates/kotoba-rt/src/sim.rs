//! The `SimHost` seam — the deterministic simulation behind the rollback engine.
//!
//! This is the Rust-side mirror of the `kotoba:kge` WIT contract
//! (`wit/kge.wit`). The rollback engine is generic over this trait so the core
//! netcode is fully testable WITHOUT the WASM runtime; the production
//! implementation (`WasmSim`, future) wraps a `kotoba:kge` component and maps
//! `save_fast`/`restore_fast` onto a direct linear-memory copy.
//!
//! DETERMINISM CONTRACT: `step` MUST be a pure function of
//! (previous-state, inputs). No wall-clock, no host RNG, no I/O. Two hosts that
//! `init` with the same seed and apply the same input sequence MUST produce
//! byte-identical `state_hash` at every tick — that is the whole basis of
//! rollback reconciliation.

use crate::protocol::{Input, PlayerId, Tick};

/// A deterministic simulation the rollback engine drives.
pub trait SimHost {
    /// Deterministic init from a shared seed + opaque match config.
    fn init(&mut self, seed: u64, config: &[u8]);

    /// Advance exactly one tick. Pure over (state, inputs).
    /// `inputs` is sorted by `PlayerId` by the caller for determinism.
    fn step(&mut self, tick: Tick, inputs: &[(PlayerId, Input)]);

    /// FAST rollback save (hot path, per frame). In the core-module WASM impl
    /// this is a raw linear-memory copy; in the Component-Model impl it is the
    /// WIT `snapshot` (memory is encapsulated). `&mut self` because a component
    /// call needs `&mut Store`. Bytes are opaque to `restore_fast`.
    fn save_fast(&mut self) -> Vec<u8>;
    fn restore_fast(&mut self, snap: &[u8]);

    /// DURABLE snapshot (cold path, per snapshot interval): canonical,
    /// content-addressable. This is what gets committed / pinned / replayed.
    fn snapshot_durable(&mut self) -> Vec<u8>;
    fn restore_durable(&mut self, blob: &[u8]);

    /// Canonical state hash — the desync detector. Equal hash ⇒ equal state.
    fn state_hash(&mut self) -> [u8; 32];
}

/// Blanket impl so a `Box<dyn SimHost + Send>` is itself a `SimHost` — lets a
/// server room registry hold either `CounterSim` or `WasmComponentSim` behind one
/// type (the room-registry swap). `SimHost` is object-safe (no generics, no
/// `Self` returns), so this just forwards.
impl SimHost for Box<dyn SimHost + Send> {
    fn init(&mut self, seed: u64, config: &[u8]) {
        (**self).init(seed, config)
    }
    fn step(&mut self, tick: Tick, inputs: &[(PlayerId, Input)]) {
        (**self).step(tick, inputs)
    }
    fn save_fast(&mut self) -> Vec<u8> {
        (**self).save_fast()
    }
    fn restore_fast(&mut self, snap: &[u8]) {
        (**self).restore_fast(snap)
    }
    fn snapshot_durable(&mut self) -> Vec<u8> {
        (**self).snapshot_durable()
    }
    fn restore_durable(&mut self, blob: &[u8]) {
        (**self).restore_durable(blob)
    }
    fn state_hash(&mut self) -> [u8; 32] {
        (**self).state_hash()
    }
}

/// Reference deterministic simulation used by tests and as the contract example.
///
/// State = one accumulator per player. Each tick folds every player's `buttons`
/// weighted by `(tick+1)` so that a misprediction at tick T that is NOT
/// corrected leaves a permanently different final state — which is exactly what
/// makes the rollback tests meaningful (a wrong-then-corrected input must
/// reconverge to the ground-truth state).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CounterSim {
    seed: u64,
    acc: Vec<i64>,
}

impl CounterSim {
    pub fn new() -> Self {
        Self {
            seed: 0,
            acc: Vec::new(),
        }
    }

    /// Number of players (accumulator slots).
    pub fn players(&self) -> usize {
        self.acc.len()
    }

    /// Read a player's accumulator (test introspection).
    pub fn value(&self, player: PlayerId) -> i64 {
        self.acc.get(player.0 as usize).copied().unwrap_or(0)
    }
}

impl Default for CounterSim {
    fn default() -> Self {
        Self::new()
    }
}

impl SimHost for CounterSim {
    fn init(&mut self, seed: u64, config: &[u8]) {
        // config[0..4] LE = player count (defaults to 2 when absent).
        let n = if config.len() >= 4 {
            u32::from_le_bytes([config[0], config[1], config[2], config[3]]) as usize
        } else {
            2
        };
        self.seed = seed;
        self.acc = vec![seed as i64; n];
    }

    fn step(&mut self, tick: Tick, inputs: &[(PlayerId, Input)]) {
        let weight = (tick.0 as i64).wrapping_add(1);
        for (player, input) in inputs {
            let idx = player.0 as usize;
            if idx >= self.acc.len() {
                // Dynamic capacity: grow deterministically, new slots seeded the
                // same as `init` so every peer that reaches this player id holds
                // byte-identical state (and rollback re-sim reproduces it).
                self.acc.resize(idx + 1, self.seed as i64);
            }
            // Integer-only, order-independent per player, tick-weighted. Axes are
            // consumed via the deterministic fixed-point view ONLY — raw f32
            // (incl. NaN/Inf) can never reach state. This is what makes the sim
            // safe for cross-engine rollback.
            let axis_sum: i64 = input.quantized_axes().iter().map(|q| *q as i64).sum();
            let delta = (input.buttons as i64)
                .wrapping_add(axis_sum)
                .wrapping_mul(weight);
            self.acc[idx] = self.acc[idx].wrapping_add(delta);
        }
    }

    fn save_fast(&mut self) -> Vec<u8> {
        // "Linear-memory-like" fast image: seed + raw LE accumulators.
        let mut out = Vec::with_capacity(8 + self.acc.len() * 8);
        out.extend_from_slice(&self.seed.to_le_bytes());
        for v in &self.acc {
            out.extend_from_slice(&v.to_le_bytes());
        }
        out
    }

    fn restore_fast(&mut self, snap: &[u8]) {
        assert!(snap.len() >= 8, "kotoba-rt: corrupt fast snapshot");
        self.seed = u64::from_le_bytes(snap[0..8].try_into().unwrap());
        let body = &snap[8..];
        let n = body.len() / 8;
        self.acc = (0..n)
            .map(|i| i64::from_le_bytes(body[i * 8..i * 8 + 8].try_into().unwrap()))
            .collect();
    }

    fn snapshot_durable(&mut self) -> Vec<u8> {
        // Canonical encoding for the cold lane (here: same as fast image; the
        // WASM impl would use canonical DAG-CBOR of guest-defined state).
        self.save_fast()
    }

    fn restore_durable(&mut self, blob: &[u8]) {
        self.restore_fast(blob);
    }

    fn state_hash(&mut self) -> [u8; 32] {
        // Hash the canonical (durable) image so the detector matches the
        // replayable state, not the engine's transient layout.
        *blake3::hash(&self.snapshot_durable()).as_bytes()
    }
}
