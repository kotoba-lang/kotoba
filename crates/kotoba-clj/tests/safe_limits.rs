//! The policy's `:memory-pages` budget is applied to the emitted module's
//! linear-memory **maximum**, so the wasm engine enforces it (defense-in-depth
//! alongside the runtime's gas/StoreLimits). A safe module physically cannot
//! grow past its budget, and a budget smaller than the cell's static data is a
//! hard compile error.

use kotoba_clj::{compile_safe_kotoba, CljError, Limits, Policy};

#[test]
fn capped_module_is_valid_and_runs() {
    // The memory-capped module must still be valid wasm and execute correctly.
    let wasm = compile_safe_kotoba("(defn run [n] (* n n))", &Policy::deny_all()).unwrap();
    let out = kotoba_clj::run::run(&wasm, "run", &[6]).expect("capped module must run");
    assert_eq!(out, 36);
}

#[test]
fn default_budget_compiles_ordinary_cells() {
    // The default 4-page budget comfortably fits ordinary cells (small static
    // data), including under the prelude.
    let policy = Policy::deny_all();
    assert!(compile_safe_kotoba("(defn run [n] (+ (* n n) 1))", &policy).is_ok());
}

#[test]
fn budget_smaller_than_static_data_is_rejected() {
    // A cell whose string literal alone exceeds one 64 KiB page cannot fit in a
    // 1-page budget → hard compile error naming the shortfall.
    let big = "x".repeat(70_000);
    let src = format!(r#"(defn run [] (str-len "{big}"))"#);
    let policy = Policy::deny_all().with_limits(Limits {
        memory_pages: 1,
        fuel: 1_000_000,
        max_call_depth: 128,
        max_output_bytes: 65_536,
    });
    match compile_safe_kotoba(&src, &policy) {
        Err(CljError::Codegen(msg)) => {
            assert!(msg.contains("memory page"), "{msg}");
        }
        other => panic!("expected a memory-budget Codegen error, got {other:?}"),
    }
}

#[test]
fn oversized_memory_budget_is_rejected() {
    // A budget above the wasm32 page max (65536) would emit an invalid module;
    // reject it at compile time with a clear policy error instead.
    let policy = Policy::deny_all().with_limits(Limits {
        memory_pages: 100_000,
        fuel: 1_000_000,
        max_call_depth: 128,
        max_output_bytes: 65_536,
    });
    match compile_safe_kotoba("(defn run [n] n)", &policy) {
        Err(CljError::Policy(msg)) => assert!(msg.contains("wasm32 maximum"), "{msg}"),
        other => panic!("expected an over-max Policy error, got {other:?}"),
    }
}

#[test]
fn budget_at_exactly_the_wasm32_max_is_accepted() {
    // 65536 pages is the boundary — valid.
    let policy = Policy::deny_all().with_limits(Limits {
        memory_pages: 65_536,
        fuel: 1_000_000,
        max_call_depth: 128,
        max_output_bytes: 65_536,
    });
    assert!(compile_safe_kotoba("(defn run [n] n)", &policy).is_ok());
}

#[test]
fn generous_budget_fits_the_same_big_cell() {
    // The same large-literal cell compiles under a budget that fits it.
    let big = "x".repeat(70_000);
    let src = format!(r#"(defn run [] (str-len "{big}"))"#);
    let policy = Policy::deny_all().with_limits(Limits {
        memory_pages: 8,
        fuel: 1_000_000,
        max_call_depth: 128,
        max_output_bytes: 65_536,
    });
    assert!(
        compile_safe_kotoba(&src, &policy).is_ok(),
        "an 8-page budget must fit a ~70 KiB literal"
    );
}
