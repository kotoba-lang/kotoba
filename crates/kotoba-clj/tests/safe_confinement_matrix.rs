//! Adversarial confinement matrix — the executable threat model.
//!
//! Each defense layer of the confined `compile_safe_kotoba` toolchain is asserted
//! against the escape-hatch class it is responsible for, naming the *specific*
//! `CljError` variant so a regression that lets a vector through (or moves it to
//! the wrong layer) fails loudly. This is the composed counterpart to the
//! per-layer suites (`safe_subset`, `safe_types`, `safe_type_infer`,
//! `safe_policy`, `safe_effects`): it locks the layered defense as a whole.
//!
//! Layer order (first match wins): subset → literal/inferred type → effect →
//! capability. Runtime memory-safety traps are the last line, in emitted code.

use kotoba_clj::run::run;
use kotoba_clj::{compile_safe_kotoba, compile_str, CljError, Policy};

fn assert_variant(res: Result<Vec<u8>, CljError>, want: &str) {
    let ok = matches!(
        (&res, want),
        (Err(CljError::Subset(_)), "subset")
            | (Err(CljError::Type(_)), "type")
            | (Err(CljError::Policy(_)), "policy")
            | (Err(CljError::Effect(_)), "effect")
    );
    assert!(ok, "expected {want} denial, got {res:?}");
}

// ── Layer 1: subset gate — language escape hatches ──────────────────────────

#[test]
fn subset_gate_denies_every_escape_hatch_class() {
    let deny = Policy::deny_all();
    for src in [
        // dynamic code / metaprogramming
        r#"(defn run [x] (eval x))"#,
        r#"(defn run [s] (read-string s))"#,
        r#"(defn run [] (defmacro m [] 1))"#,
        // runtime require / namespace mutation
        r#"(defn run [] (require (quote evil.ns)))"#,
        r#"(defn run [v] (alter-var-root v))"#,
        // dynamic var / global mutation
        r#"(defn run [] (set! x 1))"#,
        // shared mutable state / concurrency
        r#"(defn run [] (atom 0))"#,
        r#"(defn run [] (future (+ 1 1)))"#,
        // ambient I/O
        r#"(defn run [] (slurp "/etc/passwd"))"#,
        r#"(defn run [] (println "leak"))"#,
        // raw linear-memory access (iter: T1)
        r#"(defn run [a] (store64! a 0))"#,
        r#"(defn run [a] (load64 a))"#,
        r#"(defn run [n] (alloc n))"#,
        // host interop syntax
        r#"(defn run [x] (.exec x))"#,
        r#"(defn run [] (Runtime. ))"#,
        r#"(defn run [] (new java.io.File "x"))"#,
    ] {
        assert_variant(compile_safe_kotoba(src, &deny), "subset");
    }
}

// ── Layer 2: type checks — i64 handle punning ───────────────────────────────

#[test]
fn type_gate_denies_handle_punning() {
    let deny = Policy::deny_all();
    for src in [
        r#"(defn run [] (+ "a" 1))"#,             // arithmetic on a string
        r#"(defn run [] (bit-and "a" 1))"#,       // bitwise on a string
        r#"(defn run [] (Math/sqrt "a"))"#,       // math on a string
        r#"(defn run [] (< "a" 1))"#,             // ordered compare on a string
        r#"(defn run [] (str-len 5))"#,           // number as a string handle
        r#"(defn run [] (byte-at "ab" 9))"#,      // statically out-of-bounds read
        r#"(defn run [] (let [s "x"] (* s 2)))"#, // inferred string in arithmetic
    ] {
        assert_variant(compile_safe_kotoba(src, &deny), "type");
    }
}

// ── Layer 3: effect gate — declared effects must cover what runs ────────────

#[test]
fn effect_gate_denies_under_declaration() {
    // Declares pure, but writes the graph. Fires before the capability gate,
    // even though the write capability *is* granted.
    let src = r#"(defn run {:effects #{}} [] (kqe-assert! "kg" "a" "p" "v"))"#;
    assert_variant(
        compile_safe_kotoba(src, &Policy::deny_all().grant_graph_write(["kg"])),
        "effect",
    );
}

// ── Layer 4: capability gate — deny-by-default host access ──────────────────

#[test]
fn capability_gate_denies_ungranted_host_access() {
    // Honest effect declarations, but the capabilities are not granted.
    for src in [
        r#"(defn run {:effects #{:graph-write}} [] (kqe-assert! "kg" "a" "p" "v"))"#,
        r#"(defn run {:effects #{:graph-read}} [] (kqe-get-objects "kg" "s" "p"))"#,
        r#"(defn run {:effects #{:infer}} [] (llm-infer "m" "p"))"#,
    ] {
        assert_variant(compile_safe_kotoba(src, &Policy::deny_all()), "policy");
    }
}

// ── Layer 5: runtime traps — memory safety in emitted code ──────────────────

#[test]
fn runtime_traps_on_out_of_bounds_read() {
    // A runtime index past the string length traps rather than reading adjacent
    // memory (the static check only covers literal indices).
    let wasm = compile_str(r#"(defn at [i] (byte-at "ab" i))"#).unwrap();
    assert_eq!(run(&wasm, "at", &[0]).unwrap(), 97); // in-bounds is fine
    assert!(run(&wasm, "at", &[9]).is_err(), "OOB read must trap");
    assert!(run(&wasm, "at", &[-1]).is_err(), "negative index must trap");
}

#[test]
fn runtime_traps_on_buffer_overflow() {
    // Appending past a buffer's capacity traps rather than overflowing it.
    let src = r#"(defn over []
                   (let [b (bytes-alloc 1)]
                     (byte-append! b 1)
                     (byte-append! b 2)
                     (bytes-len b)))"#;
    let wasm = compile_str(src).unwrap();
    assert!(
        run(&wasm, "over", &[]).is_err(),
        "buffer overflow must trap"
    );
}

// ── Composition: a cell stacking vectors is still denied ────────────────────

#[test]
fn layered_defense_denies_a_multi_vector_cell() {
    // Ambient I/O *and* a string-arithmetic pun *and* ungranted graph write.
    // The outermost (subset) layer catches it first; the point is that nothing
    // about combining vectors creates a gap.
    let src = r#"(defn run []
                   (do (println (+ "leak" 1))
                       (kqe-assert! "kg" "a" "p" "v")))"#;
    assert!(
        compile_safe_kotoba(src, &Policy::deny_all()).is_err(),
        "a multi-vector cell must be denied"
    );
}

// ── Higher-order functions do not open a hole in any gate ───────────────────

#[test]
fn closures_cannot_smuggle_capabilities_past_the_policy_gate() {
    // A host call hidden inside a closure is still gated: the capability
    // collector walks `fn` bodies, so the import is denied under deny-all and
    // permitted only when granted. Confinement is not lexical-scope-evadable.
    let src = r#"(defn run [] (let [f (fn [] (kqe-assert! "kg" "a" "p" "v"))] (f)))"#;
    assert_variant(compile_safe_kotoba(src, &Policy::deny_all()), "policy");
    let granted = compile_safe_kotoba(src, &Policy::deny_all().grant_graph_write(["kg"]));
    assert!(
        granted.is_ok(),
        "the same closure compiles once the capability is granted: {granted:?}"
    );
}

#[test]
fn per_cid_binding_holds_through_closures() {
    // Confinement is instance-level, not just class-level, *and* it survives a
    // closure: granting graph-write on graphA does not authorize a write to
    // graphB hidden in a closure.
    let src = r#"(defn run [] (let [f (fn [] (kqe-assert! "graphB" "a" "p" "v"))] (f)))"#;
    assert_variant(
        compile_safe_kotoba(src, &Policy::deny_all().grant_graph_write(["graphA"])),
        "policy",
    );
    // The matching cid compiles — the binding is precise, not blanket-deny.
    let matched = compile_safe_kotoba(src, &Policy::deny_all().grant_graph_write(["graphB"]));
    assert!(matched.is_ok(), "the granted cid must compile: {matched:?}");
}

#[test]
fn closures_cannot_smuggle_effects_past_the_declaration() {
    // The effect collector also walks `fn` bodies, attributing the closure's
    // graph-write to the function that lexically contains it. A `:effects #{}`
    // declaration is therefore rejected even though the write is nested in a
    // closure (and even though the capability itself is granted).
    let src =
        r#"(defn run {:effects #{}} [] (let [f (fn [] (kqe-assert! "kg" "a" "p" "v"))] (f)))"#;
    assert_variant(
        compile_safe_kotoba(src, &Policy::deny_all().grant_graph_write(["kg"])),
        "effect",
    );
}

#[test]
fn a_clean_cell_still_compiles() {
    // The matrix must not be vacuous: a well-typed cell that declares its effect
    // honestly and uses only the capability it was granted must compile.
    let src = r#"(defn run {:effects #{:graph-read}} [] (kqe-get-objects "kg" "s" "p"))"#;
    let wasm = compile_safe_kotoba(src, &Policy::deny_all().grant_graph_read(["kg"]))
        .expect("a clean cell must compile");
    assert!(wasm.starts_with(b"\0asm"));
}

#[test]
fn per_cid_through_params_is_shadow_safe() {
    // `g` the parameter is shadowed by a `let`, so the host-call target is the
    // inner (granted) cid, not the parameter. A caller passing an unrelated cid
    // must NOT be flagged — the parameter does not flow to the target.
    let src = r#"(defn writer [g] (let [g "graphA"] (kqe-assert! g "s" "p" "v")))
                 (defn run [] (writer "graphB"))"#;
    let wasm = compile_safe_kotoba(src, &Policy::deny_all().grant_graph_write(["graphA"]));
    assert!(
        wasm.is_ok(),
        "a shadowed parameter must not mis-flag the caller: {wasm:?}"
    );
}

#[test]
fn per_cid_through_params_still_denies_unshadowed() {
    // Regression: the feature itself still works — an *unshadowed* param that
    // flows to the target rejects a caller's ungranted literal cid.
    let src = r#"(defn writer [g] (kqe-assert! g "s" "p" "v"))
                 (defn run [] (writer "graphB"))"#;
    assert_variant(
        compile_safe_kotoba(src, &Policy::deny_all().grant_graph_write(["graphA"])),
        "policy",
    );
}
