use crate::cid::KotobaCid;
use crate::store::BlockStore;
use serde_bytes::ByteBuf;
use std::collections::BTreeMap;

/// Prolly Tree — probabilistic boundary, content-addressed ordered set.
///
/// The **boundary** is a content-defined chunk split keyed on the *entry key*:
/// `blake3(key)[0..4] & BOUNDARY_MASK == 0` (history-independent, structurally
/// shared). The **block CID** is independent of the boundary: nodes are encoded
/// as canonical **DAG-CBOR** (ADR-2606022150) and addressed by
/// `sha2-256(dag-cbor-bytes)` — a genuine CIDv1 dag-cbor link (see `put_node`).
pub const BOUNDARY_MASK: u32 = 0x0000_00FF; // tune for ~256 byte chunks in PoC

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum ProllyNode {
    Leaf {
        entries: Vec<(Vec<u8>, Vec<u8>)>, // (key, value) sorted
        cid: KotobaCid,
    },
    Internal {
        children: Vec<(Vec<u8>, KotobaCid)>, // (boundary_key, child_cid)
        cid: KotobaCid,
    },
}

/// On-block serialization mirror of [`ProllyNode`], encoded as **true DAG-CBOR**
/// (ADR-2606022150 D1):
///
/// - child links are `::cid::Cid` → emitted as **IPLD CID tag-42**, not raw bytes,
///   so a generic DAG-CBOR / IPFS tool can walk the tree;
/// - keys/values are `serde_bytes::ByteBuf` → CBOR byte strings, not arrays;
/// - the node's **own CID is not stored inside the block** (it is the hash of the
///   block — storing it would be circular and non-canonical); `load_node` restores
///   it from the lookup CID.
///
/// `KotobaCid`'s global serde is deliberately left unchanged (byte array in commit
/// blocks / server JSON / `StoredDatom`); tag-42 is contained to this codec.
#[derive(serde::Serialize, serde::Deserialize)]
enum ProllyNodeDag {
    Leaf {
        entries: Vec<(ByteBuf, ByteBuf)>,
    },
    Internal {
        children: Vec<(ByteBuf, ::cid::Cid)>,
    },
}

impl ProllyNodeDag {
    fn from_node(node: &ProllyNode) -> anyhow::Result<Self> {
        Ok(match node {
            ProllyNode::Leaf { entries, .. } => ProllyNodeDag::Leaf {
                entries: entries
                    .iter()
                    .map(|(k, v)| (ByteBuf::from(k.clone()), ByteBuf::from(v.clone())))
                    .collect(),
            },
            ProllyNode::Internal { children, .. } => ProllyNodeDag::Internal {
                children: children
                    .iter()
                    .map(|(k, c)| {
                        c.to_standard_cid()
                            .map(|cid| (ByteBuf::from(k.clone()), cid))
                            .map_err(|e| anyhow::anyhow!("child link → CID: {e:?}"))
                    })
                    .collect::<anyhow::Result<Vec<_>>>()?,
            },
        })
    }

    fn into_node(self, self_cid: KotobaCid) -> anyhow::Result<ProllyNode> {
        Ok(match self {
            ProllyNodeDag::Leaf { entries } => ProllyNode::Leaf {
                entries: entries
                    .into_iter()
                    .map(|(k, v)| (k.into_vec(), v.into_vec()))
                    .collect(),
                cid: self_cid,
            },
            ProllyNodeDag::Internal { children } => ProllyNode::Internal {
                children: children
                    .into_iter()
                    .map(|(k, cid)| {
                        KotobaCid::from_standard_cid(&cid)
                            .map(|kc| (k.into_vec(), kc))
                            .ok_or_else(|| anyhow::anyhow!("CID tag-42 link → KotobaCid"))
                    })
                    .collect::<anyhow::Result<Vec<_>>>()?,
                cid: self_cid,
            },
        })
    }
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

/// Entry-level result of [`ProllyTree::diff_entries`] (`a` = before, `b` = after).
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct ProllyDiff {
    /// Keys present in `b` but not `a` — `(key, new_value)`.
    pub added: Vec<(Vec<u8>, Vec<u8>)>,
    /// Keys present in `a` but not `b` — `(key, old_value)`.
    pub removed: Vec<(Vec<u8>, Vec<u8>)>,
    /// Keys in both with a different value — `(key, old_value, new_value)`.
    pub changed: Vec<(Vec<u8>, Vec<u8>, Vec<u8>)>,
}

impl ProllyDiff {
    /// True when the two roots hold the same set of entries.
    pub fn is_empty(&self) -> bool {
        self.added.is_empty() && self.removed.is_empty() && self.changed.is_empty()
    }

    /// Total number of differing entries.
    pub fn len(&self) -> usize {
        self.added.len() + self.removed.len() + self.changed.len()
    }
}

#[derive(Debug, Default)]
pub struct ProllyTree {
    pub root: Option<KotobaCid>,
    nodes: BTreeMap<KotobaCid, ProllyNode>,
}

impl ProllyTree {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn root_cid(&self) -> Option<&KotobaCid> {
        self.root.as_ref()
    }

    /// Diff two roots at leaf-block granularity → `(leaves_only_in_a, leaves_only_in_b)`.
    ///
    /// Both leaf lists are gathered by walking *internal* nodes only (the leaves
    /// themselves are never loaded), then any leaf CID that appears in BOTH trees
    /// is dropped — unchanged leaves share a CID (content addressing), so they
    /// cancel.  Cost is `O(#internal nodes)` block loads, independent of how many
    /// entries the leaves hold; identical subtrees are pruned by the shared-CID
    /// cancellation.  Returns the differing leaf CIDs (useful for replication:
    /// "ship these blocks").  For an entry-level diff use [`Self::diff_entries`].
    pub fn diff(
        a_root: &KotobaCid,
        b_root: &KotobaCid,
        store: &dyn BlockStore,
    ) -> anyhow::Result<(Vec<KotobaCid>, Vec<KotobaCid>)> {
        if a_root == b_root {
            return Ok((vec![], vec![]));
        }
        let a_leaves = Self::list_leaves(a_root, store)?;
        let b_leaves = Self::list_leaves(b_root, store)?;
        let a_set: std::collections::HashSet<&KotobaCid> =
            a_leaves.iter().map(|(_, c)| c).collect();
        let b_set: std::collections::HashSet<&KotobaCid> =
            b_leaves.iter().map(|(_, c)| c).collect();
        let only_a = a_leaves
            .iter()
            .filter(|(_, c)| !b_set.contains(c))
            .map(|(_, c)| c.clone())
            .collect();
        let only_b = b_leaves
            .iter()
            .filter(|(_, c)| !a_set.contains(c))
            .map(|(_, c)| c.clone())
            .collect();
        Ok((only_a, only_b))
    }

    /// List every leaf in the tree as `(max_key, leaf_cid)` in ascending key
    /// order, descending only through `Internal` nodes (leaves are never loaded).
    ///
    /// Cost: `O(#internal nodes)` block loads.  Used by [`Self::diff`] /
    /// [`Self::diff_entries`] for CID-level pruning and by the incremental
    /// [`Self::apply_batch`] to rebuild the internal spine without re-reading
    /// every entry.
    pub fn list_leaves(
        root: &KotobaCid,
        store: &dyn BlockStore,
    ) -> anyhow::Result<Vec<(Vec<u8>, KotobaCid)>> {
        let mut out = Vec::new();
        Self::list_leaves_inner(root, store, &mut out)?;
        Ok(out)
    }

    fn list_leaves_inner(
        node_cid: &KotobaCid,
        store: &dyn BlockStore,
        out: &mut Vec<(Vec<u8>, KotobaCid)>,
    ) -> anyhow::Result<()> {
        let Some(node) = Self::load_node(node_cid, store)? else {
            return Ok(());
        };
        match node {
            ProllyNode::Leaf { entries, .. } => {
                // Only reached when the whole tree is a single leaf.
                let max_key = entries.last().map(|(k, _)| k.clone()).unwrap_or_default();
                out.push((max_key, node_cid.clone()));
            }
            ProllyNode::Internal { children, .. } => {
                // All children of an Internal node sit at the same depth (Prolly
                // leaves are level-aligned), so one peek tells us whether this is
                // the bottom internal level.  If so, emit each child's
                // (max_key, leaf_cid) straight from this node — the leaves
                // themselves are never loaded, keeping listing O(#internal nodes)
                // instead of O(#leaves).
                let children_are_leaves = match children.first() {
                    Some((_, first_cid)) => {
                        matches!(
                            Self::load_node(first_cid, store)?,
                            Some(ProllyNode::Leaf { .. })
                        )
                    }
                    None => false,
                };
                if children_are_leaves {
                    out.extend(children);
                } else {
                    for (_, child_cid) in children {
                        Self::list_leaves_inner(&child_cid, store, out)?;
                    }
                }
            }
        }
        Ok(())
    }

    /// Entry-level diff of two roots → added / removed / changed.
    ///
    /// `a` is the *before* tree, `b` the *after*.  Identical leaves (same CID in
    /// both trees) are never loaded, so the cost is proportional to the size of
    /// the **differing** leaves plus the `O(#internal nodes)` leaf listing — the
    /// `O(|diff|)` behaviour that makes db-before/after, branch/merge and
    /// replication-by-diff cheap on a content-addressed store.
    pub fn diff_entries(
        a_root: &KotobaCid,
        b_root: &KotobaCid,
        store: &dyn BlockStore,
    ) -> anyhow::Result<ProllyDiff> {
        let mut diff = ProllyDiff::default();
        if a_root == b_root {
            return Ok(diff);
        }
        let a_leaves = Self::list_leaves(a_root, store)?;
        let b_leaves = Self::list_leaves(b_root, store)?;
        let a_set: std::collections::HashSet<KotobaCid> =
            a_leaves.iter().map(|(_, c)| c.clone()).collect();
        let b_set: std::collections::HashSet<KotobaCid> =
            b_leaves.iter().map(|(_, c)| c.clone()).collect();

        // Load only the leaves unique to each side; their entries, concatenated
        // in leaf order, are globally sorted (leaf ranges are ordered + disjoint).
        let a_entries = Self::collect_leaf_entries(
            a_leaves
                .iter()
                .filter(|(_, c)| !b_set.contains(c))
                .map(|(_, c)| c),
            store,
        )?;
        let b_entries = Self::collect_leaf_entries(
            b_leaves
                .iter()
                .filter(|(_, c)| !a_set.contains(c))
                .map(|(_, c)| c),
            store,
        )?;

        // Merge-compare two sorted (key, value) streams.
        let (mut i, mut j) = (0usize, 0usize);
        while i < a_entries.len() && j < b_entries.len() {
            let (ka, va) = &a_entries[i];
            let (kb, vb) = &b_entries[j];
            match ka.cmp(kb) {
                std::cmp::Ordering::Less => {
                    diff.removed.push((ka.clone(), va.clone()));
                    i += 1;
                }
                std::cmp::Ordering::Greater => {
                    diff.added.push((kb.clone(), vb.clone()));
                    j += 1;
                }
                std::cmp::Ordering::Equal => {
                    if va != vb {
                        diff.changed.push((ka.clone(), va.clone(), vb.clone()));
                    }
                    i += 1;
                    j += 1;
                }
            }
        }
        for (k, v) in &a_entries[i..] {
            diff.removed.push((k.clone(), v.clone()));
        }
        for (k, v) in &b_entries[j..] {
            diff.added.push((k.clone(), v.clone()));
        }
        Ok(diff)
    }

    fn collect_leaf_entries<'a, I>(
        leaf_cids: I,
        store: &dyn BlockStore,
    ) -> anyhow::Result<Vec<(Vec<u8>, Vec<u8>)>>
    where
        I: Iterator<Item = &'a KotobaCid>,
    {
        let mut out = Vec::new();
        for cid in leaf_cids {
            if let Some(ProllyNode::Leaf { entries, .. }) = Self::load_node(cid, store)? {
                out.extend(entries);
            }
        }
        Ok(out)
    }

    /// Serialize a node to **canonical DAG-CBOR** (tag-42 CID links) and write it
    /// to the block store. Returns the node's CID = `sha2-256(dag-cbor-bytes)`
    /// (CIDv1, codec dag-cbor) — a genuine IPLD link (ADR-2606022150 D1). The
    /// self-CID field is excluded from the encoded block (it is the block's hash).
    pub fn put_node(node: &ProllyNode, store: &dyn BlockStore) -> anyhow::Result<KotobaCid> {
        let dag = ProllyNodeDag::from_node(node)?;
        let buf = serde_ipld_dagcbor::to_vec(&dag)
            .map_err(|e| anyhow::anyhow!("dag-cbor encode: {e}"))?;
        let cid = KotobaCid::from_bytes(&buf);
        store.put(&cid, &buf)?;
        Ok(cid)
    }

    /// Load a ProllyNode from the block store by CID, decoding the DAG-CBOR block
    /// and restoring the node's own CID from the lookup key.
    pub fn load_node(
        cid: &KotobaCid,
        store: &dyn BlockStore,
    ) -> anyhow::Result<Option<ProllyNode>> {
        match store.get(cid)? {
            None => Ok(None),
            Some(bytes) => {
                let dag: ProllyNodeDag = serde_ipld_dagcbor::from_slice(&bytes)
                    .map_err(|e| anyhow::anyhow!("dag-cbor decode: {e}"))?;
                Ok(Some(dag.into_node(cid.clone())?))
            }
        }
    }

    /// Walk the ProllyTree from `root` and return all referenced block CIDs (root inclusive).
    ///
    /// Recursively follows all `Internal` node children.  Leaf entries are not followed
    /// (their values are opaque bytes, not CID references).  Used by GC to compute the
    /// live set reachable from a commit's ProllyTree roots.
    pub fn walk_all_cids(
        root: &KotobaCid,
        store: &dyn BlockStore,
    ) -> anyhow::Result<Vec<KotobaCid>> {
        let mut out = vec![root.clone()];
        let Some(node) = Self::load_node(root, store)? else {
            return Ok(out);
        };
        if let ProllyNode::Internal { children, .. } = node {
            for (_, child_cid) in children {
                out.extend(Self::walk_all_cids(&child_cid, store)?);
            }
        }
        Ok(out)
    }

    /// Flush all in-memory nodes to the block store.
    /// Returns the root CID if the tree has a root.
    pub fn flush(&self, store: &dyn BlockStore) -> anyhow::Result<Option<KotobaCid>> {
        for node in self.nodes.values() {
            Self::put_node(node, store)?;
        }
        Ok(self.root.clone())
    }

    /// Build a complete ProllyTree from a flat entry list, writing every
    /// node to `store`.  Returns the root CID.
    ///
    /// Algorithm (single-pass bottom-up):
    ///   1. Sort entries by key.
    ///   2. Split into Leaf chunks at probabilistic boundaries
    ///      (`is_boundary` fires ~1/256 of the time with BOUNDARY_MASK=0xFF,
    ///      giving chunks of ~256 entries on average).
    ///   3. Persist each Leaf; collect (max_key, leaf_cid) pairs.
    ///   4. If >1 leaf, recursively build Internal levels until a single root
    ///      remains — each level applies the same boundary split to child keys.
    pub fn build_tree(
        entries: Vec<(Vec<u8>, Vec<u8>)>,
        store: &dyn BlockStore,
    ) -> anyhow::Result<KotobaCid> {
        if entries.is_empty() {
            let leaf = ProllyNode::Leaf {
                entries: vec![],
                cid: KotobaCid::default(),
            };
            return Self::put_node(&leaf, store);
        }

        let mut sorted = entries;
        sorted.sort_unstable_by(|a, b| a.0.cmp(&b.0));

        let leaf_ptrs = Self::build_leaf_level(sorted, store)?;
        if leaf_ptrs.len() == 1 {
            return Ok(leaf_ptrs.into_iter().next().unwrap().1);
        }
        Self::build_internal_level(leaf_ptrs, store)
    }

    /// Incrementally apply a batch of `upserts` and `deletes` to the tree rooted
    /// at `prev_root`, writing **only the blocks that actually change**, and
    /// return the new root CID.
    ///
    /// This is the path-copying counterpart to [`Self::build_tree`]: instead of
    /// re-reading and re-chunking every entry, it
    ///   1. lists the previous leaf pointers (`O(#internal nodes)` loads),
    ///   2. loads + re-chunks only the leaves a batch key routes into (handling
    ///      boundary-key splits and boundary-delete merges locally), keeping
    ///      every untouched leaf's CID verbatim, then
    ///   3. rebuilds the internal spine over the (mostly unchanged) pointer list.
    ///
    /// Because leaf membership is a pure function of the key set
    /// (`is_boundary(key)`), the result is **bit-for-bit identical** to
    /// `build_tree` over the same final entries — same root CID — so it composes
    /// with content-addressed dedup, [`Self::diff`] and replication.
    ///
    /// `deletes` are applied after `upserts`; an upsert of a key also present in
    /// `deletes` wins (the key survives).  `prev_root = None` (or an empty tree)
    /// degrades to `build_tree(upserts)`.
    pub fn apply_batch(
        prev_root: Option<&KotobaCid>,
        upserts: Vec<(Vec<u8>, Vec<u8>)>,
        deletes: Vec<Vec<u8>>,
        store: &dyn BlockStore,
    ) -> anyhow::Result<KotobaCid> {
        // Coalesce the batch: last-writer-wins on upserts; an upsert shadows a
        // delete of the same key.
        let mut up: BTreeMap<Vec<u8>, Vec<u8>> = BTreeMap::new();
        for (k, v) in upserts {
            up.insert(k, v);
        }
        let mut del: std::collections::BTreeSet<Vec<u8>> = std::collections::BTreeSet::new();
        for k in deletes {
            if !up.contains_key(&k) {
                del.insert(k);
            }
        }

        // No previous tree → plain build (deletes are vacuous).
        let Some(prev_root) = prev_root else {
            return Self::build_tree(up.into_iter().collect(), store);
        };

        let leaves = Self::list_leaves(prev_root, store)?;
        // Empty / sentinel tree → plain build.
        let is_empty_prev = leaves.is_empty()
            || (leaves.len() == 1 && {
                matches!(
                    Self::load_node(&leaves[0].1, store)?,
                    Some(ProllyNode::Leaf { ref entries, .. }) if entries.is_empty()
                )
            });
        if is_empty_prev {
            return Self::build_tree(up.into_iter().collect(), store);
        }
        if up.is_empty() && del.is_empty() {
            return Ok(prev_root.clone());
        }

        let n = leaves.len();
        // Route each batch key to the leaf index that owns its key range:
        // the first leaf whose max_key >= key, else the trailing leaf.
        let route = |key: &[u8]| -> usize {
            let idx = leaves.partition_point(|(mk, _)| mk.as_slice() < key);
            if idx >= n {
                n - 1
            } else {
                idx
            }
        };
        let mut touched = vec![false; n];
        for k in up.keys().chain(del.iter()) {
            touched[route(k)] = true;
        }

        // Left-to-right sweep: copy untouched leaves verbatim, re-chunk touched
        // runs (growing forward when a boundary-key deletion dissolves a seam).
        let mut result_ptrs: Vec<(Vec<u8>, KotobaCid)> = Vec::new();
        let mut i = 0usize;
        while i < n {
            if !touched[i] {
                result_ptrs.push(leaves[i].clone());
                i += 1;
                continue;
            }
            // Gather the maximal run of consecutive touched leaves.
            let lo = i;
            let mut hi = i;
            while hi + 1 < n && touched[hi + 1] {
                hi += 1;
            }
            // Region entry map = all entries of leaves[lo..=hi].
            let mut region: BTreeMap<Vec<u8>, Vec<u8>> = BTreeMap::new();
            for leaf_ptr in &leaves[lo..=hi] {
                if let Some(ProllyNode::Leaf { entries, .. }) = Self::load_node(&leaf_ptr.1, store)?
                {
                    region.extend(entries);
                }
            }
            // Apply edits routed into this run.
            for (k, v) in up.iter().filter(|(k, _)| {
                let r = route(k);
                r >= lo && r <= hi
            }) {
                region.insert(k.clone(), v.clone());
            }
            for k in del.iter().filter(|k| {
                let r = route(k);
                r >= lo && r <= hi
            }) {
                region.remove(k);
            }
            // Forward-merge: if the region no longer terminates on a boundary key
            // (e.g. its boundary terminator was deleted) and a following leaf
            // exists, absorb the next leaf so the seam re-forms correctly.
            while hi + 1 < n {
                let terminates_on_boundary = region
                    .keys()
                    .next_back()
                    .map(|k| ProllyNode::is_boundary(k))
                    .unwrap_or(false);
                if terminates_on_boundary || region.is_empty() {
                    break;
                }
                hi += 1;
                if let Some(ProllyNode::Leaf { entries, .. }) =
                    Self::load_node(&leaves[hi].1, store)?
                {
                    region.extend(entries);
                }
            }
            // Re-chunk the region with the canonical boundary rule.
            let region_entries: Vec<(Vec<u8>, Vec<u8>)> = region.into_iter().collect();
            let region_ptrs = Self::build_leaf_level(region_entries, store)?;
            result_ptrs.extend(region_ptrs);
            i = hi + 1;
        }

        // Rebuild the spine (mirrors build_tree's tail).
        if result_ptrs.is_empty() {
            let leaf = ProllyNode::Leaf {
                entries: vec![],
                cid: KotobaCid::default(),
            };
            return Self::put_node(&leaf, store);
        }
        if result_ptrs.len() == 1 {
            return Ok(result_ptrs.into_iter().next().unwrap().1);
        }
        Self::build_internal_level(result_ptrs, store)
    }

    fn build_leaf_level(
        entries: Vec<(Vec<u8>, Vec<u8>)>,
        store: &dyn BlockStore,
    ) -> anyhow::Result<Vec<(Vec<u8>, KotobaCid)>> {
        let mut ptrs: Vec<(Vec<u8>, KotobaCid)> = Vec::new();
        let mut chunk: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();

        for entry in entries {
            let at_boundary = ProllyNode::is_boundary(&entry.0);
            chunk.push(entry);
            if at_boundary {
                let max_key = chunk.last().unwrap().0.clone();
                let leaf = ProllyNode::Leaf {
                    entries: std::mem::take(&mut chunk),
                    cid: KotobaCid::default(),
                };
                let cid = Self::put_node(&leaf, store)?;
                ptrs.push((max_key, cid));
            }
        }
        if !chunk.is_empty() {
            let max_key = chunk.last().unwrap().0.clone();
            let leaf = ProllyNode::Leaf {
                entries: chunk,
                cid: KotobaCid::default(),
            };
            let cid = Self::put_node(&leaf, store)?;
            ptrs.push((max_key, cid));
        }
        Ok(ptrs)
    }

    /// Point-query: look up `key` in the ProllyTree rooted at `root_cid`.
    ///
    /// Each tree level requires one `store.get()` call — on a cold BlockStore
    /// (IPFS / S3) this multiplies the network RTT by the tree depth.
    /// With ~256-entry leaves, depth = ceil(log256(N)):
    ///   - 1K entries  → 1–2 levels → 1–2 RTTs
    ///   - 1M entries  → 3–4 levels → 3–4 RTTs
    ///   - 1B entries  → 5–6 levels → 5–6 RTTs
    ///
    /// Returns `None` if the key is not found.
    pub fn get(
        root: &KotobaCid,
        key: &[u8],
        store: &dyn BlockStore,
    ) -> anyhow::Result<Option<Vec<u8>>> {
        let Some(node) = Self::load_node(root, store)? else {
            return Ok(None);
        };
        match node {
            ProllyNode::Leaf { entries, .. } => Ok(entries
                .into_iter()
                .find(|(k, _)| k.as_slice() == key)
                .map(|(_, v)| v)),
            ProllyNode::Internal { children, .. } => {
                // Find the first child whose max_key >= key, then recurse.
                let child_cid = children
                    .into_iter()
                    .find(|(max_key, _)| max_key.as_slice() >= key)
                    .map(|(_, cid)| cid);
                match child_cid {
                    Some(cid) => Self::get(&cid, key, store),
                    None => Ok(None),
                }
            }
        }
    }

    /// Return all `(key, value)` pairs whose key starts with `prefix`.
    ///
    /// Because the ProllyTree is lexicographically sorted, all matching entries
    /// are contiguous. Traversal skips subtrees whose max_key precedes `prefix`
    /// and stops as soon as a subtree's entries no longer start with `prefix`.
    ///
    /// Cost: O(log N + M) block loads, where M = number of matching leaf entries.
    pub fn scan_prefix(
        root: &KotobaCid,
        prefix: &[u8],
        store: &dyn BlockStore,
    ) -> anyhow::Result<Vec<(Vec<u8>, Vec<u8>)>> {
        let Some(node) = Self::load_node(root, store)? else {
            return Ok(vec![]);
        };
        match node {
            ProllyNode::Leaf { entries, .. } => Ok(entries
                .into_iter()
                .filter(|(k, _)| k.starts_with(prefix))
                .collect()),
            ProllyNode::Internal { children, .. } => {
                // Matching keys live in the contiguous range [prefix, upper),
                // where `upper` is the first key lexicographically after every
                // key with this prefix.  Child i covers `(prev_max, max_key_i]`,
                // so it can overlap the prefix range iff `max_key_i >= prefix`
                // AND `prev_max < upper`.  Once `prev_max >= upper` no later child
                // can match → stop.  This bounds an absent/sparse prefix to a
                // single root-to-leaf path instead of scanning the whole tail.
                let upper = Self::prefix_upper_bound(prefix);
                let mut result = Vec::new();
                let mut prev_max: Option<Vec<u8>> = None;
                for (max_key, child_cid) in children {
                    if max_key.as_slice() < prefix {
                        prev_max = Some(max_key);
                        continue;
                    }
                    if let (Some(pm), Some(up)) = (prev_max.as_ref(), upper.as_ref()) {
                        if pm.as_slice() >= up.as_slice() {
                            break;
                        }
                    }
                    result.extend(Self::scan_prefix(&child_cid, prefix, store)?);
                    prev_max = Some(max_key);
                }
                Ok(result)
            }
        }
    }

    /// Smallest byte string strictly greater than every string starting with
    /// `prefix` (the exclusive upper bound of the prefix range).  `None` when no
    /// such bound exists (empty prefix, or all-`0xFF` prefix) → range is open to
    /// the end of the key space.
    fn prefix_upper_bound(prefix: &[u8]) -> Option<Vec<u8>> {
        let mut up = prefix.to_vec();
        while let Some(&b) = up.last() {
            if b < 0xFF {
                *up.last_mut().unwrap() = b + 1;
                return Some(up);
            }
            up.pop();
        }
        None
    }

    /// Return all `(key, value)` pairs whose key is greater than or equal to `start`.
    ///
    /// This is the ordered-tree primitive behind Datomic-style `seek-datoms`.
    /// Traversal skips subtrees whose max key is still before the seek key, then
    /// streams the remaining leaves in index order.
    pub fn scan_from(
        root: &KotobaCid,
        start: &[u8],
        store: &dyn BlockStore,
    ) -> anyhow::Result<Vec<(Vec<u8>, Vec<u8>)>> {
        let Some(node) = Self::load_node(root, store)? else {
            return Ok(vec![]);
        };
        match node {
            ProllyNode::Leaf { entries, .. } => Ok(entries
                .into_iter()
                .filter(|(k, _)| k.as_slice() >= start)
                .collect()),
            ProllyNode::Internal { children, .. } => {
                let mut result = Vec::new();
                for (max_key, child_cid) in children {
                    if max_key.as_slice() < start {
                        continue;
                    }
                    result.extend(Self::scan_from(&child_cid, start, store)?);
                }
                Ok(result)
            }
        }
    }

    fn build_internal_level(
        children: Vec<(Vec<u8>, KotobaCid)>,
        store: &dyn BlockStore,
    ) -> anyhow::Result<KotobaCid> {
        let mut ptrs: Vec<(Vec<u8>, KotobaCid)> = Vec::new();
        let mut chunk: Vec<(Vec<u8>, KotobaCid)> = Vec::new();

        for child in children {
            // Use the child CID (not the max key) to determine internal-level
            // boundaries.  The key would cause infinite recursion because the
            // same key keeps triggering the boundary check at every level.
            // The CID changes at each level (it's the hash of node content), so
            // the boundary condition will not repeat indefinitely.
            let at_boundary = ProllyNode::is_boundary(&child.1 .0);
            chunk.push(child);
            if at_boundary {
                let max_key = chunk.last().unwrap().0.clone();
                let node = ProllyNode::Internal {
                    children: std::mem::take(&mut chunk),
                    cid: KotobaCid::default(),
                };
                let cid = Self::put_node(&node, store)?;
                ptrs.push((max_key, cid));
            }
        }
        if !chunk.is_empty() {
            let max_key = chunk.last().unwrap().0.clone();
            let node = ProllyNode::Internal {
                children: chunk,
                cid: KotobaCid::default(),
            };
            let cid = Self::put_node(&node, store)?;
            ptrs.push((max_key, cid));
        }

        if ptrs.len() == 1 {
            return Ok(ptrs.into_iter().next().unwrap().1);
        }
        // Another level needed — ptrs.len() >= 2; CID-based boundaries
        // guarantee convergence because CIDs change each time nodes are rebuilt.
        Self::build_internal_level(ptrs, store)
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
            Self {
                blocks: Arc::new(RwLock::new(HashMap::new())),
            }
        }
        fn block_count(&self) -> usize {
            self.blocks.read().unwrap().len()
        }
    }

    impl BlockStore for MemoryBlockStore {
        fn put(&self, cid: &KotobaCid, data: &[u8]) -> anyhow::Result<()> {
            self.blocks
                .write()
                .unwrap()
                .insert(cid.0, Bytes::copy_from_slice(data));
            Ok(())
        }
        fn get(&self, cid: &KotobaCid) -> anyhow::Result<Option<Bytes>> {
            Ok(self.blocks.read().unwrap().get(&cid.0).cloned())
        }
        fn has(&self, cid: &KotobaCid) -> bool {
            self.blocks.read().unwrap().contains_key(&cid.0)
        }
    }

    /// blake3 vs sha2-256 at the ProllyTree boundary-hot-path granularity.
    /// `is_boundary` runs `blake3::hash(key)` once per entry during every
    /// build_tree; this measures the cost of swapping it to sha2-256.
    /// Run: `cargo test -p kotoba-core hash_blake3_vs_sha256_boundary --release -- --ignored --nocapture`
    #[test]
    #[ignore]
    fn hash_blake3_vs_sha256_boundary() {
        use sha2::{Digest, Sha256};
        use std::time::Instant;

        // Representative ProllyTree keys: ~48B eavt index keys + 36B child CIDs.
        let keys: Vec<Vec<u8>> = (0u32..100_000)
            .map(|i| {
                let mut k = Vec::with_capacity(48);
                k.extend_from_slice(b"eavt:");
                k.extend_from_slice(&i.to_be_bytes());
                k.extend_from_slice(&[0xab; 39]);
                k
            })
            .collect();
        let rounds = 20;

        // Warm + measure blake3 (current).
        let mut acc = 0u64;
        let t = Instant::now();
        for _ in 0..rounds {
            for k in &keys {
                let h = blake3::hash(k);
                acc ^= u32::from_be_bytes(h.as_bytes()[0..4].try_into().unwrap()) as u64;
            }
        }
        let blake3_ns = t.elapsed().as_nanos() as f64 / (rounds * keys.len()) as f64;

        // Measure sha2-256 (candidate).
        let t = Instant::now();
        for _ in 0..rounds {
            for k in &keys {
                let d = Sha256::digest(k);
                acc ^= u32::from_be_bytes(d[0..4].try_into().unwrap()) as u64;
            }
        }
        let sha_ns = t.elapsed().as_nanos() as f64 / (rounds * keys.len()) as f64;

        // Full build_tree cost (blake3 boundary) over 100k entries, to size the
        // hash portion against total tree-build work.
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> =
            keys.iter().map(|k| (k.clone(), b"v".to_vec())).collect();
        let t = Instant::now();
        let _root = ProllyTree::build_tree(entries, &store).unwrap();
        let build_ms = t.elapsed().as_millis();

        eprintln!("\n── ProllyTree boundary hash: blake3 vs sha2-256 (per key, ~48B) ──");
        eprintln!("blake3      : {blake3_ns:.1} ns/hash");
        eprintln!(
            "sha2-256    : {sha_ns:.1} ns/hash   ({:.2}x blake3)",
            sha_ns / blake3_ns
        );
        eprintln!("build_tree(100k, blake3): {build_ms} ms total");
        eprintln!(
            "est. boundary-hash share of build_tree: blake3≈{:.0}ms  sha256≈{:.0}ms  (Δ≈{:.0}ms/100k entries)",
            blake3_ns * 100_000.0 / 1e6,
            sha_ns * 100_000.0 / 1e6,
            (sha_ns - blake3_ns) * 100_000.0 / 1e6
        );
        eprintln!("(acc={acc})");
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

    // ── ADR-2606022150 D1: blocks are genuine DAG-CBOR with tag-42 CID links ──

    /// An `Internal` node's encoded block must carry its child links as **IPLD
    /// CID tag-42** (CBOR major-7 tag 42 = bytes `0xD8 0x2A`), not the old raw
    /// `[u8;36]` byte array. This is the difference between a real IPLD DAG (any
    /// dag-cbor tool can walk it) and dag-cbor-in-name-only.
    #[test]
    fn internal_node_block_encodes_cid_links_as_tag42() {
        let store = MemoryBlockStore::new();
        // Two real child blocks → two CIDv1 dag-cbor links in the parent.
        let child_a = ProllyTree::put_node(
            &ProllyNode::Leaf {
                entries: vec![(b"a".to_vec(), b"1".to_vec())],
                cid: KotobaCid::from_bytes(b"x"),
            },
            &store,
        )
        .unwrap();
        let child_b = ProllyTree::put_node(
            &ProllyNode::Leaf {
                entries: vec![(b"b".to_vec(), b"2".to_vec())],
                cid: KotobaCid::from_bytes(b"x"),
            },
            &store,
        )
        .unwrap();
        let parent = ProllyNode::Internal {
            children: vec![
                (b"a".to_vec(), child_a.clone()),
                (b"b".to_vec(), child_b.clone()),
            ],
            cid: KotobaCid::from_bytes(b"x"),
        };
        let parent_cid = ProllyTree::put_node(&parent, &store).unwrap();

        // Inspect the RAW block bytes the store holds.
        let raw = store.get(&parent_cid).unwrap().unwrap();
        // CBOR tag 42 prefix appears once per child link.
        let tag42 = raw.windows(2).filter(|w| w == b"\xd8\x2a").count();
        assert_eq!(
            tag42, 2,
            "two children → two tag-42 CID links in the DAG-CBOR block"
        );

        // And the canonical tag-42 payload is `0x00 || cid-bytes` (multibase
        // identity prefix), so each child's 36 CID bytes appear verbatim.
        assert!(
            raw.windows(36).any(|w| w == child_a.0),
            "child_a CID bytes present in block"
        );
        assert!(
            raw.windows(36).any(|w| w == child_b.0),
            "child_b CID bytes present in block"
        );

        // Round-trips back to the same KotobaCid links.
        match ProllyTree::load_node(&parent_cid, &store).unwrap().unwrap() {
            ProllyNode::Internal { children, .. } => {
                assert_eq!(children[0].1, child_a);
                assert_eq!(children[1].1, child_b);
            }
            _ => panic!("expected internal"),
        }
    }

    /// The node CID is `sha2-256(dag-cbor)` and deterministic: identical content
    /// → identical CID (content addressing), and the self-CID field is excluded
    /// from the block (so it can't perturb the hash).
    #[test]
    fn dagcbor_node_cid_is_deterministic_and_self_cid_excluded() {
        let store = MemoryBlockStore::new();
        let mk = |self_cid: &[u8]| ProllyNode::Leaf {
            entries: vec![(b"k".to_vec(), b"v".to_vec())],
            cid: KotobaCid::from_bytes(self_cid),
        };
        // Same entries, DIFFERENT bogus self-cid → same block CID (self-cid not encoded).
        let c1 = ProllyTree::put_node(&mk(b"self-one"), &store).unwrap();
        let c2 = ProllyTree::put_node(&mk(b"self-two"), &store).unwrap();
        assert_eq!(
            c1, c2,
            "self-CID field must not affect the content-addressed block"
        );
        // The CID is a valid CIDv1 dag-cbor sha2-256 link.
        assert!(c1.is_ipfs_compatible());
        assert!(c1.to_standard_cid().is_ok());
    }

    // ── regression: build_internal_level must use CID not max_key ────────────
    //
    // Before the fix, build_internal_level called is_boundary(&child.0) — the
    // same max_key that fired the boundary at leaf level.  That key would fire
    // again at every recursive call → unbounded recursion → stack overflow.
    //
    // Any test that builds a tree large enough to produce ≥2 leaf chunks will
    // fail with a stack overflow if the regression is reintroduced.

    /// Regression: build_tree must terminate for 1K entries.
    /// With BOUNDARY_MASK=0xFF (1/256 rate) and 1K entries, ~4 boundary keys
    /// appear, producing multiple leaf chunks and triggering build_internal_level.
    /// Before the fix this overflowed the stack; after the fix it completes.
    #[test]
    fn build_tree_1k_terminates_and_get_works() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0u64..1_000)
            .map(|i| (i.to_le_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(entries, &store).unwrap();

        // A key in the middle must be found.
        let key = 500u64.to_le_bytes().to_vec();
        let val = ProllyTree::get(&root, &key, &store).unwrap();
        assert_eq!(val.as_deref(), Some(b"v500".as_ref()));

        // First and last key.
        let v0 = ProllyTree::get(&root, &0u64.to_le_bytes(), &store).unwrap();
        assert_eq!(v0.as_deref(), Some(b"v0".as_ref()));
        let v999 = ProllyTree::get(&root, &999u64.to_le_bytes(), &store).unwrap();
        assert_eq!(v999.as_deref(), Some(b"v999".as_ref()));
    }

    /// Regression: larger tree (10K entries) must also terminate.
    #[test]
    fn build_tree_10k_terminates() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0u64..10_000)
            .map(|i| (i.to_le_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(entries, &store).unwrap();
        let val = ProllyTree::get(&root, &5_000u64.to_le_bytes(), &store).unwrap();
        assert_eq!(val.as_deref(), Some(b"v5000".as_ref()));
    }

    /// Missing key returns None (does not panic or recurse).
    #[test]
    fn build_tree_get_missing_key() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0u64..100)
            .map(|i| (i.to_le_bytes().to_vec(), b"x".to_vec()))
            .collect();
        let root = ProllyTree::build_tree(entries, &store).unwrap();
        let val = ProllyTree::get(&root, &999u64.to_le_bytes(), &store).unwrap();
        assert!(val.is_none());
    }

    /// Single entry: tree = just one leaf node; get must still work.
    #[test]
    fn build_tree_single_entry() {
        let store = MemoryBlockStore::new();
        let entries = vec![(b"only".to_vec(), b"value".to_vec())];
        let root = ProllyTree::build_tree(entries, &store).unwrap();
        let val = ProllyTree::get(&root, b"only", &store).unwrap();
        assert_eq!(val.as_deref(), Some(b"value".as_ref()));
        let none = ProllyTree::get(&root, b"other", &store).unwrap();
        assert!(none.is_none());
    }

    // ─────────────────────────────────────────────────────────────────────────

    #[test]
    fn flush_empty_tree_returns_none() {
        let store = MemoryBlockStore::new();
        let tree = ProllyTree::new();
        let root = tree.flush(&store).unwrap();
        assert!(root.is_none());
        assert_eq!(store.block_count(), 0);
    }

    // ── scan_prefix ──────────────────────────────────────────────────────────

    /// scan_prefix returns all entries whose key starts with the given prefix.
    #[test]
    fn scan_prefix_returns_matching_entries() {
        let store = MemoryBlockStore::new();
        // Keys: "alice:name", "alice:knows", "bob:name", "charlie:name"
        let entries: Vec<(Vec<u8>, Vec<u8>)> = vec![
            (b"alice:knows".to_vec(), b"bob".to_vec()),
            (b"alice:name".to_vec(), b"Alice".to_vec()),
            (b"bob:name".to_vec(), b"Bob".to_vec()),
            (b"charlie:name".to_vec(), b"Charlie".to_vec()),
        ];
        let root = ProllyTree::build_tree(entries, &store).unwrap();

        let matches = ProllyTree::scan_prefix(&root, b"alice:", &store).unwrap();
        assert_eq!(matches.len(), 2, "expected 2 entries for alice prefix");
        let keys: std::collections::HashSet<Vec<u8>> =
            matches.iter().map(|(k, _)| k.clone()).collect();
        assert!(
            keys.contains(b"alice:knows".as_ref() as &[u8]),
            "alice:knows must be found"
        );
        assert!(
            keys.contains(b"alice:name".as_ref() as &[u8]),
            "alice:name must be found"
        );
    }

    /// scan_prefix with no matching entries returns empty vec.
    #[test]
    fn scan_prefix_empty_result_for_absent_prefix() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0u64..100)
            .map(|i| (format!("x{i:04}").into_bytes(), b"v".to_vec()))
            .collect();
        let root = ProllyTree::build_tree(entries, &store).unwrap();
        let matches = ProllyTree::scan_prefix(&root, b"zzz", &store).unwrap();
        assert!(matches.is_empty(), "no entries should match absent prefix");
    }

    /// scan_prefix on a larger tree (1K entries) terminates and finds correct entries.
    #[test]
    fn scan_prefix_larger_tree() {
        let store = MemoryBlockStore::new();
        // prefix "b" entries: "b000".."b049" (50 entries) interleaved with "a*" and "c*"
        let mut entries: Vec<(Vec<u8>, Vec<u8>)> = Vec::new();
        for i in 0u32..500 {
            entries.push((format!("a{i:04}").into_bytes(), b"va".to_vec()));
        }
        for i in 0u32..50 {
            entries.push((format!("b{i:04}").into_bytes(), b"vb".to_vec()));
        }
        for i in 0u32..450 {
            entries.push((format!("c{i:04}").into_bytes(), b"vc".to_vec()));
        }
        entries.sort_unstable_by(|(a, _), (b, _)| a.cmp(b));
        let root = ProllyTree::build_tree(entries, &store).unwrap();

        let matches = ProllyTree::scan_prefix(&root, b"b", &store).unwrap();
        assert_eq!(matches.len(), 50, "expected 50 'b' entries");
        assert!(matches.iter().all(|(k, _)| k.starts_with(b"b")));
    }

    // ── scan_from ─────────────────────────────────────────────────────────────

    #[test]
    fn scan_from_returns_ordered_entries_at_or_after_start() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = ["a001", "a002", "b001", "b002", "c001"]
            .into_iter()
            .map(|key| (key.as_bytes().to_vec(), format!("v-{key}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(entries, &store).unwrap();

        let matches = ProllyTree::scan_from(&root, b"b001", &store).unwrap();
        let keys = matches
            .into_iter()
            .map(|(key, _)| String::from_utf8(key).unwrap())
            .collect::<Vec<_>>();
        assert_eq!(keys, vec!["b001", "b002", "c001"]);
    }

    #[test]
    fn scan_from_larger_tree_skips_subtrees_before_start() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0u32..1_000)
            .map(|i| {
                (
                    format!("k{i:04}").into_bytes(),
                    format!("v{i}").into_bytes(),
                )
            })
            .collect();
        let root = ProllyTree::build_tree(entries, &store).unwrap();

        let matches = ProllyTree::scan_from(&root, b"k0995", &store).unwrap();
        let keys = matches
            .into_iter()
            .map(|(key, _)| String::from_utf8(key).unwrap())
            .collect::<Vec<_>>();
        assert_eq!(keys, vec!["k0995", "k0996", "k0997", "k0998", "k0999"]);
    }

    // ── additional gap tests ──────────────────────────────────────────────────

    #[test]
    fn prolly_node_cid_accessor_leaf() {
        let expected_cid = KotobaCid::from_bytes(b"leaf-cid");
        let node = ProllyNode::Leaf {
            entries: vec![(b"k".to_vec(), b"v".to_vec())],
            cid: expected_cid.clone(),
        };
        assert_eq!(node.cid(), &expected_cid);
    }

    #[test]
    fn prolly_node_cid_accessor_internal() {
        let expected_cid = KotobaCid::from_bytes(b"internal-cid");
        let node = ProllyNode::Internal {
            children: vec![(b"max".to_vec(), KotobaCid::from_bytes(b"child"))],
            cid: expected_cid.clone(),
        };
        assert_eq!(node.cid(), &expected_cid);
    }

    #[test]
    fn is_boundary_is_deterministic() {
        // Same key must always give the same result
        let key = b"deterministic-boundary-key";
        let r1 = ProllyNode::is_boundary(key);
        let r2 = ProllyNode::is_boundary(key);
        assert_eq!(r1, r2, "is_boundary must be deterministic for same key");
    }

    #[test]
    fn diff_same_root_returns_empty_vecs() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0u64..500)
            .map(|i| (i.to_le_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(entries, &store).unwrap();
        let (only_a, only_b) = ProllyTree::diff(&root, &root, &store).unwrap();
        assert!(
            only_a.is_empty(),
            "diff of same root: only_in_a must be empty"
        );
        assert!(
            only_b.is_empty(),
            "diff of same root: only_in_b must be empty"
        );
    }

    #[test]
    fn diff_different_roots_returns_non_empty() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..500)
            .map(|i| (i.to_le_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root_a = ProllyTree::build_tree(base.clone(), &store).unwrap();
        let mut changed = base;
        changed.push((10_000u64.to_le_bytes().to_vec(), b"new".to_vec()));
        let root_b = ProllyTree::build_tree(changed, &store).unwrap();
        let (only_a, only_b) = ProllyTree::diff(&root_a, &root_b, &store).unwrap();
        assert!(
            !only_a.is_empty() || !only_b.is_empty(),
            "diff of different roots must report at least one differing leaf"
        );
    }

    // ── entry-level diff ──────────────────────────────────────────────────────

    /// diff_entries reports a single added key and nothing else.
    #[test]
    fn diff_entries_single_add() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..1_000)
            .map(|i| (i.to_be_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root_a = ProllyTree::build_tree(base.clone(), &store).unwrap();
        let mut after = base;
        after.push((10_000u64.to_be_bytes().to_vec(), b"vNEW".to_vec()));
        let root_b = ProllyTree::build_tree(after, &store).unwrap();

        let d = ProllyTree::diff_entries(&root_a, &root_b, &store).unwrap();
        assert_eq!(d.removed.len(), 0, "nothing removed");
        assert_eq!(d.changed.len(), 0, "nothing changed");
        assert_eq!(d.added.len(), 1, "exactly one add");
        assert_eq!(d.added[0].0, 10_000u64.to_be_bytes().to_vec());
        assert_eq!(d.added[0].1, b"vNEW".to_vec());
    }

    /// diff_entries reports a value change as `changed`, not add+remove.
    #[test]
    fn diff_entries_single_change() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..1_000)
            .map(|i| (i.to_be_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root_a = ProllyTree::build_tree(base.clone(), &store).unwrap();
        let mut after = base;
        after[500].1 = b"CHANGED".to_vec();
        let root_b = ProllyTree::build_tree(after, &store).unwrap();

        let d = ProllyTree::diff_entries(&root_a, &root_b, &store).unwrap();
        assert_eq!(d.added.len(), 0);
        assert_eq!(d.removed.len(), 0);
        assert_eq!(d.changed.len(), 1);
        assert_eq!(d.changed[0].0, 500u64.to_be_bytes().to_vec());
        assert_eq!(d.changed[0].2, b"CHANGED".to_vec());
    }

    /// diff_entries reports a removal.
    #[test]
    fn diff_entries_single_remove() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..1_000)
            .map(|i| (i.to_be_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root_a = ProllyTree::build_tree(base.clone(), &store).unwrap();
        let after: Vec<_> = base
            .into_iter()
            .filter(|(k, _)| k != &500u64.to_be_bytes().to_vec())
            .collect();
        let root_b = ProllyTree::build_tree(after, &store).unwrap();

        let d = ProllyTree::diff_entries(&root_a, &root_b, &store).unwrap();
        assert_eq!(d.added.len(), 0);
        assert_eq!(d.changed.len(), 0);
        assert_eq!(d.removed.len(), 1);
        assert_eq!(d.removed[0].0, 500u64.to_be_bytes().to_vec());
    }

    /// diff_entries on identical roots is empty.
    #[test]
    fn diff_entries_identical_is_empty() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..1_000)
            .map(|i| (i.to_be_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(base, &store).unwrap();
        let d = ProllyTree::diff_entries(&root, &root, &store).unwrap();
        assert!(d.is_empty());
    }

    /// diff_entries matches a brute-force diff over a mixed add/remove/change set.
    #[test]
    fn diff_entries_matches_brute_force() {
        use std::collections::BTreeMap;
        let store = MemoryBlockStore::new();
        let before: BTreeMap<Vec<u8>, Vec<u8>> = (0u64..2_000)
            .map(|i| (i.to_be_bytes().to_vec(), format!("v{i}").into_bytes()))
            .collect();
        // after: drop multiples of 7, change multiples of 11, add 3 fresh keys
        let mut after: BTreeMap<Vec<u8>, Vec<u8>> = BTreeMap::new();
        for (k, v) in &before {
            let i = u64::from_be_bytes(k.clone().try_into().unwrap());
            if i % 7 == 0 {
                continue; // removed
            }
            if i % 11 == 0 {
                after.insert(k.clone(), format!("changed{i}").into_bytes());
            } else {
                after.insert(k.clone(), v.clone());
            }
        }
        for i in 5_000u64..5_003 {
            after.insert(i.to_be_bytes().to_vec(), b"added".to_vec());
        }

        let root_a = ProllyTree::build_tree(before.clone().into_iter().collect(), &store).unwrap();
        let root_b = ProllyTree::build_tree(after.clone().into_iter().collect(), &store).unwrap();
        let d = ProllyTree::diff_entries(&root_a, &root_b, &store).unwrap();

        // brute force
        let mut exp_added = 0;
        let mut exp_removed = 0;
        let mut exp_changed = 0;
        for k in before
            .keys()
            .chain(after.keys())
            .collect::<std::collections::BTreeSet<_>>()
        {
            match (before.get(k), after.get(k)) {
                (Some(_), None) => exp_removed += 1,
                (None, Some(_)) => exp_added += 1,
                (Some(va), Some(vb)) if va != vb => exp_changed += 1,
                _ => {}
            }
        }
        assert_eq!(d.added.len(), exp_added, "added count");
        assert_eq!(d.removed.len(), exp_removed, "removed count");
        assert_eq!(d.changed.len(), exp_changed, "changed count");
    }

    // ── apply_batch (incremental path-copy) ──────────────────────────────────

    /// Find a u64 BE key in [lo, hi) that IS a chunk boundary, for split/merge tests.
    fn find_boundary_key(lo: u64, hi: u64) -> Option<u64> {
        (lo..hi).find(|i| ProllyNode::is_boundary(&i.to_be_bytes()))
    }

    /// Find a u64 BE key in [lo, hi) that is NOT a chunk boundary.
    fn find_non_boundary_key(lo: u64, hi: u64) -> Option<u64> {
        (lo..hi).find(|i| !ProllyNode::is_boundary(&i.to_be_bytes()))
    }

    fn be(i: u64) -> Vec<u8> {
        i.to_be_bytes().to_vec()
    }

    /// apply_batch with no previous tree == build_tree.
    #[test]
    fn apply_batch_no_prev_equals_build_tree() {
        let store = MemoryBlockStore::new();
        let entries: Vec<(Vec<u8>, Vec<u8>)> = (0u64..1_000)
            .map(|i| (be(i), format!("v{i}").into_bytes()))
            .collect();
        let incr = ProllyTree::apply_batch(None, entries.clone(), vec![], &store).unwrap();
        let scratch = ProllyTree::build_tree(entries, &store).unwrap();
        assert_eq!(incr, scratch);
    }

    /// Inserting a NON-boundary key converges with from-scratch and is local.
    #[test]
    fn apply_batch_insert_non_boundary_converges() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..2_000)
            .map(|i| (be(i), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(base.clone(), &store).unwrap();

        let k = find_non_boundary_key(10_000, 11_000).expect("a non-boundary key exists");
        let new =
            ProllyTree::apply_batch(Some(&root), vec![(be(k), b"NEW".to_vec())], vec![], &store)
                .unwrap();

        let mut final_set = base;
        final_set.push((be(k), b"NEW".to_vec()));
        let scratch = ProllyTree::build_tree(final_set, &store).unwrap();
        assert_eq!(
            new, scratch,
            "incremental insert must converge with build_tree"
        );
        assert_eq!(
            ProllyTree::get(&new, &be(k), &store).unwrap().as_deref(),
            Some(b"NEW".as_ref())
        );
    }

    /// Inserting a BOUNDARY key (forces a leaf split) converges.
    #[test]
    fn apply_batch_insert_boundary_key_split_converges() {
        let store = MemoryBlockStore::new();
        // Use sparse keys so we can drop a fresh boundary key in the middle.
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..2_000)
            .map(|i| (be(i * 10), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(base.clone(), &store).unwrap();

        // a boundary key strictly inside the existing range, not already present
        let k = (1u64..20_000)
            .find(|i| i % 10 != 0 && ProllyNode::is_boundary(&i.to_be_bytes()))
            .expect("a fresh boundary key exists");
        let new = ProllyTree::apply_batch(
            Some(&root),
            vec![(be(k), b"SPLIT".to_vec())],
            vec![],
            &store,
        )
        .unwrap();

        let mut final_set = base;
        final_set.push((be(k), b"SPLIT".to_vec()));
        let scratch = ProllyTree::build_tree(final_set, &store).unwrap();
        assert_eq!(new, scratch, "boundary-key split must converge");
    }

    /// Deleting a BOUNDARY key (forces a leaf merge with its successor) converges.
    #[test]
    fn apply_batch_delete_boundary_key_merge_converges() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..3_000)
            .map(|i| (be(i), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(base.clone(), &store).unwrap();

        // a boundary key that is present and not the global max
        let k = find_boundary_key(1, 2_900).expect("a present boundary key exists");
        let new = ProllyTree::apply_batch(Some(&root), vec![], vec![be(k)], &store).unwrap();

        let final_set: Vec<_> = base.into_iter().filter(|(kk, _)| kk != &be(k)).collect();
        let scratch = ProllyTree::build_tree(final_set, &store).unwrap();
        assert_eq!(new, scratch, "boundary-key merge must converge");
        assert!(ProllyTree::get(&new, &be(k), &store).unwrap().is_none());
    }

    /// Deleting every key yields the same empty-tree root as build_tree([]).
    #[test]
    fn apply_batch_delete_all_converges_to_empty() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..500).map(|i| (be(i), b"v".to_vec())).collect();
        let root = ProllyTree::build_tree(base.clone(), &store).unwrap();
        let dels: Vec<Vec<u8>> = base.iter().map(|(k, _)| k.clone()).collect();
        let new = ProllyTree::apply_batch(Some(&root), vec![], dels, &store).unwrap();
        let empty = ProllyTree::build_tree(vec![], &store).unwrap();
        assert_eq!(new, empty);
    }

    /// Randomized mixed batches over many rounds must each converge with a
    /// from-scratch rebuild of the running key/value map.
    #[test]
    fn apply_batch_randomized_convergence() {
        let store = MemoryBlockStore::new();
        // Deterministic LCG — no external rng, reproducible.
        let mut seed = 0x1234_5678_9abc_def0u64;
        let mut rng = || {
            seed = seed
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            seed >> 16
        };

        let mut model: BTreeMap<Vec<u8>, Vec<u8>> = (0u64..1_500)
            .map(|i| (be(i), format!("v{i}").into_bytes()))
            .collect();
        let mut root = ProllyTree::build_tree(model.clone().into_iter().collect(), &store).unwrap();

        for round in 0..30u64 {
            // Net per-batch effect (last-write-wins within the batch) keeps the
            // upsert/delete lists disjoint — apply_batch's contract.
            let mut net: BTreeMap<Vec<u8>, Option<Vec<u8>>> = BTreeMap::new();
            let ops = 1 + (rng() % 40);
            for _ in 0..ops {
                let key_space = 3_000u64;
                let k = rng() % key_space;
                match rng() % 3 {
                    1 => {
                        net.insert(be(k), None); // delete
                    }
                    other => {
                        let tag = if other == 0 { 'r' } else { 'o' };
                        net.insert(be(k), Some(format!("{tag}{round}-{k}").into_bytes()));
                    }
                }
            }
            let mut upserts = Vec::new();
            let mut deletes = Vec::new();
            for (k, v) in &net {
                match v {
                    Some(val) => {
                        upserts.push((k.clone(), val.clone()));
                        model.insert(k.clone(), val.clone());
                    }
                    None => {
                        deletes.push(k.clone());
                        model.remove(k);
                    }
                }
            }
            root = ProllyTree::apply_batch(Some(&root), upserts, deletes, &store).unwrap();
            let scratch =
                ProllyTree::build_tree(model.clone().into_iter().collect(), &store).unwrap();
            assert_eq!(
                root, scratch,
                "round {round}: incremental root must equal from-scratch root"
            );
        }
    }

    /// apply_batch writes only the blocks that change: a 1-key edit on a large
    /// tree must write far fewer leaf-sized blocks than a full rebuild.
    #[test]
    fn apply_batch_writes_only_changed_blocks() {
        let store = MemoryBlockStore::new();
        let base: Vec<(Vec<u8>, Vec<u8>)> = (0u64..5_000)
            .map(|i| (be(i), format!("v{i}").into_bytes()))
            .collect();
        let root = ProllyTree::build_tree(base, &store).unwrap();
        let before = store.block_count();

        let k = find_non_boundary_key(100_000, 101_000).unwrap();
        let _new =
            ProllyTree::apply_batch(Some(&root), vec![(be(k), b"X".to_vec())], vec![], &store)
                .unwrap();
        let written = store.block_count() - before;

        // A full rebuild would touch ~5000/256 ≈ 20 leaves + spine. Incremental
        // should add only a handful of new blocks (1 changed leaf + spine path).
        assert!(
            written < 10,
            "incremental edit wrote {written} new blocks; expected a handful, not a full rebuild"
        );
    }

    #[test]
    fn build_tree_empty_returns_no_root() {
        // build_tree([]) must not panic and must return a valid (but empty) root CID
        // OR handle the empty case gracefully. The actual behavior depends on impl.
        let store = MemoryBlockStore::new();
        // An empty entry list should produce exactly one leaf (or handle gracefully).
        // This test verifies no panic only — the exact return value is impl-defined.
        let result = ProllyTree::build_tree(vec![], &store);
        // May be Ok or Err, but must not panic.
        let _ = result;
    }
}
