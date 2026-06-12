use bytes::Bytes;
use dashmap::DashMap;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::sync::Arc;

#[derive(Default, Clone)]
pub struct MemoryBlockStore {
    blocks: Arc<DashMap<[u8; 36], Bytes>>,
    pinned: Arc<DashMap<[u8; 36], ()>>,
}

impl MemoryBlockStore {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn block_count(&self) -> usize {
        self.blocks.len()
    }

    #[cfg(test)]
    pub(crate) fn insert_unchecked(&self, cid: &KotobaCid, data: &[u8]) {
        self.blocks.insert(cid.0, Bytes::copy_from_slice(data));
    }
}

impl BlockStore for MemoryBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        anyhow::ensure!(
            KotobaCid::from_bytes(data) == *cid,
            "cid mismatch: expected {}, got {}",
            cid.to_multibase(),
            KotobaCid::from_bytes(data).to_multibase()
        );
        self.blocks.insert(cid.0, Bytes::copy_from_slice(data));
        Ok(())
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        let Some(block) = self.blocks.get(&cid.0).map(|r| r.clone()) else {
            return Ok(None);
        };
        if KotobaCid::from_bytes(&block) != *cid {
            tracing::warn!(cid = %cid, "memory block failed CID verification");
            self.blocks.remove(&cid.0);
            return Ok(None);
        }
        Ok(Some(block))
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.get(cid).ok().flatten().is_some()
    }

    fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
        self.blocks.remove(&cid.0);
        self.pinned.remove(&cid.0);
        Ok(())
    }

    fn pin(&self, cid: &KotobaCid) {
        self.pinned.insert(cid.0, ());
    }

    fn unpin(&self, cid: &KotobaCid) {
        self.pinned.remove(&cid.0);
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.pinned.contains_key(&cid.0)
    }

    fn all_cids(&self) -> Vec<KotobaCid> {
        let cids: Vec<KotobaCid> = self.blocks.iter().map(|r| KotobaCid(*r.key())).collect();
        cids.into_iter()
            .filter(|cid| self.get(cid).ok().flatten().is_some())
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cid(tag: &[u8]) -> KotobaCid {
        KotobaCid::from_bytes(tag)
    }

    #[test]
    fn put_and_get_roundtrip() {
        let store = MemoryBlockStore::new();
        let data = b"data";
        let c = cid(data);
        store.put(&c, data).unwrap();
        assert_eq!(store.get(&c).unwrap().as_deref(), Some(data.as_slice()));
    }

    #[test]
    fn get_missing_returns_none() {
        let store = MemoryBlockStore::new();
        assert!(store.get(&cid(b"absent")).unwrap().is_none());
    }

    #[test]
    fn has_reflects_put_and_delete() {
        let store = MemoryBlockStore::new();
        let data = b"x";
        let c = cid(data);
        assert!(!store.has(&c));
        store.put(&c, data).unwrap();
        assert!(store.has(&c));
        store.delete(&c).unwrap();
        assert!(!store.has(&c));
    }

    #[test]
    fn delete_missing_is_idempotent() {
        let store = MemoryBlockStore::new();
        store.delete(&cid(b"never-existed")).unwrap();
    }

    #[test]
    fn block_count_tracks_puts_and_deletes() {
        let store = MemoryBlockStore::new();
        assert_eq!(store.block_count(), 0);
        let c1 = cid(b"a");
        let c2 = cid(b"b");
        store.put(&c1, b"a").unwrap();
        store.put(&c2, b"b").unwrap();
        assert_eq!(store.block_count(), 2);
        store.delete(&c1).unwrap();
        assert_eq!(store.block_count(), 1);
    }

    #[test]
    fn pin_prevents_nothing_but_is_tracked() {
        let store = MemoryBlockStore::new();
        let data = b"v";
        let c = cid(data);
        store.put(&c, data).unwrap();
        assert!(!store.is_pinned(&c));
        store.pin(&c);
        assert!(store.is_pinned(&c));
        store.unpin(&c);
        assert!(!store.is_pinned(&c));
    }

    #[test]
    fn all_cids_returns_all_stored_keys() {
        let store = MemoryBlockStore::new();
        let c1 = cid(b"");
        let c2 = cid(b"two");
        store.put(&c1, b"").unwrap();
        store.put(&c2, b"two").unwrap();
        let cids = store.all_cids();
        assert!(cids.contains(&c1));
        assert!(cids.contains(&c2));
        assert_eq!(cids.len(), 2);
    }

    #[test]
    fn put_same_content_is_idempotent() {
        let store = MemoryBlockStore::new();
        let data = b"same";
        let c = cid(data);
        store.put(&c, data).unwrap();
        store.put(&c, data).unwrap();
        assert_eq!(store.get(&c).unwrap().as_deref(), Some(data.as_slice()));
        assert_eq!(store.block_count(), 1);
    }

    #[test]
    fn clone_shares_underlying_data() {
        let store1 = MemoryBlockStore::new();
        let store2 = store1.clone();
        let data = b"value";
        let c = cid(data);
        store1.put(&c, data).unwrap();
        assert!(store2.has(&c), "clone shares inner Arc");
        assert_eq!(store2.get(&c).unwrap().as_deref(), Some(data.as_slice()));
    }

    #[test]
    fn empty_data_put_and_get() {
        let store = MemoryBlockStore::new();
        let c = cid(b"");
        store.put(&c, b"").unwrap();
        let got = store.get(&c).unwrap().expect("block should exist");
        assert_eq!(got.len(), 0);
        assert!(store.has(&c));
    }

    #[test]
    fn unpin_nonexistent_cid_is_noop() {
        let store = MemoryBlockStore::new();
        let c = cid(b"never-pinned");
        store.unpin(&c);
        assert!(!store.is_pinned(&c));
    }

    #[test]
    fn pin_then_delete_does_not_keep_pin() {
        let store = MemoryBlockStore::new();
        let data = b"data";
        let c = cid(data);
        store.put(&c, data).unwrap();
        store.pin(&c);
        assert!(store.is_pinned(&c));
        store.delete(&c).unwrap();
        assert!(!store.has(&c));
        assert!(!store.is_pinned(&c));
    }

    #[test]
    fn all_cids_empty_on_new_store() {
        let store = MemoryBlockStore::new();
        assert!(store.all_cids().is_empty());
    }

    #[test]
    fn block_count_starts_at_zero() {
        let store = MemoryBlockStore::new();
        assert_eq!(store.block_count(), 0);
    }

    #[test]
    fn large_block_data_roundtrip() {
        let store = MemoryBlockStore::new();
        let large_data: Vec<u8> = (0u8..=255u8).cycle().take(4096).collect();
        let c = cid(&large_data);
        store.put(&c, &large_data).unwrap();
        let got = store.get(&c).unwrap().expect("should exist");
        assert_eq!(got.as_ref(), large_data.as_slice());
    }

    #[test]
    fn put_rejects_mismatched_cid() {
        let store = MemoryBlockStore::new();
        let c = cid(b"expected");

        let err = store.put(&c, b"different").unwrap_err();

        assert!(err.to_string().contains("cid mismatch"));
        assert!(!store.has(&c));
    }

    #[test]
    fn get_removes_corrupted_unchecked_block() {
        let store = MemoryBlockStore::new();
        let c = cid(b"expected");
        store.insert_unchecked(&c, b"different");

        assert!(store.get(&c).unwrap().is_none());
        assert!(!store.has(&c));
    }

    #[test]
    fn all_cids_skips_and_removes_corrupted_unchecked_block() {
        let store = MemoryBlockStore::new();
        let good = cid(b"good");
        let corrupt = cid(b"expected");
        store.put(&good, b"good").unwrap();
        store.insert_unchecked(&corrupt, b"different");

        let cids = store.all_cids();

        assert_eq!(cids, vec![good]);
        assert!(!store.has(&corrupt));
        assert_eq!(store.block_count(), 1);
    }
}
