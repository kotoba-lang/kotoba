//! Step 5b: **live invoke** a Kotoba-compiled `kotoba-node` component through
//! kotoba-runtime's real host (`WasmExecutor`), which binds every `kotoba:kais`
//! interface, instantiates the component, calls `run(ctx-cbor)`, and lifts the
//! `result<list<u8>, string>` return.
//!
//! This is the end-to-end proof that compiled Kotoba runs on kotoba-runtime —
//! and the true test of the hand-emitted Canonical-ABI variant return layout
//! (`[tag:u8=0 @0, ptr @4, len @8]`): if it were wrong, wasmtime's lift would
//! trap or mis-read here, where `assert_loads` (compile-only) could not.
#![cfg(feature = "component")]

use std::collections::HashMap;

use kotoba_clj::component::compile_kais_component_str;
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::WasmExecutor;

const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;

/// Compile `src` to a kotoba-node component and invoke `run(ctx)` via the real
/// `WasmExecutor`, returning the `ok` output bytes.
fn invoke(src: &str, ctx: &[u8]) -> Vec<u8> {
    let component = compile_kais_component_str(src, KAIS_WIT_DIR).expect("compile kotoba-node");
    let exec = WasmExecutor::new(GAS).expect("executor");
    let result = exec
        .execute(
            "kotoba-test-program",
            &component,
            "did:key:z6MkTestAgent",
            ctx.to_vec(),
            Vec::<WitQuad>::new(),
            HashMap::<String, String>::new(),
        )
        .expect("execute run(ctx)");
    result.output_cbor
}

#[test]
fn fixed_output_runs_on_real_executor() {
    // `(defn run [ctx] "hello")` → ok("hello"), regardless of ctx.
    let out = invoke(r#"(defn run [ctx] "hello")"#, b"any-ctx-bytes");
    assert_eq!(out, b"hello");
}

#[test]
fn echoes_ctx_bytes_through_executor() {
    // The raw ctx-cbor bytes the host lowers in are handed to the program as its
    // input handle; echoing returns them verbatim through the result<> ABI.
    let ctx = b"\x82\x01\x02arbitrary ctx bytes \xff\x00";
    let out = invoke("(defn run [ctx] ctx)", ctx);
    assert_eq!(out, ctx);
}

#[test]
fn output_length_matches_input_inspection() {
    // run branches on the ctx length, returning different in-memory literals —
    // exercises str-len on the lowered input plus a data-segment result, all
    // lifted back out by the host.
    let src = r#"
        (defn run [ctx]
          (if (> (str-len ctx) 4) "big" "small"))
    "#;
    assert_eq!(invoke(src, b"hi"), b"small");
    assert_eq!(invoke(src, b"hello world"), b"big");
}
