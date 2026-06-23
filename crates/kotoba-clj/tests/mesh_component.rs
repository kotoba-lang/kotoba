//! KOTOBA Mesh M7: multi-export component codegen.
//!
//! A Clojure guest that defines `(defn run …)` and `(defn on-http …)` compiles
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
