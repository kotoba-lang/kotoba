//! Phase **S4**: per-cid (instance-level) capability binding. The capability
//! gate is no longer just "may write *some* graph" (class-level) — a host call
//! whose graph argument is a string literal must name a graph the policy
//! actually grants. This is the compile-time twin of CACAO's
//! `leaf.graph ⊆ root.graph` attenuation, tightening **T3** to instance
//! granularity.
//!
//! A `"*"` allowlist entry restores class-level ("any graph") behaviour, and a
//! *dynamic* (non-literal) graph argument falls back to the class-level gate
//! because it cannot be checked statically.

use kotoba_clj::{compile_safe_clj, CljError, Policy};

fn denied_policy(res: Result<Vec<u8>, CljError>) {
    assert!(
        matches!(res, Err(CljError::Policy(_))),
        "expected Policy denial, got {res:?}"
    );
}

#[test]
fn write_to_granted_graph_compiles() {
    let src = r#"(defn run [] (kqe-assert! "graphA" "s" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn write_to_ungranted_graph_is_denied_even_with_class_grant() {
    // The class IS granted (graphA), but the program writes graphB — denied.
    // This is the whole point of S4: a write grant to one graph does not let
    // you write another.
    let src = r#"(defn run [] (kqe-assert! "graphB" "s" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    match compile_safe_clj(src, &policy) {
        Err(CljError::Policy(msg)) => {
            assert!(
                msg.contains("graphB"),
                "denial should name the graph: {msg}"
            );
            assert!(msg.contains("graph-write"), "{msg}");
        }
        other => panic!("expected Policy denial, got {other:?}"),
    }
}

#[test]
fn retract_is_scoped_per_cid_too() {
    let src = r#"(defn run [] (kqe-retract! "graphB" "s" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    denied_policy(compile_safe_clj(src, &policy));
}

#[test]
fn read_is_scoped_per_cid() {
    let src = r#"(defn run [] (kqe-get-objects "graphB" "s" "p"))"#;
    // read granted for graphA only → reading graphB is denied
    let policy = Policy::deny_all().grant_graph_read(["graphA"]);
    denied_policy(compile_safe_clj(src, &policy));
    // ...and granting graphB lets it through
    let policy = Policy::deny_all().grant_graph_read(["graphB"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn wildcard_allows_any_literal_graph() {
    let src = r#"(defn run [] (kqe-assert! "anyGraphAtAll" "s" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["*"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn multiple_granted_graphs_each_allowed() {
    let policy = Policy::deny_all().grant_graph_write(["graphA", "graphB"]);
    for g in ["graphA", "graphB"] {
        let src = format!(r#"(defn run [] (kqe-assert! "{g}" "s" "p" "v"))"#);
        assert!(
            compile_safe_clj(&src, &policy).is_ok(),
            "graph {g} should compile"
        );
    }
    // a third, ungranted graph is still denied
    let src = r#"(defn run [] (kqe-assert! "graphC" "s" "p" "v"))"#;
    denied_policy(compile_safe_clj(src, &policy));
}

#[test]
fn dynamic_graph_arg_falls_back_to_class_level() {
    // The graph is a parameter, not a literal — it cannot be checked
    // statically, so the class-level gate governs: granted class → compiles,
    // even though no specific cid is named.
    let src = r#"(defn run [g] (kqe-assert! g "s" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    assert!(
        compile_safe_clj(src, &policy).is_ok(),
        "a dynamic graph target falls back to the class-level gate"
    );
    // ...but with the class entirely ungranted it is still denied.
    denied_policy(compile_safe_clj(src, &Policy::deny_all()));
}

#[test]
fn per_cid_check_reaches_nested_positions() {
    // The per-cid gate is recursive: an ungranted write buried in an if-branch
    // is still caught.
    let src = r#"(defn run [x] (if x (kqe-assert! "graphB" "s" "p" "v") 0))"#;
    let policy = Policy::deny_all().grant_graph_write(["graphA"]);
    denied_policy(compile_safe_clj(src, &policy));
}

// ── per-model scoping for inference (same instance-level principle) ─────────

#[test]
fn inference_on_granted_model_compiles() {
    let src = r#"(defn run [] (llm-infer "modelA" "prompt"))"#;
    let policy = Policy::deny_all().grant_infer(["modelA"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn inference_on_ungranted_model_is_denied_with_class_grant() {
    // Inference IS granted (modelA), but the program runs modelB — denied.
    let src = r#"(defn run [] (llm-infer "modelB" "prompt"))"#;
    let policy = Policy::deny_all().grant_infer(["modelA"]);
    match compile_safe_clj(src, &policy) {
        Err(CljError::Policy(msg)) => {
            assert!(
                msg.contains("modelB"),
                "denial should name the model: {msg}"
            );
            assert!(msg.contains("infer"), "{msg}");
        }
        other => panic!("expected Policy denial, got {other:?}"),
    }
}

#[test]
fn inference_wildcard_allows_any_model() {
    let src = r#"(defn run [] (llm-infer "any-model" "p"))"#;
    let policy = Policy::deny_all().grant_infer(["*"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn inference_dynamic_model_falls_back_to_class_level() {
    let src = r#"(defn run [m] (llm-infer m "p"))"#;
    let policy = Policy::deny_all().grant_infer(["modelA"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
    denied_policy(compile_safe_clj(src, &Policy::deny_all()));
}

#[test]
fn edn_policy_enforces_specific_cid() {
    let edn = r#"{:imports {:graph-write ["bafyOnlyThis"]}
                  :limits {:memory-pages 4 :fuel 1000000}}"#;
    let policy = Policy::parse_edn(edn).unwrap();
    assert!(compile_safe_clj(
        r#"(defn run [] (kqe-assert! "bafyOnlyThis" "s" "p" "v"))"#,
        &policy
    )
    .is_ok());
    denied_policy(compile_safe_clj(
        r#"(defn run [] (kqe-assert! "bafyOther" "s" "p" "v"))"#,
        &policy,
    ));
}
