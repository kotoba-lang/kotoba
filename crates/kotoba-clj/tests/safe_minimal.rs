//! Least-privilege policy synthesis: `minimal_policy(src)` computes the
//! smallest [`Policy`] under which a cell compiles. Two invariants anchor it:
//!   (1) **sufficiency** — the synthesized policy always compiles the cell;
//!   (2) **minimality** — it grants only what the cell targets, and removing a
//!       grant breaks compilation.

use kotoba_clj::{compile_safe_kotoba, minimal_policy, CljError, Policy};

fn denied_policy(res: Result<Vec<u8>, CljError>) {
    assert!(
        matches!(res, Err(CljError::Policy(_))),
        "expected Policy denial, got {res:?}"
    );
}

#[test]
fn pure_cell_needs_deny_all() {
    let src = "(defn run [n] (* n n))";
    let p = minimal_policy(src).unwrap();
    assert!(p.graph_read.is_empty());
    assert!(p.graph_write.is_empty());
    assert!(p.infer.is_empty());
    assert!(!p.auth);
    assert!(compile_safe_kotoba(src, &p).is_ok());
}

#[test]
fn minimal_policy_is_sufficient_by_construction() {
    // A range of cells: the synthesized policy must always compile them.
    for src in [
        "(defn run [n] (inc n))",
        r#"(defn run [] (kqe-assert! "graphA" "s" "p" "v"))"#,
        r#"(defn run [] (kqe-get-objects "graphB" "s" "p"))"#,
        r#"(defn run [] (llm-infer "modelX" "prompt"))"#,
        r#"(defn run [] (has-capability? "r" "a"))"#,
        r#"(defn run [g] (kqe-assert! g "s" "p" "v"))"#, // dynamic graph
        r#"(defn run []
              (do (kqe-assert! "gA" "s" "p" "v")
                  (llm-infer "mX" "x")
                  (has-capability? "r" "a")))"#,
    ] {
        let p = minimal_policy(src).unwrap();
        assert!(
            compile_safe_kotoba(src, &p).is_ok(),
            "minimal policy must compile: {src}"
        );
    }
}

#[test]
fn minimal_policy_pins_literal_resources() {
    let src = r#"(defn run []
                   (do (kqe-assert! "gWrite" "s" "p" "v")
                       (kqe-get-objects "gRead" "s" "p")
                       (llm-infer "mInfer" "x")))"#;
    let p = minimal_policy(src).unwrap();
    assert_eq!(p.graph_write.iter().collect::<Vec<_>>(), vec!["gWrite"]);
    assert_eq!(p.graph_read.iter().collect::<Vec<_>>(), vec!["gRead"]);
    assert_eq!(p.infer.iter().collect::<Vec<_>>(), vec!["mInfer"]);
    assert!(!p.auth, "auth not used → not granted");
}

#[test]
fn minimal_policy_is_actually_minimal() {
    // Removing the single grant the cell needs must break compilation.
    let src = r#"(defn run [] (kqe-assert! "graphA" "s" "p" "v"))"#;
    let p = minimal_policy(src).unwrap();
    assert!(compile_safe_kotoba(src, &p).is_ok());

    // Drop the graph-write grant → no longer compiles.
    let mut stripped = p.clone();
    stripped.graph_write.clear();
    denied_policy(compile_safe_kotoba(src, &stripped));
}

#[test]
fn dynamic_target_widens_to_wildcard() {
    let src = r#"(defn run [g] (kqe-assert! g "s" "p" "v"))"#;
    let p = minimal_policy(src).unwrap();
    assert!(p.graph_write.contains("*"), "dynamic graph → wildcard");
    assert!(compile_safe_kotoba(src, &p).is_ok());
}

#[test]
fn kqe_query_needs_read_class_via_wildcard() {
    // kqe-query reads but names no graph → minimal grants graph-read "*".
    let src = r#"(defn run [] (kqe-query "kg/role"))"#;
    let p = minimal_policy(src).unwrap();
    assert!(p.graph_read.contains("*"));
    assert!(p.graph_write.is_empty());
    assert!(compile_safe_kotoba(src, &p).is_ok());
}

#[test]
fn policy_edn_round_trips() {
    // to_edn → parse_edn preserves the gated grants and limits.
    let p = Policy::deny_all()
        .grant_graph_write(["gA", "gB"])
        .grant_graph_read(["gR"])
        .grant_infer(["mX"])
        .grant_auth();
    let edn = p.to_edn();
    let back = Policy::parse_edn(&edn).expect("emitted policy EDN must re-parse");

    assert_eq!(back.graph_write, p.graph_write);
    assert_eq!(back.graph_read, p.graph_read);
    assert_eq!(back.infer, p.infer);
    assert_eq!(back.auth, p.auth);
    assert_eq!(back.limits, p.limits);
}

#[test]
fn synthesized_policy_emits_parseable_edn() {
    let src = r#"(defn run [] (kqe-assert! "graphA" "s" "p" "v"))"#;
    let p = minimal_policy(src).unwrap();
    let edn = p.to_edn();
    // The emitted artifact is a usable policy.edn that gates the same way.
    let reparsed = Policy::parse_edn(&edn).unwrap();
    assert!(compile_safe_kotoba(src, &reparsed).is_ok());
    assert!(edn.contains("graphA"));
}

// ── over-grant linter (the complement: policy grants the cell doesn't use) ──

#[test]
fn exact_fit_policy_has_no_unused_grants() {
    let src = r#"(defn run [] (kqe-assert! "gA" "s" "p" "v"))"#;
    let p = minimal_policy(src).unwrap();
    assert!(
        kotoba_clj::unused_grants(src, &p).unwrap().is_empty(),
        "the minimal policy must report no over-grants"
    );
}

#[test]
fn unused_whole_class_is_reported() {
    // Cell only writes; policy also grants infer + auth → both unused.
    let src = r#"(defn run [] (kqe-assert! "gA" "s" "p" "v"))"#;
    let p = Policy::deny_all()
        .grant_graph_write(["gA"])
        .grant_infer(["m"])
        .grant_auth();
    let unused = kotoba_clj::unused_grants(src, &p).unwrap();
    assert!(unused.iter().any(|u| u.contains("infer")), "{unused:?}");
    assert!(unused.iter().any(|u| u.contains("auth")), "{unused:?}");
    assert_eq!(unused.len(), 2);
}

#[test]
fn unused_specific_cid_is_reported() {
    // Cell writes only gA; policy grants gA + gB → gB is unused.
    let src = r#"(defn run [] (kqe-assert! "gA" "s" "p" "v"))"#;
    let p = Policy::deny_all().grant_graph_write(["gA", "gB"]);
    let unused = kotoba_clj::unused_grants(src, &p).unwrap();
    assert_eq!(unused.len(), 1);
    assert!(
        unused[0].contains("gB") && !unused[0].contains("gA"),
        "{unused:?}"
    );
}

#[test]
fn wildcard_grant_is_not_flagged_as_unused() {
    // A `"*"` grant is intentionally broad → never reported, even if the cell
    // targets only one graph.
    let src = r#"(defn run [] (kqe-assert! "gA" "s" "p" "v"))"#;
    let p = Policy::deny_all().grant_graph_write(["*"]);
    assert!(kotoba_clj::unused_grants(src, &p).unwrap().is_empty());
}

#[test]
fn dynamic_target_suppresses_per_cid_unused_claims() {
    // The cell writes a dynamic graph; we can't prove any granted cid unused.
    let src = r#"(defn run [g] (kqe-assert! g "s" "p" "v"))"#;
    let p = Policy::deny_all().grant_graph_write(["gA", "gB"]);
    assert!(
        kotoba_clj::unused_grants(src, &p).unwrap().is_empty(),
        "dynamic target → no per-cid unused claims"
    );
}
