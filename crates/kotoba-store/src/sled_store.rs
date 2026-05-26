use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use crate::block_store::StoreError;
use std::collections::HashSet;
use std::sync::{Arc, RwLock};

/// Sled-backed block store.  The 36-byte CID is used directly as the sled key.
/// Pins are kept in-memory (not persisted across restarts); agents re-pin on startup.
pub struct SledBlockStore {
    db:     sled::Db,
    /// Named tree used for block storage ("blocks" when opened via `from_db`).
    tree:   Option<sled::Tree>,
    pinned: Arc<RwLock<HashSet<[u8; 36]>>>,
}

impl SledBlockStore {
    pub fn open(path: impl AsRef<std::path::Path>) -> Result<Self, StoreError> {
        let db = sled::open(path)?;
        Ok(Self { db, tree: None, pinned: Arc::new(RwLock::new(HashSet::new())) })
    }

    pub fn temporary() -> Result<Self, StoreError> {
        let db = sled::Config::new().temporary(true).open()?;
        Ok(Self { db, tree: None, pinned: Arc::new(RwLock::new(HashSet::new())) })
    }

    /// Build from a shared sled::Db, using the "blocks" named tree.
    /// Allows server.rs to share one Sled DB across blocks / journal / vault.
    pub fn from_db(db: &sled::Db) -> sled::Result<Self> {
        let tree = db.open_tree("blocks")?;
        Ok(Self {
            db:     db.clone(),
            tree:   Some(tree),
            pinned: Arc::new(RwLock::new(HashSet::new())),
        })
    }

    /// Open a named tree within the same Sled DB.
    pub fn open_tree(&self, name: &str) -> sled::Result<sled::Tree> {
        self.db.open_tree(name)
    }

    #[inline]
    fn tree_insert(&self, key: &[u8], val: &[u8]) -> sled::Result<Option<sled::IVec>> {
        if let Some(t) = &self.tree { t.insert(key, val) } else { self.db.insert(key, val) }
    }
    #[inline]
    fn tree_get(&self, key: &[u8]) -> sled::Result<Option<sled::IVec>> {
        if let Some(t) = &self.tree { t.get(key) } else { self.db.get(key) }
    }
    #[inline]
    fn tree_contains(&self, key: &[u8]) -> sled::Result<bool> {
        if let Some(t) = &self.tree { t.contains_key(key) } else { self.db.contains_key(key) }
    }
    #[inline]
    fn tree_remove(&self, key: &[u8]) -> sled::Result<Option<sled::IVec>> {
        if let Some(t) = &self.tree { t.remove(key) } else { self.db.remove(key) }
    }
}

impl BlockStore for SledBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.tree_insert(&cid.0, data)
            .map(|_| ())
            .map_err(|e| anyhow::anyhow!("sled put: {e}"))
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        self.tree_get(&cid.0)
            .map(|opt| opt.map(|v| Bytes::copy_from_slice(&v)))
            .map_err(|e| anyhow::anyhow!("sled get: {e}"))
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.tree_contains(&cid.0).unwrap_or(false)
    }

    fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
        self.tree_remove(&cid.0)
            .map(|_| ())
            .map_err(|e| anyhow::anyhow!("sled delete: {e}"))
    }

    fn pin(&self, cid: &KotobaCid) {
        self.pinned.write().unwrap().insert(cid.0);
    }

    fn unpin(&self, cid: &KotobaCid) {
        self.pinned.write().unwrap().remove(&cid.0);
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.pinned.read().unwrap().contains(&cid.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::block_store::put_verified;

    #[test]
    fn put_and_get_roundtrip() {
        let store = SledBlockStore::temporary().unwrap();
        let data = b"hello kotoba block";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        let retrieved = store.get(&cid).unwrap().unwrap();
        assert_eq!(retrieved.as_ref(), data);
    }

    #[test]
    fn put_verified_rejects_mismatch() {
        let store = SledBlockStore::temporary().unwrap();
        let cid = KotobaCid::from_bytes(b"real data");
        let result = put_verified(&store, &cid, b"wrong data");
        assert!(result.is_err());
    }

    #[test]
    fn has_returns_false_for_missing() {
        let store = SledBlockStore::temporary().unwrap();
        let cid = KotobaCid::from_bytes(b"not stored");
        assert!(!store.has(&cid));
    }

    #[test]
    fn delete_removes_block() {
        let store = SledBlockStore::temporary().unwrap();
        let data = b"to be deleted";
        let cid = KotobaCid::from_bytes(data);
        store.put(&cid, data).unwrap();
        assert!(store.has(&cid));
        store.delete(&cid).unwrap();
        assert!(!store.has(&cid));
    }

    #[test]
    fn pin_protects_and_unpin_releases() {
        let store = SledBlockStore::temporary().unwrap();
        let cid = KotobaCid::from_bytes(b"pinned-block");
        assert!(!store.is_pinned(&cid));
        store.pin(&cid);
        assert!(store.is_pinned(&cid));
        store.unpin(&cid);
        assert!(!store.is_pinned(&cid));
    }
}
