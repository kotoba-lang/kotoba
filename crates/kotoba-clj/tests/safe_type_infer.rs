//! Phase **S1b** typed-HIR core: forward type inference over the AST. Unlike
//! the literal check, this catches mismatches on *variables* whose type is
//! statically inferable — propagated through `let` bindings and operation
//! results. `Unknown` (params, user-fn results, containers) is permissive, so
//! there are no false positives.

use kotoba_clj::{compile_safe_kotoba, CljError, Policy};

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
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (let [s "x"] (+ s 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn let_bound_number_in_string_op_is_caught() {
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (let [n 5] (str-len n)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn byte_buffer_in_arithmetic_is_caught() {
    // bytes-alloc → Bytes; using it in `+` is a type error.
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (let [b (bytes-alloc 8)] (+ b 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn type_propagates_through_rebinding() {
    // s : Str, t = s (so t : Str), then (+ t 1) → error.
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (let [s "x" t s] (+ t 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn bytes_finish_result_is_a_string() {
    // bytes-finish : Str → using it numerically is an error.
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (let [s (bytes-finish (bytes-alloc 4))] (+ s 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn if_join_of_two_strings_is_a_string() {
    // both branches Str → the binding is Str → arithmetic on it is an error.
    denied_type(compile_safe_kotoba(
        r#"(defn run [c] (let [s (if c "a" "b")] (+ s 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn string_op_on_inferred_string_is_correct() {
    // str-len of bytes-finish result (Str) is well-typed.
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (str-len (bytes-alloc 4)))"#, // Bytes in str-len → error
        &Policy::deny_all(),
    ));
}

// ── no false positives ─────────────────────────────────────────────────────

#[test]
fn let_bound_number_arithmetic_compiles() {
    let wasm = compile_safe_kotoba(
        r#"(defn run [] (let [n 5] (+ n (* n 2))))"#,
        &Policy::deny_all(),
    )
    .expect("numeric let-binding arithmetic must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn let_bound_string_in_string_op_compiles() {
    let wasm = compile_safe_kotoba(
        r#"(defn run [] (let [s "hello"] (str-len s)))"#,
        &Policy::deny_all(),
    )
    .expect("string let-binding in str-len must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn parameter_typed_values_are_permissive() {
    // `x` is a parameter → Unknown → may be used anywhere without a type error.
    let wasm = compile_safe_kotoba(r#"(defn run [x] (+ (str-len x) x))"#, &Policy::deny_all())
        .expect("operations on parameters must not be flagged");
    assert!(is_wasm(&wasm));
}

#[test]
fn if_join_of_differing_types_is_unknown() {
    // branches differ (Str vs Num) → binding is Unknown → no error (conservative).
    let wasm = compile_safe_kotoba(
        r#"(defn run [c] (let [v (if c "a" 1)] (str-len v)))"#,
        &Policy::deny_all(),
    )
    .expect("a join of differing types is Unknown, not an error");
    assert!(is_wasm(&wasm));
}

// ── cross-function inference: a call's result type is the callee's signature ──

#[test]
fn cross_function_string_return_in_arithmetic_is_caught() {
    // `greet` provably returns a string; `(+ (greet) 1)` computes on the handle.
    denied_type(compile_safe_kotoba(
        r#"(defn greet [] "hi")
           (defn run [] (+ (greet) 1))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn cross_function_bytes_finish_return_in_arithmetic_is_caught() {
    // `build` returns the Str result of bytes-finish; arithmetic on it is wrong.
    denied_type(compile_safe_kotoba(
        r#"(defn build [] (bytes-finish (bytes-alloc 4)))
           (defn run [] (+ (build) 1))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn cross_function_string_return_in_string_op_compiles() {
    // `greet` : Str → str-len of it is well-typed (no false positive).
    let wasm = compile_safe_kotoba(
        r#"(defn greet [] "hello")
           (defn run [] (str-len (greet)))"#,
        &Policy::deny_all(),
    )
    .expect("str-len of a string-returning call must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn cross_function_numeric_return_in_arithmetic_compiles() {
    // `double` : Num → arithmetic on its result is fine.
    let wasm = compile_safe_kotoba(
        r#"(defn double [n] (* n 2))
           (defn run [] (+ (double 5) 1))"#,
        &Policy::deny_all(),
    )
    .expect("arithmetic on a numeric-returning call must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn cross_function_unknown_return_stays_permissive() {
    // `id` returns its parameter → Unknown → the caller is not flagged.
    let wasm = compile_safe_kotoba(
        r#"(defn id [x] x)
           (defn run [] (str-len (id 5)))"#,
        &Policy::deny_all(),
    )
    .expect("an Unknown-returning call must stay permissive");
    assert!(is_wasm(&wasm));
}

#[test]
fn numeric_return_does_not_propagate_across_the_boundary() {
    // Soundness boundary: a `Num`-typed return may actually be a string/bytes
    // *handle* built by arithmetic (the i64 model packs handles), so a `Num`
    // return collapses to Unknown at the call boundary and is NOT flagged when
    // passed to a string op. Conservative but sound — only genuine `Str` returns
    // (literals / bytes-finish) propagate. This must compile, not error.
    let wasm = compile_safe_kotoba(
        r#"(defn mk [] 5)
           (defn run [] (str-len (mk)))"#,
        &Policy::deny_all(),
    )
    .expect("a Num-returning call must stay permissive at the boundary");
    assert!(is_wasm(&wasm));
}

#[test]
fn mutual_recursion_converges_without_false_positive() {
    // ping/pong are mutually recursive and both return Num; the fixpoint must
    // converge (not loop) and not flag the well-typed arithmetic in `run`.
    let wasm = compile_safe_kotoba(
        r#"(defn ping [n] (if (zero? n) 0 (pong (dec n))))
           (defn pong [n] (if (zero? n) 1 (ping (dec n))))
           (defn run [] (+ (ping 4) 1))"#,
        &Policy::deny_all(),
    )
    .expect("mutually-recursive numeric functions must converge and compile");
    assert!(is_wasm(&wasm));
}

// ── call-site argument check against inferred parameter requirements ─────────

#[test]
fn string_literal_to_numeric_parameter_is_caught() {
    // `add1` uses `n` in `(+ n 1)` → parameter requires a number; passing a
    // string literal is a real bug the i64 model would miscompute.
    denied_type(compile_safe_kotoba(
        r#"(defn add1 [n] (+ n 1))
           (defn run [] (add1 "x"))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn number_literal_to_string_parameter_is_caught() {
    // `slen` uses `s` in `(str-len s)` → parameter requires a string.
    denied_type(compile_safe_kotoba(
        r#"(defn slen [s] (str-len s))
           (defn run [] (slen 5))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn matching_literal_argument_compiles() {
    // Correct types — no false positive.
    let wasm = compile_safe_kotoba(
        r#"(defn add1 [n] (+ n 1))
           (defn run [] (add1 7))"#,
        &Policy::deny_all(),
    )
    .expect("a numeric literal into a numeric parameter must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn polymorphically_used_parameter_imposes_no_requirement() {
    // `x` is used both numerically (`zero?`, `+`) and as a string (`str-len`)
    // → conflicting requirements collapse to Any → the call is not flagged.
    let wasm = compile_safe_kotoba(
        r#"(defn weird [x] (if (zero? x) (str-len x) (+ x 1)))
           (defn run [] (weird "x"))"#,
        &Policy::deny_all(),
    )
    .expect("a polymorphically-used parameter must impose no requirement");
    assert!(is_wasm(&wasm));
}

#[test]
fn shadowed_parameter_imposes_no_requirement() {
    // `s` the parameter is shadowed by `(let [s 5] …)`; the numeric use is of
    // the inner `s`, so the parameter must carry no requirement (sound under
    // shadowing) — the string-literal call must compile, not error.
    let wasm = compile_safe_kotoba(
        r#"(defn f [s] (let [s 5] (+ s 1)))
           (defn run [] (f "hello"))"#,
        &Policy::deny_all(),
    )
    .expect("a shadowed parameter must impose no requirement");
    assert!(is_wasm(&wasm));
}

#[test]
fn non_literal_argument_is_not_constrained() {
    // The argument is an arithmetic expression, not a literal — it could be a
    // packed handle, so it is not checked against the string requirement.
    let wasm = compile_safe_kotoba(
        r#"(defn slen [s] (str-len s))
           (defn run [n] (slen (+ n 1)))"#,
        &Policy::deny_all(),
    )
    .expect("a non-literal argument must not be constrained (handle-pun safety)");
    assert!(is_wasm(&wasm));
}

// ── bitwise ops are numeric (variable-level + result type) ──────────────────

#[test]
fn let_bound_string_in_bitwise_op_is_caught() {
    // `s : Str` flows into a bit op (a variable the literal check can't see).
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (let [s "x"] (bit-or s 1)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn bitwise_result_is_numeric() {
    // `(bit-and a b)` is inferred Num, so using it as a string is an error.
    denied_type(compile_safe_kotoba(
        r#"(defn run [a b] (str-len (bit-and a b)))"#,
        &Policy::deny_all(),
    ));
}

// ── math builtins are numeric ───────────────────────────────────────────────

#[test]
fn math_builtins_on_string_literal_are_caught() {
    for src in [
        r#"(defn run [] (Math/sqrt "x"))"#,
        r#"(defn run [] (Math/floor "x"))"#,
        r#"(defn run [] (Math/round "x"))"#,
        r#"(defn run [] (double "x"))"#,
        r#"(defn run [] (int "x"))"#,
    ] {
        denied_type(compile_safe_kotoba(src, &Policy::deny_all()));
    }
}

#[test]
fn math_builtin_on_let_bound_string_is_caught() {
    denied_type(compile_safe_kotoba(
        r#"(defn run [] (let [s "x"] (Math/sqrt s)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn math_builtin_result_is_numeric() {
    // `(Math/sqrt n)` is inferred Num, so using it as a string is an error.
    denied_type(compile_safe_kotoba(
        r#"(defn run [n] (str-len (Math/sqrt n)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn math_builtins_on_numbers_compile() {
    let wasm = compile_safe_kotoba(
        r#"(defn run [n] (Math/sqrt (double (Math/abs (+ n 1)))))"#,
        &Policy::deny_all(),
    )
    .expect("math builtins on numeric values must compile");
    assert!(is_wasm(&wasm));
}

// ── return-type ⟂ parameter-requirement: connected at the call site ─────────

#[test]
fn string_returning_call_into_numeric_parameter_is_caught() {
    // Connects both inferences: `greet` is inferred to return Str, `add1`'s
    // parameter is inferred to require Num. The non-literal argument `(greet)`
    // is a genuine string flowing into a numeric parameter → a real bug.
    denied_type(compile_safe_kotoba(
        r#"(defn greet [] "hi")
           (defn add1 [n] (+ n 1))
           (defn run [] (add1 (greet)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn let_bound_string_into_numeric_parameter_is_caught() {
    // The argument is a variable inferred to be Str via `let` — caught too.
    denied_type(compile_safe_kotoba(
        r#"(defn add1 [n] (+ n 1))
           (defn run [] (let [s "x"] (add1 s)))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn numeric_returning_call_into_numeric_parameter_compiles() {
    // `two`'s Num return collapses to Unknown at the boundary, so the argument
    // is unconstrained — no false positive even though both sides are numeric.
    let wasm = compile_safe_kotoba(
        r#"(defn two [] 2)
           (defn add1 [n] (+ n 1))
           (defn run [] (add1 (two)))"#,
        &Policy::deny_all(),
    )
    .expect("a numeric-returning call into a numeric parameter must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn string_returning_call_into_string_op_compiles() {
    // The genuine string flows into a string parameter — well-typed.
    let wasm = compile_safe_kotoba(
        r#"(defn greet [] "hi")
           (defn shout [s] (str-len s))
           (defn run [] (shout (greet)))"#,
        &Policy::deny_all(),
    )
    .expect("a string-returning call into a string parameter must compile");
    assert!(is_wasm(&wasm));
}
