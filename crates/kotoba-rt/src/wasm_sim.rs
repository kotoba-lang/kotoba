//! `WasmSim` — a [`SimHost`](crate::sim::SimHost) backed by a real WASM guest
//! that the host drives, with per-frame rollback via a **direct linear-memory
//! snapshot** (ADR-2606060001). This is the load-bearing proof of the design's
//! central claim: the same deterministic guest runs as server authority and
//! (future) browser prediction, and the host rewinds it by copying its linear
//! memory — never by serializing state across the boundary per frame.
//!
//! ## Scope (honest)
//!
//! Production targets the **Component Model** (`kotoba:kge`, `wit/kge.wit`) so
//! one component is portable to `kotoba-runtime` (server) and
//! `kotoba-runtime-web` (browser). Building/loading a *component* needs the
//! `wasm32-wasip2` + `cargo-component` toolchain, which is not assumed here, so
//! this module drives a **core wasm module** over a small ABI that MIRRORS the
//! `kge` contract:
//!
//! | kge (component)            | core-module ABI (here)                     |
//! |----------------------------|--------------------------------------------|
//! | `init(seed, config)`       | `init(seed: i64)`                          |
//! | `step(tick, inputs)`       | `set_input(player,buttons)*` then `step(tick)` |
//! | `snapshot()`/`restore()`   | read/write the `[state_ptr, +state_len)` region |
//! | host linear-memory rollback| `save_fast`/`restore_fast` copy whole memory |
//! | `state-hash()`             | host blake3 over the state region          |
//!
//! Swapping this for the Component Model executor (reusing kotoba-runtime's
//! dynamic-`Val` dispatch) is the remaining production step; the `SimHost` seam
//! means the rollback engine and room actor do not change.

use wasmtime::{Engine, Instance, Memory, Module, Store, TypedFunc};

use crate::protocol::{Input, PlayerId, Tick};
use crate::sim::SimHost;

/// Error constructing a `WasmSim`.
#[derive(Debug, thiserror::Error)]
pub enum WasmSimError {
    #[error("wasm: {0}")]
    Wasm(String),
}

/// A guest-driven deterministic simulation.
pub struct WasmSim {
    store: Store<()>,
    memory: Memory,
    f_init: TypedFunc<i64, ()>,
    f_set_input: TypedFunc<(i64, i64), ()>,
    f_step: TypedFunc<i64, ()>,
    state_ptr: usize,
    state_len: usize,
}

impl WasmSim {
    /// Compile + instantiate a core wasm module (binary or WAT text) exporting
    /// the ABI above plus a `memory`. Deterministic config (NaN canonicalization
    /// on; threads/SIMD off by default).
    pub fn from_bytes(wasm: impl AsRef<[u8]>) -> Result<Self, WasmSimError> {
        let mut config = wasmtime::Config::new();
        config.cranelift_nan_canonicalization(true);
        let engine = Engine::new(&config).map_err(|e| WasmSimError::Wasm(e.to_string()))?;
        let module = Module::new(&engine, wasm).map_err(|e| WasmSimError::Wasm(e.to_string()))?;
        let mut store = Store::new(&engine, ());
        // The `game` world imports nothing → no linker entries required.
        let instance = Instance::new(&mut store, &module, &[])
            .map_err(|e| WasmSimError::Wasm(e.to_string()))?;

        let memory = instance
            .get_memory(&mut store, "memory")
            .ok_or_else(|| WasmSimError::Wasm("guest exports no `memory`".into()))?;
        let f_init = instance
            .get_typed_func::<i64, ()>(&mut store, "init")
            .map_err(|e| WasmSimError::Wasm(e.to_string()))?;
        let f_set_input = instance
            .get_typed_func::<(i64, i64), ()>(&mut store, "set_input")
            .map_err(|e| WasmSimError::Wasm(e.to_string()))?;
        let f_step = instance
            .get_typed_func::<i64, ()>(&mut store, "step")
            .map_err(|e| WasmSimError::Wasm(e.to_string()))?;
        let f_state_ptr = instance
            .get_typed_func::<(), i32>(&mut store, "state_ptr")
            .map_err(|e| WasmSimError::Wasm(e.to_string()))?;
        let f_state_len = instance
            .get_typed_func::<(), i32>(&mut store, "state_len")
            .map_err(|e| WasmSimError::Wasm(e.to_string()))?;

        let state_ptr = f_state_ptr
            .call(&mut store, ())
            .map_err(|e| WasmSimError::Wasm(e.to_string()))? as usize;
        let state_len = f_state_len
            .call(&mut store, ())
            .map_err(|e| WasmSimError::Wasm(e.to_string()))? as usize;

        Ok(Self {
            store,
            memory,
            f_init,
            f_set_input,
            f_step,
            state_ptr,
            state_len,
        })
    }

    fn state_region(&self) -> &[u8] {
        &self.memory.data(&self.store)[self.state_ptr..self.state_ptr + self.state_len]
    }
}

impl SimHost for WasmSim {
    fn init(&mut self, seed: u64, _config: &[u8]) {
        self.f_init
            .call(&mut self.store, seed as i64)
            .expect("kge guest init trapped");
    }

    fn step(&mut self, tick: Tick, inputs: &[(PlayerId, Input)]) {
        for (player, input) in inputs {
            // Quantized fixed-point axes fold into the staged scalar — raw f32
            // (incl. NaN/Inf) never reaches the guest (determinism).
            let axis_sum: i64 = input.quantized_axes().iter().map(|q| *q as i64).sum();
            let buttons = input.buttons as i64 + axis_sum;
            self.f_set_input
                .call(&mut self.store, (player.0 as i64, buttons))
                .expect("kge guest set_input trapped");
        }
        self.f_step
            .call(&mut self.store, tick.0 as i64)
            .expect("kge guest step trapped");
    }

    fn save_fast(&mut self) -> Vec<u8> {
        // The ADR's per-frame rollback save: a direct copy of the guest's whole
        // linear memory. No guest call, no serialization.
        self.memory.data(&self.store).to_vec()
    }

    fn restore_fast(&mut self, snap: &[u8]) {
        // Write the saved image back over the whole linear memory.
        let dst = self.memory.data_mut(&mut self.store);
        let n = snap.len().min(dst.len());
        dst[..n].copy_from_slice(&snap[..n]);
    }

    fn snapshot_durable(&mut self) -> Vec<u8> {
        // Canonical, content-addressable: just the state region.
        self.state_region().to_vec()
    }

    fn restore_durable(&mut self, blob: &[u8]) {
        let ptr = self.state_ptr;
        let len = self.state_len.min(blob.len());
        let dst = self.memory.data_mut(&mut self.store);
        dst[ptr..ptr + len].copy_from_slice(&blob[..len]);
    }

    fn state_hash(&mut self) -> [u8; 32] {
        *blake3::hash(self.state_region()).as_bytes()
    }
}
