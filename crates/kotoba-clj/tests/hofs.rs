//! Higher-order sequence functions (`map`/`filter`/`reduce`/…) from the prelude,
//! driven by real closures over the WASM funcref table. Each test compiles
//! `PRELUDE + (defn t [_] body)` and runs `t` on wasmtime, so green = the whole
//! closures + call_indirect + heap-vector pipeline executes end to end.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

fn eval(body: &str) -> i64 {
    let src = format!("(defn t [_] {body})");
    let wasm = compile_str_with_prelude(&src).expect("compile");
    run(&wasm, "t", &[0]).expect("run")
}

#[test]
fn map_then_reduce_sum() {
    // sum (map *10 [1 2 3]) = 10+20+30 = 60
    assert_eq!(
        eval("(reduce (fn [a x] (+ a x)) 0 (map (fn [x] (* x 10)) (vector 1 2 3)))"),
        60
    );
}

#[test]
fn map_reader_macro() {
    // (map #(* % %) [1 2 3 4]) → [1 4 9 16]; nth 3 = 16
    assert_eq!(eval("(vec-nth (map #(* % %) (vector 1 2 3 4)) 3)"), 16);
}

#[test]
fn filter_even_count() {
    assert_eq!(eval("(vec-count (filter (fn [x] (even? x)) (vector 1 2 3 4)))"), 2);
}

#[test]
fn remove_even_count() {
    assert_eq!(eval("(vec-count (remove (fn [x] (even? x)) (vector 1 2 3 4)))"), 2);
}

#[test]
fn reduce_no_init_uses_first() {
    // (reduce + [5 7 9]) = 21
    assert_eq!(eval("(reduce (fn [a x] (+ a x)) (vector 5 7 9))"), 21);
}

#[test]
fn closure_capture_inside_map() {
    // captured `k` reaches the lifted map callback through the closure record
    assert_eq!(
        eval("(let [k 100] (vec-nth (map (fn [x] (+ x k)) (vector 1 2 3)) 0))"),
        101
    );
}

#[test]
fn range_and_reduce() {
    // (reduce + 0 (range 5)) = 0+1+2+3+4 = 10
    assert_eq!(eval("(reduce (fn [a x] (+ a x)) 0 (range 5))"), 10);
}

#[test]
fn range_start_end() {
    // (range 3 7) = [3 4 5 6]; sum = 18
    assert_eq!(eval("(reduce (fn [a x] (+ a x)) 0 (range 3 7))"), 18);
}

#[test]
fn map_indexed_adds_index() {
    // (map-indexed + [10 20 30]) → [10 21 32]; nth 2 = 32
    assert_eq!(
        eval("(vec-nth (map-indexed (fn [i x] (+ i x)) (vector 10 20 30)) 2)"),
        32
    );
}

#[test]
fn some_returns_first_truthy() {
    assert_eq!(eval("(some (fn [x] (if (> x 2) x 0)) (vector 1 2 3))"), 3);
}

#[test]
fn every_true_and_false() {
    assert_eq!(eval("(every? (fn [x] (> x 0)) (vector 1 2 3))"), 1);
    assert_eq!(eval("(every? (fn [x] (> x 1)) (vector 1 2 3))"), 0);
}

#[test]
fn comp_composes_two_fns() {
    // ((comp *2 +1) 10) = (10+1)*2 = 22 — comp itself returns a closure
    assert_eq!(
        eval("((comp (fn [x] (* x 2)) (fn [x] (+ x 1))) 10)"),
        22
    );
}

#[test]
fn partial_prefixes_args() {
    // ((partial + 40) 2) = 42 — partial returns a closure capturing 40
    assert_eq!(eval("((partial (fn [a b] (+ a b)) 40) 2)"), 42);
}

#[test]
fn into_extends_presized_vector() {
    // pre-size dst (vec-conj! does not grow), then into += [3 4 5]
    assert_eq!(
        eval("(let [d (vec-make 8)] (vec-conj! d 1) (vec-conj! d 2) (vec-count (into d (vector 3 4 5))))"),
        5
    );
}

#[test]
fn keep_drops_nil_results() {
    // keep f where f returns 0 (nil) for odds → keeps doubled evens
    // [1 2 3 4] → f = (if even? (* x 10) nil) → [20 40]; count = 2
    assert_eq!(
        eval("(vec-count (keep (fn [x] (if (even? x) (* x 10) nil)) (vector 1 2 3 4)))"),
        2
    );
}

#[test]
fn higher_order_chain_map_filter_reduce() {
    // sum of squares of evens in 0..6: evens {0,2,4} → {0,4,16} → 20
    assert_eq!(
        eval(
            "(reduce (fn [a x] (+ a x)) 0
               (map (fn [x] (* x x))
                 (filter (fn [x] (even? x)) (range 6))))"
        ),
        20
    );
}
