//! End-to-end integration on a **real** agent cell — the in-repo LangGraph echo
//! agent (`examples/kotoba-langgraph-echo-clj/agent.clj`, ~100 lines: CBOR
//! decode, byte-building, a `defgraph`, and a checkpoint `kqe-assert!`). It runs
//! the whole safe-clj pipeline together — subset, type, effect, capability, and
//! per-cid gates plus the least-privilege tooling — on non-synthetic code.

use kotoba_clj::{
    compile_safe_clj_with_prelude, embedded_capability_ifaces, infer_effects, minimal_policy,
    unused_grants, CljError, Policy,
};

const AGENT: &str = include_str!("../../../examples/kotoba-langgraph-echo-clj/agent.clj");

#[test]
fn agent_minimal_policy_is_exactly_one_graph_write() {
    // The cell's only host effect is a checkpoint write to "lgraph/ckpt".
    let p = minimal_policy(AGENT).unwrap();
    assert_eq!(p.graph_write.iter().collect::<Vec<_>>(), vec!["lgraph/ckpt"]);
    assert!(p.graph_read.is_empty(), "cell does not read the graph");
    assert!(p.infer.is_empty(), "cell does not run inference");
    assert!(!p.auth, "cell does not introspect CACAO");
}

#[test]
fn agent_compiles_confined_with_its_minimal_policy() {
    let p = minimal_policy(AGENT).unwrap();
    let wasm =
        compile_safe_clj_with_prelude(AGENT, &p).expect("real agent must compile under safe-clj");
    assert!(wasm.starts_with(b"\0asm"));

    // The audited capability surface is exactly the one graph interface — no
    // llm/auth leaked in by the prelude or codegen.
    assert_eq!(embedded_capability_ifaces(&wasm), vec!["kotoba:kais/kqe@0.1.0"]);
}

#[test]
fn agent_minimal_policy_has_no_over_grants() {
    let p = minimal_policy(AGENT).unwrap();
    assert!(unused_grants(AGENT, &p).unwrap().is_empty());
}

#[test]
fn agent_run_effect_is_graph_write() {
    let eff = infer_effects(AGENT).unwrap();
    assert!(eff["run"].contains("graph-write"));
    // ...and it never claims read/infer/auth.
    assert!(!eff["run"].contains("graph-read"));
    assert!(!eff["run"].contains("infer"));
}

#[test]
fn agent_is_denied_without_the_write_grant() {
    // deny-all → the checkpoint write is unauthorized.
    assert!(matches!(
        compile_safe_clj_with_prelude(AGENT, &Policy::deny_all()),
        Err(CljError::Policy(_))
    ));
}

#[test]
fn agent_is_denied_for_the_wrong_graph() {
    // Granting a *different* graph must not authorize the checkpoint write
    // (per-cid scoping on a real cell).
    let p = Policy::deny_all().grant_graph_write(["some/other-graph"]);
    assert!(matches!(
        compile_safe_clj_with_prelude(AGENT, &p),
        Err(CljError::Policy(_))
    ));
}
