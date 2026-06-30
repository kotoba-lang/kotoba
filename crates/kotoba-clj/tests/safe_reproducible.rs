//! Phase **S5** (supply chain): reproducible builds for the confined toolchain.
//!
//! A safe-built module is content-addressed (its CID is `blake3` of the wasm
//! bytes), so a deterministic build is what makes a module's identity stable —
//! the foundation of supply-chain integrity. These tests lock that property for
//! `compile_safe_kotoba` / `compile_safe_kotoba_with_prelude`.
//!
//! ## Why this has teeth
//!
//! Rust's `HashMap` draws a fresh random seed per `HashMap::new()`, so two
//! HashMaps built in the *same* process generally iterate in different orders.
//! Codegen builds fresh maps (`offsets`, `fn_index`, `import_index`, …) on every
//! compile; if it ever emitted bytes by *iterating* one of them, two compiles in
//! this one test process would diverge and these assertions would fail. They
//! pass because every emission walks source-ordered `Vec`s and uses the maps
//! only as lookups — exactly the invariant we want to keep.

use kotoba_clj::{compile_safe_kotoba, compile_safe_kotoba_with_prelude, Policy};

/// Compile `src` `n` times and assert every result is byte-identical, returning
/// the canonical bytes. `n >= 3` to give per-compile seed variation a chance to
/// surface any iteration-order dependence.
fn assert_deterministic(label: &str, compile: impl Fn() -> Vec<u8>, n: usize) -> Vec<u8> {
    assert!(n >= 3);
    let first = compile();
    assert!(first.starts_with(b"\0asm"), "{label}: not a wasm module");
    for i in 1..n {
        let again = compile();
        assert_eq!(
            first, again,
            "{label}: compile #{i} differs from #0 — the safe build is not reproducible"
        );
    }
    first
}

// A program rich in the structures that flow through codegen's HashMaps: many
// string literals (data-segment `offsets`), many functions of several arities
// (`fn_index`, `type_for_arity`), and mutual recursion.
const RICH: &str = r#"
    (defn a [] "alpha")
    (defn b [] "bravo")
    (defn c [] "charlie")
    (defn d [x] (str-len x))
    (defn e [x y] (+ (str-len x) y))
    (defn pick [n] (if (< n 0) (a) (if (= n 0) (b) (c))))
    (defn ping [n] (if (zero? n) 0 (pong (dec n))))
    (defn pong [n] (if (zero? n) 1 (ping (dec n))))
    (defn run [n] (+ (e (a) (ping n)) (d (pick n))))
"#;

#[test]
fn pure_program_is_byte_reproducible() {
    assert_deterministic(
        "pure",
        || compile_safe_kotoba(RICH, &Policy::deny_all()).unwrap(),
        5,
    );
}

#[test]
fn prelude_program_is_byte_reproducible() {
    // The prelude pulls in the whole container/CBOR substrate — the heaviest
    // codegen path, with the most map traffic.
    let src = "(defn run [] (let [v (vector 1 2 3) m {:k 7}] (+ (count v) (get m :k))))";
    assert_deterministic(
        "prelude",
        || compile_safe_kotoba_with_prelude(src, &Policy::deny_all()).unwrap(),
        5,
    );
}

#[test]
fn host_import_program_is_byte_reproducible() {
    // Host imports exercise the `import_index` map and the policy-aware prelude.
    let src = r#"(defn run [] (kqe-count (kqe-get-objects "kg" "s" "p")))"#;
    let policy = Policy::deny_all().grant_graph_read(["kg"]);
    assert_deterministic(
        "host-import",
        || compile_safe_kotoba_with_prelude(src, &policy).unwrap(),
        5,
    );
}

#[test]
fn distinct_sources_produce_distinct_bytes() {
    // Discriminating power: determinism must not be the trivial "always equal".
    // Two programs differing only in a literal and a constant must differ.
    let a = compile_safe_kotoba(r#"(defn run [] (str-len "hello"))"#, &Policy::deny_all()).unwrap();
    let b =
        compile_safe_kotoba(r#"(defn run [] (str-len "world!"))"#, &Policy::deny_all()).unwrap();
    assert_ne!(a, b, "distinct sources must yield distinct modules");
}

#[test]
fn reproducible_across_independent_policies() {
    // The same source + an equivalent (freshly built) policy must still produce
    // identical bytes — the policy object's construction order must not leak in.
    let src = r#"(defn run [] (kqe-count (kqe-get-objects "kg" "s" "p")))"#;
    let one = compile_safe_kotoba_with_prelude(src, &Policy::deny_all().grant_graph_read(["kg"]))
        .unwrap();
    let two = compile_safe_kotoba_with_prelude(src, &Policy::deny_all().grant_graph_read(["kg"]))
        .unwrap();
    assert_eq!(one, two, "equivalent policies must yield identical modules");
}

// ── the component path (what self-hosting ships) is reproducible too ─────────

#[cfg(feature = "component")]
#[test]
fn safe_component_build_is_byte_reproducible() {
    use kotoba_clj::component::compile_component_str_with_prelude;
    // A confined module is distributed as a WASM *Component* (the self-hosted
    // analyzer is one). The component build — core module + wit-component
    // wrapping — must be byte-deterministic so the component's content-address
    // (CID) is stable: supply-chain integrity for the dogfooded gate.
    let src = r#"(defn run [input]
                   (let [b (bytes-alloc 3)]
                     (byte-append! b 65)
                     (byte-append! b 66)
                     (bytes-finish b)))"#;
    let first = compile_component_str_with_prelude(src).expect("component compile");
    assert!(first.starts_with(b"\0asm"), "must be a wasm component");
    for _ in 0..4 {
        let again = compile_component_str_with_prelude(src).expect("component compile");
        assert_eq!(
            first, again,
            "the safe component build must be reproducible (stable CID)"
        );
    }
}
