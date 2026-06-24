//! Standalone runner: instantiate an emitted **core module** with wasmtime and
//! call an exported function with i64 arguments.
//!
//! Phase boundary (see crate docs / ADR): this runs the module on a plain
//! `wasmtime::Engine`. It is **not** the kotoba-runtime Component-Model host —
//! binding these programs to the `kotoba:kais` WIT world (kqe/kse/auth/llm) is
//! phase 2.

use wasmtime::{Engine, Instance, Module, Store, Val};

use crate::CljError;

/// Instantiate `wasm` and call exported function `func` with `args`.
pub fn run(wasm: &[u8], func: &str, args: &[i64]) -> Result<i64, CljError> {
    let engine = Engine::default();
    let module = Module::new(&engine, wasm).map_err(|e| CljError::Run(e.to_string()))?;
    let mut store = Store::new(&engine, ());
    let instance =
        Instance::new(&mut store, &module, &[]).map_err(|e| CljError::Run(e.to_string()))?;
    let f = instance
        .get_func(&mut store, func)
        .ok_or_else(|| CljError::Run(format!("module has no exported function `{func}`")))?;

    let params: Vec<Val> = args.iter().map(|a| Val::I64(*a)).collect();
    let mut results = vec![Val::I64(0)];
    f.call(&mut store, &params, &mut results)
        .map_err(|e| CljError::Run(e.to_string()))?;

    match results.first() {
        Some(Val::I64(v)) => Ok(*v),
        other => Err(CljError::Run(format!("unexpected result kind: {other:?}"))),
    }
}

/// Like [`run`], but bounds execution with wasmtime **fuel** so an unbounded
/// loop in untrusted source cannot hang the host. One fuel unit is consumed per
/// executed wasm instruction; exhausting `fuel` traps with an out-of-fuel error
/// (surfaced as [`CljError::Run`]). Use this on any path that compiles+runs
/// caller-supplied source (e.g. a network endpoint).
pub fn run_with_fuel(wasm: &[u8], func: &str, args: &[i64], fuel: u64) -> Result<i64, CljError> {
    let mut config = wasmtime::Config::new();
    config.consume_fuel(true);
    let engine = Engine::new(&config).map_err(|e| CljError::Run(e.to_string()))?;
    let module = Module::new(&engine, wasm).map_err(|e| CljError::Run(e.to_string()))?;
    let mut store = Store::new(&engine, ());
    store.set_fuel(fuel).map_err(|e| CljError::Run(e.to_string()))?;
    let instance =
        Instance::new(&mut store, &module, &[]).map_err(|e| CljError::Run(e.to_string()))?;
    let f = instance
        .get_func(&mut store, func)
        .ok_or_else(|| CljError::Run(format!("module has no exported function `{func}`")))?;

    let params: Vec<Val> = args.iter().map(|a| Val::I64(*a)).collect();
    let mut results = vec![Val::I64(0)];
    f.call(&mut store, &params, &mut results)
        .map_err(|e| CljError::Run(e.to_string()))?;

    match results.first() {
        Some(Val::I64(v)) => Ok(*v),
        other => Err(CljError::Run(format!("unexpected result kind: {other:?}"))),
    }
}

/// Convenience: compile `src` and immediately run `func(args)`.
pub fn compile_and_run(src: &str, func: &str, args: &[i64]) -> Result<i64, CljError> {
    let wasm = crate::compile_str(src)?;
    run(&wasm, func, args)
}

/// Exercise the linear-memory substrate: instantiate `wasm`, call the exported
/// `cabi_realloc` bump allocator once per `(align, size)` request, then write a
/// `0xAB` pattern across every returned region and read it back — proving the
/// regions are real, writable, and (when the requests exceed the initial pages)
/// that the allocator grew memory rather than trapping.
///
/// Returns the allocated pointers in request order, so callers can assert
/// alignment / monotonicity / non-overlap.
pub fn alloc_probe(wasm: &[u8], requests: &[(i32, i32)]) -> Result<Vec<i32>, CljError> {
    let engine = Engine::default();
    let module = Module::new(&engine, wasm).map_err(|e| CljError::Run(e.to_string()))?;
    let mut store = Store::new(&engine, ());
    let instance =
        Instance::new(&mut store, &module, &[]).map_err(|e| CljError::Run(e.to_string()))?;
    let realloc = instance
        .get_typed_func::<(i32, i32, i32, i32), i32>(&mut store, "cabi_realloc")
        .map_err(|e| CljError::Run(format!("cabi_realloc export: {e}")))?;
    let memory = instance
        .get_memory(&mut store, "memory")
        .ok_or_else(|| CljError::Run("module has no exported `memory`".into()))?;

    // All allocations first (each call briefly borrows the store).
    let mut ptrs = Vec::with_capacity(requests.len());
    for &(align, size) in requests {
        let p = realloc
            .call(&mut store, (0, 0, align, size))
            .map_err(|e| CljError::Run(format!("cabi_realloc trapped: {e}")))?;
        ptrs.push(p);
    }

    // Then a single mutable view of memory to write+verify each region.
    let data = memory.data_mut(&mut store);
    for (i, &(_, size)) in requests.iter().enumerate() {
        let p = ptrs[i] as usize;
        let end = p + size as usize;
        if end > data.len() {
            return Err(CljError::Run(format!(
                "region [{p}, {end}) exceeds memory len {}",
                data.len()
            )));
        }
        data[p..end].iter_mut().for_each(|b| *b = 0xAB);
    }
    for (i, &(_, size)) in requests.iter().enumerate() {
        let p = ptrs[i] as usize;
        if !data[p..p + size as usize].iter().all(|b| *b == 0xAB) {
            return Err(CljError::Run(format!("region {i} not writable/readable")));
        }
    }
    Ok(ptrs)
}
