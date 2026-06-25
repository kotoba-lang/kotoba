//! **Capability Confinement (theorem T3) verified in the emitted bytes.**
//!
//! The other safe-mode tests assert compile success/failure — a *proxy* for
//! confinement. These assert the property itself: the wasm module a safe build
//! emits embeds, in its import section, the interface name of every host
//! capability it uses (`kotoba:kais/kqe@0.1.0`, field `assert-quad`, …). So a
//! byte-scan for those names is a direct check that
//!
//!   1. an ungranted capability is *physically absent* from the module, and
//!   2. a granted module does not *leak* extra capabilities (e.g. the prelude
//!      or codegen silently pulling in `llm`/`auth`).
//!
//! Because the runtime can only bind imports a module declares, "absent from
//! the bytes" is the strongest possible form of "cannot reach that resource".

use kotoba_clj::{
    compile_safe_clj, compile_safe_clj_with_prelude, embedded_capability_ifaces, Policy,
};

/// Does the module embed `needle` as a contiguous byte string? Import
/// module/field names are stored UTF-8 in the import section, so this detects
/// the presence of a wired host import.
fn embeds(wasm: &[u8], needle: &str) -> bool {
    wasm.windows(needle.len()).any(|w| w == needle.as_bytes())
}

/// Every `kotoba:kais` interface name a host import can reference.
const ALL_IFACES: &[&str] = &[
    "kotoba:kais/kqe@0.1.0",
    "kotoba:kais/llm@0.1.0",
    "kotoba:kais/auth@0.1.0",
];

/// Assert the module wires exactly `expected` interfaces and no others.
fn assert_only_ifaces(wasm: &[u8], expected: &[&str]) {
    for iface in ALL_IFACES {
        let want = expected.contains(iface);
        let got = embeds(wasm, iface);
        assert_eq!(
            got, want,
            "interface `{iface}`: expected embedded={want}, found={got} — \
             confinement leak or missing import"
        );
    }
}

#[test]
fn pure_module_has_no_kais_imports() {
    // A pure program must carry ZERO host-capability imports in its bytes.
    let wasm = compile_safe_clj("(defn run [n] (* n n))", &Policy::deny_all()).unwrap();
    assert!(
        !embeds(&wasm, "kotoba:kais/"),
        "a pure module must embed no kotoba:kais import at all"
    );
}

#[test]
fn write_grant_emits_only_the_kqe_import() {
    let src = r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#;
    let policy = Policy::deny_all().grant_graph_write(["kg"]);
    let wasm = compile_safe_clj(src, &policy).unwrap();

    assert!(
        embeds(&wasm, "assert-quad"),
        "graph-write must wire assert-quad"
    );
    // The decisive confinement check: NO llm, NO auth leaked in.
    assert_only_ifaces(&wasm, &["kotoba:kais/kqe@0.1.0"]);
}

#[test]
fn infer_grant_emits_only_the_llm_import() {
    let src = r#"(defn run [] (llm-infer "model-cid-xyz" "ping"))"#;
    let policy = Policy::deny_all().grant_infer(["model-cid-xyz"]);
    let wasm = compile_safe_clj(src, &policy).unwrap();

    assert!(embeds(&wasm, "infer"), "infer grant must wire llm.infer");
    assert_only_ifaces(&wasm, &["kotoba:kais/llm@0.1.0"]);
}

#[test]
fn auth_grant_emits_only_the_auth_import() {
    let src = r#"(defn run [] (has-capability? "g" "read"))"#;
    let policy = Policy::deny_all().grant_auth();
    let wasm = compile_safe_clj(src, &policy).unwrap();

    assert!(
        embeds(&wasm, "has-capability"),
        "auth grant must wire has-capability"
    );
    assert_only_ifaces(&wasm, &["kotoba:kais/auth@0.1.0"]);
}

#[test]
fn prelude_under_deny_all_leaks_no_capability() {
    // The container/CBOR prelude must add no host import to a pure module.
    let wasm =
        compile_safe_clj_with_prelude("(defn run [n] (inc n))", &Policy::deny_all()).unwrap();
    assert!(
        !embeds(&wasm, "kotoba:kais/"),
        "the prelude must not leak any host-capability import under deny-all"
    );
}

#[test]
fn read_grant_with_prelude_wires_only_kqe() {
    // With graph-read granted, the kqe accessor prelude links in — and ONLY the
    // kqe interface should appear, never llm/auth.
    let src = r#"(defn run [] (kqe-count (kqe-get-objects "kg" "a" "p")))"#;
    let policy = Policy::deny_all().grant_graph_read(["kg"]);
    let wasm = compile_safe_clj_with_prelude(src, &policy).unwrap();

    assert!(
        embeds(&wasm, "get-objects"),
        "graph-read must wire get-objects"
    );
    assert_only_ifaces(&wasm, &["kotoba:kais/kqe@0.1.0"]);
}

#[test]
fn granting_more_than_used_emits_only_what_is_used() {
    // A generous policy (all classes granted) must still only emit the imports
    // the program actually *uses* — capability surface tracks the code, not the
    // grant. Here the program only writes, so only kqe should appear.
    let src = r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#;
    let policy = Policy::deny_all()
        .grant_graph_read(["kg"])
        .grant_graph_write(["kg"])
        .grant_infer(["m"])
        .grant_auth();
    let wasm = compile_safe_clj(src, &policy).unwrap();
    assert_only_ifaces(&wasm, &["kotoba:kais/kqe@0.1.0"]);
}

#[test]
fn module_using_all_interfaces_reports_all_three() {
    // A program touching graph-write + infer + auth must surface all three
    // distinct kais interfaces — exercises the multi-interface audit path.
    let src = r#"
        (defn run []
          (do (kqe-assert! "kg" "a" "p" "v")
              (llm-infer "m" "x")
              (has-capability? "g" "read")))
    "#;
    let policy = Policy::deny_all()
        .grant_graph_write(["kg"])
        .grant_infer(["m"])
        .grant_auth();
    let wasm = compile_safe_clj(src, &policy).unwrap();

    let mut got = embedded_capability_ifaces(&wasm);
    got.sort_unstable();
    let mut want = vec![
        "kotoba:kais/auth@0.1.0",
        "kotoba:kais/kqe@0.1.0",
        "kotoba:kais/llm@0.1.0",
    ];
    want.sort_unstable();
    assert_eq!(got, want);
}

#[test]
fn embedded_capability_ifaces_reports_the_audited_surface() {
    // The public audit helper must agree with the byte-level reality and be
    // usable to check a built module against its policy.
    let pure = compile_safe_clj("(defn run [n] (inc n))", &Policy::deny_all()).unwrap();
    assert!(embedded_capability_ifaces(&pure).is_empty());

    let src = r#"(defn run [] (kqe-assert! "kg" "a" "p" "v"))"#;
    let wasm = compile_safe_clj(src, &Policy::deny_all().grant_graph_write(["kg"])).unwrap();
    assert_eq!(
        embedded_capability_ifaces(&wasm),
        vec!["kotoba:kais/kqe@0.1.0"]
    );

    let src = r#"(defn run [] (llm-infer "m" "x"))"#;
    let wasm = compile_safe_clj(src, &Policy::deny_all().grant_infer(["m"])).unwrap();
    assert_eq!(
        embedded_capability_ifaces(&wasm),
        vec!["kotoba:kais/llm@0.1.0"]
    );
}
