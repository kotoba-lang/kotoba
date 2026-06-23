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

use ed25519_dalek::{Signature, Verifier, VerifyingKey};
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

/// A Council member's attestation over a [`ParamVersion`]: their ed25519 public
/// key and a signature over the version's [`id`](ParamVersion::id) (its 36
/// content-address bytes). The signer pubkey is the member identity matched
/// against the council set.
#[derive(Debug, Clone)]
pub struct Attestation {
    pub signer: [u8; 32],
    pub sig: [u8; 64],
}

/// Verify ed25519 attestations over `version` and ratify (GROWTH p12, the real
/// crypto path over [`ratify`]'s counting). An attestation counts iff its signer
/// is in `council` (by pubkey) **and** its signature over `version.id()` verifies.
/// Distinct valid signers only; forged, wrong-message, or non-member attestations
/// are dropped. `threshold` is clamped to `≥ 1`.
pub fn verify_and_ratify(
    version: &ParamVersion,
    attestations: &[Attestation],
    council: &HashSet<[u8; 32]>,
    threshold: usize,
) -> Ratification {
    let msg = version.id().0;
    let mut valid: HashSet<[u8; 32]> = HashSet::new();
    for a in attestations {
        if !council.contains(&a.signer) {
            continue;
        }
        let Ok(vk) = VerifyingKey::from_bytes(&a.signer) else {
            continue;
        };
        if vk.verify(&msg, &Signature::from_bytes(&a.sig)).is_ok() {
            valid.insert(a.signer);
        }
    }
    let threshold = threshold.max(1);
    Ratification {
        approvals: valid.len(),
        threshold,
        ratified: valid.len() >= threshold,
    }
}

/// The `social/capital/params/active` pointer with ratified transitions (GROWTH
/// p12): the active [`ParamVersion`] advances only when a Council quorum's
/// ed25519 attestations over the proposal verify. An operator cannot move the
/// pointer alone. The prior version id is recorded so the change history is
/// auditable (and each id is anchorable on Base for objective finality, p8).
#[derive(Debug, Clone)]
pub struct ActiveParams {
    current: ParamVersion,
    history: Vec<KotobaCid>,
}

impl ActiveParams {
    pub fn new(initial: ParamVersion) -> Self {
        Self {
            current: initial,
            history: Vec::new(),
        }
    }

    pub fn current(&self) -> &ParamVersion {
        &self.current
    }

    /// Content id of the active params — the value the active pointer holds.
    pub fn current_id(&self) -> KotobaCid {
        self.current.id()
    }

    /// Prior version ids, oldest first (the ratified change history).
    pub fn history(&self) -> &[KotobaCid] {
        &self.history
    }

    /// Attempt to make `proposed` the active params: verify the `attestations`
    /// against `council` at `threshold` and, **iff ratified**, advance the
    /// pointer (recording the superseded id in history). Returns the
    /// [`Ratification`] either way — the pointer is unchanged when it is not
    /// ratified. Re-activating the already-active version is a no-op (but still
    /// requires a fresh quorum, since attestations are over the version id).
    pub fn try_activate(
        &mut self,
        proposed: ParamVersion,
        attestations: &[Attestation],
        council: &HashSet<[u8; 32]>,
        threshold: usize,
    ) -> Ratification {
        let r = verify_and_ratify(&proposed, attestations, council, threshold);
        if r.ratified && proposed.id() != self.current.id() {
            self.history.push(self.current.id());
            self.current = proposed;
        }
        r
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ed25519_dalek::{Signer, SigningKey};

    fn did(s: &str) -> KotobaCid {
        KotobaCid::from_bytes(s.as_bytes())
    }

    fn key(seed: u8) -> SigningKey {
        SigningKey::from_bytes(&[seed; 32])
    }

    fn attest(sk: &SigningKey, version: &ParamVersion) -> Attestation {
        Attestation {
            signer: sk.verifying_key().to_bytes(),
            sig: sk.sign(&version.id().0).to_bytes(),
        }
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
    fn ratify_invariants_hold_adversarially() {
        // Security: approvals always equal the count of DISTINCT council members
        // among the attesters (duplicates and non-members never inflate it), and
        // ratified iff that reaches the (>=1-clamped) threshold — no mix of
        // padding attesters can ever cross the quorum. Deterministic sweep.
        let c = council(&["alice", "bob", "carol"]);
        let pool = [
            did("alice"), did("alice"), did("bob"),       // dups
            did("mallory"), did("eve"), did("carol"),     // non-members + member
        ];
        for take in 0..=pool.len() {
            let attesters = &pool[..take];
            for threshold in 0usize..6 {
                let r = ratify(attesters, &c, threshold);
                let distinct_members = attesters
                    .iter()
                    .filter(|a| c.contains(*a))
                    .collect::<HashSet<_>>()
                    .len();
                assert_eq!(r.approvals, distinct_members, "approvals must be distinct members only");
                assert!(r.approvals <= c.len(), "can't exceed the council size");
                assert_eq!(r.threshold, threshold.max(1), "threshold clamped to >=1");
                assert_eq!(r.ratified, distinct_members >= threshold.max(1));
            }
        }
    }

    #[test]
    fn threshold_is_clamped_to_one() {
        let c = council(&["alice"]);
        // threshold 0 would auto-ratify anything; clamp to 1.
        assert!(!ratify(&[], &c, 0).ratified, "no approvals can't ratify");
        assert!(ratify(&[did("alice")], &c, 0).ratified);
    }

    // ── real ed25519 attestation verification ─────────────────────────────

    #[test]
    fn verify_and_ratify_accepts_quorum_of_valid_member_sigs() {
        let (a, b) = (key(1), key(2));
        let council: HashSet<[u8; 32]> =
            [a.verifying_key().to_bytes(), b.verifying_key().to_bytes()].into_iter().collect();
        let v = ParamVersion::new("2.0.0", did("params"));
        let r = verify_and_ratify(&v, &[attest(&a, &v), attest(&b, &v)], &council, 2);
        assert_eq!(r.approvals, 2);
        assert!(r.ratified);
    }

    #[test]
    fn verify_and_ratify_rejects_forged_wrong_message_and_nonmember() {
        let (a, b, mallory) = (key(1), key(2), key(9));
        let council: HashSet<[u8; 32]> =
            [a.verifying_key().to_bytes(), b.verifying_key().to_bytes()].into_iter().collect();
        let v = ParamVersion::new("2.0.0", did("params"));
        let other = ParamVersion::new("2.0.1", did("params"));

        // forged: claim a's pubkey but sign with mallory's key.
        let forged = Attestation {
            signer: a.verifying_key().to_bytes(),
            sig: mallory.sign(&v.id().0).to_bytes(),
        };
        // wrong message: b signs a DIFFERENT version.
        let wrong_msg = Attestation {
            signer: b.verifying_key().to_bytes(),
            sig: b.sign(&other.id().0).to_bytes(),
        };
        // non-member: mallory validly signs v but isn't on the council.
        let nonmember = attest(&mallory, &v);

        let r = verify_and_ratify(&v, &[forged, wrong_msg, nonmember], &council, 1);
        assert_eq!(r.approvals, 0, "forged/wrong-msg/non-member all dropped");
        assert!(!r.ratified);
    }

    #[test]
    fn verify_and_ratify_counts_a_member_once_despite_duplicate_attestations() {
        let a = key(1);
        let council: HashSet<[u8; 32]> = [a.verifying_key().to_bytes()].into_iter().collect();
        let v = ParamVersion::new("2.0.0", did("params"));
        let r = verify_and_ratify(&v, &[attest(&a, &v), attest(&a, &v)], &council, 2);
        assert_eq!(r.approvals, 1, "same valid signer twice is one approval");
        assert!(!r.ratified);
    }

    // ── ActiveParams pointer ──────────────────────────────────────────────

    #[test]
    fn active_params_advances_only_on_ratified_change() {
        let (a, b) = (key(1), key(2));
        let council: HashSet<[u8; 32]> =
            [a.verifying_key().to_bytes(), b.verifying_key().to_bytes()].into_iter().collect();
        let v0 = ParamVersion::new("1.0.0", did("p0"));
        let mut active = ActiveParams::new(v0.clone());
        assert_eq!(active.current_id(), v0.id());
        assert!(active.history().is_empty());

        // a quorum-ratified proposal advances the pointer + records history.
        let v1 = ParamVersion::new("2.0.0", did("p1"));
        let r = active.try_activate(v1.clone(), &[attest(&a, &v1), attest(&b, &v1)], &council, 2);
        assert!(r.ratified);
        assert_eq!(active.current_id(), v1.id());
        assert_eq!(active.history(), &[v0.id()]);

        // an UNratified proposal (only one approval, threshold 2) is rejected:
        // the pointer does not move.
        let v2 = ParamVersion::new("3.0.0", did("p2"));
        let r2 = active.try_activate(v2.clone(), &[attest(&a, &v2)], &council, 2);
        assert!(!r2.ratified);
        assert_eq!(active.current_id(), v1.id(), "pointer unchanged on rejection");
        assert_eq!(active.history(), &[v0.id()], "history unchanged");
    }

    #[test]
    fn active_params_reactivating_current_is_a_noop() {
        let a = key(1);
        let council: HashSet<[u8; 32]> = [a.verifying_key().to_bytes()].into_iter().collect();
        let v0 = ParamVersion::new("1.0.0", did("p0"));
        let mut active = ActiveParams::new(v0.clone());
        // ratified, but it's the already-active version → no history churn.
        let r = active.try_activate(v0.clone(), &[attest(&a, &v0)], &council, 1);
        assert!(r.ratified);
        assert_eq!(active.current_id(), v0.id());
        assert!(active.history().is_empty(), "re-activating current adds no history");
    }
}
