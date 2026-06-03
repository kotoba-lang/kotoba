//! DID ↔ Signal identity binding + Signal-as-key-wrap-transport (ADR-2606014000 D4).
//!
//! Implements the verification side of the `app.etzhayyim.encrypted.signalIdentity`
//! lexicon: an actor publishes, in their own repo, a signed assertion of which
//! Signal `IdentityKey` is canonical for their DID. A peer MUST verify this
//! binding against the DID document's signing key **before** establishing an
//! X3DH session — otherwise a malicious PDS could substitute a Signal identity
//! and read the conversation (the gap ADR-2605181100 specified but never
//! enforced).
//!
//! Per-record symmetric keys are then wrapped under the *established Signal
//! session* (`wrap_record_key`), so each `app.etzhayyim.encrypted.keyWrap`
//! ciphertext inherits the Double Ratchet's forward secrecy and post-compromise
//! security — not a static key.

use crate::identity::IdentityKey;
use crate::prekey::PreKeyBundle;
use crate::ratchet::RatchetMessage;
use crate::session::Session;
use crate::SignalError;
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use kotoba_crypto::aead::CryptoError;
use serde::{Deserialize, Serialize};

/// Domain-separation tag for the binding signature (prevents cross-protocol reuse).
const BINDING_DOMAIN: &[u8] = b"kotoba/signal-identity-binding/v1";

/// A DID ↔ Signal identity binding (the verifiable core of
/// `app.etzhayyim.encrypted.signalIdentity`).
///
/// Note on key model: the lexicon's single `signalIdentityKey` field follows the
/// libsignal one-key model; kotoba's `IdentityKey` is a two-key pair (Ed25519
/// `signing` + X25519 `dh`). We bind **both** so the binding fully pins the
/// Signal identity used in X3DH. The binding signature itself is produced by the
/// actor's **DID** signing key — distinct from the Signal key it vouches for.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct SignalBinding {
    /// Self-DID; MUST equal the publishing repo owner.
    pub did: String,
    /// Signal IdentityKey Ed25519 signing public component (32 bytes).
    pub signal_identity_key: Vec<u8>,
    /// Signal IdentityKey X25519 DH public component (32 bytes).
    pub signal_dh_key: Vec<u8>,
    /// libsignal registration id (14-bit per Signal protocol).
    pub signal_registration_id: u32,
    /// RFC-3339 timestamp.
    pub created_at: String,
}

impl SignalBinding {
    /// Build a binding from a Signal `IdentityKey` public half.
    pub fn from_identity(
        did: impl Into<String>,
        ik: &IdentityKey,
        registration_id: u32,
        created_at: impl Into<String>,
    ) -> Self {
        Self {
            did: did.into(),
            signal_identity_key: ik.signing.clone(),
            signal_dh_key: ik.dh.clone(),
            signal_registration_id: registration_id,
            created_at: created_at.into(),
        }
    }

    /// Canonical, domain-separated, length-prefixed bytes that get signed.
    ///
    /// Length-prefixing every field makes the encoding unambiguous (no two
    /// distinct field sets can produce the same payload), which a bare
    /// concatenation would not guarantee.
    pub fn signing_payload(&self) -> Vec<u8> {
        let mut out = Vec::new();
        let mut push = |bytes: &[u8]| {
            out.extend_from_slice(&(bytes.len() as u32).to_be_bytes());
            out.extend_from_slice(bytes);
        };
        push(BINDING_DOMAIN);
        push(self.did.as_bytes());
        push(&self.signal_identity_key);
        push(&self.signal_dh_key);
        push(&self.signal_registration_id.to_be_bytes());
        push(self.created_at.as_bytes());
        out
    }

    /// Sign this binding with the actor's **DID** Ed25519 signing key (publisher side).
    pub fn sign(&self, did_signing_key: &SigningKey) -> Vec<u8> {
        did_signing_key.sign(&self.signing_payload()).to_bytes().to_vec()
    }

    /// Verify the binding signature against the DID document's Ed25519 public key.
    ///
    /// The caller MUST have resolved `did_pubkey` from the DID document **fresh**
    /// (mirrors `kotoba_auth::cacao::Cacao::verify_with_pubkey`). Returns `true`
    /// only if the signature is valid — i.e. the DID owner really vouches for
    /// this Signal identity.
    pub fn verify(&self, signature: &[u8], did_pubkey: &[u8; 32]) -> bool {
        let Ok(vk) = VerifyingKey::from_bytes(did_pubkey) else {
            return false;
        };
        let Ok(sig) = Signature::from_slice(signature) else {
            return false;
        };
        vk.verify(&self.signing_payload(), &sig).is_ok()
    }

    /// Does the identity advertised in a pre-key `bundle` match this binding?
    ///
    /// Call this after `verify` and before `Session::initiate`: it guarantees the
    /// bundle you are about to X3DH against carries the *same* Signal identity the
    /// DID owner signed, closing the substitution gap.
    pub fn matches_bundle(&self, bundle: &PreKeyBundle) -> bool {
        bundle.identity_key.signing == self.signal_identity_key
            && bundle.identity_key.dh == self.signal_dh_key
    }
}

/// Wrap a 32-byte record key under an established Signal session — the ciphertext
/// for an `app.etzhayyim.encrypted.keyWrap` record. Forward secrecy and
/// post-compromise security come from the underlying Double Ratchet
/// (ADR-2606014000 D4): each wrap advances the ratchet, so compromising one
/// wrap key does not expose past or future record keys.
pub fn wrap_record_key(
    session: &mut Session,
    record_key: &[u8; 32],
) -> Result<RatchetMessage, SignalError> {
    session.encrypt(record_key)
}

/// Unwrap a record key produced by `wrap_record_key` on the recipient side.
pub fn unwrap_record_key(
    session: &mut Session,
    msg: &RatchetMessage,
) -> Result<[u8; 32], SignalError> {
    let pt = session.decrypt(msg)?;
    pt.as_slice()
        .try_into()
        .map_err(|_| SignalError::Crypto(CryptoError::OpenFailed))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::identity::IdentityKeyPair;
    use crate::prekey::{PreKey, PreKeyBundle, SignedPreKey};
    use ed25519_dalek::SigningKey;

    fn did_key() -> SigningKey {
        SigningKey::from_bytes(&[7u8; 32])
    }

    #[test]
    fn binding_sign_verify_roundtrip() {
        let did = "did:web:etzhayyim.com:actor:alice";
        let sig_ik = IdentityKeyPair::generate();
        let binding = SignalBinding::from_identity(did, &sig_ik.public_key(), 4242, "2026-06-01T00:00:00Z");

        let did_sk = did_key();
        let sig = binding.sign(&did_sk);
        let did_pub = did_sk.verifying_key().to_bytes();

        assert!(binding.verify(&sig, &did_pub), "valid binding must verify");
    }

    #[test]
    fn binding_verify_rejects_wrong_did_key() {
        let sig_ik = IdentityKeyPair::generate();
        let binding = SignalBinding::from_identity("did:web:b", &sig_ik.public_key(), 1, "2026-06-01T00:00:00Z");
        let sig = binding.sign(&did_key());
        // A different DID key (attacker / malicious PDS) must not validate.
        let wrong_pub = SigningKey::from_bytes(&[9u8; 32]).verifying_key().to_bytes();
        assert!(!binding.verify(&sig, &wrong_pub));
    }

    #[test]
    fn binding_verify_rejects_tampered_identity_key() {
        let sig_ik = IdentityKeyPair::generate();
        let did_sk = did_key();
        let binding = SignalBinding::from_identity("did:web:c", &sig_ik.public_key(), 1, "t");
        let sig = binding.sign(&did_sk);

        // Swap the bound Signal key — signature must no longer match.
        let mut tampered = binding.clone();
        tampered.signal_identity_key = IdentityKeyPair::generate().public_key().signing;
        assert!(!tampered.verify(&sig, &did_sk.verifying_key().to_bytes()));
    }

    #[test]
    fn binding_verify_rejects_wrong_length_signature() {
        let sig_ik = IdentityKeyPair::generate();
        let did_sk = did_key();
        let binding = SignalBinding::from_identity("did:web:d", &sig_ik.public_key(), 1, "t");
        // A 32-byte (wrong-length) signature must be rejected, not panic.
        assert!(!binding.verify(&[0u8; 32], &did_sk.verifying_key().to_bytes()));
        assert!(!binding.verify(&[], &did_sk.verifying_key().to_bytes()));
    }

    #[test]
    fn binding_verify_rejects_invalid_pubkey_point() {
        let sig_ik = IdentityKeyPair::generate();
        let binding = SignalBinding::from_identity("did:web:e", &sig_ik.public_key(), 1, "t");
        let sig = binding.sign(&did_key());
        // An all-0xFF buffer is not a canonical Ed25519 point → verify returns false.
        assert!(!binding.verify(&sig, &[0xFFu8; 32]));
    }

    #[test]
    fn signing_payload_is_field_unambiguous() {
        let ik = IdentityKeyPair::generate().public_key();
        let a = SignalBinding::from_identity("did:web:a", &ik, 1, "t");
        let b = SignalBinding::from_identity("did:web:ab", &ik, 1, "t");
        // Length-prefixing must make these distinct (no field-boundary collision).
        assert_ne!(a.signing_payload(), b.signing_payload());
        // Determinism.
        assert_eq!(a.signing_payload(), a.signing_payload());
        // registrationId is part of the payload.
        let c = SignalBinding::from_identity("did:web:a", &ik, 2, "t");
        assert_ne!(a.signing_payload(), c.signing_payload());
    }

    #[test]
    fn matches_bundle_rejects_dh_mismatch() {
        let did = "did:plc:carol";
        let ik = IdentityKeyPair::generate();
        let spk = SignedPreKey::generate(1, &ik);
        let bundle = PreKeyBundle {
            did: did.into(),
            device_id: "dev".into(),
            identity_key: ik.public_key(),
            signed_prekey: spk.public_bytes().to_vec(),
            signed_prekey_id: spk.id,
            signed_prekey_sig: spk.signature.clone(),
            one_time_prekey: None,
            one_time_prekey_id: None,
        };
        // Same signing key as the bundle, but a DIFFERENT dh key → must not match.
        let mut binding = SignalBinding::from_identity(did, &ik.public_key(), 1, "t");
        binding.signal_dh_key = IdentityKeyPair::generate().public_key().dh;
        assert!(!binding.matches_bundle(&bundle), "dh mismatch must be rejected");
    }

    #[test]
    fn matches_bundle_detects_substitution() {
        let did = "did:plc:bob";
        let bob_ik = IdentityKeyPair::generate();
        let bob_spk = SignedPreKey::generate(1, &bob_ik);
        let bundle = PreKeyBundle {
            did: did.into(),
            device_id: "dev-1".into(),
            identity_key: bob_ik.public_key(),
            signed_prekey: bob_spk.public_bytes().to_vec(),
            signed_prekey_id: bob_spk.id,
            signed_prekey_sig: bob_spk.signature.clone(),
            one_time_prekey: None,
            one_time_prekey_id: None,
        };

        let good = SignalBinding::from_identity(did, &bob_ik.public_key(), 1, "t");
        assert!(good.matches_bundle(&bundle), "honest bundle must match binding");

        // Attacker substitutes a different identity key in the bundle.
        let evil_ik = IdentityKeyPair::generate();
        assert!(
            !SignalBinding::from_identity(did, &evil_ik.public_key(), 1, "t").matches_bundle(&bundle),
            "substituted Signal identity must be rejected"
        );
    }

    #[test]
    fn wrap_unwrap_record_key_over_real_session() {
        // Establish a real Signal session (X3DH + Double Ratchet), then use it to
        // wrap a 32-byte record key — the keyWrap transport.
        let alice_ik = IdentityKeyPair::generate();
        let bob_ik = IdentityKeyPair::generate();
        let bob_spk = SignedPreKey::generate(1, &bob_ik);
        let bob_opk = PreKey::generate(100);
        let bundle = PreKeyBundle {
            did: "did:plc:bob".into(),
            device_id: "dev-1".into(),
            identity_key: bob_ik.public_key(),
            signed_prekey: bob_spk.public_bytes().to_vec(),
            signed_prekey_id: bob_spk.id,
            signed_prekey_sig: bob_spk.signature.clone(),
            one_time_prekey: Some(bob_opk.public_bytes().to_vec()),
            one_time_prekey_id: Some(bob_opk.id),
        };

        let (mut alice, ep_bytes) = Session::initiate(&alice_ik, &bundle).unwrap();
        let ep: [u8; 32] = ep_bytes.try_into().unwrap();
        let mut bob = Session::accept(
            &bob_ik,
            &bob_spk,
            Some(&bob_opk),
            &alice_ik.public_key(),
            &ep,
            "did:plc:alice",
            "dev-a",
        )
        .unwrap();

        let record_key = [0x5Au8; 32];
        let wrapped = wrap_record_key(&mut alice, &record_key).unwrap();
        let unwrapped = unwrap_record_key(&mut bob, &wrapped).unwrap();
        assert_eq!(unwrapped, record_key, "record key survives the Signal wrap transport");
    }
}
