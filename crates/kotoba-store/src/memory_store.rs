use bytes::Bytes;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;
use std::collections::HashMap;
use std::sync::{Arc, RwLock};

#[derive(Default, Clone)]
pub struct MemoryBlockStore {
    blocks: Arc<RwLock<HashMap<[u8; 36], Bytes>>>,
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
}
