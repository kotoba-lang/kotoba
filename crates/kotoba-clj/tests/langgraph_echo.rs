//! The **Clojure-WASM port of the componentize-py LangGraph echo agent**
//! (`examples/kotoba-langgraph-echo-clj/agent.clj` ⇄
//! `examples/kotoba-langgraph-echo/agent.py`) — the "Python LangGraph actor →
//! Clojure WASM actor" migration path, proven end-to-end on the real host:
//!
//!   - the agent source is the *example file itself* (`include_str!`), compiled
//!     with the full prelude to a `kotoba-node` component;
//!   - `run(ctx)` receives the same CBOR `InvokeContext` the Python
//!     `handle_invoke` decodes (`{"graph", "session_cid", "args": {"input",
//!     "thread_id"}}`) and returns the same `{"ok": <JSON state>}` result;
//!   - the `KotobaCheckpointer.save` write surfaces as a kqe Datom on
//!     graph `lgraph/ckpt` with object-cbor `{"Text": <JSON state>}`.
#![cfg(feature = "component")]

use std::collections::HashMap;

use ciborium::Value;
use kotoba_clj::component::compile_kais_component_str;
use kotoba_clj::prelude;
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::{InvokeResult, WasmExecutor};

const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;
const AGENT_DID: &str = "did:key:z6MkLanggraphEchoClj";

/// The example agent source — the file under `examples/` IS what runs here.
const AGENT_CLJ: &str = include_str!("../../../examples/kotoba-langgraph-echo-clj/agent.clj");

fn agent_component() -> Vec<u8> {
    let src = format!("{}\n{}", prelude(), AGENT_CLJ);
    compile_kais_component_str(&src, KAIS_WIT_DIR).expect("compile agent.clj to kotoba-node")
}

fn invoke(ctx: Vec<u8>) -> InvokeResult {
    let exec = WasmExecutor::new(GAS).expect("executor");
    exec.execute(
        "clj-langgraph-echo",
        &agent_component(),
        AGENT_DID,
        ctx,
        Vec::<WitQuad>::new(),
        HashMap::new(),
    )
    .expect("execute run(ctx)")
}

fn cbor(value: &Value) -> Vec<u8> {
    let mut out = Vec::new();
    ciborium::into_writer(value, &mut out).expect("cbor encode");
    out
}

fn text(s: &str) -> Value {
    Value::Text(s.to_string())
}

/// The InvokeContext wire format from `py/kotoba_langgraph/_entry.py`:
/// `{"args": {"input": {"prompt": ..}, "thread_id": ..}, "graph": .., "session_cid": ..}`.
fn invoke_ctx(prompt: &str, session_cid: &str, thread_id: Option<&str>) -> Vec<u8> {
    let input = Value::Map(vec![(text("prompt"), text(prompt))]);
    let mut args = vec![(text("input"), input)];
    if let Some(t) = thread_id {
        args.push((text("thread_id"), text(t)));
    }
    cbor(&Value::Map(vec![
        (text("args"), Value::Map(args)),
        (text("graph"), text("lgraph-def-cid")),
        (text("session_cid"), text(session_cid)),
    ]))
}

/// Decode the agent's output as the `{"ok": <json>}` map and return the json.
fn ok_json(output_cbor: &[u8]) -> String {
    let value: Value = ciborium::from_reader(output_cbor).expect("output is CBOR");
    let map = value.as_map().expect("output is a CBOR map");
    assert_eq!(map.len(), 1, "exactly the ok entry");
    assert_eq!(map[0].0.as_text(), Some("ok"));
    map[0].1.as_text().expect("ok holds a JSON string").to_string()
}

// ---- echo semantics: prompt round-trips to response ---------------------------

#[test]
fn prompt_round_trips_to_response() {
    // The verified Python recipe: {"prompt": "hello kotoba wasm"} →
    // OUTPUT {"response": "hello kotoba wasm"} — same bytes-level result here,
    // including json.dumps' default separators and the EchoState key order.
    let result = invoke(invoke_ctx("hello kotoba wasm", "sess-1", Some("t-1")));
    assert_eq!(
        ok_json(&result.output_cbor),
        r#"{"prompt": "hello kotoba wasm", "response": "hello kotoba wasm"}"#
    );
}

#[test]
fn empty_prompt_when_input_has_no_prompt_key() {
    // _echo: state.get("prompt", "") — a prompt-less input yields "".
    let input = Value::Map(vec![(text("other"), text("x"))]);
    let ctx = cbor(&Value::Map(vec![
        (text("args"), Value::Map(vec![(text("input"), input)])),
        (text("session_cid"), text("sess-2")),
    ]));
    let result = invoke(ctx);
    assert_eq!(ok_json(&result.output_cbor), r#"{"prompt": "", "response": ""}"#);
}

#[test]
fn prompt_falls_back_to_args_when_input_absent() {
    // _entry.py: input_state = args.get("input", args) — without an "input"
    // map the args dict itself is the input state.
    let ctx = cbor(&Value::Map(vec![
        (text("args"), Value::Map(vec![(text("prompt"), text("direct"))])),
        (text("session_cid"), text("sess-3")),
    ]));
    let result = invoke(ctx);
    assert_eq!(
        ok_json(&result.output_cbor),
        r#"{"prompt": "direct", "response": "direct"}"#
    );
}

// ---- KotobaCheckpointer.save → kqe Datom ---------------------------------------

#[test]
fn checkpointer_persists_state_to_lgraph_ckpt() {
    // checkpointer.py storage layout: graph "lgraph/ckpt" / subject thread_id /
    // predicate "state" / object CBOR {"Text": json.dumps(state)}.
    let result = invoke(invoke_ctx("hi", "sess-4", Some("thread-42")));
    assert_eq!(result.assert_quads.len(), 1, "one checkpoint write per invoke");
    let q = &result.assert_quads[0];
    assert_eq!(q.graph, "lgraph/ckpt");
    assert_eq!(q.subject, "thread-42");
    assert_eq!(q.predicate, "state");
    let expected_obj = cbor(&Value::Map(vec![(
        text("Text"),
        text(r#"{"prompt": "hi", "response": "hi"}"#),
    )]));
    assert_eq!(q.object_cbor, expected_obj);
    // kqe.assert-quad charges gas, same as the Python actor's checkpoint write
    assert!(result.gas_used >= 10, "gas charged for the assert, got {}", result.gas_used);
}

#[test]
fn thread_id_defaults_to_session_cid() {
    // _entry.py: thread_id = args.get("thread_id", session_cid).
    let result = invoke(invoke_ctx("yo", "session-as-thread", None));
    assert_eq!(result.assert_quads.len(), 1);
    assert_eq!(result.assert_quads[0].subject, "session-as-thread");
}

// ---- size: the migration-path payoff -------------------------------------------

#[test]
fn component_is_orders_of_magnitude_smaller_than_componentize_py() {
    // The componentize-py build of the same agent is ~18 MB (bundled CPython).
    // The kotoba-clj component must stay under 64 KiB.
    let component = agent_component();
    println!("kotoba-clj echo component: {} bytes", component.len());
    assert!(
        component.len() < 64 * 1024,
        "expected a tiny component, got {} bytes",
        component.len()
    );
}
