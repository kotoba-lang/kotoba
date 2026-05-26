use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use bytes::Bytes;
use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;

/// BlobRef — reference to a content-addressed blob
#[derive(Debug, Clone)]
pub struct BlobRef {
    pub cid:  KotobaCid,
    pub size: usize,
}

/// Vault — chunked binary blob store.
///
/// If built with `with_block_store()`, every `put()` is persisted to the
/// given `BlockStore`.  `get()` checks the in-memory cache first and falls
/// back to the block store on a miss, populating the cache on retrieval.
pub struct Vault {
    blobs: Arc<RwLock<HashMap<String, Bytes>>>,
    store: Option<Arc<dyn BlockStore + Send + Sync>>,
}

impl Vault {
    /// In-memory only — no persistence.
    pub fn new() -> Self {
        Self { blobs: Arc::new(RwLock::new(HashMap::new())), store: None }
    }

    /// Persistent — blobs are written to / read from the given block store.
    pub fn with_block_store(store: Arc<dyn BlockStore + Send + Sync>) -> Self {
        Self { blobs: Arc::new(RwLock::new(HashMap::new())), store: Some(store) }
    }

    /// Legacy sled-backed constructor — kept for migration compatibility.
    #[deprecated(note = "use with_block_store instead")]
    pub fn with_sled_tree(_tree: sled::Tree) -> Self {
        Self::new()
    }

    pub async fn put(&self, data: Bytes) -> BlobRef {
        let cid = KotobaCid::from_bytes(&data);
        let key = cid.to_multibase();
        let size = data.len();
        self.blobs.write().await.insert(key, data.clone());

        if let Some(store) = &self.store {
            store.put(&cid, &data).ok();
        }

        BlobRef { cid, size }
    }

    pub async fn get(&self, cid: &KotobaCid) -> Option<Bytes> {
        let key = cid.to_multibase();

        // fast path: in-memory cache
        if let Some(blob) = self.blobs.read().await.get(&key).cloned() {
            return Some(blob);
        }

        // fallback: block store
        if let Some(store) = &self.store {
            if let Ok(Some(bytes)) = store.get(cid) {
                self.blobs.write().await.insert(key, bytes.clone());
                return Some(bytes);
            }
        }

        None
    }

    pub async fn contains(&self, cid: &KotobaCid) -> bool {
        let key = cid.to_multibase();
        if self.blobs.read().await.contains_key(&key) {
            return true;
        }
        if let Some(store) = &self.store {
            return store.has(cid);
        }
        false
    }
}

impl Default for Vault {
    fn default() -> Self { Self::new() }
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::store::BlockStore;
    use std::collections::HashMap;
    use std::sync::{Arc, RwLock as StdRwLock};

    #[derive(Default)]
    struct MemStore(StdRwLock<HashMap<[u8; 36], Bytes>>);
    impl BlockStore for MemStore {
        fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
            self.0.write().unwrap().insert(cid.0, Bytes::copy_from_slice(data));
            Ok(())
        }
        fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
            Ok(self.0.read().unwrap().get(&cid.0).cloned())
        }
        fn has(&self, cid: &KotobaCid) -> bool {
            self.0.read().unwrap().contains_key(&cid.0)
        }
        fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
            self.0.write().unwrap().remove(&cid.0);
            Ok(())
        }
        fn pin(&self, _: &KotobaCid) {}
        fn unpin(&self, _: &KotobaCid) {}
        fn is_pinned(&self, _: &KotobaCid) -> bool { false }
    }

    #[tokio::test]
    async fn put_returns_blob_ref_with_correct_size() {
        let vault = Vault::new();
        let data = Bytes::from_static(b"size test payload");
        let blob_ref = vault.put(data.clone()).await;
        assert_eq!(blob_ref.size, data.len());
    }

    #[tokio::test]
    async fn put_then_get_returns_same_bytes() {
        let vault = Vault::new();
        let data = Bytes::from(vec![0xDE, 0xAD, 0xBE, 0xEF]);
        let blob_ref = vault.put(data.clone()).await;
        let retrieved = vault.get(&blob_ref.cid).await;
        assert_eq!(retrieved, Some(data));
    }

    #[tokio::test]
    async fn get_on_unknown_cid_returns_none() {
        let vault = Vault::new();
        let unknown_cid = KotobaCid::from_bytes(b"this was never stored");
        assert!(vault.get(&unknown_cid).await.is_none());
    }

    #[tokio::test]
    async fn contains_returns_true_after_put_false_before() {
        let vault = Vault::new();
        let data = Bytes::from_static(b"contains check");
        let cid = KotobaCid::from_bytes(&data);
        assert!(!vault.contains(&cid).await);
        vault.put(data).await;
        assert!(vault.contains(&cid).await);
    }

    #[tokio::test]
    async fn different_content_produces_different_cids() {
        let vault = Vault::new();
        let ref_a = vault.put(Bytes::from_static(b"content alpha")).await;
        let ref_b = vault.put(Bytes::from_static(b"content beta")).await;
        assert_ne!(ref_a.cid, ref_b.cid);
    }

    #[tokio::test]
    async fn block_store_vault_survives_cache_eviction() {
        let store = Arc::new(MemStore::default()) as Arc<dyn BlockStore + Send + Sync>;
        let vault = Vault::with_block_store(store.clone());

        let data = Bytes::from_static(b"persistent blob");
        let blob_ref = vault.put(data.clone()).await;

        // Fresh vault sharing the same block store (empty in-memory cache)
        let vault2 = Vault::with_block_store(store);
        let retrieved = vault2.get(&blob_ref.cid).await;
        assert_eq!(retrieved, Some(data));
    }
}
