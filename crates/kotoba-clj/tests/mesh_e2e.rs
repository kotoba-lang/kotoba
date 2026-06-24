//! Capstone end-to-end: the whole KOTOBA Mesh pipeline in one test —
//!
//!   Clojure source  --kotoba-clj-->  kotoba-mesh WASM component  (M7–M10)
//!        manifest    --kotoba-lattice deploy_messages-->  PutTriggers/PutRoutes (M16)
//!        routing     --TriggerRoutes--> which component fires for which event   (M13–M15)
//!        execution   --WasmExecutor.execute_on_*--> the matching guest export   (M11)
//!
//! Only the live net_actor gossip/inject hop (needs a running swarm) is out of
//! scope here; that path is covered by kotoba-server's net_actor unit tests.

use kotoba_clj::component::compile_kais_mesh_component_str;
use kotoba_lattice::routes::parse_schedule_ms;
use kotoba_lattice::{deploy_messages, AppManifest, LatticeMessage, TriggerRoutes};
use kotoba_runtime::host::WitQuad;
use kotoba_runtime::WasmExecutor;
use std::collections::{BTreeMap, HashMap};

const WIT: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../kotoba-runtime/wit");
const GAS: u64 = 10_000_000;

// One component handling all four trigger kinds; each export returns a distinct
// constant so we can prove the routed export actually ran.
const SRC: &str = "(ns bot) \
    (defn run [c] \"RUN\") \
    (defn on-http [r] \"HTTP\") \
    (defn on-tick [e] \"TICK\") \
    (defn on-kse [t p] \"KSE\")";

#[test]
fn full_pipeline_compile_deploy_route_execute() {
    // ── 1. compile Clojure → kotoba-mesh component ────────────────────────
    let component = compile_kais_mesh_component_str(SRC, WIT).expect("compile mesh component");
    assert_eq!(&component[0..4], b"\0asm");
    let cid = kotoba_core::cid::KotobaCid::from_bytes(&component).to_multibase();

    // ── 2. manifest binding the component to all trigger kinds ────────────
    let manifest = format!(
        "{{:kotoba.app/name \"bot\" \
           :kotoba.app/components \
           [{{:name \"bot\" :cid \"{cid}\" \
              :triggers [{{:type :http :route \"/reply\"}} \
                         {{:type :kse :topic \"kotoba/mail/in\"}} \
                         {{:type :cron :schedule \"every 5m\"}} \
                         {{:type :datom-delta :predicate \"mail/received\"}}]}}]}}"
    );
    let app = AppManifest::from_edn(&manifest).expect("parse manifest");

    // ── 3. deploy plan: PutTriggers (datom-Δ) + PutRoutes (kse/cron/http) ──
    let msgs = deploy_messages(&app, &BTreeMap::new());
    assert!(
        msgs.iter().any(|(_, m)| matches!(m, LatticeMessage::PutTriggers { triggers, .. } if !triggers.is_empty())),
        "deploy must emit PutTriggers for the datom-Δ trigger"
    );
    assert!(
        msgs.iter()
            .any(|(_, m)| matches!(m, LatticeMessage::PutRoutes { .. })),
        "deploy must emit PutRoutes for kse/cron/http"
    );

    // ── 4. routing: each event source resolves to our component cid ───────
    let routes = TriggerRoutes::from_app(&app, &BTreeMap::new());
    assert_eq!(routes.http_target("/reply"), Some(cid.as_str()));
    assert!(routes.kse_targets("kotoba/mail/in").contains(&cid));
    assert_eq!(routes.cron, vec![(cid.clone(), "every 5m".to_string())]);
    assert_eq!(parse_schedule_ms(&routes.cron[0].1), Some(300_000));

    // ── 5. execution: the routed cid runs the matching export ─────────────
    let exec = WasmExecutor::new(GAS).expect("executor");
    let did = "did:key:zMeshE2E";
    let q = Vec::<WitQuad>::new;
    let h = HashMap::<String, String>::new;

    // HTTP route → on-http
    let http_cid = routes.http_target("/reply").unwrap();
    let out = exec
        .execute_on_http(http_cid, &component, did, b"req".to_vec(), q(), h())
        .expect("on-http")
        .output_cbor;
    assert_eq!(out, b"HTTP");

    // KSE topic → on-kse
    let kse_cid = &routes.kse_targets("kotoba/mail/in")[0];
    let out = exec
        .execute_on_kse(
            kse_cid,
            &component,
            did,
            "kotoba/mail/in".into(),
            b"payload".to_vec(),
            q(),
            h(),
        )
        .expect("on-kse")
        .output_cbor;
    assert_eq!(out, b"KSE");

    // cron → on-tick
    let (cron_cid, _sched) = &routes.cron[0];
    let out = exec
        .execute_on_tick(cron_cid, &component, did, 1_700_000_000_000, q(), h())
        .expect("on-tick")
        .output_cbor;
    assert_eq!(out, b"TICK");

    // generic placement → run
    let out = exec
        .execute(&cid, &component, did, b"ctx".to_vec(), q(), h())
        .expect("run")
        .output_cbor;
    assert_eq!(out, b"RUN");
}
