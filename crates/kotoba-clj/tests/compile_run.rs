//! End-to-end: Clojure-subset source → wasm bytes → wasmtime execution.
//!
//! The discriminating tests are the recursive ones (factorial, fibonacci,
//! mutual recursion). A flat `(+ a b)` proves almost nothing about call/local/
//! branch codegen — recursion exercises all three.

use kotoba_clj::run::{alloc_probe, compile_and_run};
use kotoba_clj::{compile_str, CljError};

#[test]
fn wasm_magic_header() {
    let wasm = compile_str("(defn id [x] x)").unwrap();
    assert_eq!(&wasm[..4], b"\0asm", "must be a real wasm module");
}

#[test]
fn arithmetic_and_nary() {
    assert_eq!(
        compile_and_run("(defn add [a b] (+ a b))", "add", &[2, 3]).unwrap(),
        5
    );
    assert_eq!(
        compile_and_run("(defn s4 [a b c d] (+ a b c d))", "s4", &[1, 2, 3, 4]).unwrap(),
        10
    );
    assert_eq!(
        compile_and_run("(defn neg [x] (- x))", "neg", &[7]).unwrap(),
        -7
    );
    assert_eq!(
        compile_and_run("(defn d [a b] (- a b))", "d", &[10, 3]).unwrap(),
        7
    );
    assert_eq!(
        compile_and_run("(defn m [a b] (* a b))", "m", &[6, 7]).unwrap(),
        42
    );
    assert_eq!(
        compile_and_run("(defn q [a b] (/ a b))", "q", &[20, 6]).unwrap(),
        3
    );
    assert_eq!(
        compile_and_run("(defn r [a b] (mod a b))", "r", &[20, 6]).unwrap(),
        2
    );
    assert_eq!(
        compile_and_run("(defn mn [a b c] (min a b c))", "mn", &[7, -3, 4]).unwrap(),
        -3
    );
    assert_eq!(
        compile_and_run("(defn mx [a b c] (max a b c))", "mx", &[7, -3, 4]).unwrap(),
        7
    );
}

#[test]
fn comparisons_and_logic() {
    assert_eq!(
        compile_and_run("(defn lt [a b] (< a b))", "lt", &[1, 2]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn lt [a b] (< a b))", "lt", &[2, 1]).unwrap(),
        0
    );
    assert_eq!(
        compile_and_run("(defn ge [a b] (>= a b))", "ge", &[2, 2]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn eq [a b] (= a b))", "eq", &[5, 5]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn nt [x] (not x))", "nt", &[0]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn nt [x] (not x))", "nt", &[9]).unwrap(),
        0
    );
    assert_eq!(
        compile_and_run("(defn a [x y] (and x y))", "a", &[1, 0]).unwrap(),
        0
    );
    assert_eq!(
        compile_and_run("(defn a [x y] (and x y))", "a", &[3, 4]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn o [x y] (or x y))", "o", &[0, 0]).unwrap(),
        0
    );
    assert_eq!(
        compile_and_run("(defn o [x y] (or x y))", "o", &[0, 7]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn p [x] (even? x))", "p", &[-4]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn p [x] (even? x))", "p", &[-3]).unwrap(),
        0
    );
    assert_eq!(
        compile_and_run("(defn p [x] (odd? x))", "p", &[7]).unwrap(),
        1
    );
    assert_eq!(
        compile_and_run("(defn p [x] (odd? x))", "p", &[8]).unwrap(),
        0
    );
}

#[test]
fn clojure_core_qualified_numeric_builtins_work() {
    let src = r#"
        (defn arithmetic [x]
          (+ (clojure.core/inc x)
             (clojure.core/dec x)
             (clojure.core/abs -3)
             (clojure.core/quot 9 2)
             (clojure.core/min 9 2 7)
             (clojure.core/max -5 -2 -9)))
        (defn predicates []
          (and (clojure.core/zero? 0)
               (clojure.core/nil? nil)
               (clojure.core/some? 1)
               (clojure.core/pos? 4)
               (clojure.core/neg? -1)
               (clojure.core/even? 8)
               (clojure.core/odd? -3)
               (clojure.core/not= 1 2 3)))
        (defn nary []
          (and (= 1 1 1) (< 1 2 3) (<= 1 1 2) (> 3 2 1) (>= 3 3 2)))
    "#;
    let wasm = compile_str(src).unwrap();
    assert_eq!(
        kotoba_clj::run::run(&wasm, "arithmetic", &[10]).unwrap(),
        27
    );
    assert_eq!(kotoba_clj::run::run(&wasm, "predicates", &[]).unwrap(), 1);
    assert_eq!(kotoba_clj::run::run(&wasm, "nary", &[]).unwrap(), 1);
}

#[test]
fn if_when_let_do() {
    let max = "(defn max [a b] (if (> a b) a b))";
    assert_eq!(compile_and_run(max, "max", &[3, 9]).unwrap(), 9);
    assert_eq!(compile_and_run(max, "max", &[9, 3]).unwrap(), 9);

    let if_without_else = "(defn f [x] (if (> x 0) (* x 2)))";
    assert_eq!(compile_and_run(if_without_else, "f", &[4]).unwrap(), 8);
    assert_eq!(compile_and_run(if_without_else, "f", &[-4]).unwrap(), 0);

    let if_not = "(defn f [x] (if-not (> x 0) 9 (* x 2)))";
    assert_eq!(compile_and_run(if_not, "f", &[4]).unwrap(), 8);
    assert_eq!(compile_and_run(if_not, "f", &[-4]).unwrap(), 9);

    let w = "(defn w [x] (when (> x 0) (* x 10)))";
    assert_eq!(compile_and_run(w, "w", &[4]).unwrap(), 40);
    assert_eq!(compile_and_run(w, "w", &[-4]).unwrap(), 0);

    let when_not = "(defn w [x] (when-not (> x 0) (* (- x) 10)))";
    assert_eq!(compile_and_run(when_not, "w", &[4]).unwrap(), 0);
    assert_eq!(compile_and_run(when_not, "w", &[-4]).unwrap(), 40);

    // sequential let: second binding sees the first
    let l = "(defn l [x] (let [a (* x 2) b (+ a 1)] (do a b)))";
    assert_eq!(compile_and_run(l, "l", &[5]).unwrap(), 11);

    let if_let = "(defn il [x] (if-let [v x] (+ v 2) 99))";
    assert_eq!(compile_and_run(if_let, "il", &[40]).unwrap(), 42);
    assert_eq!(compile_and_run(if_let, "il", &[0]).unwrap(), 99);

    let when_let = "(defn wl [x] (when-let [v x] (+ v 2)))";
    assert_eq!(compile_and_run(when_let, "wl", &[40]).unwrap(), 42);
    assert_eq!(compile_and_run(when_let, "wl", &[0]).unwrap(), 0);

    let c = "(defn c [x] (case x 0 99 1 10 (2 3) 42 5))";
    assert_eq!(compile_and_run(c, "c", &[2]).unwrap(), 42);
    assert_eq!(compile_and_run(c, "c", &[3]).unwrap(), 42);
    assert_eq!(compile_and_run(c, "c", &[1]).unwrap(), 10);
    assert_eq!(compile_and_run(c, "c", &[9]).unwrap(), 5);
}

#[test]
fn nil_keyword_and_quote_literals() {
    assert_eq!(compile_and_run("(defn n [] nil)", "n", &[]).unwrap(), 0);
    assert_eq!(
        compile_and_run("(defn k [] (str-len :demo/ok))", "k", &[]).unwrap(),
        8
    );
    assert_eq!(
        compile_and_run("(defn k [] (byte-at :demo/ok 0))", "k", &[]).unwrap(),
        b':' as i64
    );
    assert_eq!(
        compile_and_run("(defn q [] (str-len 'demo/ok))", "q", &[]).unwrap(),
        7
    );
    assert_eq!(
        compile_and_run("(defn q [] (str-len '(a b c)))", "q", &[]).unwrap(),
        7
    );
    assert_eq!(
        compile_and_run("(defn q [] (byte-at '[1 2] 0))", "q", &[]).unwrap(),
        b'[' as i64
    );
    assert_eq!(
        compile_and_run("(defn v [] (str-len #'demo/ok))", "v", &[]).unwrap(),
        7
    );
    assert_eq!(
        compile_and_run("(defn v [] (str-len (var demo/ok)))", "v", &[]).unwrap(),
        7
    );
}

#[test]
fn accepts_common_clojure_declaration_forms() {
    let src = r#"
        (comment
          (defn ignored [x] (missing x)))
        (declare later)
        (refer-clojure :exclude [max])
        (in-ns 'demo.main)
        (create-ns 'demo.extra)
        (alias 'extra 'demo.extra)
        (remove-ns 'demo.extra)
        (import '[java.time Instant])
        (gen-class)
        (set! *warn-on-reflection* true)
        (defrecord User [id name])
        (deftype Box [value])
        (defprotocol Renderable (render [this]))
        (extend-type User Renderable (render [this] (:name this)))
        (extend-protocol Renderable Box (render [this] "box"))
        (defmulti describe :kind)
        (defmethod describe :user [x] (:name x))
        (defstruct legacy-user :id :name)
        (create-struct :id :name)
        (def offset "compile-time constant" 1)
        (defonce bonus 1)
        (defn later "Adds one." {:private true} [x] (inc x))
        (defn- hidden [x] (+ x bonus))
        (defn main {:export true} [x] (hidden (+ (later x) offset)))
    "#;
    assert_eq!(compile_and_run(src, "main", &[39]).unwrap(), 42);
}

#[test]
fn accepts_top_level_do_wrapping_definitions() {
    let src = r#"
        (do
          (def offset 2)
          (defn helper [x] (+ x offset)))
        (do
          (defn main [x] (helper x)))
    "#;
    assert_eq!(compile_and_run(src, "main", &[40]).unwrap(), 42);
}

#[test]
fn accepts_single_arity_list_defn_shape() {
    let src = r#"
        (defn wrapped
          "Single arity written in Clojure's arity-list shape."
          ([x] (+ x 2)))
    "#;
    assert_eq!(compile_and_run(src, "wrapped", &[40]).unwrap(), 42);
}

#[test]
fn accepts_multi_arity_defn_for_source_calls() {
    let src = r#"
        (defn addish
          ([x] (+ x 1))
          ([x y] (+ x y)))
        (defn main [x]
          (+ (addish x) (addish x 1)))
    "#;
    assert_eq!(compile_and_run(src, "main", &[20]).unwrap(), 42);
}

#[test]
fn accepts_defn_prepost_condition_maps() {
    let src = r#"
        (defn guarded [x]
          {:pre [(pos? x)] :post [(pos? %)]}
          (+ x 4))
        (defn addish
          ([x]
           {:pre [(pos? x)]}
           (+ x 1))
          ([x y]
           {:post [(pos? %)]}
           (+ x y)))
        (defn main [x]
          (+ (guarded x) (addish x) (addish x 1)))
    "#;
    assert_eq!(compile_and_run(src, "main", &[12]).unwrap(), 42);
}

#[test]
fn accepts_threading_macros() {
    let src = r#"
        (defn first-thread [x]
          (-> x inc (+ 10) (* 2)))
        (defn last-thread [x]
          (->> x (+ 10) (* 2)))
        (defn conditional-first-thread [x]
          (cond-> x true (+ 10) (> x 0) (* 2) false (+ 1000)))
        (defn conditional-last-thread [x]
          (cond->> x true (- 100) false (+ 1000)))
        (defn named-thread [x]
          (as-> x v
            (+ v 1)
            (* v 2)))
        (defn nil-aware-first-thread [x]
          (some-> x inc (+ 10) (* 2)))
        (defn nil-aware-last-thread [x]
          (some->> x (+ 10) (* 2)))
    "#;
    assert_eq!(compile_and_run(src, "first-thread", &[10]).unwrap(), 42);
    assert_eq!(compile_and_run(src, "last-thread", &[11]).unwrap(), 42);
    assert_eq!(
        compile_and_run(src, "conditional-first-thread", &[11]).unwrap(),
        42
    );
    assert_eq!(
        compile_and_run(src, "conditional-last-thread", &[58]).unwrap(),
        42
    );
    assert_eq!(compile_and_run(src, "named-thread", &[20]).unwrap(), 42);
    assert_eq!(
        compile_and_run(src, "nil-aware-first-thread", &[10]).unwrap(),
        42
    );
    assert_eq!(
        compile_and_run(src, "nil-aware-first-thread", &[0]).unwrap(),
        0
    );
    assert_eq!(
        compile_and_run(src, "nil-aware-last-thread", &[11]).unwrap(),
        42
    );
    assert_eq!(
        compile_and_run(src, "nil-aware-last-thread", &[0]).unwrap(),
        0
    );
}

#[test]
fn recursion_factorial() {
    let src = "(defn fact [n] (if (< n 2) 1 (* n (fact (- n 1)))))";
    assert_eq!(compile_and_run(src, "fact", &[0]).unwrap(), 1);
    assert_eq!(compile_and_run(src, "fact", &[5]).unwrap(), 120);
    assert_eq!(compile_and_run(src, "fact", &[10]).unwrap(), 3_628_800);
}

#[test]
fn recursion_fibonacci() {
    let src = "(defn fib [n] (if (< n 2) n (+ (fib (- n 1)) (fib (- n 2)))))";
    assert_eq!(compile_and_run(src, "fib", &[10]).unwrap(), 55);
    assert_eq!(compile_and_run(src, "fib", &[20]).unwrap(), 6765);
}

#[test]
fn mutual_recursion() {
    // is-even?/is-odd? reference each other — proves the two-pass index table.
    let src = r#"
        (defn even? [n] (if (= n 0) 1 (odd? (- n 1))))
        (defn odd?  [n] (if (= n 0) 0 (even? (- n 1))))
    "#;
    assert_eq!(compile_and_run(src, "even?", &[10]).unwrap(), 1);
    assert_eq!(compile_and_run(src, "even?", &[7]).unwrap(), 0);
    assert_eq!(compile_and_run(src, "odd?", &[7]).unwrap(), 1);
}

#[test]
fn def_constants_inlined() {
    let src = r#"
        (def factor 10)
        (def offset (+ factor 5))
        (defn scale [x] (+ (* x factor) offset))
    "#;
    assert_eq!(compile_and_run(src, "scale", &[3]).unwrap(), 45);
}

// ---- Step 1: linear memory + cabi_realloc bump allocator --------------------

#[test]
fn module_exports_memory_and_realloc() {
    // Even a purely-numeric program now carries the linear-memory substrate.
    let wasm = compile_str("(defn id [x] x)").unwrap();
    // Two small allocations: aligned, monotonic, non-overlapping.
    let ptrs = alloc_probe(&wasm, &[(8, 16), (16, 32)]).unwrap();
    assert_eq!(ptrs.len(), 2);
    assert_eq!(ptrs[0] % 8, 0, "first ptr must be 8-aligned");
    assert_eq!(ptrs[1] % 16, 0, "second ptr must be 16-aligned");
    assert!(ptrs[1] >= ptrs[0] + 16, "allocations must not overlap");
}

#[test]
fn realloc_grows_memory_past_initial_page() {
    let wasm = compile_str("(defn id [x] x)").unwrap();
    // 1 page = 65536 bytes; ask for ~3 pages worth across allocations. The
    // probe writes+reads every region, so success proves growth (no trap) and
    // that the grown region is real, writable memory.
    let ptrs = alloc_probe(&wasm, &[(16, 100_000), (16, 100_000)]).unwrap();
    assert!(
        ptrs[1] >= ptrs[0] + 100_000,
        "second region must be disjoint"
    );
}

// ---- Step 2: Str/Bytes values backed by (ptr,len) ---------------------------

#[test]
fn string_length() {
    assert_eq!(
        compile_and_run("(defn n [] (str-len \"hello\"))", "n", &[]).unwrap(),
        5
    );
    assert_eq!(
        compile_and_run("(defn n [] (str-len \"\"))", "n", &[]).unwrap(),
        0
    );
    // multi-byte UTF-8: "あ" is 3 bytes.
    assert_eq!(
        compile_and_run("(defn n [] (str-len \"あ\"))", "n", &[]).unwrap(),
        3
    );
}

#[test]
fn byte_access() {
    // "ABC" → bytes 65,66,67
    assert_eq!(
        compile_and_run("(defn b [] (byte-at \"ABC\" 0))", "b", &[]).unwrap(),
        65
    );
    assert_eq!(
        compile_and_run("(defn b [] (byte-at \"ABC\" 2))", "b", &[]).unwrap(),
        67
    );
}

#[test]
fn strings_are_interned_and_usable_in_logic() {
    // Same literal used twice + a computed index; exercises data-segment layout
    // and the (ptr,len) handle through let/arithmetic.
    let src = r#"
        (defn sum-ends [s]
          (+ (byte-at s 0) (byte-at s (- (str-len s) 1))))
        (defn demo [] (sum-ends "AZ"))
    "#;
    // 'A'(65) + 'Z'(90) = 155
    assert_eq!(compile_and_run(src, "demo", &[]).unwrap(), 155);
}

#[test]
fn errors_are_reported() {
    assert!(
        compile_str("(defn f [x] (comment (g x) y) (+ x 1))").is_ok(),
        "expression comment bodies must not be lowered or resolved"
    );
    assert!(matches!(
        compile_str("(defn f [x] (g x))"),
        Err(CljError::Codegen(_))
    ));
    assert!(matches!(
        compile_str("(defn f [x] y)"),
        Err(CljError::Codegen(_))
    ));
    assert!(matches!(
        compile_str("(frobnicate)"),
        Err(CljError::Lower(_))
    ));
}
