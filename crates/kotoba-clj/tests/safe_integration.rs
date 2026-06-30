//! End-to-end integration on a **real** agent cell — the in-repo LangGraph echo
//! agent (`examples/kotoba-langgraph-echo-kotoba/agent.kotoba`, ~100 lines: CBOR
//! decode, byte-building, a `defgraph`, and a checkpoint `kqe-assert!`). It runs
//! the whole safe Kotoba pipeline together — subset, type, effect, capability, and
//! per-cid gates plus the least-privilege tooling — on non-synthetic code.

use kotoba_clj::{
    compile_safe_kotoba_with_prelude, embedded_capability_ifaces, infer_effects, minimal_policy,
    unused_grants, CljError, Policy,
};

const AGENT: &str = include_str!("../../../examples/kotoba-langgraph-echo-kotoba/agent.kotoba");

/// Mesh cells exercising a read+write profile (kqe-assert! + kqe-query), a bare
/// `(ns …)`, and multiple entry defns (run + on-kse / on-http).
const INGEST: &str = include_str!("../../../examples/kotoba-mesh-app/ingest.kotoba");
const REPLY: &str = include_str!("../../../examples/kotoba-mesh-app/reply.kotoba");

#[test]
fn agent_minimal_policy_is_exactly_one_graph_write() {
    // The cell's only host effect is a checkpoint write to "lgraph/ckpt".
    let p = minimal_policy(AGENT).unwrap();
    assert_eq!(
        p.graph_write.iter().collect::<Vec<_>>(),
        vec!["lgraph/ckpt"]
    );
    assert!(p.graph_read.is_empty(), "cell does not read the graph");
    assert!(p.infer.is_empty(), "cell does not run inference");
    assert!(!p.auth, "cell does not introspect CACAO");
}

#[test]
fn agent_compiles_confined_with_its_minimal_policy() {
    let p = minimal_policy(AGENT).unwrap();
    let wasm = compile_safe_kotoba_with_prelude(AGENT, &p)
        .expect("real agent must compile under safe Kotoba");
    assert!(wasm.starts_with(b"\0asm"));

    // The audited capability surface is exactly the one graph interface — no
    // llm/auth leaked in by the prelude or codegen.
    assert_eq!(
        embedded_capability_ifaces(&wasm),
        vec!["kotoba:kais/kqe@0.1.0"]
    );
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
        compile_safe_kotoba_with_prelude(AGENT, &Policy::deny_all()),
        Err(CljError::Policy(_))
    ));
}

#[test]
fn agent_is_denied_for_the_wrong_graph() {
    // Granting a *different* graph must not authorize the checkpoint write
    // (per-cid scoping on a real cell).
    let p = Policy::deny_all().grant_graph_write(["some/other-graph"]);
    assert!(matches!(
        compile_safe_kotoba_with_prelude(AGENT, &p),
        Err(CljError::Policy(_))
    ));
}

// ── mesh cells: a read+write profile on real code ──────────────────────────

#[test]
fn mesh_cells_need_write_and_read() {
    // kqe-assert! → graph-write "g"; kqe-query → graph-read (no specific graph,
    // so wildcard). Both cells share this profile.
    for src in [INGEST, REPLY] {
        let p = minimal_policy(src).unwrap();
        assert_eq!(p.graph_write.iter().collect::<Vec<_>>(), vec!["g"]);
        assert!(p.graph_read.contains("*"), "kqe-query needs graph-read");
        assert!(p.infer.is_empty() && !p.auth);
    }
}

#[test]
fn mesh_cells_compile_confined() {
    for src in [INGEST, REPLY] {
        let p = minimal_policy(src).unwrap();
        let wasm = compile_safe_kotoba_with_prelude(src, &p)
            .expect("mesh cell must compile under safe Kotoba");
        assert_eq!(
            embedded_capability_ifaces(&wasm),
            vec!["kotoba:kais/kqe@0.1.0"]
        );
    }
}

#[test]
fn mesh_cells_denied_with_write_only() {
    // Granting write but not read must reject — the cell also queries.
    for src in [INGEST, REPLY] {
        let p = Policy::deny_all().grant_graph_write(["g"]);
        assert!(
            matches!(
                compile_safe_kotoba_with_prelude(src, &p),
                Err(CljError::Policy(_))
            ),
            "a read+write cell needs both grants"
        );
    }
}

#[test]
fn mesh_cells_have_no_over_grants_under_minimal() {
    for src in [INGEST, REPLY] {
        let p = minimal_policy(src).unwrap();
        assert!(unused_grants(src, &p).unwrap().is_empty());
    }
}
