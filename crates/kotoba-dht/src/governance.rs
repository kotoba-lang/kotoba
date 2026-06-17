//! # Governance — Council-quorum ratification of versioned params (GROWTH p12)
//!
//! Network-wide parameters (the `social/capital/params/active` blob, bond floors,
//! a DNA upgrade, …) must not change on one operator's say-so: a new version is
//! active only once a **quorum of distinct Council members** has attested it.
//! This is the pure governance physics — who counts and how many are needed —
//! independent of the attestation transport and signature verification (those are
//! the auth layer; this counts ratified members over already-verified attesters).
//!
//! A [`ParamVersion`] is content-addressed, so "which params are active" is a CID
//! every node can agree on and (per ADR-002 §governance) anchor on Base.

use kotoba_core::cid::KotobaCid;
use serde::{Deserialize, Serialize};
use std::collections::HashSet;

/// A proposed parameter version: a human version label + the CID of the param
/// blob it activates. Content-addressed via [`id`](ParamVersion::id) so nodes
/// reference an exact (version, content) pair.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ParamVersion {
    pub version: String,
    pub content: KotobaCid,
}

impl ParamVersion {
    pub fn new(version: impl Into<String>, content: KotobaCid) -> Self {
        Self {
            version: version.into(),
            content,
        }
    }

    /// Canonical CBOR — the bytes the version id addresses.
    pub fn to_cbor(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        ciborium::into_writer(self, &mut buf).expect("paramversion cbor");
        buf
    }

    /// Content address of this (version, content) pair — what attesters sign and
    /// what the active-params pointer / on-chain anchor references.
    pub fn id(&self) -> KotobaCid {
        KotobaCid::from_bytes(&self.to_cbor())
    }
}

/// The outcome of a quorum check.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Ratification {
    /// Distinct Council members who attested.
    pub approvals: usize,
    /// Quorum required.
    pub threshold: usize,
    /// `true` iff `approvals >= threshold`.
    pub ratified: bool,
}

/// Ratify a param version: count the **distinct** `attesters` that are members of
/// `council`, and ratify iff that reaches `threshold`. Duplicate attestations and
/// non-members (e.g. a revoked or impostor signer) do not count. `threshold` is
/// clamped to `≥ 1` (a change always needs at least one Council approval).
///
/// Signature verification is upstream: `attesters` are the DIDs whose attestation
/// over the [`ParamVersion::id`] already verified.
pub fn ratify(
    attesters: &[KotobaCid],
    council: &HashSet<KotobaCid>,
    threshold: usize,
) -> Ratification {
    let threshold = threshold.max(1);
    let approvals = attesters
        .iter()
        .filter(|a| council.contains(*a))
        .collect::<HashSet<_>>()
        .len();
    Ratification {
        approvals,
        threshold,
        ratified: approvals >= threshold,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn did(s: &str) -> KotobaCid {
        KotobaCid::from_bytes(s.as_bytes())
    }

    fn council(members: &[&str]) -> HashSet<KotobaCid> {
        members.iter().map(|m| did(m)).collect()
    }

    #[test]
    fn param_version_id_is_deterministic_and_content_sensitive() {
        let a = ParamVersion::new("1.0.0", did("blobA"));
        assert_eq!(a.id(), a.id());
        assert_eq!(a.id(), KotobaCid::from_bytes(&a.to_cbor()));
        // version bump or content change → different id.
        assert_ne!(a.id(), ParamVersion::new("1.0.1", did("blobA")).id());
        assert_ne!(a.id(), ParamVersion::new("1.0.0", did("blobB")).id());
        // CBOR round-trips.
        let back: ParamVersion = ciborium::from_reader(a.to_cbor().as_slice()).unwrap();
        assert_eq!(back, a);
    }

    #[test]
    fn ratifies_at_threshold() {
        let c = council(&["alice", "bob", "carol"]);
        let r = ratify(&[did("alice"), did("bob")], &c, 2);
        assert_eq!(r.approvals, 2);
        assert!(r.ratified);
        // one short → not ratified.
        assert!(!ratify(&[did("alice")], &c, 2).ratified);
    }

    #[test]
    fn duplicate_attestations_count_once() {
        let c = council(&["alice", "bob"]);
        let r = ratify(&[did("alice"), did("alice"), did("alice")], &c, 2);
        assert_eq!(r.approvals, 1, "the same member attesting thrice is one approval");
        assert!(!r.ratified);
    }

    #[test]
    fn non_members_do_not_count() {
        let c = council(&["alice", "bob"]);
        // mallory is not on the council; eve isn't either.
        let r = ratify(&[did("alice"), did("mallory"), did("eve")], &c, 2);
        assert_eq!(r.approvals, 1, "only alice is a council member");
        assert!(!r.ratified);
    }

    #[test]
    fn threshold_is_clamped_to_one() {
        let c = council(&["alice"]);
        // threshold 0 would auto-ratify anything; clamp to 1.
        assert!(!ratify(&[], &c, 0).ratified, "no approvals can't ratify");
        assert!(ratify(&[did("alice")], &c, 0).ratified);
    }
}
