//! kotoba browser node — P0–P2 (ADR-2606013600).
//!
//! Proves the **kotoba read engine runs in the browser**: the `kotoba-kqe`
//! `DatomArrangement` (EAVT/AEVT/AVET/VAET covering indexes) compiled to
//! `wasm32-unknown-unknown` and driven from JavaScript through `wasm-bindgen`.
//!
//! What it demonstrates:
//!   - **P0** — the Datom read engine (the same one behind `datomic.datoms`)
//!     executes entirely in-browser, no server round-trip; a yoro-style
//!     `searchActors` over `:yoro.profile/*` Datoms returns from local state.
//!   - **P1** — durable persistence: the node exports a **canonical, content-
//!     addressed snapshot** (`snapshot()` / `snapshotCid()`) that the JS glue
//!     persists to **IndexedDB** and re-loads on cold start — reseed-free,
//!     offline-first. A remote `datomic.datoms` pull is folded in as a **delta**
//!     (idempotent — see below), so re-sync never duplicates state.
//!   - **P2** — local writes: `transact()` lands datoms in the read engine
//!     immediately; the JS glue appends the same batch to an **OPFS append-only
//!     journal**, so an un-compacted write survives a cold restart by replaying
//!     the journal on top of the snapshot (`replayJournal()`).
//!
//! **Idempotency invariant (the part that makes persistence correct).**
//! `kqe::Arrangement::insert_value` is a plain `push` — it does *not* dedup, so
//! re-loading an overlapping snapshot+journal, or replaying a delta twice, would
//! otherwise multiply rows in the AVET/EAVT vectors and corrupt `searchActors`.
//! This node therefore dedups every assertion by the **resolved entity CID**
//! (`KotobaCid` multibase) + attribute + decoded scalar — *not* by the raw `e`
//! string — so a write keyed `"e1"` in the OPFS journal and the same write keyed
//! by its CID-multibase in the IndexedDB snapshot collapse to one datom. For the
//! same reason `snapshot()` emits the entity as `cid.to_multibase()` (a stable,
//! re-parseable identity) rather than a `Debug` string.
//!
//! Not yet done: **P3** — `BrowserComponentRuntime` (jco) for in-browser
//! Pregel/UDF guests (spikes live under `web/p3-*`). Retraction / tempid upsert
//! semantics in `transact` are also a later increment (assertions only today).

use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::prolly::ProllyTree;
use kotoba_core::store::BlockStore;
use kotoba_kqe::{Arrangement, Datom, Value};
use serde::Deserialize;
use std::collections::HashMap;
use std::collections::HashSet;
use std::sync::Mutex;

/// A **CID-verifying** in-memory block cache for the browser node (P3,
/// ADR-2606013600 D5). Blocks pulled from a peer / IPFS gateway (async, JS side)
/// or restored from the durable `IdbBlockStore` are inserted here **only after
/// re-deriving and matching their CID** — trustless replication: a tampered
/// block (CID ≠ `sha2-256(dag-cbor-bytes)`) is rejected. The sync
/// `ProllyTree::scan_prefix` traversal then runs over this cache, so the browser
/// reads the canonical content-addressed Datom log via the **same Prolly/IPLD
/// code path as the server** — not a bespoke snapshot.
#[derive(Default)]
pub struct BlockCache {
    blocks: Mutex<HashMap<[u8; 36], Vec<u8>>>,
}

impl BlockCache {
    pub fn new() -> Self {
        Self::default()
    }

    /// Insert a block under its claimed CID, rejecting it unless
    /// `KotobaCid::from_bytes(bytes) == cid` (content-address re-verification).
    pub fn insert_verified(&self, cid: &KotobaCid, bytes: &[u8]) -> Result<(), String> {
        let actual = KotobaCid::from_bytes(bytes);
        if &actual != cid {
            return Err(format!(
                "CID mismatch: claimed {} != actual {}",
                cid.to_multibase(),
                actual.to_multibase()
            ));
        }
        self.blocks.lock().unwrap().insert(cid.0, bytes.to_vec());
        Ok(())
    }

    /// CID-verified insert keyed by a multibase CID string (the JS/XRPC form).
    pub fn insert_verified_multibase(&self, cid_mb: &str, bytes: &[u8]) -> Result<(), String> {
        let cid = KotobaCid::from_multibase(cid_mb)
            .ok_or_else(|| format!("bad CID multibase: {cid_mb}"))?;
        self.insert_verified(&cid, bytes)
    }

    pub fn len(&self) -> usize {
        self.blocks.lock().unwrap().len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// CIDs reachable from `root` (inclusive) that are **not yet in the cache**.
    /// Drives the browser block-sync BFS: JS pulls these via `block.get`,
    /// re-ingests them CID-verified, and calls this again until it returns empty
    /// — at which point the whole tree is local and `hydrate_from_prolly` can
    /// traverse it. Node decoding (finding `Internal` children) stays in Rust.
    pub fn missing_cids(&self, root: &KotobaCid) -> Vec<KotobaCid> {
        use kotoba_core::prolly::ProllyNode;
        let mut missing = Vec::new();
        let mut seen: HashSet<[u8; 36]> = HashSet::new();
        let mut stack = vec![root.clone()];
        while let Some(cid) = stack.pop() {
            if !seen.insert(cid.0) {
                continue;
            }
            if !self.has(&cid) {
                missing.push(cid);
                continue; // can't descend into a block we don't have yet
            }
            // Present → decode to discover children (leaves have none).
            if let Ok(Some(ProllyNode::Internal { children, .. })) =
                ProllyTree::load_node(&cid, self)
            {
                for (_, child) in children {
                    stack.push(child);
                }
            }
        }
        missing
    }
}

impl BlockStore for BlockCache {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.blocks.lock().unwrap().insert(cid.0, data.to_vec());
        Ok(())
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        Ok(self
            .blocks
            .lock()
            .unwrap()
            .get(&cid.0)
            .map(|v| Bytes::from(v.clone())))
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.blocks.lock().unwrap().contains_key(&cid.0)
    }
}

/// A browser-local kotoba read node over an in-memory Datom arrangement.
///
/// In P1 the arrangement is hydrated from `IdbBlockStore` blocks pulled (and
/// CID-verified) from a remote peer; here it is populated directly via `assert`
/// so the read engine can be exercised in isolation.
pub struct Node {
    arr: Arrangement,
    datomic_datoms: Vec<kotoba_datomic::Datom>,
    tx: KotobaCid,
    /// Dedup guard keyed by `resolved-entity-CID-multibase \u{1} attr \u{1}
    /// decoded-scalar`. Makes `assert` / `load_server_datoms` / `replay_journal`
    /// idempotent so an overlapping IndexedDB snapshot + OPFS journal (P1/P2)
    /// never double-inserts into the non-deduping kqe arrangement vectors.
    seen: HashSet<String>,
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
            seen: HashSet::new(),
        }
    }

    /// Content-addressed dedup key: resolved entity CID (stable across the raw
    /// `"e1"` journal form and the `to_multibase()` snapshot form) + attr +
    /// decoded scalar value.
    fn dedup_key(entity: &KotobaCid, attr: &str, decoded: &str) -> String {
        format!("{}\u{1}{}\u{1}{}", entity.to_multibase(), attr, decoded)
    }

    /// Number of distinct datoms currently held (post-dedup).
    pub fn datom_count(&self) -> usize {
        self.seen.len()
    }

    /// Assert one Datom. `entity` is content-hashed to a CID (real ingest keys
    /// profiles by DID → CID); the value is stored as text. Idempotent.
    pub fn assert_text(&mut self, entity: &str, attr: &str, value: &str) {
        let e = KotobaCid::from_bytes(entity.as_bytes());
        let key = Self::dedup_key(&e, attr, value);
        if !self.seen.insert(key) {
            return; // already present — keep the arrangement vectors duplicate-free
        }
        let d = Datom::assert(e.clone(), attr.to_string(), Value::Text(value.to_string()), self.tx.clone());
        self.arr.insert_datom(&d);
        self.datomic_datoms.push(kotoba_datomic::Datom::assert(
            e,
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
        self.apply_records(&arr)
    }

    /// Apply a batch of decoded datom records (the shared sink for the JSON sync
    /// path, the OPFS journal replay, and the P3 Prolly traversal). Idempotent —
    /// dedups by resolved entity CID + attr + decoded scalar.
    fn apply_records(&mut self, records: &[ServerDatom]) -> Result<usize, String> {
        let mut n = 0usize;
        for d in records {
            // Skip retractions if the server marks them.
            if d.added == Some(false) {
                continue;
            }
            // Resolve the entity to its CID the same way for every ingest path
            // (`from_multibase` for snapshot/CID forms, hash fallback for raw
            // journal forms) so dedup collapses snapshot⊕journal overlap.
            let e = parse_cid_or_hash(&d.e);
            let decoded = parse_edn_scalar(&d.v_edn);
            let key = Self::dedup_key(&e, &d.a, &decoded);
            if !self.seen.insert(key) {
                continue; // delta/replay already applied this datom — idempotent
            }
            let datom = Datom::assert(e, d.a.clone(), Value::Text(decoded), self.tx.clone());
            self.arr.insert_datom(&datom);
            self.datomic_datoms.push(d.to_datomic(&self.tx)?);
            n += 1;
        }
        Ok(n)
    }

    /// P3 (ADR-2606013600 D5): hydrate by **traversing the canonical Prolly
    /// tree** rooted at `root` (an index root, e.g. EAVT) over a CID-verified
    /// block store — the **same `ProllyTree::scan_prefix` the server uses**, not a
    /// bespoke JSON snapshot. Each leaf value is a `StoredDatom` (`{e, a, v_edn,
    /// t, added}`), the identical record shape the JSON sync path decodes, so it
    /// flows through the same idempotent `apply_records` sink. Returns the number
    /// of datoms applied (post-dedup).
    pub fn hydrate_from_prolly(
        &mut self,
        root: &KotobaCid,
        store: &dyn BlockStore,
    ) -> Result<usize, String> {
        let entries = ProllyTree::scan_prefix(root, &[], store).map_err(|e| e.to_string())?;
        let mut records = Vec::with_capacity(entries.len());
        for (_key, value) in entries {
            let rec: ServerDatom = ciborium::from_reader(value.as_slice())
                .map_err(|e| format!("stored datom decode: {e}"))?;
            records.push(rec);
        }
        self.apply_records(&records)
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

    /// P2 cold-restart recovery: replay an **OPFS append-only journal** on top
    /// of the current (snapshot-hydrated) state. Each non-empty line is one
    /// `transact` batch in `[{e,a,v_edn}]` form. Returns the number of datoms
    /// actually applied (post-dedup), so a journal whose writes were already
    /// compacted into the snapshot replays to `0`. Blank lines are skipped; a
    /// malformed line aborts (the journal is append-only and should not corrupt).
    pub fn replay_journal(&mut self, journal_text: &str) -> Result<usize, String> {
        let mut applied = 0usize;
        for line in journal_text.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            applied += self.load_server_datoms(line)?;
        }
        Ok(applied)
    }

    /// Export the full current datom set as the server `[{e,a,v_edn}]` JSON
    /// shape, so the caller can persist post-write state (seed + local writes)
    /// to IndexedDB and re-`load_server_datoms` it on the next cold start.
    ///
    /// The entity is emitted as `cid.to_multibase()` — a **stable, re-parseable**
    /// identity (`parse_cid_or_hash` round-trips it via `from_multibase`), so a
    /// snapshot reload lands on the same entity CID as the original write and the
    /// content-addressed dedup key matches. Datoms are sorted (entity, attr,
    /// value) so the snapshot bytes — and therefore `snapshot_cid()` — are
    /// deterministic for a given state.
    pub fn export_datoms_json(&self) -> String {
        let mut rows: Vec<(String, String, String)> = self
            .arr
            .datoms(&self.tx)
            .iter()
            .map(|d| {
                let v_edn = match &d.v {
                    Value::Text(s) => serde_json::to_string(s).unwrap_or_else(|_| "\"\"".into()),
                    Value::Integer(n) => n.to_string(),
                    Value::Float(f) => f.to_string(),
                    Value::Cid(c) => serde_json::to_string(&format!("{c:?}")).unwrap(),
                    other => serde_json::to_string(&format!("{other:?}")).unwrap(),
                };
                (d.e.to_multibase(), d.a.clone(), v_edn)
            })
            .collect();
        rows.sort();
        let mut out = String::from("[");
        for (i, (e, a, v_edn)) in rows.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            let e_json = serde_json::to_string(e).unwrap();
            let a_json = serde_json::to_string(a).unwrap();
            let v_edn_json = serde_json::to_string(v_edn).unwrap();
            out.push_str(&format!(
                "{{\"e\":{e_json},\"a\":{a_json},\"v_edn\":{v_edn_json},\"added\":true}}"
            ));
        }
        out.push(']');
        out
    }

    /// Content address of the current snapshot — `CIDv1(blake3(snapshot bytes))`
    /// multibase. Deterministic for a given state (export is sorted), so the JS
    /// glue can store it as the IndexedDB snapshot key / sync cursor and skip a
    /// re-persist when the head is unchanged.
    pub fn snapshot_cid(&self) -> String {
        KotobaCid::from_bytes(self.export_datoms_json().as_bytes()).to_multibase()
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
        cache: BlockCache,
    }

    #[wasm_bindgen]
    impl KotobaNode {
        #[wasm_bindgen(constructor)]
        pub fn new() -> KotobaNode {
            KotobaNode {
                inner: Node::new(),
                cache: BlockCache::new(),
            }
        }

        /// P3: ingest one content-addressed Prolly block (pulled from a peer /
        /// IPFS gateway, or restored from `IdbBlockStore`). **CID-verified** —
        /// rejects a block whose bytes don't hash to `cid`. Trustless replication.
        #[wasm_bindgen(js_name = ingestBlock)]
        pub fn ingest_block(&self, cid: &str, bytes: &[u8]) -> Result<(), JsValue> {
            self.cache
                .insert_verified_multibase(cid, bytes)
                .map_err(|e| JsValue::from_str(&e))
        }

        /// P3: hydrate by traversing the canonical Prolly tree at index `root`
        /// (multibase CID) over the CID-verified block cache — the same
        /// `scan_prefix` read path as the server. Returns datoms applied.
        #[wasm_bindgen(js_name = hydrateFromProlly)]
        pub fn hydrate_from_prolly(&mut self, root: &str) -> Result<usize, JsValue> {
            let root_cid = KotobaCid::from_multibase(root)
                .ok_or_else(|| JsValue::from_str(&format!("bad root CID: {root}")))?;
            self.inner
                .hydrate_from_prolly(&root_cid, &self.cache)
                .map_err(|e| JsValue::from_str(&e))
        }

        /// Number of CID-verified blocks held in the local cache (status/debug).
        #[wasm_bindgen(js_name = blockCount)]
        pub fn block_count(&self) -> usize {
            self.cache.len()
        }

        /// P3 block-sync driver: multibase CIDs reachable from `root` that are
        /// not yet local. The JS loop pulls these via `block.get`, re-`ingestBlock`s
        /// them (CID-verified), and repeats until empty, then `hydrateFromProlly`.
        #[wasm_bindgen(js_name = missingBlockCids)]
        pub fn missing_block_cids(&self, root: &str) -> Result<Vec<String>, JsValue> {
            let root_cid = KotobaCid::from_multibase(root)
                .ok_or_else(|| JsValue::from_str(&format!("bad root CID: {root}")))?;
            Ok(self
                .cache
                .missing_cids(&root_cid)
                .iter()
                .map(|c| c.to_multibase())
                .collect())
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

        /// P1 alias of `exportDatoms` — the canonical, content-addressed snapshot
        /// the JS glue writes to IndexedDB.
        #[wasm_bindgen]
        pub fn snapshot(&self) -> String {
            self.inner.export_datoms_json()
        }

        /// P1 content address of the current snapshot (IndexedDB key / sync cursor).
        #[wasm_bindgen(js_name = snapshotCid)]
        pub fn snapshot_cid(&self) -> String {
            self.inner.snapshot_cid()
        }

        /// P2 replay an OPFS append-only tx journal (one `transact` batch per
        /// line) on top of the snapshot-hydrated state. Returns datoms applied.
        #[wasm_bindgen(js_name = replayJournal)]
        pub fn replay_journal(&mut self, journal_text: &str) -> Result<usize, JsValue> {
            self.inner
                .replay_journal(journal_text)
                .map_err(|e| JsValue::from_str(&e))
        }

        /// Number of distinct datoms held (post-dedup) — for `status`/debug.
        #[wasm_bindgen(js_name = datomCount)]
        pub fn datom_count(&self) -> usize {
            self.inner.datom_count()
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

    // ── P1: idempotent delta sync ──────────────────────────────────────────

    #[test]
    fn reloading_the_same_datoms_is_idempotent() {
        // A delta refresh re-sends datoms the node already holds. Without the
        // resolved-CID dedup the non-deduping kqe vectors would multiply and
        // searchActors would return duplicate/garbled profiles.
        let json = r#"[
          {"e":"bafyA","a":":yoro.profile/did","v_edn":"\"did:web:etzhayyim.com:actor:tsumugi\"","added":true},
          {"e":"bafyA","a":":yoro.profile/displayName","v_edn":"\"紡ぎ Tsumugi\"","added":true}
        ]"#;
        let mut n = Node::new();
        assert_eq!(n.load_server_datoms(json).unwrap(), 2, "first load applies both");
        assert_eq!(n.load_server_datoms(json).unwrap(), 0, "re-load is a no-op");
        assert_eq!(n.datom_count(), 2);
        let hits = n.search_actors("tsumugi");
        assert_eq!(hits.len(), 1, "exactly one profile, not duplicated");
        assert_eq!(hits[0].display_name, "紡ぎ Tsumugi");
    }

    #[test]
    fn snapshot_cid_is_deterministic_and_state_sensitive() {
        let mut a = Node::new();
        a.assert_text("x", ":yoro.profile/handle", "alpha");
        a.assert_text("y", ":yoro.profile/handle", "beta");
        // Same datoms in the opposite insert order → identical sorted snapshot.
        let mut b = Node::new();
        b.assert_text("y", ":yoro.profile/handle", "beta");
        b.assert_text("x", ":yoro.profile/handle", "alpha");
        assert_eq!(a.snapshot_cid(), b.snapshot_cid(), "order-independent CID");
        // A different state must produce a different CID.
        b.assert_text("z", ":yoro.profile/handle", "gamma");
        assert_ne!(a.snapshot_cid(), b.snapshot_cid());
    }

    // ── P2: OPFS journal replay survives a cold restart ────────────────────

    #[test]
    fn cold_restart_replays_journal_on_top_of_snapshot_without_dupes() {
        // Simulate the running node: seed (becomes the IndexedDB snapshot) + a
        // local write that is appended to the OPFS journal but NOT yet compacted.
        let mut live = Node::new();
        live.load_server_datoms(
            r#"[{"e":"bafySeed","a":":yoro.profile/did","v_edn":"\"did:web:etzhayyim.com:actor:tsumugi\"","added":true}]"#,
        )
        .unwrap();
        let snapshot = live.export_datoms_json(); // → IndexedDB
        let journal = String::from(
            r#"[{"e":"w1","a":":yoro.profile/did","v_edn":"\"did:web:etzhayyim.com:actor:newcomer\""},{"e":"w1","a":":yoro.profile/displayName","v_edn":"\"新人 Newcomer\""}]"#,
        ); // → OPFS append-only journal (one line per transact)

        // Cold restart: fresh node ← snapshot, then replay the journal.
        let mut restarted = Node::new();
        restarted.load_server_datoms(&snapshot).unwrap();
        let applied = restarted.replay_journal(&journal).unwrap();
        assert_eq!(applied, 2, "the un-compacted write is recovered");
        assert_eq!(restarted.search_actors("tsumugi").len(), 1);
        assert_eq!(restarted.search_actors("newcomer").len(), 1);

        // Replaying the SAME journal again (crash before journal truncation)
        // must not duplicate — snapshot⊕journal overlap collapses by CID.
        assert_eq!(restarted.replay_journal(&journal).unwrap(), 0);
        assert_eq!(restarted.search_actors("newcomer").len(), 1);

        // And the post-write snapshot already contains the write, so replaying
        // the journal over the *compacted* snapshot is a clean no-op.
        let compacted = restarted.export_datoms_json();
        let mut next = Node::new();
        next.load_server_datoms(&compacted).unwrap();
        assert_eq!(next.replay_journal(&journal).unwrap(), 0, "compacted → journal empty");
        assert_eq!(next.search_actors("newcomer").len(), 1);
    }

    #[test]
    fn replay_journal_skips_blank_lines() {
        let mut n = Node::new();
        let journal = "\n  \n[{\"e\":\"e1\",\"a\":\":yoro.profile/handle\",\"v_edn\":\"\\\"solo\\\"\"}]\n\n";
        assert_eq!(n.replay_journal(journal).unwrap(), 1);
        assert_eq!(n.datom_count(), 1);
    }

    // ── P3: CID-verified Prolly traversal (same read path as the server) ────

    /// The browser reconstructs profiles by traversing the canonical Prolly tree
    /// over a CID-verified block cache — `ProllyTree::scan_prefix`, the same
    /// primitive the server uses — not a JSON snapshot.
    #[test]
    fn hydrate_from_prolly_reads_datoms_over_cid_verified_blocks() {
        use kotoba_kqe::{Datom as KqeDatom, Value as KqeValue};

        // Leaf value shape == kotoba_datomic StoredDatom == ServerDatom.
        #[derive(serde::Serialize)]
        struct StoredDatom {
            e: String,
            a: String,
            v_edn: String,
            t: String,
            added: bool,
        }

        let tx = KotobaCid::from_bytes(b"tx");
        let did = "did:web:etzhayyim.com:actor:tsumugi";
        let ecid = KotobaCid::from_bytes(did.as_bytes());
        let mk = |a: &str, v: &str| -> (Vec<u8>, Vec<u8>) {
            // key = canonical EAVT key (keycodec); value = ciborium StoredDatom.
            let key = KqeDatom::assert(
                ecid.clone(),
                a.to_string(),
                KqeValue::Text(v.to_string()),
                tx.clone(),
            )
            .eavt_key();
            let stored = StoredDatom {
                e: ecid.to_multibase(),
                a: a.to_string(),
                v_edn: serde_json::to_string(v).unwrap(), // EDN string form
                t: tx.to_multibase(),
                added: true,
            };
            let mut val = Vec::new();
            ciborium::into_writer(&stored, &mut val).unwrap();
            (key, val)
        };
        let entries = vec![
            mk(":yoro.profile/did", did),
            mk(":yoro.profile/handle", "etzhayyim.com.actor.tsumugi"),
            mk(":yoro.profile/displayName", "紡ぎ Tsumugi"),
        ];

        // Server builds the canonical Prolly tree.
        let server = BlockCache::new();
        let root = ProllyTree::build_tree(entries, &server).unwrap();

        // Browser pulls every block and CID-verifies it on arrival.
        let browser = BlockCache::new();
        for cid in ProllyTree::walk_all_cids(&root, &server).unwrap() {
            let bytes = server.get(&cid).unwrap().unwrap();
            browser.insert_verified(&cid, &bytes).expect("block CID verifies");
        }
        assert!(browser.len() >= 1);

        // Hydrate purely by traversing the Prolly tree over the verified cache.
        let mut node = Node::new();
        let applied = node.hydrate_from_prolly(&root, &browser).unwrap();
        assert_eq!(applied, 3, "all three datoms reconstructed via scan_prefix");
        let hits = node.search_actors("tsumugi");
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].display_name, "紡ぎ Tsumugi");

        // Re-hydrating the same root is idempotent (dedup).
        assert_eq!(node.hydrate_from_prolly(&root, &browser).unwrap(), 0);
        assert_eq!(node.search_actors("tsumugi").len(), 1);
    }

    /// The `missing_cids` BFS drives a block-sync loop that pulls a tree it has
    /// never seen, one frontier at a time, ending with a complete local tree —
    /// the same loop the Service Worker runs against `block.get`.
    #[test]
    fn missing_cids_drives_block_sync_to_completion() {
        use kotoba_kqe::{Datom as KqeDatom, Value as KqeValue};
        #[derive(serde::Serialize)]
        struct StoredDatom {
            e: String,
            a: String,
            v_edn: String,
            t: String,
            added: bool,
        }
        let tx = KotobaCid::from_bytes(b"tx");
        // Enough datoms (distinct entities) to force a multi-level tree.
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0..400)
            .map(|i| {
                let e = KotobaCid::from_bytes(format!("e{i}").as_bytes());
                let a = ":yoro.profile/handle";
                let v = format!("user{i}");
                let key =
                    KqeDatom::assert(e.clone(), a.to_string(), KqeValue::Text(v.clone()), tx.clone())
                        .eavt_key();
                let stored = StoredDatom {
                    e: e.to_multibase(),
                    a: a.to_string(),
                    v_edn: serde_json::to_string(&v).unwrap(),
                    t: tx.to_multibase(),
                    added: true,
                };
                let mut val = Vec::new();
                ciborium::into_writer(&stored, &mut val).unwrap();
                (key, val)
            })
            .collect();
        let server = BlockCache::new();
        let root = ProllyTree::build_tree(entries, &server).unwrap();

        // Browser starts empty; pull frontier-by-frontier via missing_cids.
        let browser = BlockCache::new();
        let mut rounds = 0;
        loop {
            let missing = browser.missing_cids(&root);
            if missing.is_empty() {
                break;
            }
            for cid in missing {
                let bytes = server.get(&cid).unwrap().expect("server has block");
                browser.insert_verified(&cid, &bytes).expect("CID verifies");
            }
            rounds += 1;
            assert!(rounds < 20, "block sync should converge quickly");
        }
        assert!(rounds >= 2, "a multi-level tree needs ≥2 pull rounds");

        let mut node = Node::new();
        let applied = node.hydrate_from_prolly(&root, &browser).unwrap();
        assert_eq!(applied, 400, "all datoms reconstructed after full block sync");
        assert_eq!(node.search_actors("user42").len(), 1);
    }

    /// Trustless replication: a block whose bytes don't hash to the claimed CID
    /// is rejected — a tampered peer can't poison the local cache.
    #[test]
    fn block_cache_rejects_tampered_block() {
        let cache = BlockCache::new();
        let good = b"hello kotoba block";
        let cid = KotobaCid::from_bytes(good);
        assert!(cache.insert_verified(&cid, good).is_ok());
        assert!(
            cache.insert_verified(&cid, b"tampered bytes").is_err(),
            "CID mismatch must be rejected"
        );
        assert_eq!(cache.len(), 1, "only the verified block is stored");
    }
}
