use blake3::Hasher;

/// NodeId = blake3(did_public_key) — 256-bit DHT address
/// XOR metric for neighborhood routing
#[derive(Debug, Clone, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct NodeId(pub [u8; 32]);

impl NodeId {
    pub fn from_pubkey(pubkey_bytes: &[u8]) -> Self {
        let hash = Hasher::new().update(pubkey_bytes).finalize();
        Self(*hash.as_bytes())
    }

    /// XOR distance for Kademlia-style routing
    pub fn xor_distance(&self, other: &Self) -> [u8; 32] {
        let mut dist = [0u8; 32];
        for (i, slot) in dist.iter_mut().enumerate() { *slot = self.0[i] ^ other.0[i]; }
        dist
    }

    /// Find K closest nodes from candidates (XOR metric)
    pub fn k_nearest<'a>(target: &Self, candidates: &'a [NodeId], k: usize) -> Vec<&'a NodeId> {
        let mut with_dist: Vec<(&NodeId, [u8; 32])> = candidates.iter()
            .map(|n| (n, target.xor_distance(n)))
            .collect();
        with_dist.sort_by_key(|(_, d)| *d);
        with_dist.into_iter().take(k).map(|(n, _)| n).collect()
    }
}

impl std::fmt::Display for NodeId {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", hex::encode(self.0))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_pubkey_is_deterministic() {
        let a = NodeId::from_pubkey(b"peer-key");
        let b = NodeId::from_pubkey(b"peer-key");
        assert_eq!(a, b);
    }

    #[test]
    fn from_pubkey_differs_for_different_keys() {
        let a = NodeId::from_pubkey(b"alice");
        let b = NodeId::from_pubkey(b"bob");
        assert_ne!(a, b);
    }

    #[test]
    fn xor_distance_self_is_zero() {
        let n = NodeId::from_pubkey(b"self");
        assert_eq!(n.xor_distance(&n), [0u8; 32]);
    }

    #[test]
    fn xor_distance_is_symmetric() {
        let a = NodeId::from_pubkey(b"a");
        let b = NodeId::from_pubkey(b"b");
        assert_eq!(a.xor_distance(&b), b.xor_distance(&a));
    }

    #[test]
    fn k_nearest_returns_at_most_k() {
        let target = NodeId::from_pubkey(b"target");
        let candidates: Vec<NodeId> = (0..10u8).map(|i| NodeId::from_pubkey(&[i])).collect();
        let nearest = NodeId::k_nearest(&target, &candidates, 3);
        assert_eq!(nearest.len(), 3);
    }

    #[test]
    fn k_nearest_empty_candidates() {
        let target = NodeId::from_pubkey(b"t");
        assert!(NodeId::k_nearest(&target, &[], 5).is_empty());
    }

    #[test]
    fn k_nearest_fewer_than_k() {
        let target = NodeId::from_pubkey(b"t");
        let candidates = vec![NodeId::from_pubkey(b"x")];
        assert_eq!(NodeId::k_nearest(&target, &candidates, 5).len(), 1);
    }

    #[test]
    fn display_is_64_hex_chars() {
        let n = NodeId::from_pubkey(b"display-test");
        let s = format!("{n}");
        assert_eq!(s.len(), 64);
        assert!(s.chars().all(|c| c.is_ascii_hexdigit()));
    }
}
