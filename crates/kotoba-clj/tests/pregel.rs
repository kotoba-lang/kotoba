//! Stage E: a compiled-Kotoba agent runs on the **Pregel BSP engine**
//! (`kotoba-vm::WasmPregelRunner`) — closing the "langgraph × Pregel × BSP"
//! composition. Each BSP superstep invokes the guest's `run(ctx)`:
//!
//!   superstep N — the guest CBOR-decodes its ctx (C-3), runs a `defgraph`
//!   (D) whose node asserts a Datom via `kqe-assert!` (C-5) and bumps the
//!   counter, then CBOR-encodes (C-4) `{"status": "continue"|"done", "n": k}`.
//!   The runner feeds a `continue` output back in as the next superstep's ctx;
//!   any other status votes halt (single-vertex self-loop model).
//!
//! Verified: superstep count, the per-superstep Datom writes accumulated
//! across the BSP run, gas accounting, and the final structured output.
#![cfg(feature = "component")]

use std::sync::Arc;

use kotoba_clj::component::compile_kais_component_str;
use kotoba_clj::prelude;
use kotoba_runtime::WasmExecutor;
use kotoba_vm::WasmPregelRunner;

const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;
const AGENT: &str = "did:key:z6MkPregelAgent";

/// A langgraph-shaped BSP agent. One superstep = decode ctx → run the
/// `defgraph` (its node asserts a tick Datom and increments the state counter)
/// → emit `continue` until the counter reaches 4, then `done`.
const SRC: &str = r#"
    (defn work [state]
      (do (kqe-assert! "bsp" "counter" "bsp/tick"
            (bytes-finish (cbor-enc-text! (bytes-alloc 16) "t")))
          (map-assoc! state "n" (+ (map-get state "n") 1))))

    (defgraph step
      :entry :work
      :nodes {:work work}
      :edges {:work :end})

    (defn emit [status n]
      (let [buf (bytes-alloc 64)]
        (do (cbor-enc-map-header! buf 2)
            (cbor-enc-text! buf "status")
            (cbor-enc-text! buf status)
            (cbor-enc-text! buf "n")
            (cbor-enc-uint! buf n)
            (bytes-finish buf))))

    (defn run [ctx]
      (let [r (cbor-reader ctx)]
        (if (= (cbor-map-seek r "n") 1)
          (let [s (map-make 4)]
            (do (map-assoc! s "n" (cbor-uint r))
                (let [n2 (map-get (step s) "n")]
                  (if (< n2 4) (emit "continue" n2) (emit "done" n2)))))
          (emit "done" 99))))
"#;

fn agent_component() -> Vec<u8> {
    let full = format!("{}\n{}", prelude(), SRC);
    compile_kais_component_str(&full, KAIS_WIT_DIR).expect("compile + encode")
}

fn runner(max_supersteps: u32) -> WasmPregelRunner {
    let executor = Arc::new(WasmExecutor::new(GAS).expect("executor"));
    WasmPregelRunner::new(
        executor,
        "kotoba-bsp-agent-cid",
        agent_component(),
        AGENT,
        max_supersteps,
    )
}

/// Initial ctx `{"n": n}` — what superstep 0 decodes.
fn ctx_with_n(n: u64) -> Vec<u8> {
    let val = ciborium::Value::Map(vec![(
        ciborium::Value::Text("n".into()),
        ciborium::Value::Integer(n.into()),
    )]);
    let mut buf = Vec::new();
    ciborium::into_writer(&val, &mut buf).expect("cbor");
    buf
}

/// Decode `{"status": s, "n": k}` from the agent's final output.
fn decode_status_n(cbor: &[u8]) -> (String, u64) {
    let val: ciborium::Value = ciborium::from_reader(cbor).expect("final output cbor");
    let ciborium::Value::Map(pairs) = val else {
        panic!("not a cbor map")
    };
    let mut status = None;
    let mut n = None;
    for (k, v) in &pairs {
        match k.as_text() {
            Some("status") => status = v.as_text().map(str::to_string),
            Some("n") => n = v.as_integer().map(|i| u64::try_from(i).expect("uint n")),
            _ => {}
        }
    }
    (status.expect("status key"), n.expect("n key"))
}

#[test]
fn clj_agent_runs_multiple_bsp_supersteps_and_writes_datoms() {
    // n: 0→1 (continue), 1→2 (continue), 2→3 (continue), 3→4 (done) = 4 supersteps
    let result = runner(10).run(ctx_with_n(0)).expect("BSP run");
    assert_eq!(result.supersteps_run, 4, "expected 4 supersteps");

    // one Datom asserted per superstep, accumulated across the whole BSP run
    assert_eq!(result.assert_quads.len(), 4);
    for q in &result.assert_quads {
        assert_eq!(q.graph, "bsp");
        assert_eq!(q.subject, "counter");
        assert_eq!(q.predicate, "bsp/tick");
    }

    // 4 × assert-quad (10 gas each) accumulated across supersteps
    assert!(
        result.total_gas_used >= 40,
        "gas: {}",
        result.total_gas_used
    );

    let (status, n) = decode_status_n(&result.final_output_cbor);
    assert_eq!(status, "done");
    assert_eq!(n, 4);
}

#[test]
fn clj_agent_halts_in_one_superstep_when_already_done() {
    // n=10 → the node still runs once (asserts 1 Datom, n→11) → "done" → halt
    let result = runner(10).run(ctx_with_n(10)).expect("BSP run");
    assert_eq!(result.supersteps_run, 1);
    assert_eq!(result.assert_quads.len(), 1);
    let (status, n) = decode_status_n(&result.final_output_cbor);
    assert_eq!(status, "done");
    assert_eq!(n, 11);
}

#[test]
fn max_supersteps_caps_a_continue_loop() {
    // the guest would continue until n=4, but the BSP cap stops it at 2
    let result = runner(2).run(ctx_with_n(0)).expect("BSP run");
    assert_eq!(result.supersteps_run, 2);
    // each executed superstep still asserted its Datom
    assert_eq!(result.assert_quads.len(), 2);
}
