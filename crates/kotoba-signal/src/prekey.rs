use x25519_dalek::{StaticSecret, PublicKey as X25519Public};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use zeroize::ZeroizeOnDrop;
use crate::identity::IdentityKeyPair;

pub type PreKeyId      = u32;
pub type SignedPreKeyId = u32;

/// Ephemeral one-time pre-key (OPK).
#[derive(ZeroizeOnDrop)]
pub struct PreKey {
    pub id:      PreKeyId,
    pub private: StaticSecret,
}

/// Signed semi-static pre-key (SPK).
#[derive(ZeroizeOnDrop)]
pub struct SignedPreKey {
    pub id:        SignedPreKeyId,
    pub private:   StaticSecret,
    /// Ed25519 signature over the public SPK bytes.
    pub signature: Vec<u8>,
}

/// Public pre-key bundle shared during X3DH.
/// Corresponds to `ai.gftd.signal.getPrekeyBundle` response.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PreKeyBundle {
    /// DID of the bundle owner.
    pub did:               String,
    pub device_id:         String,
    /// Identity key (serialised `IdentityKey`).
    pub identity_key:      crate::identity::IdentityKey,
    /// Signed pre-key public bytes (32 bytes).
    pub signed_prekey:     Vec<u8>,
    pub signed_prekey_id:  SignedPreKeyId,
    /// Ed25519 signature of `signed_prekey` by `identity_key.signing`.
    pub signed_prekey_sig: Vec<u8>,
    /// Optional one-time pre-key public bytes.
    pub one_time_prekey:     Option<Vec<u8>>,
    pub one_time_prekey_id:  Option<PreKeyId>,
}

impl PreKey {
    pub fn generate(id: PreKeyId) -> Self {
        Self { id, private: StaticSecret::random_from_rng(OsRng) }
    }
    pub fn public_bytes(&self) -> [u8; 32] {
        X25519Public::from(&self.private).to_bytes()
    }
    pub fn dh(&self, remote: &[u8; 32]) -> [u8; 32] {
        self.private.diffie_hellman(&X25519Public::from(*remote)).to_bytes()
    }
}

impl SignedPreKey {
    pub fn generate(id: SignedPreKeyId, identity_kp: &IdentityKeyPair) -> Self {
        let private = StaticSecret::random_from_rng(OsRng);
        let pub_bytes = X25519Public::from(&private).to_bytes();
        let signature = identity_kp.sign(&pub_bytes);
        Self { id, private, signature }
    }
    pub fn public_bytes(&self) -> [u8; 32] {
        X25519Public::from(&self.private).to_bytes()
    }
    pub fn dh(&self, remote: &[u8; 32]) -> [u8; 32] {
        self.private.diffie_hellman(&X25519Public::from(*remote)).to_bytes()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::identity::IdentityKeyPair;

    #[test]
    fn signed_prekey_signature_verifies() {
        let ik = IdentityKeyPair::generate();
        let spk = SignedPreKey::generate(1, &ik);
        let pub_bytes = spk.public_bytes();
        assert!(ik.public_key().verify(&pub_bytes, &spk.signature));
    }
}
