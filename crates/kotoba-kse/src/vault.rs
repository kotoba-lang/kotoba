use crate::store::KseStore;
use kotoba_core::cid::KotobaCid;
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

/// Vault — chunked binary blob store (clean room, inspired by NATS Object Store)
/// Large tensors (FP8 weights, embeddings) stored here.
///
/// If built with `with_store()`, every `put()` is also persisted to the backing
/// `KseStore` (fire-and-forget).  `get()` checks the in-memory cache first and
/// falls back to the store on a miss, populating the cache on retrieval.
pub struct Vault {
    blobs: Arc<RwLock<HashMap<String, Bytes>>>,
    store: Option<Arc<KseStore>>,
}

impl Vault {
    /// In-memory only — no persistence.
    pub fn new() -> Self {
        Self { blobs: Arc::new(RwLock::new(HashMap::new())), store: None }
    }

    /// Persistent — blobs are also written to / read from `store`.
    pub fn with_store(store: Arc<KseStore>) -> Self {
        Self { blobs: Arc::new(RwLock::new(HashMap::new())), store: Some(store) }
    }

    pub async fn put(&self, data: Bytes) -> BlobRef {
        let cid = KotobaCid::from_bytes(&data);
        let key = cid.to_multibase();
        let size = data.len();
        self.blobs.write().await.insert(key.clone(), data.clone());

        if let Some(store) = &self.store {
            let store_clone = Arc::clone(store);
            tokio::spawn(async move {
                let _ = store_clone.put(&key, data).await;
            });
        }

        BlobRef { cid, size }
    }

    pub async fn get(&self, cid: &KotobaCid) -> Option<Bytes> {
        let key = cid.to_multibase();

        // fast path: in-memory cache
        if let Some(blob) = self.blobs.read().await.get(&key).cloned() {
            return Some(blob);
        }

        // fallback: object_store
        if let Some(store) = &self.store {
            if let Ok(data) = store.get(&key).await {
                self.blobs.write().await.insert(key, data.clone());
                return Some(data);
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
            return store.exists(&key).await;
        }
        false
    }
}

impl Default for Vault {
    fn default() -> Self { Self::new() }
}
