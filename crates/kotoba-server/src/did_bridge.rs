//! `did ↔ cid ↔ on-chain didHash` bridge (ADR-2606082100 follow-up).
//!
//! A DID wears three identifiers across the loop, and the social-capital machinery
//! needs to move between them:
//!   - **DID string** — e.g. `did:web:alice.etzhayyim.com`, the canonical name.
//!   - **KotobaCid** — the entity key in `social/*` Datoms (`= from_bytes(did)`).
//!   - **on-chain didHash** — `keccak256(did)`, stored in `ClaimStakeEscrow`.
//!
//! So an observed on-chain disclosure event (keyed by `didHash`) can be attributed
//! to the right social-capital entity (CID), and L6 settlement can credit a **DID**
//! (not just its CID) once the DID is known. The canonical mappings are pure
//! functions; the reverse lookups need a registry of known DIDs (fed from
//! did-registration Datoms / the MEMBERS roster).

use std::collections::HashMap;

use kotoba_auth::eth::keccak256;
use kotoba_core::cid::KotobaCid;

/// Canonical DID string → social-capital entity CID — the SAME mapping the mint
/// pipeline uses when it writes `social/*` Datoms for a DID.
pub fn did_to_cid(did: &str) -> KotobaCid {
    KotobaCid::from_bytes(did.as_bytes())
}

/// On-chain `didHash` = `keccak256(did)` — what `ClaimStakeEscrow` stores as the
/// claimant's `didHash` (and what `MishmarBondEscrow` records as `didHash`).
pub fn did_hash(did: &str) -> [u8; 32] {
    keccak256(did.as_bytes())
}

/// Reverse-lookup registry over known DIDs: `cid → did` and `didHash → did`.
/// Forward mappings (`did → cid`, `did → hash`) are pure and need no registration.
#[derive(Default)]
pub struct DidCidBridge {
    by_cid: HashMap<KotobaCid, String>,
    by_hash: HashMap<[u8; 32], String>,
}

impl DidCidBridge {
    pub fn new() -> Self {
        Self::default()
    }

    /// Register a known DID (from a did-registration Datom / MEMBERS roster).
    /// Returns its entity CID. Idempotent.
    pub fn register(&mut self, did: impl Into<String>) -> KotobaCid {
        let did = did.into();
        let cid = did_to_cid(&did);
        self.by_hash.insert(did_hash(&did), did.clone());
        self.by_cid.insert(cid.clone(), did);
        cid
    }

    /// DID → entity CID (pure; works for any DID, registered or not).
    pub fn cid_of(&self, did: &str) -> KotobaCid {
        did_to_cid(did)
    }

    /// entity CID → DID (only for registered DIDs).
    pub fn did_of_cid(&self, cid: &KotobaCid) -> Option<&str> {
        self.by_cid.get(cid).map(String::as_str)
    }

    /// on-chain didHash → DID (only for registered DIDs).
    pub fn did_of_hash(&self, hash: &[u8; 32]) -> Option<&str> {
        self.by_hash.get(hash).map(String::as_str)
    }

    /// on-chain didHash → social-capital entity CID (attribute an on-chain event
    /// to its social entity). `None` if the DID behind the hash isn't registered.
    pub fn cid_of_hash(&self, hash: &[u8; 32]) -> Option<KotobaCid> {
        self.did_of_hash(hash).map(did_to_cid)
    }

    pub fn len(&self) -> usize {
        self.by_cid.len()
    }

    pub fn is_empty(&self) -> bool {
        self.by_cid.is_empty()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forward_mappings_are_pure_and_deterministic() {
        let did = "did:web:alice.etzhayyim.com";
        assert_eq!(did_to_cid(did), did_to_cid(did)); // stable
        assert_eq!(did_to_cid(did), KotobaCid::from_bytes(did.as_bytes()));
        assert_eq!(did_hash(did), keccak256(did.as_bytes()));
        // distinct DIDs → distinct cids + hashes
        assert_ne!(did_to_cid("did:web:a"), did_to_cid("did:web:b"));
        assert_ne!(did_hash("did:web:a"), did_hash("did:web:b"));
    }

    #[test]
    fn reverse_lookups_roundtrip_for_registered() {
        let mut b = DidCidBridge::new();
        let alice = "did:web:alice.etzhayyim.com";
        let bob = "did:plc:bob123";
        let alice_cid = b.register(alice);
        b.register(bob);

        assert_eq!(b.len(), 2);
        assert_eq!(b.cid_of(alice), alice_cid);
        assert_eq!(b.did_of_cid(&alice_cid), Some(alice));
        assert_eq!(b.did_of_hash(&did_hash(alice)), Some(alice));
        // attribute an on-chain didHash straight to the social entity CID
        assert_eq!(b.cid_of_hash(&did_hash(alice)), Some(alice_cid));
        assert_eq!(b.cid_of_hash(&did_hash(bob)), Some(did_to_cid(bob)));
    }

    #[test]
    fn unregistered_reverse_lookups_are_none() {
        let b = DidCidBridge::new();
        assert_eq!(b.did_of_cid(&did_to_cid("did:web:ghost")), None);
        assert_eq!(b.did_of_hash(&did_hash("did:web:ghost")), None);
        assert_eq!(b.cid_of_hash(&did_hash("did:web:ghost")), None);
        // forward mapping still works without registration
        assert_eq!(b.cid_of("did:web:ghost"), did_to_cid("did:web:ghost"));
    }

    #[test]
    fn register_is_idempotent() {
        let mut b = DidCidBridge::new();
        let a1 = b.register("did:web:a");
        let a2 = b.register("did:web:a");
        assert_eq!(a1, a2);
        assert_eq!(b.len(), 1);
    }
}
