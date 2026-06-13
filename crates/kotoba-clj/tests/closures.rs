//! End-to-end closures: `(fn …)` / `#(…)` → lambda-lifting → funcref table →
//! `call_indirect` on wasmtime. Each test compiles real source and runs it, so a
//! green result proves the whole pipeline (reader macro, AST lift, table/element
//! sections, env capture, indirect dispatch) actually executes.

use kotoba_clj::run::compile_and_run;

/// An anonymous fn that captures nothing, called immediately in head position.
#[test]
fn anon_fn_applied_in_head_position() {
    // ((fn [y] (+ y 1)) 41) => 42
    let src = "(defn run [n] ((fn [y] (+ y 1)) n))";
    assert_eq!(compile_and_run(src, "run", &[41]).unwrap(), 42);
}

/// `#(…)` reader macro reaches codegen via the same path.
#[test]
fn anon_fn_reader_macro() {
    // (#(* % 2) 21) => 42
    let src = "(defn run [n] (#(* % 2) n))";
    assert_eq!(compile_and_run(src, "run", &[21]).unwrap(), 42);
}

/// A closure capturing an enclosing `let` binding (the headline feature).
#[test]
fn closure_captures_let_binding() {
    // (let [k 10] ((fn [y] (+ y k)) n)) with n=5 => 15
    let src = "(defn run [n] (let [k 10] ((fn [y] (+ y k)) n)))";
    assert_eq!(compile_and_run(src, "run", &[5]).unwrap(), 15);
}

/// A closure stored in a `let` and called by name (closure value, not literal).
#[test]
fn closure_bound_then_called() {
    let src = "(defn run [n] (let [f (fn [y] (* y y))] (f n)))";
    assert_eq!(compile_and_run(src, "run", &[7]).unwrap(), 49);
}

/// Higher-order: a function receives a closure parameter and invokes it.
#[test]
fn higher_order_parameter() {
    let src = "
        (defn apply1 [f x] (f x))
        (defn run [n] (apply1 (fn [y] (+ y 100)) n))";
    assert_eq!(compile_and_run(src, "run", &[5]).unwrap(), 105);
}

/// Capture two variables of different provenance (a param and a let).
#[test]
fn closure_captures_param_and_let() {
    // run(a) = let b=3 in ((fn [y] (+ a b y)) 10)
    let src = "(defn run [a] (let [b 3] ((fn [y] (+ a b y)) 10)))";
    assert_eq!(compile_and_run(src, "run", &[5]).unwrap(), 18);
}

/// Two distinct closures over the same variable get independent table slots.
#[test]
fn two_closures_distinct_behaviour() {
    let src = "
        (defn pick [g h x] (+ (g x) (h x)))
        (defn run [n] (pick (fn [y] (* y 2)) (fn [y] (+ y 1)) n))";
    // pick(*2, +1, 10) = 20 + 11 = 31
    assert_eq!(compile_and_run(src, "run", &[10]).unwrap(), 31);
}

/// A closure returned from a function and applied later (escapes its scope) —
/// the captured value must live on the heap record, not a stack local.
#[test]
fn returned_closure_keeps_capture() {
    let src = "
        (defn adder [k] (fn [y] (+ y k)))
        (defn run [n] (let [add5 (adder 5)] (add5 n)))";
    assert_eq!(compile_and_run(src, "run", &[37]).unwrap(), 42);
}

/// Nested closures: inner captures a variable that is itself a capture of the
/// outer closure — exercises transitive capture through two records.
#[test]
fn nested_closure_transitive_capture() {
    // make(a) returns (fn [b] (fn [c] (+ a b c)))
    let src = "
        (defn make [a] (fn [b] (fn [c] (+ a b c))))
        (defn run [n]
          (let [f (make 100)
                g (f 20)]
            (g n)))";
    assert_eq!(compile_and_run(src, "run", &[3]).unwrap(), 123);
}
