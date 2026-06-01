//! Commit-head chain — the durable, verifiable mutable head (ADR-2606011330 #3).
//!
//! Replaces IPNS for "what is the current root of graph G?". Each commit appends
//! a **signed** `ChainContent::Commit { graph_cid, prolly_root }` to the agent's
//! per-DID `SourceChain` (append-only, hash-linked = Datomic accretion log). The
//! mutable head for a graph is the `prolly_root` of its latest Commit entry, and
//! the whole lineage is verifiable: each entry links `prev` → `cid` and carries
//! an Ed25519 signature over its canonical bytes.
//!
//! This is the mechanism the ADR's D4 "mutable head = source_chain tip" refers
//! to. The remaining wiring is the call-site: `QuadStore::commit()` (kotoba-graph)
//! invokes `record_commit(graph, new_root)` after building the ProllyTree, so the
//! head advances atomically with the commit. That cross-crate connection (graph
//! holding an `AgentIdentity`) is the last step and is intentionally left to the
//! commit-pipeline change; the signed-head mechanism itself is complete here.

use crate::source_chain::{ChainContent, ChainEntry, ChainError, SourceChain};
use ed25519_dalek::{Signer, SigningKey};
use kotoba_core::cid::KotobaCid;
use kotoba_kse::agent_identity::AgentIdentity;
use std::collections::HashMap;

/// A per-agent signed commit log plus a materialized view of the current head
/// (`prolly_root`) for each graph.
pub struct CommitChain {
    chain: SourceChain,
    signing_key: SigningKey,
    pubkey: [u8; 32],
    did: String,
    /// graph_cid bytes → latest committed prolly_root.
    heads: HashMap<[u8; 36], KotobaCid>,
}

impl CommitChain {
    /// Build a commit chain owned by `identity` (its DID is the chain agent).
    pub fn new(identity: &AgentIdentity) -> Self {
        Self {
            chain: SourceChain::new(identity.did.clone()),
            // Reconstruct from the 32-byte seed (no reliance on SigningKey: Clone).
            signing_key: SigningKey::from_bytes(&identity.signing_key.to_bytes()),
            pubkey: identity.verifying_key().to_bytes(),
            did: identity.did.clone(),
            heads: HashMap::new(),
        }
    }

    /// Append a signed Commit advancing `graph_cid`'s head to `prolly_root`.
    /// Returns the new chain-entry CID (the head pointer). The entry is signed
    /// over `signing_bytes()` and appended through `append_verified`, so a
    /// corrupted or mis-signed entry could never be accepted.
    pub fn record_commit(
        &mut self,
        graph_cid: KotobaCid,
        prolly_root: KotobaCid,
    ) -> Result<KotobaCid, ChainError> {
        let prev = self.chain.head().map(|e| e.cid.clone());
        let seq = self.chain.len() as u64;
        let content = ChainContent::Commit {
            graph_cid: graph_cid.clone(),
            prolly_root: prolly_root.clone(),
        };
        let mut entry = ChainEntry::new(prev, self.did.clone(), seq, content, Vec::new());
        let sig = self.signing_key.sign(&entry.signing_bytes());
        entry.sig = sig.to_bytes().to_vec();
        let entry_cid = entry.cid.clone();
        self.chain.append_verified(entry, &self.pubkey)?;
        self.heads.insert(graph_cid.0, prolly_root);
        Ok(entry_cid)
    }

    /// The current mutable head for `graph_cid`: the latest committed
    /// `prolly_root`, or `None` if the graph has never committed.
    pub fn head_root(&self, graph_cid: &KotobaCid) -> Option<KotobaCid> {
        self.heads.get(&graph_cid.0).cloned()
    }

    /// CID of the latest chain entry (the source-chain tip).
    pub fn source_head_cid(&self) -> Option<KotobaCid> {
        self.chain.head().map(|e| e.cid.clone())
    }

    /// Number of commits recorded.
    pub fn len(&self) -> usize {
        self.chain.len()
    }

    pub fn is_empty(&self) -> bool {
        self.chain.is_empty()
    }

    /// The agent DID that owns this chain.
    pub fn did(&self) -> &str {
        &self.did
    }

    /// 32-byte Ed25519 public key for verifying this chain's entries.
    pub fn pubkey(&self) -> &[u8; 32] {
        &self.pubkey
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ident() -> AgentIdentity {
        AgentIdentity::generate_ephemeral()
    }

    #[test]
    fn record_commit_advances_head() {
        let id = ident();
        let mut cc = CommitChain::new(&id);
        let g = KotobaCid::from_bytes(b"graph-1");
        assert!(cc.head_root(&g).is_none());

        let r1 = KotobaCid::from_bytes(b"root-1");
        cc.record_commit(g.clone(), r1.clone()).unwrap();
        assert_eq!(cc.head_root(&g), Some(r1));
        assert_eq!(cc.len(), 1);

        let r2 = KotobaCid::from_bytes(b"root-2");
        cc.record_commit(g.clone(), r2.clone()).unwrap();
        assert_eq!(cc.head_root(&g), Some(r2), "head advances to the latest root");
        assert_eq!(cc.len(), 2);
    }

    #[test]
    fn distinct_graphs_have_independent_heads() {
        let id = ident();
        let mut cc = CommitChain::new(&id);
        let g1 = KotobaCid::from_bytes(b"graph-1");
        let g2 = KotobaCid::from_bytes(b"graph-2");
        let r1 = KotobaCid::from_bytes(b"r1");
        let r2 = KotobaCid::from_bytes(b"r2");
        cc.record_commit(g1.clone(), r1.clone()).unwrap();
        cc.record_commit(g2.clone(), r2.clone()).unwrap();
        assert_eq!(cc.head_root(&g1), Some(r1));
        assert_eq!(cc.head_root(&g2), Some(r2));
        assert_eq!(cc.len(), 2, "both commits share one append-only chain");
    }

    #[test]
    fn chain_lineage_links_and_advances() {
        let id = ident();
        let mut cc = CommitChain::new(&id);
        let g = KotobaCid::from_bytes(b"g");
        let c1 = cc
            .record_commit(g.clone(), KotobaCid::from_bytes(b"r1"))
            .unwrap();
        let head_after_1 = cc.source_head_cid().unwrap();
        assert_eq!(head_after_1, c1, "source head = last entry cid");
        let c2 = cc
            .record_commit(g.clone(), KotobaCid::from_bytes(b"r2"))
            .unwrap();
        assert_ne!(c1, c2, "each commit is a distinct entry");
        assert_eq!(cc.source_head_cid(), Some(c2));
    }

    /// Integration contract for the deferred `QuadStore::commit()` wiring
    /// (ADR-2606011330 #3). Simulates the exact call the commit pipeline must
    /// make — `record_commit(graph, new_root)` after each ProllyTree build —
    /// across two graphs committing in interleaved order, and asserts each
    /// graph's mutable head resolves to its own latest root with one shared
    /// append-only signed chain. The one-line call-site insertion into
    /// `quad_store.rs` is deferred only because that file is concurrently held
    /// dirty by the background /loop; this test pins the contract it must meet.
    #[test]
    fn simulates_quadstore_commit_loop_multi_graph_interleaved() {
        let id = ident();
        let mut cc = CommitChain::new(&id);
        let ga = KotobaCid::from_bytes(b"graph-A");
        let gb = KotobaCid::from_bytes(b"graph-B");

        // Interleaved commits, as a multi-graph QuadStore would emit them.
        cc.record_commit(ga.clone(), KotobaCid::from_bytes(b"A-r1")).unwrap();
        cc.record_commit(gb.clone(), KotobaCid::from_bytes(b"B-r1")).unwrap();
        cc.record_commit(ga.clone(), KotobaCid::from_bytes(b"A-r2")).unwrap();
        cc.record_commit(gb.clone(), KotobaCid::from_bytes(b"B-r2")).unwrap();
        cc.record_commit(ga.clone(), KotobaCid::from_bytes(b"A-r3")).unwrap();

        // Each graph's head = its OWN latest root, despite interleaving.
        assert_eq!(cc.head_root(&ga), Some(KotobaCid::from_bytes(b"A-r3")));
        assert_eq!(cc.head_root(&gb), Some(KotobaCid::from_bytes(b"B-r2")));
        // One shared, append-only, signed chain of all five commits.
        assert_eq!(cc.len(), 5);
    }

    #[test]
    fn entries_are_signed_by_the_owning_identity() {
        // record_commit signs + append_verified-s against the identity's pubkey;
        // a chain built from a fresh identity verifies under its own key. The
        // negative path (wrong key rejected) is covered by source_chain tests.
        let id = ident();
        let mut cc = CommitChain::new(&id);
        assert_eq!(cc.pubkey(), &id.verifying_key().to_bytes());
        assert_eq!(cc.did(), id.did);
        // A commit must succeed (signature verifies under the agent key).
        cc.record_commit(
            KotobaCid::from_bytes(b"g"),
            KotobaCid::from_bytes(b"r"),
        )
        .expect("self-signed commit must verify and append");
    }
}
