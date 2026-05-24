use crate::cid::KotobaCid;
use crate::store::BlockStore;
use std::collections::BTreeMap;

/// Prolly Tree — probabilistic boundary, content-addressed ordered set
/// boundary condition: blake3(node_bytes)[0..4] == 0x00000000 (1/2^32 prob → ~4B chunk)
pub const BOUNDARY_MASK: u32 = 0x0000_00FF; // tune for ~256 byte chunks in PoC

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum ProllyNode {
    Leaf {
        entries: Vec<(Vec<u8>, Vec<u8>)>, // (key, value) sorted
        cid:     KotobaCid,
    },
    Internal {
        children: Vec<(Vec<u8>, KotobaCid)>, // (boundary_key, child_cid)
        cid:      KotobaCid,
    },
}

impl ProllyNode {
    pub fn cid(&self) -> &KotobaCid {
        match self {
            Self::Leaf { cid, .. } => cid,
            Self::Internal { cid, .. } => cid,
        }
    }

    pub fn is_boundary(key: &[u8]) -> bool {
        let hash = blake3::hash(key);
        let prefix = u32::from_be_bytes(hash.as_bytes()[0..4].try_into().unwrap());
        (prefix & BOUNDARY_MASK) == 0
    }
}

#[derive(Debug, Default)]
pub struct ProllyTree {
    pub root: Option<KotobaCid>,
    nodes: BTreeMap<KotobaCid, ProllyNode>,
}

impl ProllyTree {
    pub fn new() -> Self { Self::default() }

    pub fn root_cid(&self) -> Option<&KotobaCid> {
        self.root.as_ref()
    }

    /// Diff two roots → returns (only_in_a, only_in_b)
    pub fn diff(a_root: &KotobaCid, b_root: &KotobaCid) -> (Vec<KotobaCid>, Vec<KotobaCid>) {
        if a_root == b_root { return (vec![], vec![]); }
        // Full diff implementation: walk tree, compare children CIDs
        // Placeholder — O(|diff|) implementation in Phase 1
        (vec![a_root.clone()], vec![b_root.clone()])
    }

    /// Serialize a node to DAG-CBOR and write it to the block store.
    /// Returns the node's CID (= blake3(cbor_bytes)).
    pub fn put_node(node: &ProllyNode, store: &dyn BlockStore) -> anyhow::Result<KotobaCid> {
        let mut buf = Vec::new();
        ciborium::into_writer(node, &mut buf)
            .map_err(|e| anyhow::anyhow!("cbor encode: {e}"))?;
        let cid = KotobaCid::from_bytes(&buf);
        store.put(&cid, &buf)?;
        Ok(cid)
    }

    /// Load a ProllyNode from the block store by CID.
    pub fn load_node(cid: &KotobaCid, store: &dyn BlockStore) -> anyhow::Result<Option<ProllyNode>> {
        match store.get(cid)? {
            None => Ok(None),
            Some(bytes) => {
                let node: ProllyNode = ciborium::from_reader(&bytes[..])
                    .map_err(|e| anyhow::anyhow!("cbor decode: {e}"))?;
                Ok(Some(node))
            }
        }
    }

    /// Flush all in-memory nodes to the block store.
    /// Returns the root CID if the tree has a root.
    pub fn flush(&self, store: &dyn BlockStore) -> anyhow::Result<Option<KotobaCid>> {
        for node in self.nodes.values() {
            Self::put_node(node, store)?;
        }
        Ok(self.root.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::store::BlockStore;
    use bytes::Bytes;
    use std::collections::HashMap;
    use std::sync::{Arc, RwLock};

    /// Minimal in-process block store for unit tests (avoids circular dep on kotoba-store).
    struct MemoryBlockStore {
        blocks: Arc<RwLock<HashMap<[u8; 36], Bytes>>>,
    }

    impl MemoryBlockStore {
        fn new() -> Self {
            Self { blocks: Arc::new(RwLock::new(HashMap::new())) }
        }
        fn block_count(&self) -> usize {
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

    #[test]
    fn put_and_load_leaf_node() {
        let store = MemoryBlockStore::new();
        let node = ProllyNode::Leaf {
            entries: vec![(b"key1".to_vec(), b"val1".to_vec())],
            cid: KotobaCid::from_bytes(b"dummy"),
        };
        let cid = ProllyTree::put_node(&node, &store).unwrap();
        let loaded = ProllyTree::load_node(&cid, &store).unwrap().unwrap();
        match loaded {
            ProllyNode::Leaf { entries, .. } => {
                assert_eq!(entries[0].0, b"key1");
            }
            _ => panic!("expected leaf"),
        }
    }

    #[test]
    fn flush_empty_tree_returns_none() {
        let store = MemoryBlockStore::new();
        let tree = ProllyTree::new();
        let root = tree.flush(&store).unwrap();
        assert!(root.is_none());
        assert_eq!(store.block_count(), 0);
    }
}
