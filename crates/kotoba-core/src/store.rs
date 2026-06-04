use crate::cid::KotobaCid;
use bytes::Bytes;

/// Content-addressed block store — minimal trait defined in kotoba-core
/// so that kotoba-core::prolly can depend on it without a circular dep.
///
/// kotoba-store re-exports this trait and provides concrete implementations
/// (SledBlockStore, MemoryBlockStore, BudgetedBlockStore).
pub trait BlockStore: Send + Sync {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()>;
    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>>;
    fn has(&self, cid: &KotobaCid) -> bool;

    /// Write a block synchronously to every persistent tier, returning Ok
    /// only after durability is confirmed.  Default = `put` (single-tier
    /// stores are already durable).  Multi-tier implementations such as
    /// `TieredBlockStore` MUST override to bypass the fire-and-forget cold
    /// spawn and surface real errors to the caller.
    ///
    /// Use for blocks where silent cold-tier loss would be catastrophic:
    /// wrapped vault keys, root commit pointers, IPNS heads.
    fn put_durable(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        self.put(cid, data)
    }

    /// Durably write a batch of blocks, ideally in ONE cold round-trip / with
    /// concurrency, returning Ok only after all are confirmed. Default = a
    /// sequential `put_durable` loop. Cold tiers with per-block network latency
    /// (e.g. `KuboBlockStore`) SHOULD override to issue the writes concurrently
    /// so a commit's O(state) blocks cost ~one round-trip instead of N. Used by
    /// the distributed commit path to make a whole commit's reachable blocks
    /// durable without N sequential `block/put`s.
    fn put_many_durable(&self, blocks: &[(KotobaCid, Vec<u8>)]) -> anyhow::Result<()> {
        for (cid, data) in blocks {
            self.put_durable(cid, data)?;
        }
        Ok(())
    }

    /// Remove a block. Default no-op for read-only or append-only stores.
    fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
        let _ = cid;
        Ok(())
    }

    /// Protect this CID from eviction by BudgetedBlockStore. Default no-op.
    fn pin(&self, cid: &KotobaCid) {
        let _ = cid;
    }

    /// Allow this CID to be evicted again. Default no-op.
    fn unpin(&self, cid: &KotobaCid) {
        let _ = cid;
    }

    /// Returns true if this CID is currently pinned.
    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        let _ = cid;
        false
    }

    /// Enumerate all CIDs stored in this store.  Default returns empty vec for
    /// stores that don't support listing (S3, kubo).  Used by `QuadStore::gc_dead_blocks`.
    fn all_cids(&self) -> Vec<KotobaCid> {
        vec![]
    }
}

/// Blanket impl so an `Arc<dyn BlockStore>` (the type the server threads around)
/// can itself be a `BlockStore` tier — e.g. nesting an existing store under a
/// new cold tier via `TieredBlockStore::new(existing_arc, cold)`. Delegates
/// every method to the inner store, preserving overridden behaviour.
impl<T: BlockStore + ?Sized> BlockStore for std::sync::Arc<T> {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        (**self).put(cid, data)
    }
    fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
        (**self).get(cid)
    }
    fn has(&self, cid: &KotobaCid) -> bool {
        (**self).has(cid)
    }
    fn put_durable(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
        (**self).put_durable(cid, data)
    }
    fn put_many_durable(&self, blocks: &[(KotobaCid, Vec<u8>)]) -> anyhow::Result<()> {
        (**self).put_many_durable(blocks)
    }
    fn delete(&self, cid: &KotobaCid) -> anyhow::Result<()> {
        (**self).delete(cid)
    }
    fn pin(&self, cid: &KotobaCid) {
        (**self).pin(cid)
    }
    fn unpin(&self, cid: &KotobaCid) {
        (**self).unpin(cid)
    }
    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        (**self).is_pinned(cid)
    }
    fn all_cids(&self) -> Vec<KotobaCid> {
        (**self).all_cids()
    }
}
