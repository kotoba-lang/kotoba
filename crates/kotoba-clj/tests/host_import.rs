//! Stage C-1: a Clojure-compiled guest **calls a `kotoba:kais` host function**.
//!
//! `(has-capability? resource ability)` lowers to a real wasm import wired to
//! the runtime's `auth.has-capability`. This is the first time a compiled
//! kotoba-clj guest grows an import section and reaches *out* to the host (prior
//! steps only computed over bytes the host lowered *in*). Two proofs:
//!
//!  1. **The Component encoder accepts the import** — `compile_kais_component_str`
//!     runs `ComponentEncoder::…validate(true)`, so a wrong Canonical-ABI core
//!     signature or import name would fail to encode here.
//!  2. **It live-invokes through the real host** — `WasmExecutor` binds
//!     `auth.has-capability`, and the answer is driven deterministically by the
//!     `quad_snapshot` we hand `execute` (no inference engine required).
#![cfg(feature = "component")]

use std::collections::HashMap;

use kotoba_clj::component::compile_kais_component_str;
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::WasmExecutor;

const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;
const AGENT: &str = "did:key:z6MkTestAgent";

/// A guest that returns "yes"/"no" depending on whether the agent holds the
/// `read` capability on `graph/x`.
const SRC: &str = r#"
    (defn run [ctx]
      (if (has-capability? "graph/x" "read") "yes" "no"))
"#;

/// Compile SRC to a kotoba-node component and invoke it with the given snapshot.
fn invoke_with(snapshot: Vec<WitQuad>) -> Vec<u8> {
    let component = compile_kais_component_str(SRC, KAIS_WIT_DIR).expect("compile + encode");
    let exec = WasmExecutor::new(GAS).expect("executor");
    exec.execute(
        "clj-host-import-test",
        &component,
        AGENT,
        b"ctx".to_vec(),
        snapshot,
        HashMap::new(),
    )
    .expect("execute run(ctx)")
    .output_cbor
}

/// The capability quad the host's `has-capability` convention looks for:
/// subject = agent DID, predicate = `auth/capability/{resource}/{ability}`.
fn capability_quad() -> WitQuad {
    WitQuad {
        graph: String::new(),
        subject: AGENT.to_string(),
        predicate: "auth/capability/graph/x/read".to_string(),
        object_cbor: Vec::new(),
    }
}

#[test]
fn host_grants_capability() {
    assert_eq!(invoke_with(vec![capability_quad()]), b"yes");
}

#[test]
fn host_denies_when_capability_absent() {
    // empty snapshot → host returns false → guest returns "no"
    assert_eq!(invoke_with(Vec::new()), b"no");
}

#[test]
fn host_denies_when_only_unrelated_capability_present() {
    let unrelated = WitQuad {
        graph: String::new(),
        subject: AGENT.to_string(),
        predicate: "auth/capability/graph/y/write".to_string(),
        object_cbor: Vec::new(),
    };
    assert_eq!(invoke_with(vec![unrelated]), b"no");
}
