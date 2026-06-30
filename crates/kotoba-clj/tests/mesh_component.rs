//! KOTOBA Mesh M7: multi-export component codegen.
//!
//! A Kotoba guest that defines `(defn run …)` and `(defn on-http …)` compiles
//! to a single WASM component exporting BOTH, targeting the `kotoba-component`
//! world. A run-only guest falls back to the `kotoba-node` world (unchanged).

use kotoba_clj::component::{assert_loads, compile_kais_mesh_component_str};

const WIT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");

#[test]
fn mesh_component_with_on_http_loads_under_wasmtime() {
    // `run` + `on-http` → kotoba-component world, both exports present
    let src = "(ns m) (defn run [ctx] ctx) (defn on-http [req] req)";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile mesh component");
    assert_eq!(&wasm[0..4], b"\0asm", "must be a real wasm component");
    assert_loads(&wasm).expect("component (run + on-http) must load under wasmtime");
}

#[test]
fn run_only_guest_falls_back_to_kotoba_node_world() {
    let src = "(ns m) (defn run [ctx] ctx)";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile run-only");
    assert_loads(&wasm).expect("run-only component must still load");
}

#[test]
fn mesh_component_requires_a_run_export() {
    // on-http without run is rejected (run is the mandatory generic entry)
    let src = "(ns m) (defn on-http [req] req)";
    assert!(compile_kais_mesh_component_str(src, WIT).is_err());
}

#[test]
fn mesh_component_bad_wit_dir_errors_gracefully() {
    // a missing WIT package surfaces as an Err (push_dir / select_world), no panic
    let src = "(ns m) (defn run [ctx] ctx) (defn on-http [req] req)";
    assert!(compile_kais_mesh_component_str(src, "/no/such/wit/dir").is_err());
}

#[test]
fn mesh_component_with_shared_helper_fns_compiles() {
    // both entries calling a shared helper must coexist with the multi-export wrappers
    let src = "(ns m) (defn helper [x] x) \
               (defn run [ctx] (helper ctx)) \
               (defn on-http [req] (helper req))";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile with helper");
    assert_loads(&wasm).expect("run + on-http + helper must load");
}

#[test]
fn mesh_component_compile_is_byte_deterministic() {
    // same source → identical bytes → stable content-address (CID)
    let src = "(ns m) (defn run [ctx] ctx) (defn on-http [req] req)";
    let a = compile_kais_mesh_component_str(src, WIT).unwrap();
    let b = compile_kais_mesh_component_str(src, WIT).unwrap();
    assert_eq!(a, b, "mesh component compile must be deterministic");
}

#[test]
fn export_mapping_is_independent_of_defn_order() {
    // entries are resolved by name lookup, so defining on-http BEFORE run must
    // still bind each export to the correct user fn (loads = encoder validated
    // both exports against the kotoba-component world).
    let reversed = "(ns m) (defn on-http [req] req) (defn run [ctx] ctx)";
    let normal = "(ns m) (defn run [ctx] ctx) (defn on-http [req] req)";
    let a = compile_kais_mesh_component_str(reversed, WIT).expect("reversed-order compile");
    assert_loads(&a).expect("reversed-order component loads");
    // declaration order changes the module's fn layout, but both are valid
    // kotoba-component components exporting run + on-http
    let b = compile_kais_mesh_component_str(normal, WIT).expect("normal-order compile");
    assert_loads(&b).expect("normal-order component loads");
}

#[test]
fn mesh_component_using_host_imports_compiles() {
    // both entries call a kotoba:kais/kqe host import — this proves the new
    // `kotoba-component` world declares the IMPORTS correctly (the encoder
    // matches the module's kqe import against the world), not just the exports.
    let src = "(ns m) \
               (defn run [ctx] (kqe-assert! \"g\" \"run\" \"k\" \"v\")) \
               (defn on-http [req] (kqe-assert! \"g\" \"http\" \"k\" \"v\"))";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile with host imports");
    assert_loads(&wasm).expect("multi-export component using a kqe import must load");
}

#[test]
fn unsupported_handler_defn_does_not_break_compilation() {
    // on-kse isn't a wired export yet (different arity); as a plain defn it must
    // not be exported, and the component still compiles as run + on-http.
    let src = "(ns m) (defn run [ctx] ctx) \
               (defn on-http [req] req) \
               (defn on-kse [topic payload] payload)";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile with extra defn");
    assert_loads(&wasm).expect("loads; on-kse is just an unexported helper");
}

// ── M8: on-tick (cron) trigger — new (i64)->result ABI, kotoba-cron world ──

#[test]
fn cron_component_with_on_tick_loads_under_wasmtime() {
    // run + on-tick → kotoba-cron world; on-tick takes a u64 epoch directly
    let src = "(ns m) (defn run [ctx] ctx) (defn on-tick [epoch] \"ok\")";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile cron component");
    assert_eq!(&wasm[0..4], b"\0asm", "must be a real wasm component");
    assert_loads(&wasm).expect("run + on-tick must load under wasmtime");
}

#[test]
fn on_tick_routes_to_cron_world_independently_of_on_http() {
    // on-tick present, on-http absent → kotoba-cron (not kotoba-component)
    let with_tick = "(ns m) (defn run [c] c) (defn on-tick [t] \"x\")";
    assert!(compile_kais_mesh_component_str(with_tick, WIT).is_ok());
    // plain run-only still falls back to kotoba-node
    let run_only = "(ns m) (defn run [c] c)";
    assert!(compile_kais_mesh_component_str(run_only, WIT).is_ok());
}

// ── M9: on-kse (KSE topic) trigger — 2-arg (string,list<u8>)->result ABI ──

#[test]
fn kse_component_with_on_kse_loads_under_wasmtime() {
    // run + on-kse (arity 2) → kotoba-kse world
    let src = "(ns m) (defn run [c] c) (defn on-kse [topic payload] payload)";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile kse component");
    assert_eq!(&wasm[0..4], b"\0asm", "must be a real wasm component");
    assert_loads(&wasm).expect("run + on-kse must load under wasmtime");
}

#[test]
fn on_kse_routes_to_kse_world_by_arity2() {
    // on-kse (arity 2), no on-http/on-tick → kotoba-kse
    let src = "(ns m) (defn run [c] c) (defn on-kse [t p] p)";
    assert!(compile_kais_mesh_component_str(src, WIT).is_ok());
}

// ── M10: combined kotoba-mesh world — multiple triggers in one component ──

#[test]
fn mesh_component_with_all_three_triggers_loads_under_wasmtime() {
    let src = "(ns m) (defn run [c] c) \
               (defn on-http [r] r) \
               (defn on-tick [e] \"\") \
               (defn on-kse [t p] p)";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile combined component");
    assert_eq!(&wasm[0..4], b"\0asm");
    assert_loads(&wasm).expect("run + on-http + on-tick + on-kse must load");
}

#[test]
fn mesh_component_two_triggers_synthesizes_stub_for_the_third() {
    // on-http + on-tick defined; on-kse auto-stubbed → kotoba-mesh world
    let src = "(ns m) (defn run [c] c) (defn on-http [r] r) (defn on-tick [e] \"\")";
    let wasm = compile_kais_mesh_component_str(src, WIT).expect("compile 2-trigger component");
    assert_loads(&wasm).expect("2 real triggers + 1 synthesized stub must load");
}
