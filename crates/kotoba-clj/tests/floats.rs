//! f64 floating-point support: float literals, arithmetic, mixed int/float
//! promotion, float comparisons, and coercions.
//!
//! ## Value model under test
//!
//! The compiler has a single 64-bit value slot. A float occupies that slot as
//! its **IEEE-754 bit pattern** (no runtime tag); the exported `run` returns
//! the raw `i64`. A float-returning function therefore yields the bit pattern,
//! which these tests decode with `f64::from_bits(result as u64)`. A
//! comparison/coercion that yields an integer (`<`, `int`, `Math/round`) is
//! asserted directly as an i64.

use kotoba_clj::run::compile_and_run;

/// Run `src`'s `func` (no args) and decode the i64 result as an f64 bit pattern.
fn run_f64(src: &str) -> f64 {
    let bits = compile_and_run(src, "f", &[]).unwrap();
    f64::from_bits(bits as u64)
}

/// Run `src`'s `func` (no args) and return the raw i64 result.
fn run_i64(src: &str) -> i64 {
    compile_and_run(src, "f", &[]).unwrap()
}

// ── float literals ──────────────────────────────────────────────────────────

#[test]
fn float_literals_roundtrip() {
    assert_eq!(run_f64("(defn f [] 0.99)"), 0.99);
    assert_eq!(run_f64("(defn f [] 10.4)"), 10.4);
    assert_eq!(run_f64("(defn f [] 1.0)"), 1.0);
    assert_eq!(run_f64("(defn f [] -8.0)"), -8.0);
}

// ── float arithmetic ────────────────────────────────────────────────────────

#[test]
fn float_division() {
    // (/ 1.0 4.0) → 0.25 — the canonical case the i64-only compiler got wrong.
    assert_eq!(run_f64("(defn f [] (/ 1.0 4.0))"), 0.25);
}

#[test]
fn float_multiplication() {
    assert_eq!(run_f64("(defn f [] (* 2.5 4.0))"), 10.0);
}

#[test]
fn float_addition_and_subtraction() {
    assert_eq!(run_f64("(defn f [] (+ 0.1 0.2))"), 0.1 + 0.2);
    assert_eq!(run_f64("(defn f [] (- 10.4 0.4))"), 10.4 - 0.4);
    // n-ary fold
    assert_eq!(run_f64("(defn f [] (+ 1.0 2.0 3.0 0.5))"), 6.5);
}

#[test]
fn float_unary_negate() {
    assert_eq!(run_f64("(defn f [] (- 8.0))"), -8.0);
}

// ── mixed int/float promotion ───────────────────────────────────────────────

#[test]
fn mixed_int_float_promotes_to_f64() {
    // (* 5 0.4) → 2.0  (int 5 promoted to 5.0)
    assert_eq!(run_f64("(defn f [] (* 5 0.4))"), 2.0);
    // (+ 1 0.5) → 1.5
    assert_eq!(run_f64("(defn f [] (+ 1 0.5))"), 1.5);
    // (/ 7 2.0) → 3.5  (true division, not integer 3)
    assert_eq!(run_f64("(defn f [] (/ 7 2.0))"), 3.5);
    // nested: (* (+ 1 0.5) 2) → 3.0
    assert_eq!(run_f64("(defn f [] (* (+ 1 0.5) 2))"), 3.0);
}

// ── float comparisons (yield integer boolean 1/0) ──────────────────────────

#[test]
fn float_comparisons() {
    assert_eq!(run_i64("(defn f [] (< 0.1 0.2))"), 1);
    assert_eq!(run_i64("(defn f [] (< 0.2 0.1))"), 0);
    assert_eq!(run_i64("(defn f [] (> 2.5 1.5))"), 1);
    assert_eq!(run_i64("(defn f [] (<= 1.0 1.0))"), 1);
    assert_eq!(run_i64("(defn f [] (>= 1.0 2.0))"), 0);
    assert_eq!(run_i64("(defn f [] (= 0.5 0.5))"), 1);
    assert_eq!(run_i64("(defn f [] (= 0.5 0.6))"), 0);
    // mixed comparison promotes the int operand
    assert_eq!(run_i64("(defn f [] (< 1 1.5))"), 1);
    assert_eq!(run_i64("(defn f [] (> 2 1.5))"), 1);
    // n-ary chained comparison
    assert_eq!(run_i64("(defn f [] (< 0.1 0.2 0.3))"), 1);
    assert_eq!(run_i64("(defn f [] (< 0.1 0.3 0.2))"), 0);
}

// ── coercions ───────────────────────────────────────────────────────────────

#[test]
fn double_coercion() {
    // (double 3) → 3.0
    assert_eq!(run_f64("(defn f [] (double 3))"), 3.0);
    // (double 0.5) → 0.5 (passthrough)
    assert_eq!(run_f64("(defn f [] (double 0.5))"), 0.5);
    // (double x) on an arg: promote a runtime int to a float, then float-multiply
    assert_eq!(
        f64::from_bits(
            compile_and_run("(defn f [x] (* (double x) 0.5))", "f", &[7]).unwrap() as u64
        ),
        3.5
    );
}

#[test]
fn int_truncation() {
    // (int 3.9) → 3  (truncate toward zero)
    assert_eq!(run_i64("(defn f [] (int 3.9))"), 3);
    // (int -3.9) → -3 (toward zero, not floor)
    assert_eq!(run_i64("(defn f [] (int -3.9))"), -3);
    // (int 7) → 7 (passthrough)
    assert_eq!(run_i64("(defn f [] (int 7))"), 7);
    // round-trip: int of a float computation
    assert_eq!(run_i64("(defn f [] (int (* 2.5 4.0)))"), 10);
}

#[test]
fn math_round() {
    // ties away from zero (Clojure semantics)
    assert_eq!(run_i64("(defn f [] (Math/round 2.5))"), 3);
    assert_eq!(run_i64("(defn f [] (Math/round 2.4))"), 2);
    assert_eq!(run_i64("(defn f [] (Math/round -2.5))"), -3);
    assert_eq!(run_i64("(defn f [] (Math/round 0.99))"), 1);
}

#[test]
fn math_floor_ceil() {
    // floor/ceil return floats (Clojure returns double)
    assert_eq!(run_f64("(defn f [] (Math/floor 2.9))"), 2.0);
    assert_eq!(run_f64("(defn f [] (Math/floor -2.1))"), -3.0);
    assert_eq!(run_f64("(defn f [] (Math/ceil 2.1))"), 3.0);
    assert_eq!(run_f64("(defn f [] (Math/ceil -2.9))"), -2.0);
}

#[test]
fn math_abs_and_sqrt() {
    // float abs preserves float-ness
    assert_eq!(run_f64("(defn f [] (Math/abs -8.5))"), 8.5);
    assert_eq!(run_f64("(defn f [] (Math/abs 8.5))"), 8.5);
    // integer abs still works through Math/abs
    assert_eq!(run_i64("(defn f [] (Math/abs -7))"), 7);
    // sqrt
    assert_eq!(run_f64("(defn f [] (Math/sqrt 16.0))"), 4.0);
    assert_eq!(run_f64("(defn f [] (Math/sqrt 2.0))"), 2.0_f64.sqrt());
}

// ── float through if-branches ───────────────────────────────────────────────

#[test]
fn float_if_both_branches() {
    // (if true 1.5 2.5) → 1.5 ; the result is recognized as float and decodes.
    assert_eq!(run_f64("(defn f [] (if (< 1 2) 1.5 2.5))"), 1.5);
    assert_eq!(run_f64("(defn f [] (if (> 1 2) 1.5 2.5))"), 2.5);
}

// ── compound: a realistic float-heavy expression (himawari-style) ───────────

#[test]
fn compound_float_expression() {
    // weighted blend: 0.99 * prev + 0.01 * new, all-float, then a comparison.
    let src = r#"
        (defn blend [prev new]
          (+ (* 0.99 (double prev)) (* 0.01 (double new))))
    "#;
    // prev=100, new=0 → 99.0
    let bits = compile_and_run(src, "blend", &[100, 0]).unwrap();
    assert!((f64::from_bits(bits as u64) - 99.0).abs() < 1e-9);
}

// ── himawari-derived natural-float forms ────────────────────────────────────
//
// These are float expressions lifted verbatim (shape-preserving) from real
// himawari solar-manufacturing cells (ingot_wafer / outbound_logistics /
// cell_process). The whole `.cljc` cells use maps/sets/strings the subset
// can't represent, but the FLOAT SUB-EXPRESSIONS — previously broken under
// the i64-only compiler — now compile and compute the correct numeric result.

#[test]
fn himawari_ingot_wafer_kerf_math() {
    // ingot_wafer: kerf-generated = round(wafered_si_g * (k / (1 - k)))
    // with k = 0.40 (diamond-wire kerf fraction), wafered_si_g param.
    let src = r#"
        (defn kerf-generated [wafered-si-g]
          (int (Math/round (* (double wafered-si-g) (/ 0.40 (- 1.0 0.40))))))
    "#;
    // 0.40/(1-0.40) = 0.6666...; * 1000 = 666.66.. → round 667
    assert_eq!(
        compile_and_run(src, "kerf-generated", &[1000]).unwrap(),
        667
    );
}

#[test]
fn himawari_ingot_wafer_recovery_ceil() {
    // ingot_wafer: recovered = ceil(kerf_generated_g * 0.90)
    let src = r#"
        (defn recovered [kerf-g]
          (long (Math/ceil (* (double kerf-g) 0.90))))
    "#;
    // 667 * 0.90 = 600.3 → ceil 601
    assert_eq!(compile_and_run(src, "recovered", &[667]).unwrap(), 601);
}

#[test]
fn himawari_outbound_declared_value_round() {
    // outbound_logistics: declared = round(double(declaredValueUsd))
    let src = r#"
        (defn declared [v]
          (long (Math/round (double v))))
    "#;
    assert_eq!(compile_and_run(src, "declared", &[42]).unwrap(), 42);
}

#[test]
fn himawari_cell_process_dre_floor_compare() {
    // cell_process: G3 floor — achieved DRE must be ≥ 0.99 (MIN_DRE).
    // (dre 0.995 case vs the 1.0 substituted case)
    let src = r#"
        (defn meets-floor [substituted?]
          (let [dre (if (= substituted? 1) 1.0 0.995)]
            (if (>= dre 0.99) 1 0)))
    "#;
    assert_eq!(compile_and_run(src, "meets-floor", &[1]).unwrap(), 1);
    assert_eq!(compile_and_run(src, "meets-floor", &[0]).unwrap(), 1);
}

#[test]
fn himawari_ingot_wafer_thickness_cm() {
    // ingot_wafer: t-cm = thickness_um / 10000.0 ; r-cm = diameter_mm / 20.0
    let src = r#"
        (defn t-cm [thickness-um] (/ (double thickness-um) 10000.0))
        (defn r-cm [diameter-mm] (/ (double diameter-mm) 20.0))
    "#;
    // 150 um → 0.015 cm
    assert_eq!(
        f64::from_bits(compile_and_run(src, "t-cm", &[150]).unwrap() as u64),
        0.015
    );
    // 210 mm → 10.5 cm
    assert_eq!(
        f64::from_bits(compile_and_run(src, "r-cm", &[210]).unwrap() as u64),
        10.5
    );
}

// ── symbol type env: def and let propagate float-ness ───────────────────────

#[test]
fn float_def_constant_in_expr() {
    // (def ^:private MIN_DRE 0.99) used in a comparison with a float literal.
    // MIN_DRE must be recognised as float so (>= 0.995 MIN_DRE) uses f64 GE.
    let src = r#"
        (def ^:private MIN_DRE 0.99)
        (defn f [] (if (>= 0.995 MIN_DRE) 1 0))
    "#;
    // 0.995 >= 0.99 → true → 1
    assert_eq!(compile_and_run(src, "f", &[]).unwrap(), 1);

    let src2 = r#"
        (def ^:private MIN_DRE 0.99)
        (defn f [] (if (>= 0.5 MIN_DRE) 1 0))
    "#;
    // 0.5 < 0.99 → false → 0
    assert_eq!(compile_and_run(src2, "f", &[]).unwrap(), 0);
}

#[test]
fn float_let_binding_propagates() {
    // (let [r 0.99] (* 100.0 r)) → 99.0
    let bits = compile_and_run("(defn f [] (let [r 0.99] (* 100.0 r)))", "f", &[]).unwrap();
    let v = f64::from_bits(bits as u64);
    assert!((v - 99.0).abs() < 1e-9, "expected 99.0, got {v}");
}

#[test]
fn float_def_constant_arithmetic() {
    // (def K 0.4) ; K/(1-K) = 0.666...
    let src = r#"
        (def K 0.4)
        (defn f [] (/ K (- 1.0 K)))
    "#;
    let bits = compile_and_run(src, "f", &[]).unwrap();
    let v = f64::from_bits(bits as u64);
    assert!((v - (0.4 / 0.6)).abs() < 1e-9, "expected 0.666..., got {v}");
}

#[test]
fn int_let_binding_not_promoted() {
    // (let [n 5] (+ n 1)) → 6 (integer, not float)
    assert_eq!(
        compile_and_run("(defn f [] (let [n 5] (+ n 1)))", "f", &[]).unwrap(),
        6
    );
}

#[test]
fn float_let_shadows_def() {
    // A let binding with the same name as a float def but integer value
    // should shadow the def and NOT be treated as float.
    let src = r#"
        (def K 0.4)
        (defn f [] (let [K 5] (+ K 1)))
    "#;
    // Should be integer 6, not float
    assert_eq!(compile_and_run(src, "f", &[]).unwrap(), 6);
}
