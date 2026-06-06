//! `WasmComponentSim` — a [`SimHost`](crate::sim::SimHost) backed by a REAL
//! `kotoba:kge` **Component-Model** guest (ADR-2606060001). This is the portable
//! production shape: ONE component runs as server authority here and (future) in
//! the browser via `kotoba-runtime-web`.
//!
//! Built + tested against an actual component (`testdata/kge_counter.wasm`,
//! produced by `testdata/kge-counter-guest` with `cargo component`).
//!
//! Trade-off vs [`crate::wasm_sim::WasmSim`]: the Component Model encapsulates the
//! guest's linear memory, so the per-frame rollback save uses the WIT
//! `snapshot`/`restore` (portable, works in the browser too) rather than a raw
//! memory copy. Correct for rollback; a touch slower than the core-module path.
//!
//! Determinism by construction: the fixture guest is `no_std`, so the component
//! imports NO `wasi:*` — wall-clock/random/sockets are uninstantiable, not merely
//! unused. (The host still wires `wasmtime-wasi` so it can also host std guests;
//! a no-import component simply doesn't use it.)

use wasmtime::component::{Component, Linker};
use wasmtime::{Engine, Store};
use wasmtime_wasi::{ResourceTable, WasiCtx, WasiCtxBuilder, WasiView};

use crate::protocol::{Input, PlayerId, Tick};
use crate::sim::SimHost;

wasmtime::component::bindgen!({
    world: "game",
    path: "wit/kge.wit",
});

use exports::kotoba::kge::kge::Input as WitInput;

#[derive(Debug, thiserror::Error)]
pub enum WasmComponentError {
    #[error("wasm: {0}")]
    Wasm(String),
}

struct HostState {
    table: ResourceTable,
    wasi: WasiCtx,
}

impl WasiView for HostState {
    fn table(&mut self) -> &mut ResourceTable {
        &mut self.table
    }
    fn ctx(&mut self) -> &mut WasiCtx {
        &mut self.wasi
    }
}

/// A `kotoba:kge` component the rollback engine drives.
pub struct WasmComponentSim {
    store: Store<HostState>,
    game: Game,
}

impl WasmComponentSim {
    /// Load + instantiate a `game` component (binary bytes).
    pub fn from_bytes(wasm: impl AsRef<[u8]>) -> Result<Self, WasmComponentError> {
        let mut config = wasmtime::Config::new();
        config.cranelift_nan_canonicalization(true);
        let engine = Engine::new(&config).map_err(|e| WasmComponentError::Wasm(e.to_string()))?;
        let component = Component::from_binary(&engine, wasm.as_ref())
            .map_err(|e| WasmComponentError::Wasm(e.to_string()))?;

        let mut linker = Linker::new(&engine);
        wasmtime_wasi::add_to_linker_sync(&mut linker)
            .map_err(|e| WasmComponentError::Wasm(e.to_string()))?;

        let host = HostState {
            table: ResourceTable::new(),
            wasi: WasiCtxBuilder::new().build(),
        };
        let mut store = Store::new(&engine, host);
        let game = Game::instantiate(&mut store, &component, &linker)
            .map_err(|e| WasmComponentError::Wasm(e.to_string()))?;
        Ok(Self { store, game })
    }

    fn snapshot_bytes(&mut self) -> Vec<u8> {
        // Disjoint field borrows: `self.game` (&) + `self.store` (&mut).
        self.game
            .kotoba_kge_kge()
            .call_snapshot(&mut self.store)
            .expect("kge snapshot trapped")
            .expect("kge snapshot errored")
    }
}

impl SimHost for WasmComponentSim {
    fn init(&mut self, seed: u64, config: &[u8]) {
        self.game
            .kotoba_kge_kge()
            .call_init(&mut self.store, seed, config)
            .expect("kge init trapped")
            .expect("kge init errored");
    }

    fn step(&mut self, tick: Tick, inputs: &[(PlayerId, Input)]) {
        let wit: Vec<WitInput> = inputs
            .iter()
            .map(|(p, i)| WitInput {
                player: p.0,
                buttons: i.buttons,
                axes: i.axes.clone(),
            })
            .collect();
        self.game
            .kotoba_kge_kge()
            .call_step(&mut self.store, tick.0, &wit)
            .expect("kge step trapped")
            .expect("kge step errored");
    }

    // Component memory is encapsulated → the rollback save uses the WIT snapshot
    // (portable; works in the browser too), not a raw memory copy.
    fn save_fast(&mut self) -> Vec<u8> {
        self.snapshot_bytes()
    }

    fn restore_fast(&mut self, snap: &[u8]) {
        self.game
            .kotoba_kge_kge()
            .call_restore(&mut self.store, snap)
            .expect("kge restore trapped")
            .expect("kge restore errored");
    }

    fn snapshot_durable(&mut self) -> Vec<u8> {
        self.snapshot_bytes()
    }

    fn restore_durable(&mut self, blob: &[u8]) {
        self.restore_fast(blob);
    }

    fn state_hash(&mut self) -> [u8; 32] {
        // Host normalizes the guest's canonical state bytes to a fixed digest.
        *blake3::hash(&self.snapshot_bytes()).as_bytes()
    }
}
