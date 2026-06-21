//! Clojure-coverage batch — new `clojure.core` stdlib fns (PRELUDE) and the
//! `while` / `dotimes` / `doseq` / `if-some` / `when-some` iteration sugars.
//!
//! Each test compiles `PRELUDE + (defn t [_] …)` and runs `t` on wasmtime,
//! asserting an i64 derived from the result — full read→lower→codegen→run path.
//! Higher-order args are passed as real `(fn …)` closures (the closure-table /
//! `call_indirect` path), so these double as closure-capture coverage.

use kotoba_clj::compile_str_with_prelude;
use kotoba_clj::run::run;

fn eval(body: &str) -> i64 {
    let src = format!("(defn t [_] {body})");
    let wasm = compile_str_with_prelude(&src).expect("compile");
    run(&wasm, "t", &[0]).expect("run")
}

// a reusable summing closure
const SUMV: &str = "(fn [a b] (+ a b))";

// ---- subsequences ----------------------------------------------------------

#[test]
fn take_drop() {
    // sum(take 3 [10 20 30 40 50]) = 60 ; sum(drop 2 [1 2 3 4 5]) = 12
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (take 3 (vector 10 20 30 40 50)))"
        )),
        60
    );
    assert_eq!(
        eval(&format!("(reduce {SUMV} 0 (drop 2 (vector 1 2 3 4 5)))")),
        12
    );
}

#[test]
fn take_while_drop_while() {
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (take-while (fn [x] (< x 4)) (vector 1 2 3 4 1)))"
        )),
        6
    );
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (drop-while (fn [x] (< x 3)) (vector 1 2 3 4)))"
        )),
        7
    );
}

#[test]
fn butlast_take_last() {
    assert_eq!(eval("(vec-count (butlast (vector 1 2 3 4)))"), 3);
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (take-last 2 (vector 1 2 3 4)))"
        )),
        7
    );
}

#[test]
fn reverse_concat_repeat() {
    assert_eq!(eval("(vec-nth (reverse (vector 1 2 3)) 0)"), 3);
    assert_eq!(eval("(vec-count (concat (vector 1 2) (vector 3 4 5)))"), 5);
    assert_eq!(
        eval(&format!("(reduce {SUMV} 0 (concat (vector 1 2) (vector 3 4)))")),
        10
    );
    assert_eq!(eval(&format!("(reduce {SUMV} 0 (repeat 4 3))")), 12);
}

// ---- combining -------------------------------------------------------------

#[test]
fn interpose_interleave_partition() {
    // interpose 0 into [5 5 5] -> [5 0 5 0 5], count 5, sum 15
    assert_eq!(eval("(vec-count (interpose 0 (vector 5 5 5)))"), 5);
    assert_eq!(
        eval(&format!("(reduce {SUMV} 0 (interpose 0 (vector 5 5 5)))")),
        15
    );
    // interleave [1 2] [3 4 5] -> [1 3 2 4], count 4
    assert_eq!(eval("(vec-count (interleave (vector 1 2) (vector 3 4 5)))"), 4);
    // partition 2 [1 2 3 4 5] -> [[1 2] [3 4]], 2 groups, first group sums 3
    assert_eq!(eval("(vec-count (partition 2 (vector 1 2 3 4 5)))"), 2);
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (vec-nth (partition 2 (vector 1 2 3 4 5)) 0))"
        )),
        3
    );
}

// ---- dedup / ordering ------------------------------------------------------

#[test]
fn distinct_scalar() {
    assert_eq!(eval("(vec-count (distinct (vector 1 1 2 2 3 3 3)))"), 3);
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (distinct (vector 1 1 2 2 3 3 3)))"
        )),
        6
    );
}

#[test]
fn sort_ascending() {
    // sort [3 1 2] -> [1 2 3]; encode as 100*a+10*b+c = 123
    assert_eq!(
        eval(
            "(let [s (sort (vector 3 1 2))]
               (+ (* 100 (vec-nth s 0)) (+ (* 10 (vec-nth s 1)) (vec-nth s 2))))"
        ),
        123
    );
}

#[test]
fn sort_by_key() {
    // sort-by negate -> descending; first element of [1 3 2] is 3
    assert_eq!(
        eval("(vec-nth (sort-by (fn [x] (- 0 x)) (vector 1 3 2)) 0)"),
        3
    );
}

// ---- maps ------------------------------------------------------------------

#[test]
fn merge_and_merge_with() {
    assert_eq!(
        eval("(map-get (merge (hash-map \"a\" 1) (hash-map \"b\" 2)) \"b\")"),
        2
    );
    // overlapping key folded with +
    assert_eq!(
        eval(
            "(map-get (merge-with (fn [a b] (+ a b))
                                  (hash-map \"x\" 1) (hash-map \"x\" 10)) \"x\")"
        ),
        11
    );
}

#[test]
fn select_keys_zipmap_update() {
    assert_eq!(
        eval(
            "(map-count (select-keys (hash-map \"a\" 1 \"b\" 2 \"c\" 3)
                                     (vector \"a\" \"c\")))"
        ),
        2
    );
    assert_eq!(
        eval("(map-get (zipmap (vector \"k\") (vector 99)) \"k\")"),
        99
    );
    assert_eq!(
        eval("(map-get (update (hash-map \"n\" 5) \"n\" (fn [x] (+ x 1))) \"n\")"),
        6
    );
}

#[test]
fn get_in_nested() {
    assert_eq!(
        eval(
            "(get-in (hash-map \"a\" (hash-map \"b\" 42)) (vector \"a\" \"b\"))"
        ),
        42
    );
}

// ---- functional combinators ------------------------------------------------

#[test]
fn juxt_complement_fnil_keys() {
    // juxt -> [10 15], second element 15
    assert_eq!(
        eval("(vec-nth ((juxt (fn [x] (* x 2)) (fn [x] (* x 3))) 5) 1)"),
        15
    );
    // complement of (> _ 0): on 5 -> 0, on -1 -> 1
    assert_eq!(eval("((complement (fn [x] (> x 0))) 5)"), 0);
    assert_eq!(eval("((complement (fn [x] (> x 0))) -1)"), 1);
    // fnil: nonzero arg passes through
    assert_eq!(eval("((fnil (fn [x] (+ x 1)) 100) 5)"), 6);
    // max-key / min-key by negation
    assert_eq!(eval("(max-key (fn [x] (- 0 x)) 3 7)"), 3);
    assert_eq!(eval("(min-key (fn [x] (- 0 x)) 3 7)"), 7);
}

// ---- iteration sugars ------------------------------------------------------

#[test]
fn while_counts() {
    assert_eq!(
        eval(
            "(let [c (alloc 8)]
               (store64! c 0)
               (while (< (load64 c) 5) (store64! c (+ (load64 c) 1)))
               (load64 c))"
        ),
        5
    );
}

#[test]
fn dotimes_accumulates() {
    // 0+1+2+3+4 = 10
    assert_eq!(
        eval(
            "(let [c (alloc 8)]
               (store64! c 0)
               (dotimes [i 5] (store64! c (+ (load64 c) i)))
               (load64 c))"
        ),
        10
    );
}

#[test]
fn doseq_walks_vector() {
    // sum 3+4+5 = 12
    assert_eq!(
        eval(
            "(let [c (alloc 8) v (vector 3 4 5)]
               (store64! c 0)
               (doseq [x v] (store64! c (+ (load64 c) x)))
               (load64 c))"
        ),
        12
    );
}

#[test]
fn if_some_when_some() {
    // if-some binds and returns the value when non-nil (non-zero)
    assert_eq!(eval("(if-some [x 7] x 111)"), 7);
    // when-some on nil (0) takes the else path -> nil (0)
    assert_eq!(eval("(when-some [x 0] 99)"), 0);
    // when-some on non-nil runs the body
    assert_eq!(eval("(when-some [x 5] (+ x 1))"), 6);
}

// ---- strings ---------------------------------------------------------------

#[test]
fn str_cat_and_subs() {
    assert_eq!(eval("(str-eq? (str-cat \"ab\" \"cd\") \"abcd\")"), 1);
    assert_eq!(eval("(str-len (str-cat \"ab\" \"cd\"))"), 4);
    assert_eq!(eval("(str-eq? (subs \"hello\" 1 4) \"ell\")"), 1);
    assert_eq!(eval("(str-eq? (subs \"hello\" 2) \"llo\")"), 1);
}

#[test]
fn str_predicates() {
    assert_eq!(eval("(str-starts-with? \"hello\" \"he\")"), 1);
    assert_eq!(eval("(str-starts-with? \"hello\" \"lo\")"), 0);
    assert_eq!(eval("(str-includes? \"hello\" \"ell\")"), 1);
    assert_eq!(eval("(str-includes? \"hello\" \"xyz\")"), 0);
}

#[test]
fn str_join_strings() {
    assert_eq!(
        eval("(str-eq? (str-join \", \" (vector \"a\" \"b\" \"c\")) \"a, b, c\")"),
        1
    );
    // single element: no separator
    assert_eq!(eval("(str-eq? (str-join \"-\" (vector \"x\")) \"x\")"), 1);
}

#[test]
fn str_int_render() {
    assert_eq!(eval("(str-eq? (str-int 123) \"123\")"), 1);
    assert_eq!(eval("(str-eq? (str-int -45) \"-45\")"), 1);
    assert_eq!(eval("(str-eq? (str-int 0) \"0\")"), 1);
    // composition: "n=" + str-int
    assert_eq!(eval("(str-eq? (str-cat \"n=\" (str-int 7)) \"n=7\")"), 1);
}

// ---- 2-pass / pre-sized collections ----------------------------------------

#[test]
fn mapcat_concats_results() {
    // (mapcat (fn [x] [x x]) [1 2 3]) -> [1 1 2 2 3 3], sum 12
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (mapcat (fn [x] (vector x x)) (vector 1 2 3)))"
        )),
        12
    );
    assert_eq!(
        eval("(vec-count (mapcat (fn [x] (vector x x)) (vector 1 2 3)))"),
        6
    );
}

#[test]
fn frequencies_string_keyed() {
    assert_eq!(
        eval("(map-get (frequencies (vector \"a\" \"b\" \"a\" \"a\")) \"a\")"),
        3
    );
    assert_eq!(
        eval("(map-get (frequencies (vector \"a\" \"b\" \"a\" \"a\")) \"b\")"),
        1
    );
}

#[test]
fn group_by_parity() {
    // group 1..6 by even/odd; "e" group is {2,4,6} -> count 3, sum 12
    assert_eq!(
        eval(
            "(vec-count (map-get (group-by (fn [x] (if (even? x) \"e\" \"o\"))
                                           (vector 1 2 3 4 5 6)) \"e\"))"
        ),
        3
    );
    assert_eq!(
        eval(&format!(
            "(reduce {SUMV} 0 (map-get (group-by (fn [x] (if (even? x) \"e\" \"o\"))
                                                 (vector 1 2 3 4 5 6)) \"e\"))"
        )),
        12
    );
}
