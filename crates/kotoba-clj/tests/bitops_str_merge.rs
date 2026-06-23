//! Tests for bit-and / bit-or / bit-xor / bit-shift-left / bit-shift-right,
//! multi-arg `str` concat, and `merge`.
//!
//! Bit ops compile to WASM i64 instructions (and/or/xor/shl/shr_s).
//! `str` desugars to a chain of `str-cat` prelude calls.
//! `merge` is a prelude defn — tested here to confirm it is accessible and
//! produces the correct right-wins semantics.

use kotoba_clj::run::compile_and_run;
use kotoba_clj::{compile_str_with_prelude, run::run};

// Helper: compile + run a single-arg defn that ignores its arg via the prelude.
fn eval(body: &str) -> i64 {
    let src = format!("(defn t [_] {body})");
    let wasm = compile_str_with_prelude(&src).expect("compile");
    run(&wasm, "t", &[0]).expect("run")
}

// ---- bit-and ----------------------------------------------------------------

#[test]
fn bit_and_two_args() {
    // 12 = 0b1100, 10 = 0b1010  => AND = 0b1000 = 8
    assert_eq!(
        compile_and_run("(defn f [a b] (bit-and a b))", "f", &[12, 10]).unwrap(),
        8
    );
}

#[test]
fn bit_and_three_args() {
    // 0b111 & 0b110 & 0b100 = 0b100 = 4
    assert_eq!(
        compile_and_run(
            "(defn f [a b c] (bit-and a b c))",
            "f",
            &[0b111, 0b110, 0b100]
        )
        .unwrap(),
        4
    );
}

#[test]
fn bit_and_literal() {
    // (bit-and 12 10) => 8
    assert_eq!(
        compile_and_run("(defn f [_] (bit-and 12 10))", "f", &[0]).unwrap(),
        8
    );
}

// ---- bit-or -----------------------------------------------------------------

#[test]
fn bit_or_two_args() {
    // 0b0101 | 0b1010 = 0b1111 = 15
    assert_eq!(
        compile_and_run("(defn f [a b] (bit-or a b))", "f", &[5, 10]).unwrap(),
        15
    );
}

#[test]
fn bit_or_three_args() {
    // 0b001 | 0b010 | 0b100 = 0b111 = 7
    assert_eq!(
        compile_and_run(
            "(defn f [a b c] (bit-or a b c))",
            "f",
            &[0b001, 0b010, 0b100]
        )
        .unwrap(),
        7
    );
}

// ---- bit-xor ----------------------------------------------------------------

#[test]
fn bit_xor_two_args() {
    // 0b1111 ^ 0b0101 = 0b1010 = 10
    assert_eq!(
        compile_and_run("(defn f [a b] (bit-xor a b))", "f", &[15, 5]).unwrap(),
        10
    );
}

#[test]
fn bit_xor_toggle() {
    // 0b10110011 = 179; 0b11111111 = 255; XOR = 0b01001100 = 76
    assert_eq!(
        compile_and_run("(defn f [a b] (bit-xor a b))", "f", &[179, 255]).unwrap(),
        76
    );
}

// ---- bit-shift-left ---------------------------------------------------------

#[test]
fn bit_shift_left_by_4() {
    // 1 << 4 = 16
    assert_eq!(
        compile_and_run("(defn f [x n] (bit-shift-left x n))", "f", &[1, 4]).unwrap(),
        16
    );
}

#[test]
fn bit_shift_left_by_1() {
    // 7 << 1 = 14
    assert_eq!(
        compile_and_run("(defn f [x n] (bit-shift-left x n))", "f", &[7, 1]).unwrap(),
        14
    );
}

#[test]
fn bit_shift_left_literal() {
    assert_eq!(
        compile_and_run("(defn f [_] (bit-shift-left 1 4))", "f", &[0]).unwrap(),
        16
    );
}

// ---- bit-shift-right --------------------------------------------------------

#[test]
fn bit_shift_right_by_2() {
    // 32 >> 2 = 8
    assert_eq!(
        compile_and_run("(defn f [x n] (bit-shift-right x n))", "f", &[32, 2]).unwrap(),
        8
    );
}

#[test]
fn bit_shift_right_arithmetic() {
    // arithmetic right-shift (sign-extending): -8 >> 1 = -4
    assert_eq!(
        compile_and_run("(defn f [x n] (bit-shift-right x n))", "f", &[-8, 1]).unwrap(),
        -4
    );
}

// ---- multi-arg str ----------------------------------------------------------
// str desugars to str-cat chain which requires the PRELUDE.

#[test]
fn str_three_args() {
    // (str "a" "b" "c") => "abc" (len 3)
    assert_eq!(eval("(str-len (str \"a\" \"b\" \"c\"))"), 3);
    assert_eq!(eval("(str-eq? (str \"a\" \"b\" \"c\") \"abc\")"), 1);
}

#[test]
fn str_two_args() {
    assert_eq!(
        eval("(str-eq? (str \"hello\" \" world\") \"hello world\")"),
        1
    );
}

#[test]
fn str_one_arg_passthrough() {
    // (str "hello") => "hello"
    assert_eq!(eval("(str-eq? (str \"hello\") \"hello\")"), 1);
}

#[test]
fn str_zero_args_empty() {
    // (str) => "" (zero bytes)
    assert_eq!(eval("(str-len (str))"), 0);
}

#[test]
fn str_four_args() {
    // (str "a" "b" "c" "d") => "abcd"
    assert_eq!(eval("(str-eq? (str \"a\" \"b\" \"c\" \"d\") \"abcd\")"), 1);
}

// ---- merge ------------------------------------------------------------------
// `merge` is a prelude defn; right-map wins on collision.

#[test]
fn merge_right_wins() {
    // (merge {"a" 1} {"a" 2 "b" 3}) => {"a" 2, "b" 3}: right wins on "a"
    assert_eq!(
        eval(r#"(map-get (merge (hash-map "a" 1) (hash-map "a" 2 "b" 3)) "a")"#),
        2
    );
}

#[test]
fn merge_combines_disjoint_keys() {
    // (merge {"a" 1} {"b" 2}) => {"a" 1, "b" 2}, sum = 3
    assert_eq!(
        eval(
            r#"(let [m (merge (hash-map "a" 1) (hash-map "b" 2))]
                 (+ (map-get m "a") (map-get m "b")))"#
        ),
        3
    );
}

#[test]
fn merge_count() {
    // (merge {"a" 1 "b" 2} {"c" 3}) => 3 distinct keys
    assert_eq!(
        eval(r#"(map-count (merge (hash-map "a" 1 "b" 2) (hash-map "c" 3)))"#),
        3
    );
}
