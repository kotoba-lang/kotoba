use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::collections::{HashMap, HashSet};
use std::sync::{Arc, RwLock};

#[derive(Default, Clone)]
pub struct MemoryBlockStore {
    blocks: Arc<RwLock<HashMap<[u8; 36], Bytes>>>,
    pinned: Arc<RwLock<HashSet<[u8; 36]>>>,
}

impl MemoryBlockStore {
    pub fn new() -> Self { Self::default() }

    pub fn block_count(&self) -> usize {
        self.blocks.read().unwrap().len()
    }
}

impl BlockStore for MemoryBlockStore {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.blocks.write().unwrap().insert(cid.0, Bytes::copy_from_slice(data));
        Ok(())
    }

    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        Ok(self.blocks.read().unwrap().get(&cid.0).cloned())
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.blocks.read().unwrap().contains_key(&cid.0)
    }

    fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
        self.blocks.write().unwrap().remove(&cid.0);
        Ok(())
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

    fn all_cids(&self) -> Vec<KotobaCid> {
        self.blocks.read().unwrap().keys().map(|k| KotobaCid(*k)).collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cid(tag: &[u8]) -> KotobaCid { KotobaCid::from_bytes(tag) }

    #[test]
    fn put_and_get_roundtrip() {
        let store = MemoryBlockStore::new();
        let c = cid(b"block-a");
        store.put(&c, b"data").unwrap();
        assert_eq!(store.get(&c).unwrap().as_deref(), Some(b"data".as_slice()));
    }

    #[test]
    fn get_missing_returns_none() {
        let store = MemoryBlockStore::new();
        assert!(store.get(&cid(b"absent")).unwrap().is_none());
    }

    #[test]
    fn has_reflects_put_and_delete() {
        let store = MemoryBlockStore::new();
        let c = cid(b"has-test");
        assert!(!store.has(&c));
        store.put(&c, b"x").unwrap();
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
        let c1 = cid(b"c1");
        let c2 = cid(b"c2");
        store.put(&c1, b"a").unwrap();
        store.put(&c2, b"b").unwrap();
        assert_eq!(store.block_count(), 2);
        store.delete(&c1).unwrap();
        assert_eq!(store.block_count(), 1);
    }

    #[test]
    fn pin_prevents_nothing_but_is_tracked() {
        let store = MemoryBlockStore::new();
        let c = cid(b"pinned");
        store.put(&c, b"v").unwrap();
        assert!(!store.is_pinned(&c));
        store.pin(&c);
        assert!(store.is_pinned(&c));
        store.unpin(&c);
        assert!(!store.is_pinned(&c));
    }

    #[test]
    fn all_cids_returns_all_stored_keys() {
        let store = MemoryBlockStore::new();
        let c1 = cid(b"all-cids-1");
        let c2 = cid(b"all-cids-2");
        store.put(&c1, b"").unwrap();
        store.put(&c2, b"").unwrap();
        let mut cids = store.all_cids();
        cids.sort_by_key(|c| c.to_multibase());
        assert!(cids.contains(&c1));
        assert!(cids.contains(&c2));
        assert_eq!(cids.len(), 2);
    }

    #[test]
    fn put_overwrites_existing() {
        let store = MemoryBlockStore::new();
        let c = cid(b"overwrite");
        store.put(&c, b"old").unwrap();
        store.put(&c, b"new").unwrap();
        assert_eq!(store.get(&c).unwrap().as_deref(), Some(b"new".as_slice()));
        assert_eq!(store.block_count(), 1);
    }
}
