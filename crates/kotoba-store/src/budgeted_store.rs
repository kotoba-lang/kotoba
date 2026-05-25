use std::collections::{HashMap, HashSet, VecDeque};
use std::sync::{Arc, Mutex};
use bytes::Bytes;
use anyhow::Result;
use kotoba_core::cid::KotobaCid;
use kotoba_core::store::BlockStore;

/// LRU + pin-aware eviction wrapper over any BlockStore.
///
/// Tracks every block written through `put()` in an LRU index. When
/// `used_bytes > max_bytes`, `evict_cold()` removes the least-recently-used
/// *unpinned* blocks until usage drops to ≤ 80% of the budget, calling
/// `inner.delete()` on each removed block.
///
/// # Invariants
/// - Only blocks written through `put()` appear in the LRU index.
/// - Pinned blocks are never evicted.
/// - `has()` returns false for blocks that have been evicted (even if the
///   inner store still has them — shadow eviction is never used here because
///   `delete()` is called on the inner store).
pub struct BudgetedBlockStore<S: BlockStore> {
    inner:     Arc<S>,
    max_bytes: usize,
    state:     Mutex<Budget>,
}

struct Budget {
    used_bytes: usize,
    sizes:      HashMap<[u8; 36], usize>,  // cid → byte size
    lru:        VecDeque<[u8; 36]>,         // front = coldest (LRU order)
    pinned:     HashSet<[u8; 36]>,
}

impl Budget {
    fn touch(&mut self, key: [u8; 36]) {
        self.lru.retain(|k| k != &key);
        self.lru.push_back(key);
    }
}

impl<S: BlockStore + 'static> BudgetedBlockStore<S> {
    pub fn new(inner: S, max_bytes: usize) -> Self {
        Self {
            inner: Arc::new(inner),
            max_bytes,
            state: Mutex::new(Budget {
                used_bytes: 0,
                sizes: HashMap::new(),
                lru: VecDeque::new(),
                pinned: HashSet::new(),
            }),
        }
    }

    pub fn used_bytes(&self) -> usize {
        self.state.lock().unwrap().used_bytes
    }

    pub fn block_count(&self) -> usize {
        self.state.lock().unwrap().sizes.len()
    }

    /// Evict cold unpinned blocks until usage ≤ 80% of budget.
    /// Returns the number of bytes freed.
    pub fn evict_cold(&self) -> usize {
        let target = (self.max_bytes as f64 * 0.80) as usize;
        let mut freed = 0usize;
        let to_delete: Vec<[u8; 36]> = {
            let st = self.state.lock().unwrap();
            if st.used_bytes <= self.max_bytes {
                return 0;
            }
            let mut evict = Vec::new();
            let mut projected = st.used_bytes;
            for &key in &st.lru {
                if projected <= target { break; }
                if !st.pinned.contains(&key) {
                    if let Some(&sz) = st.sizes.get(&key) {
                        evict.push(key);
                        projected = projected.saturating_sub(sz);
                    }
                }
            }
            evict
        };

        for key in &to_delete {
            let cid = KotobaCid(*key);
            let _ = self.inner.delete(&cid);
            let mut st = self.state.lock().unwrap();
            st.lru.retain(|k| k != key);
            if let Some(sz) = st.sizes.remove(key) {
                st.used_bytes = st.used_bytes.saturating_sub(sz);
                freed += sz;
            }
        }
        freed
    }
}

impl<S: BlockStore + 'static> BlockStore for BudgetedBlockStore<S> {
    fn put(&self, cid: &KotobaCid, data: &[u8]) -> Result<()> {
        let size = data.len();
        self.inner.put(cid, data)?;
        {
            let mut st = self.state.lock().unwrap();
            if !st.sizes.contains_key(&cid.0) {
                st.used_bytes += size;
                st.sizes.insert(cid.0, size);
            }
            st.touch(cid.0);
        }
        if self.used_bytes() > self.max_bytes {
            self.evict_cold();
        }
        Ok(())
    }

    fn get(&self, cid: &KotobaCid) -> Result<Option<Bytes>> {
        let in_index = {
            let mut st = self.state.lock().unwrap();
            if st.sizes.contains_key(&cid.0) {
                st.touch(cid.0);
                true
            } else {
                false
            }
        };
        if in_index {
            self.inner.get(cid)
        } else {
            Ok(None)
        }
    }

    fn has(&self, cid: &KotobaCid) -> bool {
        self.state.lock().unwrap().sizes.contains_key(&cid.0)
    }

    fn delete(&self, cid: &KotobaCid) -> Result<()> {
        self.inner.delete(cid)?;
        let mut st = self.state.lock().unwrap();
        st.lru.retain(|k| k != &cid.0);
        if let Some(sz) = st.sizes.remove(&cid.0) {
            st.used_bytes = st.used_bytes.saturating_sub(sz);
        }
        Ok(())
    }

    fn pin(&self, cid: &KotobaCid) {
        self.state.lock().unwrap().pinned.insert(cid.0);
    }

    fn unpin(&self, cid: &KotobaCid) {
        self.state.lock().unwrap().pinned.remove(&cid.0);
    }

    fn is_pinned(&self, cid: &KotobaCid) -> bool {
        self.state.lock().unwrap().pinned.contains(&cid.0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::memory_store::MemoryBlockStore;

    fn cid(seed: &[u8]) -> KotobaCid { KotobaCid::from_bytes(seed) }
    fn budgeted(max: usize) -> BudgetedBlockStore<MemoryBlockStore> {
        BudgetedBlockStore::new(MemoryBlockStore::new(), max)
    }

    #[test]
    fn put_and_get_roundtrip() {
        let store = budgeted(1024 * 1024);
        let data = b"hello kotoba";
        let c = cid(data);
        store.put(&c, data).unwrap();
        assert!(store.has(&c));
        assert_eq!(store.get(&c).unwrap().unwrap().as_ref(), data);
    }

    #[test]
    fn used_bytes_tracks_puts() {
        let store = budgeted(1024 * 1024);
        let d1 = b"block one";
        let d2 = b"block two!!";
        store.put(&cid(d1), d1).unwrap();
        store.put(&cid(d2), d2).unwrap();
        assert_eq!(store.used_bytes(), d1.len() + d2.len());
    }

    #[test]
    fn evict_cold_removes_unpinned_when_over_budget() {
        // Budget = 30 bytes; fill with 3 × 10-byte blocks
        let store = budgeted(30);
        let d1 = b"0123456789"; // 10 bytes
        let d2 = b"abcdefghij"; // 10 bytes
        let d3 = b"ABCDEFGHIJ"; // 10 bytes — triggers eviction (used = 30, budget = 30, ok)
        store.put(&cid(d1), d1).unwrap();
        store.put(&cid(d2), d2).unwrap();
        store.put(&cid(d3), d3).unwrap();
        // Now add a 4th to push over budget
        let d4 = b"xxxxxxxxxxxx"; // 12 bytes → total 42 > 30
        store.put(&cid(d4), d4).unwrap();
        // After eviction, used ≤ 30*0.8 = 24 bytes, oldest blocks removed
        assert!(store.used_bytes() <= 30);
    }

    #[test]
    fn pin_prevents_eviction() {
        let store = budgeted(20);
        let d1 = b"0123456789"; // 10 bytes — pinned
        let d2 = b"abcdefghij"; // 10 bytes — cold
        let c1 = cid(d1);
        store.put(&c1, d1).unwrap();
        store.pin(&c1);
        store.put(&cid(d2), d2).unwrap();
        // Over budget by 20 bytes (budget=20, used=20 — just at limit)
        // Add 1 more byte to push over
        let d3 = b"!";
        store.put(&cid(d3), d3).unwrap();
        store.evict_cold();
        // Pinned block must survive
        assert!(store.has(&c1), "pinned block must not be evicted");
    }

    #[test]
    fn delete_removes_from_index() {
        let store = budgeted(1024);
        let data = b"deletable";
        let c = cid(data);
        store.put(&c, data).unwrap();
        assert_eq!(store.used_bytes(), data.len());
        store.delete(&c).unwrap();
        assert!(!store.has(&c));
        assert_eq!(store.used_bytes(), 0);
    }

    #[test]
    fn evicted_block_not_visible_via_has_or_get() {
        let store = budgeted(10);
        let d1 = b"0123456789"; // 10 bytes
        let d2 = b"ABCDEFGHIJK"; // 11 bytes → triggers eviction of d1
        let c1 = cid(d1);
        store.put(&c1, d1).unwrap();
        store.put(&cid(d2), d2).unwrap();
        // d1 is now evicted
        assert!(!store.has(&c1));
        assert!(store.get(&c1).unwrap().is_none());
    }
}
