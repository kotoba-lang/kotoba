/// TieredBlockStore<H, C> — hot/cold tiered block store.
///
/// Writes land in hot immediately; a background task asynchronously copies to cold.
/// Hot misses fall through to cold and promote the block back to hot.
///
/// Design:
///   hot: small + fast (e.g., BudgetedBlockStore<SledBlockStore>)
///   cold: large + slow (e.g., IrohBlockStore)
///
/// The split ensures each node only keeps its working set in hot memory/disk while
/// the full dataset is addressed and replicated in cold (iroh/IPFS-pin style).
use std::sync::Arc;
use bytes::Bytes;
use anyhow::Result;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;

pub struct TieredBlockStore<H: BlockStore + 'static, C: BlockStore + 'static> {
    hot:  Arc<H>,
    cold: Arc<C>,
}

impl<H: BlockStore + 'static, C: BlockStore + 'static> TieredBlockStore<H, C> {
    pub fn new(hot: H, cold: C) -> Self {
        Self { hot: Arc::new(hot), cold: Arc::new(cold) }
    }

    /// Expose the hot tier for pin/evict operations (e.g., SyncWindow).
    pub fn hot(&self) -> &Arc<H> { &self.hot }

    /// Expose the cold tier for inspection or background management.
    pub fn cold(&self) -> &Arc<C> { &self.cold }
}

impl<H: BlockStore + 'static, C: BlockStore + 'static> BlockStore for TieredBlockStore<H, C> {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        // Synchronous hot write
        self.hot.put(cid, data)?;
        // Async cold write — fire-and-forget; failure is logged but non-fatal
        let cold  = Arc::clone(&self.cold);
        let cid2  = cid.clone();
        let buf   = data.to_vec();
        tokio::spawn(async move {
            if let Err(e) = cold.put(&cid2, &buf) {
                tracing::warn!(cid = %cid2, err = %e, "tiered cold-put failed");
            }
        });
        Ok(())
    }

    fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
        // Fast path: hot hit
        if let Some(b) = self.hot.get(cid)? {
            return Ok(Some(b));
        }
        // Cold fallback + promote to hot
        if let Some(b) = self.cold.get(cid)? {
            if let Err(e) = self.hot.put(cid, &b) {
                tracing::warn!(cid = %cid, err = %e, "tiered hot-promote failed");
            }
            return Ok(Some(b));
        }
        Ok(None)
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.hot.has(cid) || self.cold.has(cid)
    }

    fn delete(&self, cid: &KotobaCid) -> Result<()> {
        // Delete from both tiers; ignore cold error (it may not have the block)
        let _ = self.cold.delete(cid);
        self.hot.delete(cid)
    }

    fn pin(&self, cid: &KotobaCid) {
        self.hot.pin(cid);
    }

    fn unpin(&self, cid: &KotobaCid) {
        self.hot.unpin(cid);
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.hot.is_pinned(cid)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::memory_store::MemoryBlockStore;

    fn cid(s: &[u8]) -> KotobaCid { KotobaCid::from_bytes(s) }

    fn tiered() -> TieredBlockStore<MemoryBlockStore, MemoryBlockStore> {
        TieredBlockStore::new(MemoryBlockStore::new(), MemoryBlockStore::new())
    }

    #[tokio::test]
    async fn hot_hit_does_not_touch_cold() {
        let store = tiered();
        let data  = b"hello tiered";
        let c     = cid(data);
        store.hot.put(&c, data).unwrap();
        assert!(!store.cold.has(&c), "cold should be empty");
        let got = store.get(&c).unwrap();
        assert_eq!(got.unwrap().as_ref(), data);
    }

    #[tokio::test]
    async fn cold_miss_promotes_to_hot() {
        let store = tiered();
        let data  = b"cold only block";
        let c     = cid(data);
        store.cold.put(&c, data).unwrap();
        assert!(!store.hot.has(&c), "hot should be empty before promotion");

        let got = store.get(&c).unwrap().unwrap();
        assert_eq!(got.as_ref(), data);
        // After get, hot should have the block (promotion)
        assert!(store.hot.has(&c), "promoted to hot after cold hit");
    }

    #[tokio::test]
    async fn put_goes_to_hot_immediately() {
        let store = tiered();
        let data  = b"write test";
        let c     = cid(data);
        store.put(&c, data).unwrap();
        assert!(store.hot.has(&c), "hot must have block immediately after put");
        // Cold write is async — we don't assert it here
    }

    #[test]
    fn has_checks_both_tiers() {
        let store = tiered();
        let cold_data = b"cold only";
        let hot_data  = b"hot only";
        let cc = cid(cold_data);
        let ch = cid(hot_data);
        store.cold.put(&cc, cold_data).unwrap();
        store.hot.put(&ch, hot_data).unwrap();
        assert!(store.has(&cc));
        assert!(store.has(&ch));
        assert!(!store.has(&cid(b"missing")));
    }
}
