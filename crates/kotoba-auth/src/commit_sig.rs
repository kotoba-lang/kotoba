//! CommitDag author-signature verification (ADR-sealed-cold-tier R2b).
//!
//! kotoba-datomic carries the signature mechanics (`sign` / `verify_author_sig`
//! against a caller-supplied key) but cannot resolve DIDs — this crate sits
//! above it and closes the loop: author DID (did:key) → Ed25519 pubkey →
//! verify. Also provides the `ImportCheck` closure the
//! `DistributedCommitWriter` merge path uses to gate foreign heads.

use crate::did_key::parse_ed25519_did_key;
use kotoba_datomic::distributed::{DistributedDatomCommit, ImportCheck};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum CommitSigVerdict {
    /// No `author_sig` on the commit (pre-R2b block or unsigned writer).
    Unsigned,
    /// Signature verifies against the author DID's key.
    Valid,
    /// Signature present but does NOT verify — tampering or forgery.
    Invalid,
    /// Signature present but the author DID's key cannot be resolved
    /// (non-did:key method, malformed DID, bad point).
    Unverifiable(String),
}

/// Verify a commit's embedded author signature against its own `author` DID.
pub fn verify_commit_author_sig(commit: &DistributedDatomCommit) -> CommitSigVerdict {
    if commit.author_sig.is_none() {
        return CommitSigVerdict::Unsigned;
    }
    let pk = match parse_ed25519_did_key(&commit.author) {
        Ok(pk) => pk,
        Err(e) => return CommitSigVerdict::Unverifiable(format!("author DID: {e}")),
    };
    let vk = match ed25519_dalek::VerifyingKey::from_bytes(&pk) {
        Ok(vk) => vk,
        Err(e) => return CommitSigVerdict::Unverifiable(format!("author pubkey: {e}")),
    };
    match commit.verify_author_sig(&vk) {
        Ok(true) => CommitSigVerdict::Valid,
        Ok(false) => CommitSigVerdict::Invalid,
        Err(e) => CommitSigVerdict::Unverifiable(format!("verify: {e}")),
    }
}

/// Build the merge-path import gate (R2b enforcement policy):
/// - `Invalid` ALWAYS rejects — a bad signature is active tampering evidence.
/// - `Unsigned` / `Unverifiable` reject only when `require_signed` is set
///   (`KOTOBA_REQUIRE_SIGNED_COMMITS`), so legacy chains keep merging during
///   the observe-first rollout.
pub fn commit_import_check(require_signed: bool) -> ImportCheck {
    std::sync::Arc::new(move |commit: &DistributedDatomCommit| {
        match verify_commit_author_sig(commit) {
            CommitSigVerdict::Valid => Ok(()),
            CommitSigVerdict::Invalid => Err(format!(
                "author_sig INVALID for author {} — tampered or forged commit",
                commit.author
            )),
            CommitSigVerdict::Unsigned if require_signed => Err(format!(
                "unsigned commit by {} (KOTOBA_REQUIRE_SIGNED_COMMITS is on)",
                commit.author
            )),
            CommitSigVerdict::Unverifiable(reason) if require_signed => Err(format!(
                "unverifiable author_sig ({reason}) (KOTOBA_REQUIRE_SIGNED_COMMITS is on)"
            )),
            CommitSigVerdict::Unsigned | CommitSigVerdict::Unverifiable(_) => Ok(()),
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::did_key::ed25519_pubkey_to_did_key;
    use kotoba_core::cid::KotobaCid;
    use std::collections::HashMap;

    fn signed_commit(key: &ed25519_dalek::SigningKey) -> DistributedDatomCommit {
        let did = ed25519_pubkey_to_did_key(key.verifying_key().as_bytes());
        let mut c = DistributedDatomCommit::seal(
            KotobaCid::from_bytes(b"verdict-graph"),
            KotobaCid::from_bytes(b"verdict-tx"),
            None,
            did,
            1,
            HashMap::new(),
            None,
        )
        .unwrap();
        c.sign(key).unwrap();
        c
    }

    #[test]
    fn valid_signature_verdict() {
        let key = ed25519_dalek::SigningKey::from_bytes(&[21u8; 32]);
        let c = signed_commit(&key);
        assert_eq!(verify_commit_author_sig(&c), CommitSigVerdict::Valid);
        assert!(commit_import_check(true)(&c).is_ok());
    }

    #[test]
    fn tampered_commit_is_invalid_and_always_rejected() {
        let key = ed25519_dalek::SigningKey::from_bytes(&[22u8; 32]);
        let mut c = signed_commit(&key);
        c.seq = 999; // tamper a signed field
        assert_eq!(verify_commit_author_sig(&c), CommitSigVerdict::Invalid);
        assert!(
            commit_import_check(false)(&c).is_err(),
            "invalid sig must reject even in observe mode"
        );
    }

    #[test]
    fn unsigned_verdict_gated_by_require_signed() {
        let key = ed25519_dalek::SigningKey::from_bytes(&[23u8; 32]);
        let mut c = signed_commit(&key);
        c.author_sig = None;
        assert_eq!(verify_commit_author_sig(&c), CommitSigVerdict::Unsigned);
        assert!(commit_import_check(false)(&c).is_ok(), "observe mode");
        assert!(commit_import_check(true)(&c).is_err(), "strict mode");
    }

    #[test]
    fn non_did_key_author_is_unverifiable() {
        let key = ed25519_dalek::SigningKey::from_bytes(&[24u8; 32]);
        let mut c = signed_commit(&key);
        c.author = "did:web:example.com".to_string();
        // Changing author also breaks the sig, but DID resolution fails FIRST.
        assert!(matches!(
            verify_commit_author_sig(&c),
            CommitSigVerdict::Unverifiable(_)
        ));
    }
}
