//! KOTOBA Mesh M6 — datom-Δ trigger (data-driven serverless).
//!
//!   manifest datom-delta triggers → match incoming datoms → fire components
//!
//! kotoba's distinctive trigger: a component runs when the GRAPH changes, not on
//! HTTP/cron. "When some entity gets kg/claim/role = admin, run the audit."
//!
//! Run:  cargo run -p kotoba-lattice --example mesh_delta

use kotoba_lattice::{delta_triggers, fired_by_batch, fired_by_datom, AppManifest};

const APP: &str = r#"{:kotoba.app/name "audit-bot"
    :kotoba.app/components
    [{:name "audit"   :cid "bafyAudit"
      :triggers [{:type :datom-delta :predicate "kg/claim/role" :value "admin"}]}
     {:name "indexer" :cid "bafyIndex"
      :triggers [{:type :datom-delta :predicate "kg/claim/role"}]}
     {:name "web"     :cid "bafyWeb"
      :triggers [{:type :http :route "/"}]}]}"#;

fn main() {
    let app = AppManifest::from_edn(APP).unwrap();
    let triggers = delta_triggers(&app);

    println!("datom-Δ triggers ({}):", triggers.len());
    for t in &triggers {
        println!(
            "  {} ← ({} {})",
            t.component,
            t.predicate,
            t.value.as_deref().unwrap_or("<any>")
        );
    }

    // a stream of newly-asserted datoms (predicate, object)
    let stream = [
        ("kg/claim/role", "admin"),
        ("kg/claim/role", "user"),
        ("kg/claim/name", "Alice"),
    ];

    println!("\nper-datom firing:");
    for (p, o) in stream {
        println!("  ({p} = {o}) → {:?}", fired_by_datom(&triggers, p, o));
    }

    let batch: Vec<(String, String)> =
        stream.iter().map(|(p, o)| (p.to_string(), o.to_string())).collect();
    println!("\nbatch firing (deduped): {:?}", fired_by_batch(&triggers, &batch));
    println!(
        "\nThe host fires these components by placing them (StartComponent →\n\
         WasmExecutor), the same path as auction placement. Wiring the live Δ\n\
         stream (kotoba-query Delta) into net_actor's datom-apply is the final step."
    );
}
