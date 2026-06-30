//! Stage C-2: a Kotoba-compiled guest calls `llm.infer` — a host import whose
//! `result<list<u8>, string>` return uses the indirect **return-area** ABI (the
//! step beyond C-1's direct-result `has-capability`). This is the primitive a
//! langgraph node needs: `(llm-infer model prompt)` → model output bytes.
//!
//! Two live paths through the real `WasmExecutor`:
//!   - **ok** — an injected inference engine returns text; the guest lifts it
//!     out of the return area and returns it.
//!   - **err** — the default executor has no engine, so `infer` returns the
//!     `err` variant; the guest reads the `0` sentinel and returns "ERR".
#![cfg(feature = "component")]

use std::collections::HashMap;
use std::sync::Arc;

use kotoba_clj::component::compile_kais_component_str;
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::WasmExecutor;

const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;
const AGENT: &str = "did:key:z6MkTestAgent";

/// A one-node "agent": call the model, returning its output verbatim — or "ERR"
/// if inference failed (the `0` sentinel).
const SRC: &str = r#"
    (defn run [ctx]
      (let [out (llm-infer "model-cid-xyz" "ping")]
        (if (= out 0) "ERR" out)))
"#;

fn component() -> Vec<u8> {
    compile_kais_component_str(SRC, KAIS_WIT_DIR).expect("compile + encode")
}

fn run_on(exec: &WasmExecutor) -> Vec<u8> {
    exec.execute(
        "kotoba-llm-infer-test",
        &component(),
        AGENT,
        b"ctx".to_vec(),
        Vec::<WitQuad>::new(),
        HashMap::new(),
    )
    .expect("execute run(ctx)")
    .output_cbor
}

#[test]
fn ok_path_lifts_model_output() {
    // Injected engine: ignore the prompt, return a fixed reply. Proves the
    // return-area `ok` variant is read back correctly as a string handle.
    let engine = Arc::new(|_prompt: &str, _max: usize| Ok("PONG".to_string()));
    let exec = WasmExecutor::with_inference(GAS, engine).expect("executor");
    assert_eq!(run_on(&exec), b"PONG");
}

#[test]
fn ok_path_echoes_prompt_bytes() {
    // Engine echoes the prompt it received → confirms the guest lowered the
    // prompt bytes into the call correctly (host saw "ping").
    let engine = Arc::new(|prompt: &str, _max: usize| Ok(format!("echo:{prompt}")));
    let exec = WasmExecutor::with_inference(GAS, engine).expect("executor");
    assert_eq!(run_on(&exec), b"echo:ping");
}

#[test]
fn err_path_yields_zero_sentinel() {
    // Default executor: no inference engine → host returns the `err` variant →
    // guest reads the `0` handle → "ERR".
    let exec = WasmExecutor::new(GAS).expect("executor");
    assert_eq!(run_on(&exec), b"ERR");
}
