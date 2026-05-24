use crate::cid::KotobaCid;
use bytes::Bytes;

/// Content-addressed block store — minimal trait defined in kotoba-core
/// so that kotoba-core::prolly can depend on it without a circular dep.
///
/// kotoba-store re-exports this trait and provides concrete implementations
/// (SledBlockStore, MemoryBlockStore).
pub trait BlockStore: Send + Sync {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()>;
    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>>;
    fn has(&self, cid: &KotobaCid) -> bool;
}
