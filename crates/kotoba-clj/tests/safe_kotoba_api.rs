//! Kotoba-primary aliases for the historical safe Kotoba API.
//!
//! These tests keep new Rust integrations pointed at `compile_safe_kotoba*`
//! while the old `compile_safe_clj*` names remain compatibility aliases.

use kotoba_clj::{
    compile_safe_kotoba, compile_safe_kotoba_with_prelude, compile_safe_kotoba_with_reader_target,
    CljError, Policy, ReaderTarget,
};

#[test]
fn compile_safe_kotoba_accepts_pure_kotoba_source() {
    let wasm = compile_safe_kotoba("(defn run [n] (* n n))", &Policy::deny_all()).expect("compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn compile_safe_kotoba_preserves_policy_denials() {
    let src = r#"(defn run {:effects #{:graph-write}} [] (kqe-assert! "kg" "s" "p" "v"))"#;
    let err = compile_safe_kotoba(src, &Policy::deny_all()).expect_err("deny graph-write");
    assert!(matches!(err, CljError::Policy(_)));
}

#[test]
fn compile_safe_kotoba_with_prelude_uses_same_safe_prelude_path() {
    let src = "(defn run [] (count (vector 1 2 3)))";
    let wasm = compile_safe_kotoba_with_prelude(src, &Policy::deny_all()).expect("compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn compile_safe_kotoba_with_reader_target_honors_kotoba_branch() {
    let src = r#"
        #?(:kotoba (defn run [n] (+ n 10))
           :clj    (defn run [n] (+ n 1)))
    "#;
    let wasm =
        compile_safe_kotoba_with_reader_target(src, ReaderTarget::Kotoba, &Policy::deny_all())
            .expect("compile kotoba branch");
    assert!(wasm.starts_with(b"\0asm"));
}
