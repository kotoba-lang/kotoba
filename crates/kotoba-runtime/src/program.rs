use anyhow::Result;
use dashmap::DashMap;
use std::sync::Arc;
use wasmtime::component::Component;

use crate::host::KotobaEngine;

/// ProgramStore caches compiled WASM Components by their program_cid.
///
/// program_cid SHOULD be the content-address of the raw .wasm bytes; the
/// cache is bounded so a long-running pod that loads many distinct programs
/// (e.g. distinct LangGraph actors) cannot grow without bound.  Compiled
/// Components reuse Cranelift JIT output across invocations.
const PROGRAM_CACHE_MAX: usize = 16;

#[derive(Clone)]
pub struct ProgramStore {
    engine: KotobaEngine,
    cache: Arc<DashMap<String, Component>>,
}

impl ProgramStore {
    pub fn new(engine: KotobaEngine) -> Self {
        Self {
            engine,
            cache: Arc::new(DashMap::new()),
        }
    }

    /// Load a compiled Component for `program_cid`.
    /// Caller is responsible for fetching `wasm_bytes` from Vault/Shelf if not cached.
    pub fn get_or_compile(&self, program_cid: &str, wasm_bytes: &[u8]) -> Result<Component> {
        if let Some(cached) = self.cache.get(program_cid) {
            return Ok(cached.clone());
        }
        // Bound the cache to avoid unbounded memory growth.  Each cached
        // Component holds Cranelift-compiled artefacts (~50-200 MB for
        // Python WASM bundles), so 16 entries is the practical ceiling on
        // a 4Gi pod once you account for ~600 MB of live instance memory
        // per active call.  Drop a random entry on overflow — LRU would
        // need per-call bookkeeping; for this access pattern (rare new
        // program loads) random eviction is fine.
        if self.cache.len() >= PROGRAM_CACHE_MAX {
            if let Some(stale) = self.cache.iter().next().map(|e| e.key().clone()) {
                self.cache.remove(&stale);
            }
        }
        let component = self.engine.compile(wasm_bytes)?;
        self.cache
            .insert(program_cid.to_string(), component.clone());
        Ok(component)
    }

    /// Evict a program (e.g., after retracting the program Datom projection)
    pub fn evict(&self, program_cid: &str) {
        self.cache.remove(program_cid);
    }

    pub fn cache_size(&self) -> usize {
        self.cache.len()
    }
}
