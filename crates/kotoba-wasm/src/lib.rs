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
//! **Write (2026-06-02):** the node now also WRITES content-addressed in the
//! browser — `assert` builds a write-set, `commit()` materialises it into a
//! covering EAVT `ProllyTree` (root = CIDv1 dag-cbor **sha2-256**, byte-identical
//! hashing to the server), and the wasm `commitToIdb` flushes the captured blocks
//! + a rehydration snapshot to **IndexedDB** (`IdbBlockStore`) so the write
//! survives a page reload (`hydrateFromIdb`). The sync ProllyTree build runs over
//! an in-memory hot tier, then async-flushes to IndexedDB — the same hot/cold
//! split as the server's `TieredBlockStore`. No Kubo / IPNS, so the server's
//! DHT-resolve / cold-block stalls do not apply in-browser.
//!
//! What it does NOT yet do (subsequent phases in ADR-2606013600):
//!   - retractions + delta journal (commit is assert-only, full-snapshot);
//!   - `DistributedDatomReader` Prolly traversal hydrate (uses a flat snapshot);
//!   - delta sync / peer push of the local write-set back to a server graph;
//!   - P3: `BrowserComponentRuntime` (jco) for in-browser Pregel/UDF guests.
//!
//! The wider port is purely mechanical: apply the same per-target tokio gate
//! used by `kotoba-kqe` (drop the `net` feature on wasm) to `kotoba-kse`,
//! `kotoba-datomic`, `kotoba-graph`, `kotoba-crypto`, `kotoba-store` — the only
//! wasm blocker measured was tokio's `net` feature pulling `mio`.

use kotoba_core::cid::KotobaCid;
use kotoba_core::prolly::ProllyTree;
use kotoba_core::store::BlockStore;
use kotoba_kqe::{Arrangement, Datom, Value};
use std::collections::HashMap;
use std::sync::Mutex;

/// Sync in-memory block tier for ProllyTree commits in the browser node.
///
/// `ProllyTree::build_tree` is sync over `BlockStore`, but IndexedDB
/// (`IdbBlockStore`) is async — so we commit into this hot in-memory store
/// (capturing every block), then asynchronously flush the captured set to
/// IndexedDB for durability. This mirrors the server's `TieredBlockStore`
/// hot(memory)/cold split. `Mutex` keeps it `Send + Sync` as the trait requires.
#[derive(Default)]
pub struct MemBlocks {
    blocks: Mutex<HashMap<[u8; 36], Vec<u8>>>,
}

impl MemBlocks {
    pub fn new() -> Self {
        Self::default()
    }
    /// Every captured (cid, bytes) — the set to flush to IndexedDB after commit.
    pub fn entries(&self) -> Vec<(KotobaCid, Vec<u8>)> {
        self.blocks
            .lock()
            .unwrap()
            .iter()
            .map(|(k, v)| (KotobaCid(*k), v.clone()))
            .collect()
    }
    pub fn len(&self) -> usize {
        self.blocks.lock().unwrap().len()
    }
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }
}

impl BlockStore for MemBlocks {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.blocks.lock().unwrap().insert(cid.0, data.to_vec());
        Ok(())
    }
    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<bytes::Bytes>> {
        Ok(self
            .blocks
            .lock()
            .unwrap()
            .get(&cid.0)
            .map(|v| bytes::Bytes::copy_from_slice(v)))
    }
    fn has(&self, cid: &KotobaCid) -> bool {
        self.blocks.lock().unwrap().contains_key(&cid.0)
    }
}

/// One asserted fact in source form, retained so the node can (a) re-serialise a
/// durable snapshot and (b) rebuild the covering EAVT ProllyTree on commit.
#[derive(Clone, Debug, serde::Serialize, serde::Deserialize)]
struct Written {
    e: String,
    a: String,
    v: String,
}

/// A browser-local kotoba node: an in-memory Datom read arrangement PLUS a
/// content-addressed write path (commit → ProllyTree → IndexedDB).
///
/// Reads run over `arr` (the same kqe engine as `datomic.datoms`). Writes are
/// appended to `written`, materialised into a covering EAVT `ProllyTree` by
/// `commit()` (yielding an IPFS-compatible sha2-256 root CID, identical hashing
/// to the server), and persisted to IndexedDB by the wasm `commitToIdb`.
pub struct Node {
    arr: Arrangement,
    tx: KotobaCid,
    written: Vec<Written>,
    blocks: MemBlocks,
    root: Option<KotobaCid>,
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
            written: Vec::new(),
            blocks: MemBlocks::new(),
            root: None,
        }
    }

    /// Assert one Datom. `entity` is content-hashed to a CID (real ingest keys
    /// profiles by DID → CID); the value is stored as text. The fact is also
    /// retained in source form so `commit()` / the durable snapshot can rebuild it.
    pub fn assert_text(&mut self, entity: &str, attr: &str, value: &str) {
        let d = Datom::assert(
            KotobaCid::from_bytes(entity.as_bytes()),
            attr.to_string(),
            Value::Text(value.to_string()),
            self.tx.clone(),
        );
        self.arr.insert_datom(&d);
        self.written.push(Written {
            e: entity.to_string(),
            a: attr.to_string(),
            v: value.to_string(),
        });
    }

    /// Materialise the current write-set into a covering EAVT `ProllyTree`,
    /// writing every node into the hot `blocks` tier, and return the root CID
    /// (CIDv1 dag-cbor **sha2-256**, IPFS-compatible — same hashing as the
    /// server). This is the in-browser content-addressed WRITE. Call
    /// `commitToIdb` (wasm) to make the captured blocks durable in IndexedDB.
    pub fn commit(&mut self) -> KotobaCid {
        let mut entries: Vec<(Vec<u8>, Vec<u8>)> = Vec::with_capacity(self.written.len());
        for w in &self.written {
            // EAVT key: entity-CID(36) | 0x00 | attr | 0x00 | value — sorted set.
            let e_cid = KotobaCid::from_bytes(w.e.as_bytes());
            let mut key = e_cid.0.to_vec();
            key.push(0);
            key.extend_from_slice(w.a.as_bytes());
            key.push(0);
            key.extend_from_slice(w.v.as_bytes());
            let mut val = Vec::new();
            ciborium::into_writer(w, &mut val).expect("cbor datom");
            entries.push((key, val));
        }
        let root = ProllyTree::build_tree(entries, &self.blocks).expect("build_tree");
        self.root = Some(root.clone());
        root
    }

    /// The committed root CID (multibase), or `None` before the first `commit()`.
    pub fn root_multibase(&self) -> Option<String> {
        self.root.as_ref().map(KotobaCid::to_multibase)
    }

    /// A durable snapshot of the write-set in the SAME JSON shape that
    /// `load_server_datoms` / `ai.gftd.apps.kotoba.datomic.datoms` use, so a
    /// reload (or a peer) can rehydrate via the existing read path.
    pub fn export_snapshot_json(&self) -> String {
        let arr: Vec<serde_json::Value> = self
            .written
            .iter()
            .map(|w| {
                serde_json::json!({
                    "e": w.e,
                    "a": w.a,
                    // v_edn = EDN-quoted string; parse_edn_scalar unwraps it.
                    "v_edn": serde_json::Value::String(w.v.clone()).to_string(),
                    "added": true,
                })
            })
            .collect();
        serde_json::Value::Array(arr).to_string()
    }

    /// Number of facts written this session (pre/post commit).
    pub fn written_len(&self) -> usize {
        self.written.len()
    }

    /// Write a fact whose VALUE is encrypted client-side under the agent's vault
    /// key (`signal:v1:<ct>`). The committed ProllyTree block + IndexedDB hold
    /// only ciphertext — zero-knowledge field storage in the browser.
    pub fn assert_encrypted(
        &mut self,
        crypto: &WriteCrypto,
        entity: &str,
        attr: &str,
        plaintext: &str,
    ) -> Result<(), String> {
        let envelope = crypto.encrypt(plaintext)?;
        self.assert_text(entity, attr, &envelope);
        Ok(())
    }

    /// `commit()` and Ed25519-sign the resulting root CID → `(root, did, sig)`.
    /// Proves authorship of the write set client-side (no server trust needed).
    pub fn commit_signed(&mut self, crypto: &WriteCrypto) -> (KotobaCid, String, String) {
        let root = self.commit();
        let sig = crypto.sign_hex(&root.0);
        (root, crypto.did(), sig)
    }

    /// Hydrate the arrangement from the exact JSON a remote kotoba
    /// `ai.gftd.apps.kotoba.datomic.datoms` returns: `[{e, a, v_edn, ...}]`.
    ///
    /// This is the P1 sync path (ADR-2606013600 D5): a one-time / delta block
    /// pull from a peer is decoded into Datoms and loaded into the kqe read
    /// engine — **without** the native `DistributedDatomReader` / kotoba-ipfs
    /// IPNS stack, which the browser node deliberately does not carry. The
    /// only added value-scalars are EDN strings (`"..."`) and keywords (`:kw`).
    pub fn load_server_datoms(&mut self, json: &str) -> Result<usize, String> {
        let arr: Vec<serde_json::Value> =
            serde_json::from_str(json).map_err(|e| e.to_string())?;
        let mut n = 0usize;
        for d in &arr {
            // Skip retractions if the server marks them.
            if d.get("added").and_then(|b| b.as_bool()) == Some(false) {
                continue;
            }
            let (Some(e), Some(a), Some(v_edn)) = (
                d.get("e").and_then(|x| x.as_str()),
                d.get("a").and_then(|x| x.as_str()),
                d.get("v_edn").and_then(|x| x.as_str()),
            ) else {
                continue;
            };
            // Group by the server's content-addressed entity string; the read
            // engine only needs a stable per-entity key, so hashing the `e`
            // multibase string is sufficient for the browser arrangement.
            let datom = Datom::assert(
                KotobaCid::from_bytes(e.as_bytes()),
                a.to_string(),
                Value::Text(parse_edn_scalar(v_edn)),
                self.tx.clone(),
            );
            self.arr.insert_datom(&datom);
            n += 1;
        }
        Ok(n)
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

/// Client-side sovereign crypto for the browser node — the same model as
/// `kotoba-kse::SovereignCrypto`/`AgentIdentity`, but self-contained and
/// wasm32-clean (no Journal/Vault/tokio deps). The agent holds an Ed25519
/// identity (signs commits → authorship) and a 32-byte symmetric vault key
/// (AES-256-GCM field encryption → the persisted ProllyTree/IndexedDB blocks
/// hold ciphertext, never plaintext). Entropy comes from `getrandom`'s `js`
/// backend (`crypto.getRandomValues`) in the browser. HPKE/X25519 key-wrap can
/// layer on top later; the symmetric vault key is the core SovereignCrypto unit.
pub struct WriteCrypto {
    signing_key: ed25519_dalek::SigningKey,
    vault_key: [u8; 32],
}

/// Field-encryption envelope prefix (mirrors the repo's `signal:v1:` convention).
const ENVELOPE_PREFIX: &str = "signal:v1:";

impl WriteCrypto {
    /// Generate a fresh sovereign identity + vault key (browser entropy on wasm).
    pub fn generate() -> Self {
        let mut seed = [0u8; 32];
        rand_core::RngCore::fill_bytes(&mut rand_core::OsRng, &mut seed);
        Self::from_seed(&seed)
    }

    /// Deterministic identity from a 32-byte seed (stable DID across reloads).
    pub fn from_seed(seed: &[u8; 32]) -> Self {
        let signing_key = ed25519_dalek::SigningKey::from_bytes(seed);
        // Vault key = SHA-256(seed || "kotoba-vault") — domain-separated from the
        // signing seed so the AES key is not the Ed25519 secret itself.
        use sha2::{Digest, Sha256};
        let mut h = Sha256::new();
        h.update(seed);
        h.update(b"kotoba-vault");
        let vault_key: [u8; 32] = h.finalize().into();
        Self {
            signing_key,
            vault_key,
        }
    }

    /// `did:key`-style identifier from the Ed25519 public key (hex form).
    pub fn did(&self) -> String {
        let vk = ed25519_dalek::VerifyingKey::from(&self.signing_key);
        format!("did:key:z{}", hex::encode(vk.to_bytes()))
    }

    /// Ed25519-sign arbitrary bytes (e.g. a commit root CID) → hex signature.
    pub fn sign_hex(&self, msg: &[u8]) -> String {
        use ed25519_dalek::Signer;
        hex::encode(self.signing_key.sign(msg).to_bytes())
    }

    /// Encrypt plaintext under the vault key → `signal:v1:<hex(nonce||ct)>`.
    /// The server/IndexedDB only ever sees this ciphertext.
    pub fn encrypt(&self, plaintext: &str) -> Result<String, String> {
        use aes_gcm::aead::{Aead, KeyInit};
        use aes_gcm::{Aes256Gcm, Nonce};
        let cipher = Aes256Gcm::new_from_slice(&self.vault_key).map_err(|e| e.to_string())?;
        let mut nonce_bytes = [0u8; 12];
        rand_core::RngCore::fill_bytes(&mut rand_core::OsRng, &mut nonce_bytes);
        let ct = cipher
            .encrypt(Nonce::from_slice(&nonce_bytes), plaintext.as_bytes())
            .map_err(|e| e.to_string())?;
        let mut blob = nonce_bytes.to_vec();
        blob.extend_from_slice(&ct);
        Ok(format!("{ENVELOPE_PREFIX}{}", hex::encode(blob)))
    }

    /// Decrypt a `signal:v1:` envelope back to plaintext.
    pub fn decrypt(&self, envelope: &str) -> Result<String, String> {
        use aes_gcm::aead::{Aead, KeyInit};
        use aes_gcm::{Aes256Gcm, Nonce};
        let hexpart = envelope
            .strip_prefix(ENVELOPE_PREFIX)
            .ok_or_else(|| "not a signal:v1: envelope".to_string())?;
        let blob = hex::decode(hexpart).map_err(|e| e.to_string())?;
        if blob.len() < 12 {
            return Err("envelope too short".into());
        }
        let (nonce_bytes, ct) = blob.split_at(12);
        let cipher = Aes256Gcm::new_from_slice(&self.vault_key).map_err(|e| e.to_string())?;
        let pt = cipher
            .decrypt(Nonce::from_slice(nonce_bytes), ct)
            .map_err(|e| e.to_string())?;
        String::from_utf8(pt).map_err(|e| e.to_string())
    }
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
// `/xrpc/ai.gftd.apps.kotoba.datomic.*` to these methods (ADR-2606013600 D3),
// keeping `@etzhayyim/yoro-rw-free` unchanged.
#[cfg(target_arch = "wasm32")]
mod wasm {
    use super::*;
    use kotoba_core::async_store::AsyncBlockStore;
    use kotoba_store_web::IdbBlockStore;
    use wasm_bindgen::prelude::*;

    #[wasm_bindgen]
    pub struct KotobaNode {
        inner: Node,
        crypto: Option<WriteCrypto>,
    }

    #[wasm_bindgen]
    impl KotobaNode {
        #[wasm_bindgen(constructor)]
        pub fn new() -> KotobaNode {
            KotobaNode {
                inner: Node::new(),
                crypto: None,
            }
        }

        /// Attach a sovereign identity from a 32-byte hex seed (stable DID across
        /// reloads). Enables `assertEncrypted` / `commitSigned` / `decrypt`.
        /// Returns the agent DID.
        #[wasm_bindgen(js_name = useIdentity)]
        pub fn use_identity(&mut self, seed_hex: &str) -> Result<String, JsValue> {
            let bytes = hex::decode(seed_hex.trim())
                .map_err(|e| JsValue::from_str(&format!("seed hex: {e}")))?;
            let seed: [u8; 32] = bytes
                .try_into()
                .map_err(|_| JsValue::from_str("seed must be 32 bytes (64 hex chars)"))?;
            let c = WriteCrypto::from_seed(&seed);
            let did = c.did();
            self.crypto = Some(c);
            Ok(did)
        }

        /// Generate a fresh random sovereign identity (browser entropy). Returns DID.
        #[wasm_bindgen(js_name = generateIdentity)]
        pub fn generate_identity(&mut self) -> String {
            let c = WriteCrypto::generate();
            let did = c.did();
            self.crypto = Some(c);
            did
        }

        /// Write a fact whose VALUE is encrypted client-side (`signal:v1:`).
        /// Requires an identity (`useIdentity`/`generateIdentity`).
        #[wasm_bindgen(js_name = assertEncrypted)]
        pub fn assert_encrypted(
            &mut self,
            entity: &str,
            attr: &str,
            plaintext: &str,
        ) -> Result<(), JsValue> {
            let c = self
                .crypto
                .as_ref()
                .ok_or_else(|| JsValue::from_str("no identity — call useIdentity first"))?;
            self.inner
                .assert_encrypted(c, entity, attr, plaintext)
                .map_err(|e| JsValue::from_str(&e))
        }

        /// Decrypt a `signal:v1:` envelope with the agent's vault key.
        pub fn decrypt(&self, envelope: &str) -> Result<String, JsValue> {
            let c = self
                .crypto
                .as_ref()
                .ok_or_else(|| JsValue::from_str("no identity"))?;
            c.decrypt(envelope).map_err(|e| JsValue::from_str(&e))
        }

        /// `commit()` + Ed25519-sign the root → JSON `{ root, did, sig }`.
        #[wasm_bindgen(js_name = commitSigned)]
        pub fn commit_signed(&mut self) -> Result<String, JsValue> {
            let c = self
                .crypto
                .as_ref()
                .ok_or_else(|| JsValue::from_str("no identity — call useIdentity first"))?;
            let (root, did, sig) = self.inner.commit_signed(c);
            serde_json::to_string(&serde_json::json!({
                "root": root.to_multibase(), "did": did, "sig": sig,
            }))
            .map_err(|e| JsValue::from_str(&e.to_string()))
        }

        /// Write one fact (entity, attr, value). In-memory read engine + the
        /// write-set behind `commit`. (was the read-only PoC `assert`.)
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

        /// `searchActors(q)` → JSON `{ actors: [...] }` (same shape as the XRPC).
        #[wasm_bindgen(js_name = searchActors)]
        pub fn search_actors(&self, q: &str) -> Result<String, JsValue> {
            let actors = self.inner.search_actors(q);
            serde_json::to_string(&serde_json::json!({ "actors": actors }))
                .map_err(|e| JsValue::from_str(&e.to_string()))
        }

        /// Content-addressed WRITE: materialise the write-set into a covering
        /// EAVT ProllyTree (in the hot in-memory tier) and return the root CID
        /// (CIDv1 dag-cbor sha2-256). Pure-compute, no persistence yet.
        pub fn commit(&mut self) -> String {
            self.inner.commit().to_multibase()
        }

        /// Durable WRITE: `commit()` then flush every captured ProllyTree block
        /// to IndexedDB and store a rehydration snapshot. Returns JSON
        /// `{ root, snapshot, blocks }`. After this, the write survives a page
        /// reload (rehydrate with `hydrateFromIdb(snapshot)`).
        #[wasm_bindgen(js_name = commitToIdb)]
        pub async fn commit_to_idb(&mut self) -> Result<String, JsValue> {
            let root = self.inner.commit();
            let idb = IdbBlockStore::open(None)
                .await
                .map_err(|e| JsValue::from_str(&format!("idb open: {e}")))?;
            // Flush the commit's blocks to the durable IndexedDB tier.
            let entries = self.inner.blocks.entries();
            let block_n = entries.len();
            for (cid, data) in &entries {
                idb.put_async(cid, data)
                    .await
                    .map_err(|e| JsValue::from_str(&format!("idb put: {e}")))?;
                idb.pin_async(cid).await;
            }
            // Store the rehydration snapshot (datomic.datoms JSON shape).
            let snap = self.inner.export_snapshot_json();
            let snap_cid = KotobaCid::from_bytes(snap.as_bytes());
            idb.put_async(&snap_cid, snap.as_bytes())
                .await
                .map_err(|e| JsValue::from_str(&format!("idb put snapshot: {e}")))?;
            idb.pin_async(&snap_cid).await;
            serde_json::to_string(&serde_json::json!({
                "root": root.to_multibase(),
                "snapshot": snap_cid.to_multibase(),
                "blocks": block_n,
            }))
            .map_err(|e| JsValue::from_str(&e.to_string()))
        }

        /// Rehydrate the read engine from a durable IndexedDB snapshot written by
        /// `commitToIdb` (survives page reload). Returns the datom count loaded.
        #[wasm_bindgen(js_name = hydrateFromIdb)]
        pub async fn hydrate_from_idb(&mut self, snapshot_cid: &str) -> Result<usize, JsValue> {
            let cid = KotobaCid::from_multibase(snapshot_cid)
                .ok_or_else(|| JsValue::from_str("invalid snapshot CID"))?;
            let idb = IdbBlockStore::open(None)
                .await
                .map_err(|e| JsValue::from_str(&format!("idb open: {e}")))?;
            let bytes = idb
                .get_async(&cid)
                .await
                .map_err(|e| JsValue::from_str(&format!("idb get: {e}")))?
                .ok_or_else(|| JsValue::from_str("snapshot not found in IndexedDB"))?;
            let json = String::from_utf8(bytes.to_vec())
                .map_err(|e| JsValue::from_str(&format!("snapshot utf8: {e}")))?;
            self.inner
                .load_server_datoms(&json)
                .map_err(|e| JsValue::from_str(&e))
        }

        /// The committed root CID (multibase), or empty string before `commit()`.
        #[wasm_bindgen(js_name = rootCid)]
        pub fn root_cid(&self) -> String {
            self.inner.root_multibase().unwrap_or_default()
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

    #[test]
    fn write_commit_yields_ipfs_sha256_root_and_is_deterministic() {
        let mut n = Node::new();
        n.assert_text("did:web:x:actor:a", ":yoro.profile/did", "did:web:x:actor:a");
        n.assert_text("did:web:x:actor:a", ":yoro.profile/handle", "x.actor.a");
        assert_eq!(n.written_len(), 2);

        let root = n.commit();
        // Root is the canonical IPFS-compatible CIDv1 dag-cbor sha2-256 form.
        assert!(root.is_ipfs_compatible(), "commit root must be sha2-256 CIDv1");
        assert!(!n.blocks.is_empty(), "commit must capture ProllyTree blocks");
        assert_eq!(n.root_multibase().as_deref(), Some(root.to_multibase().as_str()));

        // Determinism: same write-set → same root (content-addressed).
        let mut n2 = Node::new();
        n2.assert_text("did:web:x:actor:a", ":yoro.profile/did", "did:web:x:actor:a");
        n2.assert_text("did:web:x:actor:a", ":yoro.profile/handle", "x.actor.a");
        assert_eq!(n2.commit(), root, "same facts must commit to the same root CID");
    }

    #[test]
    fn write_snapshot_roundtrips_through_read_engine() {
        // Write → snapshot (durable form) → rehydrate into a fresh node's read
        // engine → search. This is the native equivalent of the browser
        // commitToIdb → reload → hydrateFromIdb cycle (minus IndexedDB I/O).
        let mut writer = Node::new();
        let did = "did:web:etzhayyim.com:actor:tsumugi";
        writer.assert_text(did, ":yoro.profile/did", did);
        writer.assert_text(did, ":yoro.profile/displayName", "紡ぎ Tsumugi");
        writer.commit();

        let snapshot = writer.export_snapshot_json();

        let mut reloaded = Node::new();
        let loaded = reloaded.load_server_datoms(&snapshot).unwrap();
        assert_eq!(loaded, 2, "snapshot must rehydrate all written facts");
        let hits = reloaded.search_actors("tsumugi");
        assert_eq!(hits.len(), 1);
        assert_eq!(hits[0].display_name, "紡ぎ Tsumugi");
    }

    #[test]
    fn crypto_encrypt_roundtrip_and_sign() {
        let c = WriteCrypto::from_seed(&[9u8; 32]);
        assert!(c.did().starts_with("did:key:z"));

        let env = c.encrypt("秘密 payload").unwrap();
        assert!(env.starts_with("signal:v1:"), "must be an encrypted envelope");
        assert!(!env.contains("秘密"), "plaintext must not appear in ciphertext");
        assert_eq!(c.decrypt(&env).unwrap(), "秘密 payload");

        // Deterministic identity; signature verifies against the public key.
        use ed25519_dalek::{Signature, Verifier, VerifyingKey};
        let c2 = WriteCrypto::from_seed(&[9u8; 32]);
        assert_eq!(c.did(), c2.did(), "same seed → same DID");
        let msg = b"commit-root-bytes";
        let sig_hex = c.sign_hex(msg);
        let vk = VerifyingKey::from(&c.signing_key);
        let sig = Signature::from_slice(&hex::decode(sig_hex).unwrap()).unwrap();
        assert!(vk.verify(msg, &sig).is_ok(), "signature must verify");
    }

    #[test]
    fn encrypted_write_stores_ciphertext_only_then_decrypts() {
        let crypto = WriteCrypto::from_seed(&[3u8; 32]);
        let mut n = Node::new();
        n.assert_encrypted(&crypto, "did:web:x:a", ":secret/note", "会員番号 12345")
            .unwrap();

        // The durable snapshot (what hits IndexedDB / a peer) holds ciphertext.
        let snap = n.export_snapshot_json();
        assert!(snap.contains("signal:v1:"), "snapshot must carry the envelope");
        assert!(!snap.contains("12345"), "plaintext must NOT be in the snapshot");

        // Signed content-addressed commit.
        let (root, did, sig) = n.commit_signed(&crypto);
        assert!(root.is_ipfs_compatible());
        assert!(did.starts_with("did:key:z") && sig.len() == 128);

        // The holder of the vault key recovers the plaintext from the stored value.
        let stored = n
            .datoms_by_attr_prefix(":secret/")
            .into_iter()
            .find_map(|d| match d.v {
                Value::Text(s) => Some(s),
                _ => None,
            })
            .unwrap();
        assert_eq!(crypto.decrypt(&stored).unwrap(), "会員番号 12345");
    }

    #[test]
    fn hydrate_from_server_datoms_json_then_search() {
        // Exact shape returned by ai.gftd.apps.kotoba.datomic.datoms (P1 sync).
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
}
