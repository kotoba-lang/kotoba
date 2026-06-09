//! Stage-A language growth (ADR step 4 unblock): `loop`/`recur`, `cond`, and the
//! mutable byte-buffer builder (`bytes-alloc` / `byte-append!` / `bytes-len` /
//! `bytes-finish`). These are the primitives a CBOR decode/encode — and hence a
//! real `kotoba-node` `run(ctx-cbor)` agent — needs.
//!
//! Every test runs the emitted **core module** on wasmtime and asserts an i64,
//! so they exercise the whole read → lower → codegen → run pipeline. The bytes
//! tests deliberately verify their buffers *in-guest* via `str-len`/`byte-at`
//! (closing the loop: build bytes, finish to a string handle, read them back).

use kotoba_clj::run::compile_and_run;
use kotoba_clj::{compile_str, CljError};

// ---- loop / recur -----------------------------------------------------------

#[test]
fn loop_sum_0_to_n() {
    // Σ i for i in 0..=n.
    let src = "(defn sum [n] (loop [i 0 acc 0] (if (> i n) acc (recur (+ i 1) (+ acc i)))))";
    assert_eq!(compile_and_run(src, "sum", &[0]).unwrap(), 0);
    assert_eq!(compile_and_run(src, "sum", &[5]).unwrap(), 15);
    assert_eq!(compile_and_run(src, "sum", &[100]).unwrap(), 5050);
}

#[test]
fn loop_gcd_euclid() {
    // loop bindings shadow the params with the same names (sequential init).
    let src = "(defn gcd [a b] (loop [a a b b] (if (= b 0) a (recur b (mod a b)))))";
    assert_eq!(compile_and_run(src, "gcd", &[48, 18]).unwrap(), 6);
    assert_eq!(compile_and_run(src, "gcd", &[17, 5]).unwrap(), 1);
    assert_eq!(compile_and_run(src, "gcd", &[100, 100]).unwrap(), 100);
}

#[test]
fn recur_nested_in_cond_inside_loop() {
    // recur sits inside a `cond` (→ nested `if`) inside the loop: exercises the
    // relative `br` label depth accounting (must skip the inner `if` frame).
    let src = "(defn count-up [n] (loop [i 0] (cond (>= i n) i :else (recur (+ i 1)))))";
    assert_eq!(compile_and_run(src, "count-up", &[0]).unwrap(), 0);
    assert_eq!(compile_and_run(src, "count-up", &[7]).unwrap(), 7);
}

#[test]
fn recur_inside_let_and_if() {
    // recur nested two frames deep (if → let body is a `do`, recur in if-arm).
    let src = "
      (defn f [n]
        (loop [i 0 acc 1]
          (if (>= i n)
            acc
            (let [next (* acc 2)]
              (recur (+ i 1) next)))))";
    assert_eq!(compile_and_run(src, "f", &[0]).unwrap(), 1);
    assert_eq!(compile_and_run(src, "f", &[10]).unwrap(), 1024); // 2^10
}

// ---- cond -------------------------------------------------------------------

#[test]
fn cond_three_way() {
    let src = "(defn sgn [x] (cond (< x 0) -1 (= x 0) 0 :else 1))";
    assert_eq!(compile_and_run(src, "sgn", &[-9]).unwrap(), -1);
    assert_eq!(compile_and_run(src, "sgn", &[0]).unwrap(), 0);
    assert_eq!(compile_and_run(src, "sgn", &[42]).unwrap(), 1);
}

#[test]
fn cond_no_default_falls_through_to_zero() {
    let src = "(defn pick [x] (cond (= x 1) 11 (= x 2) 22))";
    assert_eq!(compile_and_run(src, "pick", &[2]).unwrap(), 22);
    assert_eq!(compile_and_run(src, "pick", &[9]).unwrap(), 0); // nothing matched
}

// ---- byte buffer builder ----------------------------------------------------

#[test]
fn bytes_append_len_and_read() {
    // append 3 bytes, then read one back via byte-at after bytes-finish.
    let src = "
      (defn one [_]
        (let [buf (bytes-alloc 8)]
          (byte-append! buf 7)
          (byte-append! buf 9)
          (byte-append! buf 11)
          (let [s (bytes-finish buf)]
            (byte-at s 1))))";
    assert_eq!(compile_and_run(src, "one", &[0]).unwrap(), 9);
}

#[test]
fn bytes_len_tracks_appends() {
    let src = "
      (defn n [_]
        (let [buf (bytes-alloc 16)]
          (byte-append! buf 1)
          (byte-append! buf 2)
          (byte-append! buf 3)
          (bytes-len buf)))";
    assert_eq!(compile_and_run(src, "n", &[0]).unwrap(), 3);
}

#[test]
fn build_in_loop_then_sum_back() {
    // The full round-trip: a loop fills a buffer with [65,66,…,65+n-1] by
    // threading the buffer handle through `recur`, finishes it to a string, and
    // a second loop sums the bytes via str-len/byte-at. n=3 → 65+66+67 = 198.
    let src = "
      (defn build-sum [n]
        (loop [i 0 buf (bytes-alloc n)]
          (if (>= i n)
            (let [s (bytes-finish buf)]
              (loop [j 0 acc 0]
                (if (>= j (str-len s))
                  acc
                  (recur (+ j 1) (+ acc (byte-at s j))))))
            (recur (+ i 1) (byte-append! buf (+ i 65))))))";
    assert_eq!(compile_and_run(src, "build-sum", &[0]).unwrap(), 0);
    assert_eq!(compile_and_run(src, "build-sum", &[3]).unwrap(), 198);
    // [65..75) sums to (65+74)*10/2 = 695.
    assert_eq!(compile_and_run(src, "build-sum", &[10]).unwrap(), 695);
}

#[test]
fn bytes_finish_region_is_real_memory() {
    // Directly inspect linear memory: build a buffer, finish it, decode the
    // returned (ptr<<32)|len handle, and confirm the bytes are actually there.
    use wasmtime::{Engine, Instance, Module, Store, Val};

    let src = "
      (defn mk [_]
        (let [buf (bytes-alloc 4)]
          (byte-append! buf 240)
          (byte-append! buf 159)
          (byte-append! buf 145)
          (byte-append! buf 141)
          (bytes-finish buf)))";
    let wasm = compile_str(src).unwrap();

    let engine = Engine::default();
    let module = Module::new(&engine, &wasm).unwrap();
    let mut store = Store::new(&engine, ());
    let instance = Instance::new(&mut store, &module, &[]).unwrap();
    let f = instance.get_func(&mut store, "mk").unwrap();
    let mut out = [Val::I64(0)];
    f.call(&mut store, &[Val::I64(0)], &mut out).unwrap();
    let handle = match out[0] {
        Val::I64(v) => v as u64,
        _ => panic!("expected i64 handle"),
    };
    let ptr = (handle >> 32) as usize;
    let len = (handle & 0xFFFF_FFFF) as usize;
    assert_eq!(len, 4, "four bytes appended");

    let mem = instance.get_memory(&mut store, "memory").unwrap();
    let data = mem.data(&store);
    assert_eq!(&data[ptr..ptr + len], &[240, 159, 145, 141]); // 🐍 (U+1F40D) UTF-8
}

// ---- negative cases ---------------------------------------------------------

#[test]
fn recur_outside_loop_is_rejected() {
    let err = compile_str("(defn bad [x] (recur x))").unwrap_err();
    assert!(matches!(err, CljError::Codegen(_)), "got {err:?}");
}

#[test]
fn recur_arity_must_match_loop_bindings() {
    let err = compile_str("(defn bad [n] (loop [i 0] (recur i n)))").unwrap_err();
    assert!(matches!(err, CljError::Codegen(_)), "got {err:?}");
}

#[test]
fn cond_requires_even_forms() {
    let err = compile_str("(defn bad [x] (cond (= x 1) 11 12))").unwrap_err();
    assert!(matches!(err, CljError::Lower(_)), "got {err:?}");
}
