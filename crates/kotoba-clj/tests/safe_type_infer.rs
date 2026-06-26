//! Phase **S1b** typed-HIR core: forward type inference over the AST. Unlike
//! the literal check, this catches mismatches on *variables* whose type is
//! statically inferable — propagated through `let` bindings and operation
//! results. `Unknown` (params, user-fn results, containers) is permissive, so
//! there are no false positives.

use kotoba_clj::{compile_safe_clj, CljError, Policy};

fn denied_type(res: Result<Vec<u8>, CljError>) {
    assert!(
        matches!(res, Err(CljError::Type(_))),
        "expected Type denial, got {res:?}"
    );
}

fn is_wasm(b: &[u8]) -> bool {
    b.starts_with(b"\0asm")
}

// ── the new power: variable-level mismatches (literals checks miss these) ───

#[test]
fn let_bound_string_in_arithmetic_is_caught() {
    // `s` is a Var in `(+ s 1)` — the literal check cannot see it; inference can.
    denied_type(compile_safe_clj(
        r#"(defn run [] (let [s "x"] (+ s 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn let_bound_number_in_string_op_is_caught() {
    denied_type(compile_safe_clj(
        r#"(defn run [] (let [n 5] (str-len n)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn byte_buffer_in_arithmetic_is_caught() {
    // bytes-alloc → Bytes; using it in `+` is a type error.
    denied_type(compile_safe_clj(
        r#"(defn run [] (let [b (bytes-alloc 8)] (+ b 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn type_propagates_through_rebinding() {
    // s : Str, t = s (so t : Str), then (+ t 1) → error.
    denied_type(compile_safe_clj(
        r#"(defn run [] (let [s "x" t s] (+ t 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn bytes_finish_result_is_a_string() {
    // bytes-finish : Str → using it numerically is an error.
    denied_type(compile_safe_clj(
        r#"(defn run [] (let [s (bytes-finish (bytes-alloc 4))] (+ s 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn if_join_of_two_strings_is_a_string() {
    // both branches Str → the binding is Str → arithmetic on it is an error.
    denied_type(compile_safe_clj(
        r#"(defn run [c] (let [s (if c "a" "b")] (+ s 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn string_op_on_inferred_string_is_correct() {
    // str-len of bytes-finish result (Str) is well-typed.
    denied_type(compile_safe_clj(
        r#"(defn run [] (str-len (bytes-alloc 4)))"#, // Bytes in str-len → error
        &Policy::deny_all(),
    ));
}

// ── no false positives ─────────────────────────────────────────────────────

#[test]
fn let_bound_number_arithmetic_compiles() {
    let wasm = compile_safe_clj(
        r#"(defn run [] (let [n 5] (+ n (* n 2))))"#,
        &Policy::deny_all(),
    )
    .expect("numeric let-binding arithmetic must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn let_bound_string_in_string_op_compiles() {
    let wasm = compile_safe_clj(
        r#"(defn run [] (let [s "hello"] (str-len s)))"#,
        &Policy::deny_all(),
    )
    .expect("string let-binding in str-len must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn parameter_typed_values_are_permissive() {
    // `x` is a parameter → Unknown → may be used anywhere without a type error.
    let wasm = compile_safe_clj(
        r#"(defn run [x] (+ (str-len x) x))"#,
        &Policy::deny_all(),
    )
    .expect("operations on parameters must not be flagged");
    assert!(is_wasm(&wasm));
}

#[test]
fn if_join_of_differing_types_is_unknown() {
    // branches differ (Str vs Num) → binding is Unknown → no error (conservative).
    let wasm = compile_safe_clj(
        r#"(defn run [c] (let [v (if c "a" 1)] (str-len v)))"#,
        &Policy::deny_all(),
    )
    .expect("a join of differing types is Unknown, not an error");
    assert!(is_wasm(&wasm));
}
