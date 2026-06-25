//! Phase **S3** (first slice): effect-soundness checking (theorem T2). A
//! function that declares an `{:effects #{…}}` row may not perform an effect
//! the row omits, and may not declare an unknown effect. Annotations are
//! opt-in; un-annotated code is unaffected (still capability-gated).

use kotoba_clj::{compile_safe_clj, infer_effects, CljError, Policy};

fn assert_effect_denied(res: Result<Vec<u8>, CljError>) {
    match res {
        Err(CljError::Effect(_)) => {}
        other => panic!("expected CljError::Effect, got {other:?}"),
    }
}

fn is_wasm(b: &[u8]) -> bool {
    b.starts_with(b"\0asm")
}

#[test]
fn pure_declaration_on_pure_body_compiles() {
    let wasm = compile_safe_clj(
        "(defn run {:effects #{}} [n] (* n n))",
        &Policy::deny_all(),
    )
    .expect("a truly pure function may declare no effects");
    assert!(is_wasm(&wasm));
}

#[test]
fn under_declaration_is_rejected() {
    // Declares pure, but writes the graph → effect-soundness violation. This
    // fires regardless of capability grant (the effect gate runs first).
    let src = r#"(defn run {:effects #{}} [] (kqe-assert! "kg" "a" "p" "v"))"#;
    assert_effect_denied(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_write(["g"]),
    ));
}

#[test]
fn matching_declaration_compiles_when_granted() {
    // Declares graph-write, uses graph-write, and the policy grants it.
    let src = r#"(defn run {:effects #{:graph-write}} [] (kqe-assert! "kg" "a" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["g"]);
    let wasm = compile_safe_clj(src, &policy).expect("declared+used+granted must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn declaration_still_subject_to_capability_gate() {
    // Honest declaration, but the capability is NOT granted → Policy denial.
    // (Effect soundness passes; capability confinement still bites.)
    let src = r#"(defn run {:effects #{:graph-write}} [] (kqe-assert! "kg" "a" "p" "v"))"#;
    match compile_safe_clj(src, &Policy::deny_all()) {
        Err(CljError::Policy(_)) => {}
        other => panic!("expected Policy denial, got {other:?}"),
    }
}

#[test]
fn over_declaration_is_allowed() {
    // Declaring more effects than used is conservative, not unsound → allowed.
    // Only graph-write is used, so only that grant is needed.
    let src = r#"(defn run {:effects #{:graph-write :infer :auth}} [] (kqe-assert! "kg" "a" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["g"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn unknown_effect_name_is_rejected() {
    // Typo / non-existent effect → rejected (vocabulary guard).
    let src = "(defn run {:effects #{:graphwrite}} [n] n)";
    assert_effect_denied(compile_safe_clj(src, &Policy::deny_all()));
}

#[test]
fn read_declared_as_write_is_under_declaration() {
    // Uses graph-read but declares only graph-write → read is undeclared.
    let src = r#"(defn run {:effects #{:graph-write}} [] (kqe-query "kg/role"))"#;
    assert_effect_denied(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_read(["g"]).grant_graph_write(["g"]),
    ));
}

#[test]
fn unannotated_function_is_not_effect_checked() {
    // No :effects row → effect gate is skipped; capability gate still applies.
    let src = r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["g"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn multiple_effects_all_must_be_declared() {
    // Body uses write + infer; declaring only write under-declares infer.
    let src = r#"
        (defn run {:effects #{:graph-write}} []
          (do (kqe-assert! "kg" "a" "p" "v")
              (llm-infer "m" "x")))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["g"]).grant_infer(["m"]);
    assert_effect_denied(compile_safe_clj(src, &policy));

    // Declaring both → compiles (and both grants present).
    let src_ok = r#"
        (defn run {:effects #{:graph-write :infer}} []
          (do (kqe-assert! "kg" "a" "p" "v")
              (llm-infer "m" "x")))
    "#;
    assert!(compile_safe_clj(src_ok, &policy).is_ok());
}

// ── interprocedural effect propagation (effects can't hide behind a helper) ─

#[test]
fn transitive_effect_through_helper_is_caught() {
    // `run` declares pure but calls `helper`, which writes the graph.
    let src = r#"
        (defn helper [] (kqe-assert! "kg" "a" "p" "v"))
        (defn run {:effects #{}} [] (helper))
    "#;
    assert_effect_denied(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_write(["g"]),
    ));
}

#[test]
fn transitive_effect_declared_compiles() {
    // Same call graph, but `run` honestly declares the inherited effect.
    let src = r#"
        (defn helper [] (kqe-assert! "kg" "a" "p" "v"))
        (defn run {:effects #{:graph-write}} [] (helper))
    "#;
    let policy = Policy::deny_all().grant_graph_write(["g"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn two_hop_transitive_effect_is_caught() {
    // run -> mid -> leaf(write); run claims pure.
    let src = r#"
        (defn leaf [] (kqe-assert! "kg" "a" "p" "v"))
        (defn mid  [] (leaf))
        (defn run {:effects #{}} [] (mid))
    "#;
    assert_effect_denied(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_write(["g"]),
    ));
}

#[test]
fn pure_helper_adds_no_effect() {
    // Calling a genuinely pure helper keeps `run` pure.
    let src = r#"
        (defn double [n] (* n 2))
        (defn run {:effects #{}} [n] (double n))
    "#;
    assert!(compile_safe_clj(src, &Policy::deny_all()).is_ok());
}

#[test]
fn mutual_recursion_converges_and_propagates() {
    // ping <-> pong mutual recursion; pong writes. Both inherit graph-write via
    // the fixpoint, so a pure declaration on the caller is rejected (and the
    // analysis must terminate, not loop).
    let src = r#"
        (defn ping [n] (if (> n 0) (pong (- n 1)) 0))
        (defn pong [n] (do (kqe-assert! "kg" "a" "p" "v") (ping (- n 1))))
        (defn run {:effects #{}} [n] (ping n))
    "#;
    assert_effect_denied(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_write(["g"]),
    ));
}

// ── public effect inference API (source-level audit) ───────────────────────

#[test]
fn infer_effects_reports_direct_effects() {
    let src = r#"
        (defn writer [] (kqe-assert! "kg" "a" "p" "v"))
        (defn reader [] (kqe-query "kg/role"))
        (defn pure   [n] (* n n))
    "#;
    let eff = infer_effects(src).unwrap();
    assert!(eff["writer"].contains("graph-write"));
    assert!(eff["reader"].contains("graph-read"));
    assert!(eff["pure"].is_empty());
}

#[test]
fn infer_effects_propagates_transitively() {
    let src = r#"
        (defn leaf [] (llm-infer "m" "x"))
        (defn mid  [] (leaf))
        (defn top  [] (mid))
    "#;
    let eff = infer_effects(src).unwrap();
    for f in ["leaf", "mid", "top"] {
        assert!(eff[f].contains("infer"), "{f} should inherit infer");
    }
}

#[test]
fn infer_effects_unions_multiple() {
    let src = r#"
        (defn w [] (kqe-assert! "kg" "a" "p" "v"))
        (defn i [] (llm-infer "m" "x"))
        (defn both [] (do (w) (i)))
    "#;
    let eff = infer_effects(src).unwrap();
    assert!(eff["both"].contains("graph-write"));
    assert!(eff["both"].contains("infer"));
    assert_eq!(eff["both"].len(), 2);
}

#[test]
fn infer_effects_empty_for_no_defns() {
    assert!(infer_effects("(+ 1 2)").unwrap().is_empty());
}
