//! Tests for `compile_component_str_with_prelude` — a WASM Component that
//! includes the full container + CBOR prelude (vec/map/merge/str/get/mapv/…).
//!
//! Prior to this fn, `compile_component_str` produced Components without the
//! prelude, so any program using `merge`, `str a b c`, `(get m k default)`,
//! `(mapv (fn [x] …) coll)` etc. would fail to compile.  This test verifies
//! that the combined path works end-to-end.
#![cfg(feature = "component")]

use kotoba_clj::component::{assert_loads, compile_component_str_with_prelude, run_component};

/// Helper: compile with prelude + assert the result is a wasm component.
fn compile_and_assert(src: &str) -> Vec<u8> {
    let bytes = compile_component_str_with_prelude(src)
        .unwrap_or_else(|e| panic!("compile_component_str_with_prelude failed: {e:?}"));
    assert_eq!(&bytes[..4], b"\0asm", "output must start with WASM magic");
    assert!(
        bytes.len() > 100,
        "component too small: {} bytes",
        bytes.len()
    );
    bytes
}

// ── 1. Basic smoke: component is valid WASM + loads under wasmtime ────────────

#[test]
fn component_with_prelude_is_valid_wasm_component() {
    let src = r#"
      (defn run [input]
        ;; trivial: return the input
        input)
    "#;
    let bytes = compile_and_assert(src);
    println!(
        "component_with_prelude_is_valid_wasm_component: {} bytes",
        bytes.len()
    );
    assert_loads(&bytes).expect("component must load under wasmtime component model");
}

// ── 2. `merge` ────────────────────────────────────────────────────────────────

#[test]
fn component_with_prelude_merge_compiles() {
    // Uses `merge` from PRELUDE.  Verifies it compiles — does not run the
    // merged map (the run fn only passes bytes in/out).
    let src = r#"
      (defn run [input]
        (let [a {"x" 1 "y" 2}
              b {"z" 3}
              _ (merge a b)]
          input))
    "#;
    let bytes = compile_and_assert(src);
    println!(
        "component_with_prelude_merge_compiles: {} bytes",
        bytes.len()
    );
    assert_loads(&bytes).unwrap();
}

// ── 3. `str` multi-arg ────────────────────────────────────────────────────────

#[test]
fn component_with_prelude_str_compiles_and_runs() {
    // `(str a b c)` expands to str-cat calls — needs PRELUDE `str-cat` / byte builder.
    let src = r#"
      (defn run [input]
        (str "hello" "-" "world"))
    "#;
    let bytes = compile_and_assert(src);
    assert_loads(&bytes).unwrap();
    let out = run_component(&bytes, b"ignored").expect("run_component");
    assert_eq!(out, b"hello-world", "str multi-arg output mismatch");
    println!(
        "component_with_prelude_str_compiles_and_runs: {} bytes, output {:?}",
        bytes.len(),
        out
    );
}

// ── 4. `(get m k default)` ────────────────────────────────────────────────────

#[test]
fn component_with_prelude_get_with_default_compiles() {
    let src = r#"
      (defn run [input]
        (let [m {"a" 1 "b" 2}
              v (get m "c" 99)]
          ;; v is 99 (default); we return "ok" to prove it compiled + ran
          (if (= v 99) "ok" "bad")))
    "#;
    let bytes = compile_and_assert(src);
    assert_loads(&bytes).unwrap();
    let out = run_component(&bytes, b"").expect("run_component");
    assert_eq!(out, b"ok", "get with default should return 99 → ok");
    println!(
        "component_with_prelude_get_with_default_compiles: {} bytes",
        bytes.len()
    );
}

// ── 5. `(mapv (fn [x] …) coll)` ──────────────────────────────────────────────

#[test]
fn component_with_prelude_mapv_compiles() {
    // `mapv` is a higher-order fn in PRELUDE; tests closure / call_indirect path.
    let src = r#"
      (defn run [input]
        (let [coll [1 2 3]
              _ (mapv (fn [x] (* x x)) coll)]
          ;; Just verifying it compiles and runs without trapping.
          "ok"))
    "#;
    let bytes = compile_and_assert(src);
    assert_loads(&bytes).unwrap();
    let out = run_component(&bytes, b"").expect("run_component");
    assert_eq!(out, b"ok");
    println!(
        "component_with_prelude_mapv_compiles: {} bytes",
        bytes.len()
    );
}

// ── 6. Combined himawari-shaped cell pattern ──────────────────────────────────
//
// Uses merge + str a b c + (get m k default) + (mapv (fn [x] …) coll)
// together in a single component — this is the minimal pattern that
// represents a real himawari supply-chain cell.

#[test]
fn component_with_prelude_himawari_pattern() {
    let src = r#"
      ;; himawari-shaped: merge + str + get-with-default + mapv
      (defn run [input]
        (let [;; state-like map
              state {"ring" "internal" "grade" "solar-grade-6N"}
              ;; merge with update
              updated (merge state {"status" "ok"})
              ;; get with default
              ring   (get updated "ring" "external")
              ;; str multi-arg label
              label  (str "ring:" ring)
              ;; mapv over a small vector
              grades ["solar-grade-6N" "recycled-kerf"]
              _      (mapv (fn [g] (str-len g)) grades)]
          label))
    "#;
    let bytes = compile_and_assert(src);
    assert_loads(&bytes).unwrap();
    let out = run_component(&bytes, b"").expect("run_component");
    assert_eq!(out, b"ring:internal");
    println!(
        "component_with_prelude_himawari_pattern: {} bytes, output {:?}",
        bytes.len(),
        out
    );
}

// ── 7. Byte count report ──────────────────────────────────────────────────────

#[test]
fn component_with_prelude_byte_count() {
    // Report the byte size of a minimal prelude+run component so we can
    // track growth over time.  Not a pass/fail on size — just informational.
    let src = "(defn run [input] input)";
    let bytes = compile_component_str_with_prelude(src).unwrap();
    println!(
        "component_with_prelude byte count (minimal echo): {} bytes",
        bytes.len()
    );
    // Sanity: must be larger than compile_component_str (which has no prelude)
    let bytes_no_prelude = kotoba_clj::component::compile_component_str(src).unwrap();
    println!("  without prelude:  {} bytes", bytes_no_prelude.len());
    assert!(
        bytes.len() > bytes_no_prelude.len(),
        "with-prelude component ({} bytes) must be larger than no-prelude ({} bytes)",
        bytes.len(),
        bytes_no_prelude.len()
    );
}
