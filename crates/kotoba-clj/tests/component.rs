//! Step 3: Kotoba source → WASM **Component** (`run: func(list<u8>) -> list<u8>`)
//! → instantiated and invoked through `wasmtime::component`.
//!
//! Proves the Canonical-ABI `list<u8>` lift/lower path end-to-end — the same
//! machinery the future kotoba:kais `run(ctx-cbor: list<u8>)` export reuses.
#![cfg(feature = "component")]

use kotoba_clj::component::{
    compile_and_run_component, compile_component_str, compile_component_str_with_reader_target,
};
use kotoba_clj::CljError;
use kotoba_clj::ReaderTarget;

#[test]
fn component_is_real_wasm() {
    let bytes = compile_component_str("(defn run [input] input)").unwrap();
    assert_eq!(
        &bytes[..4],
        b"\0asm",
        "component must be a real wasm binary"
    );
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
fn component_compile_applies_clojure_reader_compat() {
    let src = r#"
        #_ (defn ignored [input] "bad")
        ^:private
        (defn run "entry" [input]
          (if-let [x (str-len '(a b c))]
            (-> input)
            "bad"))
    "#;
    let out = compile_and_run_component(src, b"ok").unwrap();
    assert_eq!(out, b"ok");
}

#[test]
fn component_compile_honors_reader_target() {
    let src = r#"
        (defn run [input]
          #?(:cljs "cljs" :clj "clj" :default "default"))
    "#;
    let component = compile_component_str_with_reader_target(src, ReaderTarget::Cljs).unwrap();
    let out = kotoba_clj::component::run_component(&component, b"ignored").unwrap();
    assert_eq!(out, b"cljs");
}

#[test]
fn component_entry_can_be_multi_arity_defn() {
    let src = r#"
        (defn run
          ([input] input)
          ([input suffix] suffix))
    "#;
    let out = compile_and_run_component(src, b"ok").unwrap();
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

// ---- Step 5 (reduced): the real kotoba:kais `kotoba-node` world -------------

use kotoba_clj::component::{assert_loads, compile_kais_component_str};

const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");

#[test]
fn kais_kotoba_node_component_loads_in_wasmtime() {
    // `(defn run [ctx] …)` → a Component on the *actual* kotoba-node world
    // (run: func(ctx-cbor: list<u8>) -> result<list<u8>, string>). We don't
    // decode ctx (step 4); this proves kotoba-runtime can *load* the artifact —
    // the same wasmtime Component compile path ProgramStore uses.
    let component = compile_kais_component_str(r#"(defn run [ctx] "hello")"#, KAIS_WIT_DIR)
        .expect("compile against kotoba-node world");
    assert_eq!(&component[..4], b"\0asm");
    assert_loads(&component)
        .expect("kotoba-node component must load under wasmtime component model");
}

#[test]
fn kais_entry_can_echo_raw_ctx() {
    // The raw ctx-cbor bytes are handed to the program as its input handle, so
    // an echo program is well-typed against the result<list<u8>,string> ABI.
    let component = compile_kais_component_str("(defn run [ctx] ctx)", KAIS_WIT_DIR).unwrap();
    assert_loads(&component).unwrap();
}

#[test]
fn kais_component_compile_applies_clojure_reader_compat() {
    let component = compile_kais_component_str(
        r#"
        (do
          #_ (defn run [ctx] "bad")
          ^String
          (defn run "entry" [ctx]
            (if-let [quoted (str-len '(ctx payload))]
              (-> ctx)
              "bad")))
        "#,
        KAIS_WIT_DIR,
    )
    .unwrap();
    assert_loads(&component).unwrap();
}
