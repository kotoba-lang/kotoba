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
use serde::Deserialize;

/// A browser-local kotoba read node over an in-memory Datom arrangement.
///
/// In P1 the arrangement is hydrated from `IdbBlockStore` blocks pulled (and
/// CID-verified) from a remote peer; here it is populated directly via `assert`
/// so the read engine can be exercised in isolation.
pub struct Node {
    arr: Arrangement,
    datomic_datoms: Vec<kotoba_datomic::Datom>,
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
            datomic_datoms: Vec::new(),
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
        self.datomic_datoms.push(kotoba_datomic::Datom::assert(
            KotobaCid::from_bytes(entity.as_bytes()),
            attr.to_string(),
            kotoba_edn::EdnValue::String(value.to_string()),
            self.tx.clone(),
        ));
    }

    /// Hydrate the arrangement from the exact JSON a remote kotoba
    /// `com.etzhayyim.apps.kotoba.datomic.datoms` returns: `[{e, a, v_edn, ...}]`.
    ///
    /// This is the P1 sync path (ADR-2606013600 D5): a one-time / delta block
    /// pull from a peer is decoded into Datoms and loaded into the kqe read
    /// engine — **without** the native `DistributedDatomReader` / kotoba-ipfs
    /// IPNS stack, which the browser node deliberately does not carry. The
    /// only added value-scalars are EDN strings (`"..."`) and keywords (`:kw`).
    pub fn load_server_datoms(&mut self, json: &str) -> Result<usize, String> {
        let arr: Vec<ServerDatom> = serde_json::from_str(json).map_err(|e| e.to_string())?;
        let mut n = 0usize;
        for d in &arr {
            // Skip retractions if the server marks them.
            if d.added == Some(false) {
                continue;
            }
            // Group by the server's content-addressed entity string; the read
            // engine only needs a stable per-entity key, so hashing the `e`
            // multibase string is sufficient for the browser arrangement.
            let datom = Datom::assert(
                KotobaCid::from_bytes(d.e.as_bytes()),
                d.a.clone(),
                Value::Text(parse_edn_scalar(&d.v_edn)),
                self.tx.clone(),
            );
            self.arr.insert_datom(&datom);
            self.datomic_datoms.push(d.to_datomic(&self.tx)?);
            n += 1;
        }
        Ok(n)
    }

    /// All current datoms whose attribute starts with `prefix` (AEVT-shaped scan).
    pub fn datoms_by_attr_prefix(&self, prefix: &str) -> Vec<Datom> {
        self.arr.datoms_with_attribute_prefix(&self.tx, prefix)
    }

    /// P2 local write: assert a batch of datoms into the arrangement (same
    /// `[{e,a,v_edn}]` shape as a read). The write lands in the local read
    /// engine immediately; durability is the caller's IndexedDB/OPFS layer.
    /// (Simplified Datomic transact — assertions only; tempid/unique-identity
    /// upsert + retraction semantics are a later increment.)
    pub fn transact(&mut self, datoms_json: &str) -> Result<usize, String> {
        self.load_server_datoms(datoms_json)
    }

    /// Export the full current datom set as the server `[{e,a,v_edn}]` JSON
    /// shape, so the caller can persist post-write state (seed + local writes)
    /// and re-`load_server_datoms` it on the next cold start. The exact `e`
    /// string is not round-trip-identical to the original CID, but is stable
    /// per entity within the snapshot — which is all the read engine needs.
    pub fn export_datoms_json(&self) -> String {
        let datoms = self.arr.datoms(&self.tx);
        let mut out = String::from("[");
        for (i, d) in datoms.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            let v_edn = match &d.v {
                Value::Text(s) => serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into()),
                Value::Integer(n) => n.to_string(),
                Value::Float(f) => f.to_string(),
                Value::Cid(c) => serde_json::to_string(&format!("{c:?}")).unwrap(),
                other => serde_json::to_string(&format!("{other:?}")).unwrap(),
            };
            let e = serde_json::to_string(&format!("{:?}", d.e)).unwrap();
            let a = serde_json::to_string(&d.a).unwrap();
            let v_edn_json = serde_json::to_string(&v_edn).unwrap();
            out.push_str(&format!(
                "{{\"e\":{e},\"a\":{a},\"v_edn\":{v_edn_json},\"added\":true}}"
            ));
        }
        out.push(']');
        out
    }

    /// Run a Datomic query against the browser-local Datomic DB hydrated by
    /// `load_server_datoms` / `transact`.
    pub fn datomic_q(&self, query_edn: &str, inputs_json: &str) -> Result<String, String> {
        let query = kotoba_edn::parse(query_edn).map_err(|e| format!("query_edn parse: {e}"))?;
        let input_sources: Vec<String> = if inputs_json.trim().is_empty() {
            Vec::new()
        } else {
            serde_json::from_str(inputs_json).map_err(|e| format!("inputs_json parse: {e}"))?
        };
        let inputs = input_sources
            .iter()
            .map(|src| kotoba_edn::parse(src).map_err(|e| format!("inputs_edn parse: {e}")))
            .collect::<Result<Vec<_>, _>>()?;
        let db = kotoba_datomic::Db::from_datoms(
            self.datomic_datoms.clone(),
            self.datomic_datoms.last().map(|d| d.t.clone()),
        );
        let rows = kotoba_datomic::q(query, &db, &inputs).map_err(|e| e.to_string())?;
        let rows_edn = rows
            .into_iter()
            .map(|row| {
                row.into_iter()
                    .map(|v| kotoba_edn::to_string(&v))
                    .collect::<Vec<_>>()
            })
            .collect::<Vec<_>>();
        serde_json::to_string(&serde_json::json!({
            "basis_t": db.basis_t.map(|cid| cid.to_multibase()),
            "rows_edn": rows_edn,
        }))
        .map_err(|e| e.to_string())
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

#[derive(Debug, Deserialize)]
struct ServerDatom {
    e: String,
    a: String,
    v_edn: String,
    t: Option<String>,
    added: Option<bool>,
}

impl ServerDatom {
    fn to_datomic(&self, default_tx: &KotobaCid) -> Result<kotoba_datomic::Datom, String> {
        let e = parse_cid_or_hash(&self.e);
        let t = self
            .t
            .as_deref()
            .map(parse_cid_or_hash)
            .unwrap_or_else(|| default_tx.clone());
        let v = kotoba_edn::parse(&self.v_edn).map_err(|e| format!("v_edn parse: {e}"))?;
        Ok(if self.added == Some(false) {
            kotoba_datomic::Datom::retract(e, self.a.clone(), v, t)
        } else {
            kotoba_datomic::Datom::assert(e, self.a.clone(), v, t)
        })
    }
}

fn parse_cid_or_hash(value: &str) -> KotobaCid {
    KotobaCid::from_multibase(value).unwrap_or_else(|| KotobaCid::from_bytes(value.as_bytes()))
}

/// Minimal EDN-scalar decoder mirroring `@etzhayyim/yoro-rw-free`'s
/// `parseEdnScalar`: `"str"` → str, `:kw` → bare name, else the raw token.
fn parse_edn_scalar(v_edn: &str) -> String {
    let s = v_edn.trim();
    if let Some(rest) = s.strip_prefix('"') {
        // EDN string — same escaping as JSON for our content.
        if let Ok(serde_json::Value::String(decoded)) = serde_json::from_str::<serde_json::Value>(s)
        {
            return decoded;
        }
        return rest.strip_suffix('"').unwrap_or(rest).to_string();
    }
    if let Some(kw) = s.strip_prefix(':') {
        return kw.to_string();
    }
    s.to_string()
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
// `/xrpc/com.etzhayyim.apps.kotoba.datomic.*` to these methods (ADR-2606013600 D3),
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

        /// Hydrate from a remote kotoba `datomic.datoms` JSON array (P1 sync).
        /// Returns the number of datoms loaded.
        #[wasm_bindgen(js_name = loadDatoms)]
        pub fn load_datoms(&mut self, datoms_json: &str) -> Result<usize, JsValue> {
            self.inner
                .load_server_datoms(datoms_json)
                .map_err(|e| JsValue::from_str(&e))
        }

        /// P2 local write — assert `[{e,a,v_edn}]` datoms into the local engine.
        pub fn transact(&mut self, datoms_json: &str) -> Result<usize, JsValue> {
            self.inner
                .transact(datoms_json)
                .map_err(|e| JsValue::from_str(&e))
        }

        /// Export current state as `[{e,a,v_edn}]` for IndexedDB/OPFS persistence.
        #[wasm_bindgen(js_name = exportDatoms)]
        pub fn export_datoms(&self) -> String {
            self.inner.export_datoms_json()
        }

        /// `searchActors(q)` → JSON `{ actors: [...] }` (same shape as the XRPC).
        #[wasm_bindgen(js_name = searchActors)]
        pub fn search_actors(&self, q: &str) -> Result<String, JsValue> {
            let actors = self.inner.search_actors(q);
            serde_json::to_string(&serde_json::json!({ "actors": actors }))
                .map_err(|e| JsValue::from_str(&e.to_string()))
        }

        /// `com.etzhayyim.apps.kotoba.datomic.q` over the local browser DB.
        #[wasm_bindgen(js_name = datomicQ)]
        pub fn datomic_q(&self, query_edn: &str, inputs_json: &str) -> Result<String, JsValue> {
            self.inner
                .datomic_q(query_edn, inputs_json)
                .map_err(|e| JsValue::from_str(&e))
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
        n.assert_text(
            did,
            ":yoro.profile/description",
            "Engi Knowledge Graph intel weaver",
        );

        let other = "did:web:etzhayyim.com:actor:watatsuna";
        n.assert_text(other, ":yoro.profile/did", other);

        assert_eq!(n.search_actors("").len(), 2, "empty q returns all profiles");
        let hit = n.search_actors("tsumugi");
        assert_eq!(hit.len(), 1);
        assert_eq!(hit[0].display_name, "紡ぎ Tsumugi");
    }

    #[test]
    fn hydrate_from_server_datoms_json_then_search() {
        // Exact shape returned by com.etzhayyim.apps.kotoba.datomic.datoms (P1 sync).
        let json = r#"[
          {"e":"bafyA","a":":yoro.profile/did","v_edn":"\"did:web:etzhayyim.com:actor:tsumugi\"","added":true},
          {"e":"bafyA","a":":yoro.profile/displayName","v_edn":"\"紡ぎ Tsumugi — Engi KG\"","added":true},
          {"e":"bafyB","a":":yoro.profile/did","v_edn":"\"did:web:etzhayyim.com:actor:watatsuna\"","added":true},
          {"e":"bafyC","a":":yoro.post/text","v_edn":"\"hello\"","added":true}
        ]"#;
        let mut n = Node::new();
        let loaded = n.load_server_datoms(json).unwrap();
        assert_eq!(loaded, 4);
        // Two profiles materialised; the post datom is ignored by searchActors.
        assert_eq!(n.search_actors("").len(), 2);
        let hit = n.search_actors("watatsuna");
        assert_eq!(hit.len(), 1);
        assert_eq!(hit[0].did, "did:web:etzhayyim.com:actor:watatsuna");
    }

    #[test]
    fn datomic_q_runs_over_hydrated_server_datoms() {
        let json = r#"[
          {"e":"bafyA","a":":person/name","v_edn":"\"Alice\"","t":"bafyTx","added":true},
          {"e":"bafyA","a":":person/role","v_edn":":admin","t":"bafyTx","added":true},
          {"e":"bafyB","a":":person/name","v_edn":"\"Bob\"","t":"bafyTx","added":true}
        ]"#;
        let mut n = Node::new();
        n.load_server_datoms(json).unwrap();
        let out = n
            .datomic_q(
                r#"{:find [?name] :where [[?e :person/role :admin] [?e :person/name ?name]]}"#,
                "[]",
            )
            .unwrap();
        let body: serde_json::Value = serde_json::from_str(&out).unwrap();
        assert_eq!(body["rows_edn"], serde_json::json!([["\"Alice\""]]));
    }

    #[test]
    fn transact_then_export_roundtrips_into_a_fresh_node() {
        let mut n = Node::new();
        // P2 local write
        let tx = r#"[
          {"e":"e1","a":":yoro.profile/did","v_edn":"\"did:web:etzhayyim.com:actor:newcomer\""},
          {"e":"e1","a":":yoro.profile/displayName","v_edn":"\"新人 Newcomer\""}
        ]"#;
        assert_eq!(n.transact(tx).unwrap(), 2);
        assert_eq!(n.search_actors("newcomer").len(), 1);

        // Export → re-import into a fresh node (persistence round-trip).
        let dump = n.export_datoms_json();
        let mut restored = Node::new();
        restored.load_server_datoms(&dump).unwrap();
        let hit = restored.search_actors("Newcomer");
        assert_eq!(hit.len(), 1);
        assert_eq!(hit[0].display_name, "新人 Newcomer");
    }
}
