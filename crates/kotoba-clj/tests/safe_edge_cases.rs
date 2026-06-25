//! Edge-case coverage: the three safe-clj gates must hold in *non-trivial
//! syntactic positions* — not just at the top level of a function body, but
//! nested inside threading macros, data literals, conditional branches, and
//! arity-list `defn` forms. A gate that only inspected top-level forms would
//! miss these; these tests lock in the recursive guarantee.

use kotoba_clj::{compile_safe_clj, infer_effects, CljError, Policy};

fn denied_subset(res: Result<Vec<u8>, CljError>) {
    assert!(
        matches!(res, Err(CljError::Subset(_))),
        "expected Subset denial, got {res:?}"
    );
}
fn denied_policy(res: Result<Vec<u8>, CljError>) {
    assert!(
        matches!(res, Err(CljError::Policy(_))),
        "expected Policy denial, got {res:?}"
    );
}
fn denied_effect(res: Result<Vec<u8>, CljError>) {
    assert!(
        matches!(res, Err(CljError::Effect(_))),
        "expected Effect denial, got {res:?}"
    );
}

// ── subset gate: forbidden ops in nested positions ─────────────────────────

#[test]
fn forbidden_op_inside_threading_macro_is_caught() {
    // `(-> x (eval))` threads to `(eval x)`. The forbidden call appears as a
    // child list of the `->` form — the recursive gate must catch it.
    denied_subset(compile_safe_clj(
        "(defn run [x] (-> x (eval)))",
        &Policy::deny_all(),
    ));
}

#[test]
fn forbidden_op_inside_vector_literal_is_caught() {
    denied_subset(compile_safe_clj(
        "(defn run [x] [(eval x) 1 2])",
        &Policy::deny_all(),
    ));
}

#[test]
fn forbidden_op_inside_map_literal_is_caught() {
    denied_subset(compile_safe_clj(
        "(defn run [x] {:k (resolve x)})",
        &Policy::deny_all(),
    ));
}

#[test]
fn forbidden_op_inside_conditional_branch_is_caught() {
    denied_subset(compile_safe_clj(
        "(defn run [x] (if x (set! *y* 1) 0))",
        &Policy::deny_all(),
    ));
}

#[test]
fn forbidden_require_inside_threading_step_is_caught() {
    denied_subset(compile_safe_clj(
        "(defn run [x] (-> x (require [evil.ns])))",
        &Policy::deny_all(),
    ));
}

// ── capability gate: host calls in nested positions still gated ────────────

#[test]
fn host_call_in_conditional_branch_is_gated() {
    let src = r#"(defn run [x] (if x (kqe-assert! "g" "a" "p" "v") 0))"#;
    denied_policy(compile_safe_clj(src, &Policy::deny_all()));
    assert!(compile_safe_clj(src, &Policy::deny_all().grant_graph_write(["g"])).is_ok());
}

#[test]
fn host_call_in_let_binding_is_gated() {
    let src = r#"(defn run [] (let [r (kqe-query "kg/role")] r))"#;
    denied_policy(compile_safe_clj(src, &Policy::deny_all()));
    assert!(compile_safe_clj(src, &Policy::deny_all().grant_graph_read(["g"])).is_ok());
}

// ── effect gate: inference reaches nested + arity-list positions ────────────

#[test]
fn effect_in_arity_list_defn_is_inferred() {
    // Multi-arity `defn`; one arity writes. The declared-pure row must be
    // rejected because the write is reachable.
    let src = r#"
        (defn run {:effects #{}}
          ([] (kqe-assert! "g" "a" "p" "v"))
          ([n] n))
    "#;
    denied_effect(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_write(["g"]),
    ));
}

#[test]
fn effect_in_conditional_branch_is_inferred() {
    let eff = infer_effects(r#"(defn run [x] (if x (llm-infer "m" "p") 0))"#).unwrap();
    assert!(eff["run"].contains("infer"));
}

#[test]
fn effect_in_let_body_is_inferred() {
    let eff = infer_effects(r#"(defn run [] (let [_ 1] (kqe-assert! "g" "a" "p" "v")))"#).unwrap();
    assert!(eff["run"].contains("graph-write"));
}

#[test]
fn effect_in_vector_literal_arg_is_inferred() {
    // A host call nested in a data literal still counts.
    let eff = infer_effects(r#"(defn run [] (first [(kqe-query "p") 1]))"#).unwrap();
    assert!(eff["run"].contains("graph-read"));
}

// ── all three gates compose under nesting ──────────────────────────────────

#[test]
fn nested_clean_program_with_grants_compiles() {
    let src = r#"
        (defn fetch {:effects #{:graph-read}} [] (kqe-query "kg/role"))
        (defn run {:effects #{:graph-read}} [x]
          (if x (let [r (fetch)] r) 0))
    "#;
    let policy = Policy::deny_all().grant_graph_read(["g"]);
    assert!(
        compile_safe_clj(src, &policy).is_ok(),
        "a nested, honestly-declared, granted program must compile"
    );
}
