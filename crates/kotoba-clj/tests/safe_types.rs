//! Phase **S1b** (first slice): literal type checking. The i64-only value model
//! treats a string/keyword as a *handle*, so `(+ "a" 1)` silently does handle
//! arithmetic. safe-clj rejects a numeric operator applied to a non-numeric
//! literal — the certain core of a future typed HIR (no false positives:
//! variables, which could hold a number at runtime, are never flagged).

use kotoba_clj::{compile_safe_clj, CljError, Policy};

fn denied_type(res: Result<Vec<u8>, CljError>) {
    assert!(
        matches!(res, Err(CljError::Type(_))),
        "expected Type denial, got {res:?}"
    );
}

#[test]
fn add_string_literal_is_rejected() {
    denied_type(compile_safe_clj(r#"(defn run [] (+ "a" 1))"#, &Policy::deny_all()));
}

#[test]
fn arithmetic_ops_on_string_literal_rejected() {
    for op in ["+", "-", "*", "/", "quot", "mod", "rem", "min", "max"] {
        let src = format!(r#"(defn run [] ({op} "x" 2))"#);
        denied_type(compile_safe_clj(&src, &Policy::deny_all()));
    }
}

#[test]
fn unary_numeric_ops_on_string_literal_rejected() {
    for op in ["inc", "dec", "abs", "zero?", "pos?", "neg?", "even?", "odd?"] {
        let src = format!(r#"(defn run [] ({op} "x"))"#);
        denied_type(compile_safe_clj(&src, &Policy::deny_all()));
    }
}

#[test]
fn keyword_literal_in_arithmetic_is_rejected() {
    denied_type(compile_safe_clj(
        r#"(defn run [] (+ :kw 1))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn nested_arithmetic_on_string_literal_is_caught() {
    denied_type(compile_safe_clj(
        r#"(defn run [n] (if (> n 0) (* "bad" n) 0))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn arithmetic_on_string_literal_anywhere_in_args() {
    // The bad literal is the 2nd argument, not the 1st.
    denied_type(compile_safe_clj(
        r#"(defn run [n] (+ n "tail"))"#,
        &Policy::deny_all(),
    ));
}

// ── symmetric case: string operators on numeric literals ───────────────────

#[test]
fn str_len_on_integer_literal_is_rejected() {
    denied_type(compile_safe_clj(r#"(defn run [] (str-len 5))"#, &Policy::deny_all()));
}

#[test]
fn byte_at_on_numeric_first_arg_is_rejected() {
    // First arg (the string) is numeric; the index (2nd) being numeric is fine.
    denied_type(compile_safe_clj(
        r#"(defn run [] (byte-at 42 0))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn str_len_on_float_literal_is_rejected() {
    denied_type(compile_safe_clj(
        r#"(defn run [] (str-len 3.14))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn byte_at_with_non_numeric_index_is_rejected() {
    // The index must be a number — a string/keyword/char literal there is read
    // as a byte offset (handle bits), silently.
    for idx in [r#""x""#, ":k", r#"\a"#] {
        let src = format!(r#"(defn run [] (byte-at "ab" {idx}))"#);
        denied_type(compile_safe_clj(&src, &Policy::deny_all()));
    }
}

#[test]
fn byte_at_on_string_literal_with_numeric_index_is_fine() {
    // Correct usage: string first, numeric index — must compile.
    let wasm = compile_safe_clj(r#"(defn run [] (byte-at "hi" 0))"#, &Policy::deny_all())
        .expect("byte-at on a string literal with a numeric index must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn str_len_on_variable_is_not_flagged() {
    let wasm = compile_safe_clj("(defn run [s] (str-len s))", &Policy::deny_all())
        .expect("str-len on a variable must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

// ── numeric comparisons on string literals ─────────────────────────────────

#[test]
fn comparison_ops_on_string_literal_rejected() {
    for op in ["<", ">", "<=", ">="] {
        // string literal as either operand
        let a = format!(r#"(defn run [n] ({op} "a" n))"#);
        let b = format!(r#"(defn run [n] ({op} n "z"))"#);
        denied_type(compile_safe_clj(&a, &Policy::deny_all()));
        denied_type(compile_safe_clj(&b, &Policy::deny_all()));
    }
}

#[test]
fn equality_on_string_literal_is_not_flagged() {
    // `=` is deliberately excluded (handle equality is defensible); must compile.
    let wasm = compile_safe_clj(r#"(defn run [n] (= n "x"))"#, &Policy::deny_all())
        .expect("`=` with a string literal must compile (not a numeric comparison)");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn numeric_comparison_on_numbers_compiles() {
    let wasm = compile_safe_clj("(defn run [n] (if (< n 10) n 0))", &Policy::deny_all())
        .expect("numeric comparison on numbers/variables must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

// ── container literals are non-numeric handles too ─────────────────────────

#[test]
fn vector_literal_in_arithmetic_is_rejected() {
    denied_type(compile_safe_clj(
        r#"(defn run [] (+ [1 2] 3))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn map_literal_in_arithmetic_is_rejected() {
    denied_type(compile_safe_clj(
        r#"(defn run [] (* {:a 1} 2))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn set_literal_in_arithmetic_is_rejected() {
    denied_type(compile_safe_clj(
        r#"(defn run [] (- #{1 2} 1))"#,
        &Policy::deny_all(),
    ));
}

#[test]
fn char_literal_in_arithmetic_is_rejected() {
    denied_type(compile_safe_clj(r#"(defn run [] (+ \a 1))"#, &Policy::deny_all()));
}

#[test]
fn vector_literal_in_comparison_is_rejected() {
    denied_type(compile_safe_clj(
        r#"(defn run [n] (< [1] n))"#,
        &Policy::deny_all(),
    ));
}

// ── division by literal zero (a statically-knowable trap) ──────────────────

#[test]
fn division_by_literal_zero_is_rejected() {
    for op in ["/", "mod", "rem", "quot"] {
        let src = format!(r#"(defn run [n] ({op} n 0))"#);
        denied_type(compile_safe_clj(&src, &Policy::deny_all()));
    }
}

#[test]
fn division_by_nonzero_literal_compiles() {
    let wasm = compile_safe_clj("(defn run [n] (quot n 7))", &Policy::deny_all())
        .expect("division by a non-zero literal must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn division_by_variable_is_not_flagged() {
    // A dynamic divisor could be non-zero at runtime → not statically rejected.
    let wasm = compile_safe_clj("(defn run [n d] (/ n d))", &Policy::deny_all())
        .expect("division by a variable must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn zero_dividend_is_fine() {
    // 0 as the *dividend* (first arg) is not a trap — only divisors matter.
    let wasm = compile_safe_clj("(defn run [n] (quot 0 n))", &Policy::deny_all())
        .expect("zero dividend must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

// ── no false positives ─────────────────────────────────────────────────────

#[test]
fn arithmetic_on_numbers_compiles() {
    let wasm = compile_safe_clj(
        "(defn run [n] (+ (* n n) (- n 1)))",
        &Policy::deny_all(),
    )
    .expect("numeric arithmetic must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn arithmetic_on_variables_is_not_flagged() {
    // `s` could hold a number at runtime; only *literals* are statically known
    // to be non-numeric, so a variable argument must not be rejected.
    let wasm = compile_safe_clj("(defn run [s n] (+ s n))", &Policy::deny_all())
        .expect("arithmetic on variables must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn string_literal_in_string_op_is_fine() {
    // str-len legitimately takes a string literal — not a numeric op, not flagged.
    let wasm = compile_safe_clj(r#"(defn run [] (str-len "hello"))"#, &Policy::deny_all())
        .expect("string operator on a string literal must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn string_literal_as_kqe_argument_is_fine() {
    // A graph cid string literal is not arithmetic — must not be flagged.
    let src = r#"(defn run [] (kqe-assert! "kg" "s" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["kg"]);
    assert!(compile_safe_clj(src, &policy).is_ok());
}
