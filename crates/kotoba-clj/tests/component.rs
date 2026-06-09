//! Step 3: Clojure source → WASM **Component** (`run: func(list<u8>) -> list<u8>`)
//! → instantiated and invoked through `wasmtime::component`.
//!
//! Proves the Canonical-ABI `list<u8>` lift/lower path end-to-end — the same
//! machinery the future kotoba:kais `run(ctx-cbor: list<u8>)` export reuses.
#![cfg(feature = "component")]

use kotoba_clj::component::{compile_and_run_component, compile_component_str};
use kotoba_clj::CljError;

#[test]
fn component_is_real_wasm() {
    let bytes = compile_component_str("(defn run [input] input)").unwrap();
    assert_eq!(&bytes[..4], b"\0asm", "component must be a real wasm binary");
}

#[test]
fn echo_roundtrips_bytes() {
    // The host lowers the input list into guest memory; the guest returns the
    // same (ptr,len) handle; the host lifts it back out.
    let out = compile_and_run_component("(defn run [input] input)", b"hello").unwrap();
    assert_eq!(out, b"hello");
}

#[test]
fn echo_handles_empty_and_binary() {
    let echo = "(defn run [input] input)";
    assert_eq!(compile_and_run_component(echo, b"").unwrap(), b"");
    let bin = &[0u8, 1, 2, 255, 254, 0, 42];
    assert_eq!(compile_and_run_component(echo, bin).unwrap(), bin);
}

#[test]
fn returns_data_segment_literal() {
    // Output handle points into the data segment (not the input buffer) — proves
    // the lift reads arbitrary guest memory, not just the host-lowered input.
    let out = compile_and_run_component(r#"(defn run [input] "ok")"#, b"ignored").unwrap();
    assert_eq!(out, b"ok");
}

#[test]
fn entry_can_inspect_input_then_branch() {
    // run uses the input length to choose which literal to return — exercises
    // the input handle (str-len) and a memory-resident result together.
    let src = r#"
        (defn run [input]
          (if (> (str-len input) 3) "long" "short"))
    "#;
    assert_eq!(compile_and_run_component(src, b"hi").unwrap(), b"short");
    assert_eq!(compile_and_run_component(src, b"hello").unwrap(), b"long");
}

#[test]
fn missing_run_entry_is_an_error() {
    let err = compile_component_str("(defn f [x] x)").unwrap_err();
    assert!(matches!(err, CljError::Codegen(_)), "got: {err:?}");
}

#[test]
fn run_must_be_arity_one() {
    let err = compile_component_str("(defn run [a b] (+ a b))").unwrap_err();
    assert!(matches!(err, CljError::Codegen(_)), "got: {err:?}");
}
