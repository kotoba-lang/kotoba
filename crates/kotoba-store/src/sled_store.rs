use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use crate::block_store::StoreError;

/// Sled-backed block store.  The 36-byte CID is used directly as the sled key.
pub struct SledBlockStore {
    db: sled::Db,
}

impl SledBlockStore {
    pub fn open(path: impl AsRef<std::path::Path>) -> Result<Self, StoreError> {
        let db = sled::open(path)?;
        Ok(Self { db })
    }

    pub fn temporary() -> Result<Self, StoreError> {
        let db = sled::Config::new().temporary(true).open()?;
        Ok(Self { db })
    }
}

impl BlockStore for SledBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.db.insert(&cid.0, data)
            .map(|_| ())
            .map_err(|e| anyhow::anyhow!("sled put: {e}"))
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        self.db.get(&cid.0)
            .map(|opt| opt.map(|v| Bytes::copy_from_slice(&v)))
            .map_err(|e| anyhow::anyhow!("sled get: {e}"))
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.db.contains_key(&cid.0).unwrap_or(false)
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
}
