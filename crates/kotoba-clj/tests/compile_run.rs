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
    assert_eq!(compile_and_run("(defn add [a b] (+ a b))", "add", &[2, 3]).unwrap(), 5);
    assert_eq!(compile_and_run("(defn s4 [a b c d] (+ a b c d))", "s4", &[1, 2, 3, 4]).unwrap(), 10);
    assert_eq!(compile_and_run("(defn neg [x] (- x))", "neg", &[7]).unwrap(), -7);
    assert_eq!(compile_and_run("(defn d [a b] (- a b))", "d", &[10, 3]).unwrap(), 7);
    assert_eq!(compile_and_run("(defn m [a b] (* a b))", "m", &[6, 7]).unwrap(), 42);
    assert_eq!(compile_and_run("(defn q [a b] (/ a b))", "q", &[20, 6]).unwrap(), 3);
    assert_eq!(compile_and_run("(defn r [a b] (mod a b))", "r", &[20, 6]).unwrap(), 2);
}

#[test]
fn comparisons_and_logic() {
    assert_eq!(compile_and_run("(defn lt [a b] (< a b))", "lt", &[1, 2]).unwrap(), 1);
    assert_eq!(compile_and_run("(defn lt [a b] (< a b))", "lt", &[2, 1]).unwrap(), 0);
    assert_eq!(compile_and_run("(defn ge [a b] (>= a b))", "ge", &[2, 2]).unwrap(), 1);
    assert_eq!(compile_and_run("(defn eq [a b] (= a b))", "eq", &[5, 5]).unwrap(), 1);
    assert_eq!(compile_and_run("(defn nt [x] (not x))", "nt", &[0]).unwrap(), 1);
    assert_eq!(compile_and_run("(defn nt [x] (not x))", "nt", &[9]).unwrap(), 0);
    assert_eq!(compile_and_run("(defn a [x y] (and x y))", "a", &[1, 0]).unwrap(), 0);
    assert_eq!(compile_and_run("(defn a [x y] (and x y))", "a", &[3, 4]).unwrap(), 1);
    assert_eq!(compile_and_run("(defn o [x y] (or x y))", "o", &[0, 0]).unwrap(), 0);
    assert_eq!(compile_and_run("(defn o [x y] (or x y))", "o", &[0, 7]).unwrap(), 1);
}

#[test]
fn if_when_let_do() {
    let max = "(defn max [a b] (if (> a b) a b))";
    assert_eq!(compile_and_run(max, "max", &[3, 9]).unwrap(), 9);
    assert_eq!(compile_and_run(max, "max", &[9, 3]).unwrap(), 9);

    let w = "(defn w [x] (when (> x 0) (* x 10)))";
    assert_eq!(compile_and_run(w, "w", &[4]).unwrap(), 40);
    assert_eq!(compile_and_run(w, "w", &[-4]).unwrap(), 0);

    // sequential let: second binding sees the first
    let l = "(defn l [x] (let [a (* x 2) b (+ a 1)] (do a b)))";
    assert_eq!(compile_and_run(l, "l", &[5]).unwrap(), 11);
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
    assert!(ptrs[1] >= ptrs[0] + 100_000, "second region must be disjoint");
}

// ---- Step 2: Str/Bytes values backed by (ptr,len) ---------------------------

#[test]
fn string_length() {
    assert_eq!(compile_and_run("(defn n [] (str-len \"hello\"))", "n", &[]).unwrap(), 5);
    assert_eq!(compile_and_run("(defn n [] (str-len \"\"))", "n", &[]).unwrap(), 0);
    // multi-byte UTF-8: "あ" is 3 bytes.
    assert_eq!(compile_and_run("(defn n [] (str-len \"あ\"))", "n", &[]).unwrap(), 3);
}

#[test]
fn byte_access() {
    // "ABC" → bytes 65,66,67
    assert_eq!(compile_and_run("(defn b [] (byte-at \"ABC\" 0))", "b", &[]).unwrap(), 65);
    assert_eq!(compile_and_run("(defn b [] (byte-at \"ABC\" 2))", "b", &[]).unwrap(), 67);
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
    assert!(matches!(compile_str("(defn f [x] (g x))"), Err(CljError::Codegen(_))));
    assert!(matches!(compile_str("(defn f [x] y)"), Err(CljError::Codegen(_))));
    assert!(matches!(compile_str("(frobnicate)"), Err(CljError::Lower(_))));
}
