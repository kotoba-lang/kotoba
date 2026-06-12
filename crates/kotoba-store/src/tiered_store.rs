use anyhow::Result;
use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::collections::HashSet;
/// TieredBlockStore<H, C> — hot/cold tiered block store.
///
/// Writes land in hot immediately; a background task asynchronously copies to cold.
/// Hot misses fall through to cold and promote the block back to hot.
///
/// Design:
///   hot: small + fast (BudgetedBlockStore<MemoryBlockStore>)
///   cold: large + persistent (KuboBlockStore — Kubo/IPFS HTTP, single SHA2-256 CIDv1)
///
/// Each node keeps its working set in hot memory while the full dataset is
/// stored persistently in the Kubo cold tier.  Remote durability is handled by
/// IpfsPinClient (fire-and-forget pin to the local IPFS node after put).
use std::sync::Arc;

pub struct TieredBlockStore<H: BlockStore + 'static, C: BlockStore + 'static> {
    hot: Arc<H>,
    cold: Arc<C>,
}

impl<H: BlockStore + 'static, C: BlockStore + 'static> TieredBlockStore<H, C> {
    pub fn new(hot: H, cold: C) -> Self {
        Self {
            hot: Arc::new(hot),
            cold: Arc::new(cold),
        }
    }

    /// Expose the hot tier for pin/evict operations (e.g., SyncWindow).
    pub fn hot(&self) -> &Arc<H> {
        &self.hot
    }

    /// Expose the cold tier for inspection or background management.
    pub fn cold(&self) -> &Arc<C> {
        &self.cold
    }
}

impl<H: BlockStore + 'static, C: BlockStore + 'static> BlockStore for TieredBlockStore<H, C> {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        // Synchronous hot write
        self.hot.put(cid, data)?;
        // Async cold write — fire-and-forget when a tokio runtime is available.
        // Falls back to a synchronous write (used in tests and bench contexts).
        let cold = Arc::clone(&self.cold);
        let cid2 = cid.clone();
        let buf = data.to_vec();
        if let Ok(handle) = tokio::runtime::Handle::try_current() {
            handle.spawn(async move {
                if let Err(e) = cold.put(&cid2, &buf) {
                    tracing::warn!(cid = %cid2, err = %e, "tiered cold-put failed");
                }
            });
        } else {
            // No async runtime (e.g. benchmark or sync test context): write inline
            if let Err(e) = cold.put(&cid2, &buf) {
                tracing::warn!(cid = %cid2, err = %e, "tiered cold-put (sync) failed");
            }
        }
        Ok(())
    }

    /// Durable put: write hot AND cold synchronously, surface cold errors.
    /// Caller is blocked until both tiers confirm the write — used for the
    /// wrapped vault key at genesis and similar load-bearing blocks.
    fn put_durable(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        self.hot.put(cid, data)?;
        self.cold.put(cid, data)?;
        Ok(())
    }

    /// Durable batch: write all blocks to hot (in-memory, fast) then hand the
    /// whole batch to the cold tier so it can issue the writes concurrently
    /// (~one round-trip vs N sequential). Surfaces cold errors. Used by the
    /// distributed commit path to make a commit's O(state) reachable blocks
    /// durable without N serial cold round-trips (2026-06-02; ADR-2606012200).
    fn put_many_durable(&self, blocks: &[(KotobaCid, Vec<u8>)]) -> Result<()> {
        for (cid, data) in blocks {
            anyhow::ensure!(
                verified_block(cid, data),
                "cid mismatch: expected {}, got {}",
                cid.to_multibase(),
                KotobaCid::from_bytes(data).to_multibase()
            );
        }
        for (cid, data) in blocks {
            self.hot.put(cid, data)?;
        }
        self.cold.put_many_durable(blocks)
    }

    fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
        // Fast path: hot hit
        if let Some(b) = self.hot.get(cid)? {
            if verified_block(cid, &b) {
                return Ok(Some(b));
            }
            tracing::warn!(cid = %cid, "tiered hot block failed CID verification");
            let _ = self.hot.delete(cid);
        }
        // Cold fallback + promote to hot
        if let Some(b) = self.cold.get(cid)? {
            if !verified_block(cid, &b) {
                tracing::warn!(cid = %cid, "tiered cold block failed CID verification");
                return Ok(None);
            }
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

    /// Pin to BOTH tiers.  Hot is just a flag (BudgetedBlockStore eviction
    /// guard); cold is the durable pin (Kubo's recursive pin set) that keeps
    /// the block out of GC.  Pinning only to hot — the previous behaviour —
    /// left wrapped vault keys eligible for Kubo GC and caused the
    /// "wrapped key block missing — re-genesising" loop after restart.
    fn pin(&self, cid: &KotobaCid) {
        self.hot.pin(cid);
        self.cold.pin(cid);
    }

    fn unpin(&self, cid: &KotobaCid) {
        self.hot.unpin(cid);
        self.cold.unpin(cid);
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.hot.is_pinned(cid)
    }

    fn all_cids(&self) -> Vec<KotobaCid> {
        let mut seen = HashSet::new();
        let mut out = Vec::new();
        for cid in self.hot.all_cids().into_iter().chain(self.cold.all_cids()) {
            if seen.insert(cid.0) && self.get(&cid).ok().flatten().is_some() {
                out.push(cid);
            }
        }
        out
    }
}

fn verified_block(cid: &KotobaCid, data: &[u8]) -> bool {
    KotobaCid::from_bytes(data) == *cid
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::memory_store::MemoryBlockStore;

    fn cid(s: &[u8]) -> KotobaCid {
        KotobaCid::from_bytes(s)
    }

    fn tiered() -> TieredBlockStore<MemoryBlockStore, MemoryBlockStore> {
        TieredBlockStore::new(MemoryBlockStore::new(), MemoryBlockStore::new())
    }

    #[tokio::test]
    async fn hot_hit_does_not_touch_cold() {
        let store = tiered();
        let data = b"hello tiered";
        let c = cid(data);
        store.hot.put(&c, data).unwrap();
        assert!(!store.cold.has(&c), "cold should be empty");
        let got = store.get(&c).unwrap();
        assert_eq!(got.unwrap().as_ref(), data);
    }

    #[tokio::test]
    async fn cold_miss_promotes_to_hot() {
        let store = tiered();
        let data = b"cold only block";
        let c = cid(data);
        store.cold.put(&c, data).unwrap();
        assert!(!store.hot.has(&c), "hot should be empty before promotion");

        let got = store.get(&c).unwrap().unwrap();
        assert_eq!(got.as_ref(), data);
        // After get, hot should have the block (promotion)
        assert!(store.hot.has(&c), "promoted to hot after cold hit");
    }

    #[tokio::test]
    async fn corrupted_hot_block_falls_through_to_verified_cold_block() {
        let store = tiered();
        let data = b"verified cold block";
        let c = cid(data);
        store.hot.insert_unchecked(&c, b"corrupted hot block");
        store.cold.put(&c, data).unwrap();

        let got = store.get(&c).unwrap().unwrap();

        assert_eq!(got.as_ref(), data);
        assert_eq!(store.hot.get(&c).unwrap().as_deref(), Some(data.as_slice()));
    }

    #[tokio::test]
    async fn corrupted_cold_block_is_not_returned_or_promoted() {
        let store = tiered();
        let data = b"expected block";
        let c = cid(data);
        store.cold.insert_unchecked(&c, b"corrupted cold block");

        let got = store.get(&c).unwrap();

        assert!(got.is_none());
        assert!(
            !store.hot.has(&c),
            "corrupted cold block must not be promoted"
        );
    }

    #[tokio::test]
    async fn put_goes_to_hot_immediately() {
        let store = tiered();
        let data = b"write test";
        let c = cid(data);
        store.put(&c, data).unwrap();
        assert!(
            store.hot.has(&c),
            "hot must have block immediately after put"
        );
        // Cold write is async — we don't assert it here
    }

    #[test]
    fn put_many_durable_rejects_mismatch_before_writing_hot_or_cold() {
        let store = tiered();
        let good = b"good batch block".to_vec();
        let good_cid = cid(&good);
        let bad_cid = cid(b"expected batch block");
        let bad = b"different batch block".to_vec();

        let err = store
            .put_many_durable(&[(good_cid.clone(), good), (bad_cid.clone(), bad)])
            .unwrap_err();

        assert!(err.to_string().contains("cid mismatch"));
        assert!(!store.hot.has(&good_cid));
        assert!(!store.cold.has(&good_cid));
        assert!(!store.hot.has(&bad_cid));
        assert!(!store.cold.has(&bad_cid));
    }

    #[test]
    fn has_checks_both_tiers() {
        let store = tiered();
        let cold_data = b"cold only";
        let hot_data = b"hot only";
        let cc = cid(cold_data);
        let ch = cid(hot_data);
        store.cold.put(&cc, cold_data).unwrap();
        store.hot.put(&ch, hot_data).unwrap();
        assert!(store.has(&cc));
        assert!(store.has(&ch));
        assert!(!store.has(&cid(b"missing")));
    }

    #[test]
    fn delete_removes_from_hot() {
        let store = tiered();
        let data = b"to be deleted";
        let c = cid(data);
        store.hot.put(&c, data).unwrap();
        assert!(store.hot.has(&c));
        store.delete(&c).unwrap();
        assert!(!store.hot.has(&c));
    }

    #[test]
    fn pin_and_is_pinned_delegates_to_hot() {
        let store = tiered();
        let data = b"pin test";
        let c = cid(data);
        store.hot.put(&c, data).unwrap();
        assert!(!store.is_pinned(&c));
        store.pin(&c);
        assert!(store.is_pinned(&c));
        store.unpin(&c);
        assert!(!store.is_pinned(&c));
    }

    #[test]
    fn get_missing_from_both_tiers_returns_none() {
        let store = tiered();
        let c = cid(b"definitely not stored");
        assert!(store.get(&c).unwrap().is_none());
    }

    // ── New tests ─────────────────────────────────────────────────────────────

    #[test]
    fn hot_accessor_returns_hot_tier() {
        let store = tiered();
        let data = b"accessor-test";
        let c = cid(data);
        store.hot().put(&c, data).unwrap();
        assert!(store.hot().has(&c));
        // Cold should not have it.
        assert!(!store.cold().has(&c));
    }

    #[test]
    fn cold_accessor_returns_cold_tier() {
        let store = tiered();
        let data = b"cold-accessor";
        let c = cid(data);
        store.cold().put(&c, data).unwrap();
        assert!(store.cold().has(&c));
        assert!(!store.hot().has(&c));
    }

    #[test]
    fn delete_also_removes_from_cold() {
        let store = tiered();
        let data = b"delete-cold";
        let c = cid(data);
        // Put directly in both tiers.
        store.hot().put(&c, data).unwrap();
        store.cold().put(&c, data).unwrap();
        assert!(store.has(&c));
        store.delete(&c).unwrap();
        // After delete, neither tier should have the block.
        assert!(!store.hot().has(&c));
        assert!(!store.cold().has(&c));
    }

    #[test]
    fn has_returns_false_when_both_tiers_empty() {
        let store = tiered();
        assert!(!store.has(&cid(b"nothing-here")));
    }

    #[test]
    fn unpin_after_pin_clears_is_pinned() {
        let store = tiered();
        let data = b"data";
        let c = cid(data);
        store.hot().put(&c, data).unwrap();
        store.pin(&c);
        assert!(store.is_pinned(&c));
        store.unpin(&c);
        assert!(!store.is_pinned(&c));
    }

    #[test]
    fn put_empty_data_stored_in_hot() {
        let store = tiered();
        let c = cid(b"");
        store.put(&c, b"").unwrap();
        assert!(store.hot().has(&c));
        let got = store.get(&c).unwrap().expect("should exist");
        assert_eq!(got.len(), 0);
    }

    #[test]
    fn get_returns_data_from_hot_without_going_to_cold() {
        let store = tiered();
        let data = b"only in hot";
        let c = cid(data);
        store.hot().put(&c, data).unwrap();
        // Cold is still empty.
        assert!(!store.cold().has(&c));
        let got = store.get(&c).unwrap().unwrap();
        assert_eq!(got.as_ref(), data);
        // Cold must still be empty after a hot-hit read.
        assert!(!store.cold().has(&c));
    }

    #[test]
    fn all_cids_returns_verified_union_from_hot_and_cold() {
        let store = tiered();
        let hot_data = b"tiered hot listed";
        let cold_data = b"tiered cold listed";
        let duplicate_data = b"tiered duplicate listed";
        let hot_cid = cid(hot_data);
        let cold_cid = cid(cold_data);
        let duplicate_cid = cid(duplicate_data);
        let corrupt_cid = cid(b"tiered corrupt listed");
        store.hot.put(&hot_cid, hot_data).unwrap();
        store.cold.put(&cold_cid, cold_data).unwrap();
        store.hot.put(&duplicate_cid, duplicate_data).unwrap();
        store.cold.put(&duplicate_cid, duplicate_data).unwrap();
        store
            .hot
            .insert_unchecked(&corrupt_cid, b"corrupt listed block");

        let mut cids = store.all_cids();
        cids.sort_by_key(|cid| cid.0);
        let mut expected = vec![hot_cid, cold_cid, duplicate_cid];
        expected.sort_by_key(|cid| cid.0);

        assert_eq!(cids, expected);
        assert!(
            !store.hot.has(&corrupt_cid),
            "all_cids should clean corrupt hot entries through get()"
        );
    }
}
