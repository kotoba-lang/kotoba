//! Quoted forms are **data, not code**: `'(…)` reads as `(quote …)` and is
//! never executed (eval is banned by the subset gate). So none of the gates —
//! subset, type, effect, capability — may analyze a quoted form's contents.
//! Doing so would be a false positive: rejecting valid code, mis-attributing
//! effects, or demanding capabilities the cell never exercises.

use kotoba_clj::{compile_safe_kotoba, infer_effects, minimal_policy, CljError, Policy};

#[test]
fn quoted_arithmetic_on_string_is_not_a_type_error() {
    // The `(+ "a" 1)` is quoted data — must NOT trip the literal type check.
    let src = r#"(defn run [] (str-len (quote (+ "a" 1))))"#;
    assert!(
        compile_safe_kotoba(src, &Policy::deny_all()).is_ok(),
        "quoted arithmetic is data, not a type error"
    );
}

#[test]
fn quoted_forbidden_op_is_not_a_subset_violation() {
    // A quoted `(eval …)` is inert data — not the forbidden eval call.
    let src = r#"(defn run [] (str-len (quote (eval x))))"#;
    assert!(
        compile_safe_kotoba(src, &Policy::deny_all()).is_ok(),
        "quoted `eval` is data, not an executed eval"
    );
}

#[test]
fn quoted_host_call_performs_no_effect() {
    // Quoting `(kqe-assert! …)` must NOT attribute a graph-write effect.
    let eff = infer_effects(r#"(defn run [] (quote (kqe-assert! "g" "s" "p" "v")))"#).unwrap();
    assert!(
        eff["run"].is_empty(),
        "a quoted host call performs no effect, got {:?}",
        eff["run"]
    );
}

#[test]
fn quoted_host_call_needs_no_capability() {
    // A function that only *quotes* a kqe-assert! must compile under deny-all.
    let src = r#"(defn run [] (quote (kqe-assert! "g" "s" "p" "v")))"#;
    assert!(
        compile_safe_kotoba(src, &Policy::deny_all()).is_ok(),
        "quoting a host call needs no grant"
    );
}

#[test]
fn quoted_host_call_is_not_in_minimal_policy() {
    let src = r#"(defn run [] (quote (kqe-assert! "g" "s" "p" "v")))"#;
    let p = minimal_policy(src).unwrap();
    assert!(p.graph_write.is_empty(), "quoted call must not be granted");
    assert!(p.graph_read.is_empty() && p.infer.is_empty() && !p.auth);
}

#[test]
fn real_call_alongside_quoted_call_still_gated() {
    // The quote is inert, but the *real* kqe-assert! still needs its grant —
    // and only for the real graph, not the quoted one.
    let src = r#"(defn run []
                   (do (kqe-assert! "realG" "s" "p" "v")
                       (quote (kqe-assert! "quotedG" "s" "p" "v"))))"#;
    // deny-all → denied (the real call needs a grant)
    assert!(matches!(
        compile_safe_kotoba(src, &Policy::deny_all()),
        Err(CljError::Policy(_))
    ));
    // granting only the real graph is sufficient (quoted graph irrelevant)
    let p = Policy::deny_all().grant_graph_write(["realG"]);
    assert!(compile_safe_kotoba(src, &p).is_ok());

    // and the quoted graph is correctly absent from the minimal policy
    let min = minimal_policy(src).unwrap();
    assert!(min.graph_write.contains("realG"));
    assert!(!min.graph_write.contains("quotedG"));
}

// ── (comment …) is dropped at compile time → same inert-form contract ───────

#[test]
fn comment_body_is_not_type_checked() {
    let src = r#"(defn run [n] (do (comment (+ "a" 1)) n))"#;
    assert!(
        compile_safe_kotoba(src, &Policy::deny_all()).is_ok(),
        "a commented-out type error must not be flagged"
    );
}

#[test]
fn comment_body_is_not_subset_checked() {
    let src = r#"(defn run [n] (do (comment (eval x)) n))"#;
    assert!(compile_safe_kotoba(src, &Policy::deny_all()).is_ok());
}

#[test]
fn comment_host_call_performs_no_effect_and_needs_no_grant() {
    let src = r#"(defn run [n] (do (comment (kqe-assert! "g" "s" "p" "v")) n))"#;
    assert!(
        compile_safe_kotoba(src, &Policy::deny_all()).is_ok(),
        "a commented host call needs no grant"
    );
    let eff = infer_effects(src).unwrap();
    assert!(
        eff["run"].is_empty(),
        "commented call has no effect: {:?}",
        eff["run"]
    );
    assert!(minimal_policy(src).unwrap().graph_write.is_empty());
}
