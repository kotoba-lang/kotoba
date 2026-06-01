//! kotoba browser node — P0 PoC (ADR-2606013600).
//!
//! Proves the **kotoba read engine runs in the browser**: the `kotoba-kqe`
//! `DatomArrangement` (EAVT/AEVT/AVET/VAET covering indexes) compiled to
//! `wasm32-unknown-unknown` and driven from JavaScript through `wasm-bindgen`.
//!
//! This is the feasibility gate for the full browser node. What it demonstrates:
//!   - the Datom read engine (the same one behind `datomic.datoms`) executes
//!     entirely in-browser, no server round-trip;
//!   - a yoro-style `searchActors` over `:yoro.profile/*` Datoms returns from
//!     local state — the in-browser equivalent of the path verified end-to-end
//!     against the live kotoba server.
//!
//! What it does NOT yet do (subsequent phases in ADR-2606013600):
//!   - P1: `IdbBlockStore`-backed block persistence + `DistributedDatomReader`
//!     (Prolly traversal) + the Service-Worker `/xrpc/...` transparent shim;
//!   - P2: `transact` with an OPFS journal + delta sync;
//!   - P3: `BrowserComponentRuntime` (jco) for in-browser Pregel/UDF guests.
//!
//! The wider port is purely mechanical: apply the same per-target tokio gate
//! used by `kotoba-kqe` (drop the `net` feature on wasm) to `kotoba-kse`,
//! `kotoba-datomic`, `kotoba-graph`, `kotoba-crypto`, `kotoba-store` — the only
//! wasm blocker measured was tokio's `net` feature pulling `mio`.

use kotoba_core::cid::KotobaCid;
use kotoba_kqe::{Arrangement, Datom, Value};

/// A browser-local kotoba read node over an in-memory Datom arrangement.
///
/// In P1 the arrangement is hydrated from `IdbBlockStore` blocks pulled (and
/// CID-verified) from a remote peer; here it is populated directly via `assert`
/// so the read engine can be exercised in isolation.
pub struct Node {
    arr: Arrangement,
    tx: KotobaCid,
}

impl Default for Node {
    fn default() -> Self {
        Self::new()
    }
}

impl Node {
    pub fn new() -> Self {
        Node {
            arr: Arrangement::new(),
            // A single synthetic transaction CID for the PoC. Real nodes carry
            // the commit CID resolved from the graph head.
            tx: KotobaCid::from_bytes(b"kotoba-wasm-poc-tx"),
        }
    }

    /// Assert one Datom. `entity` is content-hashed to a CID (real ingest keys
    /// profiles by DID → CID); the value is stored as text.
    pub fn assert_text(&mut self, entity: &str, attr: &str, value: &str) {
        let d = Datom::assert(
            KotobaCid::from_bytes(entity.as_bytes()),
            attr.to_string(),
            Value::Text(value.to_string()),
            self.tx.clone(),
        );
        self.arr.insert_datom(&d);
    }

    /// All current datoms whose attribute starts with `prefix` (AEVT-shaped scan).
    pub fn datoms_by_attr_prefix(&self, prefix: &str) -> Vec<Datom> {
        self.arr.datoms_with_attribute_prefix(&self.tx, prefix)
    }

    /// yoro-style actor search: scan `:yoro.profile/*` Datoms, group by entity,
    /// and return profiles whose did/handle/displayName/description contains `q`
    /// (case-insensitive). Empty `q` returns all. This mirrors
    /// `@etzhayyim/yoro-rw-free::searchActors` but runs locally over wasm.
    pub fn search_actors(&self, q: &str) -> Vec<Profile> {
        use std::collections::BTreeMap;
        let mut by_entity: BTreeMap<String, Profile> = BTreeMap::new();
        for d in self.datoms_by_attr_prefix(":yoro.profile/") {
            let v = match &d.v {
                Value::Text(s) => s.clone(),
                _ => continue,
            };
            let key = format!("{:?}", d.e);
            let p = by_entity.entry(key).or_default();
            match d.a.as_str() {
                ":yoro.profile/did" => p.did = v,
                ":yoro.profile/handle" => p.handle = v,
                ":yoro.profile/displayName" => p.display_name = v,
                ":yoro.profile/description" => p.description = v,
                _ => {}
            }
        }
        let ql = q.to_lowercase();
        by_entity
            .into_values()
            .filter(|p| {
                ql.is_empty()
                    || p.did.to_lowercase().contains(&ql)
                    || p.handle.to_lowercase().contains(&ql)
                    || p.display_name.to_lowercase().contains(&ql)
                    || p.description.to_lowercase().contains(&ql)
            })
            .collect()
    }
}

/// A yoro actor profile materialised from `:yoro.profile/*` Datoms.
#[derive(Debug, Default, Clone, serde::Serialize)]
pub struct Profile {
    pub did: String,
    pub handle: String,
    #[serde(rename = "displayName")]
    pub display_name: String,
    pub description: String,
}

// ─── wasm-bindgen surface (browser) ────────────────────────────────────────
//
// Mirrors the kotoba XRPC NSIDs so a Service Worker can dispatch
// `/xrpc/ai.gftd.apps.kotoba.datomic.*` to these methods (ADR-2606013600 D3),
// keeping `@etzhayyim/yoro-rw-free` unchanged.
#[cfg(target_arch = "wasm32")]
mod wasm {
    use super::*;
    use wasm_bindgen::prelude::*;

    #[wasm_bindgen]
    pub struct KotobaNode {
        inner: Node,
    }

    #[wasm_bindgen]
    impl KotobaNode {
        #[wasm_bindgen(constructor)]
        pub fn new() -> KotobaNode {
            KotobaNode { inner: Node::new() }
        }

        /// Seed one profile attribute (P1 replaces this with block sync).
        pub fn assert(&mut self, entity: &str, attr: &str, value: &str) {
            self.inner.assert_text(entity, attr, value);
        }

        /// `searchActors(q)` → JSON `{ actors: [...] }` (same shape as the XRPC).
        #[wasm_bindgen(js_name = searchActors)]
        pub fn search_actors(&self, q: &str) -> Result<String, JsValue> {
            let actors = self.inner.search_actors(q);
            serde_json::to_string(&serde_json::json!({ "actors": actors }))
                .map_err(|e| JsValue::from_str(&e.to_string()))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn search_actors_over_in_wasm_read_engine() {
        let mut n = Node::new();
        let did = "did:web:etzhayyim.com:actor:tsumugi";
        n.assert_text(did, ":yoro.profile/did", did);
        n.assert_text(did, ":yoro.profile/handle", "etzhayyim.com.actor.tsumugi");
        n.assert_text(did, ":yoro.profile/displayName", "紡ぎ Tsumugi");
        n.assert_text(did, ":yoro.profile/description", "Engi Knowledge Graph intel weaver");

        let other = "did:web:etzhayyim.com:actor:watatsuna";
        n.assert_text(other, ":yoro.profile/did", other);

        assert_eq!(n.search_actors("").len(), 2, "empty q returns all profiles");
        let hit = n.search_actors("tsumugi");
        assert_eq!(hit.len(), 1);
        assert_eq!(hit[0].display_name, "紡ぎ Tsumugi");
    }
}
