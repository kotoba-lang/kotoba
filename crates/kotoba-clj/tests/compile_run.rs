//! End-to-end: Kotoba/EDN-subset source → wasm bytes → wasmtime execution.
//!
//! The discriminating tests are the recursive ones (factorial, fibonacci,
//! mutual recursion). A flat `(+ a b)` proves almost nothing about call/local/
//! branch codegen — recursion exercises all three.

use kotoba_clj::run::{alloc_probe, compile_and_run, run, run_with_fuel};
use kotoba_clj::{compile_str, CljError};

#[test]
fn wasm_magic_header() {
    let wasm = compile_str("(defn id [x] x)").unwrap();
    assert_eq!(&wasm[..4], b"\0asm", "must be a real wasm module");
}

#[test]
fn run_with_fuel_executes_within_budget() {
    let wasm = compile_str("(defn add [a b] (+ a b))").unwrap();
    assert_eq!(run_with_fuel(&wasm, "add", &[2, 3], 1_000_000).unwrap(), 5);
}

#[test]
fn run_with_fuel_traps_on_unbounded_loop() {
    // A recursion that never bottoms out burns instructions forever; a small
    // fuel budget must trap rather than hang the host.
    let wasm = compile_str("(defn spin [x] (spin (+ x 1)))").unwrap();
    let err = run_with_fuel(&wasm, "spin", &[0], 10_000).unwrap_err();
    assert!(matches!(err, CljError::Run(_)), "expected a run/trap error");
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
    // (and 3 4) → 4  — Clojure `and` returns the last value when all are truthy
    // (was incorrectly 1 when `and` normalised to a boolean; fixed by FIX 1)
    assert_eq!(
        compile_and_run("(defn a [x y] (and x y))", "a", &[3, 4]).unwrap(),
        4
    );
    assert_eq!(
        compile_and_run("(defn o [x y] (or x y))", "o", &[0, 0]).unwrap(),
        0
    );
    // (or 0 7) → 7  — Clojure `or` returns the first truthy value
    // (was incorrectly 1 when `or` normalised to a boolean; fixed by FIX 1)
    assert_eq!(
        compile_and_run("(defn o [x y] (or x y))", "o", &[0, 7]).unwrap(),
        7
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

// ── FIX 1: `or` / `and` return the VALUE, not a boolean ─────────────────────
//
// These tests assert Clojure's VALUE-return semantics for `or` and `and`.
// They were the failing cases before the fix — the compiler was returning
// a normalised 0/1 boolean instead of the actual operand value.
//
// NOTE: In kotoba-clj's i64-everything value model, integer `0` is the same
// bit-pattern as `false`/`nil` (both are i64 0).  Therefore `(or 0 9)`
// correctly returns `9` in this model — `0` is the falsy sentinel.
// True integer-0-is-truthy would require a separate nil/false tag bit, which
// is outside the current value-model scope.  We document this honestly.

#[test]
fn or_returns_first_truthy_value_not_boolean() {
    // (or "x" "y") → "x"  — first truthy string value, not 1
    // We test with integers since the wasm export returns i64.
    // (or 5 9) → 5  (first operand is truthy → returned as-is)
    assert_eq!(
        compile_and_run("(defn f [x y] (or x y))", "f", &[5, 9]).unwrap(),
        5,
        "(or 5 9) should return 5 (first truthy), not 1"
    );
    // (or nil 5) → 5  — nil (0) is falsy, fall through to 5
    assert_eq!(
        compile_and_run("(defn f [x y] (or x y))", "f", &[0, 5]).unwrap(),
        5,
        "(or nil 5) should return 5"
    );
    // (or false 7) → 7  — false (0) is falsy, fall through to 7
    assert_eq!(
        compile_and_run("(defn f [x y] (or x y))", "f", &[0, 7]).unwrap(),
        7,
        "(or false 7) should return 7"
    );
    // (or nil nil) → nil (0)  — all falsy, return the last
    assert_eq!(
        compile_and_run("(defn f [x y] (or x y))", "f", &[0, 0]).unwrap(),
        0,
        "(or nil nil) should return 0 (nil)"
    );
    // n-ary: (or 0 0 42 99) → 42  (first truthy)
    assert_eq!(
        compile_and_run("(defn f [a b c d] (or a b c d))", "f", &[0, 0, 42, 99]).unwrap(),
        42,
        "(or 0 0 42 99) should return 42"
    );
}

#[test]
fn and_returns_first_falsy_or_last_value() {
    // (and 1 2 3) → 3  — all truthy, return the last
    assert_eq!(
        compile_and_run("(defn f [a b c] (and a b c))", "f", &[1, 2, 3]).unwrap(),
        3,
        "(and 1 2 3) should return 3 (last truthy), not 1"
    );
    // (and 1 nil 3) → 0  — nil (0) is falsy → return it
    assert_eq!(
        compile_and_run("(defn f [a b c] (and a b c))", "f", &[1, 0, 3]).unwrap(),
        0,
        "(and 1 nil 3) should return nil (0)"
    );
    // (and 7 8) → 8  — all truthy, return last
    assert_eq!(
        compile_and_run("(defn f [x y] (and x y))", "f", &[7, 8]).unwrap(),
        8,
        "(and 7 8) should return 8"
    );
    // (and nil 99) → nil  — first arg is falsy → return it without evaluating rest
    assert_eq!(
        compile_and_run("(defn f [x y] (and x y))", "f", &[0, 99]).unwrap(),
        0,
        "(and nil 99) should return 0 (nil)"
    );
}

#[test]
fn or_get_with_default_pattern() {
    // This is the key himawari pattern: (or (get state "key") default-value)
    // Before the fix the compiler returned 1 (truthy bool) instead of the map value.
    // After the fix it returns the actual value stored in the map.
    //
    // We test with an integer map value since the i64 return is the map's VALUE.
    // In the cell code: (or (get state "need") {})
    // — if "need" is present and non-nil, `or` must return THAT value, not 1.
    let src = r#"
        (defn probe [present? v]
          ;; Simulate: if present? != 0 return v, else return 0 (like map-get miss)
          ;; then (or that-result default-42) must return v when v != 0.
          (let [looked-up (if (= present? 1) v 0)]
            (or looked-up 42)))
    "#;
    // present, value=99 → (or 99 42) → 99
    assert_eq!(
        compile_and_run(src, "probe", &[1, 99]).unwrap(),
        99,
        "(or 99 42) should return 99 (the present value, not the default)"
    );
    // absent → (or 0 42) → 42 (default)
    assert_eq!(
        compile_and_run(src, "probe", &[0, 0]).unwrap(),
        42,
        "(or nil 42) should return 42 (the default)"
    );
}

// ── FIX 2: `def` with string-literal initialiser ─────────────────────────────

#[test]
fn def_string_literal_allowed() {
    // (def ^:private S "abc") is now valid — the string handle is stored in the
    // const map and references to S in function bodies emit the handle.
    let src = r#"
        (def ^:private GREETING "hello")
        (defn greet-len [] (str-len GREETING))
    "#;
    assert_eq!(
        compile_and_run(src, "greet-len", &[]).unwrap(),
        5,
        "(str-len GREETING) where GREETING=\"hello\" should be 5"
    );
}

#[test]
fn def_string_literal_used_in_comparison() {
    // A `def`-bound string constant can be passed to str-len and compared.
    let src = r#"
        (def ^:private TAG "abc")
        (defn tag-len [] (str-len TAG))
    "#;
    assert_eq!(
        compile_and_run(src, "tag-len", &[]).unwrap(),
        3,
        "(str-len TAG) where TAG=\"abc\" should be 3"
    );
}

// ── byte-at runtime bounds check (T1 memory safety) ─────────────────────────

#[test]
fn byte_at_in_bounds_returns_the_byte() {
    // "ab" = [97, 98]; valid indices read the right byte.
    let wasm = compile_str(r#"(defn at [i] (byte-at "ab" i))"#).unwrap();
    assert_eq!(run(&wasm, "at", &[0]).unwrap(), 97); // 'a'
    assert_eq!(run(&wasm, "at", &[1]).unwrap(), 98); // 'b'
}

#[test]
fn byte_at_out_of_bounds_traps_at_runtime() {
    // The index is a runtime value (so it passes the static literal check), but
    // an out-of-range read must trap rather than read adjacent memory (T1).
    let wasm = compile_str(r#"(defn at [i] (byte-at "ab" i))"#).unwrap();
    assert!(run(&wasm, "at", &[2]).is_err(), "index == len must trap");
    assert!(
        run(&wasm, "at", &[5]).is_err(),
        "index past the end must trap"
    );
    assert!(
        run(&wasm, "at", &[-1]).is_err(),
        "a negative index must trap"
    );
}

// ── byte-append! capacity check (T1 memory safety) ──────────────────────────

#[test]
fn byte_append_within_capacity_succeeds() {
    // A buffer sized for 2 bytes accepts exactly 2 appends.
    let src = r#"(defn fits []
                   (let [b (bytes-alloc 2)]
                     (byte-append! b 65)
                     (byte-append! b 66)
                     (bytes-len b)))"#;
    assert_eq!(compile_and_run(src, "fits", &[]).unwrap(), 2);
}

#[test]
fn byte_append_past_capacity_traps() {
    // The third append to a 2-byte buffer would overflow it → trap, not a write
    // into adjacent linear memory.
    let src = r#"(defn overflow []
                   (let [b (bytes-alloc 2)]
                     (byte-append! b 65)
                     (byte-append! b 66)
                     (byte-append! b 67)
                     (bytes-len b)))"#;
    let wasm = compile_str(src).unwrap();
    assert!(
        run(&wasm, "overflow", &[]).is_err(),
        "appending past capacity must trap"
    );
}

// ── bytes-alloc negative-capacity guard (T1 memory safety) ──────────────────

#[test]
fn bytes_alloc_negative_capacity_traps_at_runtime() {
    // A runtime-supplied negative capacity (passes the static literal check)
    // must trap at allocation, not create a huge-capacity / tiny buffer.
    let wasm = compile_str(r#"(defn mk [n] (let [b (bytes-alloc n)] (bytes-len b)))"#).unwrap();
    assert_eq!(run(&wasm, "mk", &[4]).unwrap(), 0); // valid: fresh buffer, len 0
    assert!(
        run(&wasm, "mk", &[-1]).is_err(),
        "negative capacity must trap"
    );
}

#[test]
fn negative_bytes_alloc_cannot_defeat_overflow_guard() {
    // Regression guard: a negative cap used to be stored as a huge unsigned
    // capacity, which would let byte-append! overflow the tiny allocation. It
    // now traps at allocation, before any append can run.
    let src = r#"(defn ov [n]
                   (let [b (bytes-alloc n)]
                     (byte-append! b 1)
                     (bytes-len b)))"#;
    let wasm = compile_str(src).unwrap();
    assert!(
        run(&wasm, "ov", &[-1]).is_err(),
        "a negative cap must trap before any append can overflow"
    );
}

// ── runtime division-by-zero traps (safety; static check covers only literals) ─

#[test]
fn runtime_division_by_zero_traps() {
    // A variable zero divisor passes the static literal-zero check, so the
    // emitted code must trap (wasm I64DivS / I64RemS) rather than return garbage.
    for (op, f) in [("/", "d"), ("mod", "m"), ("rem", "r"), ("quot", "q")] {
        let wasm = compile_str(&format!("(defn {f} [a b] ({op} a b))")).unwrap();
        assert!(
            run(&wasm, f, &[10, 2]).is_ok(),
            "{op} by a non-zero divisor must compute"
        );
        assert!(
            run(&wasm, f, &[10, 0]).is_err(),
            "{op} by a runtime zero divisor must trap"
        );
    }
}

// ── float→int is saturating: total, no trap, no UB (memory safety) ──────────

#[test]
fn float_to_int_saturates_and_is_total() {
    // `int` lowers to `i64.trunc_sat_f64_s`: a *total* conversion — no trap, no
    // undefined behaviour on any float. NaN → 0, ±Inf and out-of-range values
    // saturate to i64 MIN/MAX, finite values truncate toward zero. This guards
    // against a codegen change to the trapping `trunc_f64_s` (or to UB).
    let cases = [
        ("(int (Math/sqrt -1.0))", 0i64), // NaN
        ("(int (/ 1.0 0.0))", i64::MAX),  // +Inf
        ("(int (/ -1.0 0.0))", i64::MIN), // -Inf
        ("(int 1.0e30)", i64::MAX),       // beyond +range
        ("(int -1.0e30)", i64::MIN),      // beyond -range
        ("(int 2.5)", 2),                 // truncate toward zero
        ("(int -2.5)", -2),
    ];
    for (expr, want) in cases {
        let wasm = compile_str(&format!("(defn f [] {expr})")).unwrap();
        assert_eq!(
            run(&wasm, "f", &[]).unwrap(),
            want,
            "int conversion of {expr}"
        );
    }
}
