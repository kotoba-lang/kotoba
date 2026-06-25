//! Phase **S0** of the capability-confinement design
//! (`docs/ADR-safe-capability-language.md`): `compile_safe_clj` is
//! deny-by-default. A program may only use a host capability the [`Policy`]
//! grants; otherwise the module is never emitted.
//!
//! These tests assert the gate from both sides — denied programs fail with
//! [`CljError::Policy`], granted programs compile to real wasm — and that the
//! read/write split, the resource-quota floor, the policy-aware prelude, and
//! the EDN policy parser all behave.

use kotoba_clj::policy::CapClass;
use kotoba_clj::{compile_safe_clj, compile_safe_clj_with_prelude, CljError, Limits, Policy};

fn is_wasm(bytes: &[u8]) -> bool {
    bytes.starts_with(b"\0asm")
}

fn assert_policy_denied(res: Result<Vec<u8>, CljError>) {
    match res {
        Err(CljError::Policy(_)) => {}
        other => panic!("expected CljError::Policy denial, got {other:?}"),
    }
}

#[test]
fn pure_program_compiles_under_deny_all() {
    // No host capability requested → confined policy still compiles it.
    let wasm = compile_safe_clj("(defn run [n] (* n n))", &Policy::deny_all())
        .expect("pure program must compile under deny-all");
    assert!(is_wasm(&wasm));
}

#[test]
fn graph_write_denied_without_grant() {
    let src = r#"(defn run [] (kqe-assert! "kg" "alice" "kg/name" "v"))"#;
    assert_policy_denied(compile_safe_clj(src, &Policy::deny_all()));
}

#[test]
fn graph_write_allowed_with_grant() {
    let src = r#"(defn run [] (kqe-assert! "kg" "alice" "kg/name" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["bafyGraphA"]);
    let wasm = compile_safe_clj(src, &policy).expect("granted graph-write must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn read_grant_does_not_confer_write() {
    // The read/write split is the point: graph-read must NOT authorize a write.
    let src = r#"(defn run [] (kqe-assert! "kg" "alice" "kg/name" "v"))"#;
    let policy = Policy::deny_all().grant_graph_read(["bafyGraphA"]);
    assert_policy_denied(compile_safe_clj(src, &policy));
}

#[test]
fn write_grant_does_not_confer_read() {
    // ...and symmetrically, write authority must not let you read.
    let src = r#"(defn run [] (kqe-get-objects "kg" "alice" "kg/name"))"#;
    let policy = Policy::deny_all().grant_graph_write(["bafyGraphA"]);
    assert_policy_denied(compile_safe_clj(src, &policy));
}

#[test]
fn graph_read_allowed_with_grant() {
    let src = r#"(defn run [] (kqe-get-objects "kg" "alice" "kg/name"))"#;
    let policy = Policy::deny_all().grant_graph_read(["bafyGraphA"]);
    let wasm = compile_safe_clj(src, &policy).expect("granted graph-read must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn infer_denied_then_allowed() {
    let src = r#"(defn run [] (llm-infer "model-cid-xyz" "ping"))"#;
    assert_policy_denied(compile_safe_clj(src, &Policy::deny_all()));

    let policy = Policy::deny_all().grant_infer(["model-cid-xyz"]);
    let wasm = compile_safe_clj(src, &policy).expect("granted infer must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn auth_introspection_denied_then_allowed() {
    let src = r#"(defn run [] (has-capability? "graph/x" "read"))"#;
    assert_policy_denied(compile_safe_clj(src, &Policy::deny_all()));

    let policy = Policy::deny_all().grant_auth();
    let wasm = compile_safe_clj(src, &policy).expect("granted auth must compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn all_denials_are_reported_at_once() {
    // A program touching three ungranted classes should name all three.
    let src = r#"
        (defn run []
          (do
            (kqe-assert! "kg" "a" "p" "v")
            (llm-infer "m" "x")
            (has-capability? "g" "read")))
    "#;
    match compile_safe_clj(src, &Policy::deny_all()) {
        Err(CljError::Policy(msg)) => {
            assert!(msg.contains("graph-write"), "missing graph-write: {msg}");
            assert!(msg.contains("infer"), "missing infer: {msg}");
            assert!(msg.contains("auth"), "missing auth: {msg}");
        }
        other => panic!("expected aggregated Policy denial, got {other:?}"),
    }
}

#[test]
fn zero_fuel_policy_is_rejected() {
    let policy = Policy::deny_all().with_limits(Limits {
        memory_pages: 4,
        fuel: 0,
        max_call_depth: 128,
        max_output_bytes: 65_536,
    });
    let res = compile_safe_clj("(defn run [n] n)", &policy);
    match res {
        Err(CljError::Policy(msg)) => assert!(msg.contains("fuel"), "{msg}"),
        other => panic!("expected fuel-quota rejection, got {other:?}"),
    }
}

#[test]
fn zero_memory_policy_is_rejected() {
    let policy = Policy::deny_all().with_limits(Limits {
        memory_pages: 0,
        fuel: 1_000_000,
        max_call_depth: 128,
        max_output_bytes: 65_536,
    });
    assert_policy_denied(compile_safe_clj("(defn run [n] n)", &policy));
}

#[test]
fn prelude_under_deny_all_stays_pure() {
    // The container/CBOR prelude must NOT drag in any host capability: a
    // deny-all policy with the prelude still compiles a pure module.
    let src = "(defn run [n] (inc n))";
    let wasm = compile_safe_clj_with_prelude(src, &Policy::deny_all())
        .expect("pure prelude program must compile under deny-all");
    assert!(is_wasm(&wasm));
}

#[test]
fn prelude_kqe_accessors_require_read_grant() {
    // KQE_PRELUDE accessors are only linked when graph-read is granted.
    let src = r#"(defn run [] (kqe-count (kqe-get-objects "kg" "alice" "kg/name")))"#;
    // Without read grant the kqe accessor layer is absent AND the call is denied.
    assert_policy_denied(compile_safe_clj_with_prelude(src, &Policy::deny_all()));
    // With read grant the accessor prelude links in and it compiles.
    let policy = Policy::deny_all().grant_graph_read(["bafyGraphA"]);
    let wasm = compile_safe_clj_with_prelude(src, &policy)
        .expect("granted graph-read must link the kqe prelude and compile");
    assert!(is_wasm(&wasm));
}

#[test]
fn policy_parses_from_edn() {
    let edn = r#"
        {:imports
         {:graph-read   ["bafyGraphA"]
          :graph-write  ["bafyGraphA"]
          :infer        ["model-cid-xyz"]
          :auth         true
          :egress       []}
         :limits
         {:memory-pages 8
          :fuel         2000000
          :max-call-depth 64
          :max-output-bytes 32768}}
    "#;
    let policy = Policy::parse_edn(edn).expect("policy EDN must parse");

    assert!(policy.graph_read.contains("bafyGraphA"));
    assert!(policy.graph_write.contains("bafyGraphA"));
    assert!(policy.infer.contains("model-cid-xyz"));
    assert!(policy.auth);
    assert_eq!(policy.limits.memory_pages, 8);
    assert_eq!(policy.limits.fuel, 2_000_000);
    assert_eq!(policy.limits.max_call_depth, 64);
    assert_eq!(policy.limits.max_output_bytes, 32_768);

    // And the parsed policy actually gates: write is granted, so this compiles.
    let src = r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#;
    assert!(compile_safe_clj(src, &policy).is_ok());
}

#[test]
fn empty_imports_policy_denies_everything() {
    let policy = Policy::parse_edn("{:limits {:memory-pages 4 :fuel 1000000}}")
        .expect("minimal policy must parse");
    let src = r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#;
    assert_policy_denied(compile_safe_clj(src, &policy));
}

// ── parse_edn error paths ──────────────────────────────────────────────────

fn assert_parse_err(src: &str) {
    match Policy::parse_edn(src) {
        Err(CljError::Policy(_)) => {}
        other => panic!("expected CljError::Policy parse failure, got {other:?}"),
    }
}

#[test]
fn parse_edn_rejects_non_map_top_level() {
    assert_parse_err("[:not :a :map]");
    assert_parse_err("42");
}

#[test]
fn parse_edn_rejects_malformed_edn() {
    assert_parse_err("{:imports {:graph-read [");
}

#[test]
fn parse_edn_rejects_wrong_typed_fields() {
    // :graph-read must be a vector of strings, not ints.
    assert_parse_err("{:imports {:graph-read [1 2 3]}}");
    // :auth must be a boolean.
    assert_parse_err(r#"{:imports {:auth "yes"}}"#);
    // :imports must be a map.
    assert_parse_err("{:imports [:graph-read]}");
    // :limits must be a map.
    assert_parse_err("{:limits 5}");
    // :fuel must be an integer.
    assert_parse_err(r#"{:limits {:fuel "lots"}}"#);
}

#[test]
fn parse_edn_rejects_empty_input() {
    assert_parse_err("");
}

#[test]
fn parse_edn_defaults_omitted_limits() {
    // A policy that omits :limits gets the non-zero defaults, so it compiles.
    let policy = Policy::parse_edn("{:imports {}}").expect("policy without :limits must parse");
    assert!(policy.limits.fuel > 0 && policy.limits.memory_pages > 0);
    assert!(compile_safe_clj("(defn run [n] n)", &policy).is_ok());
}

// ── full host-import classification (every kqe verb) ───────────────────────

#[test]
fn retract_is_classified_as_graph_write() {
    let src = r#"(defn run [] (kqe-retract! "kg" "a" "p" "v"))"#;
    // write grant allows it; read grant alone does not.
    assert_policy_denied(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_read(["g"]),
    ));
    assert!(compile_safe_clj(src, &Policy::deny_all().grant_graph_write(["g"])).is_ok());
}

#[test]
fn query_is_classified_as_graph_read() {
    let src = r#"(defn run [] (kqe-query "kg/role"))"#;
    // read grant allows it; write grant alone does not.
    assert_policy_denied(compile_safe_clj(
        src,
        &Policy::deny_all().grant_graph_write(["g"]),
    ));
    assert!(compile_safe_clj(src, &Policy::deny_all().grant_graph_read(["g"])).is_ok());
}

// ── doc ↔ code integrity: the example policy must parse and gate ───────────

#[test]
fn example_policy_edn_parses_and_gates() {
    let edn = include_str!("../examples/safe-policy.edn");
    let policy = Policy::parse_edn(edn).expect("examples/safe-policy.edn must parse");

    // The example grants graph read+write on one cid, nothing else.
    assert!(policy.class_granted(CapClass::GraphRead));
    assert!(policy.class_granted(CapClass::GraphWrite));
    assert!(!policy.class_granted(CapClass::Infer));
    assert!(!policy.class_granted(CapClass::Auth));
    assert_eq!(policy.limits.memory_pages, 4);
    assert_eq!(policy.limits.fuel, 1_000_000);

    // A write program compiles under it; an inference program does not.
    assert!(compile_safe_clj(r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#, &policy).is_ok());
    assert_policy_denied(compile_safe_clj(
        r#"(defn run [] (llm-infer "m" "x"))"#,
        &policy,
    ));
}

// ── completeness guard: deny_all denies every class; each grant flips one ──

#[test]
fn deny_all_denies_every_capability_class() {
    let p = Policy::deny_all();
    for class in [
        CapClass::GraphRead,
        CapClass::GraphWrite,
        CapClass::Infer,
        CapClass::Auth,
    ] {
        assert!(
            !p.class_granted(class),
            "deny_all must not grant {class:?} — that would be an ambient-authority leak"
        );
        // policy_key must be stable + non-empty (used in denial messages).
        assert!(!class.policy_key().is_empty());
    }
}

#[test]
fn each_grant_flips_exactly_one_class() {
    let cases = [
        (Policy::deny_all().grant_graph_read(["g"]), CapClass::GraphRead),
        (
            Policy::deny_all().grant_graph_write(["g"]),
            CapClass::GraphWrite,
        ),
        (Policy::deny_all().grant_infer(["m"]), CapClass::Infer),
        (Policy::deny_all().grant_auth(), CapClass::Auth),
    ];
    let all = [
        CapClass::GraphRead,
        CapClass::GraphWrite,
        CapClass::Infer,
        CapClass::Auth,
    ];
    for (policy, granted) in cases {
        for class in all {
            assert_eq!(
                policy.class_granted(class),
                class == granted,
                "grant of {granted:?} must flip only {granted:?}, but {class:?} differs"
            );
        }
    }
}
