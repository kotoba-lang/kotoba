//! Stage C-5: a Clojure-compiled guest **reads and writes Datoms** through the
//! `kotoba:kais/kqe` host interface — the Datomic surface of kotoba.
//!
//!   - `(kqe-assert! g s p obj-cbor)` / `(kqe-retract! …)` exercise the
//!     flattened-record + indirect-`result<_, string>` ABI (8 flat params + a
//!     return-area pointer). Asserts land in `InvokeResult::assert_quads`.
//!   - `(kqe-get-objects g s p)` exercises a host→guest **list lift**: the host
//!     lowers `list<list<u8>>` into guest memory via our `cabi_realloc`; the
//!     guest walks the element array with the `KQE_PRELUDE` accessors.
//!   - `(kqe-query filter)` lifts `list<quad>` (32-byte records) the same way.
//!   - The **Datomic loop**: quads asserted by the compiled-Clojure agent are
//!     converted to `kotoba_kqe::Datom` → `kotoba_datomic::Datom::from_kqe` →
//!     a `Db`, and queried back — closing agent-writes → Datomic-reads.
#![cfg(feature = "component")]

use std::collections::HashMap;

use kotoba_clj::component::compile_kais_component_str;
use kotoba_clj::prelude;
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::{InvokeResult, WasmExecutor};

const KAIS_WIT_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;
const AGENT: &str = "did:key:z6MkTestAgent";

/// Compile `src` (with the full prelude) and invoke `run(ctx)` with `snapshot`.
fn invoke(src: &str, snapshot: Vec<WitQuad>) -> InvokeResult {
    let full = format!("{}\n{}", prelude(), src);
    let component = compile_kais_component_str(&full, KAIS_WIT_DIR).expect("compile + encode");
    let exec = WasmExecutor::new(GAS).expect("executor");
    exec.execute("clj-kqe-test", &component, AGENT, b"ctx".to_vec(), snapshot, HashMap::new())
        .expect("execute run(ctx)")
}

/// CBOR text bytes (what `cbor-enc-text!` produces in-guest) via ciborium, so
/// guest-built object-cbor and host-seeded object-cbor are byte-identical.
fn cbor_text(s: &str) -> Vec<u8> {
    let mut out = Vec::new();
    ciborium::into_writer(&ciborium::Value::Text(s.to_string()), &mut out).expect("cbor");
    out
}

fn quad(graph: &str, subject: &str, predicate: &str, obj: &str) -> WitQuad {
    WitQuad {
        graph: graph.to_string(),
        subject: subject.to_string(),
        predicate: predicate.to_string(),
        object_cbor: cbor_text(obj),
    }
}

// ---- writes: assert / retract -----------------------------------------------

#[test]
fn assert_quad_buffers_a_datom() {
    let src = r#"
        (defn run [ctx]
          (let [obj (bytes-finish (cbor-enc-text! (bytes-alloc 32) "Alice"))]
            (if (kqe-assert! "kg" "alice" "kg/name" obj) "asserted" "failed")))
    "#;
    let result = invoke(src, Vec::new());
    assert_eq!(result.output_cbor, b"asserted");
    assert_eq!(result.assert_quads.len(), 1);
    let q = &result.assert_quads[0];
    assert_eq!(q.graph, "kg");
    assert_eq!(q.subject, "alice");
    assert_eq!(q.predicate, "kg/name");
    // the guest-built object-cbor is spec-conformant CBOR text
    assert_eq!(q.object_cbor, cbor_text("Alice"));
    // assert-quad charges 10 gas
    assert!(result.gas_used >= 10, "expected gas for the assert, got {}", result.gas_used);
}

#[test]
fn retract_quad_buffers_a_tombstone() {
    let src = r#"
        (defn run [ctx]
          (let [obj (bytes-finish (cbor-enc-text! (bytes-alloc 32) "admin"))]
            (if (kqe-retract! "kg" "alice" "kg/role" obj) "retracted" "failed")))
    "#;
    let result = invoke(src, Vec::new());
    assert_eq!(result.output_cbor, b"retracted");
    assert!(result.assert_quads.is_empty());
    assert_eq!(result.retract_quads.len(), 1);
    assert_eq!(result.retract_quads[0].predicate, "kg/role");
    assert_eq!(result.retract_quads[0].object_cbor, cbor_text("admin"));
}

#[test]
fn assert_loop_buffers_many_datoms() {
    // 5 datoms from one invocation — the write path threads through loop/recur.
    let src = r#"
        (defn run [ctx]
          (let [obj (bytes-finish (cbor-enc-text! (bytes-alloc 32) "v"))]
            (loop [i 0]
              (if (>= i 5)
                "done"
                (do (kqe-assert! "kg" "e" "kg/tick" obj)
                    (recur (+ i 1)))))))
    "#;
    let result = invoke(src, Vec::new());
    assert_eq!(result.output_cbor, b"done");
    assert_eq!(result.assert_quads.len(), 5);
}

// ---- reads: get-objects / query ----------------------------------------------

#[test]
fn get_objects_lifts_the_object_list() {
    let snapshot = vec![
        quad("kg", "alice", "kg/name", "Alice"),
        quad("kg", "alice", "kg/role", "admin"),
        quad("kg", "bob", "kg/name", "Bob"),
    ];
    // exactly one (kg, alice, kg/name) object; return its raw CBOR bytes
    let src = r#"
        (defn run [ctx]
          (let [objs (kqe-get-objects "kg" "alice" "kg/name")]
            (if (= (kqe-count objs) 1) (kqe-obj-nth objs 0) "wrong-count")))
    "#;
    let result = invoke(src, snapshot);
    assert_eq!(result.output_cbor, cbor_text("Alice"));
}

#[test]
fn get_objects_empty_when_no_match() {
    let snapshot = vec![quad("kg", "alice", "kg/name", "Alice")];
    let src = r#"
        (defn run [ctx]
          (if (= (kqe-count (kqe-get-objects "kg" "nobody" "kg/name")) 0)
            "empty" "nonempty"))
    "#;
    assert_eq!(invoke(src, snapshot).output_cbor, b"empty");
}

#[test]
fn query_filters_by_predicate_and_lifts_quads() {
    let snapshot = vec![
        quad("kg", "alice", "kg/role", "admin"),
        quad("kg", "bob", "kg/role", "user"),
        quad("kg", "alice", "kg/name", "Alice"),
    ];
    // 2 role-quads; return the subject of the first (snapshot order preserved)
    let src = r#"
        (defn run [ctx]
          (let [qs (kqe-query "kg/role")]
            (if (= (kqe-count qs) 2) (kqe-quad-subject qs 0) "wrong-count")))
    "#;
    assert_eq!(invoke(src, snapshot).output_cbor, b"alice");
}

#[test]
fn query_quad_fields_read_back_in_guest() {
    let snapshot = vec![quad("g1", "s1", "p1", "o1")];
    // verify every lifted field of the quad record in-guest via str-eq?
    let src = r#"
        (defn run [ctx]
          (let [qs (kqe-query "")]
            (if (and (= (kqe-count qs) 1)
                     (str-eq? (kqe-quad-graph qs 0) "g1")
                     (str-eq? (kqe-quad-subject qs 0) "s1")
                     (str-eq? (kqe-quad-predicate qs 0) "p1"))
              (kqe-quad-object qs 0)
              "mismatch")))
    "#;
    assert_eq!(invoke(src, snapshot).output_cbor, cbor_text("o1"));
}

#[test]
fn read_modify_write_roundtrip() {
    // The full agent shape: read a datom, decide, write a derived datom back.
    let snapshot = vec![quad("kg", "alice", "kg/role", "admin")];
    let src = r#"
        (defn run [ctx]
          (let [objs (kqe-get-objects "kg" "alice" "kg/role")]
            (if (>= (kqe-count objs) 1)
              (if (kqe-assert! "kg" "alice" "kg/verified" (kqe-obj-nth objs 0))
                "ok" "assert-failed")
              "not-found")))
    "#;
    let result = invoke(src, snapshot);
    assert_eq!(result.output_cbor, b"ok");
    assert_eq!(result.assert_quads.len(), 1);
    assert_eq!(result.assert_quads[0].predicate, "kg/verified");
    // the derived datom carries the object read from the snapshot
    assert_eq!(result.assert_quads[0].object_cbor, cbor_text("admin"));
}

// ---- the Datomic loop ---------------------------------------------------------

/// Quads asserted by the compiled-Clojure agent become Datoms in a
/// `kotoba_datomic::Db` and are queryable through the Datomic facade —
/// agent-writes → Datomic-reads, end to end.
#[test]
fn agent_asserts_flow_into_datomic_db() {
    use kotoba_core::cid::KotobaCid;

    let src = r#"
        (defn run [ctx]
          (let [name (bytes-finish (cbor-enc-text! (bytes-alloc 32) "Alice"))
                role (bytes-finish (cbor-enc-text! (bytes-alloc 32) "admin"))]
            (do (kqe-assert! "kg" "alice" "kg/name" name)
                (kqe-assert! "kg" "alice" "kg/role" role)
                "ok")))
    "#;
    let result = invoke(src, Vec::new());
    assert_eq!(result.output_cbor, b"ok");
    assert_eq!(result.assert_quads.len(), 2);

    // SerializedQuad → kotoba_kqe::Datom → kotoba_datomic::Datom (from_kqe)
    let tx = KotobaCid::from_bytes(b"tx-clj-agent");
    let datoms: Vec<kotoba_datomic::Datom> = result
        .assert_quads
        .iter()
        .map(|q| {
            let text: ciborium::Value =
                ciborium::from_reader(q.object_cbor.as_slice()).expect("object cbor");
            let v = kotoba_kqe::datom::Value::Text(text.as_text().expect("text").to_string());
            kotoba_datomic::Datom::from_kqe(kotoba_kqe::datom::Datom {
                e: KotobaCid::from_bytes(q.subject.as_bytes()),
                a: q.predicate.clone(),
                v,
                tx: tx.clone(),
                op: true,
            })
        })
        .collect();

    let db = kotoba_datomic::Db::from_datoms(datoms, Some(tx));
    let facts = db.datoms();
    assert_eq!(facts.len(), 2);

    let alice = KotobaCid::from_bytes(b"alice");
    for f in &facts {
        assert_eq!(f.e, alice, "both datoms are about the same entity");
        assert!(f.added);
    }
    let name = facts.iter().find(|f| f.a == "kg/name").expect("kg/name datom");
    let role = facts.iter().find(|f| f.a == "kg/role").expect("kg/role datom");
    assert_eq!(name.v, kotoba_edn::EdnValue::String("Alice".to_string()));
    assert_eq!(role.v, kotoba_edn::EdnValue::String("admin".to_string()));
}
