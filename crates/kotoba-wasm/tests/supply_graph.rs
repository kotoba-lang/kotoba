//! Empirical check: the kabuto supply graph loads into the kotoba read engine
//! and the datomicQ queries the viewer relies on return correct data.
//! (Native run of the same Node API the wasm KotobaNode wraps.)
use kotoba_wasm::Node;

// The kabuto seed lives in the parent monorepo (`20-actors/kabuto/viz/`) and is
// absent in a standalone kotoba checkout. Reference it by path and load at
// RUNTIME (with a graceful skip) rather than `include_str!` — a compile-time
// include of a sometimes-absent file breaks `cargo test` for the whole crate,
// and a missing-fixture skip can't be expressed as `#[ignore]` on an
// `include_str!`. See the kotoba split (net-kotobase, 2026-06-04).
const CONTRACT_PATH: &str = concat!(
    env!("CARGO_MANIFEST_DIR"),
    "/../../../../20-actors/kabuto/viz/supply-datoms.json"
);

fn rows(n: &Node, q: &str) -> Vec<Vec<String>> {
    let out = n.datomic_q(q, "[]").unwrap();
    let v: serde_json::Value = serde_json::from_str(&out).unwrap();
    v["rows_edn"]
        .as_array()
        .unwrap()
        .iter()
        .map(|r| {
            r.as_array()
                .unwrap()
                .iter()
                .map(|c| c.as_str().unwrap().to_string())
                .collect()
        })
        .collect()
}

#[test]
fn kabuto_supply_graph_drives_the_viewer() {
    // Skip when the kabuto seed isn't checked out alongside (standalone kotoba).
    let Ok(json) = std::fs::read_to_string(CONTRACT_PATH) else {
        eprintln!("skipping kabuto_supply_graph: fixture not present at {CONTRACT_PATH}");
        return;
    };
    let json = json.as_str();
    // Expected counts are derived from the embedded contract itself, so the
    // test stays correct as the kabuto seed grows each /loop iteration.
    let contract: Vec<serde_json::Value> = serde_json::from_str(json).unwrap();
    let want_companies = contract.iter().filter(|d| d["a"] == ":company/id").count();
    let want_edges = contract
        .iter()
        .filter(|d| d["a"] == ":supply.edge/from")
        .count();
    assert!(want_companies > 100, "non-trivial seed");

    let mut n = Node::new();
    let loaded = n.load_server_datoms(json).unwrap();
    assert_eq!(loaded, contract.len(), "every contract datom loaded");

    // id query → CID-token ↔ id-string map the viewer joins on
    let ids = rows(&n, "{:find [?e ?v] :where [[?e :company/id ?v]]}");
    assert_eq!(
        ids.len(),
        want_companies,
        "all companies expose :company/id"
    );

    // names join on the SAME ?e token (stability the viewer depends on)
    let names = rows(&n, "{:find [?e ?v] :where [[?e :company/name ?v]]}");
    let name_tokens: std::collections::HashSet<_> = names.iter().map(|r| r[0].clone()).collect();
    let id_tokens: std::collections::HashSet<_> = ids.iter().map(|r| r[0].clone()).collect();
    assert!(
        id_tokens.is_subset(&name_tokens),
        "?e tokens stable across queries"
    );

    // edges: from/to/criticality/commodity all present
    let edges = rows(
        &n,
        "{:find [?f ?t ?crit ?comm] :where [[?e :supply.edge/from ?f]\
         [?e :supply.edge/to ?t][?e :supply.edge/criticality ?crit]\
         [?e :supply.edge/commodity ?comm]]}",
    );
    assert_eq!(edges.len(), want_edges, "all supply edges queryable");

    // TSMC is a known supplier hub → its id resolves and out-degree is high
    let tsmc = ids
        .iter()
        .find(|r| r[1] == "\"org.corp.tw.tsmc\"")
        .expect("TSMC present");
    let token = &tsmc[0];
    let outv = rows(&n, "{:find [?e ?v] :where [[?e :company/out ?v]]}");
    let tsmc_out = outv.iter().find(|r| &r[0] == token).map(|r| r[1].clone());
    assert_eq!(
        tsmc_out.as_deref(),
        Some("12"),
        "TSMC out-degree from the engine"
    );

    // sector renders as an EDN keyword (viewer strips the leading colon)
    let sectors = rows(&n, "{:find [?e ?v] :where [[?e :company/sector ?v]]}");
    assert!(sectors.iter().any(|r| r[1] == ":semiconductors"));
}
