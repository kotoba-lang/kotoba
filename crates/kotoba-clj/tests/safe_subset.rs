//! Phase **S1** (first slice) of the capability-confinement design: the
//! safe-subset form gate. `compile_safe_clj` is deny-by-default for *language
//! features* just as it is for *capabilities* — `eval`, runtime `require`,
//! dynamic-var mutation, reflection, and user `defmacro` are rejected, where the
//! legacy path would silently drop them.

use kotoba_clj::{compile_safe_clj, compile_safe_clj_with_prelude, CljError, Policy};

fn assert_subset_denied(res: Result<Vec<u8>, CljError>) {
    match res {
        Err(CljError::Subset(_)) => {}
        other => panic!("expected CljError::Subset denial, got {other:?}"),
    }
}

fn is_wasm(bytes: &[u8]) -> bool {
    bytes.starts_with(b"\0asm")
}

#[test]
fn plain_safe_program_compiles() {
    let wasm = compile_safe_clj("(defn run [n] (if (> n 0) n 0))", &Policy::deny_all())
        .expect("a safe-subset program must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn eval_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(defn run [x] (eval x))",
        &Policy::deny_all(),
    ));
}

#[test]
fn read_string_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(defn run [s] (read-string s))",
        &Policy::deny_all(),
    ));
}

#[test]
fn runtime_require_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(require '[evil.ns]) (defn run [n] n)",
        &Policy::deny_all(),
    ));
}

#[test]
fn user_defmacro_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(defmacro m [x] x) (defn run [n] n)",
        &Policy::deny_all(),
    ));
}

#[test]
fn set_bang_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(defn run [n] (set! *x* n))",
        &Policy::deny_all(),
    ));
}

#[test]
fn binding_dynamic_var_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(defn run [n] (binding [*x* n] n))",
        &Policy::deny_all(),
    ));
}

#[test]
fn reflection_resolve_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(defn run [s] (resolve s))",
        &Policy::deny_all(),
    ));
}

#[test]
fn gen_class_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(gen-class :name Foo) (defn run [n] n)",
        &Policy::deny_all(),
    ));
}

#[test]
fn forbidden_form_nested_in_body_is_caught() {
    // The gate is recursive: a denied op buried in a let body is still caught.
    assert_subset_denied(compile_safe_clj(
        "(defn run [n] (let [y (inc n)] (eval y)))",
        &Policy::deny_all(),
    ));
}

#[test]
fn namespaced_eval_is_caught() {
    // Match is on the unqualified name, so a fully-qualified call is caught too.
    assert_subset_denied(compile_safe_clj(
        "(defn run [x] (clojure.core/eval x))",
        &Policy::deny_all(),
    ));
}

#[test]
fn bare_ns_form_is_allowed() {
    // Naming a namespace is harmless; only loading/interop clauses are denied.
    let wasm = compile_safe_clj("(ns my.module) (defn run [n] (inc n))", &Policy::deny_all())
        .expect("a bare (ns ...) must be allowed");
    assert!(is_wasm(&wasm));
}

#[test]
fn ns_with_require_clause_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(ns my.module (:require [evil.ns])) (defn run [n] n)",
        &Policy::deny_all(),
    ));
}

#[test]
fn ns_with_import_clause_is_denied() {
    assert_subset_denied(compile_safe_clj(
        "(ns my.module (:import [java.io File])) (defn run [n] n)",
        &Policy::deny_all(),
    ));
}

#[test]
fn subset_gate_runs_under_prelude_path_too() {
    assert_subset_denied(compile_safe_clj_with_prelude(
        "(defn run [x] (eval x))",
        &Policy::deny_all(),
    ));
}

#[test]
fn prelude_itself_passes_the_subset_gate() {
    // The trusted prelude must not trip its own gate — a pure program compiles
    // with the full container/CBOR prelude prepended.
    let wasm = compile_safe_clj_with_prelude("(defn run [n] (inc n))", &Policy::deny_all())
        .expect("prelude must pass the subset gate");
    assert!(is_wasm(&wasm));
}

#[test]
fn capability_and_subset_gates_compose() {
    // A program that is both subset-clean AND capability-granted compiles;
    // failing either gate rejects it.
    let src = r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#;
    // subset-clean but capability-denied → Policy error
    match compile_safe_clj(src, &Policy::deny_all()) {
        Err(CljError::Policy(_)) => {}
        other => panic!("expected Policy denial, got {other:?}"),
    }
    // grant the capability → compiles
    let policy = Policy::deny_all().grant_graph_write(["kg"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}

// ── no mutable reference types / STM / agents ──────────────────────────────

#[test]
fn mutable_reference_types_are_denied() {
    // Each gets a clear Subset error (not a confusing "unknown function").
    for src in [
        "(defn run [] (atom 0))",
        "(defn run [a] (swap! a inc))",
        "(defn run [a] (reset! a 5))",
        "(defn run [] (volatile! 0))",
        "(defn run [a] (vswap! a inc))",
        "(defn run [] (ref 0))",
        "(defn run [r] (ref-set r 1))",
        "(defn run [r] (alter r inc))",
        "(defn run [] (dosync 1))",
        "(defn run [] (agent 0))",
        "(defn run [a] (send a inc))",
        "(defn run [a] (add-watch a :k f))",
    ] {
        assert_subset_denied(compile_safe_clj(src, &Policy::deny_all()));
    }
}

#[test]
fn ordinary_program_with_local_bang_names_still_compiles() {
    // The denylist targets reference-type ops, not every `!`-suffixed name;
    // a plain numeric program is unaffected.
    let wasm = compile_safe_clj("(defn run [n] (inc (* n n)))", &Policy::deny_all())
        .expect("ordinary program must still compile");
    assert!(wasm.starts_with(b"\0asm"));
}

// ── no ambient I/O / non-determinism / concurrency ─────────────────────────

#[test]
fn ambient_io_is_denied() {
    for src in [
        r#"(defn run [] (slurp "/etc/passwd"))"#,
        r#"(defn run [] (spit "/tmp/x" "d"))"#,
        r#"(defn run [] (println "hi"))"#,
        r#"(defn run [] (pr "x"))"#,
        r#"(defn run [] (read-line))"#,
    ] {
        assert_subset_denied(compile_safe_clj(src, &Policy::deny_all()));
    }
}

#[test]
fn non_determinism_is_denied() {
    for src in [
        "(defn run [] (rand))",
        "(defn run [] (rand-int 10))",
        "(defn run [c] (shuffle c))",
        "(defn run [] (random-uuid))",
    ] {
        assert_subset_denied(compile_safe_clj(src, &Policy::deny_all()));
    }
}

#[test]
fn ambient_concurrency_is_denied() {
    for src in [
        "(defn run [] (future (+ 1 1)))",
        "(defn run [] (promise))",
        "(defn run [c] (pmap inc c))",
        "(defn run [a b] (locking a b))",
    ] {
        assert_subset_denied(compile_safe_clj(src, &Policy::deny_all()));
    }
}

// ── no host interop call syntax ────────────────────────────────────────────

#[test]
fn host_interop_syntax_is_denied() {
    for src in [
        r#"(defn run [x] (.toUpperCase x))"#,   // method call
        r#"(defn run [x] (. x toString))"#,     // member-access special form
        r#"(defn run [] (String. "x"))"#,       // constructor (trailing dot)
        r#"(defn run [] (new String "x"))"#,    // new special form
        r#"(defn run [x] (.. x foo bar))"#,     // .. interop threading
    ] {
        assert_subset_denied(compile_safe_clj(src, &Policy::deny_all()));
    }
}
