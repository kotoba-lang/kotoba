//! M11: host-side trigger dispatch. A single combined `kotoba-mesh` component
//! defines distinct handlers; the WasmExecutor's per-trigger methods must each
//! invoke the matching export (verified by distinct return values).

use kotoba_clj::component::compile_kais_mesh_component_str;
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::WasmExecutor;
use std::collections::HashMap;

const WIT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;

#[test]
fn host_dispatches_each_trigger_to_its_own_export() {
    // each handler returns a distinct constant → proves the right export ran
    let src = "(ns m) \
               (defn run [c] \"RUN\") \
               (defn on-http [r] \"HTTP\") \
               (defn on-tick [e] \"TICK\") \
               (defn on-kse [t p] \"KSE\")";
    let comp = compile_kais_mesh_component_str(src, WIT).expect("compile kotoba-mesh component");
    let exec = WasmExecutor::new(GAS).expect("executor");
    let cid = "clj-mesh-dispatch";
    let did = "did:key:zTestAgent";
    let q = Vec::<WitQuad>::new;
    let h = HashMap::<String, String>::new;

    let run = exec
        .execute(cid, &comp, did, b"x".to_vec(), q(), h())
        .expect("run")
        .output_cbor;
    assert_eq!(run, b"RUN", "run export");

    let http = exec
        .execute_on_http(cid, &comp, did, b"req".to_vec(), q(), h())
        .expect("on-http")
        .output_cbor;
    assert_eq!(http, b"HTTP", "on-http export");

    let tick = exec
        .execute_on_tick(cid, &comp, did, 1_700_000_000_000, q(), h())
        .expect("on-tick")
        .output_cbor;
    assert_eq!(tick, b"TICK", "on-tick export");

    let kse = exec
        .execute_on_kse(
            cid,
            &comp,
            did,
            "kotoba/mail/in".into(),
            b"payload".to_vec(),
            q(),
            h(),
        )
        .expect("on-kse")
        .output_cbor;
    assert_eq!(kse, b"KSE", "on-kse export");
}

#[test]
fn missing_trigger_export_errors_cleanly() {
    // a run-only component has no on-http export → execute_on_http errors (no panic)
    let comp = compile_kais_mesh_component_str("(ns m) (defn run [c] c)", WIT).expect("compile");
    let exec = WasmExecutor::new(GAS).expect("executor");
    let r = exec.execute_on_http(
        "clj-runonly",
        &comp,
        "did:key:z",
        b"req".to_vec(),
        Vec::<WitQuad>::new(),
        HashMap::<String, String>::new(),
    );
    assert!(r.is_err(), "missing on-http export must error");
}
